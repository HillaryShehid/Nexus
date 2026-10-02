"""Personal Nexus identity and authorization.
Nexus is personal-first right now: one owner identity.
"""
from dataclasses import dataclass
from enum import Enum

class Role(str, Enum):
    OWNER = "owner"

@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: Role = Role.OWNER
    active: bool = True

DEFAULT_USERS = {"hilal": User("hilal", "Hilal")}

class Authorization:
    """Single source of truth for Nexus identity and high-impact actions."""
    def __init__(self, users=None):
        self.users = dict(users or DEFAULT_USERS)

    def get_user(self, user_id):
        return self.users.get(str(user_id))

    def require(self, user_id, minimum_role=Role.OWNER):
        user = self.get_user(user_id)
        return bool(user and user.active and user.role is Role(minimum_role))

    def can(self, user_id, action):
        user = self.get_user(user_id)
        if user is None or not user.active:
            return False
        if str(action) in {"spend_money", "change_permissions", "self_modify_foundation", "approve_high_impact"}:
            return user.role is Role.OWNER
        return True

    def describe(self, user_id):
        user = self.get_user(user_id)
        if user is None:
            return {"authenticated": False, "user_id": str(user_id)}
        return {"authenticated": user.active, "user_id": user.id, "name": user.name, "role": user.role.value}
