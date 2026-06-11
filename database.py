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

# ==========================================
#  ২. ডায়নামিক অটো-সুইচিং লজিক
# ==========================================

async def get_active_files_collection():
    """
    ফাইল ডাটাবেজগুলোর সাইজ চেক করে প্রথম যে ডাটাবেজটি ৪০০ এমবি (কনফিগ লিমিট) এর নিচে আছে,
    সেটির কালেকশন রিটার্ন করবে। সবগুলো ফুল হয়ে গেলে শেষ ডাটাবেজটি রিটার্ন করবে।
    """
    if not file_cols:
        return None

    for idx, db in enumerate(file_dbs):
        try:
            stats = await db.command("dbstats")
            # storageSize এবং indexSize যোগ করে প্রকৃত স্পেস ব্যবহার বের করা হচ্ছে
            used_bytes = stats.get("storageSize", 0) + stats.get("indexSize", 0)
            used_mb = used_bytes / (1024 * 1024)
            
            # যদি বর্তমান ডাটাবেজের সাইজ লিমিটের চেয়ে কম থাকে, তবে এটিকেই একটিভ করা হবে
            if used_mb < config.DB_LIMIT_MB:
                return file_cols[idx]
        except Exception as e:
            print(f"⚠️ ডাটাবেজ {idx+1} সাইজ চেক করতে ব্যর্থ: {e}")
            
    # যদি সবগুলো ডাটাবেজই ফুল হয়ে যায়, তবে শেষ ডাটাবেজটি ডিফল্ট হিসেবে কাজ করবে
    return file_cols[-1]

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
#  ৪. ফাইল ইনডেক্সিং এবং ডুপ্লিকেট প্রটেকশন (অপ্টিমাইজড আপডেট)
# ==========================================

async def save_file(file_name, file_size, file_id, chat_id, message_id):
    active_col = await get_active_files_collection()
    if not active_col:
        return False
    
    file_name = file_name if file_name else f"Video_File_{file_size}"
    
    # ডুপ্লিকেট প্রতিরোধের জন্য সব ফাইল ডাটাবেজে ফাইলটি ইতিমধ্যে আছে কিনা চেক করা হচ্ছে
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
    
    # ডুপ্লিকেট না থাকলে বর্তমান সচল (Active) ডাটাবেজে সেভ করা হবে এবং ইউনিক অবজেক্ট আইডি রিটার্ন করবে
    if not duplicate:
        file_data = {
            "file_name": file_name,
            "file_size": file_size,
            "file_id": file_id,
            "chat_id": chat_id,
            "message_id": message_id
        }
        # [ছোট্ট আপডেট]: সেভ হওয়ার পর ইনসার্টেড ইউনিক _id রিটার্ন করবে যা নোটিফিকেশন সিস্টেম ব্যবহার করবে
        result = await active_col.insert_one(file_data)
        return str(result.inserted_id)
        
    return False

# ==========================================
#  ৫. মাল্টি-ডিবি সার্চ এবং সর্টিং ইঞ্জিন
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
    
    # সবগুলো ফাইল ডাটাবেজে সমান্তরালভাবে সার্চ চালানো হচ্ছে
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
#  ৬. মেমরি ও প্রফেশনাল স্ট্যাটাস মেকানিজম
# ==========================================

async def get_detailed_stats():
    # সবগুলো ফাইল ডাটাবেজ থেকে মোট ফাইলের সংখ্যা বের করা
    total_files = 0
    for col in file_cols:
        total_files += await col.estimated_document_count()
        
    total_users = await users_col.estimated_document_count()
    premium_users = await users_col.count_documents({"is_premium": True})
    total_groups = await groups_col.estimated_document_count()
    
    # ব্যবহৃত মোট স্টোরেজ হিসাব করা (ইউজার ডিবি + সব ফাইল ডিবি)
    total_used_bytes = 0
    
    # ১. ইউজার ডাটাবেজের সাইজ
    try:
        u_stats = await user_db.command("dbstats")
        total_used_bytes += u_stats.get("storageSize", 0) + u_stats.get("indexSize", 0)
    except Exception:
        pass
        
    # ২. সব ফাইল ডাটাবেজের সাইজ
    for db in file_dbs:
        try:
            f_stats = await db.command("dbstats")
            total_used_bytes += f_stats.get("storageSize", 0) + f_stats.get("indexSize", 0)
        except Exception:
            pass
            
    # বাইট থেকে এমবিতে রূপান্তর
    total_used_mb = total_used_bytes / (1024 * 1024)
    
    # মোট খালি স্টোরেজ হিসাব করা (১টি ইউজার ডিবি + ফাইল ডিবির সংখ্যা) * ৫১২ এমবি
    total_dbs = 1 + len(file_dbs)
    total_capacity_mb = total_dbs * 512.0
    total_free_mb = total_capacity_mb - total_used_mb
    
    # জিবির হিসাব
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
        "free_storage": free_storage_str
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
    return deleted

async def delete_all_files_from_db():
    deleted = 0
    # সব ফাইল ডাটাবেজ ফাঁকা করা
    for col in file_cols:
        count = await col.delete_many({})
        deleted += count.deleted_count
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
