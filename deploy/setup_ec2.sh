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

echo "==> Java (Amazon Corretto 17)"
JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(which java)")")")"
export JAVA_HOME
if ! grep -q "^JAVA_HOME=" /etc/environment 2>/dev/null; then
  echo "JAVA_HOME=$JAVA_HOME" | sudo tee -a /etc/environment
fi

echo "==> App directory: $APP_DIR"
cd "$APP_DIR"

echo "==> Python venv"
$PY -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> PySpark Python paths"
PY_EXEC="$APP_DIR/venv/bin/python"
if ! grep -q "^PYSPARK_PYTHON=" /etc/environment 2>/dev/null; then
  echo "PYSPARK_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
  echo "PYSPARK_DRIVER_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
fi

if [ ! -f .env ]; then
  echo "WARNING: Create $APP_DIR/.env with GOOGLE_API_KEY=..."
fi

echo "==> systemd service"
sudo cp deploy/snapmeal.service /etc/systemd/system/snapmeal.service
sudo sed -i "s|/home/ec2-user/FoodAIProject|$APP_DIR|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|User=ec2-user|User=$APP_USER|g" /etc/systemd/system/snapmeal.service
sudo sed -i "s|JAVA_HOME=.*|JAVA_HOME=$JAVA_HOME|g" /etc/systemd/system/snapmeal.service
sudo systemctl daemon-reload
sudo systemctl enable snapmeal
sudo systemctl restart snapmeal

echo "==> nginx (conf.d — Amazon Linux layout)"
sudo cp deploy/nginx-snapmeal.conf /etc/nginx/conf.d/snapmeal.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "==> SELinux: allow nginx to proxy to Streamlit"
if command -v getenforce >/dev/null 2>&1 && [ "$(getenforce)" != "Disabled" ]; then
  sudo setsebool -P httpd_can_network_connect 1 || true
fi

echo "==> Done. Check: sudo systemctl status snapmeal"
