#!/bin/bash
# MarketNavigator v2 - SSL Certificate Setup Script
# For Liara Virtual Server (Raw Linux VPS)
# Run this script on your production server after deploying

set -e

DOMAIN="market.kareonecompany.com"
EMAIL="admin@kareonecompany.com"  # Change this to your email

echo "================================================"
echo "MarketNavigator v2 - SSL Certificate Setup"
echo "Domain: $DOMAIN"
echo "================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./scripts/setup-ssl.sh"
    exit 1
fi

# Step 1: Install certbot if not installed
echo ""
echo "[Step 1] Installing Certbot..."
if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu
    apt-get update
    apt-get install -y certbot
elif command -v yum &> /dev/null; then
    # CentOS/RHEL
    yum install -y epel-release
    yum install -y certbot
elif command -v dnf &> /dev/null; then
    # Fedora
    dnf install -y certbot
else
    echo "Could not detect package manager. Please install certbot manually."
    exit 1
fi

# Step 2: Create directories
echo ""
echo "[Step 2] Creating directories..."
mkdir -p ./nginx/ssl
mkdir -p /var/www/certbot

# Step 3: Generate temporary self-signed certificate (allows nginx to start)
echo ""
echo "[Step 3] Generating temporary self-signed certificate..."
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
    -keyout ./nginx/ssl/privkey.pem \
    -out ./nginx/ssl/fullchain.pem \
    -subj "/CN=$DOMAIN"

# Step 4: Start nginx with temporary cert
echo ""
echo "[Step 4] Starting nginx..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx

# Wait for nginx to start
sleep 5

# Step 5: Stop nginx temporarily for standalone mode
echo ""
echo "[Step 5] Stopping nginx for certificate issuance..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop nginx

# Step 6: Obtain Let's Encrypt certificate using standalone mode
echo ""
echo "[Step 6] Obtaining Let's Encrypt certificate..."
certbot certonly --standalone \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

# Step 7: Copy certificates to nginx directory
echo ""
echo "[Step 7] Copying certificates..."
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ./nginx/ssl/fullchain.pem
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ./nginx/ssl/privkey.pem
chmod 644 ./nginx/ssl/fullchain.pem
chmod 600 ./nginx/ssl/privkey.pem

# Step 8: Restart all services
echo ""
echo "[Step 8] Starting all services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo ""
echo "================================================"
echo "✅ SSL Setup Complete!"
echo ""
echo "Your site is now available at: https://$DOMAIN"
echo ""
echo "Certificate auto-renewal: Add this to crontab:"
echo "0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/*.pem $(pwd)/nginx/ssl/ && docker-compose restart nginx"
echo "================================================"

