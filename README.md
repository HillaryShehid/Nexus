# Nexus v1.6.0 — Personal AI Assistant

Nexus is currently **personal-first**. Business/CRM/sales/client workflows are intentionally out of scope for this phase so the core assistant can become deeper and more reliable first.

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
- 🎙️ **OpenAI Realtime voice conversation** with real-time speech-to-speech over WebRTC.
- 🗣️ Natural voice turn-taking with semantic voice activity detection and interruption support.
- 🔗 Realtime voice requests are bridged back into the existing NexusCore, keeping Nexus memory, planning, permissions, tools, verification, and learning authoritative.
- 🔒 The long-lived OpenAI API key stays server-side; the browser receives only a short-lived Realtime client secret.

## Realtime voice

Nexus uses OpenAI's Realtime API for actual **speech-to-speech conversation**.

The voice architecture is:

```text
Your microphone
      |
      v
 Browser WebRTC
      |
      v
 OpenAI Realtime
      |
      |  nexus_brain function call
      v
   NexusCore
      |
      v
 NexusBrain
      |
      |  memory / tools / planning / verification / learning
      v
 Authoritative Nexus response
      |
      v
 OpenAI Realtime
      |
      v
 Browser speaker
      |
      v
     You
```

This is deliberately different from a traditional:

```text
Speech-to-text → text model → text-to-speech
```

pipeline. Realtime handles the live audio conversation, while substantive requests are routed through the existing Nexus brain.

### Voice behavior

- 🎙️ Browser microphone input is captured through WebRTC.
- 🔊 Nexus audio is returned through the WebRTC audio track.
- ⚡ Voice activity detection handles natural turn-taking.
- 🛑 Nexus can be interrupted while speaking.
- 🧠 Substantive requests are sent to the existing NexusCore instead of creating a separate voice-only brain.
- 🔐 The server mints the short-lived Realtime client secret; the permanent API key is never exposed to browser JavaScript.
- ⚙️ The Realtime model and voice are configurable through environment variables.

Default configuration:

```env
NEXUS_REALTIME_MODEL=gpt-realtime-2.1
NEXUS_REALTIME_VOICE=echo
NEXUS_REALTIME_TEMPERATURE=0.8
NEXUS_REALTIME_SPEED=0.98
```

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

For the Realtime voice interface, configure `OPENAI_API_KEY` on the Nexus server before starting the local web interface.

## Tests

```bash
pytest -q
```

## Security

- 🔐 The permanent OpenAI API key must remain server-side.
- 🛡️ Realtime client sessions use short-lived credentials.
- 🧠 Voice requests remain subject to NexusCore's existing authorization and safety controls.
- ⚠️ `code_tester` is an untrusted process runner, not a perfect OS sandbox. Production deployments should eventually add a dedicated sandbox/container/VM boundary.
