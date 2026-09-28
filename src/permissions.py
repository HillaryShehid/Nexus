from src.registry import SHARED_REGISTRY


class PermissionSystem:
    def evaluate_clearance(self, tool_name: str, args: dict) -> dict:
        if tool_name not in SHARED_REGISTRY:
            return {"status": "blocked", "reason": "Access denied: unmapped tool."}
        if not isinstance(args, dict):
            return {"status": "blocked", "reason": "Access denied: invalid argument structure."}

        spec = SHARED_REGISTRY[tool_name]
        action_limits = spec["limits"].get("action")
        if action_limits is not None and "action" in args and args["action"] not in action_limits:
            return {"status": "blocked", "reason": "Access denied: invalid action."}

        policy = spec["policy"]
        if policy in {"READ", "LOW_RISK"}:
            return {"status": "allowed", "reason": "Allowed by policy."}
        if policy == "ELEVATION_REQUIRED":
            if args.get("action") == "write":
                return {"status": "approval_required", "reason": f"Authorization required to write '{args.get('path', '')}'."}
            return {"status": "allowed", "reason": "Read-only filesystem access allowed."}
        if policy == "UNTRUSTED_RUNNER":
            return {"status": "approval_required", "reason": "Authorization required to execute untrusted code."}

        return {"status": "blocked", "reason": "Access denied: unknown security policy."}

    def request_user_clearance(self, tool_name: str, args: dict) -> bool:
        print("\n🔐 [NEXUS GATE] Authorization required.")
        print(f"Tool: {tool_name} -> {args}")
        try:
            consent = input("Authorize this action? (y/n): ").strip().lower()
            return consent == "y"
        except (EOFError, KeyboardInterrupt):
            return False