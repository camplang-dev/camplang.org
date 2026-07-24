#!/usr/bin/env bash
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
	echo "error: tailscale is required to expose camplang.org over HTTPS." >&2
	exit 1
fi

tailscale serve --bg --yes --https=443 http://127.0.0.1:1111

dns_name="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"].get("DNSName", "").rstrip("."))')"
if [[ -n "$dns_name" ]]; then
	echo "HTTPS site is available at: https://$dns_name/"
fi
