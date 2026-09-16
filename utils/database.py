import sqlite3
import json
import logging
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'soc_automation.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("soc.database")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with all required tables"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS investigations (
                investigation_id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT,
                affected_user TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                verdict TEXT,
                confidence REAL,
                risk_score REAL,
                reasoning TEXT,
                escalated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                agent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS verdicts (
                verdict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk_score REAL NOT NULL,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                alert_id TEXT NOT NULL,
                verdict TEXT,
                confidence REAL,
                risk_score REAL,
                escalation_reason TEXT,
                escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                alert_id TEXT NOT NULL,
                review_reason TEXT,
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS resolved (
                resolved_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                alert_id TEXT NOT NULL,
                resolution_reason TEXT,
                resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id)
            )
            ''')

        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


def create_investigation(alert_data):
    """Create a new investigation record"""
    try:
        investigation_id = f"INV-{alert_data.get('alert_id', 'UNKNOWN')}-{int(datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO investigations
            (investigation_id, alert_id, alert_type, severity, affected_user, source_ip, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                investigation_id,
                alert_data.get('alert_id', 'UNKNOWN'),
                alert_data.get('alert_type', 'UNKNOWN'),
                alert_data.get('severity', 'UNKNOWN'),
                alert_data.get('affected_user', 'UNKNOWN'),
                alert_data.get('source_ip', 'UNKNOWN'),
                'PENDING',
                datetime.now().isoformat()
            ))
        logger.info(f"Investigation created: {investigation_id}")
        return investigation_id
    except Exception as e:
        logger.error(f"Error creating investigation: {e}")
        return None


def save_evidence(investigation_id, evidence_type, data):
    """Save a piece of evidence for an investigation"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO evidence (investigation_id, evidence_type, data)
            VALUES (?, ?, ?)
            ''', (investigation_id, evidence_type, json.dumps(data)))
        return True
    except Exception as e:
        logger.error(f"Error saving evidence: {e}")
        return False


def save_timeline_event(investigation_id, event_type, description, agent_name):
    """Save a timeline event for an investigation"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO timeline_events (investigation_id, event_type, description, agent_name)
            VALUES (?, ?, ?, ?)
            ''', (investigation_id, event_type, description, agent_name))
        return True
    except Exception as e:
        logger.error(f"Error saving timeline event: {e}")
        return False


def save_verdict(investigation_id, verdict, confidence, risk_score, reasoning):
    """Save verdict and update investigation status to COMPLETED"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO verdicts (investigation_id, verdict, confidence, risk_score, reasoning)
            VALUES (?, ?, ?, ?, ?)
            ''', (investigation_id, verdict, confidence, risk_score, reasoning))
            cursor.execute('''
            UPDATE investigations
            SET verdict = ?, confidence = ?, risk_score = ?, reasoning = ?, status = ?, completed_at = ?
            WHERE investigation_id = ?
            ''', (verdict, confidence, risk_score, reasoning, "COMPLETED", datetime.now().isoformat(), investigation_id))
        logger.info(f"Verdict saved for {investigation_id}: {verdict} (Status: COMPLETED)")
        return True
    except Exception as e:
        logger.error(f"Error saving verdict: {e}")
        return False


def get_investigation(investigation_id):
    """Retrieve investigation details (flat)"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM investigations WHERE investigation_id = ?', (investigation_id,))
            row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving investigation: {e}")
        return None


def get_all_investigations():
    """Get all investigations"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM investigations ORDER BY created_at DESC')
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving investigations: {e}")
        return []


def get_investigation_details(investigation_id):
    """Get full investigation details including evidence and timeline"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM investigations WHERE investigation_id = ?', (investigation_id,))
            inv_row = cursor.fetchone()
            if not inv_row:
                return None

            result = dict(inv_row)

            cursor.execute('SELECT evidence_type, data, created_at FROM evidence WHERE investigation_id = ? ORDER BY id', (investigation_id,))
            result['evidence'] = [
                {'evidence_type': row['evidence_type'], 'data': json.loads(row['data']), 'created_at': row['created_at']}
                for row in cursor.fetchall()
            ]

            cursor.execute('SELECT event_type, description, agent_name, created_at FROM timeline_events WHERE investigation_id = ? ORDER BY id', (investigation_id,))
            result['timeline'] = [dict(row) for row in cursor.fetchall()]

        return result
    except Exception as e:
        logger.error(f"Error retrieving investigation details: {e}")
        return None


def save_escalation(investigation_id, alert_id, verdict, confidence, risk_score, reason='Manual escalation from dashboard'):
    """Save escalation record and mark the investigation as escalated. No-op (returns
    False) if the investigation was already escalated, so this is safe to call both
    automatically (on a TRUE_POSITIVE verdict) and manually from the dashboard without
    ever creating duplicate escalation rows."""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('SELECT escalated_at FROM investigations WHERE investigation_id = ?', (investigation_id,))
            row = cursor.fetchone()
            if row and row['escalated_at']:
                logger.info(f"Escalation skipped for {investigation_id}: already escalated")
                return False

            cursor.execute('''
            INSERT INTO escalations (investigation_id, alert_id, verdict, confidence, risk_score, escalation_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (investigation_id, alert_id, verdict, confidence, risk_score, reason))
            cursor.execute('''
            UPDATE investigations SET escalated_at = ? WHERE investigation_id = ?
            ''', (datetime.now().isoformat(), investigation_id))
        logger.info(f"Escalation saved for {investigation_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving escalation: {e}")
        return False


def get_escalations():
    """Get all escalations"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM escalations ORDER BY escalated_at DESC')
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving escalations: {e}")
        return []


def save_review(investigation_id, alert_id, review_reason):
    """Save review request"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO reviews (investigation_id, alert_id, review_reason)
            VALUES (?, ?, ?)
            ''', (investigation_id, alert_id, review_reason))
        logger.info(f"Review saved for {investigation_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving review: {e}")
        return False


def get_reviews():
    """Get all review requests, with verdict/risk context from their investigation"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT rv.review_id, rv.investigation_id, rv.alert_id, rv.review_reason, rv.reviewed_at,
                   i.alert_type, i.verdict, i.confidence, i.risk_score
            FROM reviews rv
            LEFT JOIN investigations i ON rv.investigation_id = i.investigation_id
            ORDER BY rv.reviewed_at DESC
            ''')
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving reviews: {e}")
        return []


def save_resolved(investigation_id, alert_id, resolution_reason):
    """Save resolved incident"""
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO resolved (investigation_id, alert_id, resolution_reason)
            VALUES (?, ?, ?)
            ''', (investigation_id, alert_id, resolution_reason))
        logger.info(f"Incident marked as resolved: {investigation_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving resolved: {e}")
        return False


def get_resolved():
    """Get all resolved incidents, with verdict/risk context from their investigation"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT r.resolved_id, r.investigation_id, r.alert_id, r.resolution_reason, r.resolved_at,
                   i.alert_type, i.verdict, i.confidence, i.risk_score
            FROM resolved r
            LEFT JOIN investigations i ON r.investigation_id = i.investigation_id
            ORDER BY r.resolved_at DESC
            ''')
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving resolved incidents: {e}")
        return []


def get_metrics():
    """Get dashboard metrics"""
    try:
        with closing(_connect()) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM investigations')
            total_alerts = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM escalations')
            escalations = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM resolved')
            resolved = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM investigations WHERE verdict = 'TRUE_POSITIVE'")
            true_positives = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM investigations WHERE verdict = 'FALSE_POSITIVE'")
            false_positives = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM investigations WHERE verdict = 'INCONCLUSIVE'")
            inconclusive = cursor.fetchone()[0]

        return {
            'total_alerts': total_alerts,
            'escalations': escalations,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'inconclusive': inconclusive,
            'resolved': resolved
        }
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        return {'total_alerts': 0, 'escalations': 0, 'true_positives': 0, 'false_positives': 0, 'inconclusive': 0, 'resolved': 0}
