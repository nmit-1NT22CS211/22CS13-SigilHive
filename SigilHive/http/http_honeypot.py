import asyncio
import os
import sys
import ssl
import uuid
import time
from datetime import datetime, timezone
from controller import ShopHubController
from kafka_manager import HoneypotKafkaManager

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Configuration
HTTPS_HOST = "0.0.0.0"
HTTPS_PORT = int(os.getenv("HTTPS_PORT", "8443"))

# Use ShopHub controller
controller = ShopHubController()


def log(message: str, flush: bool = True):
    """Helper function to ensure logs are printed immediately"""
    print(message, flush=flush)


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
        log(f"[https][{self.session_id}] connection from {peername}")

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
                log(f"[https][{self.session_id}] parse error: {e}")
                self._buffer = self._buffer[header_end + 4 :]
                continue

    async def handle_request(
        self, method: str, path: str, version: str, headers: dict, body: str = None
    ):
        """Handle HTTPS request using ShopHub controller"""
        log(f"[https][{self.session_id}] {method} {path}")

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

        try:
            action = await controller.get_action_for_request(self.session_id, event)
        except Exception as e:
            log(f"[https][{self.session_id}] controller error: {e}")
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
            log(f"[https][{self.session_id}] disconnecting due to suspicious activity")
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
            log(f"[https][{self.session_id}] send error: {e}")

    def connection_lost(self, exc):
        if exc:
            log(f"[https][{self.session_id}] connection lost: {exc}")
        else:
            log(f"[https][{self.session_id}] connection closed")


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

        log("[https] Generating self-signed certificate for ShopHub...")

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

        log(f"[https] Certificate generated: {certfile}, {keyfile}")
        return certfile, keyfile

    except ImportError:
        log("[https] ERROR: cryptography package not installed")
        log("[https] Install with: pip install cryptography")
        raise


async def main():
    log("=" * 60)
    log("✅ ShopHub HTTPS Honeypot Starting...")
    log("=" * 60)

    loop = asyncio.get_running_loop()

    # Generate or load certificate
    certfile, keyfile = generate_self_signed_cert()

    # Create SSL context
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile, keyfile)

    # Optional: Set minimum TLS version
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    log(f"[honeypot] Starting ShopHub HTTPS honeypot on {HTTPS_HOST}:{HTTPS_PORT}")
    log(f"[honeypot] Using certificate: {certfile}")
    log("[honeypot] Simulating: ShopHub E-commerce Platform")

    # Start HTTPS honeypot with SSL
    server = await loop.create_server(
        HTTPSProtocol, HTTPS_HOST, HTTPS_PORT, ssl=ssl_context
    )

    log("=" * 60)
    log(f"✅ HTTPS honeypot listening on https://{HTTPS_HOST}:{HTTPS_PORT}")
    log(f"   Access with: curl -k https://localhost:{HTTPS_PORT}")
    log(f"   Or visit: https://localhost:{HTTPS_PORT}")
    log("=" * 60)

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        server.close()
        await server.wait_closed()
        log("[honeypot] Server shut down gracefully")


async def consumer():
    log("[kafka] Starting Kafka consumer...")
    kafka_manager = HoneypotKafkaManager()
    topics = ["DBtoHTTP", "SSHtoHTTP"]
    kafka_manager.subscribe(topics)
    log(f"[kafka] Subscribed to topics: {topics}")
    await kafka_manager.consume()


async def start():
    log("")
    log("╔════════════════════════════════════════════════════════╗")
    log("║     ShopHub Honeypot Boot Sequence                    ║")
    log("╚════════════════════════════════════════════════════════╝")
    log("")
    log("🔧 Initializing HTTPS service...")
    log("🔧 Initializing Kafka consumer...")
    log("")

    # Small delay to ensure logs are visible
    await asyncio.sleep(0.1)

    await asyncio.gather(
        main(),
        consumer(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        log("\n[honeypot] Stopped by user")
    except Exception as e:
        log(f"[honeypot] Error: {e}")
        import traceback

        traceback.print_exc()
