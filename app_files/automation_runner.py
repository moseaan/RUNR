# automation_runner.py
import os
import re
import time
import random
from playwright.sync_api import sync_playwright, Page, expect, BrowserContext, Error as PlaywrightError
from dotenv import load_dotenv
import config # Assuming config.py has necessary constants like TARGET_WEBSITE_URL
from config import CATEGORY_MAPPING # Import mapping directly
from profile_editor import INSTAGRAM_ENGAGEMENT_TYPES # Get engagement types
import datetime # Import datetime
import traceback # For detailed error logging
from typing import Tuple, Optional

# Gmail API specific imports
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import html # For decoding HTML entities in email body

# Load environment variables from .env file
load_dotenv()

# Gmail API Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly'] # Read-only is enough
CREDENTIALS_FILE = 'credentials.json'  # Path to your credentials.json
TOKEN_PICKLE_FILE = 'token.pickle' # Stores user's access and refresh tokens. Changed from .json to .pickle for consistency with original examples, though google-auth now uses JSON.

# --- Gmail API Helper Functions ---
def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PICKLE_FILE, SCOPES)
        except Exception as e:
            print(f"Error loading token from {TOKEN_PICKLE_FILE}: {e}. Will attempt to re-authenticate.")
            creds = None # Ensure creds is None if loading fails
            try:
                os.remove(TOKEN_PICKLE_FILE) # Remove corrupted/invalid token file
                print(f"Removed potentially corrupted token file: {TOKEN_PICKLE_FILE}")
            except OSError as e_remove:
                print(f"Error removing token file {TOKEN_PICKLE_FILE}: {e_remove}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing Gmail API token...")
            try:
                creds.refresh(Request())
            except Exception as e_refresh:
                print(f"Error refreshing token: {e_refresh}. Will attempt full re-authentication.")
                creds = None # Force re-authentication
        if not creds or not creds.valid: # Check again if refresh failed or no creds initially
            print(f"Gmail credentials not found or invalid. Running auth flow using {CREDENTIALS_FILE}...")
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Gmail API credentials file ('{CREDENTIALS_FILE}') not found. "
                    "Please download it from Google Cloud Console and place it in the root directory or specified path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_PICKLE_FILE, 'w') as token_file:
            token_file.write(creds.to_json())
        print(f"Gmail token saved to {TOKEN_PICKLE_FILE}")

    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Gmail API service created successfully.")
        return service
    except HttpError as error:
        print(f'An error occurred building Gmail service: {error}')
        raise # Re-raise to be caught by calling function
    except Exception as e:
        print(f"An unexpected error occurred getting Gmail service: {e}")
        raise # Re-raise

def search_dogehype_email(service, max_retries=5, retry_delay=10):
    query = 'from:info@viewzbot.com'
    
    for attempt in range(max_retries):
        try:
            print(f"Searching for Dogehype email (attempt {attempt + 1}/{max_retries}). Query: '{query}' (Searching all mail)")
            results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            print(f"DEBUG: Raw Gmail API search results for query '{query}': {results}")
            messages = results.get('messages', [])
            
            if messages:
                print(f"Found Dogehype email: {messages[0]['id']}")
                return messages[0]['id']

            print(f"No Dogehype email found yet. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

        except HttpError as error:
            print(f'An HTTP error occurred while searching email: {error}')
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay)
        except Exception as e:
            print(f"An unexpected error occurred during email search: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay)
            
    print("Could not find Dogehype verification email after multiple retries.")
    return None

def get_verification_link_from_email(service, message_id):
    try:
        print(f"Fetching email content for message ID: {message_id}...")
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = message.get('payload')
        
        if not payload:
            print("No payload in email message.")
            return None

        parts = payload.get('parts')
        data = ""

        if parts:
            for part in parts:
                if part.get('mimeType') == 'text/html':
                    data = part.get('body').get('data')
                    break
                elif part.get('mimeType') == 'text/plain' and not data:
                    data = part.get('body').get('data')
            if not data and parts and parts[0].get('body'): 
                 data = parts[0].get('body').get('data')
        elif payload.get('body'):
            data = payload.get('body').get('data')

        if not data:
            print("Could not find email body data.")
            return None

        decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        email_body_html = html.unescape(decoded_data)
        
        # print(f"[DEBUG] Decoded email body HTML (first 3000 chars):\n{email_body_html[:3000]}")

        # Step 1: Find all https links in the email body. 
        # Regex simplified to avoid linter issues with character sets.
        # It relies heavily on the Python filtering loop below for accuracy.
        candidate_links_pattern = r'href\s*=\s*(["\'])(https://.+?)\1|(https://.+?)' # Non-greedy match
        matches = re.finditer(candidate_links_pattern, email_body_html)
        
        all_found_links = []
        for match in matches:
            # Group 2 for href links, Group 3 for standalone links
            url = match.group(2) or match.group(3)
            if url:
                all_found_links.append(url) # Will be further cleaned in the loop below

        print(f"[DEBUG] Found {len(all_found_links)} potential HTTPS links using simplified regex: {all_found_links}")

        # Step 2: Iterate and validate candidates to find the correct MojoAuth link.
        # The .strip() in this loop is now very important due to the broad regex.
        for raw_link in all_found_links:
            link = raw_link.strip('<>"\'()[]{}') # Clean common wrapping chars

            # Primary target: MojoAuth link
            if (
                link.startswith("https://api.mojoauth.com/users/magiclink/verify") and
                "api_key=" in link and
                "magictext=" in link and
                "redirect_url=" in link and
                "dogehype.com" in link and # Ensure dogehype is part of the redirect
                ".png" not in link and ".jpg" not in link and ".gif" not in link # Avoid image links explicitly
            ):
                print(f"Found and validated MojoAuth magic link: {link}")
                return link

        # Fallback: If no specific MojoAuth link, check for other Dogehype links (less likely)
        for raw_link in all_found_links:
            link = raw_link.strip('<>"\'()[]{}')
            if (
                link.startswith("https://dogehype.com/verify") and 
                "state_id=" in link and
                ".png" not in link and ".jpg" not in link and ".gif" not in link
            ):
                print(f"Found Dogehype verification link (fallback): {link}")
                return link
            
            if (
                link.startswith("https://dogehype.com/dashboard") and 
                "state_id=" in link and
                "magiclink" not in link and 
                "verify" not in link and
                ".png" not in link and ".jpg" not in link and ".gif" not in link
            ):
                print(f"Found Dogehype dashboard link with state_id (deep fallback): {link}")
                return link

        print(f"Could not find a suitable verification link after all checks. Email sample (first 1000 chars):\n{email_body_html[:1000]}")
        with open("debug_email_body.html", "w", encoding="utf-8") as f:
            f.write(email_body_html)
        print("Saved full email body to debug_email_body.html for inspection.")
        return None

    except HttpError as error:
        print(f'An HTTP error occurred while fetching email content: {error}')
        return None
    except Exception as e:
        print(f"An unexpected error occurred while extracting link: {e}")
        traceback.print_exc()
        return None
# --- End of Gmail API Helper Functions ---

# Get credentials and URL
TARGET_EMAIL = os.getenv("TARGET_EMAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") # This will no longer be used for login but might be used elsewhere
DOGEHYPE_URL = config.TARGET_WEBSITE_URL
MAIL_URL = "https://www.mail.com/" # This will no longer be used

def login_to_dogehype(page: Page, context: BrowserContext) -> Page:
    if not TARGET_EMAIL: # MAIL_PASSWORD is no longer needed for this function
        raise ValueError("Missing TARGET_EMAIL in .env file for Dogehype login.")

    print("Starting Dogehype login process using Gmail API...")
    print(f"Navigating to {DOGEHYPE_URL}")
    page.goto(DOGEHYPE_URL, wait_until='load', timeout=60000)
    
    # Check 1: Already logged in?
    try:
        print("Quick check if already on dashboard (looking for: '+ Add Funds' button)")
        expect(page.get_by_role("button", name="+ Add Funds")).to_be_visible(timeout=5000) # Short timeout
        print("Already logged into Dogehype and on dashboard!")
        return page
    except Exception:
        print("Not on dashboard (initial check), proceeding with login flow.")

    # Try to click Sign Up/Sign In if visible, then check for dashboard
    try:
        sign_up_button = page.get_by_role("banner").get_by_role("button", name=re.compile("Sign Up|Sign In", re.IGNORECASE)).first
        if sign_up_button.is_visible(timeout=5000): # Quick check for button visibility
            print("Found Sign Up/Sign In button, clicking it.")
            sign_up_button.click()
            # After clicking, check if we landed on dashboard
            try:
                print("Checking if on dashboard after Sign In click (looking for: '+ Add Funds' button)")
                expect(page.get_by_role("button", name="+ Add Funds")).to_be_visible(timeout=10000)
                print("Login successful via session cookie after clicking Sign In!")
                return page
            except Exception:
                print("Not on dashboard after Sign In click, proceeding to email input.")
        else:
            print("Sign Up/Sign In button not visible/found quickly. Proceeding to email input.")
    except Exception as e:
        # This catches errors if sign_up_button locator fails or .is_visible() fails, etc.
        print(f"Could not find or click Sign Up/Sign In button: {e}. Proceeding to email input.")

    # If not returned by now, proceed with email input
    email_input = page.get_by_role("textbox", name="Enter Your Email Address")
    expect(email_input).to_be_visible(timeout=15000)
    email_input.fill(TARGET_EMAIL)
    print(f"Filled email: {TARGET_EMAIL}")

    sign_in_button = page.get_by_role("button", name="Sign in without password")
    expect(sign_in_button).to_be_enabled(timeout=10000)
    sign_in_button.click()
    print("Clicked 'Sign in without password'. Verification email requested from Dogehype.")

    # --- Gmail API Integration for fetching verification link ---
    print("Attempting to fetch verification email via Gmail API...")
    try:
        gmail_service = get_gmail_service()
        if not gmail_service:
            raise ValueError("Failed to initialize Gmail API service.")

        verification_email_id = search_dogehype_email(gmail_service)
        if not verification_email_id:
            raise ValueError("Could not find Dogehype verification email via Gmail API.")

        magic_link = get_verification_link_from_email(gmail_service, verification_email_id)
        if not magic_link:
            raise ValueError("Could not extract verification link from Dogehype email.")
        
        print(f"Extracted magic link: {magic_link}")

        # Open the magic link. Consider if it opens a new tab or navigates the current one.
        # The old flow expected a popup. We'll create a new page to simulate this and keep context clean.
        print("Opening magic link in a new page/tab...")
        verification_page = context.new_page()
        verification_page.goto(magic_link, wait_until='load', timeout=90000)
        print("Navigated to magic link.")
        
        dashboard_page = verification_page # Assume this page will become the dashboard

        # The old flow had an intermediate mojoauth link sometimes.
        # Let's check if the current URL is mojoauth and if so, try to find a continue link.
        # This part needs to be adaptable as the UI of that intermediate page might vary.
        current_url = dashboard_page.url
        print(f"Current URL after magic link: {current_url}")

        if "mojoauth.com" in current_url:
            print("On a MojoAuth page, attempting to proceed to Dogehype dashboard...")
            try:
                # Try to find a link or button that explicitly says "Continue to Dogehype" or similar
                # This is a guess, actual selector might differ.
                # Look for a link that contains 'dogehype.com' in its href
                continue_link_to_dogehype = dashboard_page.locator('a[href*="dogehype.com"]').first
                
                if not continue_link_to_dogehype.is_visible(timeout=15000):
                     # Fallback: Try to find a generic "Continue" or "Proceed" button/link if the specific one isn't found
                    continue_link_to_dogehype = dashboard_page.get_by_role("link", name=re.compile("Continue|Proceed|Access|Go to Dashboard", re.IGNORECASE)).first
                    if not continue_link_to_dogehype.is_visible(timeout=5000): # Shorter timeout for fallback
                        # Last resort: try clicking a link that might be the one DogeHype uses
                        # This was the old specific text: page.get_by_text("https://api.mojoauth.com/")
                        # However, the link to click is likely one that leads *away* from mojoauth to dogehype
                        print("Specific MojoAuth continue link not found, trying a more generic one leading to Dogehype.")
                        # This might be risky if there are multiple such links.

                print("Clicking the identified link to proceed from MojoAuth...")
                mojo_page_url_before_click = dashboard_page.url
                continue_link_to_dogehype.click()
                print("Clicked intermediate link on MojoAuth page.")
                
                try:
                    dashboard_page.wait_for_url(lambda url: "dogehype.com/dashboard" in url or url != mojo_page_url_before_click, timeout=60000)
                    print(f"Navigated to new URL: {dashboard_page.url}")
                except PlaywrightError:
                    print("URL did not change as expected after clicking MojoAuth link, or timed out. Will attempt direct dashboard navigation if needed.")
            except Exception as e:
                print(f"Could not find or click intermediate mojoauth link (or error during process): {e}. Will attempt direct dashboard navigation if needed.")
        
        # After handling potential intermediate link, ensure we are on the dashboard.
        if "dogehype.com/dashboard" not in dashboard_page.url:
            print(f"Not on dashboard URL. Current URL: {dashboard_page.url}. Attempting to navigate to dashboard.")
            final_dashboard_url = "https://dogehype.com/dashboard"
            dashboard_page.goto(final_dashboard_url, wait_until='load', timeout=60000)
            print(f"Navigated to {final_dashboard_url}")

        print("Pausing briefly for dashboard elements to render...")
        dashboard_page.wait_for_timeout(5000) # Increased pause

        print("Verifying dashboard by looking for: '+ Add Funds' button")
        expect(dashboard_page.get_by_role("button", name="+ Add Funds")).to_be_visible(timeout=30000)
        print("Successfully loaded Dogehype dashboard page using Gmail API verification.")
        
        # Close the original page if it's different from the dashboard_page and still open
        if page != dashboard_page and not page.is_closed():
            print("Closing original Dogehype login page.")
            page.close()
            
        return dashboard_page

    except FileNotFoundError as e: # Specifically for credentials.json
        print(f"Gmail API Error: {e}")
        raise # Re-raise to be caught by the main error handlers
    except (HttpError, ValueError) as e: # Catch Gmail API specific errors and ValueErrors from helpers
        print(f"Error during Gmail API login flow: {e}")
        # page.screenshot(path="error_gmail_login_debug.png") # Optional: for debugging Playwright state
        raise # Re-raise to be caught by the main error handlers in run_single_automation/run_automation_profile
    except PlaywrightError as e:
        print(f"Playwright error during Gmail API login flow: {e}")
        # page.screenshot(path="error_playwright_gmail_login_debug.png")
        raise
    except Exception as e:
        print(f"Unexpected error during Gmail API login flow: {e}")
        # page.screenshot(path="error_unexpected_gmail_login_debug.png")
        traceback.print_exc()
        raise
    # No 'finally' block needed here to close mail_page as it's not used.
    # The dashboard_page (which might be the new page or the original page) is returned.
    # Context closing is handled by the calling functions (run_single_automation, run_automation_profile)

def place_order(page: Page, platform: str, engagement_type: str, link: str, quantity: int):
    # --- PASTE of place_order function from automation.py --- 
    # (Content identical to the function previously in automation.py, including the Views service change)
    print(f"\nAttempting to place order: {quantity} {engagement_type} for {platform} -> {link} using codegen selectors.")
    print(f"Clicking initial navigation link: Misc Services")
    nav_link = page.get_by_role("link", name="Misc Services")
    expect(nav_link).to_be_visible(timeout=15000)
    expect(nav_link).to_be_enabled(timeout=5000)
    print("Hovering over Misc Services link...")
    nav_link.hover()
    page.wait_for_timeout(200)
    print("Forcing click on Misc Services link...")
    nav_link.click(force=True)
    print("Waiting for page navigation to complete after click...")
    page.wait_for_load_state('domcontentloaded', timeout=30000)
    print("Waiting for Category dropdown to appear after navigation...")
    category_css_selector = "#app > div > div.content-wrapper > main > div.card.p-4.mt-3 > form > div.form-group > select"
    print(f"Using CSS Selector for Category Dropdown: {category_css_selector}")
    category_dropdown_locator = page.locator(category_css_selector)
    expect(category_dropdown_locator).to_be_visible(timeout=20000)
    print("Category dropdown found.")

    category_label = CATEGORY_MAPPING.get((platform, engagement_type))
    if not category_label:
        raise ValueError(f"Unsupported platform/engagement combination in CATEGORY_MAPPING: {platform} / {engagement_type}")

    print(f"Selecting category: '{category_label}' using CSS selector...")
    category_dropdown = category_dropdown_locator
    print("Ensuring dropdown is enabled...")
    expect(category_dropdown).to_be_enabled(timeout=5000)
    print(f"Attempting to select option: {category_label}")
    page.wait_for_timeout(300)
    category_dropdown.select_option(value=category_label)
    print("Category selected.")

    service_label = None
    if platform == "Instagram" and engagement_type == "Views":
        service_label = "Instagram - Views + Impressions + Profile Visits - [5M/D] - 💧 - $0.289 per 1000"
    elif platform == "Instagram" and engagement_type == "Reach/Impressions":
        service_label = "Instagram Reach + Impressions - [100K/Day] - 💧⛔️ - $0.17 per 1000"
    elif platform == "Instagram" and engagement_type == "Shares":
        service_label = "Instagram - Shares - [5M/D] - $0.85 per 1000"
    elif platform == "Instagram" and engagement_type == "Saves":
        service_label = "Instagram - Saves - [Instant] - [Real] - $0.034 per 1000"

    if service_label:
        service_dropdown_selector = "#app > div > div.content-wrapper > main > div.card.p-4.mt-3 > form > div:nth-child(2) > div > select"
        print(f"Locating service dropdown using CSS: {service_dropdown_selector}")
        service_dropdown = page.locator(service_dropdown_selector)
        expect(service_dropdown).to_be_visible(timeout=10000)
        print("Service dropdown found.")
        print(f"Selecting service: '{service_label}'")
        expect(service_dropdown).to_be_enabled(timeout=5000)
        page.wait_for_timeout(300)
        service_dropdown.select_option(label=service_label)
        print("Service selected.")
        page.wait_for_timeout(500)
    else:
        print("No specific service selection needed for this category, or service mapping missing.")

    print(f"Locating link input...")
    link_input = page.locator("input[name=\"url\"]")
    print("Waiting for link input to be visible...")
    expect(link_input).to_be_visible(timeout=10000)
    print(f"Hovering and clicking link input...")
    link_input.hover()
    page.wait_for_timeout(200)
    link_input.click(force=True)
    print(f"Filling link: {link}")
    link_input.fill(link)
    print("Link filled.")

    print(f"Locating quantity input...")
    quantity_input = page.get_by_label("Quantity")
    if not quantity_input.is_visible(timeout=2000):
        print("Quantity input not found by label, trying by name='quantity'...")
        quantity_input = page.locator("input[name='quantity']")
    if not quantity_input.is_visible(timeout=2000):
        print("Quantity input not found by name, using codegen fallback (textbox name='10')...")
        quantity_input = page.get_by_role("textbox", name="10")
    expect(quantity_input).to_be_visible(timeout=10000)
    print(f"Hovering and clicking quantity input...")
    quantity_input.hover()
    page.wait_for_timeout(200)
    quantity_input.click(force=True)
    print(f"Filling quantity: {quantity}")
    quantity_input.fill(str(quantity))
    print("Quantity filled.")

    print(f"Locating submit button using codegen selector...")
    submit_button = page.get_by_role("button", name="Buy $")
    expect(submit_button).to_be_enabled(timeout=10000)
    print("Clicking submit button (normal click)...")
    submit_button.click()
    print("Order submitted! (Verification skipped)")
# --- End of place_order ---

def run_single_automation(platform: str, engagement_type: str, link: str, quantity: int, job_id: str, status_update_callback: callable, save_history_callback: callable):
    """Runs a single automation task based on direct inputs, using a non-persistent browser context."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'Starting single promo for {engagement_type}...')
    success = False
    message = "Automation failed before execution."
    browser = None 
    context = None 

    try:
        with sync_playwright() as p:
            print(f"Launching new browser instance (headless, non-persistent) for single automation.")
            browser = p.chromium.launch(
                headless=True
                # No executable_path needed, Playwright will use its own installed browser
            )
            context = browser.new_context()
            page = context.new_page()
            
            status_update_callback(job_id, 'running', 'Verifying Dogehype login...') 
            page = login_to_dogehype(page, context)
            
            status_update_callback(job_id, 'running', f'Placing order: {quantity} {engagement_type}...')
            place_order(page, platform, engagement_type, link, quantity)
            
            print(f"Order placed successfully for Job ID: {job_id}")
            success = True
            message = f"Single promo successful: {quantity} {engagement_type} for {link}"
            status_update_callback(job_id, 'success', message)

    except PlaywrightError as e:
        print(f"Playwright Error during single automation (Job ID: {job_id}): {e}")
        message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except ValueError as e: # This will catch errors from Gmail helpers too
        print(f"Value Error during single automation (Job ID: {job_id}): {e}")
        message = f"Configuration/Value Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except Exception as e:
        print(f"Unexpected Error during single automation (Job ID: {job_id}): {e}")
        traceback.print_exc()
        message = f"Unexpected Error: {e}"
        status_update_callback(job_id, 'failed', message)
    finally:
        if context: 
            try:
                context.close()
                print("Closed Playwright context for single automation.")
            except Exception as close_err:
                print(f"Error closing context: {close_err}")
        if browser:
            try:
                browser.close()
                print("Closed Playwright browser for single automation.")
            except Exception as close_err:
                print(f"Error closing browser: {close_err}")
             
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        history_entry = {
            "job_id": job_id,
            "type": "Single Promo",
            "profile_name": f"{platform} - {engagement_type}",
            "link": link,
            "quantity": quantity,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "status": "Success" if success else "Failed",
            "message": message
        }
        save_history_callback(history_entry)
        print(f"Single Promo Job {job_id} finished. Status: {'Success' if success else 'Failed'}. Duration: {duration:.2f}s")

# --- Profile Automation --- (Added Stop Check) ---
def run_automation_profile(profile_name: str, profile_data: dict, link: str, job_id: str, 
                           status_update_callback: callable, save_history_callback: callable, 
                           requested_stops: set): # Added requested_stops set argument
    """Runs automation based on a saved profile, using a non-persistent browser context and checking for stop requests."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'Starting profile promo \'{profile_name}\'...')
    print(f"--- Running Profile: {profile_name} for Link: {link} (Job ID: {job_id}) ---")

    success = False
    final_message = "Automation failed before execution."
    browser = None       
    browser_context = None 
    page = None
    total_engagements_run = 0
    main_loops = 1 

    try:
        if job_id in requested_stops:
            print(f"Stop requested for Job {job_id} before starting Playwright.")
            final_message = f"Promo '{profile_name}' stopped by user before starting."
            status_update_callback(job_id, 'stopped', final_message)
            return 
            
        engagements_to_run = profile_data.get('engagements', [])
        loop_settings = profile_data.get('loop_settings', {})
        main_loops = loop_settings.get('loops', 1)
        fixed_delay = loop_settings.get('delay', 0)
        use_random_delay = loop_settings.get('random_delay', False)
        min_delay = loop_settings.get('min_delay', 60)
        max_delay = loop_settings.get('max_delay', 300)
        
        print(f"Loop Settings: Loops={main_loops}, FixedDelay={fixed_delay}, RandomDelay={use_random_delay}, Min={min_delay}, Max={max_delay}")
        if not engagements_to_run:
            raise ValueError("Profile has no engagement settings defined.")

        with sync_playwright() as p:
            if job_id in requested_stops:
                print(f"Stop requested for Job {job_id} just before launching browser.")
                final_message = f"Promo '{profile_name}' stopped by user before browser launch."
                status_update_callback(job_id, 'stopped', final_message)
                return 
            
            print(f"Launching new browser instance (headless, non-persistent) for profile automation.")
            browser = p.chromium.launch(
                headless=True, 
                slow_mo=50, # Can keep slow_mo if it helps stability, even headless
            )
            browser_context = browser.new_context()
            page = browser_context.new_page()
            
            status_update_callback(job_id, 'running', 'Logging into Dogehype...')
            page = login_to_dogehype(page, browser_context) 
            
            for loop_num in range(1, main_loops + 1):
                if job_id in requested_stops:
                    print(f"Stop requested for Job {job_id} before starting loop {loop_num}.")
                    final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num-1}."
                    status_update_callback(job_id, 'stopped', final_message)
                    success = False 
                    break 
                    
                print(f"\n--- Starting Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")
                status_update_callback(job_id, 'running', f'Running loop {loop_num}/{main_loops}...')
                
                for engagement_setting in engagements_to_run:
                    if job_id in requested_stops:
                        print(f"Stop requested for Job {job_id} before placing order in loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        break 

                    eng_type = engagement_setting.get('type')
                    eng_participation_loops = engagement_setting.get('loops', 1)
                    
                    if not eng_type:
                        print(f"Skipping engagement with missing type: {engagement_setting}")
                        continue
                        
                    should_run_this_loop = (loop_num == 1) or (loop_num <= eng_participation_loops)
                    
                    if not should_run_this_loop:
                        print(f"  Skipping {eng_type} in Loop {loop_num} (Participation limit: {eng_participation_loops}, and not first loop)")
                        continue 
                    
                    use_random = engagement_setting.get('use_random_quantity')
                    fixed_qty = engagement_setting.get('fixed_quantity')
                    min_qty = engagement_setting.get('min_quantity')
                    max_qty = engagement_setting.get('max_quantity')

                    quantity_this_run = 0
                    if use_random:
                        if min_qty and max_qty and min_qty <= max_qty:
                            quantity_this_run = random.randint(min_qty, max_qty)
                        else:
                            print(f"Warning: Invalid Min/Max for random quantity in {eng_type}. Skipping in Loop {loop_num}.")
                            continue
                    elif fixed_qty:
                        quantity_this_run = fixed_qty
                    else:
                        print(f"Warning: No quantity specified for {eng_type}. Skipping in Loop {loop_num}.")
                        continue
                        
                    print(f"  Running Engagement in Loop {loop_num}: {eng_type} (Qty: {quantity_this_run}) - Participation Limit: {eng_participation_loops}")
                    status_update_callback(job_id, 'running', f'Loop {loop_num}/{main_loops}: Running {eng_type}')
                    
                    platform = 'Instagram' 
                    place_order(page, platform, eng_type, link, quantity_this_run)
                    total_engagements_run += 1
                    print(f"    Successfully placed order for {eng_type} in Loop {loop_num}.")
                
                if job_id in requested_stops:
                    break 
                        
                print(f"--- Finished Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")

                if loop_num < main_loops: 
                    if job_id in requested_stops:
                        print(f"Stop requested for Job {job_id} before delay after loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        break 
                        
                    delay_seconds = 0 
                    if use_random_delay:
                        if min_delay <= max_delay:
                            delay_seconds = random.uniform(min_delay, max_delay)
                        else:
                            print("Warning: Min delay > Max delay, using fixed delay instead.")
                            delay_seconds = fixed_delay
                    else:
                        delay_seconds = fixed_delay
                        
                    if delay_seconds > 0:
                        print(f"Applying delay of {delay_seconds:.2f} seconds... Job ID: {job_id}")
                        status_update_callback(job_id, 'running', f'Loop {loop_num} finished. Delaying {delay_seconds:.0f}s...')
                        if job_id in requested_stops:
                            print(f"Stop requested for Job {job_id} just before sleeping.")
                            final_message = f"Promo '{profile_name}' stopped by user before delay."
                            status_update_callback(job_id, 'stopped', final_message)
                            success = False
                            break 
                        time.sleep(delay_seconds)
                    else:
                        print("No delay configured.")
                         
            if job_id not in requested_stops:
                print(f"All loops completed for Job ID: {job_id}")
                success = True
                final_message = f"Profile '{profile_name}' completed successfully ({total_engagements_run} orders placed across {main_loops} loops)."
                status_update_callback(job_id, 'success', final_message)
            
            # No need to close browser_context or browser here if 'with sync_playwright() as p:' handles it
            # However, explicit closing is safer if not relying on 'with' for browser instance itself.
            # Since browser is defined outside the 'with p' for launch, we should close it in finally.

    except PlaywrightError as e:
        print(f"Playwright Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        final_message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    except ValueError as e: # Catches errors from Gmail helpers too
        print(f"Value Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        final_message = f"Configuration/Value Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    except Exception as e:
        print(f"Unexpected Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        traceback.print_exc()
        final_message = f"Unexpected Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    finally:
        if browser_context:
            try:
                browser_context.close()
                print("Closed Playwright context for profile automation.")
            except Exception as close_err:
                print(f"Error closing browser context in finally block: {close_err}")
        if browser:
            try:
                browser.close()
                print("Closed Playwright browser for profile automation.")
            except Exception as close_err:
                print(f"Error closing browser in finally block: {close_err}")
             
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        final_status = 'unknown'
        if job_id in requested_stops:
            final_status = 'stopped'
        elif success:
            final_status = 'success'
        else:
            final_status = 'failed'
            
        history_entry = {
            "job_id": job_id,
            "type": "Profile Promo",
            "profile_name": profile_name,
            "link": link,
            "quantity": f"{main_loops} Loops", 
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "status": final_status, 
            "message": final_message
        }
        save_history_callback(history_entry) 
        print(f"Profile Promo Job {job_id} ('{profile_name}') finished. Final Status: {final_status}. Duration: {duration:.2f}s")

# --- NEW Playwright-based Scraping Function ---
def scrape_latest_post_with_playwright(username: str) -> Tuple[Optional[str], Optional[datetime.datetime]]:
    """
    Scrapes the latest Instagram post URL and timestamp for a given username using Playwright.
    This version uses a non-persistent browser context.
    """
    profile_url = f"https://www.instagram.com/{username}/"
    post_url: Optional[str] = None
    timestamp_utc: Optional[datetime.datetime] = None  

    print(f"[Playwright Scrape] Attempting to scrape: {profile_url} using a new (headless, non-persistent) browser session.")
    browser = None 
    context: Optional[BrowserContext] = None 
    page: Optional[Page] = None 

    try:
        with sync_playwright() as p:
            print(f"[Playwright Scrape] Launching new browser instance (headless, non-persistent).")
            browser = p.chromium.launch(
                headless=True, 
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36" 
            )
            page = context.new_page()
            
            print(f"[Playwright Scrape] Navigating to {profile_url}")
            page.goto(profile_url, wait_until='domcontentloaded', timeout=90000)
            
            print("[Playwright Scrape] Waiting for main profile content to load...")
            try:
                main_content_selector = "main[role='main']" 
                page.wait_for_selector(main_content_selector, timeout=45000)
                print(f"[Playwright Scrape] Main content ({main_content_selector}) loaded.")
            except PlaywrightError as e:
                print(f"[Playwright Scrape] Timeout or error waiting for main content ({main_content_selector}) for '{username}': {type(e).__name__} - {e}")
                if page: page.screenshot(path="debug_instagram_main_content_fail.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_main_content_fail.png")
                return None, None

            page.wait_for_timeout(3000)

            print("[Playwright Scrape] Searching for the first post link within article section...")
            post_link_selector = 'main[role="main"] article a[href^="/p/"]'
            
            try:
                first_post_link_locator = page.locator(post_link_selector).first
                print(f"[Playwright Scrape] Waiting for post link ({post_link_selector}) to be visible...")
                expect(first_post_link_locator).to_be_visible(timeout=30000)
                
                href = first_post_link_locator.get_attribute('href')
                if href and href.startswith('/p/'):
                    shortcode = href.split('/')[2]
                    post_url = f"https://www.instagram.com/p/{shortcode}/"
                    print(f"[Playwright Scrape] Success! Found latest post URL: {post_url}")
                else:
                    print(f"[Playwright Scrape] Found a link, but href was invalid or missing: {href}")
                    if page: page.screenshot(path="debug_instagram_invalid_href.png")
                    print("[Playwright Scrape] Saved screenshot to debug_instagram_invalid_href.png")
                    return None, None
            except PlaywrightError as e: 
                print(f"[Playwright Scrape] Could not find or make visible the post link ({post_link_selector}) for '{username}': {type(e).__name__} - {e}")
                if page: page.screenshot(path="debug_instagram_post_not_found.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_post_not_found.png")
                return None, None

            return post_url, timestamp_utc

    except PlaywrightError as e:
        print(f"[Playwright Scrape] Playwright-specific error for '{username}': {type(e).__name__} - {e}")
        if page: 
            try:
                page.screenshot(path="debug_instagram_playwright_error.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_playwright_error.png")
            except Exception as screenshot_err:
                print(f"[Playwright Scrape] Could not take screenshot on Playwright error: {screenshot_err}")
        return None, None
    except Exception as e:
        print(f"[Playwright Scrape] Unexpected error for '{username}': {type(e).__name__} - {e}")
        if page: 
            try:
                page.screenshot(path="debug_instagram_unexpected_error.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_unexpected_error.png")
            except Exception as screenshot_err:
                print(f"[Playwright Scrape] Could not take screenshot on unexpected error: {screenshot_err}")
        return None, None
    finally:
        if context:
            try:
                context.close()
                print("[Playwright Scrape] Context closed in finally block.")
            except Exception as close_err:
                print(f"[Playwright Scrape] Error closing context in finally: {close_err}")
        if browser:
            try:
                browser.close()
                print("[Playwright Scrape] Browser closed in finally block.")
            except Exception as close_err:
                print(f"[Playwright Scrape] Error closing browser in finally: {close_err}")