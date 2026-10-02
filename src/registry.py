import os
import types

MAX_PLAN_STEPS = 5
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.join(_PROJECT_ROOT, "nexus_workspace")

_MANIFEST = {
    "web_search": {
        "required_args": ["query"],
        "types": {"query": str},
        "limits": {"query": 80},
        "policy": "READ",
    },
    "read_page": {
        "required_args": ["url"],
        "types": {"url": str},
        "limits": {"url": 200},
        "policy": "READ",
    },
    "calculator": {
        "required_args": ["expression"],
        "types": {"expression": str},
        "limits": {"expression": 100},
        "policy": "LOW_RISK",
    },
    "file_system": {
        "required_args": ["action", "path"],
        "types": {"action": str, "path": str, "content": str},
        "limits": {"action": ["read", "write"], "path": 40, "content": 3000},
        "policy": "ELEVATION_REQUIRED",
    },
    "memory_store": {
        "required_args": ["action", "key"],
        "types": {"action": str, "key": str, "value": str},
        "limits": {"action": ["read", "save", "append_conversation"], "key": 40, "value": 20000},
        "policy": "LOW_RISK",
    },
    "code_tester": {
        "required_args": ["python_code"],
        "types": {"python_code": str},
        "limits": {"python_code": 3000},
        "policy": "UNTRUSTED_RUNNER",
    },
}


def _freeze(value):
    if isinstance(value, dict):
        return types.MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value


SHARED_REGISTRY = _freeze(_MANIFEST)
