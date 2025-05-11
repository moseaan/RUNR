import json
import os
import datetime

HISTORY_FILE = "history.json"
MAX_HISTORY_ENTRIES = 100 # Limit the number of entries to keep

def load_history(filename=HISTORY_FILE):
    """Loads the automation history from the specified JSON file."""
    history = []
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                history = json.load(f)
                # Ensure it's sorted most recent first (optional, but good practice)
                history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                print(f"Loaded {len(history)} history entries from {filename}")
        else:
            print(f"{filename} not found. Starting with empty history.")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading history from {filename}: {e}. Starting fresh.")
        history = []
    return history

def save_history_entry(entry_data, filename=HISTORY_FILE):
    """Adds a new entry to the history file and saves it, managing file size."""
    history = load_history(filename) # Load existing history
    
    # Add timestamp if not present (should be added by runner)
    if 'timestamp' not in entry_data:
        entry_data['timestamp'] = datetime.datetime.now().isoformat()

    # Add the new entry to the beginning
    history.insert(0, entry_data) 

    # Limit the history size
    history = history[:MAX_HISTORY_ENTRIES]

    try:
        with open(filename, 'w') as f:
            json.dump(history, f, indent=4)
            print(f"Saved new history entry to {filename}")
            return True # Indicate success
    except IOError as e:
        print(f"Error saving history to {filename}: {e}")
        return False # Indicate failure

# Example usage (can be removed later):
# if __name__ == '__main__':
#     test_entry_success = {
#         "job_id": "test_job_123",
#         "timestamp": datetime.datetime.now().isoformat(),
#         "type": "single",
#         "platform": "Instagram",
#         "engagement": "Likes",
#         "link": "http://example.com/post1",
#         "quantity": 50,
#         "status": "success",
#         "message": "Order placed successfully.",
#         "duration": 15.2
#     }
#     test_entry_fail = {
#         "job_id": "test_job_456",
#         "timestamp": datetime.datetime.now().isoformat(),
#         "type": "profile",
#         "profile_name": "MyProfile",
#         "link": "http://example.com/post2",
#         "loop_count": 1,
#         "status": "failed",
#         "message": "Timeout waiting for element.",
#         "duration": 35.8
#     }
#     save_history_entry(test_entry_success)
#     save_history_entry(test_entry_fail)
#     loaded = load_history()
#     print(f"Loaded history: {loaded}") 