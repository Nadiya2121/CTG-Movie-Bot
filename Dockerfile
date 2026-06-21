FROM python:3.10-slim-buster

# সিস্টেম আপডেট ও FFmpeg ইনস্টল করা হচ্ছে
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# আপনার বটের মেইন রান ফাইলটির নাম যদি bot.py হয়, তবে এটি অপরিবর্তিত রাখুন
CMD ["python", "main.py"]
