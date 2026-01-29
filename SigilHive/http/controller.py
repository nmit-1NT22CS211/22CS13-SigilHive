import os
import random
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from llm_gen import generate_shophub_response_async
from kafka_manager import HoneypotKafkaManager
from file_structure import PAGES, PRODUCTS
from rl_core.q_learning_agent import shared_rl_agent
from rl_core.state_extractor import extract_state
from rl_core.reward_calculator import calculate_reward
from rl_core.logging.structured_logger import log_interaction


def log(message: str):
    """Helper to ensure immediate output"""
    print(message, flush=True)


class ShopHubState:
    """Maintains ShopHub e-commerce website state"""

    def __init__(self):
        self.pages = PAGES
        self.products = PRODUCTS
        self.api_endpoints = self._initialize_api_endpoints()

        self.rl_agent = shared_rl_agent
        self.rl_enabled = os.getenv("RL_ENABLED", "true").lower() == "true"
        log(f"[Controller] ShopHub controller ready (RL enabled: {self.rl_enabled})")

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
        self.rl_agent = shared_rl_agent
        self.rl_enabled = os.getenv("RL_ENABLED", "true").lower() == "true"
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

    async def _original_request_handler(
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

    async def get_action_for_request(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """RL-enhanced request handler - wraps original logic"""
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        body = event.get("body", None)

        # 1. Log interaction for RL
        log_interaction(
            session_id=session_id,
            protocol="http",
            input_data=f"{method} {path}",
            metadata={
                "intent": self._classify_request(method, path, headers),
                "suspicious": self._is_suspicious(method, path, headers, body),
                "method": method,
                "user_agent": headers.get("user-agent", ""),
            },
        )

        # 2. Extract current state
        state = extract_state(session_id, protocol="http")

        # 3. Select and execute action
        rl_action = None
        if self.rl_enabled and method.upper() == "GET":
            # For GET requests, always use realistic response (no RL)
            response = await self._original_request_handler(session_id, event)
        elif self.rl_enabled:
            rl_action = self.rl_agent.select_action(state)
            response = await self._execute_rl_action(rl_action, session_id, event)
        else:
            response = await self._original_request_handler(session_id, event)

        # 4. Update Q-table (only if RL action was taken)
        if self.rl_enabled and rl_action is not None:
            next_state = extract_state(session_id, protocol="http")
            reward = calculate_reward(state, next_state, protocol="http")
            self.rl_agent.update(state, rl_action, reward, next_state)

        return response

    async def _execute_rl_action(
        self, action: str, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute RL-selected action"""
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        body = event.get("body", None)
        intent = self._classify_request(method, path, headers)

        if action == "REALISTIC_RESPONSE":
            # Use existing logic
            return await self._original_request_handler(session_id, event)

        elif action == "DECEPTIVE_RESOURCE":
            # Return fake sensitive resources with honeytokens
            path_lower = path.lower()

            # Fake admin panel
            if "/admin" in path_lower:
                fake_admin_html = """<!DOCTYPE html>
    <html>
    <head>
        <title>ShopHub Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 8px; max-width: 800px; margin: 0 auto; }
            h1 { color: #2c3e50; }
            .creds { background: #ecf0f1; padding: 15px; margin: 10px 0; border-left: 4px solid #3498db; }
            .key { font-family: monospace; color: #e74c3c; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 ShopHub Admin Dashboard</h1>
            <h2>System Credentials</h2>
            
            <div class="creds">
                <h3>Database Access</h3>
                <p>Host: <span class="key">prod-mysql.shophub.internal</span></p>
                <p>User: <span class="key">admin_HONEYTOKEN_001</span></p>
                <p>Pass: <span class="key">Adm1nP@ss_HONEYTOKEN_DB_001</span></p>
            </div>
            
            <div class="creds">
                <h3>API Keys</h3>
                <p>Stripe Secret: <span class="key">sk_live_HONEYTOKEN_STRIPE_SECRET_001</span></p>
                <p>AWS Access Key: <span class="key">AKIA_HONEYTOKEN_AWS_KEY_001</span></p>
                <p>AWS Secret: <span class="key">wJalrXUtn_HONEYTOKEN_AWS_SECRET</span></p>
            </div>
            
            <div class="creds">
                <h3>SSH Access</h3>
                <p>Host: <span class="key">prod-server.shophub.com</span></p>
                <p>User: <span class="key">deploy</span></p>
                <p>Key: <span class="key">/admin/.ssh/deploy_key_HONEYTOKEN</span></p>
            </div>
        </div>
    </body>
    </html>"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {
                        "Content-Type": "text/html",
                        "Server": "nginx/1.18.0",
                        "X-Admin": "true",
                    },
                    fake_admin_html,
                    0.1,
                )

            # Fake .env file
            if ".env" in path_lower:
                fake_env = """# ShopHub Production Environment
    NODE_ENV=production
    PORT=3000

    # Database
    DB_HOST=prod-mysql.internal
    DB_USER=shophub_prod_HONEYTOKEN_001
    DB_PASS=Pr0dP@ssw0rd_HONEYTOKEN_ENV_001
    DB_NAME=shophub_production

    # Redis
    REDIS_HOST=prod-redis.internal
    REDIS_PASS=R3d1sP@ss_HONEYTOKEN_002

    # AWS Credentials
    AWS_ACCESS_KEY_ID=AKIA_HONEYTOKEN_AWS_KEY_002
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI_HONEYTOKEN_AWS_003

    # Stripe
    STRIPE_SECRET_KEY=sk_live_HONEYTOKEN_STRIPE_004
    STRIPE_WEBHOOK_SECRET=whsec_HONEYTOKEN_STRIPE_WEBHOOK

    # JWT
    JWT_SECRET=jwt_super_secret_key_HONEYTOKEN_005
    SESSION_SECRET=session_secret_HONEYTOKEN_006

    # Email
    SENDGRID_API_KEY=SG.HONEYTOKEN_SENDGRID_007"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/plain", "Server": "nginx/1.18.0"},
                    fake_env,
                    0.1,
                )

            # Fake .git/config
            if "/.git" in path_lower and "config" in path_lower:
                fake_git_config = """[core]
        repositoryformatversion = 0
        filemode = true
        bare = false
        logallrefupdates = true
    [remote "origin"]
        url = https://deploy_HONEYTOKEN:ghp_HONEYTOKEN_GITHUB_PAT_001@github.com/shophub/production.git
        fetch = +refs/heads/*:refs/remotes/origin/*
    [branch "main"]
        remote = origin
        merge = refs/heads/main
    [user]
        name = ShopHub Deploy
        email = deploy@shophub.com"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/plain", "Server": "nginx/1.18.0"},
                    fake_git_config,
                    0.1,
                )

            # Fake API keys endpoint
            if "/api/keys" in path_lower or "/api/config" in path_lower:
                fake_api_keys = {
                    "stripe": {
                        "public_key": "pk_live_HONEYTOKEN_STRIPE_PUBLIC",
                        "secret_key": "sk_live_HONEYTOKEN_STRIPE_SECRET_008",
                    },
                    "aws": {
                        "access_key_id": "AKIA_HONEYTOKEN_AWS_009",
                        "secret_access_key": "wJalrXUtnFEMI_HONEYTOKEN_010",
                    },
                    "sendgrid": {"api_key": "SG.HONEYTOKEN_SENDGRID_011"},
                    "jwt_secret": "jwt_secret_HONEYTOKEN_012",
                }
                import json

                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "application/json", "Server": "nginx/1.18.0"},
                    json.dumps(fake_api_keys, indent=2),
                    0.1,
                )

            # Fake backup files
            if "/backup" in path_lower or ".sql" in path_lower or ".dump" in path_lower:
                fake_backup = """-- ShopHub Database Backup
    -- Generated: 2025-01-15 10:30:00
    -- 
    -- Admin Credentials:
    -- Username: admin_HONEYTOKEN, Password: B@ckup_P@ss_HONEYTOKEN_013
    -- 
    USE shophub_production;

    INSERT INTO admin_users (id, username, password_hash, email, role) VALUES
    (1, 'admin', '$2b$10$HONEYTOKEN_HASH_ADMIN_001', 'admin@shophub.com', 'superadmin'),
    (2, 'dbadmin', '$2b$10$HONEYTOKEN_HASH_DBADMIN_002', 'dbadmin@shophub.com', 'admin');

    -- API Keys Table
    INSERT INTO api_keys (service, key_value) VALUES
    ('stripe', 'sk_live_HONEYTOKEN_BACKUP_014'),
    ('aws', 'AKIA_HONEYTOKEN_BACKUP_015');"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {
                        "Content-Type": "text/plain",
                        "Server": "nginx/1.18.0",
                        "Content-Disposition": "attachment; filename=backup.sql",
                    },
                    fake_backup,
                    0.1,
                )

            # Fallback to realistic if no match
            return await self._original_request_handler(session_id, event)

        elif action == "RESPONSE_DELAY":
            # Add delay then return realistic response
            response = await self._original_request_handler(session_id, event)
            response["delay"] = response.get("delay", 0.0) + random.uniform(0.5, 2.0)
            return response

        elif action == "MISLEADING_SUCCESS":
            # Return 200 OK for unauthorized/suspicious requests
            path_lower = path.lower()

            # Admin access without auth
            if "/admin" in path_lower:
                fake_success = """<!DOCTYPE html>
    <html><head><title>Admin Panel</title></head>
    <body><h1>Admin Panel</h1><p>Access granted. Loading dashboard...</p></body>
    </html>"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/html", "Server": "nginx/1.18.0"},
                    fake_success,
                    0.05,
                )

            # API requests succeed
            if "/api/" in path_lower:
                fake_api_success = {
                    "success": True,
                    "message": "Operation completed successfully",
                }
                import json

                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "application/json", "Server": "nginx/1.18.0"},
                    json.dumps(fake_api_success),
                    0.05,
                )

            # Generic success
            response = await self._original_request_handler(session_id, event)
            response["status_code"] = 200
            return response

        elif action == "FAKE_VULNERABILITY":
            # Expose fake vulnerabilities
            path_lower = path.lower()

            # Fake directory listing
            if any(
                x in path_lower for x in ["/config", "/backup", "/data", "/uploads"]
            ):
                fake_listing = """<!DOCTYPE html>
    <html>
    <head><title>Index of {path}</title></head>
    <body>
    <h1>Index of {path}</h1>
    <ul>
    <li><a href="database_backup.sql">database_backup.sql</a> - 2.4 MB</li>
    <li><a href="credentials.txt">credentials.txt</a> - 1.2 KB</li>
    <li><a href="api_keys.json">api_keys.json</a> - 892 bytes</li>
    <li><a href=".env">.env</a> - 1.5 KB</li>
    <li><a href="ssh_keys/">ssh_keys/</a></li>
    </ul>
    </body>
    </html>""".format(path=path)
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/html", "Server": "nginx/1.18.0"},
                    fake_listing,
                    0.1,
                )

            # Exposed .git directory
            if "/.git" in path_lower:
                fake_git_head = "ref: refs/heads/main"
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/plain", "Server": "nginx/1.18.0"},
                    fake_git_head,
                    0.1,
                )

            # SQL injection "success"
            if any(x in path_lower for x in ["' or", "union select", "1=1"]):
                fake_sql_result = """<!DOCTYPE html>
    <html><body>
    <h2>Search Results</h2>
    <p>Found 1 administrator account:</p>
    <pre>
    Username: admin
    Email: admin@shophub.com
    Role: superadmin
    </pre>
    </body></html>"""
                return await self._finalize_request(
                    session_id,
                    method,
                    path,
                    intent,
                    200,
                    {"Content-Type": "text/html", "Server": "nginx/1.18.0"},
                    fake_sql_result,
                    0.1,
                )

            return await self._original_request_handler(session_id, event)

        elif action == "TERMINATE_SESSION":
            # Force disconnect
            return {
                "status_code": 403,
                "headers": {
                    "Content-Type": "text/html",
                    "Server": "nginx/1.18.0",
                    "Connection": "close",
                },
                "body": "<!DOCTYPE html><html><body><h1>403 Forbidden</h1><p>Access denied.</p></body></html>",
                "delay": 0.0,
                "disconnect": True,
            }

        # Fallback to realistic response
        return await self._original_request_handler(session_id, event)
