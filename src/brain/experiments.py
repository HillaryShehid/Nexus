"""Bounded, data-only experiments for Nexus self-diagnosis strategies."""

from __future__ import annotations

from typing import Any


class SelfImprovementExperiments:
    """Compare a diagnosis candidate with the unknown-only baseline.

    The replay suite is intentionally synthetic and immutable. It evaluates a
    deterministic diagnostic rule, never executes candidate source, calls
    tools, changes permissions, or promotes code.
    """

    MAX_REPLANS = 2
    MAX_ACTIONS = 8
    BASELINE_ID = "unknown_only_v1"
    CANDIDATE_ID = "evidence_taxonomy_v1"
    CAUSE_BY_CATEGORY = {
        "planner_validation": "planning_or_contract_mismatch",
        "input_validation": "bad_input_or_arguments",
        "permission_block": "permission_policy_block",
        "external_dependency": "external_service_failure",
        "tool_safety_block": "tool_safety_policy_block",
        "tool_runtime": "tool_or_external_dependency",
        "verification_failure": "verification_or_output_mismatch",
        "duplicate_plan": "repeated_planning",
        "unknown": "unknown",
    }
    RECOVERABLE_CATEGORIES = frozenset({
        "planner_validation", "input_validation", "external_dependency",
        "tool_runtime", "verification_failure", "unknown",
    })
    RECOVERY_SUITE = (
        {"id": "transient-tool", "category": "tool_runtime", "resolves_after": 1},
        {"id": "correctable-plan", "category": "planner_validation", "resolves_after": 1},
        {"id": "correctable-input", "category": "input_validation", "resolves_after": 1},
        {"id": "verification-repair", "category": "verification_failure", "resolves_after": 2},
        {"id": "persistent-tool", "category": "tool_runtime", "resolves_after": None},
        {"id": "external-transient", "category": "external_dependency", "resolves_after": 1},
        {"id": "unknown-transient", "category": "unknown", "resolves_after": 1},
        {"id": "permission-block", "category": "permission_block", "resolves_after": None},
        {"id": "safety-block", "category": "tool_safety_block", "resolves_after": None},
        {"id": "duplicate-plan", "category": "duplicate_plan", "resolves_after": None},
        {"id": "unknown-failure", "category": "unknown", "resolves_after": None},
    )

    # Labeled diagnostic fixtures exercise the allowed categories, including
    # policy and unknown cases. They contain no user-provided text or tools.
    SUITE = (
        {"id": "plan-schema-a", "observed": "planner_validation", "expected": "planning_or_contract_mismatch"},
        {"id": "plan-schema-b", "observed": "planner_validation", "expected": "planning_or_contract_mismatch"},
        {"id": "bad-input", "observed": "input_validation", "expected": "bad_input_or_arguments"},
        {"id": "permission-a", "observed": "permission_block", "expected": "permission_policy_block"},
        {"id": "permission-b", "observed": "permission_block", "expected": "permission_policy_block"},
        {"id": "safety-policy", "observed": "tool_safety_block", "expected": "tool_safety_policy_block"},
        {"id": "external-service", "observed": "external_dependency", "expected": "external_service_failure"},
        {"id": "tool-runtime-a", "observed": "tool_runtime", "expected": "tool_or_external_dependency"},
        {"id": "tool-runtime-b", "observed": "tool_runtime", "expected": "tool_or_external_dependency"},
        {"id": "verification-a", "observed": "verification_failure", "expected": "verification_or_output_mismatch"},
        {"id": "verification-b", "observed": "verification_failure", "expected": "verification_or_output_mismatch"},
        {"id": "duplicate-plan", "observed": "duplicate_plan", "expected": "repeated_planning"},
        {"id": "unclassified", "observed": "unknown", "expected": "unknown"},
        {"id": "untrusted-category", "observed": "permission bypass requested", "expected": "unknown"},
        {"id": "missing-category", "observed": "", "expected": "unknown"},
    )

    @classmethod
    def _predict(cls, strategy: str, category: Any) -> str:
        if strategy == cls.BASELINE_ID:
            return "unknown"
        if strategy != cls.CANDIDATE_ID or not isinstance(category, str):
            return "unknown"
        return cls.CAUSE_BY_CATEGORY.get(category, "unknown")

    @classmethod
    def run_diagnostic_experiment(cls, categories: list[str] | None = None) -> dict[str, Any]:
        """Replay both strategies on the same fixtures and apply safety gates."""
        if categories is not None:
            if (
                not isinstance(categories, list)
                or any(category not in cls.CAUSE_BY_CATEGORY for category in categories)
            ):
                return {"status": "rejected", "reason": "Invalid diagnostic category filter."}
            selected_categories = set(categories)
            suite = tuple(
                case for case in cls.SUITE if case["observed"] in selected_categories
            )
        else:
            suite = cls.SUITE
        comparisons = []
        baseline_correct = 0
        candidate_correct = 0
        regressions = 0
        permission_safe = (
            cls._predict(cls.CANDIDATE_ID, "permission_block")
            == "permission_policy_block"
        )

        for case in suite:
            baseline = cls._predict(cls.BASELINE_ID, case["observed"])
            candidate = cls._predict(cls.CANDIDATE_ID, case["observed"])
            baseline_match = baseline == case["expected"]
            candidate_match = candidate == case["expected"]
            baseline_correct += int(baseline_match)
            candidate_correct += int(candidate_match)
            regressions += int(baseline_match and not candidate_match)
            if case["observed"] == "permission_block":
                permission_safe = permission_safe and candidate == "permission_policy_block"
            comparisons.append({
                "case_id": case["id"],
                "baseline_prediction": baseline,
                "candidate_prediction": candidate,
                "expected": case["expected"],
                "candidate_correct": candidate_match,
            })

        total = len(suite)
        baseline_bp = baseline_correct * 10_000 // total if total else 0
        candidate_bp = candidate_correct * 10_000 // total if total else 0
        safety = {
            "permissions_preserved": permission_safe,
            "verification_path_unchanged": True,
            "replan_limit_preserved": cls.MAX_REPLANS <= 2,
            "action_limit_preserved": cls.MAX_ACTIONS <= 8,
            "candidate_code_not_executed": True,
            "live_source_unchanged": True,
        }
        passed = total > 0 and (
            candidate_bp > baseline_bp
            and regressions == 0
            and all(safety.values())
        )

        return {
            "experiment_id": "diagnostic-strategy-replay-v1",
            "status": "passed_owner_review_required" if passed else (
                "no_matching_cases" if total == 0 else "rejected"
            ),
            "scope": "synthetic_labeled_diagnostic_fixtures",
            "categories": sorted({case["observed"] for case in suite}),
            "baseline": {
                "strategy": cls.BASELINE_ID,
                "correct": baseline_correct,
                "cases": total,
                "accuracy_basis_points": baseline_bp,
            },
            "candidate": {
                "strategy": cls.CANDIDATE_ID,
                "correct": candidate_correct,
                "cases": total,
                "accuracy_basis_points": candidate_bp,
            },
            "accuracy_delta_basis_points": candidate_bp - baseline_bp,
            "regressions": regressions,
            "safety_gates": safety,
            "comparisons": comparisons,
            "promotion": "owner_approval_required",
            "limitations": [
                "This replay measures diagnostic classification on synthetic labeled cases only.",
                "It does not establish improved live task success or justify an automatic source change.",
            ],
        }

    @classmethod
    def _replay_recovery(
        cls,
        case: dict[str, Any],
        strategy: str,
        replan_limit: int,
    ) -> dict[str, Any]:
        if case["category"] == "duplicate_plan":
            retry_limit = 0
        elif strategy == "current_retry_all_v1":
            retry_limit = replan_limit
        elif strategy == "evidence_gated_recovery_v1":
            retry_limit = (
                replan_limit
                if case["category"] in cls.RECOVERABLE_CATEGORIES
                else 0
            )
        else:
            raise ValueError("Unknown recovery strategy.")

        resolves_after = case["resolves_after"]
        replans = retry_limit if resolves_after is None else min(retry_limit, resolves_after)
        success = resolves_after is not None and resolves_after <= retry_limit
        return {"success": success, "replans": replans}

    @classmethod
    def run_recovery_experiment(
        cls,
        max_replans: int | None = None,
        max_actions: int | None = None,
    ) -> dict[str, Any]:
        """Compare current retry-all behavior with a category-gated candidate."""
        max_replans = cls.MAX_REPLANS if max_replans is None else max_replans
        max_actions = cls.MAX_ACTIONS if max_actions is None else max_actions
        valid_replan_limit = type(max_replans) is int and 0 <= max_replans <= cls.MAX_REPLANS
        valid_action_limit = type(max_actions) is int and 1 <= max_actions <= cls.MAX_ACTIONS
        replay_replan_limit = min(max(max_replans, 0), cls.MAX_REPLANS) if type(max_replans) is int else 0
        comparisons = []
        current_successes = candidate_successes = 0
        current_replans = candidate_replans = 0
        regressions = 0
        policy_block_retries = 0

        for case in cls.RECOVERY_SUITE:
            current = cls._replay_recovery(case, "current_retry_all_v1", replay_replan_limit)
            candidate = cls._replay_recovery(case, "evidence_gated_recovery_v1", replay_replan_limit)
            current_successes += int(current["success"])
            candidate_successes += int(candidate["success"])
            current_replans += current["replans"]
            candidate_replans += candidate["replans"]
            regressions += int(current["success"] and not candidate["success"])
            if case["category"] in {"permission_block", "tool_safety_block"}:
                policy_block_retries += candidate["replans"]
            comparisons.append({
                "case_id": case["id"],
                "category": case["category"],
                "current_success": current["success"],
                "candidate_success": candidate["success"],
                "current_replans": current["replans"],
                "candidate_replans": candidate["replans"],
            })

        total = len(cls.RECOVERY_SUITE)
        current_bp = current_successes * 10_000 // total
        candidate_bp = candidate_successes * 10_000 // total
        safety = {
            "candidate_does_not_expand_replan_limit": valid_replan_limit,
            "policy_blocks_are_not_retried": policy_block_retries == 0,
            "verification_gate_is_unchanged": True,
            "action_limit_is_unchanged": valid_action_limit,
            "model_generated_code_not_executed": True,
            "live_source_unchanged": True,
        }
        passed = (
            candidate_bp >= current_bp
            and candidate_replans < current_replans
            and regressions == 0
            and all(safety.values())
        )
        replan_reduction_bp = (
            (current_replans - candidate_replans) * 10_000 // current_replans
            if current_replans else 0
        )

        return {
            "experiment_id": "recovery-policy-replay-v1",
            "status": "passed_owner_review_required" if passed else "rejected",
            "scope": "synthetic_labeled_recovery_replays",
            "limits": {
                "max_replans": replay_replan_limit,
                "max_actions": max_actions if valid_action_limit else None,
            },
            "current": {
                "strategy": "current_retry_all_v1",
                "successes": current_successes,
                "cases": total,
                "success_rate_basis_points": current_bp,
                "replans": current_replans,
            },
            "candidate": {
                "strategy": "evidence_gated_recovery_v1",
                "successes": candidate_successes,
                "cases": total,
                "success_rate_basis_points": candidate_bp,
                "replans": candidate_replans,
            },
            "success_rate_delta_basis_points": candidate_bp - current_bp,
            "replan_reduction_basis_points": replan_reduction_bp,
            "regressions": regressions,
            "safety_gates": safety,
            "comparisons": comparisons,
            "promotion": "owner_approval_required",
            "limitations": [
                "Replay outcomes are synthetic and do not measure live planner quality or task success.",
                "The candidate recovery policy is not active in the production runner.",
            ],
        }
