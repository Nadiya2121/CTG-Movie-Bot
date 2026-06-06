from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from database import search_db

@Client.on_message(filters.text & filters.private)
async def search_handler(client: Client, message: Message):
    # ইউজার যদি কোনো কমান্ড (যেমন /start) দেয়, তবে সার্চ করবে না
    if message.text.startswith("/"):
        return

    query = message.text
    search_msg = await message.reply_text("খোঁজা হচ্ছে... দয়া করে অপেক্ষা করুন।")
    
    results = await search_db(query)
    
    if not results:
        await search_msg.edit_text("দুঃখিত, এই নামের কোনো মুভি বা ফাইল খুঁজে পাওয়া যায়নি। বানানটি চেক করে আবার চেষ্টা করুন।")
        return

    # রেজাল্ট সাজানো (ইউজারদের জন্য বাটন আকারে রেজাল্ট দেখাবে)
    buttons = []
    for file in results:
        file_name = file["file_name"]
        file_size = round(file["file_size"] / (1024 * 1024), 2) # MB তে কনভার্ট করা
        
        # প্রতিটি ফাইলের জন্য একটি ডাউনলোড বাটন তৈরি করা
        # এখানে মেসেজ লিঙ্ক বা ফাইল আইডি ব্যবহার করে ফাইল পাঠানো যাবে
        # সহজে ফাইল ডাউনলোড করার জন্য ফাইল আইডি বা চ্যানেলের মেসেজ লিংক ব্যবহার করা হয়েছে
        # এখানে আমরা ফাইল সরাসরি পাঠানোর সুবিধা রাখছি
        buttons.append([InlineKeyboardButton(f"🎬 {file_name} ({file_size} MB)", callback_data=f"file_{file['file_id']}")])

    await search_msg.delete()
    await message.reply_text(
        f"🔍 '{query}' এর জন্য প্রাপ্ত ফলাফলসমূহ:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# বাটন ক্লিক করলে ফাইল পাঠানোর হ্যান্ডলার
@Client.on_callback_query(filters.regex(r"^file_"))
async def send_file(client: Client, callback_query):
    file_id = callback_query.data.split("_")[1]
    await callback_query.message.reply_document(file_id)
    await callback_query.answer()
