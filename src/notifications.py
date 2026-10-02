"""Priority-aware notification queue for Personal Nexus."""
from collections import deque
from src.personal_runtime import Notification, NotificationPriority


class NotificationCenter:
    def __init__(self, max_pending: int = 200):
        if max_pending <= 0:
            raise ValueError("max_pending must be positive.")
        self.max_pending = max_pending
        self._queue: deque[Notification] = deque()

    @staticmethod
    def _priority(notification: Notification) -> int:
        return {
            NotificationPriority.CRITICAL: 4,
            NotificationPriority.HIGH: 3,
            NotificationPriority.NORMAL: 2,
            NotificationPriority.LOW: 1,
        }[notification.priority]

    def push(self, notification: Notification) -> None:
        if not isinstance(notification, Notification):
            raise TypeError("notification must be a Notification instance.")

        self._queue.append(notification)

        # When bounded storage is full, discard the oldest notification at the
        # lowest available priority. This prevents a flood of low-priority
        # events from evicting a critical alert.
        while len(self._queue) > self.max_pending:
            lowest_index = min(
                range(len(self._queue)),
                key=lambda index: (self._priority(self._queue[index]), index),
            )
            del self._queue[lowest_index]

    def pending(self) -> list[Notification]:
        return [item for item in self._queue if not item.read]

    def next(self) -> Notification | None:
        pending = self.pending()
        if not pending:
            return None
        return max(pending, key=self._priority)
