from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json
from urllib.parse import parse_qsl

app = Flask(__name__, template_folder=".", static_folder=".")

# -------------------- фронт --------------------
@app.route("/")
def index():
    return render_template("index.html")  # ваш файл из предыдущего шага

# -------------------- auth: проверка initData --------------------
def verify_init_data(init_data: str, bot_token: str):
    """
    Возвращает (ok: bool, reason: str, user: dict|None).
    Валидируем initData по правилам Telegram Web Apps:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False, "missing hash", None

    # data_check_string
    check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash.lower()):
        return False, "bad signature", None

    # user
    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None
    return True, "ok", user

@app.post("/api/auth")
def api_auth():
    data = request.get_json(silent=True) or {}
    init_data = data.get("init_data", "")
    bot_token = os.getenv("BOT_TOKEN", "")

    ok, reason, user = verify_init_data(init_data, bot_token)
    if not ok:
        # если открыть страницу вне Telegram — тут будет "bad signature"
        return jsonify(ok=False, error=reason), 200

    return jsonify(ok=True, user=user)

# (опционально) чтобы Telegram мог встраивать страницу в WebView
@app.after_request
def allow_telegram_embed(resp):
    resp.headers["X-Frame-Options"] = "ALLOWALL"
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://*.t.me https://*.telegram.org;"
    return resp

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
