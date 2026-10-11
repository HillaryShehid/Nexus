# Nexus v1.7.0 — Event-Driven AI Operating System

Nexus is the canonical intelligence layer behind Nexus Core: one shared brain with specialized Business, Builder, and Researcher roles. The current implementation is being built toward the master vision incrementally; the event/autonomy foundation is now active while full business-domain adapters are developed.


### Fast conversation mode

Simple conversational messages use a lightweight one-call path. Requests requiring tools, research, coding, or other actions still use the full verified executive pipeline.

## What Nexus is

Nexus is a personal AI system built around **one canonical intelligence layer** rather than a collection of disconnected assistants.

The underlying model provides intelligence; Nexus provides the surrounding system: identity, memory, planning, permissions, tools, verification, learning, and interfaces.

## Event-driven autonomy

Nexus now has a durable event backbone so important state changes do not depend on a user typing a command. Events can wake Nexus immediately and become resumable tasks, while an optional background scheduler performs the broader **"what needs attention right now?"** reconciliation every 15 minutes.

Initial event flows include:

- 📞 Call outcome → interested → research/client opportunity task
- 📞 Call outcome → sold → research + Nexus Builder preparation task
- ✉️ Email received → actionable email-review task
- 💳 Payment change → payment-review task
- 🌐 Project approval requested → owner-controlled approval task
- 🔔 Unknown events remain visible as review tasks instead of being silently dropped

The event layer is deliberately separate from the model. A stronger model provider can therefore be added later without rebuilding Nexus's state, autonomy, task, permission, or interface architecture.

### Autonomy architecture

```text
World change
    ↓
🧾 Durable Nexus event
    ↓
🧠 Autonomy engine
    ↓
Task / workflow decision
    ↓
Resumable Nexus task
    ↓
Research → Build → Verify → Escalate / Act
```

`NexusCore.emit_event(...)` records a world change and immediately reconciles it. `NexusCore.autonomous_check()` runs the scheduled-style reconciliation on demand, and `NexusCore.start_autonomy()` enables the optional 15-minute background loop.

`Nexus` remains responsible for identity, memory, reasoning, tools, permissions, verification, learning, and interfaces; the underlying model remains replaceable.

## Cognitive loop

Understand → Identify knowledge gaps → Research → Assess evidence → Update world state → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

## Current personal capabilities

- 🧠 One canonical Python Nexus brain.
- 🔎 Evidence-aware web research with source checks and uncertainty handling.
- 🧩 Planning, tool permissions, verification, failure diagnosis, bounded recovery, and self-evaluation.
- 💾 Persistent personal memory with a separate conversation history.
- 📓 Structured private daily activity log records run outcomes, verified accomplishments, and error categories; relevant past entries are recalled before new work.
- 📝 Resumable local tasks with checkpoints and approval states.
- 🧮 Calculator, safe web retrieval, workspace filesystem access, memory storage, and an isolated code-test runner.
- 🧬 Bounded self-improvement proposals that remain owner-controlled before promotion.
- 🔐 Centralized owner identity and fail-closed authorization.
- 🎙️ Modular LiveKit voice architecture for realtime speech-to-speech conversations.
- 🗣️ Natural voice turn-taking with configurable VAD/STT/TTS providers.
- 🔗 Voice requests are bridged back into the existing NexusCore, keeping Nexus memory, planning, permissions, tools, verification, and learning authoritative.
- ☁️ Single model-gateway integration through OmniRoute; provider selection and fallback are delegated to OmniRoute.
- ✉️ Owner-controlled email integration supports reading/searching mail and permission-gated sending.

## Realtime voice

Nexus uses a modular **LiveKit voice pipeline** for actual speech-to-speech conversation.

The voice interface uses the same OmniRoute model gateway as text chat; speech-to-text and text-to-speech remain separate interface components. The architecture is:

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

## OmniRoute model gateway

Nexus uses OmniRoute as its **only model-provider integration**. Nexus sends requests to one OpenAI-compatible endpoint; OmniRoute handles connected providers, model routing, and fallback.

```env
NEXUS_MODEL_MODE=free
NEXUS_PROVIDER_ORDER=omniroute
NEXUS_OMNIROUTE_MODEL=auto
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_API_KEY=sk_omniroute
```

Start OmniRoute separately and connect provider accounts you are eligible to use in its dashboard. Its advertised ~1.62B monthly token figure is an aggregate estimate across third-party free tiers, not a token grant or guaranteed personal allowance. Provider limits, terms, model quality, and availability still apply. Nexus no longer keeps separate direct integrations for Gemini, Groq, OpenRouter, or other model providers; OmniRoute owns that routing layer.

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

Start the OmniRoute gateway before using Nexus chat. LiveKit voice credentials are only needed when using the realtime voice path.

## Tests

```bash
pytest -q
```

## Security

- 🔐 Provider credentials remain server-side.
- 🛡️ LiveKit session credentials are minted by the local Nexus server.
- 🧠 Voice and email requests remain subject to NexusCore's existing authorization and safety controls.
- ⚠️ `code_tester` is an untrusted process runner, not a perfect OS sandbox. Production deployments should eventually add a dedicated sandbox/container/VM boundary.
