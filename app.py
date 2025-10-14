from flask import Flask, request, jsonify, render_template
import os, hmac, hashlib, json, sqlite3, time
from urllib.parse import parse_qsl
from itsdangerous import URLSafeSerializer

# -----------------------------
# Конфигурация
# -----------------------------
BOT_TOKEN   = (os.getenv("BOT_TOKEN") or "").strip()           # из BotFather
SECRET_KEY  = (os.getenv("SECRET_KEY") or "change-me").strip() # для подписи токенов
DB_PATH     = os.getenv("DB_PATH") or "app.db"                 # SQLite файл
PORT        = int(os.getenv("PORT", "8080"))

app = Flask(__name__, template_folder=".", static_folder=".")
signer = URLSafeSerializer(SECRET_KEY, salt="auth")

# -----------------------------
# База (SQLite) — простейшая
# -----------------------------
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
    CREATE TABLE IF NOT EXISTS users (
        tg_id       INTEGER PRIMARY KEY,
        username    TEXT,
        first_name  TEXT,
        last_name   TEXT,
        photo_url   TEXT,
        created_at  INTEGER,
        updated_at  INTEGER
    );
    """)
    con.commit()
    con.close()

def upsert_user_from_telegram(u: dict):
    """
    u: dict из Telegram (id, username, first_name, last_name, photo_url)
    """
    now = int(time.time())
    con = db()
    cur = con.cursor()
    cur.execute("SELECT tg_id FROM users WHERE tg_id = ?", (u["id"],))
    exists = cur.fetchone()
    if exists:
        cur.execute("""
            UPDATE users
               SET username=?, first_name=?, last_name=?, photo_url=?, updated_at=?
             WHERE tg_id=?
        """, (u.get("username"), u.get("first_name"), u.get("last_name"), u.get("photo_url"), now, u["id"]))
    else:
        cur.execute("""
            INSERT INTO users (tg_id, username, first_name, last_name, photo_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (u["id"], u.get("username"), u.get("first_name"), u.get("last_name"), u.get("photo_url"), now, now))
    con.commit()
    con.close()

def get_user_by_tgid(tg_id: int):
    con = db()
    row = con.execute("""
        SELECT tg_id, username, first_name, last_name, photo_url, created_at, updated_at
          FROM users WHERE tg_id=?
    """, (tg_id,)).fetchone()
    con.close()
    if not row: return None
    return dict(row)

# -----------------------------
# Верификация initData из Telegram WebApp
# -----------------------------
def verify_init_data(init_data: str, bot_token: str):
    """
    Алгоритм по документации:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return False, "empty init_data or bot_token", None

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        return False, "missing hash", None

    check_str = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, hash_value):
        return False, "bad signature", None

    user_json = parsed.get("user")
    user = json.loads(user_json) if user_json else None
    if user is None:
        return False, "no user", None

    # Вернём start_param, если был (может пригодиться)
    if "start_param" in parsed:
        user["start_param"] = parsed["start_param"]

    return True, "ok", user

# -----------------------------
# Роуты
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

@app.post("/api/auth")
def api_auth():
    """
    Принимает { init_data } из Telegram WebApp.
    1) Проверяем подпись
    2) Создаём/обновляем пользователя в SQLite
    3) Возвращаем user + короткий токен (подписанный itsdangerous)
    """
    data = request.get_json(silent=True) or {}
    init_data = data.get("init_data", "")
    ok, reason, user = verify_init_data(init_data, BOT_TOKEN)
    if not ok:
        return jsonify(ok=False, error=reason, user=None), 200

    upsert_user_from_telegram(user)
    token = signer.dumps({"tg_id": user["id"]})
    # Вернём актуальные данные из базы
    u = get_user_by_tgid(user["id"])
    return jsonify(ok=True, user=u, token=token), 200

@app.get("/api/me")
def api_me():
    """
    Пример защищённой ручки.
    Нужен заголовок: Authorization: Bearer <token>
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(ok=False, error="no bearer token"), 401
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = signer.loads(token)
        u = get_user_by_tgid(int(payload["tg_id"]))
        if not u:
            return jsonify(ok=False, error="user not found"), 404
        return jsonify(ok=True, user=u), 200
    except Exception as e:
        return jsonify(ok=False, error="invalid token"), 401

# -----------------------------
# Запуск
# -----------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT)
