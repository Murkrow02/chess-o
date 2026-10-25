#!/bin/sh
# Make sure nginx has a certificate for HTTPS (browsers only install a PWA over HTTPS).
#
# If /certs/cert.pem and /certs/key.pem exist they are used as they are, so you can mount your
# own. Otherwise a private certificate authority is created once (kept in the volume) and used
# to sign a server certificate for TLS_HOSTS. Trust /ca.crt on your devices and the warning goes
# away. The server certificate is re-issued when TLS_HOSTS changes.
set -eu
DIR=/certs
HOSTS="${TLS_HOSTS:-localhost}"
mkdir -p "$DIR"

if [ -f "$DIR/cert.pem" ] && [ -f "$DIR/key.pem" ] && [ ! -f "$DIR/.generated" ]; then
  echo "certs: using the certificate mounted in $DIR"
  exit 0
fi

if [ ! -f "$DIR/ca.key" ]; then
  echo "certs: creating a private certificate authority"
  openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
    -keyout "$DIR/ca.key" -out "$DIR/ca.crt" -subj "/CN=chess-o local CA/O=chess-o" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
fi

if [ -f "$DIR/cert.pem" ] && [ "$(cat "$DIR/.generated")" = "$HOSTS" ]; then
  echo "certs: certificate for $HOSTS is in place"
else
  echo "certs: issuing a certificate for $HOSTS"
  SAN=""
  for h in $(echo "$HOSTS" | tr ',' ' '); do
    if echo "$h" | grep -Eq '^[0-9.]+$|:'; then SAN="$SAN,IP:$h"; else SAN="$SAN,DNS:$h"; fi
  done
  SAN="${SAN#,}"
  FIRST=$(echo "$HOSTS" | cut -d, -f1)
  openssl req -newkey rsa:2048 -nodes -sha256 -keyout "$DIR/key.pem" -out "$DIR/server.csr" \
    -subj "/CN=$FIRST/O=chess-o" 2>/dev/null
  printf 'basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=%s\n' "$SAN" > "$DIR/server.ext"
  # 825 days is the longest validity iOS accepts for a server certificate.
  openssl x509 -req -in "$DIR/server.csr" -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial \
    -days 825 -sha256 -extfile "$DIR/server.ext" -out "$DIR/cert.pem" 2>/dev/null
  rm -f "$DIR/server.csr" "$DIR/server.ext"
  echo "$HOSTS" > "$DIR/.generated"
fi
chmod 600 "$DIR/ca.key" "$DIR/key.pem"
cp "$DIR/ca.crt" /usr/share/nginx/html/ca.crt
