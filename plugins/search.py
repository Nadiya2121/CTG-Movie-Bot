# plugins/search.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from database import search_db, get_file_by_db_id  # নতুন ফাংশন ইম্পোর্ট করা হয়েছে

@Client.on_message(filters.text & filters.private)
async def search_handler(client: Client, message: Message):
    if message.text.startswith("/"):
        return

    query = message.text
    search_msg = await message.reply_text("খোঁজা হচ্ছে... দয়া করে অপেক্ষা করুন।")
    
    results = await search_db(query)
    
    if not results:
        await search_msg.edit_text("দুঃখিত, এই নামের কোনো মুভি বা ফাইল খুঁজে পাওয়া যায়নি।")
        return

    buttons = []
    for file in results:
        file_name = file["file_name"]
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        
        # এখানে মঙ্গোডিবির ছোট ইউনিক আইডিটি (যা মাত্র ২৪ অক্ষরের) বাটনে পাঠানো হচ্ছে
        db_id = str(file["_id"])
        buttons.append([InlineKeyboardButton(f"🎬 {file_name} ({file_size} MB)", callback_data=f"file_{db_id}")])

    await search_msg.delete()
    await message.reply_text(
        f"🔍 '{query}' এর জন্য প্রাপ্ত ফলাফলসমূহ:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# বাটন ক্লিক হ্যান্ডলার
@Client.on_callback_query(filters.regex(r"^file_"))
async def send_file(client: Client, callback_query):
    # বাটন থেকে ডাটাবেজ আইডি আলাদা করা
    file_db_id = callback_query.data.split("_")[1]
    
    # ডাটাবেজ থেকে আসল ফাইল ডাটা এবং ফাইল আইডি উদ্ধার করা
    file_data = await get_file_by_db_id(file_db_id)
    
    if file_data:
        try:
            # আসল ফাইল আইডি দিয়ে ইউজারকে মুভি পাঠানো হচ্ছে
            await callback_query.message.reply_document(file_data["file_id"])
            await callback_query.answer()
        except Exception as e:
            await callback_query.answer(f"ফাইল পাঠাতে সমস্যা হচ্ছে: {str(e)}", show_alert=True)
    else:
        await callback_query.answer("দুঃখিত, এই ফাইলটি ডাটাবেজে পাওয়া যায়নি!", show_alert=True)
