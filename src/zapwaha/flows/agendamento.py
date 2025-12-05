from __future__ import annotations
import os
import re
from datetime import date, time, datetime, timedelta
import logging

# =============================================================================
# CONFIG GERAL
# =============================================================================

logger = logging.getLogger("ZapWaha")

# =============================================================================
# UX helpers (rodapés e bullets)
# =============================================================================

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

# =============================================================================
# Estado / Serviços
# =============================================================================

# Cadastro / login de clientes (planilha)
try:
    from services import clientes_services as clientes
    if hasattr(clientes, "init_planilha"):
        clientes.init_planilha()
except Exception:
    clientes = None  # permite rodar sem cadastro em dev

# Serviços (opcional)
try:
    from services.servicos import carregar_servicos, formatar_lista_servicos
except Exception:
    carregar_servicos = None
    formatar_lista_servicos = None

# State manager
try:
    from zapwaha.state.memory import state_manager  # implementação esperada
except Exception:
    # Fallback simples em memória (para dev)
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

# Excel (import robusto)
try:
    from services import excel_services as excel
except Exception:
    excel = None  # permite rodar sem Excel em dev

# =============================================================================
# Constantes / Config de fluxo
# =============================================================================

VALOR_SERVICO_PADRAO = 50.00
DEFAULT_SLOTS = ["08:00","09:00","10:00","11:00","13:00","14:00","15:00","16:00","17:00"]

# TIMEOUTS DO ATENDIMENTO HUMANO (em minutos)
HUMAN_TIMEOUT_WHEN_WAITING_MIN = 10  # Tempo limite aguardando atendente aceitar
HUMAN_TIMEOUT_WHEN_ACTIVE_MIN  = 0   # 0 = sem expiração durante atendimento ativo

# ==== Admin config (ENV e opcional arquivo JSON) ====
def _admin_ids() -> set[str]:
    ids = set()
    raw = os.getenv("ADMIN_CHAT_IDS", "")
    if raw:
        ids.update(x.strip() for x in raw.split(",") if x.strip())
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

# =============================================================================
# Helpers de validação / parsing
# =============================================================================

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

# =============================================================================
# Estados (cliente)
# =============================================================================

S_MENU = "MENU_PRINCIPAL"
S_MENU_OPCAO = "ESPERANDO_OPCAO_MENU"

S_AG_SUBMENU = "AGENDAMENTO_ESCOLHER_ACAO"

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

# =============================================================================
# Estados (admin)
# =============================================================================

S_ADMIN_MENU  = "ADMIN_MENU"
S_ADMIN_RELAY = "ADMIN_RELAY"



# =============================================================================
# Estruturas de handoff
# =============================================================================

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

# =============================================================================
# Timeout de atendimento humano
# =============================================================================

def _now():
    return datetime.now()

def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _get_timeout_minutes(chat_id: str) -> int:
    dt = state_manager.get_data(chat_id) or {}
    status = dt.get("relay_status")
    if status == "active":
        return HUMAN_TIMEOUT_WHEN_ACTIVE_MIN
    return HUMAN_TIMEOUT_WHEN_WAITING_MIN

def _extend_handoff_timeout(chat_id: str, minutes: int | None = None):
    if minutes is None:
        minutes = _get_timeout_minutes(chat_id)
    if minutes and minutes > 0:
        expires_at = _now() + timedelta(minutes=minutes)
        state_manager.update_data(chat_id, relay_expires_at=_iso(expires_at))
    else:
        state_manager.update_data(chat_id, relay_expires_at=None)

def _reset_handoff_fields(chat_id: str):
    state_manager.update_data(
        chat_id,
        relay_status=None,
        relay_active=False,
        relay_admin=None,
        relay_expires_at=None,
    )

def _check_and_expire_handoff(send, chat_id: str) -> bool:
    dt = state_manager.get_data(chat_id) or {}
    status = dt.get("relay_status")
    if status not in ("waiting", "active"):
        return False

    ex_str = dt.get("relay_expires_at")
    ex_dt = _parse_iso(ex_str) if ex_str else None
    if not ex_dt or _now() < ex_dt:
        return False

    admin_id = dt.get("relay_admin")
    tid = dt.get("ticket_id")
    ticket_label = f"#{tid}" if tid else "(sem ticket)"

    if admin_id and _relays.get(admin_id) == chat_id:
        _relays.pop(admin_id, None)

    if tid and tid in _tickets:
        _tickets[tid]["status"] = "closed"

    if status == "waiting":
        send(chat_id, "⏰ O atendimento foi *encerrado* porque não foi assumido a tempo.\nSe preferir, peça *Falar com atendente* novamente.")
    else:
        send(chat_id, "⏰ O atendimento foi *encerrado por inatividade*.\nSe ainda precisar, peça *Falar com atendente* novamente.")

    if admin_id:
        send(admin_id, f"⏹️ Ticket {ticket_label} encerrado por inatividade.")

    _reset_handoff_fields(chat_id)
    state_manager.set_state(chat_id, S_MENU)
    return True

def _sweep_expired_handoffs(send):
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
            continue

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



def _telefone_from_chat_id(chat_id: str) -> str:
    return re.sub(r"\D","", (chat_id or "").split("@")[0])

def _must_force_auth(chat_id: str) -> bool:
    # Bot sempre aberto. O login é exigido apenas
    # dentro dos handlers de negócio (ex.: opção 1 e 4).
    return False


# =============================================================================
# Pré-reserva e atualização
# =============================================================================

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

# =============================================================================
# Limpeza de dados do FLUXO (preserva login)
# =============================================================================

def _clear_flow_fields(chat_id: str):
    dt = state_manager.get_data(chat_id) or {}
    keep_keys = ("nome", "data_nascimento", "cpf", "cliente_cpf", "cliente_email", "cliente_telefone")
    keep = {k: v for k, v in dt.items() if k in keep_keys and v}
    state_manager.clear_data(chat_id)
    if keep:
        state_manager.update_data(chat_id, **keep)

# =============================================================================
# Roteador principal
# =============================================================================

def route_message(send, chat_id: str, text: str):
    t = (text or "").strip()

    # Varre expirados globalmente a cada mensagem recebida
    _sweep_expired_handoffs(send)

    # ADMIN primeiro
    if chat_id in _admin_ids():
        return _route_admin(send, chat_id, t)

    # Checa expiração da sessão deste cliente (só relevante se houver handoff ativo)
    if _check_and_expire_handoff(send, chat_id):
        return

    # Atalhos globais do cliente
    if t.lower() in ("menu", "voltar", "inicio", "início", "sair"):
        return _send_main_menu(send, chat_id)

    st = state_manager.get_state(chat_id)

    # Atendimento humano states
    if st == S_HUM_PEDIR_RESUMO:  return _handle_humano_resumo(send, chat_id, t)
    if st == S_HUM_AGUARDANDO:    return _handle_humano_aguardando(send, chat_id, t)
    if st == S_HUM_ATIVO:         return _relay_from_client(send, chat_id, t)

    # Menu e subfluxos
    if st in (S_MENU, None):      return _send_main_menu(send, chat_id)
    if st == S_MENU_OPCAO:        return _handle_menu_opcao(send, chat_id, t)
    if st == S_AG_SUBMENU:        return _handle_ag_submenu(send, chat_id, t)

    if st == S_DATA:              return _handle_data(send, chat_id, t)
    if st == S_DATA_CONF:         return _handle_data_conf(send, chat_id, t)
    if st == S_MOSTRAR_HORAS:     return _handle_escolha_hora_index(send, chat_id, t)
    if st == S_ESCOLHER_HORA:     return _handle_hora_livre(send, chat_id, t)

    if st == S_ESCOLHENDO_PAGTO:  return _handle_escolha_pagamento(send, chat_id, t)
    if st in (S_AGUARDANDO_PIX, S_AGUARDANDO_LINK):
        return _handle_confirmacao_pagamento(send, chat_id, t)

    return _send_main_menu(send, chat_id)


# =============================================================================
# Blocos de fluxo - CLIENTE
# =============================================================================

def _send_main_menu(send, chat_id):
    """Menu principal da barbearia"""
    send(
        chat_id,
        "👋 *Bem-vindo(a) à Barbearia Veinho Corts!* ✂️💈\n\n"
        "Como podemos te ajudar hoje?\n\n"
        "1️⃣ Agendar Corte ou Serviço\n"
        "2️⃣ Serviços e Valores\n"
        "3️⃣ Dúvidas Frequentes\n"
        "4️⃣ Falar com Atendente" + _nav_footer(["Responda com *1*, *2*, *3* ou *4*"])
    )
    state_manager.set_state(chat_id, S_MENU_OPCAO)

def _handle_menu_opcao(send, chat_id, t):
    """Roteamento do menu principal"""
    t = (t or "").strip()

    if t == "1":
        send(
            chat_id,
            "✂️ *Agendamento na Barbearia*\n\n"
            "1. Agendar novo corte/serviço\n"
            "2. Consultar meu próximo horário\n" +
            "3. Remarcar horário\n" +
            "4. Cancelar horário" + _nav_footer(["Responda com *1*, *2*, *3* ou *4*"])
        )
        state_manager.set_state(chat_id, S_AG_SUBMENU)
    elif t == "2":
        if carregar_servicos and formatar_lista_servicos:
            try:
                servs = carregar_servicos()
                texto = formatar_lista_servicos(servs)
                send(chat_id, texto + _nav_footer(["Digite *menu* para voltar"]))
            except Exception:
                send(chat_id, "Tabela de serviços indisponível no momento. Digite *menu* para voltar.")
        else:
            send(
                chat_id,
                "💈 *Serviços e Valores da Barbearia*\n\n"
                "✂️ Corte de Cabelo - R$ 50,00\n"
                "🧔 Barba - R$ 40,00\n"
                "💯 Combo (Corte + Barba) - R$ 80,00\n"
                "👁️ Sobrancelha - R$ 20,00\n"
                "💧 Hidratação Capilar - R$ 60,00\n"
                "🎨 Luzes/Coloração - R$ 120,00\n\n"
                "_Horário de funcionamento: Seg a Sex 9h-19h, Sáb 9h-17h_"
                + _nav_footer(["Digite *menu* para voltar"])
            )
        state_manager.set_state(chat_id, S_MENU)

    elif t == "3":
        send(
            chat_id,
            "❓ *Dúvidas Frequentes*\n\n"
            "📍 *Onde ficamos?*\n"
            "Rua Exemplo, 123 - Centro\n\n"
            "⏰ *Horário de funcionamento?*\n"
            "Seg a Sex: 9h às 19h\n"
            "Sábado: 9h às 17h\n"
            "Domingo: Fechado\n\n"
            "💳 *Formas de pagamento?*\n"
            "PIX, Cartão (débito/crédito), Dinheiro\n\n"
            "📱 *Como remarcar?*\n"
            "Digite *menu* e escolha opção 1, depois opção 3\n\n"
            "⚠️ *Política de cancelamento?*\n"
            "Cancele com no mínimo 2h de antecedência"
            + _nav_footer(["Digite *menu* para voltar"])
        )
        state_manager.set_state(chat_id, S_MENU)
    elif t == "4":
        return _start_handoff(send, chat_id)

    else:
        send(chat_id, "Opção inválida. Digite 1, 2, 3 ou 4, ou *menu* para voltar.")

def _handle_ag_submenu(send, chat_id, t):
    t = (t or "").strip()

    if t == "1":
        send(
            chat_id,
            "📅 *Para qual data você quer agendar?*\n\n"
            "Digite no formato *DD/MM/AAAA* ou *DD/MM*"
            + _nav_footer(["Ex.: *28/10/2025* ou *28/10*"])
        )
        state_manager.set_state(chat_id, S_DATA)

    else:
        send(chat_id, "Em breve.\nDigite *menu* para voltar ou *1* para agendar um novo horário.")

# ===== datas / horários =====

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

    valor_str = format_money(VALOR_SERVICO_PADRAO)
    send(chat_id,
        f"✅ *Horário Reservado!*\n\n"
        f"📅 Data: *{data_str}*\n"
        f"⏰ Horário: *{hora_str}*\n"
        f"💰 Valor: *{valor_str}*\n\n"
        "Escolha a forma de pagamento:\n\n"
        "1️⃣ PIX (Copia e Cola)\n"
        "2️⃣ Cartão de Crédito (Link de pagamento)\n\n"
        "_⚠️ Obs.: a pré-reserva vale por *10 minutos*._"
        + _nav_footer(["Responda *1* para PIX ou *2* para Cartão"]))
    state_manager.set_state(chat_id, S_ESCOLHENDO_PAGTO, data={"data": data_str, "hora": hora_str})

def _handle_escolha_pagamento(send, chat_id, t):
    if t == "1":
        pix_code = "00020126...CHAVE_PIX_BARBEARIA...52040000..."
        send(chat_id,
            "🔗 *Pagamento via PIX*\n\n"
            f"`{pix_code}`\n\n"
            "📱 Copie o código acima e cole no app do seu banco.\n\n"
            "Após realizar o pagamento, responda *paguei* aqui para confirmarmos seu horário."
            + _nav_footer(["Comando rápido: *paguei*"]))
        state_manager.set_state(chat_id, S_AGUARDANDO_PIX)
    elif t == "2":
        link = "https://pagamento.simulado/link123"
        send(chat_id,
            "💳 *Pagamento por Cartão de Crédito*\n\n"
            f"Acesse o link para pagar com segurança:\n{link}\n\n"
            "Após realizar o pagamento, responda *paguei* aqui para confirmarmos." + _nav_footer(["Comando rápido: *paguei*"]))
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
            f"✅ *Pagamento confirmado!*\n\n"
            f"Seu horário para *{data_ag} às {hora_ag}* está *CONFIRMADO*.\n\n"
            f"💈 Te esperamos na barbearia!\n"
            f"Qualquer dúvida, é só chamar."
            + _nav_footer(["Digite *menu* para voltar ao início"]))
    else:
        logger.warning(f"[FLOW] Não foi possível atualizar status para Confirmado (data={data_ag}, hora={hora_ag}).")
        send(chat_id,
            f"✅ *Pagamento recebido!*\n\n"
            f"Seu horário para *{data_ag} às {hora_ag}* está *PRÉ-CONFIRMADO*.\n"
            f"Um atendente finalizará a confirmação em instantes.\n\n"
            f"💈 Te esperamos na barbearia!"
            + _nav_footer(["Digite *menu* para voltar ao início"]))

    send(chat_id, "Posso ajudar em algo mais? Digite *menu* para voltar ao início.")
    state_manager.set_state(chat_id, S_MENU)
    _clear_flow_fields(chat_id)

# ======= Atendimento humano (cliente) =======

def _start_handoff(send, chat_id):
    send(chat_id,
         "👨‍💼 *Falar com Atendente*\n\n"
         "Escreva uma breve mensagem explicando sua dúvida ou solicitação. \n"
         "Vou repassar ao atendente e avisar quando ele entrar na conversa.\n\n"
         "_Exemplos: Quero saber sobre pacotes, Tenho uma ocasião especial, etc._"
         + _nav_footer(["Digite sua mensagem agora"]))
    state_manager.set_state(chat_id, S_HUM_PEDIR_RESUMO)

def _handle_humano_resumo(send, chat_id, resumo):
    resumo = (resumo or "").strip()
    if not resumo:
        return send(chat_id, "Pode descrever rapidamente sua dúvida?")
    tid = _find_ticket_by_client(chat_id) or _new_ticket_id()
    dt = state_manager.get_data(chat_id)
    nome = dt.get("nome") or "Cliente"
    cpf  = dt.get("cpf") or ""
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
    _extend_handoff_timeout(chat_id)

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

# =============================================================================
# Blocos de fluxo - ADMIN
# =============================================================================

def _route_admin(send, admin_id: str, t: str):
    # Se estiver em relay humano → repassa a mensagem ao cliente
    if _relays.get(admin_id):
        client_id = _relays.get(admin_id)

        if _check_and_expire_handoff(send, client_id):
            state_manager.set_state(admin_id, S_ADMIN_MENU)
            return _send_admin_main_menu(send, admin_id)

        if (t or "").lower().startswith("/encerrar"):
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

    # --- Comandos rápidos ---
    txt = (t or "").strip()

    if txt.startswith("/aceitar"):
        parts = txt.split()
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

    if txt.startswith("/logins"):
        parts = txt.split()
        try:
            limit = int(parts[1]) if len(parts) > 1 else 20
        except Exception:
            limit = 20
        return _admin_list_logins(send, admin_id, limit=limit)

    if txt.lower() in ("menu", "inicio", "início", "admin"):
        state_manager.set_state(admin_id, S_ADMIN_MENU)
        return _send_admin_main_menu(send, admin_id)

    # Garante estado de menu
    st = state_manager.get_state(admin_id)
    if st != S_ADMIN_MENU:
        state_manager.set_state(admin_id, S_ADMIN_MENU)
        return _send_admin_main_menu(send, admin_id)

    # Opções de menu
    if txt == "1":
        return _admin_list_agendamentos_hoje(send, admin_id)
    if txt == "2":
        return _admin_assumir_proximo_cliente(send, admin_id)
    if txt == "3":
        return _admin_list_chamados_abertos(send, admin_id)
    if txt == "4":
        return _admin_list_logins(send, admin_id, limit=20)

    return _send_admin_main_menu(send, admin_id)

def _send_admin_main_menu(send, admin_id):
    send(
        admin_id,
        "🔧 *Painel Admin - Barbearia Veinho Corts*\n\n"
        "1️⃣ Ver agendamentos do dia\n"
        "2️⃣ Assumir próximo cliente\n"
        "3️⃣ Chamados abertos\n"
        "4️⃣ Logins (vínculos e sessões)\n\n"
        "_Comandos:_ `/aceitar #<ticket>` • `/encerrar` • `menu`\n"
        "_Atalhos:_ `/logins` • `/logins 50`"
    )

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

def _admin_list_logins(send, admin_id, limit: int = 20, page: int = 1):
    """
    Lista vínculos de login em blocos:
    --------------
    ℹ️: <ID>
    👤: <Nome>
    🪪: <CPF formatado>
    --------------
    Considera como 'vínculo' quem tem CPF + ChatId.
    """
    def _digits(s):
        return "".join(ch for ch in str(s or "") if ch.isdigit())

    links = []

    # === 1) Preferir clientes_services (mais confiável no seu setup) ===
    try:
        if clientes and hasattr(clientes, "list_all_clients"):
            rows = clientes.list_all_clients(offset=0, limit=10_000) or []
            for r in rows:
                cpf = _digits(r.get("CPF") or r.get("Cpf") or "")
                chat = (r.get("ChatId") or r.get("ChatID") or r.get("chat_id") or r.get("WhatsApp") or "").strip()
                if not cpf or not chat:
                    continue  # só contamos vínculos reais
                links.append({
                    "id": str(r.get("ID") or r.get("Id") or r.get("id") or "").strip(),
                    "chat_id": chat,
                    "cpf": cpf,
                    "nome": str(r.get("Nome") or r.get("ClienteNome") or "").strip()
                })
    except Exception as e:
        logger.warning(f"[ADMIN] list_all_clients falhou: {e}")

    # === 2) Se não veio nada, tentar helper opcional de auth ===
    if not links:
        auth_list = globals().get("_auth_list_links")
        try:
            if callable(auth_list):
                raw = auth_list() or []
                for lk in raw:
                    cpf = _digits(lk.get("cpf"))
                    chat = (lk.get("chat_id") or lk.get("jid") or lk.get("whatsapp") or "").strip()
                    if not cpf or not chat:
                        continue
                    links.append({
                        "id": str(lk.get("ID") or lk.get("id") or lk.get("id_cliente") or "").strip(),
                        "chat_id": chat,
                        "cpf": cpf,
                        "nome": lk.get("nome") or lk.get("name") or ""
                    })
        except Exception as e:
            logger.warning(f"[ADMIN] _auth_list_links falhou: {e}")

    # === 3) Fallback por excel_services (quando existir) ===
    if not links:
        rows = []
        try:
            if excel:
                # tenta readers dedicados
                for cand in ("_read_rows_clientes", "_read_rows_clients"):
                    fn = getattr(excel, cand, None)
                    if callable(fn):
                        rows = fn() or []
                        if rows:
                            break
                # fallback: sheet=Clientes ou geral
                if not rows and hasattr(excel, "_read_rows"):
                    try:
                        rows = excel._read_rows(sheet="Clientes")
                    except TypeError:
                        rows = excel._read_rows()
        except Exception as e:
            logger.warning(f"[ADMIN] erro lendo Clientes via excel: {e}")
            rows = []

        for r in rows or []:
            cpf = _digits(r.get("CPF") or r.get("Cpf") or "")
            chat = (r.get("ChatId") or r.get("ChatID") or r.get("chat_id") or r.get("WhatsApp") or "").strip()
            if not cpf or not chat:
                continue
            links.append({
                "id": str(r.get("ID") or "").strip(),
                "chat_id": chat,
                "cpf": cpf,
                "nome": str(r.get("Nome") or r.get("ClienteNome") or "").strip()
            })

    # Ordena por nome, depois por ID
    links = sorted(links, key=lambda x: ((x.get("nome") or "").lower(), str(x.get("id") or "")))
    total = len(links)
    if total == 0:
        return send(admin_id, "📇 Não há vínculos de login registrados.")

    # Paginação
    limit = max(1, min(int(limit or 20), 200))
    page = max(1, int(page or 1))
    start = (page - 1) * limit
    end = start + limit
    slice_ = links[start:end]

    # Monta blocos
    blocos = []
    sep = "--------------"
    for i, lk in enumerate(slice_, start=start + 1):
        # ID de exibição: usa coluna ID; se vazia, usa o índice i como fallback visual
        disp_id = lk.get("id") or str(i)
        nome = (lk.get("nome") or "(sem nome)")
        cpf = (lk.get("cpf") or "-")
        cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else (cpf or "-")

        blocos.append(
            f"{sep}\n"
            f"ℹ️: {disp_id}\n"
            f"👤: {nome}\n"
            f"🪪: {cpf_fmt}\n"
            f"{sep}"
        )

    pages = (total + limit - 1) // limit
    header = "🔐 *Logins (vínculos)*"
    footer = (
        f"\n\nTotal: {total} • Página {page}/{pages}\n"
        "Ajuste a quantidade com: `/logins <qtde>` (ex.: `/logins 50`)."
    )
    send(admin_id, header + "\n" + "\n".join(blocos) + footer)



# =============================================================================
# AUTH: telas e handlers
# =============================================================================

# =============================================================================
# Roteamento final e export
# =============================================================================
