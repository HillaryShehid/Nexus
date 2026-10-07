"""Local development API for the personal Nexus brain and Realtime voice bridge."""

import ipaddress
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from hmac import compare_digest
from urllib.parse import urlparse

from src.core import NexusCore

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8787"))
WEB_ROOT = Path(__file__).parent / "web"
MAX_BODY = 16_000
MAX_VOICE_REQUEST = 8_000
NEXUS_API_TOKEN = os.getenv("NEXUS_API_TOKEN", "")

_nexus = None
_nexus_lock = threading.Lock()


def _is_loopback_host(host):
    normalized = str(host).strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        # Hostnames are treated conservatively: a non-IP bind is remote-capable.
        return False


REMOTE_BIND = not _is_loopback_host(HOST)
MIN_API_TOKEN_LENGTH = 32

if REMOTE_BIND and len(NEXUS_API_TOKEN) < MIN_API_TOKEN_LENGTH:
    raise RuntimeError(
        "Unsafe Nexus server configuration: non-loopback HOST requires "
        f"NEXUS_API_TOKEN with at least {MIN_API_TOKEN_LENGTH} characters."
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Handler(BaseHTTPRequestHandler):

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not NEXUS_API_TOKEN:
            return not REMOTE_BIND
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + NEXUS_API_TOKEN
        return compare_digest(supplied, expected)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid content length")
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Request body too large")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be an object")
        return payload

    def _get_nexus(self):
        global _nexus
        if _nexus is None:
            with _nexus_lock:
                if _nexus is None:
                    logging.info("Initializing the persistent Personal Nexus brain.")
                    _nexus = NexusCore(actor_id="hilal")
        return _nexus

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            if not self._authorized():
                self._json(401, {"error": "Unauthorized"})
                return
            try:
                self._get_nexus()
                self._json(200, {"ok": True, "service": "nexus"})
            except Exception:
                logging.exception("Nexus health check failed.")
                self._json(503, {"ok": False, "service": "nexus"})
            return

        relative = "index.html" if path in {"/", ""} else path.removeprefix("/").replace("..", "")
        file_path = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in file_path.parents and file_path != WEB_ROOT.resolve():
            self._json(403, {"error": "Forbidden"})
            return
        if not file_path.is_file():
            self._json(404, {"error": "Not found"})
            return

        data = file_path.read_bytes()
        content_type = (
            "text/html; charset=utf-8"
            if file_path.suffix == ".html"
            else "text/css; charset=utf-8"
            if file_path.suffix == ".css"
            else "application/javascript; charset=utf-8"
        )
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path

        if path in {"/api/realtime/token", "/api/realtime/brain"}:
            if not self._authorized():
                self._json(401, {"error": "Unauthorized"})
                return

        if path == "/api/livekit/token":
            if not self._authorized():
                self._json(401, {"error": "Unauthorized"})
                return
            try:
                livekit_url = os.getenv("LIVEKIT_URL", "")
                api_key = os.getenv("LIVEKIT_API_KEY", "")
                api_secret = os.getenv("LIVEKIT_API_SECRET", "")
                if not livekit_url or not api_key or not api_secret:
                    self._json(
                        503,
                        {
                            "error": (
                                "LiveKit is not configured. Set LIVEKIT_URL, "
                                "LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
                            )
                        },
                    )
                    return

                from livekit import api

                identity = "nexus-user-" + os.urandom(8).hex()
                room = "nexus-personal"
                agent_name = os.getenv("NEXUS_LIVEKIT_AGENT_NAME", "nexus")
                token = (
                    api.AccessToken(api_key, api_secret)
                    .with_identity(identity)
                    .with_grants(
                        api.VideoGrants(
                            room_join=True,
                            room=room,
                            can_publish=True,
                            can_subscribe=True,
                            can_publish_data=True,
                        )
                    )
                    .with_room_config(
                        api.RoomConfiguration(
                            agents=[api.RoomAgentDispatch(agent_name=agent_name)]
                        )
                    )
                    .to_jwt()
                )
                self._json(
                    200,
                    {
                        "server_url": livekit_url,
                        "participant_token": token,
                        "room": room,
                    },
                )
            except Exception:
                logging.exception("LiveKit token creation failed.")
                self._json(502, {"error": "Nexus could not start the LiveKit voice session."})
            return

        if path == "/api/realtime/token":
            self._json(
                410,
                {
                    "error": (
                        "The OpenAI Realtime voice path has been replaced by "
                        "the modular LiveKit voice pipeline."
                    )
                },
            )
            return

        if path == "/api/realtime/brain":
            self._json(
                410,
                {
                    "error": (
                        "The OpenAI Realtime voice bridge has been replaced by "
                        "the LiveKit Nexus agent."
                    )
                },
            )
            return

        if path == "/api/chat/stream":
            if not self._authorized():
                self._json(401, {"error": "Unauthorized"})
                return
            try:
                payload = self._read_json()
                message = payload.get("message")
                if not isinstance(message, str) or not message.strip():
                    self._json(400, {"error": "message must be non-empty text"})
                    return
                if len(message) > 8000:
                    self._json(413, {"error": "Message exceeds Nexus input limit"})
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                for chunk in self._get_nexus().stream_quick_request(message):
                    event = json.dumps({"delta": chunk}, ensure_ascii=False)
                    self.wfile.write(f"data: {event}\\n\\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: {"done":true}\\n\\n")
                self.wfile.flush()
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except Exception:
                logging.exception("Nexus streaming request failed.")
                try:
                    event = json.dumps({"error": "Nexus stopped safely after an internal error."})
                    self.wfile.write(f"data: {event}\\n\\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            return

        if path != "/api/chat":
            self._json(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "Unauthorized"})
            return

        try:
            payload = self._read_json()
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                self._json(400, {"error": "message must be non-empty text"})
                return
            if len(message) > 8000:
                self._json(413, {"error": "Message exceeds Nexus input limit"})
                return
            response = self._get_nexus().handle_request(message)
            if isinstance(response, dict):
                response = response.get("response", response)
            self._json(200, {"response": response})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            logging.exception("Nexus web request failed.")
            self._json(500, {"error": "Nexus stopped safely after an internal error."})

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    print(f"🧠 Nexus development interface: http://{HOST}:{PORT}")
    print("Voice uses the modular LiveKit agent pipeline.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
