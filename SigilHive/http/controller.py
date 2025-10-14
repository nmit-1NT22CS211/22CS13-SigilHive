from typing import Dict, Any, Optional
from llm_gen import generate_http_response_async


class WebServerState:
    """Maintains virtual web server state"""

    def __init__(self, server_type: str):
        self.server_type = server_type
        self.pages = {}
        self.files = {}

        # Initialize with common pages
        self.pages = {
            "/": {"title": "Home", "content": "Welcome to our website", "exists": True},
            "/index.html": {"title": "Home", "content": "Welcome", "exists": True},
            "/about": {"title": "About Us", "content": "About page", "exists": True},
            "/admin": {
                "title": "Admin Login",
                "content": "Admin panel",
                "exists": True,
            },
            "/login": {"title": "Login", "content": "User login", "exists": True},
            "/api/status": {"content": '{"status": "ok"}', "exists": True},
        }

        # Common files that exist
        self.files = {
            "/robots.txt": "User-agent: *\nDisallow: /admin/",
            "/favicon.ico": "[ICO file]",
            "/.git/config": "[Git config - should be protected]",
            "/wp-admin/": "[WordPress admin]",
            "/phpmyadmin/": "[phpMyAdmin]",
        }

    def page_exists(self, path: str) -> bool:
        """Check if a page exists"""
        return path in self.pages or path in self.files

    def add_page(self, path: str, title: str = None, content: str = None):
        """Add a new page"""
        self.pages[path] = {
            "title": title or "Page",
            "content": content or "Content",
            "exists": True,
        }

    def get_page_info(self, path: str) -> Optional[Dict]:
        """Get page information"""
        if path in self.pages:
            return self.pages[path]
        if path in self.files:
            return {"content": self.files[path], "exists": True}
        return None

    def get_state_summary(self) -> str:
        """Get a summary of current state for LLM context"""
        summary = f"Server type: {self.server_type}\n"
        summary += f"Available pages: {', '.join(list(self.pages.keys())[:10])}\n"
        summary += f"Total pages: {len(self.pages)}\n"
        return summary


class IntelligentHTTPController:
    """
    Intelligent controller that maintains web server state and uses LLM for realistic responses
    """

    def __init__(self, server_type: str = "nginx", persona: str = None):
        self.server_type = server_type
        self.persona = persona or f"{server_type}/1.18.0"
        self.sessions = {}
        self.server_state = WebServerState(server_type)

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        """Get or create session state"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "request_history": [],
                "suspicious_count": 0,
                "user_agent": None,
                "ip": None,
            }
        return self.sessions[session_id]

    def _classify_request(self, method: str, path: str, headers: dict) -> str:
        """Classify request intent"""
        path_lower = path.lower()

        # Check for common legitimate requests
        if path in ["/", "/index.html", "/about", "/contact"]:
            return "normal"

        # Check for admin/auth attempts
        if any(
            x in path_lower
            for x in ["/admin", "/login", "/auth", "/wp-admin", "/phpmyadmin"]
        ):
            return "admin_access"

        # Check for API requests
        if "/api/" in path_lower or path_lower.endswith(".json"):
            return "api"

        # Check for file access
        if any(path_lower.endswith(x) for x in [".php", ".asp", ".jsp", ".cgi"]):
            return "script"

        # Check for static resources
        if any(
            path_lower.endswith(x)
            for x in [".css", ".js", ".jpg", ".png", ".gif", ".ico"]
        ):
            return "static"

        # Check for config/sensitive files
        if any(
            x in path_lower for x in ["/.git", "/.env", "/config", "/backup", "/.ssh"]
        ):
            return "sensitive"

        return "other"

    def _is_suspicious(
        self, method: str, path: str, headers: dict, body: str = None
    ) -> bool:
        """Detect suspicious patterns"""
        path_lower = path.lower()

        suspicious_patterns = [
            # Path traversal
            "../",
            "..\\",
            "%2e%2e",
            # Common exploits
            "/etc/passwd",
            "/proc/self",
            "wp-config.php",
            # Shell commands
            ";cat ",
            "|ls ",
            "&whoami",
            "$(",
            "`",
            # SQL injection patterns
            "' or '1'='1",
            "union select",
            "' and '1'='1",
            # XSS patterns
            "<script>",
            "javascript:",
            "onerror=",
            # File inclusion
            "php://",
            "file://",
            "data://",
            # Scanning tools signatures
            "nikto",
            "nmap",
            "sqlmap",
            "burp",
        ]

        if any(pattern in path_lower for pattern in suspicious_patterns):
            return True

        # Check headers for scanning tools
        user_agent = headers.get("user-agent", "").lower()
        if any(
            tool in user_agent
            for tool in ["nikto", "nmap", "sqlmap", "metasploit", "burp"]
        ):
            return True

        # Check body for suspicious content
        if body:
            body_lower = body.lower()
            if any(pattern in body_lower for pattern in suspicious_patterns):
                return True

        return False

    def _determine_status_code(
        self, intent: str, is_suspicious: bool, path_exists: bool
    ) -> int:
        """Determine appropriate HTTP status code"""
        if is_suspicious:
            # Return 403 for obvious attacks, 404 for others to not reveal info
            if any(x in intent for x in ["sensitive", "script"]):
                return 403
            return 404

        if not path_exists and intent not in ["normal", "admin_access"]:
            return 404

        if intent == "admin_access":
            return 401  # Unauthorized

        if intent in ["normal", "api", "static"]:
            return 200

        return 200

    def _get_content_type(self, path: str, intent: str) -> str:
        """Determine content type based on path and intent"""
        path_lower = path.lower()

        if path_lower.endswith(".json") or intent == "api":
            return "application/json"
        elif path_lower.endswith(".css"):
            return "text/css"
        elif path_lower.endswith(".js"):
            return "application/javascript"
        elif any(path_lower.endswith(x) for x in [".jpg", ".jpeg"]):
            return "image/jpeg"
        elif path_lower.endswith(".png"):
            return "image/png"
        elif path_lower.endswith(".gif"):
            return "image/gif"
        elif path_lower.endswith(".ico"):
            return "image/x-icon"
        elif path_lower.endswith(".xml"):
            return "application/xml"
        else:
            return "text/html"

    def _build_context_for_llm(self, method: str, path: str, intent: str) -> str:
        """Build rich context for LLM including current server state"""
        context = self.server_state.get_state_summary()

        # Add specific context based on request
        page_info = self.server_state.get_page_info(path)
        if page_info:
            context += f"\nRequested page '{path}' exists\n"
            context += f"Page info: {page_info}\n"
        else:
            context += f"\nRequested page '{path}' does not exist\n"

        return context

    async def get_action_for_request(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main method: receives HTTP request event, returns action dict.
        """
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        body = event.get("body")

        session = self._get_session(session_id)

        # Update session history
        session["request_history"].append(
            {"method": method, "path": path, "timestamp": event.get("ts")}
        )
        if len(session["request_history"]) > 50:
            session["request_history"] = session["request_history"][-50:]

        # Store session info
        session["user_agent"] = headers.get("user-agent")
        session["ip"] = event.get("remote_addr")

        # Classify and check for suspicious activity
        intent = self._classify_request(method, path, headers)
        is_suspicious = self._is_suspicious(method, path, headers, body)

        if is_suspicious:
            session["suspicious_count"] += 1

        # Determine response characteristics
        path_exists = self.server_state.page_exists(path)
        status_code = self._determine_status_code(intent, is_suspicious, path_exists)
        content_type = self._get_content_type(path, intent)

        # Build context for LLM
        server_context = self._build_context_for_llm(method, path, intent)

        # Add delay for suspicious requests
        delay = 0.0
        if is_suspicious:
            delay = min(0.3 + session["suspicious_count"] * 0.1, 2.0)

        should_disconnect = session["suspicious_count"] > 20

        # Generate response using LLM
        try:
            response_body = await generate_http_response_async(
                method=method,
                path=path,
                headers=headers,
                body=body,
                intent=intent,
                server_context=server_context,
                persona=self.persona,
            )
        except Exception as e:
            response_body = f"<html><body><h1>500 Internal Server Error</h1><p>{str(e)}</p></body></html>"
            status_code = 500

        # Build response headers
        response_headers = {
            "Server": self.persona,
            "Content-Type": content_type,
            "Content-Length": str(len(response_body.encode())),
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
