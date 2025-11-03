# src/zapwaha/web/webhooks.py
import os
import json
import logging
import requests
from flask import Blueprint, request, jsonify
from zapwaha.flows.agendamento import route_message

# Client opcional (não dependemos dele para enviar)
try:
    from services.waha import Waha  # opcional
except Exception:
    Waha = None

# ====== Config (ENV) ======
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000").rstrip("/")
WAHA_SESSION = (os.getenv("WAHA_SESSION", "default") or "default").strip()
WAHA_API_KEY = os.getenv("WAHA_API_KEY")  # se setada, enviaremos em X-Api-Key

web_bp = Blueprint("web", __name__)
logger = logging.getLogger("ZapWaha")


# --------------------------------------------------------------------------------------
# Client opcional
# --------------------------------------------------------------------------------------
def build_waha():
    if not Waha:
        return None
    try:
        return Waha(api_url=WAHA_API_URL)
    except TypeError:
        pass
    try:
        return Waha(WAHA_API_URL)
    except TypeError:
        pass
    try:
        obj = Waha()
        for attr in ("api_url", "base_url", "url", "_Waha__api_url"):
            try:
                setattr(obj, attr, WAHA_API_URL)
            except Exception:
                pass
        return obj
    except Exception:
        return None


waha_service = build_waha()


# --------------------------------------------------------------------------------------
# Logs auxiliares
# --------------------------------------------------------------------------------------
def _log_payload(data: dict):
    try:
        txt = json.dumps(data, ensure_ascii=False)[:1000]
        logger.debug(f"[WEBHOOK] payload: {txt}")
    except Exception:
        pass


# --------------------------------------------------------------------------------------
# HTTP direto no WAHA (compatível com variações)
# --------------------------------------------------------------------------------------
def _send_http_waha(chat_id: str, message: str) -> bool:
    """
    Tenta enviar via diferentes variações da API do WAHA.
    Sempre inclui X-Api-Key se WAHA_API_KEY estiver definida.
    """
    base = WAHA_API_URL
    session = WAHA_SESSION

    headers_base = {}
    if WAHA_API_KEY:
        headers_base["X-Api-Key"] = WAHA_API_KEY

    # Caminhos e formatos conhecidos/testados
    url = f"{base}/api/sendText"
    variations = [
        # body com session + chatId + text/message
        (url, {"session": session, "chatId": chat_id, "text": message}, None),
        (url, {"session": session, "chatId": chat_id, "message": message}, None),

        # header x-session / X-Session
        (url, {"chatId": chat_id, "text": message}, {"x-session": session}),
        (url, {"chatId": chat_id, "message": message}, {"x-session": session}),
        (url, {"chatId": chat_id, "text": message}, {"X-Session": session}),
        (url, {"chatId": chat_id, "message": message}, {"X-Session": session}),

        # query ?session=
        (f"{url}?session={session}", {"chatId": chat_id, "text": message}, None),
        (f"{url}?session={session}", {"chatId": chat_id, "message": message}, None),

        # algumas builds usam 'to' no lugar de chatId
        (url, {"session": session, "to": chat_id, "text": message}, None),
        (f"{url}?session={session}", {"to": chat_id, "text": message}, None),

        # caminhos alternativos em builds antigas (muitas vezes 404, mas tentamos)
        (f"{base}/api/sessions/{session}/messages/text", {"chatId": chat_id, "text": message}, None),
        (f"{base}/api/messages/send", {"session": session, "chatId": chat_id, "text": message}, None),
    ]

    for u, b, extra_headers in variations:
        try:
            headers = {**headers_base, **(extra_headers or {})}
            r = requests.post(u, json=b, headers=headers, timeout=10)
            if 200 <= r.status_code < 300:
                logger.info(f"[WAHA HTTP] OK via {u}")
                return True
            logger.warning(f"[WAHA HTTP] {u} -> {r.status_code} {r.text[:200]}")
        except Exception as e:
            logger.warning(f"[WAHA HTTP] erro em {u}: {e}")

    return False


def _send(chat_id: str, message: str):
    """
    1) Tenta HTTP direto (recomendado/estável).
    2) Se falhar, tenta o client (se existir).
    3) Se ainda falhar, print no console (não perde a conversa).
    """
    if _send_http_waha(chat_id, message):
        return

    if waha_service:
        try:
            if hasattr(waha_service, "send_message"):
                try:
                    waha_service.send_message(chat_id=chat_id, message=message)
                    return
                except TypeError:
                    waha_service.send_message(chat_id, message)
                    return
            if hasattr(waha_service, "send_text"):
                try:
                    waha_service.send_text(chat_id=chat_id, text=message)
                    return
                except TypeError:
                    waha_service.send_text(chat_id, message)
                    return
        except Exception as e:
            logger.error(f"Falha ao enviar via WAHA (client): {e}")

    print(f"[SEND-FALLBACK to {chat_id}] {message}")


# --------------------------------------------------------------------------------------
# typing via HTTP (best-effort)
# --------------------------------------------------------------------------------------
def _typing_http(chat_id: str, on: bool):
    try:
        endpoint = "/api/startTyping" if on else "/api/stopTyping"
        headers = {}
        if WAHA_API_KEY:
            headers["X-Api-Key"] = WAHA_API_KEY
        # envia session no body e também tenta header de sessão
        headers["X-Session"] = WAHA_SESSION
        r = requests.post(
            f"{WAHA_API_URL}{endpoint}",
            json={"session": WAHA_SESSION, "chatId": chat_id},
            headers=headers,
            timeout=4,
        )
        if not (200 <= r.status_code < 300):
            logger.debug(f"[WAHA HTTP] typing {endpoint} -> {r.status_code} {r.text[:120]}")
    except Exception:
        pass


def _typing(chat_id: str, on: bool):
    _typing_http(chat_id, on)
    if not waha_service:
        return
    try:
        if on and hasattr(waha_service, "start_typing"):
            try:
                waha_service.start_typing(chat_id=chat_id)
            except TypeError:
                waha_service.start_typing(chat_id)
        if (not on) and hasattr(waha_service, "stop_typing"):
            try:
                waha_service.stop_typing(chat_id=chat_id)
            except TypeError:
                waha_service.stop_typing(chat_id)
    except Exception:
        pass


# --------------------------------------------------------------------------------------
# Helpers de parsing (mais variações aceitas)
# --------------------------------------------------------------------------------------
def _extract_chat_id(payload: dict) -> str | None:
    return (
        payload.get("payload", {}).get("from")
        or payload.get("data", {}).get("from")
        or payload.get("from")
        or payload.get("sender")
        or payload.get("chatId")
        or payload.get("phone")
        or payload.get("data", {}).get("chatId")
        or payload.get("data", {}).get("phone")
        or payload.get("data", {}).get("to")  # algumas builds mandam 'to' no inbound
    )


def _extract_text(payload: dict) -> str:
    # formatos conhecidos do WAHA:
    # { payload: { body: "txt" } }
    # { payload: { text: "txt" } }
    # { data: { msg: { text: "txt" } } }
    # { data: { text: "txt" } } ou { data: { body: "txt" } }
    # { message: { text: "txt" } }
    # { text: "txt" }  /  { body: "txt" }
    return (
        payload.get("payload", {}).get("body")
        or payload.get("payload", {}).get("text")
        or payload.get("data", {}).get("msg", {}).get("text")
        or payload.get("data", {}).get("text")
        or payload.get("data", {}).get("body")
        or payload.get("message", {}).get("text")
        or payload.get("body")
        or payload.get("text")
        or ""
    )


# --------------------------------------------------------------------------------------
# Rotas
# --------------------------------------------------------------------------------------
@web_bp.post("/chatbot/webhook/")
def chatbot_webhook():
    try:
        data = request.get_json(silent=True) or {}
        _log_payload(data)

        chat_id = _extract_chat_id(data)
        text = (_extract_text(data) or "").strip()
        is_group = "@g.us" in (chat_id or "")

        if not chat_id:
            logger.warning("[WEBHOOK] sem chat_id no payload; 400")
            return jsonify({"status": "bad_request"}), 400
        if is_group:
            return jsonify({"status": "success", "message": "Ignorado (grupo)."}), 200

        _typing(chat_id, True)
        route_message(_send, chat_id, text)
        _typing(chat_id, False)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.exception(f"Erro no webhook: {e}")
        try:
            chat_id_on_error = _extract_chat_id(request.get_json(silent=True) or {})
            if chat_id_on_error:
                _send(chat_id_on_error, "Desculpe, ocorreu um erro interno. Digite 'menu' para recomeçar.")
        except Exception:
            pass
        return jsonify({"status": "error", "message": "Erro interno."}), 500


@web_bp.post("/test/incoming")
def test_incoming():
    payload = request.get_json(silent=True) or {}
    chat_id = str(payload.get("user_id", "5511912345678@c.us"))
    text = str(payload.get("text", ""))

    # simula 'typing' para facilitar testes
    _typing(chat_id, True)
    route_message(_send, chat_id, text)
    _typing(chat_id, False)

    return jsonify({"ok": True, "echo": {"chat_id": chat_id, "text": text}})
