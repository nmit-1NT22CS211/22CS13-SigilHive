#!/usr/bin/env bash
# Initialize Kafka topics on startup
# This script waits for Kafka to be ready, then creates all required topics

set -e

KAFKA_HOST="${KAFKA_HOST:-kafka}"
KAFKA_PORT="${KAFKA_PORT:-9092}"

echo "[init-topics] Waiting for Kafka to be ready at ${KAFKA_HOST}:${KAFKA_PORT}..."

# Wait for Kafka to be ready
for i in {1..30}; do
    if nc -z "$KAFKA_HOST" "$KAFKA_PORT" 2>/dev/null; then
        echo "[init-topics] Kafka is ready!"
        break
    fi
    echo "[init-topics] Kafka not ready yet (attempt $i/30). Retrying in 2s..."
    sleep 2
done

# Create topics
TOPICS=(DBtoSSH HTTPtoSSH SSHtoDB HTTPtoDB SSHtoHTTP DBtoHTTP)

echo "[init-topics] Creating Kafka topics..."

for topic in "${TOPICS[@]}"; do
    echo "[init-topics] Creating topic: $topic"
    kafka-topics --create \
        --if-not-exists \
        --topic "$topic" \
        --bootstrap-server "${KAFKA_HOST}:${KAFKA_PORT}" \
        --partitions 1 \
        --replication-factor 1 \
        --config retention.ms=604800000 \
        2>&1 || echo "[init-topics] Topic $topic already exists or creation in progress"
done

echo "[init-topics] Topic creation completed!"
