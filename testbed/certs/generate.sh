#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$ROOT_DIR/../.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/../.env"
  set +a
fi
VALIDITY_DAYS="${CERT_VALIDITY_DAYS:-365}"
NEAR_EXPIRY_DAYS="${CERT_NEAR_EXPIRY_DAYS:-15}"
FORCE_CERT_REGEN="${FORCE_CERT_REGEN:-0}"

mkdir -p "$ROOT_DIR"/{ca,web,web-ec,pqc-tls,mqtt,mail,mail-imaps,db,ipsec}

if [[ ! -f "$ROOT_DIR/ca/root.key" ]]; then
  openssl genrsa -out "$ROOT_DIR/ca/root.key" 4096
  openssl req -x509 -new -nodes \
    -key "$ROOT_DIR/ca/root.key" \
    -sha256 \
    -days "$VALIDITY_DAYS" \
    -subj "/CN=Crypto Scanner Testbed Root CA/O=Crypto Scanner Testbed" \
    -out "$ROOT_DIR/ca/root.crt"
fi

sign_cert() {
  local name="$1"
  local cn="$2"
  local key_type="$3"
  local key_arg="$4"
  local days="${5:-$VALIDITY_DAYS}"
  local out_dir="$ROOT_DIR/$name"
  local ext_file="$out_dir/ext.cnf"

  mkdir -p "$out_dir"
  if [[ "$FORCE_CERT_REGEN" != "1" && -f "$out_dir/server.key" && -f "$out_dir/server.crt" ]]; then
    cp "$ROOT_DIR/ca/root.crt" "$out_dir/ca.crt"
    return
  fi
  if [[ "$key_type" == "rsa" ]]; then
    openssl genrsa -out "$out_dir/server.key" "$key_arg"
  else
    openssl ecparam -name "$key_arg" -genkey -noout -out "$out_dir/server.key"
  fi
  openssl req -new -key "$out_dir/server.key" -subj "/CN=$cn/O=Crypto Scanner Testbed" -out "$out_dir/server.csr"
  cat > "$ext_file" <<EOF
subjectAltName=DNS:$cn
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
  openssl x509 -req \
    -in "$out_dir/server.csr" \
    -CA "$ROOT_DIR/ca/root.crt" \
    -CAkey "$ROOT_DIR/ca/root.key" \
    -CAcreateserial \
    -out "$out_dir/server.crt" \
    -days "$days" \
    -sha256 \
    -extfile "$ext_file"
  chmod 600 "$out_dir/server.key"
  chmod 644 "$out_dir/server.crt"
  cp "$ROOT_DIR/ca/root.crt" "$out_dir/ca.crt"
}

sign_self_signed_cert() {
  local name="$1"
  local cn="$2"
  local key_type="$3"
  local key_arg="$4"
  local days="${5:-$VALIDITY_DAYS}"
  local out_dir="$ROOT_DIR/$name"
  local ext_file="$out_dir/ext.cnf"

  mkdir -p "$out_dir"
  if [[ "$FORCE_CERT_REGEN" != "1" && -f "$out_dir/server.key" && -f "$out_dir/server.crt" ]]; then
    cp "$out_dir/server.crt" "$out_dir/ca.crt"
    return
  fi
  if [[ "$key_type" == "rsa" ]]; then
    openssl genrsa -out "$out_dir/server.key" "$key_arg"
  else
    openssl ecparam -name "$key_arg" -genkey -noout -out "$out_dir/server.key"
  fi
  cat > "$ext_file" <<EOF
subjectAltName=DNS:$cn
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
  openssl req -x509 -new -nodes \
    -key "$out_dir/server.key" \
    -sha256 \
    -days "$days" \
    -subj "/CN=$cn/O=Crypto Scanner Testbed" \
    -out "$out_dir/server.crt" \
    -addext "subjectAltName=DNS:$cn" \
    -addext "extendedKeyUsage=serverAuth" \
    -addext "keyUsage=digitalSignature,keyEncipherment"
  chmod 600 "$out_dir/server.key"
  chmod 644 "$out_dir/server.crt"
  cp "$out_dir/server.crt" "$out_dir/ca.crt"
}

sign_cert "web" "web.testbed.local" "rsa" "2048"
sign_cert "web-ec" "web-ec.testbed.local" "ec" "prime256v1"
sign_cert "pqc-tls" "pqc-tls.testbed.local" "rsa" "2048"
sign_cert "mqtt" "mqtt.testbed.local" "rsa" "2048"
chmod 644 "$ROOT_DIR/mqtt/server.key"
sign_cert "mail" "mail.testbed.local" "rsa" "2048"
sign_cert "mail-imaps" "mail.testbed.local" "ec" "prime256v1"
sign_self_signed_cert "db" "db.testbed.local" "rsa" "1024"
sign_cert "ipsec" "ipsec.testbed.local" "rsa" "2048"

sign_cert "api-gateway" "api-gateway.testbed.local" "rsa" "2048"
sign_cert "admin-console" "admin-console.testbed.local" "ec" "prime256v1"
sign_cert "mobile-api" "mobile-api.testbed.local" "rsa" "2048"
sign_cert "auth-oidc" "auth-oidc.testbed.local" "rsa" "2048"
sign_cert "saml-idp" "saml-idp.testbed.local" "rsa" "2048"
sign_self_signed_cert "mysql-legacy" "mysql-legacy.testbed.local" "rsa" "1024"
sign_cert "redis-cache" "redis-cache.testbed.local" "rsa" "2048"
sign_cert "kafka-broker" "kafka-broker.testbed.local" "ec" "prime256v1"
sign_cert "internal-grpc" "internal-grpc.testbed.local" "rsa" "2048"
sign_cert "service-mesh-mtls" "service-mesh-mtls.testbed.local" "ec" "prime256v1"
sign_cert "gitlab-runner" "gitlab-runner.testbed.local" "rsa" "2048"
sign_cert "container-registry" "container-registry.testbed.local" "ec" "prime256v1"
sign_cert "artifact-repo" "artifact-repo.testbed.local" "rsa" "2048"
sign_cert "vault" "vault.testbed.local" "rsa" "4096"
sign_cert "backup-service" "backup-service.testbed.local" "rsa" "2048"
sign_cert "monitoring" "monitoring.testbed.local" "rsa" "2048"
sign_cert "logging" "logging.testbed.local" "rsa" "2048"
sign_self_signed_cert "legacy-java-app" "legacy-java-app.testbed.local" "rsa" "1024"

if [[ "$FORCE_CERT_REGEN" == "1" || ! -f "$ROOT_DIR/db/keystore.p12" ]]; then
  openssl pkcs12 -export \
    -inkey "$ROOT_DIR/db/server.key" \
    -in "$ROOT_DIR/db/server.crt" \
    -certfile "$ROOT_DIR/db/ca.crt" \
    -out "$ROOT_DIR/db/keystore.p12" \
    -passout pass:testbed
  chmod 600 "$ROOT_DIR/db/keystore.p12"
fi

if [[ "$FORCE_CERT_REGEN" == "1" || ! -f "$ROOT_DIR/web/legacy-rsa1024.key" || ! -f "$ROOT_DIR/web/legacy-rsa1024.crt" ]]; then
  openssl genrsa -out "$ROOT_DIR/web/legacy-rsa1024.key" 1024
  openssl req -x509 -new -nodes \
    -key "$ROOT_DIR/web/legacy-rsa1024.key" \
    -sha256 \
    -days "$NEAR_EXPIRY_DAYS" \
    -subj "/CN=legacy-rsa1024.web.testbed.local/O=Crypto Scanner Testbed" \
    -out "$ROOT_DIR/web/legacy-rsa1024.crt"
  chmod 600 "$ROOT_DIR/web/legacy-rsa1024.key"
  chmod 644 "$ROOT_DIR/web/legacy-rsa1024.crt"
fi

cat > "$ROOT_DIR/README.generated.txt" <<EOF
Generated testbed certificates.

pqc-tls/server.crt bootstraps the TLS 1.3 reference endpoint. The service
publishes ML-KEM/ML-DSA readiness metadata at /.well-known/pqc-readiness.json
so scanners can validate PQC asset handling without requiring an OQS build.
EOF
