"""Priority-aware notification queue for Personal Nexus."""
from collections import deque
from src.personal_runtime import Notification, NotificationPriority

class NotificationCenter:
    def __init__(self, max_pending: int = 200):
        if max_pending <= 0:
            raise ValueError("max_pending must be positive.")
        self.max_pending = max_pending
        self._queue: deque[Notification] = deque()

    def push(self, notification: Notification) -> None:
        self._queue.append(notification)
        while len(self._queue) > self.max_pending:
            self._queue.popleft()

    def pending(self) -> list[Notification]:
        return [item for item in self._queue if not item.read]

    def next(self) -> Notification | None:
        pending = self.pending()
        if not pending:
            return None
        priority = {
            NotificationPriority.CRITICAL: 4,
            NotificationPriority.HIGH: 3,
            NotificationPriority.NORMAL: 2,
            NotificationPriority.LOW: 1,
        }
        return max(pending, key=lambda item: priority[item.priority])
