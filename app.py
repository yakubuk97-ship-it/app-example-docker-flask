from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json
from urllib.parse import parse_qsl

app = Flask(__name__, template_folder=".", static_folder=".")

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

# ——— неблокирующая проверка initData ———
def verify_init_data(init_data: str, bot_token: str):
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_value = parsed.pop("hash", None)
        if not init_data or not bot_token or not hash_value:
            return False
        check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(calc_hash.lower(), hash_value.lower())
    except Exception:
        return False

@app.post("/api/auth")
def auth():
    data = request.get_json(silent=True) or {}
    ok = verify_init_data(data.get("init_data",""), os.getenv("BOT_TOKEN",""))
    # не ломаем интерфейс
    return jsonify(ok=bool(ok))

# ——— заглушки под действия ———
@app.post("/api/order")
def make_order():
    link = (request.json or {}).get("link","")
    if not link:
        return jsonify(ok=False, error="empty"), 400
    # здесь можно слать в админ-чат бота, писать в БД и т.п.
    return jsonify(ok=True)

@app.get("/api/track")
def track():
    _id = request.args.get("id","")
    if not _id: return jsonify(ok=False), 400
    # заглушка статуса
    return jsonify(ok=True, status="В обработке")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
