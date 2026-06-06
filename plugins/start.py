from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        f"হ্যালো {message.from_user.first_name}!\n\n"
        "আমি মুভি সার্চ বট। আপনার কাঙ্ক্ষিত মুভি বা সিরিজের নামটি লিখে মেসেজ পাঠান, আমি খুঁজে দেব।"
    )
