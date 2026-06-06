# plugins/index.py

from pyrogram import Client, filters
from pyrogram.types import Message
import config
from database import save_file

# ১. অটো-ইনডেক্সিং (শুধুমাত্র আপনার মেইন চ্যানেলে নতুন ফাইল আপলোড হলে স্বয়ংক্রিয়ভাবে সেভ হবে)
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_index(client: Client, message: Message):
    file = message.document or message.video
    await save_file(
        file_name=file.file_name,
        file_size=file.file_size,
        file_id=file.file_id,
        chat_id=message.chat.id,
        message_id=message.id
    )
    print(f"মেইন চ্যানেল থেকে নতুন ফাইল অটো-ইনডেক্স হয়েছে: {file.file_name}")


# ২. ম্যানুয়াল/বাল্ক ইনডেক্সিং (অন্য যেকোনো চ্যানেল থেকে লাস্ট মেসেজ ফরোয়ার্ড করলে পেছনের সব ফাইল ইনডেক্স হবে)
@Client.on_message(filters.forwarded & filters.private)
async def bulk_index(client: Client, message: Message):
    # শুধু বট এডমিনই এই কাজটি করতে পারবে
    if message.from_user.id != config.ADMIN_ID:
        return

    # নিশ্চিত করা যে মেসেজটি কোনো চ্যানেল থেকে ফরোয়ার্ড করা হয়েছে
    if not message.forward_from_chat:
        await message.reply_text("দয়া করে চ্যানেল থেকে একটি মিডিয়া মেসেজ ফরোয়ার্ড করুন।")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id

    status_msg = await message.reply_text("অন্যান্য চ্যানেল থেকে ফাইল ইনডেক্স করা শুরু হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    
    saved_count = 0
    # শেষ মেসেজ আইডি থেকে শুরু করে পেছনের ১০০০টি মেসেজ স্ক্যান করবে
    async for msg in client.get_chat_history(chat_id, offset_id=last_msg_id + 1, limit=1000):
        if msg.document or msg.video:
            file = msg.document or msg.video
            saved = await save_file(
                file_name=file.file_name,
                file_size=file.file_size,
                file_id=file.file_id,
                chat_id=chat_id,
                message_id=msg.id
            )
            if saved:
                saved_count += 1

    await status_msg.edit_text(
        f"ইনডেক্স সম্পন্ন হয়েছে!\n"
        f"উক্ত চ্যানেল থেকে মোট {saved_count} টি নতুন ফাইল ডাটাবেজে যুক্ত করা হয়েছে।"
    )
