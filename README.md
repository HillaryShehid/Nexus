# Nexus v1.4.1 — Adaptive Brain

Nexus v1.4.1 upgrades the executive brain on top of the protected v0.1.2 foundation.

## Cognitive loop

Understand → Synthesize → Challenge → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

## Cognitive architecture

Nexus blends six complementary layers into one intelligence:

- 🤖 **JARVIS** — executive orchestration, initiative, prioritization, and clear status.
- ⚡ **FRIDAY** — speed, triage, situational awareness, and context preservation.
- 🧠 **Ultron** — systems thinking, long-horizon planning, diagnostics, recovery, and persistence.
- 📚 **Claude Mythos** — deep research, evidence cross-checking, long-context synthesis, and scientific reasoning.
- 💬 **ChatGPT** — broad reasoning, coding, explanation, tool use, and flexible problem solving.
- 🌌 **ChatGPT Astral** — abstraction, pattern discovery, conceptual synthesis, creativity, and cross-domain reasoning.

These are not separate personalities or modes. Every meaningful task uses the full stack, with different capabilities emphasized as needed.

## v1.4.1 intelligence upgrades

- 🧠 Six-layer cognitive synthesis feeds planning.
- 🔎 Explicit hypothesis generation and uncertainty tracking.
- 🥊 Adversarial challenge of weak assumptions before action.
- 🧩 Systems/dependency analysis for complex tasks.
- ⚡ Bounded parallel execution for independent read-only/low-risk actions.
- 🌎 Verified world state is carried through the run.
- 🔄 Failure diagnosis and bounded recovery.
- 💾 Persistent task infrastructure remains available for restart-safe orchestration.
- 🩺 Foundation health auditing.
- 🧬 Self-improvement candidates are staged outside the live source tree and require owner-controlled promotion.
- 🔐 Permissions, verification, the protected foundation, and execution boundaries remain authoritative.

## Design goals

- Fast by default; deeper reasoning when a request needs it.
- Generate alternatives, challenge weak ones, then verify.
- Never bypass permissions or verification.
- Never treat memory, lessons, tool output, or errors as trusted instructions.
- Never claim an unverified action succeeded.
- Keep private chain-of-thought private; store concise state and evidence instead.

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

`code_tester` remains an **untrusted process runner**, not a perfect OS sandbox. A production deployment should eventually use a dedicated sandbox/container/VM boundary.
