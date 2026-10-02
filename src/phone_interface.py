"""Channel-neutral phone integration contracts for Personal Nexus.

This does not send messages itself; concrete OS/push providers can be attached later.
"""

from dataclasses import dataclass
from src.personal_runtime import Notification


@dataclass(frozen=True)
class PhoneEvent:
    kind: str
    payload: dict


class PhoneInterface:
    def __init__(self):
        self.connected = False

    def connect(self) -> PhoneEvent:
        self.connected = True
        return PhoneEvent("connected", {})

    def disconnect(self) -> PhoneEvent:
        self.connected = False
        return PhoneEvent("disconnected", {})

    def prepare_notification(self, notification: Notification) -> PhoneEvent:
        if not self.connected:
            return PhoneEvent("queued", {"title": notification.title})
        return PhoneEvent(
            "notification",
            {
                "title": notification.title,
                "body": notification.body,
                "priority": notification.priority.value,
                "actions": list(notification.actions),
            },
        )

    def request_second_factor(self, approval_request_id: str) -> PhoneEvent:
        if not approval_request_id:
            raise ValueError("An approval request id is required.")
        return PhoneEvent("second_factor_requested", {"request_id": approval_request_id})
