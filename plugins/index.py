# plugins/index.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import config
from database import save_file

INDEX_STATES = {}

@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_index(client: Client, message: Message):
    file = message.document or message.video
    await save_file(
        file_name=file.file_name,
        file_size=file.file_size,
        file_id=file.file_id,
        chat_id=message.chat.id,
        message_id=message.id
    )

@Client.on_message(filters.command("index") & filters.user(config.ADMIN_ID) & filters.private)
async def index_start_cmd(client: Client, message: Message):
    INDEX_STATES[message.from_user.id] = True
    instructions = (
        "📥 **চ্যানেল ইনডেক্সিং কন্ট্রোল প্যানেল**\n\n"
        "অন্য যেকোনো চ্যানেল থেকে সব মুভি ইনডেক্স করতে নিচের নিয়ম অনুসরণ করুন:\n\n"
        "১️⃣ প্রথমে নিশ্চিত করুন বটটি ওই চ্যানেলে **অ্যাডমিন (Admin)** হিসেবে যুক্ত আছে।\n"
        "২️⃣ এবার ওই চ্যানেলের **সর্বশেষ (Last) ফাইল বা মেসেজটি** এখানে ফরোয়ার্ড (Forward) করুন।\n\n"
        "👉 *ফাইলটি পাওয়ার পর বট স্বয়ংক্রিয়ভাবে পেছনের সমস্ত ফাইল ডাটাবেজে ইনডেক্স করা শুরু করবে।*"
    )
    await message.reply_text(instructions)

@Client.on_message(filters.forwarded & filters.private & filters.user(config.ADMIN_ID))
async def process_index_forward(client: Client, message: Message):
    user_id = message.from_user.id
    if not INDEX_STATES.get(user_id):
        return

    INDEX_STATES[user_id] = False

    if not message.forward_from_chat:
        await message.reply_text("❌ এটি কোনো চ্যানেল থেকে ফরোয়ার্ড করা হয়নি।")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id
    status_msg = await message.reply_text("⏳ **ইনডেক্সিং কানেকশন তৈরি হচ্ছে...**")
    
    saved_count = 0
    scanned_count = 0
    chunk_size = 100
    current_id = last_msg_id

    try:
        while current_id > 0:
            start_id = max(1, current_id - chunk_size + 1)
            msg_ids = list(range(start_id, current_id + 1))
            messages_batch = await client.get_messages(chat_id, msg_ids)
            
            for msg in reversed(messages_batch):
                scanned_count += 1
                if not msg or msg.empty:
                    continue
                if msg.document or msg.video:
                    file = msg.document or msg.video
                    saved = await save_file(
                        file_name=file.file_name,
                        file_size=file.file_size,
                        file_id=file.file_id,
                        chat_id=chat_id,
                        message_id=msg.id
                    )
                    if saved:
                        saved_count += 1
            
            await status_msg.edit_text(
                f"⏳ **মুভি ইনডেক্সিং চলমান রয়েছে...**\n\n"
                f"🔎 স্ক্যান করা মেসেজ: `{scanned_count}`/`{last_msg_id}` টি\n"
                f"📥 নতুন সংরক্ষিত মুভি: `{saved_count}` টি"
            )
            current_id -= chunk_size
            await asyncio.sleep(1.5)

        await status_msg.edit_text(
            f"🎉 **ইনডেক্সিং সফলভাবে সম্পন্ন হয়েছে!**\n\n"
            f"📊 **চূড়ান্ত রিপোর্ট:**\n"
            f"🔎 মোট স্ক্যানকৃত মেসেজ: `{scanned_count}` টি\n"
            f"📥 মোট ইনডেক্সকৃত মুভি: `{saved_count}` টি"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ ইনডেক্সিংয়ের সময় ত্রুটি ঘটেছে: `{str(e)}`")
