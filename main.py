"""
SOC Alert Automation System - Main Entry Point
Multi-Agent Orchestration System for Security Operations Center
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Import configuration
from config.settings import config
from utils.database import init_db, get_investigation

# Setup logging
def setup_logging():
    """Configure logging for the application"""
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("./logs/soc_automation.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================
# Application Information
# ============================================

APP_NAME = "SOC Alert Automation System"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Multi-Agent Orchestration for Security Operations Center"

# ============================================
# Mock Data Loader
# ============================================

def load_mock_data():
    """Load mock data from JSON files"""
    try:
        with open('./data/mock_alerts.json', 'r') as f:
            alerts = json.load(f)
        
        with open('./data/mock_ip_verdicts.json', 'r') as f:
            ip_verdicts = json.load(f)
        
        with open('./data/mock_user_baseline.json', 'r') as f:
            user_baseline = json.load(f)
        
        logger.info(f"Loaded {len(alerts)} mock alerts")
        logger.info(f"Loaded {len(ip_verdicts)} IP verdicts")
        logger.info(f"Loaded {len(user_baseline)} user baselines")

        return {
            'alerts': alerts,
            'ip_verdicts': ip_verdicts,
            'user_baseline': user_baseline
        }
    except Exception as e:
        logger.error(f"Error loading mock data: {e}")
        return None

# ============================================
# Database Status Check
# ============================================

def check_database():
    """Check if database is properly initialized"""
    try:
        init_db()
        get_investigation("test-query")  # no-op lookup; None result is fine, exceptions are not
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

# ============================================
# Application Initialization
# ============================================

def initialize_application():
    """Initialize the SOC automation application"""
    logger.info("=" * 60)
    logger.info(f"{APP_NAME} v{APP_VERSION}")
    logger.info("=" * 60)

    # Check configuration
    logger.info("Configuration loaded from config.yaml")
    logger.info(f"   Environment: {config.get('app.environment', 'unknown')}")
    logger.info(f"   Debug Mode: {config.get('app.debug', False)}")
    logger.info(f"   Mock Mode: {config.get('mock_mode.enabled', True)}")

    # Check database
    if not check_database():
        logger.error("Application initialization failed: Database error")
        return False

    # Load mock data
    mock_data = load_mock_data()
    if not mock_data:
        logger.error("Application initialization failed: Could not load mock data")
        return False

    logger.info("=" * 60)
    logger.info("Application initialized successfully")
    logger.info("=" * 60)
    
    return True

# ============================================
# Application Status
# ============================================

def get_app_status():
    """Get current application status"""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mode": "mock" if config.get('mock_mode.enabled', True) else "production",
        "database": "initialized"
    }

# ============================================
# Main Entry Point
# ============================================

def main():
    """Main entry point for the application"""
    
    # Initialize application
    if not initialize_application():
        logger.error("Failed to initialize application")
        sys.exit(1)
    
    # Print application status
    status = get_app_status()
    logger.info(f"Application Status: {json.dumps(status, indent=2)}")
    
    # Note: Flask app will be created in web/app.py
    logger.info("Next Step: Run the Flask web server")
    logger.info("   Command: python -m flask run")
    logger.info("   Access: http://127.0.0.1:5000")

if __name__ == "__main__":
    main()