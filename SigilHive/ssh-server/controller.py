# controller.py
import json
import asyncio
import numpy as np
import time
import random
from typing import Dict, Any
import llm_gen

# ShopHub application directory structure (unchanged)
SHOPHUB_STRUCTURE = {
    "~": {
        "type": "directory",
        "description": "Home directory of the ShopHub application user",
        "contents": ["shophub", ".env", ".bashrc", "README.md"],
    },
    "~/shophub": {
        "type": "directory",
        "description": "Main ShopHub ecommerce application directory",
        "contents": [
            "app",
            "config",
            "database",
            "logs",
            "scripts",
            "docker-compose.yml",
            "package.json",
            "README.md",
        ],
    },
    "~/shophub/app": {
        "type": "directory",
        "description": "Application source code",
        "contents": [
            "controllers",
            "models",
            "routes",
            "middleware",
            "utils",
            "views",
            "app.js",
        ],
    },
    "~/shophub/app/controllers": {
        "type": "directory",
        "description": "Controller files for handling business logic",
        "contents": [
            "authController.js",
            "productController.js",
            "orderController.js",
            "userController.js",
            "cartController.js",
            "paymentController.js",
        ],
    },
    "~/shophub/app/models": {
        "type": "directory",
        "description": "Database models and schemas",
        "contents": [
            "User.js",
            "Product.js",
            "Order.js",
            "Cart.js",
            "Payment.js",
            "Category.js",
            "Review.js",
        ],
    },
    "~/shophub/app/routes": {
        "type": "directory",
        "description": "API route definitions",
        "contents": [
            "auth.js",
            "products.js",
            "orders.js",
            "users.js",
            "cart.js",
            "payments.js",
            "admin.js",
        ],
    },
    "~/shophub/app/middleware": {
        "type": "directory",
        "description": "Middleware for authentication and validation",
        "contents": [
            "auth.js",
            "validation.js",
            "errorHandler.js",
            "rateLimiter.js",
            "logger.js",
        ],
    },
    "~/shophub/app/utils": {
        "type": "directory",
        "description": "Utility functions and helpers",
        "contents": [
            "emailService.js",
            "imageProcessor.js",
            "paymentGateway.js",
            "encryption.js",
            "validator.js",
        ],
    },
    "~/shophub/app/views": {
        "type": "directory",
        "description": "Email templates and view files",
        "contents": [
            "email-templates",
            "order-confirmation.html",
            "password-reset.html",
            "welcome.html",
        ],
    },
    "~/shophub/config": {
        "type": "directory",
        "description": "Configuration files",
        "contents": [
            "database.js",
            "server.js",
            "payment.js",
            "email.js",
            "redis.js",
            ".env.example",
        ],
    },
    "~/shophub/database": {
        "type": "directory",
        "description": "Database migrations and seeds",
        "contents": ["migrations", "seeds", "backup", "init.sql"],
    },
    "~/shophub/database/migrations": {
        "type": "directory",
        "description": "Database migration files",
        "contents": [
            "001_create_users.sql",
            "002_create_products.sql",
            "003_create_orders.sql",
            "004_create_categories.sql",
            "005_create_reviews.sql",
        ],
    },
    "~/shophub/database/seeds": {
        "type": "directory",
        "description": "Database seed data",
        "contents": ["users.json", "products.json", "categories.json"],
    },
    "~/shophub/logs": {
        "type": "directory",
        "description": "Application logs",
        "contents": ["access.log", "error.log", "payment.log", "audit.log"],
    },
    "~/shophub/scripts": {
        "type": "directory",
        "description": "Utility scripts",
        "contents": [
            "deploy.sh",
            "backup.sh",
            "migrate.sh",
            "seed.sh",
            "health-check.sh",
        ],
    },
}

# File contents for common files (unchanged)
FILE_CONTENTS = {
    "~/README.md": "ShopHub E-commerce Platform - Production Server\nThis server hosts the ShopHub application.",
    "~/shophub/README.md": "ShopHub - Modern E-commerce Platform\n\nA full-stack ecommerce solution built with Node.js, Express, and MongoDB.",
    "~/shophub/package.json": '{\n  "name": "shophub",\n  "version": "2.3.1",\n  "description": "ShopHub E-commerce Platform",\n  "main": "app/app.js",\n  "scripts": {\n    "start": "node app/app.js",\n    "dev": "nodemon app/app.js",\n    "migrate": "node scripts/migrate.sh"\n  }\n}',
    "~/shophub/docker-compose.yml": "version: '3.8'\nservices:\n  app:\n    build: .\n    ports:\n      - '3000:3000'\n  mongodb:\n    image: mongo:6.0\n  redis:\n    image: redis:7.0",
    "~/shophub/app/app.js": "const express = require('express');\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.listen(PORT, () => {\n  console.log(`ShopHub running on port ${PORT}`);\n});",
    "~/.env": "# ShopHub Environment Variables\nDB_HOST=localhost\nDB_NAME=shophub_prod\nREDIS_URL=redis://localhost:6379\nJWT_SECRET=<redacted>\nSTRIPE_KEY=<redacted>",
}


class Controller:
    def __init__(self, persona: str = "shophub-server"):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.persona = persona

    def _update_meta(self, session_id: str, event: Dict[str, Any]):
        meta = self.sessions.setdefault(
            session_id,
            {"cmd_count": 0, "elapsed": 0.0, "last_cmd": "", "current_dir": "~"},
        )
        meta["cmd_count"] = event.get("cmd_count", meta["cmd_count"])
        meta["elapsed"] = event.get("elapsed", meta["elapsed"])
        if "command" in event:
            meta["last_cmd"] = event.get("command", meta["last_cmd"])
        if "current_dir" in event:
            meta["current_dir"] = event.get("current_dir", meta["current_dir"])
        meta["last_ts"] = time.time()
        self.sessions[session_id] = meta
        return meta

    def get_directory_context(self, current_dir: str) -> Dict[str, Any]:
        """Get context about the current directory for the LLM"""
        # Normalize the directory path
        normalized_dir = current_dir.strip()

        # collapse trailing slashes
        if normalized_dir.endswith("/") and normalized_dir != "/":
            normalized_dir = normalized_dir[:-1]

        # try a few common normalizations
        if normalized_dir == "~" or normalized_dir == "":
            normalized_dir = "~"
        if normalized_dir in SHOPHUB_STRUCTURE:
            return SHOPHUB_STRUCTURE[normalized_dir]

        # try adding ~/ prefix if user passed a relative path
        if not normalized_dir.startswith("~") and normalized_dir.startswith("/"):
            # absolute path - leave as-is (not in shophub structure)
            pass
        elif not normalized_dir.startswith("~"):
            maybe = f"~/{normalized_dir}"
            if maybe in SHOPHUB_STRUCTURE:
                return SHOPHUB_STRUCTURE[maybe]

        # If exact match not found, return a generic directory context
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

        # common read commands
        if base_cmd in ("cat", "less", "more"):
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

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate context-aware responses based on current directory and command.
        Returns: dict { "response": str, "delay": float }
        """
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        intent = self.classify_command(cmd)

        # Get directory context
        dir_context = self.get_directory_context(current_dir)

        # Quick direct responses for trivial intents
        if intent == "print_dir":
            response_text = current_dir
            return {"response": response_text, "delay": 0.01}

        # If read_file and known file, return content quickly
        filename_hint = None
        if intent == "read_file":
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                filename_hint = parts[1].strip()
                full_path = filename_hint
                # canonicalize relative paths to be under current_dir
                if not (full_path.startswith("~") or full_path.startswith("/")):
                    full_path = f"{current_dir.rstrip('/')}/{full_path}"
                # normalize
                full_path = full_path.replace("//", "/")
                if full_path in FILE_CONTENTS:
                    return {"response": FILE_CONTENTS[full_path], "delay": 0.05}
                # try user-level paths (e.g. ~/shophub/README.md)
                if full_path.startswith("~") and full_path in FILE_CONTENTS:
                    return {"response": FILE_CONTENTS[full_path], "delay": 0.05}

        # Intent-specific simulated responses (avoid invoking LLM when possible)
        try:
            if intent == "list_dir":
                response_text = self._simulate_list_dir(dir_context)
                delay = 0.02 + random.random() * 0.15
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "identity":
                response_text = self._simulate_identity()
                delay = 0.01
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "system_info":
                response_text = self._simulate_system_info(cmd)
                delay = 0.02
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "process_list":
                response_text = self._simulate_process_list()
                delay = 0.03
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "network_probe":
                response_text = self._simulate_ping(cmd)
                delay = 0.05
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "http_fetch":
                response_text = self._simulate_http_fetch(cmd)
                delay = 0.05 + random.random() * 0.2
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "docker":
                response_text = self._simulate_docker(cmd)
                delay = 0.04
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

            if intent == "git":
                response_text = self._simulate_git(cmd, dir_context)
                delay = 0.03
                asyncio.create_task(
                    self._log_event_async(
                        session_id, cmd, intent, response_text, current_dir
                    )
                )
                return {"response": response_text, "delay": delay}

        except Exception as e:
            # If simulation fails for any reason, fall back to LLM
            print("[controller] simulation error:", e)

        # Build context for LLM fallback
        context = {
            "current_directory": current_dir,
            "directory_description": dir_context.get("description", ""),
            "directory_contents": dir_context.get("contents", []),
            "application": "ShopHub E-commerce Platform",
            "application_tech": "Node.js, Express, MongoDB, Redis, Docker",
        }

        try:
            response_text = await llm_gen.generate_response_for_command_async(
                command=cmd,
                filename_hint=filename_hint,
                persona=self.persona,
                context=context,
            )
        except Exception:
            # generic bash-like fallback error
            response_text = f"bash: {cmd}: command not found"

        # Add randomized delay
        base_delay = 0.05
        delay = base_delay + float(np.random.rand()) * 0.2

        # Log event
        asyncio.create_task(
            self._log_event_async(session_id, cmd, intent, response_text, current_dir)
        )

        return {"response": response_text, "delay": delay}

    async def _log_event_async(
        self,
        session_id: str,
        command: str,
        intent: str,
        response: str,
        current_dir: str,
    ):
        """Log events for analysis"""
        try:
            log_line = {
                "ts": time.time(),
                "session_id": session_id,
                "command": command,
                "intent": intent,
                "current_dir": current_dir,
                "response_preview": response[:400],
            }
            # ensure directory exists
            with open("session_logs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_line) + "\n")
        except Exception as e:
            print("[controller] logging error:", e)

    # ---------------------------
    # Simulation helpers
    # ---------------------------
    def _simulate_list_dir(self, dir_context: Dict[str, Any]) -> str:
        contents = dir_context.get("contents", [])
        if not contents:
            return ""  # empty dir
        # Pretty list, show directories first (heuristic)
        # dirs = [c for c in contents if not "." in c or c.endswith("/")]
        # files = [c for c in contents if c not in dirs]
        lines = []
        # show concise ls -la style
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
        # Provide a realistic whoami output
        return "shophub"

    def _simulate_system_info(self, cmd: str) -> str:
        if cmd.startswith("uname"):
            # give uname -a like output
            return "Linux shophub-server 5.15.0-100-generic #1 SMP Thu Jan 1 00:00:00 UTC 2025 x86_64 GNU/Linux"
        if cmd.startswith("hostname"):
            return "shophub-server"
        return "Unknown system info query"

    def _simulate_process_list(self) -> str:
        # Minimal ps aux like output
        sample = [
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND",
            "root         1  0.0  0.1 169084  6044 ?        Ss   09:30   0:01 /sbin/init",
            "shophub   1023  0.3  1.2 238564 25432 ?        Sl   09:31   0:12 node /home/shophub/shophub/app/app.js",
            "redis     2048  0.1  0.8  84900 16844 ?        Ssl  09:31   0:03 redis-server *:6379",
            "mongodb   3120  1.2  2.5 452128 51200 ?        Ssl  09:31   0:45 /usr/bin/mongod --config /etc/mongod.conf",
        ]
        return "\n".join(sample)

    def _simulate_ping(self, cmd: str) -> str:
        # basic simulation of ping -c 4 host
        parts = cmd.split()
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        # construct 4 lines and summary
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
        # naive simulation of curl/wget
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
        # If repository-like files exist, show a fake git status
        contents = dir_context.get("contents", [])
        if ".git" in contents:
            if cmd.strip() == "git status":
                return "On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean"
            return f"git: simulated output for '{cmd}'"
        # if no .git, show typical git error
        return "fatal: not a git repository (or any of the parent directories): .git"


# Quick test harness to exercise controller (runs when file executed directly)
if __name__ == "__main__":

    async def main():
        c = Controller()
        session = "test-sid"

        tests = [
            {"command": "pwd", "current_dir": "~"},
            {"command": "ls", "current_dir": "~/shophub"},
            {"command": "whoami", "current_dir": "~"},
            {"command": "uname -a", "current_dir": "~"},
            {"command": "ps aux", "current_dir": "~"},
            {"command": "ping -c 4 8.8.8.8", "current_dir": "~"},
            {"command": "curl http://localhost:3000", "current_dir": "~/shophub"},
            {"command": "cat README.md", "current_dir": "~"},
            {"command": "git status", "current_dir": "~/shophub"},
        ]

        for ev in tests:
            out = await c.get_action_for_session(session, ev)
            print(
                f"\n$ {ev['command']}\n{out['response']}\n(delay: {out['delay']:.3f}s)"
            )

    asyncio.run(main())
