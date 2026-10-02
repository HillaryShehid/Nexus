# Nexus v1.5.0 — Personal AI Assistant

Nexus is currently **personal-first**. Business/CRM/sales/client workflows are intentionally out of scope for this phase so the core assistant can become deeper and more reliable first.

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
- 
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
Client / API / future UI
          |
       NexusCore
          |
   NexusBrain (canonical)
     /    |     \
 memory  tasks  tools
   |       |      |
storage checkpoints permissions
                 |
            owner identity
```

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

## Tests

```bash
pytest -q
```

## Security

code_tester is an untrusted process runner, not a perfect OS sandbox. Production deployments should eventually add a dedicated sandbox/container/VM boundary.
