
let currentTab = 'single';

function switchTab(tab) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
  });
  document.querySelectorAll('.tab-button').forEach(button => {
    button.classList.remove('active');
  });

  // Show selected tab
  document.getElementById(tab + '-tab').classList.add('active');
  event.target.classList.add('active');
  currentTab = tab;
}

async function checkSingleEmail() {
  const email = document.getElementById('singleEmail').value.trim();
  const resultDiv = document.getElementById('singleResult');

  if (!email) {
    showResult(resultDiv, 'Please enter an email address', 'warning');
    return;
  }

  // Show loading
  const button = event.target;
  const originalText = button.innerHTML;
  button.innerHTML = '<span class="loading"></span> Checking...';
  button.disabled = true;

  try {
    const response = await fetch('/v2/api/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email: email })
    });

    const data = await response.json();

    if (response.ok) {
      displaySingleResult(resultDiv, data);
    } else {
      showResult(resultDiv, data.error || 'Error checking email', 'danger');
    }
  } catch (error) {
    showResult(resultDiv, 'Network error: ' + error.message, 'danger');
  } finally {
    button.innerHTML = originalText;
    button.disabled = false;
  }
}

async function checkBulkEmails() {
  const emailsText = document.getElementById('bulkEmails').value.trim();
  const resultDiv = document.getElementById('bulkResult');

  if (!emailsText) {
    showResult(resultDiv, 'Please enter email addresses', 'warning');
    return;
  }

  const emails = emailsText.split('\n').map(e => e.trim()).filter(e => e);

  if (emails.length === 0) {
    showResult(resultDiv, 'No valid emails found', 'warning');
    return;
  }

  // Show loading
  const button = event.target;
  const originalText = button.innerHTML;
  button.innerHTML = '<span class="loading"></span> Checking...';
  button.disabled = true;

  try {
    const response = await fetch('/v2/api/bulk-check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ emails: emails })
    });

    const data = await response.json();
    if (response.ok) {
      displayBulkResult(resultDiv, data);
    } else {
      showResult(resultDiv, data.error || 'Error checking emails', 'danger');
    }
  } catch (error) {
    showResult(resultDiv, 'Network error: ' + error.message, 'danger');
  } finally {
    button.innerHTML = originalText;
    button.disabled = false;
  }
}

function displaySingleResult(resultDiv, data) {
  const riskClass = getRiskClass(data.risk_level);
  const disposableText = data.is_disposable ? 'Yes' : 'No';
  const validText = data.is_valid_format ? 'Yes' : 'No';

  let checksHtml = '';
  if (data.checks) {
    checksHtml = `
            <div style="margin-top: 15px;">
                <strong>Detailed Checks:</strong>
                <ul style="margin-left: 20px; margin-top: 5px;">
                    <li>Domain Blacklisted: ${data.checks.domain_blacklist ? 'Yes' : 'No'}</li>
                    <li>Domain Whitelisted: ${data.checks.domain_whitelist ? 'Yes' : 'No'}</li>
                    <li>MX Record Exists: ${data.checks.mx_record_exists === null ? 'Unknown' : (data.checks.mx_record_exists ? 'Yes' : 'No')}</li>
                </ul>
            </div>
        `;
  }

  resultDiv.innerHTML = `
        <strong>Email:</strong> ${data.email}<br>
        <strong>Disposable:</strong> ${disposableText} <span class="risk-indicator risk-${data.risk_level}">${data.risk_level.toUpperCase()}</span><br>
        <strong>Valid Format:</strong> ${validText}<br>
        <strong>Domain:</strong> ${data.domain || 'N/A'}<br>
        <strong>Risk Score:</strong> ${data.risk_score}/100<br>
        ${checksHtml}
    `;

  resultDiv.className = `result-card ${riskClass}`;
  resultDiv.style.display = 'block';
}

function displayBulkResult(resultDiv, data) {
  const summary = data.summary;
  let resultsHtml = '';

  data.results.forEach(result => {
    const riskLevel = result.risk_level || 'unknown';
    const riskClass = getRiskClass(riskLevel);
    const riskBadge = `<span class="risk-indicator risk-${riskClass}">${riskLevel.toUpperCase()}</span>`;

    if (result.error) {
      resultsHtml += `
                <div style="margin: 10px 0px; padding: 10px; background: #ffe0e0; border-radius: 5px; color: #721c24;">
                    <strong>${result.email}</strong> - <em>Error</em>: ${result.error}
                </div>
            `;
    } else {
      const disposableText = result.is_disposable ? 'Disposable' : 'Valid';
      resultsHtml += `
                <div style="margin: 10px 0px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                    <strong>${result.email}</strong> - ${disposableText}
                    ${riskBadge}
                    (Risk: ${result.risk_score ?? 'N/A'}/100)
                </div>
            `;
    }
  });

  // Risk distribution display
  const riskDist = summary.risk_distribution || {};
  const riskStats = `
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px;">
            <div><strong>Low:</strong> ${riskDist.low || 0}</div>
            <div><strong>Medium:</strong> ${riskDist.medium || 0}</div>
            <div><strong>High:</strong> ${riskDist.high || 0}</div>
        </div>
    `;

  resultDiv.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h4>Summary:</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 10px;">
                <div><strong>Total:</strong> ${summary.total_checked}</div>
                <div><strong>Valid:</strong> ${summary.valid_count}</div>
                <div><strong>Disposable:</strong> ${summary.disposable_count}</div>
                <div><strong>Invalid:</strong> ${summary.invalid_count}</div>
                <div><strong>Errors:</strong> ${summary.error_count}</div>
            </div>
            ${riskStats}
        </div>
        <div>
            <h4>Results:</h4>
            ${resultsHtml}
        </div>
    `;

  resultDiv.className = 'result-card info';
  resultDiv.style.display = 'block';
}


function getRiskClass(riskLevel) {
  switch ((riskLevel || '').toLowerCase()) {
    case 'low': return 'low';
    case 'medium': return 'medium';
    case 'high': return 'high';
    case 'critical': return 'critical';
    default: return 'info';
  }
}

function showResult(resultDiv, message, type) {
  resultDiv.innerHTML = message;
  resultDiv.className = `result-card ${type}`;
  resultDiv.style.display = 'block';
}

async function loadStats() {
  try {
    const response = await fetch('/v2/api/stats');
    const data = await response.json();
    document.getElementById('disposableCount').textContent = data.disposable_domains_count ?? '-';
    document.getElementById('whitelistCount').textContent = data.whitelist_domains_count ?? '-';
    document.getElementById('cacheSize').textContent = data.cache_size ?? '-';

    const uptimeSeconds = data.system_info?.uptime_seconds;

    let uptimeDisplay = '-';
    let uptimeLabel = 'Uptime';

    if (uptimeSeconds != null) {
      if (uptimeSeconds < 3600) {
        const minutes = Math.round(uptimeSeconds / 60);
        uptimeDisplay = `${minutes} min`;
        uptimeLabel = 'Uptime (minutes)';
      } else {
        const hours = Math.round(uptimeSeconds / 3600);
        uptimeDisplay = `${hours} hr`;
        uptimeLabel = 'Uptime (hours)';
      }
    }

    document.getElementById('uptime').textContent = uptimeDisplay;
    document.getElementById('uptimeLabel').textContent = uptimeLabel;
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}
// Convert string to title case
function toTitleCase(str) {
  return str
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

async function checkHealth() {
  const healthContainer = document.getElementById('healthContainer');
  healthContainer.innerHTML = '<p><span class="loading"></span> Checking system health...</p>';

  try {
    const response = await fetch('/v2/api/health');
    const data = await response.json();

    let healthHtml = `
            <div class="health-status health-${data.status === 'healthy' ? 'healthy' : 'unhealthy'}">
                <i class="fas fa-${data.status === 'healthy' ? 'check-circle' : 'exclamation-circle'}"></i>
                Overall Status: ${toTitleCase(data.status)}
            </div>
        `;

    if (data.checks) {
      healthHtml += '<div style="margin-top: 15px;"><strong>Detailed Checks:</strong></div>';
      Object.entries(data.checks).forEach(([key, check]) => {
        healthHtml += `
                    <div class="health-status health-${check.status}">
                        <strong>${toTitleCase(key.replace(/_/g, ' '))}:</strong> ${check.message}
                    </div>
                `;
      });
    }

    healthContainer.innerHTML = healthHtml;

  } catch (error) {
    healthContainer.innerHTML = `<div class="health-status health-unhealthy">Error checking health: ${error.message}</div>`;
  }
}

// Load stats on page load
document.addEventListener('DOMContentLoaded', function () {
  loadStats();
});

// Auto-refresh stats every 30 seconds
setInterval(loadStats, 30000);
