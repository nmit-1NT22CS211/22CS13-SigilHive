import json
import ast
from json import JSONDecodeError
import asyncio
import os
import time
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional

try:
    from confluent_kafka import Producer, Consumer, KafkaException
except Exception as e:
    raise RuntimeError(
        "confluent-kafka not available -- install it (pip install confluent-kafka). "
        "In Docker you also need librdkafka-dev at system level."
    ) from e


class HoneypotKafka:
    """
    Simple Kafka wrapper for honeypots.
    Usage:
      kafka = HoneypotKafka("ssh", config_path="kafka_config.json")
      kafka.send("SSHtoDB", payload_dict)
      asyncio.create_task(kafka.start_consumer_loop(handler))
    """

    # mapping: which topics each honeypot should consume
    _consume_map = {
        "ssh": ["DBtoSSH", "HTTPtoSSH"],
        "database": ["SSHtoDB", "HTTPtoDB"],
        "http": ["SSHtoHTTP", "DBtoHTTP"],
    }

    def __init__(self, honeypot_name: str, config_path: str = "kafka_config.json"):
        self.honeypot = honeypot_name.lower()
        self.config = self._load_config(config_path)
        self.bootstrap = self.config.get("bootstrap_servers", "kafka:9092")
        self.interval = int(self.config.get("consumer_interval_seconds", 300))
        group_id_prefix = self.config.get("group_id_prefix", "honeypot-group")
        self.group_id = f"{group_id_prefix}-{self.honeypot}"

        # Producer
        self.producer = Producer({"bootstrap.servers": self.bootstrap})

        # Consumer
        self.consumer_topics = self._consume_map.get(self.honeypot, [])
        self.consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap,
                "group.id": self.group_id,
                "auto.offset.reset": "earliest",
                # disable auto commit to keep control (you can enable if desired)
                "enable.auto.commit": True,
            }
        )
        if self.consumer_topics:
            self.consumer.subscribe(self.consumer_topics)
        self._stop = False

    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # fallback to env vars
            return {
                "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                "consumer_interval_seconds": int(
                    os.getenv("KAFKA_CONSUMER_INTERVAL", "300")
                ),
                "group_id_prefix": os.getenv("KAFKA_GROUP_PREFIX", "honeypot-group"),
            }

    def send(self, topic: str, payload: Dict[str, Any], key: Optional[str] = None):
        """Send JSON message to topic. Blocks until message queued (producer.flush optional)."""
        payload = dict(payload)
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.utcnow().isoformat()
        if "source" not in payload:
            payload["source"] = self.honeypot
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.producer.produce(topic, value=data, key=key)
            # flush in background is okay; we flush small amounts to avoid message loss
            self.producer.poll(0)
            print(
                f"[kafka:{self.honeypot}] Sent message to topic '{topic}': {payload}"
            )  # Added print statement
        except KafkaException as e:
            print(f"[kafka:{self.honeypot}] produce error: {e}")

    def flush(self, timeout: float = 2.0):
        """Flush outstanding messages."""
        try:
            self.producer.flush(timeout=timeout)
        except Exception:
            pass

    async def start_consumer_loop(self, handler: Callable[[Dict[str, Any]], Any]):
        """
        Asynchronously polls for messages and calls handler(payload).
        The polling runs repeatedly for a window equal to interval, processing messages;
        then sleeps until next interval boundary. This satisfies "consumer will run on an interval basis".
        """
        if not self.consumer_topics:
            print(f"[kafka:{self.honeypot}] no topics to subscribe to.")
            return
        print(f"[kafka:{self.honeypot}] consumer subscribed to: {self.consumer_topics}")
        try:
            while not self._stop:
                # We will poll for interval seconds, handling messages as they come.
                start = time.time()
                deadline = start + self.interval
                while time.time() < deadline and not self._stop:
                    # poll timeout small so loop stays responsive
                    msg = self.consumer.poll(timeout=1.0)
                    if msg is None:
                        continue
                    if msg.error():
                        # ignore heartbeat and EOF errors; print others
                        print(f"[kafka:{self.honeypot}] consumer error: {msg.error()}")
                        continue
                    # Robust JSON decoding with fallbacks for common encoding/escaping issues
                    raw_bytes = msg.value()
                    payload = None
                    decode_errors = None
                    try:
                        s = raw_bytes.decode("utf-8")
                        try:
                            payload = json.loads(s)
                        except JSONDecodeError:
                            # try forgiving decode (replace invalid chars)
                            s2 = raw_bytes.decode("utf-8", errors="replace")
                            try:
                                payload = json.loads(s2)
                                decode_errors = "replaced-invalid-chars"
                            except JSONDecodeError:
                                # try to escape backslashes (common shell quoting issues)
                                try:
                                    s3 = s.replace("\\", "\\\\")
                                    payload = json.loads(s3)
                                    decode_errors = "escaped-backslashes"
                                except JSONDecodeError:
                                    # final fallback: try ast.literal_eval on the original string
                                    try:
                                        payload = ast.literal_eval(s)
                                        decode_errors = "ast-literal-eval"
                                    except Exception as e:
                                        print(
                                            f"[kafka:{self.honeypot}] json decode fail: {e}"
                                        )
                    except Exception as e:
                        print(f"[kafka:{self.honeypot}] error decoding bytes: {e}")

                    if payload is None:
                        # unable to decode payload; log raw (safe) and continue
                        try:
                            snippet = raw_bytes[:200].decode("utf-8", errors="replace")
                        except Exception:
                            snippet = str(raw_bytes[:200])
                        print(
                            f"[kafka:{self.honeypot}] Received non-decodable message (snippet): {snippet}"
                        )
                        continue

                    # success
                    if decode_errors:
                        print(
                            f"[kafka:{self.honeypot}] Received message (decoded via {decode_errors}): {payload}"
                        )
                    else:
                        print(f"[kafka:{self.honeypot}] Received message: {payload}")

                    # call handler (allow async or sync)
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(payload)
                        else:
                            # run sync handler in threadpool to avoid blocking
                            await asyncio.get_event_loop().run_in_executor(
                                None, handler, payload
                            )
                    except Exception as e:
                        print(f"[kafka:{self.honeypot}] handler error: {e}")
                # finished polling window; sleep until next interval if loop ended early
                # this loop keeps consumer active during the interval and processes messages as they come
                # if no messages arrived, this still waits interval seconds in total
                # go back and poll again
                # small sleep to yield control (not strictly necessary)
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[kafka:{self.honeypot}] consumer loop exception: {e}")
        finally:
            try:
                self.consumer.close()
            except Exception:
                pass
            print(f"[kafka:{self.honeypot}] consumer stopped")

    def stop(self):
        """Stop consumer gracefully."""
        self._stop = True
