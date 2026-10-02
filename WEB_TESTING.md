# Test Nexus in a browser

This is the first browser interface for the **personal** Nexus brain. It intentionally contains no business/CRM features and does not add Cloudflare.

## Start

1. Install the project:
   `python -m pip install -e ".[dev]"`
2. Set `OPENAI_API_KEY` and `NEXUS_MODEL` in your local `.env`.
3. Run:
   `python web_server.py`
4. Open **http://127.0.0.1:8787**.

The browser talks to the real `NexusCore` instance through `/api/chat`; it is not a fake/demo response layer.

## Voice

The browser UI includes experimental microphone input and spoken-response controls using the browser's Web Speech APIs. This is a UI-level voice bridge, not yet the full always-ready Nexus voice system from the master vision.

The existing `src/personal_runtime.py` voice foundation remains responsible for the Nexus-side voice concepts (speaker/private/silent modes, wake-word state, and routing contracts). Actual microphone, speech-recognition, TTS hardware, wake-word detection, and AirPods routing are not falsely claimed as implemented.

## Security

The development server binds to `127.0.0.1` only. Do not expose it directly to the public internet. A real deployed service needs authentication, HTTPS, rate limits, and a production server boundary before remote access.
