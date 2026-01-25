# automation_runner.py
import os
# Allow Playwright Sync API even if an event loop is active (used by debug endpoints)
os.environ.setdefault("PW_ALLOW_SYNC_IO", "1")
import re
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
from typing import Tuple, Optional, Callable

class StopRequested(Exception):
    pass

# Minimal promo logging (set to True to restore verbose logs)
VERBOSE_PROMO_LOGS = False

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

# Persistent Chrome user data directory (for real Chrome with saved logins)
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR") or os.path.join(os.path.dirname(__file__), "chrome_profile")
os.makedirs(CHROME_USER_DATA_DIR, exist_ok=True)

# Toggle for legacy Gmail-API-based magic-link login (default: disabled; prefer manual Google login in persistent Chrome)
USE_GMAIL_API_LOGIN = os.getenv("USE_GMAIL_API_LOGIN", "false").strip().lower() in ("1", "true", "yes")

# Gmail API Configuration
SCOPES = ['https://mail.google.com/']
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

def delete_gmail_message(service, message_id):
    """Deletes a Gmail message by its ID."""
    try:
        service.users().messages().delete(userId='me', id=message_id).execute()
        print(f"Deleted Gmail message with ID: {message_id}")
    except Exception as e:
        print(f"Failed to delete Gmail message {message_id}: {e}")

# --- End of Gmail API Helper Functions ---

# Get credentials and URL
TARGET_EMAIL = os.getenv("TARGET_EMAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") # This will no longer be used for login but might be used elsewhere
DOGEHYPE_URL = config.TARGET_WEBSITE_URL
MAIL_URL = "https://www.mail.com/" # This will no longer be used

# --- NEW Interruptible Sleep Function ---
def interruptible_sleep(job_id: str, duration: float, requested_stops: set, status_update_callback: Optional[Callable] = None, interval_check: float = 0.5):
    """Sleeps for a duration, but checks for stop requests at intervals."""
    slept_time = 0
    while slept_time < duration:
        if job_id in requested_stops:
            print(f"Stop requested for Job {job_id} during interruptible sleep.")
            if status_update_callback:
                status_update_callback(job_id, 'stopping', f"Stop requested during delay for job {job_id}. Interrupting sleep.")
            return True # Indicates stop was requested
        
        # Calculate remaining time and actual sleep chunk
        remaining_time = duration - slept_time
        sleep_chunk = min(interval_check, remaining_time)
        
        time.sleep(sleep_chunk)
        slept_time += sleep_chunk
        
        # Optional: Update status during long waits
        if status_update_callback and slept_time < duration: # Avoid final update if loop is about to end
             # Update less frequently to avoid log spam, e.g., every 5 seconds of sleep
            if int(slept_time) % 5 == 0 and int(slept_time) > int(slept_time - sleep_chunk) : # Check if a 5s boundary was crossed
                status_update_callback(job_id, 'running', f'Delaying... {int(duration - slept_time)}s remaining for job {job_id}.')

    return False # Indicates sleep completed without stop
# --- End of Interruptible Sleep Function ---

def is_on_dogehype_dashboard(page: Page) -> bool:
    """Heuristically determines if the current page is the Dogehype dashboard."""
    try:
        # Primary indicator: '+ Add Funds' button
        if page.get_by_role("button", name="+ Add Funds").is_visible(timeout=1500):
            return True
    except Exception:
        pass
    try:
        # Secondary: balance element exists and visible
        if page.locator("#balance").is_visible(timeout=1500):
            return True
    except Exception:
        pass
    try:
        # Tertiary: presence of dashboard keywords in URL
        if "dashboard" in (page.url or ""):
            return True
    except Exception:
        pass
    return False

def ensure_on_dashboard(page: Page) -> None:
    """Force navigation to the Dogehype dashboard URL regardless of current page.
    Safe to call even if already there.
    """
    try:
        current = page.url or ""
        if "dogehype.com/dashboard" not in current:
            page.goto("https://dogehype.com/dashboard", wait_until='load', timeout=30000)
            # Give the page a moment to render dashboard widgets
            page.wait_for_timeout(500)
        # Attempt to dismiss the 'Got it' modal if present
        try:
            dismiss_gotit_if_present(page)
        except Exception:
            pass
    except Exception:
        # Non-fatal; caller may still proceed
        pass
def extract_balance_from_dashboard(page: Page) -> Optional[str]:
    """Extracts the current balance from the Dogehype dashboard."""
    try:
        print("Attempting to extract balance from dashboard...")
        # Try to find the balance element using the selector from the user query
        balance_element = page.locator("#balance")
        
        if balance_element.is_visible(timeout=5000):
            balance_text = balance_element.text_content()
            print(f"Successfully extracted balance: {balance_text}")
            return balance_text
        else:
            print("Balance element not visible, trying alternative selectors...")
            # Try alternative selectors
            balance_element = page.locator('b.text-warning[id="balance"]')
            if balance_element.is_visible(timeout=3000):
                balance_text = balance_element.text_content()
                print(f"Successfully extracted balance with alternative selector: {balance_text}")
                return balance_text
            else:
                print("Could not find balance element with any selector")
                return None
    except Exception as e:
        print(f"Error extracting balance: {e}")
        return None

def dismiss_gotit_if_present(page: Page, timeout_ms: int = 3000) -> None:
    """Clicks the 'Got it' button on the dashboard if it is present."""
    # Primary: exact ID match
    try:
        gotit = page.locator("#gm-gotit")
        if gotit.is_visible(timeout=timeout_ms) and gotit.is_enabled(timeout=timeout_ms):
            gotit.click()
            page.wait_for_timeout(200)
            return
    except Exception:
        pass
    # Fallback: a visible "Got it" button by role/name
    try:
        btn = page.get_by_role("button", name=re.compile(r"^\s*Got\s*it\s*$", re.IGNORECASE))
        if btn.is_visible(timeout=1000) and btn.is_enabled(timeout=500):
            btn.click()
            page.wait_for_timeout(200)
    except Exception:
        pass

def login_to_dogehype(page: Page, context: BrowserContext, stop_checker: Optional[Callable[[], bool]] = None) -> Tuple[Page, Optional[str]]:
    if not TARGET_EMAIL: # MAIL_PASSWORD is no longer needed for this function
        raise ValueError("Missing TARGET_EMAIL in .env file for Dogehype login.")

    print("🔐 Starting Dogehype login process...")
    # Exact flow: Always navigate to /login first
    login_url = "https://dogehype.com/login"
    print(f"🌐 Navigating to {login_url}")
    try:
        page.goto(login_url, wait_until='load', timeout=20000)
    except Exception:
        pass
    # Brief settle for dynamic content
    page.wait_for_timeout(1000)
    # If already authenticated, /login may redirect to dashboard
    try:
        if "dogehype.com/dashboard" in (page.url or "") or is_on_dogehype_dashboard(page):
            print("✅ Already authenticated - dashboard detected after hitting /login.")
            ensure_on_dashboard(page)  # also dismisses 'Got it'
            return page, extract_balance_from_dashboard(page)
    except Exception:
        pass

    # Step 2: CLICK LOGIN BUTTON using provided selectors, then short wait
    print("🖱️ Step 2: Clicking Login button...")
    clicked_login = False
    login_selectors = [
        # Provided CSS selector (use raw string to preserve backslashes for escaped classes/pseudoselectors)
        r"body > header > nav > div.flex.items-center.gap-3 > a.px-4.py-2.rounded-xl.border.border-white\/15.hover\:bg-white\/5.transition.font-medium.focus\:outline-none.focus-visible\:ring-2.focus-visible\:ring-dhAccent-500",
        # Provided XPath
        "xpath=/html/body/header/nav/div[2]/a[2]",
    ]
    try:
        for sel in login_selectors:
            try:
                login_el = page.locator(sel)
                if login_el.is_visible(timeout=2000):
                    try:
                        login_el.scroll_into_view_if_needed(timeout=1000)
                    except Exception:
                        pass
                    login_el.click(force=True)
                    clicked_login = True
                    print(f"🖱️✅ Clicked Login via selector: {sel}")
                    break
            except Exception:
                continue
        if not clicked_login:
            # Fallback to a role-based button if custom selectors miss
            try:
                role_btn = page.get_by_role("button", name=re.compile("Login|Sign In", re.IGNORECASE)).first
                if role_btn.is_visible(timeout=2000):
                    try:
                        role_btn.scroll_into_view_if_needed(timeout=1000)
                    except Exception:
                        pass
                    role_btn.click(force=True)
                    clicked_login = True
                    print("🖱️✅ Clicked Login via role-based fallback.")
            except Exception:
                pass
    except Exception as e:
        print(f"Error while attempting to click Login: {e}")
    if clicked_login:
        # Wait for login page to load and Google button to appear
        print("⏳ Waiting for login page to load after clicking Login...")
        try:
            page.wait_for_url(re.compile(r"dogehype\.com/.+(login|auth)", re.IGNORECASE), timeout=6000)
        except Exception:
            pass
        # Poll up to ~6s for the Google button to show before taking further action
        poll_total, step_ms = 6000, 500
        polled = 0
        while polled < poll_total:
            try:
                if page.locator(".google > a:nth-child(1)").is_visible(timeout=250):
                    print("🟢 Google SSO button visible after Login click.")
                    break
            except Exception:
                pass
            page.wait_for_timeout(step_ms)
            polled += step_ms
        # If still not visible, try explicit /login route
        try:
            if not page.locator(".google > a:nth-child(1)").is_visible(timeout=500):
                print("🧭 Google SSO button not visible yet, navigating to /login explicitly...")
                page.goto("https://dogehype.com/login", wait_until='load', timeout=8000)
                page.wait_for_timeout(500)
        except Exception:
            pass

    # Step 3-5: Attempt automated Google SSO login (Sign in with Google -> Choose account -> Continue)
    try:
        print("🔎 Looking for 'Sign in with Google' button...")
        # First try the specific selector provided
        google_css_primary = page.locator(".google > a:nth-child(1)")
        google_btn_candidates = [
            google_css_primary,
            page.get_by_role("button", name=re.compile("Continue with Google|Sign in with Google|Google", re.IGNORECASE)),
            page.get_by_alt_text(re.compile("Google", re.IGNORECASE)).locator("..").filter(has=page.get_by_role("button")).first,
            page.locator("button:has(svg[aria-label*='Google'])").first,
        ]
        google_btn = None
        for cand in google_btn_candidates:
            try:
                if cand.is_visible(timeout=4500):
                    google_btn = cand
                    break
            except Exception:
                continue
        if not google_btn:
            # No fallbacks allowed: fail fast if SSO button is not present
            raise AssertionError("Google SSO button not found on Dogehype login page.")
        if google_btn:
            print("🔓 Clicking Google SSO button...")
            google_page = None
            # Ensure in view and actionable
            try:
                google_btn.scroll_into_view_if_needed(timeout=1000)
            except Exception:
                pass
            try:
                google_btn.hover(timeout=1000)
            except Exception:
                pass
            popup_opened = False
            try:
                if stop_checker and stop_checker():
                    raise StopRequested()
                with context.expect_page(timeout=15000) as new_page_info:
                    google_btn.click()
                google_page = new_page_info.value
                popup_opened = True
            except Exception as click_err:
                # Retry with force on same tab
                try:
                    google_btn.click(force=True, timeout=5000)
                    google_page = page
                except Exception:
                    # Last resort: DOM click via JS executed on the locator itself
                    try:
                        google_btn.evaluate("el => el.click()")
                        google_page = page
                    except Exception:
                        # Treat as same-tab even if no explicit success signal
                        google_page = page
            # Wait briefly for Google auth to appear (same-tab or popup)
            try:
                target_page = google_page or page
                # Wait for either Google domain in URL or presence of account chooser elements
                try:
                    target_page.wait_for_url(re.compile(r"accounts\.google|ServiceLogin|identifier", re.IGNORECASE), timeout=10000)
                except Exception:
                    # Element-based wait as alternative signal
                    if not target_page.locator("div.yAlK0b, ul[role='listbox'] li").first.is_visible(timeout=5000):
                        pass
            except Exception:
                pass
            print(f"🔁 Proceeding on auth page/tab: { (google_page.url if google_page else page.url) }")
            if google_page is None:
                google_page = page

            # Step 4: Wait for account picker list and choose account matching TARGET_EMAIL
            print(f"👤 Selecting Google account matching: {TARGET_EMAIL}")
            if stop_checker and stop_checker():
                raise StopRequested()
            account_selector_candidates = [
                google_page.locator(f"div.yAlK0b[data-email='{TARGET_EMAIL}']"),
                google_page.locator("li.aZvCDf div.yAlK0b", has_text=re.compile(re.escape(TARGET_EMAIL), re.IGNORECASE)).first,
            ]
            account_elem = None
            for loc in account_selector_candidates:
                try:
                    if loc.is_visible(timeout=8000):
                        account_elem = loc
                        break
                except Exception:
                    continue
            if not account_elem:
                # Fallback: email entry flow if no account tile is visible
                try:
                    # Wait for email input; if present, use explicit email entry path
                    try:
                        google_page.wait_for_selector("input[type='email']", timeout=7000)
                    except Exception:
                        # Try to detect text for the email on page and click nearest clickable ancestor
                        try:
                            email_text_match = google_page.get_by_text(re.compile(re.escape(TARGET_EMAIL), re.IGNORECASE)).first
                            if email_text_match and email_text_match.is_visible(timeout=3000):
                                email_text_match.locator("xpath=ancestor-or-self::*[@role='link' or @role='button' or @data-email]").first.click()
                                print("✅ Clicked the desired Google account via text match.")
                                # proceed directly to potential consent/password
                            else:
                                raise Exception("Email text not visible")
                        except Exception:
                            # Go with email field fill as last resort
                            pass
                    # If email field exists, fill and continue
                    if google_page.locator("input[type='email']").count() > 0:
                        print("✉️  Entering email on Google identifier page...")
                        if stop_checker and stop_checker():
                            raise StopRequested()
                        google_page.fill("input[type='email']", TARGET_EMAIL, timeout=5000)
                        google_page.click('#identifierNext', timeout=5000)
                        # Optional: handle password page if it appears
                        try:
                            google_page.wait_for_selector("input[type='password']", timeout=7000)
                            target_pwd = (os.getenv('TARGET_PASSWORD') or os.getenv('MAIL_PASSWORD') or '').strip()
                            if target_pwd:
                                print("🔒 Entering password on Google password page...")
                                if stop_checker and stop_checker():
                                    raise StopRequested()
                                google_page.fill("input[type='password']", target_pwd, timeout=5000)
                                google_page.click('#passwordNext', timeout=5000)
                        except Exception:
                            # Password page may not appear if session is remembered
                            pass
                    else:
                        # If no email field and no tile, raise
                        raise AssertionError("Could not find the Google account entry to select.")
                except Exception as e:
                    raise AssertionError(f"Could not complete Google email entry flow: {e}")
            else:
                # We found a clickable account element, use it
                try:
                    account_elem.click()
                    print("✅ Clicked the desired Google account.")
                except Exception as e:
                    # Try a JS click as a fallback
                    try:
                        account_elem.evaluate("el => el.click()")
                        print("✅ Clicked account via JS evaluate.")
                    except Exception:
                        raise AssertionError(f"Failed to click Google account: {e}")

            # Step 5: Handle Google consent/confirmation (same-tab or popup)
            consent_page = google_page
            try:
                with context.expect_page(timeout=8000) as maybe_consent:
                    # A small action to trigger any lazy navigation if pending
                    consent_page.wait_for_timeout(250)
                consent_page = maybe_consent.value
                print("🔁 Consent page opened in a new tab/window.")
            except Exception:
                # Likely same-tab consent
                pass

            # Broaden consent/continue selectors
            potential_pages = [p for p in {page, google_page, consent_page} if p]
            consent_clicked = False
            for p in potential_pages:
                try:
                    consent_buttons = [
                        p.get_by_role("button", name=re.compile("Continue|Allow|Next|Agree|Confirm", re.IGNORECASE)).first,
                        p.locator("button#submit_approve_access, button[name='approve']").first,
                        p.locator("[data-is-consent-action]").first,
                        p.locator(".tyoyWc button").first,
                    ]
                    for cont in consent_buttons:
                        try:
                            if stop_checker and stop_checker():
                                raise StopRequested()
                            if cont.is_visible(timeout=3000) and cont.is_enabled(timeout=500):
                                print("➡️ Clicking Google consent/continue button...")
                                cont.click()
                                consent_clicked = True
                                break
                        except Exception:
                            continue
                    if consent_clicked:
                        break
                except Exception:
                    continue

            # Step 6: Wait for redirect back to Dogehype and dashboard visibility (extended polling)
            print("⏳ Waiting for redirect back to Dogehype dashboard...")
            try:
                consent_page.wait_for_load_state('load', timeout=20000)
            except Exception:
                pass

            # Poll multiple pages in context for Dogehype dashboard
            max_wait_ms = 60000
            interval = 1000
            waited = 0
            while waited < max_wait_ms:
                try:
                    if stop_checker and stop_checker():
                        raise StopRequested()
                    # Check known pages first
                    for cand in [page, google_page, consent_page]:
                        if not cand:
                            continue
                        # If we're on MojoAuth, try to proceed to Dogehype
                        try:
                            current_url = cand.url or ""
                            if "mojoauth.com" in current_url:
                                print(f"🔄 Detected MojoAuth intermediate page: {current_url}. Trying to proceed to Dogehype…")
                                proceed_link = cand.locator("a[href*='dogehype.com']").first
                                if proceed_link.is_visible(timeout=1500):
                                    proceed_link.click()
                                    try:
                                        cand.wait_for_url(re.compile(r"dogehype\.com", re.IGNORECASE), timeout=8000)
                                        print("🔗 Proceeded from MojoAuth to Dogehype.")
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        if is_on_dogehype_dashboard(cand):
                            print("📊✅ Dashboard detected after Google SSO.")
                            ensure_on_dashboard(cand)
                            return cand, extract_balance_from_dashboard(cand)
                except Exception:
                    pass
                # Check any other pages in context as a safety
                try:
                    for p in context.pages:
                        try:
                            # Attempt MojoAuth transition here as well
                            cur = p.url or ""
                            if "mojoauth.com" in cur:
                                print(f"🔄 Detected MojoAuth on another tab: {cur}. Trying to proceed…")
                                link = p.locator("a[href*='dogehype.com']").first
                                if link.is_visible(timeout=1500):
                                    link.click()
                                    try:
                                        p.wait_for_url(re.compile(r"dogehype\.com", re.IGNORECASE), timeout=8000)
                                    except Exception:
                                        pass
                            if "dogehype.com" in cur and is_on_dogehype_dashboard(p):
                                print("📊✅ Dashboard detected on another tab after SSO.")
                                ensure_on_dashboard(p)
                                return p, extract_balance_from_dashboard(p)
                        except Exception:
                            continue
                except Exception:
                    pass
                # Small wait before next poll
                page.wait_for_timeout(interval)
                waited += interval

            # As a final attempt, navigate to dashboard (exact flow requires ending up on dashboard)
            try:
                page.goto("https://dogehype.com/dashboard", wait_until='load', timeout=30000)
                if page.get_by_role("button", name="+ Add Funds").is_visible(timeout=5000):
                    print("📊✅ Dashboard confirmed after direct navigation post-SSO.")
                    ensure_on_dashboard(page)
                    return page, extract_balance_from_dashboard(page)
            except Exception:
                pass

            raise TimeoutError("Google SSO flow did not reach the dashboard in time.")
    except StopRequested:
        raise
    except Exception as e:
        # No fallback is permitted per requirements
        raise AssertionError(f"Google SSO flow failed: {e}")

    # SSO-only policy: do not attempt any email-based login or Gmail API magic-link flow
    raise AssertionError("Login failed: Google SSO is required and no fallback (email or magic-link) is permitted.")

def place_order(page: Page, platform: str, engagement_type: str, link: str, quantity: int):
    # --- PASTE of place_order function from automation.py --- 
    # (Content identical to the function previously in automation.py, including the Views service change)
    print(f"\nAttempting to place order: {quantity} {engagement_type} for {platform} -> {link} using codegen selectors.")
    # Ensure any onboarding/overlay is dismissed before interacting
    try:
        dismiss_gotit_if_present(page)
    except Exception:
        pass
    print(f"Clicking initial navigation link: Misc Services")
    nav_link = page.get_by_role("link", name="Misc Services")
    expect(nav_link).to_be_visible(timeout=5000)
    expect(nav_link).to_be_enabled(timeout=3000)
    print("Hovering over Misc Services link...")
    nav_link.hover()
    page.wait_for_timeout(200)
    print("Forcing click on Misc Services link...")
    nav_link.click(force=True)
    print("Waiting for page navigation to complete after click...")
    try:
        page.wait_for_load_state('load', timeout=12000)
        page.wait_for_load_state('networkidle', timeout=8000)
    except Exception:
        pass
    print("Waiting for Category dropdown to appear after navigation...")
    # Try multiple robust selectors for the Category dropdown
    category_locators = [
        # Original strict CSS (may change with layout updates)
        page.locator("#app > div > div.content-wrapper > main > div.card.p-4.mt-3 > form > div.form-group > select"),
        # Label-based (preferred if accessible labels exist)
        page.get_by_label(re.compile(r"^\s*Category\s*$", re.IGNORECASE)),
        # Name attribute
        page.locator("select[name='category']"),
        # Any select inside the main form card
        page.locator("main form select").first,
        # Fallback: first visible select on the page
        page.locator("select").first,
    ]
    category_dropdown_locator = None
    for loc in category_locators:
        try:
            if loc.is_visible(timeout=2000):
                category_dropdown_locator = loc
                break
        except Exception:
            continue
    if not category_dropdown_locator:
        # Final attempt: small poll and screenshot for diagnostics
        print("Category dropdown not immediately visible, polling briefly and taking a diagnostic screenshot...")
        poll_ms, step = 4000, 500
        waited = 0
        while waited < poll_ms and not category_dropdown_locator:
            for loc in category_locators:
                try:
                    if loc.is_visible(timeout=250):
                        category_dropdown_locator = loc
                        break
                except Exception:
                    continue
            if category_dropdown_locator:
                break
            page.wait_for_timeout(step)
            waited += step
        if not category_dropdown_locator:
            try:
                page.screenshot(path="category_not_found.png", full_page=True)
                print("Saved screenshot: category_not_found.png")
            except Exception:
                pass
            raise AssertionError("Could not locate Category dropdown after navigation.")
    print("Category dropdown found.")

    category_label = CATEGORY_MAPPING.get((platform, engagement_type))
    if not category_label:
        raise ValueError(f"Unsupported platform/engagement combination in CATEGORY_MAPPING: {platform} / {engagement_type}")

    print(f"Selecting category: '{category_label}' using visible label (with value fallback)...")
    category_dropdown = category_dropdown_locator
    print("Ensuring dropdown is enabled...")
    expect(category_dropdown).to_be_enabled(timeout=3000)
    print(f"Attempting to select option: {category_label}")
    page.wait_for_timeout(300)
    try:
        category_dropdown.select_option(label=category_label)
    except Exception:
        print("Label-based selection failed, trying by value...")
        try:
            category_dropdown.select_option(value=category_label)
        except Exception as e_val:
            print(f"Value-based selection also failed: {e_val}. Falling back to contains-based matching of Category options...")
            try:
                option_loc = category_dropdown.locator("option")
                option_texts = option_loc.all_text_contents()
                print(f"Category options: {option_texts}")
                # 1) Exact text match preference for USA
                usa_exact = "Instagram - [USA]"
                if usa_exact in option_texts:
                    usa_idx = option_texts.index(usa_exact)
                    print(f"Exact USA category found at index {usa_idx}. Selecting '{usa_exact}'")
                    category_dropdown.select_option(index=usa_idx)
                else:
                    # 2) Weighted contains-based scoring
                    key_weights = {"usa": 5, "likes": 2, "instagram": 1}
                    best_idx = -1
                    best_score = -1
                    for idx, text in enumerate(option_texts):
                        lt = (text or "").lower()
                        score = sum(w for tok, w in key_weights.items() if tok in lt)
                        # Prefer entries that contain '[USA]' explicitly
                        if "[usa]" in lt:
                            score += 3
                        # Tie-breaker: prefer options earlier that include USA
                        if score > best_score or (score == best_score and best_idx >= 0 and "[usa]" in lt and "[usa]" not in (option_texts[best_idx] or "").lower()):
                            best_score = score
                            best_idx = idx
                    if best_idx >= 0 and best_score > 0:
                        print(f"Weighted Category match chose option index {best_idx} (score {best_score}) -> '{option_texts[best_idx]}'")
                        category_dropdown.select_option(index=best_idx)
                    else:
                        # 3) Last resort: pick the first option
                        if option_texts:
                            print(f"No Category match score > 0. Selecting first option as fallback -> '{option_texts[0]}'")
                            category_dropdown.select_option(index=0)
                        else:
                            raise AssertionError("Category dropdown has no options to select.")
            except Exception as e_cat:
                raise AssertionError(f"Unable to select Category via label, value, or contains-match. Intended: {category_label}. Error: {e_cat}")
    print("Category selected.")

    # Exact flow: type link right after selecting Category
    try:
        print(f"[Flow] Typing link immediately after Category selection...")
        link_input_pre = page.locator("input[name=\"url\"]")
        expect(link_input_pre).to_be_visible(timeout=5000)
        link_input_pre.hover()
        page.wait_for_timeout(200)
        link_input_pre.click(force=True)
        link_input_pre.fill(link)
        print("[Flow] Link entered after Category selection.")
    except Exception as e:
        print(f"[Flow] Warning: Could not enter link after Category selection (will still fill later). Error: {e}")

    # Normalize inputs for reliable matching
    norm_platform = (platform or "").strip()
    norm_engagement = (engagement_type or "").strip()
    # Explicit service label mapping per user specification (Instagram)
    SERVICE_LABELS = {
        ("Instagram", "Likes"): "Instagram - Likes - [USA] - [High Quality] - [5-10K/D] - [Very Fast]",
        ("Instagram", "Views"): "Instagram - Views - [Work] - [All Links]⚡",
        ("Instagram", "Saves"): "Instagram - Saves - [Instant] - [Real]",
        ("Instagram", "Shares"): "Instagram - Shares - [5M/D]",
        # Keep existing for Reach/Impressions unless changed later
        ("Instagram", "Reach/Impressions"): "Instagram Reach + Impressions - [100K/Day] - 💧⛔️ - $0.17 per 1000",
    }
    service_label = SERVICE_LABELS.get((norm_platform, norm_engagement))

    if service_label:
        # Try multiple strategies for locating the Service dropdown
        service_dropdown_candidates = [
            page.locator("#app > div > div.content-wrapper > main > div.card.p-4.mt-3 > form > div:nth-child(2) > div > select"),
            page.get_by_label(re.compile(r"^\s*Service\s*$", re.IGNORECASE)),
            page.locator("select[name='service']"),
            page.locator("main form select").nth(1),  # Often second select is service
        ]
        service_dropdown = None
        for loc in service_dropdown_candidates:
            try:
                if loc.is_visible(timeout=2000):
                    service_dropdown = loc
                    break
            except Exception:
                continue
        if not service_dropdown:
            # As a fallback, choose any second visible select
            try:
                all_selects = page.locator("select")
                count = all_selects.count()
                for i in range(min(5, count)):
                    sel = all_selects.nth(i)
                    try:
                        if sel.is_visible(timeout=500):
                            # Heuristic: skip if same as category
                            if sel == category_dropdown_locator:
                                continue
                            service_dropdown = sel
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        expect(service_dropdown).to_be_visible(timeout=5000)
        print("Service dropdown found.")
        print(f"Selecting service using robust contains-based matching first for: '{service_label}'")
        expect(service_dropdown).to_be_enabled(timeout=3000)
        page.wait_for_timeout(300)
        contains_selected = False
        try:
            option_texts = service_dropdown.locator("option").all_text_contents()
            desired = service_label
            raw_tokens = [t.strip() for t in re.split(r"\s+-\s+|\s*\|\s*", desired) if t]
            def is_price_token(tok: str) -> bool:
                return bool(re.search(r"\$\s*\d|per\s*1000|/\s*1000", tok, flags=re.IGNORECASE))
            tokens = [t for t in raw_tokens if t and not is_price_token(t)]

            # If Instagram Likes, strongly prefer USA-tagged services
            texts_lower = [(i, (txt or ""), (txt or "").lower()) for i, txt in enumerate(option_texts)]
            usa_candidates = [(i, t, tl) for i, t, tl in texts_lower if "usa" in tl]
            candidates = usa_candidates if (norm_platform.lower()=="instagram" and norm_engagement.lower()=="likes" and usa_candidates) else texts_lower
            if candidates is usa_candidates:
                print(f"Service candidates restricted to USA-tagged options: {len(usa_candidates)} found")

            # Weighted scoring among candidates
            weight_map = {
                "usa": 5,
                "high quality": 4,
                "very fast": 3,
                "5-10k/d": 2,
                "likes": 1,
            }
            best_idx = -1
            best_score = -1
            for idx, text, tl in candidates:
                score = 0
                for tok, w in weight_map.items():
                    if tok in tl:
                        score += w
                # Also add +1 for each non-price exact token substring match from desired label
                score += sum(1 for tok in tokens if tok and tok.lower() in tl)
                # Prefer USA explicitly in tie
                if score > best_score or (score == best_score and best_idx >= 0 and ("usa" in tl) and ("usa" not in candidates[[i for i,(bi,_,_) in enumerate(candidates) if bi==best_idx][0]][2])):
                    best_score = score
                    best_idx = idx

            if best_idx >= 0 and best_score > 0:
                print(f"Weighted contains-based service match chose option index {best_idx} (score {best_score}) -> '{option_texts[best_idx]}'")
                service_dropdown.select_option(index=best_idx)
                contains_selected = True
            else:
                print(f"Contains-based match not decisive. Tokens: {tokens}; Options: {option_texts}")
        except Exception as e:
            print(f"Contains-based matching failed early: {e}")

        if not contains_selected:
            # Final fallback for Instagram Likes: choose 1st option
            if (platform or '').strip().lower() == 'instagram' and (engagement_type or '').strip().lower() == 'likes':
                try:
                    option_texts = service_dropdown.locator("option").all_text_contents()
                    if len(option_texts) >= 1:
                        print(f"Final fallback: selecting 1st service option for Instagram Likes -> '{option_texts[0]}'")
                        service_dropdown.select_option(index=0)
                        print("Service selected via fallback.")
                    else:
                        raise AssertionError(f"IG Likes fallback unavailable: only {len(option_texts)} service options present: {option_texts}")
                except Exception as e2:
                    raise AssertionError(f"Unable to select service using contains-match or IG Likes fallback. Intended label: {service_label}. Error: {e2}")
            else:
                raise AssertionError(f"Unable to select service using contains-match. Intended label: {service_label}")
        else:
            print("Service selected via contains-based match.")
        page.wait_for_timeout(500)
    else:
        print("No specific service selection needed for this category, or service mapping missing.")

    print(f"Locating link input...")
    link_input = page.locator("input[name=\"url\"]")
    print("Waiting for link input to be visible...")
    expect(link_input).to_be_visible(timeout=5000)
    print(f"Hovering and clicking link input...")
    link_input.hover()
    page.wait_for_timeout(200)
    link_input.click(force=True)
    print(f"Filling link again (post-Service selection): {link}")
    link_input.fill(link)
    print("Link filled (post-Service selection).")

    print(f"Locating quantity input...")
    quantity_input = page.get_by_label("Quantity")
    if not quantity_input.is_visible(timeout=2000):
        print("Quantity input not found by label, trying by name='quantity'...")
        quantity_input = page.locator("input[name='quantity']")
    if not quantity_input.is_visible(timeout=2000):
        print("Quantity input not found by name, using codegen fallback (textbox name='10')...")
        quantity_input = page.get_by_role("textbox", name="10")
    expect(quantity_input).to_be_visible(timeout=5000)
    print(f"Hovering and clicking quantity input...")
    quantity_input.hover()
    page.wait_for_timeout(200)
    quantity_input.click(force=True)
    print(f"Filling quantity: {quantity}")
    quantity_input.fill(str(quantity))
    print("Quantity filled.")

    print(f"Locating submit button using codegen selector...")
    submit_button = page.get_by_role("button", name="Buy $")
    expect(submit_button).to_be_enabled(timeout=5000)
    if VERBOSE_PROMO_LOGS:
        print("Clicking submit button (normal click)...")
    submit_button.click()
    if VERBOSE_PROMO_LOGS:
        print("Order submitted! (Verification skipped)")
# --- End of place_order ---

def run_single_automation(platform: str, engagement_type: str, link: str, quantity: int, job_id: str, status_update_callback: callable, save_history_callback: callable, requested_stops: set):
    """Runs a single automation task based on direct inputs, using a non-persistent browser context."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'🚀 Starting single promo for {engagement_type}...')
    # Minimal terminal log
    print(f"Executing single promo for {link}")
    success = False
    message = "Automation failed before execution."
    context: Optional[BrowserContext] = None 

    try:
        with sync_playwright() as p:
            # Check immediate stop before starting
            if job_id in requested_stops:
                message = "Stop requested by user before browser launch."
                status_update_callback(job_id, 'stopped', message)
                return
            if VERBOSE_PROMO_LOGS:
                print(f"🌐 Launching Google Chrome for single automation (per-job profile).")
            safe_job = re.sub(r'[^A-Za-z0-9._-]', '_', str(job_id))
            job_profile_dir = os.path.join(CHROME_USER_DATA_DIR, f"job_{safe_job}")
            os.makedirs(job_profile_dir, exist_ok=True)
            status_update_callback(job_id, 'running', f'🌐 Launching Chrome with profile: {job_profile_dir}')
            context = p.chromium.launch_persistent_context(
                user_data_dir=job_profile_dir,
                channel="chrome",           # Use the real Chrome browser
                headless=False,              # Visible UI
                slow_mo=50,                  # Slight slow motion for visibility
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            page = context.new_page()
            
            status_update_callback(job_id, 'running', '🔐 Verifying Dogehype login...') 
            stop_checker = (lambda: job_id in requested_stops)
            try:
                page, balance = login_to_dogehype(page, context, stop_checker=stop_checker)
            except StopRequested:
                message = "Stop requested by user during login."
                status_update_callback(job_id, 'stopped', message)
                return
            # Exact flow: after confirming login/dashboard, go to homepage before promo
            try:
                page.goto("https://dogehype.com/", wait_until='load', timeout=15000)
                page.wait_for_timeout(500)
            except Exception:
                pass
            # Check stop before placing order
            if job_id in requested_stops:
                message = "Stop requested by user before placing order."
                status_update_callback(job_id, 'stopped', message)
                return
            
            status_update_callback(job_id, 'running', f'🛒 Placing order: {quantity} {engagement_type}...')
            place_order(page, platform, engagement_type, link, quantity)
            
            print(f"✅ Order placed successfully for Job ID: {job_id}")
            success = True
            message = f"Single promo successful: {quantity} {engagement_type} for {link}"
            status_update_callback(job_id, 'success', message)

    except PlaywrightError as e:
        print(f"❌ Playwright Error during single automation (Job ID: {job_id}): {e}")
        message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except ValueError as e: # This will catch errors from Gmail helpers too
        print(f"❌ Value Error during single automation (Job ID: {job_id}): {e}")
        message = f"Configuration/Value Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except Exception as e:
        print(f"❌ Unexpected Error during single automation (Job ID: {job_id}): {e}")
        traceback.print_exc()
        message = f"Unexpected Error: {e}"
        status_update_callback(job_id, 'failed', message)
    finally:
        if context: 
            try:
                # Closing the persistent context will save the session to CHROME_USER_DATA_DIR
                context.close()
                if VERBOSE_PROMO_LOGS:
                    print("Closed persistent Chrome context for single automation.")
            except Exception as close_err:
                if VERBOSE_PROMO_LOGS:
                    print(f"Error closing persistent context: {close_err}")
             
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        history_entry = {
            "job_id": job_id,
            "type": "Single Promo",
            "profile_name": f"{platform} - {engagement_type}",
            "platform": platform,
            "engagement": engagement_type,
            "link": link,
            "quantity": quantity,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "status": "Success" if success else "Failed",
            "message": message
        }
        save_history_callback(history_entry)
        # Minimal terminal log
        print(f"Single promo {'successful' if success else 'unsuccessful'} for {link}")

# --- Profile Automation --- (Added Stop Check) ---
def run_automation_profile(profile_name: str, profile_data: dict, link: str, job_id: str, 
                           status_update_callback: callable, save_history_callback: callable, 
                           requested_stops: set): # Added requested_stops set argument
    """Runs automation based on a saved profile, using a non-persistent browser context and checking for stop requests."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'🚀 Starting profile promo \'{profile_name}\'...')
    # Minimal terminal log
    print(f"Executing auto promo for {link}")
    if VERBOSE_PROMO_LOGS:
        print(f"🧩 --- Running Profile: {profile_name} for Link: {link} (Job ID: {job_id}) ---")

    success = False
    final_message = "Automation failed before execution."
    browser_context: Optional[BrowserContext] = None 
    page: Optional[Page] = None
    total_engagements_run = 0
    main_loops = 1 

    try:
        if job_id in requested_stops:
            print(f"Stop requested for Job {job_id} before starting Playwright.")
            final_message = f"Promo '{profile_name}' stopped by user before starting."
            status_update_callback(job_id, 'stopped', final_message)
            return # Exit early
            
        engagements_to_run = profile_data.get('engagements', [])
        loop_settings = profile_data.get('loop_settings', {})
        main_loops = loop_settings.get('loops', 1)
        fixed_delay = loop_settings.get('delay', 0)
        use_random_delay = loop_settings.get('random_delay', False)
        min_delay = loop_settings.get('min_delay', 60)
        max_delay = loop_settings.get('max_delay', 300)
        
        if VERBOSE_PROMO_LOGS:
            print(f"Loop Settings: Loops={main_loops}, FixedDelay={fixed_delay}, RandomDelay={use_random_delay}, Min={min_delay}, Max={max_delay}")
        if not engagements_to_run:
            raise ValueError("Profile has no engagement settings defined.")

        with sync_playwright() as p:
            if job_id in requested_stops:
                print(f"Stop requested for Job {job_id} just before launching browser.")
                final_message = f"Promo '{profile_name}' stopped by user before browser launch."
                status_update_callback(job_id, 'stopped', final_message)
                return # Exit early
            
            if VERBOSE_PROMO_LOGS:
                print(f"Launching Google Chrome for profile automation (per-job profile).")
            safe_job = re.sub(r'[^A-Za-z0-9._-]', '_', str(job_id))
            job_profile_dir = os.path.join(CHROME_USER_DATA_DIR, f"job_{safe_job}")
            os.makedirs(job_profile_dir, exist_ok=True)
            status_update_callback(job_id, 'running', f'Launching Chrome with profile: {job_profile_dir}')
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=job_profile_dir,
                channel="chrome",
                headless=False,
                slow_mo=50,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            page = browser_context.new_page()
            
            if job_id in requested_stops: # Check after browser launch but before login
                print(f"Stop requested for Job {job_id} before login.")
                final_message = f"Promo '{profile_name}' stopped by user before login."
                status_update_callback(job_id, 'stopped', final_message)
                # Attempt to close browser components before returning
                if page: page.close()
                if browser_context: browser_context.close()
                return

            status_update_callback(job_id, 'running', 'Logging into Dogehype...')
            page, balance = login_to_dogehype(page, browser_context) # This function has its own timeouts and logic
            # Exact flow: after confirming login/dashboard, go to homepage before promo
            try:
                page.goto("https://dogehype.com/", wait_until='load', timeout=15000)
                page.wait_for_timeout(500)
            except Exception:
                pass
            
            # Check stop request immediately after login_to_dogehype, as it can be lengthy
            if job_id in requested_stops:
                print(f"Stop requested for Job {job_id} immediately after login.")
                final_message = f"Promo '{profile_name}' stopped by user after login."
                status_update_callback(job_id, 'stopped', final_message)
                if page and not page.is_closed(): page.close()
                if browser_context: browser_context.close()
                return

            for loop_num in range(1, main_loops + 1):
                if job_id in requested_stops:
                    print(f"Stop requested for Job {job_id} before starting loop {loop_num}.")
                    final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num-1}."
                    status_update_callback(job_id, 'stopped', final_message)
                    success = False 
                    if page and not page.is_closed(): page.close()
                    if browser_context: browser_context.close()
                    break # Exit outer loop
                    
                if VERBOSE_PROMO_LOGS:
                    print(f"\n--- Starting Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")
                status_update_callback(job_id, 'running', f'Running loop {loop_num}/{main_loops}...')
                
                for engagement_setting in engagements_to_run:
                    if job_id in requested_stops:
                        print(f"Stop requested for Job {job_id} before placing order in loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num} (before order)."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        if page and not page.is_closed(): page.close()
                        if browser_context: browser_context.close()
                        break # Exit inner engagement loop

                    eng_type = engagement_setting.get('type')
                    eng_participation_loops = engagement_setting.get('loops', 1)
                    
                    if not eng_type:
                        if VERBOSE_PROMO_LOGS:
                            print(f"Skipping engagement with missing type: {engagement_setting}")
                        continue
                        
                    should_run_this_loop = (loop_num == 1) or (loop_num <= eng_participation_loops)
                    
                    if not should_run_this_loop:
                        if VERBOSE_PROMO_LOGS:
                            print(f"⏭️  Skipping {eng_type} in Loop {loop_num} (Participation limit: {eng_participation_loops}, and not first loop)")
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
                            if VERBOSE_PROMO_LOGS:
                                print(f"⚠️ Warning: Invalid Min/Max for random quantity in {eng_type}. Skipping in Loop {loop_num}.")
                            continue
                    elif fixed_qty:
                        quantity_this_run = fixed_qty
                    else:
                        if VERBOSE_PROMO_LOGS:
                            print(f"⚠️ Warning: No quantity specified for {eng_type}. Skipping in Loop {loop_num}.")
                        continue
                        
                    if VERBOSE_PROMO_LOGS:
                        print(f"▶️  Running Engagement in Loop {loop_num}: {eng_type} (Qty: {quantity_this_run}) - Participation Limit: {eng_participation_loops}")
                    status_update_callback(job_id, 'running', f'🔁 Loop {loop_num}/{main_loops}: Running {eng_type}')
                    
                    # Check before placing order
                    if job_id in requested_stops:
                        print(f"🛑 Stop requested for Job {job_id} just before placing order for {eng_type} in loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user before order for {eng_type}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        if page and not page.is_closed(): page.close()
                        if browser_context: browser_context.close()
                        break # Exit inner engagement_to_run loop

                    platform = 'Instagram' 
                    place_order(page, platform, eng_type, link, quantity_this_run) # This function has its own timeouts
                    total_engagements_run += 1
                    if VERBOSE_PROMO_LOGS:
                        print(f"✅ Successfully placed order for {eng_type} in Loop {loop_num}.")

                    # Check immediately after placing order
                    if job_id in requested_stops:
                        print(f"🛑 Stop requested for Job {job_id} just after placing order for {eng_type} in loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user after order for {eng_type}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        if page and not page.is_closed(): page.close()
                        if browser_context: browser_context.close()
                        break # Exit inner engagement_to_run loop
                
                if job_id in requested_stops: # Check if inner loop broke due to stop
                    if page and not page.is_closed(): page.close() # Ensure cleanup if not already done
                    if browser_context: browser_context.close()
                    break # Exit outer main_loops loop
                        
                if VERBOSE_PROMO_LOGS:
                    print(f"🏁 --- Finished Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")

                if loop_num < main_loops: 
                    if job_id in requested_stops: # Check before delay
                        print(f"🛑 Stop requested for Job {job_id} before delay after loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user before delay (loop {loop_num})."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        if page and not page.is_closed(): page.close()
                        if browser_context: browser_context.close()
                        break # Exit outer loop
                        
                    delay_seconds = 0 
                    if use_random_delay:
                        if min_delay <= max_delay:
                            delay_seconds = random.uniform(min_delay, max_delay)
                        else:
                            print("⚠️ Warning: Min delay > Max delay, using fixed delay instead.")
                            delay_seconds = fixed_delay
                    else:
                        delay_seconds = fixed_delay
                        
                    if delay_seconds > 0:
                        if VERBOSE_PROMO_LOGS:
                            print(f"⏳ Applying delay of {delay_seconds:.2f} seconds... Job ID: {job_id}")
                        status_update_callback(job_id, 'running', f'⏳ Loop {loop_num} finished. Delaying {delay_seconds:.0f}s...')
                        
                        # Use interruptible_sleep
                        if interruptible_sleep(job_id, delay_seconds, requested_stops, status_update_callback):
                            # Sleep was interrupted by a stop request
                            final_message = f"🛑 Promo '{profile_name}' stopped by user during delay after loop {loop_num}."
                            status_update_callback(job_id, 'stopped', final_message)
                            success = False
                            if page and not page.is_closed(): page.close()
                            if browser_context: browser_context.close()
                            break # Exit outer loop
                    else:
                        if VERBOSE_PROMO_LOGS:
                            print("⏭️ No delay configured.")
            # After all loops, or if a break occurred due to stop signal
            if job_id not in requested_stops and success is not False: # if not stopped and not already marked failed
                if VERBOSE_PROMO_LOGS:
                    print(f"✅ All loops completed for Job ID: {job_id}")
                success = True
                final_message = f"Profile '{profile_name}' completed successfully ({total_engagements_run} orders placed across {main_loops} loops)."
                status_update_callback(job_id, 'success', final_message)
            elif job_id in requested_stops and final_message == "Automation failed before execution.": # If stopped but no specific stop message set
                final_message = f"Promo '{profile_name}' stopped by user."
                status_update_callback(job_id, 'stopped', final_message)


    except PlaywrightError as e:
        print(f"❌ Playwright Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        final_message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    except ValueError as e: # Catches errors from Gmail helpers too
        print(f"❌ Value Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        final_message = f"Configuration/Value Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    except Exception as e:
        print(f"❌ Unexpected Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        traceback.print_exc()
        final_message = f"Unexpected Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    finally:
        # Ensure page is closed before context
        try:
            if 'page' in locals() and page and hasattr(page, 'is_closed') and not page.is_closed():
                page.close()
        except Exception as close_page_err:
            print(f"Warning closing page in finally: {close_page_err}")
        if browser_context:
            try:
                browser_context.close()
                print("🧹 Closed Playwright context for profile automation.")
            except Exception as close_err:
                # Do not raise; just log to avoid marking job as failed
                print(f"Error closing browser context in finally block: {close_err}")
             
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
        # Minimal terminal log
        print(f"Auto promo {'successful' if final_status == 'success' else 'unsuccessful'} for {link}")

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
            print(f"[Playwright Scrape] Launching new browser instance (non-headless, non-persistent).")
            browser = p.chromium.launch(
                headless=False, 
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36" 
            )
            page = context.new_page()
            
            print(f"[Playwright Scrape] Navigating to {profile_url}")
            page.goto(profile_url, wait_until='domcontentloaded', timeout=15000)
            
            print("[Playwright Scrape] Waiting for main profile content to load...")
            try:
                main_content_selector = "main[role='main']" 
                page.wait_for_selector(main_content_selector, timeout=10000)
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
                expect(first_post_link_locator).to_be_visible(timeout=5000)
                
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
                print("🧹 Closing Playwright context (profile saved).")
            except Exception as close_err:
                print(f"[Playwright Scrape] Error closing context in finally: {close_err}")
        if browser:
            try:
                browser.close()
                print("🧹 Closed Playwright browser for profile automation.")
            except Exception as close_err:
                print(f"[Playwright Scrape] Error closing browser in finally: {close_err}")

# --- NEW Balance Fetching Function ---
def get_dogehype_balance() -> Optional[str]:
    """
    Fetches the current balance from Dogehype dashboard using a quick login session.
    Returns the balance as a string or None if failed.
    """
    print("Starting balance fetch from Dogehype...")
    browser = None 
    context = None 

    try:
        with sync_playwright() as p:
            print("Launching browser for balance fetch...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            # Use the existing login function
            dashboard_page, balance = login_to_dogehype(page, context)
            
            print(f"Balance fetch completed: {balance}")
            return balance

    except Exception as e:
        print(f"Error during balance fetch: {e}")
        return None
    finally:
        if context:
            try:
                context.close()
                print("Closed browser context for balance fetch.")
            except Exception as close_err:
                print(f"Error closing context during balance fetch: {close_err}")
        if browser:
            try:
                browser.close()
                print("Closed browser for balance fetch.")
            except Exception as close_err:
                print(f"Error closing browser during balance fetch: {close_err}")