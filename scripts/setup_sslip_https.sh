#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PUBLIC_IP="${PUBLIC_IP:-}"
if [ -z "$PUBLIC_IP" ]; then
  TOKEN="$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)"
  if [ -n "$TOKEN" ]; then
    PUBLIC_IP="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
      http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
  fi
fi

if [ -z "$PUBLIC_IP" ]; then
  PUBLIC_IP="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
fi

DOMAIN="${SSLIP_DOMAIN:-${PUBLIC_IP//./-}.sslip.io}"
EMAIL="${LETSENCRYPT_EMAIL:-}"

echo "Public IP: $PUBLIC_IP"
echo "HTTPS domain: $DOMAIN"

mkdir -p deploy/certbot/www deploy/certbot/conf

echo "Starting HTTP Nginx for ACME challenge..."
docker compose up -d nginx

CERTBOT_ARGS=(
  certonly
  --webroot
  --webroot-path /var/www/certbot
  --domain "$DOMAIN"
  --agree-tos
  --non-interactive
)

if [ -n "$EMAIL" ]; then
  CERTBOT_ARGS+=(--email "$EMAIL" --no-eff-email)
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi

echo "Requesting Let's Encrypt certificate..."
docker run --rm \
  -v "$PROJECT_ROOT/deploy/certbot/conf:/etc/letsencrypt" \
  -v "$PROJECT_ROOT/deploy/certbot/www:/var/www/certbot" \
  certbot/certbot:latest "${CERTBOT_ARGS[@]}"

echo "Writing HTTPS Nginx config..."
sed "s/copilot.example.com/$DOMAIN/g" nginx/https.conf.example > nginx/default.conf

echo "Restarting Nginx with HTTPS..."
docker compose up -d nginx
docker compose exec nginx nginx -s reload || docker compose restart nginx

cat <<EOF

HTTPS is configured.

Open this on your phone:
  https://$DOMAIN

If the page does not load, check that the EC2 security group allows inbound 80 and 443.
EOF
