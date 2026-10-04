import logging

from src.brain import NexusBrain
from src.brain.health import NexusHealth
from src.brain.task_manager import TaskManager
from src.learning import LearningSystem
from src.model import AIBrain
from src.access import Authorization
from src.permissions import PermissionSystem
from src.planner import Planner
from src.tools import ToolSystem
from src.verification import VerificationSystem
from src.personal_runtime import PersonalNexusRuntime
from src.notifications import NotificationCenter
from src.events import EventStore, NexusEvent
from src.autonomy import AutonomyEngine, AutonomyScheduler

logger = logging.getLogger("nexus.core")
MAX_USER_INPUT = 8000


class NexusCore:
    """Application shell for the Nexus brain, state, events, and task system."""

    def __init__(self, actor_id="hilal"):
        self.brain_model = AIBrain()
        self.tools = ToolSystem()
        self.planner = Planner(self.brain_model)
        self.verifier = VerificationSystem(self.brain_model, self.tools)
        self.learning = LearningSystem()
        self.authorization = Authorization()
        self.permissions = PermissionSystem(self.authorization, actor_id=actor_id)
        self.tasks = TaskManager()
        self.health = NexusHealth()
        self.personal = PersonalNexusRuntime(owner_id=actor_id)
        self.notifications = NotificationCenter()

        # Events are the durable bridge between world changes and autonomous work.
        # They are intentionally independent from the model so important changes
        # can wake Nexus even when nobody sends a chat command.
        self.events = EventStore()
        self.autonomy = AutonomyEngine(
            events=self.events,
            tasks=self.tasks,
            notifier=self.notifications,
        )
        self.autonomy_scheduler = AutonomyScheduler(
            self.autonomy,
            on_error=lambda exc: logger.exception("Nexus autonomy check failed: %s", exc),
        )

        self.brain = NexusBrain(
            model=self.brain_model,
            tools=self.tools,
            planner=self.planner,
            verifier=self.verifier,
            permissions=self.permissions,
            learning=self.learning,
        )

    def health_check(self):
        return self.health.run()

    def improve_nexus(self, objective, relative_paths=None):
        return self.brain.improve(objective, relative_paths)

    def self_improvement_review(self):
        return self.brain.self_improvement_review()

    def authenticate(self, actor_id):
        self.permissions.set_actor(actor_id)
        return self.authorization.describe(actor_id)

    def emit_event(self, event_type, source, payload=None):
        """Record a world change and immediately reconcile autonomous work."""
        event = NexusEvent(
            type=event_type,
            source=source,
            payload=payload or {},
        )
        record = self.events.append(event)
        reconciliation = self.autonomy.reconcile(limit=1)
        return {"event": record, "reconciliation": reconciliation}

    def autonomous_check(self):
        """Run the scheduled-style 'what needs attention?' check now."""
        return self.autonomy.reconcile()

    def start_autonomy(self):
        """Start the optional 15-minute background reconciliation loop."""
        self.autonomy_scheduler.start()

    def stop_autonomy(self):
        """Stop the optional background reconciliation loop."""
        self.autonomy_scheduler.stop()

    def handle_request(self, user_input):
        if not isinstance(user_input, str):
            return "I need the request as text."
        if len(user_input) > MAX_USER_INPUT:
            return (
                "System limitation: the prompt is longer than the "
                f"{MAX_USER_INPUT}-character limit."
            )
        if not user_input.strip():
            return "Tell me what you want me to do."

        try:
            return self.brain.run(user_input)
        except Exception:
            logger.exception("Nexus brain failure; request stopped safely.")
            return (
                "I hit an internal brain error and stopped safely rather than "
                "pretending the task was completed."
            )
