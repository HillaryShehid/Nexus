"""Bounded, provenance-aware knowledge accumulated during one Nexus run."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4


class WorldModel:
    """Run-local knowledge with explicit epistemic type and evidence scope.

    Source-backed claims are recorded as facts only in the sense that a source
    supports the proposition. The record never treats source support as proof
    of ground truth. Retrieved page text is retained only as short cited
    excerpts; it is never treated as an instruction.
    """

    KNOWLEDGE_KINDS = frozenset({
        "fact", "observation", "inference", "hypothesis", "unknown",
    })
    CONFIDENCE_LEVELS = frozenset({"low", "medium", "high"})
    MAX_KNOWLEDGE = 48
    MAX_EVENTS = 12
    MAX_ARTIFACTS = 20
    MAX_SOURCES = 6
    MAX_EVIDENCE = 5
    MAX_TEXT = 1200

    def __init__(self):
        self.knowledge: list[dict] = []
        self.artifacts: list[str] = []
        self.events: list[dict] = []
        self.research: dict | None = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _text(value, limit: int) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.split())[:limit]

    @classmethod
    def _confidence(cls, value) -> str:
        return value if isinstance(value, str) and value in cls.CONFIDENCE_LEVELS else "low"

    @staticmethod
    def _safe_source(source: dict) -> dict | None:
        source_id = source.get("source_id")
        url = source.get("url")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 24:
            return None
        if not isinstance(url, str) or len(url) > 1000:
            return None
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                return None
            domain = parsed.hostname.lower()[:180]
        except ValueError:
            return None

        source_date = source.get("source_date")
        if not isinstance(source_date, str):
            source_date = source.get("published_at")
        if not isinstance(source_date, str):
            source_date = source.get("date")
        visible_year = source.get("visible_year")
        if type(visible_year) is not int or not 2000 <= visible_year <= 2100:
            visible_year = None

        return {
            "source_id": source_id,
            "title": WorldModel._text(source.get("title"), 250),
            "url": url,
            "domain": domain,
            "source_date": WorldModel._text(source_date, 80) or None,
            "visible_year": visible_year,
            "authority_signal": WorldModel._text(source.get("authority_signal"), 80) or "unknown",
            "freshness_signal": WorldModel._text(source.get("freshness_signal"), 80) or "unknown",
            "primary_evidence_candidate": source.get("primary_evidence_candidate") is True,
        }

    @classmethod
    def _evidence_for(cls, item: dict, sources: dict[str, dict], minimum: int = 1) -> list[dict]:
        raw = item.get("evidence")
        if not isinstance(raw, list):
            return []
        evidence = []
        seen = set()
        for entry in raw[: cls.MAX_EVIDENCE * 2]:
            if not isinstance(entry, dict):
                continue
            source_id = entry.get("source_id")
            excerpt = entry.get("excerpt")
            if not isinstance(excerpt, str):
                continue
            excerpt = excerpt.strip()
            if (
                not isinstance(source_id, str)
                or source_id not in sources
                or not 15 <= len(excerpt) <= 240
            ):
                continue
            key = (source_id, excerpt.casefold())
            if key in seen:
                continue
            seen.add(key)
            evidence.append({"source_id": source_id, "excerpt": excerpt})
            if len(evidence) == cls.MAX_EVIDENCE:
                break
        return evidence if len({item["source_id"] for item in evidence}) >= minimum else []

    @classmethod
    def _provenance_for(cls, evidence: list[dict], sources: dict[str, dict]) -> list[dict]:
        provenance = []
        for cited in evidence:
            source = sources[cited["source_id"]]
            provenance.append({key: source[key] for key in (
                "source_id", "title", "url", "domain", "source_date", "visible_year",
                "authority_signal", "freshness_signal", "primary_evidence_candidate",
            )})
        return provenance

    @classmethod
    def _claim_confidence(cls, report_confidence: str, evidence: list[dict], sources: dict[str, dict]) -> str:
        cited_sources = [
            sources[item["source_id"]]
            for item in evidence
            if item["source_id"] in sources
        ]
        domains = {source["domain"] for source in cited_sources}
        freshness_signals = [source["freshness_signal"] for source in cited_sources]
        has_stale_source = "older_year_mentioned" in freshness_signals
        all_sources_look_recent = bool(freshness_signals) and all(
            signal == "recent_year_mentioned" for signal in freshness_signals
        )
        if len(domains) >= 2:
            has_primary = any(source["primary_evidence_candidate"] for source in cited_sources)
            if report_confidence == "high" and has_primary and all_sources_look_recent:
                return "high"
            return "low" if has_stale_source else "medium"
        if (
            domains
            and not has_stale_source
            and any(source["primary_evidence_candidate"] for source in cited_sources)
        ):
            return "medium"
        return "low"

    @staticmethod
    def _freshness(kind: str, provenance: list[dict], checked_at: str) -> dict:
        sources = [item for item in provenance if isinstance(item, dict) and item.get("source_id")]
        signals = {item.get("freshness_signal") for item in sources}
        if "recent_year_mentioned" in signals and "older_year_mentioned" in signals:
            assessment = "mixed_year_signals"
        elif signals == {"recent_year_mentioned"}:
            assessment = "recent_year_mentioned"
        elif signals == {"older_year_mentioned"}:
            assessment = "older_year_mentioned"
        elif "no_year_visible" in signals:
            assessment = "no_year_visible"
        elif kind == "observation":
            assessment = "current_run"
        else:
            assessment = "unknown"
        return {
            "assessment": assessment,
            "basis": "heuristic source-year signals; this does not validate truth or publication date",
            "source_dates": [item["source_date"] for item in sources if item.get("source_date")][:5],
            "assessed_at": checked_at,
        }

    def _append_knowledge(
        self,
        kind: str,
        content: str,
        *,
        confidence: str = "low",
        status: str,
        evidence: list[dict] | None = None,
        provenance: list[dict] | None = None,
        conflicts_with: list[str] | None = None,
        verification_scope: str = "",
    ) -> dict | None:
        content = self._text(content, self.MAX_TEXT)
        if kind not in self.KNOWLEDGE_KINDS or not content:
            return None
        clean_evidence = []
        raw_evidence = evidence if isinstance(evidence, list) else []
        for item in raw_evidence[: self.MAX_EVIDENCE * 2]:
            if not isinstance(item, dict):
                continue
            source_id = self._text(item.get("source_id"), 24)
            excerpt = item.get("excerpt")
            excerpt = excerpt.strip() if isinstance(excerpt, str) else ""
            if source_id and 15 <= len(excerpt) <= 240:
                clean_evidence.append({"source_id": source_id, "excerpt": excerpt})
            if len(clean_evidence) >= self.MAX_EVIDENCE:
                break
        clean_provenance = []
        raw_provenance = provenance if isinstance(provenance, list) else []
        for item in raw_provenance[: self.MAX_SOURCES * 2]:
            if not isinstance(item, dict):
                continue
            clean_item = {}
            for key, value in item.items():
                if not isinstance(key, str) or len(key) > 40:
                    continue
                if key in {"step", "visible_year"} and type(value) is int:
                    clean_item[key] = value
                elif value is None and key == "source_date":
                    clean_item[key] = None
                elif isinstance(value, str):
                    clean_item[key] = self._text(value, 1000 if key == "url" else 250)
                elif type(value) is bool and key == "primary_evidence_candidate":
                    clean_item[key] = value
            if clean_item:
                clean_provenance.append(clean_item)
        now = self._now()
        clean_provenance = clean_provenance[: self.MAX_SOURCES]
        evidence_checked = kind == "fact" or (kind == "observation" and bool(clean_evidence))
        claim_truth_verified = False if kind in {"fact", "inference", "hypothesis"} else None
        record = {
            "knowledge_id": f"K{uuid4().hex[:12]}",
            "type": kind,
            "kind": kind,
            "claim": content,
            "content": content,
            "confidence": self._confidence(confidence),
            "status": self._text(status, 40) or "unverified",
            "evidence": clean_evidence,
            "sources": [item for item in clean_provenance if item.get("source_id")],
            "provenance": clean_provenance,
            "timestamp": now,
            "created_at": now,
            "last_checked_at": now,
            "conflicts_with": list(dict.fromkeys(
                item[:40] for item in (conflicts_with if isinstance(conflicts_with, list) else [])
                if isinstance(item, str) and item
            ))[:8],
            "contradictions": list(dict.fromkeys(
                item[:40] for item in (conflicts_with if isinstance(conflicts_with, list) else [])
                if isinstance(item, str) and item
            ))[:8],
            "freshness": self._freshness(kind, clean_provenance, now),
            "verification": {
                "evidence_checked": evidence_checked,
                "claim_truth_verified": claim_truth_verified,
                "scope": self._text(verification_scope, 180),
            },
            "verification_scope": self._text(verification_scope, 180),
        }
        self.knowledge.append(record)
        self.knowledge = self.knowledge[-self.MAX_KNOWLEDGE :]
        return record

    def add_inference(
        self, content: str, evidence: list[dict] | None = None,
        confidence: str = "low", provenance: list[dict] | None = None,
    ):
        """Record a reasoned conclusion without upgrading it to a fact."""
        return self._append_knowledge(
            "inference", content, confidence=confidence, status="inferred",
            evidence=evidence, provenance=provenance,
            verification_scope="Reasoned conclusion; not independently established.",
        )

    def add_hypothesis(
        self, content: str, evidence: list[dict] | None = None,
        confidence: str = "low", provenance: list[dict] | None = None,
    ):
        """Record a candidate explanation that still needs investigation."""
        return self._append_knowledge(
            "hypothesis", content, confidence=confidence, status="untested",
            evidence=evidence, provenance=provenance,
            verification_scope="Candidate explanation; requires discriminating evidence.",
        )

    def add_unknown(self, content: str, provenance: list[dict] | None = None):
        return self._append_knowledge(
            "unknown", content, confidence="low", status="unresolved",
            provenance=provenance, verification_scope="Information gap; no adequate evidence recorded.",
        )

    def add_research_report(self, report):
        """Convert a bounded research report into typed, source-linked records."""
        if not isinstance(report, dict):
            return

        now = self._now()
        raw_sources = report.get("sources") if isinstance(report.get("sources"), list) else []
        sources = {}
        for raw_source in raw_sources[: self.MAX_SOURCES]:
            if not isinstance(raw_source, dict):
                continue
            source = self._safe_source(raw_source)
            if source:
                sources[source["source_id"]] = source

        report_confidence = self._confidence(report.get("confidence"))
        claims = []
        for item in (report.get("claims") if isinstance(report.get("claims"), list) else [])[:8]:
            if not isinstance(item, dict):
                continue
            claim = self._text(item.get("claim"), 400)
            evidence = self._evidence_for(item, sources)
            if not claim or not evidence:
                continue
            fact = self._append_knowledge(
                "fact", claim,
                confidence=self._claim_confidence(report_confidence, evidence, sources),
                status="source_supported",
                evidence=evidence,
                provenance=self._provenance_for(evidence, sources),
                verification_scope="Cited source text supports this claim; source support is not ground truth.",
            )
            if fact:
                claims.append({"claim": fact["content"], "evidence": fact["evidence"],
                               "knowledge_id": fact["knowledge_id"]})

        contradictions = []
        for item in (report.get("contradictions") if isinstance(report.get("contradictions"), list) else [])[:8]:
            if not isinstance(item, dict):
                continue
            issue = self._text(item.get("issue", item.get("claim")), 400)
            evidence = self._evidence_for(item, sources, minimum=2)
            if not issue or not evidence:
                continue
            related_claim = self._text(item.get("related_claim"), 400)
            cited_domains = {sources[entry["source_id"]]["domain"] for entry in evidence}
            fact_ids = [
                record["knowledge_id"] for record in self.knowledge
                if related_claim and record["kind"] == "fact"
                and record["content"].casefold() == related_claim.casefold()
            ]
            conflict = self._append_knowledge(
                "observation", f"Sources conflict about: {issue}",
                confidence="high" if len(cited_domains) >= 2 else "medium",
                status="conflicted", evidence=evidence,
                provenance=self._provenance_for(evidence, sources),
                conflicts_with=fact_ids,
                verification_scope="Observed disagreement between cited sources; underlying truth remains unresolved.",
            )
            if conflict:
                for record in self.knowledge:
                    if record["knowledge_id"] in fact_ids:
                        record["status"] = "conflicted"
                        record["conflicts_with"] = list(dict.fromkeys(
                            record["conflicts_with"] + [conflict["knowledge_id"]]
                        ))[:8]
                        record["contradictions"] = record["conflicts_with"].copy()
                contradictions.append({
                    "issue": issue,
                    "related_claim": related_claim or None,
                    "evidence": evidence,
                    "knowledge_id": conflict["knowledge_id"],
                })

        missing = report.get("missing_information")
        missing = missing if isinstance(missing, list) else []
        unknowns = []
        raw_queries = report.get("queries") if isinstance(report.get("queries"), list) else []
        query_provenance = [{"type": "research", "query": self._text(query, 100)}
                            for query in raw_queries[:2]
                            if isinstance(query, str)]
        for item in missing[:8]:
            unknown = self.add_unknown(self._text(item, 180), provenance=query_provenance)
            if unknown:
                unknowns.append(unknown["content"])

        status = report.get("status")
        allowed_statuses = {
            "enough_evidence", "insufficient_evidence", "no_verified_sources",
            "contradictory_evidence", "deferred_action_budget", "no_safe_search_query",
            "research_unavailable",
        }
        self.research = {
            "status": status if isinstance(status, str) and status in allowed_statuses else "unknown",
            "checked_at": now,
            "queries": [self._text(item, 100) for item in raw_queries[:2]
                        if isinstance(item, str)],
            "sources": list(sources.values())[: self.MAX_SOURCES],
            "claims": claims[:8],
            "contradictions": contradictions[:8],
            "missing_information": unknowns[:8],
            "confidence": report_confidence,
            "summary": self._text(report.get("summary"), 1000),
            "decision": self._text(report.get("decision"), 80) or "research_gap_remains",
            "source_quality_note": self._text(report.get("source_quality_note"), 300),
            "web_page_content_is_untrusted": True,
        }

    def add_verified_step(self, task, result):
        if not isinstance(task, dict) or not isinstance(result, dict):
            return
        detail = self._text(result.get("result", ""), self.MAX_TEXT)
        tool_name = task.get("tool")
        if tool_name in {"web_search", "read_page"}:
            detail = "Retrieved untrusted web content; see source-assessed research evidence."
        description = self._text(task.get("description", ""), 200)
        record = {
            "step": task.get("step") if type(task.get("step")) is int else None,
            "tool": self._text(tool_name, 60),
            "description": description,
            "evidence": detail,
        }
        self.events.append(record)
        self.events = self.events[-self.MAX_EVENTS :]

        if detail and tool_name not in {"web_search", "read_page"}:
            self._append_knowledge(
                "observation", detail, confidence="medium", status="observed",
                provenance=[{
                    "type": "tool_result",
                    "tool": self._text(tool_name, 60),
                    "step": record["step"],
                    "description": description,
                }],
                verification_scope="Tool result passed Nexus's configured structural verification.",
            )
        if tool_name == "file_system" and result.get("success") is True:
            args = task.get("args") if isinstance(task.get("args"), dict) else {}
            path = self._text(args.get("path"), 200)
            if path:
                self.artifacts.append(path)
                self.artifacts = self.artifacts[-self.MAX_ARTIFACTS :]

    def add_failure(self, task, category="unknown"):
        """Record the observed failure category without retaining raw error text."""
        if not isinstance(task, dict):
            return
        step = task.get("step") if type(task.get("step")) is int else None
        tool_name = self._text(task.get("tool"), 60) or "unknown_tool"
        safe_category = self._text(category, 60) or "unknown"
        detail = f"Tool action was not verified; classified category: {safe_category}."
        description = self._text(task.get("description", ""), 200)
        self.events.append({
            "step": step,
            "tool": tool_name,
            "description": description,
            "evidence": detail,
        })
        self.events = self.events[-self.MAX_EVENTS :]
        self._append_knowledge(
            "observation", f"{tool_name} action failed verification ({safe_category}).",
            confidence="high", status="observed",
            provenance=[{
                "type": "failure_event",
                "tool": tool_name,
                "step": step,
                "category": safe_category,
                "description": description,
            }],
            verification_scope="Observed Nexus failure classification; raw error details are not retained here.",
        )

    def snapshot(self):
        knowledge = deepcopy(self.knowledge[-16:])
        return {
            # Compatibility view: only source-supported propositions are facts.
            "facts": [item["content"] for item in knowledge
                      if item["kind"] == "fact" and item["status"] == "source_supported"][-12:],
            "knowledge": knowledge,
            "artifacts": self.artifacts[-self.MAX_ARTIFACTS :],
            "events": self.events[-self.MAX_EVENTS :],
            "research": deepcopy(self.research),
        }

    def as_prompt(self, limit=5000):
        """Serialize a valid, bounded JSON snapshot without cutting JSON mid-token."""
        if type(limit) is not int:
            limit = 5000
        limit = min(max(limit, 32), 50_000)
        payload = self.snapshot()

        def encoded():
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        collections = ("events", "artifacts", "knowledge")
        while len(encoded()) > limit:
            removed = False
            for key in collections:
                if payload[key]:
                    payload[key].pop(0)
                    removed = True
                    if key == "knowledge":
                        payload["facts"] = [
                            item["content"] for item in payload["knowledge"]
                            if item["kind"] == "fact" and item["status"] == "source_supported"
                        ][-12:]
                    break
            if removed:
                continue
            if payload["research"]:
                research = payload["research"]
                for key in ("sources", "claims", "contradictions", "queries", "missing_information"):
                    if research.get(key):
                        research[key].pop(0)
                        removed = True
                        break
                if not removed and research.get("summary"):
                    research["summary"] = research["summary"][: max(0, len(research["summary"]) // 2)]
                    removed = True
            if not removed:
                return json.dumps({"truncated": True}, separators=(",", ":"))
        return encoded()
