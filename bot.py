# bot.py

import asyncio
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# ১. পাইথনের নতুন ভার্সনে Pyrogram এর ইভেন্ট লুপ এরর এড়ানোর কোড
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client
import config


# ২. ওয়েব সার্ভার লজিক (Render-এর পোর্ট বাইন্ডিং সফল করার জন্য)
class DummyWebServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running alive!") # Render এই রেসপন্স পেলে বুঝবে বট সচল আছে

def run_web_server():
    # Render স্বয়ংক্রিয়ভাবে একটি পোর্ট দেয়, না পেলে ডিফল্ট ৮০৮০ ব্যবহার করবে
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyWebServer)
    print(f"ওয়েব সার্ভার চালু হয়েছে পোর্ট নম্বর: {port}")
    server.serve_forever()


# ৩. ব্যাকগ্রাউন্ড থ্রেডে ওয়েব সার্ভারটি চালু করা
threading.Thread(target=run_web_server, daemon=True).start()


# ৪. মূল পাইগ্রাম বট ক্লায়েন্ট সেটআপ
plugins = dict(root="plugins")

app = Client(
    "movie_search_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=plugins
)

if __name__ == "__main__":
    print("অভিনন্দন! আপনার মুভি বটটি ওয়েব সার্ভারসহ সফলভাবে চালু হয়েছে।")
    app.run()
