# plugins/index.py

import asyncio
import re  # রেগুলার এক্সপ্রেশন ব্যবহারের জন্য যুক্ত করা হলো
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import config
# database থেকে save_file, normalize_text এবং অন্যান্য প্রয়োজনীয় অবজেক্ট ইম্পোর্ট করা হলো
from database import save_file, get_active_files_collection, requests_col, normalize_text
# circular import এড়াতে এবং কোড ক্লিন রাখতে search প্লাগইন থেকে clean_movie_title ইম্পোর্ট করা হলো
from plugins.search import clean_movie_title

# ইনডেক্সিং স্টেট ট্র্যাকিং (স্কিপ কাউন্ট সহ)
INDEX_STATES = {}

# মাল্টিপল এডমিন ফিল্টার (config.ADMINS তালিকা চেক করবে)
is_admin = filters.create(lambda _, __, message: message.from_user and message.from_user.id in config.ADMINS)


# ==========================================
#  সহায়ক ফাংশন: ক্যাপশন থেকে ভাষা সনাক্তকরণ লজিক
# ==========================================
def detect_language_from_caption(caption: str) -> str:
    """
    মেসেজের ক্যাপশন স্ক্রিন করে যেকোনো স্থানে থাকা ভাষা (Language) সনাক্ত করে।
    এটি ক্যাপশনের অনেক গভীরে বা নিচে থাকলেও খুঁজে বের করতে সক্ষম।
    """
    if not caption:
        return ""
        
    caption_lower = caption.lower()
    
    # সনাক্তকরণের জন্য বিভিন্ন ভাষার কি-ওয়ার্ড ও প্যাটার্ন
    lang_patterns = {
        "Bengali": [r"\bbengali\b", r"\bbangla\b", r"বাংলা"],
        "Hindi": [r"\bhindi\b", r"हिन्दी", r"हिंदी"],
        "Tamil": [r"\btamil\b", r"தமிழ்"],
        "Telugu": [r"\btelugu\b", r"తెలుగు"],
        "English": [r"\benglish\b", r"\beng\b"],
        "Dual Audio": [r"\bdual\b", r"দ্বৈত অডিও", r"dual audio", r"dual-audio"],
        "Multi Audio": [r"\bmulti\b", r"multi audio", r"multi-audio"]
    }
    
    detected = []
    for lang, patterns in lang_patterns.items():
        for pattern in patterns:
            if re.search(pattern, caption_lower):
                detected.append(lang)
                break  # এই ভাষার একটি প্যাটার্ন মিললে পরবর্তী ভাষায় চলে যাবে
                
    if detected:
        # যদি "Dual Audio" বা একাধিক ভাষা পাওয়া যায়
        if "Dual Audio" in detected or len(detected) > 1:
            if "Dual Audio" in detected:
                return "Dual Audio"
            return " + ".join(detected)
        return detected[0]
        
    return ""


# রিকোয়েস্টকারী ইউজারকে মুভি আপলোড হওয়া মাত্র নোটিফাই করার অটোমেটিক টাস্ক (সেফটি সহ)
async def check_and_notify_requests(client: Client, file_name: str, file_db_id: str):
    if not file_name or not isinstance(file_name, str):
        return
        
    try:
        cursor = requests_col.find({"status": "pending"})
        async for req in cursor:
            req_query = req["query"].lower().strip()
            
            if req_query in file_name.lower():
                user_id = req["user_id"]
                
                # নোটিফিকেশনে সুন্দর দেখানোর জন্য নাম ক্লিন করা হচ্ছে
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


# মেইন চ্যানেলের অটো-ইনডেক্সিং (কোয়ালিটি ট্যাগ ও অটো-ল্যাঙ্গুয়েজ ডিটেক্ট সহ)
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_index(client: Client, message: Message):
    file = message.document or message.video
    raw_fname = file.file_name if file.file_name else f"Video_File_{file.file_size}"
    
    # [নরমালাইজেশন]: ফ্যান্সি ফন্ট সাধারণ ফন্টে রূপান্তর করা হচ্ছে (কোয়ালিটি বা ভাষা অক্ষুণ্ন থাকবে)
    normalized_fname = normalize_text(raw_fname)
    
    # [ক্যাপশন থেকে ভাষা সনাক্তকরণ]
    caption_text = message.caption if message.caption else ""
    detected_lang = detect_language_from_caption(caption_text)
    
    # যদি ভাষা সনাক্ত হয় এবং তা ফাইলের নামে আগে থেকে না থাকে, তবে যুক্ত করা হবে
    if detected_lang and detected_lang.lower() not in normalized_fname.lower():
        name_parts = normalized_fname.rsplit(".", 1)
        if len(name_parts) == 2:
            normalized_fname = f"{name_parts[0]} [{detected_lang}].{name_parts[1]}"
        else:
            normalized_fname = f"{normalized_fname} [{detected_lang}]"
    
    saved_id = await save_file(
        file_name=normalized_fname, # কোয়ালিটি ও ক্যাপশন ল্যাঙ্গুয়েজসহ সম্পূর্ণ নামটি ডাটাবেজে সেভ হচ্ছে
        file_size=file.file_size,
        file_id=file.file_id,
        chat_id=message.chat.id,
        message_id=message.id
    )
    if saved_id and isinstance(saved_id, str):
        asyncio.create_task(check_and_notify_requests(client, normalized_fname, saved_id))


# ম্যানুয়াল ইনডেক্সিং (Turbo Speed Batch with Dynamic Skip, Font Normalization, Quality Preservation & Auto-Language)
@Client.on_message(filters.command("index") & is_admin & filters.private)
async def index_start_cmd(client: Client, message: Message):
    skip_count = 0
    if len(message.command) > 1:
        try:
            skip_count = int(message.command[1])
        except ValueError:
            await message.reply_text("⚠️ **ভুল সংখ্যা!** দয়া করে সঠিক সংখ্যা লিখুন। যেমন: `/index 200000`")
            return
            
    INDEX_STATES[message.from_user.id] = {
        "active": True,
        "skip": skip_count
    }
    
    skip_text = f" (প্রথম `{skip_count}` টি মেসেজ স্কিপ করা হবে)" if skip_count > 0 else ""
    instructions = (
        f"📥 **চ্যানেল ইনডেক্সিং কন্ট্রোল প্যানেল (Turbo Speed)**\n"
        f"⚙️ স্ট্যাটাস: **সচল**{skip_text}\n\n"
        f"অন্য যেকোনো চ্যানেল থেকে সব মুভি ইনডেক্স করতে নিচের নিয়ম অনুসরণ করুন:\n\n"
        f"১️⃣ প্রথমে নিশ্চিত করুন বটটি ওই চ্যানেলে **অ্যাডমিন (Admin)** হিসেবে যুক্ত আছে।\n"
        f"২️⃣ এবার ওই চ্যানেলের **সর্বশেষ (Last) ফাইল বা মেসেজটি** এখানে ফরোয়ার্ড (Forward) করুন।\n\n"
        f"👉 *ফাইলটি পাওয়ার পর বট স্বয়ংক্রিয়ভাবে পেছনের সমস্ত ফাইল ডাটাবেজে ইনডেক্স করা শুরু করবে।*"
    )
    await message.reply_text(instructions)

@Client.on_message(filters.forwarded & filters.private & is_admin)
async def process_index_forward(client: Client, message: Message):
    user_id = message.from_user.id
    state = INDEX_STATES.get(user_id)
    
    if not state or not state.get("active"):
        return

    INDEX_STATES[user_id] = {"active": False, "skip": 0}

    if not message.forward_from_chat:
        await message.reply_text("❌ এটি কোনো চ্যানেল থেকে ফরোয়ার্ড করা হয়নি।")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id
    
    skip_count = state.get("skip", 0)
    current_id = last_msg_id - skip_count
    
    if current_id <= 0:
        await message.reply_text(f"⚠️ **ভুল সংখ্যা!** আপনার স্কিপ করার সংখ্যা `{skip_count}` মূল মেসেজ আইডি `{last_msg_id}` থেকে বড় বা সমান।")
        return

    status_msg = await message.reply_text(
        f"⏳ **Turbo Speed ইনডেক্সিং কানেকশন তৈরি হচ্ছে...**\n"
        f"ℹ️ শুরু হচ্ছে মেসেজ আইডি: `{current_id}` থেকে (স্কিপ করা হয়েছে: `{skip_count}` টি মেসেজ)"
    )
    
    saved_count = 0
    skipped_count = 0  
    scanned_count = skip_count
    chunk_size = 200
    last_edit_scanned_count = skip_count 

    try:
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
                    
                    # [নরমালাইজেশন]: ফ্যান্সি ফন্ট পরিবর্তন কিন্তু আসল কোয়ালিটি/ট্যাগ সংরক্ষণ
                    normalized_fname = normalize_text(raw_fname)
                    
                    # [ক্যাপশন থেকে ভাষা সনাক্তকরণ]
                    caption_text = msg.caption if msg.caption else ""
                    detected_lang = detect_language_from_caption(caption_text)
                    
                    # যদি ভাষা সনাক্ত হয় এবং তা ফাইলের নামে আগে থেকে না থাকে, তবে যুক্ত করা হবে
                    if detected_lang and detected_lang.lower() not in normalized_fname.lower():
                        name_parts = normalized_fname.rsplit(".", 1)
                        if len(name_parts) == 2:
                            normalized_fname = f"{name_parts[0]} [{detected_lang}].{name_parts[1]}"
                        else:
                            normalized_fname = f"{normalized_fname} [{detected_lang}]"
                    
                    batch_files.append({
                        "file_name": normalized_fname, # কোয়ালিটি ও ভাষা সহ আসল নামটি ডাটাবেজে স্টোর হবে
                        "file_size": file.file_size,
                        "file_id": file.file_id,
                        "chat_id": chat_id,
                        "message_id": msg.id
                    })

            if batch_files:
                active_col = await get_active_files_collection()
                if active_col is None:
                    raise Exception("কোনো সচল ফাইল ডাটাবেজ কালেকশন খুঁজে পাওয়া যায়নি!")

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
                    f"⚙️ *বট বিরতিহীনভাবে কাজ করছে।*"
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
