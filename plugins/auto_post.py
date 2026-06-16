# plugins/auto_post.py

import asyncio
import re
import urllib.parse
import urllib.request
import json
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import config

# database.py থেকে প্রয়োজনীয় কালেকশন এবং ইউজার ডাটাবেজ সরাসরি ইম্পোর্ট করা হলো
from database import file_cols, user_db, save_file

# --- লুপ-স্বাধীন গ্লোবাল স্পিনলক সেট (ডাবল পোস্ট সম্পূর্ণ বন্ধ করার জন্য) ---
processing_keys = set()

# --- ডিফল্ট পোস্টার লিংক (ছবি না পাওয়া গেলে এটি পোস্টার হিসেবে কাজ করবে) ---
DEFAULT_POSTER = "https://graph.org/file/f3ecbcbc63345d3eb97c2.jpg"

# --- ল্যাঙ্গুয়েজ কোড ম্যাপ (TMDb এর সংক্ষেপিত রূপ থেকে পূর্ণ রূপ) ---
LANG_MAP = {
    "en": "English", "hi": "Hindi", "bn": "Bengali", "ta": "Tamil",
    "te": "Telugu", "ml": "Malayalam", "kn": "Kannada", "ko": "Korean",
    "ja": "Japanese", "zh": "Chinese", "es": "Spanish", "fr": "French",
    "ru": "Russian", "it": "Italian", "de": "German"
}

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

# --- চ্যাট আইডি ফরম্যাটিং হেল্পার ---
def get_chat_id(chat_id_val):
    if isinstance(chat_id_val, str):
        if re.match(r'^-?\d+$', chat_id_val):
            return int(chat_id_val)
    return chat_id_val

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

# --- অত্যন্ত নিখুঁত ও উন্নত ভাষা সনাক্তকরণ ফাংশন ---
def detect_language(filename: str, tmdb_lang_code: str = None) -> str:
    filename_lower = filename.lower()
    detected_langs = []
    
    # ৩ অক্ষরের শর্ট কোড এবং পূর্ণ নাম সনাক্তকরণ রুলস
    lang_patterns = [
        (r'\b(telugu|tel)\b', "Telugu"),
        (r'\b(tamil|tam)\b', "Tamil"),
        (r'\b(hindi|hin)\b', "Hindi"),
        (r'\b(bengali|bangla|ben)\b', "Bengali"),
        (r'\b(english|eng)\b', "English"),
        (r'\b(malayalam|mal)\b', "Malayalam"),
        (r'\b(kannada|kan)\b', "Kannada"),
        (r'\b(korean|kor)\b', "Korean"),
        (r'\b(japanese|jap)\b', "Japanese")
    ]
    
    # স্পেশাল ক্যারেক্টারগুলোকে স্পেস দিয়ে রিপ্লেস করে নরমাল করা
    normalized_name = filename_lower.replace("-", " ").replace(".", " ").replace("_", " ").replace("[", " ").replace("]", " ")
    
    for pattern, label in lang_patterns:
        if re.search(pattern, normalized_name):
            if label not in detected_langs:
                detected_langs.append(label)
                
    if len(detected_langs) >= 2:
        langs_str = " + ".join(detected_langs)
        return f"Dual Audio [{langs_str}]"
    elif len(detected_langs) == 1:
        if "dual" in filename_lower:
            return f"Dual Audio [{detected_langs[0]}]"
        return detected_langs[0]
        
    if "dual" in filename_lower:
        return "Dual Audio"
    if "multi" in filename_lower:
        return "Multi Audio"
        
    if tmdb_lang_code and tmdb_lang_code in LANG_MAP:
        return LANG_MAP[tmdb_lang_code]
        
    return "Not Specified"

# --- অত্যন্ত শক্তিশালী ক্লিন-আপ ফাংশন ---
def advanced_clean_title(name: str) -> str:
    if not name or not isinstance(name, str):
        return "Movie File"
        
    name = re.sub(r'\.(mkv|mp4|avi|webm|ts|m4v|3gp)$', '', name, flags=re.IGNORECASE)
    
    name = re.sub(r'@[a-zA-Z0-9_]+', '', name)
    name = re.sub(r'(https?://)?(t\.me|telegram\.me|telegram\.dog)/[a-zA-Z0-9_\+]+', '', name)
    domain_extensions = "com|org|net|xyz|club|co|tv|link|info|me|cc|site|space|click|in|online|icu|buzz|movie|hub"
    name = re.sub(r'\b[a-zA-Z0-9-]+\.(' + domain_extensions + r')\b', '', name, flags=re.IGNORECASE)
    
    name = re.sub(r'\[[^\]]*\]', ' ', name)
    name = re.sub(r'\((?!\d{4}\))[^\)]*\)', ' ', name)
    
    junk_keywords = [
        r'\bdual[- ]?audio\b', r'\bmulti[- ]?audio\b', r'\bhindi\b', r'\benglish\b', r'\bbengali\b', 
        r'\btamil\b', r'\btelugu\b', r'\bpunjabi\b', r'\bmalayalam\b', r'\bclean\b', r'\baud\b',
        r'\bhevc\b', r'\bx264\b', r'\bx265\b', r'\b10bit\b', r'\b8bit\b', r'\bh264\b', r'\bh265\b',
        r'\baac\b', r'\bac3\b', r'\bdd5\.1\b', r'\bweb[-]?dl\b', r'\bweb[-]?rip\b', r'\bbluray\b', 
        r'\bhdrip\b', r'\bbrrip\b', r'\bcamrip\b', r'\bcam\b', r'\bhdtv\b', r'\bhdr\b', r'\besub\b', 
        r'\bmsub\b', r'\bsubtitles\b', r'\beng\b', r'\bhin\b', r'\borg\b', r'\buncut\b', r'\brip\b'
    ]
    for kw in junk_keywords:
        name = re.sub(kw, ' ', name, flags=re.IGNORECASE)
    
    name = name.replace(".", " ").replace("_", " ").replace("-", " ")
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.title()
    
    if not name:
         name = "Movie File"
    return name

# --- সিজন এবং এপিসোড সনাক্ত করার ফাংশন ---
def parse_season_episode(name: str):
    se_pattern = re.compile(
        r'\bS(\d{1,2})\s*E(\d{1,2})\b|\bSeason\s*(\d{1,2})\s*Episode\s*(\d{1,2})\b',
        re.IGNORECASE
    )
    match = se_pattern.search(name)
    if match:
        s1, e1, s2, e2 = match.groups()
        season = int(s1 or s2)
        episode = int(e1 or e2)
        return season, episode

    s_pattern = re.compile(r'\bS(\d{1,2})\b|\bSeason\s*(\d{1,2})\b', re.IGNORECASE)
    s_match = s_pattern.search(name)
    if s_match:
        s1, s2 = s_match.groups()
        return int(s1 or s2), None

    e_pattern = re.compile(r'\bE(\d{1,2})\b|\b(?:Episode|Ep)\s*(\d{1,2})\b', re.IGNORECASE)
    e_match = e_pattern.search(name)
    if e_match:
        e1, e2 = e_match.groups()
        return None, int(e1 or e2)

    return None, None

# --- টিএমডিবি সার্চের জন্য নাম ফিল্টার করার ফাংশন ---
def clean_search_query(name: str) -> str:
    cleaned = advanced_clean_title(name)
    cleaned = re.sub(
        r'\b(S\d{1,2}\s*E\d{1,2}|S\d{1,2}|E\d{1,2}|Season\s*\d{1,2}|Episode\s*\d{1,2}|EP\s*\d{1,2})\b', 
        '', 
        cleaned, 
        flags=re.IGNORECASE
    )
    return re.sub(r'\s+', ' ', cleaned).strip()

# --- সিঙ্ক ইউআরআই রিড করার ফাংশন ---
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
    search_name = clean_search_query(raw_name)
    match = re.search(r'\b(19|20)\d{2}\b', search_name)
    if match:
        year = match.group(0)
        name_part = search_name.split(year)[0]
        clean_name = name_part.strip()
        return clean_name, year
    else:
        return search_name, None

# --- TMDb এপিআই থেকে মেটাডাটা সংগ্রহের ফাংশন ---
async def fetch_tmdb_metadata(raw_file_name: str):
    api_key = getattr(config, "TMDB_API_KEY", None)
    if not api_key or api_key == "your_tmdb_api_key":
        return None
        
    movie_name, release_year = parse_name_and_year(raw_file_name)
    if not movie_name:
        return None
        
    loop = asyncio.get_running_loop()
    
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={urllib.parse.quote(movie_name)}&language=en-US"
    data = await loop.run_in_executor(None, fetch_sync_url, search_url)
    
    if not data or not data.get("results"):
        short_name = " ".join(movie_name.split()[:3])
        if short_name and short_name != movie_name:
            search_url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={urllib.parse.quote(short_name)}&language=en-US"
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
    # ডাটাবেজ প্রসেস সম্পন্ন হওয়ার জন্য ২ সেকেন্ড বিরতি
    await asyncio.sleep(2)
    
    media = message.document or message.video
    file_name = media.file_name
    file_size_mb = round(media.file_size / (1024 * 1024), 2)
    
    db_id = None
    
    # ১. ডাটাবেজ চেক
    for col in file_cols:
        doc = await col.find_one({"file_id": media.file_id})
        if doc:
            db_id = str(doc["_id"])
            break
            
    if not db_id:
        for col in file_cols:
            doc = await col.find_one({"file_name": file_name, "file_size": media.file_size})
            if doc:
                db_id = str(doc["_id"])
                break
            
    if not db_id:
        try:
            db_id = await save_file(file_name, media.file_size, media.file_id, message.chat.id, message.id)
        except Exception as e:
            print(f"Error while calling save_file: {e}")
        
    if not db_id:
        print("Skipping post: File ID could not be retrieved.")
        return
        
    cleaned_title = advanced_clean_title(file_name)
    season, episode = parse_season_episode(file_name)
    movie_meta = await fetch_tmdb_metadata(file_name)
    bot_username = getattr(config, "BOT_USERNAME", "CTGMovieBot")
    
    # ল্যাঙ্গুয়েজ নির্ধারণ
    tmdb_lang_code = movie_meta.get("original_language") if movie_meta else None
    detected_lang = detect_language(file_name, tmdb_lang_code)
    
    # ইউনিক কি নির্ধারণ
    if movie_meta:
        media_type = movie_meta.get("media_type", "movie")
        tmdb_id = movie_meta.get("id")
        if media_type == "tv" and season is not None:
            unique_key = f"tv_{tmdb_id}_S{season:02d}"
        else:
            unique_key = f"{media_type}_{tmdb_id}"
    else:
        slug = re.sub(r'[^a-z0-9]', '', cleaned_title.lower())
        if season is not None:
            unique_key = f"raw_{slug}_S{season:02d}"
        else:
            unique_key = f"raw_{slug}"
        
    current_quality = detect_quality(file_name)
    file_info = {
        "db_id": db_id,
        "file_name": file_name,
        "size": file_size_mb,
        "quality": current_quality,
        "season": season,
        "episode": episode
    }
    
    # --- [Spinlock to prevent concurrent double posts - 100% Loop Safe] ---
    while unique_key in processing_keys:
        await asyncio.sleep(0.5)
        
    processing_keys.add(unique_key)
    
    try:
        posts_col = user_db["channel_posts"]
        files_list = []
        existing_post = None
        use_aggregation = False
        
        try:
            # প্রথমে নতুন পোস্ট হিসেবে ইনসার্ট করার চেষ্টা করা হবে
            await posts_col.insert_one({
                "_id": unique_key,
                "files": [file_info],
                "msg_id": None
            })
            files_list = [file_info]
            use_aggregation = True
        except Exception:
            # যদি পোস্টটি অলরেডি ডাটাবেজে থাকে, তবে নতুন ফাইলটি পুশ করা হবে
            try:
                await posts_col.update_one(
                    {"_id": unique_key},
                    {"$addToSet": {"files": file_info}}
                )
                existing_post = await posts_col.find_one({"_id": unique_key})
                if existing_post:
                    files_list = existing_post.get("files", [])
                    use_aggregation = True
            except Exception as e:
                print(f"Bypass aggregation error: {e}")
                files_list = [file_info]
                use_aggregation = False
            
        # বাটন সাজানো
        def get_sort_key(item):
            return (item.get("season") or 0, item.get("episode") or 0, item.get("quality", ""))
            
        files_list = sorted(files_list, key=get_sort_key)
        
        buttons = []
        size_parts = []
        for f in files_list:
            download_url = f"https://t.me/{bot_username}?start=app_{f['db_id']}"
            ep_prefix = ""
            if f.get("season") is not None and f.get("episode") is not None:
                ep_prefix = f"S{f['season']:02d}E{f['episode']:02d} | "
            elif f.get("episode") is not None:
                ep_prefix = f"EP {f['episode']:02d} | "
                
            btn_label = f"🍿 {ep_prefix}{f['quality']} - {f['size']} MB 🍿"
            buttons.append([InlineKeyboardButton(btn_label, url=download_url)])
            
            size_label = f"{ep_prefix.replace(' | ', '')} ({f['quality']})" if ep_prefix else f"{f['quality']}"
            size_parts.append(f"`{size_label}: {f['size']} MB`")
            
        size_str = "\n" + "\n".join(size_parts) if len(size_parts) > 3 else " | ".join(size_parts)
        
        # poster link
        poster_url = DEFAULT_POSTER
        if movie_meta and movie_meta.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w500{movie_meta['poster_path']}"
            
        # ক্যাপশন তৈরি
        if movie_meta:
            media_type = movie_meta.get("media_type", "movie")
            if media_type == "tv":
                title_raw = movie_meta.get("name") or movie_meta.get("original_name") or file_name
                year = movie_meta.get("first_air_date", "N/A")[:4]
                season_str = f" (Season {season})" if season is not None else ""
                header_text = "📺 **NEW WEB SERIES ADDED!** 📺"
                title_label = "Series Name"
                display_title = f"{title_raw}{season_str}"
            else:
                title_raw = movie_meta.get("title") or movie_meta.get("original_title") or file_name
                year = movie_meta.get("release_date", "N/A")[:4]
                header_text = "🎬 **NEW MOVIE ADDED!** 🎬"
                title_label = "Movie Name"
                display_title = title_raw
                
            if re.search(r'[\u0980-\u09ff]', title_raw):
                title = cleaned_title
            else:
                title = display_title
                
            rating = movie_meta.get("vote_average", "N/A")
            genre_ids = movie_meta.get("genre_ids", [])
            genre_names = [GENRE_MAP.get(gid) for gid in genre_ids if GENRE_MAP.get(gid)]
            genres = ", ".join(genre_names) if genre_names else "N/A"
            
            caption_text = (
                f"{header_text}\n\n"
                f"📝 **{title_label}:** `{title}` ({year})\n"
                f"🌍 **Language:** `{detected_lang}`\n"
                f"🌟 **Rating:** ⭐ `{rating}/10`\n"
                f"🎭 **Genre:** `{genres}`\n"
                f"💾 **Size:** {size_str}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🍿 Select your preferred episode/quality below to download instantly!"
            )
        else:
            # ফলব্যাক সাধারণ ক্যাপশন
            season_str = f" (Season {season})" if season is not None else ""
            caption_text = (
                f"🎬 **NEW FILE ADDED!** 🎬\n\n"
                f"📝 **File Name:** `{cleaned_title}{season_str}`\n"
                f"🌍 **Language:** `{detected_lang}`\n"
                f"💾 **Size:** {size_str}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🍿 Select your preferred episode/quality below to download instantly!"
            )
            
        update_chat_id = get_chat_id(config.UPDATE_CHANNEL_ID)
        sent_msg = None
        
        # এডিট করার চেষ্টা করা হচ্ছে (যদি আগের মেসেজ আইডি থাকে)
        if use_aggregation and existing_post and existing_post.get("msg_id"):
            msg_id = existing_post["msg_id"]
            try:
                await client.edit_message_caption(
                    chat_id=update_chat_id,
                    message_id=msg_id,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return
            except Exception as e:
                print(f"Failed to edit message {msg_id}: {e}. Posting a new update message instead.")
                
        # নতুন পোস্ট পাঠানোর প্রক্রিয়া
        try:
            sent_msg = await client.send_photo(
                chat_id=update_chat_id,
                photo=poster_url,
                caption=caption_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            print(f"Failed to send poster photo: {e}. Trying fallback to DEFAULT_POSTER.")
            try:
                sent_msg = await client.send_photo(
                    chat_id=update_chat_id,
                    photo=DEFAULT_POSTER,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as err:
                print(f"Failed to send default poster photo: {err}. Sending text instead.")
                try:
                    sent_msg = await client.send_message(
                        chat_id=update_chat_id,
                        text=caption_text,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception as msg_err:
                    print(f"Complete failure: {msg_err}")
                
        # ডেটাবেজে পোস্টের মেসেজ আইডি আপডেট রাখা হচ্ছে
        if sent_msg and use_aggregation:
            try:
                await posts_col.update_one(
                    {"_id": unique_key},
                    {"$set": {"msg_id": sent_msg.id, "files": files_list}},
                    upsert=True
                )
            except Exception as e:
                print(f"Failed to update post reference in DB: {e}")
    finally:
        # প্রসেস শেষ হলে লকটি রিলিজ করা হচ্ছে
        processing_keys.discard(unique_key)
