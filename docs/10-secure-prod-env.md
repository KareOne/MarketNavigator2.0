# Secure Production Environment Storage - MarketNavigator v2

## Purpose
Best practices for storing and managing production secrets securely on Ubuntu servers, including file permissions, encryption, access controls, and secret rotation procedures.

---

## Production Secret Storage Strategy

### Option 1: Encrypted .env File (Simple, Recommended for Small Teams)

#### Setup

```bash
# SSH to production server
ssh user@production-server
cd /opt/marketnavigator/MarketNavigator2.0

# Create .env file with production secrets
nano .env
# (paste production values)

# Set restrictive permissions
chmod 600 .env
chown $USER:$USER .env

# Verify permissions
ls -l .env
# Should show: -rw------- (only owner can read/write)

# Verify ownership
stat .env | grep "Access:"
# Should show your user as owner
```

#### Encrypt .env File (Additional Security)

```bash
# Install GPG
sudo apt install gnupg

# Create encryption key
gpg --gen-key
# Follow prompts to create key

# Encrypt .env file
gpg --encrypt --recipient your-email@example.com .env
# Creates: .env.gpg

# Move original to secure location
sudo mv .env /root/.env.backup
sudo chmod 600 /root/.env.backup

# To decrypt when needed
gpg --decrypt .env.gpg > .env
chmod 600 .env

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Delete decrypted .env after services start (optional)
# WARNING: You'll need it if containers restart
shred -u .env  # Secure delete
```

---

### Option 2: Docker Secrets (Swarm Mode)

#### Convert to Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Create secrets
echo "your-secret-key" | docker secret create django_secret_key -
echo "your-db-password" | docker secret create db_password -
echo "your-aws-key" | docker secret create aws_secret_key -

# List secrets
docker secret ls

# View secret (can't view content)
docker secret inspect django_secret_key
```

#### Update docker-compose.yml for Secrets

```yaml
version: '3.8'

services:
  backend:
    image: marketnavigator/backend:latest
    secrets:
      - django_secret_key
      - db_password
      - aws_secret_key
    environment:
      - SECRET_KEY_FILE=/run/secrets/django_secret_key
      - DB_PASSWORD_FILE=/run/secrets/db_password
      - AWS_SECRET_ACCESS_KEY_FILE=/run/secrets/aws_secret_key

secrets:
  django_secret_key:
    external: true
  db_password:
    external: true
  aws_secret_key:
    external: true
```

#### Update Django to Read from Secret Files

```python
# backend/config/settings.py
import os

def read_secret(secret_name):
    """Read Docker secret from /run/secrets/"""
    try:
        with open(f'/run/secrets/{secret_name}', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback to environment variable
        return os.getenv(secret_name.upper())

# Use secrets
SECRET_KEY = read_secret('django_secret_key') or os.getenv('SECRET_KEY')
DB_PASSWORD = read_secret('db_password') or os.getenv('DB_PASSWORD')
```

---

### Option 3: HashiCorp Vault (Enterprise-Grade)

#### Install Vault

```bash
# Install Vault
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update && sudo apt install vault

# Start Vault server (dev mode - NOT for production)
vault server -dev

# For production, use proper server config
vault server -config=/etc/vault/config.hcl
```

#### Store Secrets in Vault

```bash
# Set Vault address
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='<root-token-from-init>'

# Enable kv secrets engine
vault secrets enable -path=marketnavigator kv-v2

# Store secrets
vault kv put marketnavigator/production \
  secret_key="your-secret-key" \
  db_password="your-db-password" \
  aws_secret_key="your-aws-key"

# Read secret
vault kv get marketnavigator/production
```

#### Integrate with Docker Compose

```yaml
services:
  backend:
    image: marketnavigator/backend:latest
    environment:
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}
      - VAULT_PATH=marketnavigator/production
    command: >
      sh -c "
        vault kv get -field=secret_key marketnavigator/production > /tmp/secret_key &&
        vault kv get -field=db_password marketnavigator/production > /tmp/db_password &&
        export SECRET_KEY=$(cat /tmp/secret_key) &&
        export DB_PASSWORD=$(cat /tmp/db_password) &&
        python manage.py runserver
      "
```

---

## File Permission Hardening

### Secure .env File

```bash
# Set ownership to deployment user
sudo chown deployuser:deployuser .env

# Remove all permissions except owner read/write
chmod 600 .env

# Verify
ls -l .env
# Output: -rw------- 1 deployuser deployuser 2048 Dec 31 10:00 .env

# Prevent accidental deletion
sudo chattr +i .env  # Make immutable
sudo chattr -i .env  # Remove immutable when you need to edit
```

### Secure Docker Compose Files

```bash
# docker-compose.yml (can be world-readable)
chmod 644 docker-compose.yml

# docker-compose.prod.yml (restrict if contains secrets)
chmod 600 docker-compose.prod.yml

# Scraper environment files
chmod 600 scrapers/Crunchbase_API/.env
chmod 600 scrapers/Tracxn_API/config.py

# SSL certificates
chmod 600 nginx/ssl/*.pem
chmod 600 nginx/ssl/*.key
```

### Secure Project Directory

```bash
# Set directory ownership
sudo chown -R deployuser:deployuser /opt/marketnavigator/MarketNavigator2.0

# Set directory permissions (755 = rwxr-xr-x)
find /opt/marketnavigator/MarketNavigator2.0 -type d -exec chmod 755 {} \;

# Set file permissions (644 = rw-r--r--)
find /opt/marketnavigator/MarketNavigator2.0 -type f -exec chmod 644 {} \;

# Exception: Scripts should be executable
chmod +x scripts/*.sh

# Exception: Sensitive files (600)
chmod 600 .env scrapers/*/.env nginx/ssl/*
```

---

## Access Control

### User Separation

```bash
# Create dedicated deployment user
sudo adduser deployuser --disabled-password

# Add to docker group
sudo usermod -aG docker deployuser

# Set up SSH key authentication
sudo -u deployuser mkdir -p /home/deployuser/.ssh
sudo -u deployuser chmod 700 /home/deployuser/.ssh

# Copy your public key
sudo -u deployuser nano /home/deployuser/.ssh/authorized_keys
# Paste your SSH public key
sudo -u deployuser chmod 600 /home/deployuser/.ssh/authorized_keys

# Test SSH access
ssh deployuser@production-server
```

### Restrict Root Access

```bash
# Disable direct root login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no

# Restart SSH
sudo systemctl restart sshd

# Use sudo for admin tasks
# deployuser can use sudo without password for docker
sudo visudo
# Add: deployuser ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose
```

### Audit Access

```bash
# Check who accessed .env file
sudo ausearch -f /opt/marketnavigator/MarketNavigator2.0/.env

# Enable file access auditing
sudo apt install auditd
sudo auditctl -w /opt/marketnavigator/MarketNavigator2.0/.env -p rwa -k env_access

# View audit logs
sudo ausearch -k env_access
```

---

## Secret Rotation Procedures

### Rotate Django SECRET_KEY

```bash
# 1. Generate new secret
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")

# 2. Backup current .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 3. Update .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env

# 4. Restart services (forces re-encryption of sessions)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# 5. Verify
docker exec mn2-backend python manage.py shell -c "from django.conf import settings; print(len(settings.SECRET_KEY))"
# Should output: 68 (or similar length)

# 6. Note: All users will be logged out (sessions invalidated)
```

### Rotate Database Password

```bash
# 1. Change password on database server
# (Liara dashboard → PostgreSQL → Change Password)

# 2. Update .env
nano .env
# Update DB_PASSWORD=new_password

# 3. Test connection
docker exec mn2-backend python manage.py dbshell
# Should connect successfully

# 4. Restart services
docker-compose restart backend celery-worker celery-beat
```

### Rotate MinIO Credentials

```bash
# 1. Access MinIO console
# Open http://YOUR_SERVER:9001
# Login with current credentials

# 2. Create new access key
# Settings → Service Accounts → Create New

# 3. Update .env
nano .env
# Update:
# AWS_ACCESS_KEY_ID=new_access_key
# AWS_SECRET_ACCESS_KEY=new_secret_key

# 4. Restart services
docker-compose restart backend celery-worker

# 5. Revoke old access key in MinIO console

# 6. Test file upload
docker exec mn2-backend python manage.py shell -c "
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
default_storage.save('test.txt', ContentFile(b'test'))
print('Upload successful')
"
```

### Rotate AI API Keys

```bash
# 1. Generate new keys from providers:
# - OpenAI: https://platform.openai.com/api-keys
# - Liara: https://console.liara.ir/api-keys
# - Metis: https://metisai.ir/dashboard/api-keys

# 2. Update .env
nano .env
# Update:
# OPENAI_API_KEY=sk-new-key
# LIARA_API_KEY=eyJ-new-token
# METIS_API_KEY=tpsg-new-key

# 3. Restart Celery workers (they use AI services)
docker-compose restart celery-worker

# 4. Test AI functionality
docker exec mn2-celery-worker python manage.py shell -c "
from services.openai_service import OpenAIService
service = OpenAIService()
response = service.generate_text('Hello')
print('AI service working:', bool(response))
"

# 5. Revoke old keys from provider dashboards
```

---

## Backup and Recovery

### Backup Production Secrets

```bash
# Encrypt and backup .env
gpg --encrypt --recipient admin@company.com .env

# Upload to secure location
scp .env.gpg backup-server:/backups/marketnavigator/$(date +%Y%m%d).env.gpg

# Store GPG key securely (not on server!)
# Export: gpg --export-secret-keys admin@company.com > private-key.asc
# Encrypt: gpg -c private-key.asc
# Store in password manager or encrypted USB drive
```

### Recovery Procedure

```bash
# Download encrypted backup
scp backup-server:/backups/marketnavigator/20251231.env.gpg /tmp/

# Decrypt
gpg --decrypt /tmp/20251231.env.gpg > /opt/marketnavigator/MarketNavigator2.0/.env

# Set permissions
chmod 600 /opt/marketnavigator/MarketNavigator2.0/.env

# Restart services
cd /opt/marketnavigator/MarketNavigator2.0
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

---

## Monitoring and Alerts

### File Integrity Monitoring

```bash
# Install AIDE (Advanced Intrusion Detection Environment)
sudo apt install aide

# Configure AIDE to monitor .env
sudo nano /etc/aide/aide.conf
# Add: /opt/marketnavigator/MarketNavigator2.0/.env R+b+sha256

# Initialize database
sudo aideinit

# Check for changes daily (cron)
sudo crontab -e
# Add: 0 2 * * * /usr/bin/aide --check && /usr/bin/logger "AIDE check passed" || /usr/bin/logger "AIDE check FAILED"
```

### Failed Access Alerts

```bash
# Monitor failed sudo attempts
sudo nano /etc/rsyslog.d/50-sudo.conf
# Add:
# :msg, contains, "sudo" /var/log/sudo.log
# :msg, contains, "sudo" @log-server:514

# Restart rsyslog
sudo systemctl restart rsyslog

# Set up log alert (example using email)
sudo apt install mailutils
echo '#!/bin/bash
tail -n 50 /var/log/auth.log | grep "Failed password" && echo "Failed login attempts" | mail -s "Security Alert" admin@company.com
' | sudo tee /usr/local/bin/alert-failed-logins.sh
sudo chmod +x /usr/local/bin/alert-failed-logins.sh

# Run hourly
echo "0 * * * * /usr/local/bin/alert-failed-logins.sh" | sudo crontab -
```

---

## Compliance Checklist

### Before Production Deploy

- [ ] `.env` file has 600 permissions (owner read/write only)
- [ ] `.env` owned by deployment user (not root)
- [ ] No secrets hardcoded in docker-compose.yml
- [ ] All secrets > 20 characters random
- [ ] Database password changed from default
- [ ] MinIO password changed from default
- [ ] Django SECRET_KEY is production-grade (50+ chars)
- [ ] SSH key authentication enabled
- [ ] Root SSH login disabled
- [ ] Firewall configured (only 80/443 open)
- [ ] Fail2ban installed (brute-force protection)
- [ ] Backup procedure documented and tested
- [ ] Secret rotation schedule defined

### Monthly Security Tasks

- [ ] Review access logs for suspicious activity
- [ ] Verify file permissions haven't changed
- [ ] Check for failed login attempts
- [ ] Rotate API keys (if >90 days old)
- [ ] Update all system packages
- [ ] Review Docker image versions
- [ ] Test backup restoration
- [ ] Audit user access (remove departed team members)

---

## Common Security Mistakes

### ❌ Mistake 1: World-Readable .env

```bash
# BAD
-rw-r--r-- 1 user user 2048 Dec 31 .env
# Anyone on server can read secrets!
```

**Fix:**
```bash
chmod 600 .env
```

### ❌ Mistake 2: Secrets in Docker Compose

```yaml
# BAD - Secrets visible in Git
services:
  backend:
    environment:
      - SECRET_KEY=hardcoded-secret-key-abc123
```

**Fix:**
```yaml
# GOOD - Reference from .env
services:
  backend:
    environment:
      - SECRET_KEY=${SECRET_KEY}
```

### ❌ Mistake 3: Using Root User

```bash
# BAD - Running as root
sudo docker-compose up -d
```

**Fix:**
```bash
# GOOD - Run as unprivileged user
# Add user to docker group
sudo usermod -aG docker deployuser
# Run as deployuser
su - deployuser
docker-compose up -d
```

### ❌ Mistake 4: No Backup Encryption

```bash
# BAD - Unencrypted backup
scp .env backup-server:/backups/
```

**Fix:**
```bash
# GOOD - Encrypted backup
gpg --encrypt --recipient admin@company.com .env
scp .env.gpg backup-server:/backups/
```

---

## Quick Reference Commands

```bash
# Check file permissions
ls -l .env
stat .env

# Set secure permissions
chmod 600 .env
chown deployuser:deployuser .env

# Encrypt file
gpg --encrypt --recipient admin@example.com .env

# Decrypt file
gpg --decrypt .env.gpg > .env

# Verify no secrets in Git
git log -p .env | grep -i "password\|api.key\|secret"

# Rotate secret
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env

# Audit file access
sudo ausearch -f /opt/marketnavigator/MarketNavigator2.0/.env

# Test database connection
docker exec mn2-backend python manage.py dbshell
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Security Team  
**Review Schedule:** Quarterly + After any security incident  
**Secret Rotation:** Every 90 days
