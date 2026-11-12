#!/bin/bash
# Update a running EC2 deployment: pull the branch, rebuild changed images and restart.
# Usage on the instance:  cd /opt/joblab && bash deploy/aws/deploy.sh [branch]
set -euo pipefail
cd "$(dirname "$0")/../.."
BRANCH="${1:-main}"

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
# The Elastic IP is attached after launch: refresh DJANGO_ALLOWED_HOSTS every deploy.
bash deploy/aws/configure-env.sh
docker compose up -d --build --remove-orphans
docker image prune -f
docker compose ps
bash deploy/aws/smoke-test.sh "http://127.0.0.1"
