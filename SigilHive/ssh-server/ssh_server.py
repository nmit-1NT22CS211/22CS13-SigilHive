# ssh_server.py
# Minimal asyncssh-based honeypot server that awaits async controller responses (LLM-driven).
import asyncio
import asyncssh
import os
import time
import uuid
from datetime import datetime, timezone
from controller import Controller

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "2222"))

# Instantiate the async controller (uses llm_gen internally)
controller = Controller(persona="ubuntu-22.04")


class HoneypotSession(asyncssh.SSHServerSession):
    def __init__(self, session_id):
        super().__init__()
        self._chan = None
        self.session_id = session_id
        self._input = ""
        self.start_time = time.time()
        self.cmd_count = 0
        self._closed = False
        self.current_dir = "~"  # Track current directory

    def connection_made(self, chan):
        # channel object set by asyncssh when session starts
        self._chan = chan
        print(f"[honeypot][{self.session_id}] connection_made called")
        # Send initial banner and prompt
        try:
            self._chan.write("Welcome to Ubuntu 22.04 LTS\n")
            self._write_prompt()
            print(f"[honeypot][{self.session_id}] banner and prompt sent")
        except Exception as e:
            print(f"[honeypot][{self.session_id}] error in connection_made: {e}")
            import traceback

            traceback.print_exc()

    def _write_prompt(self):
        """Write the shell prompt based on current directory"""
        if self._chan and not self._closed:
            try:
                prompt = f"user@honeypot:{self.current_dir}$ "
                self._chan.write(prompt)
            except Exception as e:
                print(f"[honeypot][{self.session_id}] error in _write_prompt: {e}")

    def data_received(self, data, datatype):
        """
        Called by asyncssh when data arrives. This method must not be async, so we
        schedule the async handler with asyncio.create_task.
        """
        self._input += data
        # Process full lines (commands) terminated by newline or carriage return
        while "\n" in self._input or "\r" in self._input:
            # Handle both \n and \r\n
            if "\r\n" in self._input:
                line, self._input = self._input.split("\r\n", 1)
            elif "\n" in self._input:
                line, self._input = self._input.split("\n", 1)
            elif "\r" in self._input:
                line, self._input = self._input.split("\r", 1)
            else:
                break

            cmd = line.strip()
            # Handle exit/logout commands
            if cmd.lower() in ("exit", "logout", "quit"):
                try:
                    self._chan.write("\nGoodbye!\n")
                    self._chan.exit(0)
                except Exception:
                    pass
                return

            # ignore empty lines but show prompt
            if cmd == "":
                try:
                    self._write_prompt()
                except Exception:
                    pass
                continue

            # Handle cd command specially to update directory state
            if cmd.startswith("cd ") or cmd == "cd":
                self._handle_cd_command(cmd)
                continue

            self.cmd_count += 1
            # schedule an async handler so event loop remains responsive
            asyncio.create_task(self.handle_command(cmd))

    def _handle_cd_command(self, cmd: str):
        """Handle cd command to update current directory"""
        parts = cmd.split(maxsplit=1)

        if len(parts) == 1 or (len(parts) > 1 and parts[1] == "~"):
            # cd with no args or cd ~ goes to home
            self.current_dir = "~"
        elif len(parts) > 1 and parts[1] == "..":
            # cd .. goes up one directory
            if self.current_dir == "~" or self.current_dir == "/":
                # Already at home or root, stay there
                pass
            elif self.current_dir.startswith("~/"):
                # Handle ~/something format
                parts_dir = self.current_dir[2:].split("/")  # Remove ~/ prefix
                if len(parts_dir) == 1:
                    # Only one level deep (e.g., ~/Desktop), go back to ~
                    self.current_dir = "~"
                else:
                    # Multiple levels, go up one
                    self.current_dir = "~/" + "/".join(parts_dir[:-1])
            elif "/" in self.current_dir:
                # Absolute path
                parts_dir = self.current_dir.split("/")
                if len(parts_dir) <= 2:
                    # At root level
                    self.current_dir = "/"
                else:
                    self.current_dir = "/".join(parts_dir[:-1])
            else:
                # Shouldn't happen, but go to home as fallback
                self.current_dir = "~"
        elif len(parts) > 1 and parts[1] == "/":
            # cd / goes to root
            self.current_dir = "/"
        elif len(parts) > 1 and parts[1].startswith("/"):
            # Absolute path
            self.current_dir = parts[1]
        elif len(parts) > 1:
            # Relative path - append to current dir
            if self.current_dir == "~":
                self.current_dir = f"~/{parts[1]}"
            elif self.current_dir == "/":
                self.current_dir = f"/{parts[1]}"
            else:
                self.current_dir = f"{self.current_dir}/{parts[1]}"

        # Log the directory change
        print(f"[honeypot][{self.session_id}] cd: {self.current_dir}")

    async def handle_command(self, cmd: str):
        """
        Async handler that:
        - builds an event
        - awaits controller.get_action_for_session(...) which returns LLM-generated response
        - sleeps for the returned delay (to simulate system behavior)
        - writes the response to the SSH channel
        """
        if self._closed or not self._chan:
            return

        event = {
            "session_id": self.session_id,
            "type": "command",
            "command": cmd,
            "ts": datetime.now(timezone.utc).isoformat(),
            "cmd_count": self.cmd_count,
            "elapsed": time.time() - self.start_time,
        }

        try:
            # Ask controller for an action (this is async and may call LLM)
            action = await controller.get_action_for_session(self.session_id, event)
        except Exception as e:
            # If LLM/controller fails, return a safe fallback message
            print(f"[honeypot][{self.session_id}] controller error: {e}")
            action = {"response": f"bash: {cmd}: command not found", "delay": 0.05}

        # Insert a small delay if controller requested it
        delay = float(action.get("delay", 0.0) or 0.0)
        try:
            if delay > 0:
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        response_text = action.get("response", "")
        if response_text is None:
            response_text = ""

        # Write response safely to the channel
        try:
            # Write the response
            if response_text:
                self._chan.write(response_text)
                if not response_text.endswith("\n"):
                    self._chan.write("\n")
            # Show prompt again with current directory
            self._write_prompt()
        except (BrokenPipeError, EOFError, asyncssh.Error) as e:
            print(f"[honeypot][{self.session_id}] write error (channel closed): {e}")
            self._closed = True

    def eof_received(self):
        print(f"[honeypot][{self.session_id}] EOF received")
        return True

    def break_received(self, msec):
        # Handle Ctrl+C
        print(f"[honeypot][{self.session_id}] break received")
        return True

    def signal_received(self, signal):
        # Handle signals
        print(f"[honeypot][{self.session_id}] signal received: {signal}")
        pass

    def session_started(self):
        # Called when session is fully established
        print(f"[honeypot][{self.session_id}] session_started called")
        pass

    def terminal_size_changed(self, width, height, pixwidth, pixheight):
        # Handle terminal resize
        print(f"[honeypot][{self.session_id}] terminal size: {width}x{height}")
        pass

    def pty_requested(self, term_type, term_size, term_modes):
        # Accept PTY (pseudo-terminal) requests
        print(f"[honeypot][{self.session_id}] PTY requested: {term_type}")
        return True

    def shell_requested(self):
        # This must return True to accept shell requests
        print(f"[honeypot][{self.session_id}] shell_requested - accepting")
        return True

    def connection_lost(self, exc):
        print(f"[honeypot][{self.session_id}] connection_lost: {exc}")
        self._closed = True


class HoneypotServer(asyncssh.SSHServer):
    def connection_made(self, conn):
        peer = conn.get_extra_info("peername")
        print(f"[honeypot] connection from {peer}")
        self._conn = conn

    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        print(f"[honeypot] auth attempt user={username}, pass={password}")
        return True

    def session_requested(self):
        session_id = str(uuid.uuid4())
        print(f"[honeypot] session requested: {session_id}")
        return HoneypotSession(session_id)


def session_factory():
    """Factory function that creates new session instances"""
    session_id = str(uuid.uuid4())
    print(f"[honeypot] creating session: {session_id}")
    return HoneypotSession(session_id)


async def start_server():
    host_key_file = "ssh_host_key"
    if not os.path.exists(host_key_file):
        print("[honeypot] generating host key...")
        try:
            key = asyncssh.generate_private_key("ssh-rsa", key_size=2048)
            key.write_private_key(host_key_file)
            os.chmod(host_key_file, 0o600)
        except Exception as e:
            print(f"[honeypot] key generation error: {e}")
            import subprocess

            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "rsa",
                    "-b",
                    "2048",
                    "-f",
                    host_key_file,
                    "-N",
                    "",
                ],
                check=True,
            )

    try:
        await asyncssh.create_server(
            HoneypotServer,
            HOST,
            PORT,
            server_host_keys=[host_key_file],
            allow_scp=False,
            sftp_factory=None,
        )
        print(f"[honeypot] SSH listening on {HOST}:{PORT}")
        await asyncio.Future()
    except Exception as exc:
        print(f"[honeypot] error starting server: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\n[honeypot] exiting on user interrupt")
    except Exception as e:
        print(f"[honeypot] runtime error: {e}")
