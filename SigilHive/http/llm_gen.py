# shophub_llm_gen.py
import os
import json
import time
import asyncio
import hashlib
import re
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[llm_gen] WARNING: GEMINI_API_KEY not set. Set it in .env or env vars.")

CACHE_PATH = "shophub_cache.json"
_cache = {}

# Load cache
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


def clean_llm_output(text: str) -> str:
    """Remove markdown code blocks and other formatting artifacts from LLM output"""
    if not isinstance(text, str):
        return ""

    # Remove markdown code blocks (```html, ```json, ```, etc.)
    # Pattern: ```language\n content \n```
    text = re.sub(r"^```[\w]*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n```$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```[\w]*", "", text)
    text = re.sub(r"```$", "", text)

    # Remove any remaining triple backticks
    text = text.replace("```", "")

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def sanitize(text: str) -> str:
    """Remove sensitive patterns"""
    if not isinstance(text, str):
        return ""

    # First clean markdown artifacts
    text = clean_llm_output(text)

    # Replace sensitive data with placeholders
    replacements = {
        "sk_live_": "[REDACTED_STRIPE_KEY]",
        "sk_test_": "[REDACTED_STRIPE_KEY]",
        "password=": "password=[REDACTED]",
        "api_key=": "api_key=[REDACTED]",
        "-----BEGIN": "[REDACTED_KEY]-----BEGIN",
    }

    out = text
    for pattern, replacement in replacements.items():
        if pattern in out:
            out = out.replace(pattern, replacement)

    # Limit length
    if len(out) > 12000:
        out = out[:12000] + "\n...[content truncated]"

    return out


def _build_shophub_prompt(
    method: str,
    path: str,
    headers: dict,
    body: str = None,
    intent: str = None,
    status_code: int = 200,
    server_context: str = None,
) -> str:
    """Build prompt for ShopHub response generation"""

    headers_str = "\n".join([f"{k}: {v}" for k, v in (headers or {}).items()])
    body_str = f"\nRequest Body:\n{body}" if body else ""

    prompt = f"""You are generating realistic HTTP responses for the ShopHub e-commerce platform honeypot.

SHOPHUB CONTEXT:
{server_context or "ShopHub - Modern E-commerce Platform"}

REQUEST DETAILS:
Method: {method}
Path: {path}
Intent: {intent}
Expected Status Code: {status_code}

Headers:
{headers_str}
{body_str}

RESPONSE GENERATION RULES:
1. Generate a complete, realistic HTML/JSON response that ShopHub would return
2. For status code {status_code}, generate appropriate content
3. Match the response to the intent: {intent}
4. ALWAYS generate a response - never refuse or say you cannot generate content
5. Be creative and realistic - make it look like a real e-commerce site

INTENT-SPECIFIC GUIDELINES:
- home: Generate attractive homepage with featured products, categories, promotional banners
- product_page: Show product details with images, price, add to cart button, reviews
- shopping: Display cart items with subtotal, checkout button, or checkout form
- auth: Show login/register form with email, password fields
- admin: Show admin login form or dashboard (redirect if not authenticated)
- api: Return JSON response with appropriate data structure
- static_page: Return informational content (about us, contact, help)
- static: Return appropriate content for static resources (.css, .js files should have realistic content)
- suspicious: Return error page (403 Forbidden or 404 Not Found)
- other: Generate appropriate page based on the path

SECURITY RULES:
- DO NOT include real passwords, API keys, private keys, or sensitive credentials
- Use placeholder values like "[REDACTED]", "demo@example.com", "***" for sensitive fields
- For admin pages, show realistic UI but don't expose real system information
- For error pages, return generic error messages without revealing system details

STYLING:
- Use modern, clean HTML5 with inline CSS or reference to /assets/css/style.css
- Include realistic navigation bar with: Home, Products, Cart, Login/Account
- Use professional color scheme: primary blues/purples, white backgrounds
- Include ShopHub logo/branding in header
- Add footer with links: About, Contact, Help, Terms, Privacy

FORMAT REQUIREMENTS:
- For HTML pages: Return complete HTML document starting with <!DOCTYPE html>
- For API endpoints: Return valid JSON with appropriate structure
- For errors (404, 403, 500): Return styled error page matching ShopHub design
- For CSS files: Return actual CSS code with styles for the website
- For JavaScript files: Return actual JavaScript code (can be simple/placeholder but should be valid JS)
- For image requests (.jpg, .png, .gif): Return HTML comment indicating image placeholder

EXAMPLES BY INTENT:

HOME PAGE (status 200):
<!DOCTYPE html>
<html>
<head>
    <title>ShopHub - Your Online Shopping Destination</title>
    <style>
        /* Modern e-commerce styling */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #f8f9fa; }}
        /* ... more styles ... */
    </style>
</head>
<body>
    <header>
        <nav>Home | Products | Cart | Login</nav>
    </header>
    <section class="hero">
        <h1>Welcome to ShopHub</h1>
        <p>Your one-stop destination for online shopping</p>
    </section>
    <section class="featured-products">
        <!-- Product cards here -->
    </section>
    <footer>&copy; 2025 ShopHub</footer>
</body>
</html>

PRODUCT PAGE (status 200):
Generate full product detail page with image placeholder, price, description, add to cart button, reviews section

CART PAGE (status 200):
Generate shopping cart with items list, subtotal, checkout button

API RESPONSE (status 200):
{{"success": true, "data": {{"products": [...], "total": 10}}, "message": "Success"}}

ERROR PAGE (status 404):
Generate styled 404 page with ShopHub branding, friendly message, link back to home

CSS FILE REQUEST (status 200):
/* ShopHub Main Styles */
body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
.header {{ background: #2c3e50; color: white; padding: 20px; }}
/* ... more CSS rules ... */

JAVASCRIPT FILE REQUEST (status 200):
// ShopHub Frontend JavaScript
document.addEventListener('DOMContentLoaded', function() {{
    // Cart functionality
    console.log('ShopHub initialized');
}});

CRITICAL OUTPUT REQUIREMENTS:
- Output ONLY the raw response content without any markdown formatting
- DO NOT wrap output in ```html or ``` or any markdown syntax
- DO NOT include HTTP headers or status codes in the output
- Return pure HTML, JSON, CSS, or JavaScript content directly
- Start immediately with the content (<!DOCTYPE html> for HTML, {{ for JSON, etc.)
- Make it realistic and complete - this is a honeypot, so quality matters!

NOW GENERATE THE RESPONSE FOR: {method} {path} (Status: {status_code}, Intent: {intent})
"""

    return prompt


def _get_llm_client():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,  # Increased for more variety
        max_output_tokens=4096,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Synchronous call to Gemini"""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)

        # If response is empty or too short, try again with emphasis
        if not text or len(text.strip()) < 50:
            print("[llm_gen] Response too short, retrying...")
            resp = client.invoke(
                [
                    HumanMessage(
                        content=prompt
                        + "\n\nIMPORTANT: Generate a COMPLETE response with full HTML/JSON content."
                    )
                ]
            )
            text = resp.content if hasattr(resp, "content") else str(resp)

    except Exception as e:
        print(f"[llm_gen] Gemini error: {e}")
        # Return minimal error response
        text = "<html><body><h1>Error</h1><p>Service temporarily unavailable</p></body></html>"

    return sanitize(text)


async def generate_shophub_response_async(
    method: str,
    path: str,
    headers: dict = None,
    body: str = None,
    intent: str = None,
    status_code: int = 200,
    server_context: str = None,
    force_refresh: bool = False,
) -> str:
    """Generate ShopHub response using LLM"""

    # Create cache key
    key_raw = f"shophub:{method}|{path}|{intent}|{status_code}"
    cache_key = _cache_key("response", key_raw)

    if not force_refresh and cache_key in _cache:
        print(f"[llm_gen] Cache hit for {method} {path}")
        return _cache[cache_key]

    print(
        f"[llm_gen] Generating response for {method} {path} (intent: {intent}, status: {status_code})"
    )

    # Build prompt
    prompt = _build_shophub_prompt(
        method=method,
        path=path,
        headers=headers or {},
        body=body,
        intent=intent,
        status_code=status_code,
        server_context=server_context,
    )

    # Call LLM in thread
    try:
        out = await asyncio.to_thread(_call_gemini_sync, prompt)
    except Exception as e:
        print(f"[llm_gen] Error generating response: {e}")
        # Minimal fallback only for critical errors
        out = "<html><body><h1>Error</h1><p>Service Error</p></body></html>"

    # Sanitize and cache
    out = sanitize(out)

    # Verify output is not empty
    if not out or len(out.strip()) < 20:
        print(f"[llm_gen] WARNING: Generated response too short for {path}")
        out = f"<html><body><h1>ShopHub</h1><p>Content loading...</p></body></html>"

    _cache[cache_key] = out

    # Persist cache periodically
    if int(time.time()) % 10 == 0:
        _persist_cache()

    print(f"[llm_gen] Generated {len(out)} bytes for {path}")
    return out


# Sync wrapper
def generate_shophub_response(
    method: str,
    path: str,
    headers: dict = None,
    body: str = None,
    intent: str = None,
    status_code: int = 200,
    server_context: str = None,
    force_refresh: bool = False,
) -> str:
    return asyncio.get_event_loop().run_until_complete(
        generate_shophub_response_async(
            method,
            path,
            headers,
            body,
            intent,
            status_code,
            server_context,
            force_refresh,
        )
    )
