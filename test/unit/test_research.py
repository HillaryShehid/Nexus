import json
from datetime import datetime

from src.brain.research import ResearchController


def test_research_is_requested_only_for_material_gap_or_explicit_web_request():
    assert not ResearchController.should_research({
        "research_required": False, "missing_information": [],
    }, "Explain a stable concept")
    assert ResearchController.should_research({
        "research_required": True, "missing_information": ["current release status"],
    }, "Is this package currently broken?")
    assert not ResearchController.should_research({
        "research_required": True, "missing_information": ["latest release"],
    }, "Do not use the internet; answer from local files")


def test_queries_reject_obvious_secrets_and_keep_private_request_out():
    brief = {
        "research_queries": ["package docs sk_live_123456789012345678"],
        "missing_information": [],
    }
    assert ResearchController._queries(brief, "user context") == []


def test_research_fields_are_sanitized_by_the_executive(mocker):
    from types import SimpleNamespace
    from src.brain.executive import ExecutiveController

    model = mocker.MagicMock()
    model.generate.return_value = {
        "success": True,
        "content": json.dumps({
            "goal": "check package behavior",
            "needs_action": True,
            "research_required": True,
            "research_reason": "Need external evidence" * 30,
            "research_queries": ["  official package docs   ", "x" * 180, 42],
        }),
    }
    brief = ExecutiveController(model).brief(
        "Why does this fail?", "", "",
        SimpleNamespace(name="research", depth="normal", profile="research"),
    )

    assert brief["research_required"] is True
    assert len(brief["research_reason"]) == 300
    assert brief["research_queries"] == ["official package docs", "x" * 100]


def test_synthesis_requires_verbatim_source_evidence_and_downranks_conflicts():
    sources = [
        {
            "source_id": "S1", "domain": "docs.pytest.org",
            "primary_evidence_candidate": True,
            "freshness_signal": "no_year_visible",
            "body": "Pytest supports assertion rewriting for test modules.",
        },
        {
            "source_id": "S2", "domain": "example.net",
            "primary_evidence_candidate": False,
            "freshness_signal": "no_year_visible",
            "body": "This page claims assertion rewriting is unavailable.",
        },
    ]
    raw = {
        "claims": [{
            "claim": "Pytest supports assertion rewriting.",
            "evidence": [{
                "source_id": "S1",
                "excerpt": "Pytest supports assertion rewriting for test modules.",
            }],
        }],
        "contradictions": [{
            "issue": "Sources disagree about rewriting support.",
            "evidence": [
                {"source_id": "S1", "excerpt": "Pytest supports assertion rewriting for test modules."},
                {"source_id": "S2", "excerpt": "This page claims assertion rewriting is unavailable."},
            ],
        }],
        "missing_information": [],
        "enough_evidence": True,
        "confidence": "high",
        "summary": "Sources disagree.",
    }
    result = ResearchController._validate_synthesis(raw, sources, {"goal": "pytest"})

    assert len(result["claims"]) == 1
    assert len(result["contradictions"]) == 1
    assert result["enough_evidence"] is False

    raw["claims"][0]["evidence"][0]["excerpt"] = "Invented quotation with no source support."
    result = ResearchController._validate_synthesis(raw, sources, {"goal": "pytest"})
    assert result["claims"] == []
    assert result["confidence"] == "low"


def test_research_searches_then_opens_a_source_and_returns_source_assessment():
    class Model:
        def generate(self, _system, prompt, **_kwargs):
            source = json.loads(prompt)["sources"][0]
            return {
                "success": True,
                "content": json.dumps({
                    "claims": [{
                        "claim": "Official docs describe the test fixture behavior.",
                        "evidence": [{
                            "source_id": source["source_id"],
                            "excerpt": "Pytest supports assertion rewriting for test modules.",
                        }],
                    }],
                    "contradictions": [],
                    "missing_information": [],
                    "enough_evidence": True,
                    "confidence": "high",
                    "summary": "The official documentation supports this behavior.",
                }),
            }

    calls = []

    def execute(task):
        calls.append(task["tool"])
        if task["tool"] == "web_search":
            payload = {
                "query": task["args"]["query"],
                "results": [{
                    "title": "Pytest assertion rewriting",
                    "url": "https://docs.pytest.org/en/stable/how-to/assert.html",
                    "snippet": "Pytest supports assertion rewriting for test modules.",
                }],
            }
        else:
            payload = {
                "origin": task["args"]["url"],
                "resolved_ip": "203.0.113.8",
                "body": "Pytest supports assertion rewriting for test modules.",
            }
        return {"verified": True, "result": {"result": json.dumps(payload)}}

    controller = ResearchController(Model())
    report, actions = controller.research(
        "Is pytest rewriting supported?",
        {
            "goal": "Confirm pytest assertion rewriting support",
            "missing_information": ["official documentation behavior"],
            "research_reason": "Need current technical facts",
            "research_queries": ["pytest assertion rewriting official docs"],
        },
        execute,
        max_tool_calls=2,
    )

    assert calls == ["web_search", "read_page"]
    assert len(actions) == 2
    assert report["status"] == "enough_evidence"
    assert report["sources"][0]["authority_signal"] == "official_domain_candidate"
    assert report["sources"][0]["freshness_signal"] == "no_year_visible"
    assert report["claims"][0]["evidence"][0]["source_id"] == "S1"
    assert report["web_page_content_is_untrusted"] is True


def test_research_runs_one_bounded_followup_when_first_evidence_is_insufficient():
    class Model:
        calls = 0

        def generate(self, _system, prompt, **_kwargs):
            self.calls += 1
            sources = json.loads(prompt)["sources"]
            evidence = sources[-1]
            content = {
                "claims": [{
                    "claim": "The project documentation describes the supported release behavior.",
                    "evidence": [{
                        "source_id": evidence["source_id"],
                        "excerpt": evidence["body"],
                    }],
                }],
                "contradictions": [],
                "missing_information": ["release notes from another independent source"],
                "enough_evidence": self.calls > 1,
                "confidence": "high" if self.calls > 1 else "low",
                "summary": "Only source excerpts can appear in the final report.",
            }
            return {"success": True, "content": json.dumps(content)}

    model = Model()
    calls = []

    def execute(task):
        calls.append((task["tool"], task["args"].copy()))
        if task["tool"] == "web_search":
            query = task["args"]["query"]
            if len([kind for kind, _ in calls if kind == "web_search"]) == 1:
                result = {
                    "title": "Pytest release documentation",
                    "url": "https://docs.pytest.org/en/stable/announce/index.html",
                    "snippet": "Pytest official release documentation and version notes.",
                }
            else:
                result = {
                    "title": "Pytest releases on GitHub",
                    "url": "https://github.com/pytest-dev/pytest/releases",
                    "snippet": "Pytest release notes from the project repository.",
                }
            payload = {"query": query, "results": [result]}
        else:
            if "github.com" in task["args"]["url"]:
                origin = "https://github.com/pytest-dev/pytest/releases"
                body = f"{datetime.now().year}: the project lists supported release notes here."
            else:
                origin = "https://docs.pytest.org/en/stable/announce/index.html"
                body = f"{datetime.now().year}: the project documentation describes the supported release behavior."
            payload = {"origin": origin, "resolved_ip": "203.0.113.9", "body": body}
        return {"verified": True, "result": {"result": json.dumps(payload)}}

    report, tool_calls = ResearchController(model).research(
        "Check pytest release support",
        {
            "goal": "Check pytest release support",
            "missing_information": ["independent release source"],
            "research_queries": ["pytest current release support official documentation"],
        },
        execute,
        max_tool_calls=4,
    )

    assert model.calls == 2
    assert [call["task"]["tool"] for call in tool_calls] == [
        "web_search", "read_page", "web_search", "read_page",
    ]
    assert len(report["queries"]) == 2
    assert len(report["sources"]) == 2
    assert report["status"] == "enough_evidence"


def test_volatile_facts_need_a_recently_mentioned_year():
    older_year = datetime.now().year - 2
    body = f"Package release {older_year} is documented here."
    sources = [{
        "source_id": "S1", "domain": "docs.python.org",
        "primary_evidence_candidate": True,
        "freshness_signal": "older_year_mentioned",
        "body": body,
    }]
    raw = {
        "claims": [{
            "claim": "The docs describe an earlier package release.",
            "evidence": [{"source_id": "S1", "excerpt": body}],
        }],
        "contradictions": [], "missing_information": [],
        "enough_evidence": True, "confidence": "high", "summary": "",
    }

    result = ResearchController._validate_synthesis(
        raw, sources, {"goal": "Find the current package release"}
    )

    assert result["enough_evidence"] is False


def test_search_result_structural_verification_does_not_assert_claim_truth():
    from src.verification import VerificationSystem

    verifier = VerificationSystem(None, None)
    task = {"tool": "web_search", "args": {}, "description": "Search for sources."}
    valid = verifier.verify_step_result(task, {
        "success": True,
        "result": json.dumps({
            "query": "package issue",
            "results": [{
                "title": "Issue tracker", "url": "https://github.com/example/project/issues/1",
                "snippet": "One user reports a failure.",
            }],
        }),
    })
    invalid = verifier.verify_step_result(task, {
        "success": True,
        "result": '{"query":"package issue","results":[{"title":"missing fields"}]}',
    })

    assert valid["verified"] is True
    assert "structure" in valid["reason"]
    assert invalid["verified"] is False


def test_brain_routes_requested_research_through_permission_and_world_model():
    from types import SimpleNamespace
    from src.brain.brain import NexusBrain

    class Allowed:
        def evaluate_clearance(self, *_args):
            return {"status": "allowed"}

    class Tools:
        def execute(self, _name, _args):
            return {
                "success": True,
                "result": json.dumps({"query": "test", "results": []}),
            }

    class Verifier:
        def verify_step_result(self, *_args):
            return {"verified": True}

    class Capabilities:
        def select(self, _request):
            return {"active_layers": []}

    class Researcher:
        def research(self, _request, _brief, execute, max_tool_calls):
            assert max_tool_calls == 2
            task = {
                "step": 1, "tool": "web_search", "args": {"query": "test"},
                "description": "Search public sources.",
            }
            return ({
                "status": "no_verified_sources", "queries": ["test"],
                "sources": [], "claims": [], "contradictions": [],
                "missing_information": ["source evidence unavailable"],
                "confidence": "low", "summary": "No verified source.",
                "decision": "research_gap_remains",
            }, [{"task": task, "outcome": execute(task)}])

    brain = NexusBrain.__new__(NexusBrain)
    brain.router = SimpleNamespace(route=lambda _request: SimpleNamespace(
        name="research", depth="normal", max_actions=3, profile="research",
    ))
    brain.capabilities = Capabilities()
    brain.memory = SimpleNamespace(read_context=lambda: "")
    brain.learning = SimpleNamespace(retrieve_lessons=lambda: "")
    brain.executive = SimpleNamespace(brief=lambda *_args: {
        "goal": "Check an external technical fact", "intent": "research",
        "constraints": [], "known_facts": [],
        "missing_information": ["current technical behavior"], "assumptions": [],
        "needs_action": False, "research_required": True,
        "research_reason": "The fact may have changed", "research_queries": ["official docs"],
        "success_criteria": [],
    })
    brain.research_controller = Researcher()
    brain.permissions = Allowed()
    brain.tools = Tools()
    brain.verifier = Verifier()
    captured = {}

    def finish(state, _brief, _route, run_metrics=None, _started_at=None):
        captured["state"] = state
        captured["metrics"] = run_metrics
        return {"response": "Done", "status": state.status}

    brain._finish = finish
    result = brain.run_detailed("Please research this technical question")

    assert result["response"] == "Done"
    assert captured["metrics"]["tool_attempts"] == 1
    assert captured["state"].world["research"]["status"] == "no_verified_sources"
    assert captured["state"].world["facts"] == []
    assert "untrusted web content" in captured["state"].world["events"][0]["evidence"]
