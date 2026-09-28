import json

class WorldModel:
    """Run-local world state built only from verified evidence."""

    def __init__(self):
        self.facts = []
        self.artifacts = []
        self.events = []

    def add_verified_step(self, task, result):
        detail = str(result.get("result",""))[:1200]
        record = {"step":task.get("step"),"tool":task.get("tool"),
                  "description":task.get("description","")[:200],"evidence":detail}
        self.events.append(record)
        if detail:
            self.facts.append(detail)
        if task.get("tool") == "file_system" and result.get("success"):
            self.artifacts.append(task.get("args",{}).get("path","")[:200])

    def snapshot(self):
        return {"facts":self.facts[-12:],"artifacts":self.artifacts[-20:],"events":self.events[-12:]}

    def as_prompt(self, limit=5000):
        return json.dumps(self.snapshot(), ensure_ascii=False)[:limit]
