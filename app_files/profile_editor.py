import customtkinter as ctk
from config import MINIMUM_QUANTITIES # To show minimums in labels
import tkinter.messagebox as messagebox # For showing validation errors
from profile_manager import save_profiles # <--- Import save_profiles

# Define which engagement types are relevant for Instagram profiles
# (Should ideally match the options shown in main_app for Instagram)
INSTAGRAM_ENGAGEMENT_TYPES = ["Likes", "Views", "Saves", "Shares", "Reach/Impressions"]

class ProfileEditorDialog(ctk.CTkToplevel):
    def __init__(self, master, *, logical_parent, existing_profile_data=None, existing_profile_name=None):
        super().__init__(master)
        
        self.logical_parent = logical_parent # Reference to the object holding profiles
        self.result = None   # Store the result (profile name, profile data)
        self.existing_name = existing_profile_name
        self.existing_data = existing_profile_data or {}

        self.title("Edit Promotion Profile" if existing_profile_data else "Add New Promotion Profile")
        self.geometry("600x680") # Increased height slightly for status bar
        self.transient(master)
        self.grab_set()

        # --- Status Bar (Top Right) ---
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(side=ctk.TOP, fill="x", padx=15, pady=(5, 0))
        self.status_label = ctk.CTkLabel(self.status_frame, text="", width=200, anchor="e")
        # Pack status label to the right
        self.status_label.pack(side=ctk.RIGHT, padx=5)
        self._clear_status_after_delay_id = None # To manage hiding the status

        # --- Widgets --- 
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, fill="both", padx=15, pady=(5, 15)) # Adjust padding

        # Profile Name
        self.name_frame = ctk.CTkFrame(self.main_frame)
        self.name_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(self.name_frame, text="Profile Name:", width=100).pack(side=ctk.LEFT, padx=5)
        self.name_entry = ctk.CTkEntry(self.name_frame, placeholder_text="e.g., My Standard Push")
        self.name_entry.pack(side=ctk.LEFT, expand=True, fill="x", padx=5)
        if existing_profile_name:
            self.name_entry.insert(0, existing_profile_name)

        # --- Engagement Quantities Section ---
        ctk.CTkLabel(self.main_frame, text="Instagram Engagement Settings:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 2))

        self.engagement_widgets = {} # Store all widgets for each type

        for eng_type in INSTAGRAM_ENGAGEMENT_TYPES:
            widgets = {}
            min_qty_site = MINIMUM_QUANTITIES.get(("Instagram", eng_type), 0) # Min required by site

            row_frame = ctk.CTkFrame(self.main_frame)
            row_frame.pack(fill="x", pady=4)

            # Label (includes site minimum)
            label_text = f"{eng_type} (Min: {min_qty_site})"
            ctk.CTkLabel(row_frame, text=label_text, width=150, anchor="w").pack(side=ctk.LEFT, padx=(5, 0))

            # Fixed Quantity
            widgets['qty_entry'] = ctk.CTkEntry(row_frame, width=60, placeholder_text="Count")
            widgets['qty_entry'].pack(side=ctk.LEFT, padx=5)
            widgets['qty_entry'].insert(0, str(self.existing_data.get(f'{eng_type}_quantity', 0)))

            # Random Checkbox
            widgets['rand_var'] = ctk.BooleanVar(value=self.existing_data.get(f'{eng_type}_use_random', False))
            widgets['rand_cb'] = ctk.CTkCheckBox(row_frame, text="Rand?", variable=widgets['rand_var'], width=20,
                                                 command=lambda et=eng_type: self._toggle_random_qty(et))
            widgets['rand_cb'].pack(side=ctk.LEFT, padx=(0, 5))

            # Min/Max Quantity Entries (initially potentially disabled)
            widgets['min_entry'] = ctk.CTkEntry(row_frame, width=60, placeholder_text="Min Count")
            widgets['min_entry'].pack(side=ctk.LEFT, padx=2)
            widgets['min_entry'].insert(0, str(self.existing_data.get(f'{eng_type}_min_qty', min_qty_site if min_qty_site > 0 else 10))) # Default min if random

            widgets['max_entry'] = ctk.CTkEntry(row_frame, width=60, placeholder_text="Max Count")
            widgets['max_entry'].pack(side=ctk.LEFT, padx=2)
            widgets['max_entry'].insert(0, str(self.existing_data.get(f'{eng_type}_max_qty', 100))) # Default max if random

            # Loop Participation Repeats Entry
            ctk.CTkLabel(row_frame, text="Loop Repeats:", width=90, anchor="e").pack(side=ctk.LEFT, padx=(10, 2))
            widgets['loop_repeats_entry'] = ctk.CTkEntry(row_frame, width=40, placeholder_text="Count")
            widgets['loop_repeats_entry'].pack(side=ctk.LEFT, padx=5)
            widgets['loop_repeats_entry'].insert(0, str(self.existing_data.get(f'{eng_type}_loop_repeats', 0)))

            self.engagement_widgets[eng_type] = widgets
            self._toggle_random_qty(eng_type) # Set initial state for min/max entries

        # --- Loop Settings Section ---
        ctk.CTkLabel(self.main_frame, text="Loop Settings:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
        loop_frame = ctk.CTkFrame(self.main_frame)
        loop_frame.pack(fill="x", pady=5)

        # Loop Count
        ctk.CTkLabel(loop_frame, text="Loops:          ", anchor="w").pack(side=ctk.LEFT, padx=5)
        self.loop_count_entry = ctk.CTkEntry(loop_frame, width=60)
        self.loop_count_entry.pack(side=ctk.LEFT, padx=5)
        self.loop_count_entry.insert(0, str(self.existing_data.get('loop_count', 1)))

        # Fixed Delay
        ctk.CTkLabel(loop_frame, text="Delay (s):", anchor="w").pack(side=ctk.LEFT, padx=(20, 5))
        self.loop_delay_entry = ctk.CTkEntry(loop_frame, width=60, placeholder_text="Seconds")
        self.loop_delay_entry.pack(side=ctk.LEFT, padx=5)
        self.loop_delay_entry.insert(0, str(self.existing_data.get('loop_delay', 0)))

        # Random Delay Checkbox
        self.random_delay_var = ctk.BooleanVar(value=self.existing_data.get('use_random_delay', False))
        self.random_delay_cb = ctk.CTkCheckBox(loop_frame, text="Rand?", variable=self.random_delay_var,
                                               command=self._toggle_random_delay)
        self.random_delay_cb.pack(side=ctk.LEFT, padx=(0, 5))

        # Min/Max Delay Entries
        self.min_delay_entry = ctk.CTkEntry(loop_frame, width=60, placeholder_text="Min (s)")
        self.min_delay_entry.pack(side=ctk.LEFT, padx=2)
        self.min_delay_entry.insert(0, str(self.existing_data.get('min_delay', 60)))

        self.max_delay_entry = ctk.CTkEntry(loop_frame, width=60, placeholder_text="Max (s)")
        self.max_delay_entry.pack(side=ctk.LEFT, padx=2)
        self.max_delay_entry.insert(0, str(self.existing_data.get('max_delay', 300)))

        self._toggle_random_delay() # Set initial state

        # --- Buttons ---
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(pady=20)

        self.save_button = ctk.CTkButton(self.button_frame, text="Save Profile", command=self._save)
        self.save_button.pack(side=ctk.LEFT, padx=10)

        self.cancel_button = ctk.CTkButton(self.button_frame, text="Cancel", command=self._cancel, fg_color="grey")
        self.cancel_button.pack(side=ctk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _show_status(self, message, color="green", duration_ms=3000):
        """Displays a status message in the top-right label."""
        # Cancel any previous hide timer
        if self._clear_status_after_delay_id:
            self.after_cancel(self._clear_status_after_delay_id)
            self._clear_status_after_delay_id = None

        self.status_label.configure(text=message, text_color="white", fg_color=color)
        self.update_idletasks() # Force UI update
        # Schedule to clear the message
        self._clear_status_after_delay_id = self.after(duration_ms, self._clear_status)

    def _clear_status(self):
        """Clears the status message."""
        self.status_label.configure(text="", fg_color="transparent")
        self._clear_status_after_delay_id = None

    def _toggle_random_qty(self, eng_type):
        """Enable/disable min/max qty entries based on checkbox state."""
        widgets = self.engagement_widgets[eng_type]
        if widgets['rand_var'].get():
            widgets['min_entry'].configure(state=ctk.NORMAL)
            widgets['max_entry'].configure(state=ctk.NORMAL)
            widgets['qty_entry'].configure(state=ctk.DISABLED)
            # Optional: Clear fixed quantity entry or set to 0
            # widgets['qty_entry'].delete(0, ctk.END)
            # widgets['qty_entry'].insert(0, "0")
        else:
            widgets['min_entry'].configure(state=ctk.DISABLED)
            widgets['max_entry'].configure(state=ctk.DISABLED)
            widgets['qty_entry'].configure(state=ctk.NORMAL)

    def _toggle_random_delay(self):
        """Enable/disable min/max delay entries based on checkbox state."""
        if self.random_delay_var.get():
            self.min_delay_entry.configure(state=ctk.NORMAL)
            self.max_delay_entry.configure(state=ctk.NORMAL)
            self.loop_delay_entry.configure(state=ctk.DISABLED)
        else:
            self.min_delay_entry.configure(state=ctk.DISABLED)
            self.max_delay_entry.configure(state=ctk.DISABLED)
            self.loop_delay_entry.configure(state=ctk.NORMAL)

    def _validate_and_get_data(self):
        profile_name = self.name_entry.get().strip()
        if not profile_name:
            messagebox.showerror("Validation Error", "Profile Name cannot be empty.", parent=self)
            return None, None
        
        # Check for name conflicts using logical_parent
        if profile_name != self.existing_name and profile_name in self.logical_parent.profiles:
            messagebox.showerror("Validation Error", f"Profile name '{profile_name}' already exists.", parent=self)
            return None, None

        profile_data = {}
        has_positive_qty = False # Track if at least one engagement has quantity > 0

        # Validate Engagement Settings
        for eng_type, widgets in self.engagement_widgets.items():
            min_qty_site = MINIMUM_QUANTITIES.get(("Instagram", eng_type), 0)
            use_random = widgets['rand_var'].get()

            profile_data[f'{eng_type}_use_random'] = use_random

            if use_random:
                min_str = widgets['min_entry'].get().strip()
                max_str = widgets['max_entry'].get().strip()
                profile_data[f'{eng_type}_quantity'] = 0 # Store 0 for fixed quantity when random

                if not min_str.isdigit() or not max_str.isdigit():
                    messagebox.showerror("Validation Error", f"Min/Max quantity for {eng_type} must be numbers.", parent=self)
                    return None, None
                min_val = int(min_str)
                max_val = int(max_str)

                if min_val < 0 or max_val < 0:
                    messagebox.showerror("Validation Error", f"Min/Max quantity for {eng_type} cannot be negative.", parent=self)
                    return None, None
                if min_val > max_val:
                    messagebox.showerror("Validation Error", f"Min quantity cannot be greater than Max for {eng_type}.", parent=self)
                    return None, None
                # Warn if max is below site minimum, but allow saving
                if max_val > 0 and max_val < min_qty_site:
                     print(f"Warning: Max quantity {max_val} for {eng_type} is below site minimum {min_qty_site}. Saving anyway.")
                if max_val == 0: # Can't have random range from 0 to 0 effectively
                     print(f"Warning: Max quantity for {eng_type} is 0, random range is ineffective.")
                     profile_data[f'{eng_type}_use_random'] = False # Turn off random if max is 0
                     min_val = 0

                profile_data[f'{eng_type}_min_qty'] = min_val
                profile_data[f'{eng_type}_max_qty'] = max_val
                if max_val > 0: has_positive_qty = True

            else: # Using fixed quantity
                qty_str = widgets['qty_entry'].get().strip()
                profile_data[f'{eng_type}_min_qty'] = 0 # Store 0 when not random
                profile_data[f'{eng_type}_max_qty'] = 0 # Store 0 when not random

                if not qty_str.isdigit():
                    messagebox.showerror("Validation Error", f"Quantity for {eng_type} must be a number.", parent=self)
                    return None, None
                qty_val = int(qty_str)

                if qty_val < 0:
                    messagebox.showerror("Validation Error", f"Quantity for {eng_type} cannot be negative.", parent=self)
                    return None, None
                # Warn if below site minimum, but allow saving
                if qty_val > 0 and qty_val < min_qty_site:
                     print(f"Warning: Quantity {qty_val} for {eng_type} is below site minimum {min_qty_site}. Saving anyway.")

                profile_data[f'{eng_type}_quantity'] = qty_val
                if qty_val > 0: has_positive_qty = True

            # Validate Loop Repeats for this engagement type
            loop_repeats_str = widgets['loop_repeats_entry'].get().strip()
            if not loop_repeats_str.isdigit():
                messagebox.showerror("Validation Error", f"Loop Repeats for {eng_type} must be a non-negative number.", parent=self)
                return None, None
            loop_repeats = int(loop_repeats_str)
            if loop_repeats < 0:
                 messagebox.showerror("Validation Error", f"Loop Repeats for {eng_type} cannot be negative.", parent=self)
                 return None, None
            profile_data[f'{eng_type}_loop_repeats'] = loop_repeats

        if not has_positive_qty:
            messagebox.showwarning("Validation Warning", "No engagement types have a quantity greater than 0. The profile may not do anything.", parent=self)
            # Allow saving anyway

        # Validate Loop Settings
        loop_count_str = self.loop_count_entry.get().strip()
        if not loop_count_str.isdigit():
            messagebox.showerror("Validation Error", "Number of Loops must be a number.", parent=self)
            return None, None
        loop_count = int(loop_count_str)
        if loop_count < 0:
             messagebox.showerror("Validation Error", "Number of Loops cannot be negative.", parent=self)
             return None, None
        profile_data['loop_count'] = max(1, loop_count) # Treat 0 as 1 (no loop beyond first run)

        use_random_delay = self.random_delay_var.get()
        profile_data['use_random_delay'] = use_random_delay
        profile_data['loop_delay'] = 0
        profile_data['min_delay'] = 0
        profile_data['max_delay'] = 0

        if use_random_delay:
            min_delay_str = self.min_delay_entry.get().strip()
            max_delay_str = self.max_delay_entry.get().strip()

            if not min_delay_str.isdigit() or not max_delay_str.isdigit():
                messagebox.showerror("Validation Error", "Min/Max Delay must be numbers.", parent=self)
                return None, None
            min_delay = int(min_delay_str)
            max_delay = int(max_delay_str)

            if min_delay < 0 or max_delay < 0:
                 messagebox.showerror("Validation Error", "Min/Max Delay cannot be negative.", parent=self)
                 return None, None
            if min_delay > max_delay:
                messagebox.showerror("Validation Error", "Min Delay cannot be greater than Max Delay.", parent=self)
                return None, None

            profile_data['min_delay'] = min_delay
            profile_data['max_delay'] = max_delay
        else: # Fixed delay
            delay_str = self.loop_delay_entry.get().strip()
            if not delay_str.isdigit():
                messagebox.showerror("Validation Error", "Loop Delay must be a number.", parent=self)
                return None, None
            delay = int(delay_str)
            if delay < 0:
                 messagebox.showerror("Validation Error", "Loop Delay cannot be negative.", parent=self)
                 return None, None
            profile_data['loop_delay'] = delay

        # Convert old keys (just quantity) to new format if necessary
        # This part is handled by using .get() with defaults during loading/saving
        # We just need to ensure all NEW keys are present in the output dict.

        print("Validated profile data:", profile_data) # Debug print
        return profile_name, profile_data

    def _save(self):
        # 1. Validate data from UI
        profile_name, profile_data = self._validate_and_get_data()

        # 2. If valid, store the result
        if profile_name is not None:
            self.result = (profile_name, profile_data)
            print(f"ProfileEditorDialog result set to: {self.result}")
            # 3. Notify the parent *before* closing
            if hasattr(self.logical_parent, '_handle_profile_dialog_close'):
                print("[ProfileEditorDialog] Attempting to call _handle_profile_dialog_close on parent...")
                self.logical_parent._handle_profile_dialog_close(self.result, is_edit=(self.existing_name is not None))
                print("[ProfileEditorDialog] Parent notified.")
            else:
                print("[ProfileEditorDialog] *** Error: logical_parent missing _handle_profile_dialog_close method. ***")
            self.destroy() # 4. Close the dialog

    def _cancel(self):
        print("ProfileEditorDialog cancelled.")
        self.result = None
        # Notify parent of cancellation
        if hasattr(self.logical_parent, '_handle_profile_dialog_close'):
            print("[ProfileEditorDialog] Attempting to call _handle_profile_dialog_close on parent (Cancel)...")
            self.logical_parent._handle_profile_dialog_close(None, is_edit=(self.existing_name is not None))
            print("[ProfileEditorDialog] Parent notified (Cancel).")
        else:
             print("[ProfileEditorDialog] *** Error: logical_parent missing _handle_profile_dialog_close method (Cancel). ***")
        self.destroy()

# Example Usage (for testing the dialog standalone)
if __name__ == "__main__":
    # Create a dummy parent window and profiles dict for testing
    root = ctk.CTk()
    root.withdraw() # Hide the dummy root window
    class DummyParent:
        profiles = {"TestProfile": {"Likes_quantity": 50, "Views_quantity": 1000, "loop_count": 2, "use_random_delay": True, "min_delay": 10, "max_delay": 20}}
    dummy_parent = DummyParent()

    # Test adding a new profile
    print("Testing Add New...")
    add_dialog = ProfileEditorDialog(master=root, logical_parent=dummy_parent) # Pass correct args
    result_add = add_dialog.result
    print("Add Result:", result_add)

    # Test editing an existing profile
    print("\nTesting Edit Existing...")
    edit_dialog = ProfileEditorDialog(master=root, # Tkinter parent
                                    logical_parent=dummy_parent, # Logical parent
                                    existing_profile_name="TestProfile",
                                    existing_profile_data=dummy_parent.profiles["TestProfile"])
    result_edit = edit_dialog.result
    print("Edit Result:", result_edit)

    root.destroy() 