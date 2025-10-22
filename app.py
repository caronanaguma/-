import os
import io
import pytesseract
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image, ImageEnhance, ImageFilter
from difflib import SequenceMatcher
import cv2
import numpy as np
import time

app = Flask(__name__)

# 環境変数から取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 名前変換表
NAME_MAP = {
    "Tomoka Tachi": "フ・ユランス",
    "田中良汰": "けっこんしてないしょうどくだいおう",
    "ようすけ": "ドライブ・ダ・ヴィンチ",
    "佐藤大地": "トトロっちたいさ",
    "なお": "すいじょうき",
    "りの": "めーめ",
    "ももこ": "ウィンターホワイト",
    "櫻井佑太": "いぬラッセル",
    "なぎさ": "オレンジクッキー",
    "なかむらゆうく": "イルカザル",
    "みゆ": "チョコりん",
    "えりこ": "みなみんとん",
    "Kazutaka": "めいたんていティラノ",
    "宮内菜摘": "ポニーツェル",
    "原田澪": "あきしば",
    "そうま": "トプトプス",
    "やまりょー": "198%のにくじゃが",
    "原田月読": "天照カウンセラー",
    "だいすけ": "フジタリアン",
    "柳川 和希": "アップルジャパン",
    "あいり": "トイプーエル",
    "北條": "米から産まれた日本うさぎ",
    "栁町京一": "ミステリーくじら",
    "くま": "トラッキークリーム",
    "高橋勇輝": "Banana",
    "かな": "はれぽぽ",
    "山本知広": "韓国のサーモンパンチ",
    "鵜飼 理央": "モングミン",
    "快": "スイカうんどうかい",
    "ゆい": "ピュアノ",
    "赤羽佳菜": "カントリーベリー",
    "あやな": "3時のこしあん",
    "ひらり": "ウイリアーラ",
    "けいすけ": "カロン",
    "だんばら": "しけ　みずいろクロワッサン",
    "晴南": "フリーオレ",
    "ともき": "キリン・ゼロ",
    "ももか": "いぬやマーメイド",
    "chihena": "しろくまメロン",
    "みお": "さくらのうえにも一年",
    "れい": "ピンクのぬりかべ",
    "Masataka": "おおたにシックス",
    "シバタ": "ハートパキッ",
    "Yui": "いちごルビー",
    "reika": "パンダルム",
    "直起": "えいこうのくつひも",
    "はな": "プラン・A・クトン",
    "nishida": "ホワイトはなごん",
    "Mutsuna": "チャーリス",
    "時羽": "ポインアップ",
    "たかや": "オニオンクラフト",
    "🎩HAYATO🎹": "モスプーさん",
    "ねね": "ぱっきゃん",
    "セナ": "仮面ライダーリカグルト",
    "Riiko🍡": "ココルー",
    "ayumi": "カルピスの森",
    "美月": "パンプキンピーチ",
    "こうだい": "くすりうりの彼女",
    "なぎと": "ワンマグロピース",
    "おかの だいご": "さくらえび",
    "かえ": "まっちゃっこ",
    "ゆきこ": "ドーナツ将軍",
    "ももな": "こうきゅうカビゴン",
    "ここみ": "ちたファンとう"
}

# 表の順序
NAME_ORDER = list(NAME_MAP.keys())

# --- 追加：ユーザーごとの一時データ ---
user_temp_results = {}  # {user_id: {"names": {}, "timestamp": float}}

def preprocess_image_v2(image):
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    denoised = cv2.medianBlur(binary, 3)
    return Image.fromarray(denoised)

def similarity_ratio(str1, str2):
    s1 = str1.replace(' ', '').replace('　', '').lower()
    s2 = str2.replace(' ', '').replace('　', '').lower()
    return SequenceMatcher(None, s1, s2).ratio()

def find_best_match(detected, threshold=0.65):
    best_match = None
    best_ratio = 0
    for name in NAME_MAP.keys():
        ratio = similarity_ratio(detected, name)
        detected_clean = detected.replace(' ', '').replace('　', '')
        name_clean = name.replace(' ', '').replace('　', '')
        if detected_clean in name_clean or name_clean in detected_clean:
            ratio = max(ratio, 0.8)
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = name
    if best_ratio >= threshold:
        return best_match, best_ratio
    return None, 0

@app.route("/")
def hello():
    return "VoteReader Bot v6 - Fuzzy Matching (multi-image supported)"

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
    try:
        user_id = event.source.user_id
        now = time.time()

        # 古いデータを削除（30分経過したら）
        if user_id in user_temp_results and now - user_temp_results[user_id]["timestamp"] > 1800:
            del user_temp_results[user_id]

        # ユーザーの一時データがなければ作成
        if user_id not in user_temp_results:
            user_temp_results[user_id] = {"names": {}, "timestamp": now}

        # 画像取得
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO(message_content.content)
        image = Image.open(image_bytes)

        # サイズ制限
        max_size = 2000
        if image.width > max_size or image.height > max_size:
            ratio = min(max_size / image.width, max_size / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # OCR試行
        all_detected = set()
        text1 = pytesseract.image_to_string(image, lang='jpn+eng', config='--psm 6')
        all_detected.update([l.strip() for l in text1.split('\n') if l.strip() and len(l.strip()) >= 2])
        processed = preprocess_image_v2(image)
        text2 = pytesseract.image_to_string(processed, lang='jpn+eng', config='--psm 6')
        all_detected.update([l.strip() for l in text2.split('\n') if l.strip() and len(l.strip()) >= 2])
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(2.0)
        text3 = pytesseract.image_to_string(enhanced, lang='jpn+eng', config='--psm 6')
        all_detected.update([l.strip() for l in text3.split('\n') if l.strip() and len(l.strip()) >= 2])

        matched_names = {}
        for detected in all_detected:
            matched_name, ratio = find_best_match(detected)
            if matched_name:
                if matched_name not in matched_names or ratio > matched_names[matched_name][1]:
                    matched_names[matched_name] = (detected, ratio)

        # 一時保存データに統合（重複削除＆高一致率優先）
        for name, (detected, ratio) in matched_names.items():
            if name not in user_temp_results[user_id]["names"] or ratio > user_temp_results[user_id]["names"][name][1]:
                user_temp_results[user_id]["names"][name] = (detected, ratio)
        user_temp_results[user_id]["timestamp"] = now

        # すべての結果を統合して出力
        combined = user_temp_results[user_id]["names"]
        sorted_names = [n for n in NAME_ORDER if n in combined]

        if sorted_names:
            display_names = []
            debug_info = "\n\n【マッチング詳細】\n"
            for name in sorted_names:
                detected_text, ratio = combined[name]
                percent = int(round(ratio * 100))
                converted = NAME_MAP[name]
                if percent < 100:
                    display_names.append(f"{converted}({percent}%)")
                else:
                    display_names.append(converted)
                debug_info += f"{name} ← {detected_text} ({percent}%)\n"

            converted_text = "・".join(display_names)
            count = len(sorted_names)
            reply_text = f"{converted_text}({count}){debug_info}"
        else:
            reply_text = "名前が見つかりませんでした。\n\n【OCR結果】\n" + "\n".join(list(all_detected)[:20])

    except Exception as e:
        reply_text = f"エラー: {str(e)}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
