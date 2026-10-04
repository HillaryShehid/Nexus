# Nexus v1.6.0 — Personal AI Assistant

Nexus is currently **personal-first**. Business/CRM/sales/client workflows are intentionally out of scope for this phase so the core assistant can become deeper and more reliable first.


### Fast local conversation mode

Simple conversational messages are routed through a lightweight one-call path using a smaller local model by default. This avoids running the full planning, verification, research, and self-evaluation pipeline for messages that do not require actions, while preserving Nexus identity, recalled memory, and conversation persistence. Requests that need tools, research, coding, or other actions still use the full verified executive pipeline.

## What Nexus is

Nexus is a personal AI system built around **one canonical intelligence layer** rather than a collection of disconnected assistants.

The underlying model provides intelligence; Nexus provides the surrounding system: identity, memory, planning, permissions, tools, verification, learning, and interfaces.

## Cognitive loop

Understand → Identify knowledge gaps → Research → Assess evidence → Update world state → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

## Current personal capabilities

- 🧠 One canonical Python Nexus brain.
- 🔎 Evidence-aware web research with source checks and uncertainty handling.
- 🧩 Planning, tool permissions, verification, failure diagnosis, bounded recovery, and self-evaluation.
- 💾 Persistent personal memory with a separate conversation history.
- 📝 Resumable local tasks with checkpoints and approval states.
- 🧮 Calculator, safe web retrieval, workspace filesystem access, memory storage, and an isolated code-test runner.
- 🧬 Bounded self-improvement proposals that remain owner-controlled before promotion.
- 🔐 Centralized owner identity and fail-closed authorization.
- 🎙️ Modular LiveKit voice architecture for realtime speech-to-speech conversations.
- 🗣️ Natural voice turn-taking with configurable VAD/STT/TTS providers.
- 🔗 Voice requests are bridged back into the existing NexusCore, keeping Nexus memory, planning, permissions, tools, verification, and learning authoritative.
- 🦙 Local-first model inference through Ollama is now the default, so normal Nexus reasoning does not require paid OpenAI API credits.
- ✉️ Owner-controlled email integration supports reading/searching mail and permission-gated sending.

## Realtime voice

Nexus uses a modular **LiveKit voice pipeline** for actual speech-to-speech conversation.

The default local-first architecture is:

```text
Your microphone
      |
      v
 Browser WebRTC
      |
      v
    LiveKit
      |
      +--> STT (Deepgram optional / local inference fallback)
      |
      v
 Local Ollama model
      |
      v
   NexusCore
      |
      |  memory / tools / planning / verification / learning
      v
 Authoritative Nexus response
      |
      v
 TTS (Kokoro local / ElevenLabs optional)
      |
      v
 Browser speaker
      |
      v
     You
```

LiveKit is the realtime transport/orchestration layer, while NexusCore remains the authoritative brain. Cloud providers can be enabled later, but local Ollama + local voice components are the preferred zero-cost development path.

## Local-first model

The default model provider is **Ollama**. Quick conversation defaults to the smaller `llama3.2:1b` model for low latency, while normal/deeper profiles continue to use `llama3.2` unless overridden.

Nexus can still use OpenAI when explicitly selected with:

```env
NEXUS_MODEL_PROVIDER=openai
OPENAI_API_KEY=...
```

For local inference:

```env
NEXUS_MODEL_PROVIDER=ollama
NEXUS_LOCAL_MODEL=llama3.2
NEXUS_QUICK_MODEL=llama3.2:1b
NEXUS_OLLAMA_URL=http://localhost:11434/v1
```

## Email

Nexus includes an owner-controlled IMAP/SMTP email adapter. Reading/searching mail can be used by the assistant, while outbound sending remains permission-gated.

## Unlimited chat

Nexus has **no artificial chat-count quota**. The conversation log is not truncated to a fixed number of chats.

There are still technical safeguards such as individual request size, model context size, storage capacity, execution time, external API limits, and safety/resource protection. Those are engineering limits, not a limit on how many conversations you can have.

Nexus keeps the full local conversation log while recalling only a recent context window when building a model prompt. This keeps reasoning practical without deleting older chats.

## Personal identity

The current identity model intentionally contains only one user:

- Hilal — OWNER

There are no business users, callers, workers, sales roles, CRM roles, client records, lead-finder workflows, payment workflows, or business-specific permissions in the current personal phase.

High-impact operations remain owner-controlled and permission checks fail closed.

## Architecture

Nexus has one canonical intelligence layer. Interfaces should call into that brain rather than create competing AI implementations.

```text
Client / API / Realtime Voice / future UI
              |
           NexusCore
              |
       NexusBrain (canonical)
        /      |       \
    memory   tasks    tools
      |        |        |
   storage  checkpoints permissions
                       |
                 owner identity
```

The Realtime voice layer is an interface, not a second Nexus brain.

## Memory and tasks

CognitiveMemory uses a replaceable MemoryStore adapter. Conversation exchanges are persisted automatically.

The task manager is bounded for reliability and storage safety. Those task-storage safeguards are separate from chat history and do not impose a chat-count limit.

## Research and self-improvement

- Retrieved pages are treated as untrusted evidence, never as instructions.
- Research reports source conflicts and uncertainty rather than pretending weak evidence is certain.
- Self-improvement experiments are bounded and synthetic where appropriate.
- No self-improvement candidate is promoted into the live foundation automatically.

## Run

```bash
python -m pip install -e ".[dev]"
python run.py
```

For the local-first web interface, start Ollama with the configured local model. LiveKit voice credentials are only needed when using the realtime voice path.

## Tests

```bash
pytest -q
```

## Security

- 🔐 Provider credentials remain server-side.
- 🛡️ LiveKit session credentials are minted by the local Nexus server.
- 🧠 Voice and email requests remain subject to NexusCore's existing authorization and safety controls.
- ⚠️ `code_tester` is an untrusted process runner, not a perfect OS sandbox. Production deployments should eventually add a dedicated sandbox/container/VM boundary.
