#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.1password"

if ! command -v op >/dev/null 2>&1; then
  echo "1Password CLI 'op' is not installed." >&2
  exit 127
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.1password.example and fill it with op:// references." >&2
  exit 2
fi

cd "${ROOT}"
source .venv/bin/activate
exec op run --env-file "${ENV_FILE}" -- "$@"
