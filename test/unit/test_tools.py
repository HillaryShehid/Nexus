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
