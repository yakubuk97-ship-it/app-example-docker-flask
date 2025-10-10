from flask import Flask, render_template, send_from_directory, jsonify, request, session
import os, hashlib, hmac, time, urllib.parse, json

app = Flask(__name__, template_folder=".", static_folder=".")
app.secret_key = os.getenv("SECRET_KEY", "change-me-please")  # лучше положить в переменные окружения

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

# --- Разрешаем встраивание в Telegram WebView ---
@app.after_request
def allow_telegram_embed(resp):
    resp.headers['X-Frame-Options'] = 'ALLOWALL'
    resp.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://*.t.me https://*.telegram.org;"
    return resp

# --- SPA-режим: отдаём index.html, если файла нет ---
@app.route("/<path:path>")
def static_proxy(path):
    if os.path.exists(path):
        return send_from_directory(".", path)
    return render_template("index.html")

# ---------- Telegram initData auth ----------
def verify_init_data(init_data: str, bot_token: str):
    """
    Проверка подписи согласно документации Telegram Mini Apps:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        return None

    data = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    if 'hash' not in data:
        return None

    received_hash = data.pop('hash')
    # формируем data_check_string
    data_check_string = '\n'.join(f"{k}={data[k]}" for k in sorted(data.keys()))

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calc_hash != received_hash:
        return None

    # опционально ограничим «свежесть» логина (24 часа)
    if 'auth_date' in data:
        try:
            if time.time() - int(data['auth_date']) > 24 * 3600:
                return None
        except Exception:
            return None

    # user — JSON-строка
    try:
        user = json.loads(data.get('user', '{}'))
    except Exception:
        user = {}

    return user

@app.post("/api/auth")
def api_auth():
    init_data = request.json.get('init_data') if request.is_json else request.form.get('init_data', '')
    user = verify_init_data(init_data, os.environ['BOT_TOKEN'])
    if not user:
        return jsonify(ok=False, error="unauthorized"), 401

    session['user'] = user   # сохраним в сессии (Flask cookie)
    return jsonify(ok=True, user=user)

@app.get("/api/user")
def api_user():
    user = session.get('user')
    if not user:
        return jsonify(ok=False), 401
    return jsonify(ok=True, user=user)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
