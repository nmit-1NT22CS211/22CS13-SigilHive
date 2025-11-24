# https_honeypot.py
import asyncio
import os
import ssl
import uuid
import time
from datetime import datetime, timezone
from .controller import ShopHubController
from kafka_manager import HoneypotKafka

# Configuration
HTTPS_HOST = "0.0.0.0"
HTTPS_PORT = int(os.getenv("HTTPS_PORT", "8443"))

# Use ShopHub controller
controller = ShopHubController()

# Kafka manager for HTTP honeypot
kafka = HoneypotKafka(
    "http", config_path=os.getenv("KAFKA_CONFIG_PATH", "kafka_config.json")
)


class HTTPSProtocol(asyncio.Protocol):
    """Implements HTTPS protocol for ShopHub honeypot"""

    def __init__(self):
        self.transport = None
        self.session_id = str(uuid.uuid4())[:8]
        self.request_count = 0
        self.start_time = time.time()
        self._buffer = b""
        self.remote_addr = None

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        self.remote_addr = peername[0] if peername else "unknown"
        print(f"[https][{self.session_id}] connection from {peername}")

    def data_received(self, data):
        self._buffer += data

        # Try to parse HTTP request(s)
        while b"\r\n\r\n" in self._buffer:
            # Find end of headers
            header_end = self._buffer.index(b"\r\n\r\n")
            request_data = self._buffer[: header_end + 4]

            # Parse the request
            try:
                lines = request_data.decode("utf-8", errors="ignore").split("\r\n")
                if not lines:
                    self._buffer = self._buffer[header_end + 4 :]
                    continue

                # Parse request line
                request_line = lines[0]
                parts = request_line.split(" ")
                if len(parts) != 3:
                    self._buffer = self._buffer[header_end + 4 :]
                    continue

                method, path, version = parts

                # Parse headers
                headers = {}
                for line in lines[1:]:
                    if ": " in line:
                        key, value = line.split(": ", 1)
                        headers[key.lower()] = value

                # Check for body
                body = None
                content_length = int(headers.get("content-length", 0))

                if content_length > 0:
                    # Need to read body
                    body_start = header_end + 4
                    if len(self._buffer) < body_start + content_length:
                        # Wait for complete body
                        break
                    body = self._buffer[
                        body_start : body_start + content_length
                    ].decode("utf-8", errors="ignore")
                    self._buffer = self._buffer[body_start + content_length :]
                else:
                    self._buffer = self._buffer[header_end + 4 :]

                # Handle the request
                self.request_count += 1
                asyncio.create_task(
                    self.handle_request(method, path, version, headers, body)
                )

            except Exception as e:
                print(f"[https][{self.session_id}] parse error: {e}")
                self._buffer = self._buffer[header_end + 4 :]
                continue

    async def handle_request(
        self, method: str, path: str, version: str, headers: dict, body: str = None
    ):
        """Handle HTTPS request using ShopHub controller"""
        print(f"[https][{self.session_id}] {method} {path}")

        event = {
            "session_id": self.session_id,
            "type": "https_request",
            "method": method,
            "path": path,
            "version": version,
            "headers": headers,
            "body": body,
            "ts": datetime.now(timezone.utc).isoformat(),
            "request_count": self.request_count,
            "elapsed": time.time() - self.start_time,
            "remote_addr": self.remote_addr,
        }

        # Publish event to Kafka for other honeypots to consume
        try:
            kafka.send(
                "HTTPtoDB",
                {
                    "target": "database", # Added target
                    "event_type": "http_request",
                    "session_id": self.session_id,
                    "method": method,
                    "path": path,
                    "body_preview": (body[:400] if body else None),
                    "remote_addr": self.remote_addr, # Re-added remote_addr
                },
            )
            kafka.send(
                "HTTPtoSSH",
                {
                    "target": "ssh", # Added target
                    "event_type": "http_request",
                    "session_id": self.session_id,
                    "method": method,
                    "path": path,
                    "remote_addr": self.remote_addr,
                    "user_agent": headers.get("user-agent") # Added user_agent
                },
            )
        except Exception as e:
            print(f"[https][{self.session_id}] Kafka send error: {e}")

        try:
            action = await controller.get_action_for_request(self.session_id, event)
        except Exception as e:
            print(f"[https][{self.session_id}] controller error: {e}")
            action = {
                "status_code": 500,
                "headers": {"Content-Type": "text/html", "Server": "nginx/1.18.0"},
                "body": "<html><body><h1>500 Internal Server Error</h1></body></html>",
                "delay": 0.0,
            }

        # Apply delay if specified
        delay = action.get("delay", 0.0)
        if delay > 0:
            await asyncio.sleep(delay)

        # Send response
        status_code = action.get("status_code", 200)
        response_headers = action.get("headers", {})
        response_body = action.get("body", "")

        self.send_response(status_code, response_headers, response_body)

        # Disconnect if needed
        if action.get("disconnect"):
            print(
                f"[https][{self.session_id}] disconnecting due to suspicious activity"
            )
            self.transport.close()

    def send_response(self, status_code: int, headers: dict, body: str):
        """Send HTTPS response"""
        # Status line
        status_messages = {
            200: "OK",
            201: "Created",
            204: "No Content",
            301: "Moved Permanently",
            302: "Found",
            304: "Not Modified",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        status_message = status_messages.get(status_code, "Unknown")
        response = f"HTTP/1.1 {status_code} {status_message}\r\n"

        # Headers
        for key, value in headers.items():
            response += f"{key}: {value}\r\n"

        # Add standard headers if not present
        if "Date" not in headers:
            response += f"Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"

        # End of headers
        response += "\r\n"

        # Body
        response += body

        # Send
        try:
            self.transport.write(response.encode("utf-8"))
        except Exception as e:
            print(f"[https][{self.session_id}] send error: {e}")

    def connection_lost(self, exc):
        if exc:
            print(f"[https][{self.session_id}] connection lost: {exc}")
        else:
            print(f"[https][{self.session_id}] connection closed")


def generate_self_signed_cert(certfile="shophub_cert.pem", keyfile="shophub_key.pem"):
    """Generate self-signed certificate for ShopHub"""
    if os.path.exists(certfile) and os.path.exists(keyfile):
        return certfile, keyfile

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime as dt

        print("[https] Generating self-signed certificate for ShopHub...")

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Generate certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ShopHub Inc"),
                x509.NameAttribute(NameOID.COMMON_NAME, "shophub.com"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.now(timezone.utc))
            .not_valid_after(dt.datetime.now(timezone.utc) + dt.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("shophub.com"),
                        x509.DNSName("www.shophub.com"),
                        x509.DNSName("localhost"),
                    ]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Write private key
        with open(keyfile, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write certificate
        with open(certfile, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f"[https] Certificate generated: {certfile}, {keyfile}")
        return certfile, keyfile

    except ImportError:
        print("[https] ERROR: cryptography package not installed")
        print("[https] Install with: pip install cryptography")
        raise


async def main():
    loop = asyncio.get_running_loop()

    async def http_kafka_handler(msg):
        try:
            print(f"[http][kafka] received: {msg}")
            sid = msg.get("session_id")
            if sid and hasattr(controller, "sessions"):
                sess = controller.sessions.setdefault(sid, {})
                sess.setdefault("cross_messages", []).append(msg)

            # Example reaction: if DB reported suspicious IPs, add it to blocklist in controller
            if msg.get("event_type") == "suspicious_ip":
                ip = msg.get("ip")
                if ip:
                    # store into controller sessions or blocklist (implement as you prefer)
                    print(f"[http] add to blocklist: {ip}")
                    # Example: Add to a simple in-memory blocklist
                    if not hasattr(controller, "blocklist"):
                        controller.blocklist = set()
                    controller.blocklist.add(ip)
        except Exception as e:
            print(f"[http][kafka] handler error: {e}")

    # start kafka consumer loop
    try:
        loop.create_task(kafka.start_consumer_loop(http_kafka_handler))
    except Exception as e:
        print(f"[honeypot] Error starting Kafka consumer loop: {e}")

    # Generate or load certificate
    certfile, keyfile = generate_self_signed_cert()

    # Create SSL context
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile, keyfile)

    # Optional: Set minimum TLS version
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    print(f"[honeypot] Starting ShopHub HTTPS honeypot on {HTTPS_HOST}:{HTTPS_PORT}")
    print(f"[honeypot] Using certificate: {certfile}")
    print("[honeypot] Simulating: ShopHub E-commerce Platform")

    # Start HTTPS honeypot with SSL
    server = await loop.create_server(
        HTTPSProtocol, HTTPS_HOST, HTTPS_PORT, ssl=ssl_context
    )

    print(f"[honeypot] HTTPS honeypot listening on https://{HTTPS_HOST}:{HTTPS_PORT}")
    print(f"[honeypot] Access with: curl -k https://localhost:{HTTPS_PORT}")
    print(f"[honeypot] Or visit: https://localhost:{HTTPS_PORT}")

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        server.close()
        await server.wait_closed()
        print("[honeypot] server shut down gracefully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[honeypot] stopped by user")
    except Exception as e:
        print(f"[honeypot] runtime error: {e}")
