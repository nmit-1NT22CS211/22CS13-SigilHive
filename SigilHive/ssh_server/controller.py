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
                value={
                    "timestamp": payload["timestamp"],
                    "session_id": session_id,
                    "command": cmd,
                    "intent": intent,
                    "current_dir": current_dir,
                },
            )
        except Exception as e:
            print(f"[controller] kafka error in finalize: {e}")

        return {"response": response, "delay": delay}

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        intent = self.classify_command(cmd)

        if not self.rl_enabled:
            return await self._original_command_handler(session_id, event)

        try:
            state = extract_state(meta, intent)
            state_idx = self.rl_agent.get_state_index(state)
            action_idx = self.rl_agent.choose_action(state_idx)
            action = self.rl_agent.actions[action_idx]

            action_result = await self._execute_rl_action(action, session_id, event)

            next_meta = self.sessions.get(session_id, meta)
            next_state = extract_state(next_meta, intent)
            next_state_idx = self.rl_agent.get_state_index(next_state)

            reward = calculate_reward(meta, next_meta, intent, action)

            self.rl_agent.update_q_value(state_idx, action_idx, reward, next_state_idx)

            log_interaction(session_id, state, action, reward, next_state, meta)

            return action_result

        except Exception as e:
            print(f"[Controller] RL error: {e}")
            return await self._original_command_handler(session_id, event)

    async def _original_command_handler(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Original command handler without RL"""
        meta = self.sessions.get(session_id, {})
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        intent = self.classify_command(cmd)

        dir_context = self.get_directory_context(current_dir)

        context = {
            "current_directory": current_dir,
            "directory_description": dir_context.get("description", ""),
            "directory_contents": dir_context.get("contents", []),
            "application": "ShopHub E-commerce Platform",
            "application_tech": "Node.js, Express, MongoDB, Redis",
        }

        if intent == "clear_screen":
            return await self._finalize(
                session_id, cmd, intent, current_dir, "\033[H\033[2J", 0.0
            )

        elif intent == "show_history":
            hist = meta.get("command_history", [])
            numbered = "\n".join(f"  {i+1}  {c}" for i, c in enumerate(hist[-20:]))
            return await self._finalize(session_id, cmd, intent, current_dir, numbered, 0.1)

        elif intent == "echo":
            text = cmd[4:].strip() if len(cmd) > 4 else ""
            return await self._finalize(session_id, cmd, intent, current_dir, text, 0.0)

        elif intent == "show_env":
            env_vars = """HOME=/home/shophub
USER=shophub
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
NODE_ENV=production
PORT=3000
DB_HOST=prod-mysql.internal
REDIS_HOST=prod-redis.internal"""
            return await self._finalize(session_id, cmd, intent, current_dir, env_vars, 0.1)

        elif intent == "read_file_no_arg":
            base_cmd = cmd.split()[0] if cmd.split() else "cat"
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                f"{base_cmd}: missing file operand\nTry '{base_cmd} --help' for more information.",
                0.05,
            )

        elif intent == "read_file":
            return await self._handle_read_file(session_id, cmd, current_dir, context)

        elif intent == "list_dir":
            return await self._handle_list_dir(session_id, cmd, current_dir, context)

        elif intent == "identity":
            if "whoami" in cmd:
                return await self._finalize(
                    session_id, cmd, intent, current_dir, "shophub", 0.05
                )
            else:
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    "uid=1000(shophub) gid=1000(shophub) groups=1000(shophub),27(sudo),999(docker)",
                    0.05,
                )

        elif intent == "system_info":
            if "uname" in cmd:
                if "-a" in cmd:
                    return await self._finalize(
                        session_id,
                        cmd,
                        intent,
                        current_dir,
                        "Linux shophub-prod-01 5.15.0-89-generic #99-Ubuntu SMP Mon Oct 30 20:42:41 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux",
                        0.05,
                    )
                return await self._finalize(
                    session_id, cmd, intent, current_dir, "Linux", 0.05
                )
            else:
                return await self._finalize(
                    session_id, cmd, intent, current_dir, "shophub-prod-01", 0.05
                )

        elif intent == "process_list":
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                self._simulate_ps(cmd),
                0.1,
            )

        elif intent == "netstat":
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                self._simulate_netstat(cmd),
                0.1,
            )

        elif intent == "print_dir":
            full_path = current_dir
            if full_path == "~":
                full_path = "/home/shophub"
            elif full_path.startswith("~/"):
                full_path = "/home/shophub/" + full_path[2:]
            return await self._finalize(session_id, cmd, intent, current_dir, full_path, 0.05)

        elif intent == "docker":
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                self._simulate_docker(cmd),
                0.1,
            )

        elif intent == "git":
            git_output = self._simulate_git(cmd, dir_context)
            return await self._finalize(
                session_id, cmd, intent, current_dir, git_output, 0.1
            )

        elif intent == "grep_no_arg":
            base_cmd = cmd.split()[0] if cmd.split() else "grep"
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                f"Usage: {base_cmd} [OPTION]... PATTERN [FILE]...\nTry '{base_cmd} --help' for more information.",
                0.05,
            )

        else:
            llm_response = await generate_response_for_command_async(
                command=cmd,
                filename_hint=None,
                persona=self.persona,
                context=context,
                force_refresh=False,
            )
            return await self._finalize(
                session_id, cmd, intent, current_dir, llm_response, 0.1
            )

    async def _handle_read_file(
        self, session_id: str, cmd: str, current_dir: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle file reading commands (cat, less, more)"""
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return await self._finalize(
                session_id,
                cmd,
                "read_file_no_arg",
                current_dir,
                f"{parts[0]}: missing file operand",
                0.05,
            )

        filename = parts[1].strip()
        intent = "read_file"

        # Check if file exists in directory listing
        if not self._file_exists_in_directory(current_dir, filename):
            return await self._finalize(
                session_id,
                cmd,
                intent,
                current_dir,
                f"{parts[0]}: {filename}: No such file or directory",
                0.05,
            )

        # Try to find file in FILE_CONTENTS
        file_path_key = self._find_file_case_insensitive(current_dir, filename)
        
        # If file exists in FILE_CONTENTS, return that content
        if file_path_key:
            content = self.file_contents[file_path_key]
            return await self._finalize(
                session_id, cmd, intent, current_dir, content, 0.1
            )

        # File exists in directory but not in FILE_CONTENTS - generate content with LLM
        print(f"[Controller] File '{filename}' exists in directory but not in FILE_CONTENTS, generating content with LLM")
        
        llm_response = await generate_response_for_command_async(
            command=cmd,
            filename_hint=filename,
            persona=self.persona,
            context=context,
            force_refresh=False,
        )
        
        return await self._finalize(
            session_id, cmd, intent, current_dir, llm_response, 0.1
        )

    async def _handle_list_dir(
        self, session_id: str, cmd: str, current_dir: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle directory listing commands"""
        parts = cmd.split()
        base_cmd = parts[0] if parts else "ls"

        target_dir = current_dir
        if len(parts) > 1 and not parts[1].startswith("-"):
            target_dir = parts[1]

        dir_context = self.get_directory_context(target_dir)
        contents = dir_context.get("contents", [])

        if not contents:
            return await self._finalize(session_id, cmd, "list_dir", current_dir, "", 0.05)

        if "-la" in cmd or "-al" in cmd or "-l" in cmd:
            listing_parts = []
            listing_parts.append(f"total {len(contents) * 4}")

            for item in contents:
                if item.startswith("."):
                    perm = "drwxr-xr-x" if item == ".git" else "-rw-r--r--"
                    size = "4096" if item == ".git" else str(random.randint(100, 5000))
                elif item.endswith("/"):
                    perm = "drwxr-xr-x"
                    size = "4096"
                    item = item.rstrip("/")
                elif any(
                    item.endswith(ext) for ext in [".js", ".json", ".md", ".txt", ".sh"]
                ):
                    perm = "-rw-r--r--"
                    size = str(random.randint(500, 10000))
                else:
                    perm = "drwxr-xr-x"
                    size = "4096"

                date_str = "Jan 15 10:30"
                listing_parts.append(f"{perm} 1 shophub shophub {size:>8} {date_str} {item}")

            listing = "\n".join(listing_parts)
            return await self._finalize(
                session_id, cmd, "list_dir", current_dir, listing, 0.1
            )
        else:
            listing = "  ".join(contents)
            return await self._finalize(
                session_id, cmd, "list_dir", current_dir, listing, 0.05
            )

    def _simulate_ps(self, cmd: str) -> str:
        if "aux" in cmd or "-ef" in cmd:
            return (
                "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
                "root         1  0.0  0.1  22536  3892 ?        Ss   10:00   0:01 /sbin/init\n"
                "shophub   1234  2.5  5.2 987654 98765 ?        Sl   10:05   1:23 node /home/shophub/shophub/server.js\n"
                "shophub   1235  0.1  1.2 456789 23456 ?        S    10:05   0:05 node /home/shophub/shophub/worker.js\n"
                "mongodb   2345  1.2  3.4 678901 45678 ?        Sl   10:00   0:45 /usr/bin/mongod --config /etc/mongod.conf\n"
                "redis     3456  0.3  0.8 234567 12345 ?        Ssl  10:00   0:12 /usr/bin/redis-server *:6379"
            )
        return "  PID TTY          TIME CMD\n 1234 pts/0    00:00:00 bash\n 5678 pts/0    00:00:00 ps"

    def _simulate_netstat(self, cmd: str) -> str:
        return (
            "Active Internet connections (only servers)\n"
            "Proto Recv-Q Send-Q Local Address           Foreign Address         State\n"
            "tcp        0      0 0.0.0.0:3000            0.0.0.0:*               LISTEN\n"
            "tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN\n"
            "tcp        0      0 127.0.0.1:6379          0.0.0.0:*               LISTEN\n"
            "tcp        0      0 127.0.0.1:27017         0.0.0.0:*               LISTEN"
        )

    def _simulate_docker(self, cmd: str) -> str:
        if "ps" in cmd:
            return (
                "CONTAINER ID   IMAGE           COMMAND                  CREATED        STATUS        PORTS                    NAMES\n"
                'a1b2c3d4e5f6   shophub:latest  "node server.js"         2 hours ago    Up 2 hours    0.0.0.0:3000->3000/tcp   shophub_app\n'
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

    def end_session(self, session_id: str):
        """Clean up session data"""
        if session_id in self.sessions:
            print(f"[Controller] Session {session_id} ended")
            del self.sessions[session_id]