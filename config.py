# config.py
import os
from pyrogram import filters

# --- বটের প্রধান এপিআই ক্রেডেনশিয়ালস ---
API_ID = 29462738          # আপনার Telegram API ID (integer)
API_HASH = "297f51aaab99720a09e80273628c3c24"  # আপনার Telegram API Hash (string)
BOT_TOKEN = "8970571544:AAHkBPmDzF9crRDbeCq6-Z3RNqDpEe7i9QA"  # BotFather থেকে পাওয়া টোকেন

# --- এডমিন কনফিগারেশন (মাল্টিপল এডমিন সাপোর্ট) ---
ADMINS = [8297458824, 5370676246]  # উদাহরণ: [8297458824, 12345678, 87654321]

# বটের প্রধান মালিক বা প্রথম এডমিন
ADMIN_ID = ADMINS[0] if ADMINS else None

# এডমিনদের জন্য পাইরোগ্রাম কাস্টম ফিল্টার
is_admin = filters.create(lambda _, __, message: message.from_user and message.from_user.id in ADMINS)

# --- চ্যানেল ও ডাটাবেজ আইডি ---
MAIN_CHANNEL_ID = -1002439983925  # প্রধান মুভি চ্যানেল আইডি (ফোর্স সাবস্ক্রিপশন)
LOG_CHANNEL = -1003973741130      # আপনার রিকোয়েস্ট নোটিফিকেশন বা লগ চ্যানেল আইডি

# --- মাল্টিপল ডাটাবেজ কনফিগারেশন (Multi-DB Config) ---

# ১. ইউজার ডাটাবেজ (এখানে ৪র্থ ডাটাবেজের লিঙ্কটি দেওয়া হলো, এটিতে শুধুমাত্র ইউজাররা সেভ হবে, কোনো মুভি ফাইল সেভ হবে না)
USER_DATABASE_URI = "mongodb+srv://hepemo5263:hepemo5263@cluster0.5vugv.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# ২. ফাইল বা মুভি ডাটাবেজগুলোর তালিকা (তালিকা থেকে ৪র্থ ডাটাবেজটি বাদ দেওয়া হলো, যাতে এখানে ভুল করেও কোনো ফাইল সেভ না হয়)
FILE_DATABASE_URIS = [
    "mongodb+srv://hahema9427:hahema9427@cluster0.3mf49.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", # ১ম ফাইল ডিবি (রিড-অনলি)
    "mongodb+srv://xanoye1655:xanoye1655@cluster0.toknq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", # ২য় ফাইল ডিবি (নতুন ফাইল সেভ হবে)
    "mongodb+srv://manogog673:manogog673@cluster0.ot1qt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # ৩য় ফাইল ডিবি (নতুন ফাইল সেভ হবে)
]

# ৩. প্রতিটি ফাইল ডাটাবেজের সর্বোচ্চ স্টোরেজ লিমিট (আপনার নির্দেশ অনুযায়ী ৩০০ এমবি সেট করা হয়েছে)
DB_LIMIT_MB = 300

# --- আর্নিং ও মিনি অ্যাপ কনফিগারেশন ---
BOT_USERNAME = "CTGMovieBot"  # বটের ইউজারনেম ( শুরুতে @ দেবেন না)
WEB_URL = "gorgeous-ashla-ctgnahid-3b872c36.koyeb.app"  # Koyeb অ্যাপের লিংক ( শুরুতে https:// দেবেন না)

# আপনার আয়ের ডিরেক্ট অ্যাড লিংকসমূহ (Adsterra এবং OMG10)
DIRECT_AD_LINKS = [
    "https://www.effectivecpmnetwork.com/p4bm30ss3?key=8bb102e9258871570c79a9a90fa3cf9f",
    "https://www.effectivecpmnetwork.com/q5cpmxwy44?key=075b9f116b4174922cadfae2d3291743",
    "https://www.effectivecpmnetwork.com/c90zejmfrg?key=45a67d2f1523ee6b3988c4cc8f764a35",
    "https://www.effectivecpmnetwork.com/a37vi5p8z?key=921db14d454c2b0e780ab51966b651a6",
    "https://www.effectivecpmnetwork.com/m30pd1efbm?key=e7b1df640000086bd44393a929d6ebab",
    "https://www.effectivecpmnetwork.com/jxuaz5zk?key=6faf197d33f98bcb3bc070b020c19664",
    "https://omg10.com/4/10136724",
    "https://omg10.com/4/10395944",
    "https://omg10.com/4/11063339"
]

# --- বাটনগুলোর জন্য নিজস্ব প্রমোショナル ও সোশ্যাল লিংকসমূহ ---
CHANNEL_LINK_1 = "https://t.me/+6hvCoblt6CxhZjhl"       # 🍿 All Movies বাটন লিংক
CHANNEL_LINK_2 = "https://t.me/TGLinkBase"              # 📢 Backup Channel বাটন লিংক

GROUP_LINK = "https://t.me/Movie_Request_Group_23"           # 💬 Movie Group বাটন লিংক
HOW_TO_USE_LINK = "https://t.me/HowtoDowlnoad"             # ❓ How to Use বাটন লিংক
DEVELOPER_LINK = "https://t.me/ProBotDeveloperBot"     # 👨‍💻 Owner & Developer বাটন লিংক

# --- নতুন ভিজ্যুয়াল ডিজাইন কনফিগারেশন ---
START_BANNER = "https://files.catbox.moe/k9xrhs.jpg"
