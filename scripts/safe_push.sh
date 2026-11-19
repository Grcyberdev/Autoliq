#!/usr/bin/env bash
set -euo pipefail

MSG="${1:-Update liquor mappings}"
SKIP_CI="${2:-}"

if [ "$SKIP_CI" = "--skip-ci" ]; then
  MSG="$MSG [skip ci]"
fi

echo "🔍 Checking Python syntax..."
if [ -x "./env/bin/python3" ]; then
  ./env/bin/python3 -m py_compile scripts/*.py
else
  python3 -m py_compile scripts/*.py
fi
echo "✅ Syntax OK."

echo "🔄 Syncing with origin/main (auto-stashing local edits)..."
git pull --rebase --autostash origin main

echo "📦 Staging and committing..."
git add -A
if git diff --staged --quiet; then
  echo "ℹ️ Nothing to commit."
  exit 0
fi

git commit -m "$MSG"
echo "🚀 Pushing to origin/main..."
git push origin main
echo "✅ Done!"
