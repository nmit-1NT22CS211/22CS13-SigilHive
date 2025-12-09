# kafka_manager.py - FIXED VERSION
import json
import os
import sys
import time
import asyncio
from typing import Any
from collections import defaultdict
from confluent_kafka import Producer, Consumer, KafkaException


def log(message: str):
    """Helper to ensure immediate output - forcefully prints to terminal"""
    print(message, file=sys.stderr, flush=True)
    sys.stderr.flush()
    # Also print to stdout for redundancy
    print(message, file=sys.stdout, flush=True)
    sys.stdout.flush()


class HoneypotKafkaManager:
    def __init__(self, bootstrap_servers=None, max_retries=5, retry_delay=2):
        log("🚀 [Kafka Manager] Initializing HoneypotKafkaManager...")

        if bootstrap_servers is None:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

        log(f"🔧 [Kafka Manager] Bootstrap servers: {bootstrap_servers}")

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

        log(
            f"🔄 [Kafka Manager] Attempting to connect to Kafka (max {max_retries} retries)..."
        )

        # Try to connect with retries
        for attempt in range(max_retries):
            try:
                log(
                    f"🔌 [Kafka Manager] Connection attempt {attempt + 1}/{max_retries}..."
                )

                self.producer = Producer(self.producer_config)
                self.consumer = Consumer(self.consumer_config)

                # Test the connection by getting metadata
                log("🧪 [Kafka Manager] Testing connection...")
                self.producer.list_topics(timeout=5)

                self.enabled = True
                log(
                    f"✅ [Kafka Manager] Successfully connected to Kafka at {bootstrap_servers}"
                )
                break
            except KafkaException as e:
                if attempt < max_retries - 1:
                    log(
                        f"⏳ [Kafka Manager] Attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s..."
                    )
                    log(f"   Error details: {str(e)}")
                    time.sleep(retry_delay)
                else:
                    log(
                        f"⚠️ [Kafka Manager] Failed to connect after {max_retries} attempts"
                    )
                    log(f"   Final error: {str(e)}")
                    log("⚠️ [Kafka Manager] Running WITHOUT Kafka support")
            except Exception as e:
                log(f"❌ [Kafka Manager] Unexpected error during connection: {str(e)}")
                log("⚠️ [Kafka Manager] Running WITHOUT Kafka support")
                break

    def delivery_report(self, err: str, msg: Any):
        """Callback for message delivery reports"""
        if err:
            log(f"❌ [Kafka Producer] Message delivery failed: {err}")
        else:
            # Log every message to ensure visibility
            self.message_count += 1
            log(
                f"✅ [Kafka Producer] Message #{self.message_count} delivered to topic '{msg.topic()}'"
            )

    def send(self, topic: str, value: dict, **kwargs):
        """Send message to Kafka topic

        Args:
            topic: Kafka topic name
            value: Message payload (dict or string)
            **kwargs: Additional parameters (ignored for backward compatibility)
        """
        # Ignore extra parameters like 'service' and 'event_type' for backward compatibility
        if kwargs:
            log(f"ℹ️ [Kafka Send] Ignoring extra parameters: {list(kwargs.keys())}")

        log(f"📤 [Kafka Send] Attempting to send message to topic '{topic}'")

        if not self.enabled or self.producer is None:
            log(f"⚠️ [Kafka Send] Kafka not enabled - message NOT sent to '{topic}'")
            return  # Silently skip if Kafka not available

        try:
            # Convert dict to JSON string if needed
            if isinstance(value, dict):
                value_bytes = json.dumps(value).encode("utf-8")
            elif isinstance(value, str):
                value_bytes = value.encode("utf-8")
            else:
                value_bytes = str(value).encode("utf-8")

            log(f"📊 [Kafka Send] Payload size: {len(value_bytes)} bytes")

            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )
            self.producer.poll(0)

            if self.message_count % 100 == 0:
                log(
                    f"💾 [Kafka Producer] Flushing after {self.message_count} messages..."
                )
                self.producer.flush()

        except BufferError:
            # Queue is full, flush and retry
            log("⚠️ [Kafka Producer] Buffer full! Flushing and retrying...")
            self.producer.flush()
            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )
            log("✅ [Kafka Producer] Retry successful after flush")
        except Exception as e:
            log(f"❌ [Kafka Send] Failed to send to topic '{topic}': {str(e)}")
            import traceback

            log(f"   Stack trace: {traceback.format_exc()}")

    def send_dashboard(
        self, topic: str, value: Any, service: str = "unknown", event_type: str = "log"
    ):
        """Send message to Kafka topic with service and event_type."""
        log(
            f"📤 [Kafka Dashboard] Sending to topic '{topic}' (service: {service}, type: {event_type})"
        )

        if not self.enabled or self.producer is None:
            log(
                f"⚠️ [Kafka Dashboard] Kafka not enabled - message NOT sent to '{topic}'"
            )
            return  # Silently skip if Kafka not available

        if isinstance(value, dict):
            payload = value.copy()
        elif isinstance(value, str):
            payload = {"message": value}
        else:
            payload = {"message": str(value)}

        payload.update(
            {"service": service, "event_type": event_type, "timestamp": time.time()}
        )

        value_bytes = json.dumps(payload).encode("utf-8")
        log(f"📊 [Kafka Dashboard] Payload size: {len(value_bytes)} bytes")

        try:
            # Produce message
            log(f"📄 [Kafka Dashboard] Producing message to '{topic}'...")
            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )

            # Poll to trigger callbacks and clear queue
            # Using 0 timeout means non-blocking
            self.producer.poll(0)

            # Optionally flush every N messages for better reliability
            # Remove this if you want to rely on auto-flush
            if self.message_count % 100 == 0:
                log(
                    f"💾 [Kafka Producer] Flushing after {self.message_count} messages..."
                )
                self.producer.flush()

        except BufferError:
            # Queue is full, flush and retry
            log("⚠️ [Kafka Producer] Buffer full! Flushing and retrying...")
            self.producer.flush()
            self.producer.produce(
                topic=topic, value=value_bytes, callback=self.delivery_report
            )
            log("✅ [Kafka Producer] Retry successful after flush")
        except Exception as e:
            log(f"❌ [Kafka Dashboard] Failed to send to topic '{topic}': {str(e)}")
            import traceback

            log(f"   Stack trace: {traceback.format_exc()}")

    def subscribe(self, topics: list):
        """Subscribe to Kafka topics"""
        log(
            f"📋 [Kafka Subscribe] Attempting to subscribe to {len(topics)} topics: {topics}"
        )

        if not self.enabled or self.consumer is None:
            log("⚠️ [Kafka Subscribe] Kafka not available - subscription skipped")
            return

        log(f"📥 [Kafka Subscribe] Successfully subscribed to topics: {topics}")
        self.topics = topics
        self.consumer.subscribe(topics)

    async def consume(self):
        """Consume messages from subscribed topics"""
        log("🎬 [Kafka Consumer] Starting consumer...")

        if not self.enabled or self.consumer is None:
            log("⚠️ [Kafka Consumer] Kafka not available - consumer NOT started")
            return

        log(
            f"🔄 [Kafka Consumer] Consumer active - polling every {self.interval_seconds}s"
        )
        log(f"🔌 [Kafka Consumer] Subscribed topics: {self.topics}")
        last_process_time = time.time()

        for t in self.topics:
            self.message_buffer[t] = []
            log(f"🗂️ [Kafka Consumer] Initialized buffer for topic '{t}'")

        try:
            iteration = 0
            while True:
                iteration += 1

                # Log every 100 iterations to show it's working
                if iteration % 100 == 0:
                    log(
                        f"💓 [Kafka Consumer] Heartbeat - iteration {iteration}, still consuming..."
                    )

                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # No message available - this is normal
                    pass
                elif msg.error():
                    log(f"❌ [Kafka Consumer] Error received: {msg.error()}")
                else:
                    topic = msg.topic()
                    value = msg.value().decode("utf-8")
                    self.message_buffer[topic].append(value)

                    # Log EVERY message received
                    log(
                        f"📨 [Kafka Consumer] Message received on topic '{topic}' (buffer size: {len(self.message_buffer[topic])})"
                    )
                    log(f"   Content preview: {value[:100]}...")

                current_time = time.time()
                if current_time - last_process_time >= self.interval_seconds:
                    log(
                        f"⏰ [Kafka Consumer] Batch processing interval reached ({self.interval_seconds}s)"
                    )

                    for topic in self.topics:
                        if self.message_buffer[topic]:
                            log(
                                f"📦 [Kafka Batch] Processing {len(self.message_buffer[topic])} messages from '{topic}'"
                            )
                            self.message_buffer[topic] = []
                            log(f"🧹 [Kafka Batch] Buffer cleared for topic '{topic}'")
                        else:
                            log(
                                f"🔭 [Kafka Batch] No messages in buffer for topic '{topic}'"
                            )

                    last_process_time = current_time

                await asyncio.sleep(0.1)

        except Exception as e:
            log(f"❌ [Kafka Consumer] Critical error while consuming: {str(e)}")
            import traceback

            log("Full stack trace:")
            log(traceback.format_exc())
        finally:
            if self.consumer:
                log("🛑 [Kafka Consumer] Shutting down consumer...")
                self.consumer.close()
                log("✅ [Kafka Consumer] Consumer closed successfully")

    def close(self):
        """Clean shutdown of Kafka connections"""
        log("🛑 [Kafka Manager] Initiating shutdown...")

        if self.producer:
            log("💾 [Kafka Producer] Flushing remaining messages...")
            self.producer.flush(timeout=5)
            log("✅ [Kafka Producer] Flush complete")

        if self.consumer:
            log("🛑 [Kafka Consumer] Closing consumer...")
            self.consumer.close()
            log("✅ [Kafka Consumer] Consumer closed")

        log("✅ [Kafka Manager] Shutdown complete")
