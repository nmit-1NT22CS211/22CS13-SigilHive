#!/usr/bin/env python3
"""
Complete SSH Honeypot Fix - Kills old process and starts new server
"""

import subprocess
import sys
import time
import socket
import threading
import paramiko
from colorama import init, Fore

init(autoreset=True)

PORT = 5555
HOST = "0.0.0.0"
VALID_USERNAME = "shophub"
VALID_PASSWORD = "ShopHub121!"


def kill_process_on_port(port):
    """Kill any process using the specified port on Windows"""
    print(f"{Fore.CYAN}[*] Checking for processes on port {port}...")

    try:
        # Find processes using the port
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, shell=True
        )

        pids = set()
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        pids.add(pid)
                    except ValueError:
                        continue

        if not pids:
            print(f"{Fore.GREEN}[✓] Port {port} is free")
            return True

        print(f"{Fore.YELLOW}[!] Found {len(pids)} process(es) using port {port}")

        # Kill each process
        for pid in pids:
            print(f"{Fore.CYAN}[*] Killing PID {pid}...")
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)], capture_output=True, shell=True
            )

        time.sleep(1)
        print(f"{Fore.GREEN}[✓] Processes killed")
        return True

    except Exception as e:
        print(f"{Fore.RED}[✗] Error: {e}")
        return False


class HoneypotSSHServer(paramiko.ServerInterface):
    """Minimal SSH Server for Honeypot"""

    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            print(f"{Fore.GREEN}[AUTH] ✓ Login: {username}")
            return paramiko.AUTH_SUCCESSFUL
        print(f"{Fore.RED}[AUTH] ✗ Failed: {username}")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ):
        return True


def handle_client(client_socket, client_address):
    """Handle SSH client connection"""
    print(f"\n{Fore.CYAN}[CONN] {client_address[0]}:{client_address[1]}")

    try:
        transport = paramiko.Transport(client_socket)
        transport.set_gss_host(socket.getfqdn(""))

        # Generate server key
        host_key = paramiko.RSAKey.generate(2048)
        transport.add_server_key(host_key)

        server = HoneypotSSHServer()
        transport.start_server(server=server)

        channel = transport.accept(20)
        if channel is None:
            return

        # Send banner
        channel.send("\r\nWelcome to ShopHub Server\r\n")
        channel.send("shophub@shophub-server:~$ ")

        server.event.wait(10)
        if not server.event.is_set():
            channel.close()
            return

        # Command loop
        cmd_buffer = ""

        while True:
            if channel.recv_ready():
                data = channel.recv(1024)
                if not data:
                    break

                char = data.decode("utf-8", errors="ignore")

                if char in ["\r", "\n"]:
                    cmd = cmd_buffer.strip()
                    if cmd:
                        print(f"{Fore.YELLOW}[CMD] {cmd}")

                        # Basic command responses
                        if cmd in ["exit", "logout"]:
                            channel.send("\r\nLogout\r\n")
                            break
                        elif cmd == "whoami":
                            channel.send(f"\r\n{VALID_USERNAME}\r\n")
                        elif cmd == "pwd":
                            channel.send(f"\r\n/home/{VALID_USERNAME}\r\n")
                        elif cmd == "hostname":
                            channel.send(f"\r\n{VALID_USERNAME}-server\r\n")
                        elif cmd == "id":
                            channel.send(
                                f"\r\nuid=1000({VALID_USERNAME}) gid=1000({VALID_USERNAME}) groups=1000({VALID_USERNAME})\r\n"
                            )
                        elif cmd == "uname -a":
                            channel.send(
                                f"\r\nLinux {VALID_USERNAME}-server 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux\r\n"
                            )
                        elif cmd.startswith("echo"):
                            text = cmd[4:].strip().strip('"').strip("'")
                            channel.send(f"\r\n{text}\r\n")
                        elif cmd == "ls":
                            channel.send(
                                "\r\n.bashrc  .bash_history  .env  .ssh  shophub\r\n"
                            )
                        elif cmd == "ls -la":
                            channel.send("\r\ntotal 32\r\n")
                            channel.send(
                                "drwxr-xr-x  5 shophub shophub 4096 Nov 18 10:00 .\r\n"
                            )
                            channel.send(
                                "drwxr-xr-x  3 root    root    4096 Nov 18 10:00 ..\r\n"
                            )
                            channel.send(
                                "-rw-r--r--  1 shophub shophub  220 Nov 18 10:00 .bashrc\r\n"
                            )
                            channel.send(
                                "-rw-------  1 shophub shophub  500 Nov 18 10:00 .bash_history\r\n"
                            )
                            channel.send(
                                "-rw-r--r--  1 shophub shophub  807 Nov 18 10:00 .env\r\n"
                            )
                            channel.send(
                                "drwx------  2 shophub shophub 4096 Nov 18 10:00 .ssh\r\n"
                            )
                            channel.send(
                                "drwxr-xr-x  8 shophub shophub 4096 Nov 18 10:00 shophub\r\n"
                            )
                        elif cmd == "cat .env":
                            channel.send("\r\nDB_HOST=localhost\r\n")
                            channel.send("DB_PORT=5432\r\n")
                            channel.send("DB_USER=shophub_admin\r\n")
                            channel.send("REDIS_URL=redis://localhost:6379\r\n")
                            channel.send("NODE_ENV=production\r\n")
                        elif cmd == "cat .bashrc":
                            channel.send("\r\n# .bashrc\r\n")
                            channel.send("alias ll='ls -la'\r\n")
                            channel.send("export PS1='\\u@\\h:\\w\\$ '\r\n")
                        elif cmd == "cat .bash_history":
                            channel.send("\r\nls -la\r\n")
                            channel.send("cd shophub\r\n")
                            channel.send("npm start\r\n")
                        elif cmd == "env":
                            channel.send("\r\nUSER=shophub\r\n")
                            channel.send("HOME=/home/shophub\r\n")
                            channel.send("PATH=/usr/local/bin:/usr/bin:/bin\r\n")
                            channel.send("SHELL=/bin/bash\r\n")
                        elif cmd == "history":
                            channel.send("\r\n  1  ls -la\r\n")
                            channel.send("  2  cd shophub\r\n")
                            channel.send("  3  cat .env\r\n")
                        elif cmd == "clear":
                            channel.send("\033[2J\033[H")
                        elif cmd.startswith("cd"):
                            # Just acknowledge cd commands
                            pass
                        elif cmd.startswith("cat"):
                            parts = cmd.split(maxsplit=1)
                            if len(parts) > 1:
                                channel.send(
                                    f"\r\ncat: {parts[1]}: No such file or directory\r\n"
                                )
                            else:
                                channel.send("\r\ncat: missing operand\r\n")
                        elif cmd.startswith("ps"):
                            channel.send("\r\nUSER       PID  %CPU %MEM COMMAND\r\n")
                            channel.send(f"shophub   1234  0.5  2.1 node app.js\r\n")
                            channel.send(f"shophub   1235  0.0  0.5 /bin/bash\r\n")
                        elif cmd.startswith("grep") or cmd.startswith("find"):
                            # Simulate search with no results
                            time.sleep(0.5)
                        else:
                            channel.send(f"\r\n{cmd}: command not found\r\n")

                    channel.send(f"shophub@shophub-server:~$ ")
                    cmd_buffer = ""

                elif char in ["\x7f", "\x08"]:  # Backspace
                    if cmd_buffer:
                        cmd_buffer = cmd_buffer[:-1]
                        channel.send("\b \b")

                else:
                    cmd_buffer += char
                    channel.send(char)

        print(f"{Fore.CYAN}[DISC] Client disconnected")

    except Exception as e:
        print(f"{Fore.RED}[ERROR] {e}")

    finally:
        try:
            transport.close()
        except:
            pass


def start_honeypot():
    """Start the SSH honeypot server"""
    print(f"{Fore.CYAN}{'=' * 70}")
    print(f"{Fore.CYAN}SSH HONEYPOT SERVER")
    print(f"{Fore.CYAN}{'=' * 70}\n")

    # Kill any existing process on the port
    if not kill_process_on_port(PORT):
        print(f"{Fore.RED}[✗] Failed to free port {PORT}")
        return

    print(f"\n{Fore.CYAN}Starting server on {HOST}:{PORT}")
    print(f"Username: {VALID_USERNAME}")
    print(f"Password: {VALID_PASSWORD}")
    print(f"\n{Fore.GREEN}[READY] Server is running! Press Ctrl+C to stop.\n")

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(100)

        while True:
            client_socket, client_address = server_socket.accept()
            thread = threading.Thread(
                target=handle_client, args=(client_socket, client_address), daemon=True
            )
            thread.start()

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}[STOP] Server stopped")

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR] {e}")

    finally:
        try:
            server_socket.close()
        except:
            pass


if __name__ == "__main__":
    start_honeypot()
