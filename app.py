from flask import Flask, render_template, send_from_directory, jsonify, request
import os, json, hmac, hashlib, urllib.parse

# ... твой существующий код ...

BOT_TOKEN = os.getenv("BOT_TOKEN")  # НЕ коммить в git! добавить в переменные окружения на Timeweb

def verify_telegram_init_data(init_data: str) -> dict:
    """
    Проверка подписи initData из Telegram Web App.
    Алгоритм: HMAC-SHA256(data_check_string, secret_key=SHA256(BOT_TOKEN))
    """
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set on server")

    # разберём "k=v&k2=v2..."
    pairs = {}
    for chunk in init_data.split('&'):
        if not chunk: 
            continue
        k, v = chunk.split('=', 1)
        pairs[k] = urllib.parse.unquote(v)

    tg_hash = pairs.pop('hash', None)
    if not tg_hash:
        raise ValueError("hash is missing")

    data_check_string = '\n'.join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calc_hash != tg_hash:
        raise ValueError("bad signature")

    return pairs  # здесь будут строки: user=..., auth_date=..., query_id=... и т.п.

@app.route("/api/auth", methods=["POST"])
def api_auth():
    payload = request.get_json(force=True, silent=True) or {}
    init_data = payload.get("initData", "")
    try:
        parsed = verify_telegram_init_data(init_data)
        user = json.loads(parsed.get("user", "{}"))  # это объект пользователя от Telegram
        return jsonify(ok=True, user=user, auth_date=parsed.get("auth_date"))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400
