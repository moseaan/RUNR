    // Provider normalization for comparisons (inside scope)
    function canonicalProviderId(p) {
        const lc = (p || '').toString().toLowerCase().replace(/\s+/g, '');
        if (lc === 'mysocialsboost' || lc === 'mysocials' || lc === 'mysocialgroup' || lc === 'mysocialgroups') return 'mysocialsboost';
        if (lc === 'smmk' || lc === 'smmkings' || lc === 'smm' || lc === 'smmkingscom') return 'smmkings';
        if (lc === 'justanotherpanel' || lc === 'jap' || lc === 'justanother') return 'justanotherpanel';
        if (lc === 'peakerr' || lc === 'peakar' || lc === 'pekerr') return 'peakerr';
        return lc;
    }

    async function handleEditMonitoring(event) {
        console.log('handleEditMonitoring called');
        const monitorListStatus = document.getElementById('monitor-list-status');
        const btn = event.currentTarget;
        const targetId = btn.getAttribute('data-target-id');
        const oldUsername = btn.getAttribute('data-target-name') || '';
        const oldProfile = btn.getAttribute('data-profile-name') || '';

        // Simple prompts for now; can be upgraded to a modal later
        const newUsername = prompt('Edit target username:', oldUsername);
        if (newUsername === null) return; // cancelled
        const newProfile = prompt('Edit promotion profile name:', oldProfile);
        if (newProfile === null) return; // cancelled
        const username = newUsername.trim();
        const profileName = newProfile.trim();
        if (!username || !profileName) {
            if (monitorListStatus) showTemporaryStatus(monitorListStatus, 'Username and profile cannot be empty.', 'warning');
            return;
        }

        try {
            btn.disabled = true;
            if (monitorListStatus) showTemporaryStatus(monitorListStatus, `Saving edits for ${oldUsername}...`, 'info', 0);
            const res = await apiCall(`/api/monitoring/targets/${targetId}`, 'PUT', {
                target_username: username,
                promotion_profile_name: profileName
            });
            if (res && res.success && res.targets) {
                renderMonitoringTargets(res.targets);
                if (monitorListStatus) showTemporaryStatus(monitorListStatus, 'Edits saved.', 'success');
            } else {
                if (monitorListStatus) showTemporaryStatus(monitorListStatus, res.error || 'Failed to save edits.', 'danger');
                btn.disabled = false;
            }
        } catch (e) {
            if (monitorListStatus) showTemporaryStatus(monitorListStatus, 'Error saving edits.', 'danger');
            btn.disabled = false;
        }
    }
    // Overrides loader/cacher (inside scope)
    async function loadServiceOverrides() {
        if (serviceOverridesCache) return serviceOverridesCache;
        try {
            const res = await apiCall('/api/services/overrides', 'GET');
            if (res && res.success) {
                serviceOverridesCache = res.overrides || {};
            } else {
                serviceOverridesCache = {};
            }
        } catch(_) { serviceOverridesCache = {}; }
        return serviceOverridesCache;
    }
    function getServiceOverride(platform, engagement) {
        const ov = serviceOverridesCache || {};
        if (!platform || !engagement) return null;
        const canon = (s) => (s || '').toString().toLowerCase().replace(/[^a-z0-9]/gi, '');
        const p = canon(platform);
        const e = canon(engagement);
        const pkey = Object.keys(ov).find(k => canon(k) === p);
        if (!pkey) return null;
        const perPlat = ov[pkey] || {};
        const ekey = Object.keys(perPlat).find(k => canon(k) === e);
        return ekey ? perPlat[ekey] : null;
    }
// JavaScript for fetching data and handling UI interactions - will be added later

console.log("Script loaded.");

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed");

    // --- Global State (Declare caches AND other state vars BEFORE other logic) ---
    let profilesDataCache = {}; 
    let minimumQuantities = {};
    let currentProfileJobId = null;
    let statusCheckInterval = null; // Declare ONCE here
    let tempStatusTimeouts = {}; // Declare ONCE here
    let engagementOptionsCache = []; // Define cache here
    let profileModal = null; // <<< Assign the modal element here after DOM load
    let historyPollIntervalId = null;
    let serviceOverridesCache = null; // cache of overrides by platform->engagement

    // --- Element Refs (Get elements needed across different initializers/listeners) ---
    const runProfileBtn = document.getElementById('start-profile-promo-btn'); 
    const stopProfileBtn = document.getElementById('stop-profile-btn'); 
    const profileSelectPromo = document.getElementById('profile-select-promo'); 
    const promoLinkInput = document.getElementById('profile-link-input'); 
    const profileSelectProfilePage = document.getElementById('profile-select');
    const addProfileBtn = document.getElementById('add-profile-btn');
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const deleteProfileBtn = document.getElementById('delete-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-modal-btn');
    const profileEditorForm = document.getElementById('profile-editor-form');
    const useRandomDelayCheckbox = document.getElementById('use-random-delay');
    const profileNameInput = document.getElementById('profile-name');
    const originalProfileNameInput = document.getElementById('original-profile-name');
    const loopCountInput = document.getElementById('loop-count');
    const loopDelayInput = document.getElementById('loop-delay');
    const minDelayInput = document.getElementById('min-delay');
    const maxDelayInput = document.getElementById('max-delay');
    const engagementSettingsDiv = document.getElementById('engagement-settings');
    const profileSelectDropdown = document.getElementById('profile-select');
    // ... add other commonly used refs if needed ...

    // Assign the modal element after DOM load
    profileModal = document.getElementById('profile-editor-modal');

    // --- CORE HELPER FUNCTIONS (Define BEFORE first use) ---

    // --- Global readiness flags and updater for top status ---
    let singleReady = false;
    let promoReady = false;

    function updateGlobalReadyStatus() {
        const statusAreaId = 'status-text';
        const statusMessageId = 'status-text';
        if (singleReady && promoReady) {
            showStatus('Ready', 'success', statusAreaId, statusMessageId);
        } else {
            showStatus('Not Ready', 'danger', statusAreaId, statusMessageId);
        }

    }

    // --- Persist active jobs across refresh using localStorage ---
    const ACTIVE_JOBS_KEY = 'mim_active_jobs';
    function getStoredActiveJobs() {
        try {
            const raw = localStorage.getItem(ACTIVE_JOBS_KEY);
            const arr = raw ? JSON.parse(raw) : [];
            return Array.isArray(arr) ? arr : [];
        } catch (_) { return []; }
    }
    function setStoredActiveJobs(list) {
        try { localStorage.setItem(ACTIVE_JOBS_KEY, JSON.stringify(Array.from(new Set(list)))); } catch(_) {}
    }
    function addActiveJobId(jobId) {
        const list = getStoredActiveJobs();
        if (!list.includes(jobId)) { list.push(jobId); setStoredActiveJobs(list); }
    }
    function removeActiveJobId(jobId) {
        const list = getStoredActiveJobs().filter(id => id !== jobId);
        setStoredActiveJobs(list);
    }

    // Store job metadata for restoration
    const JOB_META_KEY = 'mim_job_metadata';
    function getJobMetadata() {
        try {
            const raw = localStorage.getItem(JOB_META_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (_) { return {}; }
    }
    function setJobMetadata(meta) {
        try { localStorage.setItem(JOB_META_KEY, JSON.stringify(meta)); } catch(_) {}
    }
    function saveJobMeta(jobId, containerId, label, link) {
        const meta = getJobMetadata();
        meta[jobId] = { containerId, label, link, timestamp: Date.now() };
        setJobMetadata(meta);
    }
    function removeJobMeta(jobId) {
        const meta = getJobMetadata();
        delete meta[jobId];
        setJobMetadata(meta);
    }

    // Restore active jobs on page load (cross-device support)
    async function restoreActiveJobs() {
        try {
            // Fetch ALL active jobs from server (source of truth)
            const data = await apiCall('/api/jobs/active');
            if (!data || !data.success || !Array.isArray(data.jobs)) {
                console.warn('No active jobs to restore or API call failed.');
                return;
            }

            console.log(`Restoring ${data.jobs.length} active job(s) from server...`);
            
            for (const job of data.jobs) {
                const { job_id, label, link, container_id } = job;
                
                // Check if job row already exists (avoid duplicates)
                if (document.getElementById(`job-${job_id}`)) {
                    console.log(`Job row for ${job_id} already exists, skipping.`);
                    continue;
                }
                
                // Create job row with server metadata
                if (label && container_id) {
                    createJobRow(container_id, job_id, label, link || '');
                    // Start polling for this job
                    startPerJobPolling(job_id);
                    // Update localStorage for redundancy
                    try {
                        addActiveJobId(job_id);
                        saveJobMeta(job_id, container_id, label, link || '');
                    } catch (_) {}
                } else {
                    console.warn(`Job ${job_id} missing metadata (label or container_id), skipping.`);
                }
            }

            // Clean up localStorage: remove jobs not in server's active list
            const serverActiveIds = data.jobs.map(j => j.job_id);
            const storedIds = getStoredActiveJobs();
            for (const jobId of storedIds) {
                if (!serverActiveIds.includes(jobId)) {
                    console.log(`Removing completed job ${jobId} from localStorage.`);
                    removeActiveJobId(jobId);
                    removeJobMeta(jobId);
                }
            }
        } catch (e) {
            console.error('Error restoring active jobs:', e);
        }
    }

    // Generic API Call Helper
    async function apiCall(endpoint, method = 'GET', body = null) {
        console.log(`API Call: ${method} ${endpoint}`, body ? body : '');
        const statusArea = document.getElementById('main-status-area') || document.body; // Fallback
        const statusMessage = document.getElementById('main-status-message') || statusArea;
        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    // Add any other required headers like CSRF tokens if needed
                },
            };
            if (body) {
                options.body = JSON.stringify(body);
            }
            const response = await fetch(endpoint, options);
            const contentType = (response.headers && response.headers.get && response.headers.get('content-type')) ? response.headers.get('content-type') : '';
            let data = null;
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                const text = await response.text();
                const snippet = (text || '').slice(0, 200);
                const ct = contentType || 'unknown';
                const statusInfo = `${response.status} ${response.statusText}`.trim();
                console.error(`Non-JSON response for ${method} ${endpoint} [${statusInfo}; content-type: ${ct}]:`, snippet);
                showStatus(`API Error: Non-JSON response (${statusInfo}).`, 'danger', 'main-status-area', 'main-status-message');
                throw new Error(`Non-JSON response (${statusInfo}; content-type: ${ct}): ${snippet}`);
            }

            if (!response.ok) {
                const errorMsg = data.error || data.message || `HTTP error! status: ${response.status}`;
                console.error(`API Error (${response.status}) for ${method} ${endpoint}:`, errorMsg);
                showStatus(`API Error: ${errorMsg}`, 'danger', 'main-status-area', 'main-status-message');
                throw new Error(errorMsg); // Throw error to be caught by caller
            }
            console.log(`API Success: ${method} ${endpoint}`, data);
            return data; // Return successful data
        } catch (error) {
            console.error(`Network/Fetch Error for ${method} ${endpoint}:`, error);
            const errorText = error.message.includes('HTTP error') ? error.message : `Network error. Check console and backend.`;
            showStatus(`Error: ${errorText}`, 'danger', 'main-status-area', 'main-status-message');
            throw error; // Re-throw error to be caught by caller
        }
    }

    // Show status message in designated area OR as a toast
    function showStatus(message, type = 'info', areaId = 'main-status-area', messageId = 'main-status-message', duration = 0, isToast = false) {
        if (isToast) {
            const toastContainer = document.getElementById('toast-container');
            if (!toastContainer) {
                console.error("Toast container '#toast-container' not found. Displaying message in console.");
                console.log(`Toast (${type}): ${message}`);
                return;
            }

            const toastId = `toast-${Date.now()}`; // Unique ID for the toast
            const toastElement = document.createElement('div');
            // Using Bootstrap alert classes for styling, adaptable to other frameworks
            // Ensure your CSS includes styles for .alert, .alert-{type}, .alert-dismissible, .fade, .show, .btn-close
            const alertType = (type === 'danger') ? 'danger' : (type === 'success') ? 'success' : (type === 'warning') ? 'warning' : 'info';
            toastElement.className = `alert alert-${alertType} alert-dismissible fade show m-2`; 
            toastElement.setAttribute('role', 'alert');
            toastElement.id = toastId;

            toastElement.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;

            console.log(`Showing Toast (${type}) [${toastId}]: ${message}`);
            toastContainer.appendChild(toastElement);

            // Auto-dismiss after duration
            if (duration > 0) {
                setTimeout(() => {
                    const currentToast = document.getElementById(toastId);
                    if (currentToast) {
                        // Attempt to use Bootstrap's dismiss method if available, otherwise remove directly
                        try {
                            const bsAlert = new bootstrap.Alert(currentToast);
                            if (bsAlert) {
                                bsAlert.close();
                            } else {
                                currentToast.remove();
                            }
                        } catch (e) {
                            // Fallback if bootstrap JS isn't loaded or fails
                            currentToast.remove();
                        }
                    }
                }, duration);
            }
            return; // Exit after handling toast
        }

        // --- Original logic for non-toast status updates --- 
        const statusArea = document.getElementById(areaId);
        const statusMessage = document.getElementById(messageId);
        
        if (!statusArea || !statusMessage) {
            console.warn(`showStatus: Could not find status elements (areaId: ${areaId}, messageId: ${messageId}). Message: ${message}`);
            return; // Exit if elements aren't found
        }

        console.log(`Status (${type}) [${areaId}/${messageId}]: ${message}`);
        
        // --- NEW Styling: Only apply text color class, remove background/alert styling ---
        let textClass = 'text-body'; // Default text color (usually inherits from body)
        switch (type) {
            case 'success':
                textClass = 'text-success';
                break;
            case 'danger':
                textClass = 'text-danger';
                break;
            case 'warning':
                textClass = 'text-warning';
                break;
            case 'info':
                 textClass = 'text-info'; // Or maybe text-primary?
                 break;
            // Add more cases if needed
        }

        // Apply class ONLY to the message element, remove alert classes from area
        statusArea.className = 'status-area'; // Remove alert classes, keep a base class if needed
        statusMessage.className = `status-message ${textClass}`; // Apply only text color
        statusMessage.textContent = message;
        statusArea.style.display = 'block'; // Make sure area is visible

        // Auto-hide after duration if specified
        if (duration > 0) {
            setTimeout(() => {
                try {
                    statusArea.style.display = 'none';
                } catch(_) {}
            }, duration);
        }
    }
    // Expose globally for inline page scripts (e.g., services.html)
    try { window.showStatus = showStatus; } catch(_) {}
    
    // Show status temporarily in a specific element (different from main status area)
    function showTemporaryStatus(element, message, type = 'info', duration = 3000, isHtml = false) {
        if (!element) {
            console.warn("showTemporaryStatus called with null element for message:", message);
            return;
        }
        // Use a unique key based on element ID or create one
        const elementId = element.id || `temp-status-${Math.random().toString(36).substring(7)}`;
        if (!element.id) element.id = elementId;

        // Clear any previous timeout for this specific element
        clearTimeout(tempStatusTimeouts[elementId]);

        // Set the message (handle HTML)
         if (isHtml) {
            element.innerHTML = message;
        } else {
            element.textContent = message;
        }
        element.className = `status-display text-${type}`; // Use Bootstrap text color classes
        console.log(`Temp Status (${type}) for [${elementId}]: ${message}`);

        // Set timeout to clear the message
        tempStatusTimeouts[elementId] = setTimeout(() => {
            clearTemporaryStatus(element);
        }, duration);
    }

    // Clear temporary status from an element
     function clearTemporaryStatus(element) {
        if (!element) return;
        element.textContent = '';
        element.className = 'status-display'; // Reset to base class
        // Clear timeout if it exists
        const elementId = element.id;
        if (elementId && tempStatusTimeouts[elementId]) {
            clearTimeout(tempStatusTimeouts[elementId]);
            delete tempStatusTimeouts[elementId];
        }
    }

    // --- Job Rows and Per-Job Polling (for async promos) ---
    const jobPollers = {}; // jobId -> intervalId
    const jobDelayCountdowns = {}; // jobId -> { intervalId, endAt }
    const COUNTDOWN_STORAGE_KEY = 'mim_countdown_timers';

    function saveCountdownToStorage(jobId, endAt, loopProgress) {
        try {
            const saved = JSON.parse(localStorage.getItem(COUNTDOWN_STORAGE_KEY) || '{}');
            saved[jobId] = { endAt, loopProgress, savedAt: Date.now() };
            localStorage.setItem(COUNTDOWN_STORAGE_KEY, JSON.stringify(saved));
        } catch (e) {
            console.warn('Could not save countdown to localStorage:', e);
        }
    }

    function getCountdownFromStorage(jobId) {
        try {
            const saved = JSON.parse(localStorage.getItem(COUNTDOWN_STORAGE_KEY) || '{}');
            return saved[jobId];
        } catch (e) {
            return null;
        }
    }

    function clearCountdownFromStorage(jobId) {
        try {
            const saved = JSON.parse(localStorage.getItem(COUNTDOWN_STORAGE_KEY) || '{}');
            delete saved[jobId];
            localStorage.setItem(COUNTDOWN_STORAGE_KEY, JSON.stringify(saved));
        } catch (e) {}
    }

    function clearJobCountdown(jobId) {
        const cd = jobDelayCountdowns[jobId];
        if (cd && cd.intervalId) {
            try { clearInterval(cd.intervalId); } catch(_) {}
        }
        delete jobDelayCountdowns[jobId];
        clearCountdownFromStorage(jobId);
    }

    function parseDelaySeconds(message) {
        if (!message || typeof message !== 'string') return null;
        const m = message.toLowerCase();
        // Try mm:ss
        let mmss = m.match(/\b(\d{1,2}):(\d{2})\b/);
        if (mmss) {
            const mm = parseInt(mmss[1], 10);
            const ss = parseInt(mmss[2], 10);
            if (!isNaN(mm) && !isNaN(ss)) return mm * 60 + ss;
        }
        // Try numeric seconds (supports decimals): "123.4s", "123 seconds"
        let secs = m.match(/\b(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds)\b/);
        if (secs) {
            const s = parseFloat(secs[1]);
            if (!isNaN(s)) return Math.ceil(s);
        }
        // Try phrases like "delay before next loop" with number (allow decimals)
        let numb = m.match(/\b(\d{1,5}(?:\.\d+)?)\b/);
        if (numb && /delay|next\s*loop|wait|cooldown/.test(m)) {
            const s = parseFloat(numb[1]);
            if (!isNaN(s)) return Math.ceil(s);
        }
        return null;
    }

    function parseLoopProgress(message) {
        if (!message || typeof message !== 'string') return '';
        // Match patterns like "5/10 loops completed" or "15/25 loops completed"
        const match = message.match(/(\d+)\/(\d+)\s*loops?\s*completed/i);
        if (match) {
            return ` -- ${match[1]}/${match[2]} Loops Completed`;
        }
        return '';
    }

    function startJobCountdown(jobId, seconds, stepEl, baseLabel, originalMessage) {
      if (!jobId || !stepEl || !seconds || seconds <= 0) return;
      const now = Date.now();
      const proposedEndAt = now + Math.ceil(seconds) * 1000;
      const loopProgress = originalMessage ? parseLoopProgress(originalMessage) : '';
      const existing = jobDelayCountdowns[jobId];
      // Reuse existing if shorter/new
      if (existing && existing.endAt && existing.endAt > now) {
          if (proposedEndAt + 500 < existing.endAt) { // allow small tolerance
              existing.endAt = proposedEndAt;
          }
          // Update display immediately based on existing endAt
          const remainingMs0 = Math.max(0, existing.endAt - now);
          const rem0 = Math.ceil(remainingMs0 / 1000);
          const pretty0 = `${rem0}s`;
          stepEl.textContent = baseLabel ? `${baseLabel}: next loop in ${pretty0}${loopProgress}` : `Status: Next loop in ${pretty0}${loopProgress}`;
          return;
      }
      if (existing && existing.endAt && existing.endAt <= now) {
          const finishedAgo = (existing.finishedAt ? (now - existing.finishedAt) : (now - existing.endAt));
          const sameDeclared = (existing.declaredSeconds === Math.ceil(seconds));
          if (finishedAgo < 3500 && sameDeclared) {
              // Keep showing resuming briefly; do not restart yet
              stepEl.textContent = baseLabel ? `${baseLabel}: resuming...` : 'Status: resuming...';
              return;
          }
      }

      const endAt = proposedEndAt;
      clearJobCountdown(jobId);
      // Save to localStorage for page reload persistence
      saveCountdownToStorage(jobId, endAt, loopProgress);
      
      jobDelayCountdowns[jobId] = {
          endAt,
          loopProgress,
          declaredSeconds: Math.ceil(seconds),
          finishedAt: null,
          intervalId: setInterval(() => {
              const remainingMs = endAt - Date.now();
              if (remainingMs <= 0) {
                  try { clearInterval(jobDelayCountdowns[jobId]?.intervalId); } catch(_) {}
                  if (jobDelayCountdowns[jobId]) {
                      jobDelayCountdowns[jobId].intervalId = null;
                      jobDelayCountdowns[jobId].finishedAt = Date.now();
                  }
                  clearCountdownFromStorage(jobId);
                  stepEl.textContent = baseLabel ? `${baseLabel}: resuming...` : 'Status: resuming...';
                  return;
              }
              const rem = Math.ceil(remainingMs / 1000);
              const pretty = `${rem}s`;
              stepEl.textContent = baseLabel ? `${baseLabel}: next loop in ${pretty}${loopProgress}` : `Status: Next loop in ${pretty}${loopProgress}`;
          }, 1000)
      };
      // Update immediately so user sees it tick without waiting 1s
      const pretty0 = `${Math.ceil(seconds)}s`;
      stepEl.textContent = baseLabel ? `${baseLabel}: next loop in ${pretty0}${loopProgress}` : `Status: Next loop in ${pretty0}${loopProgress}`;
  }

    function createJobRow(containerId, jobId, label, link) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const row = document.createElement('div');
        row.className = 'd-flex align-items-center justify-content-between border rounded p-2 mb-2';
        row.id = `job-${jobId}`;
        row.innerHTML = `
            <div class="text-white">
                <strong>${label}</strong>
                <div class="small">Job: ${jobId}</div>
                ${link ? `<div class=\"small\"><a href=\"${link}\" target=\"_blank\" rel=\"noopener\" class=\"text-primary text-decoration-underline\">${link}</a></div>` : ''}
                <div id="job-step-${jobId}" class="small text-info">Status: pending</div>
            </div>
            <div class="d-flex align-items-center gap-2">
                <div id="job-status-${jobId}" class="badge bg-secondary">pending</div>
                <button id="stop-job-${jobId}" class="btn btn-sm btn-outline-danger">Stop</button>
            </div>
        `;
        container.prepend(row);

        // Attach per-job Stop handler
        const stopBtn = document.getElementById(`stop-job-${jobId}`);
        const statusChip = document.getElementById(`job-status-${jobId}`);
        if (stopBtn) {
            stopBtn.addEventListener('click', async () => {
                try {
                    stopBtn.disabled = true;
                    if (statusChip) {
                        statusChip.className = 'badge bg-warning';
                        statusChip.textContent = 'stopped';
                    }
                    const res = await apiCall('/api/stop_promo', 'POST', { job_id: jobId });
                    if (!(res && res.success)) {
                        // Re-enable if stop failed
                        stopBtn.disabled = false;
                        if (statusChip) {
                            statusChip.className = 'badge bg-warning';
                            statusChip.textContent = 'stop_failed';
                        }
                    }
                } catch (e) {
                    // Error path: re-enable and mark
                    stopBtn.disabled = false;
                    if (statusChip) {
                        statusChip.className = 'badge bg-warning';
                        statusChip.textContent = 'stop_error';
                    }
                }
            });
        }
    }

    async function pollJob(jobId, onUpdate, onDone) {
        try {
            const data = await apiCall(`/api/job_status/${encodeURIComponent(jobId)}`);
            if (data && data.success) {
                const status = (data.status || '').toLowerCase();
                onUpdate(status, data.message);
                if (['success','failed','stopped'].includes(status)) {
                    onDone(status, data.message);
                    // Remove from persisted active list on terminal state
                    try { 
                        removeActiveJobId(jobId);
                        removeJobMeta(jobId);
                    } catch(_) {}
                    return false; // stop
                }
                return true; // keep polling
            } else {
                onDone('unknown', data && data.error ? data.error : 'Not Found');
                return false;
            }
        } catch (e) {
            onUpdate('warning', `Error polling: ${e.message}`);
            return true; // transient, continue polling
        }
    }

    function startPerJobPolling(jobId) {
        const statusChip = document.getElementById(`job-status-${jobId}`);
        const stepEl = document.getElementById(`job-step-${jobId}`);
        const stopBtn = document.getElementById(`stop-job-${jobId}`);
        let intervalId = null;
        
        // Try to restore countdown from localStorage (survives page refresh)
        const savedCountdown = getCountdownFromStorage(jobId);
        if (savedCountdown && savedCountdown.endAt && stepEl) {
            const now = Date.now();
            const remainingMs = savedCountdown.endAt - now;
            if (remainingMs > 0) {
                // Countdown is still active, restore it
                const remainingSecs = Math.ceil(remainingMs / 1000);
                console.log(`Restoring countdown for ${jobId}: ${remainingSecs}s remaining`);
                // Create a fake message with the loop progress to be parsed
                const fakeMsg = savedCountdown.loopProgress ? `Delay ${remainingSecs}s ${savedCountdown.loopProgress.replace(' -- ', '')}` : `Delay ${remainingSecs}s`;
                startJobCountdown(jobId, remainingSecs, stepEl, 'Status', fakeMsg);
            } else {
                // Countdown expired while page was unloaded
                clearCountdownFromStorage(jobId);
            }
        }
        
        // Poll function to be called both immediately and on interval
        const doPoll = async () => {
            const keep = await pollJob(
                jobId,
                (status, message) => {
                    if (statusChip) {
                        const map = {success:'bg-success', failed:'bg-danger', stopped:'bg-warning', running:'bg-info', pending:'bg-secondary', warning:'bg-warning'};
                        statusChip.className = `badge ${map[status]||'bg-secondary'}`;
                        statusChip.textContent = status;
                    }
                    if (stepEl) {
                        // Prefer server-provided message; fallback to status
                        let msg = (message && typeof message === 'string') ? message : status;
                        // Optional normalization example
                        if (/logging into doge?hype/i.test(msg)) {
                            msg = 'navigating to dogehype.com/login';
                        }
                        // Detect delay-before-next-loop and start live countdown
                        const delaySecs = parseDelaySeconds(msg);
                        if (delaySecs != null && /delay|next\s*loop|wait|cooldown|sleep/i.test(msg)) {
                            startJobCountdown(jobId, delaySecs, stepEl, 'Status', msg);
                        } else {
                            // If we previously had a countdown for this job, clear it
                            clearJobCountdown(jobId);
                            stepEl.textContent = `Status: ${msg}`;
                        }
                    }
                    // If finished, remove Stop button; if stopping, disable it
                    if (stopBtn) {
                        if (status === 'stopped' || status === 'failed' || status === 'success') {
                            stopBtn.remove();
                        }
                    }
                },
                () => {
                    clearInterval(intervalId);
                    delete jobPollers[jobId];
                    clearJobCountdown(jobId);
                    try { 
                        removeActiveJobId(jobId);
                        removeJobMeta(jobId);
                    } catch(_) {}
                    if (stopBtn) {
                        // On completion, remove the Stop button entirely
                        try { stopBtn.remove(); } catch (e) { /* ignore */ }
                    }
                }
            );
            if (!keep) {
                clearInterval(intervalId);
                delete jobPollers[jobId];
                if (stopBtn) {
                    try { stopBtn.remove(); } catch (e) { /* ignore */ }
                }
            }
        };
        
        // Poll immediately on job restore (don't wait 3 seconds)
        doPoll();
        
        // Then set up interval for subsequent polls
        intervalId = setInterval(doPoll, 3000);
        jobPollers[jobId] = intervalId;
    }

    // Format ISO datetime string
    function formatIsoDateTime(isoString) {
        if (!isoString) return 'N/A';
        try {
            // Handle potential 'Z' - replace with +00:00 for Date object parsing
             const date = new Date(isoString.replace('Z', '+00:00'));
             // Format locale-specific, more readable
             return date.toLocaleString(undefined, { // Use browser's locale
                 year: 'numeric', month: 'short', day: 'numeric',
                 hour: 'numeric', minute: '2-digit' //, second: '2-digit'
             });
        } catch (e) {
            console.error("Error formatting date:", isoString, e);
            return isoString; // Return original if parsing fails
        }
    }

    // --- Action Functions (Define BEFORE they are attached as listeners) ---
    // Start Single Promotion (Single Promo Section Specific)
    async function startSinglePromotion() {
        console.log("startSinglePromotion button clicked");
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const linkInput = document.getElementById('link-input');
        const quantityInput = document.getElementById('quantity-input');
        const startBtn = document.getElementById('start-single-promo-btn');
        const statusAreaId = 'single-promo-status-area';
        const statusMessageId = 'single-promo-status-message';

        if(!platformSelect || !engagementSelect || !linkInput || !quantityInput || !startBtn) {
            console.error("startSinglePromotion: Missing one or more required UI elements.");
            showStatus("UI Error: Cannot find promotion elements.", 'danger', statusAreaId, statusMessageId);
            return;
        }

        const platform = platformSelect.value;
        const engagement = engagementSelect.value;
        const link = linkInput.value.trim();
        const quantity = quantityInput.value.trim();
        // Resolve selected service (prefer saved override; else use dataset; else cheapest)
        let selectedService = null;
        // 1) Try override
        try {
            await loadServiceOverrides();
            const ov = getServiceOverride(platform, engagement);
            if (ov) {
                // Try to find in CSV list; if not available yet, construct minimal object
                let services = [];
                try { services = await loadServicesByCategory(platform, engagement); } catch(e) { services = []; }
                let svc = (services || []).find(s => {
                    const sp = canonicalProviderId(s.provider || s.provider_label);
                    const sid = (typeof s.service_id === 'string') ? parseInt(s.service_id) : s.service_id;
                    const ovid = (typeof ov.service_id === 'string') ? parseInt(ov.service_id) : ov.service_id;
                    return sp === canonicalProviderId(ov.provider) && sid === ovid;
                }) || null;
                if (!svc) {
                    svc = {
                        provider: ov.provider,
                        provider_label: ov.provider_label || ov.provider,
                        service_id: ov.service_id,
                        min_qty: ov.min_qty,
                        max_qty: ov.max_qty,
                        rate_per_1k: ov.rate_per_1k
                    };
                }
                selectedService = svc;
                try { engagementSelect.dataset.selectedService = JSON.stringify(svc); } catch(_) {}
                // Update bounds/cost based on override
                setSinglePromoQuantityBoundsFromService(selectedService);
                updateSingleCostDisplay(selectedService);
            }
        } catch(_) { /* ignore */ }
        // 2) If still not resolved, try dataset
        if (!selectedService) {
            try {
                if (engagementSelect && engagementSelect.dataset && engagementSelect.dataset.selectedService) {
                    selectedService = JSON.parse(engagementSelect.dataset.selectedService);
                }
            } catch (_) { selectedService = null; }
        }
        // 3) Fallback to cheapest
        if (!selectedService) {
            try {
                const services = await loadServicesByCategory(platform, engagement);
                if (services && services.length > 0) {
                    selectedService = services[0];
                    try { engagementSelect.dataset.selectedService = JSON.stringify(selectedService); } catch(_) {}
                    setSinglePromoQuantityBoundsFromService(selectedService);
                    updateSingleCostDisplay(selectedService);
                }
            } catch (e) { /* ignore */ }
        }

        if (!platform || !engagement) {
            showStatus("Please select Platform and Engagement type.", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }
        if (!link) {
            showStatus("Please enter the Link for the promotion.", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }
        if (!quantity) {
            showStatus("Please enter the Quantity for the promotion.", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }

        if (!selectedService) {
            showStatus("No service available for this engagement.", 'danger', statusAreaId, statusMessageId, 4000);
            return;
        }

        // Basic Link Validation
        if (!link.toLowerCase().startsWith('https://')) {
            showStatus("Link must start with https://", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }

        const quantityNum = parseInt(quantity, 10);
        if (isNaN(quantityNum) || quantityNum <= 0) {
            showStatus("Quantity must be a positive number.", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }

        // Strict per-service min/max validation (from CSV via selectedService)
        const svcMin = (selectedService.min_qty != null) ? parseInt(selectedService.min_qty, 10) : null;
        const svcMax = (selectedService.max_qty != null) ? parseInt(selectedService.max_qty, 10) : null;
        if (svcMin != null && quantityNum < svcMin) {
            showStatus(`Minimum quantity for this service is ${svcMin}.`, 'warning', statusAreaId, statusMessageId, 4000);
            return;
        }
        if (svcMax != null && quantityNum > svcMax) {
            showStatus(`Maximum quantity for this service is ${svcMax}.`, 'warning', statusAreaId, statusMessageId, 4000);
            return;
        }

        showStatus(`Scheduling single promo: ${quantity} of ${engagement} via service #${selectedService.service_id}...`, 'info', statusAreaId, statusMessageId);

        apiCall('/api/start_single_promo_by_service', 'POST', { 
                platform, 
                engagement, 
                service_id: selectedService.service_id, 
                link, 
                quantity: quantityNum 
            })
            .then(data => {
                if (data.success && data.job_id) {
                    const jobId = data.job_id;
                    showStatus(data.message || 'Single promo scheduled.', 'info', statusAreaId, statusMessageId);
                    // Create per-job row and start polling that job only
                    const svcName = (selectedService.name || ((selectedService.provider_label || selectedService.provider) + ' #' + selectedService.service_id));
                    const label = `Single Promo: ${engagement} — ${svcName}`;
                    createJobRow('single-promo-jobs', jobId, label, link);
                    try { 
                        addActiveJobId(jobId);
                        saveJobMeta(jobId, 'single-promo-jobs', label, link);
                    } catch(_) {}
                    startPerJobPolling(jobId);
                } else {
                    showStatus(data.error || 'Failed to schedule single promo.', 'danger', statusAreaId, statusMessageId);
                }
            })
            .catch(error => {
                 // API call helper already shows status
            });
    }

    // Start Profile-Based Promotion (Promo Page Specific)
    function startProfilePromotion(profileName, link, platform) { // Pass params directly
        console.log("startProfilePromotion called");
        const statusAreaId = 'promo-status-area';
        const statusMessageId = 'promo-status-message';

        // Validation already done in the event listener
        showStatus(`Scheduling profile promo: '${profileName}' (${platform}) for ${link}...`, 'info', statusAreaId, statusMessageId);

        apiCall('/api/start_promo', 'POST', { profile_name: profileName, link: link, platform: platform })
             .then(data => {
                if (data.success && data.job_id) {
                    const jobId = data.job_id;
                    currentProfileJobId = jobId; // maintained for legacy references
                    showStatus(data.message || `Profile promo '${profileName}' scheduled. Job ID: ${jobId}`, 'info', statusAreaId, statusMessageId);
                    // Create per-job row and start per-job polling (like single promo)
                    const label = `Auto Promo: ${profileName}${platform ? ' — ' + platform : ''}`;
                    createJobRow('auto-promo-jobs', jobId, label, link);
                    try { 
                        addActiveJobId(jobId);
                        saveJobMeta(jobId, 'auto-promo-jobs', label, link);
                    } catch(_) {}
                    startPerJobPolling(jobId);
                } else {
                    showStatus(data.error || 'Failed to schedule profile promo.', 'danger', statusAreaId, statusMessageId);
                }
            })
            .catch(error => {
                 // API call helper already shows status
            });
    }
    
    // --- Polling Functions ---
    function startStatusPolling(jobId) {
        stopStatusPolling(); // Clear any existing interval
        console.log(`Starting status polling for Job ID: ${jobId}`);
        showStatus(`Job ${jobId} running... Polling status.`, 'info', 'promo-status-area', 'promo-status-message'); // Use specific area
        
        // Ensure stop button is enabled during polling
        // Deprecated: global stop button per requirements. Per-job stop buttons are created in rows.
        
        statusCheckInterval = setInterval(async () => {
            // Make checkJobStatus async if it wasn't already
            await checkJobStatus(jobId);
        }, 3000); // Check every 3 seconds
    }

    function stopStatusPolling() {
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
            console.log("Stopped status polling.");
        }
        // Don't reset currentProfileJobId here, handleFinalJobStatus does that.
    }

    async function checkJobStatus(jobId) {
        console.log(`Polling status for Job ID: ${jobId}`);
        if (!jobId) return;
        // Check if this is still the job we care about
        if (jobId !== currentProfileJobId) {
             console.log(`Polling stopped for ${jobId} because current job is now ${currentProfileJobId}`);
             stopStatusPolling(); // Stop polling for this old job
             return;
        }

        try {
            const data = await apiCall(`/api/job_status/${encodeURIComponent(jobId)}`);
            if (data.success) {
                const status = data.status.toLowerCase();
                const message = data.message || status;
                // Only update primary status if it's still the current job
                showStatus(`Job Status: ${status} - ${message}`, 'info', 'promo-status-area', 'promo-status-message'); // Update message too

                if (status === 'success' || status === 'failed' || status === 'stopped') {
                     showStatus(`Job ${jobId} finished with status: ${status}. ${message}`, 
                                status === 'success' ? 'success' : (status === 'failed' ? 'danger' : 'warning'), 
                                'promo-status-area', 'promo-status-message', 5000); // Show final status briefly
                     handleFinalJobStatus(jobId); // Call handler to stop polling & enable buttons
                 }
                 // else keep polling ('pending' or 'running' or 'stopping')
            } else {
                 // Job ID might disappear if server restarts or cleans up, or API returns error
                 console.warn(`Job ID ${jobId} status check failed: ${data.error || 'Not Found'}. Stopping poll.`);
                 showStatus(`Job ${jobId} status unknown or finished (${data.error || 'Not Found'}).`, 'warning', 'promo-status-area', 'promo-status-message', 5000);
                 handleFinalJobStatus(jobId); // Stop polling & enable buttons
            }
         } catch (error) {
             console.error(`Error polling job status for ${jobId}:`, error);
             // Don't necessarily stop polling on transient network errors
             // Show temporary error in status bar
             showStatus(`Error checking job status for ${jobId}. Retrying... (${error.message})`, 'warning', 'promo-status-area', 'promo-status-message');
         }
     }
     
    // --- Button Enable/Disable --- 
    function disableActionButtons() {
        console.log("Disabling action buttons...");
        const singlePromoBtn = document.getElementById('start-single-promo-btn');
        const profilePromoBtn = document.getElementById('start-profile-promo-btn');
        const stopBtn = document.getElementById('stop-profile-btn'); // Also manage stop button
        if(singlePromoBtn) singlePromoBtn.disabled = true;
        if(profilePromoBtn) profilePromoBtn.disabled = true;
        if(stopBtn) stopBtn.disabled = true; // Usually disable stop too initially
    }

    function enableActionButtons() {
        console.log("Enabling action buttons...");
        const singlePromoBtn = document.getElementById('start-single-promo-btn');
        const profilePromoBtn = document.getElementById('start-profile-promo-btn');
        if(singlePromoBtn) singlePromoBtn.disabled = false;
        if(profilePromoBtn) profilePromoBtn.disabled = false;
        // Per-job stop buttons are managed within each job row
    }

    // --- Initialization Functions (Define BEFORE first use) ---
    async function initializeAppCommon() {
        console.log("Initializing common app components (loading data)... ");
        let localProfilesData = {}; // Local variable to store loaded profiles
        const results = await Promise.allSettled([
            // Modify loadProfiles call to store result locally
            (async () => { 
                localProfilesData = await loadProfiles(); 
                return localProfilesData; // Explicitly return for promise settlement
            })(),
            loadMinimumQuantities()
        ]);
        console.log("Common init data load results:", results);
        if (results[0].status === 'rejected') {
            console.error("Failed to load profiles during init.");
        }
        if (results[1].status === 'rejected') {
            console.error("Failed to load minimum quantities during init.");
        }
        // Return the loaded profiles data (might be empty on error)
        return localProfilesData; 
    }

    async function loadProfiles() {
        console.log("Executing loadProfiles...");
        try {
            // Assign to global cache AND return the data
            profilesDataCache = await apiCall('/api/profiles');
            console.log("loadProfiles fetched data successfully into cache:", profilesDataCache);
            return profilesDataCache; // Return the loaded data
            } catch (error) {
            console.error("Error caught in loadProfiles:", error);
            profilesDataCache = {}; // Reset cache on error
            return {}; // Return empty object on error
            // throw error; // Let initializeAppCommon handle logging
        }
    }

    async function loadMinimumQuantities() {
        console.log("Executing loadMinimumQuantities...");
        try {
            minimumQuantities = await apiCall('/api/config/minimums');
            console.log("loadMinimumQuantities completed successfully:", minimumQuantities);
        } catch (error) {
            console.error("Error caught in loadMinimumQuantities:", error);
            minimumQuantities = {}; // Reset cache on error
            throw error; // Re-throw to be caught by Promise.allSettled
        }
    }

    // --- Services (CSV-backed) helpers ---
    async function loadPlatformsFromServer() {
        const res = await apiCall('/api/services/platforms');
        if (res && res.success) return res.platforms || [];
        return [];
    }

    async function loadEngagementsFromServer(platform) {
        const res = await apiCall(`/api/services/engagements?platform=${encodeURIComponent(platform)}`);
        if (res && res.success) return res.engagements || [];
        return [];
    }

    async function loadServicesByCategory(platform, engagement) {
        const url = `/api/services/by_category?platform=${encodeURIComponent(platform)}&engagement=${encodeURIComponent(engagement)}`;
        const res = await apiCall(url);
        if (res && res.success) return res.services || [];
        return [];
    }

    // Apply per-service quantity bounds to Single Promo input
    function setSinglePromoQuantityBoundsFromService(svc) {
        const qtyInput = document.getElementById('quantity-input');
        if (!qtyInput || !svc) return;
        const minQ = (svc.min_qty != null) ? parseInt(svc.min_qty, 10) : null;
        const maxQ = (svc.max_qty != null) ? parseInt(svc.max_qty, 10) : null;
        // Set attributes
        if (minQ != null) qtyInput.min = String(minQ); else qtyInput.removeAttribute('min');
        if (maxQ != null) qtyInput.max = String(maxQ); else qtyInput.removeAttribute('max');
        // Adjust current value into range if set
        const cur = parseInt(qtyInput.value || '');
        if (!isNaN(cur)) {
            let adj = cur;
            if (minQ != null && adj < minQ) adj = minQ;
            if (maxQ != null && adj > maxQ) adj = maxQ;
            qtyInput.value = String(adj);
        }
        // Set placeholder to show bounds
        const minTxt = (minQ != null) ? minQ : '';
        const maxTxt = (maxQ != null) ? maxQ : '';
        if (minTxt !== '' || maxTxt !== '') {
            qtyInput.placeholder = `${minTxt !== '' ? minTxt : ''}${(minTxt !== '' || maxTxt !== '') ? ' - ' : ''}${maxTxt !== '' ? maxTxt : ''}`.trim();
        }
        // Immediately refresh cost display reflecting any adjusted value
        try { updateSingleCostDisplay(svc); } catch(_) {}
    }

    function clearSinglePromoQuantityBounds() {
        const qtyInput = document.getElementById('quantity-input');
        if (!qtyInput) return;
        qtyInput.removeAttribute('min');
        qtyInput.removeAttribute('max');
        qtyInput.placeholder = '';
    }

    // --- Cost helpers ---
    function formatCurrency(val, digits = 6) {
        if (val == null || isNaN(val)) return '-';
        try { return `$${Number(val).toFixed(digits)}`; } catch { return '-'; }
    }

    function updateSingleCostDisplay(selectedService = null) {
        const el = document.getElementById('single-cost-display');
        const svcInfoEl = document.getElementById('single-service-info');
        const qtyInput = document.getElementById('quantity-input');
        const engagementSelect = document.getElementById('engagement-select');
        const platformSelect = document.getElementById('platform-select');
        if (!el) return;
        let svc = selectedService;
        // Prefer saved override
        const platform = platformSelect ? platformSelect.value : '';
        const engagement = engagementSelect ? engagementSelect.value : '';
        let ov = null;
        if (platform && engagement && serviceOverridesCache) {
            try { ov = getServiceOverride(platform, engagement); } catch(_) { ov = null; }
        }
        if (!ov && platform && engagement && !serviceOverridesCache) {
            loadServiceOverrides().then(() => {
                updateSingleCostDisplay(selectedService);
            }).catch(() => {});
        }
        if (ov) {
            svc = {
                provider: ov.provider,
                provider_label: ov.provider_label || ov.provider,
                service_id: ov.service_id,
                min_qty: ov.min_qty,
                max_qty: ov.max_qty,
                rate_per_1k: ov.rate_per_1k
            };
            try { if (engagementSelect && engagementSelect.dataset) engagementSelect.dataset.selectedService = JSON.stringify(svc); } catch(_) {}
        }
        if (!svc && engagementSelect && engagementSelect.dataset && engagementSelect.dataset.selectedService) {
            try { svc = JSON.parse(engagementSelect.dataset.selectedService); } catch(_) { svc = null; }
        }
        if (!svc) {
            el.textContent = '';
            if (svcInfoEl) svcInfoEl.textContent = '';
            return;
        }
        if (svcInfoEl) {
            const prov = (svc.provider || svc.provider_label || '').toString().toLowerCase();
            let provAbbr = (svc.provider_label || svc.provider || '').toString().toUpperCase().replace(/\s+/g, '');
            if (prov === 'justanotherpanel') provAbbr = 'JAP';
            else if (prov === 'peakerr') provAbbr = 'PEAKERR';
            else if (prov === 'smmkings') provAbbr = 'SMMK';
            else if (prov === 'mysocialsboost') provAbbr = 'MSB';
            svcInfoEl.textContent = `${provAbbr} #${svc.service_id}`;
        }
        const rate = (svc.rate_per_1k != null) ? parseFloat(svc.rate_per_1k) : null;
        const qty = qtyInput ? parseInt(qtyInput.value || '0', 10) : 0;
        const cost = (rate != null && !isNaN(qty)) ? (rate * qty / 1000.0) : null;
        el.textContent = (cost != null) ? `Total Quantity: ${qty.toLocaleString()} -- Total Cost: ${formatCurrency(cost)}` : '';
    }

    function clearSingleCostDisplay() {
        const el = document.getElementById('single-cost-display');
        if (el) el.textContent = '';
        const svcInfoEl = document.getElementById('single-service-info');
        if (svcInfoEl) svcInfoEl.textContent = '';
    }

    // CSV is source of truth. No hardcoded fallback engagements.
    function getFallbackEngagements(_platform) {
        return [];
    }

    function populateSelectOptions(selectEl, options, { includePlaceholder = true, placeholderText = '-- Select --' } = {}) {
        if (!selectEl) return;
        while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
        if (includePlaceholder) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = placeholderText;
            selectEl.appendChild(opt);
        }
        options.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v;
            opt.textContent = v;
            selectEl.appendChild(opt);
        });
    }

    // --- Services Flyout UI ---
    let currentFlyoutEl = null;
    function closeFlyout() {
        if (currentFlyoutEl && currentFlyoutEl.parentNode) {
            currentFlyoutEl.parentNode.removeChild(currentFlyoutEl);
        }
        currentFlyoutEl = null;
        document.removeEventListener('click', onDocClickClose);
        document.removeEventListener('keydown', onEscClose);
    }
    function onDocClickClose(e) {
        if (!currentFlyoutEl) return;
        if (currentFlyoutEl.contains(e.target)) return;
        closeFlyout();
    }
    function onEscClose(e) {
        if (e.key === 'Escape') closeFlyout();
    }
    function positionFlyout(anchor, flyout) {
        const rect = anchor.getBoundingClientRect();
        const top = rect.top + window.scrollY;
        const left = rect.right + window.scrollX + 8; // show to the right
        flyout.style.top = `${top}px`;
        flyout.style.left = `${left}px`;
    }
    function renderServicesFlyout(anchorEl, platform, engagement, services, onPick) {
        // Auto-pick the first/only service; no UI flyout
        closeFlyout();
        const svc = (services && services.length > 0) ? services[0] : null;
        if (svc && typeof onPick === 'function') {
            onPick(svc);
        }
        return; // no DOM changes
    }

    async function showServicesFlyoutForSelect(platformEl, engagementEl) {
        if (!platformEl || !engagementEl) return;
        const platform = platformEl.value;
        const engagement = engagementEl.value || engagementEl.options[engagementEl.selectedIndex]?.textContent;
        if (!platform || !engagement) return;
        let services = [];
        try {
            services = await loadServicesByCategory(platform, engagement);
        } catch (e) { services = []; }
        renderServicesFlyout(engagementEl, platform, engagement, services);
    }

    // --- Custom Engagement Dropdown (so we can anchor flyout to the hovered item) ---
    function ensureCustomEngagementDropdown(selectEl, platformEl, idPrefix) {
        if (!selectEl || !platformEl) return null;
        // If already created, return elements
        const existingBtn = document.getElementById(`${idPrefix}-eng-btn`);
        const existingMenu = document.getElementById(`${idPrefix}-eng-menu`);
        if (existingBtn && existingMenu) return { btn: existingBtn, menu: existingMenu };

        // Hide the native select but keep it for form value and compatibility
        selectEl.style.display = 'none';
        selectEl.style.position = 'absolute';
        selectEl.style.pointerEvents = 'none';
        selectEl.style.opacity = '0';
        const parent = selectEl.parentElement;
        const wrap = document.createElement('div');
        wrap.className = 'position-relative';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-secondary w-100';
        btn.id = `${idPrefix}-eng-btn`;
        btn.textContent = '-- Select Engagement --';
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu show';
        menu.id = `${idPrefix}-eng-menu`;
        menu.style.display = 'none';
        menu.style.position = 'absolute';
        menu.style.zIndex = '1050';
        menu.style.maxHeight = '320px';
        menu.style.overflow = 'auto';
        menu.style.width = '100%';

        wrap.appendChild(btn);
        wrap.appendChild(menu);
        // Label to show chosen subcategory (service)
        // Always create for logic consistency, but hide it for 'single' to avoid duplicate display
        const subLabel = document.createElement('div');
        subLabel.id = `${idPrefix}-eng-selected-sub`;
        subLabel.className = 'text-muted small mt-1';
        subLabel.textContent = '';
        if (idPrefix === 'single' || idPrefix === 'modal') subLabel.style.display = 'none';
        wrap.appendChild(subLabel);
        // Place custom control right after the hidden select
        selectEl.insertAdjacentElement('afterend', wrap);
        console.log(`[CustomEngagement] Created custom control '${idPrefix}'`);

        function openMenu() {
            menu.style.display = 'block';
            const rect = btn.getBoundingClientRect();
            menu.style.top = `${btn.offsetTop + btn.offsetHeight}px`;
            menu.style.left = `${btn.offsetLeft}px`;
            document.addEventListener('click', onDocClickCloseMenu, { capture: true });
        }
        function closeMenu() {
            menu.style.display = 'none';
            document.removeEventListener('click', onDocClickCloseMenu, { capture: true });
        }
        function onDocClickCloseMenu(e) {
            if (menu.contains(e.target) || btn.contains(e.target)) return;
            closeMenu();
        }
        btn.addEventListener('click', () => {
            if (menu.style.display === 'none') openMenu(); else closeMenu();
        });

        // Public API to set items
        function setItems(engagements) {
            // Clear
            while (menu.firstChild) menu.removeChild(menu.firstChild);
            if (!engagements || engagements.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'dropdown-item disabled';
                empty.textContent = 'No engagements';
                menu.appendChild(empty);
                btn.textContent = '-- Select Engagement --';
                return;
            }
            engagements.forEach(eng => {
                const item = document.createElement('a');
                item.href = '#';
                item.className = 'dropdown-item';
                item.textContent = eng;
                // Click -> select engagement and auto-pick first service
                item.addEventListener('click', async (ev) => {
                    ev.preventDefault();
                    const platform = platformEl.value;
                    if (!platform) return;
                    selectEl.value = eng;
                    let services = [];
                    try { services = await loadServicesByCategory(platform, eng); } catch(e) { services = []; }
                    // Prefer saved override if present (guarded)
                    let ov = null;
                    try {
                        await loadServiceOverrides();
                        ov = getServiceOverride(platform, eng);
                    } catch(_) { ov = null; }
                    let svc = null;
                    if (ov) {
                        // Try to find exact match in CSV services
                        svc = (services || []).find(s => {
                            const sp = canonicalProviderId(s.provider || s.provider_label);
                            const sid = (typeof s.service_id === 'string') ? parseInt(s.service_id) : s.service_id;
                            const ovid = (typeof ov.service_id === 'string') ? parseInt(ov.service_id) : ov.service_id;
                            return sp === canonicalProviderId(ov.provider) && sid === ovid;
                        }) || null;
                        if (!svc) {
                            // Construct minimal service object from override
                            svc = {
                                provider: ov.provider,
                                provider_label: ov.provider_label || ov.provider,
                                service_id: ov.service_id,
                                min_qty: ov.min_qty,
                                max_qty: ov.max_qty,
                                rate_per_1k: ov.rate_per_1k
                            };
                        }
                    }
                    if (!svc) {
                        svc = (services && services.length > 0) ? services[0] : null;
                    }
                    if (svc) {
                        try { selectEl.dataset.selectedService = JSON.stringify(svc); } catch(_) {}
                        // Show only the engagement in the selector UI
                        if (subLabel) subLabel.textContent = `${eng}`;
                        if (btn) btn.textContent = `${eng}`;
                        if (idPrefix === 'single') {
                            setSinglePromoQuantityBoundsFromService(svc);
                            updateSingleCostDisplay(svc);
                        }
                    } else {
                        // Clear selection if none available
                        try { delete selectEl.dataset.selectedService; } catch(_) {}
                        if (subLabel) subLabel.textContent = `${eng}`;
                        btn.textContent = `${eng}`;
                    }
                    try { if (typeof closeMenu === 'function') closeMenu(); } catch(_) {}
                });
                menu.appendChild(item);
            });
            // Restore selected service label if exists
            if (selectEl.dataset.selectedService) {
                try {
                    const svc = JSON.parse(selectEl.dataset.selectedService);
                    const eng = selectEl.value || '';
                    if (eng) {
                        // On restore, also show only engagement
                        subLabel.textContent = `${eng}`;
                        if (idPrefix === 'single') btn.textContent = `${eng}`;
                        // Ensure bounds and cost display reflect restored service
                        if (idPrefix === 'single') {
                            setSinglePromoQuantityBoundsFromService(svc);
                            updateSingleCostDisplay(svc);
                        }
                    }
                } catch (_) { /* ignore */ }
            } else {
                // If no saved selection, try to reflect override silently
                try {
                    const eng = selectEl.value || '';
                    const platform = platformEl.value || '';
                    const applyFromOverride = (ov) => {
                        if (!ov) return;
                        const constructed = {
                            provider: ov.provider,
                            provider_label: ov.provider_label || ov.provider,
                            service_id: ov.service_id,
                            min_qty: ov.min_qty,
                            max_qty: ov.max_qty,
                            rate_per_1k: ov.rate_per_1k
                        };
                        try { selectEl.dataset.selectedService = JSON.stringify(constructed); } catch(_) {}
                        if (idPrefix === 'single') {
                            setSinglePromoQuantityBoundsFromService(constructed);
                            updateSingleCostDisplay(constructed);
                        }
                        // Also reflect engagement label
                        if (subLabel) subLabel.textContent = `${eng}`;
                        if (btn) btn.textContent = `${eng}`;
                    };
                    if (eng && platform) {
                        // Use cache immediately if available
                        if (serviceOverridesCache) {
                            applyFromOverride(getServiceOverride(platform, eng));
                        }
                        // Refresh overrides asynchronously and apply if still relevant
                        loadServiceOverrides().then(() => {
                            if ((selectEl.value || '') === eng && (platformEl.value || '') === platform && !selectEl.dataset.selectedService) {
                                applyFromOverride(getServiceOverride(platform, eng));
                            }
                        }).catch(()=>{});
                    }
                } catch(_) {}
                // Do not clear labels here to avoid wiping out state set above
            }
        }

        return { btn, menu, setItems };
    }

    // --- Single Promo page init ---
    async function initializeSinglePromoPage() {
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const runBtn = document.getElementById('start-single-promo-btn');
        const qtyInput = document.getElementById('quantity-input');
        if (!platformSelect || !engagementSelect || !runBtn) {
            console.log('Single Promo elements not found; skipping initializeSinglePromoPage');
            return;
        }
        // Warm overrides so engagement picks reflect current selection immediately
        try { await loadServiceOverrides(); } catch(_) {}
        // Create custom engagement dropdown so we can anchor flyout to items
        const singleCustom = (typeof ensureCustomEngagementDropdown === 'function')
            ? ensureCustomEngagementDropdown(engagementSelect, platformSelect, 'single')
            : null;

        // Populate platforms
        try {
            let platforms = await loadPlatformsFromServer();
            if (!platforms || platforms.length === 0) {
                console.warn('Platforms API returned empty list. Using fallback set.');
                platforms = ['Instagram','TikTok','YouTube','X (Twitter)','Spotify'];
            }
            populateSelectOptions(platformSelect, platforms);
            // Auto-load engagements when platform changes
            platformSelect.addEventListener('change', async () => {
                const p = platformSelect.value;
                if (!p) {
                    populateSelectOptions(engagementSelect, []);
                    if (singleCustom && singleCustom.setItems) singleCustom.setItems([]);
                    // Reset visual state
                    const lbl = document.getElementById('single-eng-selected-sub');
                    if (lbl) lbl.textContent = '';
                    const btnEl = document.getElementById('single-eng-btn');
                    if (btnEl) btnEl.textContent = '-- Select Engagement --';
                    return;
                }
                const engs = await loadEngagementsFromServer(p);
                populateSelectOptions(engagementSelect, engs);
                if (singleCustom && singleCustom.setItems) singleCustom.setItems(engs);
                // Reset selection label/button on platform change
                try { delete engagementSelect.dataset.selectedService; } catch(_) {}
                clearSinglePromoQuantityBounds();
                const lbl = document.getElementById('single-eng-selected-sub');
                if (lbl) lbl.textContent = '';
                const btnEl = document.getElementById('single-eng-btn');
                if (btnEl) btnEl.textContent = '-- Select Engagement --';
            });
            // If first option exists, trigger change to load engagements
            if (platforms && platforms.length > 0) {
                platformSelect.value = '';
                // Select first real option
                platformSelect.selectedIndex = 1; // 0 is placeholder
                const engs = await loadEngagementsFromServer(platformSelect.value);
                populateSelectOptions(engagementSelect, engs);
                if (singleCustom && singleCustom.setItems) singleCustom.setItems(engs);
                // Clear any prior selection
                try { delete engagementSelect.dataset.selectedService; } catch(_) {}
                clearSinglePromoQuantityBounds();
                const lbl2 = document.getElementById('single-eng-selected-sub');
                if (lbl2) lbl2.textContent = '';
                const btn2 = document.getElementById('single-eng-btn');
                if (btn2) btn2.textContent = '-- Select Engagement --';
            }
        } catch (e) {
            console.error('Failed to populate platforms/engagements:', e);
            // Last-chance fallback
            populateSelectOptions(platformSelect, ['Instagram','TikTok','YouTube','X (Twitter)','Spotify']);
        }

        // Attach Run handler
        runBtn.addEventListener('click', startSinglePromotion);
        // Recalculate Single Promo cost on any quantity change
        const qtyInput2 = document.getElementById('quantity-input');
        if (qtyInput2) {
            const recalc = () => updateSingleCostDisplay();
            qtyInput2.addEventListener('input', recalc);
            qtyInput2.addEventListener('change', recalc);
            qtyInput2.addEventListener('keyup', recalc);
        }
        singleReady = true;
        updateGlobalReadyStatus();
    }

    // --- Promo page init (profile-based run/stop buttons) ---
    async function initializePromoPage(profiles) {
        const runBtn = document.getElementById('start-profile-promo-btn');
        const stopBtn = document.getElementById('stop-profile-btn');
        const profileSelect = document.getElementById('profile-select-promo');
        const linkInput = document.getElementById('profile-link-input');
        // Auto cost preview
        async function updateAutoCost() {
            const profileName = profileSelect ? profileSelect.value : '';
            const el = document.getElementById('auto-cost-display');
            if (!el) return;
            if (!profileName) { el.textContent=''; return; }
            try {
                const payload = { profile_name: profileName };
                const res = await apiCall('/api/estimate/auto_cost', 'POST', payload);
                if (res && res.success) {
                    el.textContent = `Estimated Total Cost: ${formatCurrency(res.total_cost)} (${res.loops} loop(s))`;
                } else {
                    el.textContent = '';
                }
            } catch (e) {
                if (el) el.textContent = '';
            }
        }
        if (profileSelect) profileSelect.addEventListener('change', updateAutoCost);
        setTimeout(updateAutoCost, 0);

        if (runBtn) {
            runBtn.addEventListener('click', () => {
                const profileName = profileSelect ? profileSelect.value : '';
                const link = linkInput ? (linkInput.value || '').trim() : '';
                if (!profileName) {
                    showStatus('Please select a profile.', 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link || !link.startsWith('https://')) {
                    showStatus('Please enter a valid https:// link.', 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                startProfilePromotion(profileName, link);
            });
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', async () => {
                if (!currentProfileJobId) return;
                try {
                    stopBtn.disabled = true;
                    const res = await apiCall('/api/stop_promo', 'POST', { job_id: currentProfileJobId });
                    if (!(res && res.status === 'success')) stopBtn.disabled = false;
                } catch (e) {
                    stopBtn.disabled = false;
                }
            });
        }
        promoReady = true;
        updateGlobalReadyStatus();
    }

    // --- Balances page init ---
    async function initializeBalancesPage() {
        const providers = ['justanotherpanel', 'peakerr', 'smmkings', 'mysocialsboost'];
        const timers = {};

        async function fetchBalance(provider) {
            try {
                const data = await apiCall(`/api/balances/${provider}`);
                const td = document.getElementById(`balance-value-${provider}`);
                if (td) {
                    if (data && data.success && data.data) {
                        const bal = data.data.balance || data.data.Balance || data.data.raw || '—';
                        const cur = data.data.currency || '';
                        td.textContent = cur ? `${bal} ${cur}` : `${bal}`;
                    } else {
                        td.textContent = 'Error';
                    }
                }
            } catch (e) {
                const td = document.getElementById(`balance-value-${provider}`);
                if (td) td.textContent = 'Error';
            }
        }

        function startAuto(provider) {
            const intervalInput = document.getElementById(`interval-${provider}`);
            const enabled = document.getElementById(`auto-${provider}`)?.checked;
            if (timers[provider]) {
                clearInterval(timers[provider]);
                delete timers[provider];
            }
            if (!enabled) return;
            let sec = 60;
            try { sec = Math.max(10, parseInt(intervalInput.value, 10) || 60); } catch (e) { sec = 60; }
            timers[provider] = setInterval(() => fetchBalance(provider), sec * 1000);
        }

        // Wire buttons and switches
        providers.forEach(p => {
            const btn = document.getElementById(`btn-fetch-${p}`);
            if (btn) btn.addEventListener('click', () => fetchBalance(p));
            const chk = document.getElementById(`auto-${p}`);
            if (chk) chk.addEventListener('change', () => startAuto(p));
            const inp = document.getElementById(`interval-${p}`);
            if (inp) inp.addEventListener('change', () => startAuto(p));
        });

        // Initial one-shot fetch for all
        providers.forEach(p => fetchBalance(p));
    }

    // --- Run Initialization (FIRST IIFE) --- 
    (async () => {
        const statusAreaId = 'status-text'; // ID of the status div
        const statusMessageId = 'status-text'; // Using the same ID for the message part
        try {
            const loadedProfiles = await initializeAppCommon(); // Loads data into caches, GETS PROFILES
            
            // --- Page Detection (Moved Here) ---
            const isOnPromoPage = !!document.getElementById('start-profile-promo-btn'); // Promo page detection
            const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
            const isOnBalancesPage = !!document.getElementById('balances-root');
            const isOnProfilePage = !!document.getElementById('add-profile-btn'); 
            const isOnHistoryPage = !!document.getElementById('history-list'); // Check for History page
            console.log(`Page Check (Inside IIFE): Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}, History=${isOnHistoryPage}`);

            // --- ALWAYS Try to Populate Common Dropdowns AFTER Data Load ---
            // This handles the index page case where specific page init might not run
            const profileSelectPromoElem = document.getElementById('profile-select-promo');
            if (profileSelectPromoElem) {
                 console.log("Attempting to populate #profile-select-promo globally after init...");
                 populateProfileDropdown(profileSelectPromoElem, loadedProfiles);
             } else {
                 console.log("#profile-select-promo not found during global init.");
             }
            const profileSelectProfilePageElem = document.getElementById('profile-select');
            if (profileSelectProfilePageElem) {
                 console.log("Attempting to populate #profile-select globally after init...");
                 populateProfileDropdown(profileSelectProfilePageElem, loadedProfiles);
             } else {
                 console.log("#profile-select not found during global init.");
             }
            // ---

            // Page-specific initializations (These might re-populate or add listeners)
            if (isOnPromoPage) {
                console.log("Running Promo Page specific init...");
                // Pass loaded profiles to avoid race condition
                await initializePromoPage(loadedProfiles);
                await initializeSinglePromoPage();
                // Moved status message inside initializePromoPage for better timing
                // setTimeout(() => { showStatus("Promo Page Ready", "success", "promo-status-area", "promo-status-message", 3000); }, 10); 
            } else if (isOnMonitorPage) {
                console.log("Running Monitor Page specific init...");
                // Pass loaded profiles to avoid race condition
                await initializeMonitorPage(loadedProfiles); // Needs loaded profiles for dropdown
                // Show status after init completes
                // setTimeout(() => { showStatus("Monitor Page Ready", "success", "monitor-page-status-area", "monitor-page-status-message", 3000); }, 10); // <<< REMOVED THIS LINE
            } else if (isOnBalancesPage) {
                console.log("Running Balances Page specific init...");
                await initializeBalancesPage();
            } else if (isOnProfilePage) { 
                 console.log("Running Profile Page specific init...");
                 // Pass loaded profiles to avoid race condition
                 initializeProfilePage(loadedProfiles);
                 // Populate dropdown is now handled globally or within initializeProfilePage
                 // const profileSelectProfilePage = document.getElementById('profile-select'); // Get specific element
                 // if (profileSelectProfilePage) { // Populate correct dropdown
                 //     populateProfileDropdown(profileSelectProfilePage, loadedProfiles);
                 // } else {
                 //     console.error("Could not find profile select dropdown on Profile page.");
                 // }
                 // setTimeout(() => { showStatus("Profile Page Ready", "success", "profile-page-status-area", "profile-page-status-message", 3000); }, 10); // <<< REMOVED THIS LINE
                 
                 // Setup import handler
                 const importProfilesBtn = document.getElementById('import-profiles-btn');
                 const importProfilesFile = document.getElementById('import-profiles-file');
                 if (importProfilesBtn && importProfilesFile) {
                     importProfilesBtn.addEventListener('click', () => {
                         importProfilesFile.click();
                     });
                     importProfilesFile.addEventListener('change', async (e) => {
                         const file = e.target.files[0];
                         if (!file) return;
                         if (!file.name.endsWith('.json')) {
                             alert('Please select a JSON file');
                             return;
                         }
                         const formData = new FormData();
                         formData.append('file', file);
                         try {
                             showStatus('Importing profiles...', 'info', 'profile-page-status-area', 'profile-page-status-message');
                             const res = await fetch('/api/import/profiles', { method: 'POST', body: formData });
                             const data = await res.json();
                             if (data.success) {
                                 showStatus(data.message || 'Import successful! Reloading...', 'success', 'profile-page-status-area', 'profile-page-status-message', 2000);
                                 setTimeout(() => { location.reload(); }, 2000);
                             } else {
                                 showStatus('Import failed: ' + (data.error || 'Unknown error'), 'danger', 'profile-page-status-area', 'profile-page-status-message');
                             }
                         } catch (err) {
                             showStatus('Error importing: ' + err.message, 'danger', 'profile-page-status-area', 'profile-page-status-message');
                         }
                         importProfilesFile.value = '';
                     });
                 }
            } else if (isOnHistoryPage) {
                console.log("Running History Page specific init...");
                // Live status polling for History
                function formatHistoryStatusText(text) {
                    const s = (text == null) ? '' : String(text);
                    // Replace standalone 'failed' with 'Stopped', preserve other tokens
                    return s.replace(/\bfailed\b/gi, 'Stopped');
                }
                function applyStatusClass(cell, status) {
                    const base = 'status-cell';
                    const s = (status || '').toLowerCase();
                    // Map statuses to Bootstrap text color classes
                    let textClass = 'text-white'; // default for loading/unknown
                    if (s === 'cancel' || s === 'canceled' || s === 'cancelled' || s === 'failed' || s === 'stopped') {
                        textClass = 'text-danger'; // red
                    } else if (s === 'completed' || s === 'success' || s === 'finished' || s === 'done') {
                        textClass = 'text-success'; // green
                    } else if (s === 'pending' || s === 'queued') {
                        textClass = 'text-warning'; // yellow
                    } else if (s === 'before' || s === 'in-progress' || s === 'in_progress' || s === 'running' || s === 'processing') {
                        textClass = 'text-primary'; // blue
                    } else if (s === 'loading') {
                        textClass = 'text-white'; // white
                    }
                    // Bold for Processing, Cancel, Completed, Pending (and aliases)
                    const shouldBold = (
                        s === 'processing' || s === 'in-progress' || s === 'in_progress' || s === 'running' ||
                        s === 'cancel' || s === 'canceled' || s === 'cancelled' || s === 'failed' || s === 'stopped' ||
                        s === 'completed' || s === 'success' || s === 'finished' || s === 'done' ||
                        s === 'pending' || s === 'queued'
                    );
                    const weightClass = shouldBold ? 'fw-bold' : '';
                    cell.className = `${base} ${textClass} ${weightClass} status-${s}`.trim();
                    cell.textContent = formatHistoryStatusText((status||'unknown').charAt(0).toUpperCase() + (status||'unknown').slice(1));
                }
                function getQueryParam(name) {
                    const params = new URLSearchParams(window.location.search);
                    return params.get(name);
                }
                function getVisibleHistoryRows() {
                    return Array.from(document.querySelectorAll('#history-list tbody tr[data-job-id]'));
                }
                async function fetchAndRenderForRow(row) {
                    const jobId = row && row.getAttribute('data-job-id');
                    if (!jobId) return;
                    try {
                        const res = await apiCall(`/api/history/live_status?job_id=${encodeURIComponent(jobId)}`);
                        if (!(res && res.success && Array.isArray(res.results) && res.results.length > 0)) return;
                        const r = res.results[0];
                        const cell = row.querySelector('.status-cell');
                        if (!cell) return;
                        applyStatusClass(cell, r.aggregate_status);
                        let displayText = '';
                        if (Array.isArray(r.items) && r.items.length > 0) {
                            const rawStatuses = r.items.map(it => {
                                const rawObj = (it && typeof it.raw === 'object' && it.raw) ? it.raw : {};
                                return rawObj && rawObj.status != null ? String(rawObj.status) : (it && it.status ? String(it.status) : 'unknown');
                            });
                            if (rawStatuses.length === 1) {
                                displayText = rawStatuses[0];
                            } else {
                                const counts = {};
                                rawStatuses.forEach(s => { counts[s] = (counts[s] || 0) + 1; });
                                displayText = Object.entries(counts).map(([k,v]) => v > 1 ? `${k} x${v}` : k).join(', ');
                            }
                        } else {
                            displayText = (r.aggregate_status || 'unknown');
                        }
                        const cap = (displayText || 'unknown');
                        cell.textContent = formatHistoryStatusText(cap.charAt(0).toUpperCase() + cap.slice(1));
                        if (Array.isArray(r.items)) {
                            r.items.forEach(it => {
                                const provider = it && it.provider ? String(it.provider) : '';
                                const orderId = it && it.order_id != null ? String(it.order_id) : '';
                                if (!orderId) return;
                                const sel = `.order-item[data-order-id="${CSS.escape(orderId)}"]${provider ? `[data-provider="${CSS.escape(provider)}"]` : ''}`;
                                const orderItem = row.querySelector(sel);
                                if (!orderItem) return;
                                const raw = (it && typeof it.raw === 'object' && it.raw) ? it.raw : {};
                                const chargeEl = orderItem.querySelector('.order-status-charge');
                                const startEl = orderItem.querySelector('.order-status-start');
                                const statusEl = orderItem.querySelector('.order-status-status');
                                const remainsEl = orderItem.querySelector('.order-status-remains');
                                const currencyEl = orderItem.querySelector('.order-status-currency');
                                if (chargeEl) chargeEl.textContent = (raw.charge != null ? String(raw.charge) : '-');
                                if (startEl) startEl.textContent = (raw.start_count != null ? String(raw.start_count) : '-');
                                if (statusEl) statusEl.textContent = (it && it.status ? String(it.status) : (raw.status != null ? String(raw.status) : '-'));
                                if (remainsEl) remainsEl.textContent = (raw.remains != null ? String(raw.remains) : '-');
                                if (currencyEl) currencyEl.textContent = (raw.currency != null ? String(raw.currency) : '-');
                            });
                        }
                    } catch (_) { /* ignore */ }
                }
                async function progressiveLoadHistoryStatuses() {
                    const rows = getVisibleHistoryRows();
                    for (const row of rows) {
                        await fetchAndRenderForRow(row);
                    }
                }
                const pageParam = getQueryParam('page');
                const isFirstPage = !pageParam || String(pageParam) === '1';
                if (isFirstPage) {
                    // Progressive, top-to-bottom load for first page only
                    progressiveLoadHistoryStatuses();
                    // Optional: refresh on visibility/focus to update latest
                    document.addEventListener('visibilitychange', () => {
                        if (document.visibilityState === 'visible') {
                            progressiveLoadHistoryStatuses();
                        }
                    });
                    window.addEventListener('focus', () => {
                        progressiveLoadHistoryStatuses();
                    });
                } else {
                    // Do not load live API statuses on non-first pages
                    try { if (historyPollIntervalId) clearInterval(historyPollIntervalId); } catch(_) {}
                }
            } else {
                // Assuming it might be the index/single promo page if none of the others match specifically
                console.log("Running on Index/Single Promo Page specific init (fallback)...");
                await initializeSinglePromoPage(); // Initialize elements for single promo section
                // No specific dropdowns to populate here initially, handled globally now
            }
            
            // --- Initialize Balance Display (on all pages that have it) --- REMOVED DUPLICATE
            // This is now handled in the main initApp function
            
            console.log(`Initialization and listeners setup finished.`);
            // Update global top status based on section readiness
            updateGlobalReadyStatus();

        } catch (initError) {
             console.error("Critical error during app initialization:", initError);
             // Update status to Error on failure
             showStatus("Initialization Error", "danger", statusAreaId, statusMessageId); // Keep error visible
         }
    })();

    // After initializations, rehydrate any active jobs so they persist across refresh
    (async () => {
        try {
            await restoreActiveJobs();
        } catch (_) { /* ignore */ }
        // Also periodically re-run to restore rows if the server/local state updates or if a row was removed
        try {
            setInterval(() => { restoreActiveJobs().catch(()=>{}); }, 10000);
        } catch (_) { /* ignore */ }
    })();

    // --- Keep-Alive Ping: Prevent server spin-down ---
    (function startKeepAlivePing() {
        async function ping() {
            try {
                await fetch('/api/ping', { method: 'GET' });
                console.log('[Keep-Alive] Ping sent');
            } catch (e) {
                console.warn('[Keep-Alive] Ping failed:', e.message);
            }
        }
        // Ping immediately on load
        ping();
        // Then ping every 10 seconds
        setInterval(ping, 10000);
    })();

    // --- Promo Page Specific Initialization ---
    async function initializePromoPage(profiles) { // <-- Accept profiles data
        console.log("Running initializePromoPage with profiles:", profiles);

        // Ensure data caches are populated (should be by initializeAppCommon)
        if (!profiles || Object.keys(profiles).length === 0) {
            console.warn("Profile data passed to initializePromoPage is empty.");
            showStatus("Failed to load profile data. Cannot populate dropdown.", 'warning', 'promo-status-area', 'promo-status-message');
        }

        // 1) Populate profile dropdown
        const profileSelectPromo = document.getElementById('profile-select-promo');
        if (profileSelectPromo) {
            populateProfileDropdown(profileSelectPromo, profiles);
            // Add change listener to update cost display
            profileSelectPromo.addEventListener('change', () => updateAutoPromoCostDisplay(profiles));
            // Initial cost display
            updateAutoPromoCostDisplay(profiles);
        }

        // 2) Populate platform dropdown from CSV with fallback (ensures Spotify shows)
        const promoPlatformSelect = document.getElementById('promo-platform-select');
        if (promoPlatformSelect) {
            try {
                let platforms = await loadPlatformsFromServer();
                if (!platforms || platforms.length === 0) {
                    platforms = ['Instagram','TikTok','YouTube','X (Twitter)','Spotify'];
                }
                populateSelectOptions(promoPlatformSelect, platforms);
                if (platforms && platforms.length > 0) {
                    promoPlatformSelect.selectedIndex = 1; // 0 is placeholder
                }
            } catch (e) {
                console.error('Failed to populate Auto Promo platform list:', e);
                populateSelectOptions(promoPlatformSelect, ['Instagram','TikTok','YouTube','X (Twitter)','Spotify']);
            }
        }

        // 3) Attach Listeners for Profile Promo section
        const runProfileBtn = document.getElementById('start-profile-promo-btn');
        const stopProfileBtn = document.getElementById('stop-profile-btn');
        const promoLinkInput = document.getElementById('profile-link-input');

        if (runProfileBtn && profileSelectPromo && promoLinkInput) {
            runProfileBtn.addEventListener('click', () => {
                const profileName = profileSelectPromo.value;
                const link = promoLinkInput.value.trim();
                if (!profileName) {
                    showStatus('Please select a promotion profile.', 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link) {
                    showStatus('Please enter the link for the profile promotion.', 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link.toLowerCase().startsWith('https://')) {
                    showStatus('Link must start with https://', 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                // Determine platform: use dropdown if provided, otherwise derive from profile settings
                let platform = '';
                if (promoPlatformSelect && promoPlatformSelect.value) {
                    platform = promoPlatformSelect.value;
                } else {
                    try {
                        const profileObj = (profiles && profiles[profileName]) || (profilesDataCache && profilesDataCache[profileName]);
                        const engagements = profileObj && Array.isArray(profileObj.engagements) ? profileObj.engagements : [];
                        const platforms = [...new Set(engagements.map(e => e && e.platform).filter(Boolean))];
                        if (platforms.length > 0) {
                            platform = platforms[0];
                        }
                    } catch (_) { /* ignore and leave platform empty */ }
                }
                // Start promo; backend treats missing/empty platform as 'no filter' and uses profile settings
                startProfilePromotion(profileName, link, platform);
            });
        } else {
            console.error('Could not find one or more required elements for profile promo form listeners.');
            showStatus('UI Error: Profile promo form incomplete.', 'danger', 'promo-status-area', 'promo-status-message');
        }

        if (stopProfileBtn) {
            // Hide global stop button in favor of per-job stop buttons
            try { stopProfileBtn.style.display = 'none'; } catch(_) {}
        }

        promoReady = !!(runProfileBtn && profileSelectPromo && promoLinkInput);
        updateGlobalReadyStatus();
    }

    // --- Auto Promo Cost Display ---
    function updateAutoPromoCostDisplay(profiles) {
        const profileSelect = document.getElementById('profile-select-promo');
        const costDisplay = document.getElementById('auto-cost-display');
        
        if (!profileSelect || !costDisplay) return;
        
        const selectedProfileName = profileSelect.value;
        if (!selectedProfileName || !profiles || !profiles[selectedProfileName]) {
            costDisplay.textContent = '';
            return;
        }
        
        const profile = profiles[selectedProfileName];
        const engagements = profile.engagements || [];
        
        let totalCost = 0;
        let costBreakdown = [];
        
        for (const eng of engagements) {
            const rate = parseFloat(eng.rate_per_1k) || 0;
            const loops = parseInt(eng.loops) || 1;
            
            // Calculate quantity per loop
            let qtyPerLoop = 0;
            let minTotalQty, maxTotalQty, minCost, maxCost;
            
            if (eng.use_random_quantity) {
                const minQty = parseInt(eng.min_quantity) || 0;
                const maxQty = parseInt(eng.max_quantity) || 0;
                qtyPerLoop = (minQty + maxQty) / 2; // Average for estimate
                
                // Calculate ranges
                minTotalQty = minQty * loops;
                maxTotalQty = maxQty * loops;
                minCost = (rate * minTotalQty) / 1000;
                maxCost = (rate * maxTotalQty) / 1000;
            } else {
                qtyPerLoop = parseInt(eng.fixed_quantity) || 0;
                minTotalQty = maxTotalQty = qtyPerLoop * loops;
                minCost = maxCost = (rate * minTotalQty) / 1000;
            }
            
            const totalQty = qtyPerLoop * loops;
            const engCost = (rate * totalQty) / 1000;
            totalCost += engCost;
            
            const engType = eng.type || 'Unknown';
            if (eng.use_random_quantity) {
                costBreakdown.push(`${engType} - Quantity: ${minTotalQty.toLocaleString()}-${maxTotalQty.toLocaleString()} -- Cost: ${formatCurrency(minCost)}-${formatCurrency(maxCost)}`);
            } else {
                costBreakdown.push(`${engType} - Quantity: ${minTotalQty.toLocaleString()} -- Cost: ${formatCurrency(minCost)}`);
            }
        }
        
        if (totalCost > 0) {
            costDisplay.innerHTML = `<strong>Estimated Total Cost:</strong> ${formatCurrency(totalCost)}<br>${costBreakdown.join('<br>')}`;
        } else {
            costDisplay.textContent = '';
        }
        
        // Also update provider cost breakdown if available
        if (typeof window.updateProviderCostBreakdown === 'function') {
            window.updateProviderCostBreakdown();
        }
    }

    // --- Single Promo Page Specific Initialization (ensure CSV-backed platforms incl. Spotify) ---
    async function initializeSinglePromoPage() {
        console.log('Running initializeSinglePromoPage (CSV-backed) ...');
        if (!minimumQuantities || Object.keys(minimumQuantities).length === 0) {
            console.warn('Minimum quantities not ready for Single Promo init.');
            showStatus('Failed to load configuration. Engagement options may be incorrect.', 'warning', 'single-promo-status-area', 'single-promo-status-message');
        }

        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const singlePromoBtn = document.getElementById('start-single-promo-btn');
        const qtyInput = document.getElementById('quantity-input');
        if (!platformSelect || !engagementSelect || !singlePromoBtn) {
            console.error('Could not find Single Promo elements.');
            showStatus('UI Error: Single promo controls missing.', 'danger', 'single-promo-status-area', 'single-promo-status-message');
            return;
        }

        // Create custom engagement dropdown to replace native select UI
        const singleCustom = (typeof ensureCustomEngagementDropdown === 'function')
            ? ensureCustomEngagementDropdown(engagementSelect, platformSelect, 'single')
            : null;

        try {
            let platforms = await loadPlatformsFromServer();
            if (!platforms || platforms.length === 0) {
                platforms = ['Instagram','TikTok','YouTube','X (Twitter)','Spotify'];
            }
            populateSelectOptions(platformSelect, platforms);
            platformSelect.addEventListener('change', async () => {
                const p = platformSelect.value;
                if (!p) {
                    populateSelectOptions(engagementSelect, []);
                    if (singleCustom && singleCustom.setItems) singleCustom.setItems([]);
                    const lbl = document.getElementById('single-eng-selected-sub');
                    if (lbl) lbl.textContent = '';
                    const btnEl = document.getElementById('single-eng-btn');
                    if (btnEl) btnEl.textContent = '-- Select Engagement --';
                    try { delete engagementSelect.dataset.selectedService; } catch(_) {}
                    clearSinglePromoQuantityBounds();
                    clearSingleCostDisplay();
                    return;
                }
                let engs = [];
                try { engs = await loadEngagementsFromServer(p); } catch (_) {}
                populateSelectOptions(engagementSelect, engs);
                if (singleCustom && singleCustom.setItems) singleCustom.setItems(engs);
                try { delete engagementSelect.dataset.selectedService; } catch(_) {}
                const lbl = document.getElementById('single-eng-selected-sub');
                if (lbl) lbl.textContent = '';
                const btnEl = document.getElementById('single-eng-btn');
                if (btnEl) btnEl.textContent = '-- Select Engagement --';
                clearSinglePromoQuantityBounds();
                clearSingleCostDisplay();
            });

            if (platforms && platforms.length > 0) {
                platformSelect.selectedIndex = 1;
                let engs = [];
                try { engs = await loadEngagementsFromServer(platformSelect.value); } catch(_) {}
                populateSelectOptions(engagementSelect, engs);
                if (singleCustom && singleCustom.setItems) singleCustom.setItems(engs);
                try { delete engagementSelect.dataset.selectedService; } catch(_) {}
                const lbl2 = document.getElementById('single-eng-selected-sub');
                if (lbl2) lbl2.textContent = '';
                const btn2 = document.getElementById('single-eng-btn');
                if (btn2) btn2.textContent = '-- Select Engagement --';
                clearSinglePromoQuantityBounds();
                clearSingleCostDisplay();
            }
        } catch (e) {
            console.error('Failed to populate Single Promo:', e);
            populateSelectOptions(platformSelect, ['Instagram','TikTok','YouTube','X (Twitter)','Spotify']);
        }

        singlePromoBtn.addEventListener('click', startSinglePromotion);
        // Recalculate Single Promo cost on any quantity change
        if (qtyInput) {
            const recalc = () => updateSingleCostDisplay();
            qtyInput.addEventListener('input', recalc);
            qtyInput.addEventListener('change', recalc);
            qtyInput.addEventListener('keyup', recalc);
        }
        singleReady = true;
        updateGlobalReadyStatus();
    }


    // --- Utility Functions --- 

    // --- OLD STOP FUNCTION (kept for reference, replaced by API call) ---
    /*
    function stopProfilePromotion() {
        if (!currentProfileJobId) {
            showStatus("No profile promotion is currently running.", 'info', 'promo-status-area', 'promo-status-message');
            return;
        }
        console.log(`Requesting stop for job: ${currentProfileJobId}`);
        showStatus(`Requesting stop for job ${currentProfileJobId}...`, 'warning', 'promo-status-area', 'promo-status-message');
        // Here, you'd ideally send a request to the backend to stop the job
        // Since we don't have a direct kill mechanism via the scheduler easily from frontend,
        // this might just update UI state and rely on the backend job checking a flag.
        // For now, just stop polling and update UI.
        stopStatusPolling();
        enableActionButtons(); // Re-enable buttons after requesting stop
        showStatus(`Stop requested for job ${currentProfileJobId}. Backend process might take time to halt.`, 'info', 'promo-status-area', 'promo-status-message');
        currentProfileJobId = null; // Assume stop is requested
    }
    */

    async function stopProfilePromotion() {
        console.log("[Debug] stopProfilePromotion called. currentProfileJobId:", currentProfileJobId); // Added for debugging
        if (!currentProfileJobId) {
            showStatus("No profile promotion job ID found to stop.", 'warning', 'promo-status-area', 'promo-status-message', 3000);
            return;
        }
        console.log(`Requesting stop via API for job: ${currentProfileJobId}`);
        showStatus(`Requesting stop for job ${currentProfileJobId}...`, 'warning', 'promo-status-area', 'promo-status-message');
        const stopButton = document.getElementById('stop-profile-btn');
        if(stopButton) stopButton.disabled = true; // Disable stop button immediately

        try {
            const data = await apiCall('/api/stop_promo', 'POST', { job_id: currentProfileJobId });
            if (data && data.status === 'success') {
                showStatus(data.message || `Stop requested for job ${currentProfileJobId}.`, 'info', 'promo-status-area', 'promo-status-message');
                // Optionally, also stop monitoring for the associated target
                // This requires knowing the target ID or username/profile
                // If you have the profile name or username, call stopMonitoringForTarget
                // Example: await stopMonitoringForTarget(targetId); // Needs mapping
            } else {
                showStatus(data.message || `Failed to register stop request for job ${currentProfileJobId}.`, 'warning', 'promo-status-area', 'promo-status-message', 5000);
                if(stopButton) stopButton.disabled = false;
            }
        } catch (error) {
            showStatus(`Error sending stop request for ${currentProfileJobId}. Check console.`, 'danger', 'promo-status-area', 'promo-status-message');
            if(stopButton) stopButton.disabled = false;
        }
        // Note: currentProfileJobId is NOT cleared here. The polling function handles final state.
    }

    function handleFinalJobStatus(jobId) {
        console.log(`Handling final status for Job ID: ${jobId}`);
        stopStatusPolling(); // Stop polling since job is finished
        enableActionButtons(); // Re-enable Run/Single buttons
        
        // Ensure the Stop button is disabled as the job is no longer active
        const stopBtn = document.getElementById('stop-profile-btn');
        if (stopBtn) {
            stopBtn.disabled = true;
        }
        
        // Clear job ID *after* handling final status
        if (jobId === currentProfileJobId) {
            currentProfileJobId = null; 
            console.log("Cleared currentProfileJobId.");
        } else {
            console.warn(`Final status handled for ${jobId}, but it wasn't the currentProfileJobId (${currentProfileJobId})`);
        }

        // Optional: Refresh history page if it's implemented
        // if (typeof refreshHistory === 'function') { refreshHistory(); }
    }

    // Refactored to use minimumQuantities cache
    function populateProfileDropdown(dropdownElement, profiles) { // <-- Accept profiles data
        if (!dropdownElement) {
            console.error("populateProfileDropdown called with null dropdownElement.");
            return;
        }
        const dropdownId = dropdownElement.id || 'unknown-dropdown'; // Get ID for logging
        console.log(`Populating profile dropdown: #${dropdownId}`);

        // Clear existing options (except placeholder if desired)
        dropdownElement.innerHTML = ''; // Clear all options

        // Add a default/placeholder option
        const placeholderOption = document.createElement('option');
        placeholderOption.value = "";
        placeholderOption.textContent = "-- Select Profile --";
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        dropdownElement.appendChild(placeholderOption);

        // Use passed-in profiles data instead of global cache
        // *** ADD DETAILED LOG HERE ***
        console.log(`Profiles data received by populateProfileDropdown for #${dropdownId}:`, JSON.stringify(profiles));
        if (!profiles || Object.keys(profiles).length === 0) {
            console.warn(`No profiles found in passed data for dropdown #${dropdownId}.`);
            // Optionally add an option indicating no profiles are available
             const noProfilesOption = document.createElement('option');
             noProfilesOption.value = "";
             noProfilesOption.textContent = "No profiles available";
             noProfilesOption.disabled = true;
             dropdownElement.appendChild(noProfilesOption);
            return; // Exit if no profiles
        }

        // Sort profile names alphabetically for consistency
        console.log("Profile names found in passed data:", Object.keys(profiles)); // Log keys before sorting
        const sortedProfileNames = Object.keys(profiles).sort((a, b) => a.localeCompare(b));
        console.log("Sorted profile names:", sortedProfileNames);

        // Populate with profiles from passed data
        sortedProfileNames.forEach(profileName => {
            console.log(`Attempting to add option for profile: ${profileName}`); // Log each attempt
            const option = document.createElement('option');
            option.value = profileName;
            option.textContent = profileName;
            dropdownElement.appendChild(option);
            console.log(`Successfully appended option for: ${profileName}`); // Log success
        });
        console.log(`Finished populating dropdown #${dropdownId} with ${sortedProfileNames.length} profiles.`);
        
        // Return true if profiles were actually added (more than just placeholder)
        return sortedProfileNames.length > 0; 
    }


    // --- Utility Functions ---

    // --- Function to update the minimum quantity label/placeholder ---
    function updateMinQuantityLabel() {
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const quantityInput = document.getElementById('quantity-input'); // Assumes this ID for the quantity input
        const quantityLabel = document.querySelector('label[for="quantity-input"]'); // Find label associated with input

        if (!platformSelect || !engagementSelect || !quantityInput) {
            console.warn("Missing elements for updating min quantity label.");
            return;
        }

        const selectedPlatform = platformSelect.value;
        const selectedEngagement = engagementSelect.value;
        let minQty = 1; // Default to 1 if not found or not applicable, ensuring it's at least 1.

        if (selectedPlatform && selectedEngagement && minimumQuantities) {
            const key = "('" + selectedPlatform + "', '" + selectedEngagement + "')";
            minQty = minimumQuantities[key] || 1; // Use 1 as a fallback if key not found
        }

        const placeholderText = minQty > 0 ? `Minimum: ${minQty}` : "Quantity";
        quantityInput.placeholder = placeholderText;
        quantityInput.min = minQty; // <<< SET THE MIN ATTRIBUTE HERE

        // Optionally update the label text itself
        if (quantityLabel) {
            // quantityLabel.textContent = minQty > 0 ? `Quantity (Min: ${minQty}):` : "Quantity:"; // Example
        }
        console.log(`Updated quantity input for ${selectedPlatform}/${selectedEngagement}: Placeholder='${placeholderText}', Min Attribute='${minQty}'`);
    }

    // Refactored to use minimumQuantities cache
    function updateEngagementOptions() {
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');

        if (!platformSelect || !engagementSelect) {
            console.error("Cannot update engagement options: Platform or Engagement select not found.");
            return;
        }

        const selectedPlatform = platformSelect.value;
        engagementSelect.innerHTML = ''; // Clear existing options

        const placeholderOption = document.createElement('option');
        placeholderOption.value = "";
        placeholderOption.textContent = "-- Select Engagement --";
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        engagementSelect.appendChild(placeholderOption);

        if (!selectedPlatform) {
             console.log("No platform selected, engagement dropdown cleared.");
             engagementSelect.disabled = true;
             updateMinQuantityLabel(); // Update label based on cleared engagement
             return; // Exit if no platform selected
        }
        
        engagementSelect.disabled = false; // Enable dropdown if platform is selected

        // Extract valid engagement types for the selected platform from the minimumQuantities cache
        const availableEngagements = new Set();
        if (minimumQuantities && typeof minimumQuantities === 'object') {
            Object.keys(minimumQuantities).forEach(key => {
                // Log the key being processed and its length for debugging
                console.log(`Processing key: '${key}', Length: ${key.length}`);
                
                // --- NEW Parsing Logic: Regular Expression --- 
                let platform = null;
                let engagement = null;
                // Regex to match "('Platform Name', 'Engagement Type')"
                const match = key.match(/^\('([^']+)',\s*'([^']+)'\)$/);
                if (match && match.length === 3) {
                    platform = match[1];
                    engagement = match[2];
                } 
                // --- End NEW Parsing Logic ---

                if (platform && engagement) { 
                    if (platform === selectedPlatform) {
                        availableEngagements.add(engagement);
                    }
                } else {
                    console.warn(`Could not parse minimum quantity key: ${key} (Regex failed)`);
                }
            });
        } else {
            console.warn("Minimum quantities cache is not ready or invalid.");
            // Potentially fall back to hardcoded defaults? Or show error?
        }

        if (availableEngagements.size === 0) {
             console.warn(`No engagement types found for platform '${selectedPlatform}' in minimumQuantities cache.`);
             const noEngagementsOption = document.createElement('option');
             noEngagementsOption.value = "";
             noEngagementsOption.textContent = "No options for platform";
             noEngagementsOption.disabled = true;
             engagementSelect.appendChild(noEngagementsOption);
             engagementSelect.disabled = true;
        } else {
            // Sort and add options
            const sortedEngagements = Array.from(availableEngagements).sort();
            sortedEngagements.forEach(engType => {
                const option = document.createElement('option');
                option.value = engType;
                option.textContent = engType;
                engagementSelect.appendChild(option);
            });
             console.log(`Populated engagement dropdown for ${selectedPlatform} with:`, sortedEngagements);
        }
        
        // Trigger label update after repopulating
        updateMinQuantityLabel(); 
    }

    // --- Monitoring Page Specific Initialization ---
    async function initializeMonitorPage(profiles) { // <-- Accept profiles data
        console.log("Running initializeMonitorPage...");

        // Ensure profile data is available
        if (!profiles || Object.keys(profiles).length === 0) {
            console.warn("Profile data not available for Monitor Page init.");
            // Optionally, show an error or try reloading profiles? 
        }

        // 1. Load settings and targets concurrently
        await Promise.allSettled([
            loadMonitoringSettings(),
            loadMonitoringTargets()
        ]);
        console.log("Initial settings and targets loaded for Monitor Page.");

        // 2. Populate the 'Add Target' profile dropdown
        const monitorAddProfileSelect = document.getElementById('monitor-add-profile-select');
        if (monitorAddProfileSelect) {
            populateProfileDropdown(monitorAddProfileSelect, profiles); // <-- Pass profiles data
        } else {
            console.error("Monitor Add Profile Select dropdown not found.");
        }

        // 3. Attach main page listeners
        const saveSettingsBtn = document.getElementById('save-monitoring-settings-btn');
        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', saveMonitoringSettings);
        } else {
            console.error("Save monitoring settings button not found.");
        }

        const addTargetBtn = document.getElementById('add-monitoring-target-btn');
        if (addTargetBtn) {
            addTargetBtn.addEventListener('click', addMonitoringTarget);
        } else {
            console.error("Add monitoring target button not found.");
        }

        const testScrapeBtn = document.getElementById('test-scrape-btn');
        if (testScrapeBtn) {
            testScrapeBtn.addEventListener('click', testGetLatestPost);
        } else {
            console.error("Test scrape button not found.");
        }

        console.log("Monitor Page Listeners Attached.");
    }

    // --- Monitoring Page Specific Functions ---

    async function loadMonitoringSettings() {
        console.log("Executing loadMonitoringSettings...");
        const pollingIntervalInput = document.getElementById('polling-interval-input');
        const settingsStatus = document.getElementById('settings-status');
        if(!pollingIntervalInput || !settingsStatus) {
            console.warn("loadMonitoringSettings: Missing required elements.");
            return; 
        }

        try {
            const data = await apiCall('/api/monitoring/settings');
            if (data.success && data.settings) {
                // --- Defer UI update slightly --- 
                setTimeout(() => {
                    pollingIntervalInput.value = data.settings.polling_interval_seconds || '';
                    console.log("Polling interval input value set to:", pollingIntervalInput.value);
                }, 0);
                // --------------------------------
                console.log("loadMonitoringSettings completed successfully.");
            } else {
                showTemporaryStatus(settingsStatus, data.error || "Failed to load settings.", "danger");
            }
        } catch (error) {
            console.error("Error caught in loadMonitoringSettings:", error);
            // API call helper shows main status error
            showTemporaryStatus(settingsStatus, "Error loading settings.", "danger");
        }
    }

    function saveMonitoringSettings() {
        console.log("saveMonitoringSettings button clicked");
        const pollingIntervalInput = document.getElementById('polling-interval-input');
        const settingsStatus = document.getElementById('settings-status');
        if(!pollingIntervalInput || !settingsStatus) { // Check new ID
            console.error("saveMonitoringSettings: Missing one or more required UI elements.");
            return;
        }

        const interval = pollingIntervalInput.value.trim();
        if (!interval || isNaN(parseInt(interval))) {
            showTemporaryStatus(settingsStatus, "Polling interval must be a number.", "warning");
            return;
        }
        const intervalSeconds = parseInt(interval);
        if (intervalSeconds < 30) {
             showTemporaryStatus(settingsStatus, "Polling interval must be at least 30 seconds.", "warning");
             return;
        }

        showTemporaryStatus(settingsStatus, "Saving...", "info", 0); // Show saving indicator
        apiCall('/api/monitoring/settings', 'PUT', { polling_interval_seconds: intervalSeconds })
            .then(data => {
                if (data.success) {
                    showTemporaryStatus(settingsStatus, "Interval saved successfully!", "success");
            } else {
                    showTemporaryStatus(settingsStatus, data.error || "Failed to save settings.", "danger");
                }
            })
            .catch(error => showTemporaryStatus(settingsStatus, `Error saving settings.`, "danger"));
            // API call helper shows main status error if needed
    }

    async function loadMonitoringTargets() {
        console.log("Executing loadMonitoringTargets...");
        const monitorListStatus = document.getElementById('monitor-list-status');
        if(!monitorListStatus) {
            console.warn("loadMonitoringTargets: Missing monitorListStatus element.");
            // Continue, but won't show status messages for this area
        } 
        // if(monitorListStatus) showTemporaryStatus(monitorListStatus, "Loading targets...", "info", 0); // <<< REMOVED THIS LINE
        try {
            const data = await apiCall('/api/monitoring/targets');
            if (data.success && data.targets) {
                 renderMonitoringTargets(data.targets);
                 if (data.targets.length === 0) {
                     // showTemporaryStatus(monitorListStatus, "No targets being monitored.", "info"); // <<< REMOVED THIS LINE
                 } else {
                     clearTemporaryStatus(monitorListStatus); // Clear loading message
                 }
                console.log("loadMonitoringTargets completed successfully.");
            } else {
                 showTemporaryStatus(monitorListStatus, data.error || "Failed to load targets.", "danger");
                 renderMonitoringTargets([]); // Render empty state
            }
        } catch (error) {
            console.error("Error caught in loadMonitoringTargets:", error);
            // API call helper shows main status error
            showTemporaryStatus(monitorListStatus, `Error loading targets.`, "danger");
            renderMonitoringTargets([]); // Render empty state
        }
    }

    function renderMonitoringTargets(targets) {
        const monitoringTargetsList = document.getElementById('monitoring-targets-list'); // tbody element
        if(!monitoringTargetsList) {
            console.error("renderMonitoringTargets: Cannot find monitoring-targets-list element.");
            return;
        }

         monitoringTargetsList.innerHTML = ''; // Clear existing rows
 
         if (!targets || targets.length === 0) {
             monitoringTargetsList.innerHTML = '<tr><td colspan="6" class="text-center">No targets configured. Use the form above to add one.</td></tr>';
             return;
         }
 
         // Sort targets? Maybe alphabetically by username?
         targets.sort((a, b) => (a.target_username || '').localeCompare(b.target_username || ''));
 
         targets.forEach(target => {
             const row = document.createElement('tr');
             row.setAttribute('data-target-id', target.id); // Store ID for actions
 
             const statusText = target.is_running ? 'Running' : 'Stopped';
             const statusClass = target.is_running ? 'text-success' : 'text-danger';
             const toggleButtonText = target.is_running ? 'Stop' : 'Start';
             const toggleButtonClass = target.is_running ? 'btn-warning' : 'btn-success';
 
             // Format dates nicely or show N/A
             const lastChecked = target.last_checked_timestamp ? formatIsoDateTime(target.last_checked_timestamp) : 'N/A';
             const lastPushed = target.last_pushed_post_url ? `<a href="${target.last_pushed_post_url}" target="_blank" title="${target.last_pushed_post_url}">${target.last_pushed_post_url.substring(0, 35)}...</a>` : 'N/A';
 
 
             row.innerHTML = `
                 <td>${target.target_username || 'N/A'}</td>
                 <td>${target.promotion_profile_name || 'N/A'}</td>
                 <td class="${statusClass}">${statusText}</td>
                 <td>${lastChecked}</td>
                 <td class="text-break">${lastPushed}</td>
                 <td>
                    <button class="btn btn-sm ${toggleButtonClass} toggle-monitor-btn" data-target-id="${target.id}" data-target-name="${target.target_username}" data-current-state="${target.is_running}">
                        ${toggleButtonText}
                    </button>
                    <button class="btn btn-sm btn-secondary edit-monitor-btn ms-1" data-target-id="${target.id}" data-target-name="${target.target_username}" data-profile-name="${target.promotion_profile_name||''}">
                        Edit
                    </button>
                    <button class="btn btn-sm btn-danger remove-monitor-btn ms-1" data-target-id="${target.id}" data-target-name="${target.target_username}">
                        Remove
                    </button>
                </td>
             `;
             monitoringTargetsList.appendChild(row);
         });
 
          // Add event listeners after rows are created
          addMonitoringListActionListeners();
    }

    function addMonitoringListActionListeners() {
        document.querySelectorAll('.toggle-monitor-btn').forEach(button => {
            // Remove existing listener before adding new one to prevent duplicates
            button.replaceWith(button.cloneNode(true)); // Clone to remove listeners
        });
         document.querySelectorAll('.remove-monitor-btn').forEach(button => {
            button.replaceWith(button.cloneNode(true)); // Clone to remove listeners
        });
         document.querySelectorAll('.edit-monitor-btn').forEach(button => {
            button.replaceWith(button.cloneNode(true));
         });

        // Add listeners to the new buttons
        document.querySelectorAll('.toggle-monitor-btn').forEach(button => {
            button.addEventListener('click', handleToggleMonitoring);
        });
        document.querySelectorAll('.remove-monitor-btn').forEach(button => {
            button.addEventListener('click', handleRemoveMonitoring);
        });
        document.querySelectorAll('.edit-monitor-btn').forEach(button => {
            button.addEventListener('click', handleEditMonitoring);
        });
    }

    // Helper: Find running auto promo job for a username/profile (stub, needs backend support or job tracking)
    async function stopAutoPromoForTarget(targetUsername, profileName) {
        // This function assumes you have a way to map username/profile to a running job ID
        // For now, we use currentProfileJobId if available and matches
        if (currentProfileJobId) {
            // Optionally, check if the job matches the profile/username
            await stopProfilePromotion();
        }
    }

    // Helper: Stop monitoring for a target by ID
    async function stopMonitoringForTarget(targetId) {
        // PUT to /api/monitoring/targets/<target_id> with is_running: false
        await apiCall(`/api/monitoring/targets/${targetId}`, 'PUT', { is_running: false });
    }

    // Patch: When stopping a monitored target, also stop auto promo
    function handleToggleMonitoring(event) {
        console.log("handleToggleMonitoring called");
        const monitorListStatus = document.getElementById('monitor-list-status');
        if(!monitorListStatus) return;

        const button = event.currentTarget;
        const targetId = button.getAttribute('data-target-id');
        const targetName = button.getAttribute('data-target-name');
        const currentState = button.getAttribute('data-current-state') === 'true';
        const newState = !currentState;
        const action = newState ? 'Starting' : 'Stopping';

        showTemporaryStatus(monitorListStatus, `${action} monitoring for ${targetName}...`, "info", 0);
        button.disabled = true; // Disable button during API call

        apiCall(`/api/monitoring/targets/${targetId}`, 'PUT', { is_running: newState })
            .then(async data => {
                if (data.success && data.targets) {
                    renderMonitoringTargets(data.targets); // Re-render the whole list
                    showTemporaryStatus(monitorListStatus, `Successfully ${newState ? 'started' : 'stopped'} monitoring for ${targetName}.`, "success");
                    // If stopping, also stop auto promo for this target
                    if (!newState) {
                        // Find the profile name for this target
                        const target = data.updated_target || (data.targets.find(t => t.id === targetId));
                        if (target) {
                            await stopAutoPromoForTarget(target.target_username, target.promotion_profile_name);
                        }
                    }
                } else {
                     showTemporaryStatus(monitorListStatus, data.error || `Failed to ${action.toLowerCase()} monitoring.`, "danger");
                     button.disabled = false;
                }
            })
            .catch(error => {
                showTemporaryStatus(monitorListStatus, `Error ${action.toLowerCase()} monitoring.`, "danger");
                button.disabled = false;
            });
    }

    
    function handleRemoveMonitoring(event) {
        console.log("handleRemoveMonitoring called");
         const monitorListStatus = document.getElementById('monitor-list-status');
         if(!monitorListStatus) return;

        const button = event.currentTarget;
        const targetId = button.getAttribute('data-target-id');
        const targetName = button.getAttribute('data-target-name');

        if (!confirm(`Are you sure you want to remove monitoring for "${targetName}"?`)) {
            return;
        }

        showTemporaryStatus(monitorListStatus, `Removing ${targetName}...`, "info", 0);
         button.disabled = true; // Disable button during API call
         const row = button.closest('tr');
         if (row) {
             const toggleBtn = row.querySelector('.toggle-monitor-btn');
              if (toggleBtn) toggleBtn.disabled = true;
         }


        apiCall(`/api/monitoring/targets/${targetId}`, 'DELETE')
            .then(data => {
                if (data.success && data.targets) {
                    renderMonitoringTargets(data.targets); // Re-render the whole list
                    showTemporaryStatus(monitorListStatus, `Successfully removed ${targetName}.`, "success");
                } else {
                    showTemporaryStatus(monitorListStatus, data.error || `Failed to remove target.`, "danger");
                    // Re-enable buttons on failure
                    button.disabled = false;
                    if (row) {
                        const toggleBtn = row.querySelector('.toggle-monitor-btn');
                         if (toggleBtn) toggleBtn.disabled = false;
                    }
                }
            })
            .catch(error => {
                 // API call helper shows main status error
                 showTemporaryStatus(monitorListStatus, `Error removing target.`, "danger");
                 // Re-enable buttons on failure
                 button.disabled = false;
                 if (row) {
                     const toggleBtn = row.querySelector('.toggle-monitor-btn');
                     if (toggleBtn) toggleBtn.disabled = false;
                 }
            });
    }


    function addMonitoringTarget() {
        console.log("addMonitoringTarget button clicked");
        // Get elements needed for this function
        const monitorUsernameInput = document.getElementById('monitor-username-input');
        const monitorAddProfileSelect = document.getElementById('monitor-add-profile-select'); // Use new unique ID
        const addTargetStatus = document.getElementById('add-target-status');
        const addMonitoringTargetBtn = document.getElementById('add-monitoring-target-btn');
        // Check elements exist
        if(!monitorUsernameInput || !monitorAddProfileSelect || !addTargetStatus || !addMonitoringTargetBtn) { // Check new ID
            console.error("addMonitoringTarget: Missing one or more required UI elements.");
            showStatus("UI Error: Cannot find monitoring add form elements.", 'danger', 'add-target-status'); // Show error in relevant status area
            return;
        }

        let username = monitorUsernameInput.value.trim();
        const profileName = monitorAddProfileSelect.value; // Use new unique ID

        if (!username) {
            showTemporaryStatus(addTargetStatus, "Target username cannot be empty.", "warning");
                        return; 
                    }
         if (!profileName) {
            showTemporaryStatus(addTargetStatus, "Please select a promotion profile.", "warning");
            return;
        }

        // Basic username format check and correction
        if (username.startsWith('@')) {
             username = username.substring(1);
             monitorUsernameInput.value = username; // Update input field visually
             console.log(`Corrected username from @${username} to ${username}`);
        }

        showTemporaryStatus(addTargetStatus, `Adding target ${username}...`, "info", 0);
        addMonitoringTargetBtn.disabled = true;


        apiCall('/api/monitoring/targets', 'POST', { target_username: username, promotion_profile_name: profileName })
            .then(data => {
                 addMonitoringTargetBtn.disabled = false;
                 if (data.success && data.targets) {
                     showTemporaryStatus(addTargetStatus, `Successfully added ${username}.`, "success");
                     renderMonitoringTargets(data.targets); // Re-render list
                     monitorUsernameInput.value = ''; // Clear input on success
                     monitorAddProfileSelect.value = ''; // Reset dropdown using new ID
                     clearTemporaryStatus(addTargetStatus); // Clear success message after a delay maybe?
                } else {
                      showTemporaryStatus(addTargetStatus, data.error || `Failed to add target.`, "danger");
                 }
             })
             .catch(error => {
                  // API call helper shows main status error
                  addMonitoringTargetBtn.disabled = false;
                  showTemporaryStatus(addTargetStatus, `Error adding target.`, "danger");
             });
    }


    // Test Get Latest Post (Manual Scrape) (Monitor Page Specific)
    function testGetLatestPost() {
        console.log("testGetLatestPost button clicked");
        // Get elements inside function
        const testScrapeUsernameInput = document.getElementById('test-scrape-username-input');
        const testScrapeBtn = document.getElementById('test-scrape-btn');
        const testScrapeResult = document.getElementById('test-scrape-result');
        // Check elements exist
        if(!testScrapeUsernameInput || !testScrapeBtn || !testScrapeResult) {
            console.error("testGetLatestPost: Missing one or more required test elements.");
            showStatus("UI Error: Cannot find test scrape elements.", 'danger', 'test-scrape-result'); // Show error in relevant status area
            return;
        }

        let username = testScrapeUsernameInput.value.trim();
        if (!username) {
            showTemporaryStatus(testScrapeResult, "Please enter a username to test.", "warning");
            return;
        }
         // Auto-remove @ if present
         if (username.startsWith('@')) {
             username = username.substring(1);
             testScrapeUsernameInput.value = username; // Update input visually
         }

        showTemporaryStatus(testScrapeResult, `Testing scrape for ${username}...`, "info", 0);
        testScrapeBtn.disabled = true;

        apiCall('/api/monitoring/test_get_latest_post', 'POST', { target_username: username })
            .then(data => {
                testScrapeBtn.disabled = false;
                if (data.success) {
                    const timestampText = data.timestamp_iso ? ` (${formatIsoDateTime(data.timestamp_iso)})` : ' (Timestamp not found)';
                    // Use isHtml = true in showStatus to render the link
                    showTemporaryStatus(testScrapeResult, `Success! Found: <a href="${data.url}" target="_blank">${data.url}</a>${timestampText}`, "success", 10000, true);
            } else {
                     showTemporaryStatus(testScrapeResult, `Failed: ${data.error || 'Could not get post info.'}`, "danger");
                 }
            })
            .catch(error => {
                 // API call helper shows main status error
                 testScrapeBtn.disabled = false;
                 showTemporaryStatus(testScrapeResult, `Error during test.`, "danger");
            });
    }

    // --- Profile Page Specific Initialization ---
    function initializeProfilePage(profiles) { // <-- Accept profiles data
        console.log("Running initializeProfilePage with profiles:", profiles);

        // 1. Populate Engagement Options Cache from minimumQuantities
        engagementOptionsCache = []; // Clear previous cache if any
        if (minimumQuantities && typeof minimumQuantities === 'object') {
            Object.keys(minimumQuantities).forEach(key => {
                // Corrected parsing based on previous findings
                let platform = null;
                let engagement = null;
                // Regex to match "('Platform Name', 'Engagement Type')"
                const match = key.match(/^\('([^']+)',\s*'([^']+)'\)$/);
                if (match && match.length === 3) {
                    platform = match[1];
                    engagement = match[2];
                } 
                // --- End Alternative Parsing Logic ---

                if (engagement && !engagementOptionsCache.includes(engagement)) { // Use parsed engagement
                    engagementOptionsCache.push(engagement);
                }
            });
            engagementOptionsCache.sort(); // Sort alphabetically
            console.log("Populated engagementOptionsCache:", engagementOptionsCache);
        } else {
            console.warn("Minimum quantities data not available or invalid, cannot populate engagement cache.");
        }

        // 2. Find Elements 
        const profileSelectDropdownElem = document.getElementById('profile-select'); 
        // const addProfileBtnElem = document.getElementById('add-profile-btn'); // Don't need to find it here anymore
        const editProfileBtnElem = document.getElementById('edit-profile-btn');
        const deleteProfileBtnElem = document.getElementById('delete-profile-btn');

        // Remove listener attachment from here
        // if (addProfileBtnElem) { ... }
        
        // 3. Set initial button states 
        if (editProfileBtnElem) editProfileBtnElem.disabled = true; // Disable initially
        if (deleteProfileBtnElem) deleteProfileBtnElem.disabled = true; // Disable initially

        // 4. Attach Listeners HERE
        console.log("Attaching listeners inside initializeProfilePage...");
        if (profileSelectDropdownElem) { 
            profileSelectDropdownElem.addEventListener('change', handleProfileSelectionChange); 
            handleProfileSelectionChange(); // Call once to set initial state based on default selection
        }
        if (addProfileBtn) { 
            console.log("Found #add-profile-btn, attaching listener...");
            addProfileBtn.addEventListener('click', () => { 
                console.log(`[Click Handler] Value of profileModal: ${profileModal ? 'Exists' : 'NULL or Undefined'}`);
                // Remove setTimeout wrapper - call directly
                openProfileModal();
            }); 
        } else { console.error("#add-profile-btn not found for listener."); }
        
        if (editProfileBtnElem) { editProfileBtnElem.addEventListener('click', handleEditProfileClick); }
        if (deleteProfileBtnElem) { deleteProfileBtnElem.addEventListener('click', handleDeleteProfileClick); }

        // Also attach modal button listeners here if the modal is part of this page's core elements
        const saveProfileBtnElem = document.getElementById('save-profile-btn');
        const closeModalBtnElem = document.getElementById('close-modal-btn');
        const cancelModalBtnElem = document.getElementById('cancel-modal-btn');
        const useRandomDelayCheckboxElem = document.getElementById('use-random-delay');

        if (saveProfileBtnElem) { 
            saveProfileBtnElem.addEventListener('click', (event) => {
                console.log("#save-profile-btn CLICKED - event listener triggered."); // <-- ADDED LOG
                event.preventDefault(); // Prevent default form submission if it's inside a form
                handleSaveProfile();
            });
        }
        if (closeModalBtnElem) { closeModalBtnElem.addEventListener('click', closeProfileModal); }
        if (cancelModalBtnElem) { cancelModalBtnElem.addEventListener('click', closeProfileModal); }
        if (useRandomDelayCheckboxElem) { useRandomDelayCheckboxElem.addEventListener('change', toggleRandomDelayInputs); }
        
        // --- NEW: Attach listener for platform change within modal ---
        const modalPlatformSelect = document.getElementById('modal-platform-select');
        if (modalPlatformSelect) {
            console.log("Attaching listener for #modal-platform-select change...");
            modalPlatformSelect.addEventListener('change', handleModalPlatformChange);
        } else {
             console.error("#modal-platform-select not found during initial listener setup.");
        }
        // ---
        
        // --- NEW: Attach listener for Add Engagement Button within modal ---
        const addEngagementBtn = document.getElementById('add-engagement-row-btn');
        if (addEngagementBtn) {
            console.log("Attaching listener for #add-engagement-row-btn click...");
            addEngagementBtn.addEventListener('click', handleAddEngagementRow);
        } else {
             console.error("#add-engagement-row-btn not found during initial listener setup.");
        }
        // ---
        
        console.log("Profile Page Initialized and Listeners Attached."); 
    }

    // --- Listener for dynamically added Remove buttons ---
    const addedRowsContainer = document.getElementById('added-engagement-rows');
    if (addedRowsContainer) {
        addedRowsContainer.addEventListener('click', function(event) {
            if (event.target.classList.contains('remove-engagement-row-btn')) {
                console.log("Remove button clicked");
                const rowToRemove = event.target.closest('.engagement-row');
                if (rowToRemove) {
                    const type = rowToRemove.dataset.engagementType || 'this row';
                    console.log(`Removing row for ${type}`);
                    rowToRemove.remove();

                    // Check if container is now empty (excluding header)
                    const remainingRows = addedRowsContainer.querySelectorAll('.engagement-row');
                    if (remainingRows.length === 0) {
                        const header = addedRowsContainer.querySelector('.dynamic-engagement-header-row');
                        if (header) {
                            console.log("Last engagement row removed, removing dynamic header.");
                            header.remove();
                        }
                    }
                    // Recalculate total cost after removal
                    try { updateModalProfileCostEstimate(); } catch(_) {}
                } else {
                    console.error("Could not find parent row to remove.");
                }
            }
        });
    } else {
        console.error("Could not find #added-engagement-rows container to attach delegated listener.");
    }

    // --- Function to handle adding an engagement row ---
    function handleAddEngagementRow() {
        const platformSelect = document.getElementById('modal-platform-select');
        const engagementSelect = document.getElementById('modal-engagement-select');
        const container = document.getElementById('added-engagement-rows'); // Use correct container ID

        if (!platformSelect || !engagementSelect || !container) { // Check container
            console.error("Cannot add engagement row: Missing critical elements.");
            return;
        }

        const platform = platformSelect.value;
        const engagementType = engagementSelect.value;
        // Require a specific service selection from the modal dropdown flyout
        let selectedService = null;
        if (engagementSelect && engagementSelect.dataset && engagementSelect.dataset.selectedService) {
            try { selectedService = JSON.parse(engagementSelect.dataset.selectedService); } catch (_) { selectedService = null; }
        }

        if (!engagementType) {
            alert("Please select an engagement type to add.");
            return;
        }
        if (!selectedService || !selectedService.service_id) {
            alert("Please pick a specific service for the selected engagement (hover/click an engagement and choose a service from the flyout).");
            return;
        }

        const existingRow = container.querySelector(`.engagement-row[data-engagement-type="${engagementType}"]`);
        if (existingRow) {
            alert(`"${engagementType}" has already been added.`);
            return;
        }

        // --- Check for and add header if it's the first row --- 
        const existingHeader = container.querySelector('.dynamic-engagement-header-row');
        if (!existingHeader) {
            console.log("Adding dynamic engagement header row...");
            const headerRow = document.createElement('div');
            headerRow.className = 'row g-2 mb-2 fw-bold text-light dynamic-engagement-header-row'; // Added specific class
            // Use shortened, centered headers (except Engagement)
            headerRow.innerHTML = `
                <div class="col-2" style="white-space: nowrap;">Engagement</div>
                <div class="col-2 text-center" style="white-space: nowrap;">Fixed Qty</div>
                <div class="col-1 text-center" style="white-space: nowrap;">Random?</div>
                <div class="col-2 text-center" style="white-space: nowrap;">Min Qty</div>
                <div class="col-2 text-center" style="white-space: nowrap;">Max Qty</div>
                <div class="col-2 text-center" style="white-space: nowrap;">Loop(s)</div>
                <div class="col-1"></div> <!-- Placeholder for remove button column -->
            `;
            container.prepend(headerRow); // Add header *before* the first row
        }
        // -------

        // Determine UI minimum from selected service if available, else fallback to configured minimums
        let minRequired = 1;
        if (selectedService && selectedService.min_qty != null) {
            const parsed = parseInt(selectedService.min_qty, 10);
            if (!isNaN(parsed) && parsed > 0) minRequired = parsed;
        } else {
            try {
                const key = "('" + platform + "', '" + engagementType + "')";
                const cfgMin = minimumQuantities && minimumQuantities[key];
                if (cfgMin != null && !isNaN(parseInt(cfgMin, 10)) && parseInt(cfgMin, 10) > 0) {
                    minRequired = parseInt(cfgMin, 10);
                }
            } catch (_) {}
        }

        console.log(`Adding row for: ${engagementType} (Platform: ${platform}, MinQty UI: ${minRequired}, Service: #${selectedService.service_id})`);
        addEngagementRow(
            engagementType,
            {
                service_id: selectedService.service_id,
                service_name: (selectedService.name || ((selectedService.provider_label || selectedService.provider)+ ' #' + selectedService.service_id)),
                rate_per_1k: (selectedService.rate_per_1k != null) ? parseFloat(selectedService.rate_per_1k) : null,
                min_qty: (selectedService.min_qty != null) ? parseInt(selectedService.min_qty, 10) : null,
                max_qty: (selectedService.max_qty != null) ? parseInt(selectedService.max_qty, 10) : null
            },
            minRequired,
            platform
        );
        // Update total cost after adding a row
        try { updateModalProfileCostEstimate(); } catch(_) {}

    }

    // --- Profile Page Specific Functions --- (Now includes initializeProfilePage)

    function handleProfileSelectionChange() {
        console.log("handleProfileSelectionChange triggered."); // Log start
        // Get elements within the handler as their state might change
        const profileSelectDropdownElem = document.getElementById('profile-select');
        const editProfileBtnElem = document.getElementById('edit-profile-btn');
        const deleteProfileBtnElem = document.getElementById('delete-profile-btn');
        
        if (!profileSelectDropdownElem || !editProfileBtnElem || !deleteProfileBtnElem) {
            console.warn("handleProfileSelectionChange: Could not find necessary elements.");
            return;
        }
        console.log("Found elements in handleProfileSelectionChange."); // Log elements found
        
        const selectedProfile = profileSelectDropdownElem.value;
        console.log(`Selected profile: '${selectedProfile}'`); // Log selected value

        if (selectedProfile) {
            console.log("Enabling Edit/Delete buttons..."); // Log before enabling
            editProfileBtnElem.disabled = false;
            deleteProfileBtnElem.disabled = false;
            console.log("Edit/Delete buttons enabled."); // Log after enabling
            // Optionally display selected profile details here
        } else {
            console.log("Disabling Edit/Delete buttons..."); // Log before disabling
            editProfileBtnElem.disabled = true;
            deleteProfileBtnElem.disabled = true;
            console.log("Edit/Delete buttons disabled."); // Log after disabling
        }
        console.log("handleProfileSelectionChange finished."); // Log end
    }

    function openProfileModal(profileData = null) {
        console.log("[+] openProfileModal START. Data:", profileData);
        if (!profileModal) {
            console.error("Cannot open modal: Global profileModal variable is null or undefined!");
            return;
        }

        // --- Find elements --- 
        const profileEditorForm = document.getElementById('profile-editor-form');
        const originalProfileNameInput = document.getElementById('original-profile-name');
        const editorTitle = document.getElementById('editor-title'); 
        const profileNameInput = document.getElementById('profile-name');
        // Engagement Selection Elements
        const platformSelect = document.getElementById('modal-platform-select');
        const engagementSelect = document.getElementById('modal-engagement-select');
        const addEngagementBtn = document.getElementById('add-engagement-row-btn');
        // Container for dynamic rows
        const addedRowsContainer = document.getElementById('added-engagement-rows');
        // Loop Settings Elements
        const loopCountInput = document.getElementById('loop-count');
        const loopDelayInput = document.getElementById('loop-delay');
        const useRandomDelayCheckbox = document.getElementById('use-random-delay');
        const minDelayInput = document.getElementById('min-delay');
        const maxDelayInput = document.getElementById('max-delay');

        // --- Check if essential elements were found --- 
        // Ensure all elements needed for the *new* structure are checked
        if (!profileEditorForm || !originalProfileNameInput || !editorTitle || !profileNameInput || 
            !platformSelect || !engagementSelect || !addEngagementBtn || !addedRowsContainer || // Check for the NEW container
            !loopCountInput || !loopDelayInput || !useRandomDelayCheckbox || !minDelayInput || !maxDelayInput) {
            console.error("Cannot open modal: One or more required child elements are missing inside #profile-editor-modal. Halting modal open.");
            // Maybe show an error to the user?
            return;
        }
        console.log("All required modal elements found.");

        // --- Reset Form Fields and State --- 
        console.log("Resetting form fields and dynamic area...");
        profileEditorForm.reset();
        originalProfileNameInput.value = '';
        addedRowsContainer.innerHTML = ''; // Clear dynamically added rows
        platformSelect.innerHTML = ''; // Clear platform options before repopulating
        engagementSelect.innerHTML = '<option value="">-- Select Platform First --</option>'; // Reset engagement options
        engagementSelect.disabled = true;
        addEngagementBtn.disabled = true;

        // --- Populate Platform Dropdown from CSV with fallback --- 
        console.log("Populating platform dropdown from CSV...");
        platformSelect.innerHTML = '';
        const platformPlaceholder = document.createElement('option');
        platformPlaceholder.value = "";
        platformPlaceholder.textContent = "-- Select Platform --";
        platformPlaceholder.disabled = true;
        platformPlaceholder.selected = true;
        platformSelect.appendChild(platformPlaceholder);
        (async () => {
            try {
                let platforms = await loadPlatformsFromServer();
                if (!platforms || platforms.length === 0) {
                    console.warn('Platforms API returned empty for modal. Using fallback.');
                    platforms = ['Instagram','TikTok','YouTube','X (Twitter)','Spotify'];
                }
                platforms.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p;
                    option.textContent = p;
                    platformSelect.appendChild(option);
                });
            } catch (err) {
                console.error('Failed to load platforms for modal:', err);
                ['Instagram','TikTok','YouTube','X (Twitter)','Spotify'].forEach(p => {
                    const option = document.createElement('option');
                    option.value = p;
                    option.textContent = p;
                    platformSelect.appendChild(option);
                });
            }
        })();

        // Ensure the change handler is attached even if original binding missed (modal may be dynamic)
        try {
            platformSelect.removeEventListener('change', handleModalPlatformChange);
        } catch (e) { /* ignore if not attached */ }
        platformSelect.addEventListener('change', handleModalPlatformChange);

        // --- Setup Listeners for Platform/Engagement Selection (Remove old ones first if necessary) --- 
        // It's generally safer to attach listeners once outside the openModal function,
        // but if we need to re-attach or if elements are dynamic, do it here.
        // For now, assume listeners are attached once in initializeProfilePage.
        // We just need to ensure the handler exists.
        if (typeof handleModalPlatformChange !== 'function') {
            console.error("handleModalPlatformChange function not found! Engagement dropdown will not populate.");
        }
        
        // --- Set Mode (Add vs Edit) --- 
        console.log("Setting up modal for Add or Edit mode...");
        if (profileData && profileData.name) { // Check if profileData exists and has a name
            // Edit mode
            console.log("Edit mode detected.");
            editorTitle.textContent = "Edit Profile";
            originalProfileNameInput.value = profileData.name;
            profileNameInput.value = profileData.name;
            
            // Populate Loop Settings
            loopCountInput.value = profileData.loop_settings?.loops || 1;
            loopDelayInput.value = profileData.loop_settings?.delay || 0;
            useRandomDelayCheckbox.checked = profileData.loop_settings?.random_delay || false;
            minDelayInput.value = profileData.loop_settings?.min_delay || 0;
            maxDelayInput.value = profileData.loop_settings?.max_delay || 0;

            // Rebuild saved engagement rows
            console.log("Rebuilding saved engagement rows...");
            if (profileData.engagements && Array.isArray(profileData.engagements)) {
                 profileData.engagements.forEach(savedEng => {
                    // Assuming addEngagementRow exists and works with the new structure
                    // Use the saved platform (fallback to Instagram)
                    if (typeof addEngagementRow === 'function') {
                        const platform = savedEng.platform || 'Instagram';
                        const svcMin = (savedEng && savedEng.min_qty != null) ? parseInt(savedEng.min_qty, 10) : null;
                        const minRequired = (svcMin && svcMin > 0) ? svcMin : 1; // Enforce per-service min when available
                        addEngagementRow(savedEng.type, savedEng, minRequired, platform); // Pass saved data + platform
                    } else {
                         console.error("addEngagementRow function is missing!");
                    }
                 });
            } else {
                console.log("No existing engagement data found to rebuild.");
            }

        } else {
            // Add mode
            console.log("Add mode detected.");
            editorTitle.textContent = "Add New Profile";
            // Loop settings defaults are handled by form.reset() or HTML values
            // No engagement rows to add initially
        }

        console.log("Calling toggleRandomDelayInputs...");
        toggleRandomDelayInputs(); // Ensure correct state for loop delays
        console.log("Adding .is-visible class...");
        profileModal.classList.add('is-visible');
        console.log("Added .is-visible class.");
        // Ensure the total cost display exists (create if missing)
        let costElInit = document.getElementById('profile-total-cost');
        if (!costElInit) {
            try {
                const saveBtn = document.getElementById('save-profile-btn');
                const actionsWrap = saveBtn ? saveBtn.parentElement : null; // .text-end border-top...
                const insertParent = actionsWrap ? actionsWrap.parentElement : null; // form root child
                costElInit = document.createElement('div');
                costElInit.id = 'profile-total-cost';
                costElInit.className = 'small text-info mt-2';
                if (insertParent && actionsWrap) {
                    insertParent.insertBefore(costElInit, actionsWrap);
                } else {
                    // Fallback: append to form
                    document.getElementById('profile-editor-form')?.appendChild(costElInit);
                }
                console.log('[ProfilesModal] Injected #profile-total-cost into DOM.');
            } catch (e) { console.warn('Could not inject profile total cost element:', e); }
        }
        // Show a default estimate line so the section is visibly active
        if (costElInit) costElInit.textContent = `Estimated Total Cost: ${formatCurrency(0)}`;
        // Initialize and bind total cost estimate updates
        try { updateModalProfileCostEstimate(); } catch(_) {}
        try {
            const loopCountInputEl = document.getElementById('loop-count');
            if (loopCountInputEl) {
                loopCountInputEl.addEventListener('input', updateModalProfileCostEstimate);
                loopCountInputEl.addEventListener('change', updateModalProfileCostEstimate);
            }
        } catch(_) {}
        
        console.log("[-] openProfileModal END."); 
    }

    // --- Compute and render the total cost estimate for the profile modal ---
    function updateModalProfileCostEstimate() {
        const costEl = document.getElementById('profile-total-cost');
        if (!costEl) return;
        const rowsContainer = document.getElementById('added-engagement-rows');
        if (!rowsContainer) { costEl.textContent = ''; return; }
        const rows = rowsContainer.querySelectorAll('.engagement-row');
        if (!rows || rows.length === 0) { costEl.textContent = ''; return; }

        let totalRowsCost = 0;
        let maxRowLoops = 1;
        rows.forEach(row => {
            const rateAttr = row.getAttribute('data-service-rate');
            const rate = (rateAttr != null && rateAttr !== '') ? parseFloat(rateAttr) : null;
            if (rate == null || isNaN(rate)) return; // cannot compute without a rate
            const isRandom = row.querySelector('input.engagement-random-cb')?.checked;
            const fixedQty = parseInt(row.querySelector('input.engagement-fixed-qty')?.value || '0', 10) || 0;
            const minQty = parseInt(row.querySelector('input.engagement-min-qty')?.value || '0', 10) || 0;
            const maxQty = parseInt(row.querySelector('input.engagement-max-qty')?.value || '0', 10) || 0;
            const rowLoops = parseInt(row.querySelector('input.engagement-loops')?.value || '1', 10) || 1;
            if (rowLoops > maxRowLoops) maxRowLoops = rowLoops;
            const svcMinAttr = row.getAttribute('data-service-min');
            const svcMaxAttr = row.getAttribute('data-service-max');
            const svcMin = svcMinAttr ? parseInt(svcMinAttr, 10) : null;
            const svcMax = svcMaxAttr ? parseInt(svcMaxAttr, 10) : null;

            // MAX-based quantity per user request
            let qty = 0;
            if (isRandom) {
                // Use user-provided Max Qty if valid; else fall back to service max; else 0
                if (maxQty > 0) {
                    qty = maxQty;
                } else if (svcMax && svcMax > 0) {
                    qty = svcMax;
                } else if (svcMin && svcMin > 0) { // last resort
                    qty = svcMin;
                }
            } else {
                // Fixed: use fixed quantity if set; else fallback to service max, then min
                if (fixedQty > 0) {
                    qty = fixedQty;
                } else if (svcMax && svcMax > 0) {
                    qty = svcMax;
                } else if (svcMin && svcMin > 0) {
                    qty = svcMin;
                }
            }
            if (qty <= 0) return;

            const itemCost = (rate * qty) / 1000.0; // cost per execution of this engagement
            totalRowsCost += (itemCost * rowLoops);
        });

        // Auto-set master loop-count to the highest per-row loops for display consistency only
        const loopCountEl = document.getElementById('loop-count');
        if (loopCountEl) {
            const current = parseInt(loopCountEl.value || '1', 10) || 1;
            if (current !== maxRowLoops) loopCountEl.value = String(maxRowLoops);
        }

        // Do NOT multiply by master loops; total already includes each row's loops
        let total = totalRowsCost;
        if (!isFinite(total) || isNaN(total)) total = 0;
        costEl.textContent = `Estimated Total Cost: ${formatCurrency(total)}`;
    }

    // --- NEW Listener function for Platform change INSIDE modal ---
    async function handleModalPlatformChange() {
        const platformSelect = document.getElementById('modal-platform-select');
        const engagementSelect = document.getElementById('modal-engagement-select');
        const addEngagementBtn = document.getElementById('add-engagement-row-btn');

        if (!platformSelect || !engagementSelect || !addEngagementBtn) {
            console.error("Modal platform/engagement select/button not found in change handler.");
            return;
        }

        const selectedPlatform = platformSelect.value;
        console.log(`Modal Platform selected: ${selectedPlatform}`);
        
        // Clear current engagement options and any selected service state
        engagementSelect.innerHTML = ''; 
        try { delete engagementSelect.dataset.selectedService; } catch(_) {}
        // Remove existing custom dropdown wrapper to avoid stale handlers
        try {
            const existingBtn = document.getElementById('modal-eng-btn');
            const existingMenu = document.getElementById('modal-eng-menu');
            if (existingBtn) {
                const wrap = existingBtn.parentElement;
                if (wrap && wrap.parentElement) wrap.parentElement.removeChild(wrap);
            } else if (existingMenu) {
                const wrap = existingMenu.parentElement;
                if (wrap && wrap.parentElement) wrap.parentElement.removeChild(wrap);
            }
        } catch(_) {}

        if (!selectedPlatform) {
            // No platform selected - Reset engagement dropdown
            const placeholder = document.createElement('option');
            placeholder.value = "";
            placeholder.textContent = "-- Select Platform First --";
            engagementSelect.appendChild(placeholder);
            engagementSelect.disabled = true;
            addEngagementBtn.disabled = true;
            return;
        }

        // Enable dropdown and button now that a platform is selected
        engagementSelect.disabled = false;
        addEngagementBtn.disabled = false;

        // Add placeholder
        const placeholder = document.createElement('option');
        placeholder.value = "";
        placeholder.textContent = "-- Select Engagement --";
        engagementSelect.appendChild(placeholder);

        try {
            let engagements = await loadEngagementsFromServer(selectedPlatform);
            if (!engagements || engagements.length === 0) {
                console.warn(`Modal: No engagements from API for ${selectedPlatform}. Using fallback.`);
                engagements = getFallbackEngagements(selectedPlatform);
            }
            if (engagements && engagements.length) {
                engagements.forEach(engType => {
                    const option = document.createElement('option');
                    option.value = engType;
                    option.textContent = engType;
                    engagementSelect.appendChild(option);
                });
                // Setup a fresh custom dropdown for modal engagement
                const customDrop = ensureCustomEngagementDropdown(engagementSelect, platformSelect, 'modal');
                if (customDrop && customDrop.setItems) customDrop.setItems(engagements);
                // Reset selection state for new platform
                engagementSelect.value = '';
                if (customDrop.btn) customDrop.btn.textContent = '-- Select Engagement --';
                const sub = document.getElementById('modal-eng-selected-sub');
                if (sub) sub.textContent = '';
                // Close any open flyout
                try { if (typeof closeFlyout === 'function') closeFlyout(); } catch(_) {}
                console.log(`Populated modal engagement dropdown for ${selectedPlatform} with:`, engagements);
            } else {
                const noOptions = document.createElement('option');
                noOptions.textContent = "No options found";
                engagementSelect.appendChild(noOptions);
                engagementSelect.disabled = true; 
                addEngagementBtn.disabled = true;
            }
        } catch (e) {
            console.error('Failed to load engagements for modal:', e);
            const noOptions = document.createElement('option');
            noOptions.textContent = "Error loading options";
            engagementSelect.appendChild(noOptions);
            engagementSelect.disabled = true; 
            addEngagementBtn.disabled = true;
        }
    }

    // --- Need to attach the listener in initializeProfilePage ---
    // (Placeholder - actual attachment is done later)

    function closeProfileModal() {
        console.log("Attempting to close modal...");
        if (!profileModal) { // Use global variable
            console.error("Cannot close modal: #profile-editor-modal element not found or not assigned!");
            return;
        }
        profileModal.classList.remove('is-visible'); // Use class to hide
        console.log("Removed .is-visible class.");
    }

    function populateEngagementRows(savedEngagements = []) { 
        engagementSettingsDiv.innerHTML = ''; 
        console.log("Populating engagement rows with saved data:", savedEngagements);
        const savedEngagementsMap = {}; 
        if (Array.isArray(savedEngagements)) {
            savedEngagements.forEach(eng => { 
                if(eng && eng.type) { 
                    savedEngagementsMap[eng.type] = eng; 
            }
        });
    }

        // Assume 'Instagram' for min qty check for now
        const platform = 'Instagram';

        engagementOptionsCache.forEach(engagementType => {
            const savedData = savedEngagementsMap[engagementType];
            // Calculate min required for this type
            const minQtyKey = "('" + platform + "', '" + engagementType + "')";
            const minRequired = minimumQuantities[minQtyKey] || 1; // Default to 1 if not found
            addEngagementRow(engagementType, savedData, minRequired); // Pass minRequired
        });
    }

    function addEngagementRow(engagementTypeName, engagementData = null, minRequired = 1, platform = 'Instagram') {
        console.log(`Adding row for type: ${engagementTypeName}, MinRequired: ${minRequired}, Data:`, engagementData);
        
        const row = document.createElement('div');
        row.className = 'row g-2 mb-1 engagement-row'; 
        row.setAttribute('data-engagement-type', engagementTypeName);
        row.setAttribute('data-platform', platform);
        if (engagementData && engagementData.service_id) {
            row.setAttribute('data-service-id', String(engagementData.service_id));
            if (engagementData.service_name) row.setAttribute('data-service-name', engagementData.service_name);
            if (engagementData.rate_per_1k != null) row.setAttribute('data-service-rate', String(engagementData.rate_per_1k));
            if (engagementData.min_qty != null) row.setAttribute('data-service-min', String(engagementData.min_qty));
            if (engagementData.max_qty != null) row.setAttribute('data-service-max', String(engagementData.max_qty));
        }
        // Remove stored min/max data attributes if they exist from previous attempt
        delete row.dataset.minQty;
        delete row.dataset.maxQty;

        // 1. Engagement Type Column
        const typeCol = document.createElement('div');
        typeCol.className = 'col-2 d-flex align-items-center text-light'; // Changed to col-2
        typeCol.style.whiteSpace = 'nowrap'; 
        // Compact label: show 'engagement-type - service_id' to avoid overflow behind controls
        if (engagementData && (engagementData.service_id || row.getAttribute('data-service-id'))) {
            const sid = String(engagementData.service_id || row.getAttribute('data-service-id'));
            typeCol.textContent = `${engagementTypeName} - ${sid}`;
            // Keep full service name as tooltip if available
            if (engagementData.service_name) typeCol.title = engagementData.service_name;
        } else {
            typeCol.textContent = engagementTypeName;
        }
        row.appendChild(typeCol);

        // 2. Fixed Quantity Input Column
        const fixedQtyCol = document.createElement('div');
        fixedQtyCol.className = 'col-2';
        const fixedQtyInput = document.createElement('input');
        fixedQtyInput.type = 'number';
        fixedQtyInput.className = 'engagement-fixed-qty form-control'; 
        fixedQtyInput.min = minRequired; 
        fixedQtyInput.placeholder = `Min: ${minRequired}`;
        fixedQtyInput.value = engagementData?.fixed_quantity || '';
        fixedQtyInput.disabled = engagementData?.use_random_quantity || false; // Set initial state
        fixedQtyCol.appendChild(fixedQtyInput);
        row.appendChild(fixedQtyCol);

        // 3. Random Switch Column
        const randomCol = document.createElement('div');
        randomCol.className = 'col-1 d-flex justify-content-center align-items-center'; // Keep col-1
        const switchWrapper = document.createElement('div');
        switchWrapper.className = 'form-check form-switch';
        const randomCheckbox = document.createElement('input');
        randomCheckbox.type = 'checkbox';
        randomCheckbox.className = 'engagement-random-cb form-check-input'; 
        randomCheckbox.checked = engagementData?.use_random_quantity || false;
        randomCheckbox.setAttribute('role', 'switch');
        switchWrapper.appendChild(randomCheckbox);
        randomCol.appendChild(switchWrapper);
        row.appendChild(randomCol);
        
        // 4. Min Quantity Input Column
        const minQtyCol = document.createElement('div');
        minQtyCol.className = 'col-2'; // Keep col-2
        const minQtyInput = document.createElement('input');
        minQtyInput.type = 'number';
        minQtyInput.className = 'engagement-min-qty form-control'; 
        minQtyInput.min = minRequired; 
        minQtyInput.placeholder = `Min: ${minRequired}`;
        minQtyInput.value = engagementData?.min_quantity || '';
        minQtyInput.disabled = !randomCheckbox.checked; // Set initial state
        minQtyCol.appendChild(minQtyInput);
        row.appendChild(minQtyCol);

        // 5. Max Quantity Input Column
        const maxQtyCol = document.createElement('div');
        maxQtyCol.className = 'col-2'; // Keep col-2
        const maxQtyInput = document.createElement('input');
        maxQtyInput.type = 'number';
        maxQtyInput.className = 'engagement-max-qty form-control'; 
        maxQtyInput.min = minRequired; 
        maxQtyInput.placeholder = 'Max';
        maxQtyInput.value = engagementData?.max_quantity || '';
        maxQtyInput.disabled = !randomCheckbox.checked; // Set initial state
        maxQtyCol.appendChild(maxQtyInput);
        row.appendChild(maxQtyCol);
        
        // 6. Loops Input Column
        const loopCol = document.createElement('div');
        loopCol.className = 'col-2'; // Changed to col-2
        const loopInput = document.createElement('input');
        loopInput.type = 'number';
        loopInput.className = 'engagement-loops form-control'; 
        loopInput.min = '1'; 
        loopInput.placeholder = 'Loops';
        loopInput.value = engagementData?.loops || 1; 
        loopCol.appendChild(loopInput);
        row.appendChild(loopCol);

        // 7. Remove Button Column (NEW)
        const removeCol = document.createElement('div');
        removeCol.className = 'col-1 d-flex align-items-center justify-content-center'; // Keep col-1
        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'btn btn-danger btn-sm remove-engagement-row-btn'; // Specific class for listener
        removeButton.textContent = 'X'; // Simple remove text/icon
        removeButton.title = `Remove ${engagementTypeName} settings`;
        removeCol.appendChild(removeButton);
        row.appendChild(removeCol);

        // Attach listeners to recalc cost when inputs change
        const recalc = () => { try { updateModalProfileCostEstimate(); } catch(_) {} };
        fixedQtyInput.addEventListener('input', recalc);
        minQtyInput.addEventListener('input', recalc);
        maxQtyInput.addEventListener('input', recalc);
        loopInput.addEventListener('input', recalc);
        randomCheckbox.addEventListener('change', () => {
            minQtyInput.disabled = !randomCheckbox.checked;
            maxQtyInput.disabled = !randomCheckbox.checked;
            fixedQtyInput.disabled = randomCheckbox.checked;
            recalc();
        });

        // Reverted Event listener for the random checkbox
        randomCheckbox.addEventListener('change', (e) => { 
            const isChecked = e.target.checked;
            fixedQtyInput.disabled = isChecked;
            minQtyInput.disabled = !isChecked;
            maxQtyInput.disabled = !isChecked;
            if (isChecked) {
                 fixedQtyInput.value = ''; 
                 fixedQtyInput.placeholder = `Min: ${minRequired}`; // Reset placeholder
            } else {
                 minQtyInput.value = '';
                 maxQtyInput.value = '';
                 minQtyInput.placeholder = `Min: ${minRequired}`;
                 maxQtyInput.placeholder = 'Max';
                 // Restore fixed placeholder if needed (already set above)
            }
        });

        // NO longer need to dispatch initial change event as initial state is set on inputs
        // randomCheckbox.dispatchEvent(new Event('change'));

        // Append to the CORRECT container
        const container = document.getElementById('added-engagement-rows');
        if (container) {
             container.appendChild(row);
        } else {
             console.error("Could not find #added-engagement-rows container to append row!");
             // Optionally show an error to the user
        }
        // engagementSettingsDiv.appendChild(row); // REMOVED - Incorrect container
    }

    function handleEditProfileClick() {
        const selectedProfileName = profileSelectDropdown.value;
        if (!selectedProfileName) {
            showStatus("Please select a profile to edit.", "warning");
            return;
        }
        // Fetch full profile data (assuming profilesDataCache holds it)
        const profileData = profilesDataCache[selectedProfileName];
        if (profileData) {
            // Need to structure the data slightly for the modal function
            const modalData = {
                name: selectedProfileName,
                engagements: profileData.engagements || [],
                loop_settings: profileData.loop_settings || {}
            };
            openProfileModal(modalData);
                     } else {
            showStatus(`Error: Could not find data for profile '${selectedProfileName}'.`, "danger");
        }
    }

    function handleDeleteProfileClick() {
        const selectedProfileName = profileSelectDropdown.value;
        if (!selectedProfileName) {
            showStatus("Please select a profile to delete.", "warning");
                     return; 
                }
        if (confirm(`Are you sure you want to delete the profile "${selectedProfileName}"?`)) {
            console.log(`Attempting to delete profile: ${selectedProfileName}`);
            apiCall(`/api/profiles/${selectedProfileName}`, 'DELETE')
                .then(data => {
                    if (data.success) {
                        profilesDataCache = data.profiles; // Update cache
                        populateProfileDropdown(profileSelectDropdown, profilesDataCache); // Repopulate dropdown
                        handleProfileSelectionChange(); // Update button states
                        showStatus(`Profile "${selectedProfileName}" deleted successfully.`, "success");
                        closeProfileModal(); // Close modal if it happened to be open
                    } else {
                        showStatus(data.error || "Failed to delete profile.", "danger");
                    }
                })
                .catch(error => {
                     // API call shows primary status, maybe add specific one?
                     console.error("Error deleting profile:", error);
                     showStatus(`Error deleting profile: ${error.message}`, 'danger');
                 });
        }
    }

    function handleSaveProfile() {
        console.log("handleSaveProfile function started..."); // <-- ADDED LOG
        console.log("Attempting to save profile...");
        const profileName = profileNameInput.value.trim();
        const originalName = originalProfileNameInput.value;
        if (!profileName) {
            // Do NOT replace the input; show message in a dedicated status element under the field
            let nameStatus = document.getElementById('profile-name-status');
            if (!nameStatus) {
                nameStatus = document.createElement('div');
                nameStatus.id = 'profile-name-status';
                nameStatus.className = 'small mt-1';
                // Insert after the input
                if (profileNameInput && profileNameInput.parentElement) {
                    profileNameInput.parentElement.appendChild(nameStatus);
                }
            }
            showTemporaryStatus(nameStatus, "Profile Name cannot be empty.", "warning");
            // Bind one-time input listener to clear message when user types
            try {
                const clearFn = () => { clearTemporaryStatus(nameStatus); profileNameInput.removeEventListener('input', clearFn); };
                profileNameInput.addEventListener('input', clearFn);
            } catch (_) {}
            return;
        }

        const engagements = [];
        const modalEngagementRowsContainer = document.getElementById('added-engagement-rows'); // Get the correct container within the modal
        if (!modalEngagementRowsContainer) {
            console.error("Could not find the container '#added-engagement-rows' for engagement rows in the modal.");
            alert("Internal error: Could not find engagement settings container. Please check console.");
            return; 
        }
        const engagementRows = modalEngagementRowsContainer.querySelectorAll('.engagement-row'); // Query the correct container
        let firstErrorElement = null; 

        engagementRows.forEach(row => {
            const type = row.getAttribute('data-engagement-type'); 
            const platform = row.getAttribute('data-platform') || 'Instagram';
            const serviceIdAttr = row.getAttribute('data-service-id');
            const serviceRateAttr = row.getAttribute('data-service-rate');
            const fixedQtyInput = row.querySelector('input.engagement-fixed-qty');
            const isRandom = row.querySelector('input.engagement-random-cb').checked;
            const minQtyInput = row.querySelector('input.engagement-min-qty');
            const maxQtyInput = row.querySelector('input.engagement-max-qty');
            const loopInput = row.querySelector('input.engagement-loops');
            
            let hasData = false; 
            let isValid = true; 
            let validationMessage = ""; // Store specific error message
            const engagement = {
                type: type,
                platform: platform,
                service_id: serviceIdAttr ? parseInt(serviceIdAttr, 10) : undefined,
                rate_per_1k: serviceRateAttr != null ? parseFloat(serviceRateAttr) : undefined,
                use_random_quantity: isRandom,
                fixed_quantity: null,
                min_quantity: null,
                max_quantity: null,
                loops: parseInt(loopInput.value) || 1
            };

            // --- UI min relaxed; server validates against CSV per selected service ---
            const minRequired = 1;

            fixedQtyInput.style.borderColor = ''; // Reset borders
            minQtyInput.style.borderColor = '';
            maxQtyInput.style.borderColor = '';

            if (isRandom) {
                const minVal = minQtyInput.value.trim();
                const maxVal = maxQtyInput.value.trim();
                if (minVal || maxVal) { 
                    hasData = true;
                    const min = parseInt(minVal);
                    const max = parseInt(maxVal);
                    if (isNaN(min) || min <= 0 || isNaN(max) || max <= 0 || min > max) {
                        isValid = false;
                        validationMessage = "Invalid Min/Max quantity.";
                        minQtyInput.style.borderColor = 'red'; 
                        maxQtyInput.style.borderColor = 'red';
                        if (!firstErrorElement) firstErrorElement = minQtyInput;
                    } else if (minRequired !== undefined && min < minRequired) { // *** ADD MIN CHECK ***
                        isValid = false;
                        validationMessage = `Minimum for random must be at least ${minRequired}.`;
                        minQtyInput.style.borderColor = 'red';
                         if (!firstErrorElement) firstErrorElement = minQtyInput;
                    } else {
                        engagement.min_quantity = min;
                        engagement.max_quantity = max;
                    }
                }
            } else {
                const fixedVal = fixedQtyInput.value.trim();
                if (fixedVal) { 
                    hasData = true;
                    const fixed = parseInt(fixedVal);
                    if (isNaN(fixed) || fixed <= 0) {
                        isValid = false;
                        validationMessage = "Invalid Fixed quantity.";
                        fixedQtyInput.style.borderColor = 'red'; 
                        if (!firstErrorElement) firstErrorElement = fixedQtyInput;
                    } else if (minRequired !== undefined && fixed < minRequired) { // *** ADD MIN CHECK ***
                         isValid = false;
                         validationMessage = `Minimum fixed quantity is ${minRequired}.`;
                         fixedQtyInput.style.borderColor = 'red';
                         if (!firstErrorElement) firstErrorElement = fixedQtyInput;
                    } else {
                        engagement.fixed_quantity = fixed;
                    }
                } 
            }

            if (hasData && isValid) {
                engagements.push(engagement);
            } else if (hasData && !isValid) {
                 // Error occurred, keep track of the first one
                 if (!firstErrorElement) { // Should have been set, but fallback
                     firstErrorElement = (isRandom) ? minQtyInput : fixedQtyInput;
                 }
                 // Store validation message on the row for display? (Optional)
                 row.dataset.validationError = validationMessage; 
            }
        });

        if (firstErrorElement) {
            const errorRow = firstErrorElement.closest('.engagement-row');
            const specificMessage = errorRow.dataset.validationError || "Please correct highlighted errors.";
            // Use showStatus for profile modal errors, need status elements in the modal
            // For now, let's revert to simple alert or console log for modal errors
            // showTemporaryStatus(errorRow, specificMessage, "warning"); 
            console.error("Profile Save Validation Error:", specificMessage, errorRow);
            alert(`Validation Error: ${specificMessage}`); // Simple alert for now
            firstErrorElement.focus();
            delete errorRow.dataset.validationError; 
            return; 
        }
        
        // Collect loop settings
        const loopCountVal = parseInt(loopCountInput.value) || 1;
        const loopDelayVal = parseFloat(loopDelayInput.value) || 0;
        const useRandomDelayVal = useRandomDelayCheckbox.checked;
        const minDelayVal = parseFloat(minDelayInput.value) || 0;
        const maxDelayVal = parseFloat(maxDelayInput.value) || 0;

        if (useRandomDelayVal && minDelayVal > maxDelayVal) {
            // showTemporaryStatus(minDelayInput.parentElement, "Min delay cannot be greater than Max delay.", "warning");
            alert("Validation Error: Min delay cannot be greater than Max delay."); // Simple alert
            return;
        }

        // --- Build the NESTED settings object expected by the backend --- 
        const profileSettings = {
            engagements: engagements, // The array of engagement objects
            loop_settings: { // The loop settings object
                loops: loopCountVal,
                delay: loopDelayVal,
                random_delay: useRandomDelayVal,
                min_delay: minDelayVal,
                max_delay: maxDelayVal
            }
        };

        const profilePayload = {
            name: profileName,
            settings: profileSettings, // Send the NESTED settings object
            original_name: originalName
        };

        console.log("Saving profile data (nested payload):", JSON.stringify(profilePayload, null, 2));

        apiCall('/api/profiles', 'POST', profilePayload)
            .then(data => {
                if (data.success) {
                    profilesDataCache = data.profiles; // Update cache
                    populateProfileDropdown(profileSelectDropdown, profilesDataCache); // Repopulate dropdown
                    profileSelectDropdown.value = profileName; // Select the newly saved/edited profile
                    handleProfileSelectionChange(); // Update button states
                    showStatus("Profile saved successfully!", "success", null, null, 5000, true); // Show as a toast for 5 seconds
                    closeProfileModal();
                } else {
                     // Show error near the save button or profile name
                     showTemporaryStatus(saveProfileBtn.parentElement, data.error || "Failed to save profile.", "danger");
                 }
             })
             .catch(error => {
                 console.error("Error saving profile:", error);
                 // showTemporaryStatus(saveProfileBtn.parentElement, `Error: ${error.message}`, 'danger');
                 alert(`Error saving profile: ${error.message}`); // Simple alert
             });
    }

    function toggleRandomDelayInputs() {
        const isChecked = useRandomDelayCheckbox.checked;
        minDelayInput.disabled = !isChecked;
        maxDelayInput.disabled = !isChecked;
        loopDelayInput.disabled = isChecked;
        if (isChecked) loopDelayInput.value = ''; // Clear fixed delay if random checked
    }

    // --- DEBUG PAGE HANDLERS ---
    function dbgSetResult(ok, resultSpan, logPre, logText) {
        if (resultSpan) {
            resultSpan.textContent = ok ? '✓' : '✗';
            resultSpan.className = ok ? 'text-success fw-bold' : 'text-danger fw-bold';
        }
        if (logPre) {
            logPre.textContent = typeof logText === 'string' ? logText : JSON.stringify(logText, null, 2);
        }
    }

    async function dbgPost(endpoint, body) {
        return await apiCall(endpoint, 'POST', body || {});
    }

    function bindDebugButton(btnId, resultSpanId, logPreId, endpoint, getPayload = () => ({})) {
        const btn = document.getElementById(btnId);
        const resultSpan = document.getElementById(resultSpanId);
        const logPre = document.getElementById(logPreId);
        if (!btn) return;
        btn.addEventListener('click', async () => {
            try {
                if (resultSpan) {
                    resultSpan.textContent = '...';
                    resultSpan.className = 'text-info fw-bold';
                }
                const payload = getPayload();
                const data = await dbgPost(endpoint, payload);
                const ok = !!(data && data.success);
                const logText = data && data.log ? data.log : data;
                dbgSetResult(ok, resultSpan, logPre, logText);
            } catch (e) {
                dbgSetResult(false, resultSpan, logPre, `Error: ${e.message}`);
            }
        });
    }

    async function initializeDebugPage() {
        console.log('Initializing Debug Page...');
        // Open Chrome
        bindDebugButton('dbg-open-browser-btn','dbg-open-browser-result','dbg-open-browser-log','/api/debug/open_browser');
        // Navigate to login
        bindDebugButton('dbg-nav-login-btn','dbg-nav-login-result','dbg-nav-login-log','/api/debug/nav_login', () => {
            const urlInput = document.getElementById('dbg-login-url');
            return { url: urlInput ? urlInput.value.trim() : '' };
        });
        // Select Google -> Run full automation login to mirror real flow
        bindDebugButton('dbg-select-google-btn','dbg-select-google-result','dbg-select-google-log','/api/debug/login');
        // Enter Email
        bindDebugButton('dbg-enter-email-btn','dbg-enter-email-result','dbg-enter-email-log','/api/debug/enter_email', () => {
            const emailInput = document.getElementById('dbg-email');
            return { email: emailInput ? emailInput.value.trim() : '' };
        });
        // Continue after Email
        bindDebugButton('dbg-continue-email-btn','dbg-continue-email-result','dbg-continue-email-log','/api/debug/continue_email');
        // Enter Password
        bindDebugButton('dbg-enter-password-btn','dbg-enter-password-result','dbg-enter-password-log','/api/debug/enter_password', () => {
            const pwdInput = document.getElementById('dbg-password');
            return { password: pwdInput ? pwdInput.value : '' };
        });
        // Continue after Password
        bindDebugButton('dbg-continue-password-btn','dbg-continue-password-result','dbg-continue-password-log','/api/debug/continue_password');
        // Verify Dashboard
        bindDebugButton('dbg-verify-dashboard-btn','dbg-verify-dashboard-result','dbg-verify-dashboard-log','/api/debug/verify_dashboard');
        // Submit Promo
        bindDebugButton('dbg-submit-promo-btn','dbg-submit-promo-result','dbg-submit-promo-log','/api/debug/submit_promo', () => {
            const product = document.getElementById('dbg-product')?.value?.trim() || '';
            const model_size = document.getElementById('dbg-model-size')?.value?.trim() || '';
            const link = document.getElementById('dbg-link')?.value?.trim() || '';
            return { product, model_size, link };
        });
        console.log('Debug Page Ready');
    }

    // --- MAIN EXECUTION --- 
    async function initApp() {
        console.log("Starting App Initialization...");
        // 1. Load common data first and store returned profiles
        const loadedProfiles = await initializeAppCommon();

        // --- Add listener for Save Username button ---
        const saveUsernameBtnElem = document.getElementById('save-username-btn');
        if (saveUsernameBtnElem) {
            saveUsernameBtnElem.addEventListener('click', saveUsername);
            console.log("Attached listener to #save-username-btn");
        } else {
            console.error("Could not find #save-username-btn to attach listener.");
        }
        // --- Load initial username ---
        await loadUsername(); // Load username after attaching listener

        // 2. Detect Page by checking for unique elements
        const promoTitleElem = document.getElementById('page-title-promo'); // Check for unique H2 ID
        const addProfileBtnElem = document.getElementById('add-profile-btn');
        const saveMonitoringSettingsBtnElem = document.getElementById('save-monitoring-settings-btn');
        const historyListElem = document.getElementById('history-list'); // Check for History page

        const isOnPromoPage = !!promoTitleElem; // Use H2 check
        const isOnProfilePage = !!addProfileBtnElem;
        const isOnMonitorPage = !!saveMonitoringSettingsBtnElem;
        const isOnHistoryPage = !!historyListElem;
        const isOnDebugPage = !!document.getElementById('debug-page-container') || (document.body && document.body.id === 'page-debug');
        console.log(`Page Check by Element: Promo=${isOnPromoPage}, Profiles=${isOnProfilePage}, Monitor=${isOnMonitorPage}, History=${isOnHistoryPage}, Debug=${isOnDebugPage}`);

        // 3. Run Page-Specific UI Setup & Attach Listeners
        // Prioritize Promo page check
        if (isOnPromoPage) {
            console.log("Initializing Promo Page (detected by element)...");
            // Pass loaded profiles to avoid race condition
            await initializePromoPage(loadedProfiles);
            await initializeSinglePromoPage();
            // Restore any active jobs from server for cross-device visibility
            await restoreActiveJobs();
        } else if (isOnProfilePage) {
            console.log("Initializing Profiles Page (detected by element)...");
            // Populate dropdown first
            const profileSelectProfilePage = document.getElementById('profile-select'); 
            if (profileSelectProfilePage) { 
                populateProfileDropdown(profileSelectProfilePage, loadedProfiles);
            } else {
                console.error("Could not find profile select dropdown on Profile page (#profile-select).");
            }
            // Initialize page (which attaches listeners)
            await initializeProfilePage(loadedProfiles);
            // Show status after init completes
            setTimeout(() => { showStatus("Profile Page Ready", "success", "profile-page-status-area", "profile-page-status-message", 3000); }, 10);
        } else if (isOnMonitorPage) {
            console.log("Initializing Monitor Page (detected by element)...");
            await initializeMonitorPage(loadedProfiles); // Needs loaded profiles for dropdown
            // Show status after init completes
            setTimeout(() => { showStatus("Monitor Page Ready", "success", "monitor-page-status-area", "monitor-page-status-message", 3000); }, 10);
        } else if (isOnHistoryPage) {
            console.log("Initializing History Page (detected by element)...");
            function initializeHistoryPage() {
                console.log("Initializing History Page...");
                // TODO: Add any specific listeners or UI setup for the history table if needed.
                // For now, it's mostly static HTML generated by Flask.
                // showStatus("History Page Ready", "success", "status-text", "status-text", 3000);
            }
            initializeHistoryPage();
        } else if (isOnDebugPage) {
            console.log("Initializing Debug Page (detected by element)...");
            await initializeDebugPage();
        } else {
            console.log(`Running on unknown page or index page without specific elements.`);
            // Attempt to initialize single promo section if it exists anyway (might be index)
            await initializeSinglePromoPage(); 
        }
        
        // Balance display removed from UI; no initialization needed here.
        
        console.log(`App Initialization finished.`);
    }

    // --- Attach the main initialization to DOMContentLoaded --- 
    // Ensure this is at the top-level scope, not inside another function
    document.addEventListener('DOMContentLoaded', () => {
        console.log("DOMContentLoaded event fired. Pushing initApp to end of queue...");
        // Add setTimeout wrapper to ensure DOM is fully ready and other scripts potentially loaded
        setTimeout(() => {
            console.log("setTimeout(0) callback: Starting App Initialization...");
            // Call initApp, assuming it's defined in the outer scope
            initApp().catch(err => {
                console.error("Fatal error during app initialization:", err);
                showStatus("Critical error initializing application. Please check console.", "danger", "main-status-area", "main-status-message", null);
            });
        }, 0); // Zero delay pushes execution after current stack clears
    }); // Close DOMContentLoaded listener

    // Update UI with fetched username
    function updateUsernameDisplay(username) {
        const usernameInput = document.getElementById('username-display'); // Use original ID
        if (usernameInput) {
            usernameInput.value = username || ''; // Set input value
            console.log("Username display updated:", username);
        } else {
            console.warn("#username-input field not found on current page.");
        }
    }

    // Fetch username
    async function loadUsername() {
        try {
            const data = await apiCall('/api/username', 'GET');
            if (data && data.success) {
                updateUsernameDisplay(data.username);
                return data.username; // Return the username for potential use
            }
        } catch (error) {
            console.error("Failed to load username initially.");
            updateUsernameDisplay('Error loading'); // Show error in display
            // No need to re-throw usually, handled by apiCall
        }
        return null; // Indicate failure
    }

    // Save username
    async function saveUsername() {
        const usernameInput = document.getElementById('username-display'); // Use original ID
        const saveBtn = document.getElementById('save-username-btn'); // Use original ID
        const statusAreaId = 'profile-page-status-area'; // Use profile page specific status
        const statusMessageId = 'profile-page-status-message';

        if (!usernameInput || !saveBtn) {
            console.error("Cannot save username, input or button not found.");
            return;
        }
        const newUsername = usernameInput.value.trim();
        if (!newUsername) {
            showStatus("Username cannot be empty.", 'warning', statusAreaId, statusMessageId, 3000);
            return;
        }

        // Disable button during save
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            const data = await apiCall('/api/username', 'POST', { username: newUsername });
            if (data && data.success) {
                showStatus("Username saved successfully!", 'success', statusAreaId, statusMessageId, 3000);
                updateUsernameDisplay(data.username); // Update display with potentially cleaned name
            } else {
                // Error already shown by apiCall
                // Revert to last saved value on failure by reloading
                const lastUsername = await loadUsername(); // Fetch the last saved username
                if (lastUsername !== null) {
                    usernameInput.value = lastUsername;
                } else {
                    // Handle case where loadUsername also failed
                    usernameInput.value = ''; // Or keep the failed input? Reverting seems safer.
                    showStatus("Failed to save username and could not reload previous value.", 'danger', statusAreaId, statusMessageId, 5000);
                }
            }
        } catch (error) {
            // Error already shown by apiCall
            // Revert to last saved value on failure by reloading
             const lastUsername = await loadUsername(); // Fetch the last saved username
             if (lastUsername !== null) {
                 usernameInput.value = lastUsername;
             } else {
                 // Handle case where loadUsername also failed
                 usernameInput.value = ''; // Or keep the failed input? Reverting seems safer.
                 showStatus("Failed to save username and could not reload previous value.", 'danger', statusAreaId, statusMessageId, 5000);
             }
        } finally {
             // Re-enable button
             saveBtn.disabled = false;
             saveBtn.textContent = 'Save Username'; // Restore original button text
        }
    }
});