# Nexus v0.2.0 — Brain foundation

Nexus v0.2.0 keeps the v0.1.2 safety/tool foundation and adds a cognitive orchestration layer.

## Brain loop

Understand → Remember → Reason → Decide → Act → Verify → Diagnose → Adapt → Learn → Respond

The brain is split into small components:

- `src/brain/understanding.py` — turns the owner's request into a structured goal and constraints.
- `src/brain/state.py` — maintains the current cognitive state and evidence.
- `src/brain/memory.py` — reads/writes Nexus memory through the existing memory tool.
- `src/brain/decision.py` — selects the next registered tool action and validates it before execution.
- `src/brain/brain.py` — orchestrates the cognitive loop and recovery behavior.

The existing planner, permissions, tools, verification, and learning systems remain underneath the brain. The model is a reasoning component, not the whole application.

## Setup

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the two environment variables.

Run Nexus:

```bash
python run.py
```

Run tests:

```bash
pytest -q
```

## Important security note

`code_tester` is an **untrusted process runner**, not a perfect operating-system sandbox. It has a timeout, isolated working directory, isolated environment, and no shell invocation, but full OS-level isolation requires a dedicated sandbox/container/VM layer.
