# plugins/admin.py

import asyncio
import time
import psutil  # লাইভ র‌্যাম এবং সিপিইউ রিড করার জন্য
from pyrogram import Client, filters
from pyrogram.types import Message
import config
from database import (
    get_detailed_stats, 
    delete_files_by_name, 
    delete_all_files_from_db, 
    get_all_users,
    add_premium_user,
    remove_premium_user,
    get_all_premium_users
)

# বটের আপটাইম হিসাব করার জন্য স্টার্ট টাইম রেকর্ড করা হলো
START_TIME = time.time()

# আপটাইম ফরম্যাট করার প্রফেশনাল ফাংশন
def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "d"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list[3] + " " + time_list[2] + " " + time_list[1] + " " + time_list[0]
    elif len(time_list) == 3:
        ping_time += time_list[2] + " " + time_list[1] + " " + time_list[0]
    elif len(time_list) == 2:
        ping_time += time_list[1] + " " + time_list[0]
    elif len(time_list) == 1:
        ping_time += time_list[0]
    else:
        ping_time = "0s"
    return ping_time

# মাল্টিপল এডমিন ফিল্টার
is_admin = filters.create(lambda _, __, message: message.from_user and message.from_user.id in config.ADMINS)

# প্রফেশনাল লাইভ স্ট্যাটাস স্ক্রিন (আপনার নতুন ডিজাইন ও রিকোয়ারমেন্টের সমন্বয়ে)
@Client.on_message(filters.command("stats") & is_admin)
async def stats_cmd(client: Client, message: Message):
    # ডাটাবেজ থেকে ডিটেইলড ডাটা সংগ্রহ
    data = await get_detailed_stats()
    
    # সার্ভার মেমোরি ও আপটাইম সংগ্রহ
    uptime = get_readable_time(int(time.time() - START_TIME))
    ram_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent()
    
    stats_text = (
        f"╭────[ 📊 ꜱʏꜱᴛᴇᴍ sᴛᴀᴛᴜs 📊 ] ────⍟\n"
        f"│\n"
        f"├ ★ 𝚃𝙾𝚃𝙰𝙻 𝙵𝙸𝙻𝙴𝚂: `{data['total_files']}`\n"
        f"├ ★ 𝚃𝙾𝚃𝙰𝙻 𝚄𝚂𝙴𝚁𝚂: `{data['total_users']}`\n"
        f"├ ★ 𝚃𝙾𝚃𝙰𝙻 𝙲𝙷𝙰𝚃𝚂: `{data['total_groups']}`\n"
        f"├ ★ 𝙿𝚁𝙴𝙼𝙸𝚄𝙼 𝚄𝚂𝙴𝚁𝚂: `{data['premium_users']}`\n"
        f"├ ★ 𝚄𝚂𝙴𝙳 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: `{data['used_storage']}`\n"
        f"├ ★ 𝙵𝚁𝙴𝙴 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: `{data['free_storage']}`\n"
        f"│\n"
        f"├────[ ⚙️ sᴇʀᴠᴇʀ sᴘᴇᴄs ⚙️ ]────⍟\n"
        f"│\n"
        f"├⋟ ᴜᴘᴛɪᴍᴇ ⋟ `{uptime}`\n"
        f"├⋟ ʀᴀᴍ ⋟ `{ram_usage}%`\n"
        f"├⋟ ᴄᴘᴜ ⋟ `{cpu_usage}%`\n"
        f"│\n"
        f"╰─────────────────────⍟"
    )
    
    await message.reply_text(stats_text)

@Client.on_message(filters.command("delete") & is_admin)
async def delete_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ **সঠিক নিয়ম:** `/delete [মুভির নাম]` লিখে পাঠান।")
        return
    query = " ".join(message.command[1:])
    deleted_count = await delete_files_by_name(query)
    await message.reply_text(f"✅ ডাটাবেজ থেকে **'{query}'** নামের মোট `{deleted_count}` টি ফাইল ডিলিট করা হয়েছে।")

@Client.on_message(filters.command("clean_database") & is_admin)
async def clean_database_cmd(client: Client, message: Message):
    deleted_count = await delete_all_files_from_db()
    await message.reply_text(f"🛑 **ডাটাবেজ সম্পূর্ণ খালি করা হয়েছে!**\nমোট `{deleted_count}` টি ফাইল স্থায়ীভাবে মুছে ফেলা হয়েছে।")

@Client.on_message(filters.command("broadcast") & is_admin)
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("⚠️ **ব্যবহার বিধি:** যেকোনো মেসেজ বা পোস্টের ওপর রিপ্লাই দিয়ে লিখুন `/broadcast`")
        return
    status_msg = await message.reply_text("📢 ব্রডকাস্ট শুরু হচ্ছে...")
    users = await get_all_users()
    success = 0
    failed = 0
    for user_id in users:
        try:
            await message.reply_to_message.copy(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"📢 **ব্রডকাস্ট সফলভাবে সম্পন্ন হয়েছে!**\n\n"
        f"✅ সফলভাবে পাঠানো হয়েছে: `{success}` জন ইউজারকে\n"
        f"❌ ব্যর্থ হয়েছে (বট ব্লক করেছে): `{failed}` জন ইউজার"
    )

# --- প্রিমিয়াম নিয়ন্ত্রণ কমান্ডসমূহ ---
@Client.on_message(filters.command("add_premium") & is_admin)
async def add_premium_cmd(client: Client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("⚠️ **ব্যবহার বিধি:** `/add_premium [User_ID]` অথবা যেকোনো ইউজারের মেসেজে রিপ্লাই দিয়ে লিখুন `/add_premium`")
        return
    
    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        try:
            user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("⚠️ **ভুল আইডি!** দয়া করে সঠিক সংখ্যাসূচক ইউজার আইডি দিন।")
            return
    
    await add_premium_user(user_id)
    await message.reply_text(f"👑 **সফল হয়েছে!**\nইউজার আইডি `{user_id}` কে সফলভাবে প্রিমিয়াম (VIP) মেম্বার হিসেবে যুক্ত করা হয়েছে।")

@Client.on_message(filters.command("remove_premium") & is_admin)
async def remove_premium_cmd(client: Client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("⚠️ **ব্যবহার বিধি:** `/remove_premium [User_ID]` অথবা যেকোনো ইউজারের মেসেজে রিপ্লাই দিয়ে লিখুন `/remove_premium`")
        return
    
    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        try:
            user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("⚠️ **ভুল আইডি!** দয়া করে সঠিক সংখ্যাসূচক ইউজার আইডি দিন।")
            return
    
    await remove_premium_user(user_id)
    await message.reply_text(f"❌ **রিমুভ করা হয়েছে!**\nইউজার আইডি `{user_id}` কে সফলভাবে প্রিমিয়াম মেম্বারশিপ থেকে বাদ দেওয়া হয়েছে।")

@Client.on_message(filters.command("premiums") & is_admin)
async def premiums_list_cmd(client: Client, message: Message):
    premium_users = await get_all_premium_users()
    if not premium_users:
        await message.reply_text("ℹ️ বর্তমানে ডাটাবেজে কোনো প্রিমিয়াম ইউজার যুক্ত নেই।")
        return
    
    text = "👑 **প্রিমিয়াম (VIP) ইউজারদের তালিকা:**\n\n"
    for idx, u_id in enumerate(premium_users, 1):
        text += f"{idx}. `{u_id}`\n"
    await message.reply_text(text)
