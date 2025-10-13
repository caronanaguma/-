import os
import io
import pytesseract
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image

app = Flask(__name__)

# 環境変数から取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/")
def hello():
    return "VoteReader Bot is running! v3 (Tesseract)"

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
    """画像メッセージを受信したときの処理"""
    
    # 画像を取得
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    
    # バイトデータを画像に変換
    image_bytes = io.BytesIO(message_content.content)
    image = Image.open(image_bytes)
    
    # OCR で文字を読み取る
    try:
        # Tesseract で日本語と英語を読み取る
        text = pytesseract.image_to_string(image, lang='jpn+eng')
        
        # 読み取った文字を行ごとに分割
        detected_texts = [line.strip() for line in text.split('\n') if line.strip()]
        
        # ★ ここで名前変換ルールを適用 ★
        converted_names = []
        for name in detected_texts:
            # 例: 特定の文字を置き換える
            converted = name.replace("太郎", "タロウ")
            converted = converted.replace("花子", "ハナコ")
            converted_names.append(converted)
        
        # 結果を整形
        if converted_names:
            names_list = "\n".join([f"・{name}" for name in converted_names])
            reply_text = f"読み取った名前:\n\n{names_list}\n\n合計: {len(converted_names)}人"
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

