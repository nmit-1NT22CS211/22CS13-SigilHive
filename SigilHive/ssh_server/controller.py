# controller.py - FIXED VERSION
import llm_gen
import asyncio
import numpy as np
import time
import random
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from adaptive_response import AdaptiveResponseSystem
from smart_prompt_generator import SmartPromptGenerator
from dynamic_filesystem import DynamicFileSystem
from smart_cache import SmartCache
from enhanced_analytics import EnhancedAnalytics, CommandEvent
from kafka_manager import HoneypotKafkaManager
from file_structure import SHOPHUB_STRUCTURE, FILE_CONTENTS

ENHANCEMENTS_ENABLED = True


class Controller:
    def __init__(self, persona: str = "shophub-server"):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.persona = persona
        self.background_tasks = []  # Track background tasks
        self.kafka_manager = HoneypotKafkaManager()

        # ensure we modify the module-level flag if needed
        global ENHANCEMENTS_ENABLED

        # Initialize enhancement systems (with fallback)
        if ENHANCEMENTS_ENABLED:
            try:
                self.adaptive_system = AdaptiveResponseSystem()
                self.prompt_generator = SmartPromptGenerator()
                self.dynamic_fs = DynamicFileSystem(SHOPHUB_STRUCTURE)
                self.cache = SmartCache(max_memory_cache_size=100)
                self.analytics = EnhancedAnalytics()

                # DON'T start background tasks here - they'll be started later
                print("[Controller] ✅ All enhancements loaded successfully")
            except Exception as e:
                print(f"[Controller] ⚠️  Enhancement initialization error: {e}")
                ENHANCEMENTS_ENABLED = False

        if not ENHANCEMENTS_ENABLED:
            print("[Controller] Running in BASIC mode (no enhancements)")

    async def start_background_tasks(self):
        """Start background tasks - call this after event loop is running"""
        if not ENHANCEMENTS_ENABLED:
            return

        try:
            # Create and store background tasks
            cache_task = asyncio.create_task(self._background_cache_cleanup())
            fs_task = asyncio.create_task(self._background_fs_evolution())

            self.background_tasks.extend([cache_task, fs_task])
            print("[Controller] 🔄 Background tasks started")
        except Exception as e:
            print(f"[Controller] ⚠️  Could not start background tasks: {e}")

    async def stop_background_tasks(self):
        """Stop all background tasks gracefully"""
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        print("[Controller] 🛑 Background tasks stopped")

    def _update_meta(self, session_id: str, event: Dict[str, Any]):
        meta = self.sessions.setdefault(
            session_id,
            {
                "cmd_count": 0,
                "elapsed": 0.0,
                "last_cmd": "",
                "current_dir": "~",
                "command_history": [],
                "discovered_files": [],
            },
        )
        meta["cmd_count"] = event.get("cmd_count", meta["cmd_count"])
        meta["elapsed"] = event.get("elapsed", meta["elapsed"])

        if "command" in event:
            cmd = event.get("command", meta["last_cmd"])
            meta["last_cmd"] = cmd
            meta["command_history"].append(cmd)

            # Keep last 50 commands
            if len(meta["command_history"]) > 50:
                meta["command_history"] = meta["command_history"][-50:]

        if "current_dir" in event:
            meta["current_dir"] = event.get("current_dir", meta["current_dir"])

        meta["last_ts"] = time.time()
        self.sessions[session_id] = meta
        return meta

    def get_directory_context(self, current_dir: str) -> Dict[str, Any]:
        """Get context about the current directory for the LLM"""
        normalized_dir = current_dir.strip()

        if normalized_dir.endswith("/") and normalized_dir != "/":
            normalized_dir = normalized_dir[:-1]

        if normalized_dir == "~" or normalized_dir == "":
            normalized_dir = "~"
        if normalized_dir in SHOPHUB_STRUCTURE:
            return SHOPHUB_STRUCTURE[normalized_dir]

        if not normalized_dir.startswith("~") and normalized_dir.startswith("/"):
            pass
        elif not normalized_dir.startswith("~"):
            maybe = f"~/{normalized_dir}"
            if maybe in SHOPHUB_STRUCTURE:
                return SHOPHUB_STRUCTURE[maybe]

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

        # Terminal control commands
        if base_cmd in ("clear", "reset"):
            return "clear_screen"
        if base_cmd == "history":
            return "show_history"
        if base_cmd == "echo":
            return "echo"
        if base_cmd == "env" or base_cmd == "printenv":
            return "show_env"

        # Commands that require arguments
        if base_cmd in ("cat", "less", "more"):
            # Check if filename is provided
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
            # Check if pattern is provided
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

        if full_path in FILE_CONTENTS:
            return full_path

        full_path_lower = full_path.lower()
        for key in FILE_CONTENTS.keys():
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
                topic="honeypot-logs", value=payload, service="ssh", event_type=intent
            )

        except Exception as e:
            print(f"[Controller] Kafka send error: {e}")

        return {"response": response, "delay": delay}

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        command_history = meta.get("command_history", [])
        intent = self.classify_command(cmd)

        # --- Filesystem evolution ---
        if ENHANCEMENTS_ENABLED:
            try:
                self.dynamic_fs.evolve_filesystem(session_id, command_history)
                dir_context = self.dynamic_fs.get_structure().get(
                    current_dir, self.get_directory_context(current_dir)
                )
            except Exception:
                dir_context = self.get_directory_context(current_dir)
        else:
            dir_context = self.get_directory_context(current_dir)

        # --- Cache lookup ---
        cache_key = f"{session_id}:{cmd}:{current_dir}"
        if ENHANCEMENTS_ENABLED:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    attacker_profile = self.adaptive_system.get_attacker_profile(
                        session_id
                    )
                    if not attacker_profile:
                        attacker_profile = (
                            self.adaptive_system.analyze_attacker_behavior(
                                session_id, command_history
                            )
                        )

                    adaptive = self.adaptive_system.get_adaptive_response(
                        session_id, cmd, cached, command_history
                    )

                    return await self._finalize(
                        session_id,
                        cmd,
                        intent,
                        current_dir,
                        adaptive["response"],
                        adaptive["delay"],
                    )
            except Exception:
                pass

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

                # dynamic FS
                if ENHANCEMENTS_ENABLED:
                    try:
                        fpath = f"{current_dir}/{filename_hint}"
                        dyn = self.dynamic_fs.get_file_content(fpath)
                        if dyn:
                            return await self._finalize(
                                session_id, cmd, intent, current_dir, dyn, 0.05
                            )
                    except Exception:
                        pass

                # predefined FS
                matched_path = self._find_file_case_insensitive(
                    current_dir, filename_hint
                )
                if matched_path:
                    content = FILE_CONTENTS[matched_path]
                    return await self._finalize(
                        session_id, cmd, intent, current_dir, content, 0.05
                    )

                # file not found
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

        if ENHANCEMENTS_ENABLED:
            try:
                attacker_profile = self.adaptive_system.analyze_attacker_behavior(
                    session_id, command_history
                )
                discovered_files = meta.get("discovered_files", [])
                context["enhanced_prompt"] = (
                    self.prompt_generator.build_contextual_prompt(
                        session_id=session_id,
                        command=cmd,
                        current_dir=current_dir,
                        intent=intent,
                        attacker_profile=attacker_profile,
                        discovered_files=discovered_files,
                    )
                )
            except Exception:
                pass

        try:
            response_text = await llm_gen.generate_response_for_command_async(
                command=cmd,
                filename_hint=filename_hint,
                persona=self.persona,
                context=context,
            )
        except Exception:
            response_text = (
                f"bash: {cmd.split()[0] if cmd else 'unknown'}: command not found"
            )

        # Adaptive + Cache
        if ENHANCEMENTS_ENABLED:
            try:
                await self.cache.set(cache_key, response_text)
                adaptive = self.adaptive_system.get_adaptive_response(
                    session_id, cmd, response_text, command_history
                )
                return await self._finalize(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    adaptive["response"],
                    adaptive["delay"],
                )
            except Exception:
                pass

        # final fallback
        delay = 0.05 + float(np.random.rand()) * 0.2
        return await self._finalize(
            session_id, cmd, intent, current_dir, response_text, delay
        )

    def _log_to_analytics(
        self,
        session_id: str,
        command: str,
        intent: str,
        current_dir: str,
        response: str,
        delay: float,
        success: bool,
    ):
        """Log command to analytics system"""
        if not ENHANCEMENTS_ENABLED:
            return

        try:
            event = CommandEvent(
                session_id=session_id,
                timestamp=datetime.now(),
                command=command,
                intent=intent,
                current_dir=current_dir,
                response_preview=response[:400],
                delay=delay,
                success=success,
            )
            self.analytics.log_command(event)
        except Exception as e:
            print(f"[Controller] Analytics logging error: {e}")

    async def _background_cache_cleanup(self):
        """Background task to clean up expired cache entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                self.cache.cleanup_expired()
                stats = self.cache.get_stats()
                print(f"[Controller] 🧹 Cache cleanup: {stats['hit_rate']} hit rate")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Controller] Cache cleanup error: {e}")

    async def _background_fs_evolution(self):
        """Background task to evolve filesystem"""
        while True:
            try:
                await asyncio.sleep(600)  # Every 10 minutes

                for session_id, meta in self.sessions.items():
                    commands = meta.get("command_history", [])
                    if commands:
                        self.dynamic_fs.evolve_filesystem(session_id, commands)

                print("[Controller] 🌱 Filesystem evolved")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Controller] Filesystem evolution error: {e}")

    def get_analytics_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get analytics report"""
        if ENHANCEMENTS_ENABLED:
            return self.analytics.generate_report(hours)
        return {}

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if ENHANCEMENTS_ENABLED:
            return self.cache.get_stats()
        return {}

    def end_session(self, session_id: str):
        """End a session and finalize analytics"""
        if session_id in self.sessions:
            if ENHANCEMENTS_ENABLED:
                try:
                    profile = self.adaptive_system.get_attacker_profile(session_id)
                    self.analytics.end_session(session_id, profile)
                except Exception:
                    pass

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
