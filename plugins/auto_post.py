# plugins/auto_post.py

import asyncio
import re
import urllib.parse
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import config
from database import save_file, clean_movie_title

# --- মুভির নাম থেকে বছর ও পরিচ্ছন্ন নাম আলাদা করার ফাংশন ---
def parse_name_and_year(raw_name: str):
    # ৪ ডিজিটের বছর খোঁজা হচ্ছে (১৯০০ থেকে ২০৯৯ পর্যন্ত)
    match = re.search(r'\b(19|20)\d{2}\b', raw_name)
    if match:
        year = match.group(0)
        # বছরের পূর্ববর্তী অংশটিকে মুভির আসল নাম হিসেবে আলাদা করা হচ্ছে
        name_part = raw_name.split(year)[0]
        # নাম থেকে ডট, আন্ডারস্কোর সরিয়ে পরিচ্ছন্ন করা হচ্ছে
        clean_name = name_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        # অতিরিক্ত ডাবল স্পেস ডিলিট
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        return clean_name, year
    else:
        # যদি বছর খুঁজে পাওয়া না যায়
        clean_name = clean_movie_title(raw_name)
        return clean_name, None

# --- TMDb এপিআই থেকে বছর সহ মুভি বা সিরিজ (Multi Search) এর বাংলা মেটাডাটা ও পোস্টার সংগ্রহের ফাংশন ---
async def fetch_tmdb_metadata(raw_file_name: str):
    api_key = getattr(config, "TMDB_API_KEY", None)
    if not api_key or api_key == "your_tmdb_api_key":
        return None
        
    movie_name, release_year = parse_name_and_year(raw_file_name)
    
    # Multi Search API ব্যবহার করা হচ্ছে যা মুভি এবং ওয়েব সিরিজ একসাথে সার্চ করতে পারে
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={urllib.parse.quote(movie_name)}&language=bn-BD"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        # বছর অনুযায়ী নিখুঁত ম্যাচিং ফিল্টার করা হচ্ছে
                        matched_item = None
                        if release_year:
                            for item in results:
                                media_type = item.get("media_type")
                                # মুভির জন্য release_date এবং সিরিজের জন্য first_air_date চেক করা হচ্ছে
                                date_key = "release_date" if media_type == "movie" else "first_air_date"
                                item_date = item.get(date_key, "")
                                if item_date and item_date.startswith(release_year):
                                    matched_item = item
                                    break
                                    
                        # যদি বছর দিয়ে কোনো ম্যাচ না পাওয়া যায় বা ফাইলে বছর না থাকে, তবে প্রথম মুভি বা সিরিজটি নেওয়া হবে
                        if not matched_item:
                            valid_results = [r for r in results if r.get("media_type") in ["movie", "tv"]]
                            if valid_results:
                                matched_item = valid_results[0]
                                
                        if matched_item:
                            media_type = matched_item.get("media_type")
                            item_id = matched_item.get("id")
                            
                            # যদি বাংলা কাহিনী সংক্ষেপ (Overview) খালি থাকে, তবে ইংলিশ ফলব্যাক নেওয়া হবে
                            if not matched_item.get("overview") or matched_item.get("overview").strip() == "":
                                eng_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={api_key}&language=en-US"
                                async with session.get(eng_url) as eng_resp:
                                    if eng_resp.status == 200:
                                        eng_data = await eng_resp.json()
                                        matched_item["overview"] = eng_data.get("overview")
                                        
                            return matched_item
        except Exception as e:
            print(f"TMDb API Error: {e}")
    return None

# --- প্রধান চ্যানেলে মুভি/সিরিজ আপলোড হওয়া মাত্রই স্বয়ংক্রিয়ভাবে ক্যাচ করার হ্যান্ডলার ---
@Client.on_message(filters.chat(config.MAIN_CHANNEL_ID) & (filters.document | filters.video))
async def auto_channel_post_handler(client: Client, message: Message):
    # ডাটাবেজ সেভ সম্পন্ন হওয়ার জন্য সামান্য অপেক্ষা
    await asyncio.sleep(2)
    
    # ফাইলের তথ্য সংগ্রহ
    media = message.document or message.video
    file_name = media.file_name
    file_size_mb = round(media.file_size / (1024 * 1024), 2)
    
    # মঙ্গোডিবি থেকে এই ফাইলের অবজেক্ট আইডি খোঁজা
    from database import file_cols
    db_id = None
    for col in file_cols:
        doc = await col.find_one({"file_id": media.file_id})
        if doc:
            db_id = str(doc["_id"])
            break
            
    if not db_id:
        # যদি কোনো কারণে আগে সেভ না হয়ে থাকে, তবে এখন সেভ করে নেওয়া হচ্ছে
        db_id = await save_file(file_name, media.file_size, media.file_id, message.chat.id, message.id)
        
    if not db_id:
        return  # আইডি না পাওয়া গেলে পোস্ট করা হবে না
        
    # TMDb থেকে বছরসহ নিখুঁত ম্যাচিং তথ্য সংগ্রহ (মুভি ও ওয়েব সিরিজ ক্যাটাগরি ডিটেকশন)
    movie_meta = await fetch_tmdb_metadata(file_name)
    
    bot_username = getattr(config, "BOT_USERNAME", "CTGMovieBot")
    download_url = f"https://t.me/{bot_username}?start=get_{db_id}"
    
    buttons = [
        [
            InlineKeyboardButton("🍿 ওয়ান-ক্লিক ডাউনলোড লিংক 🍿", url=download_url)
        ]
    ]
    
    # যদি TMDb-তে তথ্য পাওয়া যায়
    if movie_meta:
        media_type = movie_meta.get("media_type", "movie")
        
        # মুভি নাকি ওয়েব সিরিজ তা আলাদাভাবে ফরম্যাটিং করা হচ্ছে
        if media_type == "tv":
            title = movie_meta.get("name") or movie_meta.get("original_name") or file_name
            year = movie_meta.get("first_air_date", "N/A")[:4]
            header_text = "📺 **নতুন ওয়েব সিরিজ যুক্ত করা হয়েছে!** 📺"
            title_label = "সিরিজের নাম"
        else:
            title = movie_meta.get("title") or movie_meta.get("original_title") or file_name
            year = movie_meta.get("release_date", "N/A")[:4]
            header_text = "🎬 **নতুন মুভি যুক্ত করা হয়েছে!** 🎬"
            title_label = "মুভির নাম"
            
        rating = movie_meta.get("vote_average", "N/A")
        overview = movie_meta.get("overview") or "কোনো কাহিনী সংক্ষেপ পাওয়া যায়নি।"
        poster_path = movie_meta.get("poster_path")
        
        caption_text = (
            f"{header_text}\n\n"
            f"📝 **{title_label}:** `{title}` ({year})\n"
            f"🌟 **রেটিং:** ⭐ `{rating}/10`\n"
            f"💾 **সাইজ:** `{file_size_mb} MB`\n\n"
            f"📖 **কাহিনী সংক্ষেপ (Overview):**\n"
            f"_{overview[:400]}..._\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🍿 সরাসরি বটের ইনবক্স থেকে ওয়ান-ক্লিকে ডাউনলোড করতে নিচের বাটনে চাপ দিন।"
        )
        
        # যদি পোস্টার ইমেজ থাকে তবে ফটো আকারে পোস্ট করা হবে
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            try:
                await client.send_photo(
                    chat_id=config.UPDATE_CHANNEL_ID,
                    photo=poster_url,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return
            except Exception as e:
                print(f"Failed to send poster photo: {e}")
                
    # যদি TMDb-তে কোনো তথ্য না পাওয়া যায় বা ফটো ফেইল করে, তবে সাধারণ টেক্সট আকারে পোস্ট হবে
    cleaned_title = clean_movie_title(file_name)
    fallback_text = (
        f"🎬 **নতুন ফাইল যুক্ত করা হয়েছে!** 🎬\n\n"
        f"📝 **ফাইলের নাম:** `{cleaned_title}`\n"
        f"💾 **ফাইলের সাইজ:** `{file_size_mb} MB`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🍿 সরাসরি বটের ইনবক্স থেকে ওয়ান-ক্লিকে ডাউনলোড করতে নিচের বাটনে চাপ দিন।"
    )
    try:
        await client.send_message(
            chat_id=config.UPDATE_CHANNEL_ID,
            text=fallback_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Failed to send fallback update message: {e}")
