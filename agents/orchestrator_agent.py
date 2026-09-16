import json
import logging
import time
from datetime import datetime
from pathlib import Path

from utils.database import create_investigation, save_evidence, save_verdict, save_timeline_event, save_escalation, get_investigation_details
from agents.evidence_gatherer_agent import EvidenceGathererAgent
from agents.investigation_agent import InvestigationAgent
from agents.verdict_analyzer_agent import VerdictAnalyzerAgent
from agents.health_monitor_agent import HealthMonitorAgent

DATA_DIR = Path(__file__).parent.parent / "data"
AUTO_ESCALATE_VERDICTS = {"TRUE_POSITIVE"}

logger = logging.getLogger("soc.orchestrator")


def _load_json(filename):
    try:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}


class OrchestratorAgent:
    def __init__(self):
        logger.info("Initializing orchestrator...")
        self.evidence_gatherer = EvidenceGathererAgent()
        self.investigation_agent = InvestigationAgent()
        self.verdict_analyzer = VerdictAnalyzerAgent()
        self.health_monitor = HealthMonitorAgent()
        self.ip_verdicts = _load_json("mock_ip_verdicts.json")
        self.user_baseline = _load_json("mock_user_baseline.json")
        logger.info("Orchestrator ready")

    def _agents(self):
        return {
            "Evidence Gatherer": self.evidence_gatherer,
            "Investigation Agent": self.investigation_agent,
            "Verdict Analyzer": self.verdict_analyzer,
        }

    def _timed_step(self, agent_name, fn, *args, **kwargs):
        start = time.perf_counter()
        success = True
        try:
            return fn(*args, **kwargs)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.health_monitor.record_step(agent_name, duration_ms, success)

    def start_investigation(self, alert_data):
        """Create the investigation record synchronously. Fast (single DB insert) - safe
        to call directly from a request handler before handing off the rest of the work
        to a background task."""
        investigation_id = create_investigation(alert_data)
        if not investigation_id:
            return None
        logger.info(f"Investigation created: {investigation_id}")
        save_timeline_event(investigation_id, "INVESTIGATION_STARTED", "Investigation started", "Orchestrator")
        return investigation_id

    def run_investigation(self, investigation_id, alert_data, on_step=None):
        """Runs evidence gathering -> stakeholder investigation -> verdict analysis ->
        auto-escalation for an already-created investigation. Safe to call from a
        background thread. If on_step is given, it's called after every timeline event
        with {event_type, description, agent_name, investigation_id} for live streaming."""

        def emit(event_type, description, agent_name):
            save_timeline_event(investigation_id, event_type, description, agent_name)
            if on_step:
                on_step({
                    "investigation_id": investigation_id,
                    "event_type": event_type,
                    "description": description,
                    "agent_name": agent_name,
                })

        try:
            logger.info(f"[{investigation_id}] Gathering evidence...")
            evidence_list = self._timed_step(
                "Evidence Gatherer",
                self.evidence_gatherer.gather_all_evidence,
                investigation_id, alert_data, self.ip_verdicts, self.user_baseline,
            )
            for evidence in evidence_list:
                save_evidence(investigation_id, evidence["evidence_type"], evidence["data"])
                emit("EVIDENCE_COLLECTED", f"Collected {evidence['evidence_type']}", "Evidence Gatherer")

            logger.info(f"[{investigation_id}] Stakeholder investigation...")
            investigation_result = self._timed_step(
                "Investigation Agent",
                self.investigation_agent.conduct_investigation,
                investigation_id, alert_data, evidence_list,
            )
            if investigation_result and "summary" in investigation_result:
                save_evidence(investigation_id, "STAKEHOLDER_CONTACT", investigation_result)
                emit("STAKEHOLDER_CONTACTED", investigation_result["summary"], "Investigation Agent")

            logger.info(f"[{investigation_id}] Verdict analysis...")
            verdict_data = self._timed_step(
                "Verdict Analyzer",
                self.verdict_analyzer.analyze_and_verdict,
                investigation_id, evidence_list, alert_data,
            )
            verdict = verdict_data.get("verdict")
            if verdict:
                save_verdict(investigation_id, verdict, verdict_data.get("confidence", 0), verdict_data.get("risk_score", 0), verdict_data.get("reasoning", ""))
                emit("VERDICT_DETERMINED", f"Verdict: {verdict} (risk {verdict_data.get('risk_score')}/10)", "Verdict Analyzer")

            if verdict in AUTO_ESCALATE_VERDICTS:
                escalated = save_escalation(
                    investigation_id, alert_data.get("alert_id"), verdict,
                    verdict_data.get("confidence", 0), verdict_data.get("risk_score", 0),
                    reason=f"Auto-escalated: {verdict} verdict (risk {verdict_data.get('risk_score')}/10, confidence {int(verdict_data.get('confidence', 0) * 100)}%)",
                )
                if escalated:
                    emit("INCIDENT_ESCALATED", f"Auto-escalated due to {verdict} verdict", "Orchestrator")

            health_status = self.health_monitor.get_status(self._agents())
            investigation_details = get_investigation_details(investigation_id)

            logger.info(f"[{investigation_id}] Investigation complete: {verdict}")

            return {
                "success": True,
                "investigation_id": investigation_id,
                "alert_id": alert_data.get("alert_id"),
                "status": "COMPLETED",
                "timestamp": datetime.now().isoformat(),
                "investigation": investigation_details,
                "evidence": investigation_details.get("evidence", []) if investigation_details else [],
                "timeline": investigation_details.get("timeline", []) if investigation_details else [],
                "agents_status": health_status,
                "total_evidence": len(evidence_list),
                "verdict": verdict,
                "verdict_confidence": verdict_data.get("confidence", 0),
                "risk_score": verdict_data.get("risk_score", 0),
                "escalated_at": investigation_details.get("escalated_at") if investigation_details else None,
            }
        except Exception as e:
            logger.error(f"[{investigation_id}] Error: {e}")
            return {"success": False, "investigation_id": investigation_id, "error": str(e), "timestamp": datetime.now().isoformat()}

    def orchestrate_investigation(self, alert_data, on_step=None):
        """Synchronous convenience wrapper: create + run in one call. Used by tests and
        any caller that doesn't need progressive streaming."""
        investigation_id = self.start_investigation(alert_data)
        if not investigation_id:
            return {"success": False, "error": "Failed to create investigation"}
        return self.run_investigation(investigation_id, alert_data, on_step=on_step)

    def get_status(self):
        return {"agent_name": "Orchestrator", "status": "Online", "last_updated": datetime.now().isoformat()}


orchestrator = OrchestratorAgent()
