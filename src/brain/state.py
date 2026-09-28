from dataclasses import dataclass, field
from typing import Any
@dataclass
class CognitiveState:
    request: str
    goal: str=""
    intent: str=""
    constraints: list[str]=field(default_factory=list)
    known_facts: list[str]=field(default_factory=list)
    missing_information: list[str]=field(default_factory=list)
    assumptions: list[str]=field(default_factory=list)
    completed_steps: list[dict[str,Any]]=field(default_factory=list)
    failures: list[dict[str,Any]]=field(default_factory=list)
    lessons: list[dict[str,Any]]=field(default_factory=list)
    plan: list[dict[str,Any]]=field(default_factory=list)
    world: dict[str,Any]=field(default_factory=dict)
    next_action: dict[str,Any]|None=None
    status: str="new"
    def snapshot(self):
        return {"request":self.request,"goal":self.goal,"intent":self.intent,"constraints":self.constraints[-20:],"known_facts":self.known_facts[-20:],"missing_information":self.missing_information[-20:],"assumptions":self.assumptions[-20:],"plan":self.plan[-8:],"world":self.world,"completed_steps":self.completed_steps[-10:],"failures":self.failures[-10:],"lessons":self.lessons[-10:],"status":self.status}
