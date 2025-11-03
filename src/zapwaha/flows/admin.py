# src/zapwaha/flows/admin.py
from __future__ import annotations
import os, json, re
from datetime import date, datetime
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger("ZapWaha")

# =========================
# Config: quem é admin?
# =========================
def _normalize_chat_id(x: str) -> str:
    x = (x or "").strip()
    if not x:
        return x
    if "@c.us" in x or "@g.us" in x:
        return x
    # se vier só dígitos, assume WhatsApp individual
    if re.fullmatch(r"\d{10,15}", x):
        return f"{x}@c.us"
    return x

def _load_admins() -> set[str]:
    ids: List[str] = []

    # 1) ENV (prioritário). Ex.: ADMIN_NUMBERS="5511912345678@c.us,5511987654321"
    envv = os.getenv("ADMIN_NUMBERS", "")
    if envv.strip():
        for raw in envv.split(","):
            norm = _normalize_chat_id(raw)
            if norm:
                ids.append(norm)

    # 2) Arquivo opcional: /app/config/admins.json com {"admins":[ "...", "..." ]}
    try:
        cfg_path = "/app/config/admins.json"
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
            for raw in data.get("admins", []):
                norm = _normalize_chat_id(raw)
                if norm:
                    ids.append(norm)
    except Exception as e:
        logger.warning(f"[ADMIN] Falha lendo admins.json: {e}")

    # dedup
    return set([x for x in ids if x])

ADMINS = _load_admins()

def is_admin(chat_id: str) -> bool:
    return (chat_id or "") in ADMINS


# =========================
# Caixinhas / UI helpers
# =========================
def _box_loose(header: str, body_lines: list[str], footer_line: str | None) -> str:
    parts = [header] + body_lines + ([footer_line] if footer_line else [])
    width = max((len(p) for p in parts), default=0)
    top    = "╔" + "═" * width + "╗"
    middle = "╠" + "═" * width + "╣"
    bottom = "╚" + "═" * width + "╝"
    body = "\n".join(body_lines + ([footer_line] if footer_line else []))
    return f"{top}\n{header}\n{middle}\n{body}\n{bottom}"

def _nav_footer(lines: list[str]) -> str:
    barra = "─" * 42
    corpo = "\n".join(f"• {ln}" for ln in lines)
    atalhos = "• *menu* — voltar ao início"
    return f"\n\n{barra}\nAtalhos:\n{corpo}\n{atalhos}"


# =========================
# Dependências (Excel + State)
# =========================
try:
    from zapwaha.state.memory import state_manager
except Exception:
    class _FallbackState:
        _mem = {}
        def get_state(self, chat_id): return self._mem.get(chat_id, {}).get("state")
        def set_state(self, chat_id, state, data=None):
            curr = self._mem.get(chat_id, {})
            curr["state"] = state
            if data: curr.update(data)
            self._mem[chat_id] = curr
        def get_data(self, chat_id): return self._mem.get(chat_id, {})
        def update_data(self, chat_id, **kw):
            curr = self._mem.get(chat_id, {})
            curr.update(kw)
            self._mem[chat_id] = curr
        def clear_data(self, chat_id):
            st = self.get_state(chat_id)
            self._mem[chat_id] = {"state": st}
    state_manager = _FallbackState()

try:
    from services import excel_services as excel
except Exception:
    excel = None


# =========================
# Fila de contato humano
# =========================
class ContactQueue:
    _seq = 1000
    _pending: list[dict] = []  # cada item: {id, client, nome, cpf, motivo, created}

    @classmethod
    def add(cls, client_chat_id: str, nome: Optional[str], cpf: Optional[str], motivo: Optional[str]) -> dict:
        cls._seq += 1
        ticket = f"TK{cls._seq}"
        item = {
            "id": ticket,
            "client": client_chat_id,
            "nome": nome or "(sem nome)",
            "cpf": cpf or "(sem CPF)",
            "motivo": (motivo or "").strip() or "(motivo não informado)",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cls._pending.append(item)
        return item

    @classmethod
    def list(cls) -> list[dict]:
        return list(cls._pending)

    @classmethod
    def pop_by_ticket(cls, ticket: str) -> Optional[dict]:
        for i, it in enumerate(cls._pending):
            if it["id"] == ticket:
                return cls._pending.pop(i)
        return None

    @classmethod
    def get_by_index(cls, idx1: int) -> Optional[dict]:
        i0 = idx1 - 1
        if 0 <= i0 < len(cls._pending):
            return cls._pending.pop(i0)
        return None


# =========================
# Proxy (admin <-> cliente)
# =========================
class ProxyHub:
    _a2c: Dict[str, str] = {}  # admin -> client
    _c2a: Dict[str, str] = {}  # client -> admin

    @classmethod
    def start(cls, admin_id: str, client_id: str):
        cls._a2c[admin_id] = client_id
        cls._c2a[client_id] = admin_id

    @classmethod
    def end_by_admin(cls, admin_id: str) -> Optional[str]:
        client = cls._a2c.pop(admin_id, None)
        if client:
            cls._c2a.pop(client, None)
        return client

    @classmethod
    def end_by_client(cls, client_id: str) -> Optional[str]:
        admin = cls._c2a.pop(client_id, None)
        if admin:
            cls._a2c.pop(admin, None)
        return admin

    @classmethod
    def counterpart(cls, who: str) -> Optional[str]:
        return cls._a2c.get(who) or cls._c2a.get(who)

    @classmethod
    def admin_has_chat(cls, admin_id: str) -> bool:
        return admin_id in cls._a2c

    @classmethod
    def client_in_chat(cls, client_id: str) -> bool:
        return client_id in cls._c2a


def queue_contact_request(send, client_chat_id: str, nome: Optional[str], cpf: Optional[str], motivo: Optional[str] = None):
    """
    Chame isto do fluxo do CLIENTE quando quiser escalar p/ humano.
    Ex.: admin.queue_contact_request(send, chat_id, nome, cpf, 'Dúvida X')
    """
    item = ContactQueue.add(client_chat_id, nome, cpf, motivo)
    # notifica todos admin
    if ADMINS:
        txt = (
            "🛎️ *Novo pedido de contato humano!*\n\n"
            f"• Cliente: *{item['nome']}*\n"
            f"• CPF: *{item['cpf']}*\n"
            f"• ChatID: `{item['client']}`\n"
            f"• Motivo: {item['motivo']}\n"
            f"• Ticket: *{item['id']}*\n\n"
            "Responda *aceitar <n>* (pelo índice) ou */aceitar <TICKET>* para iniciar um chat privado."
        )
        for adm in ADMINS:
            try:
                send(adm, txt)
            except Exception:
                pass


# =========================
# Painel Admin (menu/estados)
# =========================
S_ADM_MENU = "ADM_MENU"
S_ADM_WAIT_DATE = "ADM_WAIT_DATE"

def _send_admin_menu(send, chat_id: str):
    send(chat_id,
        "🛠️ *Painel do Admin*\n\n"
        "1) 📅 Ver agenda de *HOJE*\n"
        "2) 📆 Ver agenda por *data*\n"
        "3) 🧑‍💼 *Contatos pendentes* (pedidos de humano)\n"
        "4) 🔌 *Encerrar chat humano* atual\n"
        "9) ↩️ Sair (voltar ao menu do cliente)\n"
        + _nav_footer(["Dica: */aceitar <TICKET>* para aceitar direto"]))
    state_manager.set_state(chat_id, S_ADM_MENU)

def _format_agenda_do_dia(data_str: str) -> str:
    rows = []
    try:
        if excel and hasattr(excel, "listar_agendamentos_por_data"):
            rows = excel.listar_agendamentos_por_data(data_str)
        elif excel and hasattr(excel, "_read_rows"):
            rows = [r for r in excel._read_rows() if (r.get("Data") == data_str)]
    except Exception as e:
        logger.warning(f"[ADMIN] Falha ao ler agenda: {e}")
        rows = []

    if not rows:
        return _box_loose(f"🗓️ Agenda — {data_str}", ["(sem agendamentos)"], " ")

    linhas = []
    # ordena por hora
    def _hkey(r):
        try:
            return r.get("Hora") or ""
        except Exception:
            return ""
    rows = sorted(rows, key=_hkey)

    for r in rows:
        h = r.get("Hora") or "--:--"
        nm = r.get("ClienteNome") or "(s/ nome)"
        st = r.get("Status") or "-"
        linhas.append(f"{h} — {nm} ({st})")
    return _box_loose(f"🗓️ Agenda — {data_str}", linhas, " ")


def _listar_pendentes_txt() -> str:
    pend = ContactQueue.list()
    if not pend:
        return _box_loose("📬 Contatos pendentes", ["(nenhum pedido)"], " ")
    body = []
    for i, it in enumerate(pend, start=1):
        body.append(f"{i}) {it['nome']} — CPF {it['cpf']} — id={it['id']}")
    footer = "Use: *aceitar <n>* ou */aceitar <TICKET>*"
    return _box_loose("📬 Contatos pendentes", body, footer)


def _handle_admin_option(send, chat_id: str, t: str):
    if t == "1":
        hoje = date.today().strftime("%d/%m/%Y")
        send(chat_id, _format_agenda_do_dia(hoje))
        return _send_admin_menu(send, chat_id)

    if t == "2":
        send(chat_id, "Informe a *data* (DD/MM/AAAA) para listar os agendamentos.")
        return state_manager.set_state(chat_id, S_ADM_WAIT_DATE)

    if t == "3":
        send(chat_id, _listar_pendentes_txt())
        return _send_admin_menu(send, chat_id)

    if t == "4":
        if ProxyHub.admin_has_chat(chat_id):
            client = ProxyHub.end_by_admin(chat_id)
            if client:
                send(chat_id, "🔌 Chat humano encerrado. Mensagens voltam ao fluxo normal.")
                try:
                    send(client, "🔌 O atendente encerrou o chat humano. Você voltou ao atendimento automático.")
                except Exception:
                    pass
        else:
            send(chat_id, "Não há chat humano ativo para encerrar.")
        return _send_admin_menu(send, chat_id)

    if t == "9":
        # “sair”: apenas limpa estado (o roteador principal vai cair no fluxo cliente)
        state_manager.set_state(chat_id, None)
        return send(chat_id, "Saindo do painel do admin. Digite *menu* para ver o menu do cliente.")

    # aceitar <n> (por índice)
    m = re.fullmatch(r"aceitar\s+(\d+)", t, flags=re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        item = ContactQueue.get_by_index(idx)
        if not item:
            send(chat_id, "Índice inválido ou já atendido.")
            return _send_admin_menu(send, chat_id)
        _start_proxy_with_item(send, chat_id, item)
        return

    # /aceitar <TICKET>
    m = re.fullmatch(r"/?aceitar\s+([A-Za-z0-9_-]+)", t, flags=re.IGNORECASE)
    if m:
        ticket = m.group(1)
        item = ContactQueue.pop_by_ticket(ticket)
        if not item:
            send(chat_id, "Ticket inválido, inexistente ou já atendido.")
            return _send_admin_menu(send, chat_id)
        _start_proxy_with_item(send, chat_id, item)
        return

    send(chat_id, "Opção inválida. Use 1, 2, 3, 4 ou 9, ou comandos *aceitar <n>* / */aceitar <ticket>*.")
    _send_admin_menu(send, chat_id)

def _start_proxy_with_item(send, admin_id: str, item: dict):
    client = item["client"]
    ProxyHub.start(admin_id, client)
    send(admin_id,
         "✅ Você está *conectado* ao cliente.\n"
        "Envie suas mensagens normalmente para que eu repasse a ele.\n"
         "Para encerrar: */encerrar*.")
    try:
        send(client,
            "🧑‍💼 Um atendente assumiu sua conversa.\n"
            "Tudo que você enviar será repassado a ele.\n"
            "Para encerrar, responda *encerrar*.")
    except Exception:
        pass


# =========================
# Relay: intercepta antes do roteador
# =========================
def maybe_relay(send, chat_id: str, text: str) -> bool:
    """
    Se *chat_id* está em um chat humano ativo, faz o repasse e retorna True.
    Se for admin e a mensagem começar com '/', *não* repassa (deixa cair no menu admin).
    """
    t = (text or "").strip()

    # ADMIN → CLIENTE
    if chat_id in ProxyHub._a2c:
        if t.startswith("/"):  # comandos admin durante chat
            if t.lower().startswith("/encerrar"):
                client = ProxyHub.end_by_admin(chat_id)
                send(chat_id, "🔌 Chat humano encerrado.")
                if client:
                    try:
                        send(client, "🔌 O atendente encerrou o chat humano. Você voltou ao atendimento automático.")
                    except Exception:
                        pass
                return True
            # deixa cair no painel admin (/aceitar etc.)
            return False
        # mensagem normal → repassar
        client = ProxyHub._a2c[chat_id]
        try:
            send(client, f"(Atendente) {t}")
        except Exception:
            pass
        return True

    # CLIENTE → ADMIN
    if chat_id in ProxyHub._c2a:
        # permitir o cliente encerrar
        if t.lower() in ("encerrar", "/encerrar", "fim"):
            admin = ProxyHub.end_by_client(chat_id)
            send(chat_id, "🔌 Você encerrou o chat humano. Voltando ao atendimento automático.")
            if admin:
                try:
                    send(admin, "🔌 O cliente encerrou o chat humano.")
                except Exception:
                    pass
            return True
        admin = ProxyHub._c2a[chat_id]
        try:
            send(admin, f"(Cliente) {t}")
        except Exception:
            pass
        return True

    return False


# =========================
# Roteador do Admin
# =========================
def route_admin_message(send, chat_id: str, text: str):
    t = (text or "").strip()

    # atalhos globais
    if t.lower() in ("menu", "/menu", "painel", "/painel"):
        return _send_admin_menu(send, chat_id)

    # se admin já está em chat humano, comandos são tratados no maybe_relay
    if ProxyHub.admin_has_chat(chat_id):
        # qualquer comando de barra cai no painel
        if t.startswith("/"):
            return _handle_admin_option(send, chat_id, t)
        # sem barra — provavelmente já foi relayed no maybe_relay
        return _send_admin_menu(send, chat_id)

    # estados
    st = state_manager.get_state(chat_id)
    if st not in (S_ADM_MENU, S_ADM_WAIT_DATE):
        return _send_admin_menu(send, chat_id)

    if st == S_ADM_MENU:
        return _handle_admin_option(send, chat_id, t)

    if st == S_ADM_WAIT_DATE:
        # parse DD/MM/AAAA
        m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", t)
        if not m:
            send(chat_id, "Data inválida. Use DD/MM/AAAA.")
            return
        dd, mm, yyyy = map(int, m.groups())
        try:
            _ = date(yyyy, mm, dd)
        except ValueError:
            return send(chat_id, "Data inválida. Use DD/MM/AAAA.")
        data_str = f"{dd:02d}/{mm:02d}/{yyyy}"
        send(chat_id, _format_agenda_do_dia(data_str))
        return _send_admin_menu(send, chat_id)
