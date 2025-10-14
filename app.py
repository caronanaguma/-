import os
import io
import pytesseract
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image, ImageEnhance, ImageFilter

app = Flask(__name__)

# 環境変数から取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
        
        # OCRで文字を読み取る（シンプル版）
        text = pytesseract.image_to_string(image, lang='jpn+eng')
        
        # 読み取った文字を整形
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if lines:
            # 番号付きで表示
            result = "【OCR読み取り結果】\n\n"
            for i, line in enumerate(lines, 1):
                result += f"{i}. {line}\n"
            result += f"\n合計 {len(lines)} 行"
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
