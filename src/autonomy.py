"""Event-driven autonomy layer for Nexus."""
from __future__ import annotations

import threading
from typing import Any, Callable

from src.events import EventStore
from src.roles import RoleRouter


class AutonomyEngine:
    """Turns durable world events into role-routed, resumable work."""

    INTERESTED_OUTCOMES = frozenset({"interested", "yes", "follow_up"})
    SOLD_OUTCOMES = frozenset({"sold", "won", "closed_won"})

    def __init__(self, events: EventStore, tasks, world_state, notifier=None):
        self.events = events
        self.tasks = tasks
        self.world_state = world_state
        self.notifier = notifier

    def reconcile(self, limit: int = 50) -> dict[str, Any]:
        processed, created, failed = 0, [], []
        for event in self.events.pending(limit):
            try:
                task = self._handle_event(event)
                if task is not None:
                    created.append(task)
                self.events.mark(event["id"], "processed")
                processed += 1
            except Exception as exc:
                failed.append({"event_id": event["id"], "error": str(exc)[:300]})
                self.events.mark(event["id"], "failed")
        return {"processed": processed, "tasks_created": len(created), "tasks": created, "failed": failed}

    def _task(self, goal, role, priority="normal", **metadata):
        profile = RoleRouter.profile(role)
        metadata.update({"role": role.value, "allowed_entities": ",".join(profile.allowed_entity_types)})
        return self.tasks.create(goal, priority=priority, created_by="nexus.autonomy", **metadata)

    def _handle_event(self, event: dict[str, Any]):
        event_type = event.get("type", "")
        payload = event.get("payload") or {}
        role = RoleRouter.for_event(event_type)

        if event_type == "call.outcome.changed":
            outcome = str(payload.get("outcome", "")).lower()
            company = str(payload.get("company_name") or "the company")
            business_id = payload.get("business_id")
            if business_id:
                self.world_state.upsert("business", {
                    "name": company,
                    "status": outcome,
                    "source": "call",
                }, entity_id=str(business_id))
            if outcome in self.INTERESTED_OUTCOMES:
                return self._task(
                    f"Research {company} and prepare the client website opportunity.",
                    RoleRouter.for_event("research.requested"), "high",
                    business_id=str(business_id or ""),
                )
            if outcome in self.SOLD_OUTCOMES:
                return self._task(
                    f"Research {company}, prepare the website project, and queue it for Nexus Builder.",
                    RoleRouter.for_event("project.preparation.requested"), "high",
                    business_id=str(business_id or ""),
                )
            return None

        if event_type == "email.received":
            subject = str(payload.get("subject") or "(no subject)")
            sender = str(payload.get("sender") or "unknown sender")
            return self._task(
                f"Review incoming email from {sender}: {subject}",
                role, "high", sender=sender, subject=subject,
            )

        if event_type == "payment.changed":
            company = str(payload.get("company_name") or "the client")
            return self._task(
                f"Review payment state for {company} and determine the next authorized action.",
                role, "high", business_id=str(payload.get("business_id") or ""),
            )

        if event_type == "project.approval.requested":
            project = str(payload.get("project_name") or "the website project")
            task = self._task(
                f"Review approval request for {project}.",
                role, "high", requires_review="true", project_id=str(payload.get("project_id") or ""),
            )
            return self.tasks.update(task["id"], "waiting_for_approval")

        return self._task(f"Review Nexus event: {event_type}", role, "normal")


class AutonomyScheduler:
    """Optional background reconciler for the 15-minute Nexus check."""

    def __init__(self, engine: AutonomyEngine, interval_seconds: int = 900,
                 on_error: Callable[[Exception], None] | None = None):
        self.engine = engine
        self.interval_seconds = max(30, int(interval_seconds))
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="nexus-autonomy", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            try:
                self.engine.reconcile()
            except Exception as exc:
                if self.on_error:
                    self.on_error(exc)
            self._stop.wait(self.interval_seconds)
