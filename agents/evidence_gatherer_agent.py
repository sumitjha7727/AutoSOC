import logging
from datetime import datetime

logger = logging.getLogger("soc.evidence_gatherer")

# Suspicious log event types the Verdict Analyzer treats as red flags
FLAGGED_LOG_EVENTS = {
    "MALICIOUS_PROCESS_EXECUTED", "SUSPICIOUS_OUTBOUND_CONNECTION", "FILE_QUARANTINED",
    "LARGE_DATA_TRANSFER", "UNUSUAL_PORT_ACTIVITY", "SUDO_ATTEMPT_FAILED",
    "UNAUTHORIZED_ACCESS_ATTEMPT", "ADMIN_GROUP_MODIFIED",
    "ACCOUNT_LOCKOUT_TRIGGERED", "SUSPICIOUS_LOGIN_PATTERN",
    "EXCESSIVE_DNS_QUERY_VOLUME", "SUSPICIOUS_DNS_SUBDOMAIN_PATTERN", "BEACONING_INTERVAL_DETECTED",
    "MASS_FILE_ENCRYPTION_DETECTED", "RANSOM_NOTE_CREATED", "SHADOW_COPY_DELETION_ATTEMPT",
    "MALICIOUS_LINK_CLICKED", "CREDENTIAL_ENTERED_ON_EXTERNAL_SITE",
    "SEQUENTIAL_PORT_PROBE_DETECTED",
}

# Representative mock log patterns per alert type, tied to the affected user
LOG_PATTERNS = {
    "SUSPICIOUS_LOGIN_FROM_NEW_LOCATION": lambda user: [
        {"event_type": "FAILED_LOGIN", "timestamp": "2026-09-09 14:23:00", "user": user, "attempts": 5},
        {"event_type": "SUCCESSFUL_LOGIN", "timestamp": "2026-09-09 14:25:00", "user": user},
        {"event_type": "LARGE_DATA_TRANSFER", "timestamp": "2026-09-09 14:26:00", "user": user, "file_size_gb": 2.5},
    ],
    "MALWARE_DETECTED": lambda user: [
        {"event_type": "MALICIOUS_PROCESS_EXECUTED", "timestamp": "2026-09-09 14:25:10", "user": user, "process": "svch0st.exe"},
        {"event_type": "SUSPICIOUS_OUTBOUND_CONNECTION", "timestamp": "2026-09-09 14:25:15", "user": user, "destination_port": 4444},
        {"event_type": "FILE_QUARANTINED", "timestamp": "2026-09-09 14:25:40", "user": user, "file": "invoice.exe"},
    ],
    "UNUSUAL_NETWORK_TRAFFIC": lambda user: [
        {"event_type": "LARGE_DATA_TRANSFER", "timestamp": "2026-09-09 14:27:05", "user": user, "file_size_gb": 8.2},
        {"event_type": "UNUSUAL_PORT_ACTIVITY", "timestamp": "2026-09-09 14:27:20", "user": user, "port": 8081},
        {"event_type": "SUCCESSFUL_LOGIN", "timestamp": "2026-09-09 14:26:50", "user": user},
    ],
    "PRIVILEGE_ESCALATION_ATTEMPT": lambda user: [
        {"event_type": "SUDO_ATTEMPT_FAILED", "timestamp": "2026-09-09 14:29:05", "user": user, "attempts": 3},
        {"event_type": "UNAUTHORIZED_ACCESS_ATTEMPT", "timestamp": "2026-09-09 14:29:20", "user": user, "target": "/etc/shadow"},
        {"event_type": "ADMIN_GROUP_MODIFIED", "timestamp": "2026-09-09 14:29:45", "user": user, "group": "domain-admins"},
    ],
    "NORMAL_ACTIVITY": lambda user: [
        {"event_type": "SUCCESSFUL_LOGIN", "timestamp": "2026-09-09 14:31:00", "user": user},
        {"event_type": "FILE_ACCESS", "timestamp": "2026-09-09 14:32:00", "user": user, "file": "quarterly_report.xlsx"},
        {"event_type": "LOGOUT", "timestamp": "2026-09-09 15:02:00", "user": user},
    ],
    "BRUTE_FORCE_ATTACK": lambda user: [
        {"event_type": "FAILED_LOGIN", "timestamp": "2026-09-09 14:35:00", "user": user, "attempts": 47},
        {"event_type": "ACCOUNT_LOCKOUT_TRIGGERED", "timestamp": "2026-09-09 14:35:30", "user": user},
        {"event_type": "SUSPICIOUS_LOGIN_PATTERN", "timestamp": "2026-09-09 14:35:45", "user": user, "unique_source_ips": 1},
    ],
    "DNS_TUNNELING": lambda user: [
        {"event_type": "EXCESSIVE_DNS_QUERY_VOLUME", "timestamp": "2026-09-09 14:40:00", "user": user, "queries_per_minute": 850},
        {"event_type": "SUSPICIOUS_DNS_SUBDOMAIN_PATTERN", "timestamp": "2026-09-09 14:40:10", "user": user, "domain": "a8f3d1.datax-sync.net"},
        {"event_type": "BEACONING_INTERVAL_DETECTED", "timestamp": "2026-09-09 14:40:20", "user": user, "interval_seconds": 60},
    ],
    "RANSOMWARE_ACTIVITY": lambda user: [
        {"event_type": "MASS_FILE_ENCRYPTION_DETECTED", "timestamp": "2026-09-09 14:45:00", "user": user, "files_encrypted": 4213},
        {"event_type": "RANSOM_NOTE_CREATED", "timestamp": "2026-09-09 14:45:05", "user": user, "file": "README_DECRYPT.txt"},
        {"event_type": "SHADOW_COPY_DELETION_ATTEMPT", "timestamp": "2026-09-09 14:45:10", "user": user},
    ],
    "PHISHING_LINK_CLICKED": lambda user: [
        {"event_type": "MALICIOUS_LINK_CLICKED", "timestamp": "2026-09-09 14:50:00", "user": user, "url": "hxxp://secure-office365-login.net"},
        {"event_type": "CREDENTIAL_ENTERED_ON_EXTERNAL_SITE", "timestamp": "2026-09-09 14:50:15", "user": user},
    ],
    "PORT_SCAN_DETECTED": lambda user: [
        {"event_type": "SEQUENTIAL_PORT_PROBE_DETECTED", "timestamp": "2026-09-09 14:55:00", "user": user, "ports_scanned": 24, "target_range": "10.0.7.0/24"},
    ],
}

# Deterministic mock geolocation lookup, keyed by IP
IP_GEO_LOOKUP = {
    "202.91.87.45": {"country": "China", "city": "Beijing"},
    "192.168.1.105": {"country": "Internal", "city": "Internal Network"},
    "10.0.1.50": {"country": "Internal", "city": "Internal Network"},
    "172.16.0.25": {"country": "Internal", "city": "Internal Network"},
    "203.0.113.45": {"country": "USA", "city": "Headquarters"},
    "185.220.101.13": {"country": "Russia", "city": "Moscow"},
    "192.168.2.44": {"country": "Internal", "city": "Internal Network"},
    "91.243.85.22": {"country": "Romania", "city": "Bucharest"},
    "45.155.204.9": {"country": "Netherlands", "city": "Amsterdam"},
    "10.0.7.19": {"country": "Internal", "city": "Internal Network"},
}


def _is_private_ip(ip):
    if not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    return (
        octets[0] == 10
        or (octets[0] == 172 and 16 <= octets[1] <= 31)
        or (octets[0] == 192 and octets[1] == 168)
    )


class EvidenceGathererAgent:
    def __init__(self):
        self.evidence_collected = []
        self.tasks_completed = 0
        self.errors = 0
        logger.info("Evidence Gatherer initialized")

    def gather_all_evidence(self, investigation_id, alert_data, ip_verdicts, user_baseline):
        try:
            evidence_list = []
            log_analysis = self._analyze_logs(alert_data)
            evidence_list.append({"evidence_type": "LOG_ANALYSIS", "data": log_analysis})
            ip_reputation = self._check_ip_reputation(alert_data.get("source_ip"), ip_verdicts)
            evidence_list.append({"evidence_type": "IP_REPUTATION", "data": ip_reputation})
            geolocation = self._get_geolocation(alert_data.get("source_ip"))
            evidence_list.append({"evidence_type": "GEOLOCATION", "data": geolocation})
            user_baseline_evidence = self._check_user_baseline(alert_data.get("affected_user"), user_baseline)
            evidence_list.append({"evidence_type": "USER_BASELINE", "data": user_baseline_evidence})
            self.evidence_collected = evidence_list
            self.tasks_completed += 1
            return evidence_list
        except Exception as e:
            self.errors += 1
            logger.error(f"Error: {e}")
            return []

    def _analyze_logs(self, alert_data):
        user = alert_data.get("affected_user", "unknown")
        alert_type = alert_data.get("alert_type", "")
        pattern_fn = LOG_PATTERNS.get(alert_type, LOG_PATTERNS["NORMAL_ACTIVITY"])
        raw_logs = pattern_fn(user)
        flagged = [log for log in raw_logs if log["event_type"] in FLAGGED_LOG_EVENTS or (log["event_type"] == "FAILED_LOGIN" and log.get("attempts", 0) >= 3)]
        return {"raw_logs": raw_logs, "logs_found": len(raw_logs), "flagged_events": len(flagged)}

    def _check_ip_reputation(self, source_ip, ip_verdicts):
        if not source_ip or source_ip not in ip_verdicts:
            return {"ip": source_ip, "threat_level": "LOW", "reputation_score": 10, "abuse_reports": 0}
        entry = dict(ip_verdicts.get(source_ip, {}))
        entry["ip"] = source_ip
        return entry

    def _get_geolocation(self, source_ip):
        geo = IP_GEO_LOOKUP.get(source_ip)
        if geo:
            return {"ip": source_ip, "country": geo["country"], "city": geo["city"], "is_internal": geo["country"] == "Internal"}
        is_internal = _is_private_ip(source_ip)
        return {
            "ip": source_ip,
            "country": "Internal" if is_internal else "Unknown",
            "city": "Internal Network" if is_internal else "Unknown External Location",
            "is_internal": is_internal,
        }

    def _check_user_baseline(self, user, user_baseline):
        if not user or user not in user_baseline:
            return {"user": user, "department": "UNKNOWN", "typical_login_locations": [], "never_accessed_from_countries": [], "known": False}
        entry = dict(user_baseline.get(user, {}))
        entry["user"] = user
        entry["known"] = True
        return entry

    def get_status(self):
        return {
            "agent_name": "Evidence Gatherer",
            "status": "Online",
            "evidence_collected": len(self.evidence_collected),
            "tasks_completed": self.tasks_completed,
            "errors": self.errors,
            "last_updated": datetime.now().isoformat(),
        }
