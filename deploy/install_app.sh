#!/bin/bash
# Run on EC2 (Session Manager) after backend/ and deploy/ are in /opt/cloudcart
set -e
sudo dnf install -y python3 python3-pip
cd /opt/cloudcart/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo cp /opt/cloudcart/deploy/cloudcart.service /etc/systemd/system/cloudcart.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudcart
sleep 3
curl -i http://127.0.0.1:5000/health
