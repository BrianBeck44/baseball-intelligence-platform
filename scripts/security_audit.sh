#!/usr/bin/env bash
set -u

ROOT="${1:-.}"
cd "$ROOT" || exit 1

echo "============================================================"
echo "Security Audit for: $(pwd)"
echo "============================================================"

# 1) Git status
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo
  echo "== Git status =="
  git status --short --branch
else
  echo
  echo "== Not a git repo =="
fi

# 2) Secret patterns
PATTERN='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|BEGIN [A-Z ]*PRIVATE KEY|-----BEGIN .*PRIVATE KEY-----|(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9/+=._:-]{8,}|postgresql://[^[:space:]]+:[^@[:space:]]+@)'

echo
echo "== Searching working tree for likely secrets =="
grep -RInE \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=node_modules \
  --exclude-dir=.idea \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.gif' \
  --exclude='*.svg' \
  --exclude='*.ico' \
  --exclude='*.pdf' \
  --binary-files=without-match \
  "$PATTERN" . 2>/dev/null || echo "No obvious secret patterns found in working tree."

echo
echo "== Likely secret-bearing filenames =="
find . \
  -type f \
  \( -iname '.env*' -o -iname '*.pem' -o -iname '*.key' -o -iname '*.p12' -o -iname '*.pfx' -o -iname '*.crt' -o -iname '*.cer' -o -iname '*.jks' -o -iname '*secret*' -o -iname '*token*' -o -iname '*password*' \) \
  ! -path './.git/*' \
  ! -path './node_modules/*' \
  ! -path './.venv/*' \
  -print 2>/dev/null | sed 's#^\./##' || true

echo
echo "== Files that look like config/env files =="
find . \
  -type f \
  \( -iname '.env' -o -iname '.env.*' -o -iname '*.env' -o -iname '*.env.*' -o -iname 'config.yml' -o -iname 'config.yaml' -o -iname '*.conf' -o -iname '*.ini' -o -iname '*.toml' -o -iname '*.properties' \) \
  ! -path './.git/*' \
  ! -path './node_modules/*' \
  ! -path './.venv/*' \
  -print 2>/dev/null | sed 's#^\./##' || true

# 3) Git history scan
echo
echo "== Checking git history for secret-like content =="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git rev-list --all >/dev/null 2>&1; then
    git log --all -p -- . \
      -- . ':(exclude)node_modules' ':(exclude).git' 2>/dev/null \
      | grep -nE "$PATTERN" -B2 -A6 || echo "No obvious secrets found in git history."
  else
    echo "No reachable commits found."
  fi
else
  echo "Not a git repo; skipped git history scan."
fi

echo
echo "== Recommended follow-up =="
echo "- Remove any .env files from git history if they contain real credentials."
echo "- Check GitHub Actions secrets, deployment configs, and local scripts."
echo "- If you find a secret, rotate it immediately and rewrite history if needed."
echo "- For stronger detection, run: git log -p --all -- .env .env.*"
echo "- Also check: git grep -nE 'AKIA|ghp_|BEGIN .*PRIVATE KEY|password|secret|token' $(git rev-list --all)"
echo
echo "============================================================"
echo "Audit complete."
echo "============================================================"