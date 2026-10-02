import logging

from src.access import Authorization, Role
from src.registry import SHARED_REGISTRY

logger = logging.getLogger("nexus.permissions")


class PermissionSystem:
    """Deterministic tool-policy gate with optional user/role authorization."""

    def __init__(self, authorization=None):
        self.authorization = authorization or Authorization()

    def evaluate_clearance(self, tool_name: str, args: dict, actor_id=None) -> dict:
        spec = SHARED_REGISTRY.get(tool_name)
        if spec is None:
            return {"status": "blocked", "reason": "Unknown tool."}

        if not isinstance(args, dict):
            return {"status": "blocked", "reason": "Invalid argument structure."}

        if actor_id is not None:
            actor = self.authorization.get_user(actor_id)
            if actor is None or not actor.active:
                return {"status": "blocked", "reason": "Unknown or inactive user."}
            if not self.authorization.can(actor_id, tool_name):
                return {"status": "blocked", "reason": "User role is not authorized for this action."}

        allowed_actions = spec["limits"].get("action")
        if allowed_actions is not None and "action" in args and args["action"] not in allowed_actions:
            return {"status": "blocked", "reason": "Requested action is not permitted."}

        policy = spec["policy"]
        if policy in {"READ", "LOW_RISK"}:
            return {"status": "allowed", "reason": "Policy permits automatic execution."}

        if tool_name == "file_system" and args.get("action") == "read":
            return {"status": "allowed", "reason": "Filesystem reads are non-destructive."}

        if policy in {"ELEVATION_REQUIRED", "UNTRUSTED_RUNNER"}:
            return {"status": "approval_required", "reason": "This action requires explicit owner approval."}

        return {"status": "blocked", "reason": "Unknown permission policy; fail closed."}

    def request_user_clearance(self, tool_name: str, args: dict) -> bool:
        print(f"\\n🔐 Nexus wants permission to run: {tool_name}")
        print(f"Arguments: {args}")
        try:
            answer = input("Allow this action? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    def describe_user(self, actor_id):
        return self.authorization.describe(actor_id)
