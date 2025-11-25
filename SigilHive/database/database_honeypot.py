# shophub_mysql_honeypot.py
import asyncio
import os
import struct
import uuid
import time
import hashlib
import json
from datetime import datetime, timezone
from controller import ShopHubDBController

# Configuration
MYSQL_HOST = "0.0.0.0"
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "2224"))

# Set to True to require passwords, False to accept without password (for testing)
REQUIRE_PASSWORD = os.getenv("REQUIRE_PASSWORD", "false").lower() == "true"

# Valid credentials for the honeypot
VALID_CREDENTIALS = {
    "shophub_app": "shophub123",
    "root": "rootpass",
    "admin": "admin123",
}

# ShopHub MySQL controller
controller = ShopHubDBController()


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

        # Generate auth salt (20 bytes total, split into two parts)
        self.auth_salt = os.urandom(20)
        auth_data_part1 = self.auth_salt[:8]
        auth_data_part2 = self.auth_salt[8:] + b"\x00"

        filler = b"\x00"
        # Capability flags - enable more authentication options
        # CLIENT_LONG_PASSWORD | CLIENT_PROTOCOL_41 | CLIENT_SECURE_CONNECTION | CLIENT_PLUGIN_AUTH
        capability_flags_1 = struct.pack("<H", 0xF7FF)
        charset = struct.pack("B", 0x21)  # utf8_general_ci
        status_flags = struct.pack("<H", 0x0002)
        capability_flags_2 = struct.pack("<H", 0x8000)  # CLIENT_PLUGIN_AUTH
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

        # SHA1(password)
        stage1 = hashlib.sha1(password.encode()).digest()
        # SHA1(SHA1(password))
        stage2 = hashlib.sha1(stage1).digest()
        # SHA1(salt + SHA1(SHA1(password)))
        stage3 = hashlib.sha1(salt + stage2).digest()
        # XOR SHA1(password) with stage3
        result = bytes(a ^ b for a, b in zip(stage1, stage3))
        return result

    def verify_password(self, username: str, auth_response: bytes) -> bool:
        """Verify password against valid credentials"""
        if username not in VALID_CREDENTIALS:
            print(f"[mysql][{self.session_id}] unknown user: {username}")
            return False

        expected_password = VALID_CREDENTIALS[username]
        expected_hash = self.mysql_native_password(expected_password, self.auth_salt)

        is_valid = auth_response == expected_hash

        if not is_valid:
            print(f"[mysql][{self.session_id}] password mismatch")
            print(f"[mysql][{self.session_id}]   expected: {expected_hash.hex()}")
            print(f"[mysql][{self.session_id}]   received: {auth_response.hex()}")
        else:
            print(f"[mysql][{self.session_id}] ✓ password verified")

        return is_valid

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
        """Send result set"""
        try:
            print(f"[mysql][{self.session_id}] === SEND_TEXT_RESULT DEBUG ===")
            print(f"[mysql][{self.session_id}] Input type: {type(result_data)}")

            # Normalize result data
            if isinstance(result_data, str):
                print(
                    f"[mysql][{self.session_id}] Input is STRING, first 200 chars: {result_data[:200]}"
                )
                try:
                    # Try to parse as JSON first
                    if result_data.strip().startswith("{"):
                        parsed = json.loads(result_data)
                        print(
                            f"[mysql][{self.session_id}] Parsed STRING to JSON: {list(parsed.keys())}"
                        )
                        if isinstance(parsed, dict):
                            if "columns" in parsed and "rows" in parsed:
                                # It's already in the right format
                                print(
                                    f"[mysql][{self.session_id}] Found columns and rows!"
                                )
                                result_data = parsed
                            elif "text" in parsed:
                                result_data = {
                                    "columns": ["result"],
                                    "rows": [[parsed["text"]]],
                                }
                            else:
                                result_data = {
                                    "columns": ["result"],
                                    "rows": [[result_data]],
                                }
                        else:
                            result_data = {
                                "columns": ["result"],
                                "rows": [[result_data]],
                            }
                    else:
                        result_data = {"columns": ["result"], "rows": [[result_data]]}
                except json.JSONDecodeError as e:
                    print(f"[mysql][{self.session_id}] JSON decode error: {e}")
                    result_data = {"columns": ["result"], "rows": [[result_data]]}
            elif isinstance(result_data, dict):
                print(
                    f"[mysql][{self.session_id}] Input is DICT with keys: {list(result_data.keys())}"
                )
                if "text" in result_data and "columns" not in result_data:
                    result_data = {
                        "columns": ["result"],
                        "rows": [[result_data["text"]]],
                    }
                elif not ("columns" in result_data and "rows" in result_data):
                    result_data = {"columns": ["result"], "rows": [[str(result_data)]]}
            else:
                result_data = {"columns": ["result"], "rows": [[str(result_data)]]}

            columns = result_data.get("columns", ["result"])
            rows = result_data.get("rows", [])
            num_columns = len(columns)

            print(
                f"[mysql][{self.session_id}] Final: {num_columns} columns, {len(rows)} rows"
            )
            print(f"[mysql][{self.session_id}] Columns: {columns}")

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
                        value_str = ""
                    else:
                        value_str = str(value)
                    row_payload += self.encode_length_string(value_str.encode())
                self.send_packet(row_payload, current_seq)
                current_seq += 1

            # EOF after rows
            self.send_packet(eof_packet, current_seq)

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
            # Check if this is a response to AuthSwitchRequest
            if self.auth_switch_sent:
                print(f"[mysql][{self.session_id}] === AUTH SWITCH RESPONSE ===")
                print(f"[mysql][{self.session_id}] Length: {len(payload)} bytes")
                print(f"[mysql][{self.session_id}] Hex: {payload.hex()}")

                # The response should be just the auth data (20 bytes for mysql_native_password)
                if len(payload) == 20:
                    auth_response = payload
                    print(
                        f"[mysql][{self.session_id}] Auth response: {auth_response.hex()}"
                    )

                    if self.verify_password(self.username, auth_response):
                        self.authenticated = True
                        self.auth_switch_sent = False
                        # Set default database to shophub
                        controller.db_state.use_database("shophub")
                        print(
                            f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL ✓✓✓"
                        )
                        print(
                            f"[mysql][{self.session_id}] Default database set to: shophub"
                        )
                        self.send_ok_packet(sequence_id + 1)
                    else:
                        print(
                            f"[mysql][{self.session_id}] ✗✗✗ AUTHENTICATION FAILED ✗✗✗"
                        )
                        self.send_error_packet(
                            1045,
                            "28000",
                            f"Access denied for user '{self.username}'@'localhost' (using password: YES)",
                            sequence_id + 1,
                        )
                        await asyncio.sleep(0.5)
                        self.transport.close()
                else:
                    print(
                        f"[mysql][{self.session_id}] Unexpected auth response length: {len(payload)}"
                    )
                    self.send_error_packet(
                        1045, "28000", "Access denied", sequence_id + 1
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                return

            # Parse HandshakeResponse packet
            try:
                print(f"[mysql][{self.session_id}] === AUTH PACKET DEBUG ===")
                print(f"[mysql][{self.session_id}] Length: {len(payload)} bytes")
                print(
                    f"[mysql][{self.session_id}] First 80 bytes hex:\n{payload[:80].hex()}"
                )

                # Try to parse the packet
                pos = 0

                # Client capability flags (4 bytes)
                if len(payload) < 32:
                    raise Exception(f"Packet too short: {len(payload)} bytes")

                capability_flags = struct.unpack("<I", payload[pos : pos + 4])[0]
                pos += 4

                # Max packet size (4 bytes)
                # max_packet = struct.unpack("<I", payload[pos : pos + 4])[0]
                pos += 4

                # Charset (1 byte)
                # charset = payload[pos]
                pos += 1

                # Reserved (23 bytes)
                pos += 23

                # Now at position 32 - username should start here
                print(
                    f"[mysql][{self.session_id}] Position 32, looking for username..."
                )

                # Username (null-terminated)
                username_start = pos
                username_end = payload.find(b"\x00", pos)

                if username_end == -1:
                    raise Exception("Username not null-terminated")

                self.username = payload[username_start:username_end].decode(
                    "utf-8", errors="ignore"
                )
                pos = username_end + 1

                print(f"[mysql][{self.session_id}] Username: '{self.username}'")
                print(f"[mysql][{self.session_id}] Position after username: {pos}")
                print(
                    f"[mysql][{self.session_id}] Remaining bytes: {len(payload) - pos}"
                )

                if pos >= len(payload):
                    print(f"[mysql][{self.session_id}] No auth data - empty password")
                    self.send_error_packet(
                        1045,
                        "28000",
                        f"Access denied for user '{self.username}'@'localhost' (using password: NO)",
                        sequence_id + 1,
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                    return

                # Auth response length
                auth_len_byte = payload[pos]
                print(
                    f"[mysql][{self.session_id}] Auth length byte at pos {pos}: 0x{auth_len_byte:02x} ({auth_len_byte})"
                )

                # Check if CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA is set
                if (
                    capability_flags & 0x00200000
                ):  # CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
                    print(f"[mysql][{self.session_id}] Using length-encoded auth data")
                    # Length-encoded integer
                    if auth_len_byte < 251:
                        auth_response_len = auth_len_byte
                        pos += 1
                    elif auth_len_byte == 0xFC:
                        auth_response_len = struct.unpack(
                            "<H", payload[pos + 1 : pos + 3]
                        )[0]
                        pos += 3
                    elif auth_len_byte == 0xFD:
                        auth_response_len = struct.unpack(
                            "<I", payload[pos + 1 : pos + 4] + b"\x00"
                        )[0]
                        pos += 4
                    else:
                        auth_response_len = 0
                        pos += 1
                else:
                    # Fixed 1-byte length
                    print(f"[mysql][{self.session_id}] Using 1-byte auth data length")
                    auth_response_len = auth_len_byte
                    pos += 1

                print(
                    f"[mysql][{self.session_id}] Auth response length: {auth_response_len}"
                )
                print(f"[mysql][{self.session_id}] Current position: {pos}")

                if auth_response_len == 0:
                    print(
                        f"[mysql][{self.session_id}] Empty auth response - checking for plugin auth"
                    )

                    # Check if there's a database name and plugin name after
                    # Format: [auth_len=0][database][plugin_name]
                    remaining_data = payload[pos:]
                    print(
                        f"[mysql][{self.session_id}] Remaining data after auth_len: {remaining_data.hex()}"
                    )

                    if len(remaining_data) > 0:
                        # Try to read database name (null-terminated)
                        db_end = remaining_data.find(b"\x00")
                        if db_end != -1 and db_end > 0:
                            db_name = remaining_data[:db_end].decode(
                                "utf-8", errors="ignore"
                            )
                            print(f"[mysql][{self.session_id}] Database: '{db_name}'")
                            remaining_data = remaining_data[db_end + 1 :]

                        # Try to read plugin name
                        if len(remaining_data) > 0:
                            plugin_end = remaining_data.find(b"\x00")
                            if plugin_end != -1:
                                plugin_name = remaining_data[:plugin_end].decode(
                                    "utf-8", errors="ignore"
                                )
                                print(
                                    f"[mysql][{self.session_id}] Plugin: '{plugin_name}'"
                                )

                                # Send AuthSwitchRequest for mysql_native_password
                                print(
                                    f"[mysql][{self.session_id}] Sending auth switch request"
                                )
                                self.auth_switch_sent = True
                                auth_switch = (
                                    b"\xfe"  # Auth switch request
                                    + b"mysql_native_password\x00"
                                    + self.auth_salt
                                    + b"\x00"
                                )
                                self.send_packet(auth_switch, sequence_id + 1)
                                return

                    # FOR TESTING: Accept any user without password (if REQUIRE_PASSWORD is False)
                    if not REQUIRE_PASSWORD:
                        print(
                            f"[mysql][{self.session_id}] === PASSWORD NOT REQUIRED (TESTING MODE) ==="
                        )
                        if self.username in VALID_CREDENTIALS:
                            self.authenticated = True
                            # Set default database to shophub
                            controller.db_state.use_database("shophub")
                            print(
                                f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL (NO PASSWORD) ✓✓✓"
                            )
                            print(
                                f"[mysql][{self.session_id}] Default database set to: shophub"
                            )
                            self.send_ok_packet(sequence_id + 1)
                            return

                    # Reject - no password provided
                    print(
                        f"[mysql][{self.session_id}] No password provided and REQUIRE_PASSWORD={REQUIRE_PASSWORD}"
                    )
                    self.send_error_packet(
                        1045,
                        "28000",
                        f"Access denied for user '{self.username}'@'localhost' (using password: NO)",
                        sequence_id + 1,
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                    return

                if pos + auth_response_len > len(payload):
                    print(
                        f"[mysql][{self.session_id}] Auth response would exceed packet"
                    )
                    print(
                        f"[mysql][{self.session_id}] Need: {pos + auth_response_len}, Have: {len(payload)}"
                    )
                    raise Exception("Auth response exceeds packet")

                auth_response = payload[pos : pos + auth_response_len]
                print(
                    f"[mysql][{self.session_id}] Auth response ({len(auth_response)} bytes): {auth_response.hex()}"
                )

                # Verify password
                if self.verify_password(self.username, auth_response):
                    self.authenticated = True
                    # Set default database to shophub
                    controller.db_state.use_database("shophub")
                    print(
                        f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL ✓✓✓"
                    )
                    print(
                        f"[mysql][{self.session_id}] Default database set to: shophub"
                    )
                    self.send_ok_packet(sequence_id + 1)
                else:
                    print(f"[mysql][{self.session_id}] ✗✗✗ AUTHENTICATION FAILED ✗✗✗")
                    self.send_error_packet(
                        1045,
                        "28000",
                        f"Access denied for user '{self.username}'@'localhost' (using password: YES)",
                        sequence_id + 1,
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()

            except Exception as e:
                print(f"[mysql][{self.session_id}] Auth error: {e}")
                import traceback

                traceback.print_exc()
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

            # DEBUG: Print response type and content
            print(f"[mysql][{self.session_id}] === RESPONSE DEBUG ===")
            print(f"[mysql][{self.session_id}] Response type: {type(response)}")
            if isinstance(response, str):
                print(f"[mysql][{self.session_id}] Response is STRING")
                print(f"[mysql][{self.session_id}] First 300 chars: {response[:300]}")
            elif isinstance(response, dict):
                print(f"[mysql][{self.session_id}] Response is DICT")
                print(f"[mysql][{self.session_id}] Keys: {list(response.keys())}")
                if "columns" in response:
                    print(
                        f"[mysql][{self.session_id}] Has 'columns': {response['columns']}"
                    )
                if "rows" in response:
                    print(
                        f"[mysql][{self.session_id}] Has 'rows': {len(response['rows'])} rows"
                    )
                if "text" in response:
                    print(
                        f"[mysql][{self.session_id}] Has 'text': {response['text'][:100]}"
                    )

            # Parse string responses that might be JSON
            if isinstance(response, str):
                response = response.strip()
                # Try to parse as JSON if it looks like JSON
                if response.startswith("{"):
                    try:
                        parsed = json.loads(response)
                        print(
                            f"[mysql][{self.session_id}] Successfully parsed STRING as JSON"
                        )
                        print(
                            f"[mysql][{self.session_id}] Parsed keys: {list(parsed.keys())}"
                        )
                        response = parsed
                    except json.JSONDecodeError as e:
                        print(f"[mysql][{self.session_id}] JSON parse error: {e}")
                        response = {"text": response}
                else:
                    response = {"text": response}
            elif not isinstance(response, dict):
                response = {"text": str(response)}

            response_text = (
                response.get("text", "")
                if isinstance(response, dict)
                else str(response)
            )

            next_seq = sequence_id + 1
            q_upper = query.upper().strip()

            if response_text.startswith("ERROR"):
                self.send_error_packet(1064, "42000", response_text, next_seq)
            elif "Database changed" in response_text:
                self.send_ok_packet(next_seq)
            elif "Query OK" in response_text:
                affected = 1 if "1 row" in response_text else 0
                self.send_ok_packet(next_seq, affected_rows=affected)
            elif q_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")):
                # For SELECT queries, prefer columns/rows format
                print(f"[mysql][{self.session_id}] Sending result set for SELECT query")
                self.send_text_result(response, next_seq)
            else:
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
