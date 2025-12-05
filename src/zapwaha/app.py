# src/zapwaha/app.py
from flask import Flask
from zapwaha.web.webhooks import web_bp
from zapwaha.web.debug import debug_bp   # <— NOVO

app = Flask(__name__)

# se quiser, guarda o token também no config (fallback):
import os
app.config["ADMIN_TOKEN"] = os.getenv("ADMIN_TOKEN")

# blueprints
app.register_blueprint(web_bp)
app.register_blueprint(debug_bp, url_prefix="/debug/clients")  # <— exatamente esse prefixo
