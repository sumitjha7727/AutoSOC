import logging
from datetime import datetime
from config.settings import config

logger = logging.getLogger("soc.verdict_analyzer")

SENSITIVE_DEPARTMENTS = {"IT", "Security"}


class VerdictAnalyzerAgent:
    def __init__(self):
        self.verdicts = []
        self.tasks_completed = 0
        self.errors = 0
        logger.info("Verdict Analyzer initialized")

    def analyze_and_verdict(self, investigation_id, evidence_items, alert_data):
        try:
            evidence = {item["evidence_type"]: item["data"] for item in evidence_items}

            ip_score, ip_reason = self._score_ip_reputation(evidence.get("IP_REPUTATION", {}))
            geo_score, geo_reason = self._score_geolocation(evidence.get("GEOLOCATION", {}), evidence.get("USER_BASELINE", {}))
            log_score, log_reason = self._score_logs(evidence.get("LOG_ANALYSIS", {}))
            baseline_score, baseline_reason = self._score_user_baseline(evidence.get("USER_BASELINE", {}))

            risk_score = round(ip_score + geo_score + log_score + baseline_score, 2)

            high_threshold = config.get("verdict.high_risk_score", 7.0)
            medium_threshold = config.get("verdict.medium_risk_score", 4.0)
            confidence_threshold = config.get("verdict.confidence_threshold", 0.75)

            confidence = round(min(0.95, 0.5 + min(0.45, abs(risk_score - 5.5) / 6)), 2)

            if risk_score >= high_threshold and confidence >= confidence_threshold:
                verdict = "TRUE_POSITIVE"
            elif risk_score < medium_threshold:
                verdict = "FALSE_POSITIVE"
            else:
                verdict = "INCONCLUSIVE"

            reasoning = (
                f"IP reputation: {ip_reason} (+{ip_score}). "
                f"Geolocation: {geo_reason} (+{geo_score}). "
                f"Log analysis: {log_reason} (+{log_score}). "
                f"User baseline: {baseline_reason} (+{baseline_score}). "
                f"Total risk score {risk_score}/10 -> {verdict} (confidence {int(confidence * 100)}%)."
            )

            verdict_data = {
                "investigation_id": investigation_id,
                "verdict": verdict,
                "confidence": confidence,
                "risk_score": risk_score,
                "reasoning": reasoning,
                "score_breakdown": {
                    "ip_reputation": ip_score,
                    "geolocation": geo_score,
                    "log_analysis": log_score,
                    "user_baseline": baseline_score,
                },
                "timestamp": datetime.now().isoformat(),
            }
            self.verdicts.append(verdict_data)
            self.tasks_completed += 1
            return verdict_data
        except Exception as e:
            self.errors += 1
            return {"error": str(e), "investigation_id": investigation_id, "verdict": "INCONCLUSIVE", "confidence": 0, "risk_score": 0, "reasoning": f"Analysis failed: {e}"}

    def _score_ip_reputation(self, ip_evidence):
        reputation_score = ip_evidence.get("reputation_score", 0)
        threat_level = ip_evidence.get("threat_level", "LOW")
        if reputation_score >= 70:
            return 3, f"{threat_level} threat level, reputation score {reputation_score}/100"
        elif reputation_score >= 40:
            return 2, f"{threat_level} threat level, reputation score {reputation_score}/100"
        elif reputation_score >= 20:
            return 1, f"{threat_level} threat level, reputation score {reputation_score}/100"
        return 0, f"{threat_level} threat level, reputation score {reputation_score}/100"

    def _score_geolocation(self, geo_evidence, baseline_evidence):
        if geo_evidence.get("is_internal"):
            return 0, "internal network address, no geolocation risk"
        country = geo_evidence.get("country", "Unknown")
        city = geo_evidence.get("city", "Unknown")
        never_from = baseline_evidence.get("never_accessed_from_countries", [])
        typical = baseline_evidence.get("typical_login_locations", [])
        if not baseline_evidence.get("known"):
            return 1, f"login from {city}, {country}; user baseline unknown so location can't be verified"
        if country in never_from:
            return 2, f"login from {city}, {country}; user has never accessed from this country"
        if city not in typical and country not in typical:
            return 1, f"login from {city}, {country}; outside user's typical locations {typical}"
        return 0, f"login from {city}, {country}; matches user's typical location"

    def _score_logs(self, log_evidence):
        flagged = log_evidence.get("flagged_events", 0)
        score = min(3, flagged)
        if flagged == 0:
            return 0, "no suspicious log events detected"
        return score, f"{flagged} suspicious log event(s) detected"

    def _score_user_baseline(self, baseline_evidence):
        if not baseline_evidence.get("known"):
            return 2, "affected user not found in baseline records"
        department = baseline_evidence.get("department", "UNKNOWN")
        if department in SENSITIVE_DEPARTMENTS:
            return 1, f"user belongs to sensitive department ({department})"
        return 0, f"user belongs to standard department ({department})"

    def get_status(self):
        return {
            "agent_name": "Verdict Analyzer",
            "status": "Online",
            "verdicts_determined": len(self.verdicts),
            "tasks_completed": self.tasks_completed,
            "errors": self.errors,
            "last_updated": datetime.now().isoformat(),
        }
