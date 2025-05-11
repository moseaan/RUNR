import json
import os
import datetime
from playwright.sync_api import sync_playwright, Page, expect, BrowserContext, Error as PlaywrightError
import time
import uuid # Import uuid to generate unique IDs for targets

# Assuming USER_DATA_DIR is defined appropriately, maybe import from automation_runner or config
try:
    # If USER_DATA_DIR is in automation_runner (preferred)
    from automation_runner import USER_DATA_DIR
except ImportError:
    # Fallback if it's defined elsewhere or needs direct path
    print("Warning: USER_DATA_DIR not found in automation_runner, using relative path.")
    USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "dogehype_session")

CONFIG_FILE = "monitoring_config.json"
DEFAULT_POLLING_INTERVAL = 300 # Default 5 minutes

def load_monitoring_config():
    """Loads the monitoring configuration from JSON file."""
    default_config = {
        "polling_interval_seconds": DEFAULT_POLLING_INTERVAL,
        "targets": []
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure all top-level keys are present
                config.setdefault("polling_interval_seconds", DEFAULT_POLLING_INTERVAL)
                config.setdefault("targets", [])
                # Optional: Validate structure of each target? For now, assume correct.
                return config
        else:
            # Create the file with defaults if it doesn't exist
            save_monitoring_config(default_config)
            return default_config
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading monitoring config from {CONFIG_FILE}: {e}. Using defaults.")
        # Attempt to save defaults if loading failed badly
        try:
            save_monitoring_config(default_config)
        except Exception as save_e:
             print(f"Failed to save default monitoring config after load error: {save_e}")
        return default_config

def save_monitoring_config(config_data):
    """Saves the monitoring configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Monitoring config saved to {CONFIG_FILE}")
        return True
    except IOError as e:
        print(f"Error saving monitoring config to {CONFIG_FILE}: {e}")
        return False

# --- Helper Functions for Target Management ---

def add_monitoring_target(target_username, promotion_profile_name):
    """Adds a new monitoring target to the configuration."""
    config_data = load_monitoring_config()
    target_id = str(uuid.uuid4()) # Generate a unique ID
    new_target = {
        "id": target_id,
        "target_username": target_username,
        "promotion_profile_name": promotion_profile_name,
        "last_pushed_post_url": None,
        "is_running": True, # Start as running by default
        "last_checked_timestamp": None
    }
    config_data["targets"].append(new_target)
    if save_monitoring_config(config_data):
        return new_target # Return the added target with its ID
    else:
        return None

def update_monitoring_target(target_id, updates):
    """Updates an existing monitoring target by its ID."""
    config_data = load_monitoring_config()
    target_found = False
    for target in config_data["targets"]:
        if target.get("id") == target_id:
            target.update(updates) # Apply changes from the updates dictionary
            target_found = True
            break
    if not target_found:
        print(f"Error: Target ID '{target_id}' not found for update.")
        return False
    
    return save_monitoring_config(config_data)


def remove_monitoring_target(target_id):
    """Removes a monitoring target by its ID."""
    config_data = load_monitoring_config()
    initial_length = len(config_data["targets"])
    config_data["targets"] = [t for t in config_data["targets"] if t.get("id") != target_id]
    
    if len(config_data["targets"]) == initial_length:
         print(f"Warning: Target ID '{target_id}' not found for removal.")
         return False # Indicate not found or no change
         
    return save_monitoring_config(config_data)

def get_monitoring_target(target_id):
    """Gets a specific monitoring target by its ID."""
    config_data = load_monitoring_config()
    for target in config_data["targets"]:
        if target.get("id") == target_id:
            return target
    return None # Not found

# --- Placeholder for Scraping Logic ---
def get_latest_post_info(username: str):
    """
    Uses Playwright to scrape the latest post URL and its timestamp for a given username.
    Returns: (latest_post_url, post_datetime_object) or (None, None) if error/not found.
    """
    print(f"[Monitor] Checking profile: {username}")
    latest_post_url = None
    post_datetime = None
    
    # Ensure user data directory exists
    abs_user_data_dir = os.path.abspath(USER_DATA_DIR)
    if not os.path.exists(abs_user_data_dir):
        print(f"[Monitor] User Data Directory does not exist, creating: {abs_user_data_dir}")
        os.makedirs(abs_user_data_dir)
        
    context = None # Define context outside try block for finally
    try:
        with sync_playwright() as p:
            # Using persistent context might help with login state
            print(f"[Monitor] Launching browser with context: {abs_user_data_dir}")
            context = p.chromium.launch_persistent_context(
                abs_user_data_dir, 
                headless=False, # Start headless=False for debugging selectors
                slow_mo=50 # Add slight delay for stability
            )
            page = context.new_page()
            
            # Navigate to profile page
            profile_url = f"https://www.instagram.com/{username}/"
            print(f"[Monitor] Navigating to {profile_url}")
            page.goto(profile_url, wait_until='domcontentloaded', timeout=45000)
            
            # --- Handle Potential Modals & Login Redirect ---
            page.wait_for_timeout(2000) # Short wait for modals like restrictions
            
            # Check for restriction modal (adjust selector if needed)
            restriction_modal_selector = 'div[role="dialog"]:has-text("We added a restriction")'
            restriction_modal = page.locator(restriction_modal_selector)
            if restriction_modal.is_visible():
                print("[Monitor] Account restriction modal detected. Attempting to close.")
                close_button = restriction_modal.locator('button[aria-label="Close"]')
                if close_button.is_visible():
                    close_button.click()
                    print("[Monitor] Clicked modal close button.")
                    page.wait_for_timeout(1000) # Wait a bit after closing
                else:
                    print("[Monitor] Could not find close button on restriction modal.")
                    # Decide how to proceed - maybe fail here? For now, continue cautiously.
            
            # Check for login redirect AFTER navigation and modal handling
            if "/accounts/login/" in page.url.lower():
                print("[Monitor] *** Error: Redirected to login page. Session might be invalid or account requires login. Aborting check. ***")
                # Optionally, clear cookies or take other actions?
                # context.clear_cookies() 
                return None, None
                
            # --- !! CRITICAL PART: Finding Selectors !! ---
            # These selectors WILL likely break and need adjustment.
            # Strategy: Find the container for posts, then the first link within it.
            
            # Wait for the main content area (might change) - Ensure it's loaded AFTER modal handling
            print("[Monitor] Waiting for main content area selector: main")
            try:
                page.wait_for_selector('main', timeout=20000) 
                print("[Monitor] Main content area loaded.")
            except PlaywrightError as e:
                 print(f"[Monitor] *** Error: Failed to find 'main' content area after timeout: {e}. Page structure might have changed or failed to load. ***")
                 return None, None # Cannot proceed without main content

            # Might need to target based on parent structure.
            # --- NEW SELECTOR --- Try finding the first link starting with /p/ inside the article tag
            first_post_link_selector = "article a[href^='/p/']" # Revised selector
            
            print(f"[Monitor] Defining locator for first post link: {first_post_link_selector}")
            first_post_link_locator = page.locator(first_post_link_selector).first
            
            print(f"[Monitor] Waiting for locator to be visible: {first_post_link_selector} (first match)")
            expect(first_post_link_locator).to_be_visible(timeout=25000) # Increased timeout slightly
            
            latest_post_href = first_post_link_locator.get_attribute('href')

            # --- Click the found post link and get URL --- 
            try:
                print(f"[Monitor] Clicking the first post link...")
                first_post_link_locator.click()
                # Wait for navigation to the post page after the click
                print("[Monitor] Waiting for post page navigation to complete...")
                page.wait_for_load_state('domcontentloaded', timeout=30000) 
                # Get the URL from the browser bar after navigation
                latest_post_url = page.url 
                print(f"[Monitor] Current URL after click: {latest_post_url}")
                # Basic check if the URL looks like a post URL
                if "/p/" not in latest_post_url:
                    print("[Monitor] *** Warning: URL after click doesn't look like a post URL. Proceeding cautiously. ***")
            except PlaywrightError as click_e:
                print(f"[Monitor] *** Error clicking post link or waiting for navigation: {click_e} ***")
                # Screenshot?
                # page.screenshot(path="error_screenshot_click.png")
                return None, None

            # --- Check for login redirect AGAIN after navigating to post (via click) ---
            if "/accounts/login/" in latest_post_url.lower(): # Check the URL obtained after click
                print("[Monitor] *** Error: Redirected to login page when trying to view post. Aborting check. ***")
                return None, None

            # --- Get Timestamp from Post Page ---
            # Selector for the timestamp (looking for <time> tag with datetime attr)
            time_selector = "time[datetime]" # Ideal case
            print(f"[Monitor] Waiting for timestamp selector: {time_selector}")
            # Add try-except around timestamp finding
            try:
                time_locator = page.locator(time_selector).first 
                # Use a shorter timeout for the time element as it should load relatively quickly
                expect(time_locator).to_be_attached(timeout=15000) 
            except PlaywrightError as e:
                 print(f"[Monitor] *** Error: Failed to find or wait for the timestamp ({time_selector}): {e} ***")
                 # Screenshot?
                 # page.screenshot(path="error_screenshot_timestamp.png")
                 return None, None # Fail if timestamp not found

            datetime_str = time_locator.get_attribute('datetime')
            if datetime_str:
                print(f"[Monitor] Found datetime attribute: {datetime_str}")
                # Parse ISO 8601 string (like 2023-10-27T15:04:01.000Z)
                # Need to handle the 'Z' (Zulu/UTC) timezone indicator
                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1] + '+00:00'
                post_datetime = datetime.datetime.fromisoformat(datetime_str)
                print(f"[Monitor] Parsed timestamp: {post_datetime}")
            else:
                 # TODO: Implement fallback parsing for relative times ('1h', '15m') if needed.
                 # This is complex and less reliable. Start without it.
                 print("[Monitor] Could not find 'datetime' attribute on <time> tag. Timestamp parsing failed.")
                 # Set post_datetime to None if parsing fails - handled by initialization

            print("[Monitor] Scraping finished successfully.")

    except PlaywrightError as pe:
         print(f"[Monitor] Playwright error checking {username}: {pe}")
         # Add screenshot on general Playwright errors too?
         # try:
         #    page.screenshot(path="error_screenshot_playwright.png")
         # except: pass # Ignore screenshot error if page/context is bad
         post_datetime = None # Ensure None is returned on error
         latest_post_url = None
    except Exception as e:
        print(f"[Monitor] General error checking {username}: {e}")
        import traceback
        traceback.print_exc()
        post_datetime = None # Ensure None is returned on error
        latest_post_url = None
    finally:
        if context:
            try:
                print("[Monitor] Closing browser context.")
                context.close()
            except Exception as close_err:
                print(f"[Monitor] Error closing context: {close_err}")
                
    # Return the found URL and the datetime object (or None if errors occurred)
    return latest_post_url, post_datetime

# --- Example usage (for testing) ---
# if __name__ == '__main__':
#     test_username = "instagram" # Replace with a public profile for testing
#     url, dt = get_latest_post_info(test_username)
#     if url and dt:
#         print(f"\nLatest post for {test_username}:")
#         print(f"  URL: {url}")
#         print(f"  Time: {dt} (UTC: {dt.astimezone(datetime.timezone.utc)})")
#         # Check time difference
#         now_utc = datetime.datetime.now(datetime.timezone.utc)
#         time_diff = now_utc - dt.astimezone(datetime.timezone.utc)
#         print(f"  Time since posted: {time_diff}")
#         if time_diff < datetime.timedelta(hours=1):
#             print("  Post is within the last hour!")
#         else:
#             print("  Post is older than 1 hour.")
#     else:
#         print(f"\nCould not get latest post info for {test_username}.") 