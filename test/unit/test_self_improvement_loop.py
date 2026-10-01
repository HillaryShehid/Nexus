import json

from src.brain.self_improvement_loop import SelfImprovementLoop


def _performance(category="tool_runtime", tool="calculator", runs=3, history=True):
    return {
        "history_recorded": history,
        "weakness_signals": [{
            "type": "repeated_tool_failure",
            "tool": tool,
            "distinct_runs": runs,
            "failure_events": runs,
            "window_runs": runs,
            "threshold": 3,
        }],
        "root_cause_hypotheses": [{
            "tool": tool,
            "hypotheses": [{
                "cause_hypothesis": "tool_or_external_dependency",
                "observed_category": category,
                "supporting_runs": runs,
                "supporting_events": runs,
                "evidence_share_bp": 10_000,
                "confidence": "hypothesis_only",
            }],
        }],
    }


def test_weak_or_unknown_cause_collects_evidence_without_experiment(tmp_path):
    loop = SelfImprovementLoop(str(tmp_path))
    cycle = loop.advance(_performance(category="unknown", runs=7))

    assert cycle["status"] == "collecting_evidence"
    assert cycle["experiment"] is None
    assert cycle["candidate_active"] is False


def test_supported_hypothesis_runs_one_filtered_synthetic_experiment(tmp_path):
    loop = SelfImprovementLoop(str(tmp_path))
    cycle = loop.advance(_performance(category="tool_runtime"))

    assert cycle["status"] == "experiment_complete"
    assert cycle["experiment"]["scope"] == "synthetic_labeled_diagnostic_fixtures"
    assert cycle["experiment"]["observed_category"] == "tool_runtime"
    assert cycle["confidence_before"] == "hypothesis_only"
    assert cycle["confidence_after"] == "synthetic_evidence_supports_prediction"
    assert cycle["evidence_stage"] == "synthetic_only"
    assert cycle["candidate_active"] is False
    assert cycle["promotion"] == "owner_approval_required"

    repeated = loop.advance(_performance(category="tool_runtime", runs=4))
    assert repeated["status"] == "waiting_for_new_evidence"
    assert repeated["experiment"] is None
    assert loop.report()["completed_investigations"] == 1


def test_recovery_signal_runs_replay_without_claiming_live_improvement(tmp_path):
    loop = SelfImprovementLoop(str(tmp_path))
    performance = {
        "history_recorded": True,
        "weakness_signals": [{
            "type": "unrecovered_replanning", "distinct_runs": 3,
            "failure_events": 5, "window_runs": 3, "threshold": 3,
        }],
        "root_cause_hypotheses": [],
    }
    cycle = loop.advance(performance)

    assert cycle["experiment"]["scope"] == "synthetic_labeled_recovery_replays"
    assert cycle["confidence_after"] == "synthetic_evidence_supports_prediction"
    assert cycle["candidate_active"] is False
    assert loop.report()["live_task_efficacy_established"] is False


def test_recurrent_known_failure_can_trigger_bounded_external_research(tmp_path):
    class Researcher:
        def research(self, request, brief, execute, max_tool_calls):
            assert "official technical sources" in request
            assert max_tool_calls == 4
            assert brief["research_queries"] == [
                "calculator tool_or_external_dependency official documentation troubleshooting"
            ]
            return {
                "status": "enough_evidence",
                "queries": brief["research_queries"],
                "sources": [{
                    "source_id": "S1", "title": "Official calculator docs",
                    "url": "https://docs.example.org/calculator", "domain": "docs.example.org",
                    "authority_signal": "official_domain_candidate",
                    "primary_evidence_candidate": True,
                    "freshness_signal": "recent_year_mentioned",
                    "relevance_basis_points": 8000,
                }],
                "claims": [], "contradictions": [],
                "missing_information": [], "confidence": "medium",
                "summary": "A bounded public-source review.",
            }, []

    loop = SelfImprovementLoop(str(tmp_path))
    cycle = loop.advance(
        _performance(), research_controller=Researcher(), execute=lambda _task: None
    )

    assert cycle["external_research"]["status"] == "enough_evidence"
    assert cycle["next_action"] == "review_source_backed_hypothesis_in_sandbox"
    journal = json.loads((tmp_path / "nexus_self_improvement.json").read_text())
    assert "private" not in repr(journal).lower()
