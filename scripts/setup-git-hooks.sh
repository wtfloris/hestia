#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

chmod +x .githooks/check-sql-secrets.sh .githooks/pre-commit .githooks/pre-push
git config core.hooksPath .githooks

echo "Git hooks enabled via core.hooksPath=.githooks"
echo "Current hooksPath: $(git config --get core.hooksPath)"

