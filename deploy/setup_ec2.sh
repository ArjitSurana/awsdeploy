#!/bin/bash
# Run on Ubuntu 22.04 EC2 as ubuntu user (after cloning the repo).
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/FoodAIProject}"
PY="${PY:-python3}"

echo "==> System packages"
sudo apt-get update -y
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  openjdk-17-jdk \
  nginx \
  git

echo "==> Java"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
grep -q JAVA_HOME /etc/environment || echo "JAVA_HOME=$JAVA_HOME" | sudo tee -a /etc/environment

echo "==> App directory: $APP_DIR"
cd "$APP_DIR"

echo "==> Python venv"
$PY -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> PySpark Python paths"
PY_EXEC="$(which python)"
grep -q PYSPARK_PYTHON /etc/environment || {
  echo "PYSPARK_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
  echo "PYSPARK_DRIVER_PYTHON=$PY_EXEC" | sudo tee -a /etc/environment
}

if [ ! -f .env ]; then
  echo "WARNING: Create $APP_DIR/.env with GOOGLE_API_KEY=..."
fi

echo "==> systemd service"
sudo cp deploy/snapmeal.service /etc/systemd/system/snapmeal.service
sudo sed -i "s|/home/ubuntu/FoodAIProject|$APP_DIR|g" /etc/systemd/system/snapmeal.service
sudo systemctl daemon-reload
sudo systemctl enable snapmeal
sudo systemctl restart snapmeal

echo "==> nginx"
sudo cp deploy/nginx-snapmeal.conf /etc/nginx/sites-available/snapmeal
sudo ln -sf /etc/nginx/sites-available/snapmeal /etc/nginx/sites-enabled/snapmeal
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "==> Done. Check: sudo systemctl status snapmeal"
