# plugins/auto_post.py

import asyncio
import re
import urllib.parse
import urllib.request
import json
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import config
from database import save_file

# --- টিএমডিবি ক্যাটাগরি আইডি ডিকশনারি ম্যাপিং ---
GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western",
    # টিভি সিরিজ ক্যাটাগরি
    10759: "Action & Adventure", 10762: "Kids", 10763: "News",
    10764: "Reality", 10765: "Sci-Fi & Fantasy", 10766: "Soap",
    10767: "Talk", 10768: "War & Politics"
}

# --- ফাইল কোয়ালিটি সনাক্ত করার ফাংশন ---
def detect_quality(name: str) -> str:
    if not name:
        return "HD Quality"
    patterns = [
        (r'\b(2160p|4k|uhd)\b', '4K UHD'),
        (r'\b(1080p|fhd)\b', '1080p FHD'),
        (r'\b(720p|hd)\b', '720p HD'),
        (r'\b(480p|sd)\b', '480p SD'),
        (r'\b(webrip|web-rip|webdl|web-dl)\b', 'WEB-DL'),
        (r'\b(bluray|blu-ray)\b', 'BluRay'),
        (r'\b(hdtv)\b', 'HDTV'),
        (r'\b(camrip|cam|hc)\b', 'CAMRip')
    ]
    try:
        for pattern, label in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                if label in ['WEB-DL', 'BluRay', 'HDTV', 'CAMRip']:
                    res_match = re.search(r'\b(480p|720p|1080p|2160p)\b', name, re.IGNORECASE)
                    if res_match:
                        return f"{res_match.group(0)} {label}"
                return label
    except Exception as e:
        print(f"Quality detection error: {e}")
    return "HD Quality"

# --- সুনির্দিষ্ট ক্লিন-আপ ফাংশন ---
def clean_movie_title(name: str) -> str:
    if not name or not isinstance(name, str):
        return "Movie File"
        
    name = re.sub(r'@[a-zA-Z0-9_]+', '', name)
    name = re.sub(r'(https?://)?(t\.me|telegram\.me|telegram\.dog)/[a-zA-Z0-9_\+]+', '', name)
    
    domain_extensions = "com|org|net|xyz|club|co|tv|link|info|me|cc|site|space|click|in|online|icu"
    name = re.sub(r'\b[a-zA-Z0-9-]+\.(' + domain_extensions + r')\b', '', name, flags=re.IGNORECASE)
    
    name = re.sub(r'\.(mkv|mp4|avi|webm|ts|m4v|3gp)$', '', name, flags=re.IGNORECASE)
    
    name = name.replace(".", " ").replace("_", " ").replace("-", " ")
    name = re.sub(r'\s+', ' ', name).strip()
    
    if not name:
         name = "Movie File"
    return name

# --- পাইথনের স্ট্যান্ডার্ড লাইব্রেরি দিয়ে সিঙ্ক ইউআরআই রিড করার ফাংশন ---
def fetch_sync_url(url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Sync fetch error: {e}")
    return None

# --- মুভির নাম থেকে বছর ও পরিচ্ছন্ন নাম আলাদা করার ফাংশন ---
def parse_name_and_year(raw_name: str):
    match = re.search(r'\b(19|20)\d{2}\b', raw_name)
    if match:
        year = match.group(0)
        name_part = raw_name.split(year)[0]
        clean_name = name_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        return clean_name, year
    else:
        clean_name = clean_movie_title(raw_name)
        return clean_name, None

# --- TMDb এপিআই থেকে মেটাডাটা সংগ্রহের ফাংশন ---
async def fetch_tmdb_metadata(raw_file_name: str):
    api_key = getattr(config, "TMDB_API_KEY", None)
    if not api_key or api_key == "your_tmdb_api_key":
        return None
        
    movie_name, release_year = parse_name_and_year(raw_file_name)
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={urllib.parse.quote(movie_name)}&language=en-US"
    
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, fetch_sync_url, search_url)
    
    if data:
        results = data.get("results", [])
        if results:
            matched_item = None
            if release_year:
                for item in results:
                    media_type = item.get("media_type")
                    date_key = "release_date" if media_type == "movie" else "first_air_date"
                    item_date = item.get(date_key, "")
                    if item_date and item_date.startswith(release_year):
                        matched_item = item
                        break
                        
            if not matched_item:
                valid_results = [r for r in results if r.get("media_type") in ["movie", "tv"]]
                if valid_results:
                    matched_item = valid_results[0]
                    
            if matched_item:
                return matched_item
    return None

# --- প্রধান চ্যানেলে মুভি/সিরিজ আপলোড হ্যান্ডলার ---
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_channel_post_handler(client: Client, message: Message):
    await asyncio.sleep(2)
    
    media = message.document or message.video
    file_name = media.file_name
    file_size_mb = round(media.file_size / (1024 * 1024), 2)
    
    from database import file_cols
    db_id = None
    
    # ১. প্রথমে ফাইল ইউনিক আইডি দিয়ে খোঁজ করা হচ্ছে
    for col in file_cols:
        doc = await col.find_one({"file_id": media.file_id})
        if doc:
            db_id = str(doc["_id"])
            break
            
    # ২. নাম ও সাইজ দিয়ে ডাটাবেজে ডুপ্লিকেট খোঁজ করা হচ্ছে
    if not db_id:
        for col in file_cols:
            doc = await col.find_one({"file_name": file_name, "file_size": media.file_size})
            if doc:
                db_id = str(doc["_id"])
                break
            
    # ৩. ডাটাবেজে না থাকলে নতুন ফাইল হিসেবে সেভ করা হচ্ছে
    if not db_id:
        try:
            db_id = await save_file(file_name, media.file_size, media.file_id, message.chat.id, message.id)
        except Exception as e:
            print(f"Error saving file: {e}")
        
    if not db_id:
        print("Skipping auto post: db_id not found or failed to save.")
        return
        
    cleaned_title = clean_movie_title(file_name)
    movie_meta = await fetch_tmdb_metadata(file_name)
    bot_username = getattr(config, "BOT_USERNAME", "CTGMovieBot")
    
    # ইউনিক কি (Key) নির্ধারণ
    if movie_meta:
        media_type = movie_meta.get("media_type", "movie")
        tmdb_id = movie_meta.get("id")
        unique_key = f"{media_type}_{tmdb_id}"
    else:
        slug = re.sub(r'[^a-z0-9]', '', cleaned_title.lower())
        unique_key = f"raw_{slug}"
        
    current_quality = detect_quality(file_name)
    file_info = {
        "db_id": db_id,
        "file_name": file_name,
        "size": file_size_mb,
        "quality": current_quality
    }
    
    # ডেটাবেজ মার্জিং লজিক (নিরাপদ ট্রাই-এক্সেপ্ট ব্লক সহ)
    files_list = [file_info]  # ডিফল্ট ফলব্যাক মান
    existing_post = None
    posts_col = None
    use_aggregation = False
    
    try:
        if file_cols and len(file_cols) > 0:
            db = file_cols[0].database
            posts_col = db["channel_posts"]
            
            existing_post = await posts_col.find_one({"_id": unique_key})
            if existing_post:
                files_list = existing_post.get("files", [])
                if not any(f["db_id"] == db_id for f in files_list):
                    files_list.append(file_info)
                    await posts_col.update_one({"_id": unique_key}, {"$set": {"files": files_list}})
            else:
                await posts_col.insert_one({"_id": unique_key, "files": files_list, "msg_id": None})
            use_aggregation = True
    except Exception as e:
        print(f"Database aggregation/lookup error: {e}. Falling back to normal posting.")
        files_list = [file_info]
        use_aggregation = False
        
    # বাটন ও সাইজ টেক্সট সাজানো
    buttons = []
    size_parts = []
    for f in files_list:
        download_url = f"https://t.me/{bot_username}?start=app_{f['db_id']}"
        btn_label = f"🍿 Download [{f['quality']} - {f['size']} MB] 🍿"
        buttons.append([InlineKeyboardButton(btn_label, url=download_url)])
        size_parts.append(f"`{f['quality']}: {f['size']} MB`")
        
    size_str = " | ".join(size_parts)
    
    # ক্যাপশন ফরম্যাটিং (টিএমডিবি ডাটা থাকলে)
    if movie_meta:
        media_type = movie_meta.get("media_type", "movie")
        if media_type == "tv":
            title_raw = movie_meta.get("name") or movie_meta.get("original_name") or file_name
            year = movie_meta.get("first_air_date", "N/A")[:4]
            header_text = "📺 **NEW WEB SERIES ADDED!** 📺"
            title_label = "Series Name"
        else:
            title_raw = movie_meta.get("title") or movie_meta.get("original_title") or file_name
            year = movie_meta.get("release_date", "N/A")[:4]
            header_text = "🎬 **NEW MOVIE ADDED!** 🎬"
            title_label = "Movie Name"
            
        if re.search(r'[\u0980-\u09ff]', title_raw):
            title = cleaned_title
        else:
            title = title_raw
            
        rating = movie_meta.get("vote_average", "N/A")
        genre_ids = movie_meta.get("genre_ids", [])
        genre_names = [GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)]
        genres = ", ".join(genre_names) if genre_names else "N/A"
        poster_path = movie_meta.get("poster_path")
        
        caption_text = (
            f"{header_text}\n\n"
            f"📝 **{title_label}:** `{title}` ({year})\n"
            f"🌟 **Rating:** ⭐ `{rating}/10`\n"
            f"🎭 **Genre:** `{genres}`\n"
            f"💾 **Size:** {size_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🍿 Select your preferred quality below to download instantly!"
        )
    else:
        # ফলব্যাক সাধারণ ক্যাপশন
        poster_path = None
        caption_text = (
            f"🎬 **NEW FILE ADDED!** 🎬\n\n"
            f"📝 **File Name:** `{cleaned_title}`\n"
            f"💾 **Size:** {size_str}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🍿 Select your preferred quality below to download instantly!"
        )
        
    # এডিটিং বা নতুন পোস্ট করার প্রক্রিয়া
    sent_msg = None
    if use_aggregation and existing_post and existing_post.get("msg_id"):
        msg_id = existing_post["msg_id"]
        try:
            if poster_path:
                await client.edit_message_caption(
                    chat_id=config.UPDATE_CHANNEL_ID,
                    message_id=msg_id,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await client.edit_message_text(
                    chat_id=config.UPDATE_CHANNEL_ID,
                    message_id=msg_id,
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            return  # এডিট সফল হলে এখানেই ফাংশন শেষ হবে
        except Exception as e:
            print(f"Failed to edit message {msg_id}: {e}. Sending as a new post...")
            
    # নতুন পোস্ট পাঠানোর প্রক্রিয়া
    if poster_path:
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        try:
            sent_msg = await client.send_photo(
                chat_id=config.UPDATE_CHANNEL_ID,
                photo=poster_url,
                caption=caption_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            print(f"Failed to send poster photo: {e}")
            
    if not sent_msg:
        try:
            sent_msg = await client.send_message(
                chat_id=config.UPDATE_CHANNEL_ID,
                text=caption_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            print(f"Failed to send update message: {e}")
            
    # ডেটাবেজে মেসেজ আইডি সংরক্ষণ (ভবিষ্যতে এডিটের জন্য)
    if sent_msg and use_aggregation and posts_col is not None:
        try:
            await posts_col.update_one(
                {"_id": unique_key},
                {"$set": {"msg_id": sent_msg.id, "files": files_list}},
                upsert=True
            )
        except Exception as e:
            print(f"Failed to save post reference to DB: {e}")
