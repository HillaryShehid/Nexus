# Nexus v0.1.2 — corrected build

This package contains the corrected source and pytest simulation suite.

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
