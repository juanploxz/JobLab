#!/bin/bash
# Create .env from .env.example with a random secret, a random DB password and the public IP.
# Safe to re-run: an existing .env is kept, only the allowed hosts are refreshed.
set -euo pipefail
cd "$(dirname "$0")/../.."

metadata() {
    local token
    token=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
    curl -fsS -H "X-aws-ec2-metadata-token: ${token}" \
        "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || true
}

PUBLIC_IP="${PUBLIC_IP:-$(metadata public-ipv4)}"
PUBLIC_HOST="${PUBLIC_HOST:-$(metadata public-hostname)}"

if [ ! -f .env ]; then
    cp .env.example .env
    SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${SECRET}|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" .env
fi

HOSTS="localhost,127.0.0.1,django"
[ -n "$PUBLIC_IP" ] && HOSTS="${HOSTS},${PUBLIC_IP}"
[ -n "$PUBLIC_HOST" ] && HOSTS="${HOSTS},${PUBLIC_HOST}"
[ -n "${EXTRA_HOSTS:-}" ] && HOSTS="${HOSTS},${EXTRA_HOSTS}"
sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=${HOSTS}|" .env

echo "DJANGO_ALLOWED_HOSTS=${HOSTS}"
