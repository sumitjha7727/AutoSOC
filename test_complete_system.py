"""
Complete System Test - End-to-End Testing
Tests all components working together
"""
import json
import sqlite3
from datetime import datetime

print("\n" + "=" * 70)
print("SOC AUTOMATION SYSTEM - END-TO-END TEST")
print("=" * 70)

# ============================================
# PHASE 1: Initialization
# ============================================

print("\n" + "=" * 70)
print("PHASE 1: System Initialization")
print("=" * 70)

print("\n[*] Loading mock data...")
try:
    with open('./data/mock_alerts.json', 'r') as f:
        alerts = json.load(f)
    print(f"    OK: Loaded {len(alerts)} alerts")
except Exception as e:
    print(f"    FAIL: {e}")
    exit(1)

print("\n[*] Initializing database...")
try:
    from utils.database import init_db, DB_PATH, get_all_investigations
    init_db()
    print("    OK: Database initialized")
except Exception as e:
    print(f"    FAIL: {e}")
    exit(1)

print("\n[*] Importing orchestrator...")
try:
    from agents.orchestrator_agent import orchestrator
    print("    OK: Orchestrator imported (agents initialized)")
except Exception as e:
    print(f"    FAIL: {e}")
    exit(1)

# ============================================
# PHASE 2: Full Workflow Test - all 5 alerts
# ============================================

print("\n" + "=" * 70)
print("PHASE 2: Full Workflow Testing")
print("=" * 70)

print("\nRunning complete investigations for all 5 alerts...\n")

results = []
for idx, alert in enumerate(alerts, 1):
    print(f"Investigation {idx}/{len(alerts)}: {alert['alert_id']} ({alert['alert_type']})")
    try:
        result = orchestrator.orchestrate_investigation(alert)
        assert result.get("success"), result.get("error")
        assert result["status"] == "COMPLETED"

        results.append({
            "alert_id": alert["alert_id"],
            "investigation_id": result["investigation_id"],
            "verdict": result["verdict"],
            "confidence": result["verdict_confidence"],
            "risk_score": result["risk_score"],
            "status": "PASSED",
        })
        print(f"    PASSED - Verdict: {result['verdict']} ({result['verdict_confidence']*100:.0f}%, risk {result['risk_score']}/10)")
    except Exception as e:
        print(f"    FAILED - {e}")
        results.append({"alert_id": alert["alert_id"], "status": "FAILED", "error": str(e)})

# ============================================
# PHASE 3: Database Verification
# ============================================

print("\n" + "=" * 70)
print("PHASE 3: Database Verification")
print("=" * 70)

print("\n[*] Checking database records...")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for table in ("investigations", "evidence", "verdicts", "timeline_events"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"    {table}: {count} rows")
        assert count > 0, f"Expected rows in {table}"

    conn.close()
    print("    OK: All tables populated")
except Exception as e:
    print(f"    FAIL: {e}")
    exit(1)

investigations = get_all_investigations()
assert len(investigations) >= len(alerts), "Expected at least one investigation per alert"

# ============================================
# PHASE 4: Summary Report
# ============================================

print("\n" + "=" * 70)
print("FINAL SUMMARY REPORT")
print("=" * 70)

passed = sum(1 for r in results if r.get("status") == "PASSED")
failed = sum(1 for r in results if r.get("status") == "FAILED")

print(f"\nInvestigations Completed: {passed}/{len(alerts)}")
print(f"Success Rate: {(passed/len(alerts))*100:.0f}%")

print("\nDetailed Results:")
print("-" * 70)
for result in results:
    if result["status"] == "PASSED":
        print(f"PASSED | {result['alert_id']} | {result['verdict']} | confidence {result['confidence']*100:.0f}% | risk {result['risk_score']}/10")
    else:
        print(f"FAILED | {result['alert_id']} | {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"{failed} test(s) failed - review logs above")
    exit(1)
print("=" * 70)

print(f"\nTest completed at: {datetime.now().isoformat()}\n")
