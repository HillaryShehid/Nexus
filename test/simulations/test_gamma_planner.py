import json
from src.core import NexusCore

def test_complete_plan_act_verify_retry_flow(mocker):
    brain = mocker.MagicMock()
    mocker.patch("src.core.AIBrain", return_value=brain)
    initial_plan = {"plan":[{"step":1,"tool":"calculator","args":{"expression":"1 / 0"},"description":"Attempt math fraction"}]}
    repaired_task = {"step":1,"tool":"calculator","args":{"expression":"4 + 4"},"description":"Attempt math fraction"}
    brain.generate.side_effect = [
        {"success":True,"content":json.dumps(initial_plan),"error":None},
        {"success":True,"content":"Division by zero root cause.","error":None},
        {"success":True,"content":json.dumps(repaired_task),"error":None},
        {"success":True,"content":"Final synthesis response.","error":None},
    ]
    nexus = NexusCore()
    result = nexus.handle_request("Solve this query.")
    assert result == "Final synthesis response."
    assert len(nexus.research_canvas) == 1
    assert nexus.research_canvas[0]["status"] == "SUCCESS"
    assert nexus.research_canvas[0]["detail"] == "8"
