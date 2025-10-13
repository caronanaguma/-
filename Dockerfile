FROM python:3.11-slim

# Tesseractと日本語データをインストール
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn app:app --workers=1 --threads=2 --timeout=120 --bind=0.0.0.0:$PORT
