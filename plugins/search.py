# plugins/search.py

import asyncio
import re
import urllib.parse  # শেয়ার লিংকের টেক্সট এনকোড করার জন্য
from fuzzywuzzy import process, fuzz  # fuzz ইম্পোর্ট করা হয়েছে স্ট্রিক্ট সর্টিংয়ের জন্য
from pyrogram import Client, filters, ContinuePropagation
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from pyrogram.enums import ChatType
from pyrogram.errors import UserNotParticipant, MessageNotModified
# database থেকে প্রয়োজনীয় ফাংশন ইম্পোর্ট করা হয়েছে
from database import search_db, get_file_by_db_id, add_user, save_movie_request, is_premium_user, add_group
import config

FILES_PER_PAGE = 5

# গ্রুপ ল্যাঙ্গুয়েজের সংক্ষিপ্ত ম্যাপ (৬৪-বাইট কলব্যাক লিমিট সুরক্ষার জন্য)
GLANG_MAP = {
    "all": "all",
    "bn": "bangla",
    "hi": "hindi",
    "en": "english",
    "ta": "tamil",
    "te": "telugu"
}

# --- ৬৪-বাইট কলব্যাক লিমিট সুরক্ষার জন্য বাইট-ভিত্তিক ট্রাঙ্কেট ফাংশন ---
def safe_bytes_truncate(text: str, max_bytes: int) -> str:
    encoded = text.encode('utf-8')
    sliced = encoded[:max_bytes]
    return sliced.decode('utf-8', errors='ignore').strip()

# --- সুনির্দিষ্ট ক্লিন-আপ ফাংশন ---
def clean_movie_title(name: str) -> str:
    if not name or not isinstance(name, str):
        return "Movie File"
        
    # ১. টেলিগ্রাম ইউজারনেম ও লিংক ডিলিট
    name = re.sub(r'@[a-zA-Z0-9_]+', '', name)
    name = re.sub(r'(https?://)?(t\.me|telegram\.me|telegram\.dog)/[a-zA-Z0-9_\+]+', '', name)
    
    # ২. ডেমেইন লিংক ডিলিট
    domain_extensions = "com|org|net|xyz|club|co|tv|link|info|me|cc|site|space|click|in|online|icu"
    name = re.sub(r'\b[a-zA-Z0-9-]+\.(' + domain_extensions + r')\b', '', name, flags=re.IGNORECASE)
    
    # ৩. মুভি ফাইল এক্সটেনশন ডিলিট
    name = re.sub(r'\.(mkv|mp4|avi|webm|ts|m4v|3gp)$', '', name, flags=re.IGNORECASE)
    
    # ৪. নামের মাঝের সমস্ত ডট, আন্ডারস্কোর ও হাইফেন স্পেস দিয়ে প্রতিস্থাপন
    name = name.replace(".", " ").replace("_", " ").replace("-", " ")
    
    # অতিরিক্ত ডাবল স্পেস ক্লিন করা
    name = re.sub(r'\s+', ' ', name).strip()
    
    if not name:
         name = "Movie File"
    return name

# --- ৫ মিনিট পর ফাইল স্বয়ংক্রিয়ভাবে মুছে দেওয়ার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_file(message: Message):
    await asyncio.sleep(300) # ৩০০ সেকেন্ড = ৫ মিনিট
    try:
        await message.delete()
    except:
        pass

# --- ৫ মিনিট পর ইউজারের সার্চ এবং বটের বাটন মেসেজ ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_search_messages(user_msg: Message, bot_msg: Message):
    await asyncio.sleep(300) # ৩০০ সেকেন্ড = ৫ মিনিট
    try:
        await user_msg.delete()
    except:
        pass
    try:
        await bot_msg.delete()
    except:
        pass

# --- গ্রুপে বটের রিপ্লাই ৫ মিনিট পর ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_group_reply(message: Message):
    await asyncio.sleep(300) # ৩০০ সেকেন্ড = ৫ মিনিট
    try:
        await message.delete()
    except:
        pass

# --- 🍿 মাল্টি-ওয়ার্ড ক্যান্ডিডেট ম্যাচিং এআই স্পেলিং চেকার 🍿 ---
async def get_close_match_from_db(query: str):
    try:
        from database import file_cols
        
        # ৩ অক্ষরের চেয়ে বড় শব্দগুলো আলাদা করা
        clean_q = query.lower().replace(".", " ").replace("-", " ").replace("_", " ").strip()
        words = [w for w in clean_q.split() if len(w) >= 3]
        if not words:
            return None
            
        name_map = {}
        
        # ডাইনামিক $or ফিল্টার
        query_filter = {"$or": [{"file_name": {"$regex": re.escape(w), "$options": "i"}} for w in words]}
        
        # আপনার যুক্ত করা প্রতিটি ফাইল ডাটাবেজ থেকে ডায়নামিকভাবে ক্যান্ডিডেট মুভি স্ক্যান করা হবে
        for col in file_cols:
            try:
                cursor = col.find(query_filter, {"file_name": 1}).limit(500)
                async for doc in cursor:
                    fname = doc.get("file_name")
                    if fname:
                        cleaned = clean_movie_title(fname)
                        normalized = cleaned.lower().replace(".", " ").replace("-", " ").replace("_", " ").strip()
                        name_map[normalized] = cleaned
            except Exception as e:
                print(f"Error scanning close match in collection: {e}")
        
        if not name_map:
            return None
            
        # ইউজারের সার্চ কোয়েরি নরমাল করা হচ্ছে
        query_norm = query.lower().replace(".", " ").replace("-", " ").replace("_", " ").strip()
        
        # fuzz.ratio ব্যবহার করে স্ট্রিক্ট ম্যাচ
        best_match_tuple = process.extractOne(query_norm, list(name_map.keys()), scorer=fuzz.ratio)
        
        if best_match_tuple:
            best_match, score = best_match_tuple
            if score >= 40:
                return name_map[best_match]
                
        return None
    except Exception as e:
        print(f"Fuzzy match error: {e}")
        return None

# --- নয়েজ ওয়ার্ড রিমুভার ---
def clean_search_query(query: str) -> str:
    cleaned = query.lower().replace(".", " ").replace("-", " ").replace("_", " ")
    noise_words = ["movie", "movies", "full", "hd", "bluray", "web-dl", "mkv", "mp4", "mubi", "bin", "muby", "mube"]
    words = cleaned.split()
    if len(words) > 1:
        cleaned_words = [w for w in words if w not in noise_words]
        if cleaned_words:
            return " ".join(cleaned_words)
    return query

# --- প্রফেশনাল এআই প্রগ্রেসিভ সার্চ ইঞ্জিন ---
async def advanced_search_db(query: str):
    results = await search_db(query)
    if results:
        return results, query
        
    words = query.strip().split()
    if len(words) > 1:
        no_years = [w for w in words if not (w.isdigit() and len(w) == 4)]
        if len(no_years) < len(words) and no_years:
            new_query = " ".join(no_years)
            results = await search_db(new_query)
            if results:
                return results, new_query
                
    temp_words = list(words)
    while len(temp_words) > 1:
        temp_words.pop()
        new_query = " ".join(temp_words)
        results = await search_db(new_query)
        if results:
            return results, new_query
            
    return [], query


@Client.on_message(filters.text)
async def main_handler(client: Client, message: Message):
    text = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0

    # ==========================================
    # --- এডমিন চ্যাট/চ্যানেল থেকে আসা কাস্টম রিপ্লাই হ্যান্ডলার ---
    # ==========================================
    if message.reply_to_message:
        parent_msg = message.reply_to_message
        if parent_msg.text and "রিকোয়েস্ট আইডি" in parent_msg.text:
            match_id = re.search(r"রিকোয়েস্ট আইডি:\s*(\d+)", parent_msg.text)
            if match_id:
                target_user_id = int(match_id.group(1))
                custom_text = text
                
                movie_name = "Requested Movie"
                match_movie = re.search(r"🎬\s*মুভি:\s*(.+)", parent_msg.text)
                if match_movie:
                    movie_name = match_movie.group(1).strip()
                
                user_msg = (
                    f"💬 **এডমিন আপনার রিকোয়েস্টের উত্তর দিয়েছেন!**\n\n"
                    f"🎬 মুভি: `{movie_name}`\n"
                    f"📢 উত্তর: **{custom_text}**"
                )
                
                try:
                    await client.send_message(chat_id=target_user_id, text=user_msg)
                    await message.reply_text("✅ আপনার কাস্টম উত্তরটি ইউজারের কাছে পাঠানো হয়েছে।")
                    
                    # এডমিন চ্যানেলের মূল মেসেজের টেক্সট আপডেট
                    base_text = parent_msg.text.split("✍️ **কাস্টম উত্তর:**")[0].strip()
                    await parent_msg.edit_text(
                        f"{base_text}\n\n"
                        f"🔵 **স্ট্যাটাস:** কাস্টম উত্তর পাঠানো হয়েছে (উত্তরদাতা: {message.from_user.mention if message.from_user else 'Admin'})\n"
                        f"💬 **উত্তর:** `{custom_text}`"
                    )
                except Exception as e:
                    await message.reply_text(f"❌ ইউজারের কাছে মেসেজ পাঠানো যায়নি: {str(e)}")
                return

    if text.startswith("/") and not text.startswith("/start"):
        raise ContinuePropagation

    # ==========================================
    # --- ক. পার্সোনাল চ্যাট হ্যান্ডলার (Private PM) ---
    # ==========================================
    if message.chat.type == ChatType.PRIVATE:
        if message.from_user:
            try:
                await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            except Exception as e:
                print(f"Error registering user at start: {e}")

        if text.startswith("/start"):
            
            # --- সিকিউরিটি চেক এবং ফাইল ডেলিভারি ---
            if len(text.split()) > 1:
                start_param = text.split()[1]
                
                # ক. ইউজার যদি বিজ্ঞাপন দেখে বা প্রিমিয়াম প্যানেল থেকে ওয়ান-ক্লিক ফাইলের জন্য ফিরে আসে
                if start_param.startswith("get_"):
                    file_db_id = start_param.replace("get_", "")
                    file_data = await get_file_by_db_id(file_db_id)
                    
                    if file_data:
                        try:
                            raw_name = file_data["file_name"]
                            cleaned_name = clean_movie_title(raw_name)
                            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
                            
                            # [প্রিমিয়াম ব্র্যান্ডেড ওয়াটারমার্ক ক্যাপশন]
                            caption_text = (
                                f"🎬 **👑 ꜰɪʟᴇ ɴᴀᴍᴇ:** `{cleaned_name}`\n"
                                f"💾 ** provide 👑 ꜱɪᴢᴇ:** `{file_size} MB`\n"
                                f"⚡️ ** do ꜱᴘᴇᴇᴅ:** `Unlimited (Ultra Fast CDN)`\n\n"
                                f"🍿 **ᴊᴏɪɴ ᴏᴜʀ ᴍᴏᴠɪᴇ ɴᴇᴛᴡᴏʀᴋ:**\n"
                                f"├─ 🍿 [All Movies Channel]({config.CHANNEL_LINK_1})\n"
                                f"├─ 📢 [Backup Channel]({config.CHANNEL_LINK_2})\n"
                                f"└─ 💬 [Movie Request Group]({config.GROUP_LINK})\n\n"
                                f"👨‍💻 *Power and Branded by CTG Network Team*\n\n"
                                f"⚠️ **⚠️ ꜱᴇᴄᴜʀɪᴛʏ ᴀʟᴇʀᴛ:**\n"
                                f"কপিরাইট এড়াতে এই ফাইলটি আগামী **৫ মিনিট** পর চ্যাট থেকে স্বয়ংক্রিয়ভাবে মুছে যাবে। তাই দ্রুত ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                            )
                            
                            bot_username = getattr(config, "BOT_USERNAME", "CTGMovieBot")
                            share_text = f"🍿 Get '{cleaned_name}' movie instantly from this bot!"
                            encoded_share_text = urllib.parse.quote(share_text)
                            share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=get_{file_db_id}&text={encoded_share_text}"
                            
                            promo_buttons = [
                                [
                                    InlineKeyboardButton("📢 Channel ↗️", url=config.CHANNEL_LINK_2),
                                    InlineKeyboardButton("💬 Groups ↗️", url=config.GROUP_LINK)
                                ],
                                [
                                    InlineKeyboardButton("📲 Share With Friends ➡️", url=share_url)
                                ]
                            ]
                            
                            sent_file = await client.send_cached_media(
                                chat_id=message.chat.id,
                                file_id=file_data["file_id"],
                                caption=caption_text,
                                reply_markup=InlineKeyboardMarkup(promo_buttons)
                            )
                            asyncio.create_task(auto_delete_file(sent_file))
                            asyncio.create_task(auto_delete_search_messages(message, sent_file))
                        except Exception as e:
                            await message.reply_text(f"❌ দুঃখিত, ফাইলটি পাঠানো যাচ্ছে না: {str(e)}")
                    else:
                        await message.reply_text("❌ দুঃখিত, ফাইলটি ডাটাবেজে খুঁজে পাওয়া যায়নি!")
                    return
                
                # খ. ইউজার যদি গ্রুপ থেকে সরাসরি বটের চ্যাটে আসে (এখনো বিজ্ঞাপন দেখেনি)
                else:
                    file_db_id = start_param.replace("app_", "")
                    file_data = await get_file_by_db_id(file_db_id)
                    
                    if file_data:
                        file_name = clean_movie_title(file_data["file_name"])
                        raw_url = config.WEB_URL.strip().replace("https://", "").replace("http://", "").rstrip("/")
                        
                        web_app_url = f"https://{raw_url}/download?id={file_db_id}&user_id={user_id}"
                        
                        buttons = [
                            [InlineKeyboardButton(
                                text="🍿 Open Web App to Download",
                                web_app=WebAppInfo(url=web_app_url)
                            )]
                        ]
                        app_msg = await message.reply_text(
                            f"🎬 **ফাইলের নাম:** `{file_name}`\n\n"
                            f"👉 ফাইলটি ডাউনলোড করার জন্য নিচের বাটনে ক্লিক করে বিজ্ঞাপনটি আনলক করুন।",
                            reply_markup=InlineKeyboardMarkup(buttons)
                        )
                        asyncio.create_task(auto_delete_search_messages(message, app_msg))
                    else:
                        await message.reply_text("❌ দুঃখিত, ফাইলটি ডাটাবেজে খুঁজে পাওয়া যায়নি!")
                    return

            welcome_text = (
                f"👋 **Hey {message.from_user.mention}** 🍿\n\n"
                f"I Am **CTG Movie Search Bot (Tier-1 Premium Edition)**\n"
                f"I can find your favorite Movies, Series, Animes, and other files instantly!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 **মুভি খোঁজার নিয়ম:**\n"
                f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম (বানান সঠিক রেখে) লিখে মেসেজ পাঠান। যেমন: `KGF Chapter 2`\n\n"
                f"⚡️ **বটের প্রধান সুবিধাসমূহ:**\n"
                f"├─ ⚡️ আল্ট্রা হাই-স্পিড ডাউনলোড লিংক\n"
                f"├─ 🗣 এআই চালিত অটো বানান সংশোধন ব্যবস্থা\n"
                f"└─ 🍿 ৫টি প্রধান ভাষার হাজার হাজার মুভির কালেকশন\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👇 নিচের বাটনগুলো ব্যবহার করে আমাদের সাথে যুক্ত থাকুন।"
            )

            bot_username = getattr(config, "BOT_USERNAME", "bot")
            dev_link = getattr(config, "DEVELOPER_LINK", "https://t.me/your_telegram_username")

            start_buttons = [
                [
                    InlineKeyboardButton("➕ Add Me To Your Groups ➕", url=f"https://t.me/{bot_username}?startgroup=true")
                ],
                [
                    InlineKeyboardButton("🔍 Search", url=config.GROUP_LINK),
                    InlineKeyboardButton("🤖 Updates", url=config.CHANNEL_LINK_2)
                ],
                [
                    InlineKeyboardButton("👑 Buy Premium", callback_data="premium_info"),
                    InlineKeyboardButton("❓ How to Use", url=config.HOW_TO_USE_LINK)
                ],
                [
                    InlineKeyboardButton("👨‍💻 Owner & Developer", url=dev_link)
                ]
            ]
            
            welcome_msg = None
            if config.START_BANNER:
                try:
                    if config.START_BANNER.lower().endswith(".gif"):
                        welcome_msg = await message.reply_animation(
                            animation=config.START_BANNER,
                            caption=welcome_text,
                            reply_markup=InlineKeyboardMarkup(start_buttons)
                        )
                    else:
                        welcome_msg = await message.reply_photo(
                            photo=config.START_BANNER,
                            caption=welcome_text,
                            reply_markup=InlineKeyboardMarkup(start_buttons)
                        )
                except Exception as e:
                    print(f"Error sending banner: {e}")
                    welcome_msg = await message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(start_buttons))
            else:
                welcome_msg = await message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(start_buttons))

            asyncio.create_task(auto_delete_search_messages(message, welcome_msg))
            return

        if text.startswith("/"):
            return

        # --- সাধারণ সার্চ কুয়েরি (PM চ্যাটে) ---
        query = text
        cleaned_text = text.lower().replace(".", " ").replace("-", " ").replace("_", " ")
        noise_words = ["movie", "movies", "full", "hd", "bluray", "web-dl", "mkv", "mp4", "mubi", "bin", "muby", "mube"]
        words = cleaned_text.split()
        if len(words) > 1:
            cleaned_words = [w for w in words if w not in noise_words]
            if cleaned_words:
                query = " ".join(cleaned_words)

        search_msg = await message.reply_text("🔍 খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
        
        # ১.১ প্রথম ধাপ: মঙ্গোডিবির হুবহু অ্যান্ড সার্চ
        results = await search_db(query)
        if results:
            await search_msg.delete()
            results_msg = await send_search_results(message, results, query, page=0, lang="all")
            asyncio.create_task(auto_delete_search_messages(message, results_msg))
            return
            
        # ১.২ দ্বিতীয় ধাপ: এআই স্পেলিং চেকার
        await search_msg.edit_text("🤖 **ভুল বানান শনাক্ত হয়েছে! AI বানান সংশোধন করছে...**")
        await asyncio.sleep(1.5) 
        
        closest_match = await get_close_match_from_db(query)
        
        if closest_match:
            await search_msg.edit_text(
                f"✅ **AI সাজেস্ট করেছে:** `{closest_match}`\n"
                f"🔄 **স্বয়ংক্রিয়ভাবে খোঁজা হচ্ছে:** `{closest_match}`..."
            )
            await asyncio.sleep(1.5) 
            
            corrected_results, _ = await advanced_search_db(closest_match)
            if corrected_results:
                await search_msg.delete()
                results_msg = await send_search_results(message, corrected_results, closest_match, page=0, lang="all")
                asyncio.create_task(auto_delete_search_messages(message, results_msg))
                return

        # ১.৩ তৃতীয় ধাপ: প্রগ্রেসিভ সার্চ
        results, matched_query = await advanced_search_db(query)
        if results:
            await search_msg.delete()
            results_msg = await send_search_results(message, results, matched_query, page=0, lang="all")
            asyncio.create_task(auto_delete_search_messages(message, results_msg))
            return

        # ১.৪ চতুর্থ ধাপ: কোনোভাবেই ফাইল না পাওয়া গেলে
        safe_query = safe_bytes_truncate(query, 55)
        req_buttons = [
            [InlineKeyboardButton("📢 Request Admin to Upload", callback_data=f"req|{safe_query}")]
        ]
        await search_msg.edit_text(
            f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল আমাদের সার্ভারে পাওয়া যায়নি।\n\n"
            f"👉 আপনি চাইলে নিচের বাটনে ক্লিক করে এডমিনকে রিকোয়েস্ট পাঠাতে পারেন। মুভিটি আপলোড হওয়ার সাথে সাথে আপনার ইনবক্সে নোটিফিকেশন চলে আসবে।",
            reply_markup=InlineKeyboardMarkup(req_buttons)
        )
        asyncio.create_task(auto_delete_search_messages(message, search_msg))
        return

    # ==========================================
    # --- খ. গ্রুপ চ্যাট হ্যান্ডলার (Auto-Filter Group Mode) ---
    # ==========================================
    elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if text.startswith("/"):
            return
            
        await add_group(message.chat.id, message.chat.title)
            
        query = text
        cleaned_text = text.lower().replace(".", " ").replace("-", " ").replace("_", " ")
        noise_words = ["movie", "movies", "full", "hd", "bluray", "web-dl", "mkv", "mp4", "mubi", "bin", "muby", "mube"]
        words = cleaned_text.split()
        if len(words) > 1:
            cleaned_words = [w for w in words if w not in noise_words]
            if cleaned_words:
                query = " ".join(cleaned_words)

        results, matched_query = await advanced_search_db(query)
        
        # গ্রুপ চ্যাটেও প্রথমে হুবহু অ্যান্ড সার্চ
        if results:
            group_reply = await send_group_results(message, results, query, page=0, lang="all", searcher_id=user_id)
            asyncio.create_task(auto_delete_group_reply(group_reply))
            return
            
        # গ্রুপ চ্যাটের বানান এআই সংশোধন লজিক
        closest_match = await get_close_match_from_db(query)
        if closest_match:
            safe_closest = safe_bytes_truncate(closest_match, 25)
            suggestion_buttons = [
                [InlineKeyboardButton(f"🎬 Search '{closest_match}'", callback_data=f"gtsearch|{safe_closest}|{user_id}")]
            ]
            
            user_mention = message.from_user.mention if message.from_user else "ইউজার"
            
            suggestion_msg = await message.reply_text(
                f"❌ দুঃখিত {user_mention}, আপনার খোঁজা ফাইলটি পাওয়া যায়নি।\n\n"
                f"🤔 আপনি কি **'{closest_match}'** মুভিটি খুঁজছেন?",
                reply_markup=InlineKeyboardMarkup(suggestion_buttons)
            )
            asyncio.create_task(auto_delete_group_reply(suggestion_msg))
            return
            
        # গ্রুপ চ্যাটের প্রোগ্রেসিভ সার্চ লজিক
        results, matched_query = await advanced_search_db(query)
        if results:
            group_reply = await send_group_results(message, results, matched_query, page=0, lang="all", searcher_id=user_id)
            asyncio.create_task(auto_delete_group_reply(group_reply))
            return
            
        # গ্রুপ চ্যাটের মুভি রিকোয়েস্ট বাটন
        safe_query = safe_bytes_truncate(query, 55)
        req_buttons = [
            [InlineKeyboardButton("📢 Request Admin", callback_data=f"req|{safe_query}")]
        ]
        
        user_mention = message.from_user.mention if message.from_user else "ইউজার"
        
        not_found_msg = await message.reply_text(
            f"❌ দুঃখিত {user_mention}, **'{query}'** মুভিটি পাওয়া যায়নি।\n"
            f"👉 আপনি চাইলে নিচের বাটনে চাপ দিয়ে এডমিনকে রিকোয়েস্ট করতে পারেন।",
            reply_markup=InlineKeyboardMarkup(req_buttons)
        )
        asyncio.create_task(auto_delete_group_reply(not_found_msg))


# সার্চ রেজাল্ট পেজ আকারে সাজানো এবং ল্যাঙ্গুয়েজ ফিল্টারিং বাটন (PM চ্যাটের জন্য)
async def send_search_results(message_or_query, results, query, page=0, lang="all"):
    lang = lang.lower()
    filtered_results = []
    
    # ল্যাঙ্গুয়েজ ফিল্টারিং প্রসেস
    for f in results:
        file_name = f.get("file_name", "").lower()
        caption = f.get("caption", "").lower() if f.get("caption") else ""
        searchable_text = f"{file_name} {caption}"
        
        if lang == "bangla":
            if any(k in searchable_text for k in ["bangla", "bengali", "ben", "bng", "বাংলা", "বেঙ্গলি"]):
                filtered_results.append(f)
        elif lang == "hindi":
            if any(k in searchable_text for k in ["hindi", "hin", "dual", "multi"]):
                filtered_results.append(f)
        elif lang == "english":
            if any(k in searchable_text for k in ["english", "eng", "dual", "multi"]):
                filtered_results.append(f)
        elif lang == "tamil":
            if any(k in searchable_text for k in ["tamil", "tam"]):
                filtered_results.append(f)
        elif lang == "telugu":
            if any(k in searchable_text for k in ["telugu", "tel"]):
                filtered_results.append(f)
        else:
            filtered_results.append(f)

    total_results = len(filtered_results)
    safe_query = safe_bytes_truncate(query, 25)
    
    if total_results == 0:
        text_no_file = f"❌ দুঃখিত, আপনার নির্বাচিত ফিল্টারে কোনো ফাইল পাওয়া যায়নি।"
        back_btn = [[InlineKeyboardButton("🔙 Reset Filter", callback_data=f"lang|0|all|{safe_query}")]]
        try:
            if isinstance(message_or_query, Message):
                return await message_or_query.reply_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
            else:
                return await message_or_query.message.edit_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
        except MessageNotModified:
            pass
        return

    start_index = page * FILES_PER_PAGE
    end_index = start_index + FILES_PER_PAGE
    current_page_results = filtered_results[start_index:end_index]
    
    raw_url = config.WEB_URL.strip()
    if raw_url.lower().startswith("https://"):
        raw_url = raw_url[8:]
    elif raw_url.lower().startswith("http://"):
        raw_url = raw_url[7:]
    if raw_url.endswith("/"):
        raw_url = raw_url[:-1]
    
    user_id = message_or_query.from_user.id if isinstance(message_or_query, Message) else message_or_query.from_user.id

    # বাটন জেনারেট (পিএম প্রিমিয়াম লেআউট)
    buttons = []
    for file in current_page_results:
        raw_fname = file.get("file_name", "Movie File")
        file_name = clean_movie_title(raw_fname)
        
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        
        web_app_url = f"https://{raw_url}/download?id={db_id}&user_id={user_id}"
        buttons.append([InlineKeyboardButton(
            text=f"✨ {file_name} [{file_size} MB]",
            web_app=WebAppInfo(url=web_app_url)
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page|{page - 1}|{safe_query}|{lang}"))
    
    total_pages = (total_results + FILES_PER_PAGE - 1) // FILES_PER_PAGE
    nav_buttons.append(InlineKeyboardButton(f"✨ Page {page + 1}/{total_pages} ✨", callback_data="pages_info"))
    
    if end_index < total_results:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"page|{page + 1}|{safe_query}|{lang}"))
        
    if nav_buttons:
        buttons.append(nav_buttons)

    lang_row1 = [
        InlineKeyboardButton("🇧🇩 Bangla", callback_data=f"lang|0|bangla|{safe_query}"),
        InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"lang|0|hindi|{safe_query}"),
        InlineKeyboardButton("🇺🇸 English", callback_data=f"lang|0|english|{safe_query}")
    ]
    lang_row2 = [
        InlineKeyboardButton("🔥 Tamil", callback_data=f"lang|0|tamil|{safe_query}"),
        InlineKeyboardButton("⚡️ Telugu", callback_data=f"lang|0|telugu|{safe_query}"),
        InlineKeyboardButton("🔙 Reset Filter", callback_data=f"lang|0|all|{safe_query}")
    ]
    buttons.append(lang_row1)
    buttons.append(lang_row2)

    reply_markup = InlineKeyboardMarkup(buttons)
    text = f"🍿 **'{query}'** এর জন্য প্রাপ্ত ফলাফলসমূহ (ফিল্টার: `{lang.upper()}`):"
    
    try:
        if isinstance(message_or_query, Message):
            return await message_or_query.reply_text(text, reply_markup=reply_markup)
        else:
            return await message_or_query.message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass


# --- গ্রুপের ভেতরেই পেজিনেশন এবং ল্যাঙ্গুয়েজ ফিল্টার বাটন জেনারেট করার উন্নত ফাংশন ---
async def send_group_results(message_or_query, results, query, page=0, lang="all", searcher_id=0):
    lang = lang.lower()
    filtered_results = []
    
    for f in results:
        file_name = f.get("file_name", "").lower()
        caption = f.get("caption", "").lower() if f.get("caption") else ""
        searchable_text = f"{file_name} {caption}"
        
        if lang == "bangla":
            if any(k in searchable_text for k in ["bangla", "bengali", "ben", "bng", "বাংলা", "বেঙ্গলি"]):
                filtered_results.append(f)
        elif lang == "hindi":
            if any(k in searchable_text for k in ["hindi", "hin", "dual", "multi"]):
                filtered_results.append(f)
        elif lang == "english":
            if any(k in searchable_text for k in ["english", "eng", "dual", "multi"]):
                filtered_results.append(f)
        elif lang == "tamil":
            if any(k in searchable_text for k in ["tamil", "tam"]):
                filtered_results.append(f)
        elif lang == "telugu":
            if any(k in searchable_text for k in ["telugu", "tel"]):
                filtered_results.append(f)
        else:
            filtered_results.append(f)

    total_results = len(filtered_results)
    safe_query = safe_bytes_truncate(query, 24)  # কলব্যাক লিমিটের জন্য ছোট ট্রাঙ্কেশন

    if total_results == 0:
        text_no_file = f"❌ দুঃখিত, নির্বাচিত ফিল্টারে গ্রুপে কোনো ফাইল পাওয়া যায়নি।"
        back_btn = [[InlineKeyboardButton("🔙 Reset Filter", callback_data=f"gl|0|all|{safe_query}|{searcher_id}")]]
        try:
            if isinstance(message_or_query, Message):
                return await message_or_query.reply_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
            else:
                return await message_or_query.message.edit_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
        except MessageNotModified:
            pass
        return

    start_index = page * FILES_PER_PAGE
    end_index = start_index + FILES_PER_PAGE
    current_page_results = filtered_results[start_index:end_index]
    
    buttons = []
    for file in current_page_results:
        raw_fname = file.get("file_name", "Movie File")
        file_name = clean_movie_title(raw_fname)
        
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        
        # আকর্ষণীয় বাটন ডিজাইন
        buttons.append([InlineKeyboardButton(
            text=f"🎬 {file_name} [{file_size} MB]",
            callback_data=f"gfile|{db_id}|{searcher_id}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"gpage|{page - 1}|{safe_query}|{searcher_id}|{lang}"))
    
    total_pages = (total_results + FILES_PER_PAGE - 1) // FILES_PER_PAGE
    nav_buttons.append(InlineKeyboardButton(f"⚡️ Page {page + 1}/{total_pages} ⚡️", callback_data="pages_info"))
    
    if end_index < total_results:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"gpage|{page + 1}|{safe_query}|{searcher_id}|{lang}"))
        
    if nav_buttons:
        buttons.append(nav_buttons)

    # গ্রুপ চ্যাটের জন্য আকর্ষণীয় ল্যাঙ্গুয়েজ রো-বাটন সেটআপ (ইউনিক gl কলব্যাক)
    lang_row1 = [
        InlineKeyboardButton("🇧🇩 Bangla", callback_data=f"gl|0|bn|{safe_query}|{searcher_id}"),
        InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"gl|0|hi|{safe_query}|{searcher_id}"),
        InlineKeyboardButton("🇺🇸 English", callback_data=f"gl|0|en|{safe_query}|{searcher_id}")
    ]
    lang_row2 = [
        InlineKeyboardButton("🔥 Tamil", callback_data=f"gl|0|ta|{safe_query}|{searcher_id}"),
        InlineKeyboardButton("⚡️ Telugu", callback_data=f"gl|0|te|{safe_query}|{searcher_id}"),
        InlineKeyboardButton("🔙 Reset Filter", callback_data=f"gl|0|all|{safe_query}|{searcher_id}")
    ]
    buttons.append(lang_row1)
    buttons.append(lang_row2)

    reply_markup = InlineKeyboardMarkup(buttons)
    text_reply = (
        f"🍿 **SearchResult for: '{query}'**\n"
        f"🌐 **Selected Filter:** `{lang.upper()}`\n\n"
        f"👇 মুভি ফাইলটি সরাসরি আপনার ইনবক্সে পেতে নিচের বাটনে ক্লিক করুন:\n\n"
        f"⚠️ *এই মেসেজটি ৫ মিনিট পর ডিলিট হয়ে যাবে।*"
    )
    
    try:
        if isinstance(message_or_query, Message):
            return await message_or_query.reply_text(text_reply, reply_markup=reply_markup)
        else:
            return await message_or_query.message.edit_text(text_reply, reply_markup=reply_markup)
    except MessageNotModified:
        pass


# ==========================================
# --- গ. কলব্যাক কুয়েরি হ্যান্ডলার (Callback Handler) ---
# ==========================================

# ১. পেজ নেভিগেশন বাটন ক্লিক (PM)
@Client.on_callback_query(filters.regex(r"^page\|"))
async def page_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    query = data[2]
    lang = data[3]
    
    results, matched_query = await advanced_search_db(query)
    if results:
        await send_search_results(callback_query, results, matched_query, page=target_page, lang=lang)
    await callback_query.answer()

# ২. ল্যাঙ্গুয়েজ ফিল্টার বাটন ক্লিক (PM)
@Client.on_callback_query(filters.regex(r"^lang\|"))
async def lang_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    lang = data[2]
    query = data[3]
    
    results, matched_query = await advanced_search_db(query)
    if results:
        await send_search_results(callback_query, results, matched_query, page=target_page, lang=lang)
    await callback_query.answer()

# ২.১ ল্যাঙ্গুয়েজ ফিল্টার বাটন ক্লিক (Group)
@Client.on_callback_query(filters.regex(r"^gl\|"))
async def group_lang_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    lang_short = data[2]
    query = data[3]
    searcher_id = int(data[4])
    clicker_id = callback_query.from_user.id
    
    if clicker_id != searcher_id:
        await callback_query.answer(
            "⚠️ দুঃখিত! এই ফিল্টার পরিবর্তন করার ক্ষমতা শুধু সার্চকারীর রয়েছে।", 
            show_alert=True
        )
        return
        
    lang_full = GLANG_MAP.get(lang_short, "all")
    results, matched_query = await advanced_search_db(query)
    if results:
        await send_group_results(callback_query, results, matched_query, page=target_page, lang=lang_full, searcher_id=searcher_id)
    await callback_query.answer()

@Client.on_callback_query(filters.regex(r"^pages_info$"))
async def pages_info_click(client: Client, callback_query):
    await callback_query.answer("এটি বর্তমান পেজ নম্বর এবং ফিল্টার নির্দেশ করছে।", show_alert=False)

# ৩. গ্রুপ ফাইল ক্লিক ভেরিফিকেশন (ইউজার লকড)
@Client.on_callback_query(filters.regex(r"^gfile\|"))
async def group_file_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    file_db_id = data[1]
    searcher_id = int(data[2])
    clicker_id = callback_query.from_user.id

    if clicker_id != searcher_id:
        await callback_query.answer(
            "⚠️ দুঃখিত! এই সার্চ রেজাল্টটি আপনার জন্য নয়। অনুগ্রহ করে নিজে গ্রুপে মুভির নাম লিখে সার্চ করুন।", 
            show_alert=True
        )
        return

    await callback_query.answer(
        url=f"https://t.me/{config.BOT_USERNAME}?start={file_db_id}"
    )

# ৪. প্রিমিয়াম পপ-আপ অ্যালার্ট
@Client.on_callback_query(filters.regex(r"^premium_info$"))
async def premium_info_click_handler(client: Client, callback_query):
    premium_text = (
        "👑 **𝗖𝗧𝗚 𝗠𝗢𝗩𝗜𝗘 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗠𝗘𝗠𝗕𝗘𝗥𝗦𝗛𝗜package** 👑\n\n"
        "কোনো শর্টলিংক বা বিজ্ঞাপন ছাড়াই সরাসরি ফাইল এবং আল্ট্রা-স্পিড ডাউনলোড সুবিধা পেতে আজই ভিআইপি মেম্বারশিপ গ্রহণ করুন!\n\n"
        "✨ **মেম্বারদের বিশেষ সুবিধাসমূহ:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 **Ad-Free Experience:** ওয়ান-ক্লিক ডিরেক্ট ফাইল ডাউনলোড (কোনো মিনি অ্যাপ আসবে না)!\n"
        "⚡️ **Super Speed:** সরাসরি ক্যাশ ফাইল ডেলিভারি!\n"
        "🤝 **VIP Request Support:** এডমিনের সরাসরি সাপোর্ট ও ফাস্ট ট্র্যাক রিকোয়েস্ট সুবিধা!\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💵 **মূল্য:** মাত্র ৫০ টাকা / প্রতি মাস\n"
        "📞 **বিকাশ / নগদ (Send Money):** `018XXXXXXXX`\n\n"
        "👉 সেন্ড মানি করার পর স্ক্রিনশট এবং ট্রানজিশন আইডি সহ বটের মেইন এডমিনকে ইনবক্সে পাঠিয়ে দিন।"
    )
    back_button = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start_back")]]
    try:
        await callback_query.message.edit_text(premium_text, reply_markup=InlineKeyboardMarkup(back_button))
    except MessageNotModified:
        pass
    await callback_query.answer()

# ৪.১ হোম মেনুতে ফিরে যাওয়ার ব্যাক বাটন হ্যান্ডলার
@Client.on_callback_query(filters.regex(r"^start_back$"))
async def start_back_handler(client: Client, callback_query):
    welcome_text = (
        f"👋 **Hey {callback_query.from_user.mention}** 🍿\n\n"
        f"I Am **CTG Movie Search Bot (Tier-1 Premium Edition)**\n"
        f"I can find your favorite Movies, Series, Animes, and other files instantly!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 **মুভি খোঁজার নিয়ম:**\n"
        f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম (বানান সঠিক রেখে) লিখে মেসেজ পাঠান। যেমন: `KGF Chapter 2`\n\n"
        f"⚡️ **বটের প্রধান সুবিধাসমূহ:**\n"
        f"├─ ⚡️ আল্ট্রা হাই-স্পিড ডাউনলোড লিংক\n"
        f"├─ 🗣 এআই চালিত অটো বানান সংশোধন ব্যবস্থা\n"
        f"└─ 🍿 ৫টি প্রধান ভাষার হাজার হাজার মুভির কালেকশন\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 নিচের বাটনগুলো ব্যবহার করে আমাদের সাথে যুক্ত থাকুন।"
    )
    bot_username = getattr(config, "BOT_USERNAME", "bot")
    dev_link = getattr(config, "DEVELOPER_LINK", "https://t.me/your_telegram_username")
    
    start_buttons = [
        [
            InlineKeyboardButton("➕ Add Me To Your Groups ➕", url=f"https://t.me/{bot_username}?startgroup=true")
        ],
        [
            InlineKeyboardButton("🔍 Search", url=config.GROUP_LINK),
            InlineKeyboardButton("🤖 Updates", url=config.CHANNEL_LINK_2)
        ],
        [
            InlineKeyboardButton("👑 Buy Premium", callback_data="premium_info"),
            InlineKeyboardButton("❓ How to Use", url=config.HOW_TO_USE_LINK)
        ],
        [
            InlineKeyboardButton("👨‍💻 Owner & Developer", url=dev_link)
        ]
    ]
    try:
        await callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(start_buttons))
    except MessageNotModified:
        pass
    await callback_query.answer()

# ৫. সাজেস্টেড সার্চ ক্লিক হ্যান্ডলার (PM)
@Client.on_callback_query(filters.regex(r"^tsearch\|"))
async def tsearch_click_handler(client: Client, callback_query):
    query = callback_query.data.split("|")[1]
    await callback_query.message.delete()
    results, matched_query = await advanced_search_db(query)
    if results:
        results_msg = await send_search_results(callback_query.message, results, matched_query, page=0, lang="all")
        asyncio.create_task(auto_delete_search_messages(callback_query.message, results_msg))
    else:
        await callback_query.answer("দুঃখিত, কোনো ফাইল পাওয়া যায়নি!", show_alert=True)

# 6. মুভি রিকোয়েস্ট সেভ হ্যান্ডলার এবং এডমিন নোটিফিকেশন সিস্টেম
@Client.on_message(filters.command("request"))
@Client.on_callback_query(filters.regex(r"^req\|"))
async def request_movie_handler(client: Client, callback_query):
    is_callback = not isinstance(callback_query, Message)
    
    if is_callback:
        query = callback_query.data.split("|")[1]
        user = callback_query.from_user
        msg_ctx = callback_query.message
    else:
        if len(callback_query.command) < 2:
            await callback_query.reply_text("⚠️ **ব্যবহার বিধি:** `/request [মুভির নাম]`")
            return
        query = " ".join(callback_query.command[1:])
        user = callback_query.from_user
        msg_ctx = callback_query

    user_id = user.id
    username = f"@{user.username}" if user.username else "নেই"
    first_name = user.first_name or "ইউজার"
    
    from database import save_movie_request
    saved = await save_movie_request(user_id, query)
    
    if saved:
        success_text = (
            f"✅ **মুভি রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
            f"🎬 মুভির নাম: `{query}`\n\n"
            f"👉 এডমিন মুভিটি আপলোড করার সাথে সাথে আপনার ইনবক্সে নোটিফিকেশন চলে আসবে।"
        )
        if is_callback:
            await callback_query.answer("✅ আপনার রিকোয়েস্টটি এডমিনের কাছে পাঠানো হয়েছে!", show_alert=True)
            await msg_ctx.edit_text(success_text)
        else:
            await msg_ctx.reply_text(success_text)
        
        log_text = (
            f"🍿 **নতুন মুভি রিকোয়েস্ট এসেছে!**\n\n"
            f"👤 **ইউজার:** [{first_name}](tg://user?id={user_id})\n"
            f"🔗 **ইউজারনেম:** {username}\n"
            f"🎬 **মুভি:** {query}\n\n"
            f"🆔 **(রিকোয়েস্ট আইডি: {user_id})**"
        )
        
        admin_buttons = [
            [
                InlineKeyboardButton("🚫 রিলিজ হয়নি", callback_data=f"admin_req|not_released|{user_id}"),
                InlineKeyboardButton("❌ বানান ভুল", callback_data=f"admin_req|wrong_sp|{user_id}")
            ],
            [
                InlineKeyboardButton("🟢 আপলোড হয়েছে", callback_data=f"admin_req|uploaded|{user_id}"),
                InlineKeyboardButton("✍️ কাস্টম মেসেজ", callback_data=f"admin_req|custom|{user_id}")
            ]
        ]
        
        if hasattr(config, "LOG_CHANNEL") and config.LOG_CHANNEL:
            try:
                await client.send_message(
                    chat_id=config.LOG_CHANNEL,
                    text=log_text,
                    reply_markup=InlineKeyboardMarkup(admin_buttons)
                )
            except Exception as e:
                print(f"Failed to send request to admin channel: {e}")
    else:
        err_msg = "⚠️ আপনি ইতিমধ্যেই এই মুভিটির রিকোয়েস্ট পাঠিয়েছেন!"
        if is_callback:
            await callback_query.answer(err_msg, show_alert=True)
        else:
            await msg_ctx.reply_text(err_msg)

# ৭. এডমিনদের বাটনে ক্লিক হ্যান্ডলার
@Client.on_callback_query(filters.regex(r"^admin_req\|"))
async def admin_request_action_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    action = data[1]
    target_user_id = int(data[2])
    
    msg_text = callback_query.message.text
    movie_name = "Requested Movie"
    match = re.search(r"🎬\s*মুভি:\s*(.+)", msg_text)
    if match:
        movie_name = match.group(1).strip()
        
    if action == "not_released":
        user_msg = (
            f"⚠️ **মুভি রিকোয়েস্ট আপডেট!**\n\n"
            f"🎬 মুভি: `{movie_name}`\n"
            f"📢 স্ট্যাটাস: **মুভিটি এখনো ওটিটি বা থিয়েটারে রিলিজ হয়নি।**\n\n"
            f"রিলিজ হওয়ার পর আমাদের ডাটাবেজে যুক্ত করে দেওয়া হবে। ধন্যবাদ!"
        )
        try:
            await client.send_message(chat_id=target_user_id, text=user_msg)
            await callback_query.answer("✅ ইউজারকে রিলিজ না হওয়ার বিষয়টি জানানো হয়েছে।", show_alert=True)
            await callback_query.message.edit_text(
                f"{msg_text}\n\n"
                f"🔴 **স্ট্যাটাস:** রিলিজ হয়নি (উত্তরদাতা: {callback_query.from_user.mention})"
            )
        except Exception as e:
            await callback_query.answer(f"❌ ইউজারকে মেসেজ পাঠানো যায়নি: {str(e)}", show_alert=True)
            
    elif action == "wrong_sp":
        user_msg = (
            f"❌ **মুভি রিকোয়েস্ট আপডেট!**\n\n"
            f"🎬 মুভি: `{movie_name}`\n"
            f"📢 স্ট্যাটাস: **বানান ভুল ছিল।**\n\n"
            f"দয়া করে গুগল অথবা উইকিপিডিয়া থেকে সঠিক নাম দেখে আবার রিকোয়েস্ট করুন।"
        )
        try:
            await client.send_message(chat_id=target_user_id, text=user_msg)
            await callback_query.answer("✅ ইউজারকে বানান ভুলের বিষয়টি জানানো হয়েছে।", show_alert=True)
            await callback_query.message.edit_text(
                f"{msg_text}\n\n"
                f"🟡 **স্ট্যাটাস:** বানান ভুল (উত্তরদাতা: {callback_query.from_user.mention})"
            )
        except Exception as e:
            await callback_query.answer(f"❌ ইউজারকে মেসেজ পাঠানো যায়নি: {str(e)}", show_alert=True)
            
    elif action == "uploaded":
        user_msg = (
            f"🎉 **মুভি রিকোয়েস্ট আপডেট!**\n\n"
            f"🎬 মুভি: `{movie_name}`\n"
            f"📢 স্ট্যাটাস: **মুভিটি আপলোড করা হয়েছে!**\n\n"
            f"🔍 এখনই বটের ইনবক্সে সঠিক নাম লিখে সার্চ করুন এবং ফাইলটি সংগ্রহ করুন।"
        )
        try:
            await client.send_message(chat_id=target_user_id, text=user_msg)
            await callback_query.answer("✅ ইউজারকে মুভি আপলোডের বিষয়টি জানানো হয়েছে।", show_alert=True)
            await callback_query.message.edit_text(
                f"{msg_text}\n\n"
                f"🟢 **স্ট্যাটাস:** আপলোড সম্পন্ন (উত্তরদাতা: {callback_query.from_user.mention})"
            )
        except Exception as e:
            await callback_query.answer(f"❌ ইউজারকে মেসেজ পাঠানো যায়নি: {str(e)}", show_alert=True)
            
    elif action == "custom":
        await callback_query.answer("✍️ কাস্টম উত্তর পাঠাতে এই মেসেজের 'Reply' তে আপনার টেক্সটটি লিখুন।", show_alert=True)
        try:
            await callback_query.message.edit_text(
                f"{msg_text}\n\n"
                f"✍️ **কাস্টম উত্তর:** এই মেসেজের 'Reply'-তে আপনার কাঙ্ক্ষিত উত্তরটি লিখুন।\n"
                f"(রিকোয়েস্ট আইডি: {target_user_id})"
            )
        except Exception:
            pass

# ৮. গ্রুপ পেজ নেভিগেশন বাটন ক্লিক হ্যান্ডলার (ইউজার লকড)
@Client.on_callback_query(filters.regex(r"^gpage\|"))
async def group_page_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    query = data[2]
    searcher_id = int(data[3])
    lang = data[4] if len(data) > 4 else "all"
    clicker_id = callback_query.from_user.id
    
    if clicker_id != searcher_id:
        await callback_query.answer(
            "⚠️ দুঃখিত! এই পেজ পরিবর্তন করার ক্ষমতা শুধু সার্চকারীর রয়েছে। নিজে গ্রুপে নাম লিখে সার্চ করুন।", 
            show_alert=True
        )
        return
        
    results, matched_query = await advanced_search_db(query)
    if results:
        await send_group_results(callback_query, results, matched_query, page=target_page, lang=lang, searcher_id=searcher_id)
    await callback_query.answer()

# ৯. সাজেস্টেড সার্চ ক্লিক হ্যান্ডলার (গ্রুপ চ্যাটের জন্য - ইউজার লকড)
@Client.on_callback_query(filters.regex(r"^gtsearch\|"))
async def gtsearch_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    query = data[1]
    searcher_id = int(data[2])
    clicker_id = callback_query.from_user.id
    
    if clicker_id != searcher_id:
        await callback_query.answer(
            "⚠️ দুঃখিত! এই সার্চ সাজেশনটি আপনার জন্য নয়। অনুগ্রহ করে নিজে গ্রুপে নাম লিখে সার্চ করুন।", 
            show_alert=True
        )
        return
        
    await callback_query.message.delete()
    results, matched_query = await advanced_search_db(query)
    if results:
        group_reply = await send_group_results(callback_query, results, matched_query, page=0, lang="all", searcher_id=searcher_id)
        asyncio.create_task(auto_delete_group_reply(group_reply))
    else:
        await callback_query.answer("দুঃখিত, কোনো ফাইল পাওয়া যায়নি!", show_alert=True)
