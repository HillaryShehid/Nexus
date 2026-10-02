"""Identity and authorization primitives for Nexus.

This module is intentionally independent from the tool registry so every
interface can enforce the same actor/permission policy.
"""
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    WORKER = "worker"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: Role
    active: bool = True


DEFAULT_USERS = {
    "hilal": User("hilal", "Hilal", Role.OWNER),
    "hamza": User("hamza", "Hamza", Role.WORKER),
    "talha": User("talha", "Talha", Role.WORKER),
    "zachariah": User("zachariah", "Zachariah", Role.WORKER),
    "mustafa": User("mustafa", "Mustafa", Role.WORKER),
}


class Authorization:
    """Central policy gate. Individual tools should not invent role rules."""

    ROLE_ORDER = {Role.WORKER: 10, Role.ADMIN: 20, Role.OWNER: 30}

    def __init__(self, users=None):
        self.users = dict(users or DEFAULT_USERS)

    def get_user(self, user_id):
        return self.users.get(str(user_id))

    def require(self, user_id, minimum_role=Role.WORKER):
        user = self.get_user(user_id)
        if user is None or not user.active:
            return False
        return self.ROLE_ORDER[user.role] >= self.ROLE_ORDER[Role(minimum_role)]

    def can(self, user_id, action):
        user = self.get_user(user_id)
        if user is None or not user.active:
            return False
        action = str(action)
        if action in {"deploy_website", "purchase_domain", "spend_money", "change_permissions"}:
            return user.role is Role.OWNER
        if action in {"manage_team", "manage_settings"}:
            return user.role in {Role.ADMIN, Role.OWNER}
        return True

    def describe(self, user_id):
        user = self.get_user(user_id)
        if user is None:
            return {"authenticated": False, "user_id": str(user_id)}
        return {
            "authenticated": user.active,
            "user_id": user.id,
            "name": user.name,
            "role": user.role.value,
        }
