# kafka_manager.py
import json
import os
import time
import asyncio
from typing import Any
from collections import defaultdict
from confluent_kafka import Producer, Consumer, KafkaException


def log(message: str):
    """Helper to ensure immediate output"""
    print(message, flush=True)


class HoneypotKafkaManager:
    def __init__(self, bootstrap_servers=None, max_retries=5, retry_delay=2):
        if bootstrap_servers is None:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

        self.producer_config = {
            "bootstrap.servers": bootstrap_servers,
            "linger.ms": 10,  # Small batching delay
            "compression.type": "snappy",  # Enable compression
        }
        self.consumer_config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": "honeypot-tracker",
            "auto.offset.reset": "earliest",
        }

        self.topics = None
        self.interval_seconds = 300
        self.message_buffer = defaultdict(list)
        self.enabled = False
        self.producer = None
        self.consumer = None
        self.message_count = 0

        # Try to connect with retries
        for attempt in range(max_retries):
            try:
                self.producer = Producer(self.producer_config)
                self.consumer = Consumer(self.consumer_config)

                # Test the connection by getting metadata
                self.producer.list_topics(timeout=5)

                self.enabled = True
                log(f"✅ Connected to Kafka at {bootstrap_servers}")
                break
            except KafkaException as e:
                if attempt < max_retries - 1:
                    log(
                        f"⏳ Kafka connection attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    log(
                        f"⚠️ Kafka not available after {max_retries} attempts, running without Kafka: {e}"
                    )
            except Exception as e:
                log(f"⚠️ Kafka not available, running without Kafka: {e}")
                break

    def delivery_report(self, err: str, msg: Any):
        """Callback for message delivery reports"""
        if err:
            log(f"❌ [Kafka] Message delivery failed: {err}")
        else:
            # Only log every 10th message to avoid spam
            self.message_count += 1
            if self.message_count % 10 == 1:
                log(
                    f"✅ [Kafka] Delivered message #{self.message_count} to {msg.topic()}"
                )

    def send(self, topic: str, value: Any, service: str = "unknown", event_type: str = "log"):
        """Send message to Kafka topic with service and event_type."""
        if not self.enabled or self.producer is None:
            return  # Silently skip if Kafka not available

        if isinstance(value, dict):
            payload = value.copy()
        elif isinstance(value, str):
            payload = {"message": value}
        else:
            payload = {"message": str(value)}

        payload.update({
            "service": service,
            "event_type": event_type,
            "timestamp": time.time()
        })
        
        value_bytes = json.dumps(payload).encode("utf-8")

        try:
            # Produce message
            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )

            # Poll to trigger callbacks and clear queue
            # Using 0 timeout means non-blocking
            self.producer.poll(0)

            # Optionally flush every N messages for better reliability
            # Remove this if you want to rely on auto-flush
            if self.message_count % 100 == 0:
                self.producer.flush()

        except BufferError:
            # Queue is full, flush and retry
            log("⚠️ [Kafka] Producer queue full, flushing...")
            self.producer.flush()
            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )
        except Exception as e:
            log(f"⚠️ [Kafka] Failed to send to topic '{topic}': {e}")

    def subscribe(self, topics: list):
        """Subscribe to Kafka topics"""
        if not self.enabled or self.consumer is None:
            log("⚠️ [Kafka] Not available, skipping subscription")
            return

        log(f"📥 [Kafka] Subscribing to topics: {topics}")
        self.topics = topics
        self.consumer.subscribe(topics)

    async def consume(self):
        """Consume messages from subscribed topics"""
        if not self.enabled or self.consumer is None:
            log("⚠️ [Kafka] Not available, consumer not started")
            return

        log(f"🔄 [Kafka] Consumer started, polling every {self.interval_seconds}s")
        last_process_time = time.time()

        for t in self.topics:
            self.message_buffer[t] = []

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # No message available
                    pass
                elif msg.error():
                    log(f"❌ [Kafka Consumer] Error: {msg.error()}")
                else:
                    topic = msg.topic()
                    value = msg.value().decode("utf-8")
                    self.message_buffer[topic].append(value)

                    # Log first message received
                    if len(self.message_buffer[topic]) == 1:
                        log(f"📨 [Kafka] First message received on topic '{topic}'")

                current_time = time.time()
                if current_time - last_process_time >= self.interval_seconds:
                    for topic in self.topics:
                        if self.message_buffer[topic]:
                            log(
                                f"📦 [Kafka Batch] Processing {len(self.message_buffer[topic])} messages from '{topic}'"
                            )
                            self.message_buffer[topic] = []

                    last_process_time = current_time

                await asyncio.sleep(0.1)

        except Exception as e:
            log(f"❌ [Kafka Consumer] Error while consuming: {e}")
            import traceback

            traceback.print_exc()
        finally:
            if self.consumer:
                log("🛑 [Kafka] Closing consumer...")
                self.consumer.close()

    def close(self):
        """Clean shutdown of Kafka connections"""
        if self.producer:
            log("🛑 [Kafka] Flushing producer...")
            self.producer.flush(timeout=5)
        if self.consumer:
            log("🛑 [Kafka] Closing consumer...")
            self.consumer.close()
