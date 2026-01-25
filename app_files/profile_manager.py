# profile_manager.py
import json
import os

try:
    from mongo_state import (
        load_profiles_from_mongo,
        save_profiles_to_mongo,
        save_single_profile_to_mongo,
        delete_profile_from_mongo,
        clear_profiles_cache,
        is_mongo_available
    )
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

# Get the directory where this script resides
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PROFILE_FILE = os.path.join(SCRIPT_DIR, "profiles.json")
USER_SETTINGS_FILE = os.path.join(SCRIPT_DIR, "user_settings.json")

def load_profiles(filename=DEFAULT_PROFILE_FILE):
    """Loads profiles from MongoDB (primary) or JSON file (fallback)."""
    # Try MongoDB first
    if MONGO_AVAILABLE and is_mongo_available():
        mongo_profiles = load_profiles_from_mongo()
        if mongo_profiles is not None and len(mongo_profiles) > 0:
            print(f"Loaded {len(mongo_profiles)} profiles from MongoDB")
            return mongo_profiles
        # MongoDB available but empty - try to migrate from JSON
        json_profiles = _load_profiles_from_json(filename)
        if json_profiles:
            save_profiles_to_mongo(json_profiles)
            print(f"✅ Migrated {len(json_profiles)} profiles from JSON to MongoDB")
            return json_profiles
    
    # Fallback to JSON file
    return _load_profiles_from_json(filename)


def _load_profiles_from_json(filename=DEFAULT_PROFILE_FILE):
    """Loads profiles directly from JSON file."""
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
        profiles = {}
    return profiles


def save_profiles(profiles, filename=DEFAULT_PROFILE_FILE):
    """Saves profiles to MongoDB (primary) and JSON file (backup)."""
    success = True
    
    # Save to MongoDB first (primary storage)
    if MONGO_AVAILABLE and is_mongo_available():
        if not save_profiles_to_mongo(profiles):
            success = False
    
    # Also save to JSON file as backup
    try:
        with open(filename, 'w') as f:
            json.dump(profiles, f, indent=4)
            print(f"Saved profiles to {filename}")
    except IOError as e:
        print(f"Error saving profiles to {filename}: {e}")
        success = False
    
    return success

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