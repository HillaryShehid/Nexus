import json
import os
import tempfile
from datetime import datetime, timezone

from src.registry import WORKSPACE_DIR


class TaskManager:
    """Persistent task queue for resumable Nexus work."""

    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.path = os.path.realpath(os.path.join(WORKSPACE_DIR, "nexus_tasks.json"))

    def _load(self):
        if not os.path.exists(self.path) or os.path.islink(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []

    def _save(self, tasks):
        fd, temp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix=".nexus_tasks_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(tasks[-50:], f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

    def create(self, goal, priority="normal"):
        now=datetime.now(timezone.utc).isoformat()
        task={"id":datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
              "goal":str(goal)[:800],
              "priority":priority if priority in {"low","normal","high"} else "normal",
              "status":"queued","created_at":now,"updated_at":now}
        tasks=self._load(); tasks.append(task); self._save(tasks)
        return task

    def update(self, task_id, status, **fields):
        tasks=self._load()
        for task in tasks:
            if task.get("id")==task_id:
                task["status"]=status
                task["updated_at"]=datetime.now(timezone.utc).isoformat()
                task.update({k:str(v)[:2000] for k,v in fields.items()})
                self._save(tasks)
                return task
        return None

    def active(self):
        return [t for t in self._load() if t.get("status") in {"queued","running","waiting"}]
