from __future__ import annotations

import ast
import re
from pathlib import Path


class NexusHealth:
    """Fast structural health checks for the Nexus foundation."""

    REQUIRED_FILES = (
        "run.py",
        "src/core.py",
        "src/model.py",
        "src/registry.py",
        "src/tools.py",
        "src/planner.py",
        "src/permissions.py",
        "src/verification.py",
        "src/learning.py",
        "src/brain/brain.py",
        "src/brain/adaptation.py",
        "src/brain/executor.py",
        "src/brain/goals.py",
        "src/brain/memory.py",
        "src/brain/router.py",
        "src/brain/state.py",
        "src/brain/task_manager.py",
        "src/brain/world_model.py",
        "src/brain/identity.py",
        "src/brain/capabilities.py",
        "src/brain/executive.py",
        "src/brain/self_evaluation.py",
        "src/brain/self_improvement_loop.py",
        "src/brain/research.py",
        "src/brain/experiments.py",
        "src/brain/self_improvement.py",
    )

    def __init__(self, project_root: str | None = None):
        default_root = Path(__file__).resolve().parents[2]
        self.root = Path(project_root).resolve() if project_root else default_root

    def run(self) -> dict:
        issues: list[str] = []

        for relative in self.REQUIRED_FILES:
            path = self.root / relative
            if not path.is_file():
                issues.append(f"missing:{relative}")
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError):
                issues.append(f"syntax:{relative}")

        try:
            from src.registry import SHARED_REGISTRY
            from src.tools import ToolSystem

            expected = set(SHARED_REGISTRY)
            actual = set(ToolSystem().dispatch_table)
            if expected != actual:
                missing = sorted(expected - actual)
                extra = sorted(actual - expected)
                issues.append(
                    "tool_registry_mismatch:"
                    f"missing_dispatch={missing},extra_dispatch={extra}"
                )
        except Exception as exc:
            issues.append(f"runtime_import:{type(exc).__name__}")

        try:
            from src.brain.capabilities import NexusCapabilityStack
            from src.brain.identity import NexusIdentity

            expected_layers = {
                "JARVIS",
                "FRIDAY",
                "Ultron",
                "Claude Mythos",
                "ChatGPT",
                "ChatGPT Astral",
            }
            actual_layers = set(
                NexusCapabilityStack().select("health")["active_layers"]
            )
            if actual_layers != expected_layers:
                issues.append(
                    "cognitive_layer_mismatch:"
                    f"expected={sorted(expected_layers)},actual={sorted(actual_layers)}"
                )

            identity_text = NexusIdentity().system_prompt()
            if re.search(r"\bAstra\b", identity_text):
                issues.append("stale_cognitive_layer:Astra")
            if identity_text.count("ChatGPT Astral") != 1:
                issues.append("duplicate_or_missing_cognitive_layer:ChatGPT Astral")

            from src.brain.self_improvement import SelfImprovementEngine

            protected = set(SelfImprovementEngine.PROTECTED_PATHS)
            allowed = set(SelfImprovementEngine.DEFAULT_ALLOWLIST)
            overlap = sorted(protected & allowed)
            if overlap:
                issues.append(f"self_improvement_boundary:{overlap}")
        except Exception as exc:
            issues.append(f"self_improvement_import:{type(exc).__name__}")

        return {
            "healthy": not issues,
            "issues": issues,
            "checked_files": len(self.REQUIRED_FILES),
        }
