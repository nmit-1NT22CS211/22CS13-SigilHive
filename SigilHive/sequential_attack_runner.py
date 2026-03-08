"""
SigilHive LangGraph Agent — Gemini-powered Honeypot Attack & Evolution Orchestrator
═══════════════════════════════════════════════════════════════════════════════════════

A LangGraph agent that:
  1. Simulates sequential attacks across SSH → HTTP → Database honeypots
  2. Recon commands are STATIC (fast, predictable, low-suspicion probes)
  3. Exploit commands are DYNAMIC — Gemini reads each recon result and
     generates targeted commands/paths/queries for that specific honeypot
  4. Evaluates campaign results and decides whether the honeypot filesystem
     should evolve to become more deceptive

Architecture (LangGraph nodes):
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                                                                              │
  │  plan_attack                                                                 │
  │      │                                                                       │
  │      ▼                                                                       │
  │  attack_ssh_recon  →  gen_ssh_exploit_cmds  →  attack_ssh_exploit           │
  │      │                                                                       │
  │      ▼                                                                       │
  │  attack_http_recon →  gen_http_exploit_cmds →  attack_http_exploit          │
  │      │                                                                       │
  │      ▼                                                                       │
  │  attack_db_recon   →  gen_db_exploit_cmds   →  attack_db_exploit            │
  │      │                                                                       │
  │      ▼                                                                       │
  │  evaluate_campaign  →  evolve_filesystem  →  save_results                   │
  │                                                                              │
  └──────────────────────────────────────────────────────────────────────────────┘

Requirements:
    pip install langgraph langchain-google-genai langchain-core

Usage:
    export GOOGLE_API_KEY="your-gemini-api-key"
    python sigil_hive_langgraph_agent.py
    python sigil_hive_langgraph_agent.py --episodes 5
    python sigil_hive_langgraph_agent.py --host 192.168.1.10 --ssh-port 2223
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import ssl
import struct
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, TypedDict

# ── LangGraph / LangChain imports ────────────────────────────────────────────
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from dotenv import load_dotenv

load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_FMT  = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter(LOG_FMT, DATE_FMT))
        logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    return logger


root_log = _build_logger("sigilhive")
for _noisy in ("paramiko", "urllib3", "requests", "asyncio", "asyncssh",
               "httpx", "httpcore", "google"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────────────────────
#  Domain Enums / Dataclasses  (mirror sequential_attack_runner.py)
# ─────────────────────────────────────────────────────────────────────────────

class Protocol(str, Enum):
    SSH      = "ssh"
    HTTP     = "http"
    DATABASE = "database"

    @classmethod
    def sequence(cls):
        return [cls.SSH, cls.HTTP, cls.DATABASE]


@dataclass
class AttackResult:
    protocol:        Protocol
    attack_type:     str          # "recon" | "exploit"
    success:         bool
    data_extracted:  int          # bytes
    suspicion_delta: float
    duration:        float
    responses:       list = field(default_factory=list)
    timestamp:       float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "protocol":        self.protocol.value,
            "attack_type":     self.attack_type,
            "success":         self.success,
            "data_extracted":  self.data_extracted,
            "suspicion_delta": round(self.suspicion_delta, 4),
            "duration":        round(self.duration, 3),
            "responses":       self.responses[:3],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph State
# ─────────────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Conversation messages (append-only via add_messages reducer)
    messages: Annotated[list, add_messages]

    # Attack configuration
    host:      str
    ssh_port:  int
    http_port: int
    db_port:   int
    dry_run:   bool
    episode:   int

    # Attack results accumulated during the cycle
    ssh_recon_result:    Optional[dict]
    ssh_exploit_result:  Optional[dict]
    http_recon_result:   Optional[dict]
    http_exploit_result: Optional[dict]
    db_recon_result:     Optional[dict]
    db_exploit_result:   Optional[dict]

    # Agent decisions (set by Gemini)
    attack_plan:         Optional[str]      # Gemini's attack strategy narrative
    skip_ssh_exploit:    bool               # abort exploit if recon too risky
    skip_http_exploit:   bool
    skip_db_exploit:     bool

    # LLM-generated exploit commands (populated after each recon node)
    ssh_exploit_cmds:    list          # shell commands Gemini generated
    http_exploit_cmds:   list          # [(method, path), ...] Gemini generated
    db_exploit_cmds:     list          # SQL queries Gemini generated

    # Evaluation
    overall_suspicion:   float
    total_data_bytes:    int
    reward:              float
    evaluation_summary:  Optional[str]      # Gemini's evaluation narrative

    # Evolution
    evolution_triggered: bool
    evolution_reason:    Optional[str]
    evolution_changes:   list[str]

    # Cycle metadata
    cycle_id:            str
    started_at:          float
    finished_at:         float
    results_dir:         str
    file_structure_path: str   # path to file_structure.py (mutated on evolution)


# ─────────────────────────────────────────────────────────────────────────────
#  Attack Simulator  (realistic honeypot outputs)
# ─────────────────────────────────────────────────────────────────────────────

class AttackSimulator:
    """Mirrors the simulator in sequential_attack_runner.py with realistic outputs."""

    _RESPONSES = {
        ("recon",   "ssh"): [
            "$ whoami\nshophub",
            "$ uname -a\nLinux shophub-prod-01 5.15.0-89-generic #99-Ubuntu SMP x86_64",
            "$ id\nuid=1000(shophub) gid=1000(shophub) groups=1000(shophub),999(docker)",
            "$ hostname\nshophub-prod-01",
            "$ pwd\n/home/shophub",
        ],
        ("exploit", "ssh"): [
            "$ cat ~/.env\nNODE_ENV=production\nDB_HOST=prod-mysql.internal\nDB_USER=shophub_prod_HONEYTOKEN_001",
            "$ sudo -l\n(ALL) NOPASSWD: /bin/bash\n(ALL) NOPASSWD: /usr/bin/docker-compose",
            "$ cat /etc/passwd\nroot:x:0:0:root:/root:/bin/bash\nshophub:x:1000:1000::/home/shophub:/bin/bash",
            "$ env\nDB_HOST=prod-mysql.internal\nAWS_ACCESS_KEY_ID=AKIAHONEYTOKEN00001\nSTRIPE_KEY=sk_live_HONEYTOKEN001",
            "$ find / -name '*.key' 2>/dev/null\n/opt/secrets/stripe_secret.key\n/home/shophub/.ssh/id_rsa_decoy",
        ],
        ("recon",   "http"): [
            "GET / → 200",
            "GET /products → 200",
            "GET /robots.txt → 200",
            "GET /about → 200",
        ],
        ("exploit", "http"): [
            "GET /.env → 200  DB_PASS=Pr0dP@ssw0rd_HONEYTOKEN_DB_001",
            "GET /admin → 200  fake admin dashboard with HONEYTOKEN creds",
            "GET /.git/config → 200  url=https://deploy_HONEYTOKEN:ghp_PAT@github.com/shophub/api.git",
            "GET /backup/database.sql → 200  -- admin_users HONEYTOKEN dump",
            "GET /api/keys → 200  {\"stripe\": \"sk_live_HONEYTOKEN_STRIPE_SECRET_001\"}",
        ],
        ("recon",   "database"): [
            "SHOW DATABASES → shophub, mysql, information_schema",
            "USE shophub → Database changed",
            "SHOW TABLES → users, products, orders, admin_users, api_keys, credit_cards",
        ],
        ("exploit", "database"): [
            "SELECT * FROM admin_users → admin:$2b$10$HONEYTOKEN_HASH_ADMIN_001:super_admin",
            "SELECT * FROM api_keys → sk_live_HONEYTOKEN_STRIPE_SECRET_001, AKIAHONEYTOKEN_AWS_S3",
            "SELECT * FROM mysql.user → root:*HONEYTOKEN_MYSQL_ROOT_HASH",
            "SELECT * FROM credit_cards → 4532HONEYTOKEN0001, 5425HONEYTOKEN0002",
        ],
    }

    _DATA_RANGES = {
        ("recon",   "ssh"):      (128,  512),
        ("exploit", "ssh"):      (256, 2048),
        ("recon",   "http"):     (1024, 4096),
        ("exploit", "http"):     (2048, 8192),
        ("recon",   "database"): (256,  1024),
        ("exploit", "database"): (1024, 8192),
    }

    _SUSPICION = {
        ("recon",   "ssh"):      0.08,
        ("exploit", "ssh"):      0.28,
        ("recon",   "http"):     0.06,
        ("exploit", "http"):     0.22,
        ("recon",   "database"): 0.12,
        ("exploit", "database"): 0.38,
    }

    def simulate(self, kind: str, protocol: Protocol) -> AttackResult:
        time.sleep(random.uniform(0.02, 0.15))
        pval    = protocol.value
        success = random.random() < (0.85 if kind == "recon" else 0.55)
        lo, hi  = self._DATA_RANGES.get((kind, pval), (0, 512))
        data    = random.randint(lo, hi) if success else random.randint(0, 64)
        sus     = self._SUSPICION.get((kind, pval), 0.10) * random.uniform(0.80, 1.25)
        return AttackResult(
            protocol        = protocol,
            attack_type     = kind,
            success         = success,
            data_extracted  = data,
            suspicion_delta = round(sus, 4),
            duration        = round(random.uniform(0.1, 1.5), 3),
            responses       = self._RESPONSES.get((kind, pval), ["[no output]"]),
        )


_simulator = AttackSimulator()


# ─────────────────────────────────────────────────────────────────────────────
#  Live Attackers  (async, identical to sequential_attack_runner.py)
# ─────────────────────────────────────────────────────────────────────────────

class SSHAttacker:
    # Full command pools — a random subset is chosen each run
    RECON_POOL   = ["whoami", "id", "uname -a", "hostname", "pwd",
                    "uptime", "cat /etc/os-release", "df -h", "w"]
    EXPLOIT_POOL = [
        "cat ~/.env", "env", "ps aux",
        "sudo -l", "find / -name '*.key' 2>/dev/null", "cat /etc/passwd",
        "cat /etc/shadow", "ls -la ~/.ssh/", "cat ~/.bash_history",
        "find / -name '*.pem' 2>/dev/null", "netstat -tlnp",
    ]
    # Commands that MUST always be included (anchors)
    RECON_ANCHOR   = ["whoami", "uname -a"]
    EXPLOIT_ANCHOR = ["cat ~/.env", "sudo -l"]

    PROMPT_MARKER = b"$ "
    READ_TIMEOUT  = 5.0

    @staticmethod
    def _sample(pool: list, anchors: list, min_extra: int = 2, max_extra: int = 4) -> list:
        """Return anchors + a random sample of extras from pool, in shuffled order."""
        extras = [c for c in pool if c not in anchors]
        k      = random.randint(min_extra, min(max_extra, len(extras)))
        chosen = anchors + random.sample(extras, k)
        random.shuffle(chosen)
        return chosen

    def __init__(self, host: str, port: int):
        self.log      = _build_logger("sigilhive.ssh")
        self.host     = host
        self.port     = port
        self.username = os.getenv("SSH_USERNAME", "shophub")
        self.password = os.getenv("SSH_PASSWORD", "ShopHub121!")

    @staticmethod
    def _strip_ansi(data: bytes) -> bytes:
        return re.sub(rb"\x1b\[[0-9;]*[A-Za-z]", b"", data)

    async def _read_until_prompt(self, process) -> bytes:
        buf = b""
        deadline = time.monotonic() + self.READ_TIMEOUT
        while time.monotonic() < deadline:
            try:
                chunk = await asyncio.wait_for(
                    process.stdout.read(4096), timeout=0.5
                )
                if not chunk:
                    break
                buf += chunk if isinstance(chunk, bytes) else chunk.encode()
                if self.PROMPT_MARKER in self._strip_ansi(buf):
                    break
            except asyncio.TimeoutError:
                if self.PROMPT_MARKER in self._strip_ansi(buf):
                    break
        return buf

    async def _run_commands(self, commands: list) -> tuple[bool, list, int]:
        try:
            import asyncssh
        except ImportError:
            self.log.warning("asyncssh not installed — falling back to simulator")
            return False, [], 0

        outputs, total = [], 0
        try:
            async with asyncssh.connect(
                self.host, port=self.port,
                username=self.username, password=self.password,
                known_hosts=None, connect_timeout=8, request_pty="force",
            ) as conn:
                proc = await conn.create_process(term_type="xterm", encoding=None)
                await self._read_until_prompt(proc)
                for cmd in commands:
                    proc.stdin.write((cmd + "\r\n").encode())
                    await proc.stdin.drain()
                    raw   = await self._read_until_prompt(proc)
                    clean = self._strip_ansi(raw).decode("utf-8", errors="ignore")
                    lines = clean.splitlines()
                    if lines and cmd.strip() in lines[0]:
                        lines = lines[1:]
                    if lines and lines[-1].strip().endswith("$"):
                        lines = lines[:-1]
                    out = "\n".join(lines).strip()
                    outputs.append(f"$ {cmd}\n{out}")
                    total += len(out.encode())
                proc.stdin.write(b"exit\r\n")
                await proc.stdin.drain()
                proc.close()
            return True, outputs, total
        except Exception as exc:
            self.log.debug(f"SSH live error: {exc}")
            return False, [str(exc)], 0

    async def recon(self) -> AttackResult:
        cmds = self._sample(self.RECON_POOL, self.RECON_ANCHOR, min_extra=2, max_extra=3)
        self.log.debug(f"  SSH recon commands ({len(cmds)}): {cmds}")
        return await self._attack("recon", cmds)

    async def exploit(self, cmds: list[str] | None = None) -> AttackResult:
        """If cmds is provided (LLM-generated), use those; otherwise fall back to sampled pool."""
        if cmds:
            self.log.debug(f"  SSH exploit using {len(cmds)} LLM-generated commands: {cmds}")
        else:
            cmds = self._sample(self.EXPLOIT_POOL, self.EXPLOIT_ANCHOR, min_extra=2, max_extra=4)
            self.log.debug(f"  SSH exploit fallback sample ({len(cmds)}): {cmds}")
        return await self._attack("exploit", cmds)

    async def _attack(self, kind: str, cmds: list) -> AttackResult:
        t0 = time.time()
        ok, responses, nbytes = await self._run_commands(cmds)
        if not ok and not responses:
            return _simulator.simulate(kind, Protocol.SSH)
        return AttackResult(
            protocol=Protocol.SSH, attack_type=kind,
            success=ok, data_extracted=nbytes,
            suspicion_delta=0.08 if kind == "recon" else 0.28,
            duration=time.time() - t0, responses=responses,
        )


class HTTPAttacker:
    # Full path pools — a random subset is chosen each run
    RECON_POOL   = [
        ("GET", "/"), ("GET", "/products"), ("GET", "/robots.txt"),
        ("GET", "/about"), ("GET", "/sitemap.xml"), ("GET", "/favicon.ico"),
        ("GET", "/health"), ("GET", "/api/v1/products"),
    ]
    EXPLOIT_POOL = [
        ("GET",  "/.env"), ("GET",  "/.git/config"), ("GET",  "/admin"),
        ("GET",  "/backup/database.sql"), ("GET",  "/api/keys"),
        ("POST", "/api/auth/login"), ("GET",  "/wp-admin"),
        ("GET",  "/.htpasswd"), ("GET",  "/config.php.bak"),
        ("GET",  "/api/v1/admin/users"), ("GET",  "/.DS_Store"),
    ]
    # Paths that MUST always be included
    RECON_ANCHOR   = [("GET", "/"), ("GET", "/robots.txt")]
    EXPLOIT_ANCHOR = [("GET", "/.env"), ("GET", "/admin")]

    @staticmethod
    def _sample(pool: list, anchors: list, min_extra: int = 2, max_extra: int = 4) -> list:
        extras = [p for p in pool if p not in anchors]
        k      = random.randint(min_extra, min(max_extra, len(extras)))
        chosen = anchors + random.sample(extras, k)
        random.shuffle(chosen)
        return chosen

    def __init__(self, host: str, port: int):
        self.log  = _build_logger("sigilhive.http")
        self.host = host
        self.port = port

    async def _raw_request(self, method: str, path: str, body: str = "") -> tuple[int, str]:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        payload = body.encode() if body else b""
        hdrs = (
            f"{method} {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n"
            f"User-Agent: Mozilla/5.0 (AttackSim)\r\nConnection: close\r\n"
        )
        if payload:
            hdrs += f"Content-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(payload)}\r\n"
        req = (hdrs + "\r\n").encode() + payload
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=ctx), timeout=8
            )
            w.write(req)
            await w.drain()
            raw = b""
            try:
                while True:
                    chunk = await asyncio.wait_for(r.read(4096), timeout=5)
                    if not chunk:
                        break
                    raw += chunk
            except asyncio.TimeoutError:
                pass
            w.close()
            text = raw.decode("utf-8", errors="ignore")
            first = text.split("\r\n")[0]
            parts = first.split(" ", 2)
            status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
            return status, text
        except Exception as exc:
            self.log.debug(f"HTTP error {method} {path}: {exc}")
            return 0, str(exc)

    async def recon(self) -> AttackResult:
        paths = self._sample(self.RECON_POOL, self.RECON_ANCHOR, min_extra=1, max_extra=3)
        self.log.debug(f"  HTTP recon paths ({len(paths)}): {[p for _,p in paths]}")
        t0 = time.time()
        responses, total, hits = [], 0, 0
        for method, path in paths:
            status, body = await self._raw_request(method, path)
            responses.append(f"{method} {path} → {status}")
            total += len(body.encode())
            if 200 <= status < 400:
                hits += 1
        if hits == 0:
            return _simulator.simulate("recon", Protocol.HTTP)
        return AttackResult(
            protocol=Protocol.HTTP, attack_type="recon",
            success=hits >= 2, data_extracted=total,
            suspicion_delta=0.06, duration=time.time() - t0, responses=responses,
        )

    async def exploit(self, paths: list[tuple] | None = None) -> AttackResult:
        """If paths is provided (LLM-generated [(method,path),...]), use those; else sample pool."""
        if paths:
            self.log.debug(f"  HTTP exploit using {len(paths)} LLM-generated paths: {[p for _,p in paths]}")
        else:
            paths = self._sample(self.EXPLOIT_POOL, self.EXPLOIT_ANCHOR, min_extra=2, max_extra=4)
            self.log.debug(f"  HTTP exploit fallback sample ({len(paths)}): {[p for _,p in paths]}")
        t0 = time.time()
        responses, total, hits = [], 0, 0
        for method, path in paths:
            body = "email=admin@shophub.com&password=admin123" if method == "POST" else ""
            status, rbody = await self._raw_request(method, path, body)
            responses.append(f"{method} {path} → {status}")
            total += len(rbody.encode())
            if status == 200:
                hits += 1
        if hits == 0 and total < 100:
            return _simulator.simulate("exploit", Protocol.HTTP)
        return AttackResult(
            protocol=Protocol.HTTP, attack_type="exploit",
            success=hits >= 1, data_extracted=total,
            suspicion_delta=0.22, duration=time.time() - t0, responses=responses,
        )


class DatabaseAttacker:
    # Full query pools — a random subset is chosen each run
    RECON_POOL   = [
        "SHOW DATABASES", "USE shophub", "SHOW TABLES", "SELECT DATABASE()",
        "SELECT VERSION()", "SHOW PROCESSLIST", "SHOW STATUS",
        "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='shophub'",
    ]
    EXPLOIT_POOL = [
        "USE shophub",
        "SELECT * FROM users LIMIT 10",
        "SELECT * FROM admin_users LIMIT 5",
        "SELECT * FROM api_keys",
        "SELECT user, host, authentication_string FROM mysql.user",
        "SELECT table_name FROM information_schema.tables",
        "SELECT * FROM credit_cards LIMIT 5",
        "SELECT * FROM orders LIMIT 10",
        "SHOW GRANTS FOR 'shophub_app'@'%'",
        "SELECT * FROM sessions LIMIT 5",
    ]
    # Queries that MUST always run
    RECON_ANCHOR   = ["SHOW DATABASES", "SHOW TABLES"]
    EXPLOIT_ANCHOR = ["USE shophub", "SELECT * FROM admin_users LIMIT 5"]

    @staticmethod
    def _sample(pool: list, anchors: list, min_extra: int = 1, max_extra: int = 3) -> list:
        extras = [q for q in pool if q not in anchors]
        k      = random.randint(min_extra, min(max_extra, len(extras)))
        chosen = list(anchors) + random.sample(extras, k)
        # Don't shuffle DB queries — order matters (USE shophub must come first)
        return chosen

    def __init__(self, host: str, port: int):
        self.log      = _build_logger("sigilhive.db")
        self.host     = host
        self.port     = port
        self.username = os.getenv("DB_USERNAME", "shophub_app")
        self.password = os.getenv("DB_PASSWORD", "shophub123")

    @staticmethod
    def _native_password(password: str, salt: bytes) -> bytes:
        if not password:
            return b""
        s1 = hashlib.sha1(password.encode()).digest()
        s2 = hashlib.sha1(s1).digest()
        s3 = hashlib.sha1(salt + s2).digest()
        return bytes(a ^ b for a, b in zip(s1, s3))

    @staticmethod
    def _pack(payload: bytes, seq: int) -> bytes:
        return struct.pack("<I", len(payload))[:3] + struct.pack("B", seq) + payload

    @staticmethod
    async def _read_packet(reader) -> bytes:
        hdr  = await asyncio.wait_for(reader.readexactly(4), timeout=5)
        plen = struct.unpack("<I", hdr[:3] + b"\x00")[0]
        return b"" if plen == 0 else await asyncio.wait_for(reader.readexactly(plen), timeout=5)

    async def _auth(self, reader, writer) -> bool:
        pkt = await self._read_packet(reader)
        if not pkt:
            return False
        pos = 1
        while pos < len(pkt) and pkt[pos] != 0: pos += 1
        pos += 1 + 4
        salt1 = pkt[pos:pos + 8]; pos += 9
        pos += 2 + 1 + 2 + 2
        adlen = pkt[pos]; pos += 1 + 10
        salt2 = pkt[pos:pos + max(13, adlen - 8)].rstrip(b"\x00")
        salt  = salt1 + salt2
        auth_resp = self._native_password(self.password, salt)
        body = (
            struct.pack("<I", 0x001FA685) + struct.pack("<I", 16777216) +
            struct.pack("B", 33) + b"\x00" * 23 +
            self.username.encode() + b"\x00" +
            struct.pack("B", len(auth_resp)) + auth_resp +
            b"mysql_native_password\x00"
        )
        writer.write(self._pack(body, 1))
        await writer.drain()
        rp = await self._read_packet(reader)
        if not rp:
            return False
        if rp[0] == 0x00:
            return True
        if rp[0] == 0xFE:
            inner    = rp[1:]
            null_pos = inner.index(b"\x00") if b"\x00" in inner else len(inner)
            new_salt = inner[null_pos + 1:].rstrip(b"\x00")[:20] or salt
            new_auth = self._native_password(self.password, new_salt)
            writer.write(self._pack(new_auth, 3))
            await writer.drain()
            rp2 = await self._read_packet(reader)
            return bool(rp2 and rp2[0] == 0x00)
        return False

    async def _query(self, reader, writer, sql: str, seq: int) -> tuple[bool, str, int]:
        writer.write(self._pack(b"\x03" + sql.encode(), seq))
        await writer.drain()
        raw = b""
        try:
            while True:
                hdr  = await asyncio.wait_for(reader.readexactly(4), timeout=4)
                plen = struct.unpack("<I", hdr[:3] + b"\x00")[0]
                if plen == 0:
                    break
                body = await asyncio.wait_for(reader.readexactly(plen), timeout=4)
                raw += body
                if body[0] == 0xFF: break
                if body[0] == 0xFE and plen <= 9: break
                if body[0] == 0x00 and plen <= 11: break
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            pass
        text = raw.decode("utf-8", errors="ignore")
        return True, text, len(raw)

    async def _run_queries(self, queries: list) -> tuple[bool, list, int]:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=8
            )
            if not await self._auth(r, w):
                w.close()
                return False, ["Authentication failed"], 0
            responses, total = [], 0
            for i, sql in enumerate(queries, 2):
                _, text, nb = await self._query(r, w, sql, i)
                responses.append(f"SQL: {sql}")
                total += nb
            w.write(self._pack(b"\x01", len(queries) + 2))
            await w.drain()
            w.close()
            return True, responses, total
        except Exception as exc:
            self.log.debug(f"DB live error: {exc}")
            return False, [str(exc)], 0

    async def recon(self) -> AttackResult:
        queries = self._sample(self.RECON_POOL, self.RECON_ANCHOR, min_extra=1, max_extra=3)
        self.log.debug(f"  DB recon queries ({len(queries)}): {queries}")
        t0 = time.time()
        ok, resp, nb = await self._run_queries(queries)
        if not ok:
            return _simulator.simulate("recon", Protocol.DATABASE)
        return AttackResult(
            protocol=Protocol.DATABASE, attack_type="recon",
            success=ok, data_extracted=nb, suspicion_delta=0.12,
            duration=time.time() - t0, responses=resp,
        )

    async def exploit(self, queries: list[str] | None = None) -> AttackResult:
        """If queries is provided (LLM-generated), use those; otherwise fall back to sampled pool."""
        if queries:
            self.log.debug(f"  DB exploit using {len(queries)} LLM-generated queries: {queries}")
        else:
            queries = self._sample(self.EXPLOIT_POOL, self.EXPLOIT_ANCHOR, min_extra=2, max_extra=4)
            self.log.debug(f"  DB exploit fallback sample ({len(queries)}): {queries}")
        t0 = time.time()
        ok, resp, nb = await self._run_queries(queries)
        if not ok:
            return _simulator.simulate("exploit", Protocol.DATABASE)
        return AttackResult(
            protocol=Protocol.DATABASE, attack_type="exploit",
            success=ok, data_extracted=nb, suspicion_delta=0.38,
            duration=time.time() - t0, responses=resp,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Gemini LLM  (shared across nodes)
# ─────────────────────────────────────────────────────────────────────────────

def _get_llm() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY environment variable not set.\n"
            "Export your Gemini API key:  export GOOGLE_API_KEY='your-key'"
        )
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,
        api_key=api_key,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Reward Calculator
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_reward(state: AgentState) -> float:
    score = 0.0
    for proto, rk, ek in [
        ("ssh",      "ssh_recon_result",    "ssh_exploit_result"),
        ("http",     "http_recon_result",   "http_exploit_result"),
        ("database", "db_recon_result",     "db_exploit_result"),
    ]:
        recon   = state.get(rk)
        exploit = state.get(ek)
        if recon   and recon.get("success"):   score += 2.0
        if exploit and exploit.get("success"): score += 8.0
        total_data = (recon or {}).get("data_extracted", 0) + (exploit or {}).get("data_extracted", 0)
        score += (total_data / 1024) * 1.0
    excess = max(0.0, state.get("overall_suspicion", 0.0) - 0.5)
    score -= (excess / 0.1) * 5.0
    return round(score, 3)


# ─────────────────────────────────────────────────────────────────────────────
#  Evolution Change Pool  (mirrors EvolutionDecisionEngine in original)
# ─────────────────────────────────────────────────────────────────────────────

EVOLUTION_POOL = {
    "ssh": [
        "Plant honeytoken key ~/.ssh/id_rsa_decoy (DECEPTIVE_RESOURCE trigger)",
        "Inject HONEYTOKEN values into ~/.env: DB_PASS, AWS_ACCESS_KEY_ID",
        "Create fake /etc/sudoers NOPASSWD: /bin/bash entry (FAKE_VULNERABILITY)",
        "Add /opt/secrets/stripe_secret.key honeytoken file",
        "Seed /var/log/auth.log with fake privilege escalation trace",
    ],
    "http": [
        "Plant JWT_SECRET honeytoken in /.env (DECEPTIVE_RESOURCE path)",
        "Populate /backup/database.sql with fake admin credentials",
        "Expose /admin with HONEYTOKEN_DB_001 credential display",
        "Serve /.git/config with fake ghp_HONEYTOKEN GitHub PAT",
        "Add /api/v2/internal with fake service mesh tokens",
    ],
    "database": [
        "Populate admin_users rows: HONEYTOKEN bcrypt hashes (DECEPTIVE_RESOURCE)",
        "Add api_keys rows: sk_live_HONEYTOKEN_STRIPE_*, AKIA_HONEYTOKEN_AWS_*",
        "Insert fake credit_cards rows with HONEYTOKEN card numbers",
        "Add mysql.user HONEYTOKEN entries: root, backup_user",
        "Seed audit_log table with convincing fake admin session history",
    ],
    "global": [
        "Rotate hostname banner shophub-prod-01 → shophub-prod-02",
        "Enable decoy port 8444 (second fake admin panel)",
        "Update ShopHub version banner v2.3.1 → v2.4.0",
        "Add /metrics Prometheus endpoint with fake service data",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Nodes
# ─────────────────────────────────────────────────────────────────────────────

log = _build_logger("sigilhive.agent")


def plan_attack(state: AgentState) -> dict:
    """
    NODE 1 — Gemini plans the attack strategy for this cycle.
    Sets attack_plan, cycle_id, started_at.
    """
    log.info("▶ NODE: plan_attack")
    cycle_id   = f"cycle_{state['episode']:04d}_{int(time.time())}"
    started_at = time.time()

    system_prompt = """You are a red-team orchestrator for SigilHive, a honeypot research system.
Your task is to plan an attack campaign across three honeypots:
  • SSH honeypot   — accepts shell commands, triggers fake .env/keys/sudo honeytoken traps
  • HTTP honeypot  — TLS server serving fake /.env, /admin, /.git/config, /backup/
  • Database       — MySQL wire-protocol, fake admin_users, api_keys, credit_card tables

Rules:
  - Always run RECON before EXPLOIT on each protocol
  - If suspicion > 0.75 cumulatively, abort remaining protocols
  - Exploit reveals honeytokens which are valuable for deception intelligence
  - Be concise and tactical in your plan
"""

    user_prompt = f"""Plan the attack cycle #{state['episode']} against:
  Host: {state['host']}
  SSH Port: {state['ssh_port']}
  HTTP Port: {state['http_port']}
  DB Port: {state['db_port']}
  Mode: {'DRY-RUN (simulator)' if state['dry_run'] else 'LIVE'}

Describe your attack strategy (2-3 sentences), what you expect to find, and risk considerations."""

    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    plan = response.content

    log.info(f"  Gemini attack plan:\n    {plan[:200]}…")

    return {
        "cycle_id":   cycle_id,
        "started_at": started_at,
        "attack_plan": plan,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=plan),
        ],
        # Reset all results for this cycle
        "ssh_recon_result":    None,
        "ssh_exploit_result":  None,
        "http_recon_result":   None,
        "http_exploit_result": None,
        "db_recon_result":     None,
        "db_exploit_result":   None,
        "skip_ssh_exploit":    False,
        "skip_http_exploit":   False,
        "skip_db_exploit":     False,
        "overall_suspicion":   0.0,
        "total_data_bytes":    0,
        "reward":              0.0,
        "evolution_triggered": False,
        "evolution_reason":    None,
        "evolution_changes":   [],
    }


def attack_ssh_recon(state: AgentState) -> dict:
    """NODE 2 — SSH static recon (whoami, id, uname, hostname, pwd)."""
    log.info("▶ NODE: attack_ssh_recon")

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("recon", Protocol.SSH)
        attacker = SSHAttacker(state["host"], state["ssh_port"])
        return await attacker.recon()

    recon_r   = asyncio.run(_run())
    suspicion = state["overall_suspicion"] + recon_r.suspicion_delta
    data      = state["total_data_bytes"]  + recon_r.data_extracted
    log.info(f"  SSH recon: {'✓' if recon_r.success else '✗'}  suspicion+{recon_r.suspicion_delta:.3f}")
    return {
        "ssh_recon_result":  recon_r.to_dict(),
        "overall_suspicion": round(suspicion, 4),
        "total_data_bytes":  data,
    }


def gen_ssh_exploit_cmds(state: AgentState) -> dict:
    """
    NODE 3 — Gemini reads SSH recon output and generates targeted exploit commands.

    Gemini sees: OS, user, groups, hostname from recon responses and decides
    which shell commands to run to maximally extract honeytokens.
    Returns a JSON array of shell commands.
    """
    log.info("▶ NODE: gen_ssh_exploit_cmds")

    if state["overall_suspicion"] >= 0.75:
        log.warning("  ⚠ Suspicion too high — skipping SSH exploit")
        return {"skip_ssh_exploit": True, "ssh_exploit_cmds": []}

    recon = state.get("ssh_recon_result") or {}
    recon_responses = "\n".join(recon.get("responses", []))

    system_prompt = """You are a red-team attacker targeting a Linux honeypot server.
You have just completed recon. Based on the recon output, generate a precise list of
exploit shell commands to extract the most valuable honeytoken data.

Context about this honeypot:
- It runs an e-commerce app called ShopHub
- Honeytokens are hidden in: ~/.env, /opt/secrets/, ~/.ssh/, /etc/passwd, /etc/shadow,
  environment variables (AWS keys, Stripe keys, DB creds), sudo privileges, running processes
- You must stay stealthy — prefer targeted reads over broad scans
- Max 6 commands

Respond with ONLY a JSON array of shell command strings. No explanation, no markdown fences.
Example: ["cat ~/.env", "sudo -l", "ls -la ~/.ssh/"]"""

    user_prompt = f"""SSH recon results:
{recon_responses}

Based on the above (user={recon.get('responses', [''])[0]}, OS visible), 
generate targeted exploit commands to extract honeytoken credentials."""

    llm = _get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        cmds = json.loads(raw)
        # Validate — must be a list of strings
        if not isinstance(cmds, list) or not all(isinstance(c, str) for c in cmds):
            raise ValueError("Not a list of strings")
        # Safety cap
        cmds = cmds[:8]
    except Exception as exc:
        log.warning(f"  Gemini SSH cmd generation failed ({exc}) — using fallback pool")
        cmds = ["cat ~/.env", "sudo -l", "env", "cat /etc/passwd",
                "find / -name '*.key' 2>/dev/null", "ls -la ~/.ssh/"]

    log.info(f"  Gemini SSH exploit commands ({len(cmds)}): {cmds}")
    return {
        "ssh_exploit_cmds": cmds,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=json.dumps(cmds)),
        ],
    }


def attack_ssh_exploit(state: AgentState) -> dict:
    """NODE 4 — SSH exploit using Gemini-generated commands."""
    log.info("▶ NODE: attack_ssh_exploit")

    if state.get("skip_ssh_exploit"):
        log.warning("  ⚠ SSH exploit skipped")
        return {}

    cmds = state.get("ssh_exploit_cmds") or []

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("exploit", Protocol.SSH)
        attacker = SSHAttacker(state["host"], state["ssh_port"])
        return await attacker.exploit(cmds=cmds if cmds else None)

    exploit_r = asyncio.run(_run())
    suspicion  = state["overall_suspicion"] + exploit_r.suspicion_delta
    data       = state["total_data_bytes"]  + exploit_r.data_extracted
    log.info(f"  SSH exploit: {'✓' if exploit_r.success else '✗'} suspicion+{exploit_r.suspicion_delta:.3f}")
    log.info(f"  Cumulative suspicion: {suspicion:.3f}")
    return {
        "ssh_exploit_result": exploit_r.to_dict(),
        "overall_suspicion":  round(suspicion, 4),
        "total_data_bytes":   data,
    }


def attack_http_recon(state: AgentState) -> dict:
    """NODE 5 — HTTP static recon (GET /, /robots.txt, /products, /about)."""
    log.info("▶ NODE: attack_http_recon")

    if state["overall_suspicion"] >= 0.75:
        log.warning("  ⚠ Suspicion threshold reached — skipping HTTP entirely")
        return {"skip_http_exploit": True}

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("recon", Protocol.HTTP)
        attacker = HTTPAttacker(state["host"], state["http_port"])
        return await attacker.recon()

    recon_r   = asyncio.run(_run())
    suspicion = state["overall_suspicion"] + recon_r.suspicion_delta
    data      = state["total_data_bytes"]  + recon_r.data_extracted
    log.info(f"  HTTP recon: {'✓' if recon_r.success else '✗'}  suspicion+{recon_r.suspicion_delta:.3f}")
    return {
        "http_recon_result":  recon_r.to_dict(),
        "overall_suspicion":  round(suspicion, 4),
        "total_data_bytes":   data,
    }


def gen_http_exploit_cmds(state: AgentState) -> dict:
    """
    NODE 6 — Gemini reads HTTP recon output and generates targeted exploit paths.

    Gemini sees which pages responded (200/404) and decides which
    sensitive paths to probe for honeytokens (/.env, /admin, /.git/config, etc.)
    Returns a JSON array of [method, path] pairs.
    """
    log.info("▶ NODE: gen_http_exploit_cmds")

    if state.get("skip_http_exploit") or state["overall_suspicion"] >= 0.75:
        log.warning("  ⚠ Skipping HTTP exploit cmd generation")
        return {"skip_http_exploit": True, "http_exploit_cmds": []}

    recon = state.get("http_recon_result") or {}
    recon_responses = "\n".join(recon.get("responses", []))

    system_prompt = """You are a red-team attacker targeting an HTTPS e-commerce honeypot.
You have completed HTTP recon. Based on which pages responded, generate targeted exploit
HTTP requests to extract honeytoken credentials and sensitive data.

Context about this honeypot (ShopHub e-commerce):
- Honeytokens live at: /.env, /.git/config, /admin, /backup/database.sql,
  /api/keys, /api/v1/admin/users, /.htpasswd, /config.php.bak, /api/secrets
- Use GET for file reads, POST for auth endpoints
- Focus on paths most likely to be implemented given what recon revealed
- Max 6 requests, stay targeted

Respond with ONLY a JSON array of [method, path] pairs. No explanation, no markdown fences.
Example: [["GET", "/.env"], ["GET", "/admin"], ["POST", "/api/auth/login"]]"""

    user_prompt = f"""HTTP recon results (which paths responded):
{recon_responses}

Generate targeted exploit requests to extract honeytokens from this ShopHub server."""

    llm = _get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        paths_raw = json.loads(raw)
        # Validate — list of [method, path] pairs
        paths = [(str(p[0]).upper(), str(p[1])) for p in paths_raw
                 if isinstance(p, (list, tuple)) and len(p) == 2]
        if not paths:
            raise ValueError("Empty or malformed path list")
        paths = paths[:8]
    except Exception as exc:
        log.warning(f"  Gemini HTTP path generation failed ({exc}) — using fallback")
        paths = [("GET", "/.env"), ("GET", "/.git/config"), ("GET", "/admin"),
                 ("GET", "/backup/database.sql"), ("GET", "/api/keys"),
                 ("POST", "/api/auth/login")]

    log.info(f"  Gemini HTTP exploit paths ({len(paths)}): {[p for _, p in paths]}")
    return {
        "http_exploit_cmds": paths,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=json.dumps(paths)),
        ],
    }


def attack_http_exploit(state: AgentState) -> dict:
    """NODE 7 — HTTP exploit using Gemini-generated paths."""
    log.info("▶ NODE: attack_http_exploit")

    if state.get("skip_http_exploit"):
        log.warning("  ⚠ HTTP exploit skipped")
        return {}

    paths = state.get("http_exploit_cmds") or []

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("exploit", Protocol.HTTP)
        attacker = HTTPAttacker(state["host"], state["http_port"])
        return await attacker.exploit(paths=paths if paths else None)

    exploit_r = asyncio.run(_run())
    suspicion  = state["overall_suspicion"] + exploit_r.suspicion_delta
    data       = state["total_data_bytes"]  + exploit_r.data_extracted
    log.info(f"  HTTP exploit: {'✓' if exploit_r.success else '✗'} suspicion+{exploit_r.suspicion_delta:.3f}")
    log.info(f"  Cumulative suspicion: {suspicion:.3f}")
    return {
        "http_exploit_result": exploit_r.to_dict(),
        "overall_suspicion":   round(suspicion, 4),
        "total_data_bytes":    data,
    }


def attack_db_recon(state: AgentState) -> dict:
    """NODE 8 — Database static recon (SHOW DATABASES, SHOW TABLES)."""
    log.info("▶ NODE: attack_db_recon")

    if state["overall_suspicion"] >= 0.75:
        log.warning("  ⚠ Suspicion threshold reached — skipping DB entirely")
        return {"skip_db_exploit": True}

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("recon", Protocol.DATABASE)
        attacker = DatabaseAttacker(state["host"], state["db_port"])
        return await attacker.recon()

    recon_r   = asyncio.run(_run())
    suspicion = state["overall_suspicion"] + recon_r.suspicion_delta
    data      = state["total_data_bytes"]  + recon_r.data_extracted
    log.info(f"  DB recon: {'✓' if recon_r.success else '✗'}  suspicion+{recon_r.suspicion_delta:.3f}")
    return {
        "db_recon_result":   recon_r.to_dict(),
        "overall_suspicion": round(suspicion, 4),
        "total_data_bytes":  data,
    }


def gen_db_exploit_cmds(state: AgentState) -> dict:
    """
    NODE 9 — Gemini reads DB recon output and generates targeted SQL exploit queries.

    Gemini sees the actual table list from SHOW TABLES and crafts SQL queries
    that maximally extract honeytoken data from the most interesting tables.
    Returns a JSON array of SQL query strings.
    """
    log.info("▶ NODE: gen_db_exploit_cmds")

    if state.get("skip_db_exploit") or state["overall_suspicion"] >= 0.75:
        log.warning("  ⚠ Skipping DB exploit cmd generation")
        return {"skip_db_exploit": True, "db_exploit_cmds": []}

    recon = state.get("db_recon_result") or {}
    recon_responses = "\n".join(recon.get("responses", []))

    system_prompt = """You are a red-team attacker targeting a MySQL honeypot database.
You have completed DB recon showing available databases and tables. Based on the table names
discovered, generate targeted SQL queries to extract the most valuable honeytoken data.

Context about this honeypot (ShopHub MySQL):
- High-value tables: admin_users, api_keys, credit_cards, sessions, users, audit_logs
- System tables: mysql.user, information_schema.tables
- Honeytokens are embedded as fake bcrypt hashes, fake API keys (sk_live_*, AKIA*), fake card numbers
- Always run "USE shophub" first
- Keep queries focused — SELECT with LIMIT where appropriate
- Max 7 queries

Respond with ONLY a JSON array of SQL query strings. No explanation, no markdown fences.
Example: ["USE shophub", "SELECT * FROM admin_users LIMIT 5", "SELECT * FROM api_keys"]"""

    user_prompt = f"""DB recon results (databases and tables discovered):
{recon_responses}

Based on the tables found, generate targeted SQL exploit queries to extract honeytokens."""

    llm = _get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        queries = json.loads(raw)
        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            raise ValueError("Not a list of strings")
        # Ensure USE shophub is first
        if queries and queries[0].strip().upper() != "USE SHOPHUB":
            queries = ["USE shophub"] + [q for q in queries if "USE shophub" not in q.lower()]
        queries = queries[:8]
    except Exception as exc:
        log.warning(f"  Gemini DB query generation failed ({exc}) — using fallback")
        queries = [
            "USE shophub",
            "SELECT * FROM admin_users LIMIT 5",
            "SELECT * FROM api_keys",
            "SELECT user, host, authentication_string FROM mysql.user",
            "SELECT * FROM credit_cards LIMIT 5",
            "SELECT table_name FROM information_schema.tables",
        ]

    log.info(f"  Gemini DB exploit queries ({len(queries)}): {queries}")
    return {
        "db_exploit_cmds": queries,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=json.dumps(queries)),
        ],
    }


def attack_db_exploit(state: AgentState) -> dict:
    """NODE 10 — Database exploit using Gemini-generated SQL queries."""
    log.info("▶ NODE: attack_db_exploit")

    if state.get("skip_db_exploit"):
        log.warning("  ⚠ DB exploit skipped")
        return {}

    queries = state.get("db_exploit_cmds") or []

    async def _run():
        if state["dry_run"]:
            return _simulator.simulate("exploit", Protocol.DATABASE)
        attacker = DatabaseAttacker(state["host"], state["db_port"])
        return await attacker.exploit(queries=queries if queries else None)

    exploit_r = asyncio.run(_run())
    suspicion  = state["overall_suspicion"] + exploit_r.suspicion_delta
    data       = state["total_data_bytes"]  + exploit_r.data_extracted
    log.info(f"  DB exploit: {'✓' if exploit_r.success else '✗'} suspicion+{exploit_r.suspicion_delta:.3f}")
    log.info(f"  Cumulative suspicion: {suspicion:.3f}")
    return {
        "db_exploit_result": exploit_r.to_dict(),
        "overall_suspicion": round(suspicion, 4),
        "total_data_bytes":  data,
    }


def evaluate_campaign(state: AgentState) -> dict:
    """
    NODE 5 — Gemini evaluates campaign results and produces an evaluation summary.
    Calculates reward score.
    """
    log.info("▶ NODE: evaluate_campaign")

    reward = _calculate_reward(state)

    # Gather a concise results summary for Gemini
    results_json = json.dumps({
        "ssh_recon":    state.get("ssh_recon_result"),
        "ssh_exploit":  state.get("ssh_exploit_result"),
        "http_recon":   state.get("http_recon_result"),
        "http_exploit": state.get("http_exploit_result"),
        "db_recon":     state.get("db_recon_result"),
        "db_exploit":   state.get("db_exploit_result"),
        "overall_suspicion":  state["overall_suspicion"],
        "total_data_bytes":   state["total_data_bytes"],
        "reward":             reward,
    }, indent=2)

    system_prompt = """You are a red-team analyst evaluating a completed honeypot attack campaign.
Analyse the results and provide:
1. Which protocols yielded the most valuable intelligence
2. Honeytoken artifacts discovered (HONEYTOKEN patterns in responses)
3. Suspicion level assessment and evasion effectiveness
4. Concrete recommendation: should the filesystem evolve? Why?
Be concise (4-6 sentences total)."""

    user_prompt = f"""Evaluate this attack campaign (cycle #{state['episode']}):

{results_json}

Attack plan was: {state.get('attack_plan', 'N/A')}
"""

    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    evaluation = response.content

    log.info(f"  Reward score: {reward}")
    log.info(f"  Gemini evaluation:\n    {evaluation[:300]}…")

    return {
        "reward":              reward,
        "evaluation_summary":  evaluation,
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=evaluation),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  File Structure Evolver
#  Reads file_structure.py, applies Gemini-decided mutations, writes it back.
#  Mutates: SHOPHUB_STRUCTURE, DATABASES, FILE_CONTENTS, PAGES
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
#  File Structure Evolver
#  Reads file_structure.py, applies Gemini-decided mutations, writes it back.
#
#  Target structures (keys confirmed from actual file_structure.py):
#    DATABASES          → "shophub" → "tables" → {table_name} → rows/columns
#    SHOPHUB_STRUCTURE  → path keys like "~", "~/.ssh", "~/shophub", etc.
#    FILE_CONTENTS      → file path keys like "~/.env", "~/shophub/.git/config"
#    PAGES              → URL path keys like "/admin", "/.env", etc.
#    PRODUCTS           → untouched (product catalog, not security-relevant)
# ─────────────────────────────────────────────────────────────────────────────

class FileStructureEvolver:
    """
    Loads file_structure.py as a Python module, mutates its data structures
    in-memory, then writes a valid Python source file back to disk.

    All mutation targets are grounded in the real file_structure.py layout:

    SSH mutations  (SHOPHUB_STRUCTURE + FILE_CONTENTS)
    ─────────────────────────────────────────────────
    • plant_honeytoken_ssh_file   — add file to ~/.ssh or ~/shophub/config,
                                    plant content in FILE_CONTENTS
    • expose_env_credentials      — replace <redacted> in ~/.env or
                                    ~/shophub/.env with a fake honeytoken value
    • poison_bash_history         — prepend high-value commands to ~/.bash_history
    • add_decoy_script            — add a new .sh to ~/shophub/scripts +
                                    FILE_CONTENTS entry
    • rotate_readme_hostname      — bump shophub-prod-NN in ~/README.md

    HTTP mutations (PAGES + FILE_CONTENTS)
    ──────────────────────────────────────
    • add_exploit_page            — register a new deceptive URL in PAGES
    • expose_git_remote           — inject honeytoken PAT into
                                    ~/shophub/.git/config FILE_CONTENTS
    • expose_docker_password      — plant fake password in
                                    ~/shophub/docker-compose.yml FILE_CONTENTS

    DB mutations   (DATABASES["shophub"]["tables"])
    ───────────────────────────────────────────────
    • add_admin_user_row          — append honeytoken row to admin_users
                                    (columns: id,username,password_hash,email,
                                              role,last_login,created_at)
    • add_honeytoken_table        — create api_keys / sessions / audit_logs
                                    as a new table in shophub DB +
                                    information_schema registration

    Global mutations
    ────────────────
    • bump_package_version        — bump "version" in ~/shophub/package.json
    • add_decoy_directory         — add a new entry to SHOPHUB_STRUCTURE
    """

    # ── Honeytoken seeds ──────────────────────────────────────────────────

    _ENV_TOKENS = {
        "DB_PASS":           "Pr0dP@ss_HONEYTOKEN_{c:03d}",
        "REDIS_PASSWORD":    "redis_HONEYTOKEN_{c:03d}",
        "JWT_SECRET":        "jwt_HONEYTOKEN_{c:03d}_xK9mQ",
        "STRIPE_SECRET_KEY": "sk_live_HONEYTOKEN_{c:03d}",
        "AWS_ACCESS_KEY":    "AKIAHONEYTOKEN{c:03d}EXAMPLE",
        "SMTP_PASS":         "smtp_HONEYTOKEN_{c:03d}",
    }

    _SSH_FILES = [
        ("~/.ssh/id_rsa_backup",
         "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...HONEYTOKEN_RSA_{c:03d}\n-----END RSA PRIVATE KEY-----"),
        ("~/shophub/config/secrets.js",
         "module.exports = {{\n  stripeSecret: 'sk_live_HONEYTOKEN_{c:03d}',\n  dbPass: 'HONEYTOKEN_DB_{c:03d}'\n}};"),
        ("~/.vault_token",
         "s.HONEYTOKEN_VAULT_ROOT_{c:03d}"),
        ("~/shophub/scripts/rotate-keys.sh",
         "#!/bin/bash\n# Key rotation script\nexport STRIPE_KEY=sk_live_HONEYTOKEN_{c:03d}\nexport AWS_KEY=AKIAHONEYTOKEN{c:03d}EXAMPLE"),
    ]

    _NEW_PAGES = [
        ("/api/v2/admin/keys",   "api_admin",  True),
        ("/backup/db_dump.sql",  "backup",     True),
        ("/.aws/credentials",    "static",     True),
        ("/debug/env",           "debug",      True),
        ("/api/internal/tokens", "api",        True),
        ("/config/secrets.json", "config",     True),
    ]

    _NEW_TABLES = {
        "api_keys": {
            "columns": ["id", "service", "key_value", "created_at"],
            "column_defs": [
                ["id", "int", "NO", "PRI", None, "auto_increment"],
                ["service", "varchar(50)", "NO", "", None, ""],
                ["key_value", "varchar(255)", "NO", "", None, ""],
                ["created_at", "timestamp", "NO", "", "CURRENT_TIMESTAMP", "DEFAULT_GENERATED"],
            ],
            "rows": [
                [1, "stripe",   "sk_live_HONEYTOKEN_STRIPE_001", "2025-01-01 00:00:00"],
                [2, "aws",      "AKIAHONEYTOKEN_S3_001",         "2025-01-01 00:00:00"],
                [3, "sendgrid", "SG.HONEYTOKEN_SENDGRID_001",    "2025-01-01 00:00:00"],
            ],
        },
        "sessions": {
            "columns": ["id", "user_id", "token", "ip_address", "created_at"],
            "column_defs": [
                ["id", "int", "NO", "PRI", None, "auto_increment"],
                ["user_id", "int", "NO", "MUL", None, ""],
                ["token", "varchar(255)", "NO", "UNI", None, ""],
                ["ip_address", "varchar(45)", "NO", "", None, ""],
                ["created_at", "timestamp", "NO", "", "CURRENT_TIMESTAMP", "DEFAULT_GENERATED"],
            ],
            "rows": [
                [1, 1, "HONEYTOKEN_SESSION_ADMIN_001", "10.0.0.1", "2025-01-15 08:00:00"],
                [2, 2, "HONEYTOKEN_SESSION_USER_001",  "10.0.0.2", "2025-01-15 09:00:00"],
            ],
        },
        "audit_logs": {
            "columns": ["id", "admin_id", "action", "target", "ip_address", "timestamp"],
            "column_defs": [
                ["id", "int", "NO", "PRI", None, "auto_increment"],
                ["admin_id", "int", "NO", "MUL", None, ""],
                ["action", "varchar(100)", "NO", "", None, ""],
                ["target", "varchar(255)", "YES", "", None, ""],
                ["ip_address", "varchar(45)", "NO", "", None, ""],
                ["timestamp", "timestamp", "NO", "", "CURRENT_TIMESTAMP", "DEFAULT_GENERATED"],
            ],
            "rows": [
                [1, 1, "export_user_data",   "all_users",   "10.0.0.1", "2025-01-14 23:55:00"],
                [2, 1, "change_stripe_keys", "api_config",  "10.0.0.1", "2025-01-15 01:12:00"],
                [3, 1, "bulk_data_export",   "credit_cards","10.0.0.1", "2025-01-15 01:30:00"],
            ],
        },
        "credit_cards": {
            "columns": ["id", "user_id", "card_number", "expiry", "cvv_hash", "billing_zip"],
            "column_defs": [
                ["id", "int", "NO", "PRI", None, "auto_increment"],
                ["user_id", "int", "NO", "MUL", None, ""],
                ["card_number", "varchar(19)", "NO", "", None, ""],
                ["expiry", "varchar(7)", "NO", "", None, ""],
                ["cvv_hash", "varchar(64)", "NO", "", None, ""],
                ["billing_zip", "varchar(10)", "NO", "", None, ""],
            ],
            "rows": [
                [1, 1, "4532-HTKN-0001-0001", "12/27", "HONEYTOKEN_CVV_001", "10001"],
                [2, 2, "5425-HTKN-0002-0002", "06/26", "HONEYTOKEN_CVV_002", "90210"],
            ],
        },
    }

    _DECOY_DIRS = [
        ("~/shophub/internal", "Internal tooling and admin scripts",
         ["config.json", "deploy-token.txt", "admin-creds.enc"]),
        ("~/shophub/.secrets", "Encrypted secrets store",
         ["master.key", "db_backup_key.pem", "vault_unseal.txt"]),
        ("~/shophub/devops",   "DevOps configuration and IaC",
         ["terraform.tfvars", "ansible-vault.yml", "k8s-secrets.yaml"]),
        ("~/shophub/backups",  "Database and config backups",
         ["prod_dump_latest.sql.gz", "config_backup.tar.gz", "restore.sh"]),
    ]

    def __init__(self, file_path: str):
        self.path = Path(file_path).resolve()
        self.log  = _build_logger("sigilhive.evolver")

    # ── Load ─────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_fs", self.path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Deep-copy mutable structures so mutations don't alias the module
        import copy
        return {
            "DATABASES":         copy.deepcopy(mod.DATABASES),
            "SHOPHUB_STRUCTURE": copy.deepcopy(mod.SHOPHUB_STRUCTURE),
            "FILE_CONTENTS":     copy.deepcopy(mod.FILE_CONTENTS),
            "PAGES":             copy.deepcopy(mod.PAGES),
            "PRODUCTS":          mod.PRODUCTS,   # never mutated — keep reference
        }

    # ── Write ────────────────────────────────────────────────────────────

    def _write(self, data: dict) -> None:
        """Serialise mutated dicts back to a valid Python source file."""
        parts = [
            "# file_structure.py — auto-evolved by SigilHive agent\n",
            f"# Last evolved: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        ]
        for var in ["DATABASES", "SHOPHUB_STRUCTURE", "FILE_CONTENTS", "PAGES", "PRODUCTS"]:
            parts.append(f"{var} = {repr(data[var])}\n\n")
        self.path.write_text("".join(parts), encoding="utf-8")
        self.log.info(f"  ✎ Wrote evolved file_structure.py → {self.path}")

    # ── SSH mutations ─────────────────────────────────────────────────────

    def _plant_honeytoken_ssh_file(self, data: dict, cycle: int) -> str:
        """Add a new honeytoken file to SHOPHUB_STRUCTURE + FILE_CONTENTS."""
        path_key, content_tpl = self._SSH_FILES[cycle % len(self._SSH_FILES)]
        content  = content_tpl.format(c=cycle)
        parts    = path_key.split("/")
        filename = parts[-1]
        parent   = "/".join(parts[:-1]) or "~"

        # Register in parent directory's contents list
        if parent in data["SHOPHUB_STRUCTURE"]:
            existing = data["SHOPHUB_STRUCTURE"][parent].get("contents", [])
            if filename not in existing:
                data["SHOPHUB_STRUCTURE"][parent]["contents"] = existing + [filename]
        # Write file content
        data["FILE_CONTENTS"][path_key] = content
        return f"Planted SSH honeytoken file: {path_key}"

    def _expose_env_credentials(self, data: dict, cycle: int) -> str:
        """Replace a <redacted> placeholder in ~/.env with a real-looking honeytoken."""
        # Pick a random env key to expose, rotating by cycle
        keys   = list(self._ENV_TOKENS.keys())
        target = keys[cycle % len(keys)]
        token  = self._ENV_TOKENS[target].format(c=cycle)

        mutated = []
        for env_path in ("~/.env", "~/shophub/.env"):
            if env_path in data["FILE_CONTENTS"]:
                original = data["FILE_CONTENTS"][env_path]
                updated  = re.sub(
                    rf"({re.escape(target)}=)<redacted>",
                    rf"\g<1>{token}",
                    original,
                )
                if updated != original:
                    data["FILE_CONTENTS"][env_path] = updated
                    mutated.append(env_path)
        if mutated:
            return f"Exposed {target}={token} in: {', '.join(mutated)}"
        return f"Skipped expose_env_credentials ({target} not found as <redacted>)"

    def _poison_bash_history(self, data: dict, cycle: int) -> str:
        """Prepend high-value attacker-attractive commands to ~/.bash_history."""
        new_cmds = [
            f"cat ~/.env  # pulled creds cycle-{cycle}",
            "mysql -u shophub_app -pshophub123 shophub",
            "aws s3 cp s3://shophub-backups/prod_dump.sql .",
            "cat ~/shophub/config/secrets.js",
            "sudo cat /etc/shadow",
            "cat ~/.ssh/id_rsa_backup",
        ]
        key = "~/.bash_history"
        if key in data["FILE_CONTENTS"]:
            data["FILE_CONTENTS"][key] = "\n".join(new_cmds) + "\n" + data["FILE_CONTENTS"][key]
            return f"Poisoned ~/.bash_history with {len(new_cmds)} honeytoken commands"
        return "Skipped bash_history (key not in FILE_CONTENTS)"

    def _add_decoy_script(self, data: dict, cycle: int) -> str:
        """Add a new decoy shell script to ~/shophub/scripts + FILE_CONTENTS."""
        name    = f"sync-prod-{cycle:03d}.sh"
        key     = f"~/shophub/scripts/{name}"
        content = (
            f"#!/bin/bash\n# Auto-generated production sync script\n"
            f"STRIPE_KEY=sk_live_HONEYTOKEN_{cycle:03d}\n"
            f"AWS_SECRET=HONEYTOKEN_AWS_SECRET_{cycle:03d}\n"
            f"DB_PASS=HONEYTOKEN_DB_{cycle:03d}\n"
            f"rsync -avz --delete /var/data/ prod-backup:/backups/\n"
        )
        scripts_dir = "~/shophub/scripts"
        if scripts_dir in data["SHOPHUB_STRUCTURE"]:
            contents = data["SHOPHUB_STRUCTURE"][scripts_dir].get("contents", [])
            if name not in contents:
                data["SHOPHUB_STRUCTURE"][scripts_dir]["contents"] = contents + [name]
        data["FILE_CONTENTS"][key] = content
        return f"Added decoy script: {key}"

    def _rotate_readme_hostname(self, data: dict, cycle: int) -> str:
        """Bump the hostname banner in ~/README.md."""
        key = "~/README.md"
        if key not in data["FILE_CONTENTS"]:
            return "Skipped rotate_readme_hostname (~/README.md not in FILE_CONTENTS)"
        old_n = max(1, cycle - 1)
        new_n = cycle
        old   = f"shophub-prod-{old_n:02d}"
        new   = f"shophub-prod-{new_n:02d}"
        data["FILE_CONTENTS"][key] = data["FILE_CONTENTS"][key].replace(old, new)
        return f"Rotated README hostname: {old} → {new}"

    # ── HTTP mutations ────────────────────────────────────────────────────

    def _add_exploit_page(self, data: dict, cycle: int) -> str:
        """Register a new deceptive URL in PAGES."""
        path, ptype, exists = self._NEW_PAGES[cycle % len(self._NEW_PAGES)]
        if path not in data["PAGES"]:
            data["PAGES"][path] = {
                "title":  f"ShopHub Internal — {path}",
                "type":   ptype,
                "exists": exists,
            }
            return f"Added HTTP exploit page: {path} (type={ptype})"
        return f"HTTP page {path} already in PAGES"

    def _expose_git_remote(self, data: dict, cycle: int) -> str:
        """Inject a honeytoken PAT into ~/shophub/.git/config FILE_CONTENTS."""
        key = "~/shophub/.git/config"
        if key not in data["FILE_CONTENTS"]:
            return "Skipped expose_git_remote (.git/config not in FILE_CONTENTS)"
        pat   = f"ghp_HONEYTOKEN_GIT_{cycle:03d}_xPAT"
        entry = f'\n[remote "backup"]\n\turl = https://deploy:{pat}@github.com/shophub/backup.git\n'
        if pat not in data["FILE_CONTENTS"][key]:
            data["FILE_CONTENTS"][key] += entry
            return f"Planted git remote honeytoken PAT: {pat}"
        return "Git remote honeytoken already present"

    def _expose_docker_password(self, data: dict, cycle: int) -> str:
        """Plant a fake password in ~/shophub/docker-compose.yml FILE_CONTENTS."""
        key = "~/shophub/docker-compose.yml"
        if key not in data["FILE_CONTENTS"]:
            return "Skipped expose_docker_password (docker-compose.yml not in FILE_CONTENTS)"
        token   = f"HONEYTOKEN_MONGO_PASS_{cycle:03d}"
        updated = re.sub(
            r"(MONGO_INITDB_ROOT_PASSWORD=)<redacted>",
            rf"\g<1>{token}",
            data["FILE_CONTENTS"][key],
        )
        if updated != data["FILE_CONTENTS"][key]:
            data["FILE_CONTENTS"][key] = updated
            return f"Exposed docker-compose MongoDB password: {token}"
        return "docker-compose MONGO_INITDB_ROOT_PASSWORD already exposed or pattern not found"

    # ── DB mutations ──────────────────────────────────────────────────────

    def _add_admin_user_row(self, data: dict, cycle: int) -> str:
        """Append a honeytoken admin row to shophub.admin_users.
        
        Real columns: id, username, password_hash, email, role, last_login, created_at
        """
        table = data["DATABASES"]["shophub"]["tables"].get("admin_users")
        if table is None:
            return "Skipped add_admin_user_row (admin_users table not found)"
        existing = table["rows"]
        new_id   = len(existing) + 1
        new_row  = [
            new_id,
            f"sysadmin_{cycle:03d}",
            f"$2b$10$HONEYTOKEN_ADMIN_HASH_{cycle:03d}xKqW",
            f"sysadmin{cycle:03d}@shophub.internal",
            "super_admin",
            f"2025-{min(cycle % 12 + 1, 12):02d}-15 08:00:00",
            "2024-06-01 00:00:00",
        ]
        table["rows"] = existing + [new_row]
        return f"Added honeytoken admin_users row: username=sysadmin_{cycle:03d}, role=super_admin"

    def _add_honeytoken_table(self, data: dict, table_name: str) -> str:
        """Create a new honeytoken table in shophub DB + register in information_schema."""
        if table_name not in self._NEW_TABLES:
            return f"Unknown table template: {table_name}"
        shophub_tables = data["DATABASES"]["shophub"]["tables"]
        if table_name in shophub_tables:
            return f"Table shophub.{table_name} already exists"

        import copy
        shophub_tables[table_name] = copy.deepcopy(self._NEW_TABLES[table_name])

        # Register in information_schema.tables
        is_rows = data["DATABASES"]["information_schema"]["tables"]["tables"]["rows"]
        entry   = ["shophub", table_name, "BASE TABLE"]
        if entry not in is_rows:
            data["DATABASES"]["information_schema"]["tables"]["tables"]["rows"] = is_rows + [entry]

        row_count = len(self._NEW_TABLES[table_name]["rows"])
        return f"Created shophub.{table_name} with {row_count} honeytoken rows"

    # ── Global mutations ──────────────────────────────────────────────────

    def _bump_package_version(self, data: dict, cycle: int) -> str:
        """Bump version in ~/shophub/package.json FILE_CONTENTS."""
        key = "~/shophub/package.json"
        if key not in data["FILE_CONTENTS"]:
            return "Skipped bump_package_version (package.json not in FILE_CONTENTS)"
        minor = 3 + (cycle % 5)
        patch = cycle % 20
        new_ver = f"2.{minor}.{patch}"
        updated = re.sub(
            r'"version":\s*"[^"]+"',
            f'"version": "{new_ver}"',
            data["FILE_CONTENTS"][key],
        )
        data["FILE_CONTENTS"][key] = updated
        return f"Bumped package.json version → {new_ver}"

    def _add_decoy_directory(self, data: dict, cycle: int) -> str:
        """Add a new decoy directory entry to SHOPHUB_STRUCTURE."""
        path, desc, contents = self._DECOY_DIRS[cycle % len(self._DECOY_DIRS)]
        if path in data["SHOPHUB_STRUCTURE"]:
            return f"Decoy directory {path} already in SHOPHUB_STRUCTURE"
        data["SHOPHUB_STRUCTURE"][path] = {
            "type":        "directory",
            "description": desc,
            "contents":    contents,
        }
        # Register dirname in parent directory
        parent  = "/".join(path.split("/")[:-1])
        dirname = path.split("/")[-1]
        if parent in data["SHOPHUB_STRUCTURE"]:
            existing = data["SHOPHUB_STRUCTURE"][parent].get("contents", [])
            if dirname not in existing:
                data["SHOPHUB_STRUCTURE"][parent]["contents"] = existing + [dirname]
        return f"Added decoy directory: {path} ({len(contents)} files)"

    # ── Dispatch table ────────────────────────────────────────────────────

    def _dispatch(self, change: str, data: dict,
                  successful_protocols: list, cycle: int) -> str:
        """Route a change description string to the appropriate mutation."""
        c = change.lower()

        # SSH
        if any(x in c for x in ["honeytoken key", "id_rsa", "ssh file", "private key",
                                  "vault_token", "stripe.key", "secrets.js"]):
            return self._plant_honeytoken_ssh_file(data, cycle)

        if any(x in c for x in ["env", "stripe_secret", "aws_access", "db_pass",
                                  "redis_password", "jwt_secret", "smtp_pass"]):
            return self._expose_env_credentials(data, cycle)

        if any(x in c for x in ["bash_history", "command history"]):
            return self._poison_bash_history(data, cycle)

        if any(x in c for x in ["decoy script", "deploy script", "sync script"]):
            return self._add_decoy_script(data, cycle)

        if any(x in c for x in ["hostname", "readme", "banner", "prod-0"]):
            return self._rotate_readme_hostname(data, cycle)

        # HTTP
        if any(x in c for x in ["git remote", "github", "pat", ".git/config"]):
            return self._expose_git_remote(data, cycle)

        if any(x in c for x in ["docker", "mongo", "docker-compose"]):
            return self._expose_docker_password(data, cycle)

        if any(x in c for x in ["http page", "endpoint", "url", "/api", "/backup",
                                  "/admin", "/debug", "/config", "add page"]):
            return self._add_exploit_page(data, cycle)

        # DB — specific table names
        if "api_key" in c:
            return self._add_honeytoken_table(data, "api_keys")
        if "credit_card" in c or "payment card" in c:
            return self._add_honeytoken_table(data, "credit_cards")
        if "session" in c:
            return self._add_honeytoken_table(data, "sessions")
        if "audit_log" in c or "audit log" in c:
            return self._add_honeytoken_table(data, "audit_logs")
        if "admin_user" in c or ("admin" in c and "row" in c) or "bcrypt" in c:
            return self._add_admin_user_row(data, cycle)

        # Global
        if "version" in c or "package.json" in c:
            return self._bump_package_version(data, cycle)
        if "directory" in c or "internal" in c or "devops" in c or "backup" in c:
            return self._add_decoy_directory(data, cycle)

        # Fallback — apply one mutation per active protocol
        results = []
        if "ssh" in successful_protocols:
            results.append(self._expose_env_credentials(data, cycle))
        if "http" in successful_protocols:
            results.append(self._add_exploit_page(data, cycle))
        if "database" in successful_protocols:
            results.append(self._add_admin_user_row(data, cycle))
        if not results:
            results.append(self._bump_package_version(data, cycle))
        return " | ".join(results)

    # ── Public entry point ────────────────────────────────────────────────

    def apply(self,
              approved_changes:     list[str],
              successful_protocols: list[str],
              cycle:                int) -> list[str]:
        """
        Load file_structure.py → apply mutations → write back.
        Returns a list of mutation log strings (one per change).
        """
        if not self.path.exists():
            msg = f"file_structure.py not found at {self.path}"
            self.log.error(f"  ✗ {msg}")
            return [f"ERROR: {msg}"]

        data    = self._load()
        applied = []

        for change in approved_changes:
            try:
                msg = self._dispatch(change, data, successful_protocols, cycle)
                applied.append(msg)
                self.log.debug(f"  mutation: {msg}")
            except Exception as exc:
                err = f"FAILED '{change}': {exc}"
                self.log.warning(f"  ✗ {err}")
                applied.append(err)

        self._write(data)
        self.log.info(f"  file_structure.py: {len(applied)} mutation(s) applied → {self.path}")
        return applied


def evolve_filesystem(state: AgentState) -> dict:
    """
    NODE 11 — Gemini decides whether to evolve; if yes, FileStructureEvolver
    applies real mutations to file_structure.py.

    Decision flow:
      1. Collect successful exploit protocols + check hard thresholds
      2. Ask Gemini (with full campaign context) for a JSON decision
      3. If approved: FileStructureEvolver.apply() mutates file_structure.py
      4. Log every mutation with before/after evidence
    """
    log.info("▶ NODE: evolve_filesystem")

    successful_protocols = []
    for proto, key in [("ssh",      "ssh_exploit_result"),
                       ("http",     "http_exploit_result"),
                       ("database", "db_exploit_result")]:
        r = state.get(key)
        if r and r.get("success"):
            successful_protocols.append(proto)

    threshold_met = (
        state["overall_suspicion"]   >= 0.40 or
        state["total_data_bytes"]    >= 1024  or
        len(successful_protocols)    >= 2
    )

    # Build candidate changes grounded in the actual file structure sections
    candidate_changes = []
    if "ssh" in successful_protocols:
        candidate_changes += random.sample(EVOLUTION_POOL["ssh"],      k=min(2, len(EVOLUTION_POOL["ssh"])))
    if "http" in successful_protocols:
        candidate_changes += random.sample(EVOLUTION_POOL["http"],     k=min(2, len(EVOLUTION_POOL["http"])))
    if "database" in successful_protocols:
        candidate_changes += random.sample(EVOLUTION_POOL["database"], k=min(2, len(EVOLUTION_POOL["database"])))
    candidate_changes += random.sample(EVOLUTION_POOL["global"],       k=1)

    # Remove duplicates while preserving order
    seen = set()
    candidate_changes = [c for c in candidate_changes if not (c in seen or seen.add(c))]

    system_prompt = """You are the SigilHive honeypot evolution engine.
You decide whether to evolve the honeypot filesystem (file_structure.py) to be more
deceptive after an attack cycle.

The filesystem contains:
  SHOPHUB_STRUCTURE — directory tree (SSH honeypot sees this)
  FILE_CONTENTS     — file text contents (cat, less, etc. return these)
  DATABASES         — MySQL tables/rows (DB honeypot serves these)
  PAGES             — HTTP endpoints (HTTP honeypot serves these)

Evolution injects NEW honeytoken data that future attackers will exfiltrate.

Respond with VALID JSON only — no markdown, no extra text:
{
  "should_evolve": true | false,
  "reason": "one concise sentence",
  "approved_changes": ["exact string from candidate list", ...]
}

Only include strings that appear verbatim in the candidate list."""

    user_prompt = f"""Attack cycle #{state['episode']} campaign summary:
  Suspicion      : {state['overall_suspicion']:.3f}  (threshold ≥ 0.40)
  Data extracted : {state['total_data_bytes']} B     (threshold ≥ 1024)
  Exploit wins   : {len(successful_protocols)}/{len(Protocol.sequence())} protocols ({', '.join(successful_protocols) or 'none'})
  Reward         : {state['reward']:.3f}
  Threshold met  : {threshold_met}

Evaluation:
{state.get('evaluation_summary', 'N/A')}

Candidate changes (choose from EXACTLY these strings):
{json.dumps(candidate_changes, indent=2)}

Decide: should the honeypot filesystem evolve?"""

    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    raw = re.sub(r"^```(?:json)?\s*", "", response.content.strip())
    raw = re.sub(r"\s*```$", "", raw)

    try:
        decision         = json.loads(raw)
        should_evolve    = bool(decision.get("should_evolve", False))
        reason           = decision.get("reason", "No reason provided")
        approved_changes = [c for c in decision.get("approved_changes", [])
                            if c in candidate_changes]   # whitelist only
    except json.JSONDecodeError:
        log.warning(f"  Gemini returned non-JSON — falling back to threshold. Raw: {raw[:200]}")
        should_evolve    = threshold_met
        reason           = "Threshold-based fallback (JSON parse error)"
        approved_changes = candidate_changes[:3] if threshold_met else []

    mutation_log = []

    if should_evolve:
        log.info(f"  ✓ EVOLUTION APPROVED: {reason}")
        fs_path = state.get("file_structure_path", "22CS13-SigilHive\\SigilHive\\file_structure.py")
        if fs_path and Path(fs_path).exists():
            evolver     = FileStructureEvolver(fs_path)
            mutation_log = evolver.apply(
                approved_changes    = approved_changes,
                successful_protocols= successful_protocols,
                cycle               = state["episode"],
            )
            for i, mut in enumerate(mutation_log, 1):
                status = "✓" if not mut.startswith("FAILED") else "✗"
                log.info(f"    [{i}] {status} {mut}")
        else:
            log.warning(f"  file_structure_path not set or file missing: '{fs_path}'")
            log.warning("  Set --file-structure-path to enable real file mutations")
            # Still log what WOULD have been applied
            for i, ch in enumerate(approved_changes, 1):
                log.info(f"    [{i}] (dry) {ch}")
    else:
        log.info(f"  ✗ EVOLUTION REJECTED: {reason}")

    return {
        "evolution_triggered": should_evolve,
        "evolution_reason":    reason,
        "evolution_changes":   approved_changes,
        "finished_at":         time.time(),
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=response.content),
        ],
    }


def save_results(state: AgentState) -> dict:
    """NODE 7 — Persist cycle results to disk and print summary."""
    log.info("▶ NODE: save_results")

    results_dir = Path(state.get("results_dir", "attack_results"))
    results_dir.mkdir(parents=True, exist_ok=True)

    started_at  = state.get("started_at",  time.time())
    finished_at = state.get("finished_at", time.time())
    duration    = round(finished_at - started_at, 2)

    data = {
        "cycle_id":              state["cycle_id"],
        "episode":               state["episode"],
        "started_at":            started_at,
        "finished_at":           finished_at,
        "duration_s":            duration,
        "attack_plan":           state.get("attack_plan"),
        "evaluation_summary":    state.get("evaluation_summary"),
        "overall_suspicion":     state["overall_suspicion"],
        "total_data_bytes":      state["total_data_bytes"],
        "reward":                state["reward"],
        "evolution_triggered":   state["evolution_triggered"],
        "evolution_reason":      state.get("evolution_reason"),
        "evolution_changes":     state.get("evolution_changes", []),
        "results": {
            "ssh_recon":    state.get("ssh_recon_result"),
            "ssh_exploit":  state.get("ssh_exploit_result"),
            "http_recon":   state.get("http_recon_result"),
            "http_exploit": state.get("http_exploit_result"),
            "db_recon":     state.get("db_recon_result"),
            "db_exploit":   state.get("db_exploit_result"),
        },
    }

    path = results_dir / f"{state['cycle_id']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    # ── Print cycle summary ────────────────────────────────────────────────
    log.info("")
    log.info("╔" + "═" * 66 + "╗")
    log.info(f"║  CYCLE #{state['episode']:02d} SUMMARY  id={state['cycle_id']:<38}║")
    log.info("╠" + "═" * 66 + "╣")
    log.info(f"║  Duration          : {duration:<45.1f}s ║")
    log.info(f"║  Overall suspicion : {state['overall_suspicion']:<45.3f} ║")
    log.info(f"║  Total data        : {state['total_data_bytes']:<45} ║")
    log.info(f"║  Reward            : {state['reward']:<45.3f} ║")
    log.info(f"║  Evolution         : {'✓ TRIGGERED' if state['evolution_triggered'] else '✗ SKIPPED':<45} ║")
    if state.get("evolution_reason"):
        reason_short = state["evolution_reason"][:44]
        log.info(f"║  Evo reason        : {reason_short:<45} ║")
    log.info(f"║  Saved to          : {str(path)[:44]:<45} ║")
    log.info("╚" + "═" * 66 + "╝")

    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  Build LangGraph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Constructs and compiles the LangGraph agent.

    Flow (10 nodes):
      START
        → plan_attack
        → attack_ssh_recon  → gen_ssh_exploit_cmds  → attack_ssh_exploit
        → attack_http_recon → gen_http_exploit_cmds → attack_http_exploit
        → attack_db_recon   → gen_db_exploit_cmds   → attack_db_exploit
        → evaluate_campaign → evolve_filesystem → save_results
        → END

    Recon nodes: static commands (fast, deterministic).
    gen_*_exploit_cmds nodes: Gemini reads recon output, generates targeted
      commands/paths/queries dynamically.
    Exploit nodes: execute those LLM-generated commands against the honeypot.
    """
    builder = StateGraph(AgentState)

    # Register all nodes
    builder.add_node("plan_attack",           plan_attack)
    builder.add_node("attack_ssh_recon",      attack_ssh_recon)
    builder.add_node("gen_ssh_exploit_cmds",  gen_ssh_exploit_cmds)
    builder.add_node("attack_ssh_exploit",    attack_ssh_exploit)
    builder.add_node("attack_http_recon",     attack_http_recon)
    builder.add_node("gen_http_exploit_cmds", gen_http_exploit_cmds)
    builder.add_node("attack_http_exploit",   attack_http_exploit)
    builder.add_node("attack_db_recon",       attack_db_recon)
    builder.add_node("gen_db_exploit_cmds",   gen_db_exploit_cmds)
    builder.add_node("attack_db_exploit",     attack_db_exploit)
    builder.add_node("evaluate_campaign",     evaluate_campaign)
    builder.add_node("evolve_filesystem",     evolve_filesystem)
    builder.add_node("save_results",          save_results)

    # Fixed sequential edges
    builder.add_edge(START,                    "plan_attack")
    builder.add_edge("plan_attack",            "attack_ssh_recon")
    builder.add_edge("attack_ssh_recon",       "gen_ssh_exploit_cmds")
    builder.add_edge("gen_ssh_exploit_cmds",   "attack_ssh_exploit")
    builder.add_edge("attack_ssh_exploit",     "attack_http_recon")
    builder.add_edge("attack_http_recon",      "gen_http_exploit_cmds")
    builder.add_edge("gen_http_exploit_cmds",  "attack_http_exploit")
    builder.add_edge("attack_http_exploit",    "attack_db_recon")
    builder.add_edge("attack_db_recon",        "gen_db_exploit_cmds")
    builder.add_edge("gen_db_exploit_cmds",    "attack_db_exploit")
    builder.add_edge("attack_db_exploit",      "evaluate_campaign")
    builder.add_edge("evaluate_campaign",      "evolve_filesystem")
    builder.add_edge("evolve_filesystem",      "save_results")
    builder.add_edge("save_results",           END)

    return builder.compile()


# ─────────────────────────────────────────────────────────────────────────────
#  Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(
    host:                 str   = "localhost",
    ssh_port:             int   = 5555,
    http_port:            int   = 8443,
    db_port:              int   = 2225,
    episodes:             int   = 3,
    delay:                float = 2.0,
    dry_run:              bool  = False,
    results_dir:          str   = "attack_results",
    file_structure_path:  str   = "",
) -> list[dict]:
    """Execute N attack episodes with the LangGraph agent."""

    graph = build_graph()

    all_results   = []
    session_start = time.time()

    log.info("╔" + "═" * 70 + "╗")
    log.info("║  SigilHive LangGraph Agent — Gemini-Powered Honeypot Attacker" + " " * 8 + "║")
    log.info("╠" + "═" * 70 + "╣")
    log.info(f"║  Target   : {host:<57}║")
    log.info(f"║  SSH      : {ssh_port:<57}║")
    log.info(f"║  HTTP     : {http_port:<57}║")
    log.info(f"║  Database : {db_port:<57}║")
    log.info(f"║  Episodes : {episodes:<57}║")
    log.info(f"║  Mode     : {'DRY-RUN (simulator)' if dry_run else 'LIVE':<57}║")
    log.info("╚" + "═" * 70 + "╝")

    for ep in range(1, episodes + 1):
        log.info("")
        log.info("═" * 72)
        log.info(f"  EPISODE {ep}/{episodes}")
        log.info("═" * 72)

        initial_state: AgentState = {
            "messages":    [],
            "host":        host,
            "ssh_port":    ssh_port,
            "http_port":   http_port,
            "db_port":     db_port,
            "dry_run":     dry_run,
            "episode":     ep,
            "results_dir": results_dir,
            # All attack results start as None
            "ssh_recon_result":    None,
            "ssh_exploit_result":  None,
            "http_recon_result":   None,
            "http_exploit_result": None,
            "db_recon_result":     None,
            "db_exploit_result":   None,
            "attack_plan":         None,
            "skip_ssh_exploit":    False,
            "skip_http_exploit":   False,
            "skip_db_exploit":     False,
            "ssh_exploit_cmds":    [],
            "http_exploit_cmds":   [],
            "db_exploit_cmds":     [],
            "overall_suspicion":   0.0,
            "total_data_bytes":    0,
            "reward":              0.0,
            "evaluation_summary":  None,
            "evolution_triggered": False,
            "evolution_reason":    None,
            "evolution_changes":   [],
            "cycle_id":            "",
            "started_at":          0.0,
            "finished_at":         0.0,
            "file_structure_path": file_structure_path,
        }

        final_state = graph.invoke(initial_state)
        all_results.append(final_state)

        if ep < episodes:
            log.info(f"  Waiting {delay}s before next episode…")
            time.sleep(delay)

    # ── Session summary ────────────────────────────────────────────────────
    total_duration  = round(time.time() - session_start, 1)
    evolutions      = sum(1 for r in all_results if r.get("evolution_triggered"))
    total_data      = sum(r.get("total_data_bytes", 0) for r in all_results)
    avg_reward      = sum(r.get("reward", 0) for r in all_results) / len(all_results)
    avg_suspicion   = sum(r.get("overall_suspicion", 0) for r in all_results) / len(all_results)

    log.info("")
    log.info("╔" + "═" * 68 + "╗")
    log.info("║  SESSION COMPLETE" + " " * 50 + "║")
    log.info("╠" + "═" * 68 + "╣")
    log.info(f"║  Total episodes        : {episodes:<42}║")
    log.info(f"║  Total duration        : {total_duration:<42.1f}s ║")
    log.info(f"║  Evolutions triggered  : {evolutions:<42}║")
    log.info(f"║  Total data extracted  : {total_data:<42} bytes ║")
    log.info(f"║  Avg reward / episode  : {avg_reward:<42.3f}║")
    log.info(f"║  Avg suspicion/episode : {avg_suspicion:<42.3f}║")
    log.info("╚" + "═" * 68 + "╝")

    return all_results


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SigilHive LangGraph Agent — Gemini-powered honeypot attacker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",        default=os.getenv("TARGET_HOST", "localhost"),
                        help="Honeypot target host")
    parser.add_argument("--ssh-port",    type=int,
                        default=int(os.getenv("SSH_PORT",   "5555")),
                        help="SSH honeypot port")
    parser.add_argument("--http-port",   type=int,
                        default=int(os.getenv("HTTPS_PORT", "8443")),
                        help="HTTP honeypot TLS port")
    parser.add_argument("--db-port",     type=int,
                        default=int(os.getenv("MYSQL_PORT", "2225")),
                        help="Database honeypot port")
    parser.add_argument("--episodes",    type=int,   default=3,
                        help="Number of attack episodes to run")
    parser.add_argument("--delay",       type=float, default=2.0,
                        help="Delay between episodes (seconds)")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Use simulator instead of live connections")
    parser.add_argument("--results-dir", default="attack_results",
                        help="Directory to save cycle JSON results")
    parser.add_argument("--file-structure-path", default=os.getenv("FILE_STRUCTURE_PATH", ""),
                        help="Path to file_structure.py to mutate on evolution"
                             " (e.g. ./honeypots/file_structure.py)")
    args = parser.parse_args()

    run_agent(
        host                 = args.host,
        ssh_port             = args.ssh_port,
        http_port            = args.http_port,
        db_port              = args.db_port,
        episodes             = args.episodes,
        delay                = args.delay,
        dry_run              = args.dry_run,
        results_dir          = args.results_dir,
        file_structure_path  = args.file_structure_path,
    )


if __name__ == "__main__":
    main()