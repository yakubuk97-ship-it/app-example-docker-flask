from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json, time
from urllib.parse import parse_qsl
from threading import Lock

app = Flask(__name__, template_folder=".", static_folder=".")

# ------------ базовые ручки ------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

# ------------ проверка initData ------------
def verify_init_data(init_data: str, bot_token: str):
    """
    Возвращает (ok: bool, reason: str, user: dict|None, start_param: str|None)
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None, None

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash", None, None

    # data_check_string
    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash.lower(), hash_value.lower()):
        return False, "bad signature", None, None

    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None
    start_param = parsed.get("start_param") or parsed.get("startapp")
    return True, "ok", user, start_param

@app.post("/api/auth")
def auth():
    data = request.get_json(silent=True) or {}
    init_data = data.get("init_data", "")
    bot_token = os.getenv("BOT_TOKEN", "")
    ok, reason, user, _ = verify_init_data(init_data, bot_token)
    if not ok:
        # не блокируем интерфейс
        return jsonify(ok=False, error=reason, user=None), 200
    return jsonify(ok=True, user=user)

# ------------ заглушки API ------------
@app.route("/api/user")
def api_user():
    return jsonify(ok=True, user={"id": 1, "name": "Guest"})

@app.route("/api/favorites", methods=["GET", "POST", "DELETE"])
def api_favs():
    return jsonify(ok=True, items=[])

@app.route("/api/cart", methods=["GET", "POST", "DELETE"])
def api_cart():
    return jsonify(ok=True, items=[], total=0)

@app.route("/api/shops")
def api_shops():
    return jsonify(ok=True, shops=[
        {"id": 1, "name": "Ozon"},
        {"id": 2, "name": "Wildberries"},
        {"id": 3, "name": "Yandex Market"},
    ])

# ------------ рефералки ------------
BOT_USERNAME       = os.getenv("BOT_USERNAME", "").strip()         # напр. MyPersonalBuyer_bot (без @)
WEBAPP_SHORT_NAME  = os.getenv("WEBAPP_SHORT_NAME", "").strip()    # напр. mypersonalbuyer (short name web-app)
_ref_lock = Lock()
_ref_file = "referrals.json"

def _load_ref():
    if not os.path.exists(_ref_file):
        return {"visits": [], "links": {}}
    try:
        with open(_ref_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"visits": [], "links": {}}

def _save_ref(data):
    with _ref_lock:
        with open(_ref_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def build_ref_link(user_id: int) -> str:
    if not BOT_USERNAME or not WEBAPP_SHORT_NAME:
        raise RuntimeError("Set BOT_USERNAME and WEBAPP_SHORT_NAME env vars")
    # ссылка открывает ваш mini app с параметром startapp=ref_<id>
    return f"https://t.me/{BOT_USERNAME}/{WEBAPP_SHORT_NAME}?startapp=ref_{user_id}"

@app.post("/api/ref/link")
def api_ref_link():
    data = request.get_json(force=True, silent=True) or {}
    init_data = data.get("init_data", "")
    ok, reason, user, _ = verify_init_data(init_data, os.getenv("BOT_TOKEN",""))
    if not ok or not user:
        return jsonify(ok=False, error=reason or "unauthorized"), 401

    uid = int(user["id"])
    link = build_ref_link(uid)

    ref = _load_ref()
    ref["links"][str(uid)] = link
    _save_ref(ref)
    return jsonify(ok=True, link=link)

@app.post("/api/ref/register_visit")
def api_ref_register_visit():
    data = request.get_json(force=True, silent=True) or {}
    init_data = data.get("init_data", "")
    ok, reason, user, start_param = verify_init_data(init_data, os.getenv("BOT_TOKEN",""))
    if not ok or not user:
        return jsonify(ok=False, error=reason or "unauthorized"), 401

    if not (start_param and start_param.startswith("ref_")):
        return jsonify(ok=True, registered=False)

    inviter_id = int(start_param.split("ref_", 1)[-1])
    visitor_id = int(user["id"])
    if inviter_id == visitor_id:
        return jsonify(ok=True, registered=False)

    ref = _load_ref()
    ref["visits"].append({"inviter": inviter_id, "visitor": visitor_id, "ts": int(time.time())})
    _save_ref(ref)
    return jsonify(ok=True, registered=True)

# ------------ запуск ------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
