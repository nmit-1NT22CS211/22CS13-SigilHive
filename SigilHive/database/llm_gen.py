import os
import json
import time
import asyncio
import hashlib
from typing import Optional
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[llm_gen] WARNING: GEMINI_API_KEY not set")

CACHE_PATH = "shophub_db_cache.json"
_cache = {}

# Load cache if it exists
try:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
except Exception as e:
    print(f"[llm_gen] cache load error: {e}")
    _cache = {}


def _persist_cache():
    """Persist cache to disk with atomic write to avoid corrupt files."""
    try:
        tmp_path = CACHE_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CACHE_PATH)
    except Exception as e:
        print(f"[llm_gen] cache save error: {e}")


def _cache_key(prefix: str, key: str) -> str:
    """Create a deterministic short cache key from arbitrary input."""
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{h}"


def sanitize(text: str) -> str:
    """Sanitize output (redact secrets and truncate very long output)."""
    if not isinstance(text, str):
        return ""

    replacements = {
        "$2b$10$": "$2b$10$[REDACTED]",
        "txn_": "txn_[REDACTED]",
        "PAY-": "PAY-[REDACTED]",
    }

    out = text
    for pattern, replacement in replacements.items():
        if pattern in out:
            out = out.replace(pattern, replacement)

    # Less aggressive truncation to avoid breaking JSON
    MAX_LEN = 50000
    if len(out) > MAX_LEN:
        out = out[:MAX_LEN] + "\n...[truncated]"

    return out


def clean_json_response(text: str) -> str:
    """
    Remove markdown code blocks and extra formatting from LLM response and
    attempt to extract a single JSON object if present.

    Returns cleaned text (JSON string if JSON could be isolated, otherwise original cleaned text).
    """
    if not isinstance(text, str):
        return ""

    # Remove simple ```json / ``` fences
    text = text.replace("```json", "").replace("```", "")
    text = text.strip()

    # First try: whole string is JSON
    try:
        json.loads(text)
        return text
    except Exception:
        pass

    # Try to extract first JSON object using brace counting
    if "{" in text and "}" in text:
        start = text.find("{")
        counter = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == "{":
                counter += 1
            elif text[i] == "}":
                counter -= 1
                if counter == 0:
                    end = i
                    break
        if start != -1 and end != -1:
            candidate = text[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    return text


def _build_prompt(
    query: str, intent: Optional[str] = None, db_context: Optional[str] = None
) -> str:
    """Build the prompt for the LLM to simulate MySQL responses for ShopHub."""
    prompt = f"""You are simulating a MySQL 8.0 database for the ShopHub e-commerce platform.

DATABASE CONTEXT:
{db_context or "ShopHub E-commerce Database"}

USER QUERY:
{query}

QUERY TYPE: {intent or "read"}

RESPONSE RULES:
1. For SELECT/SHOW queries: Return ONLY valid JSON with "columns" (list) and "rows" (list of lists)
   Example: {{"columns": ["id", "name"], "rows": [[1, "Product A"], [2, "Product B"]]}}
   DO NOT wrap in markdown code blocks or add any extra text.

2. For DESCRIBE/DESC queries:
   - ONLY return column information that EXISTS in the DATABASE CONTEXT above
   - Use the EXACT column names from the database schema
   - Return format: {{"columns": ["Field", "Type", "Null", "Key", "Default", "Extra"], "rows": [...]}}

3. For DDL/DML (CREATE, INSERT, UPDATE, DELETE): Return confirmation message
   Example: Query OK, 1 row affected

4. For errors: Return ERROR XXXX (SQLSTATE): message
   Example: ERROR 1146 (42S02): Table 'products' doesn't exist

5. SECURITY:
   - Never expose real passwords (use $2b$10$[REDACTED] format)
   - Never expose full credit card numbers
   - Never expose API keys or tokens
   - Redact transaction IDs as txn_[REDACTED] or PAY-[REDACTED]

6. DATA GENERATION REQUIREMENTS (VERY IMPORTANT):
   - For SELECT queries: Generate 20-50 rows of REALISTIC, VARIED data
   - Make data look like a REAL production e-commerce database
   - Use realistic names, emails, addresses, product names, prices
   - Vary the data - don't repeat patterns
   - Use realistic timestamps (mix of dates from 2024-2025)
   - Make IDs sequential (1, 2, 3, ...)

7. FORMAT:
   - For JSON: Valid JSON ONLY, no markdown, no code blocks, no explanations
   - For messages: Single line only
   - NEVER use ```json or ``` markers
   - Column names in SELECT must EXACTLY match the schema in DATABASE CONTEXT

HARD FORMAT CONSTRAINTS:
- If the query is SELECT/SHOW/DESCRIBE: you MUST return exactly one JSON object.
- That JSON MUST contain exactly two top-level keys: "columns" and "rows".
- Do NOT output any other text before or after the JSON.
- Do NOT wrap JSON in markdown or any code fences.

Generate the response now:
"""
    return prompt


def _get_llm_client():
    """Instantiate the Gemini (Google) client wrapper."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3,
        max_output_tokens=4096,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Call Gemini synchronously and return text content. Handles basic exceptions."""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        print(resp)
        if hasattr(resp, "content"):
            content = resp.content
            if isinstance(content, list):
                text = " ".join(map(str, content))
            else:
                text = str(content)
        else:
            text = str(resp)

        # Clean up the response (remove markdown, extract json if present)
        text = clean_json_response(text)

    except Exception as e:
        text = f"ERROR: Database temporarily unavailable - {e}"
    return text


async def generate_db_response_async(
    query: str,
    intent: Optional[str] = None,
    db_context: Optional[str] = None,
    force_refresh: bool = False,
) -> str:
    """Generate database response using LLM (async wrapper). Uses cache unless force_refresh=True."""
    key_raw = f"query:{query}|intent:{intent}|ctx:{db_context or ''}"
    cache_key = _cache_key("db", key_raw)

    if not force_refresh and cache_key in _cache:
        return _cache[cache_key]

    prompt = _build_prompt(query, intent, db_context)

    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error during LLM call: {e}")
        out = "ERROR 1064 (42000): Internal server error"

    out = sanitize(out)
    _cache[cache_key] = out

    try:
        if int(time.time()) % 10 == 0:
            _persist_cache()
    except Exception:
        pass

    return out


def generate_db_response(
    query: str,
    intent: Optional[str] = None,
    db_context: Optional[str] = None,
    force_refresh: bool = False,
) -> str:
    """Blocking wrapper around generate_db_response_async"""
    return asyncio.run(
        generate_db_response_async(query, intent, db_context, force_refresh)
    )


if __name__ == "__main__":
    example_query = os.getenv(
        "SHOPHUB_TEST_QUERY", "SELECT id, name FROM products LIMIT 5;"
    )
    print("Running example query:", example_query)
    try:
        result = generate_db_response(example_query)
        print(result)
    except Exception as exc:
        print("[llm_gen] runtime error:", exc)
