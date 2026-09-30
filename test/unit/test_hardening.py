import os
from pathlib import Path

from src.brain.executor import ParallelActionExecutor
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
