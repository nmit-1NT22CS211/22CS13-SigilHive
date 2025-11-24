import asyncio
import asyncssh
import os
import time
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from .controller import Controller, SHOPHUB_STRUCTURE
from kafka_manager import HoneypotKafka

# Load environment variables from .env file
load_dotenv()

# Listen on all interfaces (IPv4 & IPv6 inside container)
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "2223"))

# Configure valid credentials
VALID_USERNAME = os.getenv("SSH_USERNAME", "shophub")
VALID_PASSWORD = os.getenv("SSH_PASSWORD", "ShopHub121!")

controller = Controller(persona="shophub-production-server")
controller.sessions = {}  # Initialize sessions dictionary

# Kafka manager for SSH honeypot
kafka = HoneypotKafka(
    "ssh", config_path=os.getenv("KAFKA_CONFIG_PATH", "kafka_config.json")
)


# Define a resilient async Kafka handler for consumer loop
async def ssh_kafka_handler(*args, **kwargs):
    try:
        print(f"[honeypot] kafka handler invoked with args={args} kwargs={kwargs}")

        if hasattr(controller, "handle_kafka_event"):
            try:
                await controller.handle_kafka_event(*args, **kwargs)
            except TypeError:
                controller.handle_kafka_event(*args, **kwargs)
    except Exception as e:
        print(f"[honeypot] ssh_kafka_handler error: {e}")


class HoneypotSession(asyncssh.SSHServerSession):
    def __init__(self, session_id):
        super().__init__()
        self._chan = None
        self.session_id = session_id
        self._input = ""
        self.start_time = time.time()
        self.cmd_count = 0
        self._closed = False
        self.current_dir = "~"
        self.username = "shophub"
        self.hostname = "shophub-prod-01"

    def connection_made(self, chan):
        self._chan = chan
        controller.sessions[self.session_id] = {"transport": chan}
        peer = chan.get_extra_info("peername")
        print(f"[honeypot][{self.session_id}] connection established from {peer}")
        try:
            banner = f"""
╔═══════════════════════════════════════════════════════════╗
║         Welcome to ShopHub Production Server              ║
║                                                           ║
║  WARNING: Unauthorized access is strictly prohibited      ║
║  All activities are monitored and logged                  ║
╚═══════════════════════════════════════════════════════════╝

ShopHub v2.3.1 - E-commerce Platform
Last login: {datetime.now().strftime("%a %b %d %H:%M:%S %Y")} from 10.0.2.15

"""
            self._chan.write(str(banner))
            self._chan.write("\r\n")
            self._write_prompt()
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error in connection_made: {e}")

    def _write_prompt(self):
        """Write a realistic shell prompt"""
        if self._chan and not self._closed:
            try:
                prompt = (
                    f"\033[32m{self.username}@{self.hostname}\033[0m:"
                    f"\033[34m{self.current_dir}\033[0m$ "
                )
                self._chan.write(str(prompt))
            except Exception as e:
                print(f"[honeypot][{self.session_id}] error in _write_prompt: {e}")

    def _normalize_path(self, path: str) -> str:
        """Normalize a path relative to current directory"""
        if path.startswith("/"):
            if path == "/":
                return "/"
            if path.startswith("/home/shophub"):
                return path.replace("/home/shophub", "~")
            return path
        elif path.startswith("~"):
            return path
        elif path == ".":
            return self.current_dir
        elif path == "..":
            return self._get_parent_dir(self.current_dir)
        else:
            if self.current_dir == "~":
                return f"~/{path}"
            elif self.current_dir.endswith("/"):
                return f"{self.current_dir}{path}"
            else:
                return f"{self.current_dir}/{path}"

    def _get_parent_dir(self, path: str) -> str:
        """Get parent directory of given path"""
        if path in ("~", "/", "/home/shophub"):
            return "~"

        path = path.rstrip("/")

        if path.startswith("~/"):
            parts = path[2:].split("/")
            if len(parts) <= 1:
                return "~"
            return "~/" + "/".join(parts[:-1])

        if path.startswith("/"):
            parts = path[1:].split("/")
            if len(parts) <= 1:
                return "/"
            return "/" + "/".join(parts[:-1])

        return "~"

    def _directory_exists(self, path: str) -> bool:
        """Check if a directory exists in our structure"""
        normalized = self._normalize_path(path)
        return normalized in SHOPHUB_STRUCTURE

    def data_received(self, data, datatype):
        """Handle incoming data from SSH client"""
        self._input += data

        while "\n" in self._input or "\r" in self._input:
            if "\r\n" in self._input:
                line, self._input = self._input.split("\r\n", 1)
            elif "\n" in self._input:
                line, self._input = self._input.split("\n", 1)
            elif "\r" in self._input:
                line, self._input = self._input.split("\r", 1)
            else:
                break

            cmd = line.strip()

            if cmd.lower() in ("exit", "logout", "quit"):
                try:
                    self._chan.write("\nGoodbye from ShopHub!\n")
                    self._chan.exit(0)
                except Exception:
                    pass
                return

            if cmd == "":
                try:
                    self._write_prompt()
                except Exception:
                    pass
                continue

            if cmd.startswith("cd ") or cmd == "cd":
                self._handle_cd_command(cmd)
                continue

            self.cmd_count += 1
            asyncio.create_task(self.handle_command(cmd))

    def _handle_cd_command(self, cmd: str):
        """Handle cd command with validation"""
        parts = cmd.split(maxsplit=1)

        if len(parts) == 1 or (len(parts) > 1 and parts[1] == "~"):
            self.current_dir = "~"
        elif len(parts) > 1 and parts[1] == "..":
            self.current_dir = self._get_parent_dir(self.current_dir)
        elif len(parts) > 1 and parts[1] == ".":
            pass
        elif len(parts) > 1 and parts[1] == "/":
            self.current_dir = "~"
        else:
            target_path = self._normalize_path(parts[1])
            if self._directory_exists(target_path):
                self.current_dir = target_path
            else:
                try:
                    self._chan.write(
                        f"bash: cd: {parts[1]}: No such file or directory\n"
                    )
                except Exception:
                    pass
                finally:
                    try:
                        self._write_prompt()
                    except Exception:
                        pass
                    return

        print(f"[honeypot][{self.session_id}] cd -> {self.current_dir}")

        try:
            self._write_prompt()
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error writing prompt after cd: {e}")

    async def handle_command(self, cmd: str):
        """Handle commands asynchronously - pass everything to controller"""
        if self._closed or not self._chan:
            return

        peer_ip = (
            self._chan.get_extra_info("peername")[0]
            if self._chan and self._chan.get_extra_info("peername")
            else "unknown"
        )

        event = {
            "session_id": self.session_id,
            "type": "command",
            "command": cmd,
            "current_dir": self.current_dir,
            "ts": datetime.now(timezone.utc).isoformat(),
            "cmd_count": self.cmd_count,
            "elapsed": time.time() - self.start_time,
            "remote_addr": peer_ip,
        }

        try:
            action = await controller.get_action_for_session(self.session_id, event)
        except Exception as e:
            print(f"[honeypot][{self.session_id}] controller error: {e}")
            cmd_parts = cmd.split()
            base = cmd_parts[0] if cmd_parts else "unknown"
            action = {
                "response": f"bash: {base}: command not found",
                "delay": 0.05,
            }

        response_text = action.get("response", "") or ""
        delay = float(action.get("delay", 0.0) or 0.0)

        # Publish SSH event to Kafka AFTER we have the response
        try:
            preview = response_text[:400] if response_text else ""
            kafka.send(
                "SSHtoDB",
                {
                    "target": "database",
                    "event_type": "ssh_command",
                    "session_id": self.session_id,
                    "command": cmd,
                    "result_preview": preview,
                    "remote_addr": peer_ip,
                    "current_dir": self.current_dir,
                },
            )
            kafka.send(
                "SSHtoHTTP",
                {
                    "target": "http",
                    "event_type": "ssh_command",
                    "session_id": self.session_id,
                    "command": cmd,
                    "result_preview": preview,
                },
            )
        except Exception as e:
            print(f"[honeypot][{self.session_id}] Kafka send error: {e}")

        if delay > 0:
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

        try:
            self._chan.write(str(response_text))
            if not str(response_text).endswith("\n"):
                self._chan.write("\n")
            self._write_prompt()
        except (BrokenPipeError, EOFError, asyncssh.Error) as e:
            print(f"[honeypot][{self.session_id}] write error (connection closed): {e}")
            self._closed = True

    def eof_received(self):
        print(f"[honeypot][{self.session_id}] EOF received")
        return True

    def break_received(self, msec):
        print(f"[honeypot][{self.session_id}] break received (Ctrl+C)")
        return True

    def signal_received(self, signal):
        print(f"[honeypot][{self.session_id}] signal received: {signal}")
        pass

    def session_started(self):
        print(f"[honeypot][{self.session_id}] session started")
        pass

    def terminal_size_changed(self, width, height, pixwidth, pixheight):
        print(f"[honeypot][{self.session_id}] terminal resized: {width}x{height}")
        pass

    def pty_requested(self, *args, **kwargs):
        """
        Accept any pty_requested signature across asyncssh versions.
        """
        try:
            if len(args) >= 1:
                term = args[0]
            else:
                term = kwargs.get("term_type", kwargs.get("term", "<unknown>"))
            width = args[1] if len(args) >= 2 else kwargs.get("width", 80)
            height = args[2] if len(args) >= 3 else kwargs.get("height", 24)
            print(
                f"[honeypot][{self.session_id}] pty requested: term={term}, size={width}x{height}"
            )
        except Exception:
            print(f"[honeypot][{self.session_id}] pty requested (could not parse args)")
        return True

    def shell_requested(self):
        print(f"[honeypot][{self.session_id}] shell requested")
        return True

    def connection_lost(self, exc):
        self._closed = True
        duration = time.time() - self.start_time
        print(f"[honeypot][{self.session_id}] connection closed after {duration:.2f}s")

        if self.session_id in controller.sessions:
            del controller.sessions[self.session_id]

        try:
            controller.end_session(self.session_id)
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error ending session: {e}")

        if exc:
            print(f"[honeypot][{self.session_id}] connection error: {exc}")


class HoneypotServer(asyncssh.SSHServer):
    """Custom SSH server class that creates sessions"""

    def __init__(self):
        super().__init__()
        self.conn_id = str(uuid.uuid4())[:8]
        print(
            f"[honeypot][{self.conn_id}] new SSH connection from {conn.get_extra_info('peername')}"
        )

    def connection_lost(self, exc):
        if exc:
            print(f"[honeypot][{self.conn_id}] connection error: {exc}")
        else:
            print(f"[honeypot][{self.conn_id}] connection closed cleanly")

    def begin_auth(self, username):
        print(f"[honeypot][{self.conn_id}] authentication attempt for '{username}'")
        return True

    # --- CRITICAL FIX: ADDED METHOD TO TRIGGER PASSWORD PROMPT ---
    def get_password(self, username):
        """Forces the server to send the password prompt to the client."""
        # Returning an empty string tells asyncssh to request a password interactively.
        return ""

    # ------------------------------------------------------------

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        print(f"[honeypot][{self.conn_id}] login attempt: {username}:{password}")

        # You may want to log failed attempts to Kafka here before returning False

        is_valid = username == VALID_USERNAME and password == VALID_PASSWORD

        if is_valid:
            print(
                f"[honeypot][{self.conn_id}] ✓ authentication successful for '{username}'"
            )
        else:
            print(
                f"[honeypot][{self.conn_id}] ✗ authentication failed for '{username}'"
            )

        return is_valid

    def session_requested(self):
        session_id = str(uuid.uuid4())[:8]
        print(f"[honeypot][{self.conn_id}] session requested -> {session_id}")
        return HoneypotSession(session_id)

    def kbdint_auth_supported(self):
        return False

    def public_key_auth_supported(self):
        return False


def ensure_host_key(path):
    """Create an ED25519 host key file if it doesn't exist (helps first-run)."""
    if os.path.exists(path):
        return
    try:
        print("[honeypot] generating ssh host key...")
        key = asyncssh.generate_private_key("ssh-ed25519")
        with open(path, "wb") as f:
            f.write(key.export_private_key())
        pub = key.export_public_key()
        with open(path + ".pub", "wb") as f:
            f.write(pub)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        print("[honeypot] ssh host key generated")
    except Exception as e:
        print(f"[honeypot] failed to generate host key: {e}")


async def start_server():
    """Start the honeypot SSH server"""
    print(f"[honeypot] starting SSH honeypot on {HOST}:{PORT} ...")
    print(f"[honeypot] valid credentials: {VALID_USERNAME}:{VALID_PASSWORD}")

    host_key_path = "./ssh_server/ssh_host_key"
    print(f"[honeypot] DEBUG: Using hardcoded SSH_HOST_KEY_PATH: {host_key_path}")
    ensure_host_key(host_key_path)

    try:
        host_key = asyncssh.read_private_key(host_key_path)
        print("[honeypot] Host key loaded successfully")
    except Exception as e:
        print(f"[honeypot] ERROR: Failed to load host key: {e}")
        return

    try:
        await controller.start_background_tasks()
    except Exception as e:
        print(f"[honeypot] warning: background tasks failed to start: {e}")

    try:
        # In ssh_server.py, update the asyncssh.create_server call
        # In ssh_server.py, update the asyncssh.create_server call
        server = await asyncssh.create_server(
            HoneypotServer,
            HOST,
            PORT,
            server_host_keys=[host_key],
            server_version="SSH-2.0-OpenSSH_8.9p1 Ubuntu-3",
            # EXPANDED ALGORITHM LISTS FOR COMPATIBILITY
            kex_algs=[
                "curve25519-sha256",
                "diffie-hellman-group14-sha256",
                "diffie-hellman-group16-sha512",
                "diffie-hellman-group18-sha512",
            ],
            encryption_algs=[
                "chacha20-poly1305@openssh.com",
                "aes256-gcm@openssh.com",
                "aes128-gcm@openssh.com",  # <-- CORRECTED TYPO HERE
                "aes256-ctr",
                "aes128-ctr",
            ],
            mac_algs=["hmac-sha2-512", "hmac-sha2-256"],
            compression_algs=["none"],
        )

        print(f"[honeypot] 🚀 SSH honeypot listening on {HOST}:{PORT}")
        print("[honeypot] Waiting for SSH connections...")

        loop = asyncio.get_running_loop()
        loop.create_task(kafka.start_consumer_loop(ssh_kafka_handler))

        await server.wait_closed()

    except (OSError, asyncssh.Error) as exc:
        print(f"[honeypot] server failed to start: {exc}")

    finally:
        try:
            await controller.stop_background_tasks()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except (KeyboardInterrupt, SystemExit):
        print("\n[honeypot] shutting down gracefully...")
