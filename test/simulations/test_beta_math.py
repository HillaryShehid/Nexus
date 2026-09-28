def test_division_by_zero_is_handled(real_tools):
    result = real_tools.execute("calculator", {"expression": "5 / (10 - 10)"})
    assert result["success"] is False
    assert "Division by zero" in result["error"]

def test_exponent_explosion_is_blocked(real_tools):
    result = real_tools.execute("calculator", {"expression": "999 ** 999"})
    assert result["success"] is False
    assert "boundaries exceeded" in result["error"]

def test_chained_overflow_is_blocked(real_tools):
    result = real_tools.execute("calculator", {"expression": "100000000 * 100000000 * 100000000"})
    assert result["success"] is False
    assert "overflow" in result["error"]

def test_negative_and_addition_work(real_tools):
    result = real_tools.execute("calculator", {"expression": "-5 + 8"})
    assert result["success"] is True
    assert result["result"] == "3"

def test_code_is_not_executable_through_calculator(real_tools):
    result = real_tools.execute("calculator", {"expression": "__import__('os')"})
    assert result["success"] is False
