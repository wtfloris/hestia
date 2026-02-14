#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-check}"

staged_plain="$(git diff --cached --name-only --diff-filter=ACMR | grep -E '^misc/sql/.*\.sql$' || true)"

auto_encrypt_file() {
    local sql_file="$1"
    local enc_file="${sql_file}.enc"

    if [[ ! -f "$sql_file" ]]; then
        echo "Cannot auto-encrypt missing file: $sql_file"
        exit 1
    fi

    if ! command -v sops >/dev/null 2>&1; then
        echo "sops is not installed, cannot auto-encrypt $sql_file"
        exit 1
    fi

    if [[ -z "${SOPS_AGE_RECIPIENTS:-}" ]]; then
        echo "SOPS_AGE_RECIPIENTS is not set, cannot auto-encrypt $sql_file"
        echo "Example: export SOPS_AGE_RECIPIENTS='age1...'"
        exit 1
    fi

    echo "Auto-encrypting $sql_file -> $enc_file"
    sops --encrypt --age "$SOPS_AGE_RECIPIENTS" "$sql_file" > "$enc_file"
    git add "$enc_file"

    if git ls-files --error-unmatch "$sql_file" >/dev/null 2>&1; then
        git rm --cached -q "$sql_file"
    else
        git restore --staged "$sql_file" 2>/dev/null || true
    fi
}

if [[ -n "$staged_plain" ]]; then
    if [[ "$MODE" == "auto" ]]; then
        while IFS= read -r sql_file; do
            [[ -z "$sql_file" ]] && continue
            auto_encrypt_file "$sql_file"
        done <<< "$staged_plain"
    else
        echo "Plain SQL files are staged in misc/sql:"
        echo "$staged_plain"
        echo "Stage encrypted .sql.enc files instead."
        exit 1
    fi
fi

tracked_plain="$(git ls-files misc/sql | grep -E '\.sql$' || true)"
if [[ -n "$tracked_plain" ]]; then
    echo "Plain SQL files are tracked in git (not allowed):"
    echo "$tracked_plain"
    echo "Convert these to .sql.enc and remove plaintext from git."
    exit 1
fi
