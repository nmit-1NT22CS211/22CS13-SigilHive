import os
import numpy as np
import time
import random
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from llm_gen import generate_response_for_command_async
from kafka_manager import HoneypotKafkaManager
from file_structure import SHOPHUB_STRUCTURE, FILE_CONTENTS
from rl_core.q_learning_agent import shared_rl_agent
from rl_core.state_extractor import extract_state
from rl_core.reward_calculator import calculate_reward
from rl_core.logging.structured_logger import log_interaction


class Controller:
    def __init__(self, persona: str = "shophub-server"):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.persona = persona
        self.kafka_manager = HoneypotKafkaManager()
        self.file_structure = SHOPHUB_STRUCTURE
        self.file_contents = FILE_CONTENTS

        self.rl_agent = shared_rl_agent
        self.rl_enabled = os.getenv("RL_ENABLED", "true").lower() == "true"
        print(f"[Controller] ✅ Controller initialized (RL enabled: {self.rl_enabled})")

    def _update_meta(self, session_id: str, event: Dict[str, Any]):
        meta = self.sessions.setdefault(
            session_id,
            {
                "cmd_count": 0,
                "elapsed": 0.0,
                "last_cmd": "",
                "current_dir": "~",
                "command_history": [],
            },
        )
        meta["cmd_count"] = event.get("cmd_count", meta["cmd_count"])
        meta["elapsed"] = event.get("elapsed", meta["elapsed"])

        if "command" in event:
            cmd = event.get("command", meta["last_cmd"])
            meta["last_cmd"] = cmd
            meta["command_history"].append(cmd)

            if len(meta["command_history"]) > 50:
                meta["command_history"] = meta["command_history"][-50:]

        if "current_dir" in event:
            meta["current_dir"] = event.get("current_dir", meta["current_dir"])

        meta["last_ts"] = time.time()
        self.sessions[session_id] = meta
        return meta

    def get_directory_context(self, current_dir: str) -> Dict[str, Any]:
        """Get context about the current directory"""
        normalized_dir = current_dir.strip()

        if normalized_dir.endswith("/") and normalized_dir != "/":
            normalized_dir = normalized_dir[:-1]

        if normalized_dir == "~" or normalized_dir == "":
            normalized_dir = "~"

        if normalized_dir in self.file_structure:
            return self.file_structure[normalized_dir]

        if not normalized_dir.startswith("~") and normalized_dir.startswith("/"):
            pass
        elif not normalized_dir.startswith("~"):
            maybe = f"~/{normalized_dir}"
            if maybe in self.file_structure:
                return self.file_structure[maybe]

        return {
            "type": "directory",
            "description": f"Directory: {current_dir}",
            "contents": [],
        }

    def classify_command(self, cmd: str) -> str:
        cmd = (cmd or "").strip()
        if cmd == "":
            return "noop"

        cmd_parts = cmd.split()
        base_cmd = cmd_parts[0] if cmd_parts else ""

        if base_cmd in ("clear", "reset"):
            return "clear_screen"
        if base_cmd == "history":
            return "show_history"
        if base_cmd == "echo":
            return "echo"
        if base_cmd == "env" or base_cmd == "printenv":
            return "show_env"
        if base_cmd in ("cat", "less", "more"):
            if len(cmd_parts) < 2:
                return "read_file_no_arg"
            return "read_file"
        if base_cmd in ("ls", "dir", "ll"):
            return "list_dir"
        if base_cmd in ("whoami", "id"):
            return "identity"
        if base_cmd in ("uname", "hostname"):
            return "system_info"
        if base_cmd in ("ps", "top", "htop"):
            return "process_list"
        if base_cmd in ("netstat", "ss"):
            return "netstat"
        if base_cmd == "ping":
            return "network_probe"
        if base_cmd in ("curl", "wget"):
            return "http_fetch"
        if base_cmd == "pwd":
            return "print_dir"
        if base_cmd in ("find", "locate"):
            return "search"
        if base_cmd in ("grep", "egrep"):
            if len(cmd_parts) < 2:
                return "grep_no_arg"
            return "grep"
        if base_cmd in ("tail", "head"):
            return "file_peek"
        if base_cmd == "df":
            return "disk_usage"
        if base_cmd == "free":
            return "memory_info"
        if base_cmd in ("docker", "docker-compose"):
            return "docker"
        if base_cmd in ("npm", "node"):
            return "nodejs"
        if base_cmd == "git":
            return "git"
        if base_cmd.startswith("sudo"):
            return "privilege_escalation"
        if base_cmd == "ssh":
            return "remote_ssh"
        return "unknown"

    def _file_exists_in_directory(self, current_dir: str, filename: str) -> bool:
        """Check if a file exists in the directory structure"""
        dir_context = self.get_directory_context(current_dir)
        contents = dir_context.get("contents", [])

        filename_lower = filename.lower()
        for item in contents:
            if item.lower() == filename_lower:
                return True
        return False

    def _find_file_case_insensitive(
        self, current_dir: str, filename: str
    ) -> Optional[str]:
        """Find a file in FILE_CONTENTS with case-insensitive matching"""
        if filename.startswith("~"):
            full_path = filename
        elif filename.startswith("/"):
            full_path = filename
        else:
            if current_dir.endswith("/"):
                full_path = f"{current_dir}{filename}"
            else:
                full_path = f"{current_dir}/{filename}"

        full_path = full_path.replace("//", "/")

        if full_path in self.file_contents:
            return full_path

        full_path_lower = full_path.lower()
        for key in self.file_contents.keys():
            if key.lower() == full_path_lower:
                return key

        return None

    async def _finalize(
        self,
        session_id: str,
        cmd: str,
        intent: str,
        current_dir: str,
        response: str,
        delay: float,
    ):
        try:
            payload = {
                "session_id": session_id,
                "command": cmd,
                "intent": intent,
                "current_dir": current_dir,
                "response": response,
                "delay": delay,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.kafka_manager.send(topic="SSHtoHTTP", value=payload)
            self.kafka_manager.send(topic="SSHtoDB", value=payload)
            self.kafka_manager.send_dashboard(
                topic="honeypot-logs",
                value=payload,
                service="ssh",
                event_type=intent,
            )

        except Exception as e:
            print(f"[Controller] Kafka send error: {e}")

        return {"response": response, "delay": delay}

    async def _original_command_handler(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        command_history = meta.get("command_history", [])
        intent = self.classify_command(cmd)

        dir_context = self.get_directory_context(current_dir)

        # --- print_dir ---
        if intent == "print_dir":
            response_text = current_dir
            return await self._finalize(
                session_id, cmd, intent, current_dir, response_text, 0.01
            )

        # --- clear_screen ---
        if intent == "clear_screen":
            response_text = "\033[2J\033[H"
            return await self._finalize(
                session_id, cmd, intent, current_dir, response_text, 0.01
            )

        # --- show_history ---
        if intent == "show_history":
            lines = [f"  {i}  {c}" for i, c in enumerate(command_history[-50:], 1)]
            response_text = "\n".join(lines)
            return await self._finalize(
                session_id, cmd, intent, current_dir, response_text, 0.01
            )

        # --- echo ---
        if intent == "echo":
            parts = cmd.split(maxsplit=1)
            response_text = parts[1] if len(parts) > 1 else ""
            return await self._finalize(
                session_id, cmd, intent, current_dir, response_text, 0.01
            )

        # --- env ---
        if intent == "show_env":
            env_vars = {
                "USER": "shophub",
                "HOME": "/home/shophub",
                "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
                "SHELL": "/bin/bash",
                "PWD": current_dir.replace("~", "/home/shophub"),
                "LANG": "en_US.UTF-8",
                "NODE_ENV": "production",
                "PORT": "3000",
            }
            response_text = "\n".join(f"{k}={v}" for k, v in env_vars.items())
            return await self._finalize(
                session_id, cmd, intent, current_dir, response_text, 0.01
            )

        # --- missing args ---
        if intent == "read_file_no_arg":
            msg = f"{cmd.split()[0]}: missing operand\nTry '{cmd.split()[0]} --help' for more information."
            return await self._finalize(session_id, cmd, intent, current_dir, msg, 0.01)

        if intent == "grep_no_arg":
            msg = "grep: missing pattern\nUsage: grep [OPTION]... PATTERN [FILE]..."
            return await self._finalize(session_id, cmd, intent, current_dir, msg, 0.01)

        # --- read_file ---
        filename_hint = None
        if intent == "read_file":
            parts = cmd.split()
            file_parts = [p for p in parts[1:] if not p.startswith("-")]
            if file_parts:
                filename_hint = file_parts[0]

                matched_path = self._find_file_case_insensitive(
                    current_dir, filename_hint
                )
                if matched_path:
                    content = self.file_contents[matched_path]
                    return await self._finalize(
                        session_id, cmd, intent, current_dir, content, 0.05
                    )

                msg = f"cat: {filename_hint}: No such file or directory"
                return await self._finalize(
                    session_id, cmd, intent, current_dir, msg, 0.02
                )

        # --- simulated responses ---
        try:
            if intent == "list_dir":
                response_text = self._simulate_list_dir(dir_context, cmd)
                delay = 0.02 + random.random() * 0.15
                return await self._finalize(
                    session_id, cmd, intent, current_dir, response_text, delay
                )

            if intent == "identity":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_identity(),
                    0.01,
                )

            if intent == "system_info":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_system_info(cmd),
                    0.02,
                )

            if intent == "process_list":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_process_list(),
                    0.03,
                )

            if intent == "network_probe":
                return await self._finalize(
                    session_id, cmd, intent, current_dir, self._simulate_ping(cmd), 0.05
                )

            if intent == "http_fetch":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_http_fetch(cmd),
                    0.05,
                )

            if intent == "docker":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_docker(cmd),
                    0.04,
                )

            if intent == "git":
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    self._simulate_git(cmd, dir_context),
                    0.03,
                )

        except Exception as e:
            print(f"[Controller] Simulation error: {e}")

        # --- LLM fallback ---
        context = {
            "current_directory": current_dir,
            "directory_description": dir_context.get("description", ""),
            "directory_contents": dir_context.get("contents", []),
            "application": "ShopHub E-commerce Platform",
            "application_tech": "Node.js, Express, MongoDB, Redis, Docker",
        }

        try:
            response_text = await generate_response_for_command_async(
                command=cmd,
                filename_hint=filename_hint,
                persona=self.persona,
                context=context,
            )
        except Exception:
            response_text = (
                f"bash: {cmd.split()[0] if cmd else 'unknown'}: command not found"
            )

        delay = 0.05 + float(np.random.rand()) * 0.2
        return await self._finalize(
            session_id, cmd, intent, current_dir, response_text, delay
        )

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """RL-enhanced command handler - wraps original logic"""

        # Update session metadata first
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")

        # 1. Log interaction for RL
        log_interaction(
            session_id=session_id,
            protocol="ssh",
            input_data=cmd,
            metadata={
                "intent": self.classify_command(cmd),
                "current_dir": current_dir,
                "cmd_count": meta.get("cmd_count", 0),
            },
        )

        # 2. Extract current state
        state = extract_state(session_id, protocol="ssh")

        # 3. Select and execute action
        rl_action = None
        if self.rl_enabled and self.classify_command(cmd) in ["list_dir", "cat_file", "show_env"]:
            # For read commands, always use realistic response (no RL)
            response = await self._original_command_handler(session_id, event)
        elif self.rl_enabled:
            rl_action = self.rl_agent.select_action(state)
            response = await self._execute_rl_action(rl_action, session_id, event)
        else:
            response = await self._original_command_handler(session_id, event)

        # 4. Update Q-table (only if RL action was taken)
        if self.rl_enabled and rl_action is not None:
            next_state = extract_state(session_id, protocol="ssh")
            reward = calculate_reward(state, next_state, protocol="ssh")
            self.rl_agent.update(state, rl_action, reward, next_state)

        return response

    def end_session(self, session_id: str):
        """End a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    # Simulation helper methods
    def _simulate_list_dir(self, dir_context: Dict[str, Any], cmd: str) -> str:
        contents = dir_context.get("contents", [])
        if not contents:
            return ""

        show_hidden = "-a" in cmd or "-la" in cmd or "-al" in cmd
        lines = []

        if show_hidden:
            lines.append("drwxr-xr-x  2 shophub shophub 4096 .")
            lines.append("drwxr-xr-x  2 shophub shophub 4096 ..")

        for name in contents:
            if name.endswith("/"):
                lines.append(f"drwxr-xr-x  2 shophub shophub 4096 {name}")
            elif "." in name:
                lines.append(
                    f"-rw-r--r--  1 shophub shophub {random.randint(20, 4000)} {name}"
                )
            else:
                lines.append(f"drwxr-xr-x  2 shophub shophub 4096 {name}")
        return "\n".join(lines)

    def _simulate_identity(self) -> str:
        return "shophub"

    def _simulate_system_info(self, cmd: str) -> str:
        if cmd.startswith("uname"):
            return "Linux shophub-server 5.15.0-100-generic #1 SMP Thu Jan 1 00:00:00 UTC 2025 x86_64 GNU/Linux"
        if cmd.startswith("hostname"):
            return "shophub-server"
        return "Unknown system info query"

    def _simulate_process_list(self) -> str:
        sample = [
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND",
            "root         1  0.0  0.1 169084  6044 ?        Ss   09:30   0:01 /sbin/init",
            "shophub   1023  0.3  1.2 238564 25432 ?        Sl   09:31   0:12 node /home/shophub/shophub/app/app.js",
            "redis     2048  0.1  0.8  84900 16844 ?        Ssl  09:31   0:03 redis-server *:6379",
            "mongodb   3120  1.2  2.5 452128 51200 ?        Ssl  09:31   0:45 /usr/bin/mongod --config /etc/mongod.conf",
        ]
        return "\n".join(sample)

    def _simulate_ping(self, cmd: str) -> str:
        parts = cmd.split()
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        rtts = [round(random.uniform(0.3, 3.0), 3) for _ in range(4)]
        lines = [f"PING {target} ({target}): 56 data bytes"]
        for i, r in enumerate(rtts, 1):
            lines.append(f"64 bytes from {target}: icmp_seq={i} ttl=64 time={r} ms")
        avg = round(sum(rtts) / len(rtts), 3)
        lines.append("")
        lines.append(f"--- {target} ping statistics ---")
        lines.append("4 packets transmitted, 4 packets received, 0.0% packet loss")
        lines.append(f"round-trip min/avg/max = {min(rtts)}/{avg}/{max(rtts)} ms")
        return "\n".join(lines)

    def _simulate_http_fetch(self, cmd: str) -> str:
        if "http" in cmd:
            return "HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\n\n<html><head><title>ShopHub</title></head><body><h1>ShopHub</h1></body></html>"
        return "wget: missing URL"

    def _simulate_docker(self, cmd: str) -> str:
        if "ps" in cmd or "container ls" in cmd:
            return (
                "CONTAINER ID   IMAGE          COMMAND                  CREATED        STATUS        PORTS                    NAMES\n"
                'a1b2c3d4e5f6   shophub:latest  "node /app/app.js"      2 hours ago    Up 2 hours    0.0.0.0:3000->3000/tcp   shophub_app\n'
                'd7e8f9a0b1c2   mongo:6.0       "docker-entrypoint.s…" 3 hours ago    Up 3 hours    27017/tcp                shophub_mongo\n'
            )
        if "images" in cmd:
            return "REPOSITORY   TAG       IMAGE ID       CREATED       SIZE\nshophub       latest    abcdef012345   2 hours ago   200MB\nmongo         6.0       123456abcdef   3 weeks ago   350MB"
        return "docker: unknown command or not implemented in honeypot simulation"

    def _simulate_git(self, cmd: str, dir_context: Dict[str, Any]) -> str:
        contents = dir_context.get("contents", [])
        if ".git" in contents:
            if cmd.strip() == "git status":
                return "On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean"
            return f"git: simulated output for '{cmd}'"
        return "fatal: not a git repository (or any of the parent directories): .git"

    async def _execute_rl_action(
        self, action: str, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute RL-selected action"""
        meta = self.sessions[session_id]
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        intent = self.classify_command(cmd)

        if action == "REALISTIC_RESPONSE":
            # Use existing logic
            return await self._original_command_handler(session_id, event)

        elif action == "DECEPTIVE_RESOURCE":
            # Return fake sensitive files with honeytokens
            cmd_lower = cmd.lower()

            # Fake /etc/passwd
            if "passwd" in cmd_lower and "etc" in cmd_lower:
                fake_passwd = """root:x:0:0:root:/root:/bin/bash
    daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
    shophub:x:1000:1000:ShopHub App:/home/shophub:/bin/bash
    admin:x:1001:1001:Admin User:/home/admin:/bin/bash
    dbbackup:x:1002:1002:Database Backup:/home/dbbackup:/bin/bash
    deploy:x:1003:1003:Deployment:/home/deploy:/bin/bash"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_passwd, 0.05
                )

            # Fake /etc/shadow
            if "shadow" in cmd_lower and "etc" in cmd_lower:
                fake_shadow = """root:$6$HONEYTOKEN_ROOT_001:19000:0:99999:7:::
    shophub:$6$HONEYTOKEN_APP_002:19000:0:99999:7:::
    admin:$6$HONEYTOKEN_ADMIN_003:19000:0:99999:7:::
    deploy:$6$HONEYTOKEN_DEPLOY_004:19000:0:99999:7:::"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_shadow, 0.05
                )

            # Fake .env file
            if ".env" in cmd_lower:
                fake_env = """# ShopHub Production Environment
    NODE_ENV=production
    PORT=3000

    # Database
    DB_HOST=prod-mysql.internal
    DB_USER=shophub_prod_HONEYTOKEN_001
    DB_PASS=Pr0dP@ssw0rd_HONEYTOKEN_DB_001
    DB_NAME=shophub_production

    # Redis
    REDIS_HOST=prod-redis.internal
    REDIS_PASS=R3d1sP@ss_HONEYTOKEN_002

    # AWS
    AWS_ACCESS_KEY_ID=AKIA_HONEYTOKEN_AWS_KEY_001
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG_HONEYTOKEN_AWS_SECRET

    # Stripe
    STRIPE_SECRET_KEY=sk_live_HONEYTOKEN_STRIPE_SECRET_KEY_001

    # JWT
    JWT_SECRET=jwt_super_secret_HONEYTOKEN_003"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_env, 0.05
                )

            # Fake SSH private key
            if "id_rsa" in cmd_lower or ("ssh" in cmd_lower and "key" in cmd_lower):
                fake_key = """-----BEGIN OPENSSH PRIVATE KEY-----
    b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcn
    NhAAAAAwEAAQAAAQEA0HONEYTOKEN_SSH_PRIVATE_KEY_DATA_001_FAKE_FOR_TRACKING
    AAAECAwQAAECAwQAAECAwQAAECAwQAAECAwQAAECAwQAAECAwQ=
    -----END OPENSSH PRIVATE KEY-----"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_key, 0.05
                )

            # Fake config files
            if "config" in cmd_lower and any(
                x in cmd_lower for x in ["db", "database", "mysql"]
            ):
                fake_config = """[client]
    host = prod-mysql.internal
    user = shophub_admin_HONEYTOKEN
    password = MyS3cr3t_HONEYTOKEN_005
    database = shophub_production

    [mysqldump]
    user = backup_user_HONEYTOKEN
    password = B@ckup_P@ss_HONEYTOKEN_006"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_config, 0.05
                )

            # Fallback to realistic if no match
            return await self._original_command_handler(session_id, event)

        elif action == "RESPONSE_DELAY":
            # Add delay then return realistic response
            response = await self._original_command_handler(session_id, event)
            response["delay"] = response.get("delay", 0.0) + random.uniform(0.5, 2.0)
            return response

        elif action == "MISLEADING_SUCCESS":
            # Fake successful privilege escalation
            if intent == "privilege_escalation":
                # Fake sudo success - return root prompt
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    "[sudo] password for shophub:\n# ",
                    0.1,
                )

            # Fake successful file operations
            if intent in ["read_file", "search"]:
                return await self._finalize(
                    session_id, cmd, intent, current_dir, "", 0.05
                )

            return await self._finalize(session_id, cmd, intent, current_dir, "", 0.05)

        elif action == "FAKE_VULNERABILITY":
            # Expose fake vulnerabilities to keep attacker engaged
            cmd_lower = cmd.lower()

            # Fake find results showing sensitive files
            if "find" in cmd_lower and any(
                x in cmd_lower for x in [".key", "key", "secret", "credential"]
            ):
                fake_find = """/home/shophub/.ssh/id_rsa
    /home/shophub/shophub/config/api_keys.json
    /var/backups/ssl/private.key
    /opt/secrets/database.key
    /etc/shophub/stripe_secret.key
    /home/deploy/.aws/credentials"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_find, 0.2
                )

            # Fake sudo -l showing excessive privileges
            if "sudo" in cmd_lower and ("-l" in cmd_lower or "list" in cmd_lower):
                fake_sudo = """Matching Defaults entries for shophub on this host:
        env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

    User shophub may run the following commands on shophub-server:
        (ALL) NOPASSWD: /usr/bin/systemctl restart shophub
        (ALL) NOPASSWD: /usr/bin/docker-compose
        (ALL) NOPASSWD: /bin/bash
        (root) /usr/bin/mysql"""
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_sudo, 0.1
                )

            # Fake world-writable sensitive files
            if "ls" in cmd_lower and "-la" in cmd_lower and "etc" in cmd_lower:
                response = await self._original_command_handler(session_id, event)
                # Add a suspicious world-writable file to the output
                if isinstance(response.get("response"), str):
                    response["response"] += (
                        "\n-rw-rw-rw-  1 root root  1234 Jan 15 10:00 backup_credentials.txt"
                    )
                return response

            # Fake exposed Docker socket
            if "docker" in cmd_lower or "sock" in cmd_lower:
                fake_docker = (
                    """srw-rw-rw- 1 root docker 0 Jan 15 09:30 /var/run/docker.sock"""
                )
                return await self._finalize(
                    session_id, cmd, intent, current_dir, fake_docker, 0.1
                )

            return await self._original_command_handler(session_id, event)

        elif action == "TERMINATE_SESSION":
            # Force disconnect
            return {
                "response": "Connection to shophub-prod-01 closed by remote host.\nConnection to shophub-prod-01 closed.",
                "delay": 0.0,
                "disconnect": True,
            }

        # Fallback to realistic response
        return await self._original_command_handler(session_id, event)
