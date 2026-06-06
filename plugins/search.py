# plugins/search.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from database import search_db, get_file_by_db_id

@Client.on_message(filters.text & filters.private)
async def search_handler(client: Client, message: Message):
    if message.text.startswith("/"):
        return

    query = message.text
    search_msg = await message.reply_text("🔍 আপনার ফাইলটি খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    
    results = await search_db(query)
    
    if not results:
        await search_msg.edit_text(
            f"❌ দুঃখিত, **'{query}'** নামের কোনো মুভি বা ফাইল আমাদের ডাটাবেজে পাওয়া যায়নি।\n\n"
            f"💡 *টিপস:* বানানটি পুনরায় চেক করুন অথবা শুধুমাত্র মুভির মূল নামটি লিখে সার্চ করুন।"
        )
        return

    buttons = []
    for file in results:
        file_name = file["file_name"]
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        
        # বাটন ফরম্যাট
        buttons.append([InlineKeyboardButton(f"🎬 {file_name} [{file_size} MB]", callback_data=f"file_{db_id}")])

    await search_msg.delete()
    await message.reply_text(
        f"🍿 **'{query}'** এর জন্য প্রাপ্ত ফলাফলসমূহ:\n*(নিচের বাটনে ক্লিক করে ফাইলটি ডাউনলোড করুন)*",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# বাটন ক্লিক হ্যান্ডলার (এখানেই এররটি ফিক্স করা হয়েছে)
@Client.on_callback_query(filters.regex(r"^file_"))
async def send_file(client: Client, callback_query):
    file_db_id = callback_query.data.split("_")[1]
    file_data = await get_file_by_db_id(file_db_id)
    
    if file_data:
        try:
            # send_cached_media ব্যবহারের ফলে ভিডিও বা ডকুমেন্ট যেকোনো ফাইল স্বয়ংক্রিয়ভাবে চলে যাবে
            await client.send_cached_media(
                chat_id=callback_query.message.chat.id,
                file_id=file_data["file_id"]
            )
            await callback_query.answer()
        except Exception as e:
            await callback_query.answer(f"ফাইল পাঠাতে ব্যর্থ হয়েছে: {str(e)}", show_alert=True)
    else:
        await callback_query.answer("দুঃখিত, ফাইলটি আমাদের সার্ভারে খুঁজে পাওয়া যায়নি!", show_alert=True)
