"""
Test script for Orchestrator Agent
"""
import json
from utils.database import init_db
from agents.orchestrator_agent import orchestrator


def test_orchestrator():
    print("\n" + "=" * 70)
    print("TESTING ORCHESTRATOR AGENT")
    print("=" * 70)

    init_db()

    with open('./data/mock_alerts.json', 'r') as f:
        alerts = json.load(f)

    test_alert = alerts[0]

    print(f"\nTest Alert: {test_alert.get('alert_id')}")
    print(f"Type: {test_alert.get('alert_type')}")
    print(f"Severity: {test_alert.get('severity')}")

    result = orchestrator.orchestrate_investigation(test_alert)

    assert result.get("success"), f"Orchestration failed: {result.get('error')}"
    assert result["status"] == "COMPLETED"
    assert result["total_evidence"] == 4
    assert result["verdict"] in ("TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE")

    print("\n" + "=" * 70)
    print("ORCHESTRATION RESULTS")
    print("=" * 70)
    print(f"\nInvestigation ID: {result['investigation_id']}")
    print(f"Alert ID: {result['alert_id']}")
    print(f"Status: {result['status']}")
    print(f"Verdict: {result['verdict']} (confidence {result['verdict_confidence']*100:.0f}%, risk {result['risk_score']}/10)")

    print(f"\nAgent Health:")
    for agent_status in result["agents_status"]["agents"]:
        print(f"  {agent_status['agent_name']}: {agent_status['health']} | avg {agent_status['response_time_ms']}ms")

    print(f"\nTimeline ({len(result['timeline'])} events):")
    for event in result["timeline"]:
        print(f"  [{event['agent_name']}] {event['description']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    test_orchestrator()
