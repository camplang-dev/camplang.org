#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(cd "$ROOT/.." && pwd)"

CAMPC="${CAMPC:-$WORKSPACE/dev/bin/campc}"
DEV_ROOT="${CAMP_DEV_ROOT:-$WORKSPACE/dev}"
OUTPUT_ROOT="${CAMP_API_SRC:-$ROOT/api-src}"

if [ ! -x "$CAMPC" ]; then
	echo "error: campc was not found or is not executable: $CAMPC" >&2
	echo "set CAMPC=/path/to/campc to use a different compiler." >&2
	exit 1
fi

mkdir -p "$OUTPUT_ROOT/stdlib"
"$CAMPC" --version > "$OUTPUT_ROOT/campc-version.txt"

tmp="$(mktemp "${TMPDIR:-/tmp}/camp-api-docs.XXXXXX")"
cleanup() {
	rm -f "$tmp"
}
trap cleanup EXIT

generate_metadata() {
	local output="$1"
	shift

	"$CAMPC" dump metadata "$@" > "$tmp"
	python3 - "$tmp" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if data.get("format") != "camp.metadata":
    raise SystemExit("metadata output did not use format 'camp.metadata'")
if data.get("version") != 1:
    raise SystemExit(f"unsupported metadata version: {data.get('version')}")
PY
	cp "$tmp" "$output"
}

generate_metadata "$OUTPUT_ROOT/stdlib/std_api.json" \
	"$DEV_ROOT/lib/std/src/"*.camp \
	--metadata public \
	--nostdlib

if [ "${CAMP_GENERATE_PACKAGE_API_DOCS:-}" = "1" ]; then
	PACKAGE_ROOT="${CAMP_PACKAGE_ROOT:-$WORKSPACE/pkg.camplang.org}"
	if [ -d "$PACKAGE_ROOT/ext-json/src" ]; then
		mkdir -p "$OUTPUT_ROOT/packages/ext-json"
		generate_metadata "$OUTPUT_ROOT/packages/ext-json/ext_json_api.json" \
			"$PACKAGE_ROOT/ext-json/src/"*.camp \
			--metadata public
	fi
fi

echo "generated API metadata in $OUTPUT_ROOT"
