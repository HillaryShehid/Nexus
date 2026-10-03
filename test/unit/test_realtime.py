from src.realtime import RealtimeConfig, RealtimeVoice


def test_realtime_session_uses_current_ga_configuration():
    realtime = RealtimeVoice(RealtimeConfig(model="gpt-realtime-2.1", voice="echo"))
    payload = realtime.session_payload()["session"]

    assert payload["type"] == "realtime"
    assert payload["model"] == "gpt-realtime-2.1"
    assert payload["audio"]["output"]["voice"] == "echo"
    assert payload["tool_choice"] == "required"
    assert payload["tools"][0]["name"] == "nexus_brain"
    assert payload["turn_detection"]["interrupt_response"] is True


def test_safety_identifier_is_stable_and_not_plaintext():
    first = RealtimeVoice.safety_identifier("hilal")
    second = RealtimeVoice.safety_identifier("hilal")

    assert first == second
    assert first != "hilal"
    assert len(first) == 64
