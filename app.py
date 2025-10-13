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
    "ひ": "ウイリアーラ",
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

# 名前の順序を定義（表の上から順）
NAME_ORDER = [
    "Tomoka Tachi", "田中良汰", "ようすけ", "佐藤大地", "なお", "りの", "ももこ", 
    "櫻井佑太", "なぎさ", "なかむらゆうく", "みゆ", "えりこ", "Kazutaka", "宮内菜摘", 
    "原田澪", "そうま", "やまりょー", "原田月読", "だいすけ", "柳川 和希", "あいり", 
    "北條", "栁町京一", "くま", "高橋勇輝", "かな", "山本知広", "鵜飼 理央", "快", 
    "ゆい", "赤羽佳菜", "あやな", "ひらり", "けいすけ", "だんばら", "晴南", "ともき", 
    "ももか", "chihena", "みお", "れい", "Masataka", "シバタ", "Yui", "reika", 
    "直起", "はな", "nishida", "Mutsuna", "時羽", "たかや", "🎩HAYATO🎹", "ねね", 
    "セナ", "Riiko🍡", "ayumi", "美月", "こうだい", "なぎと", "おかの だいご", "かえ", 
    "ゆきこ", "ももな", "ここみ"
]

@app.route("/")
def hello():
    return "VoteReader Bot is running! v4 (Name Converter)"

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
        
        # 読み取った文字を行ごとに分割（空行を除く）
        detected_names = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 変換された名前を格納
        converted_names = []
        found_names = []
        
        # 検出された各名前を変換表でチェック
        for detected in detected_names:
            detected_clean = detected.strip()
            # 完全一致をチェック
            if detected_clean in NAME_MAP:
                found_names.append(detected_clean)
                converted_names.append(NAME_MAP[detected_clean])
        
        # 表の順序に並び替え
        sorted_pairs = []
        for name in NAME_ORDER:
            if name in found_names:
                sorted_pairs.append((name, NAME_MAP[name]))
        
        # 結果を整形
        if sorted_pairs:
            # 変換後の名前を・で連結
            converted_text = "・".join([pair[1] for pair in sorted_pairs])
            count = len(sorted_pairs)
            reply_text = f"{converted_text}({count})"
        else:
            reply_text = "登録されている名前が見つかりませんでした。"
    
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


