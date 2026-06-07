# bot.py

import asyncio
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import random

# ১. পাইথনের নতুন ভার্সনে Pyrogram এর ইভেন্ট লুপ এরর এড়ানোর কোড
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client
import config

# ২. আল্ট্রা-প্রিমিয়াম নিয়ন আরজিবি মিনি অ্যাপ টেমপ্লেট (Netflix/Glowing Style)
# .format() এর এরর এড়াতে CSS এবং JS এর সকল সাধারণ ব্র্যাকেটকে Double Brackets {{ }} করা হয়েছে।
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Movie</title>
    <!-- টেলিগ্রামের অফিশিয়াল ওয়েব অ্যাপ স্ক্রিপ্ট (ইনস্ট্যান্ট ক্লোজ করার জন্য আবশ্যক) -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
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
        }}
        
        /* আরজিবি পালসিং বর্ডার অ্যানিমেশন */
        @keyframes borderGlow {{
            0% {{ border-color: rgba(255, 0, 85, 0.4); box-shadow: 0 0 15px rgba(255, 0, 85, 0.2); }}
            50% {{ border-color: rgba(0, 240, 255, 0.4); box-shadow: 0 0 15px rgba(0, 240, 255, 0.2); }}
            100% {{ border-color: rgba(255, 0, 85, 0.4); box-shadow: 0 0 15px rgba(255, 0, 85, 0.2); }}
        }}
        
        .container {{
            width: 100%;
            max-width: 400px;
            background: rgba(30, 30, 38, 0.65);
            padding: 30px 20px;
            border-radius: 24px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 0, 85, 0.4);
            animation: borderGlow 6s infinite ease-in-out;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
        }}
        
        h2 {{ 
            color: #ff0055; 
            margin: 0 0 15px 0; 
            font-size: 28px; 
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            text-shadow: 0 0 12px rgba(255, 0, 85, 0.4);
        }}
        
        /* প্রফেশনাল ফাইল ইনফরমেশন কার্ড */
        .info-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: left;
        }
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .info-row:last-child {{ margin-bottom: 0; }}
        .info-label {{ color: #9ca3af; }}
        .info-value {{ color: #ffffff; font-weight: 600; }}
        .info-value.neon-green {{ color: #00ff88; text-shadow: 0 0 8px rgba(0, 255, 136, 0.2); }}
        
        .step-card {{
            background: rgba(255, 255, 255, 0.04);
            padding: 14px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-size: 13px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #d1d5db;
            line-height: 1.4;
        }}
        
        /* বাটন স্টাইলিং ও অ্যানিমেশন */
        .btn {{
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
        }}
        .btn-ad {{
            background: linear-gradient(135deg, #ff0055, #b3003b);
            color: white;
            box-shadow: 0 4px 15px rgba(255, 0, 85, 0.4);
        }}
        .btn-ad:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 0, 85, 0.6);
        }}
        .btn-download {{
            background-color: #1f2937;
            color: #4b5563;
            border: 1px solid #374151;
            pointer-events: none;
        }}
        .btn-download.active {{
            background: linear-gradient(135deg, #00ff88, #009951);
            color: #000000;
            font-weight: 800;
            pointer-events: auto;
            box-shadow: 0 0 25px rgba(0, 255, 136, 0.7);
            border: none;
        }}
        
        .success-badge {{
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
        }}
        
        /* আর্নিং সাপোর্ট নোটিশ */
        .support-note {{
            font-size: 11px;
            color: #6b7280;
            margin-top: 20px;
            line-height: 1.4;
            text-align: center;
        }}
        
        /* স্ক্যানিং লোডার স্ক্রিন */
        #loader {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 70vh;
        }}
        .loader-title {{
            font-size: 18px;
            font-weight: bold;
            color: #00f0ff;
            text-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
            margin-bottom: 15px;
        }}
        .progress-container {{
            width: 80%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .progress-bar {{
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, #ff0055, #00f0ff);
            box-shadow: 0 0 10px #00f0ff;
            transition: width 0.05s ease-out;
        }}
        .loader-percent {{
            font-size: 14px;
            margin-top: 10px;
            color: #9ca3af;
        }}
    </style>
    <script>
        let tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        // ১.৫ সেকেন্ডের ডাইনামিক ফাইল স্ক্যানিং অ্যানিমেশন
        window.addEventListener("DOMContentLoaded", () => {{
            let percent = 0;
            let bar = document.getElementById("bar");
            let pText = document.getElementById("percent-text");
            
            let interval = setInterval(() => {{
                percent += 5;
                if (percent <= 100) {{
                    bar.style.width = percent + "%";
                    pText.innerText = percent + "% Completed";
                }} else {{
                    clearInterval(interval);
                    // স্ক্যানিং শেষ হলে লোডার বন্ধ করে মেইন পেজ সচল করা হবে
                    document.getElementById("loader").style.display = "none";
                    document.getElementById("app-content").style.display = "block";
                }}
            }}, 70); // ১.৪ সেকেন্ড সময় নেবে সম্পূর্ণ হতে
        }});

        function unlockDownload() {{
            window.open("{ad_link}", "_blank");
            
            document.getElementById("btn-ad").style.display = "none";
            document.getElementById("success-badge").style.display = "block";
            
            var downloadBtn = document.getElementById("download-btn");
            downloadBtn.classList.add("active");
            downloadBtn.innerText = "⚡️ Get Movie File";
            document.getElementById("step-text").innerText = "লিংকটি সচল হয়েছে! নিচের বাটনে চাপ দিন।";
        }}

        function getMovie() {{
            tg.openTelegramLink("https://t.me/{bot_username}?start=get_{file_db_id}");
            setTimeout(function() {{
                tg.close();
            }}, 500);
        }}
    </script>
</head>
<body>
    <!-- লোডিং স্ক্রিন (১.৫ সেকেন্ডের জন্য ফাইল ভেরিফাই দেখাবে) -->
    <div id="loader">
        <div class="loader-title">🔍 Generating Secure CDN Link...</div>
        <div class="progress-container">
            <div id="bar" class="progress-bar"></div>
        </div>
        <div id="percent-text" class="loader-percent">0% Completed</div>
    </div>

    <!-- মূল কনটেন্ট (প্রথমে হাইড থাকবে, স্ক্যানিং শেষে চমৎকারভাবে ফেড-ইন হবে) -->
    <div id="app-content" class="container" style="display: none;">
        <h2>CTG PREMIUM SEARCH</h2>
        
        <!-- প্রফেশনাল ফাইল ইনফরমেশন কার্ড -->
        <div class="info-card">
            <div class="info-row">
                <span class="info-label">🚀 Download Speed:</span>
                <span class="info-value">1 Gbps Unlimited</span>
            </div>
            <div class="info-row">
                <span class="info-label">🛡 Safety Status:</span>
                <span class="info-value neon-green">Safe & Verified ✅</span>
            </div>
            <div class="info-row">
                <span class="info-label">🌐 Server Status:</span>
                <span class="info-value neon-green">Active Premium CDN</span>
            </div>
        </div>
        
        <div id="step-text" class="step-card">
            ধাপ ১: প্রথমে নিচের লাল বাটনে ক্লিক করে বিজ্ঞাপন পেজটি লোড করুন এবং ডাউনলোড লিংকটি আনলক করুন।
        </div>
        
        <div id="success-badge" class="success-badge">✅ Link Unlocked successfully!</div>
        
        <button id="btn-ad" class="btn btn-ad" onclick="unlockDownload()">🔓 Unlock Download Link</button>
        <button id="download-btn" class="btn btn-download" onclick="getMovie()">🔒 Locked</button>
        
        <!-- আর্নিং সাপোর্ট নোটিশ -->
        <div class="support-note">
            বটের হাই-স্পিড সার্ভার খরচ চালাতে এবং আপনাকে সম্পূর্ণ ফ্রিতে সেবা দিতে আমাদের একটি ছোট্ট বিজ্ঞাপন দেখতে হয়। সহযোগিতার জন্য ধন্যবাদ!
        </div>
    </div>
</body>
</html>
"""

class DummyWebServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/download":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            
            ad_link = random.choice(config.DIRECT_AD_LINKS)
            
            response_html = HTML_TEMPLATE.format(
                file_db_id=file_db_id,
                bot_username=config.BOT_USERNAME,
                ad_link=ad_link
            )
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response_html.encode("utf-8"))
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

# Daemon Thread-এ সার্ভার সচল করা
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
