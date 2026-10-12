import logging
import sys

from src.access import Authorization
from src.registry import SHARED_REGISTRY

logger = logging.getLogger("nexus.permissions")


class PermissionSystem:
    """Deterministic tool-policy gate with centralized owner authorization."""

    def __init__(self, authorization=None, actor_id=None):
        self.authorization = authorization or Authorization()
        self.actor_id = None
        self.approval_handler = None
        if actor_id is not None:
            self.set_actor(actor_id)

    def set_actor(self, actor_id):
        if actor_id is None:
            self.actor_id = None
            return
        if self.authorization.get_user(actor_id) is None:
            raise ValueError("Unknown Nexus user.")
        self.actor_id = str(actor_id)

    def evaluate_clearance(self, tool_name: str, args: dict, actor_id=None) -> dict:
        actor_id = self.actor_id if actor_id is None else actor_id
        spec = SHARED_REGISTRY.get(tool_name)
        if spec is None:
            return {"status": "blocked", "reason": "Unknown tool."}
        if not isinstance(args, dict):
            return {"status": "blocked", "reason": "Invalid argument structure."}

        # Reject invalid actions before authentication or approval routing.
        allowed_actions = spec["limits"].get("action")
        if allowed_actions is not None and "action" in args and args["action"] not in allowed_actions:
            return {"status": "blocked", "reason": "Requested action is not permitted."}

        policy = spec["policy"]
        if actor_id is None:
            if policy in {"ELEVATION_REQUIRED", "UNTRUSTED_RUNNER"}:
                return {"status": "approval_required", "authenticated": False, "reason": "Owner authentication is required before approval can be requested."}
            return {"status": "blocked", "reason": "Authenticated owner context is required."}

        actor = self.authorization.get_user(actor_id)
        if actor is None or not actor.active:
            return {"status": "blocked", "reason": "Unknown or inactive user."}

        # Read-only exceptions must be evaluated before the tool's broad policy.
        if tool_name == "email" and args.get("action") in {"read", "search"}:
            return {"status": "allowed", "reason": "Email reads are non-destructive."}
        if tool_name == "file_system" and args.get("action") == "read":
            return {"status": "allowed", "reason": "Filesystem reads are non-destructive."}

        if policy in {"ELEVATION_REQUIRED", "UNTRUSTED_RUNNER"}:
            if not self.authorization.can(actor_id, "approve_high_impact"):
                return {"status": "blocked", "reason": "Owner role is required to approve this action."}
            return {
                "status": "approval_required",
                "authenticated": True,
                "reason": "Owner approval is required for this action.",
            }
        if policy in {"READ", "LOW_RISK"}:
            return {"status": "allowed", "reason": "Policy permits automatic execution."}
        return {"status": "blocked", "reason": "Unknown permission policy; fail closed."}

    def request_user_clearance(self, tool_name: str, args: dict) -> bool:
        if callable(self.approval_handler):
            try:
                return self.approval_handler(tool_name, args) is True
            except Exception:
                logger.exception("Approval handler failed; action denied.")
                return False
        if not getattr(sys.stdin, "isatty", lambda: False)():
            logger.warning("No interactive approval channel is available; action denied.")
            return False
        print(f"\n🔐 Nexus wants permission to run: {tool_name}")
        print(f"Arguments: {args}")
        try:
            answer = input("Allow this action? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    def describe_user(self, actor_id):
        return self.authorization.describe(actor_id)
