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

# ২. প্রফেশনাল মোবাইল-রেসপন্সিভ মিনি অ্যাপের HTML টেমপ্লেট
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Movie</title>
    <style>
        body {{
            background-color: #121212;
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            text-align: center;
            padding: 20px;
            margin: 0;
        }}
        .container {{
            max-width: 450px;
            margin: 50px auto;
            background: #1e1e1e;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        }}
        h2 {{ color: #e50914; margin-bottom: 5px; font-size: 24px; }}
        .movie-title {{ font-size: 16px; color: #aaaaaa; margin-bottom: 30px; word-wrap: break-word; }}
        .step {{
            background: #2b2b2b;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
            text-align: left;
            border-left: 5px solid #e50914;
        }}
        .btn {{
            display: block;
            width: 100%;
            padding: 15px 0;
            margin: 10px 0;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            transition: 0.3s;
        }}
        .btn-ad {{
            background-color: #e50914;
            color: white;
        }}
        .btn-ad:hover {{ background-color: #b20710; }}
        .btn-download {{
            background-color: #0088cc;
            color: white;
            opacity: 0.5;
            pointer-events: none; /* প্রথমে এটি লক থাকবে */
        }}
        .btn-download.active {{
            opacity: 1;
            pointer-events: auto; /* অ্যাড দেখার পর এটি আনলক হবে */
            box-shadow: 0 0 15px rgba(0, 136, 204, 0.6);
        }}
    </style>
    <script>
        function unlockDownload() {{
            // ১. ইউজারের নতুন ট্যাবে বিজ্ঞাপনের লিংক ওপেন করা
            window.open("{ad_link}", "_blank");
            
            // ২. ডাউনলোড বাটনটি আনলক করা
            setTimeout(function() {{
                var downloadBtn = document.getElementById("download-btn");
                downloadBtn.classList.add("active");
                downloadBtn.innerText = "⚡️ Get Movie File";
                document.getElementById("step-text").innerText = "ধাপ ২: নিচে আনলক হওয়া বাটনে ক্লিক করে ফাইলটি সংগ্রহ করুন!";
            }}, 2000); // ২ সেকেন্ড পর আনলক হবে
        }}
    </script>
</head>
<body>
    <div class="container">
        <h2>CTG MOVIE DOWNLOAD</h2>
        <div class="movie-title">🎬 {movie_title}</div>
        
        <div id="step-text" class="step">
            ধাপ ১: প্রথমে নিচের লাল বাটনে ক্লিক করে ডাউনলোড লিংকটি আনলক (Unlock) করুন।
        </div>
        
        <!-- অ্যাড বাটন (এটিতে ক্লিক করলে ডিরেক্ট অ্যাড ওপেন হবে এবং ডাউনলোড বাটন সচল হবে) -->
        <button class="btn btn-ad" onclick="unlockDownload()">🔓 Unlock Download Link</button>
        
        <!-- আসল ডাউনলোড বাটন (টেলিগ্রাম বটের চ্যাটে ফেরত নিয়ে যাবে) -->
        <a id="download-btn" class="btn btn-download" href="https://t.me/{bot_username}?start={file_db_id}">🔒 Locked</a>
    </div>
</body>
</html>
"""

# ৩. কাস্টম ওয়েব সার্ভার রাউটিং
class DummyWebServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        # যদি ইউজার ডাউনলোডের লিংকে ক্লিক করে
        if parsed_url.path == "/download":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            movie_title = query_params.get("title", ["Movie File"])[0]
            
            # র্যান্ডমলি একটি অ্যাড লিংক সিলেক্ট করা আয়ের জন্য
            ad_link = random.choice(config.DIRECT_AD_LINKS)
            
            # ডাইনামিক ডাটা দিয়ে HTML পেজ তৈরি
            response_html = HTML_TEMPLATE.format(
                movie_title=movie_title,
                file_db_id=file_db_id,
                bot_username=config.BOT_USERNAME,
                ad_link=ad_link
            )
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response_html.encode("utf-8"))
            
        else:
            # Render-এর নিয়মিত হেলথ চেকের জন্য বেসিক রেসপন্স
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"CTG Movie Bot is running alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyWebServer)
    print(f"ওয়েব সার্ভার এবং মিনি অ্যাপ পোর্ট {port}-এ চালু হয়েছে।")
    server.serve_forever()

# ব্যাকগ্রাউন্ড থ্রেডে সার্ভার চালু করা
threading.Thread(target=run_web_server, daemon=True).start()

# ৪. পাইগ্রাম বট ক্লায়েন্ট
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
