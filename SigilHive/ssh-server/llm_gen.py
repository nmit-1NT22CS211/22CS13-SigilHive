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

# load cache on import
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


# Basic sanitizer to redact dangerous substrings
_BANNED_SUBSTRS = [
    "rm -rf",
    "sudo ",
    "dd if=",
    "curl ",
    "wget ",
    "nc ",
    "ncat ",
    "sshpass",
    "exploit",
    "metasploit",
    "chmod 777",
    "password",
    "passwd",
    "PRIVATE KEY",
    "api_key",
    "secret",
    "SECRET_KEY",
    "SECRET",
    "PRIVATE_KEY",
]


def sanitize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    out = text
    for b in _BANNED_SUBSTRS:
        out = out.replace(b, "[REDACTED]")
    # extra safety: limit length
    if len(out) > 8000:
        out = out[:8000] + "\n...[truncated]"
    return out


def _build_prompt(command: str, filename_hint: str = None, persona: str = None) -> str:
    """
    Build a safety-first prompt that instructs Gemini to generate *only* simulated outputs,
    never any secrets, commands, or instructions for misuse.
    """
    persona_line = (
        f"You are simulating the text output of a UNIX system (persona: {persona})."
        if persona
        else "You are simulating the text output of a UNIX-like system."
    )
    file_line = f"Target filename hint: {filename_hint}." if filename_hint else ""
    prompt = (
        f"{persona_line}\n"
        f"{file_line}\n"
        "IMPORTANT SAFETY RULES (must obey):\n"
        "1) Produce only harmless simulated output (file contents, command output, or banners).\n"
        "2) DO NOT include real passwords, private keys, API keys, exploit commands, or step-by-step instructions.\n"
        "3) DO NOT include runnable shell commands or instructions (no code that attackers could copy to exploit systems).\n"
        "4) Keep output plausible and concise. If generating a file, make it look like a README, config snippet, or benign log.\n"
        "5) If asked to simulate network commands (ping/curl/ssh), simulate plausible-looking output; DO NOT perform any network access.\n\n"
        f"User asked to run: `{command}`\n\n"
        "Produce ONLY the simulated command output or file content — nothing else (no commentary, no analysis).\n"
    )
    return prompt


def _get_llm_client():
    # instantiate the LangChain Gemini wrapper
    # Using model "gemini-1.5-pro" as example; change if not available for your key
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        max_output_tokens=1024,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """
    Synchronous call to Gemini via LangChain.
    We'll wrap this in asyncio.to_thread for async use.
    """
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        # `resp.content` contains the reply
        text = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        text = f"[LLM error: {e}]"
    return sanitize(text)


async def generate_response_for_command_async(
    command: str,
    filename_hint: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    """
    Async wrapper: returns LLM-generated safe string. Uses cache keyed by command+filename_hint.
    Call this from async code via 'await'.
    """
    key_raw = f"cmd:{command}|file:{filename_hint or ''}"
    cache_key = _cache_key("resp", key_raw)
    if not force_refresh and cache_key in _cache:
        return _cache[cache_key]

    prompt = _build_prompt(
        command=command, filename_hint=filename_hint, persona=persona
    )
    # call blocking LLM in thread to avoid blocking event loop
    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        out = f"[LLM call failed: {e}]"
    # final sanitize & cache
    out = sanitize(out)
    _cache[cache_key] = out
    # persist occasionally (cheap)
    if int(time.time()) % 10 == 0:
        _persist_cache()
    return out


# small utility sync wrapper if needed:
def generate_response_for_command(
    command: str,
    filename_hint: str = None,
    persona: str = None,
    force_refresh: bool = False,
) -> str:
    return asyncio.get_event_loop().run_until_complete(
        generate_response_for_command_async(
            command, filename_hint, persona, force_refresh
        )
    )
