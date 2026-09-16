"""
Test script for Investigation Agent
"""
import json
from utils.database import init_db, create_investigation
from agents.evidence_gatherer_agent import EvidenceGathererAgent
from agents.investigation_agent import InvestigationAgent


def test_investigation_agent():
    print("\n" + "=" * 70)
    print("TESTING INVESTIGATION AGENT")
    print("=" * 70)

    init_db()

    with open('./data/mock_alerts.json', 'r') as f:
        alerts = json.load(f)
    with open('./data/mock_ip_verdicts.json', 'r') as f:
        ip_verdicts = json.load(f)
    with open('./data/mock_user_baseline.json', 'r') as f:
        user_baseline = json.load(f)

    test_alert = alerts[0]
    investigation_id = create_investigation(test_alert)
    assert investigation_id

    print(f"\nTest Alert: {test_alert.get('alert_id')}")
    print(f"Type: {test_alert.get('alert_type')}")
    print(f"Affected User: {test_alert.get('affected_user')}")

    gatherer = EvidenceGathererAgent()
    evidence_items = gatherer.gather_all_evidence(investigation_id, test_alert, ip_verdicts, user_baseline)

    agent = InvestigationAgent()
    result = agent.conduct_investigation(investigation_id, test_alert, evidence_items)

    assert "error" not in result, f"Investigation failed: {result.get('error')}"
    assert result["contact_result"] in ("NO_RESPONSE", "USER_DID_NOT_RECOGNIZE", "USER_CONFIRMED")

    print("\n" + "=" * 70)
    print("INVESTIGATION RESULTS")
    print("=" * 70)
    print(f"\nContact Result: {result['contact_result']}")
    print(f"Summary: {result['summary']}")

    status = agent.get_status()
    assert status["tasks_completed"] == 1

    print("\n" + "=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    test_investigation_agent()
