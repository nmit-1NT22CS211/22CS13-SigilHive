# shophub_controller.py
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from llm_gen import generate_shophub_response_async
from kafka_manager import HoneypotKafkaManager
from file_structure import PAGES, PRODUCTS


def log(message: str):
    """Helper to ensure immediate output"""
    print(message, flush=True)


class ShopHubState:
    """Maintains ShopHub e-commerce website state"""

    def __init__(self):
        self.pages = PAGES
        self.products = PRODUCTS
        self.api_endpoints = self._initialize_api_endpoints()

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
        if path.endswith("/") and path != "/":
            path = path[:-1]

        if path in self.pages:
            return True

        if path.startswith("/api/"):
            if path in self.api_endpoints:
                return True
            for endpoint in self.api_endpoints:
                if "{id}" in endpoint:
                    pattern = endpoint.replace("{id}", r"\d+")
                    import re

                    if re.match(pattern, path):
                        return True

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
        log("[Controller] Initializing ShopHub controller...")
        self.state = ShopHubState()
        self.sessions = {}
        self.kafka_manager = HoneypotKafkaManager()
        log("[Controller] ShopHub controller ready")

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

        if path in ["/", "/index.html"]:
            return "home"

        if "/product" in path_lower:
            return "product_page"

        if path in ["/cart", "/checkout"]:
            return "shopping"

        if any(x in path_lower for x in ["/login", "/register", "/account"]):
            return "auth"

        if "/admin" in path_lower:
            return "admin"

        if path.startswith("/api/"):
            return "api"

        if any(
            path_lower.endswith(x)
            for x in [".css", ".js", ".jpg", ".png", ".gif", ".ico", ".woff", ".ttf"]
        ):
            return "static"

        if path in ["/about", "/contact", "/help", "/robots.txt", "/sitemap.xml"]:
            return "static_page"

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

    async def _finalize_request(
        self,
        session_id: str,
        method: str,
        path: str,
        intent: str,
        status_code: int,
        headers: Dict[str, str],
        body: str,
        delay: float,
    ):
        """Finalization step: send Kafka events + return unified output."""
        try:
            payload = {
                "session_id": session_id,
                "method": method,
                "path": path,
                "intent": intent,
                "status_code": status_code,
                "headers": headers,
                "body": body[:1000] if body else "",  # Truncate body for Kafka
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            log(f"[Controller] Sending to Kafka: {method} {path} -> {status_code}")
            self.kafka_manager.send(topic="HTTPtoDB", value=payload)
            self.kafka_manager.send(topic="HTTPtoSSH", value=payload)
            self.kafka_manager.send_dashboard(
                topic="honeypot-logs", value=payload, service="http", event_type=intent
            )

        except Exception as e:
            log(f"[Controller] Kafka send error: {e}")

        return {
            "status_code": status_code,
            "headers": headers,
            "body": body,
            "delay": delay,
        }

    async def get_action_for_request(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Main request handler"""
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        body = event.get("body", None)

        # Classify request
        intent = self._classify_request(method, path, headers)
        path_exists = self.state.page_exists(path)

        # Determine status
        status_code = self._determine_status_code(
            intent=intent,
            is_suspicious=False,
            path_exists=path_exists,
        )

        # Infer content type
        content_type = self._get_content_type(path, intent)

        # Build server context
        page_info = self.state.get_page_info(path)
        server_context = self.state.get_state_summary()

        if page_info:
            server_context += f"\nPage: {path}\nPage info: {page_info}\n"

        delay = 0.05

        # Generate response body
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

        except Exception as e:
            log(f"[Controller] LLM generation error: {e}")
            status_code = 500
            response_body = (
                "<!DOCTYPE html><html><head><title>500 Error</title></head>"
                "<body><h1>500 Internal Server Error</h1></body></html>"
            )

        # Standard headers
        response_headers = {
            "Server": "nginx/1.18.0",
            "Content-Type": content_type,
            "Content-Length": str(len(response_body.encode())),
            "X-Powered-By": "Express",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Connection": "keep-alive",
        }

        return await self._finalize_request(
            session_id=session_id,
            method=method,
            path=path,
            intent=intent,
            status_code=status_code,
            headers=response_headers,
            body=response_body,
            delay=delay,
        )
