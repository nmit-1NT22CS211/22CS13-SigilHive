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

# Password required by default now
REQUIRE_PASSWORD = os.getenv("REQUIRE_PASSWORD", "true").lower() == "true"

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
        self._processing = False

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
        # Capability flags
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

        stage1 = hashlib.sha1(password.encode()).digest()
        stage2 = hashlib.sha1(stage1).digest()
        stage3 = hashlib.sha1(salt + stage2).digest()
        result = bytes(a ^ b for a, b in zip(stage1, stage3))
        return result

    def verify_password(self, username: str, auth_response: bytes) -> bool:
        """Verify password against valid credentials"""
        if not REQUIRE_PASSWORD:
            print(f"[mysql][{self.session_id}] password check disabled - allowing")
            return True

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

    def send_ok_packet(self, sequence_id=1):
        """Send a MySQL 8 OK packet (correct structure)."""
        payload = (
            b"\x00"  # OK header
            b"\x00"  # affected rows = 0
            b"\x00"  # last insert id = 0
            b"\x02\x00"  # SERVER_STATUS_AUTOCOMMIT
            b"\x00\x00"  # warnings = 0
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
        """Send SELECT/SHOW results properly formatted as real MySQL tables."""
        try:
            # 1) Normalize into dict
            if isinstance(result_data, str):
                # Try JSON
                try:
                    result_data = json.loads(result_data)
                except Exception:
                    # Not JSON → wrap as text result
                    result_data = {"columns": ["result"], "rows": [[result_data]]}

            # 2) Ensure dict format
            if not isinstance(result_data, dict):
                result_data = {"columns": ["result"], "rows": [[str(result_data)]]}

            # 3) Extract columns + rows
            columns = result_data.get("columns")
            rows = result_data.get("rows")

            # If JSON was wrongly shaped
            if not isinstance(columns, list) or not isinstance(rows, list):
                result_data = {
                    "columns": ["result"],
                    "rows": [[json.dumps(result_data)]],
                }
                columns = result_data["columns"]
                rows = result_data["rows"]

            num_columns = len(columns)
            current_seq = sequence_id

            # --- COLUMN COUNT PACKET ---
            self.send_packet(self.encode_length(num_columns), current_seq)
            current_seq += 1

            # --- COLUMN DEFINITIONS ---
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
                    + struct.pack("<I", 1024)
                    + struct.pack("B", 0xFD)
                    + struct.pack("<H", 0)
                    + struct.pack("B", 0)
                    + struct.pack("<H", 0)
                )
                self.send_packet(col_def, current_seq)
                current_seq += 1

            # --- EOF AFTER COLUMNS ---
            eof_packet = b"\xfe" + struct.pack("<H", 0) + struct.pack("<H", 0x0002)
            self.send_packet(eof_packet, current_seq)
            current_seq += 1

            # --- ROWS ---
            for row in rows:
                row_payload = b""
                for value in row:
                    if value is None:
                        encoded = b""
                    else:
                        encoded = str(value).encode()
                    row_payload += self.encode_length_string(encoded)

                self.send_packet(row_payload, current_seq)
                current_seq += 1

            # --- FINAL EOF ---
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
        if self._processing:
            return

        self._processing = True

        while True:
            try:
                payload, seq = await asyncio.wait_for(
                    self._packet_queue.get(), timeout=30.0
                )
            except asyncio.TimeoutError:
                print(f"[mysql][{self.session_id}] packet worker timeout")
                break
            except Exception as e:
                print(f"[mysql][{self.session_id}] queue get error: {e}")
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

        self._processing = False

    async def handle_packet(self, payload, sequence_id):
        """Handle MySQL packet"""
        if not payload:
            return

        print(
            f"[mysql][{self.session_id}] handle_packet: seq={sequence_id}, len={len(payload)}, auth={self.authenticated}, auth_switch={self.auth_switch_sent}"
        )

        # -----------------------------
        # AUTHENTICATION / HANDSHAKE
        # -----------------------------
        if not self.authenticated:
            # 1) AUTH SWITCH RESPONSE (client replies to our 0xFE AuthSwitchRequest)
            if self.auth_switch_sent:
                print(f"[mysql][{self.session_id}] === AUTH SWITCH RESPONSE ===")
                print(f"[mysql][{self.session_id}] Length: {len(payload)} bytes")
                print(f"[mysql][{self.session_id}] Hex: {payload.hex()}")

                if len(payload) < 20:
                    print(
                        f"[mysql][{self.session_id}] Auth switch response too short: {len(payload)} bytes"
                    )
                    self.send_error_packet(
                        1045, "28000", "Access denied", sequence_id + 1
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                    return

                auth_response = payload[:20]
                print(
                    f"[mysql][{self.session_id}] Auth response (20 bytes): {auth_response.hex()}"
                )

                if self.verify_password(self.username, auth_response):
                    self.authenticated = True
                    self.auth_switch_sent = False
                    print(
                        f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL (AuthSwitch) ✓✓✓"
                    )
                    print(
                        f"[mysql][{self.session_id}] Default database: <none selected>"
                    )
                    self.send_ok_packet(sequence_id + 1)
                else:
                    print(
                        f"[mysql][{self.session_id}] ✗✗✗ AUTHENTICATION FAILED (AuthSwitch) ✗✗✗"
                    )
                    self.send_error_packet(
                        1045,
                        "28000",
                        f"Access denied for user '{self.username}'@'localhost' (using password: YES)",
                        sequence_id + 1,
                    )
                    await asyncio.sleep(0.5)
                    self.transport.close()
                return

            # 2) INITIAL HANDSHAKE RESPONSE FROM CLIENT
            try:
                print(f"[mysql][{self.session_id}] === AUTH PACKET DEBUG ===")
                print(f"[mysql][{self.session_id}] Length: {len(payload)} bytes")
                print(
                    f"[mysql][{self.session_id}] First 80 bytes hex:\n{payload[:80].hex()}"
                )

                pos = 0

                if len(payload) < 32:
                    raise Exception(f"Packet too short: {len(payload)} bytes")

                # Client capability flags (4 bytes)
                capability_flags = struct.unpack("<I", payload[pos : pos + 4])[0]
                pos += 4

                # max_packet (4), charset (1), reserved (23)
                pos += 4  # max_packet
                pos += 1  # charset
                pos += 23  # reserved

                # Username (null-terminated)
                print(
                    f"[mysql][{self.session_id}] Position 32, looking for username..."
                )
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
                    if not REQUIRE_PASSWORD:
                        self.authenticated = True
                        print(
                            f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL (No password required) ✓✓✓"
                        )
                        self.send_ok_packet(sequence_id + 1)
                        return
                    else:
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

                # CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
                if capability_flags & 0x00200000:
                    print(f"[mysql][{self.session_id}] Using length-encoded auth data")
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
                    print(f"[mysql][{self.session_id}] Using 1-byte auth data length")
                    auth_response_len = auth_len_byte
                    pos += 1

                print(
                    f"[mysql][{self.session_id}] Auth response length: {auth_response_len}"
                )
                print(f"[mysql][{self.session_id}] Current position: {pos}")

                # Case: client sent NO password in first packet → send AuthSwitchRequest
                if auth_response_len == 0:
                    print(
                        f"[mysql][{self.session_id}] Empty auth response → sending AuthSwitchRequest"
                    )
                    self.auth_switch_sent = True
                    auth_switch = (
                        b"\xfe"
                        + b"mysql_native_password\x00"
                        + self.auth_salt
                        + b"\x00"
                    )
                    self.send_packet(auth_switch, sequence_id + 1)
                    print(
                        f"[mysql][{self.session_id}] AuthSwitchRequest sent, waiting for client response..."
                    )
                    return

                # Normal case: auth data is present in this first packet
                if pos + auth_response_len > len(payload):
                    print(
                        f"[mysql][{self.session_id}] Auth response would exceed packet: need {pos + auth_response_len}, have {len(payload)}"
                    )
                    raise Exception("Auth response exceeds packet")

                auth_response = payload[pos : pos + auth_response_len]
                print(
                    f"[mysql][{self.session_id}] Auth response ({len(auth_response)} bytes): {auth_response.hex()}"
                )

                # For mysql_native_password, only first 20 bytes are relevant
                if len(auth_response) >= 20:
                    auth_response = auth_response[:20]

                # Verify password
                if self.verify_password(self.username, auth_response):
                    self.authenticated = True
                    print(
                        f"[mysql][{self.session_id}] ✓✓✓ AUTHENTICATION SUCCESSFUL (Handshake) ✓✓✓"
                    )
                    print(
                        f"[mysql][{self.session_id}] Default database: <none selected>"
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

        # -----------------------------
        # AFTER AUTHENTICATION
        # -----------------------------
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

            print(f"[mysql][{self.session_id}] === RESPONSE DEBUG ===")
            print(f"[mysql][{self.session_id}] Response type: {type(response)}")

            # Parse and normalize response
            if isinstance(response, str):
                response = response.strip()
                try:
                    parsed = json.loads(response)
                    response = parsed
                except Exception:
                    response = {"text": response}

            # If controller returned {"text": "<json>"}, unwrap it
            if isinstance(response, dict) and "text" in response:
                text = response["text"]
                if isinstance(text, str) and text.strip().startswith("{"):
                    try:
                        parsed = json.loads(text)
                        if (
                            isinstance(parsed, dict)
                            and "columns" in parsed
                            and "rows" in parsed
                        ):
                            response = parsed
                    except Exception:
                        pass

            # Send appropriate response
            if (
                isinstance(response, dict)
                and "columns" in response
                and "rows" in response
            ):
                self.send_text_result(response, sequence_id + 1)
            elif isinstance(response, str):
                if response.startswith("ERROR"):
                    self.send_error_packet(1064, "42000", response, sequence_id + 1)
                elif response.startswith("Query OK") or response == "Database changed":
                    self.send_ok_packet(sequence_id + 1)
                else:
                    self.send_text_result(
                        {"columns": ["result"], "rows": [[response]]}, sequence_id + 1
                    )
            else:
                self.send_ok_packet(sequence_id + 1)

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
