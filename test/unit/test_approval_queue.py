import threading
import time

from src.approval_queue import ApprovalQueue


def _wait_for_pending(queue, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pending = queue.list_pending()
        if pending:
            return pending[0]
        time.sleep(0.005)
    raise AssertionError("approval request was not published")


def test_approval_queue_resolves_approved_request():
    queue = ApprovalQueue(timeout_seconds=2)
    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault(
            "approved",
            queue.request_approval("file_system", {"action": "write", "path": "notes.txt"}),
        )
    )
    worker.start()

    pending = _wait_for_pending(queue)
    assert pending["tool"] == "file_system"
    assert pending["args"]["path"] == "notes.txt"
    assert queue.decide(pending["id"], True) is True
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert result["approved"] is True
    assert queue.list_pending() == []


def test_approval_queue_denial_and_expiry_fail_closed():
    queue = ApprovalQueue(timeout_seconds=1)
    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault(
            "approved", queue.request_approval("email", {"action": "send", "to": "client@example.com"})
        )
    )
    worker.start()
    pending = _wait_for_pending(queue)
    assert queue.decide(pending["id"], False) is True
    worker.join(timeout=1)
    assert result["approved"] is False

    assert queue.request_approval("email", {"action": "send"}) is False
    assert queue.list_pending() == []


def test_approval_queue_rejects_malformed_or_stale_decisions():
    queue = ApprovalQueue(timeout_seconds=1)
    assert queue.decide("missing", True) is False
    assert queue.decide("missing", "yes") is False

    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault("approved", queue.request_approval("code_tester", {"python_code": "print(1)"}))
    )
    worker.start()
    pending = _wait_for_pending(queue)
    assert queue.decide(pending["id"], 1) is False
    assert queue.decide(pending["id"], True) is True
    assert queue.decide(pending["id"], False) is False
    worker.join(timeout=1)
    assert result["approved"] is True


def test_approval_queue_shows_full_bounded_python_code():
    queue = ApprovalQueue(timeout_seconds=2)
    code = "x" * 3000
    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault(
            "approved", queue.request_approval("code_tester", {"python_code": code})
        )
    )
    worker.start()
    pending = _wait_for_pending(queue)
    assert pending["args"]["python_code"] == code
    assert queue.decide(pending["id"], False) is True
    worker.join(timeout=1)
    assert result["approved"] is False
