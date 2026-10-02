from src.personal_runtime import (
    ApprovalRequest,
    ApprovalRisk,
    OwnerControl,
    PersonalNexusRuntime,
    VoiceMode,
)
from src.voice_interface import VoiceController
from src.vision_interface import VisionController, VisionObservation
from src.notifications import NotificationCenter
from src.personal_runtime import Notification, NotificationPriority


def test_approval_targets_current_request_only():
    control = OwnerControl()
    control.request(ApprovalRequest("a", "publish", "approved site", ApprovalRisk.HIGH))
    assert control.respond("approve", request_id="wrong") is False
    assert control.pending is not None
    assert control.respond("approve", request_id="a") is True
    assert control.pending is None
    assert control.approved_request_id == "a"


def test_private_voice_routes_to_headphones():
    controller = VoiceController()
    controller.set_mode(VoiceMode.PRIVATE)
    controller.begin_listening()
    assert controller.route_response("hello").kind == "airpods"


def test_silent_voice_routes_visual_only():
    controller = VoiceController()
    controller.set_mode(VoiceMode.SILENT)
    assert controller.route_response("hello").kind == "visual_only"


def test_vision_never_authenticates_sensitive_actions():
    result = VisionController().inspect(VisionObservation(True, 0.99))
    assert result["status"] == "disabled"
    result = VisionController(
        policy=__import__("src.personal_runtime", fromlist=["VisionPolicy"]).VisionPolicy(enabled=True)
    ).inspect(VisionObservation(True, 0.99))
    assert result["authentication"] is False
    assert result["sensitive_action_requires_second_factor"] is True


def test_notifications_prioritize_critical():
    center = NotificationCenter()
    center.push(Notification("normal", "n"))
    center.push(Notification("critical", "c", NotificationPriority.CRITICAL))
    assert center.next().title == "critical"


def test_personal_runtime_has_no_business_roles():
    runtime = PersonalNexusRuntime()
    assert sorted(runtime.roles) == ["personal", "research"]
    assert runtime.status()["unlimited_conversations"] is True
