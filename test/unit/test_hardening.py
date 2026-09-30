import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.brain.executor import ParallelActionExecutor
from src.brain.executive import ExecutiveController
from src.brain.health import NexusHealth
from src.brain.self_improvement import SelfImprovementEngine
from src.registry import WORKSPACE_DIR


def test_workspace_is_repo_anchored():
    assert Path(WORKSPACE_DIR).name == "nexus_workspace"
    assert Path(WORKSPACE_DIR).is_absolute()
    assert Path(WORKSPACE_DIR).parent == Path(__file__).resolve().parents[2]


def test_health_uses_repo_root_by_default():
    health = NexusHealth()
    result = health.run()
    assert result["healthy"] is True, result["issues"]


def test_self_improvement_uses_repo_root_by_default():
    engine = SelfImprovementEngine(model=None)
    assert engine.project_root == Path(__file__).resolve().parents[2]
    assert engine.workspace == Path(WORKSPACE_DIR).resolve()


def test_parallel_executor_preserves_original_order():
    executor = ParallelActionExecutor()
    tasks = [
        {"tool": "calculator", "args": {"expression": "1+1"}},
        {"tool": "calculator", "args": {"expression": "2+2"}},
    ]
    results = executor.run(tasks, lambda task: {"verified": True, "result": task["args"]["expression"]})
    assert [index for index, _ in results] == [0, 1]
    assert [result["result"] for _, result in results] == ["1+1", "2+2"]


def test_parallel_executor_converts_worker_exception_to_failed_result():
    executor = ParallelActionExecutor()
    tasks = [{"tool": "calculator", "args": {"expression": "1+1"}}, {"tool": "calculator", "args": {"expression": "2+2"}}]

    def execute(task):
        if task["args"]["expression"] == "2+2":
            raise RuntimeError("boom")
        return {"verified": True, "result": "ok"}

    results = executor.run(tasks, execute)
    assert results[0][1]["verified"] is True
    assert results[1][1]["verified"] is False
    assert "Parallel execution failed" in results[1][1]["error"]


def test_user_requests_are_not_persisted_as_chat_memory_by_default(mocker):
    from src.core import NexusCore

    model = mocker.MagicMock()
    mocker.patch("src.core.AIBrain", return_value=model)
    nexus = NexusCore()
    mocker.patch.object(nexus.brain, "run", return_value="handled safely")

    response = nexus.handle_request("My private details should stay in this request.")

    assert response == "handled safely"
    stored = nexus.tools.execute("memory_store", {"action": "read", "key": "chat_context"})
    assert stored["success"] is True
    assert stored["result"] == "[]"


def test_persisted_chat_context_is_not_replayed_into_future_prompts(mocker):
    from src.brain.memory import CognitiveMemory

    tools = mocker.MagicMock()
    tools.execute.return_value = {
        "success": True,
        "result": "private historical text",
    }

    context = CognitiveMemory(tools).read_context()

    assert "private historical text" not in context
    tools.execute.assert_not_called()


def test_self_improvement_rejects_symlink_alias_to_protected_file(tmp_path, mocker):
    from src.brain.self_improvement import SelfImprovementEngine

    project = tmp_path / "project"
    workspace = tmp_path / "workspace"
    allowed = project / "src" / "brain" / "router.py"
    protected = project / "src" / "tools.py"
    allowed.parent.mkdir(parents=True)
    protected.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("VALUE = 'live'\n", encoding="utf-8")
    protected.write_text("VALUE = 'protected'\n", encoding="utf-8")

    engine = SelfImprovementEngine(
        model=None,
        project_root=str(project),
        workspace=str(workspace),
        allowlist=("src/brain/router.py",),
    )
    candidate = engine.candidate_root / "src" / "brain" / "router.py"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("VALUE = 'candidate'\n", encoding="utf-8")

    actual_is_symlink = Path.is_symlink
    actual_resolve = Path.resolve

    def pretend_symlink(path):
        return path == allowed or actual_is_symlink(path)

    def resolve_to_protected(path, *args, **kwargs):
        if path == allowed:
            return actual_resolve(protected, *args, **kwargs)
        return actual_resolve(path, *args, **kwargs)

    mocker.patch.object(Path, "is_symlink", pretend_symlink)
    mocker.patch.object(Path, "resolve", resolve_to_protected)

    assert engine._safe_project_path("src/brain/router.py") is None
    result = engine._promote_candidates(("src/brain/router.py",))

    assert result["success"] is False
    assert "symlink" in result["error"]
    assert protected.read_text(encoding="utf-8") == "VALUE = 'protected'\n"


def test_health_detects_stale_astra_layer_name(mocker):
    from src.brain.health import NexusHealth

    mocker.patch(
        "src.brain.identity.NexusIdentity.system_prompt",
        return_value="Nexus includes the Astra layer.",
    )

    result = NexusHealth().run()

    assert "stale_cognitive_layer:Astra" in result["issues"]


def test_parallel_executor_converts_single_worker_exception_to_failed_result():
    executor = ParallelActionExecutor()
    task = {"tool": "calculator", "args": {"expression": "1+1"}}

    results = executor.run([task], lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    assert results[0][0] == 0
    assert results[0][1]["verified"] is False
    assert "Parallel execution failed: RuntimeError" == results[0][1]["error"]


@pytest.mark.parametrize("invalid_value", [0, 1, "false", "", None, [], {}])
def test_executive_falls_back_when_needs_action_is_not_a_json_boolean(mocker, invalid_value):
    model = mocker.MagicMock()
    model.generate.return_value = {
        "success": True,
        "content": json.dumps({"goal": "do something", "needs_action": invalid_value}),
    }
    route = SimpleNamespace(name="quick", depth="quick", profile="quick")

    brief = ExecutiveController(model).brief("Do something", "", "", route)

    assert brief["goal"] == "Do something"
    assert brief["needs_action"] is True


def test_executive_accepts_an_actual_json_false_for_needs_action(mocker):
    model = mocker.MagicMock()
    model.generate.return_value = {
        "success": True,
        "content": '{"goal":"answer directly","needs_action":false}',
    }
    route = SimpleNamespace(name="quick", depth="quick", profile="quick")

    brief = ExecutiveController(model).brief("Answer this", "", "", route)

    assert brief["goal"] == "answer directly"
    assert brief["needs_action"] is False
