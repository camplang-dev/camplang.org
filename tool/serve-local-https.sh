#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! curl -fsS --max-time 2 http://127.0.0.1:1111/ >/dev/null; then
	echo "error: the Zola server is not responding at http://127.0.0.1:1111/." >&2
	echo "start it first with: tool/serve.sh" >&2
	exit 1
fi

"$ROOT/tool/create-local-https-cert.sh"
node "$ROOT/tool/serve-local-https.js"
