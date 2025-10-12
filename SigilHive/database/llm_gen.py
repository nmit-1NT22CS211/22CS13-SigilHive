# llm_gen.py
import os
import json
import hashlib
import time
from dotenv import load_dotenv
import asyncio

# LangChain Google Generative AI wrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[llm_gen] WARNING: GEMINI_API_KEY not set. Set it in .env or env vars.")

CACHE_PATH = "llm_cache.json"
_cache = {}

# Load cache on import
try:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
except Exception as e:
    print("[llm_gen] could not load cache:", e)
    _cache = {}


def _persist_cache():
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f)
    except Exception as e:
        print("[llm_gen] cache save error:", e)


def _cache_key(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{h}"


# Banned substrings for security
_BANNED_SUBSTRS = [
    "password",
    "passwd",
    "PASSWORD",
    "secret",
    "SECRET",
    "PRIVATE KEY",
    "api_key",
    "API_KEY",
    "token",
    "TOKEN",
    "credit_card",
    "ssn",
    "DROP DATABASE",
    "'; DROP TABLE",
    "UNION SELECT",
    "LOAD_FILE",
    "INTO OUTFILE",
    "INTO DUMPFILE",
    "rm -rf",
    "sudo ",
    "dd if=",
    "curl ",
    "wget ",
    "nc ",
    "exploit",
    "metasploit",
]


def sanitize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    out = text
    for b in _BANNED_SUBSTRS:
        out = out.replace(b, "[REDACTED]")
    # Limit length
    if len(out) > 8000:
        out = out[:8000] + "\n...[truncated]"
    return out


def _build_db_prompt(
    query: str,
    db_type: str = "mysql",
    intent: str = None,
    db_context: str = None,
    table_hint: str = None,
    persona: str = None,
) -> str:
    """
    Build a safety-first prompt for database query simulation.
    """
    db_name = db_type.upper() if db_type else "SQL"
    persona_line = (
        f"You are simulating the output of a {db_name} database server (version: {persona})."
        if persona
        else f"You are simulating the output of a {db_name} database server."
    )

    context_line = f"Context: {db_context}" if db_context else ""
    intent_line = f"Query type: {intent}" if intent else ""
    table_line = f"Table hint: {table_hint}" if table_hint else ""

    prompt = (
        f"{persona_line}\n"
        f"{context_line}\n"
        f"{intent_line}\n"
        f"{table_line}\n\n"
        "IMPORTANT SAFETY RULES (must obey):\n"
        "1) Produce only harmless simulated database output (query results, table structures, status messages).\n"
        "2) DO NOT include real passwords, private keys, API keys, credit card numbers, SSNs, or sensitive data.\n"
        "3) DO NOT include SQL injection payloads, exploit commands, or malicious queries.\n"
        "4) Keep output realistic and concise. For SELECT queries, return plausible sample data (2-5 rows).\n"
        "5) For SHOW/DESCRIBE commands, return realistic table/database structures.\n"
        "6) For administrative queries (GRANT/REVOKE/DROP), return appropriate error messages or success confirmations.\n"
        "7) Maintain consistency with typical database behavior and error messages.\n"
        "8) If the query appears malicious (SQL injection, etc.), return an appropriate error message.\n"
        "9) Format output EXACTLY as the database would show it (with proper column alignment, row counts, etc.).\n"
        "10) For MySQL, use MySQL-style output. For PostgreSQL, use PostgreSQL-style output.\n\n"
        f"User query: {query}\n\n"
        "Produce ONLY the simulated database output — nothing else (no commentary, no analysis).\n"
        "Format the output exactly as a real database server would display it.\n"
    )
    return prompt


def _get_llm_client():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        max_output_tokens=1024,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Synchronous call to Gemini via LangChain."""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        text = f"ERROR: {e}"
    return sanitize(text)


async def generate_db_response_async(
    query: str,
    db_type: str = "mysql",
    intent: str = None,
    db_context: str = None,
    table_hint: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    """
    Async wrapper: returns LLM-generated safe database response string.
    Uses cache keyed by query+db_type+context.
    """
    key_raw = (
        f"db:{db_type}|query:{query}|ctx:{db_context or ''}|table:{table_hint or ''}"
    )
    cache_key = _cache_key("db_resp", key_raw)

    if not force_refresh and cache_key in _cache:
        return _cache[cache_key]

    prompt = _build_db_prompt(
        query=query,
        db_type=db_type,
        intent=intent,
        db_context=db_context,
        table_hint=table_hint,
        persona=persona,
    )

    # Call blocking LLM in thread to avoid blocking event loop
    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        out = f"ERROR: LLM call failed: {e}"

    # Final sanitize & cache
    out = sanitize(out)
    _cache[cache_key] = out

    # Persist occasionally
    if int(time.time()) % 10 == 0:
        _persist_cache()

    return out


# Sync wrapper if needed
def generate_db_response(
    query: str,
    db_type: str = "mysql",
    intent: str = None,
    db_context: str = None,
    table_hint: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    return asyncio.get_event_loop().run_until_complete(
        generate_db_response_async(
            query, db_type, intent, db_context, table_hint, persona, force_refresh
        )
    )
