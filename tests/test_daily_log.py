import json

from src.daily_log import AgentDailyLog


def test_record_run_stores_structured_outcome_without_transcript(tmp_path):
    log = AgentDailyLog(log_path=str(tmp_path / "daily.jsonl"))
    result = log.record_run(
        request="Research Python deployment timeout",
        status="partial",
        route="research",
        completed_steps=[{
            "tool": "web_search",
            "description": "Found deployment documentation",
            "detail": "Verified source page",
        }],
        failures=[{"tool": "read_page", "category": "external_dependency", "error": "secret details omitted"}],
    )

    assert result["success"] is True
    entry = json.loads((tmp_path / "daily.jsonl").read_text(encoding="utf-8"))
    assert entry["status"] == "partial"
    assert entry["verified_accomplishments"][0]["tool"] == "web_search"
    assert entry["errors"] == [{"tool": "read_page", "category": "external_dependency"}]
    assert "secret details omitted" not in json.dumps(entry)


def test_relevant_context_recalls_matching_prior_lesson(tmp_path):
    log = AgentDailyLog(log_path=str(tmp_path / "daily.jsonl"))
    log.record_run(
        request="Fix Python deployment timeout",
        status="complete",
        route="research",
        completed_steps=[{"tool": "web_search", "description": "Found timeout configuration"}],
    )

    context = log.relevant_context("deployment timeout")
    assert "timeout" in context
    assert "web_search" in context


def test_relevant_context_is_empty_when_nothing_matches(tmp_path):
    log = AgentDailyLog(log_path=str(tmp_path / "daily.jsonl"))
    log.record_run(request="Research Python deployment", status="complete", route="research")
    assert log.relevant_context("watermelon astronomy") == ""
