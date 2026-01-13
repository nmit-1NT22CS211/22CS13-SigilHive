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


def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Aggressively extract JSON from LLM response.
    Returns dict if valid JSON found, None otherwise.
    """
    if not isinstance(text, str):
        return None

    text = text.strip()

    # Remove markdown code blocks
    text = text.replace("```json", "").replace("```", "").strip()

    # Strategy 1: Direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except:
        pass

    # Strategy 2: Find first complete JSON object using brace counting
    if "{" in text:
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
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    return data
            except:
                pass

    # Strategy 3: Find between first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except:
            pass

    return None


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

CRITICAL RESPONSE RULES:

1. **For SELECT/SHOW queries - RETURN ONLY VALID JSON:**
   - Output format: {{"columns": ["col1", "col2"], "rows": [[val1, val2], [val3, val4]]}}
   - DO NOT add ANY text before or after the JSON
   - DO NOT wrap in markdown code blocks (no ```json or ```)
   - DO NOT add explanations or comments
   - Just pure JSON with "columns" and "rows" keys

2. **For DESCRIBE queries:**
   - ONLY return columns that EXIST in the DATABASE CONTEXT
   - Use EXACT column names from the schema
   - Format: {{"columns": ["Field", "Type", "Null", "Key", "Default", "Extra"], "rows": [["id", "int", "NO", "PRI", null, "auto_increment"], ...]}}

3. **For DDL/DML (CREATE, INSERT, UPDATE, DELETE):**
   - Return: "Query OK, 1 row affected"

4. **For errors:**
   - Return: "ERROR XXXX (SQLSTATE): message"

5. **SECURITY - Always redact:**
   - Passwords: use $2b$10$[REDACTED]
   - Credit cards: mask all but last 4 digits
   - API keys: [REDACTED]
   - Transaction IDs: txn_[REDACTED] or PAY-[REDACTED]

6. **DATA GENERATION (VERY IMPORTANT):**
   - Generate 20-50 rows of realistic, varied data
   - Use realistic names, emails, addresses, products, prices
   - Vary the data - don't repeat patterns
   - Use realistic timestamps from 2024-2025
   - Sequential IDs (1, 2, 3, ...)

7. **OUTPUT FORMAT:**
   - If query expects table results (SELECT/SHOW/DESCRIBE): Output ONLY JSON, nothing else
   - If query is DDL/DML: Output only the status message
   - Column names must EXACTLY match schema in DATABASE CONTEXT

EXAMPLE OUTPUT FOR SELECT:
{{"columns": ["id", "name", "price"], "rows": [[1, "Laptop", 999.99], [2, "Mouse", 29.99], [3, "Keyboard", 79.99]]}}

Now generate the response for the query above. Remember: If it's a SELECT/SHOW/DESCRIBE query, output ONLY the JSON object with no additional text or formatting.
"""
    return prompt


def _get_llm_client():
    """Instantiate the Gemini (Google) client wrapper."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,
        max_output_tokens=4096,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Call Gemini synchronously and return text content. Handles basic exceptions."""
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

        print(f"[llm_gen] Raw LLM response (first 500 chars): {text[:500]}")

        # Clean up the response
        text = text.strip()

    except Exception as e:
        print(f"[llm_gen] LLM call error: {e}")
        text = f"ERROR: Database temporarily unavailable - {e}"

    return text


async def generate_db_response_async(
    query: str,
    intent: Optional[str] = None,
    db_context: Optional[str] = None,
    force_refresh: bool = False,
) -> dict:
    """
    Generate database response using LLM (async wrapper).
    Returns dict with either:
    - {"columns": [...], "rows": [...]} for SELECT/SHOW queries
    - {"text": "..."} for other queries
    """
    key_raw = f"query:{query}|intent:{intent}|ctx:{db_context or ''}"
    cache_key = _cache_key("db", key_raw)

    if not force_refresh and cache_key in _cache:
        cached = _cache[cache_key]
        print(f"[llm_gen] Cache hit for query: {query[:50]}...")
        # Ensure cached value is a dict
        if isinstance(cached, str):
            json_data = extract_json_from_response(cached)
            if json_data:
                return json_data
            return {"text": cached}
        return cached

    prompt = _build_prompt(query, intent, db_context)

    try:
        raw_response = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error during LLM call: {e}")
        return {"text": "ERROR 1064 (42000): Internal server error"}

    # Sanitize
    raw_response = sanitize(raw_response)

    # Try to extract JSON
    json_data = extract_json_from_response(raw_response)

    if json_data:
        # Validate it has the right structure
        if "columns" in json_data and "rows" in json_data:
            print(
                f"[llm_gen] ✓ Valid JSON extracted with {len(json_data.get('rows', []))} rows"
            )
            result = json_data
        else:
            print("[llm_gen] JSON found but missing columns/rows keys")
            result = {"text": raw_response}
    else:
        print("[llm_gen] No valid JSON found, wrapping as text")
        result = {"text": raw_response}

    # Cache the result
    _cache[cache_key] = result

    # Periodically persist cache
    try:
        if int(time.time()) % 10 == 0:
            _persist_cache()
    except Exception:
        pass

    return result


def generate_db_response(
    query: str,
    intent: Optional[str] = None,
    db_context: Optional[str] = None,
    force_refresh: bool = False,
) -> dict:
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
        print("Result:", json.dumps(result, indent=2))
    except Exception as exc:
        print("[llm_gen] runtime error:", exc)
