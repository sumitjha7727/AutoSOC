from datetime import datetime

SEVERE_ALERT_TYPES = {"MALWARE_DETECTED", "PRIVILEGE_ESCALATION_ATTEMPT"}


class InvestigationAgent:
    def __init__(self):
        self.investigation_data = {}
        self.tasks_completed = 0
        self.errors = 0
        print("[Investigation Agent] Initialized")

    def conduct_investigation(self, investigation_id, alert_data, evidence_list):
        """Simulate contacting the affected user / manager for confirmation, using the
        evidence already gathered to decide how the (mocked) stakeholder would respond."""
        try:
            evidence = {item["evidence_type"]: item["data"] for item in evidence_list}
            user = alert_data.get("affected_user", "unknown")
            alert_type = alert_data.get("alert_type", "")

            geo = evidence.get("GEOLOCATION", {})
            baseline = evidence.get("USER_BASELINE", {})
            ip_rep = evidence.get("IP_REPUTATION", {})

            suspicious_location = (not geo.get("is_internal")) and (
                geo.get("country") in baseline.get("never_accessed_from_countries", [])
            )
            high_threat_ip = ip_rep.get("threat_level") in ("HIGH", "CRITICAL")

            if alert_type in SEVERE_ALERT_TYPES or (suspicious_location and high_threat_ip):
                contact_result = "NO_RESPONSE"
                summary = f"{user} could not be reached within the contact window; escalating for manual follow-up."
            elif suspicious_location:
                contact_result = "USER_DID_NOT_RECOGNIZE"
                summary = f"{user} was contacted and did not recognize this login location."
            else:
                contact_result = "USER_CONFIRMED"
                summary = f"{user} confirmed this activity as expected; no action requested."

            analysis = {
                "investigation_id": investigation_id,
                "user": user,
                "contact_result": contact_result,
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
            }
            self.investigation_data = analysis
            self.tasks_completed += 1
            return analysis
        except Exception as e:
            self.errors += 1
            return {"error": str(e)}

    def get_status(self):
        return {
            "agent_name": "Investigation Agent",
            "status": "Online",
            "tasks_completed": self.tasks_completed,
            "errors": self.errors,
            "last_updated": datetime.now().isoformat(),
        }
