# plugins/start.py

from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    # এটি Render-এর লাইভ লগে প্রিন্ট হবে, যা দেখে আমরা বুঝতে পারব কমান্ডটি বটের কাছে পৌঁছেছে কিনা
    print(">>> START COMMAND TRIGGERED SUCCESSFULLY <<<") 
    
    try:
        await message.reply_text(
            f"👋 **হ্যালো {message.from_user.first_name or 'ইউজার'}!**\n\n"
            f"🎬 **CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n\n"
            f"বটটি সফলভাবে সচল রয়েছে। যেকোনো মুভির নাম লিখে সার্চ করুন।"
        )
    except Exception as e:
        print(f"Error sending start message: {e}")
