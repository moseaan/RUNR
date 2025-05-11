# profile_manager.py
import json
import os

# Get the directory where this script resides
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PROFILE_FILE = os.path.join(SCRIPT_DIR, "profiles.json")
USER_SETTINGS_FILE = os.path.join(SCRIPT_DIR, "user_settings.json")

def load_profiles(filename=DEFAULT_PROFILE_FILE):
    """Loads profiles from the specified JSON file."""
    profiles = {}
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                profiles = json.load(f)
                print(f"Loaded profiles from {filename}")
        else:
            print(f"{filename} not found. Starting with empty profiles.")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading profiles from {filename}: {e}. Starting fresh.")
        profiles = {} # Return empty dict on error
    return profiles

def save_profiles(profiles, filename=DEFAULT_PROFILE_FILE):
    """Saves the profiles dictionary to the specified JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(profiles, f, indent=4)
            print(f"Saved profiles to {filename}")
            return True # Indicate success
    except IOError as e:
        print(f"Error saving profiles to {filename}: {e}")
        return False # Indicate failure

def load_username(filename=USER_SETTINGS_FILE):
    """Loads the username from the settings file."""
    default_username = "DefaultUser"
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                settings = json.load(f)
                return settings.get("username", default_username)
        else:
            return default_username
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading username from {filename}: {e}")
        return default_username

def save_username(username, filename=USER_SETTINGS_FILE):
    """Saves the username to the settings file."""
    try:
        with open(filename, 'w') as f:
            json.dump({"username": username}, f, indent=4)
            print(f"Saved username to {filename}")
            return True
    except IOError as e:
        print(f"Error saving username to {filename}: {e}")
        return False 