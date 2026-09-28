import json, os
from src.registry import WORKSPACE_DIR
from src.verification import VerificationSystem

def test_code_tester_requires_structured_success(real_tools, mock_brain):
    verifier = VerificationSystem(mock_brain, real_tools)
    task = {"tool":"code_tester","args":{"python_code":"print('Success')"},"description":"Run test"}
    assert verifier.verify_step_result(task, {"success":True,"result":"Success","error":None})["verified"] is False
    real = real_tools.execute("code_tester", {"python_code":"print('Success')"})
    assert real["success"] is True
    assert verifier.verify_step_result(task, real)["verified"] is True

def test_file_write_verification_requires_exact_content(real_tools, mock_brain):
    verifier = VerificationSystem(mock_brain, real_tools)
    real_tools.execute("file_system", {"action":"write","path":"x.txt","content":"hello"})
    task = {"tool":"file_system","args":{"action":"write","path":"x.txt","content":"hello"},"description":"Write file"}
    result = {"success":True,"result":"written","error":None}
    assert verifier.verify_step_result(task, result)["verified"] is True
    with open(os.path.join(WORKSPACE_DIR,"x.txt"),"a",encoding="utf-8") as handle: handle.write("EXTRA")
    assert verifier.verify_step_result(task, result)["verified"] is False

def test_read_page_structure_is_checked(real_tools, mock_brain):
    verifier = VerificationSystem(mock_brain, real_tools)
    task = {"tool":"read_page","args":{"url":"https://example.com"},"description":"Read page"}
    malformed = {"success":True,"result":json.dumps({"origin":"x","resolved_ip":"8.8.8.8","body":123}),"error":None}
    assert verifier.verify_step_result(task, malformed)["verified"] is False
