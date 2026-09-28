import json

class GoalManager:
    """Tracks objective progress without exposing private chain-of-thought."""

    def __init__(self, model):
        self.model = model

    def progress_summary(self, state) -> str:
        return json.dumps({
            "goal": state.goal,
            "completed_steps": state.completed_steps[-8:],
            "failures": state.failures[-5:],
            "status": state.status,
        }, ensure_ascii=False)[:6000]

    def is_complete(self, state) -> bool:
        if not state.goal or not state.completed_steps:
            return False
        response = self.model.generate(
            "Decide if the stated goal is satisfied by the verified evidence. Reply ONLY COMPLETE or INCOMPLETE.",
            self.progress_summary(state),
        )
        return response.get("success") is True and response.get("content", "").strip() == "COMPLETE"
