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
    "<?php",
    "eval(",
    "exec(",
    "system(",
    "shell_exec(",
    "<script>",
    "javascript:",
    "onerror=",
    "onload=",
    "../../../",
    "rm -rf",
    "sudo ",
    "wget ",
    "curl ",
    "nc ",
    "exploit",
    "metasploit",
    "payload",
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


def _build_http_prompt(
    method: str,
    path: str,
    headers: dict,
    body: str = None,
    intent: str = None,
    server_context: str = None,
    persona: str = None,
) -> str:
    """
    Build a safety-first prompt for HTTP response simulation.
    """
    persona_line = (
        f"You are simulating a {persona} web server."
        if persona
        else "You are simulating a web server."
    )

    context_line = f"Server context: {server_context}" if server_context else ""
    intent_line = f"Request intent: {intent}" if intent else ""

    headers_str = "\n".join([f"{k}: {v}" for k, v in (headers or {}).items()])
    body_str = f"\nRequest Body:\n{body}" if body else ""

    prompt = (
        f"{persona_line}\n"
        f"{context_line}\n"
        f"{intent_line}\n\n"
        "IMPORTANT SAFETY RULES (must obey):\n"
        "1) Produce only harmless simulated HTTP responses (HTML pages, JSON, error messages).\n"
        "2) DO NOT include real passwords, private keys, API keys, sensitive data.\n"
        "3) DO NOT include malicious payloads, XSS, SQL injection, or exploit code.\n"
        "4) Keep output realistic and concise. Return appropriate HTTP response content.\n"
        "5) For normal requests, return plausible HTML/JSON content.\n"
        "6) For suspicious requests, return appropriate error messages (400, 403, 404, 500).\n"
        "7) For admin/login pages, return realistic but fake login forms.\n"
        "8) If the request appears malicious, return a 403 Forbidden or 404 Not Found.\n"
        "9) Format output as the body content only (HTML, JSON, or plain text).\n"
        "10) Match the content type to what would be expected for the request.\n\n"
        f"HTTP Request:\n"
        f"{method} {path}\n"
        f"Headers:\n{headers_str}\n"
        f"{body_str}\n\n"
        "Produce ONLY the HTTP response body content – nothing else (no headers, no status code commentary).\n"
        "Make it realistic for what this web server would return.\n"
    )
    return prompt


def _get_llm_client():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        max_output_tokens=2048,
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


async def generate_http_response_async(
    method: str,
    path: str,
    headers: dict = None,
    body: str = None,
    intent: str = None,
    server_context: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    """
    Async wrapper: returns LLM-generated safe HTTP response body.
    Uses cache keyed by method+path+intent.
    """
    key_raw = (
        f"http:{method}|path:{path}|intent:{intent or ''}|ctx:{server_context or ''}"
    )
    cache_key = _cache_key("http_resp", key_raw)

    if not force_refresh and cache_key in _cache:
        return _cache[cache_key]

    prompt = _build_http_prompt(
        method=method,
        path=path,
        headers=headers or {},
        body=body,
        intent=intent,
        server_context=server_context,
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
def generate_http_response(
    method: str,
    path: str,
    headers: dict = None,
    body: str = None,
    intent: str = None,
    server_context: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    return asyncio.get_event_loop().run_until_complete(
        generate_http_response_async(
            method, path, headers, body, intent, server_context, persona, force_refresh
        )
    )
