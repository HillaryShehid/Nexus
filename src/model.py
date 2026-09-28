import logging
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("nexus.model")

class AIBrain:
    """Model gateway with profile routing and safe fallback to NEXUS_MODEL."""
    def __init__(self):
        self.default_model = os.getenv("NEXUS_MODEL")
        if not self.default_model:
            raise ValueError("CRITICAL INITIALIZATION ERROR: 'NEXUS_MODEL' is missing.")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL INITIALIZATION ERROR: 'OPENAI_API_KEY' is missing.")
        self.client = OpenAI(api_key=api_key)
        self.models = {p: os.getenv(f"NEXUS_{p.upper()}_MODEL", self.default_model)
                       for p in ("quick","normal","deep","coding","research")}

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False, profile: str = "normal") -> dict:
        if not isinstance(system_prompt,str) or not isinstance(user_prompt,str):
            return {"success":False,"content":"","error":"Model input must be text."}
        selected = self.models.get(profile,self.default_model)
        try:
            kwargs={"model":selected,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],"temperature":0.1}
            if json_mode:
                kwargs["response_format"]={"type":"json_object"}
            response=self.client.chat.completions.create(**kwargs)
            choices=getattr(response,"choices",None)
            if not choices:
                return {"success":False,"content":"","error":"Model Provider Error: Empty response."}
            content=getattr(choices[0].message,"content",None)
            if not isinstance(content,str) or not content.strip():
                return {"success":False,"content":"","error":"Model Provider Error: Empty output."}
            return {"success":True,"content":content,"error":None,"model":selected,"profile":profile}
        except Exception:
            logger.exception("Provider communication failure.")
            return {"success":False,"content":"","error":"Internal Error: AI inference could not be completed safely."}
