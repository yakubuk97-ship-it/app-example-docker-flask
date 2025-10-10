from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json
from urllib.parse import parse_qsl

app = Flask(__name__, template_folder=".", static_folder=".")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

def verify_init_data(init_data: str, bot_token: str):
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash", None
    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash.lower(), hash_value.lower()):
        return False, "bad signature", None
    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None
    return True, "ok", user

@app.route("/api/auth", methods=["POST"])
def auth():
    data = request.get_json(silent=True) or {}
    init_data = data.get("init_data", "")
    bot_token = os.getenv("BOT_TOKEN", "")
    ok, reason, user = verify_init_data(init_data, bot_token)
    if not ok:
        # Больше НЕ блокируем фронт — просто сообщаем
        return jsonify(ok=False, error=reason, user=None), 200
    return jsonify(ok=True, user=user)

# ===== Заглушки под будущую логику =====

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
    # --- РЕФЕРАЛКИ: конфиг ---
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()
WEBAPP_SHORT_NAME = os.getenv("WEBAPP_SHORT_NAME", "").strip()

# простейшее "хранилище" рефералок (на проде замени на БД)
import json
from threading import Lock
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

# --- утилита: формируем персональную ссылку ---
def build_ref_link(user_id: int) -> str:
    """
    Линк, который открывает ТВОЙ мини-апп и пробрасывает ref-код через startapp.
    Важно: у тебя в BotFather должен быть настроен short_name = WEBAPP_SHORT_NAME.
    """
    if not BOT_USERNAME or not WEBAPP_SHORT_NAME:
        # на случай, если забыли выставить переменные окружения
        raise RuntimeError("Set BOT_USERNAME and WEBAPP_SHORT_NAME env vars")
    return f"https://t.me/{BOT_USERNAME}/{WEBAPP_SHORT_NAME}?startapp=ref_{user_id}"

# --- эндпойнт: вернуть персональную ссылку ---
@app.post("/api/ref/link")
def api_ref_link():
    try:
        data = request.get_json(force=True, silent=True) or {}
        init_data = data.get("init_data", "")
        user = verify_telegram_init_data(init_data)  # твоя функция в /api/auth — используй её же
        # Если у тебя авторизация пока падает (bad signature), можешь временно
        # брать user_id из поля data.get("debug_user_id") для ручной проверки.
        if not user:
            return jsonify(ok=False, error="unauthorized"), 401

        uid = user.get("id")
        link = build_ref_link(uid)

        # сохраним, что у этого uid уже есть сгенерированная ссылка (не обязательно)
        ref = _load_ref()
        ref["links"][str(uid)] = link
        _save_ref(ref)

        return jsonify(ok=True, link=link)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# --- (опц.) регистрация визита по реф-коду ---
# Если пользователь зашёл с ?startapp=ref_<X>, этот параметр придёт в initData как start_param.
# Ниже — пример: фиксируем визит.
@app.post("/api/ref/register_visit")
def api_ref_register_visit():
    try:
        data = request.get_json(force=True, silent=True) or {}
        init_data = data.get("init_data", "")
        user = verify_telegram_init_data(init_data)
        if not user:
            # можно разрешить анонимные визиты, но лучше иметь id "пришедшего"
            return jsonify(ok=False, error="unauthorized"), 401

        # твоя verify_telegram_init_data должна возвращать start_param, если он есть в initData
        start_param = user.get("start_param") or user.get("startapp") or ""
        # ждём формат ref_123456
        if not (start_param and start_param.startswith("ref_")):
            return jsonify(ok=True, registered=False)

        inviter_id = int(start_param.split("ref_", 1)[-1])
        visitor_id = int(user["id"])
        if inviter_id == visitor_id:
            return jsonify(ok=True, registered=False)  # сам себя не считаем

        ref = _load_ref()
        ref["visits"].append({
            "inviter": inviter_id,
            "visitor": visitor_id,
            "ts": int(time.time())
        })
        _save_ref(ref)
        return jsonify(ok=True, registered=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
