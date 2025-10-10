from flask import Flask, request, jsonify, render_template, send_from_directory, g
import os, hmac, hashlib, json
from urllib.parse import parse_qsl

app = Flask(__name__, template_folder=".", static_folder=".")

# ---------- утилиты ----------
def verify_telegram_init_data(init_data: str, bot_token: str):
    """
    Правильная проверка подписи initData по документации Telegram.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None

    # Парсим пары из строки a=1&b=2...
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as e:
        return False, f"parse_qsl error: {e}", None

    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash param", None

    # Строка для подписи: пары (key=value) отсортированы по ключу, через \n
    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    # Секрет = sha256(bot_token)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc, hash_value):
        return False, "bad signature", None

    # user лежит в поле "user" (JSON-строка)
    user_raw = parsed.get("user")
    try:
        user = json.loads(user_raw) if user_raw else None
    except Exception as e:
        return False, f"user json error: {e}", None

    return True, "ok", user


# ---------- страницы ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")


@app.after_request
def allow_telegram_embed(resp):
    resp.headers["X-Frame-Options"] = "ALLOWALL"
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://*.t.me https://*.telegram.org;"
    return resp


@app.route("/api/auth", methods=["POST"])
def api_auth():
    try:
        data = request.get_json(silent=True) or {}
        init_data = data.get("init_data", "")
        bot_token = os.getenv("BOT_TOKEN", "")

        ok, reason, user = verify_telegram_init_data(init_data, bot_token)
        if not ok:
            # Возвращаем всегда JSON, чтобы фронт не падал на r.json()
            return jsonify(ok=False, error=reason), 401

        # Можно сохранить user в g (или в сессию/БД)
        g.user = user
        return jsonify(ok=True, user=user)
    except Exception as e:
        # Любая непредвиденная ошибка тоже вернёт JSON
        return jsonify(ok=False, error=f"server error: {e}"), 500


@app.route("/api/order", methods=["POST"])
def api_order():
    """
    Пример приёма заказа. Здесь просто эмулируем, что пользователь уже авторизован:
    реалистично — хранить user в сессии, Redis и т.п. После успешного /api/auth.
    Для демо примем заказ без жёсткой привязки и вернём ID.
    """
    try:
        payload = request.get_json(silent=True) or {}
        order_id = os.urandom(4).hex()
        return jsonify(ok=True, order_id=order_id, request=payload)
    except Exception as e:
        return jsonify(ok=False, error=f"order error: {e}"), 400


# SPA fallback, если понадобятся вложенные маршруты
@app.route("/<path:path>")
def static_proxy(path):
    if os.path.exists(path):
        return send_from_directory(".", path)
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
