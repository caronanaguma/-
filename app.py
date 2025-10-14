import os
import io
import pytesseract
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

app = Flask(__name__)

# 環境変数から取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def preprocess_image_v2(image):
    """画像を複数の方法で前処理"""
    # PIL to numpy
    img_array = np.array(image)
    
    # グレースケール
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    
    # 二値化（適応的閾値処理）
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # ノイズ除去
    denoised = cv2.medianBlur(binary, 3)
    
    return Image.fromarray(denoised)

@app.route("/")
def hello():
    return "VoteReader Bot - OCR Test Mode"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    """画像から文字を読み取ってそのまま返す"""
    
    try:
        # 画像を取得
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO(message_content.content)
        image = Image.open(image_bytes)
        
        # 画像サイズを制限
        max_size = 2000
        if image.width > max_size or image.height > max_size:
            ratio = min(max_size / image.width, max_size / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)
        
        # 複数の方法でOCRを試す
        all_lines = []
        
        # 方法1: オリジナル画像
        text1 = pytesseract.image_to_string(image, lang='jpn+eng', config='--psm 6')
        all_lines.extend([line.strip() for line in text1.split('\n') if line.strip()])
        
        # 方法2: 前処理した画像
        processed = preprocess_image_v2(image)
        text2 = pytesseract.image_to_string(processed, lang='jpn+eng', config='--psm 6')
        all_lines.extend([line.strip() for line in text2.split('\n') if line.strip()])
        
        # 方法3: コントラスト強調
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(2.0)
        text3 = pytesseract.image_to_string(enhanced, lang='jpn+eng', config='--psm 6')
        all_lines.extend([line.strip() for line in text3.split('\n') if line.strip()])
        
        # 重複を削除して整理
        unique_lines = []
        seen = set()
        for line in all_lines:
            if line and line not in seen:
                unique_lines.append(line)
                seen.add(line)
        
        if unique_lines:
            # 番号付きで表示
            result = "【OCR読み取り結果】\n\n"
            for i, line in enumerate(unique_lines, 1):
                result += f"{i}. {line}\n"
            result += f"\n合計 {len(unique_lines)} 行"
            reply_text = result
        else:
            reply_text = "文字を読み取れませんでした。"
    
    except Exception as e:
        reply_text = f"エラー: {str(e)}"
    
    # 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
