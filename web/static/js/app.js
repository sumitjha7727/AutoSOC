// Initialize SocketIO connection
const socket = io();

// ============================================================
// PAGE LOAD - Initialize everything
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('[APP] Page loaded - initializing...');
    loadAllAlerts();
    loadAllInvestigations();
    loadAllEscalations();
    loadAllResolved();
    loadAllReviews();
    loadMetrics();
});

// ============================================================
// TAB SWITCHING
// ============================================================
function switchTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));
    
    // Remove active class from all tab buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(btn => btn.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    
    // Mark button as active
    event.target.classList.add('active');
    
    // Load data for the tab
    if (tabName === 'investigations') {
        loadAllInvestigations();
    } else if (tabName === 'escalations') {
        loadAllEscalations();
    } else if (tabName === 'resolved') {
        loadAllResolved();
    } else if (tabName === 'reviews') {
        loadAllReviews();
    } else if (tabName === 'metrics') {
        loadMetrics();
    }
    
    console.log(`[APP] Switched to tab: ${tabName}`);
}

// ============================================================
// LOAD ALL ALERTS
// ============================================================
async function loadAllAlerts() {
    try {
        const response = await fetch('/api/alerts');
        const alerts = await response.json();
        
        const dropdown = document.getElementById('alertDropdown');
        dropdown.innerHTML = '<option value="">-- Select Alert --</option>';
        
        alerts.forEach(alert => {
            const option = document.createElement('option');
            option.value = JSON.stringify(alert);
            option.textContent = `${alert.alert_id} - ${alert.alert_type} (${alert.severity})`;
            dropdown.appendChild(option);
        });
        
        console.log(`[APP] Loaded ${alerts.length} alerts`);
    } catch (error) {
        console.error('[APP] Error loading alerts:', error);
    }
}

// ============================================================
// UPDATE ALERT INFO (when dropdown changes)
// ============================================================
function updateAlertInfo() {
    const dropdown = document.getElementById('alertDropdown');
    if (dropdown.value) {
        const alert = JSON.parse(dropdown.value);
        console.log('[APP] Selected alert:', alert);
    }
}

// ============================================================
// START INVESTIGATION (streams live progress via Socket.IO)
// ============================================================
let investigationInProgress = false;

function resetStartButton() {
    investigationInProgress = false;
    const startBtn = document.getElementById('startInvestigationBtn');
    startBtn.disabled = false;
    startBtn.textContent = 'Start Investigation';
}

async function startInvestigation() {
    const dropdown = document.getElementById('alertDropdown');
    const startBtn = document.getElementById('startInvestigationBtn');

    if (!dropdown.value) {
        alert('Please select an alert first!');
        return;
    }

    if (investigationInProgress) {
        return; // guard against double-submission while one is already running
    }

    const alertData = JSON.parse(dropdown.value);
    const statusBox = document.getElementById('statusBox');
    const resultsBox = document.getElementById('resultsBox');

    investigationInProgress = true;
    startBtn.disabled = true;
    startBtn.textContent = 'Investigating...';
    statusBox.innerHTML = '<p><span class="loading"></span> Investigation started...</p><ul id="progressLog"></ul>';
    statusBox.classList.add('pending');
    statusBox.classList.remove('error');
    resultsBox.innerHTML = '';

    try {
        // Call API to start investigation - returns immediately with just the ID;
        // the actual pipeline runs in the background and streams progress below.
        const response = await fetch('/api/start-investigation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(alertData)
        });

        const result = await response.json();

        if (response.ok) {
            window.currentInvestigationId = result.investigation_id;
            loadAllInvestigations();
            console.log('[APP] Investigation started:', result);
            // Further updates arrive via the investigation_progress / investigation_complete
            // socket events handled below.
        } else {
            statusBox.innerHTML = `<p style="color: #ff6b6b;">Error: ${result.error}</p>`;
            statusBox.classList.add('error');
            resetStartButton();
        }
    } catch (error) {
        console.error('[APP] Error starting investigation:', error);
        statusBox.innerHTML = `<p style="color: #ff6b6b;">Error: ${error.message}</p>`;
        statusBox.classList.add('error');
        resetStartButton();
    }
}

// ============================================================
// LOAD INVESTIGATION RESULTS
// ============================================================
async function loadInvestigationResults(investigationId) {
    try {
        const response = await fetch(`/api/investigation-details/${investigationId}`);
        const investigation = await response.json();
        
        if (investigation) {
            // Display results in the results box
            const resultsBox = document.getElementById('resultsBox');
            resultsBox.innerHTML = `
                <div class="results-box">
                    <h3>Summary</h3>
                    <p><strong>Investigation ID:</strong> ${investigation.investigation_id}</p>
                    <p><strong>Alert ID:</strong> ${investigation.alert_id}</p>
                    <p><strong>Verdict:</strong> ${investigation.verdict || 'N/A'}</p>
                    <p><strong>Confidence:</strong> ${investigation.confidence ? (investigation.confidence * 100).toFixed(0) + '%' : 'N/A'}</p>
                    <button class="view-details-btn" onclick="viewDetails('${investigation.investigation_id}')">View Details</button>
                </div>
            `;
            
            // Store current investigation ID for modal
            window.currentInvestigationId = investigation.investigation_id;
            
            console.log('[APP] Results loaded:', investigation);
        }
    } catch (error) {
        console.error('[APP] Error loading results:', error);
    }
}

// ============================================================
// VIEW DETAILS - Open Modal
// ============================================================
async function viewDetails(investigationId) {
    try {
        const response = await fetch(`/api/investigation-details/${investigationId}`);
        const investigation = await response.json();
        
        if (investigation) {
            // Populate modal with investigation details
            document.getElementById('modalInvestigationId').textContent = investigation.investigation_id;
            document.getElementById('modalAlertId').textContent = investigation.alert_id;
            document.getElementById('modalAlertType').textContent = investigation.alert_type;
            document.getElementById('modalUserEmail').textContent = investigation.affected_user;
            document.getElementById('modalIpAddress').textContent = investigation.source_ip;

            document.getElementById('modalVerdict').textContent = investigation.verdict || 'N/A';
            document.getElementById('modalConfidence').textContent = investigation.confidence ? (investigation.confidence * 100).toFixed(0) : 'N/A';
            document.getElementById('modalRiskScore').textContent = investigation.risk_score ? investigation.risk_score.toFixed(1) : 'N/A';
            document.getElementById('modalReasoning').textContent = investigation.reasoning || 'N/A';

            // Render real evidence collected by the agents for this investigation
            const evidenceContainer = document.getElementById('modalEvidenceContainer');
            if (investigation.evidence && investigation.evidence.length > 0) {
                evidenceContainer.innerHTML = investigation.evidence.map(ev => `
                    <p><strong>${ev.evidence_type}</strong></p>
                    <pre>${JSON.stringify(ev.data, null, 2)}</pre>
                `).join('');
            } else {
                evidenceContainer.innerHTML = '<p>No evidence recorded.</p>';
            }

            // Render the real investigation timeline
            const timelineEl = document.getElementById('modalTimeline');
            if (investigation.timeline && investigation.timeline.length > 0) {
                timelineEl.innerHTML = investigation.timeline.map(ev => `
                    <li><strong>${ev.agent_name}:</strong> ${ev.description} <em>(${ev.event_type})</em></li>
                `).join('');
            } else {
                timelineEl.innerHTML = '<li>No timeline events recorded.</li>';
            }

            // Disable Escalate if this investigation was already escalated (manually or
            // automatically) - the button is a single DOM node reused across every
            // investigation, so its state must be reset fresh on every open.
            const escalateBtn = document.querySelector('.modal-buttons .escalate');
            if (escalateBtn) {
                if (investigation.escalated_at) {
                    escalateBtn.textContent = 'Already Escalated';
                    escalateBtn.disabled = true;
                } else {
                    escalateBtn.textContent = 'Escalate';
                    escalateBtn.disabled = false;
                }
            }

            // Store investigation ID for action buttons
            window.currentInvestigationId = investigationId;

            // Show modal
            document.getElementById('detailsModal').classList.add('show');

            console.log('[APP] Modal opened for investigation:', investigationId);
        }
    } catch (error) {
        console.error('[APP] Error loading investigation details:', error);
    }
}

// ============================================================
// CLOSE MODAL
// ============================================================
function closeModal() {
    document.getElementById('detailsModal').classList.remove('show');
    console.log('[APP] Modal closed');
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('detailsModal');
    if (event.target === modal) {
        modal.classList.remove('show');
    }
};

// ============================================================
// ESCALATE INCIDENT
// ============================================================
async function escalateIncident(btn) {
    const investigationId = window.currentInvestigationId;

    if (!investigationId) {
        alert('No investigation selected');
        return;
    }

    try {
        // Show loading state
        btn.textContent = 'Escalating...';
        btn.disabled = true;

        const response = await fetch('/api/escalate-incident', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ investigation_id: investigationId })
        });

        const result = await response.json();

        if (response.ok) {
            alert('Incident escalated successfully!');
            closeModal();
            loadAllEscalations(); // Refresh escalations list
            loadAllInvestigations();
            loadMetrics();
            console.log('[APP] Incident escalated:', result);
        } else {
            alert(`Error: ${result.error}`);
            btn.textContent = 'Escalate';
            btn.disabled = false;
        }
    } catch (error) {
        console.error('[APP] Error escalating incident:', error);
        alert(`Error: ${error.message}`);
        btn.textContent = 'Escalate';
        btn.disabled = false;
    }
}

// ============================================================
// MARK RESOLVED
// ============================================================
async function markResolved(btn) {
    const investigationId = window.currentInvestigationId;

    if (!investigationId) {
        alert('No investigation selected');
        return;
    }

    try {
        // Show loading state
        btn.textContent = 'Marking...';
        btn.disabled = true;

        const response = await fetch('/api/mark-resolved', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ investigation_id: investigationId })
        });

        const result = await response.json();

        if (response.ok) {
            alert('Incident marked as resolved!');
            closeModal();
            loadAllInvestigations(); // Refresh investigations list
            loadAllResolved();
            loadMetrics();
            console.log('[APP] Incident marked resolved:', result);
        } else {
            alert(`Error: ${result.error}`);
        }

        // Always reset - unlike Escalate, resolving has no persisted "already done"
        // state to preserve, so the button should be clickable again either way.
        btn.textContent = 'Mark Resolved';
        btn.disabled = false;
    } catch (error) {
        console.error('[APP] Error marking resolved:', error);
        alert(`Error: ${error.message}`);
        btn.textContent = 'Mark Resolved';
        btn.disabled = false;
    }
}

// ============================================================
// REQUEST REVIEW
// ============================================================
async function requestReview(btn) {
    const investigationId = window.currentInvestigationId;

    if (!investigationId) {
        alert('No investigation selected');
        return;
    }

    try {
        // Show loading state
        btn.textContent = 'Requesting...';
        btn.disabled = true;

        const response = await fetch('/api/request-review', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ investigation_id: investigationId })
        });

        const result = await response.json();

        if (response.ok) {
            alert('Review requested successfully!');
            closeModal();
            loadAllReviews();
            console.log('[APP] Review requested:', result);
        } else {
            alert(`Error: ${result.error}`);
        }

        // Always reset - Request Review has no persisted "already done" state either.
        btn.textContent = 'Request Review';
        btn.disabled = false;
    } catch (error) {
        console.error('[APP] Error requesting review:', error);
        alert(`Error: ${error.message}`);
        btn.textContent = 'Request Review';
        btn.disabled = false;
    }
}

// ============================================================
// LOAD ALL INVESTIGATIONS
// ============================================================
async function loadAllInvestigations() {
    try {
        const response = await fetch('/api/investigations');
        const investigations = await response.json();
        
        const tbody = document.getElementById('investigationsTable');
        
        if (investigations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #999;">No investigations yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = investigations.map(inv => `
            <tr>
                <td>${inv.investigation_id}</td>
                <td>${inv.alert_id}</td>
                <td>${inv.alert_type}</td>
                <td>${inv.affected_user}</td>
                <td>${inv.source_ip}</td>
                <td><strong style="color: ${inv.status === 'COMPLETED' ? '#51cf66' : '#ffd43b'}">${inv.status}</strong></td>
                <td>${inv.verdict || '-'}</td>
                <td><button onclick="viewDetails('${inv.investigation_id}')">View</button></td>
            </tr>
        `).join('');
        
        console.log(`[APP] Loaded ${investigations.length} investigations`);
    } catch (error) {
        console.error('[APP] Error loading investigations:', error);
    }
}

// ============================================================
// SEARCH INVESTIGATIONS
// ============================================================
async function searchInvestigations() {
    const searchTerm = document.getElementById('investigationSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#investigationsTable tr');
    
    rows.forEach(row => {
        const investigationId = row.cells[0].textContent.toLowerCase();
        if (investigationId.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// ============================================================
// LOAD ALL ESCALATIONS
// ============================================================
async function loadAllEscalations() {
    try {
        const response = await fetch('/api/escalations');
        const escalations = await response.json();
        
        const tbody = document.getElementById('escalationsTable');
        
        if (escalations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">No escalations yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = escalations.map(esc => `
            <tr>
                <td>${esc.investigation_id}</td>
                <td>${esc.alert_id}</td>
                <td>${esc.verdict}</td>
                <td>${(esc.confidence * 100).toFixed(0)}%</td>
                <td>${esc.risk_score.toFixed(1)}/10.0</td>
                <td>${new Date(esc.escalated_at).toLocaleString()}</td>
            </tr>
        `).join('');
        
        console.log(`[APP] Loaded ${escalations.length} escalations`);
    } catch (error) {
        console.error('[APP] Error loading escalations:', error);
    }
}

// ============================================================
// LOAD ALL RESOLVED INCIDENTS
// ============================================================
async function loadAllResolved() {
    try {
        const response = await fetch('/api/resolved');
        const resolved = await response.json();

        const tbody = document.getElementById('resolvedTable');

        if (resolved.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">No resolved incidents yet</td></tr>';
            return;
        }

        tbody.innerHTML = resolved.map(r => `
            <tr>
                <td>${r.investigation_id}</td>
                <td>${r.alert_id}</td>
                <td>${r.alert_type || '-'}</td>
                <td>${r.verdict || '-'}</td>
                <td>${r.resolution_reason || '-'}</td>
                <td>${new Date(r.resolved_at).toLocaleString()}</td>
            </tr>
        `).join('');

        console.log(`[APP] Loaded ${resolved.length} resolved incidents`);
    } catch (error) {
        console.error('[APP] Error loading resolved incidents:', error);
    }
}

// ============================================================
// LOAD ALL REVIEW REQUESTS
// ============================================================
async function loadAllReviews() {
    try {
        const response = await fetch('/api/reviews');
        const reviews = await response.json();

        const tbody = document.getElementById('reviewsTable');

        if (reviews.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">No review requests yet</td></tr>';
            return;
        }

        tbody.innerHTML = reviews.map(rv => `
            <tr>
                <td>${rv.investigation_id}</td>
                <td>${rv.alert_id}</td>
                <td>${rv.alert_type || '-'}</td>
                <td>${rv.verdict || '-'}</td>
                <td>${rv.review_reason || '-'}</td>
                <td>${new Date(rv.reviewed_at).toLocaleString()}</td>
            </tr>
        `).join('');

        console.log(`[APP] Loaded ${reviews.length} review requests`);
    } catch (error) {
        console.error('[APP] Error loading review requests:', error);
    }
}

// ============================================================
// LOAD METRICS
// ============================================================
async function loadMetrics() {
    try {
        const response = await fetch('/api/metrics');
        const metrics = await response.json();
        
        document.getElementById('metricTotalAlerts').textContent = metrics.total_alerts;
        document.getElementById('metricTruePositives').textContent = metrics.true_positives;
        document.getElementById('metricFalsePositives').textContent = metrics.false_positives;
        document.getElementById('metricEscalations').textContent = metrics.escalations;
        document.getElementById('metricInconclusive').textContent = metrics.inconclusive;
        
        console.log('[APP] Metrics loaded:', metrics);
    } catch (error) {
        console.error('[APP] Error loading metrics:', error);
    }
}

// ============================================================
// REAL-TIME UPDATES via SocketIO
// ============================================================
socket.on('connect', function() {
    console.log('[SocketIO] Connected to server');
});

socket.on('investigation_started', function(data) {
    console.log('[SocketIO] Investigation started:', data);
    loadAllInvestigations();
});

socket.on('investigation_progress', function(data) {
    if (data.investigation_id !== window.currentInvestigationId) return;
    const log = document.getElementById('progressLog');
    if (log) {
        const li = document.createElement('li');
        li.textContent = `[${data.agent_name}] ${data.description}`;
        log.appendChild(li);
    }
    console.log('[SocketIO] Progress:', data);
});

socket.on('investigation_complete', function(data) {
    if (data.investigation_id !== window.currentInvestigationId) return;

    const statusBox = document.getElementById('statusBox');
    if (data.success) {
        statusBox.innerHTML = `<p style="color: #51cf66;">Investigation complete! ID: ${data.investigation_id}</p>`;
        statusBox.classList.remove('pending');
        loadInvestigationResults(data.investigation_id);
    } else {
        statusBox.innerHTML = `<p style="color: #ff6b6b;">Error: ${data.error || 'Investigation failed'}</p>`;
        statusBox.classList.add('error');
    }

    resetStartButton();
    loadAllInvestigations();
    loadAllEscalations();
    loadMetrics();

    console.log('[SocketIO] Investigation complete:', data);
});

socket.on('incident_escalated', function(data) {
    console.log('[SocketIO] Incident escalated:', data);
    loadAllEscalations();
    loadMetrics();
});

socket.on('incident_resolved', function(data) {
    console.log('[SocketIO] Incident resolved:', data);
    loadAllInvestigations();
    loadAllResolved();
    loadMetrics();
});

socket.on('review_requested', function(data) {
    console.log('[SocketIO] Review requested:', data);
    loadAllReviews();
});

socket.on('disconnect', function() {
    console.log('[SocketIO] Disconnected from server');
});

console.log('[APP] Application initialized successfully');