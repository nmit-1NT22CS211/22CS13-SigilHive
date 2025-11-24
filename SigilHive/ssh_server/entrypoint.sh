#!/bin/bash
set -e

echo "SSH Honeypot: Starting up..."

# Verify SSH host key is available; if missing, generate a fallback (dev-friendly)
SSH_KEY_PATH="${SSH_HOST_KEY_PATH:-/run/secrets/ssh_host_key}"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "WARNING: SSH host key not found at $SSH_KEY_PATH"
    echo "-> continuing without pre-mounted host key; the honeypot will generate one at runtime if supported."
else
    # Set correct permissions on SSH host key
    chmod 600 "$SSH_KEY_PATH" 2>/dev/null || true
    echo "SSH host key verified at $SSH_KEY_PATH."
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
echo "Starting SSH Honeypot on port ${PORT:-2223}..."

exec "$@"