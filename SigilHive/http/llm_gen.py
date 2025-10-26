# shophub_llm_gen.py
import os
import json
import time
import asyncio
import hashlib
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


def sanitize(text: str) -> str:
    """Remove sensitive patterns"""
    if not isinstance(text, str):
        return ""

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

INTENT-SPECIFIC GUIDELINES:
- home: Generate attractive homepage with featured products, categories, promotional banners
- product_page: Show product details with images, price, add to cart button, reviews
- shopping: Display cart items with subtotal, checkout button, or checkout form
- auth: Show login/register form with email, password fields
- admin: Show admin login form or dashboard (redirect if not authenticated)
- api: Return JSON response with appropriate data structure
- static_page: Return informational content (about us, contact, help)
- static: Return appropriate content for static resources
- suspicious: Return error page (403 Forbidden or 404 Not Found)

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

FORMAT:
- For HTML pages: Return complete HTML document with <!DOCTYPE html>
- For API endpoints: Return valid JSON with appropriate structure
- For errors: Return styled error page matching ShopHub design
- For static files (.css, .js): Return appropriate content or empty response

EXAMPLES:

Home page (status 200):
- Hero banner with "Welcome to ShopHub"
- Featured product grid (3-4 products)
- Category cards (Electronics, Clothing, Home)
- Call-to-action buttons
- Search bar in header

Product listing (status 200):
- Product grid with images, names, prices
- Filter sidebar (categories, price range)
- Sort options
- Pagination

Product detail (status 200):
- Large product image
- Product name, price, description
- Add to Cart button
- Quantity selector
- Customer reviews section

Cart page (status 200):
- List of cart items with images, names, quantities, prices
- Subtotal calculation
- Proceed to Checkout button
- Continue Shopping link

Login page (status 200):
- Email and password input fields
- Login button
- "Forgot password?" link
- "Don't have an account? Register" link

API response for /api/products (status 200):
{{"success": true, "products": [{{"id": 1, "name": "Product Name", "price": 99.99}}], "total": 25}}

Error page (status 404):
- "404 - Page Not Found" heading
- Friendly message
- Link back to home
- ShopHub branding maintained

Admin login (status 401 if not auth):
- "Admin Access Required" heading
- Username and password fields
- Secure login form
- Warning about unauthorized access

NOW GENERATE THE RESPONSE:
Generate ONLY the response body content (HTML, JSON, or text).
Do not include HTTP headers or status codes in the output.
Make it realistic, professional, and appropriate for ShopHub e-commerce platform.
"""

    return prompt


def _get_llm_client():
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.4,
        max_output_tokens=4096,
        api_key=GEMINI_KEY,
    )


def _call_gemini_sync(prompt: str) -> str:
    """Synchronous call to Gemini"""
    client = _get_llm_client()
    try:
        resp = client.invoke([HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        text = "<html><body><h1>Error</h1><p>Service temporarily unavailable</p></body></html>"
        print(f"[llm_gen] Gemini error: {e}")
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
        return _cache[cache_key]

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
        out = generate_fallback_response(path, intent, status_code)

    # Sanitize and cache
    out = sanitize(out)
    _cache[cache_key] = out

    # Persist cache periodically
    if int(time.time()) % 10 == 0:
        _persist_cache()

    return out


def generate_fallback_response(path: str, intent: str, status_code: int) -> str:
    """Generate simple fallback responses when LLM fails"""

    if status_code == 404:
        return """<!DOCTYPE html>
<html>
<head>
    <title>404 - Page Not Found | ShopHub</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #e74c3c; font-size: 48px; margin: 0; }
        p { color: #666; font-size: 18px; margin: 20px 0; }
        a { color: #3498db; text-decoration: none; font-weight: bold; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <p>Oops! The page you're looking for doesn't exist.</p>
        <p><a href="/">Return to ShopHub Home</a></p>
    </div>
</body>
</html>"""

    elif status_code == 403:
        return """<!DOCTYPE html>
<html>
<head>
    <title>403 - Forbidden | ShopHub</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #e74c3c; font-size: 48px; margin: 0; }
        p { color: #666; font-size: 18px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>403 Forbidden</h1>
        <p>You don't have permission to access this resource.</p>
    </div>
</body>
</html>"""

    elif intent == "api":
        return '{"success": false, "error": "Service temporarily unavailable"}'

    else:
        return """<!DOCTYPE html>
<html>
<head>
    <title>ShopHub - Your Online Shopping Destination</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        header { background: #2c3e50; color: white; padding: 20px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .header-content { max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 28px; font-weight: bold; }
        nav a { color: white; text-decoration: none; margin-left: 30px; }
        nav a:hover { color: #3498db; }
        .hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 80px 20px; text-align: center; }
        .hero h1 { font-size: 48px; margin-bottom: 20px; }
        .hero p { font-size: 20px; margin-bottom: 30px; }
        .btn { display: inline-block; padding: 15px 30px; background: white; color: #667eea; text-decoration: none; border-radius: 5px; font-weight: bold; }
        .btn:hover { background: #f0f0f0; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .product-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 30px; margin-top: 40px; }
        .product-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
        .product-card img { width: 100%; height: 200px; object-fit: cover; border-radius: 5px; margin-bottom: 15px; }
        .product-card h3 { font-size: 18px; margin-bottom: 10px; color: #2c3e50; }
        .price { font-size: 24px; color: #27ae60; font-weight: bold; margin: 10px 0; }
        footer { background: #2c3e50; color: white; padding: 40px 20px; margin-top: 60px; text-align: center; }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="logo">🛒 ShopHub</div>
            <nav>
                <a href="/">Home</a>
                <a href="/products">Products</a>
                <a href="/cart">Cart</a>
                <a href="/login">Login</a>
            </nav>
        </div>
    </header>
    
    <div class="hero">
        <h1>Welcome to ShopHub</h1>
        <p>Your one-stop destination for online shopping</p>
        <a href="/products" class="btn">Start Shopping</a>
    </div>
    
    <div class="container">
        <h2 style="text-align: center; margin-bottom: 20px;">Featured Products</h2>
        <div class="product-grid">
            <div class="product-card">
                <div style="background: #e0e0e0; width: 100%; height: 200px; border-radius: 5px; margin-bottom: 15px;"></div>
                <h3>Wireless Headphones</h3>
                <p class="price">$79.99</p>
                <a href="/product/1" class="btn" style="font-size: 14px; padding: 10px 20px;">View Details</a>
            </div>
            <div class="product-card">
                <div style="background: #e0e0e0; width: 100%; height: 200px; border-radius: 5px; margin-bottom: 15px;"></div>
                <h3>Smart Watch</h3>
                <p class="price">$199.99</p>
                <a href="/product/2" class="btn" style="font-size: 14px; padding: 10px 20px;">View Details</a>
            </div>
            <div class="product-card">
                <div style="background: #e0e0e0; width: 100%; height: 200px; border-radius: 5px; margin-bottom: 15px;"></div>
                <h3>Laptop Stand</h3>
                <p class="price">$49.99</p>
                <a href="/product/3" class="btn" style="font-size: 14px; padding: 10px 20px;">View Details</a>
            </div>
        </div>
    </div>
    
    <footer>
        <p>&copy; 2025 ShopHub. All rights reserved.</p>
        <p style="margin-top: 10px;">
            <a href="/about" style="color: white; margin: 0 10px;">About</a>
            <a href="/contact" style="color: white; margin: 0 10px;">Contact</a>
            <a href="/help" style="color: white; margin: 0 10px;">Help</a>
        </p>
    </footer>
</body>
</html>"""


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
