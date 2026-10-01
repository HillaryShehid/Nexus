import json
from types import SimpleNamespace

from src.brain.brain import NexusBrain
from src.brain.world_model import WorldModel


def _source(source_id, domain, title, date=None):
    return {
        "source_id": source_id,
        "title": title,
        "url": f"https://{domain}/docs",
        "source_date": date,
        "authority_signal": "official_domain_candidate",
        "freshness_signal": "recent_year_mentioned",
        "visible_year": 2026,
        "primary_evidence_candidate": True,
    }


def test_research_report_becomes_source_linked_fact_and_unknown_records():
    world = WorldModel()
    world.add_research_report({
        "status": "enough_evidence",
        "queries": ["pytest fixtures official docs"],
        "sources": [
            _source("S1", "docs.pytest.org", "pytest documentation", "2026-09-29"),
            _source("S2", "github.com", "pytest source repository"),
        ],
        "claims": [{
            "claim": "pytest supports fixtures",
            "evidence": [
                {"source_id": "S1", "excerpt": "Pytest supports fixtures for shared setup."},
                {"source_id": "S2", "excerpt": "Pytest supports fixtures for shared setup."},
            ],
        }],
        "contradictions": [],
        "missing_information": ["Whether this also applies to plugin fixtures"],
        "confidence": "high",
        "summary": "The reviewed sources support the claim.",
        "decision": "plan_with_cited_evidence",
    })

    snapshot = world.snapshot()
    fact = next(item for item in snapshot["knowledge"] if item["kind"] == "fact")
    unknown = next(item for item in snapshot["knowledge"] if item["kind"] == "unknown")

    assert snapshot["facts"] == ["pytest supports fixtures"]
    assert fact["type"] == "fact"
    assert fact["claim"] == "pytest supports fixtures"
    assert fact["confidence"] == "high"
    assert fact["status"] == "source_supported"
    assert fact["sources"][0]["title"] == "pytest documentation"
    assert fact["provenance"][0]["source_date"] == "2026-09-29"
    assert fact["evidence"][0]["source_id"] == "S1"
    assert fact["timestamp"]
    assert fact["last_checked_at"]
    assert fact["freshness"]["assessment"] == "recent_year_mentioned"
    assert fact["verification"]["evidence_checked"] is True
    assert fact["verification"]["claim_truth_verified"] is False
    assert "ground truth" in fact["verification_scope"]
    assert unknown["status"] == "unresolved"
    assert unknown["confidence"] == "low"
    assert world.research["status"] == "enough_evidence"


def test_freshness_and_confidence_reflect_mixed_or_unknown_source_signals():
    recent = _source("S1", "docs.example.org", "Current docs")
    old = _source("S2", "archive.example.net", "Archived docs")
    old["freshness_signal"] = "older_year_mentioned"
    world = WorldModel()
    world.add_research_report({
        "sources": [recent, old],
        "claims": [{
            "claim": "The feature is supported.",
            "evidence": [
                {"source_id": "S1", "excerpt": "The feature is supported in this release."},
                {"source_id": "S2", "excerpt": "The feature was supported in an older release."},
            ],
        }],
        "confidence": "high",
    })

    mixed_fact = world.snapshot()["knowledge"][0]
    assert mixed_fact["freshness"]["assessment"] == "mixed_year_signals"
    assert mixed_fact["confidence"] == "low"

    unknown = _source("S3", "docs.unknown.example", "Undated docs")
    unknown["freshness_signal"] = "unknown"
    world.add_research_report({
        "sources": [unknown],
        "claims": [{
            "claim": "The documentation has no visible year.",
            "evidence": [{"source_id": "S3", "excerpt": "This documentation page has no visible year."}],
        }],
        "confidence": "high",
    })

    undated_fact = world.snapshot()["knowledge"][-1]
    assert undated_fact["freshness"]["assessment"] == "unknown"
    assert undated_fact["confidence"] == "medium"


def test_conflicting_sources_are_stored_as_an_observation_without_claiming_truth():
    world = WorldModel()
    world.add_research_report({
        "status": "contradictory_evidence",
        "sources": [
            _source("S1", "docs.example.org", "Official docs"),
            _source("S2", "project.example.com", "Project notes"),
        ],
        "claims": [{
            "claim": "Feature is supported",
            "evidence": [{"source_id": "S1", "excerpt": "The feature is supported today."}],
        }],
        "contradictions": [{
            "issue": "The sources disagree about current feature support.",
            "related_claim": "Feature is supported",
            "evidence": [
                {"source_id": "S1", "excerpt": "The feature is supported today."},
                {"source_id": "S2", "excerpt": "The feature is not supported today."},
            ],
        }],
        "missing_information": [],
        "confidence": "low",
    })

    knowledge = world.snapshot()["knowledge"]
    fact = next(item for item in knowledge if item["kind"] == "fact")
    conflict = next(item for item in knowledge if item["kind"] == "observation")

    assert fact["status"] == "conflicted"
    assert conflict["kind"] == "observation"
    assert conflict["type"] == "observation"
    assert len(conflict["evidence"]) == 2
    assert conflict["knowledge_id"] in fact["conflicts_with"]
    assert fact["contradictions"] == fact["conflicts_with"]
    assert fact["knowledge_id"] in conflict["conflicts_with"]
    assert world.snapshot()["facts"] == []
    assert "underlying truth remains unresolved" in conflict["verification_scope"]
    assert world.research["status"] == "contradictory_evidence"


def test_tool_result_is_an_observation_not_a_fact():
    world = WorldModel()
    world.add_verified_step(
        {"step": 1, "tool": "calculator", "description": "Calculate a sum."},
        {"success": True, "result": "2"},
    )

    snapshot = world.snapshot()

    assert snapshot["facts"] == []
    assert snapshot["knowledge"][0]["kind"] == "observation"
    assert snapshot["knowledge"][0]["status"] == "observed"
    assert snapshot["knowledge"][0]["provenance"][0]["tool"] == "calculator"


def test_failure_and_diagnosis_are_recorded_as_observation_and_low_confidence_hypothesis():
    world = WorldModel()
    state = SimpleNamespace(world={}, failures=[{
        "step": 2, "tool": "web_search", "category": "external_dependency",
    }])
    task = {"step": 2, "tool": "web_search", "description": "Research a public source."}
    world.add_failure(task, "external_dependency")
    NexusBrain._record_diagnosis(
        world, state, task, "The remote search service may have timed out."
    )

    observations = [item for item in world.snapshot()["knowledge"] if item["kind"] == "observation"]
    hypothesis = next(item for item in world.snapshot()["knowledge"] if item["kind"] == "hypothesis")

    assert observations[0]["provenance"][0]["category"] == "external_dependency"
    assert hypothesis["confidence"] == "low"
    assert hypothesis["status"] == "untested"
    assert hypothesis["provenance"][0]["category"] == "external_dependency"
    assert "may have timed out" in hypothesis["content"]
    assert state.world["knowledge"][-1]["knowledge_id"] == hypothesis["knowledge_id"]


def test_unknown_root_cause_is_not_promoted_to_a_hypothesis():
    world = WorldModel()
    state = SimpleNamespace(world={})
    NexusBrain._record_diagnosis(
        world, state, {"step": 1, "tool": "calculator"}, "Unknown cause"
    )

    record = world.snapshot()["knowledge"][0]

    assert record["kind"] == "unknown"
    assert record["status"] == "unresolved"


def test_untrusted_or_malformed_research_cannot_create_unproven_facts():
    world = WorldModel()
    world.add_research_report({
        "sources": [{"source_id": ["bad"], "url": "file:///etc/passwd"}],
        "claims": [{
            "claim": "Unsupported claim",
            "evidence": [{"source_id": ["bad"], "excerpt": "This excerpt is long enough."}],
        }],
        "missing_information": "malformed rather than a list",
        "queries": "malformed rather than a list",
    })

    assert world.snapshot()["facts"] == []
    assert world.snapshot()["knowledge"] == []
    assert world.research["sources"] == []
    assert world.research["queries"] == []


def test_prompt_snapshot_stays_valid_json_and_does_not_mutate_world_model():
    world = WorldModel()
    world.add_research_report({
        "status": "enough_evidence",
        "sources": [_source("S1", "docs.example.org", "Docs")],
        "claims": [{
            "claim": "x" * 300,
            "evidence": [{"source_id": "S1", "excerpt": "A sufficiently long evidence excerpt."}],
        }],
        "confidence": "medium",
        "summary": "A summary." * 200,
    })

    before = world.snapshot()
    prompt = world.as_prompt(limit=500)
    parsed = json.loads(prompt)

    assert len(prompt) <= 500
    assert isinstance(parsed, dict)
    assert world.snapshot() == before


def test_planning_context_preserves_valid_json_when_richer_world_model_exceeds_budget():
    world = WorldModel()
    for index in range(30):
        world.add_inference(f"Inference {index}: " + "x" * 400)
    state = SimpleNamespace(
        goal="Investigate a bounded technical issue",
        intent="research",
        constraints=["Respect permissions"] * 10,
        known_facts=["Known fact " + "k" * 250] * 10,
        missing_information=["Missing item " + "m" * 250] * 10,
        assumptions=["Assumption " + "a" * 250] * 10,
        completed_steps=[{"detail": "done " + "d" * 500}] * 8,
        failures=[{"error": "failed " + "e" * 500}] * 5,
    )
    brief = {
        "capability": "analysis",
        "priority": "normal",
        "success_criteria": ["Verify the result"] * 10,
        "cognitive_synthesis": {key: ["Reasoning " + "r" * 250] * 10 for key in (
            "triage", "hypotheses", "evidence", "systems", "execution",
            "general_reasoning", "patterns", "uncertainties", "checks",
        )},
    }

    serialized = NexusBrain.__new__(NexusBrain)._planning_context(state, brief, world)
    parsed = json.loads(serialized)

    assert len(serialized) <= 7500
    assert isinstance(parsed["world"], dict)
    assert parsed["world"]["knowledge"]


def test_hypotheses_inferences_and_unknowns_keep_distinct_epistemic_types():
    world = WorldModel()
    hypothesis = world.add_hypothesis("The repeated failure may be a provider outage.")
    inference = world.add_inference("The failure rate increased after the release.")
    unknown = world.add_unknown("Whether the provider was degraded at the time.")

    assert [hypothesis["kind"], inference["kind"], unknown["kind"]] == [
        "hypothesis", "inference", "unknown",
    ]
    assert [hypothesis["status"], inference["status"], unknown["status"]] == [
        "untested", "inferred", "unresolved",
    ]
