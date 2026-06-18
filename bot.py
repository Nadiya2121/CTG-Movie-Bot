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

# ১. সাধারণ (Free) ইউজারদের জন্য মিনি অ্যাপ ডাউনলোড টেমপ্লেট (নতুন নিওন-গ্লোয়িং ড্যাশবোর্ড সহ)
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
            font-size: 26px; 
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 0 12px rgba(255, 0, 85, 0.4);
        }
        
        /* সম্পূর্ণ রি-ডিজাইনকৃত প্রিমিয়াম ড্যাশবোর্ড কার্ড */
        .info-card {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01));
            border: 1px solid rgba(0, 240, 255, 0.15);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: left;
            box-shadow: inset 0 0 15px rgba(0, 240, 255, 0.05);
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 13px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            padding-bottom: 8px;
        }
        .info-row:last-child { 
            margin-bottom: 0; 
            border-bottom: none;
            padding-bottom: 0;
        }
        .info-label { 
            color: #9ca3af; 
            display: flex;
            align-items: center;
        }
        
        /* লাইভ স্ট্যাটাস ব্লিংকিং ডট */
        .status-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-dot.blue { background-color: #00f0ff; box-shadow: 0 0 8px #00f0ff; }
        .status-dot.green { background-color: #00ff88; box-shadow: 0 0 8px #00ff88; }
        .status-dot.purple { background-color: #bd00ff; box-shadow: 0 0 8px #bd00ff; }
        .status-dot.safe { background-color: #00ffaa; box-shadow: 0 0 8px #00ffaa; }
        
        .info-value { color: #ffffff; font-weight: 700; font-family: monospace; font-size: 14px; }
        .neon-green { color: #00ff88; text-shadow: 0 0 8px rgba(0, 255, 136, 0.3); }
        .neon-blue { color: #00f0ff; text-shadow: 0 0 8px rgba(0, 240, 255, 0.3); }
        .neon-purple { color: #bd00ff; text-shadow: 0 0 8px rgba(189, 0, 255, 0.3); }
        
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
                <span class="info-label"><span class="status-dot blue"></span> 📊 Database Inventory:</span>
                <span class="info-value neon-blue">$total_files+ Movies</span>
            </div>
            <div class="info-row">
                <span class="info-label"><span class="status-dot green"></span> 👥 Connected Users:</span>
                <span class="info-value neon-green">$total_users+ Online</span>
            </div>
            <div class="info-row">
                <span class="info-label"><span class="status-dot purple"></span> 💾 Storage Used:</span>
                <span class="info-value neon-purple">$used_storage</span>
            </div>
            <div class="info-row">
                <span class="info-label"><span class="status-dot safe"></span> 📉 Free Buffer Space:</span>
                <span class="info-value neon-green">$free_storage</span>
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

# ২. প্রিমিয়াম (VIP) ইউজারদের জন্য ড্যাশবোর্ড
HTML_VIP_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VIP Access Control Panel</title>
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
        
        @keyframes vipGlow {
            0% { border-color: rgba(0, 255, 136, 0.4); box-shadow: 0 0 15px rgba(0, 255, 136, 0.2); }
            50% { border-color: rgba(0, 240, 255, 0.4); box-shadow: 0 0 15px rgba(0, 240, 255, 0.2); }
            100% { border-color: rgba(0, 255, 136, 0.4); box-shadow: 0 0 15px rgba(0, 255, 136, 0.2); }
        }
        
        .container {
            width: 100%;
            max-width: 400px;
            background: rgba(30, 30, 38, 0.7);
            padding: 30px 20px;
            border-radius: 24px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 255, 136, 0.5);
            animation: vipGlow 6s infinite ease-in-out;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
        }
        
        .vip-badge {
            display: inline-block;
            background: rgba(0, 255, 136, 0.1);
            color: #00ff88;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 800;
            border: 1px solid rgba(0, 255, 136, 0.3);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
            box-shadow: 0 0 10px rgba(0, 255, 136, 0.2);
        }
        
        h2 { 
            color: #00ff88; 
            margin: 0 0 15px 0; 
            font-size: 24px; 
            font-weight: 800;
            text-transform: uppercase;
            text-shadow: 0 0 12px rgba(0, 255, 136, 0.3);
        }
        
        .info-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 25px;
            text-align: left;
        }
        .info-title {
            font-weight: bold;
            color: #00f0ff;
            word-break: break-all;
            margin-bottom: 8px;
            font-size: 14px;
            line-height: 1.4;
        }
        .info-size {
            font-size: 12px;
            color: #9ca3af;
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
            color: white;
            transition: all 0.3s ease;
        }
        .btn-stream {
            background: linear-gradient(135deg, #00f0ff, #0072ff);
            box-shadow: 0 4px 15px rgba(0, 240, 255, 0.4);
        }
        .btn-stream:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 240, 255, 0.6);
        }
        .btn-download {
            background: linear-gradient(135deg, #00ff88, #009951);
            color: #000000;
            font-weight: 800;
            box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
        }
        .btn-download:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 255, 136, 0.6);
        }
        .btn-close {
            background: #1f2937;
            border: 1px solid #374151;
            color: #9ca3af;
        }
        .btn-close:hover {
            background: #374151;
            color: white;
        }
    </style>
    <script>
        let tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        function playOnline() {
            window.location.href = "/play?id=$file_db_id";
        }

        function getMovie() {
            tg.openTelegramLink("https://t.me/$bot_username?start=get_$file_db_id");
            setTimeout(function() {
                tg.close();
            }, 500);
        }
        
        function closeApp() {
            tg.close();
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="vip-badge">👑 VIP Premium Active</div>
        <h2>CTG VIP MOVIE PANEL</h2>
        
        <div class="info-card">
            <div class="info-title">🎬 $file_name</div>
            <div class="info-size">💾 Size: <b>$file_size MB</b></div>
        </div>
        
        <button class="btn btn-stream" onclick="playOnline()">🍿 Watch Online / Stream</button>
        <button class="btn btn-download" onclick="getMovie()">⚡️ Get File in Telegram</button>
        <button class="btn btn-close" onclick="closeApp()">🛑 Close Panel</button>
    </div>
</body>
</html>
""")

# ৩. প্রিমিয়াম স্ট্রিমিং প্লেয়ার ওয়েব পেজ টেমপ্লেট
HTML_STREAM_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$file_name - ᴘʀɪᴍᴇ ɴᴇᴛᴡᴏʀᴋ</title>
    <link class="fav-icon" rel="icon" href="https://i.ibb.co/Hh4kF2b/icon.png" type="image/x-icon">
    
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght=500;600;700;800&family=Poppins:wght=400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <!-- Plyr CSS -->
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <script src="https://cdn.tailwindcss.com"></script>
    
    <style>
        :root {
            --bg-body: #0b0f15;
            --bg-card: #121824;
            --bg-btn: #1a2232;
            --text-primary: #ffffff;
            --border-accent: #00e5ff;
        }
        body.light {
            --bg-body: #f1f5f9;
            --bg-card: #ffffff;
            --bg-btn: #e2e8f0;
            --text-primary: #1e293b;
            --border-accent: #2563eb;
        }

        :root {
            --plyr-color-main: var(--border-accent);
            --plyr-range-track-height: 4px; 
            --plyr-range-thumb-height: 14px; 
        }
        .plyr__progress {
            left: 0 !important; right: 0 !important; bottom: 0 !important;
            position: absolute !important; width: 100% !important; padding: 0 !important; margin: 0 !important; z-index: 10;
        }
        .plyr--video .plyr__controls { padding-bottom: 15px !important; }

        body { 
            background-color: var(--bg-body) !important; color: var(--text-primary) !important; 
            font-family: 'Poppins', sans-serif; transition: all 0.4s ease;
        }

        @keyframes bounce-icon { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
        @keyframes pulse-icon { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.15); } }
        @keyframes wiggle-icon { 0%, 100% { transform: rotate(0deg); } 25% { transform: rotate(-12deg); } 75% { transform: rotate(12deg); } }
        @keyframes beat-icon { 0%, 100% { transform: scale(1); } 15% { transform: scale(1.25); } 30% { transform: scale(1); } 45% { transform: scale(1.25); } 60% { transform: scale(1); } }

        .anim-bounce { animation: bounce-icon 2s infinite ease-in-out; }
        .anim-pulse { animation: pulse-icon 1.5s infinite ease-in-out; }
        .anim-wiggle { animation: wiggle-icon 2s infinite linear; }
        .anim-beat { animation: beat-icon 2.5s infinite ease-in-out; }

        .btn-hover { transition: all 0.3s ease; }
        .btn-hover:hover { transform: translateY(-2px); filter: brightness(1.2); }

        .theme-wrapper {
            position: fixed;
            top: 15px;
            right: 15px;
            z-index: 10000; 
        }

        .theme-btn {
            background: var(--bg-card);
            border: 2px solid var(--border-accent);
            padding: 8px 12px;
            border-radius: 50px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            font-weight: 800;
            color: var(--text-primary);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
        }

        @media (max-width: 480px) {
            .theme-btn span {
                display: none; 
            }
            .theme-btn {
                padding: 10px; 
            }
            .theme-wrapper {
                top: 10px;
                right: 10px;
            }
        }

        .fixed-copyright {
            position: fixed; bottom: 0; left: 0; width: 100%; background: var(--bg-body); 
            backdrop-filter: blur(10px); text-align: center; padding: 10px 0; font-size: 11px; font-weight: bold;
            border-top: 1px solid rgba(128, 128, 128, 0.2); z-index: 1000;
        }
        .dmca-floating { position: fixed; bottom: 65px; right: 20px; z-index: 999; }
        @keyframes dmca-color {
            0%, 100% { background-color: #00e5ff; color: #000; box-shadow: 0 0 20px rgba(0, 229, 255, 0.5); }
            50% { background-color: #2563eb; color: #fff; box-shadow: 0 0 20px rgba(37, 99, 235, 0.6); }
        }
        .dmca-btn { animation: dmca-color 4s infinite ease-in-out; }

        .bg-card-theme { background-color: var(--bg-card) !important; border-color: rgba(128, 128, 128, 0.2) !important; }
        .bg-btn-theme { background-color: var(--bg-btn) !important; border-color: rgba(128, 128, 128, 0.2) !important; }

        .plyr__controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .custom-player-btns {
            display: flex;
            gap: 15px;
            align-items: center;
            color: white;
            font-size: 18px;
        }

        .custom-player-btns button {
            background: none;
            border: none;
            color: #00e5ff;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .custom-player-btns button:active { transform: scale(0.9); }

        #brightness-popup {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.85);
            padding: 15px 25px;
            border-radius: 15px;
            border: 1px solid #00e5ff;
            z-index: 200;
            display: none; 
            flex-direction: column;
            align-items: center;
            gap: 10px;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
        }

        #brightness-popup span { font-size: 10px; font-weight: bold; color: #00e5ff; }

        #br-slider {
            -webkit-appearance: none;
            width: 150px;
            height: 4px;
            background: #333;
            border-radius: 5px;
            outline: none;
        }

        #br-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 15px; height: 15px;
            background: #00e5ff;
            border-radius: 50%;
            cursor: pointer;
        }
        #brightness-overlay {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: black;
            pointer-events: none;
            opacity: 0; 
            z-index: 1;
        }
    </style>
</head>
<body class="antialiased pb-32">

    <!-- Theme Toggle -->
    <div class="theme-wrapper">
    <button id="theme-toggle-btn" class="theme-btn">
        <i class="fa-solid fa-circle-half-stroke" id="theme-icon"></i>
        <span id="theme-text">LIGHT MODE</span>
    </button>
    </div>

    <!-- Header Section -->
    <header class="flex flex-col items-center pt-14 pb-4"> 
    <h1 class="text-3xl md:text-4xl font-extrabold flex items-center gap-3">
        <i class="fas fa-clapperboard text-rose-600 anim-beat"></i>
        <div><span class="text-pink-400">ᴘʀɪᴍᴇ</span> <span class="text-[#00e5ff]">ɴᴇᴛᴡᴏʀᴋ</span></div>
    </h1>
        <p class="text-[12px] text-gray-400 font-bold mt-1 anim-pulse uppercase tracking-widest">
            <i class="fas fa-bolt"></i> 𝐏𝐫𝐢𝐦𝐞 𝐒𝐭𝐫𝐞𝐚𝐦𝐢𝐧𝐠 𝐏𝐥𝐚𝐭𝐟𝐨𝐫𝐦
        </p>
    </header>

    <!-- Main Container -->
    <main class="w-full max-w-[600px] mx-auto px-4 z-10 relative">
        <div class="bg-card-theme rounded-xl overflow-hidden border shadow-2xl mb-6 flex flex-col relative">
            <div class="p-4 border-b bg-card-theme">
                <h2 class="text-[#00e5ff] text-[15px] font-bold flex items-start gap-2">
                    <i class="fas fa-play-circle mt-1 anim-pulse"></i> $file_name
                </h2>
            </div>

            <!-- Video Player -->
            <div class="relative w-full aspect-video bg-black overflow-hidden">
                <video id="player" playsinline controls preload="auto">
                    <source src="$stream_url" type="video/mp4" />
                </video>
            </div>

            <div class="flex justify-between p-3 px-5 text-[12px] font-black tracking-widest bg-card-theme">
                <div class="text-gray-400"><span class="text-green-500">SIZE:</span> $file_size MB</div>
                <div class="text-gray-400"><span class="text-green-500">TIME:</span> <span id="clock">00:00:00</span></div>
            </div>
        </div>

        <!-- Buttons Section -->
        <div class="space-y-4">
            <div class="grid grid-cols-2 gap-3">
                <button onclick="streamDownload()" class="btn-hover bg-[#e11d48] text-white rounded-full py-2.5 font-bold text-sm shadow-lg">
                    <i class="fas fa-bolt anim-bounce text-yellow-300 mr-1"></i> DOWNLOAD
                </button>
                <button onclick="watchOnline()" class="btn-hover bg-[#2563eb] text-white rounded-full py-2.5 font-bold text-sm shadow-lg">
                    <i class="fas fa-folder-open anim-wiggle mr-1"></i> WATCH ONLINE
                </button>
            </div>

            <div class="grid grid-cols-2 gap-3">
                <button onclick="vlc_player()" class="btn-hover bg-btn-theme border text-gray-200 rounded-full py-2 text-[12px] font-bold">
                    <i class="fas fa-video anim-beat text-orange-500 mr-1"></i> VLC PLAYER
                </button>
                <button onclick="mx_player()" class="btn-hover bg-btn-theme border text-gray-200 rounded-full py-2 text-[12px] font-bold">
                    <i class="fas fa-play anim-pulse text-blue-400 mr-1"></i> MX PLAYER
                </button>
            </div>
            
            <div class="grid grid-cols-2 gap-3">
                <button onclick="playit_player()" class="btn-hover bg-btn-theme border text-green-400 rounded-full py-2 text-[12px] font-bold">
                    <i class="fas fa-play-circle anim-beat mr-1"></i> PLAYIT
                </button>
                <button onclick="system_player()" class="btn-hover bg-btn-theme border text-yellow-400 rounded-full py-2 text-[12px] font-bold">
                    <i class="fas fa-desktop anim-pulse mr-1"></i> SYSTEM
                </button>
            </div>

            <div class="grid grid-cols-3 gap-2">
                <button onclick="km_player()" class="btn-hover bg-btn-theme border text-gray-200 rounded-full py-2 text-[10px] font-bold">
                    <i class="fas fa-film anim-bounce text-purple-400 mr-1"></i> KM PLAYER
                </button>
                <button onclick="kodi_player()" class="btn-hover bg-btn-theme border text-gray-200 rounded-full py-2 text-[10px] font-bold">
                    <i class="fas fa-border-all anim-pulse text-blue-300 mr-1"></i> KODI
                </button>
                <button onclick="n_player()" class="btn-hover bg-btn-theme border text-cyan-400 rounded-full py-2 text-[10px] font-bold">
                    <i class="fas fa-mobile-screen anim-wiggle mr-1"></i> NPLAYER
                </button>
            </div>
        </div>
    </main>

    
    <div class="dmca-floating">
        <button onclick="openModal()" class="dmca-btn px-6 py-2 rounded-full font-black text-xs uppercase shadow-2xl border border-white/20">
            <i class="fas fa-shield-halved anim-wiggle mr-1"></i> DMCA
        </button>
    </div>

    
    <div class="fixed-copyright">
        © 2022-2026 <a href="https://t.me/PrimeXBots" class="text-[#00e5ff] underline">ᴘʀɪᴍᴇXʙᴏᴛꜱ</a> | ꜱᴇᴄᴜʀᴇ ʙʏ ᴘʀɪᴍᴇ ɴᴇᴛᴡᴏʀᴋ 🤝
    </div>

    <!-- DMCA Modal -->
    <div id="infoModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[2000] hidden items-center justify-center p-4">
        <div id="modalBox" class="bg-[#121824] border-2 border-[#1f2937] rounded-2xl w-full max-w-lg overflow-hidden flex flex-col shadow-2xl">
            <div class="p-4 border-b border-gray-800 flex justify-between items-center bg-[#121824]">
                <h3 class="font-bold text-[#00e5ff] italic uppercase tracking-wider">
                    <i class="fas fa-circle-info mr-2"></i> Bot Information
                </h3>
                <button onclick="closeModal()" class="text-gray-400 hover:text-rose-500 text-2xl">&times;</button>
            </div>
            <div class="p-5 overflow-y-auto space-y-4 max-h-[70vh]">
                <div class="bg-gray-800/40 border-l-4 border-yellow-500 p-4 rounded-r-xl">
                    <h4 class="text-yellow-500 font-bold mb-1 uppercase text-xs">
                        <i class="fas fa-file-contract mr-1"></i> Disclaimer & DMCA
                    </h4>
                    <p class="text-[12px] text-gray-400 leading-relaxed font-medium">ᴀʟʟ ꜰɪʟᴇꜱ, ʟɪɴᴋꜱ, ᴀɴᴅ ᴍᴇᴅɪᴀ ᴀᴄᴄᴇꜱꜱᴇᴅ ᴛʜʀᴏᴜɢʜ ᴛʜɪꜱ ʙᴏᴛ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴘᴜʙʟɪᴄʟʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴏɴ ᴛᴇʟᴇɢʀᴀᴍ. ᴛʜɪꜱ ʙᴏᴛ ᴅᴏᴇꜱ ɴᴏᴛ ʜᴏꜱᴛ ᴏʀ ꜱᴛᴏʀᴇ ᴀɴʏ ꜰɪʟᴇꜱ ᴏɴ ɪᴛꜱ ᴏᴡɴ ꜱᴇʀᴠᴇʀꜱ.</p>
                </div>
                <div class="bg-gray-800/40 border-l-4 border-blue-500 p-4 rounded-r-xl">
                    <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs">
                        <i class="fas fa-bullhorn mr-1"></i> Bot Updates
                    </h4>
                    <p class="text-[12px] text-gray-400 mb-3 font-medium">ꜱᴛᴀʏ ᴜᴘᴅᴀᴛᴇᴅ ᴡɪᴛʜ ᴛʜᴇ ʟᴀᴛᴇꜱᴛ ᴀɴɴᴏᴜɴᴄᴇᴍᴇɴᴛꜱ, ꜰɪxᴇꜱ, ᴀɴᴅ ɴᴇᴡ ʙᴏᴛ ʀᴇʟᴇᴀꜱᴇꜱ.</p>
                    <a href="https://t.me/PrimeXBots" target="_blank" class="inline-flex bg-blue-500/20 text-blue-400 border border-blue-500/50 px-4 py-2 rounded-lg text-[10px] font-black uppercase hover:bg-blue-500/30">Join Channel <i class="fas fa-arrow-right ml-2"></i></a>
                </div>
                <div class="bg-gray-800/40 border-l-4 border-rose-500 p-4 rounded-r-xl">
                    <h4 class="text-rose-400 font-bold mb-2 uppercase text-xs">
                        <i class="fas fa-headset mr-1"></i> Contact Support
                    </h4>
                    <p class="text-[12px] text-gray-400 mb-3 font-medium">ꜰᴏʀ Qᴜᴇʀɪᴇꜱ, ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ, ᴏʀ ᴛᴀᴋᴇᴅᴏᴡɴ ʀᴇQᴜᴇꜱᴛꜱ, ʀᴇᴀᴄʜ ᴏᴜᴛ ᴛᴏ ᴜꜱ.</p>
                    <a href="https://t.me/MR_PRIME_SUPREME" target="_blank" class="inline-flex bg-rose-500/20 text-rose-400 border border-rose-500/50 px-4 py-2 rounded-lg text-[10px] font-black uppercase hover:bg-rose-500/30">Contact Developer <i class="fas fa-paper-plane ml-2"></i></a>
                </div>
            </div>
        </div>
    </div>

    <!-- Scripts Section -->
    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        const fileUrl = "$stream_url";
        const fileName = "$file_name";

        
        function getCleanUrl() {
            let url = fileUrl.trim();
            if (url.startsWith("http:https://")) { url = url.replace("http:https://", "https://"); }
            return url;
        }

        let player;
        document.addEventListener('DOMContentLoaded', () => {
           
            player = new Plyr('#player', {
                controls: [
                    'play-large', 'play', 'progress', 'current-time', 
                    'mute', 'volume', 'settings', 'fullscreen'
                ],
                ratio: '16:9'
            });

            
            player.on('ready', () => {
                const container = player.elements.container;

               
                const overlay = document.createElement('div');
                overlay.id = 'brightness-overlay';
                container.appendChild(overlay);

                const brPopup = document.createElement('div');
                brPopup.id = 'brightness-popup';
                brPopup.innerHTML = `
                    <span>BRIGHTNESS</span>
                    <input type="range" id="br-slider" min="0" max="0.8" step="0.05" value="0.8">
                `;
                container.appendChild(brPopup);

                
                const controls = container.querySelector('.plyr__controls');
                const middleSection = document.createElement('div');
                middleSection.className = 'custom-player-btns';
                middleSection.innerHTML = `
                    <button id="custom-rewind" title="Rewind 10s"><i class="fas fa-backward"></i></button>
                    <button id="br-toggle-btn" title="Brightness"><i class="fas fa-sun"></i></button>
                    <button id="custom-forward" title="Forward 10s"><i class="fas fa-forward"></i></button>
                `;

                const playBtn = controls.querySelector('[data-plyr="play"]');
                if (playBtn) playBtn.after(middleSection);

               
                document.getElementById('custom-rewind').onclick = (e) => { 
                    e.stopPropagation(); 
                    player.currentTime = Math.max(0, player.currentTime - 10); 
                };
                
                document.getElementById('custom-forward').onclick = (e) => { 
                    e.stopPropagation(); 
                    player.currentTime = Math.min(player.duration, player.currentTime + 10); 
                };

               
                const btn = document.getElementById('br-toggle-btn');
                btn.onclick = (e) => {
                    e.stopPropagation();
                    brPopup.style.display = (brPopup.style.display === 'flex') ? 'none' : 'flex';
                };

               
                document.getElementById('br-slider').oninput = (e) => {
                    const val = parseFloat(e.target.value);
                    document.getElementById('brightness-overlay').style.opacity = (0.8 - val);
                };

                window.addEventListener('click', () => { brPopup.style.display = 'none'; });
                brPopup.onclick = (e) => e.stopPropagation();
                
                player.volume = 1;
                player.muted = false;
            });
            player.on('play', () => { player.muted = false; });
        });

        
        function watchOnline() { 
            if (player) { 
                player.play(); 
                player.fullscreen.enter(); 
                
                if (screen.orientation && screen.orientation.lock) {
                    screen.orientation.lock('landscape').catch(err => {
                        console.log("Orientation lock blocked: ", err);
                    });
                }
            } 
        }

        
        function streamDownload() {
            const a = document.createElement('a');
            a.href = getCleanUrl();
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        
        function mx_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.mxtech.videoplayer.ad;end`; }
        function vlc_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=org.videolan.vlc;end`; }
        function playit_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.playit.videoplayer;end`; }
        function n_player() {
            if (/Android/i.test(navigator.userAgent)) { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.newin.nplayer.pro;end`; }
            else { window.location.href = `nplayer-$${getCleanUrl()}`; }
        }
        function system_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;end`; }
        function km_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=com.kmplayer;end`; }
        function kodi_player() { window.location.href = `intent:$${getCleanUrl()}#Intent;action=android.intent.action.VIEW;type=video/*;package=org.xbmc.kodi;end`; }

       
        function updateClock() { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
        setInterval(updateClock, 1000); updateClock();

        function copyToClipboard() { navigator.clipboard.writeText(window.location.href).then(() => alert("Link Copied!")); }

        function openModal() { 
            const m = document.getElementById('infoModal');
            m.classList.remove('hidden'); m.classList.add('flex');
            setTimeout(() => document.getElementById('modalBox').classList.add('modal-active-anim'), 10);
        }
        function closeModal() { 
            document.getElementById('modalBox').classList.remove('modal-active-anim');
            setTimeout(() => { document.getElementById('infoModal').classList.add('hidden'); }, 400);
        }

       
        const themeBtn = document.getElementById("theme-toggle-btn");
        function applyTheme(mode) {
            if (mode === "light") {
                document.body.classList.add("light");
                document.getElementById("theme-icon").className = "fa-solid fa-moon text-blue-600";
                document.getElementById("theme-text").innerText = "DARK MODE";
            } else {
                document.body.classList.remove("light");
                document.getElementById("theme-icon").className = "fa-solid fa-sun text-[#00e5ff]";
                document.getElementById("theme-text").innerText = "LIGHT MODE";
            }
        }
        themeBtn.addEventListener("click", () => {
            const isLight = document.body.classList.contains("light");
            const newTheme = isLight ? "dark" : "light";
            localStorage.setItem("prime_pref", newTheme);
            applyTheme(newTheme);
        });
        applyTheme(localStorage.getItem("prime_pref") || "dark");
    </script>    
</body>
</html>
""")

class DummyWebServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        # ১. মিনি অ্যাপ ডাউনলোড বাটন পেইজ (প্রিমিয়াম/ফ্রি কন্ডিশনাল লজিক সহ)
        if parsed_url.path == "/download":
            query_params = parse_qs(parsed_url.query)
            file_db_id = query_params.get("id", [""])[0]
            user_id_str = query_params.get("user_id", [""])[0]
            
            user_id = 0
            if user_id_str.isdigit():
                user_id = int(user_id_str)
                
            # প্রিমিয়াম ভেরিফিকেশন চেক
            is_vip = False
            if app.loop and app.loop.is_running() and user_id > 0:
                try:
                    from database import is_premium_user
                    future = asyncio.run_coroutine_threadsafe(is_premium_user(user_id), app.loop)
                    is_vip = future.result(timeout=2)
                except Exception as e:
                    print(f"Failed to verify VIP status in server: {e}")
            
            # ডাটাবেজ থেকে মুভির রিয়েল মেটাডেটা সংগ্রহ
            file_data = None
            if app.loop and app.loop.is_running():
                try:
                    from database import get_file_by_db_id
                    future = asyncio.run_coroutine_threadsafe(get_file_by_db_id(file_db_id), app.loop)
                    file_data = future.result(timeout=2)
                except Exception as e:
                    print(f"Failed to fetch file details: {e}")
            
            if not file_data:
                self.send_error(404, "File Not Found")
                return
                
            file_name = file_data.get("file_name", "Movie File")
            file_size = round(file_data["file_size"] / (1024 * 1024), 2)
            
            # ইউজার প্রিমিয়াম হলে সরাসরি অ্যাড ছাড়া ২-বাটন প্যানেল দেখাবে
            if is_vip:
                response_html = HTML_VIP_TEMPLATE.safe_substitute(
                    file_db_id=file_db_id,
                    bot_username=config.BOT_USERNAME,
                    file_name=file_name,
                    file_size=file_size
                )
            # ইউজার সাধারণ বা ফ্রি হলে পূর্বের নিয়মে লোডার + অ্যাড স্ক্রিন দেখাবে
            else:
                base_ad = random.choice(config.DIRECT_AD_LINKS)
                rand_id = random.randint(100000, 999999)
                rand_click = random.randint(1000000, 9999999)
                
                if "?" in base_ad:
                    ad_link = f"{base_ad}&click_id={rand_click}&sub_id={rand_id}"
                else:
                    ad_link = f"{base_ad}?click_id={rand_click}&sub_id={rand_id}"
                
                # [সংশোধিত ও অপ্টিমাইজড লাইভ স্ট্যাটাস মেকানিজম]
                total_files, total_users, used_storage, free_storage = 0, 0, "0.0 MB", "2.0 GB"
                if app.loop and app.loop.is_running():
                    try:
                        from database import get_detailed_stats
                        future = asyncio.run_coroutine_threadsafe(get_detailed_stats(), app.loop)
                        stats_dict = future.result(timeout=2)
                        
                        total_files = stats_dict.get("total_files", 0)
                        total_users = stats_dict.get("total_users", 0)
                        used_storage = stats_dict.get("used_storage", "0.0 MB")
                        free_storage = stats_dict.get("free_storage", "2.0 GB")
                    except Exception as e:
                        print(f"Failed to fetch live stats: {e}")
                
                response_html = HTML_TEMPLATE.safe_substitute(
                    file_db_id=file_db_id,
                    bot_username=config.BOT_USERNAME,
                    ad_link=ad_link,
                    total_files=f"{total_files:,}",
                    total_users=f"{total_users:,}",
                    used_storage=used_storage,
                    free_storage=free_storage
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
