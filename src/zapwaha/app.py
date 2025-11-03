# src/zapwaha/app.py
from flask import Flask
from zapwaha.web.webhooks import web_bp

def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(web_bp)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "zapwaha", "status": "healthy"}

    return app

app = create_app()
