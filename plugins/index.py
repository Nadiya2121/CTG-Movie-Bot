# plugins/index.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import config
# database থেকে get_active_files_collection ইম্পোর্ট করা হয়েছে (এরর ফিক্স)
from database import save_file, get_active_files_collection

INDEX_STATES = {}

# রিকোয়েস্টকারী ইউজারকে মুভি আপলোড হওয়া মাত্র নোটিফাই করার অটোমেটিক টাস্ক (সেফটি সহ)
async def check_and_notify_requests(client: Client, file_name: str, file_db_id: str):
    if not file_name or not isinstance(file_name, str):
        return
        
    try:
        from database import db1
        requests_col = db1["requests"]
        
        cursor = requests_col.find({"status": "pending"})
        async for req in cursor:
            req_query = req["query"].lower().strip()
            
            if req_query in file_name.lower():
                user_id = req["user_id"]
                
                from plugins.search import clean_movie_title
                cleaned_name = clean_movie_title(file_name)
                
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
                    await client.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
                    await requests_col.update_one({"_id": req["_id"]}, {"$set": {"status": "completed"}})
                except Exception as e:
                    print(f"Failed to notify user {user_id}: {e}")
                    await requests_col.update_one({"_id": req["_id"]}, {"$set": {"status": "completed"}})
    except Exception as e:
        print(f"Request notify error: {e}")


# মেইন চ্যানেলের অটো-ইনডেক্সিং (সেফটি সহ)
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_index(client: Client, message: Message):
    file = message.document or message.video
    
    raw_fname = file.file_name if file.file_name else f"Video_File_{file.file_size}"
    
    saved = await save_file(
        file_name=raw_fname,
        file_size=file.file_size,
        file_id=file.file_id,
        chat_id=message.chat.id,
        message_id=message.id
    )
    if saved:
        from database import files_col1
        doc = await files_col1.find_one({"file_id": file.file_id})
        if doc:
            asyncio.create_task(check_and_notify_requests(client, raw_fname, str(doc["_id"])))


# ম্যানুয়াল ইনডেক্সিং (Turbo Speed Batch Method - সেফটি সহ)
@Client.on_message(filters.command("index") & filters.user(config.ADMIN_ID) & filters.private)
async def index_start_cmd(client: Client, message: Message):
    INDEX_STATES[message.from_user.id] = True
    instructions = (
        "📥 **চ্যানেল ইনডেক্সিং কন্ট্রোল প্যানেল (Turbo Speed)**\n\n"
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
    status_msg = await message.reply_text("⏳ **Turbo Speed ইনডেক্সিং কানেকশন তৈরি হচ্ছে...**")
    
    saved_count = 0
    skipped_count = 0  
    scanned_count = 0
    chunk_size = 200
    current_id = last_msg_id
    last_edit_scanned_count = 0 

    try:
        active_col = await get_active_files_collection()
        
        while current_id > 0:
            start_id = max(1, current_id - chunk_size + 1)
            msg_ids = list(range(start_id, current_id + 1))
            messages_batch = await client.get_messages(chat_id, msg_ids)
            
            batch_files = []
            for msg in reversed(messages_batch):
                scanned_count += 1
                if not msg or msg.empty:
                    continue
                if msg.document or msg.video:
                    file = msg.document or msg.video
                    raw_fname = file.file_name if file.file_name else f"Video_File_{file.file_size}"
                    
                    batch_files.append({
                        "file_name": raw_fname,
                        "file_size": file.file_size,
                        "file_id": file.file_id,
                        "chat_id": chat_id,
                        "message_id": msg.id
                    })

            if batch_files:
                file_ids = [f["file_id"] for f in batch_files]
                file_names = [f["file_name"] for f in batch_files]
                
                existing_docs = await active_col.find({
                    "$or": [
                        {"file_id": {"$in": file_ids}},
                        {"file_name": {"$in": file_names}}
                    ]
                }).to_list(length=len(batch_files))
                
                existing_ids = {d["file_id"] for d in existing_docs}
                existing_name_sizes = {(d["file_name"], d["file_size"]) for d in existing_docs}
                
                to_insert = []
                for f in batch_files:
                    if f["file_id"] not in existing_ids and (f["file_name"], f["file_size"]) not in existing_name_sizes:
                        to_insert.append(f)
                    else:
                        skipped_count += 1
                
                if to_insert:
                    await active_col.insert_many(to_insert)
                    saved_count += len(to_insert)
                    
                    for doc in to_insert:
                        doc_id = str(doc["_id"])
                        asyncio.create_task(check_and_notify_requests(client, doc["file_name"], doc_id))

            if scanned_count - last_edit_scanned_count >= 1000 or current_id <= chunk_size:
                await status_msg.edit_text(
                    f"⏳ **মুভি ইনডেক্সিং চলমান রয়েছে (Turbo Speed ⚡️)...**\n\n"
                    f"🔎 স্ক্যান করা মেসেজ: `{scanned_count}`/`{last_msg_id}` টি\n"
                    f"📥 নতুন সংরক্ষিত মুভি: `{saved_count}` টি\n"
                    f"♻️ ডুপ্লিকেট ফাইল স্কিপড: `{skipped_count}` টি\n\n"
                    f"⚙️ *বট বিরতিহীনভাবে রকেটের গতিতে কাজ করছে।*"
                )
                last_edit_scanned_count = scanned_count
                await asyncio.sleep(1.2)

            current_id -= chunk_size

        await status_msg.edit_text(
            f"🎉 **ইনডেক্সিং সফলভাবে সম্পন্ন হয়েছে (Turbo Finish)!**\n\n"
            f"📊 **চূড়ান্ত রিপোর্ট:**\n"
            f"🔎 মোট স্ক্যানকৃত মেসেজ: `{scanned_count}` টি\n"
            f"📥 মোট ইনডেক্সকৃত মুভি: `{saved_count}` টি\n"
            f"♻️ মোট ডুপ্লিকেট ফাইল স্কিপড: `{skipped_count}` টি"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ ইনডেক্সিংয়ের সময় ত্রুটি ঘটেছে: `{str(e)}`")
