# plugins/search.py

import asyncio
import re
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

# --- গ্রুপে বটের রিপ্লাই ১ মিনিট পর ডিলিট করার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_group_reply(message: Message):
    await asyncio.sleep(60) # ৬০ সেকেন্ড = ১ মিনিট
    try:
        await message.delete()
    except:
        pass


@Client.on_message(filters.text)
async def main_handler(client: Client, message: Message):
    text = message.text.strip()
    user_id = message.from_user.id

    # ==========================================
    # --- ক. পার্সোনাল চ্যাট হ্যান্ডলার (Private PM) ---
    # ==========================================
    if message.chat.type == ChatType.PRIVATE:
        if text.startswith("/start"):
            
            # --- ১. ফোর্স সাবস্ক্রিপশন চেক (এডমিন ছাড়া বাকি সবার জন্য বাধ্যতামূলক) ---
            if user_id != config.ADMIN_ID:
                try:
                    await client.get_chat_member(config.MAIN_CHANNEL_ID, user_id)
                except UserNotParticipant:
                    # জয়েন না থাকলে ব্লক করা হবে
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
                    # সেফটি ফিল্টার: এডমিন মেকানিজমে ভুল থাকলে যাতে সাধারণ ইউজাররা অন্তত ব্লক না হয়
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
                                f"কপিরাইট এড়াতে এই ফাইলটি আগামী **৫ মিনিট** পর স্বয়ংক্রিয়ভাবে মুছে যাবে। দয়া করে এর মধ্যেই আপনার সেভড মেসেজে ফাইলটি ফরওয়ার্ড করে রাখুন।"
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
                        await message.reply_text(
                            f"🎬 **ফাইলের নাম:** `{file_name}`\n\n"
                            f"👉 ফাইলটি ডাউনলোড করার জন্য নিচের বাটনে ক্লিক করে বিজ্ঞাপনটি আনলক করুন।",
                            reply_markup=InlineKeyboardMarkup(buttons)
                        )
                    else:
                        await message.reply_text("❌ দুঃখিত, ফাইলটি ডাটাবেজে খুঁজে পাওয়া যায়নি!")
                    return

            # সাধারণ স্টার্ট কমান্ড
            try:
                await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            except:
                pass

            welcome_text = (
                f"👋 **হ্যালো {message.from_user.first_name or 'ইউজার'}!**\n\n"
                f"🎬 **🎬 CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n"
                f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম লিখে মেসেজ পাঠান।"
            )
            await message.reply_text(welcome_text)
            return

        if text.startswith("/"):
            return

        # সাধারণ সার্চ কুয়েরি (PM চ্যাটে)
        query = clean_search_query(text)
        search_msg = await message.reply_text("🔍 খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
        results = await search_db(query)
        
        if not results:
            await search_msg.edit_text(f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল পাওয়া যায়নি।")
            return

        await search_msg.delete()
        await send_search_results(message, results, query, page=0, lang="all")

    # ==========================================
    # --- খ. গ্রুপ চ্যাট হ্যান্ডলার (Auto-Filter Group Mode) ---
    # ==========================================
    elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if text.startswith("/"):
            return
            
        query = clean_search_query(text)
        results = await search_db(query)
        
        if not results:
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
                await message_or_query.reply_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
            else:
                await message_or_query.message.edit_text(text_no_file, reply_markup=InlineKeyboardMarkup(back_btn))
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
            await message_or_query.reply_text(text, reply_markup=reply_markup)
        else:
            await message_or_query.message.edit_text(text, reply_markup=reply_markup)
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

@Client.on_callback_query(filters.regex(r"^pages_info$"))
async def pages_info_click(client: Client, callback_query):
    await callback_query.answer("এটি বর্তমান পেজ নম্বর এবং ফিল্টার নির্দেশ করছে।", show_alert=False)

# ৩. গ্রুপ ফাইল ক্লিক ভেরিফিকেশন
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

    # আসল ইউজার ক্লিক করলে তাকে বটের ইনবক্সে রিডাইরেক্ট করা হচ্ছে
    await callback_query.answer(
        url=f"https://t.me/{config.BOT_USERNAME}?start={file_db_id}"
    )
