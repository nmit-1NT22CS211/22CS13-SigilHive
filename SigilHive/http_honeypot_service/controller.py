# shophub_controller.py
from typing import Dict, Any, Optional
from .llm_gen import generate_shophub_response_async


class ShopHubState:
    """Maintains ShopHub e-commerce website state"""

    def __init__(self):
        self.pages = self._initialize_pages()
        self.products = self._initialize_products()
        self.api_endpoints = self._initialize_api_endpoints()

    def _initialize_pages(self) -> dict:
        """Initialize ShopHub pages"""
        return {
            "/": {
                "title": "ShopHub - Your Online Shopping Destination",
                "type": "home",
                "exists": True,
            },
            "/index.html": {
                "title": "ShopHub - Your Online Shopping Destination",
                "type": "home",
                "exists": True,
            },
            "/products": {
                "title": "All Products - ShopHub",
                "type": "product_listing",
                "exists": True,
            },
            "/products/electronics": {
                "title": "Electronics - ShopHub",
                "type": "category",
                "exists": True,
            },
            "/products/clothing": {
                "title": "Clothing - ShopHub",
                "type": "category",
                "exists": True,
            },
            "/products/home": {
                "title": "Home & Garden - ShopHub",
                "type": "category",
                "exists": True,
            },
            "/cart": {
                "title": "Shopping Cart - ShopHub",
                "type": "cart",
                "exists": True,
            },
            "/checkout": {
                "title": "Checkout - ShopHub",
                "type": "checkout",
                "exists": True,
            },
            "/login": {"title": "Login - ShopHub", "type": "auth", "exists": True},
            "/register": {
                "title": "Register - ShopHub",
                "type": "auth",
                "exists": True,
            },
            "/account": {
                "title": "My Account - ShopHub",
                "type": "account",
                "exists": True,
            },
            "/orders": {
                "title": "My Orders - ShopHub",
                "type": "orders",
                "exists": True,
            },
            "/admin": {
                "title": "Admin Panel - ShopHub",
                "type": "admin",
                "exists": True,
            },
            "/admin/login": {
                "title": "Admin Login - ShopHub",
                "type": "admin",
                "exists": True,
            },
            "/admin/dashboard": {
                "title": "Admin Dashboard - ShopHub",
                "type": "admin",
                "exists": True,
            },
            "/about": {"title": "About Us - ShopHub", "type": "static", "exists": True},
            "/contact": {
                "title": "Contact Us - ShopHub",
                "type": "static",
                "exists": True,
            },
            "/help": {
                "title": "Help Center - ShopHub",
                "type": "static",
                "exists": True,
            },
            "/robots.txt": {"type": "static", "exists": True},
            "/sitemap.xml": {"type": "static", "exists": True},
        }

    def _initialize_products(self) -> dict:
        """Initialize sample products"""
        return {
            "1": {
                "id": 1,
                "name": "Wireless Bluetooth Headphones",
                "price": 79.99,
                "category": "electronics",
            },
            "2": {
                "id": 2,
                "name": "Cotton T-Shirt",
                "price": 24.99,
                "category": "clothing",
            },
            "3": {
                "id": 3,
                "name": "LED Desk Lamp",
                "price": 39.99,
                "category": "home",
            },
        }

    def _initialize_api_endpoints(self) -> dict:
        """Initialize API endpoints"""
        return {
            "/api/products": {"type": "api", "method": "GET", "exists": True},
            "/api/products/{id}": {"type": "api", "method": "GET", "exists": True},
            "/api/cart": {"type": "api", "method": "GET,POST", "exists": True},
            "/api/orders": {"type": "api", "method": "GET,POST", "exists": True},
            "/api/auth/login": {"type": "api", "method": "POST", "exists": True},
            "/api/auth/register": {"type": "api", "method": "POST", "exists": True},
            "/api/user/profile": {"type": "api", "method": "GET,PUT", "exists": True},
            "/api/search": {"type": "api", "method": "GET", "exists": True},
        }

    def page_exists(self, path: str) -> bool:
        """Check if a page exists"""
        # Normalize path
        if path.endswith("/") and path != "/":
            path = path[:-1]

        # Check exact match
        if path in self.pages:
            return True

        # Check API endpoints
        if path.startswith("/api/"):
            if path in self.api_endpoints:
                return True
            # Check pattern matches (e.g., /api/products/123)
            for endpoint in self.api_endpoints:
                if "{id}" in endpoint:
                    pattern = endpoint.replace("{id}", r"\d+")
                    import re

                    if re.match(pattern, path):
                        return True

        # Check product pages
        if path.startswith("/product/"):
            return True

        return False

    def get_page_info(self, path: str) -> Optional[Dict]:
        """Get page information"""
        if path.endswith("/") and path != "/":
            path = path[:-1]

        if path in self.pages:
            return self.pages[path]

        if path in self.api_endpoints:
            return self.api_endpoints[path]

        return None

    def get_state_summary(self) -> str:
        """Get summary for LLM context"""
        return (
            "ShopHub E-commerce Platform\n"
            "- Modern online shopping website\n"
            "- Products: Electronics, Clothing, Home & Garden\n"
            "- Features: Shopping cart, checkout, user accounts, order tracking\n"
            "- Tech: Node.js, Express, MongoDB, Redis\n"
        )


class ShopHubController:
    """Controller for ShopHub HTTPS honeypot"""

    def __init__(self):
        self.state = ShopHubState()
        self.sessions = {}

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        """Get or create session"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "request_history": [],
                "suspicious_count": 0,
                "user_agent": None,
                "ip": None,
                "cart_items": 0,
                "logged_in": False,
            }
        return self.sessions[session_id]

    def _classify_request(self, method: str, path: str, headers: dict) -> str:
        """Classify request type"""
        path_lower = path.lower()

        # Home/landing pages
        if path in ["/", "/index.html"]:
            return "home"

        # Product pages
        if "/product" in path_lower:
            return "product_page"

        # Shopping flow
        if path in ["/cart", "/checkout"]:
            return "shopping"

        # Auth pages
        if any(x in path_lower for x in ["/login", "/register", "/account"]):
            return "auth"

        # Admin
        if "/admin" in path_lower:
            return "admin"

        # API
        if path.startswith("/api/"):
            return "api"

        # Static resources
        if any(
            path_lower.endswith(x)
            for x in [".css", ".js", ".jpg", ".png", ".gif", ".ico", ".woff", ".ttf"]
        ):
            return "static"

        # Static pages
        if path in ["/about", "/contact", "/help", "/robots.txt", "/sitemap.xml"]:
            return "static_page"

        # Suspicious patterns
        if any(
            x in path_lower
            for x in ["/.git", "/.env", "/config", "/backup", "wp-", "phpmyadmin"]
        ):
            return "suspicious"

        return "other"

    def _is_suspicious(
        self, method: str, path: str, headers: dict, body: str = None
    ) -> bool:
        """Detect suspicious activity"""
        path_lower = path.lower()

        suspicious_patterns = [
            "../",
            "..\\",
            "%2e%2e",
            "/etc/passwd",
            "/proc/self",
            "wp-config",
            "phpmyadmin",
            "' or '1'='1",
            "union select",
            "<script>",
            "javascript:",
            "php://",
            "file://",
            "/.git",
            "/.env",
            "/backup",
            "sqlmap",
            "nikto",
            "nmap",
        ]

        if any(pattern in path_lower for pattern in suspicious_patterns):
            return True

        user_agent = headers.get("user-agent", "").lower()
        if any(
            tool in user_agent for tool in ["nikto", "sqlmap", "nmap", "metasploit"]
        ):
            return True

        return False

    def _determine_status_code(
        self, intent: str, is_suspicious: bool, path_exists: bool
    ) -> int:
        """Determine HTTP status code"""
        if is_suspicious:
            return 403 if "suspicious" in intent else 404

        if not path_exists:
            return 404

        if intent == "admin" and not path_exists:
            return 401

        if intent in ["home", "product_page", "shopping", "static_page", "api"]:
            return 200

        if intent == "auth":
            return 200

        return 200

    def _get_content_type(self, path: str, intent: str) -> str:
        """Determine content type"""
        path_lower = path.lower()

        if path_lower.endswith(".json") or intent == "api":
            return "application/json"
        elif path_lower.endswith(".css"):
            return "text/css"
        elif path_lower.endswith(".js"):
            return "application/javascript"
        elif path_lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        elif path_lower.endswith(".png"):
            return "image/png"
        elif path_lower.endswith(".gif"):
            return "image/gif"
        elif path_lower.endswith(".ico"):
            return "image/x-icon"
        elif path_lower.endswith(".xml"):
            return "application/xml"
        elif path_lower == "/robots.txt":
            return "text/plain"
        else:
            return "text/html; charset=utf-8"

    async def get_action_for_request(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Main method to handle requests"""
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        body = event.get("body")

        session = self._get_session(session_id)

        # Update session
        session["request_history"].append(
            {"method": method, "path": path, "ts": event.get("ts")}
        )
        if len(session["request_history"]) > 50:
            session["request_history"] = session["request_history"][-50:]

        session["user_agent"] = headers.get("user-agent")
        session["ip"] = event.get("remote_addr")

        # Classify request
        intent = self._classify_request(method, path, headers)
        is_suspicious = self._is_suspicious(method, path, headers, body)

        if is_suspicious:
            session["suspicious_count"] += 1

        # Determine response
        path_exists = self.state.page_exists(path)
        status_code = self._determine_status_code(intent, is_suspicious, path_exists)
        content_type = self._get_content_type(path, intent)

        # Build context
        page_info = self.state.get_page_info(path)
        server_context = self.state.get_state_summary()
        if page_info:
            server_context += f"\nPage: {path}\nPage info: {page_info}\n"

        # Delay for suspicious requests
        delay = 0.0
        if is_suspicious:
            delay = min(0.3 + session["suspicious_count"] * 0.1, 2.0)

        should_disconnect = session["suspicious_count"] > 20

        # Generate response
        try:
            response_body = await generate_shophub_response_async(
                method=method,
                path=path,
                headers=headers,
                body=body,
                intent=intent,
                status_code=status_code,
                server_context=server_context,
            )
        except Exception:
            response_body = (
                "<!DOCTYPE html><html><head><title>500 Error</title></head>"
                "<body><h1>500 Internal Server Error</h1></body></html>"
            )
            status_code = 500

        # Build headers
        response_headers = {
            "Server": "nginx/1.18.0",
            "Content-Type": content_type,
            "Content-Length": str(len(response_body.encode())),
            "X-Powered-By": "Express",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Connection": "close" if should_disconnect else "keep-alive",
        }

        action = {
            "status_code": status_code,
            "headers": response_headers,
            "body": response_body,
            "delay": delay,
        }

        if should_disconnect:
            action["disconnect"] = True

        return action
