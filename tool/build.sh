#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v zola >/dev/null 2>&1; then
	echo "error: zola is required to build camplang.org." >&2
	echo "install with: brew install zola" >&2
	exit 1
fi

python3 "$ROOT/tool/prepare.py"
zola --root "$ROOT/tool/staging" build --output-dir "$ROOT/public" --force
