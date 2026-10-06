"""Public identity contract for the Nexus owner.

This is intentionally limited to non-sensitive project identity so a shared
clone of Nexus understands who created and owns the system. Personal/private
memory belongs in the configured memory store, not in source control.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class NexusOwnerIdentity:
    name: str = "Hilal"
    role: str = "creator and owner"
    relationship: str = "primary user and authority of Nexus"
    project: str = "Nexus / Nexus Core"
    personal_nexus_private: bool = True
    shared_nexus_core: bool = True

    @property
    def summary(self) -> str:
        return (
            f"{self.name} is the {self.role} of {self.project}. "
            f"{self.name} is Nexus's {self.relationship}. "
            "Personal Nexus memory must remain private from team members, "
            "while the shared Nexus Core intelligence can be shown and "
            "used by authorized team accounts."
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_OWNER = NexusOwnerIdentity()
