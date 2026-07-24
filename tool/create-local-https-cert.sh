#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/.local/https"
mkdir -p "$CERT_DIR"

dns_name="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"].get("DNSName", "").rstrip("."))' 2>/dev/null || true)"
tailscale_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"

if [[ -z "$dns_name" ]]; then
	dns_name="localhost"
fi

cat > "$CERT_DIR/rootCA.conf" <<EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_ca

[dn]
CN = Camp Website Local Development Root CA

[v3_ca]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical,CA:true
keyUsage = critical,keyCertSign,cRLSign
EOF

if [[ ! -f "$CERT_DIR/rootCA.key.pem" || ! -f "$CERT_DIR/rootCA.pem" ]]; then
	openssl genrsa -out "$CERT_DIR/rootCA.key.pem" 4096
	openssl req -x509 -new -nodes \
		-key "$CERT_DIR/rootCA.key.pem" \
		-sha256 \
		-days 3650 \
		-config "$CERT_DIR/rootCA.conf" \
		-out "$CERT_DIR/rootCA.pem"
fi

openssl x509 -outform der -in "$CERT_DIR/rootCA.pem" -out "$CERT_DIR/rootCA.cer"

cat > "$CERT_DIR/server.conf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = san_ext

[dn]
CN = $dns_name

[san_ext]
subjectAltName = @alt_names

[server_cert]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer

[alt_names]
DNS.1 = $dns_name
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

if [[ -n "$tailscale_ip" ]]; then
	echo "IP.2 = $tailscale_ip" >> "$CERT_DIR/server.conf"
fi

openssl genrsa -out "$CERT_DIR/server.key.pem" 2048
openssl req -new \
	-key "$CERT_DIR/server.key.pem" \
	-out "$CERT_DIR/server.csr.pem" \
	-config "$CERT_DIR/server.conf"
openssl x509 -req \
	-in "$CERT_DIR/server.csr.pem" \
	-CA "$CERT_DIR/rootCA.pem" \
	-CAkey "$CERT_DIR/rootCA.key.pem" \
	-CAcreateserial \
	-out "$CERT_DIR/server.crt.pem" \
	-days 397 \
	-sha256 \
	-extfile "$CERT_DIR/server.conf" \
	-extensions server_cert

cat "$CERT_DIR/server.crt.pem" "$CERT_DIR/rootCA.pem" > "$CERT_DIR/server.fullchain.pem"

if [[ -d "$ROOT/tool/staging/static" ]]; then
	cp "$CERT_DIR/rootCA.cer" "$ROOT/tool/staging/static/camp-local-root-ca.cer"
fi

echo "Created local HTTPS certificate for: $dns_name"
if [[ -n "$tailscale_ip" ]]; then
	echo "Included Tailscale IP SAN: $tailscale_ip"
fi
echo "Install and fully trust this root certificate on clients that need it:"
echo "$CERT_DIR/rootCA.cer"
