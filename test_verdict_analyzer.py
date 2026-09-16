"""
Test script for Verdict Analyzer Agent
"""
import json
from utils.database import init_db, create_investigation
from agents.evidence_gatherer_agent import EvidenceGathererAgent
from agents.verdict_analyzer_agent import VerdictAnalyzerAgent


def test_verdict_analyzer():
    print("\n" + "=" * 70)
    print("TESTING VERDICT ANALYZER AGENT")
    print("=" * 70)

    init_db()

    with open('./data/mock_alerts.json', 'r') as f:
        alerts = json.load(f)
    with open('./data/mock_ip_verdicts.json', 'r') as f:
        ip_verdicts = json.load(f)
    with open('./data/mock_user_baseline.json', 'r') as f:
        user_baseline = json.load(f)

    gatherer = EvidenceGathererAgent()
    analyzer = VerdictAnalyzerAgent()

    test_cases = [
        (alerts[0], "Suspicious login from new location"),
        (alerts[1], "Malware detected"),
        (alerts[4], "Normal activity"),
    ]

    for test_alert, description in test_cases:
        print(f"\n{'=' * 70}")
        print(f"TEST CASE: {description}")
        print(f"{'=' * 70}")

        investigation_id = create_investigation(test_alert)
        assert investigation_id

        evidence_items = gatherer.gather_all_evidence(investigation_id, test_alert, ip_verdicts, user_baseline)
        verdict_report = analyzer.analyze_and_verdict(investigation_id, evidence_items, test_alert)

        assert "error" not in verdict_report, f"Verdict analysis failed: {verdict_report.get('error')}"
        assert verdict_report["verdict"] in ("TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE")
        assert 0 <= verdict_report["risk_score"] <= 10
        assert 0 <= verdict_report["confidence"] <= 1

        print(f"\nAlert: {test_alert.get('alert_id')} ({test_alert.get('alert_type')})")
        print(f"Verdict: {verdict_report['verdict']}")
        print(f"Risk Score: {verdict_report['risk_score']:.1f}/10.0")
        print(f"Confidence: {verdict_report['confidence']*100:.0f}%")
        print(f"Reasoning: {verdict_report['reasoning']}")

    # Sanity check: the clean "normal activity" case should score as a false positive
    normal_activity_result = analyzer.verdicts[-1]
    assert normal_activity_result["verdict"] == "FALSE_POSITIVE", "Normal activity alert should resolve to FALSE_POSITIVE"

    print("\n" + "=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    test_verdict_analyzer()
