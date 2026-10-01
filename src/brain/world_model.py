import json

class WorldModel:
    """Run-local world state built only from verified evidence."""

    def __init__(self):
        self.facts = []
        self.artifacts = []
        self.events = []
        self.research = None

    def add_research_report(self, report):
        """Attach a bounded report; source text remains untrusted evidence."""
        if not isinstance(report, dict):
            return
        queries = report.get("queries") if isinstance(report.get("queries"), list) else []
        sources = report.get("sources") if isinstance(report.get("sources"), list) else []
        claims = report.get("claims") if isinstance(report.get("claims"), list) else []
        contradictions = report.get("contradictions") if isinstance(report.get("contradictions"), list) else []
        missing = report.get("missing_information") if isinstance(report.get("missing_information"), list) else []
        self.research = {
            "status": str(report.get("status", "unknown"))[:60],
            "queries": [str(item)[:100] for item in queries[:2] if isinstance(item, str)],
            "sources": [
                {key: (source.get(key) if key in {"relevance_basis_points", "primary_evidence_candidate"}
                       and type(source.get(key)) in {int, bool}
                       else str(source.get(key, ""))[:500]) for key in (
                    "source_id", "title", "url", "domain", "authority_signal",
                    "freshness_signal", "relevance_basis_points",
                )}
                for source in sources[:3]
                if isinstance(source, dict)
            ],
            "claims": claims[:5],
            "contradictions": contradictions[:5],
            "missing_information": [str(item)[:180] for item in missing[:8]],
            "confidence": str(report.get("confidence", "low"))[:20],
            "summary": str(report.get("summary", ""))[:1000],
            "decision": str(report.get("decision", "research_gap_remains"))[:80],
            "source_quality_note": str(report.get("source_quality_note", ""))[:300],
            "web_page_content_is_untrusted": True,
        }

    def add_verified_step(self, task, result):
        detail = str(result.get("result",""))[:1200]
        tool_name = task.get("tool")
        if tool_name in {"web_search", "read_page"}:
            detail = "Retrieved untrusted web content; see source-assessed research evidence."
        record = {"step":task.get("step"),"tool":task.get("tool"),
                  "description":task.get("description","")[:200],"evidence":detail}
        self.events.append(record)
        if detail and tool_name not in {"web_search", "read_page"}:
            self.facts.append(detail)
        if task.get("tool") == "file_system" and result.get("success"):
            self.artifacts.append(task.get("args",{}).get("path","")[:200])

    def snapshot(self):
        return {"facts":self.facts[-12:],"artifacts":self.artifacts[-20:],"events":self.events[-12:],"research":self.research}

    def as_prompt(self, limit=5000):
        return json.dumps(self.snapshot(), ensure_ascii=False)[:limit]
