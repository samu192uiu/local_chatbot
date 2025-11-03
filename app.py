import os, sys
# app.py (raiz) - habilitar logs do nosso módulo
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("ZapWaha").setLevel(logging.INFO)

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from zapwaha.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
