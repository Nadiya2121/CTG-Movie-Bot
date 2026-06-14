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
    get_all_premium_users,
    migrate_existing_fancy_fonts  # নতুন মাইগ্রেশন ফাংশনটি ইম্পোর্ট করা হলো
)

# বটের আপটাইম হিসাব করার জন্য স্টার্ট টাইম রেকর্ড করা হলো
START_TIME = time.time()

# আপটাইম বা সময় ফরম্যাট করার প্রফেশনাল ফাংশন
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

# প্রফেশনাল লাইভ স্ট্যাটাস স্ক্রিন (মূল ড্যাশবোর্ড - সামগ্রিক সামারি)
@Client.on_message(filters.command("stats") & is_admin)
async def stats_cmd(client: Client, message: Message):
    # ডাটাবেজ থেকে ডিটেইলড ডাটা সংগ্রহ
    data = await get_detailed_stats()
    
    # সার্ভার মেমোরি ও আপটাইম সংগ্রহ
    uptime = get_readable_time(int(time.time() - START_TIME))
    ram_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent()
    
    stats_text = (
        f"╭────[ 📊 ⲝʏⲝᴛⲝᴍ sᴛᴀᴛᴜs 📊 ] ────⍟\n"
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


# সম্পূর্ণ নতুন ডেডিকেটেড কমান্ড: /db (প্রতিটি ডাটাবেজের লাইভ ডিটেইলস আলাদাভাবে দেখার জন্য)
@Client.on_message(filters.command("db") & is_admin)
async def db_stats_cmd(client: Client, message: Message):
    # ডাটাবেজ থেকে ডিটেইলড ডাটা সংগ্রহ
    data = await get_detailed_stats()
    
    # ডায়নামিকভাবে প্রতিটি ডাটাবেজের স্ট্যাটাস ব্লক তৈরি করা হচ্ছে
    db_section = ""
    for db_info in data.get("file_dbs_info", []):
        # যদি ইউজার ডাটাবেজ আলাদা থাকে তবে স্পেশাল হেডার দেখাবে
        if db_info['db_num'] == "USER_DEDICATED":
            db_title = "👑 ᴜsᴇʀ ᴅᴀᴛᴀʙᴀsᴇ 👑"
            files_label = "ᴛᴏᴛᴀʟ ᴜsᴇʀs"
        else:
            db_title = f"🗃 ᴅᴀᴛᴀʙᴀsᴇ {db_info['db_num']} 🗃"
            files_label = "ᴀʟʟ ғɪʟᴇs"
            
        db_section += (
            f"├────[ {db_title} ]────⍟\n"
            f"│  ├⋟ sᴛᴀᴛᴜs ⋟ `{db_info['status']}`\n"
            f"│  ├⋟ {files_label} ⋟ `{db_info['files_count']}`\n"
            f"│  ├⋟ ᴜsᴇᴅ ⋟ `{db_info['used_mb']} MB`\n"
            f"│  └⋟ ғʀᴇᴇ ⋟ `{db_info['free_mb']} MB` (Limit: {db_info['limit']}MB)\n"
            f"│\n"
        )
    
    db_stats_text = (
        f"╭────[ 🗄 ᴍᴜʟᴛɪ-ᴅʙ sᴛᴀᴛᴜs 🗄 ]────⍟\n"
        f"│\n"
        f"{db_section}"
        f"╰─────────────────────⍟"
    )
    
    await message.reply_text(db_stats_text)


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


# --- নতুন ডাটাবেজ ফন্ট মাইগ্রেশন কমান্ড ---
@Client.on_message(filters.command("migrate") & is_admin & filters.private)
async def migrate_db_cmd(client: Client, message: Message):
    status_msg = await message.reply_text("⏳ ডাটাবেজের পুরোনো ফ্যান্সি ফন্টগুলো সাধারণ ফন্টে রূপান্তর (Normalize) করা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    start_time = time.time()
    try:
        updated_count = await migrate_existing_fancy_fonts()
        elapsed = get_readable_time(int(time.time() - start_time))
        await status_msg.edit_text(
            f"🎉 **মাইগ্রেশন সফলভাবে সম্পন্ন হয়েছে (Turbo Finish)!**\n\n"
            f"📊 **রিপোর্ট:**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ মোট রূপান্তরিত মুভি: `{updated_count}` টি\n"
            f"⏱ মোট সময় লেগেছে: `{elapsed}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 এখন পূর্বের সমস্ত মুভি সাধারণ ফন্টেই সার্চে পাওয়া যাবে।"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ মাইগ্রেশন ব্যর্থ হয়েছে! ভুল: `{e}`")


# --- প্রগতিশীল ব্রডকাস্টার (Progressive Broadcaster with Live Progress Bar) ---
@Client.on_message(filters.command("broadcast") & is_admin)
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("⚠️ **ব্যবহার বিধি:** যেকোনো মেসেজ বা পোস্টের ওপর রিপ্লাই দিয়ে লিখুন `/broadcast`")
        return
        
    status_msg = await message.reply_text("📢 ব্রডকাস্ট শুরুর জন্য ইউজার তালিকা লোড হচ্ছে...")
    users = await get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        await status_msg.edit_text("❌ ডাটাবেজে কোনো ইউজার খুঁজে পাওয়া যায়নি!")
        return
        
    await status_msg.edit_text(f"📢 ব্রডকাস্ট শুরু হচ্ছে... মোট ইউজার: `{total_users}` জন।")
    
    success = 0
    failed = 0
    scanned = 0
    start_time = time.time()
    last_edit_time = time.time()
    
    for user_id in users:
        try:
            await message.reply_to_message.copy(chat_id=user_id)
            success += 1
        except Exception:
            failed += 1
        
        scanned += 1
        
        # প্রতি ৫ সেকেন্ড পর পর লাইভ প্রোগ্রেস মেসেজ এডিট হবে (টেলিগ্রাম ফ্লুড লিমিট এড়াতে)
        current_time = time.time()
        if current_time - last_edit_time >= 5 or scanned == total_users:
            percent = round((scanned / total_users) * 100, 1)
            # ১০ ব্লকের প্রোগ্রেস বার
            filled_blocks = int(percent // 10)
            bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
            
            # ETA (Estimated Time of Arrival) বা আনুমানিক বাকি সময় হিসাব
            elapsed_time = current_time - start_time
            avg_time = elapsed_time / scanned if scanned > 0 else 0.3
            eta_sec = int((total_users - scanned) * avg_time)
            eta_str = get_readable_time(eta_sec) if eta_sec > 0 else "0s"
            
            progress_text = (
                f"📢 **ব্রডকাস্ট চলমান রয়েছে...**\n\n"
                f"📈 **অগ্রগতি:** `{percent}%` Completed\n"
                f"⚙️ `[{bar}]`\n\n"
                f"👥 মোট ইউজার: `{total_users}` জন\n"
                f"🔎 স্ক্যানড: `{scanned}`\n"
                f"✅ সফল: `{success}`\n"
                f"❌ ব্যর্থ: `{failed}`\n\n"
                f"⏱ আনুমানিক বাকি সময়: `{eta_str}`"
            )
            
            try:
                await status_msg.edit_text(progress_text)
                last_edit_time = current_time
            except Exception:
                pass
        
        # টেলিগ্রাম এপিআই রেট লিমিট প্রটেকশন
        await asyncio.sleep(0.3)
        
    # চূড়ান্ত বা ফাইনাল রিপোর্ট
    total_time = get_readable_time(int(time.time() - start_time))
    final_text = (
        f"📢 **ব্রডকাস্ট সফলভাবে সম্পন্ন হয়েছে (Turbo Broadcast Finish)!**\n\n"
        f"📊 **চূড়ান্ত রিপোর্ট:**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 মোট ইউজার: `{total_users}` জন\n"
        f"✅ সফলভাবে পাঠানো হয়েছে: `{success}` জনকে\n"
        f"❌ ব্যর্থ হয়েছে (বট ব্লকড): `{failed}` জনের কাছে\n"
        f"⏱ মোট সময় লেগেছে: `{total_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await status_msg.edit_text(final_text)

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
