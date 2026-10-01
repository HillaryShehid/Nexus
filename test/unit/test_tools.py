import json
import os
import sys
import types
import pytest

def test_workspace_write_and_read(real_tools):
    write=real_tools.execute("file_system",{"action":"write","path":"notes.txt","content":"hello Nexus"})
    assert write["success"] is True
    read=real_tools.execute("file_system",{"action":"read","path":"notes.txt"})
    assert read["success"] is True
    assert read["result"] == "hello Nexus"

def test_workspace_traversal_is_blocked(real_tools):
    result=real_tools.execute("file_system",{"action":"write","path":"../escape.txt","content":"nope"})
    assert result["success"] is False
    assert "Security Block" in result["error"]

def test_memory_round_trip(real_tools):
    save=real_tools.execute("memory_store",{"action":"save","key":"name","value":"Nexus"})
    assert save["success"] is True
    read=real_tools.execute("memory_store",{"action":"read","key":"name"})
    assert read["success"] is True
    assert read["result"] == "Nexus"

def test_code_runner_success(real_tools):
    result=real_tools.execute("code_tester",{"python_code":"print('hello')"})
    assert result["success"] is True


def test_web_search_uses_ddgs_auto_backend_and_returns_structured_results(real_tools, monkeypatch):
    calls = {}

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def text(self, query, *, max_results, backend):
            calls.update(query=query, max_results=max_results, backend=backend)
            return [{"title": "Official docs", "href": "https://docs.example.test", "body": "Relevant documentation."}]

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=FakeDDGS))
    result = real_tools.execute("web_search", {"query": "package official documentation"})

    assert result["success"] is True
    assert calls == {"query": "package official documentation", "max_results": 3, "backend": "auto"}
    assert json.loads(result["result"]) == {
        "query": "package official documentation",
        "results": [{"title": "Official docs", "url": "https://docs.example.test", "snippet": "Relevant documentation."}],
    }


def test_web_search_reports_empty_provider_results_as_failure(real_tools, monkeypatch):
    class EmptyDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def text(self, _query, *, max_results, backend):
            return []

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=EmptyDDGS))
    result = real_tools.execute("web_search", {"query": "missing results"})

    assert result == {
        "success": False,
        "result": "",
        "error": "Search Provider Error: No search results were returned.",
    }


def test_memory_store_rejects_symlink_without_reading_or_overwriting_target(real_tools):
    target = os.path.join(real_tools.workspace_root, "other_memory.json")
    original = {"conversations": [], "facts": {"secret": "outside"}}
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(original, handle)
    try:
        os.symlink(target, real_tools.memory_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform.")

    read = real_tools.execute("memory_store", {"action": "read", "key": "secret"})
    assert read["result"] != "outside"
    saved = real_tools.execute("memory_store", {"action": "save", "key": "safe", "value": "local"})
    assert saved["success"] is True
    assert not os.path.islink(real_tools.memory_file)
    with open(target, "r", encoding="utf-8") as handle:
        assert json.load(handle) == original
