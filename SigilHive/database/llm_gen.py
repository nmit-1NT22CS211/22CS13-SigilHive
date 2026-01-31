import os
import json
import time
import asyncio
import hashlib
import re
from typing import Optional
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
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
    Aggressively extract JSON from LLM response using multiple strategies.
    Returns dict if valid JSON found, None otherwise.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    text = text.strip()

    # Strategy 1: Remove markdown code blocks first
    text_clean = re.sub(r'```json\s*', '', text)
    text_clean = re.sub(r'```\s*', '', text_clean)
    text_clean = text_clean.strip()

    # Strategy 2: Try direct parse on cleaned text
    try:
        data = json.loads(text_clean)
        if isinstance(data, dict) and ('columns' in data or 'text' in data or 'error' in data):
            return data
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find JSON between first { and matching }
    if "{" in text_clean:
        start = text_clean.find("{")
        brace_count = 0
        end = -1

        for i in range(start, len(text_clean)):
            if text_clean[i] == "{":
                brace_count += 1
            elif text_clean[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i
                    break

        if start != -1 and end != -1 and end > start:
            json_str = text_clean[start : end + 1]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    # Strategy 4: Remove common preambles and try again
    patterns_to_remove = [
        r'^.*?(?:here\'s|here is|output|result|response):\s*',
        r'^[^{]*(?=\{)',  # Everything before first {
    ]
    
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        # Also remove everything after last }
        if '}' in cleaned:
            last_brace = cleaned.rfind('}')
            cleaned = cleaned[:last_brace + 1]
        
        try:
            data = json.loads(cleaned.strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    # Strategy 5: Look for JSON array format (sometimes LLMs return this)
    if text_clean.strip().startswith('['):
        try:
            data = json.loads(text_clean)
            if isinstance(data, list) and len(data) > 0:
                # Try to convert to expected format
                if isinstance(data[0], dict):
                    columns = list(data[0].keys())
                    rows = [[row.get(col) for col in columns] for row in data]
                    return {"columns": columns, "rows": rows}
        except json.JSONDecodeError:
            pass

    return None


def _build_prompt(
    query: str, intent: Optional[str] = None, db_context: Optional[str] = None
) -> str:
    """Build an improved, more directive prompt for MySQL simulation."""
    
    # Classify query type for better prompting
    query_lower = query.lower().strip()
    is_select = any(kw in query_lower for kw in ['select', 'show', 'describe', 'desc', 'explain'])
    is_ddl = any(kw in query_lower for kw in ['insert', 'update', 'delete', 'create', 'alter', 'drop'])
    
    if is_select:
        format_instruction = """Output ONLY a JSON object in this EXACT format with NO other text:
{"columns": ["col1", "col2"], "rows": [[val1, val2], [val3, val4]]}

CRITICAL: 
- Start your response with {
- End your response with }
- NO markdown code blocks
- NO explanations before or after
- NO extra text whatsoever"""
    else:
        format_instruction = """Output ONLY a status message:
For successful DDL/DML: "Query OK, N row(s) affected"
For errors: "ERROR 1234 (SQLSTATE): message"

CRITICAL: 
- Just the status message
- NO explanations
- NO extra text"""

    prompt = f"""You are a MySQL 8.0 database simulator for ShopHub e-commerce platform.

DATABASE SCHEMA:
{db_context or "ShopHub E-commerce Database"}

QUERY TO EXECUTE:
{query}

{format_instruction}

DATA GENERATION RULES (for SELECT queries):
- Generate 20-50 realistic, varied rows
- Use realistic names, emails, addresses, products, prices
- Vary the data - don't repeat patterns
- Use timestamps from 2024-2025
- Sequential IDs starting from 1
- Use EXACT column names from the schema above

SECURITY (always apply):
- Passwords: $2b$10$[REDACTED]
- Credit cards: mask to last 4 digits (e.g., ****1234)
- API keys: [REDACTED]
- Transaction IDs: txn_[REDACTED], PAY-[REDACTED]

Now generate the response following the format above:"""

    return prompt


def _get_llm_client():
    """Instantiate the Gemini client with optimized settings."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",  # Use latest model for better instruction following
        temperature=0.2,  # Lower temperature for more consistent outputs
        max_output_tokens=8192,  # Increased for larger result sets
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """
    Call Gemini synchronously with improved error handling.
    Uses system message to enforce JSON output for SELECT queries.
    """
    client = _get_llm_client()
    
    try:
        # Check if this is a SELECT query to add system message
        is_select_query = any(kw in prompt.lower() for kw in ['select', 'show', 'describe'])
        
        if is_select_query:
            # Add system message to enforce JSON
            system_msg = SystemMessage(
                content="You must respond with ONLY valid JSON. No markdown, no explanations, just pure JSON starting with { and ending with }."
            )
            messages = [system_msg, HumanMessage(content=prompt)]
        else:
            messages = [HumanMessage(content=prompt)]
        
        resp = client.invoke(messages)

        if hasattr(resp, "content"):
            content = resp.content
            if isinstance(content, list):
                text = " ".join(map(str, content))
            else:
                text = str(content)
        else:
            text = str(resp)

        # Log first 300 chars for debugging
        print(f"[llm_gen] Raw LLM response (first 300 chars): {text[:300]}")

        return text.strip()

    except Exception as e:
        print(f"[llm_gen] LLM call error: {e}")
        return f"ERROR 2013 (HY000): Lost connection to database server during query - {e}"


def _validate_and_fix_json(data: dict) -> dict:
    """
    Validate and fix common issues in LLM-generated JSON.
    Ensures proper structure for database responses.
    """
    if not isinstance(data, dict):
        return {"text": str(data)}
    
    # If it's already a text/error response, return as-is
    if 'text' in data or 'error' in data:
        return data
    
    # For SELECT responses, ensure proper structure
    if 'columns' in data or 'rows' in data:
        # Ensure both keys exist
        if 'columns' not in data:
            data['columns'] = []
        if 'rows' not in data:
            data['rows'] = []
        
        # Fix columns - ensure it's a list of strings
        if not isinstance(data['columns'], list):
            data['columns'] = []
        else:
            data['columns'] = [str(col) for col in data['columns']]
        
        # Fix rows - ensure it's a list of lists
        if not isinstance(data['rows'], list):
            data['rows'] = []
        else:
            fixed_rows = []
            for row in data['rows']:
                if isinstance(row, list):
                    fixed_rows.append(row)
                elif isinstance(row, dict):
                    # Convert dict to list based on column order
                    fixed_rows.append([row.get(col) for col in data['columns']])
                else:
                    # Skip invalid rows
                    continue
            data['rows'] = fixed_rows
        
        return data
    
    # If structure is unclear, return as text
    return {"text": json.dumps(data)}


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

    # Check cache
    if not force_refresh and cache_key in _cache:
        cached = _cache[cache_key]
        print(f"[llm_gen] Cache hit for query: {query[:50]}...")
        
        # Ensure cached value is properly structured
        if isinstance(cached, str):
            json_data = extract_json_from_response(cached)
            if json_data:
                return _validate_and_fix_json(json_data)
            return {"text": cached}
        
        return _validate_and_fix_json(cached)

    # Generate prompt
    prompt = _build_prompt(query, intent, db_context)

    # Call LLM
    try:
        raw_response = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error during LLM call: {e}")
        return {"text": f"ERROR 2013 (HY000): Lost connection to MySQL server - {e}"}

    # Sanitize
    raw_response = sanitize(raw_response)

    # Check if it's an error or status message (DDL/DML)
    if raw_response.startswith('ERROR') or raw_response.startswith('Query OK'):
        result = {"text": raw_response}
    else:
        # Try to extract JSON
        json_data = extract_json_from_response(raw_response)
        
        if json_data:
            # Validate and fix structure
            result = _validate_and_fix_json(json_data)
            
            if 'columns' in result and 'rows' in result:
                row_count = len(result.get('rows', []))
                col_count = len(result.get('columns', []))
                print(f"[llm_gen] ✓ Valid JSON extracted: {col_count} columns, {row_count} rows")
            else:
                print(f"[llm_gen] JSON extracted but converted to text format")
        else:
            # No valid JSON found
            print("[llm_gen] ⚠ No valid JSON found, wrapping as text")
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


def format_mysql_table(result: dict) -> str:
    """
    Format a database result into MySQL-style ASCII table.
    
    Args:
        result: Dict with 'columns' and 'rows', or 'text'
    
    Returns:
        Formatted string ready to send to client
    """
    # If it's a text response, return as-is
    if 'text' in result:
        return result['text']
    
    # If it's an error response
    if 'error' in result:
        return result['error']
    
    # If empty result
    if 'columns' not in result or not result['columns']:
        return "Empty set (0.00 sec)"
    
    columns = result['columns']
    rows = result.get('rows', [])
    
    if not rows:
        return "Empty set (0.00 sec)"
    
    # Calculate column widths
    col_widths = [len(str(col)) for col in columns]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                val_str = str(val) if val is not None else 'NULL'
                col_widths[i] = max(col_widths[i], len(val_str))
    
    # Build table
    lines = []
    
    # Top border
    lines.append('+' + '+'.join('-' * (w + 2) for w in col_widths) + '+')
    
    # Header row
    header_parts = []
    for i, col in enumerate(columns):
        header_parts.append(' ' + str(col).ljust(col_widths[i]) + ' ')
    lines.append('|' + '|'.join(header_parts) + '|')
    
    # Separator after header
    lines.append('+' + '+'.join('-' * (w + 2) for w in col_widths) + '+')
    
    # Data rows
    for row in rows:
        row_parts = []
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else 'NULL'
            row_parts.append(' ' + val_str.ljust(col_widths[i]) + ' ')
        lines.append('|' + '|'.join(row_parts) + '|')
    
    # Bottom border
    lines.append('+' + '+'.join('-' * (w + 2) for w in col_widths) + '+')
    
    # Row count
    row_count = len(rows)
    lines.append(f'{row_count} row{"s" if row_count != 1 else ""} in set (0.01 sec)')
    
    return '\n'.join(lines)


if __name__ == "__main__":
    # Test with example queries
    test_queries = [
        "SELECT id, name, email FROM users LIMIT 5;",
        "SHOW TABLES;",
        "DESCRIBE users;",
        "INSERT INTO products (name, price) VALUES ('Test', 99.99);",
    ]
    
    example_query = os.getenv("SHOPHUB_TEST_QUERY", test_queries[0])
    
    db_schema = """
Tables:
- users (id, username, email, created_at, last_login)
- products (id, name, description, price, category, stock)
- orders (id, user_id, total, status, created_at)
- order_items (id, order_id, product_id, quantity, price)
"""
    
    print(f"Running example query: {example_query}")
    print(f"Database schema:\n{db_schema}")
    print("-" * 80)
    
    try:
        result = generate_db_response(example_query, db_context=db_schema)
        print("\nResult structure:", json.dumps(result, indent=2)[:500])
        print("\nFormatted output:")
        print(format_mysql_table(result))
    except Exception as exc:
        print(f"[llm_gen] runtime error: {exc}")