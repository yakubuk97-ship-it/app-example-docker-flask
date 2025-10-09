from flask import Flask, render_template, send_from_directory, jsonify
import os

app = Flask(__name__, template_folder=".", static_folder=".")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ping")
def ping():
    return jsonify(ok=True, msg="pong")

# чтобы телега открывала /MyPersonalBuyer и любые вложенные пути
@app.route("/<path:path>")
def static_proxy(path):
    # если есть файлик — отдадим, иначе вернем index.html (SPA-режим)
    if os.path.exists(path):
        return send_from_directory(".", path)
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3478"))   # timeweb пример слушает 3478
    app.run(host="0.0.0.0", port=port)
