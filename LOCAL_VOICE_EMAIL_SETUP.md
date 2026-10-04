# Nexus local voice + email setup

Nexus now uses a modular voice architecture built around LiveKit Agents.

## Voice architecture

```
Browser microphone
      |
      v
LiveKit WebRTC
      |
      v
LiveKit Agent
      |
      +--> STT (Deepgram by default; provider is swappable)
      |
      +--> Ollama local LLM
      |
      +--> NexusCore / NexusBrain
      |
      +--> Kokoro local TTS
      |
      v
Browser speaker
```

The voice layer is an interface. NexusCore remains responsible for memory,
planning, permissions, tools, verification, and learning.

## Local model

Install Ollama and run the configured model:

```
ollama run llama3.2
```

The default local endpoint is:

```
http://localhost:11434/v1
```

You can change the model with `NEXUS_LOCAL_MODEL`. Larger models generally
need more RAM/VRAM. Qwen3 is another supported Ollama family.

## LiveKit

The application expects these environment variables:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `NEXUS_LIVEKIT_AGENT_NAME=nexus`

For a completely local setup, run the open-source LiveKit server on the same
PC and use its local WebSocket URL.

For a hosted development setup, LiveKit Cloud can be used instead. Its free
Build plan has hard monthly usage caps, so it should not be described as
unlimited.

Install the optional voice dependencies:

```
python -m pip install -e ".[voice]"
```

Run the web interface:

```
python web_server.py
```

Run the voice agent in a second terminal:

```
python voice_agent.py dev
```

## Speech providers

The provider layer is configurable:

- `NEXUS_VOICE_STT=deepgram`
- `NEXUS_VOICE_LLM=ollama`
- `NEXUS_VOICE_TTS=kokoro`

Deepgram and ElevenLabs can be swapped in when their API keys are available.
Kokoro can run locally through Kokoro-FastAPI, so TTS does not have to consume
cloud credits.

A local Whisper STT adapter is intentionally kept as a later provider so we
can make the entire voice path genuinely local rather than pretending a free
cloud tier is unlimited.

## Email

Nexus also has an owner-controlled email tool.

Set:

- `NEXUS_EMAIL_ADDRESS`
- `NEXUS_EMAIL_PASSWORD`
- `NEXUS_IMAP_HOST`
- `NEXUS_IMAP_PORT`
- `NEXUS_SMTP_HOST`
- `NEXUS_SMTP_PORT`

Gmail works with an app password when the account has the required security
settings enabled.

Reading/searching mail is non-destructive and can run automatically. Sending
mail is treated as an elevated action and requires Nexus owner approval.

Nexus never stores the email password in the repository. Keep credentials in
your local environment only.
