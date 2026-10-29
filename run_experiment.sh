#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}"

echo "======================================================================"
echo " Starting Solana Validator Transaction Ordering Experiment Runner"
echo "======================================================================"

python3 "${SCRIPT_DIR}/cli.py" "$@"
