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
from datetime import datetime, timedelta

app = Flask(__name__)

# 過去1分間の検出結果を保存
recent_detections = []  # [(timestamp, matched_names_dict), ...]

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

def preprocess_image_v2(image):
    """画像を前処理"""
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
    """2つの文字列の類似度を計算（0.0～1.0）"""
    s1 = str1.replace(' ', '').replace('　', '').lower()
    s2 = str2.replace(' ', '').replace('　', '').lower()
    return SequenceMatcher(None, s1, s2).ratio()

def find_best_match(detected, threshold=0.65):
    """検出された文字列に最も似ている登録名を探す"""
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
    return "VoteReader Bot v6 - Fuzzy Matching"

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
    """画像から名前を読み取って変換"""
    
    try:
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO(message_content.content)
        image = Image.open(image_bytes)
        
        max_size = 2000
        if image.width > max_size or image.height > max_size:
            ratio = min(max_size / image.width, max_size / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)
        
        all_detected = set()
        
        text1 = pytesseract.image_to_string(image, lang='jpn+eng', config='--psm 6')
        all_detected.update([line.strip() for line in text1.split('\n') if line.strip() and len(line.strip()) >= 2])
        
        processed = preprocess_image_v2(image)
        text2 = pytesseract.image_to_string(processed, lang='jpn+eng', config='--psm 6')
        all_detected.update([line.strip() for line in text2.split('\n') if line.strip() and len(line.strip()) >= 2])
        
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(2.0)
        text3 = pytesseract.image_to_string(enhanced, lang='jpn+eng', config='--psm 6')
        all_detected.update([line.strip() for line in text3.split('\n') if line.strip() and len(line.strip()) >= 2])
        
        matched_names = {}
        
        for detected in all_detected:
            matched_name, ratio = find_best_match(detected)
            if matched_name:
                if matched_name not in matched_names or ratio > matched_names[matched_name][1]:
                    matched_names[matched_name] = (detected, ratio)
        
        sorted_names = [name for name in NAME_ORDER if name in matched_names]
        
        # 今回の結果を保存
        current_time = datetime.now()
        if sorted_names:
            recent_detections.append((current_time, matched_names))
        
        # 1分以上前のデータを削除
        one_minute_ago = current_time - timedelta(minutes=1)
        recent_detections[:] = [(t, m) for t, m in recent_detections if t > one_minute_ago]
        
        # 過去1分間の統合結果を作成
        all_merged_names = {}
        for timestamp, names_dict in recent_detections:
            for name, (detected_text, ratio) in names_dict.items():
                if name not in all_merged_names or ratio > all_merged_names[name][1]:
                    all_merged_names[name] = (detected_text, ratio)
        
        merged_sorted = [name for name in NAME_ORDER if name in all_merged_names]
        
        if sorted_names:
            # 今回の結果
            converted_parts = []
            for name in sorted_names:
                detected_text, ratio = matched_names[name]
                converted_name = NAME_MAP[name]
                converted_parts.append(converted_name)
            
            today_result = "・".join(converted_parts)
            today_count = len(sorted_names)
            
            # パーセント表示（100%未満のみ）
            percent_info = ""
            for name in sorted_names:
                detected_text, ratio = matched_names[name]
                if ratio < 1.0:
                    percent_info += f"{NAME_MAP[name]}({round(ratio * 100)}%) "
            
            reply_text = f"【今回】\n{today_result}({today_count})"
            if percent_info:
                reply_text += f"\n{percent_info.strip()}"
            
            # 過去1分間の統合結果
            if len(recent_detections) > 1:  # 2件以上ある場合のみ表示
                merged_parts = []
                for name in merged_sorted:
                    merged_parts.append(NAME_MAP[name])
                
                merged_result = "・".join(merged_parts)
                merged_count = len(merged_sorted)
                
                merged_percent = ""
                for name in merged_sorted:
                    ratio = all_merged_names[name][1]
                    if ratio < 1.0:
                        merged_percent += f"{NAME_MAP[name]}({round(ratio * 100)}%) "
                
                reply_text += f"\n\n【過去1分間の統合】\n{merged_result}({merged_count})"
                if merged_percent:
                    reply_text += f"\n{merged_percent.strip()}"
        else:
            reply_text = f"名前が見つかりませんでした。\n\n【OCR結果】\n"
            reply_text += "\n".join(list(all_detected)[:20])
    
    except Exception as e:
        reply_text = f"エラー: {str(e)}"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
