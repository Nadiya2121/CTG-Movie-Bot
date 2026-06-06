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
            f"❌ দুঃখিত, **'{query}'** নামের কোনো মুভি আমাদের ডাটাবেজে পাওয়া যায়নি।"
        )
        return

    buttons = []
    for file in results:
        file_name = file["file_name"]
        file_size = round(file["file_size"] / (1024 * 1024), 2)
        db_id = str(file["_id"])
        buttons.append([InlineKeyboardButton(f"🎬 {file_name} [{file_size} MB]", callback_data=f"file_{db_id}")])

    await search_msg.delete()
    await message.reply_text(
        f"🍿 **'{query}'** এর ফলাফল নিচে দেওয়া হলো:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# বাটন ক্লিক করলে ক্যাপশন সহ ফাইল যাবে
@Client.on_callback_query(filters.regex(r"^file_"))
async def send_file(client: Client, callback_query):
    file_db_id = callback_query.data.split("_")[1]
    file_data = await get_file_by_db_id(file_db_id)
    
    if file_data:
        try:
            file_name = file_data["file_name"]
            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
            
            # ফাইলের সাথে সুন্দর ক্যাপশন যুক্ত করা হলো
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
