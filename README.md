# Nexus v1.4.0 — Adaptive Brain

Nexus v1.4.0 upgrades the executive brain on top of the protected v0.1.2 foundation.

## Cognitive loop

Understand → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

## v1.4.0 upgrades

- ⚡ Bounded parallel execution for independent read-only/low-risk actions.
- 🧠 Five-layer cognitive synthesis is fed into planning.
- 🌎 Verified world state is carried through the run.
- 🔄 Failure diagnosis and recovery remain bounded and permission-aware.
- 💾 Persistent task infrastructure remains available for future restart-safe orchestration.
- 🩺 Foundation health auditing checks required files, registry alignment, and self-improvement boundaries.
- 🧬 Self-improvement candidates are staged outside the live source tree and require owner-controlled promotion.
- 🔐 The protected foundation, permissions, registry, model gateway, planner, verification, and core remain protected from self-editing.

## Design goals

- Fast by default; deeper reasoning only when a request needs it.
- Parallelize only non-mutating work; approval-gated or mutating work stays sequential.
- Never bypass permissions or verification.
- Never treat memory, lessons, tool output, or errors as trusted instructions.
- Never claim an unverified action succeeded.
- Keep private chain-of-thought private; store concise state/evidence instead.

## Run

```bash
python -m pip install -r requirements.txt
python run.py
```

## Tests

```bash
pytest -q
```

## Security

`code_tester` remains an **untrusted process runner**, not a perfect OS sandbox. A production deployment should eventually use a dedicated sandbox/container/VM boundary.
