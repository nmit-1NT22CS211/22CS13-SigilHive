#!/usr/bin/env bash
# Create Kafka topics used by the honeypots (run from project root)
set -euo pipefail

TOPICS=(DBtoSSH HTTPtoSSH SSHtoDB HTTPtoDB SSHtoHTTP DBtoHTTP)

for t in "${TOPICS[@]}"; do
  echo "Creating topic: $t"
  docker compose exec -T kafka kafka-topics --create --if-not-exists --topic "$t" --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 || true
done

echo "Topic creation finished."
