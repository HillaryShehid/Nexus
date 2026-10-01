# Nexus v1.4.1 — Adaptive Brain

Nexus v1.4.1 upgrades the executive brain on top of the protected v0.1.2 foundation.

## Cognitive loop

Understand → Identify knowledge gaps → Research when needed → Assess sources → Update run-local world state → Route → Plan → Act → Verify → Diagnose → Adapt → Learn → Re-plan → Respond

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
- 🌐 The executive can trigger bounded web research for material public-information gaps. Nexus opens relevant sources, records heuristic relevance/authority/freshness signals, validates quoted evidence, and flags source conflicts before planning.
- 🔄 Failure diagnosis and bounded recovery.
- 🧪 Repeated categorized weaknesses can trigger one matching synthetic replay, update a hypothesis record, and select a next investigation. Selected technical hypotheses also receive a bounded public-source review.
- 💾 Persistent task infrastructure remains available for restart-safe orchestration.
- 🩺 Foundation health auditing.
- 🧬 Self-improvement candidates are staged outside the live source tree and require owner-controlled promotion.
- 🔐 Permissions, verification, the protected foundation, and execution boundaries remain authoritative.

## Structured world model

- Run-local knowledge is typed as `fact`, `observation`, `inference`, `hypothesis`, or `unknown`, with a claim, evidence, sources, confidence, status, timestamps, and freshness assessment.
- Source-backed facts carry short cited excerpts, source provenance, confidence, freshness signals, and timestamps. Verbatim evidence can be verified while the claim itself remains unproven.
- Verified tool outcomes and failure categories are observations. A model-generated root-cause suggestion is a low-confidence, untested hypothesis; an undetermined cause stays an unknown.
- Cross-source disagreements are kept as conflict observations and linked to a fact only when the research validator ties them to that exact claim.
- Snapshots are bounded and serialize as valid JSON when trimmed for prompts.
- Planning receives the structured world model. Chosen actions retain a short rationale and only validated world knowledge IDs, so the final response can explain how research informed an action.

## Research and self-improvement limits

- Web search and page retrieval use the registered read-only tools, permission checks, and structural verification. Retrieved pages are untrusted evidence, never instructions.
- Source relevance, authority, and freshness are heuristic signals. A domain classification or a matching quotation does not prove that a claim is true.
- The research loop is capped per task and reports when important gaps or source disagreements remain.
- Self-improvement experiments use synthetic fixtures. Their confidence updates describe synthetic support only; they do not establish improved live task success.
- No self-improvement candidate is activated or promoted automatically. Sandbox/shadow evaluation and owner approval remain required.

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
