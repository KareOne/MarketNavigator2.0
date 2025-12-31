# GitIgnore Environment Files - MarketNavigator v2

## Purpose
Configure `.gitignore` to prevent sensitive environment files and secrets from being committed to version control. This document explains what to exclude, why, and how to audit for accidental commits.

---

## Current Project Strategy

**Important:** This MarketNavigator project **currently tracks `.env` files** in version control (see current `.gitignore`). This section documents the **recommended best practice** for future improvements.

---

## Recommended .gitignore Rules for Environment Files

### Root `.gitignore`

Add these rules to the root `.gitignore` file:

```gitignore
# ============================================================================
# Environment Files (NEVER commit secrets!)
# ============================================================================

# Main environment files
.env
.env.local
.env.*.local
.env.development
.env.development.local
.env.test
.env.test.local
.env.production
.env.production.local

# Environment backups
.env.backup
.env.backup.*
.env.old
*.env.bak

# Docker environment
.env.docker
docker-compose.override.yml

# IDE-specific env files
.vscode/settings.json
.idea/workspace.xml

# ============================================================================
# Secrets & Credentials
# ============================================================================

# API Keys
**/api_keys.txt
**/secrets.json
**/credentials.json

# SSL Certificates
*.pem
*.key
*.crt
*.csr
*.p12
*.pfx
nginx/ssl/*.pem
nginx/ssl/*.key

# SSH Keys
*.pub
id_rsa
id_rsa.pub
id_ed25519
id_ed25519.pub

# Database dumps with sensitive data
*.sql
*.dump
*.backup

# AWS / Cloud credentials
.aws/
.credentials
**/aws-credentials.json

# ============================================================================
# Scraper Credentials
# ============================================================================

# Scraper-specific environment files
scrapers/Crunchbase_API/.env
scrapers/Crunchbase_API/credentials.json
scrapers/Crunchbase_API/browser_state.json

scrapers/Tracxn_API/.env
scrapers/Tracxn_API/credentials.json
scrapers/Tracxn_API/config_local.py

# ============================================================================
# Logs with Potential Secrets
# ============================================================================

# Application logs (may contain API keys in error messages)
*.log
logs/
ERROR_LOGS/
debug.log
error.log

# Celery logs
celerybeat-schedule
celerybeat.pid

# ============================================================================
# Build Artifacts (may contain embedded secrets)
# ============================================================================

# Next.js build (contains NEXT_PUBLIC_* values)
.next/
out/
.next.cache/

# Python compiled
__pycache__/
*.py[cod]
*.so

# ============================================================================
# Database Files
# ============================================================================

# SQLite (may contain sensitive user data)
*.sqlite3
*.sqlite
*.db

# PostgreSQL dumps
*.pgdump

# ============================================================================
# Docker Volumes (contain data)
# ============================================================================

# Local volume data
redis_data/
minio_data/
postgres_data/
backend_media/
backend_static/

# ============================================================================
# Temporary Files
# ============================================================================

# OS-specific
.DS_Store
Thumbs.db
*.swp
*.swo
*~

# Editor
.vscode/
.idea/
*.sublime-workspace

# Temporary
tmp/
temp/
*.tmp
```

### Backend-Specific `.gitignore`

Add to `backend/.gitignore`:

```gitignore
# Django secret key file (if stored separately)
secret_key.txt

# Environment
.env
.env.local

# Database
db.sqlite3
*.db

# Static files (if containing uploaded sensitive docs)
media/
static/

# Logs
*.log
```

### Frontend-Specific `.gitignore`

Add to `frontend/.gitignore`:

```gitignore
# Environment
.env
.env.local
.env.production.local
.env.development.local

# Next.js
.next/
out/
.next.cache/

# Build
build/
dist/

# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
```

---

## What Files SHOULD Be Committed

### ✅ Environment Templates (Safe to Commit)

These files contain NO sensitive values and should be tracked:

```gitignore
# Allow these files
!.env.example
!.env.template
!.env.sample
!.env.defaults

# Allow documentation
!docs/*.md
!README.md
!SECURITY.md
```

**Example `.env.example`:**

```bash
# Django
SECRET_KEY=<GENERATE_RANDOM_50_CHARS>
DEBUG=1
DB_PASSWORD=<ASK_TEAM_FOR_PASSWORD>

# API Keys
OPENAI_API_KEY=<YOUR_KEY_HERE>
LIARA_API_KEY=<YOUR_KEY_HERE>
```

**Key differences:**
- Use `<PLACEHOLDER>` syntax for secrets
- Include comments explaining how to obtain values
- Keep structure identical to actual `.env` file
- Update whenever new variables are added

---

## Transition Plan: From Tracked to Ignored

### Current State

MarketNavigator currently **tracks `.env` files** in Git. This is visible in the current `.gitignore`:

```gitignore
# NOTE: .env files ARE tracked for this project (production deployment)
# Remove these lines if you want to exclude them:
# .env
# .env.*
```

### Migration Steps (Recommended Future Improvement)

#### Step 1: Create Environment Template

```bash
# Create template from current .env
cp .env .env.example

# Edit .env.example to remove sensitive values
nano .env.example
# Replace all actual secrets with <PLACEHOLDER> syntax
```

#### Step 2: Update .gitignore

```bash
# Add to .gitignore
echo "" >> .gitignore
echo "# Environment files (added $(date +%Y-%m-%d))" >> .gitignore
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore
echo "!.env.example" >> .gitignore
```

#### Step 3: Remove .env from Git History

```bash
# Stop tracking .env (keep file locally)
git rm --cached .env
git rm --cached scrapers/Crunchbase_API/.env
git rm --cached scrapers/Tracxn_API/config.py

# Commit removal
git add .gitignore
git commit -m "chore: Stop tracking .env files, use .env.example instead"

# Push changes
git push origin main
```

#### Step 4: Scrub History (Optional - Removes Secrets from All Commits)

**Warning:** This rewrites Git history. Coordinate with team first.

```bash
# Install BFG Repo-Cleaner
# Download from: https://rpo.github.io/bfg-repo-cleaner/

# Backup repository first!
git clone --mirror https://github.com/your-org/MarketNavigator2.0.git

# Remove .env files from all commits
bfg --delete-files .env MarketNavigator2.0.git

# Force push (WARNING: This is destructive!)
cd MarketNavigator2.0.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force

# All team members must re-clone repository
```

#### Step 5: Update Team Documentation

```bash
# Update README.md with new setup instructions
cat >> README.md << 'EOF'

## Environment Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in sensitive values (get from team lead):
   - `SECRET_KEY` - Generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `DB_PASSWORD` - Get from team
   - `OPENAI_API_KEY` - Get from team
   - All other `<PLACEHOLDER>` values

3. Start development:
   ```bash
   docker-compose up -d
   ```
EOF
```

---

## Verifying .gitignore Rules

### Check if File is Ignored

```bash
# Test if .env would be ignored
git check-ignore -v .env
# Output: .gitignore:10:.env    .env

# If output is empty, file is NOT ignored (bad!)

# Test multiple files
git check-ignore -v .env scrapers/Crunchbase_API/.env backend/.env.local
```

### List All Tracked Files

```bash
# Show all tracked files (check for .env files)
git ls-files | grep -E '\\.env|\\.pem|\\.key|secret|credential'

# If any .env files appear, they're being tracked!
```

### Verify Nothing Sensitive is Staged

```bash
# Before committing, check staged files
git diff --cached --name-only

# Review content of staged files
git diff --cached

# Check for patterns that look like secrets
git diff --cached | grep -E 'api[_-]?key|password|secret|token' -i
```

---

## Git Hooks for Secret Detection

### Pre-Commit Hook (Prevent Committing Secrets)

Create `.githooks/pre-commit`:

```bash
#!/bin/bash

echo "Checking for potential secrets in staged files..."

# Patterns that look like secrets
SECRET_PATTERNS=(
    'api[_-]?key\s*=\s*["\047][a-zA-Z0-9_-]{20,}["\047]'
    'password\s*=\s*["\047][^"\047]{8,}["\047]'
    'secret[_-]?key\s*=\s*["\047][a-zA-Z0-9_-]{20,}["\047]'
    'token\s*=\s*["\047][a-zA-Z0-9._-]{20,}["\047]'
    'aws[_-]?secret\s*=\s*["\047][a-zA-Z0-9/+=]{40}["\047]'
    'private[_-]?key\s*=\s*["\047][^"\047]{40,}["\047]'
    '-----BEGIN (RSA |DSA )?PRIVATE KEY-----'
    'sk-[a-zA-Z0-9]{48}'  # OpenAI API key pattern
)

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only)

SECRETS_FOUND=0

for file in $STAGED_FILES; do
    # Skip binary files
    if file "$file" | grep -q "text"; then
        for pattern in "${SECRET_PATTERNS[@]}"; do
            if grep -qE "$pattern" "$file"; then
                echo "❌ Potential secret found in: $file"
                echo "   Pattern matched: $pattern"
                grep -nE "$pattern" "$file" | head -3
                echo ""
                SECRETS_FOUND=1
            fi
        done
    fi
done

# Check if .env files are being committed
if echo "$STAGED_FILES" | grep -qE '\.env$|\.env\.|secret|credential'; then
    echo "❌ Attempting to commit sensitive files:"
    echo "$STAGED_FILES" | grep -E '\.env$|\.env\.|secret|credential'
    echo ""
    SECRETS_FOUND=1
fi

if [ $SECRETS_FOUND -eq 1 ]; then
    echo "❌ COMMIT BLOCKED: Potential secrets detected!"
    echo ""
    echo "If these are false positives, use: git commit --no-verify"
    echo "Otherwise, remove secrets and use environment variables."
    exit 1
fi

echo "✅ No secrets detected in staged files"
exit 0
```

**Install hook:**

```bash
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

### Pre-Push Hook (Additional Safety)

Create `.githooks/pre-push`:

```bash
#!/bin/bash

echo "Final secret check before push..."

# Check commits that would be pushed
COMMITS=$(git rev-list @{u}.. 2>/dev/null)

if [ -z "$COMMITS" ]; then
    echo "No new commits to check"
    exit 0
fi

# Check each commit for sensitive files
SENSITIVE_FILES=$(git diff --name-only @{u}.. | grep -E '\.env$|\.pem$|\.key$|secret|credential')

if [ -n "$SENSITIVE_FILES" ]; then
    echo "❌ PUSH BLOCKED: Sensitive files detected in commits:"
    echo "$SENSITIVE_FILES"
    echo ""
    echo "Remove these files with: git rm --cached <file>"
    exit 1
fi

echo "✅ No sensitive files in commits"
exit 0
```

---

## Secret Scanning Tools

### 1. TruffleHog (Git History Scanner)

```bash
# Install TruffleHog
pip install truffleHog

# Scan repository
trufflehog filesystem /path/to/MarketNavigator2.0 --json > secrets_report.json

# Scan specific commits
trufflehog git file:///path/to/repo --since_commit HEAD~10
```

### 2. Gitleaks (Fast Secret Scanner)

```bash
# Install Gitleaks
brew install gitleaks  # macOS
# or download from: https://github.com/gitleaks/gitleaks/releases

# Scan repository
gitleaks detect --source . --report-format json --report-path gitleaks-report.json

# Scan uncommitted changes only
gitleaks protect --staged
```

**Add to GitHub Actions:**

```yaml
name: Secret Scanning

on: [push, pull_request]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 3. git-secrets (AWS)

```bash
# Install git-secrets
brew install git-secrets  # macOS

# Initialize in repository
cd /path/to/MarketNavigator2.0
git secrets --install

# Add patterns
git secrets --register-aws
git secrets --add 'api[_-]?key.*=.*["\047][a-zA-Z0-9]{20,}'
git secrets --add 'password.*=.*["\047][^"\047]{8,}'

# Scan repository
git secrets --scan
```

---

## Emergency: Secret Accidentally Committed

### Step 1: Immediately Revoke the Secret

**Before fixing Git history, revoke the exposed secret:**

```bash
# OpenAI API Key
# → Go to https://platform.openai.com/api-keys → Delete key

# Database Password
# → Change password immediately on database server

# AWS/MinIO Keys
# → Rotate credentials in MinIO console
```

### Step 2: Remove from Latest Commit (Not Pushed Yet)

```bash
# If secret is in most recent commit and NOT pushed
git reset HEAD~1  # Undo commit, keep changes
# Edit file to remove secret
git add .
git commit -m "Fix: Remove accidentally committed secret"
```

### Step 3: Remove from History (Already Pushed)

```bash
# Method 1: Using BFG Repo-Cleaner (fast)
bfg --replace-text passwords.txt  # File with: SECRET_KEY==> (redacted)

# Method 2: Using git filter-branch (slow but built-in)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (WARNING: Rewrites history)
git push origin --force --all
```

### Step 4: Notify Team

```
To: Engineering Team
Subject: [URGENT] Secret Exposure - Action Required

A secret was accidentally committed to Git:
- Type: API Key / Database Password / etc.
- Exposure time: 2 hours
- Action taken: Key revoked, history rewritten

Required actions:
1. Re-clone repository (history was rewritten)
2. Get new secrets from .env.example template
3. Update local .env files with new credentials

Contact [Lead] for new credentials.
```

---

## Best Practices Summary

### ✅ Do This

1. **Use `.env.example` templates** - Track structure, not secrets
2. **Add `.env` to `.gitignore`** - Prevent accidental commits
3. **Use pre-commit hooks** - Automated secret detection
4. **Rotate secrets regularly** - Every 90 days minimum
5. **Use secret managers** - AWS Secrets Manager, HashiCorp Vault
6. **Document secret locations** - Where to get credentials
7. **Scan regularly** - Use Gitleaks, TruffleHog weekly
8. **Limit secret access** - Only give production secrets to ops team

### ❌ Don't Do This

1. **Commit actual `.env` files** - Even temporarily
2. **Hardcode secrets in code** - Always use environment variables
3. **Email secrets** - Use secure password managers
4. **Reuse secrets** - Different per environment
5. **Commit commented-out secrets** - Still visible in history
6. **Use weak secrets** - Minimum 20 characters random
7. **Share secrets in Slack** - Use encrypted channels
8. **Ignore secret scanner warnings** - Always investigate

---

## Quick Reference Commands

```bash
# Check if file is ignored
git check-ignore -v .env

# List all tracked files (look for .env)
git ls-files | grep env

# Stop tracking file (keep locally)
git rm --cached .env

# Scan for secrets in staged files
git diff --cached | grep -iE 'password|api.?key|secret'

# Test .gitignore rules
echo ".env" > test.env
git status | grep test.env  # Should not appear
rm test.env

# Verify pre-commit hook is active
git config core.hooksPath
# Should output: .githooks
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Security Team  
**Review Schedule:** Quarterly + After any security incident
