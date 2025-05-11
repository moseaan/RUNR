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

    // --- Determine page based on elements existing FIRST (MOVED LATER) ---
    /*
    const isOnPromoPage = !!document.getElementById('run-profile-btn');
    const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
    const isOnProfilePage = !!document.getElementById('add-profile-btn'); 
    console.log(`Initial Page Check: Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}`);
    */

    // --- Element Refs (Get elements needed across different initializers/listeners) ---
    const runProfileBtn = document.getElementById('run-profile-btn'); 
    const stopProfileBtn = document.getElementById('stop-profile-btn'); 
    const profileSelectPromo = document.getElementById('profile-select-promo'); 
    const promoLinkInput = document.getElementById('promo-link-input'); 
    const profileSelectProfilePage = document.getElementById('profile-select');
    const addProfileBtn = document.getElementById('add-profile-btn');
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const deleteProfileBtn = document.getElementById('delete-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-modal-btn');
    const profileEditorForm = document.getElementById('profile-editor-form');
    const useRandomDelayCheckbox = document.getElementById('use-random-delay');
    // const profileModal = document.getElementById('profile-modal'); // REMOVE - profileModal is global let
    // const editorTitle = document.getElementById('profile-editor-title'); // Corrected to editor-title later
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
            const data = await response.json(); // Assume JSON response

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

    // Show status message in designated area
    function showStatus(message, type = 'info', areaId = 'main-status-area', messageId = 'main-status-message', duration = 0) {
        const statusArea = document.getElementById(areaId);
        const statusMessage = document.getElementById(messageId);
        
        if (!statusArea || !statusMessage) {
            console.warn(`showStatus: Could not find status elements (areaId: ${areaId}, messageId: ${messageId}). Message: ${message}`);
            // Fallback to console or a generic alert?
            // alert(`${type.toUpperCase()}: ${message}`); 
            return; // Exit if elements aren't found
        }

        console.log(`Status (${type}) [${areaId}/${messageId}]: ${message}`);
        
        // Use Bootstrap alert classes for styling
        statusArea.className = `alert alert-${type} status-area`; // Reset classes and set new type
        statusMessage.textContent = message;
        statusArea.style.display = 'block'; // Make sure area is visible

        // Clear any existing timeout for THIS specific area/message combo if needed
        // (Using a global or scoped timeout manager might be better if clearing is frequent)

        // Auto-hide after duration if specified
        if (duration > 0) {
            setTimeout(() => {
                statusArea.style.display = 'none'; // Hide the area
            }, duration);
        }
    }
    
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

        // Set new timeout if duration > 0
        if (duration > 0) {
            tempStatusTimeouts[elementId] = setTimeout(() => {
                clearTemporaryStatus(element); // Use helper to clear
             }, duration);
        }
    }
    
    // Clear temporary status for an element
     function clearTemporaryStatus(element) {
        if (!element) return;
        const elementId = element.id;
        if (elementId && tempStatusTimeouts[elementId]) {
            clearTimeout(tempStatusTimeouts[elementId]);
            delete tempStatusTimeouts[elementId];
        }
        element.textContent = '';
        element.className = 'status-display';
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
    function startSinglePromotion() {
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

        // Minimum Quantity Check
        const key = "('" + platform + "', '" + engagement + "')";
        const minQty = minimumQuantities[key];
        if (minQty !== undefined && quantityNum < minQty) {
             showStatus(`Minimum quantity for ${platform} ${engagement} is ${minQty}.`, 'warning', statusAreaId, statusMessageId, 4000);
             return;
        }

        showStatus(`Scheduling single promo: ${quantity} ${engagement} for ${link}...`, 'info', statusAreaId, statusMessageId);
        disableActionButtons(); // Disable both single and profile buttons

        apiCall('/api/start_single_promo', 'POST', { platform, engagement, link, quantity: quantityNum })
            .then(data => {
                if (data.success && data.job_id) {
                    currentProfileJobId = data.job_id; // Reuse the same variable for tracking active job
                    showStatus(data.message || 'Single promo scheduled.', 'info', statusAreaId, statusMessageId);
                    // Start polling if needed (consider if single promos need polling)
                    // startStatusPolling(currentProfileJobId); 
                    // For single, maybe just show success/fail and re-enable?
                    showStatus(`Job ${currentProfileJobId} scheduled successfully.`, 'success', statusAreaId, statusMessageId, 5000);
                     handleFinalJobStatus(currentProfileJobId); // Directly treat as finished for now
                } else {
                    showStatus(data.error || 'Failed to schedule single promo.', 'danger', statusAreaId, statusMessageId);
                    enableActionButtons();
                }
            })
            .catch(error => {
                 // API call helper already shows status
                 enableActionButtons();
             });
    }

    // Start Profile-Based Promotion (Promo Page Specific)
    function startProfilePromotion(profileName, link) { // Pass params directly
        console.log("startProfilePromotion called");
        const statusAreaId = 'promo-status-area';
        const statusMessageId = 'promo-status-message';
        const stopBtn = document.getElementById('stop-profile-btn');

        // Validation already done in the event listener
        showStatus(`Scheduling profile promo: '${profileName}' for ${link}...`, 'info', statusAreaId, statusMessageId);
        disableActionButtons();

        apiCall('/api/start_promo', 'POST', { profile_name: profileName, link: link })
             .then(data => {
                if (data.success && data.job_id) {
                    currentProfileJobId = data.job_id;
                    if (stopBtn) stopBtn.disabled = false; // Enable stop button only when job starts
                    showStatus(data.message || `Profile promo '${profileName}' scheduled. Job ID: ${currentProfileJobId}`, 'info', statusAreaId, statusMessageId);
                    startStatusPolling(currentProfileJobId);
                } else {
                    showStatus(data.error || 'Failed to schedule profile promo.', 'danger', statusAreaId, statusMessageId);
                    enableActionButtons(); // Re-enable run button if scheduling failed
                }
            })
            .catch(error => {
                 // API call helper already shows status
                 enableActionButtons();
            });
    }
    
    // --- Polling Functions ---
    function startStatusPolling(jobId) {
        stopStatusPolling(); // Clear any existing interval
        console.log(`Starting status polling for Job ID: ${jobId}`);
        showStatus(`Job ${jobId} running... Polling status.`, 'info', 'promo-status-area', 'promo-status-message'); // Use specific area
        
        // Ensure stop button is enabled during polling
        const stopBtn = document.getElementById('stop-profile-btn');
        if(stopBtn) stopBtn.disabled = false;
        
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
            const data = await apiCall(`/api/job_status/${jobId}`);
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
        const profilePromoBtn = document.getElementById('run-profile-btn');
        const stopBtn = document.getElementById('stop-profile-btn'); // Also manage stop button
        if(singlePromoBtn) singlePromoBtn.disabled = true;
        if(profilePromoBtn) profilePromoBtn.disabled = true;
        if(stopBtn) stopBtn.disabled = true; // Usually disable stop too initially
    }

    function enableActionButtons() {
        console.log("Enabling action buttons...");
        const singlePromoBtn = document.getElementById('start-single-promo-btn');
        const profilePromoBtn = document.getElementById('run-profile-btn');
        const stopBtn = document.getElementById('stop-profile-btn'); // Stop button should be handled separately
        if(singlePromoBtn) singlePromoBtn.disabled = false;
        if(profilePromoBtn) profilePromoBtn.disabled = false;
        // Stop button is enabled ONLY when a profile job starts and disabled when it ends (in handleFinalJobStatus)
        // if(stopBtn) stopBtn.disabled = true; 
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

    // --- Run Initialization (FIRST IIFE) --- 
    (async () => {
        await initializeAppCommon(); // Loads data into caches
        
        // --- Page Detection (Moved Here) ---
        const isOnPromoPage = !!document.getElementById('run-profile-btn');
        const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
        const isOnProfilePage = !!document.getElementById('add-profile-btn'); 
        console.log(`Page Check (Inside IIFE): Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}`);

        // Page-specific initializations
        if (isOnPromoPage) {
            console.log("Running Promo Page specific init...");
            await initializePromoPage(); // Call the new initializer
            // Moved status message inside initializePromoPage for better timing
            // setTimeout(() => { showStatus("Promo Page Ready", "success", "promo-status-area", "promo-status-message", 3000); }, 10); 
        } else if (isOnMonitorPage) {
            console.log("Running Monitor Page specific init...");
            await initializeMonitorPage(); // Calls its own populate dropdown
            setTimeout(() => { showStatus("Monitor Page Ready", "success", "monitor-page-status-area", "monitor-page-status-message", 3000); }, 10); 
        } else if (isOnProfilePage) { 
             console.log("Running Profile Page specific init...");
             const profileSelectProfilePage = document.getElementById('profile-select'); // Get specific element
             if (profileSelectProfilePage) { // Populate correct dropdown
                 populateProfileDropdown(profileSelectProfilePage);
             } else {
                 console.error("Could not find profile select dropdown on Profile page.");
             }
             initializeProfilePage(); 
             setTimeout(() => { showStatus("Profile Page Ready", "success", "profile-page-status-area", "profile-page-status-message", 3000); }, 10);
        } else {
            // Assuming it might be the index/single promo page if none of the others match specifically
            console.log("Running on Index/Single Promo Page specific init...");
            await initializeSinglePromoPage(); // Initialize elements for single promo section
            // No specific dropdowns to populate here initially, handled by interactions
        }
        
        console.log(`Initialization and listeners setup finished.`);
    })();

    // --- Promo Page Specific Initialization ---
    async function initializePromoPage(profiles) { // <-- Accept profiles data
        console.log("Running initializePromoPage with profiles:", profiles);

        // Ensure data caches are populated (should be by initializeAppCommon)
        // Can now use the passed-in profiles directly
        if (!profiles || Object.keys(profiles).length === 0) {
            console.warn("Profile data passed to initializePromoPage is empty.");
            showStatus("Failed to load profile data. Cannot populate dropdown.", 'warning', 'promo-status-area', 'promo-status-message');
            // Maybe attempt to reload or show error?
            // return; // Stop initialization if data is missing?
        }
        // Minimum quantities check (needed for engagement dropdown - though not directly used here)
        if (!minimumQuantities || Object.keys(minimumQuantities).length === 0) {
            console.warn("Minimum quantities not ready for Promo page init.");
            // This might affect engagement dropdown if it were on this page
        }

        // 1. Populate Dropdowns
        // *** Ensure correct ID is used for the promo page dropdown ***
        const profileSelectPromo = document.getElementById('profile-select-promo'); // <-- USE CORRECT ID
        if (profileSelectPromo) {
            console.log("Found promo profile select dropdown (#profile-select-promo), populating...");
            populateProfileDropdown(profileSelectPromo, profiles); // <-- Pass profiles data
        } else {
            console.error("Promo profile select dropdown (#profile-select-promo) not found.");
            showStatus("UI Error: Profile selection element missing.", 'danger', 'promo-status-area', 'promo-status-message');
        }
        
        // Note: Engagement dropdown is typically part of the SINGLE promo section, not PROFILE promo.
        // If you intended an engagement dropdown here, add its initialization.
        // updateEngagementOptions(); // Populates based on platform (hardcoded IG for now)
        // updateMinQuantityLabel(); // Updates placeholder based on selection

        // 3. Attach Listeners for Profile Promo section
        const runProfileBtn = document.getElementById('run-profile-btn');
        const stopProfileBtn = document.getElementById('stop-profile-btn');
        const promoLinkInput = document.getElementById('promo-link-input');

        if (runProfileBtn && profileSelectPromo && promoLinkInput) {
            runProfileBtn.addEventListener('click', () => {
                const profileName = profileSelectPromo.value;
                const link = promoLinkInput.value.trim();

                if (!profileName) {
                    showStatus("Please select a promotion profile.", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link) {
                    showStatus("Please enter the link for the profile promotion.", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link.toLowerCase().startsWith('https://')) {
                     showStatus("Link must start with https://", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                     return;
                }
                startProfilePromotion(profileName, link);
            });
        } else {
             console.error("Could not find one or more required elements for profile promo form listeners.");
             showStatus("UI Error: Profile promo form incomplete.", 'danger', 'promo-status-area', 'promo-status-message');
        }
        
        if (stopProfileBtn) {
            stopProfileBtn.addEventListener('click', stopProfilePromotion);
        } else {
             console.error("Could not find stop profile promo button.");
        }
        
         // Show ready status AFTER setup
        setTimeout(() => { showStatus("Promo Page Ready", "success", "promo-status-area", "promo-status-message", 3000); }, 100); 
    }

    // --- Single Promo Page Specific Initialization (if separate or part of index) ---
    async function initializeSinglePromoPage() {
        console.log("Running initializeSinglePromoPage...");
        // Ensure minimums are loaded (should be by initializeAppCommon)
         if (!minimumQuantities || Object.keys(minimumQuantities).length === 0) {
            console.warn("Minimum quantities not ready for Single Promo init.");
            showStatus("Failed to load configuration. Engagement options may be incorrect.", 'warning', 'single-promo-status-area', 'single-promo-status-message');
         }
        
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const singlePromoBtn = document.getElementById('start-single-promo-btn');

        if (platformSelect && engagementSelect) {
            // 1. Populate platform dropdown (can be static or dynamic if needed)
            // Assuming platforms are relatively static for now. Add options if empty.
            if(platformSelect.options.length <= 1) { // Keep placeholder if exists
                const platforms = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]; // Or get from config if needed
                platforms.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p;
                    option.textContent = p;
                    platformSelect.appendChild(option);
                });
            }

            // 2. Setup listener to update engagements when platform changes
            platformSelect.addEventListener('change', updateEngagementOptions);
            engagementSelect.addEventListener('change', updateMinQuantityLabel); // Update min label when engagement changes too
            
            // 3. Initial population of engagement based on default platform
            updateEngagementOptions(); // Call once on load
            updateMinQuantityLabel(); // Call once on load
            
        } else {
             console.error("Could not find platform or engagement select dropdowns for single promo.");
             showStatus("UI Error: Single promo dropdowns missing.", 'danger', 'single-promo-status-area', 'single-promo-status-message');
        }
        
        // 4. Attach listener for single promo button
        if (singlePromoBtn) {
            singlePromoBtn.addEventListener('click', startSinglePromotion);
        } else {
            console.error("Could not find single promo button.");
            showStatus("UI Error: Single promo button missing.", 'danger', 'single-promo-status-area', 'single-promo-status-message');
        }
        
        // Show ready status AFTER setup (assuming single promo elements exist)
         const statusArea = document.getElementById('single-promo-status-area');
         if (statusArea) {
            setTimeout(() => { showStatus("Single Promo Section Ready", "success", "single-promo-status-area", "single-promo-status-message", 3000); }, 150); 
         }
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

    // --- NEW Stop Function using API ---
    async function stopProfilePromotion() {
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
                // Polling should eventually reflect 'stopped' status. We don't stop polling here.
                // Button enabling will happen when polling detects final state.
            } else {
                // API call succeeded but backend reported an issue
                 showStatus(data.message || `Failed to register stop request for job ${currentProfileJobId}.`, 'warning', 'promo-status-area', 'promo-status-message', 5000);
                 if(stopButton) stopButton.disabled = false; // Re-enable if request failed
            }
        } catch (error) {
            // Network/fetch error handled by apiCall showing status
             showStatus(`Error sending stop request for ${currentProfileJobId}. Check console.`, 'danger', 'promo-status-area', 'promo-status-message');
             if(stopButton) stopButton.disabled = false; // Re-enable on error
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
        let minQty = 0; // Default to 0 if not found

        if (selectedPlatform && selectedEngagement && minimumQuantities) {
            // Construct the key string format used in the backend: "('Platform', 'Engagement')"
            // Avoid complex escaping in template literals
            const key = "('" + selectedPlatform + "', '" + selectedEngagement + "')";
            minQty = minimumQuantities[key] || 1; // Default to 1 if not found
        }

        const placeholderText = minQty > 0 ? `Minimum: ${minQty}` : "Quantity";
        quantityInput.placeholder = placeholderText;

        // Optionally update the label text itself
        if (quantityLabel) {
            // quantityLabel.textContent = minQty > 0 ? `Quantity (Min: ${minQty}):` : "Quantity:"; // Example
        }
        console.log(`Updated quantity placeholder for ${selectedPlatform}/${selectedEngagement}: "${placeholderText}" (Min: ${minQty})`);
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
                
                // --- Alternative Parsing Logic: String manipulation --- 
                let platform = null;
                let engagement = null;
                if (key.startsWith("('") && key.endsWith("')")) {
                    const content = key.substring(2, key.length - 2); // Remove (' and ')
                    const parts = content.split("', '"); // Split by ', '
                    if (parts.length === 2) {
                        platform = parts[0];
                        engagement = parts[1];
                    }
                }
                // --- End Alternative Parsing Logic ---

                if (platform && engagement) { 
                    if (platform === selectedPlatform) {
                        availableEngagements.add(engagement);
                    }
                } else {
                    console.warn(`Could not parse minimum quantity key: ${key} (String manipulation failed)`);
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
    async function initializeMonitorPage() {
        console.log("Running initializeMonitorPage...");

        // 1. Load settings and targets concurrently
        await Promise.allSettled([
            loadMonitoringSettings(),
            loadMonitoringTargets()
        ]);
        console.log("Initial settings and targets loaded for Monitor Page.");

        // 2. Populate the 'Add Target' profile dropdown
        const monitorAddProfileSelect = document.getElementById('monitor-add-profile-select');
        if (monitorAddProfileSelect) {
            populateProfileDropdown(monitorAddProfileSelect); // Use the common function
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
                pollingIntervalInput.value = data.settings.polling_interval_seconds || '';
                showTemporaryStatus(settingsStatus, "Settings loaded.", "success");
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
        if(!pollingIntervalInput || !settingsStatus) {
           console.error("saveMonitoringSettings: Missing required elements.");
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
        if(monitorListStatus) showTemporaryStatus(monitorListStatus, "Loading targets...", "info", 0);
        try {
            const data = await apiCall('/api/monitoring/targets');
            if (data.success && data.targets) {
                 renderMonitoringTargets(data.targets);
                 if (data.targets.length === 0) {
                     showTemporaryStatus(monitorListStatus, "No targets being monitored.", "info");
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
                     <button class="btn btn-sm btn-danger remove-monitor-btn" data-target-id="${target.id}" data-target-name="${target.target_username}">
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

        // Add listeners to the new buttons
        document.querySelectorAll('.toggle-monitor-btn').forEach(button => {
            button.addEventListener('click', handleToggleMonitoring);
        });
        document.querySelectorAll('.remove-monitor-btn').forEach(button => {
            button.addEventListener('click', handleRemoveMonitoring);
        });
    }

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
            .then(data => {
                if (data.success && data.targets) {
                    renderMonitoringTargets(data.targets); // Re-render the whole list
                    showTemporaryStatus(monitorListStatus, `Successfully ${newState ? 'started' : 'stopped'} monitoring for ${targetName}.`, "success");
                } else {
                     showTemporaryStatus(monitorListStatus, data.error || `Failed to ${action.toLowerCase()} monitoring.`, "danger");
                     // Button will be re-enabled by re-rendering or need manual re-enable if render fails
                     // Let's try re-enabling manually just in case render fails
                     button.disabled = false;
                }
            })
            .catch(error => {
                // API call helper shows main status error
                showTemporaryStatus(monitorListStatus, `Error ${action.toLowerCase()} monitoring.`, "danger");
                button.disabled = false; // Re-enable button on failure
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
                if (key.startsWith("('") && key.endsWith("')")) {
                    const content = key.substring(2, key.length - 2); 
                    const parts = content.split("', '"); 
                    if (parts.length === 2) {
                        platform = parts[0]; 
                        engagement = parts[1];
                    }
                }
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

        if (saveProfileBtnElem) { saveProfileBtnElem.addEventListener('click', handleSaveProfile); }
        if (closeModalBtnElem) { closeModalBtnElem.addEventListener('click', closeProfileModal); }
        if (cancelModalBtnElem) { cancelModalBtnElem.addEventListener('click', closeProfileModal); }
        if (useRandomDelayCheckboxElem) { useRandomDelayCheckboxElem.addEventListener('change', toggleRandomDelayInputs); }
        
        console.log("Profile Page Initialized and Listeners Attached."); 
    }


    // --- NEW Profile Page Specific Functions --- (Now includes initializeProfilePage)

    // let engagementOptionsCache = []; // Moved inside initializeProfilePage
    // const profileSelectDropdown = document.getElementById('profile-select'); // Already defined above

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
        console.log("[+] openProfileModal START. Data:", profileData); // Log start
        // const profileModal = document.getElementById('profile-editor-modal'); // Use global now
        if (!profileModal) { // Check global variable
            console.error("Cannot open modal: Global profileModal variable is null or undefined!");
            return;
        } else {
            // Restore this log
            console.log("Found #profile-editor-modal element via global ref.");
        }
        
        // Find other elements needed within the modal and log success/failure
        const profileEditorForm = document.getElementById('profile-editor-form');
        console.log(`> Found #profile-editor-form: ${!!profileEditorForm}`); // Granular log
        const originalProfileNameInput = document.getElementById('original-profile-name');
        console.log(`> Found #original-profile-name: ${!!originalProfileNameInput}`); // Granular log
        const engagementSettingsDiv = document.getElementById('engagement-settings');
        console.log(`> Found #engagement-settings: ${!!engagementSettingsDiv}`); // Granular log
        const editorTitle = document.getElementById('editor-title'); 
        console.log(`> Found #editor-title: ${!!editorTitle}`); // Granular log
        const profileNameInput = document.getElementById('profile-name');
        console.log(`> Found #profile-name: ${!!profileNameInput}`); // Granular log
        const loopCountInput = document.getElementById('loop-count');
        console.log(`> Found #loop-count: ${!!loopCountInput}`); // Granular log
        const loopDelayInput = document.getElementById('loop-delay');
        console.log(`> Found #loop-delay: ${!!loopDelayInput}`); // Granular log
        const useRandomDelayCheckbox = document.getElementById('use-random-delay');
        console.log(`> Found #use-random-delay: ${!!useRandomDelayCheckbox}`); // Granular log
        const minDelayInput = document.getElementById('min-delay');
        console.log(`> Found #min-delay: ${!!minDelayInput}`); // Granular log
        const maxDelayInput = document.getElementById('max-delay');
        console.log(`> Found #max-delay: ${!!maxDelayInput}`); // Granular log

        // Check if ALL essential elements were found
        console.log("Checking if all modal elements were found...");
        if (!profileEditorForm || !originalProfileNameInput || !engagementSettingsDiv || !editorTitle || !profileNameInput || !loopCountInput || !loopDelayInput || !useRandomDelayCheckbox || !minDelayInput || !maxDelayInput) {
            console.error("Cannot open modal: One or more required child elements are missing inside #profile-editor-modal. Halting modal open.");
            return;
        }
        console.log("All required child elements found.");

        console.log("Resetting form fields...");
        profileEditorForm.reset();
        originalProfileNameInput.value = '';
        engagementSettingsDiv.innerHTML = ''; // Clear previous engagement rows
        // toggleRandomDelayInputs(); // Reset random delay state - Call later
        // minDelayInput.disabled = !useRandomDelayCheckbox.checked; // Set later
        // maxDelayInput.disabled = !useRandomDelayCheckbox.checked; // Set later

        console.log("Setting up modal for Add or Edit mode...");
        if (profileData) {
            // Edit mode
            console.log("Edit mode detected.");
            editorTitle.textContent = "Edit Profile";
            originalProfileNameInput.value = profileData.name;
            profileNameInput.value = profileData.name;
            loopCountInput.value = profileData.loop_settings?.loops || 1;
            loopDelayInput.value = profileData.loop_settings?.delay || 0;
            useRandomDelayCheckbox.checked = profileData.loop_settings?.random_delay || false;
            minDelayInput.value = profileData.loop_settings?.min_delay || 60;
            maxDelayInput.value = profileData.loop_settings?.max_delay || 300;
            
            console.log("Calling populateEngagementRows (Edit mode)...");
            populateEngagementRows(profileData.engagements);
            console.log("Finished populateEngagementRows (Edit mode).");
        } else {
            // Add mode
            console.log("Add mode detected.");
            editorTitle.textContent = "Add New Profile";
            console.log("Calling populateEngagementRows (Add mode)...");
            // *** Restore call ***
            populateEngagementRows(); // Call with no args for default row(s)
            console.log("Finished populateEngagementRows (Add mode)."); // Restore log
        }

        console.log("Calling toggleRandomDelayInputs...");
        toggleRandomDelayInputs(); // Ensure correct state after population
        console.log("Adding .is-visible class...");
        profileModal.classList.add('is-visible');
        console.log("Added .is-visible class.");
        
        // Log computed styles for debugging visibility
        const computedStyle = window.getComputedStyle(profileModal);
        console.log(`Computed Visibility: ${computedStyle.visibility}`);
        console.log(`Computed Opacity: ${computedStyle.opacity}`);
        console.log(`Computed Z-Index: ${computedStyle.zIndex}`);
        console.log(`Computed Display: ${computedStyle.display}`);

        console.log("[-] openProfileModal END."); // Log end
    }

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

    function addEngagementRow(engagementTypeName, engagementData = null, minRequired = 1) { // Add minRequired param
        console.log(`Adding row for type: ${engagementTypeName}, MinRequired: ${minRequired}, Data:`, engagementData);
        const row = document.createElement('div');
        row.className = 'engagement-row';
        row.setAttribute('data-engagement-type', engagementTypeName);

        const typeLabel = document.createElement('span'); 
        typeLabel.className = 'engagement-type-label'; 
        typeLabel.textContent = engagementTypeName;

        const fixedQtyInput = document.createElement('input');
        fixedQtyInput.type = 'number';
        fixedQtyInput.className = 'engagement-fixed-qty form-control'; 
        fixedQtyInput.min = minRequired; // Set min attribute
        fixedQtyInput.placeholder = `Min: ${minRequired}`;
        fixedQtyInput.value = engagementData?.fixed_quantity || '';
        fixedQtyInput.disabled = engagementData?.use_random_quantity || false;

        const randomCheckbox = document.createElement('input');
        randomCheckbox.type = 'checkbox';
        randomCheckbox.className = 'engagement-random-cb form-check-input'; 
        randomCheckbox.checked = engagementData?.use_random_quantity || false;
        
        const minQtyInput = document.createElement('input');
        minQtyInput.type = 'number';
        minQtyInput.className = 'engagement-min-qty form-control'; 
        minQtyInput.min = minRequired; // Set min attribute
        minQtyInput.placeholder = `Min: ${minRequired}`;
        minQtyInput.value = engagementData?.min_quantity || '';
        minQtyInput.disabled = !randomCheckbox.checked;

        const maxQtyInput = document.createElement('input');
        maxQtyInput.type = 'number';
        maxQtyInput.className = 'engagement-max-qty form-control'; 
        maxQtyInput.min = minRequired; // Max also can't be less than overall min
        maxQtyInput.placeholder = 'Max';
        maxQtyInput.value = engagementData?.max_quantity || '';
        maxQtyInput.disabled = !randomCheckbox.checked;

        const loopInput = document.createElement('input');
        loopInput.type = 'number';
        loopInput.className = 'engagement-loops form-control'; 
        loopInput.min = '1'; // Loops min is always 1
        loopInput.placeholder = 'Loops';
        loopInput.value = engagementData?.loops || 1; 

        // Event listener for the random checkbox remains the same
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
            }
        });

        // Append elements in order
        row.appendChild(typeLabel);
        row.appendChild(fixedQtyInput);
        row.appendChild(randomCheckbox);
        row.appendChild(minQtyInput);
        row.appendChild(maxQtyInput);
        row.appendChild(loopInput);
        
        engagementSettingsDiv.appendChild(row);
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
        console.log("Attempting to save profile...");
        const profileName = profileNameInput.value.trim();
        const originalName = originalProfileNameInput.value;
        if (!profileName) {
            showTemporaryStatus(profileNameInput.parentElement, "Profile Name cannot be empty.", "warning");
            return;
        }

        const engagements = [];
        const engagementRows = engagementSettingsDiv.querySelectorAll('.engagement-row');
        let firstErrorElement = null; 

        engagementRows.forEach(row => {
            const type = row.getAttribute('data-engagement-type'); 
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
                use_random_quantity: isRandom,
                fixed_quantity: null,
                min_quantity: null,
                max_quantity: null,
                loops: parseInt(loopInput.value) || 1
            };

            // --- Platform is assumed 'Instagram' for now for min qty check --- 
            const platform = 'Instagram'; // Hardcode for now
            const minQtyKey = "('" + platform + "', '" + type + "')";
            const minRequired = minimumQuantities[minQtyKey] || 1; // Default to 1 if not found
            // --- End Platform Assumption ---

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
        const loopSettings = {
            loops: parseInt(loopCountInput.value) || 1,
            delay: parseFloat(loopDelayInput.value) || 0,
            random_delay: useRandomDelayCheckbox.checked,
            min_delay: parseFloat(minDelayInput.value) || 0,
            max_delay: parseFloat(maxDelayInput.value) || 0
        };

        if (loopSettings.random_delay && loopSettings.min_delay > loopSettings.max_delay) {
            // showTemporaryStatus(minDelayInput.parentElement, "Min delay cannot be greater than Max delay.", "warning");
            alert("Validation Error: Min delay cannot be greater than Max delay."); // Simple alert
            return;
        }

        const profilePayload = {
            name: profileName,
            settings: {
                engagements: engagements,
                loop_settings: loopSettings
            },
             original_name: originalName
        };

        console.log("Saving profile data:", JSON.stringify(profilePayload, null, 2));

        apiCall('/api/profiles', 'POST', profilePayload)
            .then(data => {
                if (data.success) {
                    profilesDataCache = data.profiles; // Update cache
                    populateProfileDropdown(profileSelectDropdown, profilesDataCache); // Repopulate dropdown
                    profileSelectDropdown.value = profileName; // Select the newly saved/edited profile
                    handleProfileSelectionChange(); // Update button states
                    showStatus("Profile saved successfully!", "success", "profile-page-status-area", "profile-page-status-message", 3000); // Example using hypothetical page status IDs
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

    // --- MAIN EXECUTION --- 
    async function initApp() {
        console.log("Starting App Initialization...");
        // 1. Load common data first and store returned profiles
        const loadedProfiles = await initializeAppCommon();

        // 2. Detect Page by checking for unique elements
        const promoTitleElem = document.getElementById('page-title-promo'); // Check for unique H2 ID
        const addProfileBtnElem = document.getElementById('add-profile-btn');
        const saveMonitoringSettingsBtnElem = document.getElementById('save-monitoring-settings-btn');

        const isOnPromoPage = !!promoTitleElem; // Use H2 check
        const isOnProfilePage = !!addProfileBtnElem;
        const isOnMonitorPage = !!saveMonitoringSettingsBtnElem;
        console.log(`Page Check by Element: Promo=${isOnPromoPage}, Profiles=${isOnProfilePage}, Monitor=${isOnMonitorPage}`);

        // 3. Run Page-Specific UI Setup & Attach Listeners
        // Prioritize Promo page check
        if (isOnPromoPage) {
            console.log("Initializing Promo Page (detected by element)...");
            await initializePromoPage(loadedProfiles);
            await initializeSinglePromoPage();
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
            await initializeMonitorPage(); // Needs loaded profiles for dropdown
            // Show status after init completes
            setTimeout(() => { showStatus("Monitor Page Ready", "success", "monitor-page-status-area", "monitor-page-status-message", 3000); }, 10);
        } else {
            console.log(`Running on unknown page or index page without specific elements.`);
            // Attempt to initialize single promo section if it exists anyway (might be index)
            await initializeSinglePromoPage(); 
        }
        
        console.log(`App Initialization finished.`);
    }

    // --- Attach the main initialization to DOMContentLoaded --- 
    document.addEventListener('DOMContentLoaded', () => {
        console.log("DOMContentLoaded event fired. Pushing initApp to end of queue...");
        // Add setTimeout wrapper
        setTimeout(() => {
            console.log("setTimeout(0) callback: Starting App Initialization...");
            initApp().catch(err => {
                console.error("Fatal error during app initialization:", err);
                // Display a critical error message to the user
                showStatus("Critical error initializing application. Please check console.", "danger", "main-status-area", "main-status-message");
            });
        }, 0); // Zero delay pushes execution after current stack clears
    });
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
    let profileModal = null; // <<< Define globally

    // --- Determine page based on elements existing FIRST (MOVED LATER) ---
    /*
    const isOnPromoPage = !!document.getElementById('run-profile-btn');
    const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
    const isOnProfilePage = !!document.getElementById('add-profile-btn'); 
    console.log(`Initial Page Check: Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}`);
    */

    // --- Element Refs (Get elements needed across different initializers/listeners) ---
    const runProfileBtn = document.getElementById('run-profile-btn'); 
    const stopProfileBtn = document.getElementById('stop-profile-btn'); 
    const profileSelectPromo = document.getElementById('profile-select-promo'); 
    const promoLinkInput = document.getElementById('promo-link-input'); 
    const profileSelectProfilePage = document.getElementById('profile-select');
    const addProfileBtn = document.getElementById('add-profile-btn');
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const deleteProfileBtn = document.getElementById('delete-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-modal-btn');
    const profileEditorForm = document.getElementById('profile-editor-form');
    const useRandomDelayCheckbox = document.getElementById('use-random-delay');
    // const profileModal = document.getElementById('profile-modal'); // REMOVE - profileModal is global let
    // const editorTitle = document.getElementById('profile-editor-title'); // Corrected to editor-title later
    const profileNameInput = document.getElementById('profile-name');
    const originalProfileNameInput = document.getElementById('original-profile-name');
    const loopCountInput = document.getElementById('loop-count');
    const loopDelayInput = document.getElementById('loop-delay');
    const minDelayInput = document.getElementById('min-delay');
    const maxDelayInput = document.getElementById('max-delay');
    const engagementSettingsDiv = document.getElementById('engagement-settings');
    const profileSelectDropdown = document.getElementById('profile-select');
    // ... add other commonly used refs if needed ...

    // --- CORE HELPER FUNCTIONS (Define BEFORE first use) ---

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
            const data = await response.json(); // Assume JSON response

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

    // Show status message in designated area
    function showStatus(message, type = 'info', areaId = 'main-status-area', messageId = 'main-status-message', duration = 0) {
        const statusArea = document.getElementById(areaId);
        const statusMessage = document.getElementById(messageId);
        
        if (!statusArea || !statusMessage) {
            console.warn(`showStatus: Could not find status elements (areaId: ${areaId}, messageId: ${messageId}). Message: ${message}`);
            // Fallback to console or a generic alert?
            // alert(`${type.toUpperCase()}: ${message}`); 
            return; // Exit if elements aren't found
        }

        console.log(`Status (${type}) [${areaId}/${messageId}]: ${message}`);
        
        // Use Bootstrap alert classes for styling
        statusArea.className = `alert alert-${type} status-area`; // Reset classes and set new type
        statusMessage.textContent = message;
        statusArea.style.display = 'block'; // Make sure area is visible

        // Clear any existing timeout for THIS specific area/message combo if needed
        // (Using a global or scoped timeout manager might be better if clearing is frequent)

        // Auto-hide after duration if specified
        if (duration > 0) {
            setTimeout(() => {
                statusArea.style.display = 'none'; // Hide the area
            }, duration);
        }
    }
    
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

        // Set new timeout if duration > 0
        if (duration > 0) {
            tempStatusTimeouts[elementId] = setTimeout(() => {
                clearTemporaryStatus(element); // Use helper to clear
             }, duration);
        }
    }
    
    // Clear temporary status for an element
     function clearTemporaryStatus(element) {
        if (!element) return;
        const elementId = element.id;
        if (elementId && tempStatusTimeouts[elementId]) {
            clearTimeout(tempStatusTimeouts[elementId]);
            delete tempStatusTimeouts[elementId];
        }
        element.textContent = '';
        element.className = 'status-display';
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
    function startSinglePromotion() {
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

        // Minimum Quantity Check
        const key = "('" + platform + "', '" + engagement + "')";
        const minQty = minimumQuantities[key];
        if (minQty !== undefined && quantityNum < minQty) {
             showStatus(`Minimum quantity for ${platform} ${engagement} is ${minQty}.`, 'warning', statusAreaId, statusMessageId, 4000);
             return;
        }

        showStatus(`Scheduling single promo: ${quantity} ${engagement} for ${link}...`, 'info', statusAreaId, statusMessageId);
        disableActionButtons(); // Disable both single and profile buttons

        apiCall('/api/start_single_promo', 'POST', { platform, engagement, link, quantity: quantityNum })
            .then(data => {
                if (data.success && data.job_id) {
                    currentProfileJobId = data.job_id; // Reuse the same variable for tracking active job
                    showStatus(data.message || 'Single promo scheduled.', 'info', statusAreaId, statusMessageId);
                    // Start polling if needed (consider if single promos need polling)
                    // startStatusPolling(currentProfileJobId); 
                    // For single, maybe just show success/fail and re-enable?
                    showStatus(`Job ${currentProfileJobId} scheduled successfully.`, 'success', statusAreaId, statusMessageId, 5000);
                     handleFinalJobStatus(currentProfileJobId); // Directly treat as finished for now
                } else {
                    showStatus(data.error || 'Failed to schedule single promo.', 'danger', statusAreaId, statusMessageId);
                    enableActionButtons();
                }
            })
            .catch(error => {
                 // API call helper already shows status
                 enableActionButtons();
             });
    }

    // Start Profile-Based Promotion (Promo Page Specific)
    function startProfilePromotion(profileName, link) { // Pass params directly
        console.log("startProfilePromotion called");
        const statusAreaId = 'promo-status-area';
        const statusMessageId = 'promo-status-message';
        const stopBtn = document.getElementById('stop-profile-btn');

        // Validation already done in the event listener
        showStatus(`Scheduling profile promo: '${profileName}' for ${link}...`, 'info', statusAreaId, statusMessageId);
        disableActionButtons();

        apiCall('/api/start_promo', 'POST', { profile_name: profileName, link: link })
             .then(data => {
                if (data.success && data.job_id) {
                    currentProfileJobId = data.job_id;
                    if (stopBtn) stopBtn.disabled = false; // Enable stop button only when job starts
                    showStatus(data.message || `Profile promo '${profileName}' scheduled. Job ID: ${currentProfileJobId}`, 'info', statusAreaId, statusMessageId);
                    startStatusPolling(currentProfileJobId);
                } else {
                    showStatus(data.error || 'Failed to schedule profile promo.', 'danger', statusAreaId, statusMessageId);
                    enableActionButtons(); // Re-enable run button if scheduling failed
                }
            })
            .catch(error => {
                 // API call helper already shows status
                 enableActionButtons();
            });
    }
    
    // --- Polling Functions ---
    function startStatusPolling(jobId) {
        stopStatusPolling(); // Clear any existing interval
        console.log(`Starting status polling for Job ID: ${jobId}`);
        showStatus(`Job ${jobId} running... Polling status.`, 'info', 'promo-status-area', 'promo-status-message'); // Use specific area
        
        // Ensure stop button is enabled during polling
        const stopBtn = document.getElementById('stop-profile-btn');
        if(stopBtn) stopBtn.disabled = false;
        
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
            const data = await apiCall(`/api/job_status/${jobId}`);
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
        const profilePromoBtn = document.getElementById('run-profile-btn');
        const stopBtn = document.getElementById('stop-profile-btn'); // Also manage stop button
        if(singlePromoBtn) singlePromoBtn.disabled = true;
        if(profilePromoBtn) profilePromoBtn.disabled = true;
        if(stopBtn) stopBtn.disabled = true; // Usually disable stop too initially
    }

    function enableActionButtons() {
        console.log("Enabling action buttons...");
        const singlePromoBtn = document.getElementById('start-single-promo-btn');
        const profilePromoBtn = document.getElementById('run-profile-btn');
        const stopBtn = document.getElementById('stop-profile-btn'); // Stop button should be handled separately
        if(singlePromoBtn) singlePromoBtn.disabled = false;
        if(profilePromoBtn) profilePromoBtn.disabled = false;
        // Stop button is enabled ONLY when a profile job starts and disabled when it ends (in handleFinalJobStatus)
        // if(stopBtn) stopBtn.disabled = true; 
    }

    // --- Initialization Functions (Define BEFORE first use) ---
    async function initializeAppCommon() {
        console.log("Initializing common app components (loading data)... ");
        const results = await Promise.allSettled([
            loadProfiles(),
            loadMinimumQuantities()
        ]);
        console.log("Common init data load results:", results);
        if (results[0].status === 'rejected') {
            console.error("Failed to load profiles during init.");
            // Show a persistent error?
        }
        if (results[1].status === 'rejected') {
            console.error("Failed to load minimum quantities during init.");
            // Show a persistent error?
        }
    }

    async function loadProfiles() {
        console.log("Executing loadProfiles...");
        try {
            profilesDataCache = await apiCall('/api/profiles');
            console.log("loadProfiles fetched data successfully into cache:", profilesDataCache);
            } catch (error) {
            console.error("Error caught in loadProfiles:", error);
            profilesDataCache = {}; // Reset cache on error
            throw error; // Re-throw to be caught by Promise.allSettled
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

    // --- Run Initialization (FIRST IIFE) --- 
    (async () => {
        await initializeAppCommon(); // Loads data into caches
        
        // --- Page Detection (Moved Here) ---
        const isOnPromoPage = !!document.getElementById('run-profile-btn');
        const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
        const isOnProfilePage = !!document.getElementById('add-profile-btn'); 
        console.log(`Page Check (Inside IIFE): Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}`);

        // Page-specific initializations
        if (isOnPromoPage) {
            console.log("Running Promo Page specific init...");
            await initializePromoPage(); // Call the new initializer
            // Moved status message inside initializePromoPage for better timing
            // setTimeout(() => { showStatus("Promo Page Ready", "success", "promo-status-area", "promo-status-message", 3000); }, 10); 
        } else if (isOnMonitorPage) {
            console.log("Running Monitor Page specific init...");
            await initializeMonitorPage(); // Calls its own populate dropdown
            setTimeout(() => { showStatus("Monitor Page Ready", "success", "monitor-page-status-area", "monitor-page-status-message", 3000); }, 10); 
        } else if (isOnProfilePage) { 
             console.log("Running Profile Page specific init...");
             const profileSelectProfilePage = document.getElementById('profile-select'); // Get specific element
             if (profileSelectProfilePage) { // Populate correct dropdown
                 populateProfileDropdown(profileSelectProfilePage);
             } else {
                 console.error("Could not find profile select dropdown on Profile page.");
             }
             initializeProfilePage(); 
             setTimeout(() => { showStatus("Profile Page Ready", "success", "profile-page-status-area", "profile-page-status-message", 3000); }, 10);
        } else {
            // Assuming it might be the index/single promo page if none of the others match specifically
            console.log("Running on Index/Single Promo Page specific init...");
            await initializeSinglePromoPage(); // Initialize elements for single promo section
            // No specific dropdowns to populate here initially, handled by interactions
        }
        
        console.log(`Initialization and listeners setup finished.`);
    })();

    // --- Promo Page Specific Initialization ---
    async function initializePromoPage() {
        console.log("Running initializePromoPage...");

        // Ensure data caches are populated (should be by initializeAppCommon)
        if (!profilesDataCache || Object.keys(profilesDataCache).length === 0) {
            console.warn("Profile data cache empty or not ready for Promo page init.");
            showStatus("Failed to load profile data. Cannot populate dropdown.", 'warning', 'promo-status-area', 'promo-status-message');
            // Maybe attempt to reload or show error?
            // return; // Stop initialization if data is missing?
        }
        // Minimum quantities check (needed for engagement dropdown - though not directly used here)
        if (!minimumQuantities || Object.keys(minimumQuantities).length === 0) {
            console.warn("Minimum quantities not ready for Promo page init.");
            // This might affect engagement dropdown if it were on this page
        }

        // 1. Populate Dropdowns
        // *** Corrected ID from profile-select-promo to profile-select ***
        const profileSelectPromo = document.getElementById('profile-select');
        if (profileSelectPromo) {
            console.log("Found promo profile select dropdown, populating...");
            populateProfileDropdown(profileSelectPromo); // Populate it specifically
        } else {
            console.error("Promo profile select dropdown (profile-select) not found.");
            showStatus("UI Error: Profile selection element missing.", 'danger', 'promo-status-area', 'promo-status-message');
        }
        
        // Note: Engagement dropdown is typically part of the SINGLE promo section, not PROFILE promo.
        // If you intended an engagement dropdown here, add its initialization.
        // updateEngagementOptions(); // Populates based on platform (hardcoded IG for now)
        // updateMinQuantityLabel(); // Updates placeholder based on selection

        // 3. Attach Listeners for Profile Promo section
        const runProfileBtn = document.getElementById('run-profile-btn');
        const stopProfileBtn = document.getElementById('stop-profile-btn');
        const promoLinkInput = document.getElementById('promo-link-input');

        if (runProfileBtn && profileSelectPromo && promoLinkInput) {
            runProfileBtn.addEventListener('click', () => {
                const profileName = profileSelectPromo.value;
                const link = promoLinkInput.value.trim();

                if (!profileName) {
                    showStatus("Please select a promotion profile.", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link) {
                    showStatus("Please enter the link for the profile promotion.", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                    return;
                }
                if (!link.toLowerCase().startsWith('https://')) {
                     showStatus("Link must start with https://", 'warning', 'promo-status-area', 'promo-status-message', 3000);
                     return;
                }
                startProfilePromotion(profileName, link);
            });
        } else {
             console.error("Could not find one or more required elements for profile promo form listeners.");
             showStatus("UI Error: Profile promo form incomplete.", 'danger', 'promo-status-area', 'promo-status-message');
        }
        
        if (stopProfileBtn) {
            stopProfileBtn.addEventListener('click', stopProfilePromotion);
        } else {
             console.error("Could not find stop profile promo button.");
        }
        
         // Show ready status AFTER setup
        setTimeout(() => { showStatus("Promo Page Ready", "success", "promo-status-area", "promo-status-message", 3000); }, 100); 
    }

    // --- Single Promo Page Specific Initialization (if separate or part of index) ---
    async function initializeSinglePromoPage() {
        console.log("Running initializeSinglePromoPage...");
        // Ensure minimums are loaded (should be by initializeAppCommon)
         if (!minimumQuantities || Object.keys(minimumQuantities).length === 0) {
            console.warn("Minimum quantities not ready for Single Promo init.");
            showStatus("Failed to load configuration. Engagement options may be incorrect.", 'warning', 'single-promo-status-area', 'single-promo-status-message');
         }
        
        const platformSelect = document.getElementById('platform-select');
        const engagementSelect = document.getElementById('engagement-select');
        const singlePromoBtn = document.getElementById('start-single-promo-btn');

        if (platformSelect && engagementSelect) {
            // 1. Populate platform dropdown (can be static or dynamic if needed)
            // Assuming platforms are relatively static for now. Add options if empty.
            if(platformSelect.options.length <= 1) { // Keep placeholder if exists
                const platforms = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]; // Or get from config if needed
                platforms.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p;
                    option.textContent = p;
                    platformSelect.appendChild(option);
                });
            }

            // 2. Setup listener to update engagements when platform changes
            platformSelect.addEventListener('change', updateEngagementOptions);
            engagementSelect.addEventListener('change', updateMinQuantityLabel); // Update min label when engagement changes too
            
            // 3. Initial population of engagement based on default platform
            updateEngagementOptions(); // Call once on load
            updateMinQuantityLabel(); // Call once on load
            
        } else {
             console.error("Could not find platform or engagement select dropdowns for single promo.");
             showStatus("UI Error: Single promo dropdowns missing.", 'danger', 'single-promo-status-area', 'single-promo-status-message');
        }
        
        // 4. Attach listener for single promo button
        if (singlePromoBtn) {
            singlePromoBtn.addEventListener('click', startSinglePromotion);
        } else {
            console.error("Could not find single promo button.");
            showStatus("UI Error: Single promo button missing.", 'danger', 'single-promo-status-area', 'single-promo-status-message');
        }
        
        // Show ready status AFTER setup (assuming single promo elements exist)
         const statusArea = document.getElementById('single-promo-status-area');
         if (statusArea) {
            setTimeout(() => { showStatus("Single Promo Section Ready", "success", "single-promo-status-area", "single-promo-status-message", 3000); }, 150); 
         }
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

    // --- NEW Stop Function using API ---
    async function stopProfilePromotion() {
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
                // Polling should eventually reflect 'stopped' status. We don't stop polling here.
                // Button enabling will happen when polling detects final state.
            } else {
                // API call succeeded but backend reported an issue
                 showStatus(data.message || `Failed to register stop request for job ${currentProfileJobId}.`, 'warning', 'promo-status-area', 'promo-status-message', 5000);
                 if(stopButton) stopButton.disabled = false; // Re-enable if request failed
            }
        } catch (error) {
            // Network/fetch error handled by apiCall showing status
             showStatus(`Error sending stop request for ${currentProfileJobId}. Check console.`, 'danger', 'promo-status-area', 'promo-status-message');
             if(stopButton) stopButton.disabled = false; // Re-enable on error
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
    function populateProfileDropdown(dropdownElement) { // Parameter is the ELEMENT
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

        if (!profilesDataCache || Object.keys(profilesDataCache).length === 0) {
            console.warn(`No profiles found in cache for dropdown #${dropdownId}.`);
            // Optionally add an option indicating no profiles are available
             const noProfilesOption = document.createElement('option');
             noProfilesOption.value = "";
             noProfilesOption.textContent = "No profiles available";
             noProfilesOption.disabled = true;
             dropdownElement.appendChild(noProfilesOption);
            return; // Exit if no profiles
        }

        // Sort profile names alphabetically for consistency
        console.log("Profile names found in cache:", Object.keys(profilesDataCache)); // Log keys before sorting
        const sortedProfileNames = Object.keys(profilesDataCache).sort((a, b) => a.localeCompare(b));
        console.log("Sorted profile names:", sortedProfileNames);

        // Populate with profiles from cache
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
        let minQty = 0; // Default to 0 if not found

        if (selectedPlatform && selectedEngagement && minimumQuantities) {
            // Construct the key string format used in the backend: "('Platform', 'Engagement')"
            // Avoid complex escaping in template literals
            const key = "('" + selectedPlatform + "', '" + selectedEngagement + "')";
            minQty = minimumQuantities[key] || 1; // Default to 1 if not found
        }

        const placeholderText = minQty > 0 ? `Minimum: ${minQty}` : "Quantity";
        quantityInput.placeholder = placeholderText;

        // Optionally update the label text itself
        if (quantityLabel) {
            // quantityLabel.textContent = minQty > 0 ? `Quantity (Min: ${minQty}):` : "Quantity:"; // Example
        }
        console.log(`Updated quantity placeholder for ${selectedPlatform}/${selectedEngagement}: "${placeholderText}" (Min: ${minQty})`);
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
                
                // --- Alternative Parsing Logic: String manipulation --- 
                let platform = null;
                let engagement = null;
                if (key.startsWith("('") && key.endsWith("')")) {
                    const content = key.substring(2, key.length - 2); // Remove (' and ')
                    const parts = content.split("', '"); // Split by ', '
                    if (parts.length === 2) {
                        platform = parts[0];
                        engagement = parts[1];
                    }
                }
                // --- End Alternative Parsing Logic ---

                if (platform && engagement) { 
                    if (platform === selectedPlatform) {
                        availableEngagements.add(engagement);
                    }
                } else {
                    console.warn(`Could not parse minimum quantity key: ${key} (String manipulation failed)`);
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
    async function initializeMonitorPage() {
        console.log("Running initializeMonitorPage...");

        // 1. Load settings and targets concurrently
        await Promise.allSettled([
            loadMonitoringSettings(),
            loadMonitoringTargets()
        ]);
        console.log("Initial settings and targets loaded for Monitor Page.");

        // 2. Populate the 'Add Target' profile dropdown
        const monitorAddProfileSelect = document.getElementById('monitor-add-profile-select');
        if (monitorAddProfileSelect) {
            populateProfileDropdown(monitorAddProfileSelect); // Use the common function
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
                pollingIntervalInput.value = data.settings.polling_interval_seconds || '';
                showTemporaryStatus(settingsStatus, "Settings loaded.", "success");
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
        if(!pollingIntervalInput || !settingsStatus) {
           console.error("saveMonitoringSettings: Missing required elements.");
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
        if(monitorListStatus) showTemporaryStatus(monitorListStatus, "Loading targets...", "info", 0);
        try {
            const data = await apiCall('/api/monitoring/targets');
            if (data.success && data.targets) {
                 renderMonitoringTargets(data.targets);
                 if (data.targets.length === 0) {
                     showTemporaryStatus(monitorListStatus, "No targets being monitored.", "info");
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
                     <button class="btn btn-sm btn-danger remove-monitor-btn" data-target-id="${target.id}" data-target-name="${target.target_username}">
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

        // Add listeners to the new buttons
        document.querySelectorAll('.toggle-monitor-btn').forEach(button => {
            button.addEventListener('click', handleToggleMonitoring);
        });
        document.querySelectorAll('.remove-monitor-btn').forEach(button => {
            button.addEventListener('click', handleRemoveMonitoring);
        });
    }

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
            .then(data => {
                if (data.success && data.targets) {
                    renderMonitoringTargets(data.targets); // Re-render the whole list
                    showTemporaryStatus(monitorListStatus, `Successfully ${newState ? 'started' : 'stopped'} monitoring for ${targetName}.`, "success");
                } else {
                     showTemporaryStatus(monitorListStatus, data.error || `Failed to ${action.toLowerCase()} monitoring.`, "danger");
                     // Button will be re-enabled by re-rendering or need manual re-enable if render fails
                     // Let's try re-enabling manually just in case render fails
                     button.disabled = false;
                }
            })
            .catch(error => {
                // API call helper shows main status error
                showTemporaryStatus(monitorListStatus, `Error ${action.toLowerCase()} monitoring.`, "danger");
                button.disabled = false; // Re-enable button on failure
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
    function initializeProfilePage() {
        console.log("Running initializeProfilePage...");

        // 1. Populate Engagement Options Cache from minimumQuantities
        engagementOptionsCache = []; // Clear previous cache if any
        if (minimumQuantities && typeof minimumQuantities === 'object') {
            Object.keys(minimumQuantities).forEach(key => {
                // Corrected parsing based on previous findings
                let platform = null;
                let engagement = null;
                if (key.startsWith("('") && key.endsWith("')")) {
                    const content = key.substring(2, key.length - 2); 
                    const parts = content.split("', '"); 
                    if (parts.length === 2) {
                        platform = parts[0]; 
                        engagement = parts[1];
                    }
                }
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
        if (addProfileBtn) { // Renamed for clarity within this scope
            console.log("Found #add-profile-btn, attaching listener...");
            addProfileBtn.addEventListener('click', () => openProfileModal()); 
        } else { console.error("#add-profile-btn not found for listener."); }
        
        if (editProfileBtnElem) { editProfileBtnElem.addEventListener('click', handleEditProfileClick); }
        if (deleteProfileBtnElem) { deleteProfileBtnElem.addEventListener('click', handleDeleteProfileClick); }

        // Also attach modal button listeners here if the modal is part of this page's core elements
        const saveProfileBtnElem = document.getElementById('save-profile-btn');
        const closeModalBtnElem = document.getElementById('close-modal-btn');
        const cancelModalBtnElem = document.getElementById('cancel-modal-btn');
        const useRandomDelayCheckboxElem = document.getElementById('use-random-delay');

        if (saveProfileBtnElem) { saveProfileBtnElem.addEventListener('click', handleSaveProfile); }
        if (closeModalBtnElem) { closeModalBtnElem.addEventListener('click', closeProfileModal); }
        if (cancelModalBtnElem) { cancelModalBtnElem.addEventListener('click', closeProfileModal); }
        if (useRandomDelayCheckboxElem) { useRandomDelayCheckboxElem.addEventListener('change', toggleRandomDelayInputs); }
        
        console.log("Profile Page Initialized and Listeners Attached."); 
    }


    // --- NEW Profile Page Specific Functions --- (Now includes initializeProfilePage)

    // let engagementOptionsCache = []; // Moved inside initializeProfilePage
    // const profileSelectDropdown = document.getElementById('profile-select'); // Already defined above

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
        console.log("[+] openProfileModal START. Data:", profileData); // Log start
        // const profileModal = document.getElementById('profile-editor-modal'); // Use global now
        if (!profileModal) { // Check global variable
            console.error("Cannot open modal: Global profileModal variable is null or undefined!");
            return;
        } else {
            // Restore this log
            console.log("Found #profile-editor-modal element via global ref.");
        }
        
        // Find other elements needed within the modal and log success/failure
        const profileEditorForm = document.getElementById('profile-editor-form');
        console.log(`> Found #profile-editor-form: ${!!profileEditorForm}`); // Granular log
        const originalProfileNameInput = document.getElementById('original-profile-name');
        console.log(`> Found #original-profile-name: ${!!originalProfileNameInput}`); // Granular log
        const engagementSettingsDiv = document.getElementById('engagement-settings');
        console.log(`> Found #engagement-settings: ${!!engagementSettingsDiv}`); // Granular log
        const editorTitle = document.getElementById('editor-title'); 
        console.log(`> Found #editor-title: ${!!editorTitle}`); // Granular log
        const profileNameInput = document.getElementById('profile-name');
        console.log(`> Found #profile-name: ${!!profileNameInput}`); // Granular log
        const loopCountInput = document.getElementById('loop-count');
        console.log(`> Found #loop-count: ${!!loopCountInput}`); // Granular log
        const loopDelayInput = document.getElementById('loop-delay');
        console.log(`> Found #loop-delay: ${!!loopDelayInput}`); // Granular log
        const useRandomDelayCheckbox = document.getElementById('use-random-delay');
        console.log(`> Found #use-random-delay: ${!!useRandomDelayCheckbox}`); // Granular log
        const minDelayInput = document.getElementById('min-delay');
        console.log(`> Found #min-delay: ${!!minDelayInput}`); // Granular log
        const maxDelayInput = document.getElementById('max-delay');
        console.log(`> Found #max-delay: ${!!maxDelayInput}`); // Granular log

        // Check if ALL essential elements were found
        console.log("Checking if all modal elements were found...");
        if (!profileEditorForm || !originalProfileNameInput || !engagementSettingsDiv || !editorTitle || !profileNameInput || !loopCountInput || !loopDelayInput || !useRandomDelayCheckbox || !minDelayInput || !maxDelayInput) {
            console.error("Cannot open modal: One or more required child elements are missing inside #profile-editor-modal. Halting modal open.");
            return;
        }
        console.log("All required child elements found.");

        console.log("Resetting form fields...");
        profileEditorForm.reset();
        originalProfileNameInput.value = '';
        engagementSettingsDiv.innerHTML = ''; // Clear previous engagement rows
        // toggleRandomDelayInputs(); // Reset random delay state - Call later
        // minDelayInput.disabled = !useRandomDelayCheckbox.checked; // Set later
        // maxDelayInput.disabled = !useRandomDelayCheckbox.checked; // Set later

        console.log("Setting up modal for Add or Edit mode...");
        if (profileData) {
            // Edit mode
            console.log("Edit mode detected.");
            editorTitle.textContent = "Edit Profile";
            originalProfileNameInput.value = profileData.name;
            profileNameInput.value = profileData.name;
            loopCountInput.value = profileData.loop_settings?.loops || 1;
            loopDelayInput.value = profileData.loop_settings?.delay || 0;
            useRandomDelayCheckbox.checked = profileData.loop_settings?.random_delay || false;
            minDelayInput.value = profileData.loop_settings?.min_delay || 60;
            maxDelayInput.value = profileData.loop_settings?.max_delay || 300;
            
            console.log("Calling populateEngagementRows (Edit mode)...");
            populateEngagementRows(profileData.engagements);
            console.log("Finished populateEngagementRows (Edit mode).");
        } else {
            // Add mode
            console.log("Add mode detected.");
            editorTitle.textContent = "Add New Profile";
            console.log("Calling populateEngagementRows (Add mode)...");
            // *** Restore call ***
            populateEngagementRows(); // Call with no args for default row(s)
            console.log("Finished populateEngagementRows (Add mode)."); // Restore log
        }

        console.log("Calling toggleRandomDelayInputs...");
        toggleRandomDelayInputs(); // Ensure correct state after population
        console.log("Adding .is-visible class...");
        profileModal.classList.add('is-visible');
        console.log("Added .is-visible class.");
        
        // Log computed styles for debugging visibility
        const computedStyle = window.getComputedStyle(profileModal);
        console.log(`Computed Visibility: ${computedStyle.visibility}`);
        console.log(`Computed Opacity: ${computedStyle.opacity}`);
        console.log(`Computed Z-Index: ${computedStyle.zIndex}`);
        console.log(`Computed Display: ${computedStyle.display}`);

        console.log("[-] openProfileModal END."); // Log end
    }

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

    function addEngagementRow(engagementTypeName, engagementData = null, minRequired = 1) { // Add minRequired param
        console.log(`Adding row for type: ${engagementTypeName}, MinRequired: ${minRequired}, Data:`, engagementData);
        const row = document.createElement('div');
        row.className = 'engagement-row';
        row.setAttribute('data-engagement-type', engagementTypeName);

        const typeLabel = document.createElement('span'); 
        typeLabel.className = 'engagement-type-label'; 
        typeLabel.textContent = engagementTypeName;

        const fixedQtyInput = document.createElement('input');
        fixedQtyInput.type = 'number';
        fixedQtyInput.className = 'engagement-fixed-qty form-control'; 
        fixedQtyInput.min = minRequired; // Set min attribute
        fixedQtyInput.placeholder = `Min: ${minRequired}`;
        fixedQtyInput.value = engagementData?.fixed_quantity || '';
        fixedQtyInput.disabled = engagementData?.use_random_quantity || false;

        const randomCheckbox = document.createElement('input');
        randomCheckbox.type = 'checkbox';
        randomCheckbox.className = 'engagement-random-cb form-check-input'; 
        randomCheckbox.checked = engagementData?.use_random_quantity || false;
        
        const minQtyInput = document.createElement('input');
        minQtyInput.type = 'number';
        minQtyInput.className = 'engagement-min-qty form-control'; 
        minQtyInput.min = minRequired; // Set min attribute
        minQtyInput.placeholder = `Min: ${minRequired}`;
        minQtyInput.value = engagementData?.min_quantity || '';
        minQtyInput.disabled = !randomCheckbox.checked;

        const maxQtyInput = document.createElement('input');
        maxQtyInput.type = 'number';
        maxQtyInput.className = 'engagement-max-qty form-control'; 
        maxQtyInput.min = minRequired; // Max also can't be less than overall min
        maxQtyInput.placeholder = 'Max';
        maxQtyInput.value = engagementData?.max_quantity || '';
        maxQtyInput.disabled = !randomCheckbox.checked;

        const loopInput = document.createElement('input');
        loopInput.type = 'number';
        loopInput.className = 'engagement-loops form-control'; 
        loopInput.min = '1'; // Loops min is always 1
        loopInput.placeholder = 'Loops';
        loopInput.value = engagementData?.loops || 1; 

        // Event listener for the random checkbox remains the same
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
            }
        });

        // Append elements in order
        row.appendChild(typeLabel);
        row.appendChild(fixedQtyInput);
        row.appendChild(randomCheckbox);
        row.appendChild(minQtyInput);
        row.appendChild(maxQtyInput);
        row.appendChild(loopInput);
        
        engagementSettingsDiv.appendChild(row);
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
        console.log("Attempting to save profile...");
        const profileName = profileNameInput.value.trim();
        const originalName = originalProfileNameInput.value;
        if (!profileName) {
            showTemporaryStatus(profileNameInput.parentElement, "Profile Name cannot be empty.", "warning");
            return;
        }

        const engagements = [];
        const engagementRows = engagementSettingsDiv.querySelectorAll('.engagement-row');
        let firstErrorElement = null; 

        engagementRows.forEach(row => {
            const type = row.getAttribute('data-engagement-type'); 
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
                use_random_quantity: isRandom,
                fixed_quantity: null,
                min_quantity: null,
                max_quantity: null,
                loops: parseInt(loopInput.value) || 1
            };

            // --- Platform is assumed 'Instagram' for now for min qty check --- 
            const platform = 'Instagram'; // Hardcode for now
            const minQtyKey = "('" + platform + "', '" + type + "')";
            const minRequired = minimumQuantities[minQtyKey] || 1; // Default to 1 if not found
            // --- End Platform Assumption ---

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
        const loopSettings = {
            loops: parseInt(loopCountInput.value) || 1,
            delay: parseFloat(loopDelayInput.value) || 0,
            random_delay: useRandomDelayCheckbox.checked,
            min_delay: parseFloat(minDelayInput.value) || 0,
            max_delay: parseFloat(maxDelayInput.value) || 0
        };

        if (loopSettings.random_delay && loopSettings.min_delay > loopSettings.max_delay) {
            // showTemporaryStatus(minDelayInput.parentElement, "Min delay cannot be greater than Max delay.", "warning");
            alert("Validation Error: Min delay cannot be greater than Max delay."); // Simple alert
            return;
        }

        const profilePayload = {
            name: profileName,
            settings: {
                engagements: engagements,
                loop_settings: loopSettings
            },
             original_name: originalName
        };

        console.log("Saving profile data:", JSON.stringify(profilePayload, null, 2));

        apiCall('/api/profiles', 'POST', profilePayload)
            .then(data => {
                if (data.success) {
                    profilesDataCache = data.profiles; // Update cache
                    populateProfileDropdown(profileSelectDropdown, profilesDataCache); // Repopulate dropdown
                    profileSelectDropdown.value = profileName; // Select the newly saved/edited profile
                    handleProfileSelectionChange(); // Update button states
                    showStatus("Profile saved successfully!", "success", "profile-page-status-area", "profile-page-status-message", 3000); // Example using hypothetical page status IDs
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

    // --- MAIN EXECUTION --- 
    async function initApp() {
        console.log("Starting App Initialization...");
        // 1. Load common data first
        await initializeAppCommon();

        // 2. Detect Page
        // *** Corrected ID for Promo page detection ***
        const runProfileBtnElem = document.getElementById('start-profile-promo-btn'); 
        const saveMonitoringSettingsBtnElem = document.getElementById('save-monitoring-settings-btn');
        const addProfileBtnElem = document.getElementById('add-profile-btn');

        const isOnPromoPage = !!runProfileBtnElem;
        const isOnMonitorPage = !!saveMonitoringSettingsBtnElem;
        const isOnProfilePage = !!addProfileBtnElem;
        console.log(`Page Check: Promo=${isOnPromoPage}, Monitor=${isOnMonitorPage}, Profile=${isOnProfilePage}`);

        // 3. Run Page-Specific UI Setup & Attach Listeners
        if (isOnPromoPage) {
            await initializePromoPage(); // Populates its own #profile-select dropdown
            await initializeSinglePromoPage(); 

            // --- Attach Promo Page Listeners ---
            console.log("Attaching Promo Page Listeners...");
            const profileSelectPromoElem = document.getElementById('profile-select-promo');
            const promoLinkInputElem = document.getElementById('promo-link-input');
            const stopProfileBtnElem = document.getElementById('stop-profile-btn');
            const platformSelectElem = document.getElementById('platform-select');
            const engagementSelectElem = document.getElementById('engagement-select');
            const singlePromoBtnElem = document.getElementById('start-single-promo-btn');

            if (runProfileBtnElem && profileSelectPromoElem && promoLinkInputElem) {
                runProfileBtnElem.addEventListener('click', () => {
                    const profileName = profileSelectPromoElem.value;
                    const link = promoLinkInputElem.value.trim();
                    // Inline validation or call separate validation function
                    if (!profileName) { /* ... show status ... */ return; }
                    if (!link) { /* ... show status ... */ return; }
                    if (!link.toLowerCase().startsWith('https://')) { /* ... show status ... */ return; }
                    startProfilePromotion(profileName, link);
                });
            } else {
                console.error("Missing elements for profile promo listeners.");
            }
            if (stopProfileBtnElem) {
                stopProfileBtnElem.addEventListener('click', stopProfilePromotion);
            } else {
                console.error("Stop profile promo button not found.");
            }
            
            // Single Promo Listeners
            if (platformSelectElem && engagementSelectElem) {
                platformSelectElem.addEventListener('change', updateEngagementOptions);
                engagementSelectElem.addEventListener('change', updateMinQuantityLabel);
            } else {
                 console.error("Missing elements for single promo dropdown listeners.");
            }
            if (singlePromoBtnElem) {
                 singlePromoBtnElem.addEventListener('click', startSinglePromotion);
            } else {
                console.error("Missing single promo start button.");
            }

        } else if (isOnMonitorPage) {
            await initializeMonitorPage(); // Populates its dropdown & attaches listeners
            // Additional listeners if any?
        } else if (isOnProfilePage) {
             // *** Populate dropdown FIRST ***
             const profileSelectProfilePage = document.getElementById('profile-select'); 
             if (profileSelectProfilePage) { 
                 populateProfileDropdown(profileSelectProfilePage);
             } else {
                 console.error("Could not find profile select dropdown on Profile page (#profile-select).");
             }
             // *** Initialize page (which now includes listener attachment) ***
             await initializeProfilePage(); 
             
             // --- Listener Attachment Block REMOVED From Here --- 
             // console.log("Attaching Profile Page Listeners...");
             // ... (removed listener code) ...
             
             // Show status after init completes
             setTimeout(() => { showStatus("Profile Page Ready", "success", "profile-page-status-area", "profile-page-status-message", 3000); }, 10);

        } else {
            console.log("Running on an unknown page or index page.");
            await initializeSinglePromoPage(); // Assume index has single promo
        }
        
        console.log(`App Initialization finished.`);
    }

    // --- Attach the main initialization to DOMContentLoaded --- 
    document.addEventListener('DOMContentLoaded', () => {
        console.log("DOMContentLoaded event fired. Starting App Initialization...");
        initApp().catch(err => {
            console.error("Fatal error during app initialization:", err);
            // Display a critical error message to the user
            showStatus("Critical error initializing application. Please check console.", "danger", "main-status-area", "main-status-message");
        });
    });

}); // End DOMContentLoaded