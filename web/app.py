from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
from pathlib import Path
import sys

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging_config import setup_logging
from utils.database import (
    init_db, get_investigation_details, save_escalation,
    get_escalations, save_review, get_reviews, save_resolved, get_resolved,
    get_metrics, get_all_investigations
)
from agents.orchestrator_agent import orchestrator

logger = setup_logging()

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'soc-alert-automation-secret-key'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database
init_db()

# Load mock alert data (evidence/baseline/IP data is loaded by the orchestrator's agents)
MOCK_ALERTS_PATH = Path(__file__).parent.parent / 'data' / 'mock_alerts.json'

def load_mock_data(path):
    """Load JSON mock data file"""
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[APP] Error loading {path}: {e}")
    return {}

mock_alerts = load_mock_data(MOCK_ALERTS_PATH)

logger.info("[APP] Mock data loaded successfully")

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve main dashboard page"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint for Docker/orchestration"""
    return jsonify({'status': 'ok'})

# ============================================================
# API ENDPOINTS - ALERTS
# ============================================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get all available alerts"""
    try:
        if isinstance(mock_alerts, dict) and 'alerts' in mock_alerts:
            return jsonify(mock_alerts['alerts'])
        elif isinstance(mock_alerts, list):
            return jsonify(mock_alerts)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"[APP] Error in get_alerts: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ENDPOINTS - INVESTIGATIONS
# ============================================================

@app.route('/api/investigations', methods=['GET'])
def get_investigations():
    """Get all investigations"""
    try:
        investigations = get_all_investigations()
        return jsonify(investigations)
    except Exception as e:
        logger.error(f"[APP] Error in get_investigations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/investigation-details/<investigation_id>', methods=['GET'])
def get_investigation_details_route(investigation_id):
    """Get detailed information about an investigation"""
    try:
        investigation = get_investigation_details(investigation_id)
        if investigation:
            return jsonify(investigation)
        else:
            return jsonify({'error': 'Investigation not found'}), 404
    except Exception as e:
        logger.error(f"[APP] Error in get_investigation_details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-investigation', methods=['POST'])
def start_investigation():
    """Start a new investigation. Creates the investigation record synchronously (fast)
    and returns its ID immediately, then runs the rest of the agent pipeline in a
    background task, streaming progress over Socket.IO as each step completes."""
    try:
        alert_data = request.json

        investigation_id = orchestrator.start_investigation(alert_data)
        if not investigation_id:
            return jsonify({'error': 'Failed to create investigation'}), 500

        def on_step(event):
            socketio.emit('investigation_progress', event)

        def run():
            with app.app_context():
                result = orchestrator.run_investigation(investigation_id, alert_data, on_step=on_step)
                socketio.emit('investigation_complete', {
                    'investigation_id': investigation_id,
                    'alert_id': alert_data.get('alert_id'),
                    'success': result.get('success'),
                    'verdict': result.get('verdict'),
                    'confidence': result.get('verdict_confidence'),
                    'risk_score': result.get('risk_score'),
                    'error': result.get('error'),
                })

        socketio.start_background_task(run)

        socketio.emit('investigation_started', {
            'investigation_id': investigation_id,
            'alert_id': alert_data.get('alert_id'),
        })

        logger.info(f"[APP] Investigation started: {investigation_id}")

        return jsonify({'investigation_id': investigation_id, 'status': 'started'})
    except Exception as e:
        logger.error(f"[APP] Error in start_investigation: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ENDPOINTS - ESCALATIONS
# ============================================================

@app.route('/api/escalations', methods=['GET'])
def get_escalations_route():
    """Get all escalations"""
    try:
        escalations = get_escalations()
        return jsonify(escalations)
    except Exception as e:
        logger.error(f"[APP] Error in get_escalations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/escalate-incident', methods=['POST'])
def escalate_incident():
    """Escalate an incident"""
    try:
        data = request.json
        investigation_id = data.get('investigation_id')

        if not investigation_id:
            return jsonify({'error': 'Investigation ID required'}), 400

        # Get investigation details
        investigation = get_investigation_details(investigation_id)

        if not investigation:
            return jsonify({'error': 'Investigation not found'}), 404

        if investigation.get('escalated_at'):
            return jsonify({'error': 'Investigation already escalated'}), 409

        # Save escalation
        save_escalation(
            investigation_id,
            investigation['alert_id'],
            investigation['verdict'],
            investigation['confidence'],
            investigation['risk_score']
        )

        # Emit event to all connected clients for real-time update
        socketio.emit('incident_escalated', {
            'investigation_id': investigation_id,
            'alert_id': investigation['alert_id'],
            'verdict': investigation['verdict']
        }, skip_sid=None)

        logger.info(f"[APP] Incident escalated: {investigation_id}")

        return jsonify({
            'success': True,
            'message': 'Incident escalated successfully'
        })
    except Exception as e:
        logger.error(f"[APP] Error in escalate_incident: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ENDPOINTS - ACTIONS
# ============================================================

@app.route('/api/mark-resolved', methods=['POST'])
def mark_resolved():
    """Mark incident as resolved"""
    try:
        data = request.json
        investigation_id = data.get('investigation_id')

        if not investigation_id:
            return jsonify({'error': 'Investigation ID required'}), 400

        # Get investigation details
        investigation = get_investigation_details(investigation_id)

        if not investigation:
            return jsonify({'error': 'Investigation not found'}), 404

        # Save resolved status
        save_resolved(investigation_id, investigation['alert_id'], 'Manual resolution')

        # Emit event for real-time update
        socketio.emit('incident_resolved', {
            'investigation_id': investigation_id,
            'alert_id': investigation['alert_id']
        }, skip_sid=None)

        logger.info(f"[APP] Incident marked resolved: {investigation_id}")

        return jsonify({
            'success': True,
            'message': 'Incident marked as resolved'
        })
    except Exception as e:
        logger.error(f"[APP] Error in mark_resolved: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resolved', methods=['GET'])
def get_resolved_route():
    """Get all resolved incidents"""
    try:
        resolved = get_resolved()
        return jsonify(resolved)
    except Exception as e:
        logger.error(f"[APP] Error in get_resolved: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/request-review', methods=['POST'])
def request_review_route():
    """Request review for incident"""
    try:
        data = request.json
        investigation_id = data.get('investigation_id')

        if not investigation_id:
            return jsonify({'error': 'Investigation ID required'}), 400

        # Get investigation details
        investigation = get_investigation_details(investigation_id)

        if not investigation:
            return jsonify({'error': 'Investigation not found'}), 404

        # Save review request
        save_review(investigation_id, investigation['alert_id'], 'Manual review requested')

        # Emit event for real-time update
        socketio.emit('review_requested', {
            'investigation_id': investigation_id,
            'alert_id': investigation['alert_id']
        }, skip_sid=None)

        logger.info(f"[APP] Review requested: {investigation_id}")

        return jsonify({
            'success': True,
            'message': 'Review requested successfully'
        })
    except Exception as e:
        logger.error(f"[APP] Error in request_review: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reviews', methods=['GET'])
def get_reviews_route():
    """Get all review requests"""
    try:
        reviews = get_reviews()
        return jsonify(reviews)
    except Exception as e:
        logger.error(f"[APP] Error in get_reviews: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ENDPOINTS - METRICS
# ============================================================

@app.route('/api/metrics', methods=['GET'])
def get_metrics_route():
    """Get dashboard metrics"""
    try:
        metrics = get_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"[APP] Error in get_metrics: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# SOCKETIO EVENT HANDLERS
# ============================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('[SocketIO] Client connected')
    emit('response', {'data': 'Connected to SOC Dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('[SocketIO] Client disconnected')

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    logger.info("[APP] Starting SOC Alert Automation Dashboard")
    logger.info("[APP] Navigate to http://127.0.0.1:5000")
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
