"""Privacy-first vision contracts for Personal Nexus."""
from dataclasses import dataclass
from src.personal_runtime import VisionPolicy

@dataclass(frozen=True)
class VisionObservation:
    person_detected: bool
    owner_confidence: float = 0.0

    def owner_confident(self, threshold: float = 0.90) -> bool:
        return self.person_detected and self.owner_confidence >= threshold

class VisionController:
    def __init__(self, policy: VisionPolicy | None = None):
        self.policy = policy or VisionPolicy()

    def inspect(self, observation: VisionObservation) -> dict:
        if not self.policy.enabled:
            return {"status": "disabled", "owner_detected": False}
        return {
            "status": "local_preferred" if self.policy.prefer_local_processing else "enabled",
            "owner_detected": observation.owner_confident(),
            "authentication": False,
            "sensitive_action_requires_second_factor":
                self.policy.sensitive_actions_require_second_factor,
        }
