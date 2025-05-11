import customtkinter as ctk
from ui_utils import ask_confirmation # Import the dialog function

# --- Imports for Automation Logic ---
import os
import sys
import threading # Import threading for later use (optional now)
import time # Import time for potential delays
import random # Import random for quantity/delay randomization
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from dotenv import load_dotenv
# Add automation module to path if needed (adjust relative path if structure changes)
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from automation import (
        login_to_dogehype,
        place_order,
        USER_DATA_DIR, # Get the session path
        TARGET_EMAIL # Needed for login verification steps
    )
except ImportError as e:
    print(f"ERROR: Could not import from automation.py: {e}")
    print("Make sure automation.py is in the same directory or adjust sys.path.")
    # Optionally disable the submit button or show an error in UI
    # For now, we'll let it fail later if automation can't run
    pass

# Load .env file (especially for TARGET_EMAIL)
load_dotenv()
# --- End Imports for Automation ---

# Import constants from config
from config import PLATFORM_OPTIONS, ENGAGEMENT_OPTIONS, MINIMUM_QUANTITIES # Added MINIMUM_QUANTITIES

# Define globals needed by __init__ (can move into class later if preferred)
# PLATFORM_OPTIONS = ["Instagram", "TikTok", "YouTube", "X (Twitter)"]
# ENGAGEMENT_OPTIONS = ["Likes", "Views", "Comments", "Shares", "Saves", "Followers"]

# Need json import
import json 

# Local imports
from profile_editor import ProfileEditorDialog, INSTAGRAM_ENGAGEMENT_TYPES # Import the new dialog and the list

# --- Define base path ---
# Get the directory where the current script (main_app.py) is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE_PATH = os.path.join(SCRIPT_DIR, "profiles.json") # Construct full path

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.profiles = {} # Dictionary to hold loaded profiles
        self.profile_file = PROFILE_FILE_PATH # Use the absolute path
        # Load existing profiles from disk
        self._load_profiles()

        self.title("Social Media Automator")
        self.geometry("600x750") # Increased height for new sections

        # --- Title Label ---
        self.label = ctk.CTkLabel(self, text="Social Media Automator", font=ctk.CTkFont(size=20, weight="bold"))
        self.label.pack(pady=15)

        # --- Platform Selection Frame ---
        self.platform_frame = ctk.CTkFrame(self)
        self.platform_frame.pack(pady=5, padx=20, fill="x")
        self.platform_label = ctk.CTkLabel(self.platform_frame, text="Select Platform:")
        self.platform_label.pack(side=ctk.LEFT, padx=10)
        # Assume PLATFORM_OPTIONS is defined globally or passed in
        self.platform_var = ctk.StringVar(value=PLATFORM_OPTIONS[0] if PLATFORM_OPTIONS else "")
        self.platform_dropdown = ctk.CTkComboBox(self.platform_frame, values=PLATFORM_OPTIONS, variable=self.platform_var, command=self.on_platform_select)
        self.platform_dropdown.pack(side=ctk.LEFT, expand=True, fill="x", padx=10)

        # --- Engagement Type Selection Frame ---
        self.engagement_frame = ctk.CTkFrame(self)
        self.engagement_frame.pack(pady=5, padx=20, fill="x")
        self.engagement_label = ctk.CTkLabel(self.engagement_frame, text="Engagement Type:")
        self.engagement_label.pack(side=ctk.LEFT, padx=10)
        # Assume ENGAGEMENT_OPTIONS is defined globally or passed in
        self.engagement_var = ctk.StringVar(value=ENGAGEMENT_OPTIONS[0] if ENGAGEMENT_OPTIONS else "")
        # Add command callback to update placeholder when engagement changes
        self.engagement_dropdown = ctk.CTkComboBox(self.engagement_frame, 
                                                 values=ENGAGEMENT_OPTIONS, 
                                                 variable=self.engagement_var,
                                                 command=self.on_engagement_select) 
        self.engagement_dropdown.pack(side=ctk.LEFT, expand=True, fill="x", padx=10)

        # --- Post Link Input Frame ---
        self.link_frame = ctk.CTkFrame(self)
        self.link_frame.pack(pady=5, padx=20, fill="x")
        self.link_label = ctk.CTkLabel(self.link_frame, text="Post Link:")
        self.link_label.pack(side=ctk.LEFT, padx=10)
        self.link_entry = ctk.CTkEntry(self.link_frame, placeholder_text="https://...")
        self.link_entry.pack(side=ctk.LEFT, expand=True, fill="x", padx=10)

        # --- Engagement Quantity Input Frame ---
        self.quantity_frame = ctk.CTkFrame(self)
        self.quantity_frame.pack(pady=5, padx=20, fill="x")
        self.quantity_label = ctk.CTkLabel(self.quantity_frame, text="Quantity:")
        self.quantity_label.pack(side=ctk.LEFT, padx=10)
        self.quantity_entry = ctk.CTkEntry(self.quantity_frame, placeholder_text="e.g., 100")
        self.quantity_entry.pack(side=ctk.LEFT, expand=True, fill="x", padx=10)

        # --- Submit Button (for single orders) ---
        self.submit_button = ctk.CTkButton(self, text="Start Single Automation", command=self.submit_action_wrapper) # Renamed button
        self.submit_button.pack(pady=(10, 5))

        # --- Promotion Profile Section ---
        self.profile_main_frame = ctk.CTkFrame(self)
        self.profile_main_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.profile_main_frame, text="Promotion Profiles", font=ctk.CTkFont(weight="bold")).pack()

        self.profile_selection_frame = ctk.CTkFrame(self.profile_main_frame)
        self.profile_selection_frame.pack(fill="x", pady=5, padx=5)

        self.profile_label = ctk.CTkLabel(self.profile_selection_frame, text="Select Profile:")
        self.profile_label.pack(side=ctk.LEFT, padx=(5,10))

        self.profile_var = ctk.StringVar(value="")
        self.profile_dropdown = ctk.CTkComboBox(self.profile_selection_frame, 
                                                values=list(self.profiles.keys()), 
                                                variable=self.profile_var,
                                                state="readonly") # Readonly until populated
        self.profile_dropdown.pack(side=ctk.LEFT, expand=True, fill="x", padx=5)

        self.profile_button_frame = ctk.CTkFrame(self.profile_main_frame)
        self.profile_button_frame.pack(fill="x", pady=5, padx=5)

        self.add_profile_button = ctk.CTkButton(self.profile_button_frame, text="Add New", command=self.add_profile)
        self.add_profile_button.pack(side=ctk.LEFT, padx=5)
        # --- Diagnostic Print --- #
        print(f"[Init] add_profile_button created. self.add_profile exists: {hasattr(self, 'add_profile')}")

        self.edit_profile_button = ctk.CTkButton(self.profile_button_frame, text="Edit Selected", command=self.edit_profile)
        self.edit_profile_button.pack(side=ctk.LEFT, padx=5)

        self.delete_profile_button = ctk.CTkButton(self.profile_button_frame, text="Delete Selected", command=self.delete_profile, fg_color="red")
        self.delete_profile_button.pack(side=ctk.LEFT, padx=5)

        # --- Auto Promo Section --- (UI Only for now)
        self.auto_promo_frame = ctk.CTkFrame(self)
        self.auto_promo_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.auto_promo_frame, text="Auto Promotion (using selected profile)", font=ctk.CTkFont(weight="bold")).pack()

        self.auto_link_frame = ctk.CTkFrame(self.auto_promo_frame)
        self.auto_link_frame.pack(pady=5, padx=5, fill="x")

        self.auto_link_label = ctk.CTkLabel(self.auto_link_frame, text="Instagram Post Link:")
        self.auto_link_label.pack(side=ctk.LEFT, padx=10)
        self.auto_link_entry = ctk.CTkEntry(self.auto_link_frame, placeholder_text="https://www.instagram.com/p/...")
        self.auto_link_entry.pack(side=ctk.LEFT, expand=True, fill="x", padx=10)

        self.auto_promo_button = ctk.CTkButton(self.auto_promo_frame, text="Start Auto Promo", command=self.start_auto_promo)
        self.auto_promo_button.pack(pady=10)
        
        # --- Status Label --- 
        self.status_label = ctk.CTkLabel(self, text="Status: Idle", text_color="gray")
        self.status_label.pack(pady=(0, 10))

        # Initial setup
        if PLATFORM_OPTIONS:
             self.on_platform_select(self.platform_var.get())
        self._update_quantity_placeholder() 

    def _load_profiles(self):
        """Load profiles from JSON file into self.profiles and update UI."""
        from profile_manager import load_profiles
        # load_profiles returns dict; store and refresh dropdown
        self.profiles = load_profiles(self.profile_file)
        # Populate dropdown after loading
        self._update_profile_dropdown()

    def _save_profiles(self):
        """Save current self.profiles to JSON file."""
        from profile_manager import save_profiles
        save_profiles(self.profiles, self.profile_file)

    def _update_quantity_placeholder(self):
        """Updates the quantity input placeholder based on current selections."""
        platform = self.platform_var.get()
        engagement = self.engagement_var.get()
        min_qty_key = (platform, engagement)
        minimum_required = MINIMUM_QUANTITIES.get(min_qty_key)

        if minimum_required is not None:
            placeholder = f"Min: {minimum_required}"
        else:
            placeholder = "e.g., 100" # Default if no minimum defined
        
        self.quantity_entry.configure(placeholder_text=placeholder)

    def on_engagement_select(self, choice):
        """Callback when engagement type dropdown changes."""
        print(f"Engagement selected: {choice}")
        self._update_quantity_placeholder() # Update placeholder

    def on_platform_select(self, choice):
        print(f"Platform selected: {choice}")
        # --- Update engagement options based on platform ---
        if choice == "Instagram":
            options = ["Likes", "Views", "Saves", "Shares", "Reach/Impressions"]
        elif choice == "TikTok":
            options = ["Likes", "Views", "Shares", "Saves"]
        elif choice == "YouTube":
            options = ["Likes", "Views", "Subscribers", "Shares"]
        elif choice == "X (Twitter)":
            options = ["Likes", "Retweets", "Views"]
        else:
            options = ENGAGEMENT_OPTIONS # Default/fallback

        self.engagement_dropdown.configure(values=options)
        if self.engagement_var.get() not in options:
             self.engagement_var.set(options[0] if options else "")
        else:
            current_value = self.engagement_var.get()
            self.engagement_var.set(current_value)
            
        # Update quantity placeholder after platform/engagement might have changed
        self._update_quantity_placeholder() 

    def update_status(self, message, color="gray"):
        """Helper method to update the status label safely from any thread."""
        # Use after() to schedule the update on the main Tkinter thread
        self.after(0, lambda: self.status_label.configure(text=f"Status: {message}", text_color=color))

    def submit_action_wrapper(self):
        """Wraps the submit action, potentially for threading later."""
        # For now, call directly. Later, this could start a thread.
        # Disable button to prevent multiple clicks
        # --- Start automation in a separate thread --- 
        def run_in_thread():
            try:
                self._run_automation_logic()
            finally:
                # Re-enable button from the thread (via `after`)
                self.after(0, lambda: self.submit_button.configure(state=ctk.NORMAL, text="Start Automation"))
                # Update status from thread (via `after`)
                # Check current status to avoid overwriting final success/error message
                current_status = self.status_label.cget("text")
                if "Running" in current_status or "Processing" in current_status:
                     self.update_status("Idle (finished)") # Reset if still processing

        self.submit_button.configure(state=ctk.DISABLED, text="Running...")
        self.update_status("Processing...")
        # Create and start the thread
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        # --- End threading modification ---
        
        # try:
        #     self._run_automation_logic()
        # finally:
        #     # Re-enable button regardless of success/failure
        #     self.submit_button.configure(state=ctk.NORMAL, text="Start Automation")
        

    def _run_automation_logic(self):
        """Contains the core logic for getting UI data and running automation."""
        platform = self.platform_var.get()
        engagement = self.engagement_var.get()
        link = self.link_entry.get()
        quantity_str = self.quantity_entry.get() # Renamed to quantity_str

        # --- Input Validation --- 
        if not link or not link.startswith(('http://', 'https://')):
            self.update_status("Error: Invalid or missing link.", "red")
            return
        if not quantity_str.isdigit() or int(quantity_str) <= 0:
            self.update_status("Error: Invalid or missing quantity.", "red")
            return
        quantity_int = int(quantity_str)
        
        # --- Minimum Quantity Validation --- 
        min_qty_key = (platform, engagement)
        minimum_required = MINIMUM_QUANTITIES.get(min_qty_key)
        
        if minimum_required is not None: # Check if we have a minimum defined
             if quantity_int < minimum_required:
                 error_msg = f"Error: Minimum quantity for {platform} {engagement} is {minimum_required}."
                 self.update_status(error_msg, "red")
                 print(error_msg)
                 return # Stop processing
        else:
             # Optional: Warn if minimum is not defined in config
             print(f"Warning: Minimum quantity for {platform} {engagement} not defined in config.")
             # Decide whether to proceed or stop if minimum is unknown
             # For now, we proceed.
             pass 

        # --- Confirmation --- 
        confirmation_message = (
            f"Are you sure you want to proceed?\n\n" 
            f"Platform: {platform}\n"
            f"Engagement: {engagement}\n"
            f"Quantity: {quantity_int}\n"
            f"Link: {link[:50]}{'...' if len(link) > 50 else ''}"
        )

        if ask_confirmation(self, "Confirm Action", confirmation_message):
            self.update_status("User confirmed. Starting automation...", "orange")
            print("User confirmed. Starting automation...") # Keep console log
            print(f"  Platform: {platform}")
            print(f"  Engagement: {engagement}")
            print(f"  Link: {link}")
            print(f"  Quantity: {quantity_int}")

            # --- Execute Playwright Automation --- 
            try: 
                with sync_playwright() as p:
                    self.update_status("Launching browser context...", "orange")
                    context = p.chromium.launch_persistent_context(
                        USER_DATA_DIR, 
                        headless=False, # Keep visible for debugging 
                    )
                    page = context.new_page()
                    
                    self.update_status("Logging in...", "orange")
                    dashboard_page = login_to_dogehype(page, context)
                    
                    if not dashboard_page:
                         raise Exception("Login failed or did not return a page.")

                    self.update_status("Placing order...", "orange")
                    place_order(dashboard_page, platform, engagement, link, quantity_int)
                    
                    self.update_status("Automation completed successfully!", "green")
                    print("\nAutomation completed successfully!")
                    
                    # Optional: Close context automatically after success
                    # We will rely on the finally block for closing
                    # context.close()
                    # print("Browser context closed.")
                    # Consider adding a short delay or message before closing context
                    # self.after(3000, context.close) # Remove this delayed close

            except PlaywrightError as pe:
                self.update_status(f"Playwright Error: {pe}", "red")
                print(f"\nPlaywright Error: {pe}")
                import traceback
                traceback.print_exc()
            except ValueError as ve:
                self.update_status(f"Input Error: {ve}", "red") # e.g., from category mapping
                print(f"\nInput Error: {ve}")
            except Exception as e:
                self.update_status(f"An unexpected error occurred: {e}", "red")
                print(f"\nAn unexpected error occurred: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Ensure context is closed if it exists 
                # Attempt close within its own try-except
                if 'context' in locals() and context: 
                    try:
                        print("Attempting to close browser context in finally block...")
                        context.close()
                        print("Browser context closed in finally block.")
                    except Exception as close_err:
                        print(f"Error closing context: {close_err}")
                self.submit_button.configure(state=ctk.NORMAL, text="Start Automation") # Ensure button re-enabled

        else:
            self.update_status("Operation cancelled by user.", "gray")
            print("User cancelled.")

    # --- Profile Management Methods --- 
    def _update_profile_dropdown(self):
        print("[MainApp] --- Entering _update_profile_dropdown ---") # Added entry point
        profile_names = list(self.profiles.keys())
        print(f"[MainApp] Raw profiles dictionary keys: {self.profiles.keys()}") # Log raw keys
        print(f"[MainApp] Profile names list created: {profile_names}") # Confirm list creation

        # Add check right before configure
        if not isinstance(profile_names, list):
             print(f"[MainApp] CRITICAL WARNING: profile_names is NOT a list before configure! Type: {type(profile_names)}")
        elif not profile_names:
             print("[MainApp] WARNING: profile_names is empty before configure.")
        else:
            print(f"[MainApp] Configuring dropdown with values: {profile_names}")

        self.profile_dropdown.configure(values=profile_names)
        print("[MainApp] self.profile_dropdown.configure(values=...) called.") # Confirm call

        if profile_names:
            current_selection = self.profile_var.get()
            print(f"[MainApp] Profile names exist. Current selection variable: '{current_selection}'") # Log current var value
            # Try to keep current selection if it still exists, else select first
            if current_selection in profile_names:
                print(f"[MainApp] Setting dropdown value to existing selection: {current_selection}")
                self.profile_dropdown.set(current_selection)
                # print(f"[MainApp] Dropdown set to existing selection: {current_selection}") # Redundant log removed
            else:
                new_selection = profile_names[0]
                print(f"[MainApp] Setting dropdown value to first profile: {new_selection}")
                self.profile_dropdown.set(new_selection) # Select first profile if exists
                # print(f"[MainApp] Dropdown set to first profile: {profile_names[0]}") # Redundant log removed
            print("[MainApp] Configuring dropdown state to 'normal'")
            self.profile_dropdown.configure(state="normal")
        else:
            print("[MainApp] No profile names. Clearing dropdown value.")
            self.profile_dropdown.set("")
            print("[MainApp] Configuring dropdown state to 'disabled'")
            self.profile_dropdown.configure(state="disabled")
            # print("[MainApp] Dropdown cleared and disabled.") # Redundant log removed

        # Update button states based on whether *any* profile exists now
        has_profiles = bool(profile_names)
        button_state = ctk.NORMAL if has_profiles else ctk.DISABLED
        print(f"[MainApp] Updating button states. Has profiles: {has_profiles}, New state: {button_state}")
        self.delete_profile_button.configure(state=button_state)
        self.edit_profile_button.configure(state=button_state)
        self.auto_promo_button.configure(state=button_state)
        print("[MainApp] --- Exiting _update_profile_dropdown ---") # Added exit point

    # --- NEW METHOD to handle results from ProfileEditorDialog ---
    def _handle_profile_dialog_close(self, result, is_edit):
        action = "edit" if is_edit else "add"
        print(f"\n--- [MainApp] Callback: _handle_profile_dialog_close triggered for action: {action} ---")
        print(f"[MainApp] Received result: {result}")

        if result:
            profile_name, profile_data = result
            # Check if name changed during edit to remove old key
            # Note: We need the original name if it was an edit. This is complex
            # with this callback structure. Let's simplify - editing always updates/adds new name.
            # If the name wasn't changed, it just overwrites itself.
            # If the name *was* changed, the old name remains until explicitly deleted.
            # TODO: Revisit name change handling during edit if needed.

            print(f"Updating profiles dictionary: {profile_name} -> {profile_data}")
            self.profiles[profile_name] = profile_data
            self._save_profiles()  # Save the updated dict to file
            self._update_profile_dropdown() # Refresh the UI dropdown
            self.profile_dropdown.set(profile_name) # Select the added/edited profile

            # Show success status
            status_message = f"Profile '{profile_name}' {'updated' if is_edit else 'added'} successfully."
            self.update_status(status_message, "green")
            print(status_message)
        else:
            # Dialog was cancelled
            status_message = f"Profile {action} cancelled."
            self.update_status(status_message, "gray")
            print(status_message)
        print(f"--- [MainApp] Callback: _handle_profile_dialog_close finished for action: {action} ---")

    def add_profile(self):
        print("\n--- [MainApp] add_profile method called ---")
        print("Opening Add Profile dialog...")
        # Just create the dialog. It will call _handle_profile_dialog_close on save/cancel.
        dialog = ProfileEditorDialog(master=self, logical_parent=self)
        # No need to process result here anymore
        # result = dialog.get_result()
        # ... rest of old logic removed ...

    def edit_profile(self):
        selected_profile_name = self.profile_var.get()
        if selected_profile_name:
            print(f"Opening Edit Profile dialog for: {selected_profile_name}")
            existing_data = self.profiles.get(selected_profile_name)
            if not existing_data:
                print("Error: Could not find data for selected profile.")
                self.update_status(f"Error: Data not found for '{selected_profile_name}'.", "red")
                return

            # Just create the dialog. It will call _handle_profile_dialog_close on save/cancel.
            dialog = ProfileEditorDialog(master=self,
                                         logical_parent=self,
                                         existing_profile_data=existing_data,
                                         existing_profile_name=selected_profile_name)
            # No need to process result here anymore
            # result = dialog.get_result()
            # ... rest of old logic removed ...
        else:
            print("No profile selected to edit.")
            self.update_status("Please select a profile to edit.", "orange")

    def delete_profile(self):
        selected_profile_name = self.profile_var.get()
        if selected_profile_name:
            # Add confirmation
            if ask_confirmation(self, "Confirm Deletion", f"Are you sure you want to delete profile '{selected_profile_name}'?"):
                print(f"Deleting profile: {selected_profile_name}")
                if selected_profile_name in self.profiles:
                    del self.profiles[selected_profile_name]
                    self._save_profiles()
                    self._update_profile_dropdown()
                    print(f"Profile '{selected_profile_name}' deleted.")
                else:
                     print("Error: Selected profile not found in data.")
            else:
                print("Deletion cancelled.")
        else:
            print("No profile selected to delete.")
            
    # --- Auto Promo Method ---
    def start_auto_promo(self):
        selected_profile_name = self.profile_var.get()
        link = self.auto_link_entry.get()

        if not selected_profile_name:
            self.update_status("Error: No profile selected for Auto Promo.", "red")
            return
        if not link or not link.startswith('https://www.instagram.com/'):
            self.update_status("Error: Invalid or missing Instagram link for Auto Promo.", "red")
            return

        profile_data = self.profiles.get(selected_profile_name)
        if not profile_data:
            self.update_status(f"Error: Could not load data for profile '{selected_profile_name}'.", "red")
            return

        # --- Start auto promo in a separate thread ---
        def run_auto_promo_thread():
            try:
                self._execute_auto_promo(selected_profile_name, profile_data, link)
            finally:
                # Re-enable button from the thread (via `after`)
                self.after(0, lambda: self.auto_promo_button.configure(state=ctk.NORMAL, text="Start Auto Promo"))
                # Update status if it was still running
                current_status = self.status_label.cget("text")
                if "Auto Promo Running" in current_status or "Placing order" in current_status:
                    self.update_status("Auto Promo Idle (finished)")

        self.auto_promo_button.configure(state=ctk.DISABLED, text="Running Auto Promo...")
        self.update_status(f"Auto Promo Running for '{selected_profile_name}'...", "orange")

        thread = threading.Thread(target=run_auto_promo_thread, daemon=True)
        thread.start()

    def _execute_auto_promo(self, profile_name, profile_data, link):
        """Handles the actual execution of the auto-promo sequence in a thread."""
        print(f"Executing Auto Promo for profile: {profile_name}, Link: {link}")
        # print(f"Profile data: {profile_data}") # Can be verbose, uncomment if needed

        context = None
        errors_occurred = []

        # --- Extract Loop Settings ---
        loop_count = max(1, profile_data.get('loop_count', 1)) # Ensure at least 1 loop
        use_random_delay = profile_data.get('use_random_delay', False)
        fixed_delay = profile_data.get('loop_delay', 0)
        min_delay = profile_data.get('min_delay', 0)
        max_delay = profile_data.get('max_delay', 0)

        try:
            with sync_playwright() as p:
                self.update_status("Auto Promo: Launching browser...", "orange")
                context = p.chromium.launch_persistent_context(
                    USER_DATA_DIR,
                    headless=False,
                )
                page = context.new_page()

                self.update_status("Auto Promo: Logging in...", "orange")
                dashboard_page = login_to_dogehype(page, context)

                if not dashboard_page:
                    raise Exception("Auto Promo: Login failed or did not return a page.")

                # --- Main Loop ---
                for loop_index in range(loop_count):
                    loop_num = loop_index + 1
                    self.update_status(f"Auto Promo Loop {loop_num}/{loop_count}: Starting...", "orange")
                    print(f"\n--- Starting Loop {loop_num}/{loop_count} ---")

                    # --- Iterate through defined engagement types ---
                    for eng_type in INSTAGRAM_ENGAGEMENT_TYPES:

                        # Check if this type should run in this loop iteration
                        loop_repeats = profile_data.get(f'{eng_type}_loop_repeats', 0)
                        if loop_index > 0 and loop_repeats < loop_index:
                            print(f"  Skipping {eng_type} (loop repeats exceeded for this cycle). ")
                            continue # Skip this engagement type for this loop iteration

                        # Determine quantity for this iteration
                        use_random_qty = profile_data.get(f'{eng_type}_use_random', False)
                        quantity_to_order = 0

                        if use_random_qty:
                            min_qty = profile_data.get(f'{eng_type}_min_qty', 0)
                            max_qty = profile_data.get(f'{eng_type}_max_qty', 0)
                            if max_qty >= min_qty and max_qty > 0:
                                try:
                                    quantity_to_order = random.randint(min_qty, max_qty)
                                    print(f"  Random quantity for {eng_type}: {quantity_to_order} (Range: {min_qty}-{max_qty})")
                                except ValueError as e:
                                     print(f"  Error generating random quantity for {eng_type} ({min_qty}-{max_qty}): {e}")
                                     quantity_to_order = 0 # Treat as 0 if random generation fails
                            else:
                                print(f"  Skipping random {eng_type} (invalid range or max=0: {min_qty}-{max_qty})")
                                quantity_to_order = 0
                        else:
                            quantity_to_order = profile_data.get(f'{eng_type}_quantity', 0)

                        # Place order if quantity > 0
                        if quantity_to_order > 0:
                            status_msg = f"Loop {loop_num}/{loop_count}: Placing order for {quantity_to_order} {eng_type}..."
                            self.update_status(status_msg, "orange")
                            print(f"  Placing order: Instagram, {eng_type}, {link}, {quantity_to_order}")
                            try:
                                place_order(dashboard_page, "Instagram", eng_type, link, quantity_to_order)
                                print(f"    Order placed successfully for {eng_type}.")
                                time.sleep(1) # Short pause after successful order
                            except (PlaywrightError, ValueError, Exception) as order_err:
                                error_msg = f"Loop {loop_num}/{loop_count}: Error placing order for {eng_type}: {order_err}"
                                print(f"    {error_msg}")
                                self.update_status(error_msg, "red")
                                errors_occurred.append(f"Loop {loop_num} - {eng_type}: {order_err}")
                                time.sleep(1) # Still pause briefly after error
                        else:
                            print(f"  Skipping {eng_type} (quantity is 0 for this iteration).")

                    # --- End of engagement type loop for this iteration ---
                    print(f"--- Finished Loop {loop_num}/{loop_count} ---")

                    # --- Delay between loops (if not the last one) ---
                    if loop_index < loop_count - 1:
                        delay_seconds = 0
                        if use_random_delay:
                            if max_delay >= min_delay:
                                try:
                                    delay_seconds = random.uniform(min_delay, max_delay)
                                    print(f"Random delay calculated: {delay_seconds:.2f}s (Range: {min_delay}-{max_delay})")
                                except ValueError as e:
                                    print(f"Error generating random delay ({min_delay}-{max_delay}): {e}, using fixed delay {fixed_delay}s instead.")
                                    delay_seconds = fixed_delay # Fallback to fixed delay
                            else:
                                print(f"Invalid random delay range ({min_delay}-{max_delay}), using fixed delay {fixed_delay}s instead.")
                                delay_seconds = fixed_delay # Fallback
                        else:
                            delay_seconds = fixed_delay

                        if delay_seconds > 0:
                            delay_msg = f"Loop {loop_num}/{loop_count}: Delaying for {delay_seconds:.1f} seconds..."
                            print(delay_msg)
                            self.update_status(delay_msg, "orange")
                            time.sleep(delay_seconds)
                        else:
                            print("No delay between loops.")

                # --- End of Main Loop ---

                # Final status update
                if not errors_occurred:
                    success_msg = f"Auto Promo for '{profile_name}' ({loop_count} loops) completed successfully!"
                    self.update_status(success_msg, "green")
                    print(f"\n{success_msg}")
                else:
                    fail_msg = f"Auto Promo for '{profile_name}' ({loop_count} loops) finished with errors."
                    self.update_status(fail_msg, "orange")
                    print(f"\n{fail_msg}")
                    print("Errors encountered:")
                    for err in errors_occurred:
                        print(f"  - {err}")

        except (PlaywrightError, Exception) as promo_err:
            # Errors during setup (login, etc.)
            error_msg = f"Auto Promo Error for '{profile_name}': {promo_err}"
            self.update_status(error_msg, "red")
            print(f"\n{error_msg}")
            import traceback
            traceback.print_exc()
        finally:
            # Ensure context is closed
            if context:
                try:
                    print("Auto Promo: Attempting to close browser context...")
                    context.close()
                    print("Auto Promo: Browser context closed.")
                except Exception as close_err:
                    print(f"Auto Promo: Error closing context: {close_err}")
            # Button re-enabling is handled in the calling thread wrapper

if __name__ == "__main__":
    app = App()
    app.mainloop()
