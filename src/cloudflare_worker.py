import json
import os
from workers import WorkerEntrypoint, Response

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

SYSTEM = """You are Nexus, a fast personal AI assistant.
Be useful, direct, and honest about what you actually did.
Do not claim to have used tools or completed actions unless they were actually completed.
Keep responses concise unless the user asks for depth."""

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "OPTIONS":
            return Response("", status=204, headers=self._cors())

        url = str(request.url)
        if not url.endswith("/health") and request.method != "POST":
            return Response.json({"ok": True, "service": "Nexus", "version": "0.1.3"}, headers=self._cors())

        if url.endswith("/health"):
            return Response.json({"ok": True, "service": "Nexus", "version": "0.1.3"}, headers=self._cors())

        try:
            body = await request.json()
            message = body.get("message", "")
            if not isinstance(message, str) or not message.strip():
                return self._json({"error": "message is required"}, 400)

            api_key = getattr(self.env, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
            model = getattr(self.env, "NEXUS_MODEL", None) or os.getenv("NEXUS_MODEL")
            if not api_key or not model:
                return self._json({"error": "Nexus is not configured with an AI model secret."}, 500)

            if OpenAI is None:
                return self._json({"error": "OpenAI package is unavailable in this Worker build."}, 500)

            client = OpenAI(api_key=api_key)
            result = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message[:10000]},
                ],
                temperature=0.1,
            )
            content = result.choices[0].message.content if result.choices else ""
            return self._json({"ok": True, "response": content or ""}, 200)
        except Exception:
            return self._json({"error": "Nexus could not safely process the request."}, 500)

    def _json(self, data, status):
        return Response.json(data, status=status, headers=self._cors())

    def _cors(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
