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

        // --- REMOVED Auto-hide logic ---
        /*
        // Clear any existing timeout for THIS specific area/message combo if needed
        // (Using a global or scoped timeout manager might be better if clearing is frequent)

        // Auto-hide after duration if specified
        if (duration > 0) {
            setTimeout(() => {
                statusArea.style.display = 'none'; // Hide the area
            }, duration);
        }
        */
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
        const statusAreaId = 'status-text'; // ID of the status div
        const statusMessageId = 'status-text'; // Using the same ID for the message part
        try {
            const loadedProfiles = await initializeAppCommon(); // Loads data into caches, GETS PROFILES
            
            // --- Page Detection (Moved Here) ---
            const isOnPromoPage = !!document.getElementById('start-profile-promo-btn'); // Note: This ID seems incorrect based on HTML (should be start-profile-promo-btn?)
            const isOnMonitorPage = !!document.getElementById('save-monitoring-settings-btn');
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
            } else if (isOnHistoryPage) {
                console.log("Running History Page specific init...");
                // initializeHistoryPage(); // Moved to global scope
            } else {
                // Assuming it might be the index/single promo page if none of the others match specifically
                console.log("Running on Index/Single Promo Page specific init (fallback)...");
                await initializeSinglePromoPage(); // Initialize elements for single promo section
                // No specific dropdowns to populate here initially, handled globally now
            }
            
            console.log(`Initialization and listeners setup finished.`);
            // Update status to Ready on success
            showStatus("Ready", "success", statusAreaId, statusMessageId); // Show Ready permanently

        } catch (initError) {
             console.error("Critical error during app initialization:", initError);
             // Update status to Error on failure
             showStatus("Initialization Error", "danger", statusAreaId, statusMessageId); // Keep error visible
         }
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
        const runProfileBtn = document.getElementById('start-profile-promo-btn');
        const stopProfileBtn = document.getElementById('stop-profile-btn');
        const promoLinkInput = document.getElementById('profile-link-input');

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
            console.log(`[InitSinglePromo] Before adding platforms, platformSelect.options.length = ${platformSelect.options.length}`); // Log length before check
            if(platformSelect.options.length <= 1) { // Keep placeholder if exists
                console.log("[InitSinglePromo] Condition (options.length <= 1) met. Adding platforms..."); // Log entry into block
                platformSelect.innerHTML = ''; // Clear all options

                const platforms = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]; // Or get from config if needed
                platforms.forEach(p => {
                    console.log(`[InitSinglePromo] Attempting to add platform: ${p}`); // Log each platform
                    const option = document.createElement('option');
                    option.value = p;
                    option.textContent = p;
                    platformSelect.appendChild(option);
                    console.log(`[InitSinglePromo] Successfully appended option for: ${p}`); // Log success
                });
            } else {
                 console.log(`[InitSinglePromo] Condition (options.length <= 1) NOT met. Skipping platform add.`); // Log if skipped
            }

            // 2. Setup listener to update engagements when platform changes
            platformSelect.addEventListener('change', updateEngagementOptions);
            engagementSelect.addEventListener('change', updateMinQuantityLabel); // Update min label when engagement changes too
            
            console.log("[InitSinglePromo] Calling initial updateEngagementOptions...");
            // Initial population of engagement based on default platform
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

        if (!engagementType) {
            alert("Please select an engagement type to add.");
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

        const minQtyKey = "('" + platform + "', '" + engagementType + "')";
        const minRequired = minimumQuantities[minQtyKey] || 1;

        console.log(`Adding row for: ${engagementType} (Platform: ${platform}, MinQty: ${minRequired})`);
        addEngagementRow(engagementType, null, minRequired); 

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

        // --- Populate Platform Dropdown --- 
        console.log("Populating platform dropdown...");
        const platforms = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]; // Or get from config if needed
        // Add a placeholder/default option
        const platformPlaceholder = document.createElement('option');
        platformPlaceholder.value = "";
        platformPlaceholder.textContent = "-- Select Platform --";
        platformPlaceholder.disabled = true;
        platformPlaceholder.selected = true;
        platformSelect.appendChild(platformPlaceholder);
        // Add platform options
        platforms.forEach(p => {
            const option = document.createElement('option');
            option.value = p;
            option.textContent = p;
            platformSelect.appendChild(option);
        });

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
                    // We might need to pass the PLATFORM associated with these engagements if it matters
                    // For now, assume Instagram implicitly or it's stored in savedEng?
                    if (typeof addEngagementRow === 'function') {
                        const platform = 'Instagram'; // <<< ASSUMPTION: Hardcoding for now
                        const minQtyKey = "('" + platform + "', '" + savedEng.type + "')";
                        const minRequired = minimumQuantities[minQtyKey] || 1; 
                        addEngagementRow(savedEng.type, savedEng, minRequired); // Pass saved data
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
        
        console.log("[-] openProfileModal END."); 
    }

    // --- NEW Listener function for Platform change INSIDE modal ---
    function handleModalPlatformChange() {
        const platformSelect = document.getElementById('modal-platform-select');
        const engagementSelect = document.getElementById('modal-engagement-select');
        const addEngagementBtn = document.getElementById('add-engagement-row-btn');

        if (!platformSelect || !engagementSelect || !addEngagementBtn) {
            console.error("Modal platform/engagement select/button not found in change handler.");
            return;
        }

        const selectedPlatform = platformSelect.value;
        console.log(`Modal Platform selected: ${selectedPlatform}`);
        
        // Clear current engagement options
        engagementSelect.innerHTML = ''; 

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

        // Find available engagements for this platform from minimumQuantities cache
        const availableEngagements = new Set();
        if (minimumQuantities && typeof minimumQuantities === 'object') {
             Object.keys(minimumQuantities).forEach(key => {
                 let platform = null;
                 let engagement = null;
                 // Reuse parsing logic
                 if (key.startsWith("('") && key.endsWith("')")) {
                     const content = key.substring(2, key.length - 2); 
                     const parts = content.split("', '"); 
                     if (parts.length === 2) {
                         platform = parts[0]; 
                         engagement = parts[1];
                     }
                 }
                 if (platform === selectedPlatform && engagement) {
                     availableEngagements.add(engagement);
                 }
             });
        } else {
            console.warn("Minimum quantities cache not ready for modal engagement population.");
            // Disable Add button if data is missing?
            addEngagementBtn.disabled = true;
        }

        // Populate dropdown
        if (availableEngagements.size > 0) {
            const sortedEngagements = Array.from(availableEngagements).sort();
            sortedEngagements.forEach(engType => {
                const option = document.createElement('option');
                option.value = engType;
                option.textContent = engType;
                engagementSelect.appendChild(option);
            });
            console.log(`Populated modal engagement dropdown for ${selectedPlatform} with:`, sortedEngagements);
        } else {
            console.warn(`No engagements found for platform ${selectedPlatform} in cache.`);
            const noOptions = document.createElement('option');
            noOptions.textContent = "No options found";
            engagementSelect.appendChild(noOptions);
            engagementSelect.disabled = true; // Disable if no options
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

    function addEngagementRow(engagementTypeName, engagementData = null, minRequired = 1) {
        console.log(`Adding row for type: ${engagementTypeName}, MinRequired: ${minRequired}, Data:`, engagementData);
        
        const row = document.createElement('div');
        row.className = 'row g-2 mb-1 engagement-row'; 
        row.setAttribute('data-engagement-type', engagementTypeName);
        // Remove stored min/max data attributes if they exist from previous attempt
        delete row.dataset.minQty;
        delete row.dataset.maxQty;

        // 1. Engagement Type Column
        const typeCol = document.createElement('div');
        typeCol.className = 'col-2 d-flex align-items-center text-light'; // Changed to col-2
        typeCol.style.whiteSpace = 'nowrap'; 
        typeCol.textContent = engagementTypeName;
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
            showTemporaryStatus(profileNameInput.parentElement, "Profile Name cannot be empty.", "warning");
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
        console.log(`Page Check by Element: Promo=${isOnPromoPage}, Profiles=${isOnProfilePage}, Monitor=${isOnMonitorPage}, History=${isOnHistoryPage}`);

        // 3. Run Page-Specific UI Setup & Attach Listeners
        // Prioritize Promo page check
        if (isOnPromoPage) {
            console.log("Initializing Promo Page (detected by element)...");
            // Pass loaded profiles to avoid race condition
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
        } else {
            console.log(`Running on unknown page or index page without specific elements.`);
            // Attempt to initialize single promo section if it exists anyway (might be index)
            await initializeSinglePromoPage(); 
        }
        
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

    // --- PAGE SPECIFIC INITIALIZERS (Define BEFORE use in initApp) ---

    // --- History Page Specific Initialization Function Definition ---
    // Moved here from IIFE to avoid ReferenceError on showStatus
    function initializeHistoryPage() {
        console.log("Initializing History Page...");
        // TODO: Add any specific listeners or UI setup for the history table if needed.
        // For now, it's mostly static HTML generated by Flask.
        // showStatus("History Page Ready", "success", "status-text", "status-text", 3000);
    }
    // NOTE: Removed the duplicate initializeHistoryPage function that was below the DOMContentLoaded listener.

    // --- Attach the main initialization to DOMContentLoaded ---
    // REPLACED THE ORIGINAL DUPLICATE LISTENER with the one at line 2228
}); // <<< This now correctly closes the main DOMContentLoaded listener from the start of the file.