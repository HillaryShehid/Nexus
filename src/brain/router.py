from dataclasses import dataclass

@dataclass(frozen=True)
class Route:
    name: str
    depth: str
    max_actions: int
    profile: str

class ReasoningRouter:
    """Cheap deterministic routing: fast by default, deeper reasoning only when needed."""
    def route(self, request: str) -> Route:
        text = request.lower()
        hard = ("debug","troubleshoot","architect","build","code","program","research","compare","analyze","design","deploy","fix","why")
        deep = ("complex","deeply","step by step","architecture","root cause","investigate","strategy","multiple systems","end to end")
        coding = ("code","program","script","python","javascript","bug","debug","repo","github")
        research = ("research","find sources","investigate","look up","compare","latest")
        multi = ("then","after that","and then","step","multiple","all of","find","create","make","set up","build")
        if any(x in text for x in coding) and any(x in text for x in deep):
            return Route("deep-coding","deep",8,"coding")
        if any(x in text for x in research) and any(x in text for x in deep):
            return Route("deep-research","deep",8,"research")
        if any(x in text for x in deep) or (any(x in text for x in hard) and any(x in text for x in multi)):
            return Route("deep","deep",8,"deep")
        if any(x in text for x in coding):
            return Route("coding","normal",6,"coding")
        if any(x in text for x in research):
            return Route("research","normal",6,"research")
        if any(x in text for x in hard):
            return Route("normal","normal",6,"normal")
        return Route("quick","quick",3,"quick")
