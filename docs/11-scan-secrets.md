# Scanning Git History for Secrets - MarketNavigator v2

## Purpose
Comprehensive guide to detect accidentally committed secrets in Git history, remove them safely, and prevent future leaks. Critical for security audits and compliance.

---

## Quick Secret Scan (Start Here)

### 1-Minute Scan

```bash
cd /path/to/MarketNavigator2.0

# Scan for common secret patterns in recent commits
git log -p -20 | grep -iE 'password|api[_-]?key|secret[_-]?key|token|credential' --color=always

# Check for .env files in history
git log --all --full-history -- "*.env"

# Check for hardcoded secrets in current branch
git grep -iE 'api[_-]?key.*=.*["\047][a-zA-Z0-9]{20,}["\047]'
```

**If anything is found:** Continue with comprehensive scanning below.

---

## Comprehensive Secret Detection

### Method 1: Gitleaks (Recommended)

#### Install

```bash
# macOS
brew install gitleaks

# Linux (download binary)
wget https://github.com/gitleaks/gitleaks/releases/download/v8.18.1/gitleaks_8.18.1_linux_x64.tar.gz
tar -xzf gitleaks_8.18.1_linux_x64.tar.gz
sudo mv gitleaks /usr/local/bin/
```

#### Scan Repository

```bash
# Scan entire history
gitleaks detect --source . --report-format json --report-path gitleaks-report.json --verbose

# Scan only uncommitted changes
gitleaks protect --staged

# Scan specific branch
gitleaks detect --source . --branch develop

# Scan since specific commit
gitleaks detect --source . --log-opts="--since='2024-01-01'"
```

#### Example Output

```json
{
  "Description": "Identified a generic API Key",
  "StartLine": 42,
  "EndLine": 42,
  "StartColumn": 1,
  "EndColumn": 60,
  "Match": "API_KEY = 'sk-abc123def456ghi789'",
  "Secret": "sk-abc123def456ghi789",
  "File": "backend/config/settings.py",
  "Commit": "abc123def456",
  "Author": "John Doe",
  "Email": "john@example.com",
  "Date": "2024-12-15T10:30:00Z"
}
```

#### Configure Gitleaks

Create `.gitleaks.toml` to customize rules:

```toml
title = "MarketNavigator Gitleaks Config"

[[rules]]
id = "openai-api-key"
description = "OpenAI API Key"
regex = '''sk-[a-zA-Z0-9]{48}'''
tags = ["key", "OpenAI"]

[[rules]]
id = "aws-access-key"
description = "AWS Access Key ID"
regex = '''AKIA[0-9A-Z]{16}'''
tags = ["key", "AWS"]

[[rules]]
id = "generic-api-key"
description = "Generic API Key"
regex = '''api[_-]?key\s*=\s*['"][a-zA-Z0-9_\-]{20,}['"]'''
tags = ["key", "API"]

[[rules]]
id = "database-password"
description = "Database Password"
regex = '''(password|passwd|pwd)\s*=\s*['"][^'"]{8,}['"]'''
tags = ["password", "database"]

[[rules]]
id = "jwt-token"
description = "JWT Token"
regex = '''eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}'''
tags = ["token", "JWT"]

[allowlist]
description = "Allowlisted files"
paths = [
  '''\.env\.example$''',
  '''\.env\.template$''',
  '''docs/.*\.md$''',
  '''README\.md$'''
]

commits = [
  # Add commit SHAs that contain known false positives
]

regexes = [
  # Example passwords or keys in documentation
  '''(example|sample|placeholder)[_-]?(key|password|token)'''
]
```

---

### Method 2: TruffleHog

#### Install

```bash
pip install trufflehog
```

#### Scan Repository

```bash
# Scan entire history
trufflehog filesystem /path/to/MarketNavigator2.0 --json --output trufflehog-report.json

# Scan specific branch
trufflehog git file:///path/to/MarketNavigator2.0 --branch develop

# Scan since specific date
trufflehog git file:///path/to/MarketNavigator2.0 --since-commit HEAD~50

# Scan with high entropy detection (finds random strings)
trufflehog filesystem . --json --entropy
```

#### Example Output

```json
{
  "SourceName": "MarketNavigator2.0",
  "SourceType": "Git",
  "VerificationError": null,
  "Verified": true,
  "Raw": "api_key=sk-abc123def456",
  "Redacted": "api_key=sk-abc***def***",
  "File": "backend/services/openai_service.py",
  "Commit": "abc123",
  "Email": "developer@example.com",
  "Repository": "file:///path/to/repo"
}
```

---

### Method 3: GitGuardian (Cloud-Based)

#### Install CLI

```bash
pip install ggshield
```

#### Configure

```bash
# Get API key from https://dashboard.gitguardian.com/api/personal-access-tokens
export GITGUARDIAN_API_KEY=your_api_key

# Or save to config
ggshield auth login
```

#### Scan

```bash
# Scan entire repository
ggshield secret scan repo .

# Scan specific paths
ggshield secret scan path backend/

# Scan commits
ggshield secret scan commit-range HEAD~10..HEAD
```

---

### Method 4: Manual Git Log Inspection

#### Search for Common Patterns

```bash
# Search for API keys
git log -p --all | grep -iE "api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{20,}['\"]" --color=always | less -R

# Search for passwords
git log -p --all | grep -iE "(password|passwd|pwd)\s*=\s*['\"][^'\"]{8,}['\"]" --color=always | less -R

# Search for JWT tokens
git log -p --all | grep -E "eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+" --color=always | less -R

# Search for AWS keys
git log -p --all | grep -E "AKIA[0-9A-Z]{16}" --color=always | less -R

# Search for private keys
git log -p --all | grep -E "-----BEGIN (RSA |DSA )?PRIVATE KEY-----" --color=always | less -R
```

#### Search Specific Files

```bash
# Check if .env was ever committed
git log --all --full-history --source -- .env

# Check scraper environment files
git log --all --full-history -- "scrapers/*/\.env"

# Check for any files with "secret" or "credential" in name
git log --all --name-only | grep -iE "secret|credential|password|key" | sort -u
```

#### Find Large Blobs (Possible Secret Dumps)

```bash
# Find largest files in history (may be database dumps with secrets)
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  sed -n 's/^blob //p' | \
  sort --numeric-sort --key=2 --reverse | \
  head -20 | \
  cut -c 1-12,41- | \
  numfmt --field=2 --to=iec-i --suffix=B --padding=7 --round=nearest
```

---

## Analyzing Scan Results

### Review Gitleaks Report

```bash
# Count findings by type
cat gitleaks-report.json | jq '.[] | .RuleID' | sort | uniq -c | sort -rn

# List all affected files
cat gitleaks-report.json | jq -r '.[].File' | sort -u

# Show secrets by author
cat gitleaks-report.json | jq -r '.[] | "\(.Author) - \(.File):\(.StartLine)"' | sort

# Filter out false positives (example files)
cat gitleaks-report.json | jq '.[] | select(.File | test("\\.example$|\\.template$|\\.md$") | not)'
```

### Verify Findings

```bash
# Check if secret is still in current codebase
git grep "sk-abc123def456"

# Check commit that introduced secret
git show abc123def456

# Check if secret has been removed since
git log -p --all -- backend/config/settings.py | grep -A5 -B5 "API_KEY"

# See who committed the secret
git show --format="%an %ae %ad" abc123def456 | head -1
```

---

## Removing Secrets from Git History

### ⚠️ Before You Start

**Critical warnings:**
1. **This rewrites Git history** - All commit SHAs will change
2. **All team members must re-clone** after history rewrite
3. **Backup repository first** - `git clone --mirror` to separate location
4. **Coordinate with team** - Announce maintenance window
5. **Revoke exposed secrets immediately** - Before cleaning history

---

### Method 1: BFG Repo-Cleaner (Fast, Recommended)

#### Install

```bash
# Download BFG
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
alias bfg='java -jar /path/to/bfg-1.14.0.jar'
```

#### Remove Specific Secrets

```bash
# Create replacement file
cat > secrets-to-remove.txt << 'EOF'
sk-abc123def456ghi789==><REDACTED>
AZ6t2MguosDdJ8oCval6B7bU==><REDACTED>
minioadmin123==><REDACTED>
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9==><REDACTED>
EOF

# Backup repository
git clone --mirror https://github.com/your-org/MarketNavigator2.0.git backup-repo.git

# Replace secrets in history
cd MarketNavigator2.0
bfg --replace-text secrets-to-remove.txt

# Review changes
git log --all --oneline | head -20

# Cleanup and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (WARNING: Destructive!)
git push origin --force --all
git push origin --force --tags
```

#### Delete Specific Files

```bash
# Remove .env files from all history
bfg --delete-files .env

# Remove all .pem files
bfg --delete-files '*.pem'

# Remove entire directory
bfg --delete-folders 'secret_keys'
```

---

### Method 2: git-filter-repo (Modern, Flexible)

#### Install

```bash
pip install git-filter-repo
```

#### Remove Files

```bash
# Backup first
git clone --mirror https://github.com/your-org/MarketNavigator2.0.git backup-repo.git

# Remove .env files
cd MarketNavigator2.0
git filter-repo --invert-paths --path .env

# Remove multiple files
git filter-repo --invert-paths \
  --path .env \
  --path scrapers/Crunchbase_API/.env \
  --path nginx/ssl/privkey.pem

# Force push
git push origin --force --all
```

#### Replace Content

```bash
# Create Python script for replacement
cat > replace-secrets.py << 'EOF'
import re

def replace_secrets(blob, callback_metadata):
    # Replace API keys
    blob.data = re.sub(
        b'sk-[a-zA-Z0-9]{48}',
        b'<REDACTED_OPENAI_KEY>',
        blob.data
    )
    
    # Replace passwords
    blob.data = re.sub(
        b'password=["\']([^"\']+)["\']',
        b'password="<REDACTED>"',
        blob.data
    )
    
    return blob.data

EOF

# Apply replacement
git filter-repo --blob-callback "$(cat replace-secrets.py)"
```

---

### Method 3: git filter-branch (Legacy, Slow)

```bash
# Remove .env file from all history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Remove all .pem files
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch --recursive '*.pem'" \
  --prune-empty --tag-name-filter cat -- --all

# Cleanup
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push origin --force --all
git push origin --force --tags
```

---

## Post-Cleanup Verification

### Verify Secrets Removed

```bash
# Scan again with Gitleaks
gitleaks detect --source . --verbose

# Manual grep
git log -p --all | grep -iE "sk-abc123def456|AZ6t2MguosDdJ8oCval6B7bU"
# Should return nothing

# Check file still exists in current branch
ls -la .env
# Should still exist (only removed from history)

# Check specific file in history
git log --all --full-history -- .env
# Should show empty or only recent commits
```

### Compare Before/After

```bash
# Check repository size reduced
du -sh .git/
# Should be smaller after aggressive gc

# Count commits (should be same number)
git rev-list --all --count

# Verify all branches exist
git branch -a
```

---

## Team Notification & Re-clone Procedure

### Notification Template

```markdown
🚨 **Urgent: Git History Rewrite - Action Required**

The MarketNavigator repository history has been rewritten to remove
accidentally committed secrets. All commit SHAs have changed.

**Required Action (within 24 hours):**

1. **Backup any local uncommitted changes**
   ```bash
   cd ~/MarketNavigator2.0
   git stash save "backup-before-reclone"
   ```

2. **Delete local repository**
   ```bash
   cd ..
   rm -rf MarketNavigator2.0
   ```

3. **Clone fresh copy**
   ```bash
   git clone https://github.com/your-org/MarketNavigator2.0.git
   cd MarketNavigator2.0
   ```

4. **Restore stashed changes (if any)**
   ```bash
   git stash list  # List your stashes
   # If you had stashes in old repo, manually reapply changes
   ```

5. **Verify you're on correct commit**
   ```bash
   git log --oneline -5
   # Should show new commit SHAs
   ```

**Do NOT:**
- ❌ Try to merge/pull (will fail with conflicts)
- ❌ Force push from old local repo
- ❌ Keep working on old clone

**Questions?** Contact DevOps team on Slack #devops

**Deadline:** 2025-01-01 EOD
```

---

## Prevention: Pre-commit Hooks

### Install Pre-commit Framework

```bash
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.1
    hooks:
      - id: gitleaks

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: check-merge-conflict

  - repo: local
    hooks:
      - id: check-env-files
        name: Check for .env files
        entry: .env files should not be committed
        language: fail
        files: \.env$
EOF

# Install hooks
pre-commit install

# Test
pre-commit run --all-files
```

### Custom Secret Detection Hook

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash

echo "Scanning for secrets..."

# Patterns to detect
PATTERNS=(
    'api[_-]?key\s*=\s*["\047][a-zA-Z0-9_-]{20,}["\047]'
    'password\s*=\s*["\047][^"\047]{8,}["\047]'
    'sk-[a-zA-Z0-9]{48}'
    'AKIA[0-9A-Z]{16}'
    '-----BEGIN (RSA |DSA )?PRIVATE KEY-----'
    'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'
)

FOUND=0

# Get staged files
for file in $(git diff --cached --name-only); do
    if [ -f "$file" ]; then
        for pattern in "${PATTERNS[@]}"; do
            if grep -qE "$pattern" "$file"; then
                echo "❌ Potential secret in: $file"
                echo "   Pattern: $pattern"
                grep -nE "$pattern" "$file" | head -2
                echo ""
                FOUND=1
            fi
        done
    fi
done

if [ $FOUND -eq 1 ]; then
    echo "❌ Commit blocked: Remove secrets before committing"
    echo ""
    echo "Use environment variables instead of hardcoded secrets."
    echo "Bypass with: git commit --no-verify (NOT recommended)"
    exit 1
fi

echo "✅ No secrets detected"
exit 0
EOF

chmod +x .git/hooks/pre-commit
```

---

## Continuous Monitoring

### GitHub Actions Secret Scanning

```yaml
# .github/workflows/secret-scan.yml
name: Secret Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday 2 AM

jobs:
  gitleaks:
    name: Gitleaks Secret Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}  # For Gitleaks Pro

      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: gitleaks-report
          path: gitleaks-report.json
```

---

## Quick Reference Commands

```bash
# Quick scan for secrets
git log -p -20 | grep -iE 'password|api.?key|secret|token' --color

# Comprehensive scan
gitleaks detect --source . --report-format json --report-path report.json

# Remove specific file from history
bfg --delete-files .env

# Replace secret in history
bfg --replace-text secrets.txt

# Force push after cleanup
git push origin --force --all
git push origin --force --tags

# Verify cleanup
gitleaks detect --source . --verbose

# Install pre-commit hooks
pre-commit install
pre-commit run --all-files
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Security Team  
**Scan Schedule:** Weekly automated + After any suspected leak
