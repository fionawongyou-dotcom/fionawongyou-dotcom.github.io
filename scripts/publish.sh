#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 scripts/build.py

git add .

if git diff --cached --quiet; then
  echo "No website changes to publish."
  exit 0
fi

git commit -m "Update website content $(date +%Y-%m-%d)"
git push
