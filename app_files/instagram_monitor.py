"""Instagram target‑monitoring helper
Updated 2025‑05‑04
-----------------------------------
*   Properly decrypts Chrome cookies on Windows (handles DPAPI + AES‑GCM)
*   Falls back to the public "?__a=1&__d=dis" endpoint when authenticated
    API call returns 401 or missing csrftoken
*   Keeps previous config / scheduler helpers untouched
"""
from __future__ import annotations

# --- stdlib -----------------------------------------------------------------
import base64
import datetime as _dt
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
import uuid
from typing import Dict, Tuple, Optional

# --- 3rd‑party --------------------------------------------------------------
import requests
from bs4 import BeautifulSoup

# Attempt windows crypto helpers
try:
    import win32crypt  # type: ignore
except ImportError:  # non‑windows or pywin32 missing
    win32crypt = None  # type: ignore

try:
    from Crypto.Cipher import AES  # pycryptodome
except ImportError:  # pragma: no cover
    AES = None  # type: ignore

# --- local ------------------------------------------------------------------
import config  # noqa: F401  (import side‑effects elsewhere in the project)

# ----------------------------------------------------------------------------
log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

IG_APP_ID = "936619743392459"
DEFAULT_POLLING_INTERVAL = 300  # 5 min

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "monitoring_config.json")

SESSION_PATH = os.path.join(SCRIPT_DIR, "dogehype_session")
COOKIE_DB_PATH = os.path.join(SESSION_PATH, "Network", "Cookies")
TEMP_COOKIE_PATH = os.path.join(SCRIPT_DIR, "temp_cookies.db")

# region ──────────────────────────────────────────────────────────────────────
# Cookie helpers
# ----------------------------------------------------------------------------

def _get_windows_aes_key() -> Optional[bytes]:
    """Decrypt the Chrome AES key stored in *Local State* (Windows only)."""
    if sys.platform != "win32" or win32crypt is None:
        log.debug("AES key retrieval skipped: Not Windows or pywin32 missing.")
        return None

    local_state_path = os.path.join(os.path.dirname(SESSION_PATH), "Local State")
    log.debug(f"Attempting to read Local State from: {local_state_path}")
    if not os.path.exists(local_state_path):
        log.error(f"Local State file not found at: {local_state_path}")
        return None
        
    key = None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        enc_key_b64: str = local_state["os_crypt"]["encrypted_key"]
        enc_key = base64.b64decode(enc_key_b64)[5:]  # strip "DPAPI"
        log.debug("Attempting to decrypt master key using DPAPI...")
        key = win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]
        log.info("Successfully decrypted master key from Local State.")
        return key
    except json.JSONDecodeError as json_err:
        log.error(f"Failed to parse Local State file: {json_err}")
        return None
    except KeyError as key_err:
         log.error(f"Could not find key 'os_crypt' or 'encrypted_key' in Local State: {key_err}")
         return None
    except Exception as e:
        log.error("Could not get Chrome AES key: %s", e)
        if "CryptUnprotectData" in str(e):
             log.exception("DPAPI decryption of master key failed:") 
        return None


def _aes_gcm_decrypt(encrypted_value: bytes, key: bytes) -> Optional[str]:
    """Decrypt AES‑GCM encrypted cookie value (Chrome "v10" / "v11")."""
    if AES is None:
        log.debug("AES module (pycryptodome) not available.")
        return None
    try:
        iv = encrypted_value[3:15]
        payload = encrypted_value[15:-16]
        tag = encrypted_value[-16:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted = cipher.decrypt_and_verify(payload, tag)
        log.debug("AES-GCM decryption successful.")
        return decrypted.decode("utf‑8")
    except Exception as e:  # pragma: no cover
        log.debug("AES-GCM decrypt failed: %s", e)
        return None


def _decrypt_chrome_cookie(value: str, encrypted_value: bytes, aes_key: Optional[bytes]) -> str | None:
    """Return plaintext cookie value, trying cleartext, DPAPI, then AES‑GCM."""
    if value:
        log.debug("Cookie value found in plain text.")
        return value  # already plain

    # Try DPAPI first (for older versions, although likely failing now)
    if sys.platform == "win32" and win32crypt is not None:
        try:
            log.debug("Attempting DPAPI decryption...")
            decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
            if decrypted:
                log.debug("DPAPI decryption successful.")
                return decrypted.decode("utf‑8")
            else:
                log.debug("DPAPI decryption returned empty result.")
        except Exception as dpapi_err:
            log.debug("DPAPI decryption failed: %s", dpapi_err)
            # Pass through to try AES-GCM if DPAPI failed

    # Try AES-GCM decryption if AES key is available
    # Don't strictly require v10/v11 prefix anymore, as it might be absent
    if aes_key:
        log.debug("Attempting AES-GCM decryption (regardless of prefix)...")
        decrypted_aes = _aes_gcm_decrypt(encrypted_value, aes_key)
        if decrypted_aes is not None:
             # Success logged within _aes_gcm_decrypt
             return decrypted_aes
        else:
            log.debug("AES-GCM decryption failed or data was not AES-GCM.")
    else:
        log.debug("AES-GCM decryption skipped: No AES key available.")

    log.warning("Could not decrypt cookie value using any known method.") # Changed to warning
    return None


def load_instagram_cookies(db_path: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Extract `instagram.com` cookies → (cookie‑dict, csrftoken)."""
    if not os.path.exists(db_path):
        log.error("Cookie db not found: %s", db_path)
        return None, None

    shutil.copy2(db_path, TEMP_COOKIE_PATH)
    aes_key = _get_windows_aes_key()

    cookies: Dict[str, str] = {}
    csrf_token: Optional[str] = None
    row_count = 0
    decrypted_count = 0

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(f"file:{TEMP_COOKIE_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, value, encrypted_value FROM cookies
            WHERE host_key LIKE '%instagram.com'
            """
        )
        rows = cur.fetchall()
        row_count = len(rows)
        log.info(f"Found {row_count} potential cookie rows for instagram.com in TEMP copy.")

        for name, value, enc_val in rows:
            plain = _decrypt_chrome_cookie(value, enc_val, aes_key)
            if plain is None:
                log.debug(f"Failed to decrypt cookie: {name}")
                continue  # skip if cannot decrypt
            
            decrypted_count += 1
            cookies[name] = plain
            if name == "csrftoken":
                csrf_token = plain
    except Exception as e:
        log.error("Failed reading cookies: %s", e)
        return None, None
    finally:
        if conn:
            conn.close()
        try:
            os.remove(TEMP_COOKIE_PATH)
        except OSError:
            pass

    log.info("Loaded %d decrypted instagram.com cookies", decrypted_count)
    return cookies or None, csrf_token

# endregion ───────────────────────────────────────────────────────────────────

# region ──────────────────────────────────────────────────────────────────────
# Config helpers (unchanged, but trimmed for brevity) ------------------------
# ----------------------------------------------------------------------------

def _default_config() -> dict:
    return {
        "polling_interval_seconds": DEFAULT_POLLING_INTERVAL,
        "targets": [],
    }


def load_monitoring_config() -> dict:
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf‑8") as f:
                data = json.load(f)
            data.setdefault("polling_interval_seconds", DEFAULT_POLLING_INTERVAL)
            data.setdefault("targets", [])
            return data
    except Exception as e:
        log.warning("Could not load config – using defaults: %s", e)
    # ensure file exists
    save_monitoring_config(_default_config())
    return _default_config()


def save_monitoring_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf‑8") as f:
            json.dump(cfg, f, indent=4)
        log.info(f"Monitoring config saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        log.error("Failed saving config: %s", e)
        return False


def get_monitoring_target(target_id: str) -> Optional[dict]:
    """Retrieves a specific monitoring target by its ID."""
    cfg = load_monitoring_config()
    for target in cfg.get("targets", []):
        if target.get("id") == target_id:
            return target
    return None


def add_monitoring_target(username: str, promo_profile: str) -> Optional[dict]:
    cfg = load_monitoring_config()
    # Check for existing username to prevent duplicates
    for existing_target in cfg.get("targets", []):
        if existing_target.get("target_username") == username:
            log.warning(f"Attempted to add duplicate monitoring target for username: {username}")
            # Depending on desired behavior, could return existing_target or an error indicator
            return None # Or raise an error, or return the existing one
    
    target = {
        "id": str(uuid.uuid4()),
        "target_username": username,
        "promotion_profile_name": promo_profile,
        "last_pushed_post_url": None,
        "is_running": True,
        "last_checked_timestamp": None, # Store as ISO string
    }
    cfg["targets"].append(target)
    log.info(f"Added new monitoring target: {username} (ID: {target['id']})")
    return target if save_monitoring_config(cfg) else None


def update_monitoring_target(target_id: str, updates: Dict[str, any]) -> bool:
    """Updates an existing monitoring target by ID."""
    cfg = load_monitoring_config()
    target_found = False
    for target in cfg.get("targets", []):
        if target.get("id") == target_id:
            # Ensure last_checked_timestamp is handled correctly if present in updates
            if "last_checked_timestamp" in updates and isinstance(updates["last_checked_timestamp"], _dt.datetime):
                updates["last_checked_timestamp"] = updates["last_checked_timestamp"].isoformat()
            
            target.update(updates)
            target_found = True
            log.info(f"Updating target ID {target_id} with: {updates}")
            break
    if target_found:
        return save_monitoring_config(cfg)
    log.warning(f"Attempted to update non-existent target ID: {target_id}")
    return False


def remove_monitoring_target(target_id: str) -> bool:
    """Removes a monitoring target by ID."""
    cfg = load_monitoring_config()
    original_target_count = len(cfg.get("targets", []))
    cfg["targets"] = [t for t in cfg.get("targets", []) if t.get("id") != target_id]
    if len(cfg["targets"]) < original_target_count:
        log.info(f"Removed monitoring target ID: {target_id}")
        return save_monitoring_config(cfg)
    log.warning(f"Attempted to remove non-existent target ID: {target_id}")
    return False

# endregion ───────────────────────────────────────────────────────────────────

# region ──────────────────────────────────────────────────────────────────────
# Scraping logic -------------------------------------------------------------
# ----------------------------------------------------------------------------
HDRS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    ),
    "x-ig-app-id": IG_APP_ID,
}

_DEF_TIMEOUT = 10

def get_latest_post_info(username: str) -> Tuple[Optional[str], Optional[_dt.datetime]]:
    """
    Uses the unauthenticated web_profile_info API endpoint.
    Returns: (latest_post_url, post_datetime_utc) or (None, None) if error/not found.
    Based on: https://scrapfly.io/blog/how-to-scrape-instagram/#scrape-posts-via-profile-endpoint
    """
    username = username.strip().lstrip("@")
    if not username:
        log.error("Username empty in get_latest_post_info")
        return None, None

    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    log.info(f"[Public API] Fetching Instagram data for '{username}' from: {url}")
    post_url: Optional[str] = None
    dt_utc: Optional[_dt.datetime] = None

    try:
        response = requests.get(url, headers=HDRS_BASE, timeout=_DEF_TIMEOUT)
        # Check for common non-success codes that indicate profile doesn't exist or is private
        if response.status_code == 404:
            log.warning(f"[Public API] Profile not found for '{username}' (404 Error).")
            return None, None
        if response.status_code == 401:
             log.warning(f"[Public API] Unauthorized access for '{username}' (401 Error). Profile likely private or requires different method.")
             return None, None
             
        response.raise_for_status()  # Raise for other bad responses (e.g., 429 Rate Limit, 5xx)
        data = response.json()

        # Navigate the expected JSON structure based on snippet
        edges = data["data"]["user"].get("edge_owner_to_timeline_media", {}).get("edges", [])
        if not edges:
            log.info(f"[Public API] No posts ('edges') found for user: '{username}'.")
            return None, None

        # Some profiles use the "pin" feature which can reorder the first N grid posts.
        # To ensure we truly get the most recent upload, pick the edge with the *latest* timestamp.
        latest_node = None
        latest_ts = -1
        for edge in edges:
            try:
                node = edge.get("node", {})
                ts = int(node.get("taken_at_timestamp", 0))
                if ts > latest_ts:
                    latest_ts = ts
                    latest_node = node
            except (ValueError, TypeError):
                continue

        if not latest_node or latest_ts <= 0:
            log.warning(f"[Public API] Could not determine latest post from edges for '{username}'.")
            return None, None

        shortcode = latest_node.get("shortcode")
        if not shortcode:
            log.warning(f"[Public API] Latest node missing shortcode for '{username}'.")
            return None, None

        post_url = f"https://www.instagram.com/p/{shortcode}/"
        dt_utc = _dt.datetime.fromtimestamp(latest_ts, tz=_dt.timezone.utc)
        log.info(f"[Public API] Success! Found most recent post for '{username}': {post_url} at {dt_utc}")
        return post_url, dt_utc

    except requests.exceptions.Timeout:
        log.error(f"[Public API] Timeout while fetching data for '{username}' from {url}")
        return None, None
    except requests.exceptions.HTTPError as http_err:
        log.error(f"[Public API] HTTP error fetching data for '{username}': {http_err.response.status_code} {http_err.response.reason}. URL: {url}")
        return None, None
    except requests.exceptions.RequestException as req_err:
        log.error(f"[Public API] Request error fetching data for '{username}': {req_err}. URL: {url}")
        return None, None
    except (KeyError, IndexError, TypeError) as parse_err:
        log.error(f"[Public API] Error parsing Instagram JSON structure for '{username}': {parse_err}. Check if API structure changed.")
        # Log response snippet for debugging structure changes
        try: 
            log.debug(f"Response snippet: {response.text[:500]}...")
        except NameError: # response might not be defined if request failed earlier
            pass 
        return None, None
    except json.JSONDecodeError:
        log.error(f"[Public API] Error decoding JSON response for '{username}' from {url}. Response text: {response.text[:500]}...")
        return None, None
    except Exception as e:
        log.exception(f"[Public API] An unexpected error occurred for '{username}': {e}")
        return None, None

# endregion ───────────────────────────────────────────────────────────────────

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_user = sys.argv[1] if len(sys.argv) > 1 else "instagram"
    url, dt_utc = get_latest_post_info(test_user)
    if url:
        print(f"Latest post for @{test_user}: {url}")
        if dt_utc:
            print("Posted", (_dt.datetime.now(_dt.timezone.utc) - dt_utc), "ago")
    else:
        print("Could not fetch latest post")
