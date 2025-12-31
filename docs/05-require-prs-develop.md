# Pull Request Requirements - MarketNavigator v2

## Purpose
Establish mandatory pull request (PR) requirements and review processes to ensure code quality, knowledge sharing, and prevent bugs from reaching production.

---

## PR Requirements by Target Branch

### Pull Requests to `main` Branch

**Requirements (ALL must be met):**
- ✅ At least **1 approval** from senior developer or tech lead
- ✅ All automated CI/CD checks pass (tests, linting, build)
- ✅ All conversation threads resolved
- ✅ Branch is up-to-date with main (no merge conflicts)
- ✅ Linear history (must use squash or rebase merge)
- ✅ Linked to issue/ticket (format: `Fixes #123` or `Closes #456`)
- ✅ Deployment plan documented (for breaking changes)

**Optional but Recommended:**
- 🟡 2+ approvals for high-risk changes (database schema, authentication, payment)
- 🟡 Security review for changes touching authentication, permissions, or sensitive data
- 🟡 Performance testing for changes affecting database queries or APIs

### Pull Requests to `develop` Branch

**Requirements:**
- ✅ At least **1 approval** (can be any team member)
- ✅ All automated tests pass
- ✅ Basic code review (logic, style, best practices)
- ✅ No obvious bugs or security issues

**Optional:**
- 🟡 Self-review acceptable for minor fixes (typos, formatting)
- 🟡 Can merge without approval if urgent AND all tests pass (document reason)

---

## PR Creation Guidelines

### Step 1: Create Feature Branch

```bash
# Always branch from develop (not main)
git checkout develop
git pull origin develop
git checkout -b feature/add-export-reports

# Work on feature
git add .
git commit -m "feat: Add CSV export for reports"
git push origin feature/add-export-reports
```

### Step 2: Create Pull Request

**Using GitHub CLI:**
```bash
gh pr create \
  --base develop \
  --head feature/add-export-reports \
  --title "feat: Add CSV export for reports" \
  --body "Implements CSV export functionality for reports. Closes #123"
```

**Using GitHub Web UI:**
1. Go to repository on GitHub
2. Click "Pull requests" tab
3. Click "New pull request"
4. Base: `develop`, Compare: `feature/add-export-reports`
5. Fill in PR template (see below)
6. Click "Create pull request"

### Step 3: Fill PR Template

Use this template for ALL pull requests:

```markdown
## Description
Brief description of what this PR does and why.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Related Issue
Closes #<issue-number>

## Changes Made
- Added CSV export button to reports page
- Created new endpoint `/api/reports/{id}/export/csv`
- Added Celery task for async export generation
- Updated frontend to handle download

## Testing Done
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Tested on local environment
- [ ] Tested on staging environment (if applicable)

## Screenshots (if applicable)
![Screenshot](url-to-screenshot)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (if needed)
- [ ] No new warnings introduced
- [ ] Database migrations created (if needed)
- [ ] Environment variables documented (if new vars added)

## Deployment Notes
- No special deployment steps required
- OR: Requires running migrations: `python manage.py migrate`
- OR: Requires new environment variable: `EXPORT_MAX_ROWS=10000`

## Rollback Plan (for breaking changes)
If this causes issues, revert with: `git revert <commit-sha>`
```

**Save as:** `.github/pull_request_template.md` (GitHub will auto-populate PRs)

---

## Code Review Process

### Reviewer Responsibilities

#### 1. Functional Review
- ✅ Does the code do what it claims?
- ✅ Are edge cases handled?
- ✅ Are error messages clear and helpful?
- ✅ Is the user experience intuitive?

#### 2. Code Quality Review
- ✅ Is the code readable and maintainable?
- ✅ Are variable/function names descriptive?
- ✅ Is there unnecessary code duplication?
- ✅ Are functions/methods too long (>50 lines)?
- ✅ Is complexity reasonable (avoid over-engineering)?

#### 3. Security Review
- ✅ Is user input validated and sanitized?
- ✅ Are SQL queries parameterized (no SQL injection)?
- ✅ Are authentication/authorization checks present?
- ✅ Are secrets hardcoded? (should use env vars)
- ✅ Are sensitive data logged?

#### 4. Performance Review
- ✅ Are database queries optimized? (avoid N+1 queries)
- ✅ Are large datasets paginated?
- ✅ Are expensive operations cached?
- ✅ Are background tasks used for slow operations?

#### 5. Testing Review
- ✅ Are there sufficient unit tests?
- ✅ Do tests cover edge cases?
- ✅ Are test names descriptive?
- ✅ Do all tests pass?

### How to Review a Pull Request

#### Step 1: Checkout PR Locally

```bash
# Method 1: Using GitHub CLI
gh pr checkout 123

# Method 2: Using Git
git fetch origin pull/123/head:pr-123
git checkout pr-123
```

#### Step 2: Run Tests Locally

```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test

# Run linters
flake8 backend/
cd frontend && npm run lint
```

#### Step 3: Test Functionality

```bash
# Start services
docker-compose up -d

# Test the feature manually
# - Navigate to affected pages
# - Try edge cases (empty input, special characters, etc.)
# - Check browser console for errors
# - Verify database changes (if applicable)
```

#### Step 4: Review Code in GitHub

**Line-by-line comments:**
- Click on line number to add comment
- Be specific: "Consider extracting this into a separate function"
- Suggest code: Use ```python suggestion syntax
- Use "Request changes" for blocking issues
- Use "Comment" for minor suggestions
- Use "Approve" when ready to merge

**Example comments:**

**Blocking issue:**
```
🚫 This query could cause N+1 problem with large datasets.
Consider using `select_related('organization')`:

```python suggestion
reports = Report.objects.filter(user=user).select_related('organization')
```
```

**Minor suggestion:**
```
💡 Consider adding a docstring to explain the algorithm:

```python suggestion
def calculate_score(metrics):
    """
    Calculates weighted score based on multiple metrics.
    
    Args:
        metrics (dict): Dictionary of metric names to values
    
    Returns:
        float: Weighted score between 0-100
    """
    ...
```
```

**Praise:**
```
✅ Great use of type hints! This makes the code much more maintainable.
```

#### Step 5: Provide Final Review

**Approve:**
- Click "Review changes" → "Approve"
- Add comment: "LGTM! 🚀" (Looks Good To Me)

**Request changes:**
- Click "Review changes" → "Request changes"
- Summarize blocking issues
- PR author must address and re-request review

**Comment only:**
- For minor suggestions that don't block merge
- Author can choose to address now or create follow-up issue

---

## PR Merge Strategies

### Squash and Merge (Recommended for Most PRs)

**When to use:** Feature branches with multiple commits

**Benefits:**
- Clean, linear history
- One commit per feature in main branch
- Easy to revert entire feature

**How to:**
```bash
# GitHub UI: Click "Squash and merge"

# Or via CLI:
gh pr merge 123 --squash
```

**Commit message format:**
```
feat: Add CSV export for reports (#123)

- Added CSV export button
- Created export API endpoint
- Added Celery task for async generation

Co-authored-by: John Doe <john@example.com>
```

### Rebase and Merge

**When to use:** PRs with clean, atomic commits that tell a story

**Benefits:**
- Preserves individual commits
- Maintains linear history
- Good for bug fixes with clear progression

**How to:**
```bash
# GitHub UI: Click "Rebase and merge"

# Or via CLI:
gh pr merge 123 --rebase
```

### Merge Commit (Not Recommended)

**When to use:** Rarely (creates merge commits)

**Drawback:** Clutters history with merge commits

---

## Automated PR Checks

### Required Status Checks

Create `.github/workflows/pr-checks.yml`:

```yaml
name: PR Checks

on:
  pull_request:
    branches: [main, develop]

jobs:
  backend-lint:
    name: Backend Linting
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install flake8 black isort
      - name: Run flake8
        run: flake8 backend/ --max-line-length=120 --exclude=migrations
      - name: Check black formatting
        run: black --check backend/
      - name: Check isort
        run: isort --check-only backend/

  backend-tests:
    name: Backend Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        env:
          DB_HOST: localhost
          DB_PORT: 5432
          DB_NAME: postgres
          DB_USER: postgres
          DB_PASSWORD: postgres
          REDIS_URL: redis://localhost:6379/0
        run: |
          cd backend
          python manage.py test --verbosity=2

  frontend-lint:
    name: Frontend Linting
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run ESLint
        run: |
          cd frontend
          npm run lint

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Build
        run: |
          cd frontend
          npm run build

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
```

### PR Size Checker

Add to GitHub Actions:

```yaml
  pr-size:
    name: Check PR Size
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check PR size
        run: |
          CHANGED_FILES=$(git diff --name-only origin/${{ github.base_ref }}...HEAD | wc -l)
          CHANGED_LINES=$(git diff --shortstat origin/${{ github.base_ref }}...HEAD | awk '{print $4 + $6}')
          
          echo "Changed files: $CHANGED_FILES"
          echo "Changed lines: $CHANGED_LINES"
          
          if [ $CHANGED_FILES -gt 50 ] || [ $CHANGED_LINES -gt 1000 ]; then
            echo "⚠️ Warning: This PR is quite large. Consider splitting into smaller PRs."
            echo "Changed files: $CHANGED_FILES (recommended: <50)"
            echo "Changed lines: $CHANGED_LINES (recommended: <1000)"
          fi
```

---

## PR Labels

Use labels to categorize PRs:

| Label | Color | When to Use |
|-------|-------|-------------|
| `bug` | #d73a4a | Bug fixes |
| `feature` | #0e8a16 | New features |
| `enhancement` | #a2eeef | Improvements to existing features |
| `documentation` | #0075ca | Documentation changes |
| `breaking-change` | #d93f0b | Changes that break backward compatibility |
| `urgent` | #ff0000 | Requires immediate attention |
| `work-in-progress` | #fbca04 | Not ready for review |
| `needs-review` | #008672 | Ready for review |
| `security` | #ee0701 | Security-related changes |
| `performance` | #5319e7 | Performance improvements |
| `dependencies` | #0366d6 | Dependency updates |

**Auto-label with GitHub Actions:**

```yaml
  label-pr:
    name: Auto-label PR
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v4
        with:
          repo-token: "${{ secrets.GITHUB_TOKEN }}"
```

Create `.github/labeler.yml`:

```yaml
documentation:
  - '**/*.md'
  - 'docs/**/*'

backend:
  - 'backend/**/*'

frontend:
  - 'frontend/**/*'

dependencies:
  - 'backend/requirements.txt'
  - 'frontend/package.json'
  - 'frontend/package-lock.json'
```

---

## PR Etiquette

### For PR Authors

**Do:**
- ✅ Keep PRs small and focused (one feature/fix per PR)
- ✅ Write clear PR descriptions
- ✅ Link to related issues
- ✅ Respond to review comments within 24 hours
- ✅ Mark conversations as resolved after addressing
- ✅ Test thoroughly before requesting review
- ✅ Keep PR updated with base branch (rebase regularly)

**Don't:**
- ❌ Create huge PRs (>500 lines changed)
- ❌ Mix unrelated changes in one PR
- ❌ Force-push after someone started reviewing (breaks their comments)
- ❌ Merge without addressing review comments
- ❌ Take review comments personally (it's about code, not you)

### For Reviewers

**Do:**
- ✅ Review within 48 hours (or notify author if delayed)
- ✅ Be constructive and specific in feedback
- ✅ Praise good code (not just criticize)
- ✅ Suggest improvements, don't demand
- ✅ Explain WHY when requesting changes
- ✅ Approve PRs promptly when satisfied

**Don't:**
- ❌ Nitpick minor style issues (use linters instead)
- ❌ Block PRs for personal preference differences
- ❌ Approve without actually reviewing
- ❌ Leave vague comments ("this is bad")
- ❌ Request changes without explaining how to fix

---

## Review Response Time SLAs

| PR Type | Review SLA | Approval SLA |
|---------|-----------|--------------|
| **Hotfix (production down)** | 15 minutes | 30 minutes |
| **Urgent (blocking other work)** | 4 hours | 1 day |
| **Feature (normal priority)** | 1 day | 2 days |
| **Documentation** | 2 days | 3 days |
| **Dependencies** | 1 day | 2 days |

**If SLA not met:**
- Author can ping reviewer in Slack
- Tech lead can re-assign to another reviewer
- For urgent PRs, any team member can review

---

## Common PR Mistakes and How to Avoid Them

### Mistake 1: Creating PR from main branch

**Problem:** Can't merge because you'd be merging main into main

**Solution:**
```bash
# Always branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
```

### Mistake 2: Committing secrets/credentials

**Problem:** API keys in code

**Solution:**
```bash
# Before committing, scan for secrets
git diff --cached | grep -i 'api_key\|password\|secret'

# Use environment variables
API_KEY = os.getenv('API_KEY')  # Good
API_KEY = 'sk-abc123'  # BAD!
```

### Mistake 3: Not updating with base branch

**Problem:** Merge conflicts prevent merging

**Solution:**
```bash
# Regularly rebase on develop
git checkout develop
git pull origin develop
git checkout feature/my-feature
git rebase develop

# Resolve conflicts if any
git rebase --continue

# Force push (safe for feature branches)
git push --force-with-lease
```

### Mistake 4: Breaking existing tests

**Problem:** Your changes broke unrelated tests

**Solution:**
```bash
# Run full test suite before creating PR
python manage.py test  # Backend
npm test  # Frontend

# Fix any broken tests BEFORE creating PR
```

### Mistake 5: Incomplete PR description

**Problem:** Reviewers don't understand what PR does

**Solution:**
- Use PR template (fills in automatically)
- Include screenshots for UI changes
- Link to design docs for complex features
- Explain WHY, not just WHAT

---

## PR Metrics and Monitoring

### Track These Metrics

1. **Time to First Review:** Should be <1 day
2. **Time to Merge:** Should be <3 days
3. **Review Cycles:** Should be <3 iterations
4. **PR Size:** Should be <400 lines changed
5. **PR Rejection Rate:** Should be <10%

### Dashboard (Example using GitHub API)

```bash
# Average time to merge (last 30 days)
gh api graphql -f query='
{
  repository(owner:"your-org", name:"MarketNavigator2.0") {
    pullRequests(first:100, states:MERGED, orderBy:{field:UPDATED_AT, direction:DESC}) {
      nodes {
        title
        createdAt
        mergedAt
      }
    }
  }
}' | jq '.data.repository.pullRequests.nodes[] | 
  ((.mergedAt | fromdateiso8601) - (.createdAt | fromdateiso8601)) / 86400' | 
  awk '{sum+=$1; count++} END {print sum/count " days"}'
```

---

## Quick Reference Commands

```bash
# Create PR from CLI
gh pr create --base develop --head feature/my-feature --fill

# List open PRs
gh pr list

# View PR status
gh pr status

# Checkout PR for local testing
gh pr checkout 123

# Request review from specific person
gh pr edit 123 --add-reviewer @username

# Merge PR
gh pr merge 123 --squash --delete-branch

# View PR diff
gh pr diff 123

# Add label to PR
gh pr edit 123 --add-label "urgent"
```

---

**Last Updated:** 2025-12-31  
**Maintainer:** Tech Lead  
**Review Schedule:** Quarterly
