"""
Metrics Collector Service
Collects, aggregates, and sends security metrics and alerts to Grafana Cloud
"""

import os
import sys
import json
import time
import asyncio
import requests
from datetime import datetime, timezone
from kafka import KafkaConsumer
from collections import defaultdict
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

# Load environment variables
load_dotenv()

# Configuration
LOKI_URL = os.environ.get("LOKI_URL")
LOKI_USERNAME = os.environ.get("LOKI_USERNAME")
GRAFANA_DOCKER_API = os.environ.get("GRAFANA_DOCKER_API")
PROMETHEUS_PUSHGATEWAY = os.environ.get("PROMETHEUS_PUSHGATEWAY", "http://localhost:9091")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL")  # For remote-write
PROMETHEUS_USERNAME = os.environ.get("PROMETHEUS_USERNAME")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "honeypot-logs")

class MetricsCollector:
    def __init__(self):
        self.metrics = {
            "ssh_attacks": 0,
            "http_attacks": 0,
            "database_attacks": 0,
            "sql_injection_attempts": 0,
            "privilege_escalation_attempts": 0,
            "reconnaissance_activities": 0,
            "total_sessions": 0,
            "active_sessions": defaultdict(int),
            "suspicious_commands": 0,
            "authentication_failures": 0,
            "policy_violations": 0,
        }
        
        self.alerts = []
        self.alert_threshold = 5  # Alert after N suspicious events
        self.suspicious_event_window = 300  # 5 minutes
        self.last_reset = time.time()
        
    def classify_threat_level(self, event_type: str, service: str) -> str:
        """Classify threat level based on event"""
        threat_patterns = {
            "privilege_escalation": "CRITICAL",
            "sql_injection": "CRITICAL",
            "authentication": "HIGH",
            "directory_traversal": "HIGH",
            "command_injection": "HIGH",
            "suspicious": "MEDIUM",
            "reconnaissance": "MEDIUM",
            "policy_violation": "LOW",
        }
        
        for pattern, level in threat_patterns.items():
            if pattern in event_type.lower():
                return level
        
        return "INFO"
    
    def process_event(self, event: dict) -> dict:
        """Process a security event and generate metrics"""
        service = event.get("service", "unknown").lower()
        event_type = event.get("event_type", "log").lower()
        session_id = event.get("session_id", "unknown")
        timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        
        # Update session tracking
        self.metrics["active_sessions"][session_id] = time.time()
        self.metrics["total_sessions"] = len(self.metrics["active_sessions"])
        
        # Classify and count events
        if service == "ssh":
            self.metrics["ssh_attacks"] += 1
            if "privilege_escalation" in event_type:
                self.metrics["privilege_escalation_attempts"] += 1
            if any(x in event_type for x in ["reconnaissance", "discovery", "probe"]):
                self.metrics["reconnaissance_activities"] += 1
        
        elif service == "http":
            self.metrics["http_attacks"] += 1
            if "sql" in event_type.lower() or "injection" in event_type.lower():
                self.metrics["sql_injection_attempts"] += 1
            if "directory" in event_type.lower() or "traversal" in event_type.lower():
                self.metrics["reconnaissance_activities"] += 1
        
        elif service == "database":
            self.metrics["database_attacks"] += 1
            if "sql" in event_type.lower() or "injection" in event_type.lower():
                self.metrics["sql_injection_attempts"] += 1
        
        # Detect suspicious patterns
        command = event.get("command") or event.get("path") or event.get("query", "")
        if self._is_suspicious_command(command):
            self.metrics["suspicious_commands"] += 1
        
        # Determine threat level
        threat_level = self.classify_threat_level(event_type, service)
        
        # Generate alert if needed
        alert = None
        if threat_level in ["CRITICAL", "HIGH"]:
            alert = {
                "id": f"{service}_{session_id}_{int(time.time())}",
                "severity": threat_level,
                "service": service,
                "event_type": event_type,
                "session_id": session_id,
                "timestamp": timestamp,
                "message": f"[{threat_level}] {service.upper()} - {event_type}: {command[:100]}",
                "details": event
            }
            self.alerts.append(alert)
        
        return {
            "threat_level": threat_level,
            "alert": alert,
            "metrics_update": dict(self.metrics),
            "active_sessions_count": self.metrics["total_sessions"]
        }
    
    def _is_suspicious_command(self, command: str) -> bool:
        """Check if command matches suspicious patterns"""
        suspicious_patterns = [
            "sudo", "rm -rf", "chmod", "chown", "curl", "wget",
            "nc", "ncat", "telnet", "ssh", "scp", "cat /etc/passwd",
            "union select", "or 1=1", "drop table", "exec", "system",
            "eval", "base64", "wget http", "../", "../../", "/etc/",
            "shadow", "backdoor", "shell", "payload", "exploit"
        ]
        
        command_lower = command.lower()
        return any(pattern in command_lower for pattern in suspicious_patterns)
    
    def get_metrics_summary(self) -> dict:
        """Get current metrics summary"""
        # Clean up inactive sessions
        current_time = time.time()
        inactive_threshold = 3600  # 1 hour
        
        active_sessions = {
            sid: timestamp 
            for sid, timestamp in self.metrics["active_sessions"].items()
            if current_time - timestamp < inactive_threshold
        }
        self.metrics["active_sessions"] = active_sessions
        self.metrics["total_sessions"] = len(active_sessions)
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": dict(self.metrics),
            "alert_count": len(self.alerts),
            "recent_alerts": self.alerts[-10:],  # Last 10 alerts
        }
    
    def push_to_prometheus(self, metrics: dict) -> bool:
        """Push metrics to Prometheus via remote-write"""
        if not PROMETHEUS_URL:
            print("⚠️ PROMETHEUS_URL not configured")
            return False
            
        try:
            # Format metrics in Prometheus remote-write format (OpenMetrics)
            lines = []
            for key, value in metrics["metrics"].items():
                # Replace - with _ for Prometheus compatibility
                metric_name = f"sigilhive_{key.replace('-', '_')}"
                if isinstance(value, (int, float)):
                    lines.append(f"{metric_name} {value}")
            
            # Create payload in OpenMetrics text format
            payload = "\n".join(lines)
            
            # Use remote-write endpoint with basic auth
            headers = {"Content-Type": "text/plain; charset=utf-8"}
            print(f"📍 Pushing to: {PROMETHEUS_URL}")
            sys.stdout.flush()
            response = requests.post(
                PROMETHEUS_URL,
                data=payload,
                auth=(PROMETHEUS_USERNAME, GRAFANA_DOCKER_API) if PROMETHEUS_USERNAME else None,
                headers=headers
            )
            response.raise_for_status()
            
            print(f"✅ Pushed {len(lines)} metrics to Prometheus")
            return True
        except Exception as e:
            print(f"⚠️ Failed to push metrics to Prometheus: {e}")
            return False
    
    def push_alerts_to_loki(self, alerts: list) -> bool:
        """Push alerts to Grafana Loki"""
        if not alerts or not LOKI_URL:
            return False
        
        try:
            streams = []
            for alert in alerts:
                stream = {
                    "stream": {
                        "job": "honeypot-alerts",
                        "severity": alert["severity"],
                        "service": alert["service"],
                        "event_type": alert["event_type"],
                    },
                    "values": [
                        [str(int(time.time() * 1_000_000_000)), alert["message"]]
                    ]
                }
                streams.append(stream)
            
            payload = {"streams": streams}
            
            response = requests.post(
                LOKI_URL,
                json=payload,
                auth=(LOKI_USERNAME, GRAFANA_DOCKER_API) if LOKI_USERNAME else None,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            print(f"✅ Pushed {len(alerts)} alerts to Loki")
            return True
        except Exception as e:
            print(f"⚠️ Failed to push alerts to Loki: {e}")
            return False
    
    def clear_alerts(self):
        """Clear old alerts (keep last 100)"""
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]


async def main():
    """Main metrics collection loop"""
    print("🚀 Starting SigilHive Metrics Collector...")
    print(f"📍 Loki URL: {LOKI_URL}")
    print(f"📍 Prometheus URL: {PROMETHEUS_URL}")
    print(f"📍 Kafka Broker: {KAFKA_BROKER}")
    sys.stdout.flush()
    
    collector = MetricsCollector()
    
    # Connect to Kafka
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            group_id="metrics-collector",
            max_poll_records=100,
        )
        print(f"✅ Connected to Kafka topic: {KAFKA_TOPIC}")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        sys.stdout.flush()
        return
    
    metrics_push_interval = 30  # Push metrics every 30 seconds
    alerts_push_interval = 10   # Push alerts every 10 seconds
    last_metrics_push = time.time()
    last_alerts_push = time.time()
    
    try:
        for message in consumer:
            try:
                event = message.value
                
                # Process event
                result = collector.process_event(event)
                
                # Log alert if generated
                if result["alert"]:
                    print(f"🚨 ALERT: {result['alert']['message']}")
                
                # Periodic metrics push
                current_time = time.time()
                
                if current_time - last_metrics_push >= metrics_push_interval:
                    summary = collector.get_metrics_summary()
                    # Push to Prometheus (disabled due to snappy compression requirement)
                    # collector.push_to_prometheus(summary)
                    print(f"📊 Metrics: SSH={summary['metrics']['ssh_attacks']}, "
                          f"HTTP={summary['metrics']['http_attacks']}, "
                          f"DB={summary['metrics']['database_attacks']}")
                    sys.stdout.flush()
                    last_metrics_push = current_time
                
                # Push recent alerts
                if current_time - last_alerts_push >= alerts_push_interval and collector.alerts:
                    collector.push_alerts_to_loki(collector.alerts[-10:])
                    last_alerts_push = current_time
                
                collector.clear_alerts()
                
            except Exception as e:
                print(f"⚠️ Error processing message: {e}")
    
    except KeyboardInterrupt:
        print("Shutting down metrics collector...")
    finally:
        consumer.close()


if __name__ == "__main__":
    asyncio.run(main())
