# shophub_mysql_honeypot.py
import asyncio
import os
import struct
import uuid
import time
import hashlib
import json
from datetime import datetime, timezone
from .controller import ShopHubDBController
from kafka_manager import HoneypotKafka
import os

# Configuration
MYSQL_HOST = "0.0.0.0"
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "2222"))
REQUIRE_PASSWORD = os.getenv("REQUIRE_PASSWORD", "false").lower() == "true"

# Valid credentials
VALID_CREDENTIALS = {
    "shophub_app": "shophub123",
    "root": "rootpass",
    "admin": "admin123",
}

controller = ShopHubDBController()

# Kafka manager for Database honeypot
kafka = HoneypotKafka(
    "database", config_path=os.getenv("KAFKA_CONFIG_PATH", "kafka_config.json")
)


class MySQLProtocol(asyncio.Protocol):
    """MySQL protocol implementation for ShopHub honeypot"""

    def __init__(self):
        self.transport = None
        self.session_id = str(uuid.uuid4())[:8]
        self.query_count = 0
        self.start_time = time.time()
        self.authenticated = False
        self.username = None
        self.auth_salt = None
        self.auth_switch_sent = False
        self._buffer = b""
        self._packet_queue = asyncio.Queue()
        self._worker_task = None

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        print(f"[mysql][{self.session_id}] connection from {peername}")
        self.send_handshake()

    def send_handshake(self):
        """Send MySQL handshake packet"""
        protocol_version = 10
        server_version = b"8.0.33-ShopHub\x00"
        connection_id = struct.pack("<I", hash(self.session_id) & 0xFFFFFFFF)

        self.auth_salt = os.urandom(20)
        auth_data_part1 = self.auth_salt[:8]
        auth_data_part2 = self.auth_salt[8:] + b"\x00"

        filler = b"\x00"
        capability_flags_1 = struct.pack("<H", 0xF7FF)
        charset = struct.pack("B", 0x21)
        status_flags = struct.pack("<H", 0x0002)
        capability_flags_2 = struct.pack("<H", 0x8000)
        auth_data_len = struct.pack("B", 21)
        reserved = b"\x00" * 10
        auth_plugin = b"mysql_native_password\x00"

        payload = (
            struct.pack("B", protocol_version)
            + server_version
            + connection_id
            + auth_data_part1
            + filler
            + capability_flags_1
            + charset
            + status_flags
            + capability_flags_2
            + auth_data_len
            + reserved
            + auth_data_part2
            + auth_plugin
        )

        self.send_packet(payload, 0)

    def mysql_native_password(self, password: str, salt: bytes) -> bytes:
        """Calculate MySQL native password hash"""
        if not password:
            return b""
        stage1 = hashlib.sha1(password.encode()).digest()
        stage2 = hashlib.sha1(stage1).digest()
        stage3 = hashlib.sha1(salt + stage2).digest()
        result = bytes(a ^ b for a, b in zip(stage1, stage3))
        return result

    def verify_password(self, username: str, auth_response: bytes) -> bool:
        """Verify password against valid credentials"""
        if username not in VALID_CREDENTIALS:
            return False
        expected_password = VALID_CREDENTIALS[username]
        expected_hash = self.mysql_native_password(expected_password, self.auth_salt)
        return auth_response == expected_hash

    def send_packet(self, payload, sequence_id):
        """Send MySQL packet"""
        length = len(payload)
        header = struct.pack("<I", length)[:3] + struct.pack("B", sequence_id)
        self.transport.write(header + payload)

    def send_ok_packet(self, sequence_id=1, affected_rows=0):
        """Send OK packet"""
        payload = (
            b"\x00"
            + self.encode_length(affected_rows)
            + self.encode_length(0)
            + struct.pack("<H", 0x0002)
            + struct.pack("<H", 0x0000)
        )
        self.send_packet(payload, sequence_id)

    def send_error_packet(self, error_code, sql_state, message, sequence_id=1):
        """Send ERR packet"""
        payload = (
            b"\xff"
            + struct.pack("<H", error_code)
            + b"#"
            + sql_state.encode()
            + message.encode()
        )
        self.send_packet(payload, sequence_id)

    def send_text_result(self, result_data, sequence_id=1):
        """Send result set - FIXED VERSION"""
        try:
            print(f"[mysql][{self.session_id}] === SEND_TEXT_RESULT ===")

            # Normalize result_data to dict with columns and rows
            if isinstance(result_data, str):
                result_data = result_data.strip()
                if result_data.startswith("{"):
                    try:
                        result_data = json.loads(result_data)
                    except:
                        result_data = {"columns": ["result"], "rows": [[result_data]]}
                else:
                    result_data = {"columns": ["result"], "rows": [[result_data]]}

            if not isinstance(result_data, dict):
                result_data = {"columns": ["result"], "rows": [[str(result_data)]]}

            # Handle 'text' key
            if "text" in result_data and "columns" not in result_data:
                result_data = {"columns": ["result"], "rows": [[result_data["text"]]]}

            # Ensure we have columns and rows
            if "columns" not in result_data or "rows" not in result_data:
                result_data = {"columns": ["result"], "rows": [[str(result_data)]]}

            columns = result_data["columns"]
            rows = result_data["rows"]
            num_columns = len(columns)

            print(
                f"[mysql][{self.session_id}] Sending {num_columns} columns, {len(rows)} rows"
            )

            current_seq = sequence_id

            # Column count
            self.send_packet(self.encode_length(num_columns), current_seq)
            current_seq += 1

            # Column definitions
            for col_name in columns:
                col_def = (
                    self.encode_length_string(b"def")
                    + self.encode_length_string(b"shophub")
                    + self.encode_length_string(b"shophub")
                    + self.encode_length_string(b"shophub")
                    + self.encode_length_string(str(col_name).encode())
                    + self.encode_length_string(str(col_name).encode())
                    + struct.pack("B", 0x0C)
                    + struct.pack("<H", 0x21)
                    + struct.pack("<I", 255)
                    + struct.pack("B", 0xFD)
                    + struct.pack("<H", 0)
                    + struct.pack("B", 0)
                    + struct.pack("<H", 0)
                )
                self.send_packet(col_def, current_seq)
                current_seq += 1

            # EOF after columns
            eof_packet = b"\xfe" + struct.pack("<H", 0) + struct.pack("<H", 0x0002)
            self.send_packet(eof_packet, current_seq)
            current_seq += 1

            # Rows
            for row in rows:
                row_payload = b""
                for value in row:
                    if value is None:
                        row_payload += b"\xfb"  # NULL indicator
                    else:
                        value_str = str(value)
                        row_payload += self.encode_length_string(value_str.encode())
                self.send_packet(row_payload, current_seq)
                current_seq += 1

            # EOF after rows
            self.send_packet(eof_packet, current_seq)
            print(f"[mysql][{self.session_id}] ✓ Result set sent successfully")

        except Exception as e:
            print(f"[mysql][{self.session_id}] Error in send_text_result: {e}")
            import traceback

            traceback.print_exc()
            self.send_error_packet(1064, "42000", "Internal server error", sequence_id)

    def encode_length(self, n):
        """Encode length as MySQL length-encoded integer"""
        if n < 251:
            return struct.pack("B", n)
        elif n < (1 << 16):
            return b"\xfc" + struct.pack("<H", n)
        elif n < (1 << 24):
            return b"\xfd" + struct.pack("<I", n)[:3]
        else:
            return b"\xfe" + struct.pack("<Q", n)

    def encode_length_string(self, s):
        """Encode string with length prefix"""
        return self.encode_length(len(s)) + s

    def data_received(self, data):
        self._buffer += data

        while len(self._buffer) >= 4:
            length = struct.unpack("<I", self._buffer[:3] + b"\x00")[0]
            sequence_id = self._buffer[3]

            if len(self._buffer) < 4 + length:
                break

            payload = self._buffer[4 : 4 + length]
            self._buffer = self._buffer[4 + length :]

            try:
                self._packet_queue.put_nowait((payload, sequence_id))
                if self._worker_task is None or self._worker_task.done():
                    self._worker_task = asyncio.create_task(self._packet_worker())
            except Exception as e:
                print(f"[mysql][{self.session_id}] queue error: {e}")

    async def _packet_worker(self):
        """Process packets sequentially"""
        while True:
            try:
                payload, seq = await self._packet_queue.get()
            except Exception:
                break

            try:
                await self.handle_packet(payload, seq)
            except Exception as e:
                print(f"[mysql][{self.session_id}] packet error: {e}")
                import traceback

                traceback.print_exc()
            finally:
                try:
                    self._packet_queue.task_done()
                except Exception:
                    pass

            if self.transport is None or (
                hasattr(self.transport, "is_closing") and self.transport.is_closing()
            ):
                break

    async def handle_packet(self, payload, sequence_id):
        """Handle MySQL packet"""
        if not payload:
            return

        if not self.authenticated:
            # Handle auth switch response
            if self.auth_switch_sent:
                if len(payload) == 20:
                    auth_response = payload
                    if self.verify_password(self.username, auth_response):
                        self.authenticated = True
                        self.auth_switch_sent = False
                        controller.db_state.use_database("shophub")
                        print(f"[mysql][{self.session_id}] ✓ AUTH SUCCESS")
                        self.send_ok_packet(sequence_id + 1)
                    else:
                        print(f"[mysql][{self.session_id}] ✗ AUTH FAILED")
                        self.send_error_packet(
                            1045,
                            "28000",
                            f"Access denied for user '{self.username}'",
                            sequence_id + 1,
                        )
                        await asyncio.sleep(0.5)
                        self.transport.close()
                return

            # Parse HandshakeResponse
            try:
                pos = 32  # Skip capability flags, max packet, charset, reserved
                username_end = payload.find(b"\x00", pos)
                if username_end == -1:
                    raise Exception("Username not null-terminated")

                self.username = payload[pos:username_end].decode(
                    "utf-8", errors="ignore"
                )
                pos = username_end + 1

                if pos >= len(payload):
                    if not REQUIRE_PASSWORD and self.username in VALID_CREDENTIALS:
                        self.authenticated = True
                        controller.db_state.use_database("shophub")
                        print(
                            f"[mysql][{self.session_id}] ✓ AUTH SUCCESS (no password)"
                        )
                        self.send_ok_packet(sequence_id + 1)
                        return
                    else:
                        self.send_error_packet(
                            1045, "28000", "Access denied", sequence_id + 1
                        )
                        await asyncio.sleep(0.5)
                        self.transport.close()
                        return

                auth_len_byte = payload[pos]
                capability_flags = struct.unpack("<I", payload[:4])[0]

                if capability_flags & 0x00200000:
                    if auth_len_byte < 251:
                        auth_response_len = auth_len_byte
                        pos += 1
                    else:
                        auth_response_len = 0
                        pos += 1
                else:
                    auth_response_len = auth_len_byte
                    pos += 1

                if auth_response_len == 0:
                    # Check for plugin auth
                    remaining_data = payload[pos:]
                    if len(remaining_data) > 0:
                        # Send AuthSwitchRequest
                        self.auth_switch_sent = True
                        auth_switch = (
                            b"\xfe"
                            + b"mysql_native_password\x00"
                            + self.auth_salt
                            + b"\x00"
                        )
                        self.send_packet(auth_switch, sequence_id + 1)
                        return

                    if not REQUIRE_PASSWORD and self.username in VALID_CREDENTIALS:
                        self.authenticated = True
                        controller.db_state.use_database("shophub")
                        print(
                            f"[mysql][{self.session_id}] ✓ AUTH SUCCESS (no password)"
                        )
                        self.send_ok_packet(sequence_id + 1)
                        return

                    self.send_error_packet(
                        1045, "28000", "Access denied", sequence_id + 1
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                    return

                if pos + auth_response_len > len(payload):
                    raise Exception("Auth response exceeds packet")

                auth_response = payload[pos : pos + auth_response_len]

                if self.verify_password(self.username, auth_response):
                    self.authenticated = True
                    controller.db_state.use_database("shophub")
                    print(f"[mysql][{self.session_id}] ✓ AUTH SUCCESS")
                    self.send_ok_packet(sequence_id + 1)
                else:
                    print(f"[mysql][{self.session_id}] ✗ AUTH FAILED")
                    self.send_error_packet(
                        1045,
                        "28000",
                        f"Access denied for user '{self.username}'",
                        sequence_id + 1,
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()

            except Exception as e:
                print(f"[mysql][{self.session_id}] Auth error: {e}")
                self.send_error_packet(1045, "28000", "Access denied", sequence_id + 1)
                await asyncio.sleep(0.5)
                self.transport.close()
            return

        # After authentication - handle commands
        packet_type = payload[0]

        # COM_QUERY (0x03)
        if packet_type == 0x03:
            query = payload[1:].decode("utf-8", errors="ignore").strip()
            print(f"[mysql][{self.session_id}] query: {query}")
            self.query_count += 1
            await self.handle_query(query, sequence_id)

        # COM_INIT_DB (0x02)
        elif packet_type == 0x02:
            try:
                db_name = (
                    payload[1:].decode("utf-8", errors="ignore").strip("\x00").strip()
                )
                print(f"[mysql][{self.session_id}] change database to: {db_name}")
                if db_name:
                    success = controller.db_state.use_database(db_name)
                    if success:
                        self.send_ok_packet(sequence_id + 1)
                    else:
                        self.send_error_packet(
                            1049,
                            "42000",
                            f"Unknown database '{db_name}'",
                            sequence_id + 1,
                        )
                else:
                    self.send_error_packet(
                        1049, "42000", "Unknown database", sequence_id + 1
                    )
            except Exception as e:
                print(f"[mysql][{self.session_id}] COM_INIT_DB error: {e}")
                self.send_error_packet(
                    1049, "42000", "Unknown database", sequence_id + 1
                )
            return

        # COM_QUIT (0x01)
        elif packet_type == 0x01:
            print(f"[mysql][{self.session_id}] client quit")
            self.transport.close()

    async def handle_query(self, query, sequence_id):
        """Handle SQL query"""
        try:
            event = {
                "session_id": self.session_id,
                "type": "query",
                "query": query,
                "ts": datetime.now(timezone.utc).isoformat(),
                "query_count": self.query_count,
                "elapsed": time.time() - self.start_time,
                "username": self.username,
            }
            # Publish minimal DB event to Kafka for other honeypots
            try:
                kafka.send(
                    "DBtoSSH",
                    {
                        "target": "ssh", # Added target
                        "event_type": "db_query",
                        "session_id": self.session_id,
                        "username": self.username,
                        "query": query,
                        "query_count": self.query_count, # Added query_count
                        "elapsed": time.time() - self.start_time # Added elapsed
                    },
                )
                kafka.send(
                    "DBtoHTTP",
                    {
                        "target": "http", # Added target
                        "event_type": "db_query",
                        "session_id": self.session_id,
                        "query": query,
                    },
                )
            except Exception as e:
                print(f"[mysql][{self.session_id}] Kafka send error: {e}")
            try:
                action = await controller.get_action_for_query(self.session_id, event)
            except Exception as e:
                print(f"[mysql][{self.session_id}] controller error: {e}")
                import traceback

                traceback.print_exc()
                self.send_error_packet(1064, "42000", str(e), sequence_id + 1)
                return

            if action.get("disconnect"):
                self.transport.close()
                return

            delay = action.get("delay", 0.0)
            if delay > 0:
                await asyncio.sleep(delay)

            response = action.get("response", {})
            next_seq = sequence_id + 1
            q_upper = query.upper().strip()

            # Handle string responses
            if isinstance(response, str):
                response_text = response
                if response_text.startswith("ERROR"):
                    self.send_error_packet(1064, "42000", response_text, next_seq)
                elif "Database changed" in response_text:
                    self.send_ok_packet(next_seq)
                elif "Query OK" in response_text:
                    affected = 1 if "1 row" in response_text else 0
                    self.send_ok_packet(next_seq, affected_rows=affected)
                else:
                    # Convert to result set
                    self.send_text_result(
                        {"columns": ["result"], "rows": [[response_text]]}, next_seq
                    )
                return

            # Handle dict responses
            if isinstance(response, dict):
                # Check if it has 'text' key
                if "text" in response and "columns" not in response:
                    response_text = response["text"]
                    if response_text.startswith("ERROR"):
                        self.send_error_packet(1064, "42000", response_text, next_seq)
                    elif "Database changed" in response_text:
                        self.send_ok_packet(next_seq)
                    elif "Query OK" in response_text:
                        affected = 1 if "1 row" in response_text else 0
                        self.send_ok_packet(next_seq, affected_rows=affected)
                    else:
                        self.send_text_result(
                            {"columns": ["result"], "rows": [[response_text]]}, next_seq
                        )
                    return

                # It's a result set with columns and rows
                if "columns" in response and "rows" in response:
                    self.send_text_result(response, next_seq)
                    return

            # Default: send as OK
            self.send_ok_packet(next_seq)

        except Exception as e:
            print(f"[mysql][{self.session_id}] query error: {e}")
            import traceback

            traceback.print_exc()
            self.send_error_packet(
                1064, "42000", "Internal server error", sequence_id + 1
            )

    def connection_lost(self, exc):
        duration = time.time() - self.start_time
        print(
            f"[mysql][{self.session_id}] disconnected after {duration:.1f}s ({self.query_count} queries)"
        )
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()


async def main():
    loop = asyncio.get_running_loop()

    async def db_kafka_handler(msg):
        try:
            print(f"[db][kafka] received: {msg}")
            sid = msg.get("session_id")
            if sid and hasattr(controller, "sessions"):
                sess = controller.sessions.setdefault(sid, {})
                sess.setdefault("cross_messages", []).append(msg)

            # For example, if http told db to create a decoy table:
            if msg.get("event_type") == "control" and msg.get("action") == "create_table":
                table = msg.get("table")
                if table:
                    try:
                        if hasattr(controller.db_state, "create_table_like_decoy"):
                            controller.db_state.create_table_like_decoy(table)
                            print(f"[db][kafka] Created decoy table: {table}")
                        else:
                            print(f"[db][kafka] controller.db_state does not have create_table_like_decoy method. Logging table creation request: {table}")
                    except Exception as e:
                        print(f"[db][kafka] Error creating decoy table: {e}")
        except Exception as e:
            print(f"[db][kafka] handler error: {e}")

    # start kafka consumer loop
    try:
        loop.create_task(kafka.start_consumer_loop(db_kafka_handler))
    except Exception:
        pass

    print("[honeypot] Starting ShopHub MySQL Honeypot")
    print("[honeypot] Database: ShopHub E-commerce")
    print(f"[honeypot] Listening on {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"[honeypot] Password Required: {REQUIRE_PASSWORD}")
    print("[honeypot] Valid credentials:")
    for username in VALID_CREDENTIALS.keys():
        print(f"[honeypot]   - {username}:{VALID_CREDENTIALS[username]}")
    if not REQUIRE_PASSWORD:
        print("[honeypot] ⚠️  WARNING: Running in NO-PASSWORD mode (for testing)")
        print("[honeypot] ⚠️  Set REQUIRE_PASSWORD=true to enable password checks")

    server = await loop.create_server(MySQLProtocol, MYSQL_HOST, MYSQL_PORT)

    print("[honeypot] MySQL honeypot ready")
    print(
        f"[honeypot] Connect with: mysql -h localhost -P {MYSQL_PORT} -u shophub_app -p"
    )

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        server.close()
        await server.wait_closed()
        print("[honeypot] server shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[honeypot] stopped by user")
    except Exception as e:
        print(f"[honeypot] error: {e}")
