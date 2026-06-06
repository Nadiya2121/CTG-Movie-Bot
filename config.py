# config.py

API_ID = 29462738          # আপনার Telegram API ID (integer)
API_HASH = "297f51aaab99720a09e80273628c3c24"  # আপনার Telegram API Hash (string)
BOT_TOKEN = "8970571544:AAHkBPmDzF9crRDbeCq6-Z3RNqDpEe7i9QA"  # BotFather থেকে পাওয়া টোকেন
ADMIN_ID = 8297458824      # আপনার নিজের টেলিগ্রাম ইউজার আইডি
MAIN_CHANNEL_ID = -1003973741130  # আপনার প্রধান চ্যানেলের আইডি

# --- ডাবল ডাটাবেজ কনফিগারেশন ---
DATABASE_URI = "mongodb+srv://hahema9427:hahema9427@cluster0.3mf49.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # আপনার ১ম (Primary) MongoDB লিঙ্ক
MULTIPLE_DB = False                 # ২য় ডাটাবেজ সচল করতে True রাখুন, না চাইলে False
DATABASE_URI2 = "mongodb+srv://..." # আপনার ২য় (Backup) MongoDB লিঙ্ক (ঐচ্ছিক)


# ==========================================
# --- আর্নিং ও মিনি অ্যাপ কনফিগারেশন (নতুন) ---
# ==========================================

# আপনার বটের ইউজারনেম (BotFather থেকে পাওয়া বটের ইউজারনেমটি এখানে বসান, শুরুতে @ দেবেন না)
BOT_USERNAME = "CTGMovieBot"  

# Render থেকে পাওয়া আপনার অ্যাপের লিংক (এখানে Render-এর Default Subdomain-টি বসাবেন, শুরুতে https:// বা শেষে / দেবেন না)
# উদাহরণ: "ctg-movie-bot.onrender.com"
WEB_URL = "https://gorgeous-donetta-nahidcrk-7b84dba9.koyeb.app/view/CTG-Movie-Bot"  

# আপনার আয়ের ডিরেক্ট অ্যাড লিংক (এখানে Adsterra বা অন্য যেকোনো কোম্পানির ডিরেক্ট অ্যাড লিংক বসিয়ে দিন)
DIRECT_AD_LINKS = [
    "https://www.effectivecpmnetwork.com/m30pd1efbm?key=e7b1df640000086bd44393a929d6ebab",
    "https://www.effectivecpmnetwork.com/jxuaz5zk?key=6faf197d33f98bcb3bc070b020c19664"
]
