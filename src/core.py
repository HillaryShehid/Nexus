import logging
from src.brain import NexusBrain
from src.learning import LearningSystem
from src.model import AIBrain
from src.permissions import PermissionSystem
from src.planner import Planner
from src.tools import ToolSystem
from src.verification import VerificationSystem
from src.brain.task_manager import TaskManager

logger=logging.getLogger("nexus.core")
MAX_USER_INPUT=1000

class NexusCore:
    """Application shell for the Nexus brain and persistent task system."""
    def __init__(self):
        self.brain_model=AIBrain(); self.tools=ToolSystem()
        self.planner=Planner(self.brain_model)
        self.verifier=VerificationSystem(self.brain_model,self.tools)
        self.learning=LearningSystem(); self.permissions=PermissionSystem()
        self.tasks=TaskManager()
        self.brain=NexusBrain(model=self.brain_model,tools=self.tools,planner=self.planner,
                              verifier=self.verifier,permissions=self.permissions,learning=self.learning)
    def handle_request(self,user_input):
        if not isinstance(user_input,str): return "I need the request as text."
        if len(user_input)>MAX_USER_INPUT: return "System limitation: the prompt is longer than the 1000-character limit."
        if not user_input.strip(): return "Tell me what you want me to do."
        saved=self.tools.execute("memory_store",{"action":"save","key":"chat_context","value":user_input})
        if not saved.get("success"): logger.warning("Could not save chat context: %s",saved.get("error"))
        try: return self.brain.run(user_input)
        except Exception:
            logger.exception("Nexus brain failure; request stopped safely.")
            return "I hit an internal brain error and stopped safely rather than pretending the task was completed."
