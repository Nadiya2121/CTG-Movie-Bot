# database.py

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import config

client = AsyncIOMotorClient(config.MONGO_URI)
db = client["movie_search_bot"]
files_col = db["files"]
users_col = db["users"]

# নতুন ইউজার সেভ করা
async def add_user(user_id, username, first_name):
    username = username if username else "No Username"
    first_name = first_name if first_name else "User"
    
    exists = await users_col.find_one({"user_id": user_id})
    if not exists:
        await users_col.insert_one({
            "user_id": user_id,
            "username": username,
            "first_name": first_name
        })

# নতুন ফাইল সেভ করা
async def save_file(file_name, file_size, file_id, chat_id, message_id):
    exists = await files_col.find_one({"file_id": file_id})
    if not exists:
        file_data = {
            "file_name": file_name,
            "file_size": file_size,
            "file_id": file_id,
            "chat_id": chat_id,
            "message_id": message_id
        }
        await files_col.insert_one(file_data)
        return True
    return False

# মুভি সার্চ করা
async def search_db(query):
    results = []
    cursor = files_col.find({"file_name": {"$regex": query, "$options": "i"}}).limit(20)
    async for doc in cursor:
        results.append(doc)
    return results

# ডাটাবেজ আইডি দিয়ে ফাইল খোঁজা
async def get_file_by_db_id(db_id):
    try:
        return await files_col.find_one({"_id": ObjectId(db_id)})
    except Exception:
        return None

# লাইভ স্ট্যাটাস দেখা
async def get_stats():
    total_files = await files_col.estimated_document_count()
    total_users = await users_col.estimated_document_count()
    return total_files, total_users

# নাম দিয়ে মুভি ডিলিট করা
async def delete_files_by_name(query):
    result = await files_col.delete_many({"file_name": {"$regex": query, "$options": "i"}})
    return result.deleted_count

# সম্পূর্ণ ডাটাবেজ খালি করা
async def delete_all_files_from_db():
    result = await files_col.delete_many({})
    return result.deleted_count

# ব্রডকাস্টের জন্য সব ইউজারের আইডি সংগ্রহ করা (এডমিন ফাইলের ইম্পোর্ট এরর এটি সমাধান করবে)
async def get_all_users():
    users = []
    try:
        cursor = users_col.find({})
        async for doc in cursor:
            users.append(doc["user_id"])
    except Exception as e:
        print(f"Error fetching users: {e}")
    return users
