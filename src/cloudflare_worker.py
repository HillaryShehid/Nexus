import json
from js import fetch
from workers import WorkerEntrypoint, Response

SYSTEM = """You are Nexus, a fast personal AI assistant.
Be useful, direct, and honest about what you actually did.
Do not claim to have used tools or completed actions unless they were actually completed.
Keep responses concise unless the user asks for depth."""


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "OPTIONS":
            return Response("", status=204, headers=self._cors())

        url = str(request.url)
        if url.endswith("/health"):
            return Response.json(
                {"ok": True, "service": "Nexus", "version": "0.1.3"},
                headers=self._cors(),
            )

        if request.method != "POST":
            return Response.json(
                {"ok": True, "service": "Nexus", "version": "0.1.3",
                 "usage": "POST / with {message: 'Hello Nexus'}"},
                headers=self._cors(),
            )

        try:
            body = await request.json()
            message = body.get("message", "")
            if not isinstance(message, str) or not message.strip():
                return self._json({"error": "message is required"}, 400)

            api_key = self.env.OPENAI_API_KEY
            model = getattr(self.env, "NEXUS_MODEL", None)
            if not api_key or not model:
                return self._json({"error": "Nexus is missing OPENAI_API_KEY or NEXUS_MODEL."}, 500)

            payload = {
                "model": model,
                "input": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message[:10000]},
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
                return self._json(
                    {"error": "OpenAI request failed.", "details": raw[:1000]},
                    response.status,
                )

            data = json.loads(raw)
            answer = data.get("output_text", "")
            if not answer:
                for item in data.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            answer += content.get("text", "")

            return self._json({"ok": True, "response": answer}, 200)
        except Exception:
            return self._json(
                {"error": "Nexus could not safely process the request."}, 500
            )

    def _json(self, data, status):
        return Response.json(data, status=status, headers=self._cors())

    def _cors(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
