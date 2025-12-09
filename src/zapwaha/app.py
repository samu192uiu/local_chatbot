# src/zapwaha/app.py
from flask import Flask
from zapwaha.web.webhooks import web_bp
from zapwaha.web.debug import debug_bp   # <— NOVO
from zapwaha.web.agenda_panel import agenda_bp  # <— NOVO: Painel de Agenda
import threading
import time
import logging

logger = logging.getLogger("ZapWaha")

app = Flask(__name__)

# se quiser, guarda o token também no config (fallback):
import os
app.config["ADMIN_TOKEN"] = os.getenv("ADMIN_TOKEN")

# blueprints
app.register_blueprint(web_bp)
app.register_blueprint(debug_bp, url_prefix="/debug/clients")  # <— exatamente esse prefixo
app.register_blueprint(agenda_bp)  # <— NOVO: /admin/agenda/*

# ========== JOB DE LIMPEZA DE SLOTS EXPIRADOS ==========

def _cleanup_job():
    """
    Job em background que limpa slots expirados a cada 1 minuto.
    """
    logger.info("[CLEANUP] Iniciando job de limpeza de slots expirados")
    
    while True:
        try:
            time.sleep(60)  # Executar a cada 1 minuto
            
            # Importar excel_services
            try:
                from services import excel_services as excel
                if hasattr(excel, "liberar_slots_expirados"):
                    liberados = excel.liberar_slots_expirados()
                    if liberados > 0:
                        logger.info(f"[CLEANUP] {liberados} slots expirados liberados")
            except Exception as e:
                logger.error(f"[CLEANUP] Erro ao liberar slots: {e}")
                
        except Exception as e:
            logger.error(f"[CLEANUP] Erro no job de limpeza: {e}")
            time.sleep(60)  # Continuar tentando

# Iniciar job em thread separada
cleanup_thread = threading.Thread(target=_cleanup_job, daemon=True)
cleanup_thread.start()
logger.info("[APP] Job de limpeza de slots iniciado")
