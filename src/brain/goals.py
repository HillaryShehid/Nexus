import json
class GoalManager:
    def __init__(self, model): self.model=model
    def progress_summary(self,state,success_criteria=None):
        return json.dumps({"goal":state.goal,"success_criteria":success_criteria or [],"world":state.world,"completed_steps":state.completed_steps[-8:],"failures":state.failures[-5:],"status":state.status},ensure_ascii=False)[:7000]
    def is_complete(self,state,success_criteria=None,profile="normal"):
        if not state.goal or not state.completed_steps: return False
        response=self.model.generate("Decide whether the observable goal is satisfied by verified evidence. Reply ONLY COMPLETE or INCOMPLETE.",self.progress_summary(state,success_criteria),profile=profile)
        return response.get("success") is True and response.get("content","").strip().upper()=="COMPLETE"
