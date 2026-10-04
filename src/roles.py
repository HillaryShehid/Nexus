"""Specialized Nexus roles sharing one intelligence and world state."""
from dataclasses import dataclass
from enum import Enum


class NexusRole(str, Enum):
    BUSINESS = "business"
    RESEARCHER = "researcher"
    BUILDER = "builder"


@dataclass(frozen=True)
class RoleProfile:
    role: NexusRole
    responsibilities: tuple[str, ...]
    allowed_entity_types: tuple[str, ...]


ROLE_PROFILES = {
    NexusRole.BUSINESS: RoleProfile(
        NexusRole.BUSINESS,
        ("sales", "calls", "follow-ups", "client communication", "payments", "workflow routing"),
        ("business", "contact", "lead", "call", "payment", "workflow"),
    ),
    NexusRole.RESEARCHER: RoleProfile(
        NexusRole.RESEARCHER,
        ("evidence gathering", "company research", "website assessment", "fact/assumption separation"),
        ("business", "contact", "lead", "research"),
    ),
    NexusRole.BUILDER: RoleProfile(
        NexusRole.BUILDER,
        ("website planning", "coding", "testing", "preview", "approval handoff"),
        ("business", "research", "website_project", "workflow"),
    ),
}


class RoleRouter:
    """Routes work to specialized roles without creating separate AI brains."""

    @staticmethod
    def for_event(event_type: str) -> NexusRole:
        if event_type.startswith(("call.", "email.", "payment.")):
            return NexusRole.BUSINESS
        if event_type.startswith("research."):
            return NexusRole.RESEARCHER
        if event_type.startswith(("project.", "website.")):
            return NexusRole.BUILDER
        return NexusRole.BUSINESS

    @staticmethod
    def profile(role: NexusRole) -> RoleProfile:
        return ROLE_PROFILES[role]
