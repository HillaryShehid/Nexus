# Nexus v0.1.5 — Functional Brain

Nexus v0.1.5 is the first release focused on making Nexus a real executive brain on top of the v0.1.2 foundation.

## Cognitive loop

Understand → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

### Brain components

- `src/brain/understanding.py` — converts requests into structured goals and constraints.
- `src/brain/router.py` — cheap fast/normal/deep routing so simple requests stay responsive.
- `src/brain/state.py` — persistent per-task cognitive state and evidence.
- `src/brain/memory.py` — reads/writes the existing memory system.
- `src/brain/goals.py` — tracks objective completion from verified evidence.
- `src/brain/adaptation.py` — diagnoses failures and turns them into bounded recovery plans.
- `src/brain/brain.py` — executive orchestration.

The v0.1.2 foundation still owns tools, permissions, verification, learning storage, and the model interface.

## Design goals

- Fast by default; deeper reasoning only when a request needs it.
- Plan once, execute verified steps, and re-plan after meaningful failures.
- Never bypass the permission system.
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
