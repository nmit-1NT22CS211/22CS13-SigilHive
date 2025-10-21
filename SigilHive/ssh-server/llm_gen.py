# llm_gen.py
import os
import json
import hashlib
import time
from dotenv import load_dotenv
import asyncio

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[llm_gen] WARNING: GEMINI_API_KEY not set. Set it in .env or env vars.")

CACHE_PATH = "llm_cache.json"
_cache = {}

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


_BANNED_SUBSTRS = [
    "rm -rf",
    "dd if=",
    "mkfs",
    ":(){:|:&};:",  # fork bomb
    "curl http://malicious",
    "wget http://malicious",
    "nc -e",
    "ncat -e",
    "sshpass",
    "metasploit",
    "chmod 777",
    "chmod 666",
    "PRIVATE KEY-----",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "api_key=",
    "API_KEY=",
    "SECRET_KEY=",
    "password=",
    "PASSWORD=",
    "sk_live_",
    "sk_test_",
]


def sanitize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    out = text
    for b in _BANNED_SUBSTRS:
        out = out.replace(b, "[REDACTED]")
    if len(out) > 8000:
        out = out[:8000] + "\n...[truncated]"
    return out


def _build_prompt(
    command: str, filename_hint: str = None, persona: str = None, context: dict = None
) -> str:
    """
    Build a context-aware prompt that helps the LLM generate realistic outputs
    based on the current directory and application structure.
    """
    persona_line = (
        f"You are simulating terminal output for a {persona} system."
        if persona
        else "You are simulating terminal output for a Linux server."
    )

    # Build context information
    context_info = ""
    if context:
        current_dir = context.get("current_directory", "~")
        dir_desc = context.get("directory_description", "")
        dir_contents = context.get("directory_contents", [])
        app_name = context.get("application", "")
        tech_stack = context.get("application_tech", "")

        context_info = f"""
CURRENT CONTEXT:
- Current Directory: {current_dir}
- Directory Description: {dir_desc}
- Directory Contains: {", ".join(dir_contents) if dir_contents else "empty"}
- Application: {app_name}
- Tech Stack: {tech_stack}
"""

    file_info = f"Target file: {filename_hint}" if filename_hint else ""

    prompt = f"""{persona_line}

{context_info}

CRITICAL SAFETY RULES:
1) Generate ONLY realistic terminal output (command results, file contents, or directory listings)
2) NEVER include real passwords, private keys, API keys, or sensitive credentials
3) NEVER include executable exploit code or malicious commands
4) For authentication tokens/keys in files, use placeholder values like [REDACTED], <your-key-here>, or dummy values
5) Make outputs contextually appropriate for the current directory and application
6) Keep outputs realistic and consistent with an e-commerce platform environment

CONTEXTUAL GUIDELINES:
- If in application directories, show relevant code snippets, configs, or logs
- If listing directories (ls), show contents that match the current directory context
- If reading files (cat), generate appropriate file content based on filename and location
- For logs, show realistic ecommerce application logs (orders, payments, user actions)
- For code files, show relevant Node.js/Express code snippets
- For config files, show configurations with redacted sensitive values
- For database files, show schema or sample data (no real user data)

Command to simulate: `{command}`
{file_info}

Generate ONLY the terminal output - no explanations, no commentary, no markdown formatting.
Just the raw output as it would appear in a real terminal.
"""
    return prompt


def _get_llm_client():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
        max_output_tokens=2048,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Synchronous call to Gemini via LangChain"""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        text = f"bash: command error: {e}"
    return sanitize(text)


async def generate_response_for_command_async(
    command: str,
    filename_hint: str = None,
    persona: str = None,
    context: dict = None,
    force_refresh: bool = False,
) -> str:
    """
    Async wrapper that generates context-aware responses.
    Uses cache keyed by command + directory context.
    """
    # Create cache key that includes directory context
    current_dir = context.get("current_directory", "~") if context else "~"
    key_raw = f"cmd:{command}|dir:{current_dir}|file:{filename_hint or ''}"
    cache_key = _cache_key("resp", key_raw)

    if not force_refresh and cache_key in _cache:
        return _cache[cache_key]

    prompt = _build_prompt(
        command=command, filename_hint=filename_hint, persona=persona, context=context
    )

    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception:
        out = f"bash: {command.split()[0]}: command not found"

    out = sanitize(out)
    _cache[cache_key] = out

    # Persist cache periodically
    if int(time.time()) % 10 == 0:
        _persist_cache()

    return out


def generate_response_for_command(
    command: str,
    filename_hint: str = None,
    persona: str = None,
    context: dict = None,
    force_refresh: bool = False,
) -> str:
    """Synchronous wrapper"""
    return asyncio.get_event_loop().run_until_complete(
        generate_response_for_command_async(
            command, filename_hint, persona, context, force_refresh
        )
    )
