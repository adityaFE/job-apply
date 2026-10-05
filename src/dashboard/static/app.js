/**
 * Frontend Application Controller for Job Apply Intelligence Hub.
 * Manages ATS job discovery, AI match filtering, manual application workflow,
 * and local IMAP recruitment email tracking.
 */

// State Management
const state = {
  jobs: [],
  total: 0,
  selectedStatus: 'ALL',
  searchQuery: '',
  daysBack: '',
  minScore: 0,
  sortBy: 'match_score',
  skills: [],
  omitSkills: [],
  location: '',
  remoteOnly: false,
  activeJobId: null,
  isScraping: false,
  isSyncingEmails: false
};

// DOM Elements
const jobsContainer = document.getElementById('jobs-container');
const emptyState = document.getElementById('empty-state');
const resultsCountHeading = document.getElementById('results-count-heading');

// Inputs
const searchInput = document.getElementById('search-input');
const filterDate = document.getElementById('filter-date');
const filterMinScore = document.getElementById('filter-min-score');
const filterSort = document.getElementById('filter-sort');
const filterSkillsInput = document.getElementById('filter-skills-input');
const filterOmitSkillsInput = document.getElementById('filter-omit-skills-input');
const filterLocationInput = document.getElementById('filter-location-input');
const filterRemoteToggle = document.getElementById('filter-remote-toggle');
const btnResetFilters = document.getElementById('btn-reset-filters');

// Pills Containers
const quickSkillsPills = document.getElementById('quick-skills-pills');
const quickOmitPills = document.getElementById('quick-omit-pills');

// Modals
const jobDetailModal = document.getElementById('job-detail-modal');
const profileModal = document.getElementById('profile-modal');
const linkedinModal = document.getElementById('linkedin-modal');
const emailModal = document.getElementById('email-modal');

// Buttons
const btnScrapeAll = document.getElementById('btn-scrape-all');
const scrapeBtnText = document.getElementById('scrape-btn-text');
const btnSyncEmails = document.getElementById('btn-sync-emails');
const emailSyncBtnText = document.getElementById('email-sync-btn-text');
const btnEmailConfig = document.getElementById('btn-email-config');
const btnProfileConfig = document.getElementById('btn-profile-config');
const btnLinkedinSearch = document.getElementById('btn-linkedin-search');
const btnEmptyScrape = document.getElementById('btn-empty-scrape');

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
  initEventListeners();
  await loadFilterOptions();
  await refreshDashboard();
});

function initEventListeners() {
  // Search Debounce
  let searchTimer;
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.searchQuery = e.target.value.trim();
      fetchJobs();
    }, 300);
  });

  // Date Filter
  filterDate.addEventListener('change', (e) => {
    state.daysBack = e.target.value;
    fetchJobs();
  });

  // Min Score Filter
  filterMinScore.addEventListener('change', (e) => {
    state.minScore = parseInt(e.target.value, 10);
    fetchJobs();
  });

  // Sort Filter
  filterSort.addEventListener('change', (e) => {
    state.sortBy = e.target.value;
    fetchJobs();
  });

  // Skills input
  let skillTimer;
  filterSkillsInput.addEventListener('input', (e) => {
    clearTimeout(skillTimer);
    skillTimer = setTimeout(() => {
      state.skills = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
      fetchJobs();
    }, 400);
  });

  // Omit Skills input
  let omitTimer;
  filterOmitSkillsInput.addEventListener('input', (e) => {
    clearTimeout(omitTimer);
    omitTimer = setTimeout(() => {
      state.omitSkills = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
      fetchJobs();
    }, 400);
  });

  // Location input
  let locTimer;
  filterLocationInput.addEventListener('input', (e) => {
    clearTimeout(locTimer);
    locTimer = setTimeout(() => {
      state.location = e.target.value.trim();
      fetchJobs();
    }, 400);
  });

  // Remote Toggle
  filterRemoteToggle.addEventListener('change', (e) => {
    state.remoteOnly = e.target.checked;
    fetchJobs();
  });

  // Reset Filters
  btnResetFilters.addEventListener('click', resetFilters);

  // Status Tabs
  document.querySelectorAll('#status-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#status-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedStatus = btn.dataset.status;
      fetchJobs();
    });
  });

  // Stat Card Clicks (filter by status)
  document.querySelectorAll('.stat-card[data-status]').forEach(card => {
    card.addEventListener('click', () => {
      const status = card.dataset.status;
      state.selectedStatus = status;
      document.querySelectorAll('#status-tabs .tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.status === status);
      });
      fetchJobs();
    });
  });

  // Sync All Scrapers
  btnScrapeAll.addEventListener('click', triggerScrapeAll);
  btnEmptyScrape.addEventListener('click', triggerScrapeAll);

  // Email Tracking Controls
  if (btnSyncEmails) {
    btnSyncEmails.addEventListener('click', triggerEmailSync);
  }
  if (btnEmailConfig) {
    btnEmailConfig.addEventListener('click', openEmailModal);
  }

  // Modals openers
  btnProfileConfig.addEventListener('click', openProfileModal);
  btnLinkedinSearch.addEventListener('click', () => linkedinModal.classList.add('open'));

  // Modals closers
  document.getElementById('modal-close-btn').addEventListener('click', () => jobDetailModal.classList.remove('open'));
  document.getElementById('profile-modal-close').addEventListener('click', () => profileModal.classList.remove('open'));
  document.getElementById('profile-cancel-btn').addEventListener('click', () => profileModal.classList.remove('open'));
  document.getElementById('linkedin-modal-close').addEventListener('click', () => linkedinModal.classList.remove('open'));
  document.getElementById('li-cancel-btn').addEventListener('click', () => linkedinModal.classList.remove('open'));

  if (document.getElementById('email-modal-close')) {
    document.getElementById('email-modal-close').addEventListener('click', () => emailModal.classList.remove('open'));
  }
  if (document.getElementById('email-cancel-btn')) {
    document.getElementById('email-cancel-btn').addEventListener('click', () => emailModal.classList.remove('open'));
  }

  // LinkedIn Search Submit
  document.getElementById('li-run-btn').addEventListener('click', runLinkedInSearch);

  // Profile Save
  document.getElementById('profile-save-btn').addEventListener('click', saveProfileConfig);

  // Email Config Save & Test
  if (document.getElementById('email-save-btn')) {
    document.getElementById('email-save-btn').addEventListener('click', saveEmailConfig);
  }
  if (document.getElementById('email-test-btn')) {
    document.getElementById('email-test-btn').addEventListener('click', testEmailConnection);
  }

  // Modal Notes Save
  document.getElementById('btn-save-notes').addEventListener('click', saveModalNotes);

  // Modal Status Change
  document.getElementById('modal-status-select').addEventListener('change', async (e) => {
    if (state.activeJobId) {
      await updateJobStatus(state.activeJobId, e.target.value);
    }
  });
}

function resetFilters() {
  searchInput.value = '';
  filterDate.value = '';
  filterMinScore.value = '0';
  filterSort.value = 'match_score';
  filterSkillsInput.value = '';
  filterOmitSkillsInput.value = '';
  filterLocationInput.value = '';
  filterRemoteToggle.checked = false;

  state.searchQuery = '';
  state.daysBack = '';
  state.minScore = 0;
  state.sortBy = 'match_score';
  state.skills = [];
  state.omitSkills = [];
  state.location = '';
  state.remoteOnly = false;
  state.selectedStatus = 'ALL';

  document.querySelectorAll('#status-tabs .tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.status === 'ALL');
  });
  document.querySelectorAll('.pill').forEach(p => p.classList.remove('active', 'active-omit'));

  fetchJobs();
}

async function loadFilterOptions() {
  try {
    const res = await fetch('/api/filter-options');
    const data = await res.json();

    // Render Quick Skills Pills
    if (data.profile_skills && quickSkillsPills) {
      quickSkillsPills.innerHTML = '';
      data.profile_skills.forEach(skill => {
        const pill = document.createElement('span');
        pill.className = 'pill';
        pill.textContent = skill;
        pill.addEventListener('click', () => {
          pill.classList.toggle('active');
          updateSkillsFromPills();
        });
        quickSkillsPills.appendChild(pill);
      });
    }

    // Render Quick Omit Pills
    if (data.profile_omit_skills && quickOmitPills) {
      quickOmitPills.innerHTML = '';
      data.profile_omit_skills.forEach(skill => {
        const pill = document.createElement('span');
        pill.className = 'pill';
        pill.textContent = skill;
        pill.addEventListener('click', () => {
          pill.classList.toggle('active-omit');
          updateOmitSkillsFromPills();
        });
        quickOmitPills.appendChild(pill);
      });
    }
  } catch (err) {
    console.error('Failed to load filter options:', err);
  }
}

function updateSkillsFromPills() {
  const active = Array.from(quickSkillsPills.querySelectorAll('.pill.active')).map(p => p.textContent.trim());
  state.skills = active;
  filterSkillsInput.value = active.join(', ');
  fetchJobs();
}

function updateOmitSkillsFromPills() {
  const active = Array.from(quickOmitPills.querySelectorAll('.pill.active-omit')).map(p => p.textContent.trim());
  state.omitSkills = active;
  filterOmitSkillsInput.value = active.join(', ');
  fetchJobs();
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    const stats = await res.json();

    document.getElementById('stat-total').textContent = stats.total_jobs || 0;
    document.getElementById('stat-new').textContent = stats.status_counts?.NEW || 0;
    document.getElementById('stat-saved').textContent = stats.status_counts?.SAVED || 0;
    document.getElementById('stat-applied').textContent = stats.status_counts?.APPLIED || 0;
    document.getElementById('stat-interview').textContent = stats.status_counts?.INTERVIEW || 0;

    if (document.getElementById('stat-emails')) {
      document.getElementById('stat-emails').textContent = stats.total_emails || 0;
    }
    if (document.getElementById('stat-remote-pct')) {
      document.getElementById('stat-remote-pct').textContent = `${stats.total_remote || 0} Remote Jobs`;
    }

    // Update tab counts
    document.getElementById('count-tab-all').textContent = stats.total_jobs || 0;
    document.getElementById('count-tab-new').textContent = stats.status_counts?.NEW || 0;
    document.getElementById('count-tab-saved').textContent = stats.status_counts?.SAVED || 0;
    document.getElementById('count-tab-applied').textContent = stats.status_counts?.APPLIED || 0;
    document.getElementById('count-tab-interview').textContent = stats.status_counts?.INTERVIEW || 0;
  } catch (err) {
    console.error('Failed to fetch stats:', err);
  }
}

async function fetchJobs() {
  const params = new URLSearchParams();
  if (state.searchQuery) params.append('search', state.searchQuery);
  if (state.selectedStatus && state.selectedStatus !== 'ALL') params.append('status', state.selectedStatus);
  if (state.minScore > 0) params.append('min_score', state.minScore);
  if (state.daysBack) params.append('days_back', state.daysBack);
  if (state.skills.length > 0) params.append('skills', state.skills.join(','));
  if (state.omitSkills.length > 0) params.append('omit_skills', state.omitSkills.join(','));
  if (state.location) params.append('location', state.location);
  if (state.remoteOnly) params.append('remote_only', 'true');
  params.append('sort_by', state.sortBy);
  params.append('limit', '100');

  try {
    const res = await fetch(`/api/jobs?${params.toString()}`);
    const data = await res.json();
    state.jobs = data.jobs || [];
    state.total = data.total || 0;

    renderJobs();
  } catch (err) {
    console.error('Failed to fetch jobs:', err);
  }
}

async function refreshDashboard() {
  await fetchStats();
  await fetchJobs();
}

function renderJobs() {
  resultsCountHeading.textContent = `Showing ${state.jobs.length} of ${state.total} matching jobs`;

  if (state.jobs.length === 0) {
    jobsContainer.innerHTML = '';
    emptyState.style.display = 'flex';
    return;
  }

  emptyState.style.display = 'none';
  jobsContainer.innerHTML = state.jobs.map(record => createJobCardHTML(record)).join('');

  // Attach card event listeners
  document.querySelectorAll('.job-card').forEach(card => {
    const jobId = card.dataset.id;
    const titleElem = card.querySelector('.job-title');
    if (titleElem) {
      titleElem.addEventListener('click', () => openJobDetailModal(jobId));
    }

    // Quick action buttons
    card.querySelectorAll('.btn-quick-status').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const targetStatus = btn.dataset.targetStatus;
        await updateJobStatus(jobId, targetStatus);
      });
    });
  });
}

function createJobCardHTML(record) {
  const j = record.job;
  const m = record.match;
  const status = record.status;

  // Match score class
  let scoreClass = 'score-mid';
  if (m.match_score >= 80) scoreClass = 'score-high';
  else if (m.match_score < 45) scoreClass = 'score-bad';
  else if (m.match_score < 65) scoreClass = 'score-low';

  // Date formatting
  let dateText = 'Discovered recently';
  if (j.date_posted) {
    dateText = formatRelativeDate(new Date(j.date_posted));
  }

  // Skills tags
  const matchedPills = (m.matched_skills || []).slice(0, 6)
    .map(s => `<span class="skill-tag skill-matched">${s}</span>`).join('');
  const missingPills = (m.missing_skills || []).slice(0, 3)
    .map(s => `<span class="skill-tag skill-missing">+${s}</span>`).join('');
  const omittedWarning = (m.omitted_skills_found && m.omitted_skills_found.length > 0)
    ? `<span class="skill-tag skill-omitted">⚠ Has ${m.omitted_skills_found.join(', ')}</span>`
    : '';

  return `
    <div class="job-card" data-id="${j.id}">
      <div class="job-card-header">
        <div class="company-title-wrap">
          <div class="job-meta-row">
            <span class="job-company">${escapeHTML(j.company)}</span>
            <span class="badge badge-source">${j.ats_type.toUpperCase()}</span>
            ${j.is_remote ? '<span class="badge badge-remote">REMOTE</span>' : ''}
            <span>• ${escapeHTML(j.location)}</span>
          </div>
          <h3 class="job-title">${escapeHTML(j.title)}</h3>
        </div>
        <div class="score-badge ${scoreClass}">
          🎯 ${m.match_score}% Match
        </div>
      </div>

      <div class="job-card-skills">
        ${matchedPills}
        ${missingPills}
        ${omittedWarning}
      </div>

      <div class="job-card-footer">
        <div class="footer-left">
          <span>📅 ${dateText}</span>
          <span>Status: <span class="badge badge-status badge-status-${status.toLowerCase()}">${status}</span></span>
        </div>
        <div class="card-actions">
          ${status !== 'APPLIED' ? `
            <button class="btn btn-secondary btn-sm btn-quick-status" data-target-status="APPLIED">
              ✓ Mark Applied
            </button>
          ` : '<span class="badge badge-remote">Applied ✓</span>'}

          ${status !== 'SAVED' && status !== 'APPLIED' ? `
            <button class="btn btn-secondary btn-sm btn-quick-status" data-target-status="SAVED">
              ★ Save
            </button>
          ` : ''}

          <a href="${j.url}" target="_blank" class="btn btn-primary btn-sm">
            Apply Now ↗
          </a>
        </div>
      </div>
    </div>
  `;
}

async function openJobDetailModal(jobId) {
  const record = state.jobs.find(r => r.job.id === jobId);
  if (!record) return;

  state.activeJobId = jobId;
  const j = record.job;
  const m = record.match;

  document.getElementById('modal-job-title').textContent = j.title;
  document.getElementById('modal-company-name').textContent = j.company;
  document.getElementById('modal-location').textContent = `${j.location} ${j.is_remote ? '(Remote)' : ''}`;
  document.getElementById('modal-source-badge').textContent = j.ats_type.toUpperCase();
  document.getElementById('modal-score-badge').textContent = `${m.match_score}% Match`;
  document.getElementById('modal-match-summary').textContent = m.summary;

  // Skills
  const matchedContainer = document.getElementById('modal-matched-skills');
  matchedContainer.innerHTML = (m.matched_skills || []).map(s => `<span class="skill-tag skill-matched">${s}</span>`).join('') || 'None detected';

  const missingContainer = document.getElementById('modal-missing-skills');
  missingContainer.innerHTML = (m.missing_skills || []).map(s => `<span class="skill-tag skill-missing">${s}</span>`).join('') || 'None detected';

  const omittedWarning = document.getElementById('modal-omitted-warning');
  if (m.omitted_skills_found && m.omitted_skills_found.length > 0) {
    omittedWarning.style.display = 'block';
    omittedWarning.textContent = `⚠ Warning: This job mentions omitted skills: ${m.omitted_skills_found.join(', ')}`;
  } else {
    omittedWarning.style.display = 'none';
  }

  // Notes
  document.getElementById('modal-notes-input').value = record.notes || '';

  // Job Description
  document.getElementById('modal-job-description').textContent = j.description || 'No description available.';

  // Status select
  document.getElementById('modal-status-select').value = record.status;

  // Apply button URL
  document.getElementById('modal-apply-btn').href = j.url;

  // Load Application Timeline & Email History
  await loadJobTimeline(jobId);

  jobDetailModal.classList.add('open');
}

async function loadJobTimeline(jobId) {
  const container = document.getElementById('modal-timeline-container');
  container.innerHTML = '<div class="timeline-empty">Loading application history & emails...</div>';

  try {
    const res = await fetch(`/api/jobs/${jobId}/timeline`);
    const data = await res.json();
    const timeline = data.timeline || [];

    if (timeline.length === 0) {
      container.innerHTML = '<div class="timeline-empty">No status updates or emails recorded yet.</div>';
      return;
    }

    container.innerHTML = timeline.map(item => {
      const isEmail = item.type === 'email';
      const icon = isEmail ? '✉️' : '⚡';
      const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleString() : '';

      if (isEmail) {
        return `
          <div class="timeline-item">
            <div class="timeline-icon">${icon}</div>
            <div class="timeline-content">
              <div class="timeline-header-line">
                <span class="timeline-title">${escapeHTML(item.subject)}</span>
                <span class="timeline-date">${dateStr}</span>
              </div>
              <div class="timeline-desc">
                <span class="timeline-badge category-${item.category}">${item.category}</span>
                <span>From: ${escapeHTML(item.sender)}</span>
              </div>
              ${item.snippet ? `<small style="color: #94a3b8; margin-top: 4px; font-style: italic;">"${escapeHTML(item.snippet.slice(0, 150))}..."</small>` : ''}
            </div>
          </div>
        `;
      } else {
        return `
          <div class="timeline-item">
            <div class="timeline-icon">${icon}</div>
            <div class="timeline-content">
              <div class="timeline-header-line">
                <span class="timeline-title">${escapeHTML(item.description)}</span>
                <span class="timeline-date">${dateStr}</span>
              </div>
              <div class="timeline-desc">
                ${item.old_status && item.new_status ? `<span>Transitioned: <code>${item.old_status}</code> ➔ <code>${item.new_status}</code></span>` : ''}
              </div>
            </div>
          </div>
        `;
      }
    }).join('');
  } catch (err) {
    container.innerHTML = '<div class="timeline-empty text-danger">Failed to load timeline events.</div>';
  }
}

async function updateJobStatus(jobId, newStatus) {
  try {
    const res = await fetch(`/api/jobs/${jobId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      showToast(`Job status updated to ${newStatus}`, 'success');
      await refreshDashboard();
      if (state.activeJobId === jobId) {
        await loadJobTimeline(jobId);
      }
    }
  } catch (err) {
    showToast('Failed to update job status', 'error');
  }
}

async function saveModalNotes() {
  if (!state.activeJobId) return;
  const notes = document.getElementById('modal-notes-input').value;
  try {
    const res = await fetch(`/api/jobs/${state.activeJobId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes })
    });
    if (res.ok) {
      showToast('Notes saved successfully', 'success');
      await refreshDashboard();
      await loadJobTimeline(state.activeJobId);
    }
  } catch (err) {
    showToast('Failed to save notes', 'error');
  }
}

async function triggerScrapeAll() {
  if (state.isScraping) return;
  state.isScraping = true;
  scrapeBtnText.textContent = 'Syncing...';
  btnScrapeAll.disabled = true;

  try {
    const res = await fetch('/api/scrape/all', { method: 'POST' });
    if (res.ok) {
      showToast('Full sync started in background across target portals', 'success');
      setTimeout(async () => {
        await refreshDashboard();
        state.isScraping = false;
        scrapeBtnText.textContent = 'Sync & Scrape All';
        btnScrapeAll.disabled = false;
      }, 4000);
    }
  } catch (err) {
    showToast('Failed to trigger scraper sync', 'error');
    state.isScraping = false;
    scrapeBtnText.textContent = 'Sync & Scrape All';
    btnScrapeAll.disabled = false;
  }
}

async function triggerEmailSync() {
  if (state.isSyncingEmails) return;
  state.isSyncingEmails = true;
  emailSyncBtnText.textContent = 'Syncing Emails...';
  btnSyncEmails.disabled = true;

  showToast('Connecting to IMAP server and checking for recruitment updates...', 'success');

  try {
    const res = await fetch('/api/email/sync', { method: 'POST' });
    const data = await res.json();

    if (data.errors && data.errors.length > 0) {
      showToast(`Email sync finished with notice: ${data.errors[0]}`, 'error');
    } else {
      showToast(`Email sync completed: ${data.emails_processed} checked, ${data.emails_matched} linked, ${data.status_updates} status transitions!`, 'success');
    }
    await refreshDashboard();
  } catch (err) {
    showToast('Email sync failed to connect to IMAP server', 'error');
  } finally {
    state.isSyncingEmails = false;
    emailSyncBtnText.textContent = 'Sync Emails';
    btnSyncEmails.disabled = false;
  }
}

async function openEmailModal() {
  const statusBox = document.getElementById('email-test-status');
  statusBox.style.display = 'none';

  try {
    const res = await fetch('/api/email/config');
    const cfg = await res.json();

    document.getElementById('email-cfg-enabled').checked = !!cfg.enabled;
    document.getElementById('email-cfg-host').value = cfg.host || 'imap.gmail.com';
    document.getElementById('email-cfg-port').value = cfg.port || 993;
    document.getElementById('email-cfg-username').value = cfg.username || '';
    document.getElementById('email-cfg-password').value = '';
    document.getElementById('email-cfg-lookback').value = cfg.lookback_days || 30;
    document.getElementById('email-cfg-folders').value = (cfg.folders || ['INBOX']).join(', ');
    document.getElementById('email-cfg-auto-status').checked = cfg.auto_update_status !== false;

    emailModal.classList.add('open');
  } catch (err) {
    showToast('Failed to load email tracking configuration', 'error');
  }
}

function getEmailFormData() {
  const enabled = document.getElementById('email-cfg-enabled').checked;
  const host = document.getElementById('email-cfg-host').value.trim();
  const port = parseInt(document.getElementById('email-cfg-port').value, 10) || 993;
  const username = document.getElementById('email-cfg-username').value.trim();
  const password = document.getElementById('email-cfg-password').value.trim();
  const lookback_days = parseInt(document.getElementById('email-cfg-lookback').value, 10) || 30;
  const folders = document.getElementById('email-cfg-folders').value.split(',').map(s => s.trim()).filter(Boolean);
  const auto_update_status = document.getElementById('email-cfg-auto-status').checked;

  return {
    enabled,
    host,
    port,
    username,
    password: password || null,
    use_ssl: true,
    folders: folders.length > 0 ? folders : ['INBOX'],
    lookback_days,
    auto_update_status
  };
}

async function saveEmailConfig() {
  const payload = getEmailFormData();
  try {
    const res = await fetch('/api/email/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast('Email tracking settings saved successfully!', 'success');
      emailModal.classList.remove('open');
    } else {
      showToast('Failed to save email settings', 'error');
    }
  } catch (err) {
    showToast('Error saving email configuration', 'error');
  }
}

async function testEmailConnection() {
  const statusBox = document.getElementById('email-test-status');
  statusBox.style.display = 'block';
  statusBox.className = 'test-status-box';
  statusBox.textContent = 'Testing IMAP connection and TLS handshake...';

  const payload = getEmailFormData();
  try {
    const res = await fetch('/api/email/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      statusBox.className = 'test-status-box success';
      statusBox.textContent = `✓ ${data.message}`;
    } else {
      statusBox.className = 'test-status-box error';
      statusBox.textContent = `✕ Connection failed: ${data.message}`;
    }
  } catch (err) {
    statusBox.className = 'test-status-box error';
    statusBox.textContent = '✕ Network error while testing connection';
  }
}

async function runLinkedInSearch() {
  const keywords = document.getElementById('li-search-keywords').value.trim();
  const location = document.getElementById('li-search-location').value.trim();
  const limit = parseInt(document.getElementById('li-search-limit').value, 10);

  linkedinModal.classList.remove('open');
  showToast(`Searching LinkedIn guest board for "${keywords}"...`, 'success');

  try {
    const res = await fetch('/api/scrape/linkedin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords, location, limit })
    });
    const result = await res.json();
    showToast(`LinkedIn search completed: ${result.jobs_found} found, ${result.jobs_new} new jobs added!`, 'success');
    await refreshDashboard();
  } catch (err) {
    showToast('LinkedIn search failed', 'error');
  }
}

async function openProfileModal() {
  try {
    const res = await fetch('/api/config/profile');
    const profile = await res.json();

    document.getElementById('cfg-target-roles').value = (profile.target_roles || []).join('\n');
    document.getElementById('cfg-core-skills').value = (profile.skills?.core || []).join(', ');
    document.getElementById('cfg-secondary-skills').value = (profile.skills?.secondary || []).join(', ');
    document.getElementById('cfg-omit-skills').value = (profile.omit_skills || []).join(', ');
    document.getElementById('cfg-locations').value = (profile.locations?.preferred || []).join(', ');
    document.getElementById('cfg-remote-only').checked = !!profile.locations?.remote_only;

    profileModal.classList.add('open');
  } catch (err) {
    showToast('Failed to load profile configuration', 'error');
  }
}

async function saveProfileConfig() {
  const target_roles = document.getElementById('cfg-target-roles').value.split('\n').map(s => s.trim()).filter(Boolean);
  const core_skills = document.getElementById('cfg-core-skills').value.split(',').map(s => s.trim()).filter(Boolean);
  const secondary_skills = document.getElementById('cfg-secondary-skills').value.split(',').map(s => s.trim()).filter(Boolean);
  const omit_skills = document.getElementById('cfg-omit-skills').value.split(',').map(s => s.trim()).filter(Boolean);
  const preferred_locations = document.getElementById('cfg-locations').value.split(',').map(s => s.trim()).filter(Boolean);
  const remote_only = document.getElementById('cfg-remote-only').checked;

  try {
    const res = await fetch('/api/config/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_roles,
        core_skills,
        secondary_skills,
        omit_skills,
        preferred_locations,
        remote_only
      })
    });
    if (res.ok) {
      showToast('Profile configuration updated!', 'success');
      profileModal.classList.remove('open');
      await loadFilterOptions();
      await refreshDashboard();
    }
  } catch (err) {
    showToast('Failed to save profile configuration', 'error');
  }
}

// Helpers
function formatRelativeDate(date) {
  const now = new Date();
  const diffInSeconds = Math.floor((now - date) / 1000);

  if (diffInSeconds < 3600) return 'Just now';
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
  const days = Math.floor(diffInSeconds / 86400);
  if (days === 1) return 'Yesterday';
  return `${days} days ago`;
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠'}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
