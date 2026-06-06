# plugins/admin.py

from pyrogram import Client, filters
from pyrogram.types import Message
import config
from database import get_stats, delete_files_by_name, delete_all_files_from_db

# এডমিন ফিল্টার (শুধুমাত্র কনফিগে থাকা এডমিন আইডি অনুমতি পাবে)
is_admin = filters.user(config.ADMIN_ID)

# ১. লাইভ স্ট্যাটাস দেখার কমান্ড
@Client.on_message(filters.command("stats") & is_admin)
async def stats_cmd(client: Client, message: Message):
    total_files, total_users = await get_stats()
    await message.reply_text(
        f"📊 **বটের লাইভ স্ট্যাটাস:**\n\n"
        f"👥 মোট ইউজার: `{total_users}` জন\n"
        f"📁 মোট মুভি ফাইল: `{total_files}` টি"
    )

# ২. নাম দিয়ে মুভি ডিলিট করার কমান্ড
# ব্যবহার বিধি: /delete RRR (RRR নামের সব ফাইল ডিলিট হবে)
@Client.on_message(filters.command("delete") & is_admin)
async def delete_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ **সঠিক নিয়ম:** `/delete [মুভির নাম]` লিখে পাঠান।")
        return
        
    query = " ".join(message.command[1:])
    deleted_count = await delete_files_by_name(query)
    
    await message.reply_text(f"✅ ডাটাবেজ থেকে **'{query}'** নামের মোট `{deleted_count}` টি ফাইল ডিলিট করা হয়েছে।")

# ৩. সম্পূর্ণ ডাটাবেজ ডিলিট (অল ডিলিট) করার কমান্ড
# ব্যবহার বিধি: /clean_database
@Client.on_message(filters.command("clean_database") & is_admin)
async def clean_database_cmd(client: Client, message: Message):
    deleted_count = await delete_all_files_from_db()
    await message.reply_text(f"🛑 **ডাটাবেজ সম্পূর্ণ খালি করা হয়েছে!**\nমোট `{deleted_count}` টি ফাইল স্থায়ীভাবে মুছে ফেলা হয়েছে।")
