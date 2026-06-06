# plugins/search.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from database import search_db, get_file_by_db_id, add_user

# প্রতি পৃষ্ঠায় কয়টি করে মুভি বাটন দেখাবে
FILES_PER_PAGE = 5

@Client.on_message(filters.text & filters.private)
async def main_handler(client: Client, message: Message):
    text = message.text.strip()

    # --- ১. যদি মেসেজটি '/start' হয় (সার্চ ফিল্টারের ভেতর কমান্ড হ্যান্ডলিং) ---
    if text.startswith("/start"):
        # ব্যাকগ্রাউন্ডে ইউজার সেভ করা
        try:
            await add_user(
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
        except Exception as e:
            print(f"User save error: {e}")

        # স্বাগত বার্তা পাঠানো
        welcome_text = (
            f"👋 **হ্যালো {message.from_user.first_name or 'ইউজার'}!**\n\n"
            f"🎬 **CTG Movie সার্চ বটে আপনাকে স্বাগতম!**\n"
            f"এখানে আপনি আপনার পছন্দের যেকোনো মুভি ও ওয়েব সিরিজ পেয়ে যাবেন খুবই দ্রুত।\n\n"
            f"📢 **কিভাবে মুভি খুঁজবেন?**\n"
            f"বটের ইনবক্সে সরাসরি যেকোনো মুভির নাম লিখে মেসেজ পাঠান।\n"
            f"💡 *যেমন:* `RRR` অথবা `KGF` লিখে পাঠান।\n\n"
            f"⚠️ *সহজ অনুসন্ধানের জন্য মুভির সঠিক বানানটি লেখার অনুরোধ রইল।*"
        )
        await message.reply_text(welcome_text)
        return

    # --- ২. যদি অন্য কোনো এডমিন কমান্ড হয় (যা / দিয়ে শুরু) ---
    if text.startswith("/"):
        return # এডমিন কমান্ডগুলো plugins/admin.py হ্যান্ডেল করবে

    # --- ৩. সাধারণ মেসেজ হলে মুভি সার্চ করা ---
    query = text
    search_msg = await message.reply_text("🔍 খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    
    results = await search_db(query)
    
    if not results:
        await search_msg.edit_text(f"❌ দুঃখিত, **'{query}'** নামের কোনো ফাইল পাওয়া যায়নি।")
        return

    await search_msg.delete()
    
    # প্রথম পেজ (Page 0) জেনারেট করা
    await send_search_results(message, results, query, page=0)


# সার্চ রেজাল্ট পেজ আকারে সাজানোর ফাংশন
async def send_search_results(message_or_query, results, query, page=0):
    total_results = len(results)
    start_index = page * FILES_PER_PAGE
    end_index = start_index + FILES_PER_PAGE
    
    current_page_results = results[start_index:end_index]
    
    buttons = []
    for file in current_page_results:
        file_name = file["file_name"]
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        buttons.append([InlineKeyboardButton(f"🎬 {file_name} [{file_size} MB]", callback_data=f"file_{db_id}")])

    # নেভিগেশন বাটন (Previous / Next) তৈরি
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


# পেজ পরিবর্তনের বাটন ক্লিক হ্যান্ডলার
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


# ফাইল ডেলিভারি বাটন ক্লিক হ্যান্ডলার
@Client.on_callback_query(filters.regex(r"^file_"))
async def send_file(client: Client, callback_query):
    file_db_id = callback_query.data.split("_")[1]
    file_data = await get_file_by_db_id(file_db_id)
    
    if file_data:
        try:
            file_name = file_data["file_name"]
            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
            caption_text = (
                f"🎬 **ফাইলের নাম:** `{file_name}`\n"
                f"💾 **ফাইলের সাইজ:** `{file_size} MB`\n\n"
                f"⚡️ *CTG Movie Bot-এর মাধ্যমে ডাউনলোড করার জন্য ধন্যবাদ!*"
            )
            await client.send_cached_media(
                chat_id=callback_query.message.chat.id,
                file_id=file_data["file_id"],
                caption=caption_text
            )
            await callback_query.answer()
        except Exception as e:
            await callback_query.answer(f"সমস্যা: {str(e)}", show_alert=True)
    else:
        await callback_query.answer("ফাইলটি ডাটাবেজে পাওয়া যায়নি!", show_alert=True)
