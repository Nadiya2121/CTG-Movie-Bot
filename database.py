# database.py

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import config
import re
import difflib

# ==========================================
#  ১. ডাটাবেজ কানেকশন এবং আইসোলেশন
# ==========================================

# ইউজার ডাটাবেজ কানেকশন (ইউজার, গ্রুপ ও রিকোয়েস্টের জন্য ডেডিকেটেড)
user_client = AsyncIOMotorClient(config.USER_DATABASE_URI)
user_db = user_client["movie_search_bot"]
users_col = user_db["users"]
groups_col = user_db["groups"]
requests_col = user_db["requests"]

# ফাইল বা মুভি ডাটাবেজগুলোর জন্য ডায়নামিক কানেকশন তৈরি
file_clients = []
file_dbs = []
file_cols = []

for uri in config.FILE_DATABASE_URIS:
    try:
        client = AsyncIOMotorClient(uri)
        db = client["movie_search_bot"]
        file_clients.append(client)
        file_dbs.append(db)
        file_cols.append(db["files"])
    except Exception as e:
        print(f"❌ ডাটাবেজ কানেকশন তৈরি করতে ব্যর্থ: {uri} | ভুল: {e}")

# রিয়েল-টাইম মেমোরি ট্র্যাকার এবং আকস্মিক রাইট ব্লক ট্র্যাকার
DB_SIZES_CACHE = {}
BLOCKED_DBS = set()

# ==========================================
#  ২. ডায়নামিক অটো-সুইচিং লজিক (রিয়েল-টাইম কাউন্টার)
# ==========================================

async def get_active_files_collection():
    """
    ফাইল ডাটাবেজগুলোর সাইজ চেক করে প্রথম যে ডাটাবেজটি ৪০০ এমবি (কনফিগ লিমিট) এর নিচে আছে,
    সেটির কালেকশন রিটার্ন করবে। ১ম ফাইল ডাটাবেজটি (Index 0) নতুন ফাইল সেভের ক্ষেত্রে সম্পূর্ণ স্কিপ করা হবে।
    """
    if not file_cols or len(file_cols) < 2:
        return None if not file_cols else file_cols[0]

    # [সংশোধন]: ১ম ফাইল ডাটাবেজ (Index 0) সম্পূর্ণ স্কিপ করা হচ্ছে এবং ২য় ডাটাবেজ (Index 1) থেকে শুরু করা হচ্ছে
    for idx in range(1, len(file_dbs)):
        if idx in BLOCKED_DBS:
            continue
            
        # যদি মেমোরিতে এই ডাটাবেজের সাইজ আগে থেকে লোড করা না থাকে, তবে একবার dbstats দিয়ে রিড করা হবে
        if idx not in DB_SIZES_CACHE:
            try:
                db = file_dbs[idx]
                stats = await db.command("dbstats")
                used_bytes = stats.get("storageSize", 0) + stats.get("indexSize", 0)
                used_mb = used_bytes / (1024 * 1024)
                DB_SIZES_CACHE[idx] = used_mb
            except Exception as e:
                print(f"⚠️ ডাটাবেজ {idx+1} সাইজ চেক করতে ব্যর্থ: {e}")
                DB_SIZES_CACHE[idx] = 0.0  # কোনো কারণে এরর আসলে ব্যাকআপ হিসেবে ০ ধরা হলো
        
        # মেমোরিতে থাকা রিয়েল-টাইম সাইজ চেক করা হচ্ছে
        if DB_SIZES_CACHE[idx] < config.DB_LIMIT_MB:
            return file_cols[idx]
            
    # যদি ২য়, ৩য় ও ৪র্থ সব পূর্ণ হয়ে যায়, তবে ব্লকড বাদে প্রথম সচল ডাটাবেজটি নেওয়া হবে (অবশ্যই ২য় থেকে শুরু)
    available_indices = [i for i in range(1, len(file_cols)) if i not in BLOCKED_DBS]
    if available_indices:
        return file_cols[available_indices[0]]
        
    return file_cols[1] # ২য় ফাইল ডাটাবেজ (Index 1)

# ==========================================
#  ৩. ইউজার ও গ্রুপ ম্যানেজমেন্ট (Dedicated DB)
# ==========================================

async def add_user(user_id, username, first_name):
    username = username if username else "No Username"
    first_name = first_name if first_name else "User"
    exists = await users_col.find_one({"user_id": user_id})
    if not exists:
        await users_col.insert_one({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "is_premium": False
        })

async def add_group(chat_id, chat_title):
    exists = await groups_col.find_one({"chat_id": chat_id})
    if not exists:
        await groups_col.insert_one({
            "chat_id": chat_id,
            "chat_title": chat_title if chat_title else "Group"
        })

# ==========================================
#  ৪. ফাইল ইনডেক্সিং এবং ডুপ্লিকেট প্রটেকশন (রিয়েল-টাইম ফেইলওভার)
# ==========================================

async def save_file(file_name, file_size, file_id, chat_id, message_id):
    active_col = await get_active_files_collection()
    
    if active_col is None:
        return False
    
    file_name = file_name if file_name else f"Video_File_{file_size}"
    
    # ডুপ্লিকেট প্রতিরোধের জন্য সব ফাইল ডাটাবেজে ফাইলটি ইতিমধ্যে আছে কিনা চেক করা হচ্ছে (DB1 সহ সার্চ হবে)
    duplicate = False
    for col in file_cols:
        exists = await col.find_one({
            "$or": [
                {"file_id": file_id},
                {"file_name": file_name, "file_size": file_size}
            ]
        })
        if exists:
            duplicate = True
            break
    
    # ডুপ্লিকেট না থাকলে সচল ডাটাবেজে সেভ করা হবে
    if not duplicate:
        file_data = {
            "file_name": file_name,
            "file_size": file_size,
            "file_id": file_id,
            "chat_id": chat_id,
            "message_id": message_id
        }
        
        # বর্তমান কোন কালেকশনে সেভ করার সিদ্ধান্ত নেওয়া হয়েছে তার ইনডেক্স (অবশ্যই ১ বা তার বেশি হতে হবে)
        start_idx = file_cols.index(active_col) if active_col in file_cols else 1
        if start_idx == 0:
            start_idx = 1
        
        # রাউন্ড-রবিন সিকোয়েন্সে ট্রাই করার ব্যবস্থা (১ম ডাটাবেজ তথা Index 0 সম্পূর্ণ স্কিপড)
        db_sequence = list(range(start_idx, len(file_cols))) + list(range(1, start_idx))
        if not db_sequence:
            db_sequence = [1]
        
        for idx in db_sequence:
            col = file_cols[idx]
            try:
                result = await col.insert_one(file_data)
                
                # সফলভাবে সেভ হলে বটের ইন-মেমোরি কাউন্টারে সাইজ ০.০১ এমবি বাড়িয়ে নেওয়া হচ্ছে
                if idx in DB_SIZES_CACHE:
                    DB_SIZES_CACHE[idx] += 0.01
                    
                return str(result.inserted_id)
            except Exception as e:
                err_msg = str(e)
                # হঠাৎ কোটা লক এরর আসলে এটিকে এড়িয়ে গিয়ে পরবর্তী ডাটাবেজে চেষ্টা করা হবে
                if "quota" in err_msg.lower() or "blocked" in err_msg.lower() or "8000" in err_msg:
                    print(f"⚠️ ডাটাবেজ {idx+1} রাইট লকড হয়েছে! এটিকে ব্লকড তালিকায় রাখা হলো এবং পরবর্তী ডাটাবেজে ট্রাই করা হচ্ছে।")
                    BLOCKED_DBS.add(idx)
                    continue
                else:
                    print(f"❌ ডাটাবেজ {idx+1}-এ রাইট এরর: {e}")
                    return False
        
    return False

# ==========================================
#  ৫.  মাল্টি-ডিবি সার্চ এবং সর্টিং ইঞ্জিন
# ==========================================

async def search_db(query):
    clean_q = query.lower().replace(".", " ").replace("_", " ").replace("-", " ")
    words = clean_q.strip().split()
    if not words:
        return []
    
    regex_list = [{"file_name": {"$regex": re.escape(w), "$options": "i"}} for w in words]
    query_filter = {"$and": regex_list} if len(regex_list) > 1 else regex_list[0]
    
    results = []
    seen_ids = set() # ডুপ্লিকেট এড়ানোর জন্য ইউনিক ফাইল ট্র্যাক করা
    
    # সবগুলো ফাইল ডাটাবেজে সমান্তরালভাবে সার্চ চালানো হচ্ছে (১ম ডাটাবেজের ফাইলও সার্চে আসবে)
    for col in file_cols:
        cursor = col.find(query_filter).limit(30)
        async for doc in cursor:
            if doc['file_id'] not in seen_ids:
                results.append(doc)
                seen_ids.add(doc['file_id'])
                if len(results) >= 100:  # নিরাপত্তার জন্য একটি সার্চে সর্বোচ্চ ১০০ ফাইল লোড হবে
                    break
        if len(results) >= 100:
            break
                
    # রিয়েল-টাইম সর্টিং (ইউজারের খোঁজা নামের সাথে সবচেয়ে মিল থাকা ফাইলটি আগে দেখাবে)
    def get_sort_key(doc):
        name = doc.get("file_name", "Movie File").lower()
        q = query.lower()
        if q == name:
            return 0
        if name.startswith(q):
            return 1
        ratio = difflib.SequenceMatcher(None, q, name).ratio()
        return 2 - ratio

    results.sort(key=get_sort_key)
    return results[:30] # সেরা ৩০টি রেজাল্ট রিটার্ন করবে

async def get_file_by_db_id(db_id):
    try:
        obj_id = ObjectId(db_id)
        # আইডি দিয়ে সব ফাইল ডাটাবেজে চেক করা হচ্ছে
        for col in file_cols:
            file_data = await col.find_one({"_id": obj_id})
            if file_data:
                return file_data
    except Exception:
        pass
    return None

# ==========================================
#  ৬. মেমরি ও প্রফেশনাল স্ট্যাটাস মেকানিজম (অপ্টিমাইজড)
# ==========================================

async def get_detailed_stats():
    # প্রতিটি ফাইল ডাটাবেজ থেকে আলাদাভাবে ডাটা সংগ্রহ
    file_dbs_info = []
    total_files = 0
    total_used_bytes = 0  # শুরুতে মেমোরি সুরক্ষায় ০ ইনিশিয়ালাইজ করা হলো
    
    for idx, db in enumerate(file_dbs):
        try:
            col = file_cols[idx]
            count = await col.estimated_document_count()
            total_files += count
            
            stats = await db.command("dbstats")
            used_bytes = stats.get("storageSize", 0) + stats.get("indexSize", 0)
            total_used_bytes += used_bytes
            used_mb = used_bytes / (1024 * 1024)
            
            # [উন্নত হিসাব]: ১ম ডাটাবেজের হিসাব আসল ৫১২ এমবি থেকে হবে, এবং বাকিগুলোর হিসাব config.DB_LIMIT_MB লিমিট থেকে হবে
            if idx == 0:
                free_mb = 512.0 - used_mb
                limit_display = 512
                status_str = "👑 USER DEDICATED"
            else:
                free_mb = config.DB_LIMIT_MB - used_mb
                limit_display = config.DB_LIMIT_MB
                status_str = "🟢 ACTIVE" if used_mb < config.DB_LIMIT_MB else "🔴 FULL"
                if idx in BLOCKED_DBS:
                    status_str = "🔴 BLOCKED"
            
            if free_mb < 0:
                free_mb = 0.0
            
            file_dbs_info.append({
                "db_num": idx + 1,
                "files_count": count,
                "used_mb": round(used_mb, 2),
                "free_mb": round(free_mb, 2),
                "limit": limit_display,
                "status": status_str
            })
        except Exception as e:
            file_dbs_info.append({
                "db_num": idx + 1,
                "files_count": 0,
                "used_mb": 0.0,
                "free_mb": 0.0,
                "limit": config.DB_LIMIT_MB,
                "status": "❌ OFFLINE"
            })
        
    total_users = 0
    premium_users = 0
    total_groups = 0
    try:
        # [সংশোধন]: ইউজার এবং গ্রুপ সংখ্যা মেটাডাটার বদলে সরাসরি লাইভ গোনা হবে (১০০% রিয়েল-টাইম)
        total_users = await users_col.count_documents({})
        premium_users = await users_col.count_documents({"is_premium": True})
        total_groups = await groups_col.count_documents({})
        
        # ইউজার ডাটাবেজের মেমোরি হিসাব
        u_stats = await user_db.command("dbstats")
        total_used_bytes += u_stats.get("storageSize", 0) + u_stats.get("indexSize", 0)
    except Exception as e:
        pass  # total_used_bytes অলরেডি ডিক্লেয়ার করা আছে, কোনো সমস্যা হবে না
        
    # সামগ্রিক স্টোরেজ হিসাব (জিবি/এমবি)
    total_used_mb = total_used_bytes / (1024 * 1024)
    total_dbs = 1 + len(file_dbs)
    total_capacity_mb = total_dbs * 512.0
    total_free_mb = total_capacity_mb - total_used_mb
    
    if total_used_mb >= 1024:
        used_storage_str = f"{round(total_used_mb / 1024, 2)} GB"
    else:
        used_storage_str = f"{round(total_used_mb, 2)} MB"
        
    if total_free_mb >= 1024:
        free_storage_str = f"{round(total_free_mb / 1024, 2)} GB"
    else:
        free_storage_str = f"{round(total_free_mb, 2)} MB"
        
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "total_groups": total_groups,
        "total_files": total_files,
        "used_storage": used_storage_str,
        "free_storage": free_storage_str,
        "file_dbs_info": file_dbs_info
    }

async def get_stats():
    stats = await get_detailed_stats()
    return stats["total_files"], stats["total_users"]

# ==========================================
#  ৭. এডমিন ডিলেশন ও ইউজার কন্ট্রোল লজিক
# ==========================================

async def delete_files_by_name(query):
    deleted = 0
    # সব ফাইল ডাটাবেজ থেকে নির্দিষ্ট মুভি ডিলিট করা হচ্ছে
    for col in file_cols:
        count = await col.delete_many({"file_name": {"$regex": query, "$options": "i"}})
        deleted += count.deleted_count
        
    # ডিলিশনের পর ক্যাশ এবং ব্লক তালিকা রিসেট করার তাগিদ
    DB_SIZES_CACHE.clear()
    BLOCKED_DBS.clear()
    return deleted

async def delete_all_files_from_db():
    deleted = 0
    # সব ফাইল ডাটাবেজ ফাঁকা করা
    for col in file_cols:
        count = await col.delete_many({})
        deleted += count.deleted_count
        
    # ক্যাশ সম্পূর্ণ ফাঁকা করা হলো
    DB_SIZES_CACHE.clear()
    BLOCKED_DBS.clear()
    return deleted

async def get_all_users():
    users = []
    cursor = users_col.find({})
    async for doc in cursor:
        users.append(doc["user_id"])
    return users

async def save_movie_request(user_id, query):
    exists = await requests_col.find_one({"user_id": user_id, "query": query, "status": "pending"})
    if not exists:
        await requests_col.insert_one({
            "user_id": user_id,
            "query": query,
            "status": "pending"
        })
        return True
    return False

# --- প্রিমিয়াম ইউজার কন্ট্রোল ---
async def add_premium_user(user_id: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": True}},
        upsert=True
    )

async def remove_premium_user(user_id: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": False}}
    )

async def get_all_premium_users():
    premium_users = []
    cursor = users_col.find({"is_premium": True})
    async for doc in cursor:
        premium_users.append(doc["user_id"])
    return premium_users

async def is_premium_user(user_id: int) -> bool:
    user = await users_col.find_one({"user_id": user_id})
    if user:
        return user.get("is_premium", False)
    return False
