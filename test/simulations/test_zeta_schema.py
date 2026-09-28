from src.planner import Planner

def planner(real_tools): return Planner(None)

def valid_task(): return {"step":1,"tool":"calculator","args":{"expression":"2+2"},"description":"Calculate value"}

def test_bool_step_is_rejected():
    task=valid_task(); task["step"]=True
    assert planner(None).validate_task_schema(task, expected_step_index=1)["valid"] is False

def test_empty_required_argument_is_rejected():
    task=valid_task(); task["args"]["expression"]=""
    assert planner(None).validate_task_schema(task, expected_step_index=1)["valid"] is False

def test_unknown_argument_is_rejected():
    task=valid_task(); task["args"]["evil"]="x"
    assert planner(None).validate_task_schema(task, expected_step_index=1)["valid"] is False

def test_wrong_step_number_is_rejected():
    task=valid_task(); task["step"]=2
    assert planner(None).validate_task_schema(task, expected_step_index=1)["valid"] is False

def test_unknown_tool_is_rejected():
    task=valid_task(); task["tool"]="shell"
    assert planner(None).validate_task_schema(task, expected_step_index=1)["valid"] is False
