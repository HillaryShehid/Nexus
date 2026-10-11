"""Structured private activity log for Nexus, with retrieval before future work.

Entries contain operational summaries rather than full transcripts. They are
stored under the configured Nexus workspace and are not shared automatically.
"""
import json
import os
import re
import tempfile
from datetime import datetime, timezone

from src.registry import WORKSPACE_DIR


class AgentDailyLog:
    """Append-only run ledger and lightweight keyword-based lesson retrieval."""

    def __init__(self, log_path=None):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.log_path = os.path.abspath(
            log_path or os.path.join(WORKSPACE_DIR, "nexus_daily_log.jsonl")
        )

    @staticmethod
    def _tokens(text):
        return {
            token for token in re.findall(r"[a-z0-9_]{3,}", str(text).lower())
            if token not in {"the", "and", "for", "with", "that", "this", "from", "into", "have", "will"}
        }

    @staticmethod
    def _safe_steps(steps):
        safe = []
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, dict):
                continue
            safe.append({
                "tool": str(step.get("tool", "unknown"))[:80],
                "description": str(step.get("description", ""))[:240],
                "detail": str(step.get("detail", ""))[:240],
            })
        return safe[-12:]

    @staticmethod
    def _safe_failures(failures):
        safe = []
        for failure in failures if isinstance(failures, list) else []:
            if not isinstance(failure, dict):
                continue
            safe.append({
                "tool": str(failure.get("tool", "unknown"))[:80],
                "category": str(failure.get("category", "unknown"))[:80],
            })
        return safe[-8:]

    def record_run(self, request, status, route, completed_steps=None, failures=None):
        """Record a compact run outcome; do not store the assistant's transcript."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).date().isoformat(),
            "request_summary": str(request or "").strip()[:300],
            "status": str(status or "unknown")[:40],
            "route": str(route or "unknown")[:40],
            "verified_accomplishments": self._safe_steps(completed_steps or []),
            "errors": self._safe_failures(failures or []),
            "lesson_tags": sorted(self._tokens(
                " ".join(
                    [str(request or "")] +
                    [s.get("tool", "") + " " + s.get("description", "") for s in self._safe_steps(completed_steps or [])] +
                    [f.get("tool", "") + " " + f.get("category", "") for f in self._safe_failures(failures or [])]
                )
            ))[:40],
        }
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        # Append one JSON record atomically at the file-handle level.
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"success": True, "date": entry["date"]}

    def _load_recent(self, max_lines=500):
        if not os.path.isfile(self.log_path) or os.path.islink(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()[-max_lines:]
        except (OSError, UnicodeError):
            return []
        entries = []
        for line in lines:
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return entries

    def relevant_context(self, request, limit=5):
        """Return only entries with matching terms, newest first for ties."""
        query_tokens = self._tokens(request)
        if not query_tokens:
            return ""
        scored = []
        for index, entry in enumerate(self._load_recent()):
            haystack = " ".join([
                str(entry.get("request_summary", "")),
                " ".join(entry.get("lesson_tags", [])) if isinstance(entry.get("lesson_tags"), list) else "",
                json.dumps(entry.get("verified_accomplishments", []), ensure_ascii=False),
                json.dumps(entry.get("errors", []), ensure_ascii=False),
            ])
            overlap = len(query_tokens & self._tokens(haystack))
            if overlap:
                scored.append((overlap, index, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = []
        for _, _, entry in scored[:max(1, min(int(limit), 10))]:
            selected.append({
                "date": entry.get("date", ""),
                "status": entry.get("status", ""),
                "route": entry.get("route", ""),
                "verified_accomplishments": entry.get("verified_accomplishments", []),
                "errors": entry.get("errors", []),
                "lesson_tags": entry.get("lesson_tags", []),
            })
        return json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
