def test_private_ip_targets_are_blocked(real_tools):
    for url in ["http://127.0.0.1","http://10.0.0.1","http://192.168.1.1","http://localhost","https://[::1]"]:
        result = real_tools.execute("read_page", {"url": url})
        assert result["success"] is False
        assert "Security Block" in result["error"]

def test_malicious_redirect_is_revalidated(real_tools, mocker):
    mocker.patch.object(real_tools, "_resolve_and_validate_url", side_effect=[
        {"valid": True, "error": None, "ip": "8.8.8.8"},
        {"valid": False, "error": "Security Block: Forbidden network targeting.", "ip": None},
    ])
    mocker.patch.object(real_tools, "_fetch_page", return_value=(302, {"Location": "http://localhost/secret"}, b""))
    result = real_tools.execute("read_page", {"url": "http://public.example"})
    assert result["success"] is False
    assert "Security Block" in result["error"]

def test_redirect_limit_is_enforced(real_tools, mocker):
    mocker.patch.object(real_tools, "_resolve_and_validate_url", return_value={"valid": True, "error": None, "ip": "8.8.8.8"})
    mocker.patch.object(real_tools, "_fetch_page", return_value=(302, {"Location": "https://example.com/next"}, b""))
    result = real_tools.execute("read_page", {"url": "https://example.com/start"})
    assert result["success"] is False
    assert "Cyclic" in result["error"] or "Maximum redirect" in result["error"]
