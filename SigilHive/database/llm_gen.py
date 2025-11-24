# shophub_db_llm_gen.py
import os
import json
import time
import asyncio
import hashlib
import re
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
    text = re.sub(r"```(?:json|JSON)?", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)

    # Strip surrounding whitespace
    text = text.strip()

    # Attempt to extract the first top-level JSON object {...}
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
                # Validate candidate is JSON
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
   Example: {{"columns": ["id", "name", "price"], "rows": [[1, "Laptop", "999.99"], [2, "Mouse", "29.99"]]}}
   
   CRITICAL FORMAT REQUIREMENTS:
   - Do NOT wrap in markdown code blocks (no ```json or ```)
   - Do NOT add any explanatory text before or after the JSON
   - Return ONLY the raw JSON object
   - All row values must be simple types (strings, numbers, null)

2. QUERY ANALYSIS - READ THE QUERY CAREFULLY:
   - If query has WHERE id=X, return ONLY 1 row with that exact id
   - If query has WHERE condition, return ONLY rows matching that condition
   - If query has LIMIT N, return EXACTLY N rows (or fewer if condition limits it)
   - If query has no WHERE/LIMIT, return 5-10 rows
   - If WHERE id=X and no match would exist, return 0 rows (empty array)
   
   Examples:
   - "SELECT * FROM users WHERE id=5" → 1 row with id=5
   - "SELECT * FROM products WHERE id IN (1,2,3)" → 3 rows with ids 1,2,3
   - "SELECT * FROM orders WHERE user_id=10" → 1-5 rows all with user_id=10
   - "SELECT * FROM products LIMIT 3" → exactly 3 rows
   - "SELECT * FROM users WHERE id=999" → empty rows array (id doesn't exist)

3. ID GENERATION:
   - For WHERE id=X queries: use EXACTLY that id value
   - For WHERE id IN (...): use EXACTLY those id values
   - For queries without WHERE on id: use sequential ids (1, 2, 3, 4, ...)
   - NEVER repeat the same id value in multiple rows unless the query requires it

4. For DESCRIBE/DESC queries:
   - Return column information from the DATABASE CONTEXT above
   - Format: {{"columns": ["Field", "Type", "Null", "Key", "Default", "Extra"], "rows": [["id", "int", "NO", "PRI", null, "auto_increment"], ...]}}

5. For DDL/DML (CREATE, INSERT, UPDATE, DELETE): Return confirmation message
   Example: Query OK, 1 row affected

6. For errors: Return ERROR XXXX (SQLSTATE): message
   Example: ERROR 1146 (42S02): Table 'products' doesn't exist

7. SECURITY:
   - Never expose real passwords (use $2b$10$[REDACTED] format)
   - Never expose full credit card numbers
   - Redact transaction IDs as txn_[REDACTED]

8. DATA GENERATION (IMPORTANT):
   - Generate REALISTIC, VARIED data for each row
   - Use realistic names, emails, addresses, product names, prices
   - Use realistic timestamps (dates from 2024-2025)
   - Vary the data - don't repeat patterns (different names, emails, dates)
   - Make it look like REAL production e-commerce data

9. COLUMN NAMES:
   - Use EXACT column names from the schema in DATABASE CONTEXT
   - If query has SELECT *, use all columns from the table schema
   - If query specifies columns, use only those columns

CRITICAL OUTPUT FORMAT:
- Your ENTIRE response must be ONLY the JSON object (for SELECT) or message text (for others)
- NO markdown formatting
- NO code blocks
- NO explanations
- Just the raw JSON or message

Generate the response now:
"""
    return prompt


def _get_llm_client():
    """Instantiate the Gemini (Google) client wrapper."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3,
        max_output_tokens=2048,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Call Gemini synchronously and return text content."""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        if hasattr(resp, "content"):
            content = resp.content
            if isinstance(content, list):
                text = " ".join(map(str, content))
            else:
                text = str(content)
        else:
            text = str(resp)

        # Clean up the response
        text = clean_json_response(text)

        # Validate it's proper JSON for SELECT queries
        if text.strip().startswith("{"):
            try:
                parsed = json.loads(text)
                if "columns" in parsed and "rows" in parsed:
                    # Re-serialize to ensure clean JSON
                    text = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

    except Exception as e:
        text = f"ERROR: Database temporarily unavailable - {e}"

    return sanitize(text)


async def generate_db_response_async(
    query: str,
    intent: Optional[str] = None,
    db_context: Optional[str] = None,
    force_refresh: bool = False,
) -> str:
    """Generate database response using LLM (async wrapper)."""
    key_raw = f"query:{query}|intent:{intent}|ctx:{db_context or ''}"
    cache_key = _cache_key("db", key_raw)

    if not force_refresh and cache_key in _cache:
        print(f"[llm_gen] Using cached response for query")
        return _cache[cache_key]

    prompt = _build_prompt(query, intent, db_context)

    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error during LLM call: {e}")
        out = "ERROR 1064 (42000): Internal server error"

    out = sanitize(out)
    _cache[cache_key] = out

    # Persist occasionally
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
        "SHOPHUB_TEST_QUERY", "SELECT id, name, price FROM products LIMIT 5;"
    )
    print("Running example query:", example_query)
    try:
        result = generate_db_response(example_query)
        print(result)
    except Exception as exc:
        print("[llm_gen] runtime error:", exc)
