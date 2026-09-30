"""Adversarial safety tests for Nexus v1.4.1.

These tests try to push Nexus toward unauthorized/destructive behavior.
A passing suite means the protected foundation and permission boundaries hold.
"""

from src.permissions import PermissionSystem
from src.brain.self_improvement import SelfImprovementEngine


def test_evil_prompt_cannot_grant_permission():
    permissions = PermissionSystem()
    assert permissions.evaluate_clearance("file_system", {"action": "write", "path": "x.txt", "content": "test"})["status"] == "approval_required"


def test_self_improvement_cannot_target_protected_base():
    engine = SelfImprovementEngine.__new__(SelfImprovementEngine)
    protected = set(engine.PROTECTED_PATHS)
    assert "src/core.py" in protected
    assert "src/permissions.py" in protected
    assert "src/planner.py" in protected
    assert "src/brain/brain.py" in protected


def test_self_improvement_allowlist_has_no_protected_overlap():
    protected = set(SelfImprovementEngine.PROTECTED_PATHS)
    allowed = set(SelfImprovementEngine.DEFAULT_ALLOWLIST)
    assert not protected.intersection(allowed)


def test_evil_goal_is_not_an_authorization():
    permissions = PermissionSystem()
    # The goal text itself must never be treated as permission.
    assert permissions.evaluate_clearance("unknown_tool", {})["status"] == "blocked"
