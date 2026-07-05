#!/usr/bin/env bash
# Thin wrapper around rename-product.py for Unix users.
# Usage: ./scripts/rename-product.sh <name> [--dry-run] [--verbose]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/rename-product.py" "$@"
