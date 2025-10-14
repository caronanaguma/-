# 複数枚画像対応（例）
# 複数画像をまとめてall_detectedに追加
all_detected = set()
for img_bytes in received_image_bytes_list:  # 複数画像のバイト列リスト
    image = Image.open(io.BytesIO(img_bytes))
    
    # 既存のOCR処理3種類
    for img in [image, preprocess_image_v2(image), ImageEnhance.Contrast(image).enhance(2.0)]:
        text = pytesseract.image_to_string(img, lang='jpn+eng', config='--psm 6')
        all_detected.update([line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) >= 2])

# あいまいマッチング処理は既存のまま
matched_names = {}
for detected in all_detected:
    matched_name, ratio = find_best_match(detected)
    if matched_name:
        if matched_name not in matched_names or ratio > matched_names[matched_name][1]:
            matched_names[matched_name] = (detected, ratio)
