#!/bin/bash
set -e

echo "HTTP Honeypot: Starting up..."

# Verify TLS certificates are available; if missing, allow the app to generate them
TLS_CERT="${TLS_CERT_PATH:-/run/secrets/shophub_cert}"
TLS_KEY="${TLS_KEY_PATH:-/run/secrets/shophub_key}"
if [ ! -f "$TLS_CERT" ]; then
    echo "WARNING: TLS certificate not found at $TLS_CERT"
    echo "-> continuing; the honeypot will generate a self-signed certificate at runtime if supported."
else
    echo "TLS certificate found at $TLS_CERT"
fi

if [ ! -f "$TLS_KEY" ]; then
    echo "WARNING: TLS private key not found at $TLS_KEY"
    echo "-> continuing; the honeypot will generate a self-signed key at runtime if supported."
else
    echo "TLS private key found at $TLS_KEY"
fi

# Wait for Kafka to be ready
KAFKA_HOST="${KAFKA_BOOTSTRAP_SERVERS%%:*}"
KAFKA_PORT="${KAFKA_BOOTSTRAP_SERVERS##*:}"

echo "Waiting for Kafka at ${KAFKA_HOST}:${KAFKA_PORT}..."

MAX_RETRIES=30
RETRY_COUNT=0

while ! nc -z "$KAFKA_HOST" "$KAFKA_PORT" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Kafka not available after ${MAX_RETRIES} attempts. Exiting."
        exit 1
    fi
    echo "Kafka not ready yet (attempt ${RETRY_COUNT}/${MAX_RETRIES}). Retrying in 2s..."
    sleep 2
done

echo "Kafka is ready!"
echo "Starting HTTP Honeypot on port ${HTTPS_PORT:-8443}..."

exec "$@"