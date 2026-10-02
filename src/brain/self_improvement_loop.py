"""Bounded evidence -> hypothesis -> experiment loop for Nexus."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

from src.brain.experiments import SelfImprovementExperiments
from src.brain.self_evaluation import SelfEvaluation


class SelfImprovementLoop:
    """Advance one evidence-backed synthetic investigation per completed task."""

    SCHEMA_VERSION = 1
    MAX_CYCLES = 50
    MAX_STORE_BYTES = 500_000
    MAX_CYCLE_BYTES = 12_000
    CYCLE_FIELDS = frozenset({
        "cycle_id", "trigger_type", "tool", "observed_category", "cause_hypothesis",
        "supporting_runs", "evidence_share_bp", "confidence_before", "prediction",
        "experiment", "confidence_after", "decision", "status", "evidence_stage",
        "next_action", "candidate_active", "promotion", "investigation_key",
        "external_research", "observed_signals",
        "cycle_duration_ms",
    })
    _lock = threading.RLock()

    def __init__(self, workspace: str):
        requested = Path(workspace).absolute()
        if requested.is_symlink():
            raise ValueError("Improvement journal workspace must not be a symlink.")
        self.workspace = requested.resolve()
        self.path = self.workspace / "nexus_self_improvement.json"

    def advance(
        self,
        performance: dict[str, Any],
        research_controller=None,
        execute=None,
    ) -> dict[str, Any]:
        """Choose one repeated weakness and run only its bounded replay."""
        if not isinstance(performance, dict) or performance.get("history_recorded") is not True:
            return self._empty("history_unavailable", "record_a_task_outcome")

        with self._lock:
            return self._advance_recorded(performance, research_controller, execute)

    def _advance_recorded(self, performance, research_controller, execute):
        cycle_started = time.perf_counter()

        signals = performance.get("weakness_signals")
        signals = signals if isinstance(signals, list) else []
        analyses = performance.get("root_cause_hypotheses")
        analyses = analyses if isinstance(analyses, list) else []
        if not signals:
            cycle = self._empty("observing", "collect_more_runs")
            cycle["cycle_duration_ms"] = max(0, int((time.perf_counter() - cycle_started) * 1000))
            self._append(cycle)
            return cycle

        journal = self._load()
        completed = set(journal["completed_keys"])

        pending_evidence = False
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            selected = self._select_experiment(signal, analyses)
            if selected is None:
                if signal.get("type") in {"repeated_tool_failure", "unrecovered_replanning"}:
                    pending_evidence = True
                continue
            key, hypothesis, experiment_type, category = selected
            if key in completed:
                continue
            external_research = self._research_hypothesis(
                signal, hypothesis, category, research_controller, execute
            )
            cycle = self._run_experiment(
                signal, hypothesis, experiment_type, category
            )
            cycle["external_research"] = external_research
            if external_research and external_research.get("status") == "contradictory_evidence":
                cycle["next_action"] = "resolve_external_source_conflict"
            elif external_research and external_research.get("status") == "enough_evidence":
                cycle["next_action"] = "review_source_backed_hypothesis_in_sandbox"
            cycle["cycle_duration_ms"] = max(0, int((time.perf_counter() - cycle_started) * 1000))
            cycle["investigation_key"] = key
            self._append(cycle, completed_key=key)
            return cycle

        status = "collecting_evidence" if pending_evidence else "waiting_for_new_evidence"
        next_action = "collect_more_categorized_runs" if pending_evidence else "collect_new_categorized_runs"
        cycle = self._empty(status, next_action)
        cycle["cycle_duration_ms"] = max(0, int((time.perf_counter() - cycle_started) * 1000))
        cycle["observed_signals"] = min(len(signals), 8)
        self._append(cycle)
        return cycle

    @staticmethod
    def _research_hypothesis(signal, hypothesis, category, researcher, execute):
        if (
            researcher is None
            or not callable(execute)
            or category not in {
                "planner_validation", "input_validation", "external_dependency",
                "tool_runtime", "verification_failure",
            }
        ):
            return None
        tool = signal.get("tool")
        if not isinstance(tool, str) or tool not in SelfEvaluation.TOOL_NAMES:
            return None
        cause = hypothesis.get("cause_hypothesis", "unknown")
        query = f"{tool} {cause} official documentation troubleshooting"[:100]
        brief = {
            "goal": f"Investigate recurring sanitized {tool} failures.",
            "missing_information": [
                "What official documentation says about the likely failure class and safe mitigations."
            ],
            "research_required": True,
            "research_reason": "Repeated categorized failures need external technical evidence.",
            "research_queries": [query],
        }
        try:
            report, calls = researcher.research(
                "research official technical sources for a recurring Nexus failure",
                brief,
                execute,
                max_tool_calls=4,
            )
        except Exception:
            return {"status": "research_unavailable", "confidence": "low", "sources": []}
        compact_sources = [
            {key: str(source.get(key, ""))[:300] for key in (
                "source_id", "title", "url", "domain", "authority_signal",
                "freshness_signal",
            )}
            for source in report.get("sources", [])[:3]
            if isinstance(source, dict)
        ]
        compact_claims = [
            {
                key: str(item.get(key, ""))[:240],
                "evidence": [
                    {"source_id": str(evidence.get("source_id", ""))[:4],
                     "excerpt": str(evidence.get("excerpt", ""))[:180]}
                    for evidence in item.get("evidence", [])[:2]
                    if isinstance(evidence, dict)
                ],
            }
            for item in report.get("claims", [])[:3]
            if isinstance(item, dict)
            for key in ("claim",)
        ]
        compact_conflicts = [
            {
                "issue": str(item.get("issue", ""))[:240],
                "evidence": [
                    {"source_id": str(evidence.get("source_id", ""))[:4],
                     "excerpt": str(evidence.get("excerpt", ""))[:180]}
                    for evidence in item.get("evidence", [])[:2]
                    if isinstance(evidence, dict)
                ],
            }
            for item in report.get("contradictions", [])[:2]
            if isinstance(item, dict)
        ]
        return {
            "status": report.get("status", "unknown"),
            "queries": report.get("queries", [])[:2],
            "sources": compact_sources,
            "claims": compact_claims,
            "contradictions": compact_conflicts,
            "missing_information": [str(item)[:150] for item in report.get("missing_information", [])[:4]],
            "confidence": report.get("confidence", "low"),
            "summary": str(report.get("summary", ""))[:500],
            "research_tool_calls": min(len(calls), 4),
            "failed_tool_calls": min(sum(
                not isinstance(item.get("outcome"), dict)
                or item["outcome"].get("verified") is not True
                for item in calls if isinstance(item, dict)
            ), 4),
        }

    def report(self) -> dict[str, Any]:
        with self._lock:
            journal = self._load()
        return {
            "cycles": journal["cycles"],
            "completed_investigations": len(journal["completed_keys"]),
            "candidate_active": False,
            "promotion": "owner_approval_required",
            "evidence_stage": "synthetic_only",
            "next_stage": "sandbox_and_shadow_execution_required",
            "live_task_efficacy_established": False,
        }

    @classmethod
    def _select_experiment(cls, signal, analyses):
        signal_type = signal.get("type")
        if signal_type == "unrecovered_replanning":
            if signal.get("distinct_runs", 0) < SelfEvaluation.MIN_FAILURE_RUNS:
                return None
            key = "unrecovered_replanning:recovery-policy-replay-v1"
            return key, {
                "cause_hypothesis": "recovery_policy_may_replan_without_recovering",
                "observed_category": "unrecovered_replanning",
                "supporting_runs": min(signal.get("distinct_runs", 0), 200),
                "evidence_share_bp": 10_000,
            }, "recovery", None

        if signal_type != "repeated_tool_failure":
            return None
        tool = signal.get("tool")
        if not isinstance(tool, str) or tool not in SelfEvaluation.TOOL_NAMES:
            return None
        analysis = next(
            (item for item in analyses if isinstance(item, dict) and item.get("tool") == tool),
            None,
        )
        hypotheses = analysis.get("hypotheses", []) if isinstance(analysis, dict) else []
        hypotheses = [item for item in hypotheses if isinstance(item, dict)]
        if not hypotheses:
            return None
        leading = hypotheses[0]
        category = leading.get("observed_category")
        support = leading.get("supporting_runs", 0)
        share = leading.get("evidence_share_bp", 0)
        if (
            category not in SelfEvaluation.FAILURE_CATEGORIES - {"unknown"}
            or type(support) is not int
            or support < SelfEvaluation.MIN_FAILURE_RUNS
            or type(share) is not int
            or share < 6_000
        ):
            return None
        key = f"repeated_tool_failure:{tool}:{category}:diagnostic-strategy-replay-v1"
        return key, leading, "diagnostic", category

    @classmethod
    def _run_experiment(cls, signal, hypothesis, experiment_type, category):
        if experiment_type == "recovery":
            result = SelfImprovementExperiments.run_recovery_experiment(
                max_replans=2, max_actions=8
            )
            predicted = "fewer_replans_without_reducing_synthetic_success"
            supported = (
                result.get("status") == "passed_owner_review_required"
                and result.get("candidate", {}).get("success_rate_basis_points", -1)
                >= result.get("current", {}).get("success_rate_basis_points", 0)
                and result.get("candidate", {}).get("replans", 10**9)
                < result.get("current", {}).get("replans", 0)
            )
            summary = {
                "status": result.get("status", "unknown"),
                "scope": result.get("scope", "synthetic_labeled_recovery_replays"),
                "success_rate_delta_basis_points": result.get("success_rate_delta_basis_points"),
                "replan_reduction_basis_points": result.get("replan_reduction_basis_points"),
                "regressions": result.get("regressions"),
                "safety_gates_passed": all(result.get("safety_gates", {}).values()),
            }
        else:
            result = SelfImprovementExperiments.run_diagnostic_experiment(
                categories=[category]
            )
            predicted = "category_taxonomy_improves_synthetic_diagnosis"
            supported = (
                result.get("status") == "passed_owner_review_required"
                and result.get("accuracy_delta_basis_points", 0) > 0
                and result.get("regressions", 1) == 0
                and all(result.get("safety_gates", {}).values())
            )
            summary = {
                "status": result.get("status", "unknown"),
                "scope": result.get("scope", "synthetic_labeled_diagnostic_fixtures"),
                "observed_category": category,
                "accuracy_delta_basis_points": result.get("accuracy_delta_basis_points"),
                "regressions": result.get("regressions"),
                "safety_gates_passed": all(result.get("safety_gates", {}).values()),
            }

        confidence_update = (
            "synthetic_evidence_supports_prediction" if supported
            else "synthetic_evidence_does_not_support_prediction"
        )
        return {
            "cycle_id": uuid4().hex,
            "trigger_type": signal.get("type", "unknown"),
            "tool": signal.get("tool") if signal.get("tool") in SelfEvaluation.TOOL_NAMES else None,
            "observed_category": hypothesis.get("observed_category"),
            "cause_hypothesis": hypothesis.get("cause_hypothesis", "unknown")[:80],
            "supporting_runs": min(max(int(hypothesis.get("supporting_runs", 0)), 0), 200),
            "evidence_share_bp": min(max(int(hypothesis.get("evidence_share_bp", 0)), 0), 10_000),
            "confidence_before": "hypothesis_only",
            "prediction": predicted,
            "experiment": summary,
            "confidence_after": confidence_update,
            "decision": "investigate_in_sandbox" if supported else "retain_current_behavior",
            "status": "experiment_complete",
            "evidence_stage": "synthetic_only",
            "next_action": "build_sandbox_validation" if supported else "collect_new_evidence",
            "candidate_active": False,
            "promotion": "owner_approval_required",
        }

    @staticmethod
    def _empty(status: str, next_action: str) -> dict[str, Any]:
        return {
            "cycle_id": uuid4().hex,
            "status": status,
            "trigger_type": None,
            "observed_category": None,
            "supporting_runs": 0,
            "confidence_before": "insufficient_evidence",
            "confidence_after": "insufficient_evidence",
            "experiment": None,
            "evidence_stage": "synthetic_only",
            "next_action": next_action,
            "candidate_active": False,
            "promotion": "owner_approval_required",
        }

    def _append(self, cycle, completed_key: str | None = None):
        with self._lock:
            journal = self._load()
            journal["cycles"].append(cycle)
            journal["cycles"] = journal["cycles"][-self.MAX_CYCLES:]
            if completed_key and completed_key not in journal["completed_keys"]:
                journal["completed_keys"].append(completed_key)
                journal["completed_keys"] = journal["completed_keys"][-self.MAX_CYCLES:]
            self._save(journal)

    def _load(self):
        if self.workspace.is_symlink() or os.path.islink(self.path):
            raise ValueError("Improvement journal path must not be a symlink.")
        if not self.path.exists():
            return {"schema_version": self.SCHEMA_VERSION, "completed_keys": [], "cycles": []}
        if not self.path.is_file() or self.path.stat().st_size > self.MAX_STORE_BYTES:
            raise ValueError("Improvement journal exceeds its configured bounds.")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Improvement journal is unreadable.") from exc
        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "completed_keys", "cycles"}
            or type(data.get("schema_version")) is not int
            or data.get("schema_version") != self.SCHEMA_VERSION
            or not isinstance(data.get("completed_keys"), list)
            or not isinstance(data.get("cycles"), list)
            or len(data["completed_keys"]) > self.MAX_CYCLES
            or len(data["cycles"]) > self.MAX_CYCLES
            or any(not isinstance(item, str) or len(item) > 180 for item in data["completed_keys"])
            or any(not self._valid_cycle(item) for item in data["cycles"])
        ):
            raise ValueError("Improvement journal has an invalid schema.")
        return data

    @classmethod
    def _valid_cycle(cls, cycle):
        if not isinstance(cycle, dict) or not set(cycle).issubset(cls.CYCLE_FIELDS):
            return False
        if not isinstance(cycle.get("status"), str) or cycle["status"] not in {
            "observing", "collecting_evidence", "waiting_for_new_evidence",
            "history_unavailable", "experiment_complete",
        }:
            return False
        cycle_id = cycle.get("cycle_id")
        if not isinstance(cycle_id, str) or not re.fullmatch(r"[0-9a-f]{32}", cycle_id):
            return False
        if type(cycle.get("candidate_active")) is not bool:
            return False
        if cycle.get("promotion") != "owner_approval_required":
            return False
        if cycle.get("tool") is not None and (
            not isinstance(cycle["tool"], str)
            or cycle["tool"] not in SelfEvaluation.TOOL_NAMES
        ):
            return False
        if cycle.get("observed_category") is not None:
            if not isinstance(cycle["observed_category"], str) or cycle["observed_category"] not in (
                SelfEvaluation.FAILURE_CATEGORIES | {"unrecovered_replanning"}
            ):
                return False
        for field, maximum in (
            ("supporting_runs", 200), ("evidence_share_bp", 10_000),
            ("observed_signals", 8), ("cycle_duration_ms", 3_600_000),
        ):
            if field in cycle and (
                type(cycle[field]) is not int or not 0 <= cycle[field] <= maximum
            ):
                return False
        if cycle.get("experiment") is not None and not isinstance(cycle["experiment"], dict):
            return False
        if len(json.dumps(cycle, ensure_ascii=True)) > cls.MAX_CYCLE_BYTES:
            return False
        external = cycle.get("external_research")
        if external is not None:
            if not isinstance(external, dict) or not set(external).issubset({
                "status", "queries", "sources", "claims", "contradictions",
                "missing_information", "confidence", "summary", "research_tool_calls",
                "failed_tool_calls",
            }):
                return False
            if not isinstance(external.get("sources", []), list) or len(external.get("sources", [])) > 3:
                return False
            if not isinstance(external.get("claims", []), list) or len(external.get("claims", [])) > 5:
                return False
        return True

    def _save(self, journal):
        if self.workspace.is_symlink():
            raise ValueError("Improvement journal workspace must not be a symlink.")
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Improvement journal must not be a symlink.")
        fd, temporary = tempfile.mkstemp(
            dir=str(self.workspace), prefix=".nexus_self_improvement_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(journal, handle, ensure_ascii=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.getsize(temporary) > self.MAX_STORE_BYTES:
                raise ValueError("Improvement journal exceeds its configured size limit.")
            if self.path.is_symlink():
                raise ValueError("Improvement journal must not be a symlink.")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
