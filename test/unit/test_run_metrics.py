from src.brain.brain import NexusBrain


def make_brain(clearance="allowed", tool_result=None, verification=True, raises=False):
    class Permissions:
        def evaluate_clearance(self, *_args):
            return {"status": clearance, "reason": "policy blocked"}

    class Tools:
        def execute(self, *_args):
            if raises:
                raise RuntimeError("do not persist this error")
            return tool_result or {"success": True}

    class Verifier:
        def verify_step_result(self, *_args):
            return {"verified": verification, "reason": "result mismatch"}

    brain = NexusBrain.__new__(NexusBrain)
    brain.permissions = Permissions()
    brain.tools = Tools()
    brain.verifier = Verifier()
    return brain


TASK = {"step": 1, "tool": "calculator", "args": {"expression": "1+1"}}


def test_permission_block_is_not_counted_as_a_tool_attempt():
    result = make_brain(clearance="blocked")._execute_verified(TASK)

    assert result["failure_category"] == "permission_block"
    assert result["tool_attempted"] is False


def test_tool_runtime_and_verification_failures_have_distinct_categories():
    runtime = make_brain(raises=True)._execute_verified(TASK)
    verification = make_brain(verification=False)._execute_verified(TASK)
    external = make_brain(
        tool_result={"success": False, "error": "Network Error: host unavailable"},
        verification=False,
    )._execute_verified(TASK)
    safety = make_brain(
        tool_result={"success": False, "error": "Security Block: internal target refused"},
        verification=False,
    )._execute_verified(TASK)

    assert runtime["failure_category"] == "tool_runtime"
    assert runtime["tool_attempted"] is True
    assert verification["failure_category"] == "verification_failure"
    assert verification["tool_attempted"] is True
    assert external["failure_category"] == "external_dependency"
    assert safety["failure_category"] == "tool_safety_block"


def test_verified_action_counts_as_post_replan_retry_and_recovery():
    metrics = {
        "tool_attempts": 0,
        "retry_attempts": 0,
        "retry_pending": True,
        "replans": 1,
        "recovery_success": None,
    }

    NexusBrain._record_action_metrics(metrics, {
        "tool_attempted": False, "verified": False,
    })
    NexusBrain._record_action_metrics(metrics, {
        "tool_attempted": True, "verified": True,
    })

    assert metrics["tool_attempts"] == 1
    assert metrics["retry_attempts"] == 1
    assert metrics["recovery_success"] is True
    assert metrics["retry_pending"] is False
