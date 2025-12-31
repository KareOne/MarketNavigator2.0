# Branch Protection Rules - MarketNavigator v2

## Purpose
Enforce code quality and prevent accidental pushes to critical branches. This document defines branch protection rules and enforcement mechanisms for the MarketNavigator project.

---

## Protected Branches

### Main Branch (`main`)
**Purpose:** Production-ready code only  
**Protection Level:** MAXIMUM

**Rules:**
- ❌ No direct pushes (including admins)
- ✅ Require pull request reviews (minimum 1 approval)
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up-to-date before merging
- ✅ Require linear history (no merge commits)
- ✅ Require signed commits (recommended)
- ❌ Do not allow force pushes
- ❌ Do not allow deletions

**Who can merge:**
- Repository admins (with PR approval)
- Tech leads (with PR approval)

**Automated checks before merge:**
1. All CI/CD tests pass
2. At least 1 code review approval
3. No merge conflicts with main
4. Branch is up-to-date with main

### Develop Branch (`develop`)
**Purpose:** Integration branch for features  
**Protection Level:** HIGH

**Rules:**
- ❌ No direct pushes from local machines
- ✅ Require pull request (approval optional for trusted devs)
- ✅ Require status checks to pass
- ⚠️ Allow force pushes from admins only (for cleanup)
- ❌ Do not allow deletions

**Who can merge:**
- All team members (with passing tests)
- Automated CI/CD system

---

## GitHub Branch Protection Setup

### Step 1: Navigate to Settings

1. Go to repository on GitHub: `https://github.com/your-org/MarketNavigator2.0`
2. Click **Settings** tab
3. Click **Branches** in left sidebar
4. Click **Add branch protection rule**

### Step 2: Protect Main Branch

**Branch name pattern:** `main`

**Configure protection rules:**

```yaml
# Require a pull request before merging
☑️ Require a pull request before merging
   ☑️ Require approvals: 1
   ☑️ Dismiss stale pull request approvals when new commits are pushed
   ☑️ Require review from Code Owners (if CODEOWNERS file exists)
   ☐ Restrict who can dismiss pull request reviews
   ☑️ Allow specified actors to bypass required pull requests (for emergency hotfixes)
      → Add: repository admins only

# Require status checks to pass before merging
☑️ Require status checks to pass before merging
   ☑️ Require branches to be up to date before merging
   Required checks:
     - build-backend
     - build-frontend
     - test-backend
     - lint-python
     - lint-typescript

# Require conversation resolution before merging
☑️ Require conversation resolution before merging

# Require signed commits
☑️ Require signed commits (recommended for security)

# Require linear history
☑️ Require linear history (prevents merge commits, requires rebase/squash)

# Include administrators
☐ Include administrators (admins should follow same rules)

# Restrict who can push to matching branches
☑️ Restrict who can push to matching branches
   Allow push access to: (none - force PR workflow)

# Rules applied to everyone including administrators
☑️ Do not allow bypassing the above settings

# Allow force pushes
☐ Allow force pushes (NEVER allow on main)

# Allow deletions
☐ Allow deletions (NEVER allow on main)
```

**Save changes.**

### Step 3: Protect Develop Branch

**Branch name pattern:** `develop`

**Configure protection rules:**

```yaml
# Require a pull request before merging
☑️ Require a pull request before merging
   Require approvals: 0 (or 1 for stricter workflow)
   ☑️ Dismiss stale pull request approvals when new commits are pushed

# Require status checks to pass before merging
☑️ Require status checks to pass before merging
   ☑️ Require branches to be up to date before merging
   Required checks:
     - build-backend
     - build-frontend
     - test-backend

# Require conversation resolution before merging
☑️ Require conversation resolution before merging

# Require linear history
☑️ Require linear history

# Include administrators
☐ Include administrators (allow admins to bypass for urgent fixes)

# Restrict who can push to matching branches
☐ Restrict who can push to matching branches (allow team members)

# Allow force pushes
☑️ Allow force pushes (for admins only)
   Specify who can force push: repository admins

# Allow deletions
☐ Allow deletions
```

**Save changes.**

---

## Local Git Configuration

### Prevent Accidental Pushes to Main

Add this to `.git/hooks/pre-push`:

```bash
#!/bin/bash

# Get the current branch name
current_branch=$(git symbolic-ref --short HEAD)

# Branches that should never be pushed to directly
protected_branches="main master"

# Check if current branch is protected
for branch in $protected_branches; do
    if [ "$current_branch" = "$branch" ]; then
        echo "❌ ERROR: Direct push to '$branch' branch is not allowed!"
        echo "Please create a feature branch and submit a pull request."
        echo ""
        echo "To create a feature branch:"
        echo "  git checkout -b feature/your-feature-name"
        echo ""
        exit 1
    fi
done

echo "✅ Pushing to '$current_branch' branch..."
exit 0
```

**Make it executable:**
```bash
chmod +x .git/hooks/pre-push
```

**Note:** This is a local protection. GitHub branch protection is the primary enforcement.

### Set Up Global Git Hook Template (For All Team Members)

Create a shared hooks directory:

```bash
# In project root
mkdir -p .githooks

# Create pre-push hook
cat > .githooks/pre-push << 'EOF'
#!/bin/bash

current_branch=$(git symbolic-ref --short HEAD)
protected_branches="main master"

for branch in $protected_branches; do
    if [ "$current_branch" = "$branch" ]; then
        echo "❌ ERROR: Direct push to '$branch' branch is not allowed!"
        echo "Please create a feature branch and submit a pull request."
        exit 1
    fi
done

exit 0
EOF

# Make executable
chmod +x .githooks/pre-push

# Configure Git to use this directory
git config core.hooksPath .githooks
```

**Add to project setup instructions:**
```bash
# New developers run this after cloning
git config core.hooksPath .githooks
```

---

## Enforcement Mechanisms

### 1. GitHub Branch Protection (Primary)
- **Enforcement:** Server-side (cannot be bypassed locally)
- **Scope:** All pushes to GitHub
- **Configuration:** Repository Settings → Branches

### 2. Git Hooks (Secondary)
- **Enforcement:** Local (can be bypassed with `--no-verify`)
- **Scope:** Prevents mistakes before pushing
- **Configuration:** `.githooks/pre-push`

### 3. CI/CD Pipeline (Automated Testing)
- **Enforcement:** Blocks PR merge if tests fail
- **Scope:** Code quality, tests, linting
- **Configuration:** `.github/workflows/` (if using GitHub Actions)

### 4. Code Review Process (Human)
- **Enforcement:** Required approvals before merge
- **Scope:** Logic, design, security review
- **Configuration:** GitHub PR review settings

---

## GitHub Actions for Automated Checks

Create `.github/workflows/branch-protection.yml`:

```yaml
name: Branch Protection Checks

on:
  pull_request:
    branches: [main, develop]

jobs:
  # Backend checks
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          cd backend
          python manage.py test
      
      - name: Lint Python
        run: |
          pip install flake8
          flake8 backend/ --max-line-length=120 --exclude=migrations

  # Frontend checks
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Lint TypeScript
        run: |
          cd frontend
          npm run lint
      
      - name: Build
        run: |
          cd frontend
          npm run build

  # Security checks
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run security scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
```

---

## Manual Enforcement Checklist

### Before Merging to Main

- [ ] All automated tests pass (GitHub Actions green checkmark)
- [ ] At least 1 code review approval from senior developer
- [ ] All PR comments resolved
- [ ] Branch is up-to-date with main (rebase if needed)
- [ ] No merge conflicts
- [ ] Deployment plan documented (for breaking changes)
- [ ] Database migrations reviewed (if applicable)
- [ ] Environment variables documented (if new vars added)

### Before Merging to Develop

- [ ] All automated tests pass
- [ ] Code follows project style guidelines
- [ ] No obvious bugs or security issues
- [ ] Feature is complete (not half-implemented)

---

## Emergency Hotfix Process

### When Production is Down (Bypass Normal Flow)

1. **Create hotfix branch from main:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/critical-bug-fix
   ```

2. **Make minimal fix:**
   ```bash
   # Edit files
   git add .
   git commit -m "hotfix: Fix critical production bug"
   ```

3. **Push and create PR:**
   ```bash
   git push origin hotfix/critical-bug-fix
   ```

4. **Request emergency review:**
   - Tag tech lead in PR with `@lead`
   - Set PR title: `[HOTFIX] Critical bug fix`
   - Get expedited review (15-minute SLA)

5. **Merge to main with admin override:**
   - Admin can merge with 1 approval (or override if necessary)
   - Deploy immediately to production

6. **Backport to develop:**
   ```bash
   git checkout develop
   git merge hotfix/critical-bug-fix
   git push origin develop
   ```

**GitHub Admin Override:**
- In emergency, admins can use "Merge without waiting for requirements" button
- Must be documented in PR comments with justification

---

## Violation Handling

### Scenario 1: Developer Force-Pushed to Main

**Detection:**
```bash
# GitHub notifies all watchers
# Check git log
git log --all --graph --decorate --oneline
```

**Recovery:**
```bash
# If main is corrupted, restore from last known good commit
git checkout main
git reset --hard <last-good-commit-sha>
git push origin main --force-with-lease

# Notify team immediately
```

**Prevention:**
- GitHub branch protection blocks force pushes to main
- Revoke write access from offending account temporarily
- Require additional training

### Scenario 2: Bypassed PR Process

**Detection:**
- GitHub audit log shows direct push
- No associated PR number in commit message

**Action:**
1. Revert the commit: `git revert <commit-sha>`
2. Require developer to create proper PR with the changes
3. Review process as normal
4. Document incident in team retrospective

### Scenario 3: Merged Without Approval

**Action:**
- If code quality issues found post-merge, create immediate PR to fix
- Review GitHub settings to ensure "Require approvals" is enabled
- Consider reverting merge if critical issues found

---

## Tools for Enforcement

### 1. GitHub CLI (gh)

```bash
# Install GitHub CLI
brew install gh  # macOS
# or: sudo apt install gh  # Ubuntu

# Check branch protection status
gh api repos/{owner}/{repo}/branches/main/protection

# Enable branch protection via CLI
gh api -X PUT repos/{owner}/{repo}/branches/main/protection \
  --input branch-protection.json
```

### 2. Git Aliases for Safety

Add to `~/.gitconfig`:

```ini
[alias]
    # Safe push (requires PR for main/develop)
    safepush = "!f() { \
        branch=$(git symbolic-ref --short HEAD); \
        if [ \"$branch\" = \"main\" ] || [ \"$branch\" = \"develop\" ]; then \
            echo \"ERROR: Use pull requests for $branch\"; \
            exit 1; \
        fi; \
        git push \"$@\"; \
    }; f"
    
    # Show protected branches
    protected = "!gh api repos/{owner}/{repo}/branches --jq '.[] | select(.protected==true) | .name'"
```

Usage:
```bash
git safepush  # Use instead of git push
```

### 3. Pre-commit Hooks

Install pre-commit framework:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: trailing-whitespace
      - id: end-of-file-fixer
      
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        files: ^backend/
        
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        files: ^backend/
        args: [--max-line-length=120]
EOF

# Install hooks
pre-commit install
```

---

## Monitoring and Auditing

### GitHub Audit Log

**Access:** Settings → Security → Audit log

**Monitor for:**
- Branch protection changes
- Force pushes
- Direct commits to protected branches
- Permission changes

**Set up alerts:**
```bash
# Use GitHub API to get recent protected branch events
gh api /repos/{owner}/{repo}/events \
  --jq '.[] | select(.type=="PushEvent" and .payload.ref=="refs/heads/main")'
```

### Slack Notifications

Set up GitHub Slack app:
1. Install GitHub app in Slack workspace
2. Subscribe to repository events:
   ```
   /github subscribe owner/repo reviews comments branches
   ```
3. Configure alerts for protected branch violations

---

## Best Practices

1. **Review protection settings quarterly**
   - Technology changes (new CI tools, etc.)
   - Team size changes (more approvers needed)
   - Update this document with any changes

2. **Train new developers**
   - Include branch protection in onboarding
   - Explain why rules exist
   - Practice PR workflow in sandbox repo

3. **Document exceptions**
   - Any admin overrides must be documented in PR
   - Explain why emergency bypass was necessary
   - Create post-mortem for production incidents

4. **Keep rules consistent**
   - Same rules for all protected branches (main, develop)
   - Don't make exceptions for "senior" developers
   - Rules apply to admins too (lead by example)

5. **Automate everything possible**
   - CI/CD for testing
   - Pre-commit hooks for formatting
   - GitHub Actions for security scans
   - Fewer manual checks = fewer mistakes

---

## Quick Reference

```bash
# Check current branch protection
gh api repos/{owner}/{repo}/branches/main/protection

# Create feature branch (proper workflow)
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# Push feature branch
git push origin feature/my-feature

# Create PR from command line
gh pr create --base develop --head feature/my-feature

# Emergency hotfix
git checkout -b hotfix/critical-fix main
# ... make fix ...
git push origin hotfix/critical-fix
gh pr create --base main --head hotfix/critical-fix --label "hotfix"
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Tech Lead  
**Review Schedule:** Quarterly
