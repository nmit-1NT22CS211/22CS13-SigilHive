import asyncio
import asyncssh
import os
import time
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from controller import Controller, SHOPHUB_STRUCTURE

# Load environment variables from .env file
load_dotenv()

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "2223"))

# Configure valid credentials
VALID_USERNAME = os.getenv("SSH_USERNAME", "shophub")
VALID_PASSWORD = os.getenv("SSH_PASSWORD", "ShopHub121!")

controller = Controller(persona="shophub-production-server")


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
        print(f"[honeypot][{self.session_id}] connection established")
        try:
            # Send ShopHub banner (ensure string)
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
            # Write banner and then prompt. Use str(...) to be robust.
            self._chan.write(str(banner))
            # tiny newline to reduce chance of prompt-appending artifacts
            self._chan.write("\r\n")
            self._write_prompt()
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error in connection_made: {e}")

    def _write_prompt(self):
        """Write a realistic shell prompt"""
        if self._chan and not self._closed:
            try:
                # Color codes for realistic prompt
                prompt = f"\033[32m{self.username}@{self.hostname}\033[0m:\033[34m{self.current_dir}\033[0m$ "
                self._chan.write(str(prompt))
            except Exception as e:
                print(f"[honeypot][{self.session_id}] error in _write_prompt: {e}")

    def _normalize_path(self, path: str) -> str:
        """Normalize a path relative to current directory"""
        if path.startswith("/"):
            # Absolute path - check if it's valid
            if path == "/":
                return "/"
            # For simplicity, treat /home/shophub as ~
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
            # Relative path
            if self.current_dir == "~":
                return f"~/{path}"
            elif self.current_dir.endswith("/"):
                return f"{self.current_dir}{path}"
            else:
                return f"{self.current_dir}/{path}"

    def _get_parent_dir(self, path: str) -> str:
        """Get parent directory of given path"""
        if path == "~" or path == "/" or path == "/home/shophub":
            return "~"

        # Remove trailing slash
        path = path.rstrip("/")

        # Handle ~/ prefix
        if path.startswith("~/"):
            parts = path[2:].split("/")
            if len(parts) <= 1:
                return "~"
            return "~/" + "/".join(parts[:-1])

        # Handle absolute paths
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
        # asyncssh in text mode will send strings; keep accumulating them
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

            # Handle exit commands
            if cmd.lower() in ("exit", "logout", "quit"):
                try:
                    self._chan.write("\nGoodbye from ShopHub!\n")
                    self._chan.exit(0)
                except Exception:
                    pass
                return

            # Handle empty input
            if cmd == "":
                try:
                    self._write_prompt()
                except Exception:
                    pass
                continue

            # Handle cd command locally for immediate feedback
            if cmd.startswith("cd ") or cmd == "cd":
                self._handle_cd_command(cmd)
                continue

            self.cmd_count += 1
            asyncio.create_task(self.handle_command(cmd))

    def _handle_cd_command(self, cmd: str):
        """Handle cd command with validation"""
        parts = cmd.split(maxsplit=1)

        if len(parts) == 1 or (len(parts) > 1 and parts[1] == "~"):
            # cd with no args or cd ~ goes to home
            self.current_dir = "~"
        elif len(parts) > 1 and parts[1] == "..":
            # cd .. goes up one directory
            self.current_dir = self._get_parent_dir(self.current_dir)
        elif len(parts) > 1 and parts[1] == ".":
            # cd . stays in current directory
            pass
        elif len(parts) > 1 and parts[1] == "/":
            # cd / goes to root (but we redirect to home for this app)
            self.current_dir = "~"
        else:
            # Check if target directory exists
            target_path = self._normalize_path(parts[1])
            if self._directory_exists(target_path):
                self.current_dir = target_path
            else:
                # Directory doesn't exist
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

        # Log directory change
        print(f"[honeypot][{self.session_id}] cd -> {self.current_dir}")

        # Write new prompt
        try:
            self._write_prompt()
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error writing prompt after cd: {e}")

    async def handle_command(self, cmd: str):
        """Handle commands asynchronously - pass everything to controller"""
        if self._closed or not self._chan:
            return

        event = {
            "session_id": self.session_id,
            "type": "command",
            "command": cmd,
            "current_dir": self.current_dir,
            "ts": datetime.now(timezone.utc).isoformat(),
            "cmd_count": self.cmd_count,
            "elapsed": time.time() - self.start_time,
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

        delay = float(action.get("delay", 0.0) or 0.0)
        if delay > 0:
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

        response_text = action.get("response", "")
        if not response_text:
            response_text = ""

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
        Try to unpack typical values (term, width, height) for logs.
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
            # be defensive; don't let logging break the session
            print(f"[honeypot][{self.session_id}] pty requested (could not parse args)")
        # Always accept PTY allocation for the honeypot
        return True

    def shell_requested(self):
        """Handle shell request from client"""
        print(f"[honeypot][{self.session_id}] shell requested")
        return True

    def connection_lost(self, exc):
        """Called when SSH connection is lost"""
        self._closed = True
        duration = time.time() - self.start_time
        print(f"[honeypot][{self.session_id}] connection closed after {duration:.2f}s")

        # End session in controller
        try:
            controller.end_session(self.session_id)
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error ending session: {e}")

        if exc:
            print(f"[honeypot][{self.session_id}] connection error: {exc}")


class HoneypotServer(asyncssh.SSHServer):
    """Custom SSH server class that creates sessions"""

    def connection_made(self, conn):
        self.conn_id = str(uuid.uuid4())[:8]
        print(
            f"[honeypot][{self.conn_id}] new SSH connection established from {conn.get_extra_info('peername')}"
        )

    def connection_lost(self, exc):
        if exc:
            print(f"[honeypot][{self.conn_id}] connection error: {exc}")
        else:
            print(f"[honeypot][{self.conn_id}] connection closed cleanly")

    def begin_auth(self, username):
        """Begin authentication process"""
        print(
            f"[honeypot][{self.conn_id}] authentication attempt for user '{username}'"
        )
        # Return True to require authentication
        return True

    def password_auth_supported(self):
        """Enable password authentication"""
        return True

    def kbdint_auth_supported(self):
        """Disable keyboard-interactive authentication"""
        return False

    def public_key_auth_supported(self):
        """Disable public key authentication"""
        return False

    def validate_password(self, username, password):
        """Validate password against configured credentials"""
        print(f"[honeypot][{self.conn_id}] login attempt: {username}:{password}")

        # Check if username and password match
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
        """When SSH client requests a session"""
        session_id = str(uuid.uuid4())[:8]
        return HoneypotSession(session_id)


def ensure_host_key(path="ssh_host_key"):
    """Create a RSA host key file if it doesn't exist (helps first-run)."""
    if os.path.exists(path):
        return
    try:
        print("[honeypot] generating ssh host key...")
        key = asyncssh.generate_private_key("ssh-rsa")
        with open(path, "wb") as f:
            f.write(key.export_private_key())
        # write public key too
        pub = key.export_public_key()
        with open(path + ".pub", "wb") as f:
            f.write(pub)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Ignore on Windows
        print("[honeypot] ssh host key generated")
    except Exception as e:
        print(f"[honeypot] failed to generate host key: {e}")


async def start_server():
    """Start the honeypot SSH server"""
    print(f"[honeypot] starting SSH honeypot on {HOST}:{PORT} ...")
    print(f"[honeypot] valid credentials: {VALID_USERNAME}:{VALID_PASSWORD}")

    ensure_host_key("ssh_host_key")

    # Start controller background tasks after event loop is ready
    try:
        await controller.start_background_tasks()
    except Exception as e:
        print(f"[honeypot] warning: background tasks failed to start: {e}")

    try:
        await asyncssh.create_server(
            HoneypotServer,
            HOST,
            PORT,
            server_host_keys=["ssh_host_key"],
        )
        print(f"[honeypot] ✅ listening on {HOST}:{PORT}")

        # Run forever
        await asyncio.Future()

    except (OSError, asyncssh.Error) as exc:
        print(f"[honeypot] server failed to start: {exc}")
    finally:
        # Clean shutdown
        try:
            await controller.stop_background_tasks()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except (KeyboardInterrupt, SystemExit):
        print("\n[honeypot] shutting down gracefully...")
