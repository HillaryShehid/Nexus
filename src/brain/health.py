from __future__ import annotations

import ast
import os
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
        "src/brain/identity.py",
        "src/brain/capabilities.py",
        "src/brain/executive.py",
        "src/brain/self_improvement.py",
    )

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

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
