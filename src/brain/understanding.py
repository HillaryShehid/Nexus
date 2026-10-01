"""Deprecated compatibility adapter for the active executive brief."""

import warnings

from src.brain.executive import ExecutiveController
from src.brain.router import ReasoningRouter


class UnderstandingEngine:
    """Compatibility wrapper; ExecutiveController owns request understanding."""

    _FIELDS = (
        "goal",
        "intent",
        "constraints",
        "known_facts",
        "missing_information",
        "assumptions",
        "needs_action",
    )

    def __init__(self, model):
        warnings.warn(
            "UnderstandingEngine is deprecated; use ExecutiveController.brief().",
            DeprecationWarning,
            stacklevel=2,
        )
        self._executive = ExecutiveController(model)
        self._router = ReasoningRouter()

    def analyze(self, request: str, memory: str, lessons: str) -> dict:
        """Return the legacy understanding shape from the canonical executive."""
        brief = self._executive.brief(
            request,
            memory,
            lessons,
            self._router.route(request),
        )
        return {field: brief[field] for field in self._FIELDS}
