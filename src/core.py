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

logger = logging.getLogger("nexus.core")
MAX_USER_INPUT = 8000


class NexusCore:
    """Application shell for the Nexus brain and persistent task system."""

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
