import json
from urllib.parse import urlsplit

from js import fetch
from workers import WorkerEntrypoint, Response
from src.worker_security import api_token_is_configured, cors_headers, is_authorized_bearer


MAX_MESSAGE_CHARS = 10000
MAX_REQUEST_BYTES = 50000

SYSTEM = """You are Nexus, a fast personal AI assistant.
Be useful, direct, and honest about what you actually did.
Do not claim to have used tools or completed actions unless they were actually completed.
Keep responses concise unless the user asks for depth."""


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        cors = self._cors(request)
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin")
            if origin and not cors:
                return Response("", status=403)
            return Response("", status=204, headers=cors)

        path = urlsplit(str(request.url)).path.rstrip("/") or "/"
        if request.method == "GET" and path == "/health":
            return Response.json(
                {"ok": True, "service": "Nexus", "version": "0.1.3"},
                headers=cors,
            )

        if request.method != "POST":
            return Response.json(
                {"ok": True, "service": "Nexus", "version": "0.1.3",
                 "usage": "POST / with {message: 'Hello Nexus'}"},
                headers=cors,
            )
        if path != "/":
            return self._json({"error": "Not found."}, 404, cors)

        expected_token = getattr(self.env, "NEXUS_API_TOKEN", None)
        if not api_token_is_configured(expected_token):
            return self._json(
                {"error": "Nexus API authentication is not configured."}, 503, cors
            )
        if not is_authorized_bearer(
            request.headers.get("Authorization", ""), expected_token
        ):
            return self._json({"error": "Unauthorized."}, 401, cors)

        try:
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_REQUEST_BYTES:
                        return self._json({"error": "Request body exceeds the size limit."}, 413, cors)
                    if int(content_length) < 0:
                        return self._json({"error": "Content-Length is invalid."}, 400, cors)
                except ValueError:
                    return self._json({"error": "Content-Length is invalid."}, 400, cors)
            try:
                raw_body = await request.text()
            except Exception:
                return self._json({"error": "Request body could not be read."}, 400, cors)
            if len(raw_body.encode("utf-8")) > MAX_REQUEST_BYTES:
                return self._json({"error": "Request body exceeds the size limit."}, 413, cors)
            try:
                body = json.loads(raw_body)
            except (TypeError, json.JSONDecodeError):
                return self._json({"error": "Request body must be valid JSON."}, 400, cors)
            if not isinstance(body, dict):
                return self._json({"error": "Request body must be a JSON object."}, 400, cors)
            message = body.get("message", "")
            if not isinstance(message, str) or not message.strip():
                return self._json({"error": "message is required"}, 400, cors)
            if len(message) > MAX_MESSAGE_CHARS:
                return self._json({"error": "message exceeds the size limit."}, 413, cors)

            api_key = getattr(self.env, "OPENAI_API_KEY", None)
            model = getattr(self.env, "NEXUS_MODEL", None)
            if not api_key or not model:
                return self._json(
                    {"error": "Nexus is missing its model configuration."}, 503, cors
                )

            payload = {
                "model": model,
                "input": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message},
                ],
            }

            response = await fetch(
                "https://api.openai.com/v1/responses",
                {
                    "method": "POST",
                    "headers": {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps(payload),
                },
            )

            raw = await response.text()
            if not response.ok:
                # Do not echo provider response bodies into the public API.
                return self._json({"error": "Nexus could not complete the AI request."}, 502, cors)

            data = json.loads(raw)
            answer = data.get("output_text", "")
            if not answer:
                for item in data.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            answer += content.get("text", "")

            if not isinstance(answer, str) or not answer.strip():
                return self._json({"error": "Nexus received an empty model response."}, 502, cors)
            return self._json({"ok": True, "response": answer}, 200, cors)
        except Exception:
            return self._json(
                {"error": "Nexus could not safely process the request."}, 500, cors
            )

    def _json(self, data, status, headers=None):
        return Response.json(data, status=status, headers=headers or {})

    def _cors(self, request):
        return cors_headers(
            request.headers.get("Origin"),
            getattr(self.env, "NEXUS_ALLOWED_ORIGINS", ""),
        )
