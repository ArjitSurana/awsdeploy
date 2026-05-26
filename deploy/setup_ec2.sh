#!/bin/bash
# Amazon Linux 2023 EC2 — run as ec2-user after cloning the repo.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ec2-user/FoodAIProject}"
APP_USER="${APP_USER:-ec2-user}"
PY="${PY:-python3}"

echo "==> System packages (Amazon Linux 2023)"
sudo dnf update -y
sudo dnf install -y \
  python3 python3-pip \
  git nginx \
  java-17-amazon-corretto \
  gcc python3-devel

echo "==> Java"
JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(which java)")")")"
export JAVA_HOME
if ! grep -q "^JAVA_HOME=" /etc/environment 2>/dev/null; then
  echo "JAVA_HOME=$JAVA_HOME" | sudo tee -a /etc/environment
fi

echo "==> Disk space (PySpark pip install needs ~30 GB root volume, 4+ GB free)"
df -h /
AVAIL_MB=$(df / --output=avail -m 2>/dev/null | tail -1 | tr -d ' ')
if [ -n "${AVAIL_MB:-}" ] && [ "$AVAIL_MB" -lt 4000 ]; then
  echo "ERROR: Need 4+ GB free. Expand EBS to 30 GB, then: sudo growpart /dev/nvme0n1 1 && sudo xfs_growfs -d /"
  exit 1
fi

sudo dnf clean all
rm -rf ~/.cache/pip /tmp/pip-* /tmp/build-* 2>/dev/null || true

echo "==> App directory: $APP_DIR"
cd "$APP_DIR"

echo "==> Python venv + PySpark"
$PY -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
mkdir -p "$HOME/pip_build"
export TMPDIR="$HOME/pip_build"
pip install --no-cache-dir -r requirements.txt

PY_EXEC="$APP_DIR/venv/bin/python"
grep -q "^PYSPARK_PYTHON=" /etc/environment 2>/dev/null || {
  echo "PYSPARK_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
  echo "PYSPARK_DRIVER_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
}

if [ ! -f .env ]; then
  echo "WARNING: Create $APP_DIR/.env with GOOGLE_API_KEY=..."
fi

echo "==> systemd service"
sudo cp deploy/snapmeal.service /etc/systemd/system/snapmeal.service
sudo sed -i "s|/home/ec2-user/FoodAIProject|$APP_DIR|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|User=ec2-user|User=$APP_USER|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|JAVA_HOME=.*|JAVA_HOME=$JAVA_HOME|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|PYSPARK_PYTHON=.*|PYSPARK_PYTHON=$PY_EXEC|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|PYSPARK_DRIVER_PYTHON=.*|PYSPARK_DRIVER_PYTHON=$PY_EXEC|g" /etc/systemd/system/snapmeal.service
sudo systemctl daemon-reload
sudo systemctl enable snapmeal
sudo systemctl restart snapmeal

echo "==> nginx"
sudo cp deploy/nginx-snapmeal.conf /etc/nginx/conf.d/snapmeal.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

if command -v getenforce >/dev/null 2>&1 && [ "$(getenforce)" != "Disabled" ]; then
  sudo setsebool -P httpd_can_network_connect 1 || true
fi

echo "==> Done. Check: sudo systemctl status snapmeal"
