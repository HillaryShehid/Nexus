"""Event-driven autonomy layer for Nexus.

This layer turns durable world events into resumable Nexus work. It deliberately
does not bypass permissions or perform consequential actions itself.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from src.events import EventStore


class AutonomyEngine:
    """Reconciles important events into bounded, resumable tasks."""

    INTERESTED_OUTCOMES = frozenset({"interested", "yes", "follow_up"})
    SOLD_OUTCOMES = frozenset({"sold", "won", "closed_won"})

    def __init__(self, events: EventStore, tasks, notifier=None):
        self.events = events
        self.tasks = tasks
        self.notifier = notifier

    def reconcile(self, limit: int = 50) -> dict[str, Any]:
        processed = 0
        created = []
        failed = []

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

        return {
            "processed": processed,
            "tasks_created": len(created),
            "tasks": created,
            "failed": failed,
        }

    def _handle_event(self, event: dict[str, Any]):
        event_type = event.get("type", "")
        payload = event.get("payload") or {}

        if event_type == "call.outcome.changed":
            outcome = str(payload.get("outcome", "")).lower()
            company = str(payload.get("company_name") or "the company")
            if outcome in self.INTERESTED_OUTCOMES:
                return self.tasks.create(
                    f"Research {company} and prepare the client website opportunity.",
                    priority="high",
                    created_by="nexus.autonomy",
                )
            if outcome in self.SOLD_OUTCOMES:
                return self.tasks.create(
                    f"Research {company}, prepare the website project, and queue it for Nexus Builder.",
                    priority="high",
                    created_by="nexus.autonomy",
                )
            return None

        if event_type == "email.received":
            subject = str(payload.get("subject") or "(no subject)")
            sender = str(payload.get("sender") or "unknown sender")
            return self.tasks.create(
                f"Review incoming email from {sender}: {subject}",
                priority="high",
                created_by="nexus.autonomy",
            )

        if event_type == "payment.changed":
            company = str(payload.get("company_name") or "the client")
            return self.tasks.create(
                f"Review payment state for {company} and determine the next authorized action.",
                priority="high",
                created_by="nexus.autonomy",
            )

        if event_type == "project.approval.requested":
            project = str(payload.get("project_name") or "the website project")
            task = self.tasks.create(
                f"Review approval request for {project}.",
                priority="high",
                created_by="nexus.autonomy",
                requires_approval=True,
            )
            return self.tasks.update(task["id"], "waiting_for_approval")

        return self.tasks.create(
            f"Review Nexus event: {event_type}",
            priority="normal",
            created_by="nexus.autonomy",
        )


class AutonomyScheduler:
    """Optional background reconciler for the 15-minute Nexus check."""

    def __init__(self, engine: AutonomyEngine, interval_seconds: int = 900,
                 on_error: Callable[[Exception], None] | None = None):
        self.engine = engine
        self.interval_seconds = max(30, int(interval_seconds))
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="nexus-autonomy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.engine.reconcile()
            except Exception as exc:
                if self.on_error:
                    self.on_error(exc)
            self._stop.wait(self.interval_seconds)
