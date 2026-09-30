"""Bounded, privacy-preserving measurement of Nexus task outcomes."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

from src.brain.experiments import SelfImprovementExperiments
from src.registry import SHARED_REGISTRY, WORKSPACE_DIR


class SelfEvaluation:
    """Measure reported outcomes and surface recurrence signals, never edit code."""

    SCHEMA_VERSION = 2
    MAX_RECORDS = 200
    MAX_STORE_BYTES = 1_000_000
    ANALYSIS_WINDOW = 50
    MIN_FAILURE_RUNS = 3
    MAX_WEAKNESS_SIGNALS = 8
    MAX_VERIFIED_STEPS = 8
    MAX_REPORTED_FAILURES = 5
    MAX_ACTIONS = 8
    MAX_REPLANS = 2
    MAX_DURATION_MS = 86_400_000
    OUTCOMES = frozenset({"success", "failure", "partial_success", "blocked", "unknown"})
    FAILURE_CATEGORIES = frozenset({
        "planner_validation", "input_validation", "permission_block",
        "external_dependency", "tool_safety_block", "tool_runtime",
        "verification_failure", "duplicate_plan", "unknown",
    })
    SAFE_STATUSES = frozenset({
        "ready", "acting", "progress", "complete", "partial", "budget_exhausted",
        "stopped", "recovering", "failed", "test_failed", "blocked", "unknown",
    })
    TOOL_NAMES = frozenset(SHARED_REGISTRY)
    ROOT_CAUSE_BY_CATEGORY = SelfImprovementExperiments.CAUSE_BY_CATEGORY
    ADDITIONAL_POSSIBLE_CAUSES = frozenset({"missing_information"})
    _lock = threading.RLock()

    def __init__(self, workspace: str | None = None):
        requested_workspace = Path(workspace or WORKSPACE_DIR).absolute()
        if requested_workspace.is_symlink():
            raise ValueError("Performance workspace must not be a symlink.")
        self.workspace = requested_workspace.resolve()
        self.path = self.workspace / "nexus_performance.json"

    @staticmethod
    def _is_permission_failure(error: str) -> bool:
        text = error.lower()
        return "permission" in text or "approval" in text

    @classmethod
    def _permission_block(cls, failure: dict[str, Any]) -> bool:
        # The active runner supplies only this boolean. The error fallback is
        # retained for small direct callers and tests; it is never persisted.
        if failure.get("permission_block") is True:
            return True
        category = failure.get("category")
        if isinstance(category, str) and category in cls.FAILURE_CATEGORIES:
            return category == "permission_block"
        return cls._is_permission_failure(str(failure.get("error", ""))[:400])

    @classmethod
    def assess(cls, result: Any) -> dict[str, Any]:
        """Derive metrics only from fields Nexus actually reports."""
        if not isinstance(result, dict):
            result = {}

        status = result.get("status")
        if not isinstance(status, str) or status not in cls.SAFE_STATUSES:
            status = "unknown"

        completed = result.get("completed_steps")
        if type(result.get("verified_steps")) is int:
            verified_steps = min(max(0, result["verified_steps"]), cls.MAX_VERIFIED_STEPS)
        else:
            completed = completed if isinstance(completed, list) else []
            verified_steps = min(
                sum(isinstance(step, dict) for step in completed),
                cls.MAX_VERIFIED_STEPS,
            )

        failures = result.get("failures")
        failures = [item for item in failures if isinstance(item, dict)] if isinstance(failures, list) else []
        failures = failures[: cls.MAX_REPORTED_FAILURES]
        failure_events: list[dict[str, str | None]] = []
        failure_tools: list[str] = []
        for item in failures:
            tool = item.get("tool")
            if not isinstance(tool, str) or tool not in cls.TOOL_NAMES:
                tool = None
            permission_block = cls._permission_block(item)
            category = item.get("category")
            if permission_block:
                category = "permission_block"
            elif not isinstance(category, str) or category not in cls.FAILURE_CATEGORIES or category == "permission_block":
                category = "unknown"
            failure_events.append({"tool": tool, "category": category})
            if tool is not None and category not in {"permission_block", "tool_safety_block"}:
                failure_tools.append(tool)
        blocked = [event for event in failure_events if event["category"] == "permission_block"]
        safety_blocks = [event for event in failure_events if event["category"] == "tool_safety_block"]

        if status == "complete" and verified_steps > 0:
            outcome = "success"
        elif verified_steps > 0:
            outcome = "partial_success"
        elif status == "blocked" or (
            failures and len(blocked) + len(safety_blocks) == len(failures)
        ):
            outcome = "blocked"
        elif status == "budget_exhausted":
            outcome = "blocked"
        elif failures or status in {"failed", "test_failed"}:
            outcome = "failure"
        else:
            outcome = "unknown"

        goal_achieved = True if outcome == "success" else (
            False if outcome in {"failure", "partial_success", "blocked"} else None
        )

        tool_attempts = cls._optional_count(result.get("tool_attempts"), cls.MAX_ACTIONS)
        retry_attempts = cls._optional_count(result.get("retry_attempts"), cls.MAX_ACTIONS)
        if tool_attempts is not None and retry_attempts is not None:
            retry_attempts = min(retry_attempts, tool_attempts)
        replans = cls._optional_count(result.get("replans"), cls.MAX_REPLANS)
        duration_ms = cls._optional_count(result.get("duration_ms"), cls.MAX_DURATION_MS)
        recovery_success = result.get("recovery_success")
        if type(recovery_success) is not bool:
            recovery_success = None
        verification_rate_bp = None
        tool_failure_rate_bp = None
        if tool_attempts:
            verification_rate_bp = min(10_000, verified_steps * 10_000 // tool_attempts)
            tool_failures = sum(
                event["category"] in {"tool_runtime", "external_dependency"}
                for event in failure_events
            )
            tool_failure_rate_bp = min(10_000, tool_failures * 10_000 // tool_attempts)

        return {
            "outcome": outcome,
            "status": status,
            "goal_achieved": goal_achieved,
            "verified_steps": verified_steps,
            "reported_failures": len(failures),
            "permission_blocks": len(blocked),
            "safety_blocks": len(safety_blocks),
            "failure_tools": failure_tools,
            "failure_events": failure_events,
            "tool_attempts": tool_attempts,
            "retry_attempts": retry_attempts,
            "replans": replans,
            "recovery_success": recovery_success,
            "verification_rate_bp": verification_rate_bp,
            "tool_failure_rate_bp": tool_failure_rate_bp,
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _optional_count(value: Any, maximum: int) -> int | None:
        if type(value) is not int:
            return None
        return min(max(0, value), maximum)

    def record(self, result: Any) -> dict[str, Any]:
        assessment = self.assess(result)
        record = {
            "record_id": uuid4().hex,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **assessment,
        }

        with self._lock:
            records = self._load()
            records.append(record)
            records = records[-self.MAX_RECORDS :]
            signals = self._detect_weaknesses(records)
            self._save(records)

        return {
            **record,
            "history_recorded": True,
            "weakness_signals": signals,
            "proposals": [self._proposal(signal) for signal in signals],
            "root_cause_hypotheses": self._root_cause_hypotheses(records),
        }

    def report(self) -> dict[str, Any]:
        """Return bounded history and deterministic recurrence proposals."""
        with self._lock:
            records = self._load()
        signals = self._detect_weaknesses(records)
        return {
            "records": records,
            "weakness_signals": signals,
            "proposals": [self._proposal(signal) for signal in signals],
            "root_cause_hypotheses": self._root_cause_hypotheses(records),
        }

    def _load(self) -> list[dict[str, Any]]:
        if self.workspace.is_symlink():
            raise ValueError("Performance workspace must not be a symlink.")
        if self.path.is_symlink():
            raise ValueError("Performance store must not be a symlink.")
        if not self.path.exists():
            return []
        if not self.path.is_file() or self.path.stat().st_size > self.MAX_STORE_BYTES:
            raise ValueError("Performance store is not a bounded regular file.")

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Performance store is unreadable or invalid JSON.") from exc

        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "records"}
            or type(data.get("schema_version")) is not int
            or data["schema_version"] not in {1, self.SCHEMA_VERSION}
            or not isinstance(data.get("records"), list)
            or len(data["records"]) > self.MAX_RECORDS
        ):
            raise ValueError("Performance store has an invalid schema.")
        if data["schema_version"] == 1:
            records = []
            for record in data["records"]:
                if not self._valid_v1_record(record):
                    raise ValueError("Performance store contains an invalid legacy record.")
                records.append(self._migrate_v1_record(record))
            return records
        for record in data["records"]:
            if not self._valid_record(record):
                raise ValueError("Performance store contains an invalid record.")
        return data["records"]

    @classmethod
    def _valid_v1_record(cls, record: Any) -> bool:
        required = {
            "record_id", "recorded_at", "outcome", "status", "goal_achieved",
            "verified_steps", "reported_failures", "permission_blocks", "failure_tools",
        }
        if not isinstance(record, dict) or set(record) != required:
            return False
        if not isinstance(record["record_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", record["record_id"]):
            return False
        if not isinstance(record["recorded_at"], str) or len(record["recorded_at"]) > 64:
            return False
        try:
            datetime.fromisoformat(record["recorded_at"])
        except ValueError:
            return False
        if not isinstance(record["outcome"], str) or record["outcome"] not in cls.OUTCOMES:
            return False
        if not isinstance(record["status"], str) or record["status"] not in cls.SAFE_STATUSES:
            return False
        if record["goal_achieved"] is not None and type(record["goal_achieved"]) is not bool:
            return False
        for field, maximum in (
            ("verified_steps", cls.MAX_VERIFIED_STEPS),
            ("reported_failures", cls.MAX_REPORTED_FAILURES),
            ("permission_blocks", cls.MAX_REPORTED_FAILURES),
        ):
            if type(record[field]) is not int or not 0 <= record[field] <= maximum:
                return False
        tools = record["failure_tools"]
        return (
            isinstance(tools, list)
            and len(tools) <= cls.MAX_REPORTED_FAILURES
            and all(isinstance(tool, str) and tool in cls.TOOL_NAMES for tool in tools)
        )

    @classmethod
    def _migrate_v1_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        return {
            **record,
            "failure_events": [
                {"tool": tool, "category": "unknown"}
                for tool in record["failure_tools"]
            ],
            "safety_blocks": 0,
            "tool_attempts": None,
            "retry_attempts": None,
            "replans": None,
            "recovery_success": None,
            "verification_rate_bp": None,
            "tool_failure_rate_bp": None,
            "duration_ms": None,
        }

    @classmethod
    def _valid_record(cls, record: Any) -> bool:
        required = {
            "record_id", "recorded_at", "outcome", "status", "goal_achieved",
            "verified_steps", "reported_failures", "permission_blocks", "failure_tools",
            "failure_events", "tool_attempts", "retry_attempts", "replans",
            "recovery_success", "verification_rate_bp", "tool_failure_rate_bp", "duration_ms",
            "safety_blocks",
        }
        if not isinstance(record, dict) or set(record) != required:
            return False
        if not isinstance(record["record_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", record["record_id"]):
            return False
        if not isinstance(record["recorded_at"], str) or len(record["recorded_at"]) > 64:
            return False
        try:
            datetime.fromisoformat(record["recorded_at"])
        except ValueError:
            return False
        if not isinstance(record["outcome"], str) or record["outcome"] not in cls.OUTCOMES:
            return False
        if not isinstance(record["status"], str) or record["status"] not in cls.SAFE_STATUSES:
            return False
        if record["goal_achieved"] is not None and type(record["goal_achieved"]) is not bool:
            return False
        for field, maximum in (
            ("verified_steps", cls.MAX_VERIFIED_STEPS),
            ("reported_failures", cls.MAX_REPORTED_FAILURES),
            ("permission_blocks", cls.MAX_REPORTED_FAILURES),
            ("safety_blocks", cls.MAX_REPORTED_FAILURES),
        ):
            if type(record[field]) is not int or not 0 <= record[field] <= maximum:
                return False
        tools = record["failure_tools"]
        if not (
            isinstance(tools, list)
            and len(tools) <= cls.MAX_REPORTED_FAILURES
            and all(isinstance(tool, str) and tool in cls.TOOL_NAMES for tool in tools)
        ):
            return False
        events = record["failure_events"]
        if not isinstance(events, list) or len(events) > cls.MAX_REPORTED_FAILURES:
            return False
        for event in events:
            if (
                not isinstance(event, dict)
                or set(event) != {"tool", "category"}
                or (
                    event["tool"] is not None
                    and (not isinstance(event["tool"], str) or event["tool"] not in cls.TOOL_NAMES)
                )
                or not isinstance(event["category"], str)
                or event["category"] not in cls.FAILURE_CATEGORIES
            ):
                return False
        for field, maximum in (
            ("tool_attempts", cls.MAX_ACTIONS),
            ("retry_attempts", cls.MAX_ACTIONS),
            ("replans", cls.MAX_REPLANS),
            ("verification_rate_bp", 10_000),
            ("tool_failure_rate_bp", 10_000),
            ("duration_ms", cls.MAX_DURATION_MS),
        ):
            value = record[field]
            if value is not None and (type(value) is not int or not 0 <= value <= maximum):
                return False
        recovery = record["recovery_success"]
        return recovery is None or type(recovery) is bool

    @classmethod
    def _root_cause_hypotheses(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank evidence-supported diagnostic hypotheses without asserting cause."""
        by_tool: dict[str, dict[str, dict[str, set[str] | int]]] = {}
        for record in records[-cls.ANALYSIS_WINDOW :]:
            for event in record.get("failure_events", []):
                tool = event.get("tool") or "unattributed"
                category = event.get("category", "unknown")
                bucket = by_tool.setdefault(tool, {}).setdefault(
                    category, {"runs": set(), "events": 0}
                )
                bucket["runs"].add(record["record_id"])
                bucket["events"] += 1

        analyses = []
        for tool, categories in sorted(
            by_tool.items(), key=lambda item: (-sum(v["events"] for v in item[1].values()), item[0])
        )[: cls.MAX_WEAKNESS_SIGNALS]:
            total_events = sum(value["events"] for value in categories.values())
            hypotheses = []
            for category, value in categories.items():
                hypotheses.append({
                    "cause_hypothesis": cls.ROOT_CAUSE_BY_CATEGORY[category],
                    "observed_category": category,
                    "supporting_runs": len(value["runs"]),
                    "supporting_events": value["events"],
                    "evidence_share_bp": value["events"] * 10_000 // max(total_events, 1),
                    "confidence": "hypothesis_only",
                })
            hypotheses.sort(
                key=lambda item: (-item["supporting_events"], item["observed_category"])
            )
            supported_causes = {item["cause_hypothesis"] for item in hypotheses}
            alternatives = sorted(
                (
                    set(cls.ROOT_CAUSE_BY_CATEGORY.values())
                    | set(cls.ADDITIONAL_POSSIBLE_CAUSES)
                ) - supported_causes
            )
            analyses.append({
                "tool": tool,
                "observed_failure_events": total_events,
                "hypotheses": hypotheses,
                "possible_causes_without_support": alternatives,
                "expected": "a permitted action yields a result that passes verification",
                "observed": [item["observed_category"] for item in hypotheses],
                "missing_information": [
                    "task-specific success criteria are not stored in performance history",
                    "sanitized categories do not include detailed planner, tool, or verifier evidence",
                ],
                "conclusion": "No root cause established; investigate the leading hypothesis before proposing a change.",
            })
        return analyses

    def _save(self, records: list[dict[str, Any]]) -> None:
        if self.workspace.is_symlink():
            raise ValueError("Performance workspace must not be a symlink.")
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.workspace.is_symlink():
            raise ValueError("Performance workspace must not be a symlink.")
        if self.path.is_symlink():
            raise ValueError("Performance store must not be a symlink.")
        fd, temporary = tempfile.mkstemp(
            dir=str(self.workspace), prefix=".nexus_performance_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {"schema_version": self.SCHEMA_VERSION, "records": records},
                    handle,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.getsize(temporary) > self.MAX_STORE_BYTES:
                raise ValueError("Performance store exceeds the configured size limit.")
            if self.path.is_symlink():
                raise ValueError("Performance store must not be a symlink.")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def _detect_weaknesses(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recent = records[-cls.ANALYSIS_WINDOW :]
        run_ids_by_tool: dict[str, set[str]] = {}
        failures_by_tool: dict[str, int] = {}
        for record in recent:
            for tool in set(record["failure_tools"]):
                run_ids_by_tool.setdefault(tool, set()).add(record["record_id"])
                failures_by_tool[tool] = failures_by_tool.get(tool, 0) + record["failure_tools"].count(tool)

        signals = [
            {
                "type": "repeated_tool_failure",
                "tool": tool,
                "distinct_runs": len(run_ids),
                "failure_events": failures_by_tool[tool],
                "window_runs": len(recent),
                "threshold": cls.MIN_FAILURE_RUNS,
            }
            for tool, run_ids in run_ids_by_tool.items()
            if len(run_ids) >= cls.MIN_FAILURE_RUNS
        ]
        signals.sort(key=lambda item: (-item["distinct_runs"], item["tool"]))
        return signals[: cls.MAX_WEAKNESS_SIGNALS]

    @staticmethod
    def _proposal(signal: dict[str, Any]) -> dict[str, Any]:
        tool = signal["tool"]
        return {
            "problem": f"Repeated failures have been observed for tool '{tool}'.",
            "evidence": {
                "distinct_runs": signal["distinct_runs"],
                "failure_events": signal["failure_events"],
                "analysis_window_runs": signal["window_runs"],
                "required_distinct_runs": signal["threshold"],
            },
            "suspected_cause": "Unknown; recurrence counts alone do not establish a root cause.",
            "proposed_improvement": (
                "Inspect the tool contract, sanitized failure categories, and verification path; "
                "propose a change only after confirming the cause."
            ),
            "expected_benefit": "Reduce recurring failures without expanding tool permissions.",
            "potential_risks": [
                "The repeated cases may not share one root cause.",
                "Changing a shared tool contract can regress other tasks.",
            ],
            "affected_components": [f"tool:{tool}", "planner validation", "verification"],
            "required_tests": [
                f"Targeted unit and adversarial tests for {tool}.",
                "Permission and verification regression tests.",
                "Full Python regression suite.",
            ],
            "rollback_strategy": (
                "Keep any candidate staged outside the live source tree; discard it on any failed "
                "safety or regression check and require owner approval before promotion."
            ),
            "status": "proposal_only",
        }
