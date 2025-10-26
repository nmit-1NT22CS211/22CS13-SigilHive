# shophub_db_llm_gen.py
import os
import json
import time
import asyncio
import hashlib
import re
from typing import Optional
from dotenv import load_dotenv

# Note: these imports assume you have these libraries available in your environment.
# If the actual package/module names differ in your environment, adjust accordingly.
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

    if len(out) > 10000:
        out = out[:10000] + "\n...[truncated]"

    return out


def clean_json_response(text: str) -> str:
    """
    Remove markdown code blocks and extra formatting from LLM response and
    attempt to extract a single JSON object if present.

    Returns cleaned text (JSON string if JSON could be isolated, otherwise original cleaned text).
    """
    if not isinstance(text, str):
        return ""

    # Remove triple-backtick fenced blocks (any language) and inline code fences
    # Replace fenced blocks with their content (strip fences)
    text = re.sub(
        r"```(?:[\s\S]*?\n)?", "", text
    )  # remove opening ``` and anything up to newline
    text = re.sub(r"```", "", text)  # remove closing ```
    text = re.sub(r"`([^`]*)`", r"\1", text)

    # Strip surrounding whitespace
    text = text.strip()

    # Attempt to extract the first top-level JSON object {...}
    # Use a simple brace matching: find the first '{' and match braces until balanced.
    if "{" in text and "}" in text:
        start = text.find("{")
        # attempt to find matching closing brace using a counter
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
                # Validate candidate is JSON
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                # fallthrough to returning cleaned text
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

CRITICAL:
- Your response must be ONLY the JSON object or the message text
- For SELECT queries, generate AT LEAST 20-30 rows with VARIED, REALISTIC data

Generate the response now:
"""
    return prompt


def _get_llm_client():
    """Instantiate the Gemini (Google) client wrapper."""
    # This wrapper call may vary depending on your installed library's API.
    # Adjust model and kwargs to match your environment if necessary.
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.3,
        max_output_tokens=2048,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Call Gemini synchronously and return text content. Handles basic exceptions."""
    client = _get_llm_client()
    try:
        # The exact invocation may vary depending on the wrapper implementation.
        # Here we assume .invoke takes a list of HumanMessage and returns an object with `.content`.
        resp = client.invoke([HumanMessage(content=prompt)])
        # resp might be a plain string, or an object. Try to pull content robustly.
        if hasattr(resp, "content"):
            # content could be a string or list; handle common cases
            content = resp.content
            if isinstance(content, list):
                # join list segments into one string
                text = " ".join(map(str, content))
            else:
                text = str(content)
        else:
            text = str(resp)

        # Clean up the response (remove markdown, extract json if present)
        text = clean_json_response(text)

    except Exception as e:
        # Return a standard SQL-like error string for downstream handling
        text = f"ERROR: Database temporarily unavailable - {e}"
    return sanitize(text)


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
        # Run the synchronous LLM call in a thread to avoid blocking the event loop
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error during LLM call: {e}")
        out = "ERROR 1064 (42000): Internal server error"

    out = sanitize(out)
    _cache[cache_key] = out

    # Persist occasionally to avoid frequent disk writes. We use a time-based simple heuristic.
    try:
        if int(time.time()) % 10 == 0:
            _persist_cache()
    except Exception:
        # don't let persistence errors bubble up
        pass

    return out


# Optional convenience synchronous wrapper for callers that want blocking behaviour
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
    # Simple CLI test: read a query from environment or example and print output
    example_query = os.getenv(
        "SHOPHUB_TEST_QUERY", "SELECT id, name FROM products LIMIT 5;"
    )
    print("Running example query:", example_query)
    try:
        result = generate_db_response(example_query)
        print(result)
    except Exception as exc:
        print("[llm_gen] runtime error:", exc)
