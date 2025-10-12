# database_honeypot.py
import asyncio
import os
import struct
import uuid
import time
from datetime import datetime, timezone
from controller import IntelligentDBController  # Changed import

# Configuration
MYSQL_HOST = "0.0.0.0"
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "13306"))
POSTGRES_HOST = "0.0.0.0"
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "15432"))

# Use intelligent controllers
mysql_controller = IntelligentDBController(db_type="mysql", persona="mysql-8.0")
postgres_controller = IntelligentDBController(
    db_type="postgresql", persona="postgresql-15"
)


# ============================================================================
# MySQL Protocol Implementation
# ============================================================================


class MySQLProtocol(asyncio.Protocol):
    """Implements basic MySQL protocol for honeypot"""

    def __init__(self):
        self.transport = None
        self.session_id = str(uuid.uuid4())
        self.query_count = 0
        self.start_time = time.time()
        self.current_db = None
        self.authenticated = False
        self.username = None
        self._buffer = b""

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        print(f"[mysql][{self.session_id}] connection from {peername}")
        self.send_handshake()

    def send_handshake(self):
        """Send MySQL initial handshake packet"""
        protocol_version = 10
        server_version = b"8.0.33-honeypot\x00"
        connection_id = struct.pack("<I", hash(self.session_id) & 0xFFFFFFFF)
        auth_data_part1 = os.urandom(8)
        filler = b"\x00"
        capability_flags_1 = struct.pack("<H", 0xFFFF)
        charset = struct.pack("B", 0x21)
        status_flags = struct.pack("<H", 0x0002)
        capability_flags_2 = struct.pack("<H", 0x0000)
        auth_data_len = struct.pack("B", 21)
        reserved = b"\x00" * 10
        auth_data_part2 = os.urandom(12) + b"\x00"
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

    def send_packet(self, payload, sequence_id):
        """Send a MySQL packet with header"""
        length = len(payload)
        header = struct.pack("<I", length)[:3] + struct.pack("B", sequence_id)
        self.transport.write(header + payload)

    def send_ok_packet(self, sequence_id=1, affected_rows=0, message=None):
        """Send OK packet"""
        payload = (
            b"\x00"
            + self.encode_length(affected_rows)
            + self.encode_length(0)
            + struct.pack("<H", 0x0002)
            + struct.pack("<H", 0x0000)
        )
        if message:
            payload += message.encode()
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

    def send_text_result(self, text, sequence_id=1):
        """Send result as plain text in a result set"""
        # Column count
        self.send_packet(self.encode_length(1), sequence_id)

        # Column definition
        col_def = (
            self.encode_length_string(b"def")
            + self.encode_length_string(b"")
            + self.encode_length_string(b"")
            + self.encode_length_string(b"")
            + self.encode_length_string(b"result")
            + self.encode_length_string(b"result")
            + b"\x0c"
            + struct.pack("<H", 0x21)
            + struct.pack("<I", 0x100)
            + struct.pack("B", 0xFD)
            + struct.pack("<H", 0x0000)
            + struct.pack("B", 0x00)
            + struct.pack("<H", 0x0000)
        )
        self.send_packet(col_def, sequence_id + 1)

        # EOF after columns
        eof = b"\xfe" + struct.pack("<H", 0x0000) + struct.pack("<H", 0x0002)
        self.send_packet(eof, sequence_id + 2)

        # Row data
        row = self.encode_length_string(text.encode())
        self.send_packet(row, sequence_id + 3)

        # EOF after rows
        self.send_packet(eof, sequence_id + 4)

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

            asyncio.create_task(self.handle_packet(payload, sequence_id))

    async def handle_packet(self, payload, sequence_id):
        """Handle received MySQL packet"""
        if not payload:
            return

        packet_type = payload[0]

        if not self.authenticated:
            # Parse username from auth packet
            try:
                pos = 32
                username_end = payload.find(b"\x00", pos)
                if username_end > pos:
                    self.username = payload[pos:username_end].decode(
                        "utf-8", errors="ignore"
                    )
            except Exception:
                self.username = "unknown"

            self.authenticated = True
            print(f"[mysql][{self.session_id}] client authenticated as {self.username}")
            self.send_ok_packet(sequence_id + 1)
            return

        # COM_QUERY (0x03)
        if packet_type == 0x03:
            query = payload[1:].decode("utf-8", errors="ignore").strip()
            print(f"[mysql][{self.session_id}] query: {query}")
            self.query_count += 1
            await self.handle_query(query, sequence_id)

        # COM_QUIT (0x01)
        elif packet_type == 0x01:
            print(f"[mysql][{self.session_id}] client quit")
            self.transport.close()

    async def handle_query(self, query, sequence_id):
        """Handle SQL query using intelligent controller"""
        event = {
            "session_id": self.session_id,
            "type": "query",
            "query": query,
            "ts": datetime.now(timezone.utc).isoformat(),
            "query_count": self.query_count,
            "elapsed": time.time() - self.start_time,
            "current_db": self.current_db,
            "username": self.username,
        }

        try:
            action = await mysql_controller.get_action_for_query(self.session_id, event)
        except Exception as e:
            print(f"[mysql][{self.session_id}] controller error: {e}")
            self.send_error_packet(1064, "42000", str(e), sequence_id + 1)
            return

        if action.get("disconnect"):
            self.transport.close()
            return

        delay = action.get("delay", 0.0)
        if delay > 0:
            await asyncio.sleep(delay)

        response = action.get("response", "")

        # Send appropriate response based on query type and response
        q_upper = query.upper().strip()

        if response.startswith("ERROR"):
            self.send_error_packet(1064, "42000", response, sequence_id + 1)
        elif "Database changed" in response or "Query OK" in response:
            # Extract affected rows if present
            affected = 1 if "1 row" in response else 0
            self.send_ok_packet(
                sequence_id + 1, affected_rows=affected, message=response
            )
        elif q_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "DESC")):
            self.send_text_result(response, sequence_id + 1)
        else:
            self.send_ok_packet(sequence_id + 1, message=response)

    def connection_lost(self, exc):
        print(f"[mysql][{self.session_id}] connection lost: {exc}")


# ============================================================================
# PostgreSQL Protocol Implementation
# ============================================================================


class PostgreSQLProtocol(asyncio.Protocol):
    """Implements basic PostgreSQL protocol for honeypot"""

    def __init__(self):
        self.transport = None
        self.session_id = str(uuid.uuid4())
        self.query_count = 0
        self.start_time = time.time()
        self.current_db = None
        self.authenticated = False
        self.username = None
        self.database = None
        self._buffer = b""

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        print(f"[postgres][{self.session_id}] connection from {peername}")

    def send_message(self, msg_type, payload):
        """Send PostgreSQL message"""
        if isinstance(msg_type, str):
            msg_type = msg_type.encode()[0]
        length = len(payload) + 4
        # 'struct.pack("cI", ...)' expects a bytes object for c
        self.transport.write(struct.pack("!cI", bytes([msg_type]), length) + payload)

    def send_authentication_ok(self):
        self.send_message(b"R", struct.pack("!I", 0))

    def send_ready_for_query(self):
        self.send_message(b"Z", b"I")

    def send_parameter_status(self, name, value):
        payload = name.encode() + b"\x00" + value.encode() + b"\x00"
        self.send_message(b"S", payload)

    def send_backend_key_data(self):
        pid = os.getpid()
        secret = hash(self.session_id) & 0xFFFFFFFF
        payload = struct.pack("!II", pid, secret)
        self.send_message(b"K", payload)

    def send_error_response(self, message):
        payload = (
            b"S"
            + b"ERROR\x00"
            + b"C"
            + b"42000\x00"
            + b"M"
            + message.encode()
            + b"\x00"
            + b"\x00"
        )
        self.send_message(b"E", payload)

    def send_command_complete(self, tag):
        payload = tag.encode() + b"\x00"
        self.send_message(b"C", payload)

    def send_simple_result(self, text):
        """Send simple text result"""
        # Row description: 1 column named "result"
        # Format per protocol: int16 number of fields, then for each field:
        # name (nul-terminated), table OID (int32), column attr (int16), data type OID (int32),
        # data type size (int16), type modifier (int32), format code (int16)
        payload = struct.pack("!H", 1)  # 1 column
        payload += (
            b"result\x00"
            + struct.pack("!I", 0)  # table OID
            + struct.pack("!H", 0)  # column attr
            + struct.pack("!I", 25)  # text type oid = 25 (text)
            + struct.pack("!H", -1 & 0xFFFF)  # typlen (set to -1 -> variable)
            + struct.pack("!I", -1 & 0xFFFFFFFF)  # typmod
            + struct.pack("!H", 0)  # format code (text)
        )
        self.send_message(b"T", payload)

        # Data row
        value_bytes = text.encode()
        row_payload = (
            struct.pack("!H", 1) + struct.pack("!i", len(value_bytes)) + value_bytes
        )
        self.send_message(b"D", row_payload)

        # Command complete
        self.send_command_complete("SELECT 1")
        # Ready for query follows by caller

    def data_received(self, data):
        self._buffer += data

        if not self.authenticated:
            # Attempt to process startup packet(s)
            self.handle_startup()
        else:
            self.handle_messages()

    def handle_startup(self):
        """
        Parse PostgreSQL startup packet.
        Format:
          - int32 length (includes these 4 bytes)
          - int32 protocol/version or SSLRequest code
          - If protocol is normal, then sequence of key\0value\0... ending with an additional \0
        If it's an SSLRequest (protocol == 80877103), reply 'N' to indicate no SSL and consume packet.
        """
        # Need at least 8 bytes (length + protocol)
        while True:
            if len(self._buffer) < 8:
                return

            length = struct.unpack("!I", self._buffer[:4])[0]
            if len(self._buffer) < length:
                return  # wait until full startup packet arrives

            payload = self._buffer[4:length]
            self._buffer = self._buffer[length:]

            # protocol number / SSLRequest code
            if len(payload) < 4:
                # malformed - close
                print(f"[postgres][{self.session_id}] malformed startup packet")
                self.transport.close()
                return

            protocol = struct.unpack("!I", payload[:4])[0]

            # SSLRequest code is 80877103 - respond with 'N' to deny SSL
            if protocol == 80877103:
                try:
                    self.transport.write(b"N")
                except Exception:
                    pass
                # Continue loop in case more data follows
                continue

            # normal startup packet: parse key/value pairs from payload[4:]
            params_blob = payload[4:]
            params = {}
            try:
                parts = params_blob.split(b"\x00")
                # parts ends with an extra empty element
                # it = iter(parts)
                # iterate key, value pairs
                for i in range(0, len(parts) - 1, 2):
                    key = parts[i]
                    if not key:
                        break
                    val = parts[i + 1] if (i + 1) < len(parts) else b""
                    try:
                        params[key.decode()] = val.decode()
                    except Exception:
                        try:
                            params[key.decode(errors="ignore")] = val.decode(
                                errors="ignore"
                            )
                        except Exception:
                            pass
            except Exception:
                pass

            # extract username/database
            self.username = params.get("user", "unknown")
            self.database = params.get("database")
            self.current_db = self.database
            self.authenticated = True

            print(
                f"[postgres][{self.session_id}] startup received user={self.username} db={self.database}"
            )

            # Send some default parameter statuses
            try:
                self.send_parameter_status("server_version", "15.0-honeypot")
                self.send_parameter_status("integer_datetimes", "on")
                self.send_parameter_status("server_encoding", "UTF8")
                self.send_parameter_status("client_encoding", "UTF8")
            except Exception:
                pass

            # Authentication ok + backend key + ready for query
            try:
                self.send_authentication_ok()
                self.send_backend_key_data()
                self.send_ready_for_query()
            except Exception:
                pass

            # after completing startup, if buffer contains more messages, switch to message handling
            if self._buffer:
                # continue loop so next iteration will hit handle_messages path via data_received
                continue
            else:
                return

    def handle_messages(self):
        """
        Parse and handle regular messages after authentication.
        Messages are: 1 byte type, 4 byte length, then payload(length-4).
        We'll support:
          - 'Q' Simple Query
          - 'X' Terminate
          - other types: ignore or respond minimally
        """
        while True:
            if len(self._buffer) < 5:
                return
            msg_type = self._buffer[0:1]  # bytes
            length = struct.unpack("!I", self._buffer[1:5])[0]
            if len(self._buffer) < 1 + 4 + (length - 4):
                return  # wait for full message

            payload = self._buffer[5 : 5 + (length - 4)]
            # consume
            self._buffer = self._buffer[5 + (length - 4) :]

            t = msg_type.decode(errors="ignore")
            if t == "Q":
                # Simple Query: payload is a null-terminated string (query text)
                query = payload.rstrip(b"\x00").decode("utf-8", errors="ignore").strip()
                print(f"[postgres][{self.session_id}] query: {query}")
                self.query_count += 1
                # handle asynchronously
                asyncio.create_task(self.handle_query(query))
            elif t == "X":
                print(f"[postgres][{self.session_id}] client terminate")
                try:
                    self.transport.close()
                except Exception:
                    pass
                return
            else:
                # For unsupported message types, ignore or send ReadyForQuery to keep client happy
                # Optionally log unknown message types
                # print(f"[postgres][{self.session_id}] unknown message type: {t}")
                try:
                    # send ReadyForQuery to avoid client hanging in some cases
                    self.send_ready_for_query()
                except Exception:
                    pass
                continue

    async def handle_query(self, query):
        """Handle SQL query using intelligent controller for PostgreSQL"""
        event = {
            "session_id": self.session_id,
            "type": "query",
            "query": query,
            "ts": datetime.now(timezone.utc).isoformat(),
            "query_count": self.query_count,
            "elapsed": time.time() - self.start_time,
            "current_db": self.current_db,
            "username": self.username,
        }

        try:
            action = await postgres_controller.get_action_for_query(
                self.session_id, event
            )
        except Exception as e:
            print(f"[postgres][{self.session_id}] controller error: {e}")
            try:
                self.send_error_response(str(e))
                self.send_ready_for_query()
            except Exception:
                pass
            return

        if action.get("disconnect"):
            try:
                self.transport.close()
            except Exception:
                pass
            return

        delay = action.get("delay", 0.0)
        if delay > 0:
            await asyncio.sleep(delay)

        response = action.get("response", "")

        q_upper = query.upper().strip()
        try:
            if response.startswith("ERROR"):
                # Send error response
                self.send_error_response(response)
            elif "Database changed" in response or "Query OK" in response:
                # Some commands like CREATE/USE/INSERT/UPDATE: reply with CommandComplete
                # Try to guess a suitable tag
                tag = action.get("command_tag", "COMMAND")
                # If action doesn't supply tag, craft one
                if tag == "COMMAND":
                    if q_upper.startswith("INSERT"):
                        tag = "INSERT 0 1"
                    elif q_upper.startswith("UPDATE"):
                        tag = "UPDATE 1"
                    elif q_upper.startswith("DELETE"):
                        tag = "DELETE 1"
                    else:
                        tag = "QUERY 0"
                self.send_command_complete(tag)
            elif q_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "DESC")):
                # send simple textual result
                # If response is empty, send an empty result
                self.send_simple_result(response)
            else:
                # Generic OK
                tag = action.get("command_tag", "QUERY 0")
                self.send_command_complete(tag)
        except Exception as e:
            print(f"[postgres][{self.session_id}] error sending response: {e}")
            try:
                self.send_error_response(str(e))
            except Exception:
                pass

        # After sending response(s), indicate ready for next query
        try:
            self.send_ready_for_query()
        except Exception:
            pass

    def connection_lost(self, exc):
        print(f"[postgres][{self.session_id}] connection lost: {exc}")


# ============================================================================
# Entry point
# ============================================================================


async def main():
    loop = asyncio.get_running_loop()

    # Start MySQL honeypot
    mysql_server = await loop.create_server(
        lambda: MySQLProtocol(), MYSQL_HOST, MYSQL_PORT
    )
    print(f"[honeypot] MySQL honeypot listening on {MYSQL_HOST}:{MYSQL_PORT}")

    # Start PostgreSQL honeypot
    postgres_server = await loop.create_server(
        lambda: PostgreSQLProtocol(), POSTGRES_HOST, POSTGRES_PORT
    )
    print(
        f"[honeypot] PostgreSQL honeypot listening on {POSTGRES_HOST}:{POSTGRES_PORT}"
    )

    try:
        await asyncio.gather(
            mysql_server.serve_forever(), postgres_server.serve_forever()
        )
    except asyncio.CancelledError:
        pass
    finally:
        mysql_server.close()
        postgres_server.close()
        await mysql_server.wait_closed()
        await postgres_server.wait_closed()
        print("[honeypot] servers shut down gracefully")


if __name__ == "__main__":
    try:
        print("[honeypot] starting database honeypot...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[honeypot] stopped by user")
    except Exception as e:
        print(f"[honeypot] runtime error: {e}")
