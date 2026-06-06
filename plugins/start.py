# plugins/start.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import logging

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    # ১. প্রথমে ইউজারকে স্বাগত বার্তা পাঠানো (যাতে ডাটাবেজ স্লো হলেও রেসপন্স মিস না হয়)
    welcome_text = (
        f"👋 **হ্যালো {message.from_user.first_name or 'ইউজার'}!**\n\n"
        f"🎬 **CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n"
        f"এখানে আপনি আপনার পছন্দের যেকোনো মুভি ও ওয়েব সিরিজ পেয়ে যাবেন খুবই দ্রুত।\n\n"
        f"📢 **কিভাবে মুভি খুঁজবেন?**\n"
        f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম লিখে মেসেজ পাঠান।\n"
        f"💡 *যেমন:* `RRR` অথবা `KGF` লিখে পাঠান।\n\n"
        f"⚠️ *সহজ অনুসন্ধানের জন্য মুভির সঠিক বানানটি লেখার অনুরোধ রইল।*"
    )
    
    try:
        await message.reply_text(welcome_text)
    except Exception as e:
        logging.error(f"Error sending start message: {e}")
        return

    # ২. ব্যাকগ্রাউন্ডে ইউজার সেভ করা (এটি বটের মেসেজ পাঠানোকে আটকে রাখবে না)
    try:
        from database import add_user
        user_id = message.from_user.id
        username = message.from_user.username or "No Username"
        first_name = message.from_user.first_name or "User"
        
        # create_task ব্যবহারের ফলে এটি ব্যাকগ্রাউন্ডে রান হবে, বট আটকে থাকবে না
        asyncio.create_task(add_user(user_id, username, first_name))
    except Exception as e:
        logging.error(f"Background user save failed: {e}")
