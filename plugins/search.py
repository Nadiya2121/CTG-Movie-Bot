# plugins/search.py

import asyncio
import re
import difflib  # বানান সংশোধনের Fuzzy matching এর জন্য পাইথনের নিজস্ব লাইব্রেরি
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from pyrogram.enums import ChatType
from pyrogram.errors import UserNotParticipant, MessageNotModified
from database import search_db, get_file_by_db_id, add_user
import config

FILES_PER_PAGE = 5

# --- সুনির্দিষ্ট ক্লিন-আপ ফাংশন (মুভির নাম ঠিক রেখে প্রমোশন লিংক ডিলিট করবে) ---
def clean_movie_title(name: str) -> str:
    name = re.sub(r'@[a-zA-Z0-9_]+', '', name)
    name = re.sub(r'(https?://)?(t\.me|telegram\.me|telegram\.dog)/[a-zA-Z0-9_\+]+', '', name)
    domain_extensions = "com|org|net|xyz|club|co|tv|link|info|me|cc|site|space|click|in|online|icu"
    name = re.sub(r'\b[a-zA-Z0-9-]+\.(' + domain_extensions + r')\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*$', '', name)
    name = name.replace("__", "_").replace("..", ".").replace("  ", " ")
    if not name.strip():
         name = "Movie File"
    return name.strip()

# --- ৫ মিনিট পর ফাইল স্বয়ংক্রিয়ভাবে মুছে দেওয়ার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_file(message: Message):
    await asyncio.sleep(300) # ৩০০ সেকেন্ড = ৫ মিনিট
    try:
        await message.delete()
    except:
        pass

# --- ৫ মিনিট পর ইউজারের সার্চ এবং বটের বাটন মেসেজ ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_search_messages(user_msg: Message, bot_msg: Message):
    await asyncio.sleep(300)
    try:
        await user_msg.delete()
    except:
        pass
    try:
        await bot_msg.delete()
    except:
        pass

# --- গ্রুপে বটের রিপ্লাই ১ মিনিট পর ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_group_reply(message: Message):
    await asyncio.sleep(60)
    try:
        await message.delete()
    except:
        pass

# --- বানান ভুল সংশোধন সাজেশন মেকানিজম (Did You Mean?) ---
async def get_close_match_from_db(query: str):
    try:
        # ডাটাবেজ থেকে মুভির আসল নামগুলো এনে একটি তুলনামূলক লিস্ট তৈরি করা
        from database import files_col1
        all_names = []
        cursor = files_col1.find({}, {"file_name": 1}).limit(1000) # পারফরম্যান্স বজায় রাখতে সর্বোচ্চ ১০০০ ফাইল স্ক্যান করবে
        async for doc in cursor:
            all_names.append(clean_movie_title(doc["file_name"]))
            
        # difflib দিয়ে সবচেয়ে কাছাকাছি বানানের নামটি খুঁজে বের করা (cutoff ০.৩৫ রাখা হয়েছে যাতে বেশি ভুল থাকলেও খুঁজে পায়)
        matches = difflib.get_close_matches(query, list(set(all_names)), n=1, cutoff=0.35)
        return matches[0] if matches else None
    except Exception as e:
        print(f"Fuzzy match error: {e}")
        return None


@Client.on_message(filters.text)
async def main_handler(client: Client, message: Message):
    text = message.text.strip()
    user_id = message.from_user.id

    # ==========================================
    # --- ক. পার্সোনাল চ্যাট হ্যান্ডলার (Private PM) ---
    # ==========================================
    if message.chat.type == ChatType.PRIVATE:
        if text.startswith("/start"):
            
            # --- ১. ফোর্স সাবস্ক্রিপশন চেক ---
            if user_id != config.ADMIN_ID:
                try:
                    await client.get_chat_member(config.MAIN_CHANNEL_ID, user_id)
                except UserNotParticipant:
                    fsub_buttons = [
                        [InlineKeyboardButton("🍿 Join Our Movie Channel", url=config.CHANNEL_LINK_1)],
                        [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{config.BOT_USERNAME}?start={text[7:]}" if len(text.split()) > 1 else f"https://t.me/{config.BOT_USERNAME}?start=start")]
                    ]
                    await message.reply_text(
                        f"👋 **হ্যালো {message.from_user.first_name}!**\n\n"
                        f"বট থেকে ফাইল পেতে হলে আপনাকে প্রথমে আমাদের মুভি চ্যানেলে জয়েন হতে হবে।\n\n"
                        f"👉 অনুগ্রহ করে নিচের বাটনে জয়েন করে 'Try Again' এ ক্লিক করুন।",
                        reply_markup=InlineKeyboardMarkup(fsub_buttons)
                    )
                    return
                except Exception as e:
                    print(f"FSub Warning (Make sure bot is Admin in main channel): {e}")

            # --- ২. সিকিউরিটি চেক এবং ফাইল ডেলিভারি ---
            if len(text.split()) > 1:
                start_param = text.split()[1]
                
                # ক. ইউজার যদি বিজ্ঞাপন দেখে আসল চাবি 'get_' সহ ফিরে আসে
                if start_param.startswith("get_"):
                    file_db_id = start_param.replace("get_", "")
                    file_data = await get_file_by_db_id(file_db_id)
                    
                    if file_data:
                        try:
                            raw_name = file_data["file_name"]
                            cleaned_name = clean_movie_title(raw_name)
                            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
                            
                            caption_text = (
                                f"🎬 **ফাইলের নাম:** `{cleaned_name}`\n"
                                f"💾 **ফাইলের সাইজ:** `{file_size} MB`\n\n"
                                f"📢 **চ্যানেল লিংকসমূহ নিচে দেওয়া হলো:**\n"
                                f"👉 আমাদের সাথে ব্যাকআপ চ্যানেলে যুক্ত থাকুন।\n\n"
                                f"⚠️ **নিরাপত্তা সতর্কবার্তা:**\n"
                                f"কпиরাইট এড়াতে এই ফাইলটি আগামী **৫ মিনিট** পর স্বয়ংক্রিয়ভাবে মুছে যাবে। দয়া করে এর মধ্যেই আপনার সেভড মেসেজে ফাইলটি ফরওয়ার্ড করে রাখুন।"
                            )
                            
                            promo_buttons = [
                                [InlineKeyboardButton("🍿 All Movie Link", url=config.CHANNEL_LINK_1)],
                                [InlineKeyboardButton("📢 Join Backup Channel", url=config.CHANNEL_LINK_2)]
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
                    file_db_id = start_param
                    file_data = await get_file_by_db_id(file_db_id)
                    
                    if file_data:
                        file_name = clean_movie_title(file_data["file_name"])
                        raw_url = config.WEB_URL.strip().replace("https://", "").replace("http://", "").rstrip("/")
                        web_app_url = f"https://{raw_url}/download?id={file_db_id}"
                        
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

            # সাধারণ স্টার্ট কমান্ড (ব্যানার ব্যানার এবং স্থায়ী ৪টি মেনু বাটন গ্রিড)
            try:
                await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            except:
                pass

            welcome_text = (
                f"👋 **হ্যালো {message.from_user.first_name or 'ইউজার'}!**\n\n"
                f"🎬 **CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n"
                f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম লিখে মেসেজ পাঠান।\n\n"
                f"📢 **ব্যবহারের নিয়মাবলী:**\n"
                f"১. মুভির নাম বানান সঠিক রেখে লিখে পাঠান।\n"
                f"২. নিচের বাটনগুলো ব্যবহার করে আমাদের প্রফেশনাল গ্রুপ ও চ্যানেলে যুক্ত হতে পারেন।"
            )

            # ৪টি প্রিমিয়াম ইনলাইন বাটনের স্থায়ী গ্রিড
            start_buttons = [
                [
                    InlineKeyboardButton("🍿 All Movie Link", url=config.CHANNEL_LINK_1),
                    InlineKeyboardButton("📢 Join Backup Channel", url=config.CHANNEL_LINK_2)
                ],
                [
                    InlineKeyboardButton("👑 Premium Membership", callback_data="premium_info"),
                    InlineKeyboardButton("💬 Movie Search Group", url=config.CHANNEL_LINK_1)
                ]
            ]
            
            # ব্যানার সোর্স অনুযায়ী ইমেজ বা জিআইএফ সেন্ড করা হবে
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

            # ৫ মিনিট পর ইউজার মেসেজ এবং স্বাগত বার্তা ডিলিট
            asyncio.create_task(auto_delete_search_messages(message, welcome_msg))
            return

        if text.startswith("/"):
            return

        # --- সাধারণ সার্চ কুয়েরি (PM চ্যাটে) ---
        query = text
        cleaned_text = text.lower().replace(".", " ").replace("-", " ")
        noise_words = ["movie", "movies", "full", "hd", "bluray", "web-dl", "mkv", "mp4", "mubi", "bin", "muby", "mube"]
        words = cleaned_text.split()
        if len(words) > 1:
            cleaned_words = [w for w in words if w not in noise_words]
            if cleaned_words:
                query = " ".join(cleaned_words)

        search_msg = await message.reply_text("🔍 খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
        results = await search_db(query)
        
        # যদি কোনো ফাইল ডাটাবেজে খুঁজে পাওয়া না যায় (Fuzzy Auto-Suggestion লজিক)
        if not results:
            closest_match = await get_close_match_from_db(query)
            
            if closest_match:
                # কাছাকাছি নামের সাজেশন বাটন সহ রিপ্লাই দেওয়া হচ্ছে
                suggestion_buttons = [
                    [InlineKeyboardButton(f"🎬 Search '{closest_match}'", callback_data=f"tsearch|{closest_match}")]
                ]
                await search_msg.edit_text(
                    f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল পাওয়া যায়নি।\n\n"
                    f"🤔 আপনি কি **'{closest_match}'** বোঝাতে চেয়েছেন?\n"
                    f"নিচের বাটনে চাপ দিলে স্বয়ংক্রিয়ভাবে মুভিটি সার্চ হয়ে যাবে।",
                    reply_markup=InlineKeyboardMarkup(suggestion_buttons)
                )
            else:
                await search_msg.edit_text(f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল পাওয়া যায়নি।")
                
            asyncio.create_task(auto_delete_search_messages(message, search_msg))
            return

        await search_msg.delete()
        results_msg = await send_search_results(message, results, query, page=0, lang="all")
        asyncio.create_task(auto_delete_search_messages(message, results_msg))

    # ==========================================
    # --- খ. গ্রুপ চ্যাট হ্যান্ডলার (Auto-Filter Group Mode) ---
    # ==========================================
    elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if text.startswith("/"):
            return
            
        query = text
        cleaned_text = text.lower().replace(".", " ").replace("-", " ")
        noise_words = ["movie", "movies", "full", "hd", "bluray", "web-dl", "mkv", "mp4", "mubi", "bin", "muby", "mube"]
        words = cleaned_text.split()
        if len(words) > 1:
            cleaned_words = [w for w in words if w not in noise_words]
            if cleaned_words:
                query = " ".join(cleaned_words)

        results = await search_db(query)
        
        # গ্রুপে মুভি না পাওয়া গেলে বটের স্বয়ংক্রিয় সাজেশন ট্রিক
        if not results:
            closest_match = await get_close_match_from_db(query)
            if closest_match:
                suggestion_buttons = [
                    [InlineKeyboardButton(f"🎬 Search '{closest_match}'", callback_data=f"tsearch|{closest_match}")]
                ]
                suggestion_msg = await message.reply_text(
                    f"❌ দুঃখিত {message.from_user.mention}, আপনার খোঁজা ফাইলটি পাওয়া যায়নি।\n\n"
                    f"🤔 আপনি কি **'{closest_match}'** মুভিটি খুঁজছেন?",
                    reply_markup=InlineKeyboardMarkup(suggestion_buttons)
                )
                asyncio.create_task(auto_delete_group_reply(suggestion_msg))
            return
            
        buttons = []
        for file in results[:5]:
            file_name = clean_movie_title(file["file_name"])
            file_size = round(file["file_size"] / (1024 * 1024), 2)
            db_id = str(file["_id"])
            searcher_id = message.from_user.id
            
            buttons.append([InlineKeyboardButton(
                text=f"🎬 {file_name} [{file_size} MB]",
                callback_data=f"gfile|{db_id}|{searcher_id}"
            )])
            
        text_reply = (
            f"🍿 **{message.from_user.mention}** এর খোঁজা মুভিটির **{len(results)}** টি রেজাল্ট পাওয়া গেছে।\n"
            f"👇 মুভি ফাইলটি সরাসরি আপনার ইনবক্সে পেতে নিচের বাটনে ক্লিক করুন:\n\n"
            f"⚠️ *এই মেসেজটি ১ মিনিট পর ডিলিট হয়ে যাবে।*"
        )
        
        group_reply = await message.reply_text(text_reply, reply_markup=InlineKeyboardMarkup(buttons))
        asyncio.create_task(auto_delete_group_reply(group_reply))


# সার্চ রেজাল্ট পেজ আকারে সাজানো এবং ল্যাঙ্গুয়েজ ফিল্টারিং বাটন জেনারেশন ফাংশন
async def send_search_results(message_or_query, results, query, page=0, lang="all"):
    lang = lang.lower()
    filtered_results = []
    
    if lang == "bangla":
        filtered_results = [f for f in results if any(k in f["file_name"].lower() for k in ["bangla", "bengali", "ben", "bng", "বাংলা", "বেঙ্গলি"])]
    elif lang == "hindi":
        filtered_results = [f for f in results if any(k in f["file_name"].lower() for k in ["hindi", "hin", "dual", "multi"])]
    elif lang == "english":
        filtered_results = [f for f in results if any(k in f["file_name"].lower() for k in ["english", "eng", "dual", "multi"])]
    elif lang == "tamil":
        filtered_results = [f for f in results if any(k in f["file_name"].lower() for k in ["tamil", "tam"])]
    elif lang == "telugu":
        filtered_results = [f for f in results if any(k in f["file_name"].lower() for k in ["telugu", "tel"])]
    else:
        filtered_results = results

    total_results = len(filtered_results)
    
    if total_results == 0:
        text_no_file = f"❌ দুঃখিত, আপনার নির্বাচিত ফিল্টারে কোনো ফাইল পাওয়া যায়নি।"
        back_btn = [[InlineKeyboardButton("🔙 Reset Filter", callback_data=f"lang|0|all|{query}")]]
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
    
    # ইউআরএল স্যানিটাইজার
    raw_url = config.WEB_URL.strip()
    if raw_url.lower().startswith("https://"):
        raw_url = raw_url[8:]
    elif raw_url.lower().startswith("http://"):
        raw_url = raw_url[7:]
    if raw_url.endswith("/"):
        raw_url = raw_url[:-1]
    
    buttons = []
    for file in current_page_results:
        file_name = clean_movie_title(file["file_name"])
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        web_app_url = f"https://{raw_url}/download?id={db_id}"
        
        buttons.append([InlineKeyboardButton(
            text=f"🎬 {file_name} [{file_size} MB]",
            web_app=WebAppInfo(url=web_app_url)
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ আগের", callback_data=f"page|{page - 1}|{query}|{lang}"))
    
    total_pages = (total_results + FILES_PER_PAGE - 1) // FILES_PER_PAGE
    nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="pages_info"))
    
    if end_index < total_results:
        nav_buttons.append(InlineKeyboardButton("পরের ▶️", callback_data=f"page|{page + 1}|{query}|{lang}"))
        
    if nav_buttons:
        buttons.append(nav_buttons)

    lang_row1 = [
        InlineKeyboardButton("🇧🇩 বাংলা/Bengali", callback_data=f"lang|0|bangla|{query}"),
        InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"lang|0|hindi|{query}"),
        InlineKeyboardButton("🇺🇸 English", callback_data=f"lang|0|english|{query}")
    ]
    lang_row2 = [
        InlineKeyboardButton("🇮🇳 Tamil", callback_data=f"lang|0|tamil|{query}"),
        InlineKeyboardButton("🇮🇳 Telugu", callback_data=f"lang|0|telugu|{query}"),
        InlineKeyboardButton("🔙 Reset", callback_data=f"lang|0|all|{query}")
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


# ==========================================
# --- গ. কলব্যাক কুয়েরি হ্যান্ডলার (Callback Handler) ---
# ==========================================

# ১. পেজ নেভিগেশন বাটন ক্লিক
@Client.on_callback_query(filters.regex(r"^page\|"))
async def page_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    query = data[2]
    lang = data[3]
    
    results = await search_db(query)
    if results:
        await send_search_results(callback_query, results, query, page=target_page, lang=lang)
    await callback_query.answer()

# ২. ল্যাঙ্গুয়েজ ফিল্টার বাটন ক্লিক
@Client.on_callback_query(filters.regex(r"^lang\|"))
async def lang_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    lang = data[2]
    query = data[3]
    
    results = await search_db(query)
    if results:
        await send_search_results(callback_query, results, query, page=target_page, lang=lang)
    await callback_query.answer()

# ৩. প্রোগ্রেসিভ পেজ ইনফো
@Client.on_callback_query(filters.regex(r"^pages_info$"))
async def pages_info_click(client: Client, callback_query):
    await callback_query.answer("এটি বর্তমান পেজ নম্বর এবং ফিল্টার নির্দেশ করছে।", show_alert=False)

# ৪. গ্রুপ ফাইল ক্লিক ভেরিফিকেশন (ইউজার লকড)
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

# ৫. প্রিমিয়াম পপ-আপ ইনফো অ্যালার্ট (নতুন)
@Client.on_callback_query(filters.regex(r"^premium_info$"))
async def premium_info_click_handler(client: Client, callback_query):
    premium_text = (
        "👑 CTG MOVIE PREMIUM BENEFITS:\n\n"
        "⚡️ Ad-Free (মিনি অ্যাপ ও বিজ্ঞাপন ছাড়াই সরাসরি ফাইল!)\n"
        "🚀 Unlimited High-Speed Direct Files!\n"
        "🤖 Personal Admin Support & Movie Request!\n\n"
        "💵 Price: 50 BDT / Month\n"
        "📞 Bkash/Nagad: 018XXXXXXXX\n\n"
        "👉 সেন্ড মানি করার পর ট্রানজিশন আইডি সহ স্ক্রিনশট এডমিনকে ইনবক্সে পাঠিয়ে দিন।"
    )
    await callback_query.answer(premium_text, show_alert=True)

# ৬. সাজেস্টেড সার্চ ক্লিক হ্যান্ডলার (Fuzzy "Did You Mean" Auto-Search - নতুন)
@Client.on_callback_query(filters.regex(r"^tsearch\|"))
async def tsearch_click_handler(client: Client, callback_query):
    query = callback_query.data.split("|")[1]
    
    # লোডিং বাটন মুছে দেওয়া
    await callback_query.message.delete()
    
    # নতুন সার্চ রান করা হচ্ছে স্বয়ংক্রিয়ভাবে
    results = await search_db(query)
    if results:
        results_msg = await send_search_results(callback_query.message, results, query, page=0, lang="all")
        # ৫ মিনিট পর ক্লিন-আপ টাস্ক শুরু
        asyncio.create_task(auto_delete_search_messages(callback_query.message, results_msg))
    else:
        await callback_query.answer("দুঃখিত, কোনো ফাইল পাওয়া যায়নি!", show_alert=True)
