from src.notifications import NotificationCenter
from src.personal_runtime import Notification, NotificationPriority


def test_queue_overflow_does_not_evict_critical_notification():
    center = NotificationCenter(max_pending=2)
    center.push(Notification("critical", "must keep", NotificationPriority.CRITICAL))
    center.push(Notification("normal", "older normal", NotificationPriority.NORMAL))
    center.push(Notification("low", "new low", NotificationPriority.LOW))

    pending_titles = [item.title for item in center.pending()]

    assert pending_titles == ["critical", "normal"]


def test_queue_overflow_evicts_oldest_notification_at_lowest_priority():
    center = NotificationCenter(max_pending=2)
    center.push(Notification("normal-1", "first", NotificationPriority.NORMAL))
    center.push(Notification("normal-2", "second", NotificationPriority.NORMAL))
    center.push(Notification("high", "important", NotificationPriority.HIGH))

    pending_titles = [item.title for item in center.pending()]

    assert pending_titles == ["normal-2", "high"]
    assert center.next().title == "high"


def test_invalid_notification_is_rejected():
    center = NotificationCenter(max_pending=1)

    try:
        center.push(object())
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError for invalid notification")
