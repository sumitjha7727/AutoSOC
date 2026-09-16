"""
Test script for Evidence Gatherer Agent
"""
import json
from utils.database import init_db, create_investigation
from agents.evidence_gatherer_agent import EvidenceGathererAgent


def test_evidence_gatherer():
    print("\n" + "=" * 70)
    print("TESTING EVIDENCE GATHERER AGENT")
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
    assert investigation_id, "Failed to create investigation"

    print(f"\nTest Alert: {test_alert.get('alert_id')}")
    print(f"Investigation ID: {investigation_id}")
    print(f"Affected User: {test_alert.get('affected_user')}")
    print(f"Source IP: {test_alert.get('source_ip')}")

    gatherer = EvidenceGathererAgent()
    evidence_items = gatherer.gather_all_evidence(investigation_id, test_alert, ip_verdicts, user_baseline)

    assert len(evidence_items) == 4, f"Expected 4 evidence items, got {len(evidence_items)}"
    evidence_types = {item["evidence_type"] for item in evidence_items}
    assert evidence_types == {"LOG_ANALYSIS", "IP_REPUTATION", "GEOLOCATION", "USER_BASELINE"}, f"Unexpected evidence types: {evidence_types}"

    print("\n" + "=" * 70)
    print("EVIDENCE SUMMARY")
    print("=" * 70)
    for i, evidence in enumerate(evidence_items, 1):
        print(f"\n{i}. {evidence['evidence_type']}")
        data = evidence['data']
        if evidence['evidence_type'] == 'LOG_ANALYSIS':
            print(f"   Logs Found: {data['logs_found']}, Flagged: {data['flagged_events']}")
        elif evidence['evidence_type'] == 'IP_REPUTATION':
            print(f"   Reputation Score: {data['reputation_score']}/100, Threat Level: {data['threat_level']}")
        elif evidence['evidence_type'] == 'GEOLOCATION':
            print(f"   Location: {data['city']}, {data['country']}")
        elif evidence['evidence_type'] == 'USER_BASELINE':
            print(f"   Department: {data['department']}, Typical Locations: {data['typical_login_locations']}")

    status = gatherer.get_status()
    assert status["tasks_completed"] == 1, "Task counter did not increment"

    print("\n" + "=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    test_evidence_gatherer()
