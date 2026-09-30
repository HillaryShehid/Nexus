import json
from datetime import datetime, timezone

class CognitiveMemory:
    """Structured memory facade over the existing memory_store tool."""
    def __init__(self, tools): self.tools=tools
    def read_context(self):
        # Conversation turns are working data, not persistent memory. Do not
        # automatically replay an old chat_context record into future prompts.
        return "No persisted conversation context is loaded."

    def read_fact(self,key):
        r=self.tools.execute("memory_store",{"action":"read","key":key[:40]})
        return str(r.get("result",""))[:1500]
    def save_fact(self,key,value):
        r=self.tools.execute("memory_store",{"action":"save","key":key[:40],"value":value[:1500]})
        return r.get("success") is True
    def remember(self,category,value):
        payload=json.dumps({"value":str(value)[:1200],"updated_at":datetime.now(timezone.utc).isoformat()},ensure_ascii=False)
        return self.save_fact(f"nexus_{category}",payload)
    def recall(self,category):
        return self.read_fact(f"nexus_{category}")
