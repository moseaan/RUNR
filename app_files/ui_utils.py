import customtkinter as ctk
import datetime

class ConfirmationDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x180")
        self.transient(parent) # Keep on top of parent
        self.grab_set() # Modal behavior

        self._user_confirmed = False # Store result

        self.message_label = ctk.CTkLabel(self, text=message, wraplength=320)
        self.message_label.pack(pady=20, padx=20)

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=10)

        self.confirm_button = ctk.CTkButton(self.button_frame, text="Yes, Continue", command=self._confirm)
        self.confirm_button.pack(side=ctk.LEFT, padx=10)

        self.cancel_button = ctk.CTkButton(self.button_frame, text="No, Cancel", command=self._cancel, fg_color="grey")
        self.cancel_button.pack(side=ctk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self._cancel) # Handle window close
        self.wait_window(self) # Wait until window is closed

    def _confirm(self):
        self._user_confirmed = True
        self.destroy()

    def _cancel(self):
        self._user_confirmed = False
        self.destroy()

    def get_result(self):
        return self._user_confirmed

def ask_confirmation(parent, title, message):
    dialog = ConfirmationDialog(parent, title, message)
    return dialog.get_result()

def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    """Formats an ISO datetime string into a more readable format."""
    if not value:
        return "N/A"
    try:
        # Handle potential strings or already parsed datetimes
        if isinstance(value, str):
            # Replace 'Z' if present, it signifies UTC
            dt_object = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, datetime.datetime):
            dt_object = value
        else:
            return str(value) # Cannot format, return as string
        
        # Format the datetime object
        return dt_object.strftime(format)
    except (ValueError, TypeError) as e:
        print(f"Error formatting datetime '{value}': {e}")
        # Return original value or placeholder if parsing/formatting fails
        return str(value) 