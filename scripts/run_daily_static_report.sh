#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ -f .env.1password ]]; then
  scripts/run_with_1password.sh research-copilot discover --universe all --candidate-limit 25 --top 10 --analyze-top 3 --format md
else
  research-copilot discover --universe all --candidate-limit 25 --top 10 --analyze-top 3 --format md
fi

python scripts/export_static_research_site.py --top 12
