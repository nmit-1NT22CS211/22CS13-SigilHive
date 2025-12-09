
import os
import sys
import time
import json
import requests
from kafka import KafkaConsumer
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

# Load environment variables from .env file
load_dotenv()

# Grafana Loki configuration
LOKI_URL = os.environ.get("LOKI_URL")
LOKI_USERNAME = os.environ.get("LOKI_USERNAME")
GRAFANA_DOCKER_API = os.environ.get("GRAFANA_DOCKER_API")

# Kafka configuration
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "honeypot-logs")

print(f"🔗 Grafana Connector Initialization")
print(f"📍 Kafka Broker: {KAFKA_BROKER}")
print(f"📍 Kafka Topic: {KAFKA_TOPIC}")
print(f"📍 Loki URL: {LOKI_URL}")
print(f"📍 Loki User: {LOKI_USERNAME}")
sys.stdout.flush()

def push_to_loki(log_entry):
    """Pushes a log entry to Grafana Loki."""
    if not LOKI_URL:
        print("❌ LOKI_URL not configured. Skipping push to Loki.")
        return

    headers = {"Content-type": "application/json"}
    
    # Ensure timestamp_ns is a proper integer in nanoseconds
    ts_ns = log_entry.get("timestamp_ns")
    if ts_ns is None or ts_ns == 0:
        ts_ns = str(int(time.time() * 1_000_000_000))
    else:
        ts_ns = str(int(float(ts_ns)))
    
    payload = {
        "streams": [
            {
                "stream": log_entry.get("labels", {"job": "honeypot"}),
                "values": [[ts_ns, log_entry.get("log", "")]]
            }
        ]
    }

    try:
        response = requests.post(
            LOKI_URL,
            auth=(LOKI_USERNAME, GRAFANA_DOCKER_API) if LOKI_USERNAME else None,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        print(f"✅ Pushed to Loki: service={log_entry.get('labels', {}).get('service')}, event_type={log_entry.get('labels', {}).get('event_type')}")
        sys.stdout.flush()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
        sys.stdout.flush()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error pushing to Loki: {e}")
        sys.stdout.flush()

def main():
    """Consumes messages from Kafka and pushes them to Grafana Loki."""
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            group_id="grafana-connector-loki"
        )
        print(f"✅ Connected to Kafka at {KAFKA_BROKER}")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        sys.stdout.flush()
        return

    print(f"🔄 Grafana Connector starting message consumption...")
    sys.stdout.flush()
    for message in consumer:
        log_data = message.value
        
        # Extract key fields for the log message
        service = log_data.get("service", "unknown")
        event_type = log_data.get("event_type", "log")
        session_id = log_data.get("session_id", "unknown")
        
        # Create a simple log message string (not JSON to avoid parsing issues)
        log_message = f"[{service.upper()}] {event_type} (session: {session_id})"
        if "command" in log_data:
            log_message += f" - {log_data.get('command', '')}"
        elif "path" in log_data:
            log_message += f" - {log_data.get('path', '')}"
        elif "query" in log_data:
            log_message += f" - {log_data.get('query', '')[:100]}"
        
        # Prepare the log entry for Loki
        loki_log_entry = {
            "labels": {
                "job": "honeypot",
                "service": service,
                "event_type": event_type
            },
            "timestamp_ns": str(int((log_data.get("timestamp", 0) or time.time()) * 1_000_000_000)),
            "log": log_message
        }

        push_to_loki(loki_log_entry)

if __name__ == "__main__":
    main()
