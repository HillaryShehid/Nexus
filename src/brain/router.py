from dataclasses import dataclass

@dataclass(frozen=True)
class Route:
    name: str
    depth: str
    max_actions: int

class ReasoningRouter:
    """Cheap deterministic routing so simple requests do not pay deep-reasoning latency."""
    def route(self, request: str) -> Route:
        text = request.lower()
        hard_markers = (
            "debug", "troubleshoot", "architect", "build", "code", "program",
            "research", "compare", "analyze", "design", "deploy", "fix", "why",
        )
        multi_step_markers = (
            "then", "after that", "and then", "step", "multiple", "all of",
            "find", "create", "make", "set up",
        )
        if any(m in text for m in hard_markers) and any(m in text for m in multi_step_markers):
            return Route("deep", "deep", 8)
        if any(m in text for m in hard_markers):
            return Route("normal", "normal", 6)
        return Route("quick", "quick", 3)
