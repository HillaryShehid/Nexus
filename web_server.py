"""Local development API for the personal Nexus brain and Realtime voice bridge."""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from src.core import NexusCore
from src.realtime import RealtimeVoice

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8787"))
WEB_ROOT = Path(__file__).parent / "web"
MAX_BODY = 16_000
MAX_VOICE_REQUEST = 8_000
NEXUS_API_TOKEN = os.getenv("NEXUS_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Handler(BaseHTTPRequestHandler):
    nexus = None
    realtime = None

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
            return True
        return self.headers.get("Authorization") == "Bearer " + NEXUS_API_TOKEN

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
        if self.nexus is None:
            self.nexus = NexusCore(actor_id="hilal")
        return self.nexus

    def _get_realtime(self):
        if self.realtime is None:
            self.realtime = RealtimeVoice()
        return self.realtime

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

        if path == "/api/realtime/token":
            try:
                if not OPENAI_API_KEY:
                    self._json(503, {"error": "OPENAI_API_KEY is not configured on the Nexus server."})
                    return
                token = self._get_realtime().create_client_secret(
                    OPENAI_API_KEY,
                    actor_id="hilal",
                )
                # Only the short-lived client secret and effective session are
                # returned. The long-lived server API key never reaches JS.
                self._json(200, {
                    "value": token["value"],
                    "session": token.get("session"),
                })
            except Exception:
                logging.exception("Realtime client secret creation failed.")
                self._json(502, {"error": "Nexus could not start the Realtime voice session."})
            return

        if path == "/api/realtime/brain":
            try:
                payload = self._read_json()
                message = payload.get("request")
                if not isinstance(message, str) or not message.strip():
                    self._json(400, {"error": "request must be non-empty text"})
                    return
                if len(message) > MAX_VOICE_REQUEST:
                    self._json(413, {"error": "Voice request exceeds Nexus input limit"})
                    return

                result = self._get_nexus().handle_request(message)
                if isinstance(result, dict):
                    result = result.get("response", result)
                if not isinstance(result, str):
                    result = str(result)
                self._json(200, {"response": result})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except Exception:
                logging.exception("Realtime Nexus brain bridge failed.")
                self._json(500, {"error": "Nexus stopped safely after an internal voice error."})
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
    print("Realtime voice uses OpenAI Realtime speech-to-speech over WebRTC.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
