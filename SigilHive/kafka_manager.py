# kafka_manager.py
import json
import os
import time
from typing import Any
from confluent_kafka import Producer, Consumer, KafkaException


class HoneypotKafkaManager:
    def __init__(self, bootstrap_servers=None, max_retries=5, retry_delay=2):
        if bootstrap_servers is None:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

        self.producer_config = {"bootstrap.servers": bootstrap_servers}
        self.consumer_config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": "honeypot-tracker",
            "auto.offset.reset": "earliest",
        }

        self.enabled = False
        self.producer = None
        self.consumer = None

        # Try to connect with retries
        for attempt in range(max_retries):
            try:
                self.producer = Producer(self.producer_config)
                self.consumer = Consumer(self.consumer_config)

                # Test the connection by getting metadata
                self.producer.list_topics(timeout=5)

                self.enabled = True
                print(f"✅ Connected to Kafka at {bootstrap_servers}")
                break
            except KafkaException as e:
                if attempt < max_retries - 1:
                    print(
                        f"⏳ Kafka connection attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    print(
                        f"⚠️ Kafka not available after {max_retries} attempts, running without Kafka: {e}"
                    )
            except Exception as e:
                print(f"⚠️ Kafka not available, running without Kafka: {e}")
                break

    def delivery_report(self, err: str, msg: Any):
        if err:
            print(f"❌ Message delivery failed: {err}")
        else:
            print(
                f"✅ Delivered message: {msg.value().decode('utf-8')} to {msg.topic()} topic"
            )

    def send(self, topic: str, value: dict):
        if not self.enabled or self.producer is None:
            return  # Silently skip if Kafka not available

        try:
            value = json.dumps(value).encode("utf-8")
            self.producer.produce(
                topic=topic, value=value, callback=self.delivery_report
            )
            self.producer.poll(0)
        except Exception as e:
            print(f"⚠️ Failed to send to Kafka: {e}")
