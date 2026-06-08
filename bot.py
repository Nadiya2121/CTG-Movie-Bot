# bot.py

import asyncio
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import random
import re
from string import Template

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client
import config

# ১. আল্ট্রা-প্রিমিয়াম নিয়ন আরজিবি মিনি অ্যাপ ডাউনলোড টেমপ্লেট
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Movie</title>
    <!-- টেলিগ্রামের অফিশিয়াল ওয়েব অ্যাপ স্ক্রিপ্ট -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {
            background-color: #0b0c10;
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            text-align: center;
            padding: 15px;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 95vh;
        }
        
        /* আরজিবি পালসিং বর্ডার অ্যানিমেশন */
        @keyframes borderGlow {
            0% { border-color: rgba(255, 0, 85, 0.4); box-shadow: 0 0 15px rgba(255, 0, 85, 0.2); }
            50% { border-color: rgba(0, 240, 255, 0.4); box-shadow: 0 0 15px rgba(0, 240, 255, 0.2); }
            100% { border-color: rgba(255, 0, 85, 0.4); box-shadow: 0 0 15px rgba(255, 0, 85, 0.2); }
        }
        
        .container {
            width: 100%;
            max-width: 400px;
            background: rgba(30, 30, 38, 0.65);
            padding: 30px 20px;
            border-radius: 24px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 0, 85, 0.4);
            animation: borderGlow 6s infinite ease-in-out;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
        }
        
        h2 { 
            color: #ff0055; 
            margin: 0 0 15px 0; 
            font-size: 28px; 
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 0 12px rgba(255, 0, 85, 0.4);
        }
        
        /* প্রফেশনাল ফাইল ইনফরমেশন কার্ড */
        .info-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: left;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 13px;
        }
        .info-row:last-child { margin-bottom: 0; }
        .info-label { color: #9ca3af; }
        .info-value { color: #ffffff; font-weight: 600; }
        .info-value.neon-green { color: #00ff88; text-shadow: 0 0 8px rgba(0, 255, 136, 0.2); }
        .info-value.neon-blue { color: #00f0ff; text-shadow: 0 0 8px rgba(0, 240, 255, 0.2); }
        .info-value.neon-red { color: #ff0055; text-shadow: 0 0 8px rgba(255, 0, 85, 0.2); }
        
        .step-card {
            background: rgba(255, 255, 255, 0.04);
            padding: 14px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-size: 13px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #d1d5db;
            line-height: 1.4;
        }
        
        .btn {
            display: block;
            width: 100%;
            padding: 16px 0;
            margin: 15px 0;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .btn-ad {
            background: linear-gradient(135deg, #ff0055, #b3003b);
            color: white;
            box-shadow: 0 4px 15px rgba(255, 0, 85, 0.4);
        }
        .btn-ad:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 0, 85, 0.6);
        }
        .btn-download {
            background-color: #1f2937;
            color: #4b5563;
            border: 1px solid #374151;
            pointer-events: none;
        }
        .btn-download.active {
            background: linear-gradient(135deg, #00ff88, #009951);
            color: #000000;
            font-weight: 800;
            pointer-events: auto;
            box-shadow: 0 0 25px rgba(0, 255, 136, 0.7);
            border: none;
        }
        
        .success-badge {
            display: none;
            background: rgba(0, 255, 136, 0.08);
            color: #00ff88;
            padding: 12px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid rgba(0, 255, 136, 0.2);
            margin-bottom: 15px;
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.1);
        }
        
        .support-note {
            font-size: 11px;
            color: #6b7280;
            margin-top: 20px;
            line-height: 1.4;
            text-align: center;
        }
        
        #loader {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 70vh;
        }
        .loader-title {
            font-size: 18px;
            font-weight: bold;
            color: #00f0ff;
            text-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
            margin-bottom: 15px;
        }
        .progress-container {
            width: 80%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .progress-bar {
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, #ff0055, #00f0ff);
            box-shadow: 0 0 10px #00f0ff;
            transition: width 0.05s ease-out;
        }
        .loader-percent {
            font-size: 14px;
            margin-top: 10px;
            color: #9ca3af;
        }
    </style>
    <script>
        let tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        window.addEventListener("DOMContentLoaded", () => {
            let percent = 0;
            let bar = document.getElementById("bar");
            let pText = document.getElementById("percent-text");
            
            let interval = setInterval(() => {
                percent += 5;
                if (percent <= 100) {
                    bar.style.width = percent + "%";
                    pText.innerText = percent + "% Completed";
                } else {
                    clearInterval(interval);
                    document.getElementById("loader").style.display = "none";
                    document.getElementById("app-content").style.display = "block";
                }
            }, 70);
        });

        function unlockDownload() {
            window.open("$ad_link", "_blank");
            
            document.getElementById("btn-ad").style.display = "none";
            document.getElementById("success-badge").style.display = "block";
            
            var downloadBtn = document.getElementById("download-btn");
            downloadBtn.classList.add("active");
            downloadBtn.innerText = "⚡️ Get Movie File";
            document.getElementById("step-text").innerText = "লিংকটি সচল হয়েছে! নিচের বাটনে চাপ দিন।";
        }

        function getMovie() {
            tg.openTelegramLink("https://t.me/$bot_username?start=get_$file_db_id");
            setTimeout(function() {
                tg.close();
            }, 500);
        }
    </script>
</head>
<body>
    <div id="loader">
        <div class="loader-title">🔍 Generating Secure CDN Link...</div>
        <div class="progress-container">
            <div id="bar" class="progress-bar"></div>
        </div>
        <div id="percent-text" class="loader-percent">0% Completed</div>
    </div>

    <div id="app-content" class="container" style="display: none;">
        <h2>CTG PREMIUM SEARCH</h2>
        
        <div class="info-card">
            <div class="info-row">
                <span class="info-label">📊 Database Inventory:</span>
                <span class="info-value neon-blue">$total_files+ Movies</span>
            </div>
            <div class="info-row">
                <span class="info-label">👥 Active Users:</span>
                <span class="info-value neon-green">$total_users+ Connected</span>
            </div>
            <div class="info-row">
                <span class="info-label">💾 Storage Used:</span>
                <span class="info-value neon-red">$used_mb MB / 512 MB</span>
            </div>
            <div class="info-row">
                <span class="info-label">📉 Free Storage Left:</span>
                <span class="info-value neon-green">$free_mb MB ($free_percent% Free)</span>
            </div>
            <div class="info-row">
                <span class="info-label">🌐 Server Port Speed:</span>
                <span class="info-value">1 Gbps Unlimited</span>
            </div>
        </div>
        
        <div id="step-text" class="step-card">
            ধাপ ১: প্রথমে নিচের লাল বাটনে ক্লিক করে বিজ্ঞাপন পেজটি লোড করুন এবং ডাউনলোড লিংকটি আনলক করুন।
        </div>
        
        <div id="success-badge" class="success-badge">✅ Link Unlocked successfully!</div>
        
        <button id="btn-ad" class="btn btn-ad" onclick="unlockDownload()">🔓 Unlock Download Link</button>
        <button id="download-btn" class="btn btn-download" onclick="getMovie()">🔒 Locked</button>
        
        <div class="support-note">
            বটের হাই-স্পিড সার্ভার খরচ চালাতে এবং আপনাকে সম্পূর্ণ ফ্রিতে সেবা দিতে আমাদের একটি ছোট্ট বিজ্ঞাপন দেখতে হয়। সহযোগিতার জন্য ধন্যবাদ!
        </div>
    </div>
</body>
</html>
""")

# ২. প্রিমিয়াম স্ট্রিমিং প্লেয়ার ওয়েব পেজ টেমপ্লেট (HTML_STREAM_TEMPLATE)
HTML_STREAM_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Movie - VIP Player</title>
    <!-- টেলিগ্রাম ওয়েব অ্যাপ স্ক্রিপ্ট -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {
            background-color: #0b0c10;
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 15px;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 95vh;
        }
        .container {
            width: 100%;
            max-width: 500px;
            background: rgba(30, 30, 38, 0.65);
            padding: 25px 15px;
            border-radius: 24px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 240, 255, 0.4);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
            text-align: center;
        }
        h2 { 
            color: #00f0ff; 
            margin: 0 0 15px 0; 
            font-size: 24px; 
            font-weight: 800;
            text-transform: uppercase;
            text-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
        }
        .video-player-box {
            width: 100%;
            background: #000;
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 20px;
            aspect-ratio: 16/9;
        }
        video {
            width: 100%;
            height: 100%;
        }
        .info-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 20px;
            text-align: left;
            font-size: 13px;
        }
        .file-title {
            color: #00ff88;
            font-weight: bold;
            word-break: break-all;
        }
        .btn-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }
        .btn {
            padding: 12px 10px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            color: white;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }
        .btn-vlc { background: #e65c00; }
        .btn-mx { background: #0080ff; }
        .btn-playit { background: #33cc33; }
        .btn-close { background: #374151; grid-column: span 2; }
        .btn:hover { transform: scale(1.02); filter: brightness(1.1); }
        .note {
            font-size: 11px;
            color: #9ca3af;
            line-height: 1.4;
        }
    </style>
    <script>
        let tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        function closeApp() {
            tg.close();
        }
    </script>
</head>
<body>
    <div class="container">
        <h2>👑 VIP Streaming Player</h2>
        
        <div class="video-player-box">
            <!-- HTML5 Player (MP4 ফাইল সরাসরি প্লে হবে) -->
            <video controls poster="https://github.com/NBBotz/Images/blob/main/Lucia-Filter-Bot.jpeg?raw=true">
                <source src="$stream_url" type="video/mp4">
                Your browser does not support HTML5 video streaming.
            </video>
        </div>
        
        <div class="info-card">
            <div>🎬 <span class="file-title">$file_name</span></div>
            <div style="margin-top: 5px; color: #9ca3af;">💾 Size: <b>$file_size MB</b> | Status: <b style="color: #00ff88;">VIP Streaming Enabled ⚡️</b></div>
        </div>
        
        <div style="font-size: 12px; font-weight: bold; margin-bottom: 10px; color: #00f0ff;">👉 ব্রাউজারে প্লে না হলে বা MKV/অডিও সমস্যা হলে নিচের প্লেয়ারে ওপেন করুন:</div>
        
        <div class="btn-grid">
            <a href="vlc://$stream_url" class="btn btn-vlc">🧡 Open in VLC</a>
            <a href="intent:$stream_url#Intent;package=com.mxtech.videoplayer.ad;S.title=$file_name;end" class="btn btn-mx">💙 Open in MX Player</a>
            <a href="intent:$stream_url#Intent;package=com.player.videoplayer;S.title=$file_name;end" class="btn btn-playit">💚 Open in Playit</a>
            <button class="btn btn-close" onclick="closeApp()">🛑 Close Player</button>
        </div>
        
        <div class="note">
            ⚠️ <b>পরামর্শ:</b> MKV ফাইল বা ডুয়াল অডিও মুভিগুলো নির্বিঘ্নে দেখতে এবং বাংলা সাবটাইটেল সাপোর্ট করতে <b>VLC Player</b> অথবা <b>MX Player</b> ব্যবহার করুন।
        </div>
    </div>
</body>
</html>
""")

class DummyWebServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        # ১. মিনি অ্যাপ ডাউনলোড বাটন পেইজ
        if parsed_url.path == "/download":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            
            base_ad = random.choice(config.DIRECT_AD_LINKS)
            rand_id = random.randint(100000, 999999)
            rand_click = random.randint(1000000, 9999999)
            
            if "?" in base_ad:
                ad_link = f"{base_ad}&click_id={rand_click}&sub_id={rand_id}"
            else:
                ad_link = f"{base_ad}?click_id={rand_click}&sub_id={rand_id}"
            
            total_files, total_users, used_mb, free_mb, free_percent = 0, 0, 0.0, 512.0, 100.0
            if app.loop and app.loop.is_running():
                try:
                    from database import get_detailed_stats
                    future = asyncio.run_coroutine_threadsafe(get_detailed_stats(), app.loop)
                    total_files, total_users, used_mb, free_mb, free_percent = future.result(timeout=2)
                except Exception as e:
                    print(f"Failed to fetch live stats: {e}")
            
            response_html = HTML_TEMPLATE.safe_substitute(
                file_db_id=file_db_id,
                bot_username=config.BOT_USERNAME,
                ad_link=ad_link,
                total_files=f"{total_files:,}",
                total_users=f"{total_users:,}",
                used_mb=used_mb,
                free_mb=free_mb,
                free_percent=free_percent
            )
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response_html.encode("utf-8"))

        # ২. প্রিমিয়াম স্ট্রিমিং প্লেয়ার পেইজ
        elif parsed_url.path == "/play":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            
            file_data = None
            if app.loop and app.loop.is_running():
                try:
                    from database import get_file_by_db_id
                    future = asyncio.run_coroutine_threadsafe(get_file_by_db_id(file_db_id), app.loop)
                    file_data = future.result(timeout=2)
                except Exception as e:
                    print(f"Failed to fetch file for streaming: {e}")
            
            if not file_data:
                self.send_error(404, "File Not Found")
                return
            
            raw_url = config.WEB_URL.strip().replace("https://", "").replace("http://", "").rstrip("/")
            stream_url = f"https://{raw_url}/stream?id={file_db_id}"
            file_name = file_data.get("file_name", "Movie File")
            
            # অ্যানড্রয়েড ইন্টেন্ট এবং প্লেয়ারের জটিলতা এড়াতে ফালতু স্পেশাল ক্যারেক্টার ক্লিন করা হলো
            safe_file_name = re.sub(r'[^a-zA-Z0-9\s\.\-_]', '', file_name)
            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
            
            response_html = HTML_STREAM_TEMPLATE.safe_substitute(
                stream_url=stream_url,
                file_name=safe_file_name,
                file_size=file_size
            )
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response_html.encode("utf-8"))

        # ৩. প্রিমিয়াম ডাইরেক্ট লাইভ ভিডিও স্ট্রিমিং এন্ডপয়েন্ট (HTTP 206 Partial Content সহ)
        elif parsed_url.path == "/stream":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            
            file_data = None
            if app.loop and app.loop.is_running():
                try:
                    from database import get_file_by_db_id
                    future = asyncio.run_coroutine_threadsafe(get_file_by_db_id(file_db_id), app.loop)
                    file_data = future.result(timeout=2)
                except Exception as e:
                    print(f"Failed to fetch file metadata for stream: {e}")
            
            if not file_data:
                self.send_error(404, "File Not Found")
                return
            
            file_id = file_data["file_id"]
            file_size = file_data["file_size"]
            
            # HTTP Range রিকোয়েস্ট হ্যান্ডেল করা হচ্ছে (ভিডিওর যেকোনো সেকেন্ডে টেনে টেনে দেখার জন্য)
            range_header = self.headers.get("Range")
            start = 0
            end = file_size - 1
            
            if range_header:
                match = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if match:
                    start = int(match.group(1))
                    if match.group(2):
                        end = int(match.group(2))
            
            if start > end or start >= file_size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            
            content_len = end - start + 1
            
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(content_len))
            self.send_header("Content-Disposition", f'inline; filename="{file_data["file_name"]}"')
            self.end_headers()
            
            # ব্যাকগ্রাউন্ডে পাইরোগ্রাম দিয়ে ফাইল চ্যাঙ্ক রিমোটলি রিড করে স্ট্রিম করা হচ্ছে
            if app.loop and app.loop.is_running():
                async def stream_helper():
                    try:
                        # ১ এমবি করে চ্যাঙ্ক সাইজ নির্ধারণ (ফাস্ট লোডিংয়ের জন্য)
                        chunk_size = 1024 * 1024
                        offset_parts = start // chunk_size
                        bytes_to_skip = start % chunk_size
                        bytes_sent = 0
                        
                        async for chunk in app.stream_media(file_id, offset=offset_parts):
                            if bytes_to_skip > 0:
                                if len(chunk) > bytes_to_skip:
                                    chunk = chunk[bytes_to_skip:]
                                    bytes_to_skip = 0
                                else:
                                    bytes_to_skip -= len(chunk)
                                    continue
                            
                            if bytes_sent + len(chunk) > content_len:
                                chunk = chunk[:content_len - bytes_sent]
                            
                            self.wfile.write(chunk)
                            bytes_sent += len(chunk)
                            
                            if bytes_sent >= content_len:
                                break
                    except Exception:
                        # কানেকশন ক্লোজ হলে বা ইউজার প্লেয়ার বন্ধ করলে
                        pass
                
                future = asyncio.run_coroutine_threadsafe(stream_helper(), app.loop)
                future.result()  # স্ট্রিম শেষ হওয়া পর্যন্ত ওয়েট করবে
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"CTG Movie Bot is running alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyWebServer)
    print(f"ওয়েব সার্ভার এবং মিনি অ্যাপ পোর্ট {port}-এ চালু হয়েছে।")
    server.serve_forever()

t = threading.Thread(target=run_web_server, daemon=True)
t.start()

plugins = dict(root="plugins")

app = Client(
    "movie_search_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=plugins
)

if __name__ == "__main__":
    print("অভিনন্দন! আপনার মুভি বটটি সফলভাবে চালু হয়েছে।")
    app.run()
