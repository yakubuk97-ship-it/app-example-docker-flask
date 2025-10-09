@app.after_request
def allow_telegram_embed(resp):
    resp.headers['X-Frame-Options'] = 'ALLOWALL'
    resp.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://*.t.me https://*.telegram.org;"
    return resp
