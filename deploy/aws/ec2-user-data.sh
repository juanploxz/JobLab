#!/bin/bash
# EC2 "User data" script for Amazon Linux 2023 (AWS Academy Learner Lab).
# Installs Docker + Compose, adds swap, clones JobLab and starts the whole ecosystem.
# Paste it in: EC2 > Launch instance > Advanced details > User data.
# Progress log on the instance: sudo tail -f /var/log/joblab-bootstrap.log
set -euxo pipefail
exec > >(tee -a /var/log/joblab-bootstrap.log) 2>&1

REPO_URL="${REPO_URL:-https://github.com/juanploxz/JobLab.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="/opt/joblab"
COMPOSE_VERSION="v2.29.7"

dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

# Docker Compose v2 plugin.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 2 GB of swap so small instances can build the images.
if [ ! -f /swapfile ]; then
    dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "/swapfile swap swap defaults 0 0" >> /etc/fstab
fi

if [ ! -d "$APP_DIR/.git" ]; then
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
bash deploy/aws/configure-env.sh
docker compose up -d --build
chown -R ec2-user:ec2-user "$APP_DIR"
