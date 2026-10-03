"""Local development API for the personal Nexus brain."""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from src.core import NexusCore
from src.speech import NexusSpeech

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8787"))
WEB_ROOT = Path(__file__).parent / "web"
MAX_BODY = 16_000
MAX_SPEECH_CHARS = 900
NEXUS_API_TOKEN = os.getenv("NEXUS_API_TOKEN", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Handler(BaseHTTPRequestHandler):
    nexus = None
    speech = None

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not NEXUS_API_TOKEN:
            return True
        return self.headers.get("Authorization") == "Bearer " + NEXUS_API_TOKEN

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            if not self._authorized():
                self._json(401, {"error": "Unauthorized"})
                return
            try:
                if self.nexus is None:
                    self.nexus = NexusCore(actor_id="hilal")
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
        if path == "/api/speech":
            self._handle_speech()
            return
        if path != "/api/chat":
            self._json(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid content length"})
            return
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"error": "Request body too large"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                self._json(400, {"error": "message must be non-empty text"})
                return
            if len(message) > 8000:
                self._json(413, {"error": "Message exceeds Nexus input limit"})
                return
            if self.nexus is None:
                self.nexus = NexusCore(actor_id="hilal")
            response = self.nexus.handle_request(message)
            self._json(200, {"response": response})
        except Exception:
            logging.exception("Nexus web request failed.")
            self._json(500, {"error": "Nexus stopped safely after an internal error."})

    def _handle_speech(self):
        if not self._authorized():
            self._json(401, {"error": "Unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid content length"})
            return
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"error": "Request body too large"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                self._json(400, {"error": "text must be non-empty text"})
                return
            if len(text) > MAX_SPEECH_CHARS:
                self._json(413, {"error": "Speech chunk exceeds Nexus speech limit"})
                return
            if self.speech is None:
                self.speech = NexusSpeech()
            audio = self.speech.synthesize(text)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(audio)
        except Exception:
            logging.exception("Nexus speech request failed.")
            self._json(500, {"error": "Nexus could not generate speech safely."})

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    print(f"🧠 Nexus development interface: http://{HOST}:{PORT}")
    print("Voice input uses browser speech recognition when supported; voice output uses OpenAI TTS.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
