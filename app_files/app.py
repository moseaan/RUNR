import sys
import os
# Add the browser_use library path to sys.path - RE-ADDING
if 'browser_use' not in sys.modules:
    browser_use_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'browser-use-main', 'browser-use-main'))
    if browser_use_lib_path not in sys.path:
        sys.path.insert(0, browser_use_lib_path)
        print(f"Added to sys.path: {browser_use_lib_path}")

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_apscheduler import APScheduler # Import APScheduler
import profile_manager
import automation_runner # Import the new runner module
import time
import config # Import config to access MINIMUM_QUANTITIES
import traceback # Import traceback
import history_manager # Import history manager
import datetime # Import datetime
from markupsafe import Markup # For rendering HTML safely if needed
import os # Import os for development server check
import instagram_monitor # Import the new monitor module
from apscheduler.jobstores.base import JobLookupError # For removing jobs
import json
import uuid
from ui_utils import format_datetime # Import the filter
import logging
from waitress import serve # Added for Render deployment
# from apscheduler.executors.asyncio import AsyncIOExecutor # REMOVE Import

# --- App and Scheduler Configuration ---
class Config:
    SCHEDULER_API_ENABLED = True # Optional: enables a default scheduler UI at /scheduler
    # Optional: Configure job defaults if needed
    # SCHEDULER_JOB_DEFAULTS = {
    #     'coalesce': False,
    #     'max_instances': 3
    # }

app = Flask(__name__)
app.config.from_object(Config()) # Apply configuration

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# --- Job Status Tracking --- (Used for manual/profile promotions)
job_statuses = {} # In-memory dictionary to store job status: {job_id: {'status': 'pending/running/success/failed', 'message': '...'}}

# --- CONSTANTS --- (Keep location)
# MONTIORING_JOB_ID = "instagram_monitoring_job" # Old ID, removed
GLOBAL_MONITORING_CHECK_JOB_ID = "global_monitoring_check_job"
SCHEDULE_INTERVAL_SECONDS = 60 # Default check interval
DEFAULT_POST_AGE_LIMIT_HOURS = 1 # Only promote posts newer than this

# --- Background Task Logic --- (No longer needs to be async)
def run_global_monitoring_check():
    """Scheduled function that checks ALL active targets based on polling interval."""
    print(f"\n--- Running Global Monitoring Check ({datetime.datetime.now()}) --- Sync Function")
    config_data = instagram_monitor.load_monitoring_config()
    all_targets = config_data.get('targets', [])
    polling_interval = datetime.timedelta(seconds=config_data.get('polling_interval_seconds', instagram_monitor.DEFAULT_POLLING_INTERVAL))
    profiles = None # Lazy load profiles if needed
    config_needs_saving = False # Track if any target timestamps/URLs are updated
    
    active_targets = [t for t in all_targets if t.get('is_running')]
    if not active_targets:
        print("[Global Check] No active targets found. Skipping run.")
        return

    print(f"[Global Check] Found {len(active_targets)} active targets to evaluate.")

    now_dt = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware now

    for target in active_targets:
        target_id = target.get("id")
        target_username = target.get("target_username")
        promo_profile_name = target.get("promotion_profile_name")
        last_pushed_url = target.get("last_pushed_post_url")
        last_checked_iso = target.get("last_checked_timestamp")

        if not target_username or not promo_profile_name or not target_id:
            print(f"[Global Check] Skipping target with incomplete data: {target}")
            continue

        # Determine if it's time to check this target
        should_check = False
        if last_checked_iso is None:
            should_check = True # Never checked before
            print(f"[Global Check] Target '{target_username}' ({target_id}): Never checked before.")
        else:
            try:
                last_checked_dt = datetime.datetime.fromisoformat(last_checked_iso.replace('Z', '+00:00'))
                if now_dt - last_checked_dt >= polling_interval:
                    should_check = True
                    print(f"[Global Check] Target '{target_username}' ({target_id}): Interval passed ({now_dt - last_checked_dt} >= {polling_interval}).")
                # else:
                #    print(f"[Global Check] Target '{target_username}' ({target_id}): Not time yet (Last checked: {last_checked_dt}).")
            except (ValueError, TypeError) as e:
                print(f"[Global Check] Target '{target_username}' ({target_id}): Error parsing last checked timestamp '{last_checked_iso}': {e}. Will check now.")
                should_check = True

        if should_check:
            print(f"[Global Check] ===> Checking user: {target_username}, Promo Profile: {promo_profile_name} <===")
            # Ensure we have the latest profile settings before attempting to scrape
            if profiles is None: # Reload profiles if they haven't been loaded in this run
                 profiles = profile_manager.load_profiles()
                 
            if promo_profile_name not in profiles:
                 print(f"[Global Check] *** Error: Promotion profile '{promo_profile_name}' for target '{target_username}' not found! Cannot scrape or promo. Skipping. ***")
                 continue # Skip this target if its profile is missing

            promo_settings = profiles[promo_profile_name] # Get current settings

            # Attempt to get latest post info (use synchronous call now)
            latest_post_url, post_dt_utc = instagram_monitor.get_latest_post_info(target_username)
            
            # Update last checked time immediately after scraping attempt
            target['last_checked_timestamp'] = now_dt.isoformat()
            config_needs_saving = True

            if not latest_post_url:
                print(f"[Global Check] Failed to get latest post info for '{target_username}'. Skipping promotion check.")
                continue # Error during scraping for this target

            if latest_post_url == last_pushed_url:
                print(f"[Global Check] Latest post URL for '{target_username}' is the same as the last pushed URL. No action needed.")
                continue # Already processed this post

            # --- New Post Detected --- 
            print(f"[Global Check] New post detected for '{target_username}': {latest_post_url}")

            if not post_dt_utc:
                print(f"[Global Check] Could not determine post timestamp for {latest_post_url}. Cannot check age. Will not push.")
                # Mark this URL as seen anyway to prevent re-checking its timestamp
                target['last_pushed_post_url'] = latest_post_url
                # config_needs_saving is already True
            else:
                # Ensure datetime has timezone info (should be UTC from scraping)
                if post_dt_utc.tzinfo is None:
                     post_dt_utc = post_dt_utc.replace(tzinfo=datetime.timezone.utc)
                
                time_diff = now_dt - post_dt_utc
                print(f"[Global Check] Post time: {post_dt_utc}, Current time: {now_dt}, Difference: {time_diff}")

                # Check if post is within the allowed age limit
                if time_diff < datetime.timedelta(hours=DEFAULT_POST_AGE_LIMIT_HOURS):
                    print(f"[Global Check] Post for '{target_username}' is within the last {DEFAULT_POST_AGE_LIMIT_HOURS} hour(s). Triggering promotion!")
            
                    # Schedule the actual promo job
                    try:
                        # Use a unique job ID including target ID and timestamp
                        promo_job_id = f'monitor_promo_{target_id}_{time.time()}' 
                        # Use the existing job_statuses dict for tracking these triggered promos
                        job_statuses[promo_job_id] = {'status': 'pending', 'message': f'Monitor trigger for {target_username} ({promo_profile_name})'} 
                        scheduler.add_job(
                            id=promo_job_id,
                            func=automation_runner.run_automation_profile,
                            trigger='date', # Run immediately
                            args=[promo_profile_name, promo_settings, latest_post_url, promo_job_id, update_job_status, save_history_entry_callback, requested_stops],
                            misfire_grace_time=None
                        )
                        print(f"[Global Check] Scheduled promotion job {promo_job_id} for post {latest_post_url}")
                        # Successfully scheduled, update last pushed URL in the target config
                        target['last_pushed_post_url'] = latest_post_url
                        # config_needs_saving is already True
                    except Exception as e:
                        print(f"[Global Check] *** Error scheduling promotion job for {latest_post_url} (Target: '{target_username}'): {e} ***")
                        traceback.print_exc()
                        # Don't update last_pushed_url if scheduling failed, maybe retry next time?
                else:
                    print(f"[Global Check] Post for '{target_username}' is older than {DEFAULT_POST_AGE_LIMIT_HOURS} hour(s). Skipping promotion.")
                    # Update last pushed URL so we don't re-check this old post
                    target['last_pushed_post_url'] = latest_post_url
                    # config_needs_saving is already True
        # End of if should_check
    # End of loop through targets

    # Save config changes if any timestamps or pushed URLs were updated
    if config_needs_saving:
        print(f"[Global Check] Saving updated monitoring config...")
        instagram_monitor.save_monitoring_config(config_data)

    print(f"--- Global Monitoring Check Finished --- Sync Function")

# --- Function to initialize the global monitoring scheduler job ---
def initialize_monitoring_job():
    print("[Initialize Job] Attempting to initialize global monitoring scheduler job...")
    try:
        config_data = instagram_monitor.load_monitoring_config()
        current_interval = config_data.get('polling_interval_seconds', SCHEDULE_INTERVAL_SECONDS)
        print(f"[Initialize Job] Using interval from config: {current_interval} seconds.")
        try:
            scheduler.remove_job(GLOBAL_MONITORING_CHECK_JOB_ID)
            print(f"[Initialize Job] Removed existing global monitoring job '{GLOBAL_MONITORING_CHECK_JOB_ID}'.")
        except JobLookupError:
            print(f"[Initialize Job] No existing job '{GLOBAL_MONITORING_CHECK_JOB_ID}' found to remove.")
            pass 

        # Schedule the SYNC function directly now
        scheduler.add_job(
            id=GLOBAL_MONITORING_CHECK_JOB_ID,
            func=run_global_monitoring_check, # Schedule the sync function directly
            trigger='interval',
            seconds=current_interval,
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=10)
        )
        print(f"[Initialize Job] SUCCESS: Scheduled '{GLOBAL_MONITORING_CHECK_JOB_ID}' to run every {current_interval} seconds.")
    except Exception as e:
        print(f"[Initialize Job] *** FATAL ERROR: Failed to schedule global monitoring job: {e} ***") 
        traceback.print_exc()

# Initialize the monitoring job right after scheduler starts
with app.app_context(): 
    initialize_monitoring_job()

# Register the custom filter
app.jinja_env.filters['format_datetime'] = format_datetime

# --- Custom Jinja Filter ---
@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%Y-%m-%d %H:%M:%S'):
    """Formats an ISO datetime string into a more readable format."""
    if not value:
        return "N/A"
    try:
        # Parse ISO format string (potentially with microseconds)
        # Handle potential strings or already parsed datetimes if loaded differently
        if isinstance(value, str):
            dt_object = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, datetime.datetime):
            dt_object = value
        else:
            return value # Cannot format
        # Format, potentially converting timezone if needed (assuming stored as UTC)
        # For simplicity, format directly for now
        return dt_object.strftime(format)
    except (ValueError, TypeError) as e:
        print(f"Error formatting datetime '{value}': {e}")
        # Handle cases where value is not a valid ISO string or None
        return value # Return original value if parsing fails

# --- Global state for job status and stop requests --- 
job_status_updates = {} # Stores the latest status for each job ID
requested_stops = set() # Stores job_ids requested to stop

def update_job_status(job_id, status, message=None):
    """Callback function to update the status of a manual/profile promo job."""
    if job_id in job_statuses:
        job_statuses[job_id]['status'] = status
        job_statuses[job_id]['message'] = message
        print(f"Job Status Update: {job_id} -> {status} {f'({message})' if message else ''}")
    else:
        print(f"Warning: Job ID {job_id} not found in status tracker for update ({status}).")

def save_history_entry_callback(entry):
    """Callback passed to runner functions to save history."""
    try:
        # Attempt to save the entry using the history manager
        success = history_manager.save_history_entry(entry)
        if not success:
            print(f"[Callback Error] Failed to save history entry for Job ID: {entry.get('job_id', 'N/A')}")
    except Exception as e:
        # Log any unexpected errors during saving
        print(f"[Callback Exception] Error in save_history_entry_callback for Job ID {entry.get('job_id', 'N/A')}: {e}")
        traceback.print_exc() # Print stack trace for detailed debugging

    # Original logic: Clean up stop request if the job was stopped
    if entry.get('status') == 'stopped' and 'job_id' in entry:
        requested_stops.discard(entry['job_id']) # Ensure cleanup

# --- Route for the main web page (Run Page) ---
@app.route('/')
@app.route('/promo')
def index():
    """Serves the main Run page (accessible via / and /promo)."""
    return render_template('index.html')

# --- Route for the Profiles Page ---
@app.route('/profiles')
def profiles_page():
    """Serves the Profiles management page."""
    print("--- Rendering profiles_page --- ") # DEBUG
    return render_template('profiles.html')

# --- Route for the History Page ---
@app.route('/history')
def history_page():
    """Serves the History page."""
    history_data = history_manager.load_history() 
    return render_template('history.html', history=history_data)

# --- NEW Route for the Monitoring Page ---
@app.route('/monitoring')
def monitoring_page():
    """Serves the Monitoring management page."""
    return render_template('monitoring.html')

# --- API Route to get profiles --- (Used by Profile Editor and Run page)
@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    """Returns the current profiles as JSON."""
    profiles = profile_manager.load_profiles()
    return jsonify(profiles)

# --- API Route to add/update a profile --- (Used by Profile Editor)
@app.route('/api/profiles', methods=['POST'])
def add_or_update_profile():
    """Adds a new profile or updates an existing one."""
    data = request.json
    if not data or 'name' not in data or 'settings' not in data:
        return jsonify({"success": False, "error": "Invalid data format"}), 400

    profile_name = data['name']
    profile_settings = data['settings']
    original_name = data.get('original_name') # For detecting renames during edit

    profiles = profile_manager.load_profiles()

    # Check for name conflict if renaming
    if original_name and profile_name != original_name and profile_name in profiles:
         return jsonify({"success": False, "error": f"Profile name '{profile_name}' already exists.".format(profile_name=profile_name)}), 409 # Conflict

    # Remove old entry if name changed
    if original_name and profile_name != original_name and original_name in profiles:
        del profiles[original_name]

    profiles[profile_name] = profile_settings

    if profile_manager.save_profiles(profiles):
        return jsonify({"success": True, "profiles": profiles})
    else:
        return jsonify({"success": False, "error": "Failed to save profiles"}), 500

# --- API Route to delete a profile --- (Used by Profile Editor)
@app.route('/api/profiles/<profile_name>', methods=['DELETE'])
def delete_profile_route(profile_name):
    """Deletes the specified profile."""
    profiles = profile_manager.load_profiles()
    if profile_name in profiles:
        del profiles[profile_name]
        if profile_manager.save_profiles(profiles):
            return jsonify({"success": True, "profiles": profiles})
        else:
            return jsonify({"success": False, "error": "Failed to save profiles after deletion"}), 500
    else:
        return jsonify({"success": False, "error": "Profile not found"}), 404

# --- API Route to get minimum quantities config --- (Used by Profile Editor)
@app.route('/api/config/minimums', methods=['GET'])
def get_minimum_quantities():
    """Returns the minimum quantity mapping."""
    # Convert tuple keys to string for JSON compatibility (e.g., "('Platform', 'Engagement')")
    string_key_minimums = {str(k): v for k, v in config.MINIMUM_QUANTITIES.items()}
    return jsonify(string_key_minimums)

# --- API Route to update username --- (Used by Run Page)
@app.route('/api/username', methods=['POST'])
def update_username():
    """Updates the username in user_settings.json."""
    data = request.json
    if not data or 'username' not in data:
        return jsonify({"success": False, "error": "Missing username"}), 400
    
    new_username = data['username'].strip()
    if not new_username: # Basic validation: cannot be empty
         return jsonify({"success": False, "error": "Username cannot be empty"}), 400

    if profile_manager.save_username(new_username):
        return jsonify({"success": True, "username": new_username})
    else:
        return jsonify({"success": False, "error": "Failed to save username"}), 500

# --- API Route to get username --- (Used by Run Page)
@app.route('/api/username', methods=['GET'])
def get_username():
    """Gets the saved username from user_settings.json."""
    username = profile_manager.load_username()
    return jsonify({"success": True, "username": username})

# --- NEW Multi-Target Monitoring API Endpoints ---

@app.route('/api/monitoring/targets', methods=['GET'])
def get_monitoring_targets():
    """Gets the list of current monitoring targets."""
    config_data = instagram_monitor.load_monitoring_config()
    return jsonify({"success": True, "targets": config_data.get('targets', [])})

@app.route('/api/monitoring/targets', methods=['POST'])
def add_monitoring_target_route():
    """Adds a new target to monitor."""
    data = request.json
    if not data or not data.get('target_username') or not data.get('promotion_profile_name'):
        return jsonify({"success": False, "error": "Missing target_username or promotion_profile_name"}), 400
    
    username = data['target_username'].strip()
    profile_name = data['promotion_profile_name']

    if not username:
        return jsonify({"success": False, "error": "Target username cannot be empty"}), 400

    # Optional: Check if profile_name exists?
    all_profiles = profile_manager.load_profiles()
    if profile_name not in all_profiles:
         return jsonify({"success": False, "error": f"Promotion profile '{profile_name}' not found."}), 404

    # Optional: Check for duplicate username?
    current_config = instagram_monitor.load_monitoring_config()
    if any(t['target_username'] == username for t in current_config.get('targets', [])):
         return jsonify({"success": False, "error": f"Username '{username}' is already being monitored."}), 409

    new_target = instagram_monitor.add_monitoring_target(username, profile_name)
    if new_target:
        # Return the full updated list
        updated_config = instagram_monitor.load_monitoring_config()
        return jsonify({"success": True, "targets": updated_config.get('targets', []), "added_target": new_target})
    else:
        return jsonify({"success": False, "error": "Failed to add monitoring target"}), 500

@app.route('/api/monitoring/targets/<target_id>', methods=['PUT'])
def update_monitoring_target_route(target_id):
    """Updates a monitoring target (e.g., start/stop). Requires 'is_running' in payload."""
    data = request.json
    if data is None or 'is_running' not in data or not isinstance(data['is_running'], bool):
         return jsonify({"success": False, "error": "Invalid payload. Requires 'is_running' (boolean)."}), 400

    updates = {"is_running": data['is_running']}
    # Potentially allow updating promo profile later?
    # if 'promotion_profile_name' in data: updates['promotion_profile_name'] = data['promotion_profile_name']
    
    success = instagram_monitor.update_monitoring_target(target_id, updates)
    if success:
        updated_config = instagram_monitor.load_monitoring_config()
        updated_target = instagram_monitor.get_monitoring_target(target_id) # Get the updated target data
        return jsonify({"success": True, "targets": updated_config.get('targets', []), "updated_target": updated_target})
    else:
        # Check if it failed because the ID wasn't found
        if instagram_monitor.get_monitoring_target(target_id) is None:
            return jsonify({"success": False, "error": f"Target ID '{target_id}' not found.", "status_code": 404}), 404
        else:
            return jsonify({"success": False, "error": f"Failed to update target ID '{target_id}'."}), 500

@app.route('/api/monitoring/targets/<target_id>', methods=['DELETE'])
def remove_monitoring_target_route(target_id):
    """Removes a monitoring target."""
    success = instagram_monitor.remove_monitoring_target(target_id)
    if success:
        updated_config = instagram_monitor.load_monitoring_config()
        return jsonify({"success": True, "targets": updated_config.get('targets', [])})
    else:
         # Assume failure means ID not found (based on remove_monitoring_target logic)
         return jsonify({"success": False, "error": f"Target ID '{target_id}' not found or failed to save."}), 404

@app.route('/api/monitoring/settings', methods=['GET'])
def get_monitoring_settings():
    """Gets the global monitoring settings (e.g., polling interval)."""
    config_data = instagram_monitor.load_monitoring_config()
    settings = {
        "polling_interval_seconds": config_data.get('polling_interval_seconds', instagram_monitor.DEFAULT_POLLING_INTERVAL)
    }
    return jsonify({"success": True, "settings": settings})

@app.route('/api/monitoring/settings', methods=['PUT'])
def update_monitoring_settings():
    """Updates the global monitoring settings."""
    data = request.json
    if data is None or 'polling_interval_seconds' not in data:
        return jsonify({"success": False, "error": "Missing 'polling_interval_seconds'"}), 400
        
    try:
        new_interval = int(data['polling_interval_seconds'])
        if new_interval < 30: # Add a reasonable minimum? e.g., 30 seconds
            return jsonify({"success": False, "error": "Polling interval must be at least 30 seconds"}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Polling interval must be an integer"}), 400
        
    config_data = instagram_monitor.load_monitoring_config()
    config_data['polling_interval_seconds'] = new_interval
    
    if instagram_monitor.save_monitoring_config(config_data):
        return jsonify({"success": True, "settings": {"polling_interval_seconds": new_interval}})
    else:
        return jsonify({"success": False, "error": "Failed to save monitoring settings"}), 500

# --- API Endpoint for Manual Scraping Test --- 
@app.route('/api/monitoring/test_get_latest_post', methods=['POST'])
def test_get_latest_post_route():
    """Manually triggers the scraping logic for a specific username.
    Uses the same requests-based method as the background monitor for reliability.
    """
    data = request.json
    if not data or 'target_username' not in data:
        return jsonify({"success": False, "error": "Missing target_username"}), 400
        
    target_username = data['target_username'].strip()
    if not target_username:
        return jsonify({"success": False, "error": "Target username cannot be empty"}), 400
        
    print(f"[API Test] Request received to test getting latest post for: {target_username} (using instagram_monitor.get_latest_post_info)")
    
    # --- Call the requests-based function from instagram_monitor ---
    latest_post_url, post_dt_utc = instagram_monitor.get_latest_post_info(target_username)
    # -------------------------------------------------------------
    
    if latest_post_url:
        timestamp_str = post_dt_utc.isoformat() if post_dt_utc else None 
        print(f"[API Test] Success via instagram_monitor. URL: {latest_post_url}, Timestamp: {timestamp_str}")
        return jsonify({
            "success": True, 
            "url": latest_post_url, 
            "timestamp_iso": timestamp_str
        })
    else:
        print(f"[API Test] Failed to get latest post info for {target_username} via instagram_monitor.")
        return jsonify({"success": False, "error": f"Failed to get latest post info for {target_username} using the direct API method. Check server logs for details."})

# --- Run Page: Manual Promotion Triggers --- 

# --- API Route to Start Auto Promotion --- (Manual trigger from Run page)
@app.route('/api/start_promo', methods=['POST'])
def start_promo_route():
    """Triggers the automation task in the background using a Profile."""
    data = request.json
    if not data or 'profile_name' not in data or 'link' not in data:
        return jsonify({"success": False, "error": "Missing profile_name or link"}), 400

    profile_name = data['profile_name']
    link = data['link']

    profiles = profile_manager.load_profiles()
    if profile_name not in profiles:
        return jsonify({"success": False, "error": f"Profile '{profile_name}' not found"}), 404

    profile_data = profiles[profile_name]

    # Validate link format (basic)
    # Allow different platforms now potentially, just check for https?
    if not link or not link.startswith('https://'): 
        return jsonify({"success": False, "error": "Invalid link format (must start with https://)"}), 400

    try:
        # Schedule the automation task to run immediately in the background
        job_id = f'promo_{profile_name}_{time.time()}' 
        job_statuses[job_id] = {'status': 'pending', 'message': 'Job scheduled, waiting to run.'} # Initial status
        scheduler.add_job(
            id=job_id,
            func=automation_runner.run_automation_profile,
            trigger='date', # Run immediately
            args=[profile_name, profile_data, link, job_id, update_job_status, save_history_entry_callback, requested_stops], # Pass job_id, status callback, history callback
            misfire_grace_time=None # Run even if scheduler was briefly down
        )
        print(f"Scheduled job {job_id} for profile '{profile_name}'")
        # Return job_id so frontend can poll
        return jsonify({"success": True, "message": f"Automation scheduled for profile '{profile_name}'.", "job_id": job_id}) 
    except Exception as e:
        print(f"Error scheduling job for profile '{profile_name}': {e}")
        traceback.print_exc()
        # No job_id generated if scheduling fails
        return jsonify({"success": False, "error": "Failed to schedule automation task"}), 500

# --- API Route to Start Single Promotion --- (Manual trigger from Run page)
@app.route('/api/start_single_promo', methods=['POST'])
def start_single_promo_route():
    """Triggers a single automation order in the background."""
    data = request.json
    required_fields = ['platform', 'engagement', 'link', 'quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    platform = data['platform']
    engagement = data['engagement']
    link = data['link']
    quantity_str = data['quantity']

    # Basic Validation
    if not link or not link.startswith('https://'): # Very basic check
         return jsonify({"success": False, "error": "Invalid link format (must start with https://)"}), 400
    try:
        quantity = int(quantity_str)
        if quantity <= 0:
             raise ValueError("Quantity must be positive")
    except ValueError as e:
         return jsonify({"success": False, "error": f"Invalid quantity: {e}"}), 400

    # Minimum Quantity Check
    min_qty_key = (platform, engagement)
    minimum_required = config.MINIMUM_QUANTITIES.get(min_qty_key)
    if minimum_required is not None and quantity < minimum_required:
         error_msg = f"Minimum quantity for {platform} {engagement} is {minimum_required}."
         return jsonify({"success": False, "error": error_msg}), 400

    try:
        job_id = f'single_promo_{platform}_{engagement}_{time.time()}'
        job_statuses[job_id] = {'status': 'pending', 'message': 'Job scheduled, waiting to run.'} # Initial status
        scheduler.add_job(
            id=job_id,
            func=automation_runner.run_single_automation,
            trigger='date',
            args=[platform, engagement, link, quantity, job_id, update_job_status, save_history_entry_callback], # Pass job_id, status callback, history callback
            misfire_grace_time=None
        )
        print(f"Scheduled job {job_id} for single promo")
         # Return job_id so frontend can poll
        return jsonify({"success": True, "message": f"Single promo for {engagement} scheduled.", "job_id": job_id})
    except Exception as e:
        print(f"Error scheduling single promo job: {e}")
        traceback.print_exc()
         # No job_id generated if scheduling fails
        return jsonify({"success": False, "error": "Failed to schedule single automation task"}), 500

# --- API Route to check job status --- (Used by Run page for manual/profile promos)
@app.route('/api/job_status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Returns the status of a background job (manual/profile promos ONLY)."""
    status_info = job_statuses.get(job_id)
    if status_info:
        return jsonify({"success": True, "status": status_info['status'], "message": status_info['message']})
    else:
        # Check if it might be a monitoring job ID structure (less likely to be polled, but maybe)
        if job_id.startswith('monitor_promo_'):
            return jsonify({"success": False, "error": "Monitoring job status not tracked here. Check History."}), 404
        else:
            return jsonify({"success": False, "error": "Job ID not found"}), 404

# --- NEW Stop Route --- 
@app.route('/api/stop_promo', methods=['POST'])
def stop_profile_promo():
    data = request.get_json()
    job_id = data.get('job_id')

    if not job_id:
        return jsonify({"status": "error", "message": "Missing job_id"}), 400

    job = scheduler.get_job(job_id)
    if not job:
        # Maybe it finished already? Check status dict
        if job_id in job_statuses and job_statuses[job_id]['status'] in ['success', 'failed', 'stopped']:
            return jsonify({"status": "error", "message": f"Job {job_id} has already finished."}) # No need for 404
        else:
            return jsonify({"status": "error", "message": f"Job {job_id} not found or not running."}), 404
            
    # Check if already requested to stop
    if job_id in requested_stops:
        return jsonify({"status": "success", "message": f"Stop already requested for job {job_id}."})

    # Add job_id to the set of requested stops
    requested_stops.add(job_id)
    update_job_status(job_id, 'stopping', 'Stop requested by user...') # Update status
    app.logger.info(f"Stop requested for job ID: {job_id}")

    # The running job needs to check the `requested_stops` set itself.
    # We don't directly kill the thread here.
    return jsonify({"status": "success", "message": f"Stop request registered for job {job_id}."})

# --- App Startup --- 
if __name__ == '__main__':
    # Ensure the app listens on the port specified by Render's PORT env var
    port = int(os.environ.get("PORT", 10000))
    print(f"Attempting to serve Flask app on host 0.0.0.0, port {port} using Waitress...")
    serve(app, host="0.0.0.0", port=port) 