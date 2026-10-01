import json
import logging
import os
import tempfile

from src.registry import WORKSPACE_DIR

logger = logging.getLogger("nexus.learning")


class LearningSystem:
    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.log_path = os.path.abspath(os.path.join(WORKSPACE_DIR, "nexus_lessons.json"))
        self.max_lessons_ceiling = 5

    def _load(self) -> list:
        if not os.path.exists(self.log_path) or os.path.islink(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, list):
                return []

            clean = []
            for item in loaded:
                if not isinstance(item, dict):
                    continue
                required = (
                    "failed_tool",
                    "arguments_used",
                    "observed_error_signature",
                    "diagnosed_breakdown_cause",
                    "operational_remedy",
                )
                if not all(key in item for key in required):
                    continue
                clean.append({
                    "failed_tool": str(item["failed_tool"])[:80],
                    "arguments_used": item["arguments_used"] if isinstance(item["arguments_used"], dict) else {},
                    "observed_error_signature": str(item["observed_error_signature"])[:200],
                    "diagnosed_breakdown_cause": str(item["diagnosed_breakdown_cause"])[:200],
                    "operational_remedy": str(item["operational_remedy"])[:300],
                })
            return clean[-self.max_lessons_ceiling:]
        except (OSError, UnicodeError, json.JSONDecodeError):
            logger.warning("Lessons ledger could not be read; starting with empty lessons.")
            return []

    def record_mistake(self, task: dict, error_log: str, diagnosed_cause: str) -> dict:
        lessons = self._load()
        cause = str(diagnosed_cause)[:200]
        error = str(error_log)[:200]

        remedy_map = {
            "division by zero": "Check denominators before retrying arithmetic.",
            "timeout": "Use bounded retries and avoid unnecessary repeated network work.",
            "exponent": "Reduce power operands to remain inside calculator limits.",
            "path traversal": "Keep filesystem operations inside the configured workspace.",
        }
        remedy = "Review the failed tool arguments and correct the execution strategy before retrying."
        combined = f"{cause} {error}".lower()
        for pattern, candidate in remedy_map.items():
            if pattern in combined:
                remedy = candidate
                break

        safe_args = task.get("args", {}) if isinstance(task, dict) else {}
        if not isinstance(safe_args, dict):
            safe_args = {}
        safe_args = {str(k)[:40]: str(v)[:500] for k, v in list(safe_args.items())[:20]}

        lessons.append({
            "failed_tool": str(task.get("tool", "unknown"))[:80] if isinstance(task, dict) else "unknown",
            "arguments_used": safe_args,
            "observed_error_signature": error,
            "diagnosed_breakdown_cause": cause,
            "operational_remedy": remedy,
        })
        lessons = lessons[-self.max_lessons_ceiling:]

        directory = os.path.dirname(self.log_path)
        os.makedirs(directory, exist_ok=True)
        temp_name = None
        try:
            fd, temp_name = tempfile.mkstemp(dir=directory, prefix=".nexus_lessons_", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(lessons, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.log_path)
            return {"success": True, "error": None}
        except (OSError, TypeError, ValueError) as exc:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
            return {"success": False, "error": f"Learning storage error: {str(exc)[:200]}"}

    def retrieve_lessons(self) -> str:
        lessons = self._load()
        if not lessons:
            return "No historical failures recorded."
        try:
            return json.dumps(lessons, indent=2, ensure_ascii=False)[:5000]
        except (TypeError, ValueError):
            return "No historical failures recorded."