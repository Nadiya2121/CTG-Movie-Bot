# plugins/index.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import config
from database import save_file

INDEX_STATES = {}

# --- রিকোয়েস্টকারী ইউজারকে মুভি আপলোড হওয়া মাত্র নোটিফাই করার অটোমেটিক টাস্ক (নতুন) ---
async def check_and_notify_requests(client: Client, file_name: str, file_db_id: str):
    try:
        from database import db1
        requests_col = db1["requests"]
        
        # পেন্ডিং রিকোয়েস্টের তালিকা আনা
        cursor = requests_col.find({"status": "pending"})
        async for req in cursor:
            req_query = req["query"].lower().strip()
            
            # যদি রিকোয়েস্ট করা নামটি সদ্য সেভ হওয়া ফাইলের নামের সাথে মিলে যায়
            if req_query in file_name.lower():
                user_id = req["user_id"]
                
                from plugins.search import clean_movie_title
                cleaned_name = clean_movie_title(file_name)
                
                # মিনি অ্যাপ লিংক তৈরি
                raw_url = config.WEB_URL.strip().replace("https://", "").replace("http://", "").rstrip("/")
                web_app_url = f"https://{raw_url}/download?id={file_db_id}"
                
                buttons = [
                    [InlineKeyboardButton(
                        text="🍿 Open Web App to Download",
                        web_app=WebAppInfo(url=web_app_url)
                    )]
                ]
                
                text = (
                    f"🎉 **সুসংবাদ! আপনার রিকোয়েস্ট করা মুভিটি আপলোড করা হয়েছে!**\n\n"
                    f"🎬 **মুভির নাম:** `{cleaned_name}`\n\n"
                    f"👉 মুভিটি ডাউনলোড করতে নিচের বাটনে ক্লিক করে বিজ্ঞাপনটি আনলক করুন।"
                )
                try:
                    # ইউজারকে ইনবক্সে পার্সোনাল মেসেজ পাঠানো
                    await client.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
                    # স্ট্যাটাস পরিবর্তন করা
                    await requests_col.update_one({"_id": req["_id"]}, {"$set": {"status": "completed"}})
                except Exception as e:
                    print(f"Failed to notify user {user_id}: {e}")
                    # ইউজার বট ব্লক করে রাখলেও ডাটাবেজ ক্লিয়ার রাখতে কমপ্লিট করা হবে
                    await requests_col.update_one({"_id": req["_id"]}, {"$set": {"status": "completed"}})
    except Exception as e:
        print(f"Request notify error: {e}")


# মেইন চ্যানেলের অটো-ইনডেক্সিং (আপলোড হওয়া মাত্র রিকোয়েস্ট চেক করবে)
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_index(client: Client, message: Message):
    file = message.document or message.video
    saved = await save_file(
        file_name=file.file_name,
        file_size=file.file_size,
        file_id=file.file_id,
        chat_id=message.chat.id,
        message_id=message.id
    )
    if saved:
        # মঙ্গোডিবি থেকে ফাইলটির আইডি তুলে এনে নোটিফিকেশন পাঠানো হচ্ছে
        from database import files_col1
        doc = await files_col1.find_one({"file_id": file.file_id})
        if doc:
            asyncio.create_task(check_and_notify_requests(client, file.file_name, str(doc["_id"])))


# ম্যানুয়াল ইনডেক্সিং (আইডি ব্যাচিং)
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
                        # ম্যানুয়ালি ইনডেক্স করলেও স্বয়ংক্রিয়ভাবে রিকোয়েস্টকারী ইউজারকে ফাইলসহ মেসেজ পাঠাবে
                        from database import files_col1
                        doc = await files_col1.find_one({"file_id": file.file_id})
                        if doc:
                            asyncio.create_task(check_and_notify_requests(client, file.file_name, str(doc["_id"])))
            
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
