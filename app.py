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
    # ВАЖНО: убираем возможные пробелы/переносы из токена
    bot_token = (os.getenv("BOT_TOKEN") or "").strip()

    ok, reason, user = verify_init_data(init_data, bot_token)
    if not ok:
        return jsonify(ok=False, error=reason, user=None), 200
    return jsonify(ok=True, user=user), 200

def verify_init_data(init_data: str, bot_token: str):
    """
    Проверка Telegram initData по алгоритму:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None

    # 1) Разбираем строку initData -> dict
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))

    # 2) Достаём hash и убираем его из словаря
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash", None

    # 3) Формируем data_check_string: k=v по ключам в ASCII-порядке
    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))

    # 4) SHA256(bot_token) как секретный ключ
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # 5) HMAC-SHA256(secret_key, data_check_string) в hex
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    # 6) Сравниваем безопасно
    if not hmac.compare_digest(calc_hash, hash_value):
        return False, "bad signature", None

    # 7) Возвращаем user (он приходит как JSON-строка в поле 'user')
    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None

    # Можно заодно вернуть start_param, если понадобится
    if user is not None and "start_param" in parsed:
        user["start_param"] = parsed["start_param"]

    return True, "ok", user

# (необязательно) ping для теста
@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
