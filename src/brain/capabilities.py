from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityProfile:
    name: str
    capabilities: tuple[str, ...]
    behaviors: tuple[str, ...]


class NexusCapabilityStack:
    """Concrete capability map inspired by fictional AI archetypes.

    This module describes capabilities; permissions, verification, and the
    protected Nexus foundation remain authoritative elsewhere.
    """

    profiles = (
        CapabilityProfile(
            "Astra",
            (
                "adaptive_reasoning",
                "curiosity",
                "hypothesis_generation",
                "memory_consolidation",
                "uncertainty_tracking",
            ),
            (
                "form competing hypotheses",
                "seek missing evidence",
                "update conclusions when evidence changes",
            ),
        ),
        CapabilityProfile(
            "JARVIS",
            (
                "executive_orchestration",
                "task_prioritization",
                "status_reporting",
                "proactive_housekeeping",
                "schedule_awareness",
            ),
            (
                "keep the owner informed",
                "organize multi-step work",
                "surface useful next actions without taking unauthorized actions",
            ),
        ),
        CapabilityProfile(
            "FRIDAY",
            (
                "fast_context_switching",
                "situational_awareness",
                "concise_updates",
                "rapid_triage",
                "context_preservation",
            ),
            (
                "respond quickly on simple tasks",
                "retain relevant context between steps",
                "switch between tasks without losing state",
            ),
        ),
        CapabilityProfile(
            "Ultron",
            (
                "systems_thinking",
                "long_horizon_planning",
                "self_diagnostics",
                "failure_recovery",
                "goal_persistence",
            ),
            (
                "decompose large objectives",
                "monitor system health",
                "recover from bounded failures",
                "continue pursuing authorized goals",
            ),
        ),
        CapabilityProfile(
            "Claude Mythos",
            (
                "deep_research",
                "long_context_synthesis",
                "adversarial_analysis",
                "evidence_cross_checking",
                "scientific_reasoning",
            ),
            (
                "compare competing explanations",
                "cross-check important claims",
                "separate evidence from assumptions",
                "handle large bodies of context",
            ),
        ),
    )

    def system_instructions(self) -> str:
        lines = [
            "Nexus uses five complementary capability layers.",
            "Astra: reason adaptively, explore hypotheses, track uncertainty, and consolidate lessons.",
            "JARVIS: orchestrate tasks, prioritize work, maintain concise status, and proactively surface useful actions.",
            "FRIDAY: provide fast situational awareness, rapid triage, context preservation, and concise updates.",
            "Ultron: use systems thinking, long-horizon planning, diagnostics, bounded recovery, and persistence toward authorized goals.",
            "Claude Mythos: perform deep research, synthesize large contexts, cross-check evidence, and challenge weak assumptions.",
            "Combine the layers instead of role-playing separate characters.",
            "Use deterministic permissions and verification as hard boundaries.",
            "Never invent tool results, grant yourself permissions, bypass safeguards, or modify the protected foundation.",
        ]
        return " ".join(lines)

    def capability_map(self) -> dict[str, list[str]]:
        return {
            profile.name: list(profile.capabilities)
            for profile in self.profiles
        }

    def select(self, request: str) -> dict[str, Any]:
        text = str(request or "").lower()
        selected = {"FRIDAY"}

        if any(x in text for x in ("research", "investigate", "compare", "sources", "study")):
            selected.add("Claude Mythos")
        if any(x in text for x in ("plan", "build", "project", "organize", "schedule")):
            selected.add("JARVIS")
        if any(x in text for x in ("why", "figure out", "solve", "learn", "understand")):
            selected.add("Astra")
        if any(x in text for x in ("system", "architecture", "debug", "recover", "long term")):
            selected.add("Ultron")

        return {
            "active_layers": [p.name for p in self.profiles if p.name in selected],
            "capabilities": [
                capability
                for p in self.profiles
                if p.name in selected
                for capability in p.capabilities
            ],
        }
