# Branch Naming Conventions - MarketNavigator v2

## Purpose
Standardized branch naming conventions ensure consistency, improve automation, and make repository navigation easier. This document defines mandatory branch naming rules with examples.

---

## Branch Naming Format

```
<type>/<ticket-id>-<short-description>
```

**Components:**
- `<type>`: Branch category (feature, bugfix, hotfix, etc.)
- `<ticket-id>`: Issue/ticket number (optional but recommended)
- `<short-description>`: Kebab-case description (3-5 words)

**Rules:**
- Use lowercase only
- Use hyphens (-) to separate words, NOT underscores (_)
- Keep total length under 50 characters
- Be descriptive but concise
- No special characters except hyphens

---

## Branch Types

### `feature/` - New Features

**Purpose:** Adding new functionality  
**Base branch:** `develop`  
**Merge target:** `develop`

**Examples:**
```bash
feature/123-add-csv-export
feature/456-user-notifications
feature/implement-dark-mode
feature/789-crunchbase-integration
feature/social-media-login
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b feature/123-add-csv-export
```

---

### `bugfix/` - Bug Fixes

**Purpose:** Fixing non-critical bugs in develop branch  
**Base branch:** `develop`  
**Merge target:** `develop`

**Examples:**
```bash
bugfix/234-fix-login-redirect
bugfix/567-report-export-error
bugfix/pagination-not-working
bugfix/890-memory-leak-celery
bugfix/typo-in-dashboard
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b bugfix/234-fix-login-redirect
```

---

### `hotfix/` - Critical Production Fixes

**Purpose:** Emergency fixes for production issues  
**Base branch:** `main`  
**Merge target:** `main` (then backport to `develop`)

**Examples:**
```bash
hotfix/critical-database-connection
hotfix/345-api-authentication-failure
hotfix/production-500-error
hotfix/678-payment-processing-bug
hotfix/security-vulnerability
```

**Creation:**
```bash
git checkout main
git pull origin main
git checkout -b hotfix/critical-database-connection
```

**After merge to main:**
```bash
# Backport to develop
git checkout develop
git merge hotfix/critical-database-connection
git push origin develop
```

---

### `release/` - Release Preparation

**Purpose:** Preparing for production release (version bumps, changelog)  
**Base branch:** `develop`  
**Merge target:** `main` and `develop`

**Examples:**
```bash
release/v1.0.0
release/v2.1.0
release/2025-01-15
release/v1.5.2-hotfix
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b release/v1.0.0
```

**Workflow:**
1. Create release branch from `develop`
2. Bump version numbers
3. Update CHANGELOG.md
4. Fix last-minute bugs
5. Merge to `main` and tag
6. Merge back to `develop`

---

### `chore/` - Maintenance Tasks

**Purpose:** Non-functional changes (dependencies, configs, refactoring)  
**Base branch:** `develop`  
**Merge target:** `develop`

**Examples:**
```bash
chore/update-dependencies
chore/123-upgrade-django-5
chore/configure-eslint
chore/456-refactor-auth-service
chore/cleanup-unused-imports
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b chore/update-dependencies
```

---

### `docs/` - Documentation Only

**Purpose:** Documentation changes (no code changes)  
**Base branch:** `develop` or `main`  
**Merge target:** `develop` or `main`

**Examples:**
```bash
docs/update-readme
docs/123-api-documentation
docs/add-deployment-guide
docs/456-architecture-diagrams
docs/fix-typos-in-comments
```

**Creation:**
```bash
git checkout develop  # or main for urgent doc fixes
git pull origin develop
git checkout -b docs/update-readme
```

---

### `test/` - Test Improvements

**Purpose:** Adding or improving tests (no production code changes)  
**Base branch:** `develop`  
**Merge target:** `develop`

**Examples:**
```bash
test/add-user-api-tests
test/123-integration-test-reports
test/improve-celery-task-coverage
test/456-e2e-login-flow
test/fix-flaky-test-suite
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b test/add-user-api-tests
```

---

### `refactor/` - Code Refactoring

**Purpose:** Improving code structure without changing functionality  
**Base branch:** `develop`  
**Merge target:** `develop`

**Examples:**
```bash
refactor/split-large-view-function
refactor/123-extract-report-service
refactor/simplify-auth-middleware
refactor/456-move-utils-to-package
refactor/remove-duplicate-code
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b refactor/split-large-view-function
```

---

### `experiment/` - Experimental Features

**Purpose:** Proof-of-concept or experimental work (may not be merged)  
**Base branch:** `develop`  
**Merge target:** `develop` (optional)

**Examples:**
```bash
experiment/ai-powered-recommendations
experiment/123-graphql-api-poc
experiment/realtime-collaboration
experiment/456-new-report-layout
experiment/websocket-scaling
```

**Creation:**
```bash
git checkout develop
git pull origin develop
git checkout -b experiment/ai-powered-recommendations
```

**Note:** These branches may be deleted without merging if experiment fails.

---

## Special Branches (Never Delete)

### `main`
- **Purpose:** Production-ready code
- **Protection:** Maximum (see 04-protect-main-branch.md)
- **Never:** Force push, direct commits, delete

### `develop`
- **Purpose:** Integration branch for features
- **Protection:** High (see 04-protect-main-branch.md)
- **Never:** Force push (except admins), delete

---

## Ticket ID Integration

### With GitHub Issues

**Format:** `<type>/#<issue-number>-<description>`

**Examples:**
```bash
feature/#123-add-csv-export
bugfix/#456-fix-pagination
hotfix/#789-critical-api-bug
```

**Benefits:**
- GitHub auto-links branch to issue
- Issue shows associated branches
- Easier to track feature progress

### With Jira/Linear

**Format:** `<type>/<JIRA-KEY>-<description>`

**Examples:**
```bash
feature/MN-123-add-csv-export
bugfix/MN-456-fix-pagination
hotfix/MN-789-critical-api-bug
```

**Jira key format:** `PROJECT-NUMBER` (e.g., MN-123)

---

## Automated Branch Validation

### Git Hook for Branch Name Validation

Create `.githooks/pre-push`:

```bash
#!/bin/bash

# Get current branch name
branch=$(git symbolic-ref --short HEAD)

# Allow main and develop
if [ "$branch" = "main" ] || [ "$branch" = "develop" ]; then
    exit 0
fi

# Define valid branch prefixes
valid_prefixes="feature|bugfix|hotfix|release|chore|docs|test|refactor|experiment"

# Validate branch name format
if ! echo "$branch" | grep -qE "^($valid_prefixes)/.+"; then
    echo "❌ Invalid branch name: $branch"
    echo ""
    echo "Branch name must follow format: <type>/<description>"
    echo ""
    echo "Valid types: feature, bugfix, hotfix, release, chore, docs, test, refactor, experiment"
    echo ""
    echo "Examples:"
    echo "  feature/123-add-export"
    echo "  bugfix/fix-login-error"
    echo "  hotfix/critical-api-bug"
    echo ""
    echo "Rename your branch with:"
    echo "  git branch -m <new-branch-name>"
    echo ""
    exit 1
fi

# Check branch name length
if [ ${#branch} -gt 50 ]; then
    echo "⚠️  Warning: Branch name is too long (${#branch} chars, max 50)"
    echo "Consider shortening: $branch"
fi

# Check for underscores (should use hyphens)
if echo "$branch" | grep -q "_"; then
    echo "⚠️  Warning: Use hyphens (-) instead of underscores (_)"
fi

# Check for uppercase (should be lowercase)
if echo "$branch" | grep -q "[A-Z]"; then
    echo "⚠️  Warning: Branch name should be lowercase"
fi

exit 0
```

**Install hook:**
```bash
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
```

---

### GitHub Actions Branch Name Validation

Create `.github/workflows/branch-naming.yml`:

```yaml
name: Branch Naming Convention

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  validate-branch-name:
    runs-on: ubuntu-latest
    steps:
      - name: Check branch name
        run: |
          BRANCH_NAME="${{ github.head_ref }}"
          echo "Checking branch name: $BRANCH_NAME"
          
          # Valid prefixes
          VALID_PATTERN="^(feature|bugfix|hotfix|release|chore|docs|test|refactor|experiment)/.+"
          
          if ! echo "$BRANCH_NAME" | grep -qE "$VALID_PATTERN"; then
            echo "❌ Invalid branch name: $BRANCH_NAME"
            echo ""
            echo "Branch name must follow format: <type>/<description>"
            echo "Valid types: feature, bugfix, hotfix, release, chore, docs, test, refactor, experiment"
            echo ""
            echo "Examples:"
            echo "  feature/123-add-export"
            echo "  bugfix/fix-login-error"
            echo "  hotfix/critical-api-bug"
            exit 1
          fi
          
          # Check length
          if [ ${#BRANCH_NAME} -gt 50 ]; then
            echo "⚠️  Warning: Branch name is too long (${#BRANCH_NAME} chars)"
          fi
          
          echo "✅ Branch name is valid"
```

---

## Branch Lifecycle

### 1. Creation

```bash
# Start from latest develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/123-add-export

# Make changes
git add .
git commit -m "feat: Add CSV export functionality"

# Push to remote
git push origin feature/123-add-export
```

### 2. Active Development

```bash
# Keep branch updated with develop
git checkout develop
git pull origin develop
git checkout feature/123-add-export
git rebase develop

# Fix conflicts if any
# ... resolve conflicts ...
git rebase --continue

# Force push (safe for feature branches)
git push --force-with-lease origin feature/123-add-export
```

### 3. Pull Request

```bash
# Create PR
gh pr create --base develop --head feature/123-add-export

# Wait for review and approval
# Address feedback with new commits
```

### 4. Merge and Cleanup

```bash
# After PR is merged, delete branch
git checkout develop
git pull origin develop
git branch -d feature/123-add-export

# Delete remote branch (GitHub can auto-delete)
git push origin --delete feature/123-add-export
```

---

## Branch Management Scripts

### Create Branch with Validation

Save as `scripts/new-branch.sh`:

```bash
#!/bin/bash

# Usage: ./new-branch.sh feature "add csv export" 123

if [ $# -lt 2 ]; then
    echo "Usage: $0 <type> <description> [ticket-id]"
    echo ""
    echo "Examples:"
    echo "  $0 feature 'add csv export' 123"
    echo "  $0 bugfix 'fix login error'"
    echo "  $0 hotfix 'critical api bug' 456"
    exit 1
fi

TYPE=$1
DESCRIPTION=$2
TICKET_ID=$3

# Validate type
VALID_TYPES="feature bugfix hotfix release chore docs test refactor experiment"
if ! echo "$VALID_TYPES" | grep -qw "$TYPE"; then
    echo "❌ Invalid type: $TYPE"
    echo "Valid types: $VALID_TYPES"
    exit 1
fi

# Convert description to kebab-case
KEBAB_DESC=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

# Build branch name
if [ -n "$TICKET_ID" ]; then
    BRANCH_NAME="$TYPE/$TICKET_ID-$KEBAB_DESC"
else
    BRANCH_NAME="$TYPE/$KEBAB_DESC"
fi

# Check length
if [ ${#BRANCH_NAME} -gt 50 ]; then
    echo "⚠️  Warning: Branch name is ${#BRANCH_NAME} characters (recommended: <50)"
    echo "Branch name: $BRANCH_NAME"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Determine base branch
if [ "$TYPE" = "hotfix" ]; then
    BASE_BRANCH="main"
else
    BASE_BRANCH="develop"
fi

# Create branch
echo "Creating branch: $BRANCH_NAME from $BASE_BRANCH"
git checkout $BASE_BRANCH
git pull origin $BASE_BRANCH
git checkout -b $BRANCH_NAME

echo "✅ Branch created: $BRANCH_NAME"
echo "Base: $BASE_BRANCH"
```

**Usage:**
```bash
chmod +x scripts/new-branch.sh

# With ticket ID
./scripts/new-branch.sh feature "add csv export" 123
# Creates: feature/123-add-csv-export

# Without ticket ID
./scripts/new-branch.sh bugfix "fix pagination error"
# Creates: bugfix/fix-pagination-error
```

### List Stale Branches

Save as `scripts/list-stale-branches.sh`:

```bash
#!/bin/bash

# Find branches not updated in 30+ days

echo "Branches not updated in 30+ days:"
echo ""

for branch in $(git branch -r | grep -v 'HEAD\|main\|develop'); do
    LAST_COMMIT_DATE=$(git log -1 --format=%ci "$branch")
    DAYS_AGO=$(( ($(date +%s) - $(date -d "$LAST_COMMIT_DATE" +%s)) / 86400 ))
    
    if [ $DAYS_AGO -gt 30 ]; then
        echo "$branch - Last updated $DAYS_AGO days ago"
    fi
done
```

**Usage:**
```bash
chmod +x scripts/list-stale-branches.sh
./scripts/list-stale-branches.sh
```

---

## Branch Naming Anti-Patterns

### ❌ Bad Examples

```bash
# Too vague
feature/updates
bugfix/fix
feature/changes

# Using underscores
feature/add_csv_export

# Using uppercase
Feature/Add-CSV-Export
FEATURE/CSV-EXPORT

# Too long
feature/123-add-comprehensive-csv-export-functionality-with-multiple-formats

# No prefix
add-csv-export
fix-bug

# Wrong prefix
new/feature
fix/something
```

### ✅ Good Examples

```bash
feature/123-add-csv-export
bugfix/456-fix-login-redirect
hotfix/critical-memory-leak
release/v1.0.0
chore/upgrade-dependencies
docs/update-api-guide
test/add-report-tests
refactor/simplify-auth
experiment/ai-recommendations
```

---

## Quick Reference

### Common Commands

```bash
# Create feature branch
git checkout -b feature/123-add-export develop

# Create bugfix branch
git checkout -b bugfix/456-fix-error develop

# Create hotfix branch
git checkout -b hotfix/critical-bug main

# Rename current branch
git branch -m new-branch-name

# List all branches
git branch -a

# Delete local branch
git branch -d feature/123-add-export

# Delete remote branch
git push origin --delete feature/123-add-export

# Show branch last commit date
git for-each-ref --sort=-committerdate refs/heads/ --format='%(committerdate:short) %(refname:short)'
```

### Branch Type Quick Reference

| Type | Base | Merge To | Example |
|------|------|----------|---------|
| `feature/` | develop | develop | `feature/123-add-export` |
| `bugfix/` | develop | develop | `bugfix/456-fix-login` |
| `hotfix/` | main | main + develop | `hotfix/critical-bug` |
| `release/` | develop | main + develop | `release/v1.0.0` |
| `chore/` | develop | develop | `chore/update-deps` |
| `docs/` | develop | develop | `docs/update-readme` |
| `test/` | develop | develop | `test/add-api-tests` |
| `refactor/` | develop | develop | `refactor/split-views` |
| `experiment/` | develop | develop (optional) | `experiment/ai-feature` |

---

**Last Updated:** 2025-12-31  
**Maintainer:** Tech Lead  
**Review Schedule:** Annually
