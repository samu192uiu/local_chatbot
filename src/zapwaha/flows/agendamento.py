from __future__ import annotations
import os
import re
from datetime import date, time, datetime, timedelta
import logging

# ==== UX helpers (rodapés e bullets) ====
def _nav_footer(linhas: list[str]) -> str:
    barra = "─" * 42
    corpo = "\n".join(f"• {ln}" for ln in linhas)
    atalhos = "• *menu* — voltar ao início"
    return f"\n\n{barra}\nAtalhos:\n{corpo}\n{atalhos}"

def _bullets(itens: list[tuple[str, str, str]]) -> str:
    return "\n".join(f"{emo} *{cmd}* — {desc}" for emo, cmd, desc in itens)

def _yes_no_footer(confirma_o_que: str) -> str:
    return _nav_footer([
        _bullets([("✅","sim", f"confirmar {confirma_o_que}"),
                  ("✏️","não", f"ajustar {confirma_o_que}")])
    ])

# -------------------------------
# Estado (com fallback)
# -------------------------------
try:
    from zapwaha.state.memory import state_manager  # esperado
except Exception:
    class _FallbackState:
        _mem = {}
        def get_state(self, chat_id): return self._mem.get(chat_id, {}).get("state", "MENU_PRINCIPAL")
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

# -------------------------------
# Excel (import robusto)
# -------------------------------
try:
    from services import excel_services as excel
except Exception:
    excel = None  # permite rodar sem Excel em dev

logger = logging.getLogger("ZapWaha")

VALOR_CONSULTA = 150.00
DEFAULT_SLOTS = ["08:00","09:00","10:00","11:00","13:00","14:00","15:00","16:00","17:00"]

# ==== Admin config (ENV e opcional arquivo JSON) ====
def _admin_ids() -> set[str]:
    ids = set()
    # ENV
    raw = os.getenv("ADMIN_CHAT_IDS", "")
    if raw:
        ids.update(x.strip() for x in raw.split(",") if x.strip())
    # arquivo opcional /app/config/admins.json  -> {"admins": ["...@c.us", "...@c.us"]}
    try:
        import json, pathlib
        p = pathlib.Path("/app/config/admins.json")
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for x in data.get("admins", []):
                if isinstance(x, str) and x.strip():
                    ids.add(x.strip())
    except Exception:
        pass
    return ids

# -------------------------------
# Helpers de validação / parsing
# -------------------------------
_re_date_full = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
_re_date_dm   = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})\b(?!\s*\d)")
_re_time      = re.compile(r"\b(\d{1,2}):(\d{2})\b")

def _safe_date(d:int,m:int,y:int) -> date|None:
    try:
        if y < 100:  # 2 dígitos -> 2000+
            y = 2000 + y
        return date(y,m,d)
    except ValueError:
        return None

def parse_date_fuzzy_and_optional_time(text: str, default_year: int|None=None):
    """
    Aceita:
      - DD/MM/AAAA, DD-MM-AAAA, DD.MM.AAAA
      - DD/MM, DD-MM, DD.MM  -> completa com default_year (ou ano atual)
      - opcional HH:MM
    Retorna: (data_str, hora_str|None, was_inferred)
    """
    text = (text or "").strip()
    hora_str = None
    mt = _re_time.search(text)
    if mt:
        hh, mm = map(int, mt.groups())
        try:
            _ = time(hh, mm)
            hora_str = f"{hh:02d}:{mm:02d}"
        except ValueError:
            hora_str = None

    mfull = _re_date_full.search(text)
    if mfull:
        dd, mm, yy = mfull.groups()
        dd, mm, yy = int(dd), int(mm), int(yy)
        dt = _safe_date(dd, mm, yy)
        if not dt:
            return None, None, False
        return dt.strftime("%d/%m/%Y"), hora_str, False

    mdm = _re_date_dm.search(text)
    if mdm:
        dd, mm = map(int, mdm.groups())
        year = default_year or date.today().year
        dt = _safe_date(dd, mm, year)
        if not dt:
            return None, None, False
        return dt.strftime("%d/%m/%Y"), hora_str, True

    return None, None, False

def validar_nome(nome: str) -> bool:
    return len((nome or "").strip()) >= 3 and " " in nome.strip()

def validar_data_nascimento(nasc_str: str) -> bool:
    m = _re_date_full.fullmatch((nasc_str or "").strip())
    if not m: return False
    dd, mm, yy = map(int, m.groups())
    dt = _safe_date(dd, mm, yy)
    if not dt: return False
    hoje = date.today()
    if dt >= hoje:
        return False
    idade = (hoje - dt).days // 365
    return 0 <= idade <= 120

def _cpf_puro(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")

def validar_cpf(cpf: str) -> bool:
    cpf = _cpf_puro(cpf)
    if (not cpf) or len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    def dv(digs):
        s = sum(int(digs[i]) * (len(digs)+1 - i) for i in range(len(digs)))
        r = (s * 10) % 11
        return 0 if r == 10 else r
    d1 = dv(cpf[:9]); d2 = dv(cpf[:10])
    return int(cpf[9]) == d1 and int(cpf[10]) == d2

def format_money(v: float) -> str:
    return f"R$ {v:.2f}".replace(".", ",")

def _format_grade_compact(data_str: str, slots: list[str], livres: set[str]) -> str:
    top =  "╔═══════════════════════════╗"
    sep =  "╠═══════════════════════════╣"
    bot =  "╚═══════════════════════════╝"
    header = f"  ⏰ Horários disponíveis — {data_str}"
    linhas = []
    livres_flag = False
    for i, h in enumerate(slots, 1):
        livre = (h in livres)
        status = "✅ Livre" if livre else "❌ Ocupado"
        if livre: livres_flag = True
        linhas.append(f"{i} - {h} - {status}")
    rodape = ("👉 Digite o número do horário desejado."
              if livres_flag else
              "👉 Nenhum horário livre. Envie outra data (DD/MM/AAAA).")
    bloc = "\n".join([top, header, sep, *linhas, rodape, bot])
    return bloc, livres_flag

# -------------------------------
# Estados (cliente)
# -------------------------------
S_MENU = "MENU_PRINCIPAL"
S_MENU_OPCAO = "ESPERANDO_OPCAO_MENU"

S_AG_SUBMENU = "AGENDAMENTO_ESCOLHER_ACAO"
S_NOME = "AG_NOME"
S_NOME_CONF = "AG_NOME_CONF"
S_NASC = "AG_NASC"
S_NASC_CONF = "AG_NASC_CONF"
S_CPF = "AG_CPF"
S_CPF_CONF = "AG_CPF_CONF"

S_DATA = "AG_DATA"
S_DATA_CONF = "AG_DATA_CONF"
S_MOSTRAR_HORAS = "AG_MOSTRAR_HORAS"
S_ESCOLHER_HORA = "AG_ESCOLHER_HORA"

S_ESCOLHENDO_PAGTO = "AG_ESCOLHENDO_PAGAMENTO"
S_AGUARDANDO_PIX = "AG_AGUARDANDO_COMPROVANTE_PIX"
S_AGUARDANDO_LINK = "AG_AGUARDANDO_PAGAMENTO_LINK"

# Atendimento humano
S_HUM_PEDIR_RESUMO = "HUM_PEDIR_RESUMO"
S_HUM_AGUARDANDO   = "HUM_AGUARDANDO"
S_HUM_ATIVO        = "HUM_ATIVO"

# -------------------------------
# Estados (admin)
# -------------------------------
S_ADMIN_MENU  = "ADMIN_MENU"
S_ADMIN_RELAY = "ADMIN_RELAY"

# -------------------------------
# Estruturas de handoff
# -------------------------------
_ticket_seq = 100
_tickets: dict[int, dict] = {}      # ticket_id -> {client_id, nome, cpf, resumo, status, admin_id}
_relays: dict[str, str] = {}        # admin_id -> client_id (sessão ativa)

def _new_ticket_id() -> int:
    global _ticket_seq
    _ticket_seq += 1
    return _ticket_seq

def _find_ticket_by_client(client_id: str) -> int|None:
    for tid, t in _tickets.items():
        if t.get("client_id") == client_id and t.get("status") in ("waiting","active"):
            return tid
    return None

# -------------------------------
# Timeout de atendimento humano
# -------------------------------
HUMAN_TIMEOUT_MIN = 10  # ajuste livre para testes

def _now():
    return datetime.now()

def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _extend_handoff_timeout(chat_id: str, minutes: int = HUMAN_TIMEOUT_MIN):
    """Renova o prazo de expiração do ticket."""
    expires_at = _now() + timedelta(minutes=minutes)
    state_manager.update_data(chat_id, relay_expires_at=_iso(expires_at))

def _reset_handoff_fields(chat_id: str):
    """Limpa SOMENTE campos do handoff (mantém nome/cpf/etc)."""
    state_manager.update_data(
        chat_id,
        relay_status=None,          # "waiting" | "active" | None
        relay_active=False,
        relay_admin=None,
        relay_expires_at=None,
        # ticket_id permanece (histórico). Remova se preferir:
        # ticket_id=None,
    )

def _check_and_expire_handoff(send, chat_id: str) -> bool:
    """
    Se o ticket do cliente já expirou, encerra e avisa. Retorna True se encerrou.
    Checagem pontual (para este chat_id).
    """
    dt = state_manager.get_data(chat_id) or {}
    status = dt.get("relay_status")
    if status not in ("waiting", "active"):
        return False

    ex_str = dt.get("relay_expires_at")
    ex_dt = _parse_iso(ex_str) if ex_str else None
    if not ex_dt or _now() < ex_dt:
        return False  # ainda válido

    admin_id = dt.get("relay_admin")
    tid = dt.get("ticket_id")
    ticket_label = f"#{tid}" if tid else "(sem ticket)"

    # quebra vínculo em _relays
    if admin_id and _relays.get(admin_id) == chat_id:
        _relays.pop(admin_id, None)

    # fecha ticket se existir
    if tid and tid in _tickets:
        _tickets[tid]["status"] = "closed"

    # mensagens
    if status == "waiting":
        send(chat_id, "⏰ O atendimento foi *encerrado* porque não foi assumido a tempo.\nSe preferir, peça *Falar com atendente* novamente.")
    else:
        send(chat_id, "⏰ O atendimento foi *encerrado por inatividade*.\nSe ainda precisar, peça *Falar com atendente* novamente.")

    if admin_id:
        send(admin_id, f"⏹️ Ticket {ticket_label} encerrado por inatividade.")

    # reset
    _reset_handoff_fields(chat_id)
    state_manager.set_state(chat_id, S_MENU)
    return True

def _sweep_expired_handoffs(send):
    """
    Varredura global: fecha tickets 'waiting' ou 'active' expirados.
    Dispara a cada mensagem recebida (qualquer usuário).
    """
    for tid, tk in list(_tickets.items()):
        status = tk.get("status")
        if status not in ("waiting", "active"):
            continue
        client_id = tk.get("client_id")
        if not client_id:
            continue
        dt = state_manager.get_data(client_id) or {}
        ex_str = dt.get("relay_expires_at")
        ex_dt = _parse_iso(ex_str) if ex_str else None
        if not ex_dt or _now() < ex_dt:
            continue  # ainda válido

        admin_id = dt.get("relay_admin")
        prev_status = status
        if admin_id and _relays.get(admin_id) == client_id:
            _relays.pop(admin_id, None)

        _tickets[tid]["status"] = "closed"
        _reset_handoff_fields(client_id)
        state_manager.set_state(client_id, S_MENU)

        if prev_status == "waiting":
            send(client_id, "⏰ O atendimento foi *encerrado* porque não foi assumido a tempo.\nSe preferir, peça *Falar com atendente* novamente.")
        else:
            send(client_id, "⏰ O atendimento foi *encerrado por inatividade*.\nSe ainda precisar, peça *Falar com atendente* novamente.")
        if admin_id:
            send(admin_id, f"⏹️ Ticket #{tid} encerrado por inatividade.")

# -------------------------------
# Pré-reserva e atualização
# -------------------------------
def _make_key(data_str: str, hora_str: str, chat_id: str) -> str:
    if excel and hasattr(excel, "make_key"):
        try:
            return excel.make_key(data_str, hora_str, chat_id)
        except Exception:
            pass
    return f"{data_str}_{hora_str}_{chat_id}"

def _pre_reservar(send, chat_id: str, data_str: str, hora_str: str) -> bool:
    dados = state_manager.get_data(chat_id)
    nome = dados.get("nome")
    nasc = dados.get("data_nascimento") or dados.get("nascimento")
    cpf  = dados.get("cpf")

    if not excel or not hasattr(excel, "adicionar_agendamento"):
        logger.warning("[FLOW] Excel não disponível; pulando gravação.")
        return True

    try:
        chave = excel.adicionar_agendamento(
            data_str, hora_str, chat_id,
            status="Pendente Pagamento",
            cliente_nome=nome,
            data_nasc=nasc,
            cpf=cpf,
            valor_pago=None
        )
        if not chave:
            chave = _make_key(data_str, hora_str, chat_id)
        state_manager.update_data(chat_id, ag_chave=chave, data=data_str, hora=hora_str)
        logger.info(f"[FLOW] Pré-reserva criada: {chave}")
        return True
    except Exception as e:
        logger.exception(f"[FLOW] Falha ao gravar pré-reserva ({data_str} {hora_str} {chat_id}): {e}")
        send(chat_id, "Não consegui salvar sua pré-reserva agora. Tente outro horário, por favor.")
        return False

def _update_status_confirmado(chat_id: str) -> bool:
    if not excel:
        return False
    dt = state_manager.get_data(chat_id)
    data_ag = dt.get("data"); hora_ag = dt.get("hora")
    chave = dt.get("ag_chave") or _make_key(data_ag, hora_ag, chat_id)

    if hasattr(excel, "atualizar_status_por_chave"):
        try:
            ok = excel.atualizar_status_por_chave(chave, "Confirmado")
            if ok: return True
        except TypeError:
            try:
                ok = excel.atualizar_status_por_chave(data_ag, hora_ag, chat_id, "Confirmado")
                if ok: return True
            except Exception:
                pass
        except Exception:
            pass

    if hasattr(excel, "atualizar_status"):
        try:
            ok = excel.atualizar_status(chave, "Confirmado")
            if ok: return True
        except TypeError:
            try:
                ok = excel.atualizar_status(data_ag, hora_ag, chat_id, "Confirmado")
                if ok: return True
            except Exception:
                pass
        except Exception:
            pass

    return False

# -------------------------------
# Entradas de fluxo (públicas)
# -------------------------------
def route_message(send, chat_id: str, text: str):
    t = (text or "").strip()

    # Varre expirados globalmente a cada mensagem recebida
    _sweep_expired_handoffs(send)

    # ADMIN primeiro
    if chat_id in _admin_ids():
        return _route_admin(send, chat_id, t)

    # Checa expiração da sessão deste cliente
    if _check_and_expire_handoff(send, chat_id):
        return

    # Atalhos globais do cliente
    if t.lower() in ("menu", "voltar", "inicio", "início", "sair"):
        return _send_main_menu(send, chat_id)

    st = state_manager.get_state(chat_id)

    # 👉 CORREÇÃO: rotear o estado de pedir resumo (opção 4)
    if st == S_HUM_PEDIR_RESUMO:
        return _handle_humano_resumo(send, chat_id, t)
    if st == S_HUM_AGUARDANDO:
        return _handle_humano_aguardando(send, chat_id, t)
    if st == S_HUM_ATIVO:
        return _relay_from_client(send, chat_id, t)

    if st in (S_MENU, None):
        return _send_main_menu(send, chat_id)

    if st == S_MENU_OPCAO:
        return _handle_menu_opcao(send, chat_id, t)

    if st == S_AG_SUBMENU:
        return _handle_ag_submenu(send, chat_id, t)

    if st == S_NOME:
        return _handle_nome(send, chat_id, t)
    if st == S_NOME_CONF:
        return _handle_nome_conf(send, chat_id, t)

    if st == S_NASC:
        return _handle_nasc(send, chat_id, t)
    if st == S_NASC_CONF:
        return _handle_nasc_conf(send, chat_id, t)

    if st == S_CPF:
        return _handle_cpf(send, chat_id, t)
    if st == S_CPF_CONF:
        return _handle_cpf_conf(send, chat_id, t)

    if st == S_DATA:
        return _handle_data(send, chat_id, t)
    if st == S_DATA_CONF:
        return _handle_data_conf(send, chat_id, t)
    if st == S_MOSTRAR_HORAS:
        return _handle_escolha_hora_index(send, chat_id, t)
    if st == S_ESCOLHER_HORA:
        return _handle_hora_livre(send, chat_id, t)

    if st == S_ESCOLHENDO_PAGTO:
        return _handle_escolha_pagamento(send, chat_id, t)

    if st in (S_AGUARDANDO_PIX, S_AGUARDANDO_LINK):
        return _handle_confirmacao_pagamento(send, chat_id, t)

    return _send_main_menu(send, chat_id)

# -------------------------------
# Blocos de fluxo - CLIENTE
# -------------------------------
def _send_main_menu(send, chat_id):
    send(chat_id,
        "👋 *Bem-vindo(a) à Clínica!*\n\n"
        "Como podemos te ajudar hoje?\n\n"
        "1️⃣ Agendar ou Gerenciar Aulas\n"
        "2️⃣ Informações e Valores\n"
        "3️⃣ Dúvidas Frequentes\n"
        "4️⃣ Falar com atendente"
        + _nav_footer(["Responda com *1*, *2*, *3* ou *4*"]))
    state_manager.set_state(chat_id, S_MENU_OPCAO)

def _handle_menu_opcao(send, chat_id, t):
    if t == "1":
        send(chat_id,
            "🗓️ *Agendamento e Aulas*\n\n"
            "1. Agendar nova aula/consulta\n"
            "2. Confirmar minha próxima aula\n"
            "3. Remarcar aula\n"
            "4. Cancelar aula"
            + _nav_footer(["Responda com *1*, *2*, *3* ou *4*"]))
        state_manager.set_state(chat_id, S_AG_SUBMENU)
    elif t == "2":
        send(chat_id, "Opção 2 (Informações) - Em construção...\nDigite *menu* para voltar.")
        state_manager.set_state(chat_id, S_MENU)
    elif t == "3":
        send(chat_id, "Opção 3 (Dúvidas) - Em construção...\nDigite *menu* para voltar.")
        state_manager.set_state(chat_id, S_MENU)
    elif t == "4":
        return _start_handoff(send, chat_id)
    else:
        send(chat_id, "Opção inválida. Digite 1, 2, 3 ou 4, ou *menu* para voltar.")

def _handle_ag_submenu(send, chat_id, t):
    if t == "1":
        send(chat_id,
            "Vamos começar seu cadastro 😊\n\n"
            "✍️ Qual é *seu nome completo*?"
            + _nav_footer(["Ex.: *Maria Clara Souza*"]))
        state_manager.set_state(chat_id, S_NOME)
    else:
        send(chat_id, "Em breve.\nDigite *menu* para voltar ou *1* para agendar nova aula.")

def _handle_nome(send, chat_id, nome):
    if not validar_nome(nome):
        return send(chat_id, "Preciso do *nome completo*. Pode escrever novamente?")
    state_manager.update_data(chat_id, nome_tmp=(nome or "").strip())
    state_manager.set_state(chat_id, S_NOME_CONF)
    send(chat_id,
        f"Você confirma seu nome como:\n\n*{nome.strip()}* ?"
        + _yes_no_footer("o *nome*"))

def _handle_nome_conf(send, chat_id, t):
    if t.lower() == "sim":
        dt = state_manager.get_data(chat_id)
        state_manager.update_data(chat_id, nome=dt.get("nome_tmp"))
        send(chat_id,
            "📅 Qual é a sua *data de nascimento*? (formato *DD/MM/AAAA*)"
            + _nav_footer(["Ex.: *15/04/1995*"]))
        state_manager.set_state(chat_id, S_NASC)
    elif t.lower() in ("não", "nao"):
        send(chat_id, "Sem problemas. Qual é *seu nome completo*?")
        state_manager.set_state(chat_id, S_NOME)
    else:
        send(chat_id, "Por favor responda *sim* ou *não*.")

def _handle_nasc(send, chat_id, nasc):
    nasc = (nasc or "").strip()
    if not validar_data_nascimento(nasc):
        return send(chat_id, "Formato inválido ou data incoerente. Informe no formato *DD/MM/AAAA* (ex: 15/04/1995).")
    state_manager.update_data(chat_id, nasc_tmp=nasc)
    state_manager.set_state(chat_id, S_NASC_CONF)
    send(chat_id, f"Confirma sua *data de nascimento* como *{nasc}*?"
        + _yes_no_footer("a *data de nascimento*"))

def _handle_nasc_conf(send, chat_id, t):
    if t.lower() == "sim":
        dt = state_manager.get_data(chat_id)
        state_manager.update_data(chat_id, data_nascimento=dt.get("nasc_tmp"))
        send(chat_id,
        "🪪 Me informe seu *CPF* (apenas números)."
        + _nav_footer(["Ex.: *12345678909*"]))
        state_manager.set_state(chat_id, S_CPF)
    elif t.lower() in ("não", "nao"):
        send(chat_id, "Ok, qual é a sua *data de nascimento*? (DD/MM/AAAA)")
        state_manager.set_state(chat_id, S_NASC)
    else:
        send(chat_id, "Responda *sim* ou *não*, por favor.")

def _handle_cpf(send, chat_id, cpf):
    if not validar_cpf(cpf):
        return send(chat_id, "CPF inválido. Envie novamente (apenas números).")
    cpf_num = _cpf_puro(cpf)
    state_manager.update_data(chat_id, cpf_tmp=cpf_num)
    state_manager.set_state(chat_id, S_CPF_CONF)
    send(chat_id,
        f"Confirma seu *CPF* como *{cpf_num[:3]}.{cpf_num[3:6]}.{cpf_num[6:9]}-{cpf_num[9:]}*?"
        + _yes_no_footer("o *CPF*"))

def _handle_cpf_conf(send, chat_id, t):
    if t.lower() == "sim":
        dt = state_manager.get_data(chat_id)
        state_manager.update_data(chat_id, cpf=dt.get("cpf_tmp"))
        send(chat_id,
            "Perfeito! 🎯\n"
            "Para qual *data* você quer agendar? (formato *DD/MM/AAAA* ou *DD/MM*)"
            + _nav_footer(["Ex.: *28/10/2025* ou *28/10*"]))
        state_manager.set_state(chat_id, S_DATA)
    elif t.lower() in ("não", "nao"):
        send(chat_id, "Ok, me informe novamente seu *CPF* (apenas números).")
        state_manager.set_state(chat_id, S_CPF)
    else:
        send(chat_id, "Responda *sim* ou *não*, por favor.")

# ===== datas =====
def _handle_data(send, chat_id, texto):
    data_str, hora_str, inferred = parse_date_fuzzy_and_optional_time(
        texto, default_year=date.today().year
    )
    if not data_str:
        return send(chat_id, "Não entendi a *data*. Informe no formato *DD/MM/AAAA* (ex: 28/10/2025) ou *DD/MM* (ex: 28/10).")

    if inferred:
        state_manager.update_data(chat_id, data_sugerida=data_str, hora_sugerida=hora_str)
        state_manager.set_state(chat_id, S_DATA_CONF)
        return send(chat_id, f"Você quis dizer *{data_str}*?" + _yes_no_footer("a *data*"))

    if hora_str:
        return _try_reserva_or_ask_time(send, chat_id, data_str, hora_str)

    return _mostrar_grade_horarios(send, chat_id, data_str)

def _handle_data_conf(send, chat_id, t):
    dt = state_manager.get_data(chat_id)
    sug_data = dt.get("data_sugerida")
    sug_hora = dt.get("hora_sugerida")
    if not sug_data:
        state_manager.set_state(chat_id, S_DATA)
        return send(chat_id, "Vamos tentar novamente. Qual data deseja? (DD/MM/AAAA ou DD/MM)")

    if t.lower() == "sim":
        if sug_hora:
            return _try_reserva_or_ask_time(send, chat_id, sug_data, sug_hora)
        return _mostrar_grade_horarios(send, chat_id, sug_data)
    elif t.lower() in ("não", "nao"):
        state_manager.set_state(chat_id, S_DATA)
        return send(chat_id, "Sem problemas! Informe a *data* (DD/MM/AAAA ou DD/MM).")
    else:
        return send(chat_id, "Responda *sim* para confirmar ou *não* para informar outra data.")

def _mostrar_grade_horarios(send, chat_id, data_str: str):
    livres = set()
    for h in DEFAULT_SLOTS:
        ok = True
        if excel and hasattr(excel, "verificar_disponibilidade"):
            try:
                ok = excel.verificar_disponibilidade(data_str, h)
            except Exception:
                ok = True
        if ok: livres.add(h)

    quadro, tem_livre = _format_grade_compact(data_str, DEFAULT_SLOTS, livres)
    send(chat_id, quadro)

    horas_livres_ordenadas = [h for h in DEFAULT_SLOTS if h in livres]
    state_manager.update_data(chat_id, data=data_str, horas_disponiveis=horas_livres_ordenadas)
    state_manager.set_state(chat_id, S_MOSTRAR_HORAS if tem_livre else S_DATA)

def _handle_escolha_hora_index(send, chat_id, t):
    dt = state_manager.get_data(chat_id)
    horarios = dt.get("horas_disponiveis") or []
    if not horarios:
        state_manager.set_state(chat_id, S_ESCOLHER_HORA)
        return send(chat_id, "Digite o *horário desejado* no formato HH:MM (ex: 14:00).")
    if not t.isdigit():
        return send(chat_id, "Envie o *número* do horário desejado (ex: 2).")
    idx = int(t) - 1
    if idx < 0 or idx >= len(horarios):
        return send(chat_id, "Número inválido. Escolha uma das opções listadas.")
    hora_str = horarios[idx]
    data_str = dt.get("data")
    return _try_reserva_or_ask_time(send, chat_id, data_str, hora_str)

def _handle_hora_livre(send, chat_id, t):
    t = (t or "").strip()
    if not _re_time.fullmatch(t):
        return send(chat_id, "Formato inválido. Informe no formato HH:MM (ex: 14:00).")
    dt = state_manager.get_data(chat_id)
    data_str = dt.get("data")
    return _try_reserva_or_ask_time(send, chat_id, data_str, t)

def _try_reserva_or_ask_time(send, chat_id, data_str: str, hora_str: str):
    disponivel = True
    if excel and hasattr(excel, "verificar_disponibilidade"):
        try:
            disponivel = excel.verificar_disponibilidade(data_str, hora_str)
        except Exception:
            disponivel = True
    if not disponivel:
        send(chat_id,
            f"😕 O horário *{data_str} às {hora_str}* *não está disponível*.\n"
            "Informe outro *horário* (HH:MM) ou outra *data* (DD/MM/AAAA)."
            + _nav_footer(["Ex.: *14:30* ou *29/10/2025*"]))
        state_manager.update_data(chat_id, data=data_str)
        state_manager.set_state(chat_id, S_ESCOLHER_HORA)
        return

    ok = _pre_reservar(send, chat_id, data_str, hora_str)
    if not ok:
        return

    valor_str = format_money(VALOR_CONSULTA)
    send(chat_id,
        f"✅ Horário *{data_str} às {hora_str}* reservado para pagamento.\n\n"
        f"💳 Valor: *{valor_str}*\n\n"
        "Escolha a forma de pagamento:\n"
        "1️⃣ PIX (Copia e Cola)\n"
        "2️⃣ Cartão de Crédito (Link)\n\n"
        "_Obs.: a pré-reserva vale por *10 minutos*._"
        + _nav_footer(["Responda *1* para PIX ou *2* para Cartão"]))

    state_manager.set_state(chat_id, S_ESCOLHENDO_PAGTO)
    state_manager.update_data(chat_id, data=data_str, hora=hora_str)

def _handle_escolha_pagamento(send, chat_id, t):
    if t == "1":
        pix_code = "00020126...CHAVE_PIX_CLINICA...52040000..."
        send(chat_id,
            "🔗 *PIX Copia e Cola*:\n"
            f"`{pix_code}`\n\n"
            "Após pagar, responda *paguei* aqui para confirmarmos."
            + _nav_footer(["Comando rápido: *paguei*"]))
        state_manager.set_state(chat_id, S_AGUARDANDO_PIX)
    elif t == "2":
        link = "https://pagamento.simulado/link123"
        send(chat_id,
            "💳 *Pagamento por Cartão*\n"
            f"Acesse: {link}\n\n"
            "Depois de concluir, responda *paguei* aqui."
            + _nav_footer(["Comando rápido: *paguei*"]))
        state_manager.set_state(chat_id, S_AGUARDANDO_LINK)
    else:
        send(chat_id, "Opção inválida. Responda *1* para PIX ou *2* para Cartão.")

def _handle_confirmacao_pagamento(send, chat_id, t):
    if t.lower() != "paguei":
        return send(chat_id, "Se já realizou o pagamento, responda *paguei*. Ou digite *menu* para voltar.")

    atualizado = _update_status_confirmado(chat_id)

    dt = state_manager.get_data(chat_id)
    data_ag = dt.get("data"); hora_ag = dt.get("hora")

    if atualizado:
        send(chat_id,
            f"🎉 Pagamento confirmado!\n"
            f"Seu agendamento para *{data_ag} às {hora_ag}* está *CONFIRMADO*."
            + _nav_footer(["Digite *menu* para voltar ao início"]))
    else:
        logger.warning(f"[FLOW] Não foi possível atualizar status para Confirmado (data={data_ag}, hora={hora_ag}).")
        send(chat_id,
            f"🎉 Pagamento recebido!\n"
            f"Seu agendamento para *{data_ag} às {hora_ag}* está *PRÉ-CONFIRMADO*.\n"
            "Um atendente finalizará a confirmação em instantes."
            + _nav_footer(["Digite *menu* para voltar ao início"]))

    send(chat_id, "Posso ajudar em algo mais? Digite *menu* para voltar ao início.")
    state_manager.set_state(chat_id, S_MENU)
    state_manager.clear_data(chat_id)

# ======= Atendimento humano (cliente) =======
def _start_handoff(send, chat_id):
    send(chat_id,
         "🧑‍💼 *Falar com atendente*\n"
         "Escreva uma breve mensagem explicando sua dúvida/solicitação. Vou repassar ao atendente e avisar quando ele entrar na conversa."
         + _nav_footer(["Ex.: *Quero tirar dúvidas sobre horários e valores*"]))
    state_manager.set_state(chat_id, S_HUM_PEDIR_RESUMO)

def _handle_humano_resumo(send, chat_id, resumo):
    resumo = (resumo or "").strip()
    if not resumo:
        return send(chat_id, "Pode descrever rapidamente sua dúvida?")
    # cria/guarda ticket
    tid = _find_ticket_by_client(chat_id) or _new_ticket_id()
    dt = state_manager.get_data(chat_id)
    nome = dt.get("nome") or "(sem nome)"
    cpf  = dt.get("cpf") or "(sem CPF)"
    _tickets[tid] = {
        "client_id": chat_id, "nome": nome, "cpf": cpf,
        "resumo": resumo, "status": "waiting", "admin_id": None
    }
    state_manager.update_data(
        chat_id,
        relay_status="waiting",
        relay_active=False,
        relay_admin=None,
        ticket_id=tid
    )
    state_manager.set_state(chat_id, S_HUM_AGUARDANDO)
    _extend_handoff_timeout(chat_id)  # inicia relógio

    # notifica admins (se houver)
    admins = _admin_ids()
    if admins:
        for admin in admins:
            send(admin,
                 "📨 *Novo pedido de atendimento*\n"
                 f"• Ticket: #{tid}\n"
                 f"• Cliente: `{chat_id}`\n"
                 f"• Nome: *{nome}*\n"
                 f"• CPF: *{cpf}*\n"
                 f"• Mensagem: “{resumo}”\n\n"
                 f"Para assumir, envie: `/aceitar #{tid}` ou `/aceitar {chat_id}`\n"
                 f"Para encerrar depois: `/encerrar`")

    send(chat_id, "✅ Pedido enviado! Aguarde, um atendente vai entrar na conversa em instantes. 😉")

def _handle_humano_aguardando(send, chat_id, msg_text):
    _extend_handoff_timeout(chat_id)
    if msg_text:
        send(chat_id, "Recebi sua mensagem. Assim que o atendente aceitar o atendimento, ele responde por aqui. 😉")

def _relay_from_client(send, chat_id, text):
    _extend_handoff_timeout(chat_id)
    if text.lower() in ("encerrar", "finalizar", "/encerrar"):
        return _maybe_close_relay_by_client(send, chat_id, by_client_cmd=True)

    admin_id = state_manager.get_data(chat_id).get("relay_admin")
    if not admin_id:
        send(chat_id, "Aguarde, o atendente já foi avisado e logo entra na conversa. 🙏")
        return
    send(admin_id, f"👤 *Cliente* `{chat_id}`: {text}")

def _maybe_close_relay_by_client(send, client_id, by_client_cmd=False):
    admin_id = state_manager.get_data(client_id).get("relay_admin")
    tid = state_manager.get_data(client_id).get("ticket_id")
    if admin_id and _relays.get(admin_id) == client_id:
        del _relays[admin_id]
    if tid and tid in _tickets:
        _tickets[tid]["status"] = "closed"

    state_manager.set_state(client_id, S_MENU)
    _reset_handoff_fields(client_id)

    send(client_id, "Atendimento encerrado. Digite *menu* para continuar.")
    if admin_id:
        send(admin_id, f"❕ Atendimento com `{client_id}` foi encerrado pelo cliente.")
    return

# -------------------------------
# Blocos de fluxo - ADMIN
# -------------------------------
def _route_admin(send, admin_id: str, t: str):
    if _relays.get(admin_id):
        client_id = _relays.get(admin_id)

        if _check_and_expire_handoff(send, client_id):
            state_manager.set_state(admin_id, S_ADMIN_MENU)
            return _send_admin_main_menu(send, admin_id)

        if t.lower().startswith("/encerrar"):
            _relays.pop(admin_id, None)
            tid = _find_ticket_by_client(client_id)
            if tid and tid in _tickets:
                _tickets[tid]["status"] = "closed"
            state_manager.set_state(client_id, S_MENU)
            _reset_handoff_fields(client_id)
            send(client_id, "Atendimento encerrado pelo atendente. Digite *menu* para continuar.")
            send(admin_id, "✅ Atendimento encerrado.")
            state_manager.set_state(admin_id, S_ADMIN_MENU)
            return _send_admin_main_menu(send, admin_id)

        _extend_handoff_timeout(client_id)
        send(client_id, f"👨‍💼 *Atendente*: {t}")
        return

    if t.startswith("/aceitar"):
        parts = t.split()
        target = parts[1] if len(parts) > 1 else ""
        client_id = None
        if target.startswith("#"):
            try:
                tid = int(target[1:])
                tk = _tickets.get(tid)
                if tk and tk.get("status") == "waiting":
                    client_id = tk["client_id"]
            except Exception:
                pass
        elif "@c.us" in target:
            client_id = target

        if not client_id:
            send(admin_id, "Uso: `/aceitar #<ticket>` ou `/aceitar <chat_id@c.us>`")
            return

        if _check_and_expire_handoff(send, client_id):
            return send(admin_id, "⏰ O ticket expirou por inatividade.")

        _relays[admin_id] = client_id
        state_manager.set_state(client_id, S_HUM_ATIVO)
        state_manager.update_data(client_id, relay_status="active", relay_active=True, relay_admin=admin_id)
        _extend_handoff_timeout(client_id)

        tid = _find_ticket_by_client(client_id)
        if tid and tid in _tickets:
            _tickets[tid]["status"] = "active"
            _tickets[tid]["admin_id"] = admin_id

        send(admin_id, f"✅ Você assumiu o atendimento de `{client_id}`. Envie mensagens normalmente. Para encerrar: `/encerrar`.")
        send(client_id, "👋 Um atendente entrou na conversa. Você já pode enviar suas mensagens aqui.")
        state_manager.set_state(admin_id, S_ADMIN_RELAY)
        return

    if t.lower() in ("menu", "inicio", "início", "admin"):
        state_manager.set_state(admin_id, S_ADMIN_MENU)
        return _send_admin_main_menu(send, admin_id)

    st = state_manager.get_state(admin_id)
    if st != S_ADMIN_MENU:
        state_manager.set_state(admin_id, S_ADMIN_MENU)
        return _send_admin_main_menu(send, admin_id)

    if t == "1":
        return _admin_list_agendamentos_hoje(send, admin_id)
    if t == "2":
        return _admin_assumir_proximo_cliente(send, admin_id)
    if t == "3":
        return _admin_list_chamados_abertos(send, admin_id)

    return _send_admin_main_menu(send, admin_id)

def _send_admin_main_menu(send, admin_id):
    send(admin_id,
        "🛠️ *Painel do Admin*\n\n"
        "1️⃣ Ver agendamentos do dia\n"
        "2️⃣ Assumir próximo cliente\n"
        "3️⃣ Chamados abertos\n\n"
        "_Comandos:_ `/aceitar #<ticket>` • `/encerrar` • `menu`")

def _admin_list_agendamentos_hoje(send, admin_id):
    hoje = date.today().strftime("%d/%m/%Y")
    linhas = []
    if excel and hasattr(excel, "_read_rows"):
        try:
            for r in excel._read_rows():
                if r.get("Data") == hoje:
                    hora = r.get("Hora") or "--:--"
                    nome = r.get("ClienteNome") or "(sem nome)"
                    status = r.get("Status") or "-"
                    linhas.append(f"• {hora} — {nome} ({status})")
        except Exception as e:
            logger.warning(f"[ADMIN] erro lendo planilha: {e}")

    if not linhas:
        send(admin_id, f"🗓️ Hoje ({hoje}) não há agendamentos registrados.")
    else:
        send(admin_id, f"🗓️ *Agendamentos de hoje* ({hoje}):\n" + "\n".join(linhas))

def _admin_list_chamados_abertos(send, admin_id):
    itens = []
    for tid, tk in sorted(_tickets.items()):
        if tk.get("status") == "waiting":
            nome = tk.get("nome") or "(sem nome)"
            itens.append(f"#{tid} — {nome}")
    if not itens:
        send(admin_id, "📭 Não há chamados abertos no momento.")
    else:
        send(admin_id, "📂 *Chamados abertos*\n" + "\n".join(itens) + "\n\nPara assumir: `/aceitar #<ticket>`")

def _admin_assumir_proximo_cliente(send, admin_id):
    waiting = None
    for tid, tk in sorted(_tickets.items()):
        if tk.get("status") == "waiting":
            waiting = (tid, tk)
            break
    if not waiting:
        return send(admin_id, "📭 Não há clientes aguardando no momento.")
    tid, tk = waiting
    client_id = tk["client_id"]

    if _check_and_expire_handoff(send, client_id):
        return send(admin_id, "⏰ O ticket selecionado expirou por inatividade.")

    _relays[admin_id] = client_id
    state_manager.set_state(client_id, S_HUM_ATIVO)
    state_manager.update_data(client_id, relay_status="active", relay_active=True, relay_admin=admin_id)
    _extend_handoff_timeout(client_id)

    _tickets[tid]["status"] = "active"
    _tickets[tid]["admin_id"] = admin_id

    send(admin_id, f"✅ Você assumiu o ticket #{tid} (`{client_id}`). Para encerrar: `/encerrar`.")
    send(client_id, "👋 Um atendente entrou na conversa. Você já pode enviar suas mensagens aqui.")
    state_manager.set_state(admin_id, S_ADMIN_RELAY)

# ===== roteamento auxiliar de estados =====
def _handle_humano_resumo_or_route(send, chat_id, t):
    st = state_manager.get_state(chat_id)
    if st == S_HUM_PEDIR_RESUMO:
        return _handle_humano_resumo(send, chat_id, t)
    if st == S_HUM_AGUARDANDO:
        return _handle_humano_aguardando(send, chat_id, t)
