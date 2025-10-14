from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json
from urllib.parse import parse_qsl

app = Flask(__name__, template_folder=".", static_folder=".")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/auth", methods=["POST"])
def api_auth():
    data = request.get_json(silent=True) or {}
    init_data = data.get("init_data", "")
    bot_token = os.getenv("BOT_TOKEN", "")

    ok, reason, user = verify_init_data(init_data, bot_token)
    if not ok:
        return jsonify(ok=False, error=reason), 200
    return jsonify(ok=True, user=user), 200

def verify_init_data(init_data: str, bot_token: str):
    """
    Проверка Telegram initData по алгоритму:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None

    # разбираем строку initData в dict
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash", None

    # data_check_string
    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))

    # секретный ключ = HMAC-SHA256 от bot_token
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, hash_value.lower()):
        return False, "bad signature", None

    # user JSON из initData
    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None
    return True, "ok", user

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
