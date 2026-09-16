import json
import time
from datetime import datetime
from pathlib import Path

from utils.database import create_investigation, save_evidence, save_verdict, save_timeline_event, get_investigation_details
from agents.evidence_gatherer_agent import EvidenceGathererAgent
from agents.investigation_agent import InvestigationAgent
from agents.verdict_analyzer_agent import VerdictAnalyzerAgent
from agents.health_monitor_agent import HealthMonitorAgent

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_json(filename):
    try:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Orchestrator] Error loading {filename}: {e}")
        return {}


class OrchestratorAgent:
    def __init__(self):
        print("[Orchestrator] Initializing...")
        self.evidence_gatherer = EvidenceGathererAgent()
        self.investigation_agent = InvestigationAgent()
        self.verdict_analyzer = VerdictAnalyzerAgent()
        self.health_monitor = HealthMonitorAgent()
        self.ip_verdicts = _load_json("mock_ip_verdicts.json")
        self.user_baseline = _load_json("mock_user_baseline.json")
        print("[Orchestrator] Ready")

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

    def orchestrate_investigation(self, alert_data):
        try:
            print("\n" + "=" * 60)
            print("[Orchestrator] Starting investigation orchestration")
            print("=" * 60)

            print("[Step 1] Creating investigation record...")
            investigation_id = create_investigation(alert_data)
            if not investigation_id:
                return {"success": False, "error": "Failed to create investigation"}
            print(f"[Step 1] Investigation created: {investigation_id}")
            save_timeline_event(investigation_id, "INVESTIGATION_STARTED", "Investigation started", "Orchestrator")

            print("[Step 2] Gathering evidence...")
            evidence_list = self._timed_step(
                "Evidence Gatherer",
                self.evidence_gatherer.gather_all_evidence,
                investigation_id, alert_data, self.ip_verdicts, self.user_baseline,
            )
            print(f"[Step 2] Evidence gathered: {len(evidence_list)} items")
            for evidence in evidence_list:
                save_evidence(investigation_id, evidence["evidence_type"], evidence["data"])
                save_timeline_event(investigation_id, "EVIDENCE_COLLECTED", f"Collected {evidence['evidence_type']}", "Evidence Gatherer")

            print("[Step 3] Stakeholder investigation...")
            investigation_result = self._timed_step(
                "Investigation Agent",
                self.investigation_agent.conduct_investigation,
                investigation_id, alert_data, evidence_list,
            )
            if investigation_result and "summary" in investigation_result:
                save_evidence(investigation_id, "STAKEHOLDER_CONTACT", investigation_result)
                save_timeline_event(investigation_id, "STAKEHOLDER_CONTACTED", investigation_result["summary"], "Investigation Agent")

            print("[Step 4] Verdict analysis...")
            verdict_data = self._timed_step(
                "Verdict Analyzer",
                self.verdict_analyzer.analyze_and_verdict,
                investigation_id, evidence_list, alert_data,
            )
            print(f"[Step 4] Verdict: {verdict_data.get('verdict')}")
            if "verdict" in verdict_data:
                save_verdict(investigation_id, verdict_data["verdict"], verdict_data.get("confidence", 0), verdict_data.get("risk_score", 0), verdict_data.get("reasoning", ""))
                save_timeline_event(investigation_id, "VERDICT_DETERMINED", f"Verdict: {verdict_data['verdict']} (risk {verdict_data.get('risk_score')}/10)", "Verdict Analyzer")

            print("[Step 5] Health check...")
            health_status = self.health_monitor.get_status(self._agents())

            print("[Step 6] Compiling results...")
            investigation_details = get_investigation_details(investigation_id)

            print("[Complete] Investigation orchestration done!")
            print("=" * 60 + "\n")

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
                "verdict": verdict_data.get("verdict"),
                "verdict_confidence": verdict_data.get("confidence", 0),
                "risk_score": verdict_data.get("risk_score", 0),
            }
        except Exception as e:
            print(f"[Orchestrator] Error: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    def get_status(self):
        return {"agent_name": "Orchestrator", "status": "Online", "last_updated": datetime.now().isoformat()}


orchestrator = OrchestratorAgent()
