from flask import Flask, render_template, send_from_directory, jsonify
import os

app = Flask(__name__, template_folder=".", static_folder=".")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

# разрешаем встраивание во фрейм Telegram
@app.after_request
def allow_telegram_embed(resp):
    resp.headers['X-Frame-Options'] = 'ALLOWALL'
    resp.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://*.t.me https://*.telegram.org;"
    return resp

# SPA-fallback: любые пути отдаем index.html, если файла нет
@app.route("/<path:path>")
def static_proxy(path):
    if os.path.exists(path):
        return send_from_directory(".", path)
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
