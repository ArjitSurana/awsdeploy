#!/bin/bash
# Optional EC2 "User data" script (Amazon Linux 2023).
# Paste into: Launch instance → Advanced → User data (paste as text).
# Replace REPO_URL with your GitHub repo before use.

set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/ArjitSurana/awsdeploy.git}"
APP_DIR="/home/ec2-user/FoodAIProject"

dnf update -y
dnf install -y git

sudo -u ec2-user git clone "$REPO_URL" "$APP_DIR" || true
cd "$APP_DIR"
chmod +x deploy/setup_ec2.sh
./deploy/setup_ec2.sh
