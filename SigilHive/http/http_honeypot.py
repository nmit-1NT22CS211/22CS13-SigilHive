# http_honeypot.py
import asyncio
import os
import uuid
import time
from datetime import datetime, timezone
from controller import IntelligentHTTPController

# Configuration
HTTP_HOST = "0.0.0.0"
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
HTTPS_PORT = int(os.getenv("HTTPS_PORT", "8443"))

# Use intelligent controller
http_controller = IntelligentHTTPController(server_type="nginx", persona="nginx/1.18.0")


class HTTPProtocol(asyncio.Protocol):
    """Implements HTTP/1.1 protocol for honeypot"""

    def __init__(self, is_https: bool = False):
        self.transport = None
        self.session_id = str(uuid.uuid4())
        self.request_count = 0
        self.start_time = time.time()
        self.is_https = is_https
        self._buffer = b""
        self.remote_addr = None

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        self.remote_addr = peername[0] if peername else "unknown"
        protocol = "https" if self.is_https else "http"
        print(f"[{protocol}][{self.session_id}] connection from {peername}")

    def data_received(self, data):
        self._buffer += data
        
        # Try to parse HTTP request(s)
        while b"\r\n\r\n" in self._buffer:
            # Find end of headers
            header_end = self._buffer.index(b"\r\n\r\n")
            request_data = self._buffer[:header_end + 4]
            
            # Parse the request
            try:
                lines = request_data.decode("utf-8", errors="ignore").split("\r\n")
                if not lines:
                    self._buffer = self._buffer[header_end + 4:]
                    continue
                
                # Parse request line
                request_line = lines[0]
                parts = request_line.split(" ")
                if len(parts) != 3:
                    self._buffer = self._buffer[header_end + 4:]
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
                    body = self._buffer[body_start:body_start + content_length].decode("utf-8", errors="ignore")
                    self._buffer = self._buffer[body_start + content_length:]
                else:
                    self._buffer = self._buffer[header_end + 4:]
                
                # Handle the request
                self.request_count += 1
                asyncio.create_task(self.handle_request(method, path, version, headers, body))
                
            except Exception as e:
                print(f"[http][{self.session_id}] parse error: {e}")
                self._buffer = self._buffer[header_end + 4:]
                continue

    async def handle_request(self, method: str, path: str, version: str, headers: dict, body: str = None):
        """Handle HTTP request using intelligent controller"""
        protocol = "https" if self.is_https else "http"
        print(f"[{protocol}][{self.session_id}] {method} {path}")
        
        event = {
            "session_id": self.session_id,
            "type": "http_request",
            "method": method,
            "path": path,
            "version": version,
            "headers": headers,
            "body": body,
            "ts": datetime.now(timezone.utc).isoformat(),
            "request_count": self.request_count,
            "elapsed": time.time() - self.start_time,
            "remote_addr": self.remote_addr,
            "is_https": self.is_https,
        }

        try:
            action = await http_controller.get_action_for_request(self.session_id, event)
        except Exception as e:
            print(f"[{protocol}][{self.session_id}] controller error: {e}")
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
            print(f"[{protocol}][{self.session_id}] disconnecting due to suspicious activity")
            self.transport.close()

    def send_response(self, status_code: int, headers: dict, body: str):
        """Send HTTP response"""
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
            print(f"[http][{self.session_id}] send error: {e}")

    def connection_lost(self, exc):
        protocol = "https" if self.is_https else "http"
        if exc:
            print(f"[{protocol}][{self.session_id}] connection lost: {exc}")
        else:
            print(f"[{protocol}][{self.session_id}] connection closed")


class HTTPSProtocol(HTTPProtocol):
    """HTTPS variant - same as HTTP but marked as secure"""
    
    def __init__(self):
        super().__init__(is_https=True)


async def main():
    loop = asyncio.get_running_loop()

    # Start HTTP honeypot
    http_server = await loop.create_server(
        lambda: HTTPProtocol(is_https=False), HTTP_HOST, HTTP_PORT
    )
    print(f"[honeypot] HTTP honeypot listening on {HTTP_HOST}:{HTTP_PORT}")

    # Start HTTPS honeypot (without actual TLS - just marked as HTTPS for logging)
    # In production, you would add SSL context here
    https_server = await loop.create_server(
        lambda: HTTPSProtocol(), HTTP_HOST, HTTPS_PORT
    )
    print(f"[honeypot] HTTPS honeypot listening on {HTTP_HOST}:{HTTPS_PORT}")
    print("[honeypot] Note: HTTPS is not using actual TLS encryption in this demo")

    try:
        await asyncio.gather(
            http_server.serve_forever(),
            https_server.serve_forever()
        )
    except asyncio.CancelledError:
        pass
    finally:
        http_server.close()
        https_server.close()
        await http_server.wait_closed()
        await https_server.wait_closed()
        print("[honeypot] servers shut down gracefully")


if __name__ == "__main__":
    try:
        print("[honeypot] starting HTTP honeypot...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[honeypot] stopped by user")
    except Exception as e:
        print(f"[honeypot] runtime error: {e}")