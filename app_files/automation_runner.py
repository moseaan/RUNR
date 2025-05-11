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

# Load environment variables from .env file
load_dotenv()

# Get credentials and URL
TARGET_EMAIL = os.getenv("TARGET_EMAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
DOGEHYPE_URL = config.TARGET_WEBSITE_URL
MAIL_URL = "https://www.mail.com/"

def login_to_dogehype(page: Page, context: BrowserContext) -> Page:
    # --- PASTE of login_to_dogehype function from automation.py --- 
    # (Content identical to the function previously in automation.py)
    if not TARGET_EMAIL or not MAIL_PASSWORD:
        raise ValueError("Missing TARGET_EMAIL or MAIL_PASSWORD in .env file")

    print("Starting Dogehype login process...")
    print(f"Navigating to {DOGEHYPE_URL}")
    page.goto(DOGEHYPE_URL, wait_until='load', timeout=60000)
    try:
        sign_up_button = page.get_by_role("banner").get_by_role("button", name=re.compile("Sign Up|Sign In", re.IGNORECASE)).first
        expect(sign_up_button).to_be_visible(timeout=15000)
        sign_up_button.click()
        print("Clicked Sign Up/Sign In button.")
        try:
            print("Checking if already on dashboard after Sign In click (looking for: '+ Add Funds' button)")
            expect(page.get_by_role("button", name="+ Add Funds")).to_be_visible(timeout=10000)
            print("Login successful via session cookie after clicking Sign In!")
            return page
        except Exception:
            print("Not on dashboard yet, proceeding with email input...")
            pass
    except Exception as e:
        print(f"Could not find or click Sign Up/Sign In button: {e}. Assuming login form is present.")

    email_input = page.get_by_role("textbox", name="Enter Your Email Address")
    expect(email_input).to_be_visible(timeout=15000)
    email_input.fill(TARGET_EMAIL)
    print(f"Filled email: {TARGET_EMAIL}")

    sign_in_button = page.get_by_role("button", name="Sign in without password")
    expect(sign_in_button).to_be_enabled(timeout=10000)
    sign_in_button.click()
    print("Clicked 'Sign in without password'. Verification email requested.")

    print("Opening new tab for mail.com...")
    mail_page = context.new_page()
    dashboard_page = page
    try:
        mail_page.goto(MAIL_URL, wait_until='domcontentloaded', timeout=90000)
        print("Navigated to mail.com.")
        try:
            accept_cookies_button = mail_page.locator('#onetrust-accept-btn-handler').first
            if accept_cookies_button.is_visible(timeout=5000):
                accept_cookies_button.click()
                print("Accepted cookies on mail.com.")
        except Exception:
            print("No cookie banner found or could not click it.")

        login_link = mail_page.get_by_role("link", name="Log in")
        expect(login_link).to_be_visible(timeout=15000)
        login_link.click()
        print("Clicked mail.com login link.")

        mail_email_input = mail_page.get_by_role("textbox", name="Email address")
        expect(mail_email_input).to_be_visible(timeout=10000)
        mail_email_input.fill(TARGET_EMAIL)

        mail_password_input = mail_page.get_by_role("textbox", name="Password")
        expect(mail_password_input).to_be_visible(timeout=10000)
        mail_password_input.fill(MAIL_PASSWORD)
        print("Filled mail.com credentials.")

        mail_login_button = mail_page.get_by_role("button", name="Log in")
        expect(mail_login_button).to_be_enabled(timeout=10000)
        mail_login_button.click()
        print("Clicked mail.com login button.")

        try:
            error_message_locator = mail_page.locator('.form-error:has-text("incorrect"), .error:has-text("Invalid password")').first
            if error_message_locator.is_visible(timeout=5000):
                error_text = error_message_locator.text_content()
                print(f"Detected mail.com login error: {error_text}")
                raise ValueError("Incorrect mail.com password or email detected.")
            print("No immediate mail.com login error message detected.")
        except Exception as e:
             print(f"Did not find specific mail.com error message (or check timed out): {e}")
             pass

        print("Navigating to Spam folder...")
        spam_frame_locator = mail_page.locator("[data-test='third-party-frame_mail']")
        expect(spam_frame_locator).to_be_visible(timeout=20000)
        try:
            frame_element = spam_frame_locator.element_handle(timeout=10000)
            if not frame_element:
                raise Exception("Could not get frame element handle.")
            spam_frame = frame_element.content_frame()
            if not spam_frame:
                 raise Exception("Could not get content_frame from element handle.")
        except Exception as e:
            print(f"Error getting frame content: {e}")
            mail_page.screenshot(path="error_frame_screenshot.png")
            raise

        spam_link = spam_frame.get_by_role("link", name="Spam")
        expect(spam_link).to_be_visible(timeout=15000)
        spam_link.click()
        print("Clicked Spam folder.")
        time.sleep(8)

        print("Clicking verification email row using user-provided XPath...")
        if not spam_frame:
            raise Exception("Spam frame was not properly identified before trying to click email.")
        email_xpath = "/html/body/div[3]/div[3]/div[3]/div[1]/div[1]/div/form/div[2]/div/div/table/tbody/tr[1]/td[2]"
        verification_email_row = spam_frame.locator(f"xpath={email_xpath}")
        expect(verification_email_row).to_be_visible(timeout=25000)
        verification_email_row.click()
        print("Clicked verification email row.")

        print("Locating and clicking verification link inside email...")
        email_content_frame_locator = spam_frame.locator("iframe[name=\'mail-display-content\']")
        expect(email_content_frame_locator).to_be_visible(timeout=15000)
        try:
            email_frame_element = email_content_frame_locator.element_handle(timeout=10000)
            if not email_frame_element:
                raise Exception("Could not get email frame element handle.")
            email_content_frame = email_frame_element.content_frame()
            if not email_content_frame:
                raise Exception("Could not get content_frame from email element handle.")
        except Exception as e:
            print(f"Error getting email frame content: {e}")
            mail_page.screenshot(path="error_email_frame_screenshot.png")
            raise

        verify_link_locator = email_content_frame.get_by_role("link", name="Verify Your Email")
        expect(verify_link_locator).to_be_visible(timeout=15000)

        print("Expecting popup after clicking verification link...")
        with mail_page.expect_popup() as popup_info:
            verify_link_locator.click()
        dashboard_page = popup_info.value
        print("Popup received.")
        dashboard_page.wait_for_load_state('load', timeout=60000)

        try:
            intermediate_link = dashboard_page.get_by_text("https://api.mojoauth.com/")
            expect(intermediate_link).to_be_visible(timeout=15000)
            intermediate_link.click()
            print("Clicked intermediate mojoauth link.")
            dashboard_page.wait_for_load_state('load', timeout=60000)
        except Exception as e:
            print(f"Could not find or click intermediate mojoauth link (maybe not needed?): {e}")

        final_dashboard_url = "https://dogehype.com/dashboard?state_id=680ade2098b2e3de475b4b1d"
        print(f"Navigating popup page to dashboard URL: {final_dashboard_url}")
        dashboard_page.goto(final_dashboard_url, wait_until='load', timeout=60000)

        print("Pausing briefly for dashboard elements to render...")
        dashboard_page.wait_for_timeout(3000)

        print("Verifying dashboard by looking for: '+ Add Funds' button")
        expect(dashboard_page.get_by_role("button", name="+ Add Funds")).to_be_visible(timeout=30000)
        print("Successfully loaded Dogehype dashboard page.")
        return dashboard_page

    finally:
        if 'mail_page' in locals() and not mail_page.is_closed():
            mail_page.close()
            print("Closed mail.com tab.")
# --- End of login_to_dogehype --- 

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
    """Runs a single automation task based on direct inputs."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'Starting single promo for {engagement_type}...')
    success = False
    message = "Automation failed before execution."
    # browser = None # Initialize browser variable - removed

    # --- Original Code Logic --- 
    context = None # Initialize context for finally block
    try:
        with sync_playwright() as p:
            print(f"Using Chrome Profile Path: {config.CHROME_PROFILE_PATH}")
            print(f"Using Chrome Executable: {config.CHROME_EXECUTABLE_PATH}")
            context = p.chromium.launch_persistent_context(
                config.CHROME_PROFILE_PATH, 
                headless=False, 
                # slow_mo=50, # Keep slow_mo for stability if needed
                channel="chrome", # Specify Chrome channel
                executable_path=config.CHROME_EXECUTABLE_PATH # Specify executable path
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            # Although profile loads the session, call login func to handle potential edge cases/verification
            # The login function should ideally check if already logged in first.
            status_update_callback(job_id, 'running', 'Verifying Dogehype login...') 
            page = login_to_dogehype(page, context) # Re-assign page in case a new one was created
            
            status_update_callback(job_id, 'running', f'Placing order: {quantity} {engagement_type}...')
            place_order(page, platform, engagement_type, link, quantity)
            
            print(f"Order placed successfully for Job ID: {job_id}")
            success = True
            message = f"Single promo successful: {quantity} {engagement_type} for {link}"
            status_update_callback(job_id, 'success', message)
            
            # context.close() # Close context here after successful run - Closed in finally

    except PlaywrightError as e:
        print(f"Playwright Error during single automation (Job ID: {job_id}): {e}")
        message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except ValueError as e:
        print(f"Value Error during single automation (Job ID: {job_id}): {e}")
        message = f"Configuration/Value Error: {e}"
        status_update_callback(job_id, 'failed', message)
    except Exception as e:
        print(f"Unexpected Error during single automation (Job ID: {job_id}): {e}")
        import traceback
        traceback.print_exc()
        message = f"Unexpected Error: {e}"
        status_update_callback(job_id, 'failed', message)
    finally:
        # Clean up context 
        if context: 
             try:
                 context.close()
                 print("Closed Playwright browser context.")
             except Exception as close_err:
                  print(f"Error closing context: {close_err}")
             
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        # Save history entry regardless of success/failure
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
        print(f"Single Promo Job {job_id} finished. Status: {"Success" if success else "Failed"}. Duration: {duration:.2f}s")
    # --- End of Original Code Logic ---

# --- Profile Automation --- (Added Stop Check) ---
def run_automation_profile(profile_name: str, profile_data: dict, link: str, job_id: str, 
                           status_update_callback: callable, save_history_callback: callable, 
                           requested_stops: set): # Added requested_stops set argument
    """Runs automation based on a saved profile, checking for stop requests."""
    start_time = datetime.datetime.now()
    status_update_callback(job_id, 'running', f'Starting profile promo \'{profile_name}\'...')
    print(f"--- Running Profile: {profile_name} for Link: {link} (Job ID: {job_id}) ---")
    # print(f"Profile Data Received: {profile_data}") # Can be verbose

    success = False
    final_message = "Automation failed before execution."
    browser_context = None # Use context variable for clarity
    page = None
    total_engagements_run = 0
    main_loops = 1 

    try:
        # --- Check for immediate stop before even starting Playwright --- 
        if job_id in requested_stops:
            print(f"Stop requested for Job {job_id} before starting Playwright.")
            final_message = f"Promo '{profile_name}' stopped by user before starting."
            status_update_callback(job_id, 'stopped', final_message)
            # No browser cleanup needed here
            return # Exit early
            
        # --- Extract settings --- 
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

        # --- Initialize Playwright --- 
        with sync_playwright() as p:
            # --- Check for stop again before launching browser --- 
            if job_id in requested_stops:
                 print(f"Stop requested for Job {job_id} just before launching browser.")
                 final_message = f"Promo '{profile_name}' stopped by user before browser launch."
                 status_update_callback(job_id, 'stopped', final_message)
                 return # Exit early
            
            print(f"Using Chrome Profile Path: {config.CHROME_PROFILE_PATH}")
            print(f"Using Chrome Executable: {config.CHROME_EXECUTABLE_PATH}")
            browser_context = p.chromium.launch_persistent_context(
                config.CHROME_PROFILE_PATH, 
                headless=False, 
                slow_mo=50,
                channel="chrome", # Specify Chrome channel
                executable_path=config.CHROME_EXECUTABLE_PATH # Specify executable path
            )
            page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
            
            status_update_callback(job_id, 'running', 'Logging into Dogehype...')
            page = login_to_dogehype(page, browser_context) 
            
            # --- Main Loop --- 
            for loop_num in range(1, main_loops + 1):
                # --- Check for stop before starting loop --- 
                if job_id in requested_stops:
                    print(f"Stop requested for Job {job_id} before starting loop {loop_num}.")
                    final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num-1}."
                    status_update_callback(job_id, 'stopped', final_message)
                    success = False # Mark as not fully successful
                    break # Exit main loop
                    
                print(f"\n--- Starting Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")
                status_update_callback(job_id, 'running', f'Running loop {loop_num}/{main_loops}...')
                
                # --- Inner Engagement Participation Check --- 
                for engagement_setting in engagements_to_run:
                    # --- Check for stop before placing order --- 
                    if job_id in requested_stops:
                        print(f"Stop requested for Job {job_id} before placing order in loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        break # Exit inner loop

                    eng_type = engagement_setting.get('type')
                    eng_participation_loops = engagement_setting.get('loops', 1)
                    
                    if not eng_type:
                        print(f"Skipping engagement with missing type: {engagement_setting}")
                        continue
                        
                    should_run_this_loop = (loop_num == 1) or (loop_num <= eng_participation_loops)
                    
                    if not should_run_this_loop:
                        print(f"  Skipping {eng_type} in Loop {loop_num} (Participation limit: {eng_participation_loops}, and not first loop)")
                        continue 
                    
                    # --- Determine quantity and run --- 
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
                
                # --- Check if inner loop was broken by stop request --- 
                if job_id in requested_stops:
                    break # Exit outer loop as well
                        
                # --- End of Inner Engagement Loop --- 
                print(f"--- Finished Main Loop {loop_num}/{main_loops} --- Job ID: {job_id}")

                # --- Apply Delay BETWEEN Main Loops (check for stop before sleep) --- 
                if loop_num < main_loops: 
                    if job_id in requested_stops:
                        print(f"Stop requested for Job {job_id} before delay after loop {loop_num}.")
                        final_message = f"Promo '{profile_name}' stopped by user during loop {loop_num}."
                        status_update_callback(job_id, 'stopped', final_message)
                        success = False
                        break # Exit main loop
                        
                    delay_seconds = 0 # Calculate actual delay
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
                         # Check for stop one last time before potentially long sleep
                         if job_id in requested_stops:
                             print(f"Stop requested for Job {job_id} just before sleeping.")
                             final_message = f"Promo '{profile_name}' stopped by user before delay."
                             status_update_callback(job_id, 'stopped', final_message)
                             success = False
                             break # Exit main loop
                         time.sleep(delay_seconds)
                    else:
                         print("No delay configured.")
                         
            # --- End of Main Loop --- 
            
            # Check if loop finished normally or was stopped
            if job_id not in requested_stops:
                print(f"All loops completed for Job ID: {job_id}")
                success = True
                final_message = f"Profile '{profile_name}' completed successfully ({total_engagements_run} orders placed across {main_loops} loops)."
                status_update_callback(job_id, 'success', final_message)
            # If it was stopped, the final_message and status were already set inside the loop
            
            if browser_context: browser_context.close()
            browser_context = None

    except PlaywrightError as e:
        print(f"Playwright Error during profile automation ({profile_name}, Job ID: {job_id}): {e}")
        final_message = f"Playwright Error: {e}"
        status_update_callback(job_id, 'failed', final_message)
        success = False
    except ValueError as e:
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
                 print("Closed Playwright context in finally block.")
             except Exception as close_err:
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
            "status": final_status, # Use determined final status
            "message": final_message
        }
        save_history_callback(history_entry) # Calls app.save_history_entry_callback
        print(f"Profile Promo Job {job_id} ('{profile_name}') finished. Final Status: {final_status}. Duration: {duration:.2f}s")

# --- NEW Playwright-based Scraping Function ---
def scrape_latest_post_with_playwright(username: str) -> Tuple[Optional[str], Optional[datetime.datetime]]:
    """
    Scrapes the latest Instagram post URL and timestamp for a given username using Playwright.
    This version attempts to handle login via a persistent Chrome profile.
    """
    profile_url = f"https://www.instagram.com/{username}/"
    post_url: Optional[str] = None
    timestamp_utc: Optional[datetime.datetime] = None  # Placeholder, not implemented yet

    if not config.CHROME_PROFILE_PATH or not os.path.exists(config.CHROME_PROFILE_PATH):
        print(f"[Playwright Scrape] Error: CHROME_PROFILE_PATH is not set or does not exist: {config.CHROME_PROFILE_PATH}")
        return None, None

    print(f"[Playwright Scrape] Attempting to scrape: {profile_url} using profile: {config.CHROME_PROFILE_PATH}")
    context: Optional[BrowserContext] = None # Define context here for finally block

    try:
        with sync_playwright() as p:
            print(f"[Playwright Scrape] Launching persistent context: {config.CHROME_PROFILE_PATH}")
            context = p.chromium.launch_persistent_context(
                config.CHROME_PROFILE_PATH,
                headless=True,
                channel="chrome",
                executable_path=config.CHROME_EXECUTABLE_PATH,
                timeout=60000
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            print(f"[Playwright Scrape] Navigating to {profile_url}")
            page.goto(profile_url, wait_until='domcontentloaded', timeout=90000)
            
            print("[Playwright Scrape] Waiting for main profile content to load...")
            try:
                # Wait for a general container that should exist on a profile page
                main_content_selector = "main[role='main']" 
                page.wait_for_selector(main_content_selector, timeout=45000) # Increased timeout
                print(f"[Playwright Scrape] Main content ({main_content_selector}) loaded.")
            except PlaywrightError as e:
                print(f"[Playwright Scrape] Timeout or error waiting for main content ({main_content_selector}) for '{username}': {type(e).__name__} - {e}")
                page.screenshot(path="debug_instagram_main_content_fail.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_main_content_fail.png")
                # context.close() # Already handled by with statement or finally
                return None, None

            # Additional short wait for any dynamic elements within main content
            page.wait_for_timeout(3000)

            print("[Playwright Scrape] Searching for the first post link within article section...")
            # Selector for the first post: an <a> tag with href starting /p/ inside an <article> element, within the main content
            # This is a common structure for Instagram posts.
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
                    page.screenshot(path="debug_instagram_invalid_href.png")
                    print("[Playwright Scrape] Saved screenshot to debug_instagram_invalid_href.png")
                    return None, None
            except PlaywrightError as e: # Catches TimeoutError from expect().to_be_visible()
                print(f"[Playwright Scrape] Could not find or make visible the post link ({post_link_selector}) for '{username}': {type(e).__name__} - {e}")
                page.screenshot(path="debug_instagram_post_not_found.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_post_not_found.png")
                return None, None

            # context.close() # Handled by with sync_playwright() and finally block
            return post_url, timestamp_utc

    except PlaywrightError as e:
        print(f"[Playwright Scrape] Playwright-specific error for '{username}': {type(e).__name__} - {e}")
        if page: # Check if page exists before trying to screenshot
            try:
                page.screenshot(path="debug_instagram_playwright_error.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_playwright_error.png")
            except Exception as screenshot_err:
                print(f"[Playwright Scrape] Could not take screenshot on Playwright error: {screenshot_err}")
        return None, None
    except Exception as e:
        print(f"[Playwright Scrape] Unexpected error for '{username}': {type(e).__name__} - {e}")
        # page might not be defined if error occurred before its assignment or in context creation
        if 'page' in locals() and page: 
            try:
                page.screenshot(path="debug_instagram_unexpected_error.png")
                print("[Playwright Scrape] Saved screenshot to debug_instagram_unexpected_error.png")
            except Exception as screenshot_err:
                print(f"[Playwright Scrape] Could not take screenshot on unexpected error: {screenshot_err}")
        # Consider logging traceback for unexpected errors:
        # import traceback
        # print(traceback.format_exc())
        return None, None
    finally:
        if context: # Check if context was successfully created
            try:
                context.close()
                print("[Playwright Scrape] Context closed in finally block.")
            except Exception as close_err:
                print(f"[Playwright Scrape] Error closing context in finally: {close_err}")

# Example of running the runner directly (for testing)
# if __name__ == "__main__":
#     print("Testing automation runner...")
#     # Load a test profile (replace with actual loading if needed)
#     import profile_manager
#     import history_manager # Need this for testing
#     # Dummy callbacks for testing
#     def dummy_status_update(job_id, status, message):
#         print(f"[Dummy Status] Job {job_id}: {status} - {message}")
#     def dummy_history_save(entry):
#         print(f"[Dummy History] Saving: {entry}")
#         history_manager.save_history_entry(entry) # Use the real saver for test persistence
#
#     test_profiles = profile_manager.load_profiles()
#     test_profile_name = "Test" # Or choose one that exists
#     if test_profile_name in test_profiles:
#         test_profile_data = test_profiles[test_profile_name]
#         test_link = "https://www.instagram.com/reel/C6Jh2ZxuUaA/" # Replace with a valid test link
#         test_job_id = f"test_profile_{time.time()}"
#         run_automation_profile(test_profile_name, test_profile_data, test_link, test_job_id, dummy_status_update, dummy_history_save)
#     else:
#         print(f"Test profile '{test_profile_name}' not found in profiles.json")
#
#     # Test single run
#     test_single_job_id = f"test_single_{time.time()}"
#     run_single_automation("Instagram", "Views", "https://www.instagram.com/reel/C6Jh2ZxuUaA/", 110, test_single_job_id, dummy_status_update, dummy_history_save) 