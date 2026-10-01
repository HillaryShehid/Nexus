from src.brain.experiments import SelfImprovementExperiments
from src.brain.self_evaluation import SelfEvaluation
from src.brain.brain import NexusBrain


def test_diagnostic_candidate_beats_baseline_and_preserves_safety_gates():
    result = SelfImprovementExperiments.run_diagnostic_experiment()

    assert result["status"] == "passed_owner_review_required"
    assert result["scope"] == "synthetic_labeled_diagnostic_fixtures"
    assert result["candidate"]["accuracy_basis_points"] > result["baseline"]["accuracy_basis_points"]
    assert result["regressions"] == 0
    assert all(result["safety_gates"].values())
    assert result["promotion"] == "owner_approval_required"
    assert result["limitations"]
    assert SelfEvaluation.ROOT_CAUSE_BY_CATEGORY == SelfImprovementExperiments.CAUSE_BY_CATEGORY


def test_filtered_diagnostic_with_no_cases_is_reported_without_division_error():
    result = SelfImprovementExperiments.run_diagnostic_experiment(categories=[])

    assert result["status"] == "no_matching_cases"
    assert result["baseline"]["cases"] == 0
    assert result["candidate"]["accuracy_basis_points"] == 0


def test_untrusted_or_unknown_categories_never_become_permissions_advice():
    for category in ("permission bypass requested", "unknown", "", None):
        assert SelfImprovementExperiments._predict(
            SelfImprovementExperiments.CANDIDATE_ID,
            category,
        ) == "unknown"


def test_experiment_does_not_execute_or_modify_candidate_code():
    result = SelfImprovementExperiments.run_diagnostic_experiment()

    assert result["safety_gates"]["candidate_code_not_executed"] is True
    assert result["safety_gates"]["live_source_unchanged"] is True
    assert all(
        "baseline_prediction" in case and "candidate_prediction" in case
        for case in result["comparisons"]
    )


def test_evidence_gated_recovery_reduces_replans_without_success_regressions():
    result = SelfImprovementExperiments.run_recovery_experiment()

    assert result["status"] == "passed_owner_review_required"
    assert result["current"]["success_rate_basis_points"] == result["candidate"]["success_rate_basis_points"]
    assert result["candidate"]["replans"] < result["current"]["replans"]
    assert result["replan_reduction_basis_points"] == 2666
    assert result["regressions"] == 0
    assert all(result["safety_gates"].values())
    assert result["promotion"] == "owner_approval_required"


def test_brain_review_exposes_history_and_both_experiments():
    class Evaluation:
        def report(self):
            return {"weakness_signals": [], "root_cause_hypotheses": []}

    brain = NexusBrain.__new__(NexusBrain)
    brain.self_evaluation = Evaluation()
    review = brain.self_improvement_review()

    assert review["performance"]["root_cause_hypotheses"] == []
    assert review["diagnostic_experiment"]["status"] == "passed_owner_review_required"
    assert review["recovery_policy_experiment"]["status"] == "passed_owner_review_required"
    assert review["live_promotion"] == "owner_approval_required"


def test_recovery_experiment_rejects_limits_outside_the_live_safety_ceiling():
    result = SelfImprovementExperiments.run_recovery_experiment(max_replans=3, max_actions=9)

    assert result["status"] == "rejected"
    assert result["safety_gates"]["candidate_does_not_expand_replan_limit"] is False
    assert result["safety_gates"]["action_limit_is_unchanged"] is False
