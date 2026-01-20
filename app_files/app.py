import sys
import os

from flask import Flask, render_template, jsonify, request, send_from_directory, send_file
from flask_apscheduler import APScheduler # Import APScheduler
import profile_manager
import api_runner  # API-based ordering runner
import services_catalog  # CSV-driven services catalog
import providers_api  # Provider API client
import profile_manager  # For loading profiles in estimate endpoints
import time
import config # Import config to access MINIMUM_QUANTITIES
import traceback # Import traceback
import history_manager # Import history manager
import datetime # Import datetime
import pytz # For timezone conversion
from markupsafe import Markup # For rendering HTML safely if needed
import os # Import os for development server check
import instagram_monitor # Import the new monitor module
from urllib.parse import urlparse # For building provider order links
from apscheduler.jobstores.base import JobLookupError # For removing jobs
import json
import uuid
import logging
from waitress import serve # Added for Render deployment
# from apscheduler.executors.asyncio import AsyncIOExecutor # REMOVE Import
import io
import zipfile

# --- App and Scheduler Configuration ---
class Config:
    SCHEDULER_API_ENABLED = True # Optional: enables a default scheduler UI at /scheduler
    TEMPLATES_AUTO_RELOAD = True  # Reload templates on every request (dev convenience)
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

# Persistent storage for active jobs (survives restarts)
ACTIVE_JOBS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'active_jobs.json')

def save_active_jobs():
    """Save active jobs to disk for restart recovery."""
    try:
        os.makedirs(os.path.dirname(ACTIVE_JOBS_FILE), exist_ok=True)
        # Only save non-terminal jobs
        terminal_statuses = {'success', 'failed', 'stopped'}
        active = {jid: info for jid, info in job_statuses.items() 
                  if (info.get('status') or '').lower() not in terminal_statuses}
        with open(ACTIVE_JOBS_FILE, 'w') as f:
            json.dump(active, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save active jobs: {e}")

def load_active_jobs():
    """Load active jobs from disk after restart and reschedule them."""
    try:
        if os.path.exists(ACTIVE_JOBS_FILE):
            with open(ACTIVE_JOBS_FILE, 'r') as f:
                saved_jobs = json.load(f)
            
            if saved_jobs:
                print(f"Found {len(saved_jobs)} interrupted job(s) from previous session. Resuming...")
                for job_id, job_info in saved_jobs.items():
                    # Restore to job_statuses with 'resuming' status
                    job_info['status'] = 'pending'
                    job_info['message'] = 'Resuming from previous session...'
                    job_statuses[job_id] = job_info
                    
                    # Try to reschedule the job
                    try:
                        # Parse job type from job_id
                        if job_id.startswith('promo_api_') or job_id.startswith('monitor_promo_'):
                            # Auto promo - need to reload profile and reschedule
                            profile_name = job_info.get('profile_name')
                            link = job_info.get('link')
                            if profile_name and link:
                                profiles = profile_manager.load_profiles()
                                if profile_name in profiles:
                                    profile_data = profiles[profile_name]
                                    platform_filter = None  # Extract from label if needed
                                    
                                    scheduler.add_job(
                                        id=job_id,
                                        func=api_runner.run_profile_api_promo,
                                        trigger='date',
                                        args=[profile_name, profile_data, link, job_id, update_job_status, save_history_entry_callback, requested_stops, platform_filter],
                                        misfire_grace_time=None
                                    )
                                    print(f"  ✅ Rescheduled: {job_id} ({profile_name})")
                                else:
                                    print(f"  ⚠️ Cannot resume {job_id}: Profile '{profile_name}' not found")
                                    job_statuses[job_id]['status'] = 'failed'
                                    job_statuses[job_id]['message'] = 'Cannot resume: Profile not found'
                        elif job_id.startswith('single_api_'):
                            # Single promo - would need platform, engagement, link, quantity
                            # For now, mark as unable to resume
                            print(f"  ⚠️ Cannot auto-resume single promo: {job_id}")
                            job_statuses[job_id]['status'] = 'stopped'
                            job_statuses[job_id]['message'] = 'Server restarted - manual restart required'
                    except Exception as e:
                        print(f"  ❌ Error rescheduling {job_id}: {e}")
                        job_statuses[job_id]['status'] = 'failed'
                        job_statuses[job_id]['message'] = f'Resume failed: {e}'
    except Exception as e:
        print(f"Warning: Could not load active jobs: {e}")
        traceback.print_exc()

# --- CONSTANTS --- (Keep location)
# MONTIORING_JOB_ID = "instagram_monitoring_job" # Old ID, removed
GLOBAL_MONITORING_CHECK_JOB_ID = "global_monitoring_check_job"
SCHEDULE_INTERVAL_SECONDS = 60 # Default check interval
DEFAULT_POST_AGE_LIMIT_HOURS = 1 # Only promote posts newer than this

# --- Background Task Logic --- (No longer needs to be async)
def run_global_monitoring_check():
    """Scheduled function that checks ALL active targets based on polling interval."""
    # Minimal logging per requirements
    config_data = instagram_monitor.load_monitoring_config()
    all_targets = config_data.get('targets', [])
    polling_interval = datetime.timedelta(seconds=config_data.get('polling_interval_seconds', instagram_monitor.DEFAULT_POLLING_INTERVAL))
    profiles = None # Lazy load profiles if needed
    config_needs_saving = False # Track if any target timestamps/URLs are updated
    active_targets = [t for t in all_targets if t.get('is_running')]
    if not active_targets:
        # Do not log when no active targets
        return

    now_dt = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware now
    any_new_post = False

    for target in active_targets:
        target_id = target.get("id")
        target_username = target.get("target_username")
        promo_profile_name = target.get("promotion_profile_name")
        last_pushed_url = target.get("last_pushed_post_url")
        last_checked_iso = target.get("last_checked_timestamp")

        if not target_username or not promo_profile_name or not target_id:
            continue

        # Determine if it's time to check this target
        should_check = False
        if last_checked_iso is None:
            should_check = True # Never checked before
        else:
            try:
                last_checked_dt = datetime.datetime.fromisoformat(last_checked_iso.replace('Z', '+00:00'))
                if now_dt - last_checked_dt >= polling_interval:
                    should_check = True
            except (ValueError, TypeError) as e:
                # Fallback to checking if timestamp parsing fails
                should_check = True

        if should_check:
            print(f"Checking targets (@{target_username})")
            # Ensure we have the latest profile settings before attempting to scrape
            if profiles is None: # Reload profiles if they haven't been loaded in this run
                 profiles = profile_manager.load_profiles()
                
            if promo_profile_name not in profiles:
                 print(f"Skipping target {target_username} as its profile '{promo_profile_name}' is missing.")
                 continue # Skip this target if its profile is missing

            promo_settings = profiles[promo_profile_name] # Get current settings

            # Attempt to get latest post info (use synchronous call now)
            latest_post_url, post_dt_utc = instagram_monitor.get_latest_post_info(target_username)
            
            # Update last checked time immediately after scraping attempt
            target['last_checked_timestamp'] = now_dt.isoformat()
            config_needs_saving = True

            if not latest_post_url:
                print(f"[Global Check] ⚠️ Failed to get latest post info for '{target_username}'. Skipping promotion check.")
                continue # Error during scraping for this target

            if latest_post_url == last_pushed_url:
                print(f"[Global Check] 🔁 Latest post URL for '{target_username}' is the same as the last pushed URL. No action needed.")
                continue # Already processed this post

            # --- New Post Detected --- 
            print(f"New post found ({post_dt_utc.isoformat() if post_dt_utc else 'unknown time'})")
            any_new_post = True

            if not post_dt_utc:
                print(f"[Global Check] ⌛ Could not determine post timestamp for {latest_post_url}. Cannot check age. Will not push.")
                # Mark this URL as seen anyway to prevent re-checking its timestamp
                target['last_pushed_post_url'] = latest_post_url
                # config_needs_saving is already True
            else:
                # Ensure datetime has timezone info (should be UTC from scraping)
                if post_dt_utc.tzinfo is None:
                     post_dt_utc = post_dt_utc.replace(tzinfo=datetime.timezone.utc)
                
                time_diff = now_dt - post_dt_utc
                print(f"[Global Check] 🗓️ Post time: {post_dt_utc}, Current time: {now_dt}, Difference: {time_diff}")

                # Check if post is within the allowed age limit
                if time_diff < datetime.timedelta(hours=DEFAULT_POST_AGE_LIMIT_HOURS):
                    print(f"[Global Check] ✅ Post for '{target_username}' is within the last {DEFAULT_POST_AGE_LIMIT_HOURS} hour(s). Triggering promotion!")
            
                    # Schedule the actual promo job
                    try:
                        # Use a unique job ID including target ID and timestamp
                        promo_job_id = f'monitor_promo_{target_id}_{time.time()}' 
                        # Use the existing job_statuses dict for tracking these triggered promos
                        label = f"Auto Promo: {promo_profile_name} (Monitor: {target_username})"
                        job_statuses[promo_job_id] = {
                            'status': 'pending', 
                            'message': f'Monitor trigger for {target_username} ({promo_profile_name})',
                            'label': label,
                            'link': latest_post_url,
                            'container_id': 'auto-promo-jobs',
                            'profile_name': promo_profile_name  # For resume capability
                        }
                        scheduler.add_job(
                            id=promo_job_id,
                            func=api_runner.run_profile_api_promo,
                            trigger='date', # Run immediately
                            args=[promo_profile_name, promo_settings, latest_post_url, promo_job_id, update_job_status, save_history_entry_callback, requested_stops, None],
                            misfire_grace_time=None
                        )
                        save_active_jobs()  # Save to disk for restart recovery
                        print(f"[Global Check] 📆 Scheduled promotion job {promo_job_id} for post {latest_post_url}")
                        # Successfully scheduled, update last pushed URL in the target config
                        target['last_pushed_post_url'] = latest_post_url
                        # config_needs_saving is already True
                    except Exception as e:
                        print(f"Error scheduling promo for {latest_post_url}: {e}")
                        # Don't update last_pushed_url if scheduling failed, maybe retry next time?
                else:
                    # Update last pushed URL so we don't re-check this old post
                    target['last_pushed_post_url'] = latest_post_url
                    # config_needs_saving is already True
        # End of if should_check
    # End of loop through targets

    # Save config changes if any timestamps or pushed URLs were updated
    if config_needs_saving:
        instagram_monitor.save_monitoring_config(config_data)

    if not any_new_post:
        # Minimal log about waiting until next server-side check
        next_in = config_data.get('polling_interval_seconds', instagram_monitor.DEFAULT_POLLING_INTERVAL)
        print(f"Waiting {next_in}s for next target check")

# --- Function to initialize the global monitoring scheduler job ---
def initialize_monitoring_job():
    print("[Initialize Job] 🛠️ Attempting to initialize global monitoring scheduler job...")
    try:
        config_data = instagram_monitor.load_monitoring_config()
        current_interval = config_data.get('polling_interval_seconds', SCHEDULE_INTERVAL_SECONDS)
        print(f"[Initialize Job] ⏱️ Using interval from config: {current_interval} seconds.")
        try:
            scheduler.remove_job(GLOBAL_MONITORING_CHECK_JOB_ID)
            print(f"[Initialize Job] 🗑️ Removed existing global monitoring job '{GLOBAL_MONITORING_CHECK_JOB_ID}'.")
        except JobLookupError:
            print(f"[Initialize Job] ℹ️ No existing job '{GLOBAL_MONITORING_CHECK_JOB_ID}' found to remove.")
            pass 

        # Schedule the SYNC function directly now
        scheduler.add_job(
            id=GLOBAL_MONITORING_CHECK_JOB_ID,
            func=run_global_monitoring_check, # Schedule the sync function directly
            trigger='interval',
            seconds=current_interval,
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=10)
        )
        print(f"[Initialize Job] ✅ SUCCESS: Scheduled '{GLOBAL_MONITORING_CHECK_JOB_ID}' to run every {current_interval} seconds.")
    except Exception as e:
        print(f"[Initialize Job] ❌ FATAL ERROR: Failed to schedule global monitoring job: {e}") 
        traceback.print_exc()

# Initialize the monitoring job right after scheduler starts
with app.app_context(): 
    initialize_monitoring_job()
    # Load any interrupted jobs from previous session
    load_active_jobs()

# --- Custom Jinja Filter ---
@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%Y-%m-%d %H:%M:%S'):
    """Formats an ISO datetime string into EST timezone with format: MM/DD/YYYY\nH:MM:SS AM/PM"""
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
        
        # Ensure the datetime is timezone-aware (assume EST if naive, not UTC)
        if dt_object.tzinfo is None:
            est = pytz.timezone('America/New_York')
            dt_object = est.localize(dt_object)
        else:
            # If it's already timezone-aware, convert to EST
            est = pytz.timezone('America/New_York')
            dt_object = dt_object.astimezone(est)
        
        # Format as: MM/DD/YYYY<br>H:MM:SS AM/PM (Windows-compatible)
        date_str = dt_object.strftime('%m/%d/%Y').lstrip('0').replace('/0', '/')  # Remove leading zeros
        time_str = dt_object.strftime('%I:%M:%S %p').lstrip('0')  # Remove leading zero from hour
        return Markup(f"{date_str}<br>{time_str}")
    except (ValueError, TypeError) as e:
        print(f"Error formatting datetime '{value}': {e}")
        # Handle cases where value is not a valid ISO string or None
        return value # Return original value if parsing fails

@app.template_filter('provider_order_url')
def provider_order_url_filter(provider: str) -> str:
    """Return a best-effort URL to the provider's Orders page.
    Uses providers_api.BASE_URLS to derive the root domain, then appends /orders.
    Falls back to https://<provider>.com if unknown, else '#'.
    """
    try:
        prov = providers_api._normalize_provider(provider) if hasattr(providers_api, '_normalize_provider') else str(provider or '').strip().lower().replace(' ', '')
        base_api = providers_api.BASE_URLS.get(prov)
        if base_api:
            u = urlparse(base_api)
            root = f"{u.scheme}://{u.netloc}"
            return f"{root}/orders"
        # Fallback: guess domain from provider name
        p = (str(provider or '').strip().lower().replace(' ', ''))
        if p:
            return f"https://{p}.com"
    except Exception:
        pass
    return '#'

# --- Global state for job status and stop requests --- 
job_status_updates = {} # Stores the latest status for each job ID
requested_stops = set() # Stores job_ids requested to stop

def update_job_status(job_id, status, message=None):
    """Callback function to update the status of a manual/profile promo job."""
    if job_id in job_statuses:
        job_statuses[job_id]['status'] = status
        job_statuses[job_id]['message'] = message
        print(f"📣 Job Status Update: {job_id} -> {status} {f'({message})' if message else ''}")
        # Save to disk after each update for restart recovery
        save_active_jobs()
    else:
        print(f"Warning: Job ID {job_id} not found in status tracker for update ({status}).")

def save_history_entry_callback(entry):
    """Callback passed to runner functions to save history."""
    try:
        # Attempt to save the entry using the history manager
        success = history_manager.save_history_entry(entry)
        if not success:
            print(f"[Callback Error] ❌ Failed to save history entry for Job ID: {entry.get('job_id', 'N/A')}")
    except Exception as e:
        # Log any unexpected errors during saving
        print(f"[Callback Exception] ❗ Error in save_history_entry_callback for Job ID {entry.get('job_id', 'N/A')}: {e}")
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
    print("🧩 --- Rendering profiles_page --- ") # DEBUG
    return render_template('profiles.html')

# --- Route for the History Page ---
@app.route('/history')
def history_page():
    """Serves the History page with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    all_history = history_manager.load_history()
    total_items = len(all_history)
    total_pages = (total_items + per_page - 1) // per_page  # Ceiling division
    
    # Ensure page is within valid range
    page = max(1, min(page, total_pages if total_pages > 0 else 1))
    
    # Slice history for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    history_data = all_history[start_idx:end_idx]
    
    return render_template('history.html', 
                         history=history_data,
                         current_page=page,
                         total_pages=total_pages,
                         total_items=total_items)

# --- NEW Route for the Monitoring Page ---
@app.route('/monitoring')
def monitoring_page():
    """Serves the Monitoring management page."""
    return render_template('monitoring.html')

# --- Route for the Services Page ---
@app.route('/services')
def services_page():
    """Serves the Services configuration page."""
    return render_template('services.html')

# --- Route for the Debug Page ---
@app.route('/debug')
def debug_page():
    """Serves the Debug page with step-by-step test controls."""
    return render_template('debug.html')

# --- Route for the Balances Page ---
@app.route('/balances')
def balances_page():
    """Serves the Balances page."""
    return render_template('balances.html')

# --- API Route: Ping/Health Check (Keep server alive) ---
@app.route('/api/ping', methods=['GET'])
def ping():
    """Lightweight endpoint to keep server alive and prevent spin-down."""
    return jsonify({'success': True, 'status': 'alive', 'timestamp': datetime.datetime.now().isoformat()})

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

# --- Services Catalog Endpoints (CSV-driven) ---
@app.route('/api/services/platforms', methods=['GET'])
def get_services_platforms():
    try:
        plats = services_catalog.get_platforms()
        return jsonify({"success": True, "platforms": plats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Export Endpoints ---
@app.route('/api/export/services-configs', methods=['GET'])
def export_services_configs():
    try:
        services_json_path = services_catalog._services_json_path()
        if os.path.exists(services_json_path):
            # Serve the current catalog JSON directly
            return send_file(services_json_path, mimetype='application/json', as_attachment=True, download_name='services_catalog.json')
        # Fallback: generate from memory
        data = { 'services': services_catalog._load_services_json(refresh=True), 'version': '1.0' }
        return send_file(io.BytesIO(json.dumps(data, indent=2).encode('utf-8')), mimetype='application/json', as_attachment=True, download_name='services_catalog.json')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/profiles', methods=['GET'])
def export_profiles():
    try:
        profiles_path = profile_manager.DEFAULT_PROFILE_FILE
        if not os.path.exists(profiles_path):
            # Return empty JSON structure if no profiles yet
            data = {}
            return send_file(io.BytesIO(json.dumps(data, indent=4).encode('utf-8')), mimetype='application/json', as_attachment=True, download_name='profiles.json')
        return send_file(profiles_path, mimetype='application/json', as_attachment=True, download_name='profiles.json')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/import/services-configs', methods=['POST'])
def import_services_configs():
    """Import services catalog JSON file to overwrite current config."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read and validate JSON
        try:
            content = file.read().decode('utf-8')
            data = json.loads(content)
            if 'services' not in data or not isinstance(data['services'], list):
                return jsonify({'success': False, 'error': 'Invalid services catalog format. Must contain "services" array.'}), 400
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return jsonify({'success': False, 'error': f'Invalid JSON file: {str(e)}'}), 400
        
        # Write to services_catalog.json
        services_json_path = services_catalog._services_json_path()
        os.makedirs(os.path.dirname(services_json_path), exist_ok=True)
        with open(services_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        # Clear cache to reload
        services_catalog._SERVICES_JSON_CACHE = None
        
        return jsonify({'success': True, 'message': f'Imported {len(data["services"])} services successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/import/profiles', methods=['POST'])
def import_profiles():
    """Import profiles JSON file to overwrite current profiles."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read and validate JSON
        try:
            content = file.read().decode('utf-8')
            data = json.loads(content)
            if not isinstance(data, dict):
                return jsonify({'success': False, 'error': 'Invalid profiles format. Must be a JSON object.'}), 400
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return jsonify({'success': False, 'error': f'Invalid JSON file: {str(e)}'}), 400
        
        # Write to profiles.json
        profiles_path = profile_manager.DEFAULT_PROFILE_FILE
        os.makedirs(os.path.dirname(profiles_path), exist_ok=True)
        with open(profiles_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Imported {len(data)} profiles successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/services/engagements', methods=['GET'])
def get_services_engagements():
    platform = request.args.get('platform', '').strip()
    if not platform:
        return jsonify({"success": False, "error": "Missing 'platform' query param"}), 400
    try:
        engs = services_catalog.get_engagements_by_platform(platform)
        return jsonify({"success": True, "engagements": engs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# List detailed services for a given platform + engagement (category)
@app.route('/api/services/by_category', methods=['GET'])
def get_services_by_category():
    platform = (request.args.get('platform') or '').strip()
    engagement = (request.args.get('engagement') or '').strip()
    if not platform or not engagement:
        return jsonify({"success": False, "error": "Missing 'platform' or 'engagement' query param"}), 400
    try:
        services = services_catalog.list_services(platform, engagement)
        return jsonify({"success": True, "services": services})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Service Overrides Endpoints ---
@app.route('/api/services/overrides', methods=['GET'])
def get_service_overrides():
    """Get all configured service overrides."""
    try:
        # Reflect effective selections from services catalog JSON
        services = services_catalog._load_services_json()
        mapping = {}
        for s in services:
            plat = (s.get('platform') or '').strip()
            eng = (s.get('service_category') or '').strip()
            if not plat or not eng:
                continue
            mapping.setdefault(plat, {})[eng] = {
                'service_id': s.get('service_id'),
                'provider': s.get('provider'),
                'provider_label': s.get('provider_label'),
                'name': s.get('name'),
                'min_qty': s.get('min_qty'),
                'max_qty': s.get('max_qty'),
                'rate_per_1k': s.get('rate_per_1k'),
                'tier': s.get('tier'),
                'notes': s.get('notes'),
            }
        return jsonify({"success": True, "overrides": mapping})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/services/overrides', methods=['POST'])
def set_service_override():
    """Set a service override for a specific platform/engagement."""
    data = request.json or {}
    platform = (data.get('platform') or '').strip()
    engagement = (data.get('engagement') or '').strip()
    service_id = data.get('service_id')
    provider = (data.get('provider') or '').strip()
    
    if not platform or not engagement or not service_id or not provider:
        return jsonify({"success": False, "error": "Missing required fields: platform, engagement, service_id, provider"}), 400
    
    try:
        service_id_int = int(service_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "service_id must be a valid integer"}), 400
    
    try:
        override_data = {
            'service_id': service_id_int,
            'provider': provider,
            'provider_label': data.get('provider_label'),
            'name': data.get('name'),
            'min_qty': data.get('min_qty'),
            'max_qty': data.get('max_qty'),
            'rate_per_1k': data.get('rate_per_1k'),
            'tier': data.get('tier'),
            'notes': data.get('notes')
        }
        result = services_catalog.set_override(platform, engagement, override_data)
        return jsonify({"success": True, "override": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/services/overrides/<platform>/<engagement>', methods=['DELETE'])
def delete_service_override(platform, engagement):
    """Delete a service override for a specific platform/engagement."""
    try:
        success = services_catalog.clear_override_entry(platform, engagement)
        if success:
            return jsonify({"success": True, "message": "Override deleted"})
        else:
            return jsonify({"success": False, "error": "Override not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Balances Endpoints ---
@app.route('/api/balances/<provider>', methods=['GET'])
def get_provider_balance(provider):
    try:
        data = providers_api.get_balance(provider)
        return jsonify({"success": True, "provider": provider, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/balances', methods=['GET'])
def get_all_balances():
    results = {}
    ok = True
    errors = {}
    for prov in ['justanotherpanel', 'peakerr', 'smmkings', 'mysocialsboost', 'morethanpanel']:
        try:
            results[prov] = providers_api.get_balance(prov)
        except Exception as e:
            ok = False
            errors[prov] = str(e)
    status = 200 if ok else 207
    return jsonify({"success": ok, "balances": results, "errors": errors}), status


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
        
    print(f"[API Test] 🧪 Request received to test getting latest post for: {target_username} (using instagram_monitor.get_latest_post_info)")
    
    # --- Call the requests-based function from instagram_monitor ---
    latest_post_url, post_dt_utc = instagram_monitor.get_latest_post_info(target_username)
    # -------------------------------------------------------------
    
    if latest_post_url:
        timestamp_str = post_dt_utc.isoformat() if post_dt_utc else None 
        print(f"[API Test] ✅ Success via instagram_monitor. URL: {latest_post_url}, Timestamp: {timestamp_str}")
        return jsonify({
            "success": True, 
            "url": latest_post_url, 
            "timestamp_iso": timestamp_str
        })
    else:
        print(f"[API Test] ❌ Failed to get latest post info for {target_username} via instagram_monitor.")
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
    platform_filter = (data.get('platform') or '').strip() or None

    profiles = profile_manager.load_profiles()
    if profile_name not in profiles:
        return jsonify({"success": False, "error": f"Profile '{profile_name}' not found"}), 404

    profile_data = profiles[profile_name]

    # Validate link format (basic)
    # Allow different platforms now potentially, just check for https?
    if not link or not link.startswith('https://'): 
        return jsonify({"success": False, "error": "Invalid link format (must start with https://)"}), 400

    try:
        # Schedule API-based auto promo job using CSV services
        job_id = f'promo_api_{profile_name}_{time.time()}' 
        label = f"Auto Promo: {profile_name}{' — ' + platform_filter if platform_filter else ''}"
        job_statuses[job_id] = {
            'status': 'pending', 
            'message': 'Job scheduled, waiting to run.',
            'label': label,
            'link': link,
            'container_id': 'auto-promo-jobs',
            'profile_name': profile_name  # For resume capability
        }
        scheduler.add_job(
            id=job_id,
            func=api_runner.run_profile_api_promo,
            trigger='date',
            args=[profile_name, profile_data, link, job_id, update_job_status, save_history_entry_callback, requested_stops, platform_filter],
            misfire_grace_time=None
        )
        save_active_jobs()  # Save to disk for restart recovery
        print(f"🗓️ Scheduled API job {job_id} for profile '{profile_name}'")
        return jsonify({"success": True, "message": f"Automation scheduled for profile '{profile_name}'.", "job_id": job_id}) 
    except Exception as e:
        print(f"❌ Error scheduling job for profile '{profile_name}': {e}")
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
        job_id = f'single_api_{platform}_{engagement}_{time.time()}'
        label = f"Single Promo: {platform} — {engagement} (x{quantity})"
        job_statuses[job_id] = {
            'status': 'pending', 
            'message': 'Job scheduled, waiting to run.',
            'label': label,
            'link': link,
            'container_id': 'single-promo-jobs'
        }
        scheduler.add_job(
            id=job_id,
            func=api_runner.run_single_api_order,
            trigger='date',
            args=[platform, engagement, link, quantity, job_id, update_job_status, save_history_entry_callback, requested_stops],
            misfire_grace_time=None
        )
        save_active_jobs()  # Save to disk for restart recovery
        print(f"🗓️ Scheduled API job {job_id} for single promo")
        return jsonify({"success": True, "message": f"Single promo for {engagement} scheduled.", "job_id": job_id})
    except Exception as e:
        print(f"❌ Error scheduling single promo API job: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": "Failed to schedule automation task"}), 500


# --- API Route to Start Single Promotion by Service (strict min/max) ---
@app.route('/api/start_single_promo_by_service', methods=['POST'])
def start_single_promo_by_service_route():
    """Triggers a single order for a specific service with strict min/max validation."""
    data = request.json
    required_fields = ['platform', 'engagement', 'service_id', 'link', 'quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    platform = (data.get('platform') or '').strip()
    engagement = (data.get('engagement') or '').strip()
    link = (data.get('link') or '').strip()
    service_id = data.get('service_id')
    quantity = data.get('quantity')

    # Basic Validation
    if not link or not link.startswith('https://'):
        return jsonify({"success": False, "error": "Invalid link format (must start with https://)"}), 400
    try:
        service_id = int(service_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid service_id"}), 400
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
    except Exception as e:
        return jsonify({"success": False, "error": f"Invalid quantity: {e}"}), 400

    try:
        job_id = f'single_api_by_service_{platform}_{engagement}_{service_id}_{time.time()}'
        label = f"Single Promo: {platform} — {engagement} (x{quantity}) [Service #{service_id}]"
        job_statuses[job_id] = {
            'status': 'pending', 
            'message': 'Job scheduled, waiting to run.',
            'label': label,
            'link': link,
            'container_id': 'single-promo-jobs'
        }
        scheduler.add_job(
            id=job_id,
            func=api_runner.run_order_by_service,
            trigger='date',
            args=[platform, engagement, service_id, link, quantity, job_id, update_job_status, save_history_entry_callback, requested_stops],
            misfire_grace_time=None
        )
        save_active_jobs()  # Save to disk for restart recovery
        print(f"🗓️ Scheduled API job {job_id} for single promo")
        return jsonify({"success": True, "message": f"Single promo scheduled.", "job_id": job_id})
    except Exception as e:
        print(f"❌ Error scheduling single promo API job: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": "Failed to schedule automation task"}), 500

# --- Estimation Endpoints ---
@app.route('/api/estimate/auto_cost', methods=['POST'])
def estimate_auto_cost():
    """Estimate total cost for Auto Promo based on profile settings and CSV rates.
    Payload: { profile_name?: str, profile_data?: dict, platform?: str }
    For random quantities, uses the average of min/max as expected quantity.
    """
    data = request.json or {}
    profile_name = data.get('profile_name')
    profile_data = data.get('profile_data')
    platform_filter = (data.get('platform') or '').strip() or None

    # Resolve profile_data
    if not profile_data:
        if not profile_name:
            return jsonify({"success": False, "error": "Missing profile_name or profile_data"}), 400
        profiles = profile_manager.load_profiles()
        if profile_name not in profiles:
            return jsonify({"success": False, "error": f"Profile '{profile_name}' not found"}), 404
        profile_data = profiles[profile_name]

    import services_catalog as sc

    engagements = list(profile_data.get('engagements') or [])
    loop_settings = dict(profile_data.get('loop_settings') or {})
    main_loops = int(loop_settings.get('loops') or 1)

    breakdown = []
    total_cost = 0.0

    def expected_qty(eng_row):
        if eng_row.get('use_random_quantity'):
            try:
                mn = int(eng_row.get('min_quantity') or 0)
                mx = int(eng_row.get('max_quantity') or 0)
                if mn > 0 and mx >= mn:
                    return int((mn + mx) / 2)
            except Exception:
                return 0
            return 0
        try:
            qf = int(eng_row.get('fixed_quantity') or 0)
            return max(0, qf)
        except Exception:
            return 0

    for loop_num in range(1, main_loops + 1):
        for eng in engagements:
            eng_type = (eng.get('type') or '').strip()
            if not eng_type:
                continue
            # Per-engagement participation limit
            participation_loops = int(eng.get('loops') or 1)
            if loop_num > participation_loops:
                continue

            platform = (eng.get('platform') or '').strip() or 'Instagram'
            if platform_filter and platform != platform_filter:
                continue

            qty = expected_qty(eng)
            if qty <= 0:
                continue

            svc = sc.select_service(platform, eng_type)
            if not svc:
                continue
            rate = svc.get('rate_per_1k')
            try:
                rate_f = float(rate) if rate is not None else None
            except Exception:
                rate_f = None
            cost = (rate_f * qty / 1000.0) if rate_f is not None else None
            if cost is not None:
                total_cost += cost
            breakdown.append({
                'platform': platform,
                'engagement': eng_type,
                'quantity': qty,
                'rate_per_1k': rate_f,
                'cost': None if cost is None else round(cost, 6)
            })

    # Calculate per-provider cost totals
    provider_costs = {}
    all_providers = ['justanotherpanel', 'peakerr', 'smmkings', 'mysocialsboost', 'morethanpanel']
    
    for provider in all_providers:
        provider_total = 0.0
        for loop_num in range(1, main_loops + 1):
            for eng in engagements:
                eng_type = (eng.get('type') or '').strip()
                if not eng_type:
                    continue
                participation_loops = int(eng.get('loops') or 1)
                if loop_num > participation_loops:
                    continue
                platform = (eng.get('platform') or '').strip() or 'Instagram'
                if platform_filter and platform != platform_filter:
                    continue
                qty = expected_qty(eng)
                if qty <= 0:
                    continue
                # Get services for this platform/engagement and find one from this provider
                services = sc.list_services(platform, eng_type)
                provider_svc = None
                for s in services:
                    p = (s.get('provider') or s.get('provider_label') or '').lower().replace(' ', '')
                    if p == provider or p == provider.replace(' ', ''):
                        provider_svc = s
                        break
                if provider_svc:
                    rate = provider_svc.get('rate_per_1k')
                    try:
                        rate_f = float(rate) if rate is not None else None
                    except Exception:
                        rate_f = None
                    if rate_f is not None:
                        provider_total += (rate_f * qty / 1000.0)
        provider_costs[provider] = round(provider_total, 6) if provider_total > 0 else None

    return jsonify({
        'success': True,
        'total_cost': round(total_cost, 6),
        'breakdown': breakdown,
        'loops': main_loops,
        'provider_costs': provider_costs
    })

# --- API Route to check job status --- (Used by Run page for manual/profile promos)
@app.route('/api/job_status/<path:job_id>', methods=['GET'])
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

# --- API Route: Live Order Status for History ---
@app.route('/api/history/live_status', methods=['GET'])
def get_history_live_status():
    try:
        # Optional: filter by specific job IDs (comma-separated or repeated job_id params)
        q_job_ids = (request.args.get('job_ids') or '').strip()
        job_ids = []
        if q_job_ids:
            job_ids = [jid for jid in [s.strip() for s in q_job_ids.split(',')] if jid]
        else:
            job_ids = [jid for jid in request.args.getlist('job_id') if jid]

        # Limit to last N entries when no explicit job IDs are provided
        N = int(request.args.get('limit', 30))
        N = max(1, min(N, 50))

        history = history_manager.load_history()
        results = []

        def normalize_status(s: str) -> str:
            if not s:
                return 'unknown'
            sl = s.strip().lower()
            if 'progress' in sl or 'processing' in sl:
                return 'processing'
            if 'pending' in sl:
                return 'pending'
            if 'completed' in sl or 'success' in sl or 'finished' in sl:
                return 'completed'
            if 'partial' in sl:
                return 'partial'
            if 'cancel' in sl:
                return 'canceled'
            if 'fail' in sl or 'error' in sl:
                return 'failed'
            return s

        # Build index for fast lookup
        idx = { str(e.get('job_id')): e for e in history if e.get('job_id') }

        # Determine which entries to process
        entries_to_process = []
        if job_ids:
            for jid in job_ids:
                e = idx.get(str(jid))
                if e:
                    entries_to_process.append(e)
        else:
            entries_to_process = history[:N]

        for entry in entries_to_process:
            job_id = entry.get('job_id')
            if not job_id:
                continue
            items = []
            # Single order entries
            provider = entry.get('provider')
            order_id = entry.get('order_id')
            if provider and order_id:
                try:
                    res = providers_api.order_status(provider, int(order_id))
                    items.append({
                        'provider': provider,
                        'order_id': order_id,
                        'raw': res,
                        'status': normalize_status(str(res.get('status') if isinstance(res, dict) else 'unknown'))
                    })
                except Exception as e:
                    items.append({'provider': provider, 'order_id': order_id, 'error': str(e), 'status': 'error'})
            # Multi-order (profile) entries
            for ord_item in entry.get('orders', []) or []:
                p = ord_item.get('provider')
                oid = ord_item.get('order_id')
                if p and oid:
                    try:
                        res = providers_api.order_status(p, int(oid))
                        items.append({
                            'provider': p,
                            'order_id': oid,
                            'raw': res,
                            'status': normalize_status(str(res.get('status') if isinstance(res, dict) else 'unknown'))
                        })
                    except Exception as e:
                        items.append({'provider': p, 'order_id': oid, 'error': str(e), 'status': 'error'})

            # Aggregate status for the row
            agg = 'unknown'
            statuses = [i.get('status') for i in items]
            if statuses:
                if any(s in ('failed','error','canceled') for s in statuses):
                    agg = 'failed'
                elif any(s in ('processing','pending','partial') for s in statuses):
                    if 'processing' in statuses:
                        agg = 'processing'
                    elif 'partial' in statuses:
                        agg = 'partial'
                    else:
                        agg = 'pending'
                elif all(s == 'completed' for s in statuses):
                    agg = 'completed'
            elif entry.get('status'):
                agg = normalize_status(str(entry.get('status')))

            results.append({'job_id': job_id, 'aggregate_status': agg, 'items': items})

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- API Route: List Active Jobs (pending/running/stopping) ---
@app.route('/api/jobs/active', methods=['GET'])
def list_active_jobs():
    try:
        active = []
        terminal = {'success', 'failed', 'stopped'}
        for jid, info in job_statuses.items():
            status = (info.get('status') or '').lower()
            if status not in terminal:
                active.append({
                    'job_id': jid,
                    'status': status,
                    'message': info.get('message'),
                    'label': info.get('label', ''),
                    'link': info.get('link', ''),
                    'container_id': info.get('container_id', 'auto-promo-jobs')
                })
        return jsonify({'success': True, 'jobs': active})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- API Route: Request stop of a job ---
@app.route('/api/stop_promo', methods=['POST'])
def stop_promo_route():
    data = request.json or {}
    job_id = data.get('job_id')
    if not job_id:
        return jsonify({'success': False, 'error': 'Missing job_id'}), 400
    # Mark stop request
    requested_stops.add(job_id)
    # Update visible status if tracked
    if job_id in job_statuses:
        job_statuses[job_id]['status'] = 'stopped'
        job_statuses[job_id]['message'] = 'Stopped by user request.'
    return jsonify({'success': True})

 

# --- Debug API Endpoints (Scaffold) ---
def _dbg_response(ok: bool, log: str):
    return jsonify({"success": ok, "log": log})

"""Debug Browser Manager
All Playwright sync calls must occur on the SAME thread/greenlet they were created on.
We create a dedicated worker thread that owns Playwright+Chrome persistent context.
Endpoints post actions to this worker and wait for the result, avoiding greenlet errors.
"""
import threading, queue, traceback as _tb

class _DebugWorker:
    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._started = threading.Event()
        self._stopping = threading.Event()
        self._pl = None
        self._ctx = None
        self._page = None

    def start(self):
        if not self._t.is_alive():
            self._t.start()
            self._started.wait(timeout=10)

    def stop(self):
        try:
            self._q.put(("__stop__", None))
            self._t.join(timeout=10)
        except Exception:
            pass

    def run_action(self, func, timeout=60):
        """func signature: func(context, page) -> (ok: bool, log: str)"""
        reply = queue.Queue()
        self._q.put((func, reply))
        try:
            ok, log = reply.get(timeout=timeout)
            return ok, log
        except queue.Empty:
            return False, "Debug worker timed out while executing action."

    def _ensure_ctx(self):
        # Create Playwright and persistent context if missing or closed
        if self._pl is None:
            self._pl = sync_playwright().start()
        need_new = False
        if self._ctx is None:
            need_new = True
        else:
            try:
                _ = self._ctx.pages
            except Exception:
                need_new = True
        if need_new:
            self._ctx = self._pl.chromium.launch_persistent_context(
                user_data_dir=automation_runner.CHROME_USER_DATA_DIR,
                channel="chrome",
                headless=False,
                slow_mo=50,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self._page = self._ctx.new_page()
        if self._page is None:
            self._page = self._ctx.new_page()
        else:
            try:
                _ = self._page.url
            except Exception:
                self._page = self._ctx.new_page()

    def _close_ctx(self):
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._pl:
                self._pl.stop()
        except Exception:
            pass
        self._ctx = None
        self._page = None
        self._pl = None

    def _run(self):
        self._started.set()
        while not self._stopping.is_set():
            item, reply = self._q.get()
            if item == "__stop__":
                self._stopping.set()
                break
            try:
                self._ensure_ctx()
                ok, log = item(self._ctx, self._page)
                reply.put((ok, log))
            except Exception as e:
                reply.put((False, f"Worker exception: {e}\n{_tb.format_exc()}"))
        # Cleanup
        self._close_ctx()

_debug_worker = _DebugWorker()
_debug_worker.start()

@app.route('/api/debug/open_browser', methods=['POST'])
def dbg_open_browser():
    try:
        def action(ctx, page):
            page.goto('https://dogehype.com/login', wait_until='domcontentloaded', timeout=20000)
            return True, "Chrome launched (persistent debug session) and left open. Close it manually."
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error: {e}")

@app.route('/api/debug/nav_login', methods=['POST'])
def dbg_nav_login():
    # Always navigate to the standard Dogehype login URL
    url = 'https://dogehype.com/login'
    try:
        def action(ctx, page):
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            return True, f"Navigated to: {url}"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error navigating: {e}")

@app.route('/api/debug/login', methods=['POST'])
def dbg_full_login():
    """Run the same login flow used by automations (automation_runner.login_to_dogehype)."""
    try:
        def action(ctx, page):
            try:
                p, balance = automation_runner.login_to_dogehype(page, ctx)
                return True, f"Login flow completed. URL: {p.url}. Balance: {balance or 'N/A'}"
            except Exception as e:
                return False, f"Login flow failed: {e}"
        ok, log = _debug_worker.run_action(action, timeout=120)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error running full login: {e}")

@app.route('/api/debug/select_google', methods=['POST'])
def dbg_select_google():
    # Attempt to click a Google sign-in button on Dogehype login
    try:
        def action(ctx, page):
            if 'dogehype.com/login' not in (page.url or ''):
                page.goto('https://dogehype.com/login', wait_until='domcontentloaded', timeout=20000)
            selectors = [
                "text=Google",
                "button:has-text('Google')",
                "[data-provider='google']",
                "a[href*='google']",
                "div[role='button']:has-text('Google')",
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if el and el.count() >= 0:
                        el.click(timeout=3000)
                        return True, "Clicked Google provider"
                except Exception:
                    continue
            return False, "Google provider not found"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error selecting Google: {e}")

@app.route('/api/debug/enter_email', methods=['POST'])
def dbg_enter_email():
    # Use TARGET_EMAIL from environment; ignore any client payload
    email = (os.getenv('TARGET_EMAIL') or '').strip()
    try:
        def action(ctx, page):
            page.goto('https://accounts.google.com/signin/v2/identifier', wait_until='domcontentloaded', timeout=20000)
            if not email:
                raise Exception("TARGET_EMAIL is not set in environment.")
            page.fill("input[type='email']", email, timeout=5000)
            return True, f"Email filled: {email}"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error entering email: {e}")

@app.route('/api/debug/continue_email', methods=['POST'])
def dbg_continue_email():
    try:
        def action(ctx, page):
            if 'accounts.google.com' not in (page.url or ''):
                page.goto('https://accounts.google.com/signin/v2/identifier', wait_until='domcontentloaded', timeout=20000)
            page.click('#identifierNext', timeout=5000)
            return True, "Clicked continue after email"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error clicking continue after email: {e}")

@app.route('/api/debug/enter_password', methods=['POST'])
def dbg_enter_password():
    # Use TARGET_PASSWORD if present; otherwise fallback to MAIL_PASSWORD from environment
    pwd = os.getenv('TARGET_PASSWORD') or os.getenv('MAIL_PASSWORD') or ''
    try:
        def action(ctx, page):
            page.goto('https://accounts.google.com/signin/v2/sl/pwd', wait_until='domcontentloaded', timeout=20000)
            if not pwd:
                raise Exception("TARGET_PASSWORD/MAIL_PASSWORD is not set in environment.")
            page.fill("input[type='password']", pwd, timeout=5000)
            return True, "Password filled"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error entering password: {e}")

@app.route('/api/debug/continue_password', methods=['POST'])
def dbg_continue_password():
    try:
        def action(ctx, page):
            if 'accounts.google.com' not in (page.url or ''):
                page.goto('https://accounts.google.com/signin/v2/sl/pwd', wait_until='domcontentloaded', timeout=20000)
            page.click('#passwordNext', timeout=5000)
            return True, "Clicked continue after password"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error clicking continue after password: {e}")

@app.route('/api/debug/verify_dashboard', methods=['POST'])
def dbg_verify_dashboard():
    try:
        def action(ctx, page):
            page.goto('https://dogehype.com/dashboard', wait_until='domcontentloaded', timeout=20000)
            ok = 'dashboard' in (page.url or '').lower()
            return ok, f"Dashboard URL: {page.url if ok else 'Not loaded'}"
        ok, log = _debug_worker.run_action(action)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error verifying dashboard: {e}")

@app.route('/api/debug/submit_promo', methods=['POST'])
def dbg_submit_promo():
    data = request.json or {}
    platform = (data.get('platform') or 'Instagram').strip()
    engagement = (data.get('engagement') or '').strip()
    link = (data.get('link') or '').strip()
    quantity = data.get('quantity')

    # Validate inputs
    if not engagement or not link:
        return _dbg_response(False, f"Invalid inputs: engagement={engagement}, link={link}")
    try:
        qty = int(quantity)
    except Exception:
        return _dbg_response(False, f"Invalid quantity: {quantity}")
    if qty <= 0:
        return _dbg_response(False, f"Quantity must be positive: {qty}")

    # Enforce minimums (same as main Single Promo)
    min_qty = config.MINIMUM_QUANTITIES.get((platform, engagement))
    if min_qty is not None and qty < min_qty:
        return _dbg_response(False, f"Minimum quantity for {platform} {engagement} is {min_qty}.")

    try:
        def action(ctx, page):
            p, _ = automation_runner.login_to_dogehype(page, ctx)
            automation_runner.ensure_on_dashboard(p)
            automation_runner.place_order(p, platform, engagement, link, qty)
            return True, f"Submitted promo: {engagement} x{qty} for {link} on {platform}"
        ok, log = _debug_worker.run_action(action, timeout=180)
        return _dbg_response(ok, log)
    except Exception as e:
        return _dbg_response(False, f"Error submitting promo: {e}")

@app.route('/api/debug/close', methods=['POST'])
def dbg_close():
    try:
        _debug_worker.stop()
        # Recreate worker so future clicks work again
        globals()['_debug_worker'] = _DebugWorker()
        _debug_worker.start()
        return _dbg_response(True, "Closed debug browser context.")
    except Exception as e:
        return _dbg_response(False, f"Error closing debug context: {e}")

# --- App Startup --- 
if __name__ == '__main__':
    # Ensure the app listens on the port specified by Render's PORT env var
    port = int(os.environ.get("PORT", 10000))
    print(f"Attempting to serve Flask app on host 0.0.0.0, port {port} using Waitress...")
    serve(app, host="0.0.0.0", port=port)