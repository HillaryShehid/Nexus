"""Personal Nexus runtime policies and shared interaction contracts.

This module deliberately contains no business/CRM functionality. It provides
the common personal-assistant layer that voice, vision, notifications, approvals,
and future model providers can plug into without creating separate brains.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class VoiceMode(str, Enum):
    SPEAKER = "speaker"
    PRIVATE = "private"
    SILENT = "silent"

class ApprovalRisk(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    action: str
    reason: str
    risk: ApprovalRisk = ApprovalRisk.HIGH
    requires_second_factor: bool = False

@dataclass
class OwnerControl:
    """Deterministic approval state machine."""
    owner_id: str = "owner"
    pending: ApprovalRequest | None = None
    approved_request_id: str | None = None

    def request(self, request: ApprovalRequest) -> ApprovalRequest:
        if not request.request_id or not request.action:
            raise ValueError("Approval requests need an id and action.")
        self.pending = request
        self.approved_request_id = None
        return request

    def respond(self, response: str, request_id: str | None = None) -> bool:
        if self.pending is None:
            return False
        if request_id is not None and request_id != self.pending.request_id:
            return False
        normalized = str(response).strip().lower()
        if normalized not in {"approve", "approved", "yes", "reject", "rejected", "no"}:
            return False
        if normalized in {"approve", "approved", "yes"}:
            self.approved_request_id = self.pending.request_id
            self.pending = None
            return True
        self.pending = None
        self.approved_request_id = None
        return True

    def requires_second_factor(self) -> bool:
        return bool(self.pending and self.pending.requires_second_factor)

@dataclass
class VoiceSession:
    mode: VoiceMode = VoiceMode.SPEAKER
    active: bool = False
    wake_word: str = "hey nexus"
    listening: bool = False

    def activate(self) -> None:
        self.active = True
        self.listening = True

    def deactivate(self) -> None:
        self.active = False
        self.listening = False

    def set_mode(self, mode: VoiceMode | str) -> None:
        self.mode = VoiceMode(mode)
        if self.mode == VoiceMode.SILENT:
            self.listening = False

    def should_output_audio(self) -> bool:
        return self.active and self.mode in {VoiceMode.SPEAKER, VoiceMode.PRIVATE}

@dataclass(frozen=True)
class VisionPolicy:
    enabled: bool = False
    prefer_local_processing: bool = True
    camera_upload_allowed: bool = False
    face_confidence_is_authentication: bool = False
    sensitive_actions_require_second_factor: bool = True

@dataclass
class Notification:
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    actions: list[str] = field(default_factory=list)
    read: bool = False

    def mark_read(self) -> None:
        self.read = True

@dataclass(frozen=True)
class ResourcePolicy:
    """Engineering safeguards, not chat/message quotas."""
    max_concurrent_workers: int = 4
    max_request_chars: int = 32_000
    max_tool_calls_per_run: int = 32
    max_retries_per_action: int = 2

    def validate(self) -> None:
        if min(self.max_concurrent_workers, self.max_request_chars, self.max_tool_calls_per_run) <= 0:
            raise ValueError("Resource limits must be positive.")
        if self.max_retries_per_action < 0:
            raise ValueError("Retry limit cannot be negative.")

@dataclass(frozen=True)
class NexusRole:
    name: str
    purpose: str
    permissions: tuple[str, ...] = ()

@dataclass
class PersonalNexusRuntime:
    """One shared personal Nexus identity with pluggable interfaces."""
    owner_id: str = "owner"
    voice: VoiceSession = field(default_factory=VoiceSession)
    vision: VisionPolicy = field(default_factory=VisionPolicy)
    owner_control: OwnerControl = field(default_factory=OwnerControl)
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    roles: dict[str, NexusRole] = field(default_factory=lambda: {
        "personal": NexusRole(
            "personal",
            "General personal assistance, conversation, planning, research, and authorized tool use.",
        ),
        "research": NexusRole(
            "research",
            "Evidence-based general research and verification.",
            ("research",),
        ),
    })

    def __post_init__(self) -> None:
        self.resources.validate()

    def select_role(self, name: str = "personal") -> NexusRole:
        if name not in self.roles:
            raise ValueError(f"Unknown personal Nexus role: {name}")
        return self.roles[name]

    def status(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "voice_mode": self.voice.mode.value,
            "voice_active": self.voice.active,
            "vision_enabled": self.vision.enabled,
            "pending_approval": self.owner_control.pending.request_id if self.owner_control.pending else None,
            "roles": sorted(self.roles),
            "unlimited_conversations": True,
            "artificial_paywalls": False,
            "resource_safeguards_enabled": True,
        }
