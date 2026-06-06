# plugins/search.py

import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from database import search_db, get_file_by_db_id, add_user
import config
from urllib.parse import quote

FILES_PER_PAGE = 5

# --- ফাইলের নাম থেকে অন্যের লিংক এবং ইউজারনেম মুছে দেওয়ার ক্লিন-আপ ফাংশন ---
def clean_movie_title(name: str) -> str:
    # টেলিগ্রামের ইউজারনেম মুছে ফেলা (@username)
    name = re.sub(r'@[a-zA-Z0-9_]+', '', name)
    # টেলিগ্রামের লিংক মুছে ফেলা (t.me/... বা telegram.me/...)
    name = re.sub(r'(https?://)?(t\.me|telegram\.me)/[a-zA-Z0-9_\+]+', '', name)
    # সাধারণ ওয়েবসাইট লিংক মুছে ফেলা
    name = re.sub(r'(https?://)?(www\.)?[a-zA-Z0-9-]+\.[a-zA-Z0-9.]+', '', name)
    # অতিরিক্ত আন্ডারস্কোর, ডট বা স্পেসগুলো সুন্দরভাবে গোছানো
    name = name.replace("__", "_").replace("..", ".").replace("  ", " ")
    return name.strip()

# --- ৫ মিনিট পর পাঠানো ফাইলটি স্বয়ংক্রিয়ভাবে মুছে দেওয়ার ব্যাকগ্রাউন্ড টাস্ক ---
async def auto_delete_file(message: Message):
    await asyncio.sleep(300) # ৩০০ সেকেন্ড = ৫ মিনিট
    try:
        await message.delete()
    except Exception as e:
        print(f"Failed to auto delete file: {e}")


@Client.on_message(filters.text & filters.private)
async def main_handler(client: Client, message: Message):
    text = message.text.strip()

    # --- ১. মিনি অ্যাপ থেকে "Get Movie File" চাপলে ফাইল রিসিভ ও অটো-ডিলিট প্রসেস ---
    if text.startswith("/start"):
        if len(text.split()) > 1:
            file_db_id = text.split()[1]
            file_data = await get_file_by_db_id(file_db_id)
            
            if file_data:
                try:
                    # ফাইলের নাম ক্লিন করা হচ্ছে
                    raw_name = file_data["file_name"]
                    cleaned_name = clean_movie_title(raw_name)
                    file_size = round(file_data["file_size"] / (1024 * 1024), 2)
                    
                    # প্রফেশনাল ক্যাপশন ও সতর্কবার্তা
                    caption_text = (
                        f"🎬 **ফাইলের নাম:** `{cleaned_name}`\n"
                        f"💾 **ফাইলের সাইজ:** `{file_size} MB`\n\n"
                        f"📢 **চ্যানেল লিংকসমূহ নিচে দেওয়া হলো:**\n"
                        f"👉 আমাদের সাথে ব্যাকআপ চ্যানেলে যুক্ত থাকুন।\n\n"
                        f"⚠️ **নিরাপত্তা সতর্কবার্তা:**\n"
                        f"কপিরাইট এড়াতে এই ফাইলটি আগামী **৫ মিনিট** পর স্বয়ংক্রিয়ভাবে মুছে যাবে। দয়া করে এর মধ্যেই আপনার সেভড মেসেজে ফাইলটি ফরওয়ার্ড করে রাখুন।"
                    )
                    
                    # আপনার দেওয়া চ্যানেল লিংক দিয়ে বাটন তৈরি
                    promo_buttons = [
                        [InlineKeyboardButton("🍿 All Movie Link", url=config.CHANNEL_LINK_1)],
                        [InlineKeyboardButton("📢 Join Backup Channel", url=config.CHANNEL_LINK_2)]
                    ]
                    
                    # ফাইল পাঠানো হলো
                    sent_file = await client.send_cached_media(
                        chat_id=message.chat.id,
                        file_id=file_data["file_id"],
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(promo_buttons)
                    )
                    
                    # ৫ মিনিটের জন্য কাউন্টডাউন শুরু ও ফাইল ডিলিট শিডিউল
                    asyncio.create_task(auto_delete_file(sent_file))
                    
                except Exception as e:
                    await message.reply_text(f"❌ দুঃখিত, ফাইলটি পাঠানো যাচ্ছে না: {str(e)}")
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
            f"🎬 **CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n"
            f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম লিখে মেসেজ পাঠান।"
        )
        await message.reply_text(welcome_text)
        return

    if text.startswith("/"):
        return

    # --- ২. মুভি সার্চ ও মিনি অ্যাপ বাটন ---
    query = text
    search_msg = await message.reply_text("🔍 খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    results = await search_db(query)
    
    if not results:
        await search_msg.edit_text(f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল পাওয়া যায়নি।")
        return

    await search_msg.delete()
    await send_search_results(message, results, query, page=0)


async def send_search_results(message_or_query, results, query, page=0):
    total_results = len(results)
    start_index = page * FILES_PER_PAGE
    end_index = start_index + FILES_PER_PAGE
    
    current_page_results = results[start_index:end_index]
    
    # ইউআরএল ক্লিন-আপ
    raw_url = config.WEB_URL.strip()
    if raw_url.lower().startswith("https://"):
        raw_url = raw_url[8:]
    elif raw_url.lower().startswith("http://"):
        raw_url = raw_url[7:]
    if raw_url.endswith("/"):
        raw_url = raw_url[:-1]
    
    buttons = []
    for file in current_page_results:
        # সার্চ রেজাল্টেও যাতে অন্যের ইউজারনেম/লিংক না দেখায় তার জন্য ক্লিন করা হচ্ছে
        file_name = clean_movie_title(file["file_name"])
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        
        safe_movie_title = quote(file_name)
        web_app_url = f"https://{raw_url}/download?id={db_id}&title={safe_movie_title}"
        
        buttons.append([InlineKeyboardButton(
            text=f"🎬 {file_name} [{file_size} MB]",
            web_app=WebAppInfo(url=web_app_url)
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ আগের", callback_data=f"page|{page - 1}|{query}"))
    
    total_pages = (total_results + FILES_PER_PAGE - 1) // FILES_PER_PAGE
    nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="pages_info"))
    
    if end_index < total_results:
        nav_buttons.append(InlineKeyboardButton("পরের ▶️", callback_data=f"page|{page + 1}|{query}"))
        
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons)
    text = f"🍿 **'{query}'** এর জন্য প্রাপ্ত ফলাফলসমূহ:"
    
    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(text, reply_markup=reply_markup)
    else:
        await message_or_query.message.edit_text(text, reply_markup=reply_markup)


# পেজ নেভিগেশন
@Client.on_callback_query(filters.regex(r"^page\|"))
async def page_click_handler(client: Client, callback_query):
    data = callback_query.data.split("|")
    target_page = int(data[1])
    query = data[2]
    
    results = await search_db(query)
    if results:
        await send_search_results(callback_query, results, query, page=target_page)
    await callback_query.answer()

@Client.on_callback_query(filters.regex(r"^pages_info$"))
async def pages_info_click(client: Client, callback_query):
    await callback_query.answer("এটি বর্তমান পেজ নম্বর নির্দেশ করছে।", show_alert=False)
