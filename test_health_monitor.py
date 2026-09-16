"""
Test script for Health Monitor Agent
"""
from agents.health_monitor_agent import HealthMonitorAgent
from agents.evidence_gatherer_agent import EvidenceGathererAgent


def test_health_monitor():
    print("\n" + "=" * 70)
    print("TESTING HEALTH MONITOR AGENT")
    print("=" * 70)

    monitor = HealthMonitorAgent()
    gatherer = EvidenceGathererAgent()

    monitor.record_step("Evidence Gatherer", 12.5, success=True)
    monitor.record_step("Evidence Gatherer", 15.0, success=True)

    report = monitor.get_status({"Evidence Gatherer": gatherer})

    assert report["system_status"] == "Operational"
    assert len(report["agents"]) == 1
    agent_report = report["agents"][0]
    assert agent_report["agent_name"] == "Evidence Gatherer"
    assert agent_report["response_time_ms"] == 13.8, f"Expected avg 13.8ms, got {agent_report['response_time_ms']}"
    assert agent_report["errors"] == 0

    print("\nHealth Report:")
    for agent in report["agents"]:
        print(f"  {agent['agent_name']}: {agent['health']} | avg {agent['response_time_ms']}ms | tasks {agent['tasks_completed']} | errors {agent['errors']}")
    print(f"\nSystem Status: {report['system_status']}")
    print(f"All Agents Healthy: {report['all_agents_healthy']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    test_health_monitor()
