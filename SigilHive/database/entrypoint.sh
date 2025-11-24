#!/bin/bash
set -e

echo "Database Honeypot: Starting up..."

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
echo "Starting Database Honeypot on port ${MYSQL_PORT:-2222}..."

exec "$@"