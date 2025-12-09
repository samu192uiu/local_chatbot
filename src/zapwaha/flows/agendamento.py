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

def _box_message(titulo: str, conteudo: list[str], rodape: str = None) -> str:
    """
    Cria uma mensagem formatada em caixa padronizada.
    
    Args:
        titulo: Título da mensagem (ex: "🕐 Horários disponíveis — 05/12/2025")
        conteudo: Lista de linhas do conteúdo
        rodape: Texto do rodapé (opcional, aparece fora da caixa)
    
    Returns:
        String formatada com a caixa
    """
    top = "╔════════════════════════╗"
    sep = "╠════════════════════════╣"
    bot = "╚════════════════════════╝"
    
    linhas = [top, f"  {titulo}", sep]
    
    for linha in conteudo:
        linhas.append(f"  {linha}")
    
    linhas.append("")
    linhas.append(bot)
    
    mensagem = "\n".join(linhas)
    
    if rodape:
        mensagem += f"\n{rodape}"
    
    return mensagem

def _nav_footer(linhas: list[str]) -> str:
    barra = "─" * 26
    corpo = "\n".join(f"• {ln}" for ln in linhas)
    atalhos = "• *menu* — voltar ao início"
    return f"\n↩️ Atalhos:\n{corpo}\n{atalhos}"

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

# Serviços fracionados
try:
    from services import servicos_fracionados as sf
except Exception:
    sf = None

# Agenda dinâmica
try:
    from services import agenda_dinamica as ag
except Exception:
    ag = None

# Slots dinâmicos
try:
    from services import slots_dinamicos
except Exception:
    slots_dinamicos = None

# Módulo admin (roteamento correto)
try:
    from zapwaha.flows import admin as admin_module
except Exception:
    admin_module = None

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
# DEFAULT_SLOTS removido - agora usa agenda dinâmica

# Helper para obter slots do dia (usa slots dinâmicos)
def _obter_slots_dia(data_str: str, servico_id: str = None) -> list[str]:
    """
    Retorna lista de horários disponíveis para uma data e serviço.
    Usa slots_dinamicos se disponível e servico_id fornecido.
    """
    if not servico_id or not slots_dinamicos:
        # Fallback: usar agenda dinâmica ou slots fixos
        if ag and hasattr(ag, "horarios_disponiveis_com_verificacao"):
            try:
                return ag.horarios_disponiveis_com_verificacao(data_str)
            except Exception as e:
                logger.warning(f"Erro ao obter slots dinâmicos: {e}")
        
        # Fallback final para slots fixos
        return ["08:00","09:00","10:00","11:00","13:00","14:00","15:00","16:00","17:00"]
    
    # Usar slots dinâmicos baseados no serviço
    try:
        if not excel:
            return []
        
        # Obter agendamentos do dia
        agendamentos = excel.obter_agendamentos_do_dia(data_str)
        
        # Gerar slots disponíveis para o serviço específico
        slots_disponiveis = slots_dinamicos.gerar_slots_disponiveis_para_servico(
            data_str, servico_id, agendamentos
        )
        
        return slots_disponiveis
    except Exception as e:
        logger.error(f"Erro ao gerar slots dinâmicos: {e}")
        # Fallback em caso de erro
        return ["08:00","09:00","10:00","11:00","13:00","14:00","15:00","16:00","17:00"]

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

# =============================================================================
# Geração de datas disponíveis
# =============================================================================

def _gerar_datas_disponiveis(dias: int = 14) -> list[tuple[str, str]]:
    """
    Gera lista de datas disponíveis para agendamento.
    Retorna lista de tuplas (data_formatada, data_display)
    Ex: [("05/12/2025", "Qui 05/12"), ("06/12/2025", "Sex 06/12"), ...]
    
    Pula domingos por padrão.
    Começa sempre de HOJE, atualizando automaticamente conforme os dias passam.
    """
    agora = datetime.now()
    hoje = agora.date()
    
    # Se já passou das 18h, começar do próximo dia útil
    if agora.hour >= 18:
        hoje = hoje + timedelta(days=1)
    
    datas = []
    dias_semana = {
        0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui",
        4: "Sex", 5: "Sáb", 6: "Dom"
    }
    
    dias_gerados = 0
    offset = 0
    
    while dias_gerados < dias:
        data_atual = hoje + timedelta(days=offset)
        offset += 1
        
        # Pular domingos (weekday 6)
        if data_atual.weekday() == 6:
            continue
            
        data_str = data_atual.strftime("%d/%m/%Y")
        dia_semana = dias_semana[data_atual.weekday()]
        data_display = f"{dia_semana} {data_atual.strftime('%d/%m')}"
        
        datas.append((data_str, data_display))
        dias_gerados += 1
    
    return datas

def _formatar_lista_datas(datas: list[tuple[str, str]]) -> str:
    """Formata lista de datas para exibição ao usuário."""
    top = "╔════════════════════════╗"
    titulo = "📅 Escolha a data do seu agendamento"
    sep = "╠════════════════════════╣"
    
    # Mapear números para emojis
    numeros_emoji = {
        1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
        6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
        11: "1️⃣1️⃣", 12: "1️⃣2️⃣", 13: "1️⃣3️⃣", 14: "1️⃣4️⃣"
    }
    
    linhas = ["✅ Responda apenas com o número da opção:", ""]
    for idx, (data_str, data_display) in enumerate(datas, 1):
        emoji = numeros_emoji.get(idx, f"{idx}️⃣")
        linhas.append(f"{emoji} {data_display}")
    
    linhas.append("")
    bot = "╚════════════════════════╝"
    
    return "\n".join([top, titulo, sep] + linhas + [bot])

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

S_ESCOLHER_SERVICO = "AG_ESCOLHER_SERVICO"  # Novo: escolher qual serviço agendar
S_ESCOLHER_DATA = "AG_ESCOLHER_DATA"  # Novo: escolher data da lista
S_CONSULTAR_DATA = "AG_CONSULTAR_DATA"  # Consultar horários disponíveis
S_DATA = "AG_DATA"
S_DATA_CONF = "AG_DATA_CONF"
S_MOSTRAR_HORAS = "AG_MOSTRAR_HORAS"
S_ESCOLHER_HORA = "AG_ESCOLHER_HORA"

# Remarcação
S_REMARCAR_CONFIRMAR = "AG_REMARCAR_CONFIRMAR"
S_REMARCAR_ESCOLHER_DATA = "AG_REMARCAR_ESCOLHER_DATA"
S_REMARCAR_ESCOLHER_HORA = "AG_REMARCAR_ESCOLHER_HORA"

# Cancelamento
S_CANCELAR_CONFIRMAR = "AG_CANCELAR_CONFIRMAR"

# Área do Cliente
S_AREA_CLIENTE_CPF = "AREA_CLIENTE_PEDIR_CPF"
S_AREA_CLIENTE_PIN = "AREA_CLIENTE_PEDIR_PIN"
S_AREA_CLIENTE_MENU = "AREA_CLIENTE_MENU"
S_AREA_CLIENTE_ALTERAR_PIN_NOVO = "AREA_CLIENTE_ALTERAR_PIN_NOVO"
S_AREA_CLIENTE_ALTERAR_PIN_CONF = "AREA_CLIENTE_ALTERAR_PIN_CONF"

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
    """
    Cria uma reserva temporária (10 minutos) para o horário escolhido.
    Retorna True se sucesso, False caso contrário.
    """
    dados = state_manager.get_data(chat_id)
    nome = dados.get("nome")
    nasc = dados.get("data_nascimento") or dados.get("nascimento")
    cpf  = dados.get("cpf")
    servico_id = dados.get("servico_escolhido", "corte_simples")

    if not excel or not hasattr(excel, "reservar_slot_temporario"):
        logger.warning("[FLOW] Excel não disponível; pulando gravação.")
        return True

    # Obter duração do serviço
    servico_duracao = None
    if sf:
        try:
            servico_info = sf.get_servico_por_id(servico_id)
            if servico_info:
                servico_duracao = servico_info.get("duracao_minutos", 30)
        except Exception:
            pass
    
    if not servico_duracao:
        servico_duracao = 30  # Fallback

    try:
        chave = excel.reservar_slot_temporario(
            data_str=data_str,
            hora_str=hora_str,
            chat_id=chat_id,
            cliente_nome=nome,
            data_nasc=nasc,
            cpf=cpf,
            servico_id=servico_id,
            servico_duracao=servico_duracao
        )
        
        if not chave:
            chave = _make_key(data_str, hora_str, chat_id)
        
        state_manager.update_data(chat_id, ag_chave=chave, data=data_str, hora=hora_str)
        logger.info(f"[FLOW] Reserva temporária criada: {chave} - Serviço: {servico_id} ({servico_duracao}min)")
        return True
        
    except ValueError as ve:
        # Horário indisponível ou expirado
        logger.info(f"[FLOW] Horário indisponível: {ve}")
        
        # Tentar sugerir próximo horário disponível
        if slots_dinamicos:
            try:
                agendamentos = excel.obter_agendamentos_do_dia(data_str)
                proximo = slots_dinamicos.obter_proximo_slot_disponivel(
                    data_str, hora_str, servico_id, agendamentos
                )
                
                if proximo:
                    send(chat_id, 
                        f"😕 O horário *{hora_str}* não está mais disponível.\n\n"
                        f"💡 Que tal às *{proximo}*?\n\n"
                        f"Digite *sim* para confirmar ou escolha outro horário.")
                    state_manager.update_data(chat_id, horario_sugerido=proximo)
                    return False
                else:
                    send(chat_id, 
                        f"😕 O horário *{hora_str}* não está mais disponível.\n\n"
                        f"Por favor, escolha outro horário ou outra data.")
                    return False
            except Exception as e:
                logger.error(f"Erro ao buscar próximo slot: {e}")
        
        send(chat_id, 
            f"😕 O horário *{hora_str}* não está mais disponível.\n"
            f"Por favor, escolha outro horário.")
        return False
        
    except Exception as e:
        logger.exception(f"[FLOW] Falha ao criar reserva temporária ({data_str} {hora_str} {chat_id}): {e}")
        send(chat_id, "Não consegui salvar sua reserva agora. Tente outro horário, por favor.")
        return False

def _update_status_confirmado(chat_id: str) -> bool:
    """
    Confirma a reserva temporária, transformando-a em agendamento confirmado.
    """
    if not excel or not hasattr(excel, "confirmar_reserva"):
        return False
    
    dt = state_manager.get_data(chat_id)
    chave = dt.get("ag_chave")
    
    if not chave:
        logger.warning(f"[FLOW] Sem chave de reserva para confirmar: {chat_id}")
        return False

    try:
        ok = excel.confirmar_reserva(chave)
        if ok:
            logger.info(f"[FLOW] Reserva confirmada: {chave}")
            return True
        else:
            logger.warning(f"[FLOW] Falha ao confirmar reserva: {chave}")
            return False
    except ValueError as ve:
        # Reserva expirada
        logger.warning(f"[FLOW] Reserva expirada: {chave} - {ve}")
        return False
    except Exception as e:
        logger.exception(f"[FLOW] Erro ao confirmar reserva {chave}: {e}")
        return False

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

    # ADMIN primeiro - delega para módulo admin.py
    if chat_id in _admin_ids():
        # Usa módulo admin se disponível, senão fallback para _route_admin local
        if admin_module and hasattr(admin_module, 'route_admin_message'):
            return admin_module.route_admin_message(send, chat_id, t)
        else:
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

    if st == S_ESCOLHER_SERVICO:  return _handle_escolher_servico(send, chat_id, t)
    if st == S_ESCOLHER_DATA:     return _handle_escolher_data(send, chat_id, t)
    if st == S_CONSULTAR_DATA:    return _handle_consultar_data(send, chat_id, t)
    if st == S_DATA:              return _handle_data(send, chat_id, t)
    if st == S_DATA_CONF:         return _handle_data_conf(send, chat_id, t)
    if st == S_MOSTRAR_HORAS:     return _handle_escolha_hora_index(send, chat_id, t)
    if st == S_ESCOLHER_HORA:     return _handle_hora_livre(send, chat_id, t)

    if st == S_REMARCAR_CONFIRMAR:     return _handle_remarcar_confirmar(send, chat_id, t)
    if st == S_REMARCAR_ESCOLHER_DATA: return _handle_remarcar_escolher_data(send, chat_id, t)
    if st == S_REMARCAR_ESCOLHER_HORA: return _handle_remarcar_escolher_hora(send, chat_id, t)

    if st == S_CANCELAR_CONFIRMAR:     return _handle_cancelar_confirmar(send, chat_id, t)

    # Área do Cliente
    if st == S_AREA_CLIENTE_CPF:       return _handle_area_cliente_cpf(send, chat_id, t)
    if st == S_AREA_CLIENTE_PIN:       return _handle_area_cliente_pin(send, chat_id, t)
    if st == S_AREA_CLIENTE_MENU:      return _handle_area_cliente_menu(send, chat_id, t)
    if st == S_AREA_CLIENTE_ALTERAR_PIN_NOVO: return _handle_area_cliente_alterar_pin_novo(send, chat_id, t)
    if st == S_AREA_CLIENTE_ALTERAR_PIN_CONF: return _handle_area_cliente_alterar_pin_conf(send, chat_id, t)

    return _send_main_menu(send, chat_id)


# =============================================================================
# Blocos de fluxo - CLIENTE
# =============================================================================

def _send_main_menu(send, chat_id):
    """Menu principal da barbearia"""
    top = "╔════════════════════════╗"
    titulo = "Bem-vindo(a) à Barbearia Veinho Corts!💈"
    sep = "╠════════════════════════╣"
    
    conteudo = [
        "",
        "     Como podemos te ajudar hoje?",
        "",
        "    1️⃣ Agendar Corte ou Serviço",
        "    2️⃣ Serviços e Valores",
        "    3️⃣ Dúvidas Frequentes",
        "    4️⃣ Falar com Atendente",
        "    5️⃣ Área do Cliente 🔐",
        ""
    ]
    
    bot = "╚════════════════════════╝"
    
    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
    mensagem += _nav_footer(["Responda com *1*, *2*, *3*, *4* ou *5*"])
    
    send(chat_id, mensagem)
    state_manager.set_state(chat_id, S_MENU_OPCAO)

def _handle_menu_opcao(send, chat_id, t):
    """Roteamento do menu principal"""
    t = (t or "").strip()

    if t == "1":
        top = "╔════════════════════════╗"
        titulo = "✂️ Agendamento na Barbearia"
        sep = "╠════════════════════════╣"
        
        conteudo = [
            "",
            "",
            "  1️⃣ Agendar novo corte/serviço",
            "  2️⃣ Consultar horários disponíveis",
            "  3️⃣ Consultar meu próximo horário",
            "  4️⃣ Remarcar horário",
            "  5️⃣ Cancelar horário",
            ""
        ]
        
        bot = "╚════════════════════════╝"
        
        mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
        mensagem += _nav_footer(["Responda com *1*, *2*, *3*, *4* ou *5*"])
        
        send(chat_id, mensagem)
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
            top = "╔════════════════════════╗"
            titulo = "💈 Serviços e Valores da Barbearia"
            sep = "╠════════════════════════╣"
            
            conteudo = [
                "",
                "",
                "  ✂️ Cabelo + Sombrancelha - R$ 45,00",
                "  🧔 Barba - R$ 15,00",
                "  👁️ Sombrancelha - R$ 10,00",
                "  ✨ Platinado - R$ 170,00",
                ""
            ]
            
            bot = "╚════════════════════════╝"
            rodape = "_Horário de funcionamento: consulte a agenda_"
            
            mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
            mensagem += "\n" + rodape
            mensagem += _nav_footer(["Digite *menu* para voltar"])
            
            send(chat_id, mensagem)
        state_manager.set_state(chat_id, S_MENU)

    elif t == "3":
        top = "╔════════════════════════╗"
        titulo = "❓ Dúvidas Frequentes"
        sep = "╠════════════════════════╣"
        
        conteudo = [
            "",
            "",
            "  📍 Onde ficamos?",
            "  Rua Exemplo, 123 - Centro",
            "",
            "  ⏰ Horário de funcionamento?",
            "  Seg a Sex: 9h às 19h",
            "  Sábado: 9h às 17h",
            "  Domingo: Fechado",
            "",
            "  💳 Formas de pagamento?",
            "  PIX, Cartão (débito/crédito), Dinheiro",
            "",
            "  📱 Como remarcar?",
            "  Digite menu e escolha opção 1, depois opção 4",
            "",
            "  ⚠️ Política de cancelamento?",
            "  Cancele com no mínimo 2h de antecedência",
            ""
        ]
        
        bot = "╚════════════════════════╝"
        
        mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
        mensagem += _nav_footer(["Digite *menu* para voltar"])
        
        send(chat_id, mensagem)
        state_manager.set_state(chat_id, S_MENU)
    elif t == "4":
        return _start_handoff(send, chat_id)
    elif t == "5":
        # Área do Cliente - pedir CPF
        top = "╔════════════════════════╗"
        titulo = "🔐 Área do Cliente"
        sep = "╠════════════════════════╣"
        
        conteudo = [
            "",
            "  Para acessar sua área",
            "  pessoal, precisamos",
            "  confirmar sua identidade.",
            "",
            "  📋 Digite seu CPF:",
            "  (apenas números)",
            ""
        ]
        
        bot = "╚════════════════════════╝"
        
        mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
        mensagem += _nav_footer(["Digite *menu* para cancelar"])
        
        send(chat_id, mensagem)
        state_manager.set_state(chat_id, S_AREA_CLIENTE_CPF)

    else:
        send(chat_id, "Opção inválida. Digite 1, 2, 3, 4 ou 5, ou *menu* para voltar.")

def _handle_escolher_servico(send, chat_id, t):
    """Processa escolha do serviço pelo número ou nome."""
    t_lower = t.lower().strip()
    
    if not sf:
        # Fallback sem sistema de serviços
        state_manager.update_data(chat_id, servico_escolhido="corte_simples")
        datas = _gerar_datas_disponiveis(dias=7)
        texto_datas = _formatar_lista_datas(datas)
        state_manager.update_data(chat_id, datas_disponiveis=datas)
        state_manager.set_state(chat_id, S_ESCOLHER_DATA)
        return send(chat_id, texto_datas + _nav_footer(["Digite *menu* para voltar"]))
    
    # Obter lista de serviços
    servicos = sf.listar_servicos()
    servico = None
    
    # Mapeamento de palavras-chave para IDs
    mapeamento_nomes = {
        "cabelo": "cabelo_sobrancelha",
        "corte": "cabelo_sobrancelha",
        "sombrancelha": "sobrancelha",
        "sobrancelha": "sobrancelha",
        "barba": "barba",
        "platinado": "platinado",
        "platina": "platinado"
    }
    
    # Tentar por número
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < len(servicos):
            servico = servicos[idx]
    
    # Tentar por nome/palavra-chave
    if not servico:
        # Buscar por palavra-chave
        for palavra, servico_id in mapeamento_nomes.items():
            if palavra in t_lower:
                servico = sf.get_servico_por_id(servico_id)
                if servico:
                    break
    
    # Se ainda não encontrou, tentar match parcial no nome do serviço
    if not servico:
        for s in servicos:
            nome_servico = s.get("nome", "").lower()
            if t_lower in nome_servico or nome_servico in t_lower:
                servico = s
                break
    
    if not servico:
        return send(chat_id, 
            f"❌ Serviço não encontrado.\n\n"
            f"Digite o *número* (1-{len(servicos)}) ou *nome* do serviço.\n"
            f"Exemplo: _1_ ou _barba_")
    
    servico_id = servico.get("id")
    servico_nome = servico.get("nome")
    
    # Emoji por ID
    emojis = {
        "cabelo_sobrancelha": "💇🏽",
        "barba": "🧔🏻‍♂️",
        "sobrancelha": "👁️",
        "platinado": "👨🏽‍🦳"
    }
    servico_emoji = emojis.get(servico_id, "✂️")
    
    # Salvar serviço escolhido no estado
    state_manager.update_data(chat_id, servico_escolhido=servico_id)
    
    # Mostrar confirmação e pedir data
    datas = _gerar_datas_disponiveis(dias=7)
    texto_datas = _formatar_lista_datas(datas)
    state_manager.update_data(chat_id, datas_disponiveis=datas)
    state_manager.set_state(chat_id, S_ESCOLHER_DATA)
    
    msg = f"{servico_emoji} *{servico_nome}* selecionado!\n\n{texto_datas}"
    send(chat_id, msg + _nav_footer(["Digite *menu* para voltar"]))

def _handle_ag_submenu(send, chat_id, t):
    t = (t or "").strip()

    if t == "1":
        # Primeiro passo: escolher o serviço
        if sf:
            texto_servicos = sf.listar_servicos_formatado()
            state_manager.update_data(chat_id, acao="agendar")
            state_manager.set_state(chat_id, S_ESCOLHER_SERVICO)
            send(chat_id, texto_servicos + _nav_footer(["Digite o *número* ou *nome* do serviço", "Digite *menu* para voltar"]))
        else:
            # Fallback: ir direto para escolher data (sem serviços)
            datas = _gerar_datas_disponiveis(dias=7)
            texto_datas = _formatar_lista_datas(datas)
            state_manager.update_data(chat_id, datas_disponiveis=datas, acao="agendar", servico_escolhido="corte_simples")
            state_manager.set_state(chat_id, S_ESCOLHER_DATA)
            send(chat_id, texto_datas + _nav_footer(["Digite *menu* para voltar"]))

    elif t == "2":
        # Consultar horários disponíveis
        datas = _gerar_datas_disponiveis(dias=7)
        texto_datas = _formatar_lista_datas(datas)
        
        # Salvar datas e marcar como consulta (não agendamento)
        state_manager.update_data(chat_id, datas_disponiveis=datas, acao="consultar")
        state_manager.set_state(chat_id, S_CONSULTAR_DATA)
        
        send(chat_id, texto_datas + _nav_footer(["Digite *menu* para voltar"]))

    elif t == "3":
        # Consultar próximo horário agendado
        if excel and hasattr(excel, "buscar_proximo_agendamento"):
            try:
                agendamento = excel.buscar_proximo_agendamento(chat_id)
                
                if agendamento:
                    data = agendamento.get("Data", "")
                    hora = agendamento.get("Hora", "")
                    nome = agendamento.get("ClienteNome", "Cliente")
                    
                    # Calcular dias restantes
                    try:
                        data_hora_obj = agendamento.get("data_hora_obj")
                        agora = datetime.now()
                        diferenca = data_hora_obj - agora
                        dias_restantes = diferenca.days
                        
                        # Mostrar apenas se for futuro
                        if data_hora_obj >= agora:
                            if dias_restantes == 0:
                                # Hoje
                                horas_restantes = diferenca.seconds // 3600
                                if horas_restantes > 0:
                                    quando = f"Hoje - faltam {horas_restantes}h"
                                else:
                                    minutos_restantes = diferenca.seconds // 60
                                    quando = f"Hoje - faltam {minutos_restantes} min"
                            elif dias_restantes == 1:
                                quando = "Amanhã"
                            else:
                                quando = f"Em {dias_restantes} dias"
                        else:
                            quando = ""
                    except:
                        quando = ""
                    
                    top = "╔════════════════════════╗"
                    titulo = "📅 Seu Próximo Agendamento"
                    sep = "╠════════════════════════╣"
                    
                    conteudo = [
                        "",
                        "",
                        f"  👤 {nome}",
                        f"  📅 Data: {data}",
                        f"  ⏰ Horário: {hora}",
                    ]
                    
                    if quando:
                        conteudo.append(f"  🕐 {quando}")
                    
                    conteudo.append("")
                    
                    bot = "╚════════════════════════╝"
                    
                    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                    mensagem += _nav_footer(["Digite *menu* para voltar"])
                    
                    send(chat_id, mensagem)
                else:
                    send(chat_id, 
                        "📅 Você não possui nenhum agendamento futuro.\n\n"
                        "Deseja agendar um horário agora?"
                        + _nav_footer(["Digite *1* para agendar", "Digite *menu* para voltar"]))
            except Exception as e:
                logger.error(f"Erro ao buscar próximo agendamento: {e}")
                send(chat_id, "Erro ao consultar agendamento. Digite *menu* para voltar.")
        else:
            send(chat_id, "Funcionalidade indisponível no momento. Digite *menu* para voltar.")
        
        state_manager.set_state(chat_id, S_MENU)

    elif t == "4":
        # Remarcar horário - buscar agendamento ativo
        if excel and hasattr(excel, "buscar_proximo_agendamento"):
            try:
                agendamento = excel.buscar_proximo_agendamento(chat_id)
                
                if agendamento:
                    data = agendamento.get("Data", "")
                    hora = agendamento.get("Hora", "")
                    
                    top = "╔════════════════════════╗"
                    titulo = "🔄 Remarcar Agendamento"
                    sep = "╠════════════════════════╣"
                    
                    conteudo = [
                        "",
                        "",
                        "  📋 Agendamento atual:",
                        "",
                        f"  📅 Data: {data}",
                        f"  ⏰ Horário: {hora}",
                        "",
                        "  Deseja remarcar este agendamento?",
                        ""
                    ]
                    
                    bot = "╚════════════════════════╝"
                    
                    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                    mensagem += _nav_footer(["Digite *sim* para remarcar", "Digite *não* ou *menu* para cancelar"])
                    
                    # Salvar dados do agendamento original
                    state_manager.update_data(
                        chat_id, 
                        agendamento_original_data=data,
                        agendamento_original_hora=hora,
                        agendamento_original_chave=agendamento.get("Chave", "")
                    )
                    state_manager.set_state(chat_id, S_REMARCAR_CONFIRMAR)
                    
                    send(chat_id, mensagem)
                else:
                    send(chat_id, 
                        "📅 Você não possui nenhum agendamento para remarcar.\n\n"
                        "Deseja fazer um novo agendamento?"
                        + _nav_footer(["Digite *1* para agendar", "Digite *menu* para voltar"]))
                    state_manager.set_state(chat_id, S_MENU)
            except Exception as e:
                logger.error(f"Erro ao buscar agendamento para remarcar: {e}")
                send(chat_id, "Erro ao buscar agendamento. Digite *menu* para voltar.")
                state_manager.set_state(chat_id, S_MENU)
        else:
            send(chat_id, "Funcionalidade indisponível no momento. Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)

    elif t == "5":
        # Cancelar horário - buscar agendamento ativo
        if excel and hasattr(excel, "buscar_proximo_agendamento"):
            try:
                agendamento = excel.buscar_proximo_agendamento(chat_id)
                
                if agendamento:
                    data = agendamento.get("Data", "")
                    hora = agendamento.get("Hora", "")
                    status = agendamento.get("Status", "")
                    nome = agendamento.get("ClienteNome", "Cliente")
                    
                    # Calcular quando é o agendamento
                    try:
                        data_hora_obj = agendamento.get("data_hora_obj")
                        agora = datetime.now()
                        diferenca = data_hora_obj - agora
                        dias_restantes = diferenca.days
                        
                        if data_hora_obj < agora:
                            quando = "já passou"
                        elif dias_restantes == 0:
                            horas_restantes = diferenca.seconds // 3600
                            if horas_restantes > 0:
                                quando = f"hoje - faltam {horas_restantes}h"
                            else:
                                minutos_restantes = diferenca.seconds // 60
                                quando = f"hoje - faltam {minutos_restantes} min"
                        elif dias_restantes == 1:
                            quando = "amanhã"
                        else:
                            quando = f"em {dias_restantes} dias"
                    except:
                        quando = ""
                    
                    top = "╔════════════════════════╗"
                    titulo = "❌ Cancelar Agendamento"
                    sep = "╠════════════════════════╣"
                    
                    conteudo = [
                        "",
                        "",
                        "  📋 Agendamento a cancelar:",
                        "",
                        f"  👤 {nome}",
                        f"  📅 Data: {data}",
                        f"  ⏰ Horário: {hora}",
                    ]
                    
                    if quando:
                        conteudo.append(f"  🕒 {quando.capitalize()}")
                    
                    conteudo.extend([
                        "",
                        "  ⚠️ Tem certeza que deseja cancelar?",
                        ""
                    ])
                    
                    bot = "╚════════════════════════╝"
                    
                    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                    mensagem += _nav_footer(["Digite *sim* para confirmar cancelamento", "Digite *não* ou *menu* para voltar"])
                    
                    # Salvar dados do agendamento para cancelar
                    state_manager.update_data(
                        chat_id, 
                        cancelar_data=data,
                        cancelar_hora=hora,
                        cancelar_chave=agendamento.get("Chave", "")
                    )
                    state_manager.set_state(chat_id, S_CANCELAR_CONFIRMAR)
                    
                    send(chat_id, mensagem)
                else:
                    send(chat_id, 
                        "📅 Você não possui nenhum agendamento para cancelar.\n\n"
                        "Deseja fazer um novo agendamento?"
                        + _nav_footer(["Digite *1* para agendar", "Digite *menu* para voltar"]))
                    state_manager.set_state(chat_id, S_MENU)
            except Exception as e:
                logger.error(f"Erro ao buscar agendamento para cancelar: {e}")
                send(chat_id, "Erro ao buscar agendamento. Digite *menu* para voltar.")
                state_manager.set_state(chat_id, S_MENU)
        else:
            send(chat_id, "Funcionalidade indisponível no momento. Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)

    else:
        send(chat_id, "Opção inválida. Escolha entre 1, 2, 3, 4 ou 5.")

# ===== escolher data da lista =====

def _handle_escolher_data(send, chat_id, t):
    """Processa escolha de data pelo número da lista para AGENDAMENTO."""
    if not t.isdigit():
        return send(chat_id, "Por favor, envie o *número* da data desejada (ex: 3).")
    
    dt = state_manager.get_data(chat_id)
    datas = dt.get("datas_disponiveis") or []
    
    if not datas:
        # Fallback: gerar novamente
        datas = _gerar_datas_disponiveis(dias=7)
        state_manager.update_data(chat_id, datas_disponiveis=datas)
    
    idx = int(t) - 1
    if idx < 0 or idx >= len(datas):
        return send(chat_id, f"Número inválido. Escolha entre 1 e {len(datas)}.")
    
    data_str, data_display = datas[idx]
    
    # Agora buscar horários disponíveis para essa data (para agendamento)
    return _mostrar_horarios_disponiveis(send, chat_id, data_str, data_display)

def _handle_consultar_data(send, chat_id, t):
    """Processa escolha de data pelo número da lista para CONSULTA (apenas visualização)."""
    if not t.isdigit():
        return send(chat_id, "Por favor, envie o *número* da data desejada (ex: 3).")
    
    dt = state_manager.get_data(chat_id)
    datas = dt.get("datas_disponiveis") or []
    
    if not datas:
        # Fallback: gerar novamente
        datas = _gerar_datas_disponiveis(dias=7)
        state_manager.update_data(chat_id, datas_disponiveis=datas)
    
    idx = int(t) - 1
    if idx < 0 or idx >= len(datas):
        return send(chat_id, f"Número inválido. Escolha entre 1 e {len(datas)}.")
    
    data_str, data_display = datas[idx]
    
    # Mostrar horários apenas para consulta (sem permitir agendamento)
    return _mostrar_horarios_consulta(send, chat_id, data_str, data_display)

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

def _mostrar_horarios_disponiveis(send, chat_id, data_str: str, data_display: str = None):
    """
    Busca e exibe TODOS os horários (livres e ocupados) para uma data específica.
    Usa slots dinâmicos baseados no serviço escolhido.
    """
    # Obter serviço escolhido
    dados = state_manager.get_data(chat_id)
    servico_id = dados.get("servico_escolhido", "corte_simples")
    
    # Obter slots dinâmicos do dia para o serviço específico
    slots_do_dia = _obter_slots_dia(data_str, servico_id)
    
    # Verificar status de cada horário
    horarios_status = []
    horarios_livres = []
    
    # Liberar slots expirados antes de verificar disponibilidade
    if excel and hasattr(excel, "liberar_slots_expirados"):
        try:
            excel.liberar_slots_expirados()
        except Exception as e:
            logger.warning(f"Erro ao liberar slots expirados: {e}")
    
    for h in slots_do_dia:
        disponivel = True
        if excel and hasattr(excel, "verificar_disponibilidade"):
            try:
                disponivel = excel.verificar_disponibilidade(data_str, h, servico_id)
            except Exception:
                disponivel = True
        
        status = "✅ Livre" if disponivel else "❌ Ocupado"
        horarios_status.append((h, status, disponivel))
        if disponivel:
            horarios_livres.append(h)
    
    # Verificar se tem horários disponíveis
    if not horarios_livres:
        send(chat_id,
            f"😕 Não há horários disponíveis para *{data_display or data_str}*.\n\n"
            "Por favor, escolha outra data."
            + _nav_footer(["Digite *menu* para voltar ao início"])
        )
        # Voltar para escolher outra data
        state_manager.set_state(chat_id, S_ESCOLHER_DATA)
        datas = _gerar_datas_disponiveis(dias=7)
        state_manager.update_data(chat_id, datas_disponiveis=datas)
        texto_datas = _formatar_lista_datas(datas)
        return send(chat_id, texto_datas)
    
    # Formatar lista de horários com novo visual (mostra todos)
    top = "╔════════════════════════╗"
    titulo = f"  🕐 Horários disponíveis — {data_str}"
    sep = "╠════════════════════════╣"
    
    linhas_horarios = []
    for idx, (hora, status, disponivel) in enumerate(horarios_status, 1):
        linhas_horarios.append(f"  {idx} - {hora} - {status}")
    
    bot = "╚════════════════════════╝"
    rodape = "👉 Digite o número do horário desejado."
    
    mensagem = "\n".join([top, titulo, sep] + linhas_horarios + ["", bot])
    mensagem += "\n" + rodape
    mensagem += _nav_footer(["Digite *menu* para voltar"])
    
    # Salvar estado (apenas os livres para validação)
    state_manager.update_data(
        chat_id,
        data=data_str,
        horas_disponiveis=horarios_livres,
        todos_horarios=horarios_status  # Guardar todos para referência
    )
    state_manager.set_state(chat_id, S_MOSTRAR_HORAS)
    
    send(chat_id, mensagem)

def _mostrar_horarios_consulta(send, chat_id, data_str: str, data_display: str = None):
    """
    Mostra horários disponíveis apenas para CONSULTA (visualização).
    Mostra TODOS os horários (livres e ocupados).
    """
    # Obter slots dinâmicos do dia
    slots_do_dia = _obter_slots_dia(data_str)
    
    # Verificar quais horários estão livres e quais ocupados
    horarios_status = []
    
    for h in slots_do_dia:
        disponivel = True
        if excel and hasattr(excel, "verificar_disponibilidade"):
            try:
                disponivel = excel.verificar_disponibilidade(data_str, h)
            except Exception:
                disponivel = True
        
        status = "✅ Livre" if disponivel else "❌ Ocupado"
        horarios_status.append((h, status))
    
    # Formatar com o novo visual
    top = "╔════════════════════════╗"
    titulo = f"  🕐 Horários disponíveis — {data_str}"
    sep = "╠════════════════════════╣"
    
    linhas_horarios = []
    for idx, (hora, status) in enumerate(horarios_status, 1):
        linhas_horarios.append(f"  {idx}\u2006-\u2006{hora}\u2006-\u2006{status}")
    
    total_livres = sum(1 for _, status in horarios_status if "Livre" in status)
    bot = "╚════════════════════════╝"
    rodape = f"📊 Total: {total_livres} horários disponíveis"
    
    mensagem = "\n".join([top, titulo, sep] + linhas_horarios + ["", bot])
    mensagem += "\n" + rodape
    mensagem += _nav_footer([
        "Digite *menu* para voltar",
        "Digite *1* para fazer um agendamento"
    ])
    
    state_manager.set_state(chat_id, S_MENU)
    send(chat_id, mensagem)

def _mostrar_grade_horarios(send, chat_id, data_str: str):
    slots_do_dia = _obter_slots_dia(data_str)
    livres = set()
    for h in slots_do_dia:
        ok = True
        if excel and hasattr(excel, "verificar_disponibilidade"):
            try:
                ok = excel.verificar_disponibilidade(data_str, h)
            except Exception:
                ok = True
        if ok: livres.add(h)

    quadro, tem_livre = _format_grade_compact(data_str, slots_do_dia, livres)
    send(chat_id, quadro)

    horas_livres_ordenadas = [h for h in slots_do_dia if h in livres]
    state_manager.update_data(chat_id, data=data_str, horas_disponiveis=horas_livres_ordenadas)
    state_manager.set_state(chat_id, S_MOSTRAR_HORAS if tem_livre else S_DATA)

def _handle_escolha_hora_index(send, chat_id, t):
    dt = state_manager.get_data(chat_id)
    horarios = dt.get("horas_disponiveis") or []
    todos_horarios = dt.get("todos_horarios") or []
    
    if not todos_horarios:
        state_manager.set_state(chat_id, S_ESCOLHER_HORA)
        return send(chat_id, "Digite o *horário desejado* no formato HH:MM (ex: 14:00).")
    
    if not t.isdigit():
        return send(chat_id, "Envie o *número* do horário desejado (ex: 2).")
    
    idx = int(t) - 1
    if idx < 0 or idx >= len(todos_horarios):
        return send(chat_id, "Número inválido. Escolha uma das opções listadas.")
    
    # Pegar o horário da lista completa
    hora_str, status, disponivel = todos_horarios[idx]
    
    # Verificar se o horário está livre
    if not disponivel:
        return send(chat_id, 
            f"❌ Desculpe, o horário *{hora_str}* já está ocupado.\n\n"
            "Por favor, escolha outro horário disponível.")
    
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
    # VALIDAÇÃO 1: Verificar se já tem agendamento ativo
    if excel and hasattr(excel, "tem_agendamento_ativo_na_semana"):
        try:
            tem_ativo, agendamento_info = excel.tem_agendamento_ativo_na_semana(chat_id)
            if tem_ativo and agendamento_info:
                data_atual = agendamento_info.get("Data", "")
                hora_atual = agendamento_info.get("Hora", "")
                status_atual = agendamento_info.get("Status", "")
                
                top = "╔════════════════════════╗"
                titulo = "⚠️ Limite de Agendamento Atingido"
                sep = "╠════════════════════════╣"
                
                conteudo = [
                    "",
                    "",
                    "  Você já possui um agendamento ativo:",
                    "",
                    f"  📅 Data: {data_atual}",
                    f"  ⏰ Horário: {hora_atual}",
                    f"  📊 Status: {status_atual}",
                    "",
                    "  💡 Para fazer um novo agendamento,",
                    "  cancele o atual (opção 5) ou",
                    "  aguarde ele ser realizado.",
                    ""
                ]
                
                bot = "╚════════════════════════╝"
                
                mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                mensagem += _nav_footer(["Digite *menu* para voltar"])
                
                send(chat_id, mensagem)
                state_manager.set_state(chat_id, S_MENU)
                return
        except Exception as e:
            logger.warning(f"Erro ao verificar limite semanal: {e}")
    
    # VALIDAÇÃO 2: Verificar se é feriado
    if excel and hasattr(excel, "eh_feriado"):
        try:
            if excel.eh_feriado(data_str):
                send(chat_id,
                     f"🚫 *Feriado bloqueado*\n\n"
                     f"A data *{data_str}* é um feriado e não está disponível para agendamentos.\n\n"
                     f"Por favor, escolha outra data."
                     + _nav_footer(["Digite *menu* para voltar"]))
                state_manager.set_state(chat_id, S_MENU)
                return
        except Exception as e:
            logger.warning(f"Erro ao verificar feriado: {e}")
    
    # VALIDAÇÃO 3: Verificar se horário está muito próximo (<2h)
    if excel and hasattr(excel, "horario_muito_proximo"):
        try:
            if excel.horario_muito_proximo(data_str, hora_str, horas_minimas=2):
                send(chat_id,
                     f"⏰ *Horário muito próximo*\n\n"
                     f"Para garantir a qualidade do atendimento, "
                     f"precisamos de no mínimo *2 horas* de antecedência para agendamentos.\n\n"
                     f"O horário *{data_str} às {hora_str}* está muito próximo.\n\n"
                     f"Por favor, escolha um horário com mais antecedência."
                     + _nav_footer(["Digite *menu* para voltar"]))
                state_manager.set_state(chat_id, S_MENU)
                return
        except Exception as e:
            logger.warning(f"Erro ao verificar horário próximo: {e}")
    
    # VALIDAÇÃO 4: Verificar disponibilidade do horário
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

    # CRIAR AGENDAMENTO (já com status Confirmado)
    ok = _pre_reservar(send, chat_id, data_str, hora_str)
    if not ok:
        return
    
    # CONFIRMAR AGENDAMENTO (atualizar status para garantir)
    _update_status_confirmado(chat_id)

    # MENSAGEM DE CONFIRMAÇÃO
    dados = state_manager.get_data(chat_id)
    servico_id = dados.get("servico_escolhido", "corte_simples")
    
    # Buscar informações do serviço
    servico_info = None
    if sf:
        try:
            servico_info = sf.get_servico_por_id(servico_id)
        except:
            pass
    
    # Obter valor e nome do serviço
    if servico_info:
        valor_servico = servico_info.get("valor", VALOR_SERVICO_PADRAO)
        nome_servico = servico_info.get("nome", "Corte de Cabelo")
        emoji_servico = servico_info.get("emoji", "✂️")
    else:
        valor_servico = VALOR_SERVICO_PADRAO
        nome_servico = "Corte de Cabelo"
        emoji_servico = "✂️"
    
    valor_str = format_money(valor_servico)
    
    top = "╔════════════════════════╗"
    titulo = "✅ Agendamento Confirmado!"
    sep = "╠════════════════════════╣"
    
    conteudo = [
        "",
        "",
        f"  {emoji_servico} Serviço: *{nome_servico}*",
        f"  📅 Data: *{data_str}*",
        f"  ⏰ Horário: *{hora_str}*",
        f"  💰 Valor: *{valor_str}*",
        ""
    ]
    
    # Se for serviço fracionado, adicionar resumo das etapas
    if servico_info and servico_info.get("tipo") == "fracionado" and sf:
        try:
            resumo = sf.formatar_resumo_servico(servico_id, hora_str, data_str)
            conteudo.append("")
            # Adicionar resumo formatado
            for linha in resumo.split("\n"):
                if linha.strip():
                    conteudo.append(f"  {linha}")
            conteudo.append("")
        except:
            pass
    
    conteudo.extend([
        "  💈 Te esperamos na barbearia!",
        "  💳 Pagamento no local.",
        ""
    ])
    
    bot = "╚════════════════════════╝"
    
    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
    mensagem += _nav_footer(["Digite *menu* para voltar ao início"])
    
    send(chat_id, mensagem)
    send(chat_id, "Posso ajudar em algo mais? Digite *menu* para voltar ao início.")
    
    state_manager.set_state(chat_id, S_MENU)
    _clear_flow_fields(chat_id)

# ===== Remarcação de horário =====

def _handle_remarcar_confirmar(send, chat_id, t):
    """Handler para confirmação se usuário quer remarcar."""
    t = (t or "").strip().lower()
    
    if t == "sim":
        # Usuário confirmou que quer remarcar
        datas = _gerar_datas_disponiveis(dias=7)
        texto_datas = _formatar_lista_datas(datas)
        
        state_manager.update_data(chat_id, datas_disponiveis=datas)
        state_manager.set_state(chat_id, S_REMARCAR_ESCOLHER_DATA)
        
        top = "╔════════════════════════╗"
        titulo = "🗓️ Escolha a nova data"
        sep = "╠════════════════════════╣"
        conteudo = ["", "  Selecione a nova data para", "  seu agendamento:", ""]
        bot = "╚════════════════════════╝"
        
        intro = "\n".join([top, titulo, sep] + conteudo + [bot])
        send(chat_id, intro)
        send(chat_id, texto_datas + _nav_footer(["Digite *menu* para cancelar"]))
    
    elif t in ("não", "nao"):
        send(chat_id, "Remarcação cancelada. Digite *menu* para voltar ao início.")
        state_manager.set_state(chat_id, S_MENU)
        _clear_flow_fields(chat_id)
    
    else:
        send(chat_id, "Responda *sim* para confirmar a remarcação ou *não* para cancelar.")

def _handle_remarcar_escolher_data(send, chat_id, t):
    """Handler para escolha da nova data na remarcação."""
    if not t.isdigit():
        return send(chat_id, "Por favor, envie o *número* da data desejada (ex: 3).")
    
    dt = state_manager.get_data(chat_id)
    datas = dt.get("datas_disponiveis") or []
    
    if not datas:
        datas = _gerar_datas_disponiveis(dias=7)
        state_manager.update_data(chat_id, datas_disponiveis=datas)
    
    idx = int(t) - 1
    if idx < 0 or idx >= len(datas):
        return send(chat_id, f"Número inválido. Escolha entre 1 e {len(datas)}.")
    
    data_str, data_display = datas[idx]
    
    # Buscar horários disponíveis
    slots_do_dia = _obter_slots_dia(data_str)
    horarios_livres = []
    if excel and hasattr(excel, "listar_horarios_disponiveis"):
        try:
            horarios_livres = excel.listar_horarios_disponiveis(
                data_str,
                allowed_slots=slots_do_dia
            )
        except Exception as e:
            logger.warning(f"Erro ao buscar horários disponíveis: {e}")
    
    if not horarios_livres:
        for h in slots_do_dia:
            disponivel = True
            if excel and hasattr(excel, "verificar_disponibilidade"):
                try:
                    disponivel = excel.verificar_disponibilidade(data_str, h)
                except Exception:
                    disponivel = True
            if disponivel:
                horarios_livres.append(h)
    
    if not horarios_livres:
        send(chat_id,
            f"😕 Não há horários disponíveis para *{data_display or data_str}*.\n\n"
            "Por favor, escolha outra data."
            + _nav_footer(["Digite *menu* para cancelar"]))
        return
    
    # Mostrar horários disponíveis
    top = "╔════════════════════════╗"
    titulo = f"  🕐 Horários disponíveis — {data_str}"
    sep = "╠════════════════════════╣"
    
    linhas_horarios = []
    for idx, hora in enumerate(horarios_livres, 1):
        linhas_horarios.append(f"  {idx}\u2006-\u2006{hora}\u2006-\u2006✅ Livre")
    
    bot = "╚════════════════════════╝"
    rodape = "👉 Digite o número do novo horário."
    
    mensagem = "\n".join([top, titulo, sep] + linhas_horarios + ["", bot])
    mensagem += "\n" + rodape
    mensagem += _nav_footer(["Digite *menu* para cancelar"])
    
    state_manager.update_data(
        chat_id,
        remarcar_nova_data=data_str,
        remarcar_horas_disponiveis=horarios_livres
    )
    state_manager.set_state(chat_id, S_REMARCAR_ESCOLHER_HORA)
    
    send(chat_id, mensagem)

def _handle_remarcar_escolher_hora(send, chat_id, t):
    """Handler para escolha do novo horário na remarcação."""
    if not t.isdigit():
        return send(chat_id, "Por favor, envie o *número* do horário desejado.")
    
    dt = state_manager.get_data(chat_id)
    horarios = dt.get("remarcar_horas_disponiveis") or []
    
    if not horarios:
        send(chat_id, "Erro ao processar horários. Digite *menu* para voltar.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    idx = int(t) - 1
    if idx < 0 or idx >= len(horarios):
        return send(chat_id, f"Número inválido. Escolha entre 1 e {len(horarios)}.")
    
    nova_hora = horarios[idx]
    nova_data = dt.get("remarcar_nova_data")
    
    # Dados do agendamento original
    data_antiga = dt.get("agendamento_original_data")
    hora_antiga = dt.get("agendamento_original_hora")
    chave_antiga = dt.get("agendamento_original_chave")
    
    # Verificar disponibilidade do novo horário
    disponivel = True
    if excel and hasattr(excel, "verificar_disponibilidade"):
        try:
            disponivel = excel.verificar_disponibilidade(nova_data, nova_hora)
        except Exception:
            disponivel = True
    
    if not disponivel:
        send(chat_id,
            f"😕 O horário *{nova_data} às {nova_hora}* não está mais disponível.\n"
            "Por favor, escolha outro horário."
            + _nav_footer(["Digite *menu* para cancelar"]))
        return
    
    # EXECUTAR REMARCAÇÃO
    if not excel:
        send(chat_id, "Erro: sistema de agendamentos indisponível.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    try:
        # Atualizar agendamento existente com nova data/hora
        if hasattr(excel, "atualizar_agendamento_remarcar"):
            # Função dedicada para remarcação (retorna tupla)
            sucesso, erro = excel.atualizar_agendamento_remarcar(
                chave_antiga, nova_data, nova_hora
            )
            
            # Verificar se atingiu limite de remarcações
            if not sucesso and erro == "limite_atingido":
                top = "╔════════════════════════╗"
                titulo = "⚠️ Limite de Remarcações"
                sep = "╠════════════════════════╣"
                
                conteudo = [
                    "",
                    "",
                    "  Este agendamento já foi",
                    "  remarcado anteriormente.",
                    "",
                    "  💡 Cada agendamento pode ser",
                    "  remarcado apenas *1 vez*.",
                    "",
                    "  Para alterar novamente:",
                    "  • Cancele este agendamento (opção 5)",
                    "  • Faça um novo agendamento (opção 1)",
                    ""
                ]
                
                bot = "╚════════════════════════╝"
                
                mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                mensagem += _nav_footer(["Digite *menu* para voltar"])
                
                send(chat_id, mensagem)
                state_manager.set_state(chat_id, S_MENU)
                _clear_flow_fields(chat_id)
                return
            
            elif not sucesso:
                send(chat_id, f"Erro ao processar remarcação: {erro or 'desconhecido'}")
                state_manager.set_state(chat_id, S_MENU)
                return
        else:
            # Fallback: cancelar antigo e criar novo
            if chave_antiga:
                excel.atualizar_status_por_chave(chave_antiga, "Cancelado")
            
            nome = dt.get("nome")
            nasc = dt.get("data_nascimento") or dt.get("nascimento")
            cpf = dt.get("cpf")
            servico_id = dt.get("servico_escolhido", "corte_simples")
            
            nova_chave = excel.adicionar_agendamento(
                nova_data, nova_hora, chat_id,
                status="Confirmado",
                cliente_nome=nome,
                data_nasc=nasc,
                cpf=cpf,
                valor_pago=None,
                servico_id=servico_id
            )
            sucesso = bool(nova_chave)
        
        if sucesso:
            # MENSAGEM DE CONFIRMAÇÃO
            valor_str = format_money(VALOR_SERVICO_PADRAO)
            
            top = "╔════════════════════════╗"
            titulo = "✅ Remarcação Confirmada!"
            sep = "╠════════════════════════╣"
            
            conteudo = [
                "",
                "",
                "  📋 Agendamento anterior:",
                f"  📅 {data_antiga} às {hora_antiga}",
                "",
                "  🔄 Novo agendamento:",
                f"  📅 Data: *{nova_data}*",
                f"  ⏰ Horário: *{nova_hora}*",
                f"  💰 Valor: *{valor_str}*",
                "",
                "  💈 Te esperamos na barbearia!",
                "  💳 Pagamento no local.",
                ""
            ]
            
            bot = "╚════════════════════════╝"
            
            mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
            mensagem += _nav_footer(["Digite *menu* para voltar ao início"])
            
            send(chat_id, mensagem)
            send(chat_id, "Posso ajudar em algo mais? Digite *menu* para voltar ao início.")
            
            state_manager.set_state(chat_id, S_MENU)
            _clear_flow_fields(chat_id)
        else:
            send(chat_id, "Erro ao processar remarcação. Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)
    
    except Exception as e:
        logger.exception(f"Erro ao remarcar agendamento: {e}")
        send(chat_id, "Erro ao processar remarcação. Digite *menu* para voltar.")
        state_manager.set_state(chat_id, S_MENU)

# ===== Cancelamento de horário =====

def _handle_cancelar_confirmar(send, chat_id, t):
    """Handler para confirmação de cancelamento."""
    t = (t or "").strip().lower()
    
    if t == "sim":
        # Usuário confirmou cancelamento
        dt = state_manager.get_data(chat_id)
        chave = dt.get("cancelar_chave")
        data = dt.get("cancelar_data")
        hora = dt.get("cancelar_hora")
        
        if not chave:
            send(chat_id, "Erro: agendamento não encontrado. Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)
            return
        
        # Cancelar agendamento no Excel
        try:
            if excel and hasattr(excel, "atualizar_status_por_chave"):
                sucesso = excel.atualizar_status_por_chave(chave, "Cancelado")
                
                if sucesso:
                    top = "╔════════════════════════╗"
                    titulo = "✅ Agendamento Cancelado"
                    sep = "╠════════════════════════╣"
                    
                    conteudo = [
                        "",
                        "",
                        "  Seu agendamento foi cancelado:",
                        "",
                        f"  📅 Data: {data}",
                        f"  ⏰ Horário: {hora}",
                        "",
                        "  ℹ️ Agora você pode fazer um",
                        "  novo agendamento quando quiser.",
                        ""
                    ]
                    
                    bot = "╚════════════════════════╝"
                    
                    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
                    mensagem += _nav_footer(["Digite *1* para novo agendamento", "Digite *menu* para voltar"])
                    
                    send(chat_id, mensagem)
                    state_manager.set_state(chat_id, S_MENU)
                    _clear_flow_fields(chat_id)
                else:
                    send(chat_id, "Erro ao cancelar agendamento. Digite *menu* para voltar.")
                    state_manager.set_state(chat_id, S_MENU)
            else:
                send(chat_id, "Funcionalidade indisponível. Digite *menu* para voltar.")
                state_manager.set_state(chat_id, S_MENU)
        
        except Exception as e:
            logger.exception(f"Erro ao cancelar agendamento: {e}")
            send(chat_id, "Erro ao processar cancelamento. Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)
    
    elif t in ("não", "nao"):
        send(chat_id, "Cancelamento cancelado. Seu agendamento continua ativo.\nDigite *menu* para voltar.")
        state_manager.set_state(chat_id, S_MENU)
        _clear_flow_fields(chat_id)
    
    else:
        send(chat_id, "Responda *sim* para confirmar o cancelamento ou *não* para manter o agendamento.")


# ======= Área do Cliente =======

def _handle_area_cliente_cpf(send, chat_id, t):
    """Handler para receber CPF na Área do Cliente"""
    import re
    from services import clientes_services as cs
    
    cpf = re.sub(r"\D", "", t or "")
    
    if not cpf or len(cpf) != 11:
        send(chat_id, "❌ CPF inválido. Digite 11 números ou *menu* para voltar.")
        return
    
    # Verificar se CPF existe
    cliente = cs.get_by_cpf(cpf)
    if not cliente:
        send(chat_id, 
             "❌ CPF não cadastrado.\n\n"
             "Para acessar a área do cliente, você precisa ter um agendamento conosco.\n"
             "Digite *menu* para voltar e fazer seu primeiro agendamento!")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    # Verificar se está bloqueado por tentativas
    if cs.esta_bloqueado(cpf):
        send(chat_id,
             "🔒 *Acesso temporariamente bloqueado*\n\n"
             "Você excedeu o número de tentativas de PIN.\n"
             "Por segurança, aguarde 15 minutos antes de tentar novamente.\n\n"
             "Digite *menu* para voltar ao menu principal.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    # Salvar CPF no estado e pedir PIN
    state_manager.update_data(chat_id, area_cliente_cpf=cpf)
    
    top = "╔════════════════════════╗"
    titulo = "🔐 Digite seu PIN"
    sep = "╠════════════════════════╣"
    
    conteudo = [
        "",
        f"  👤 CPF: {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}",
        "",
        "  Digite seu PIN de 4 dígitos:",
        ""
    ]
    
    bot = "╚════════════════════════╝"
    
    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
    mensagem += _nav_footer(["Digite *menu* para cancelar"])
    
    send(chat_id, mensagem)
    state_manager.set_state(chat_id, S_AREA_CLIENTE_PIN)


def _handle_area_cliente_pin(send, chat_id, t):
    """Handler para validar PIN e mostrar menu da área do cliente"""
    import re
    from services import clientes_services as cs
    
    dt = state_manager.get_data(chat_id)
    cpf = dt.get("area_cliente_cpf", "")
    
    if not cpf:
        send(chat_id, "❌ Sessão expirada. Digite *menu* para recomeçar.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    pin = re.sub(r"\D", "", t or "")
    
    if not pin or len(pin) != 4:
        send(chat_id, "❌ PIN deve ter 4 dígitos. Tente novamente ou digite *menu* para cancelar.")
        return
    
    # Verificar PIN
    if not cs.verify_pin(cpf, pin):
        # Incrementar tentativas
        tentativas = cs.incrementar_tentativa_pin(cpf)
        
        if tentativas >= 3:
            send(chat_id,
                 "🔒 *Acesso bloqueado por 15 minutos*\n\n"
                 "Você excedeu o número de tentativas de PIN (3/3).\n"
                 "Por segurança, seu acesso foi temporariamente bloqueado.\n\n"
                 "⏰ Tente novamente após 15 minutos.\n"
                 "Digite *menu* para voltar.")
            state_manager.set_state(chat_id, S_MENU)
        else:
            send(chat_id,
                 f"❌ PIN incorreto!\n\n"
                 f"⚠️ Tentativas: {tentativas}/3\n"
                 f"Restam {3 - tentativas} tentativa(s).\n\n"
                 f"Digite o PIN correto ou *menu* para cancelar.")
        return
    
    # PIN correto! Registrar login e resetar tentativas
    cs.touch_login(cpf)
    
    # Buscar dados do cliente
    cliente = cs.get_by_cpf(cpf)
    nome = cliente.get("Nome", "Cliente")
    
    # Salvar dados da sessão
    state_manager.update_data(chat_id, 
                              area_cliente_cpf=cpf,
                              area_cliente_nome=nome,
                              area_cliente_autenticado=True)
    
    # Mostrar menu da área do cliente
    top = "╔════════════════════════╗"
    titulo = f"🔐 Área do Cliente"
    sep = "╠════════════════════════╣"
    
    conteudo = [
        "",
        f"  👤 Olá, {nome.split()[0]}!",
        "",
        "  Escolha uma opção:",
        "",
        "  1️⃣ Histórico de agendamentos",
        "  2️⃣ Meus dados cadastrais",
        "  3️⃣ Alterar PIN",
        ""
    ]
    
    bot = "╚════════════════════════╝"
    
    mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
    mensagem += _nav_footer(["Responda *1*, *2* ou *3*", "Digite *menu* para sair"])
    
    send(chat_id, mensagem)
    state_manager.set_state(chat_id, S_AREA_CLIENTE_MENU)


def _handle_area_cliente_menu(send, chat_id, t):
    """Handler do menu da área do cliente"""
    from services import excel_services as es
    from services import clientes_services as cs
    
    dt = state_manager.get_data(chat_id)
    cpf = dt.get("area_cliente_cpf", "")
    autenticado = dt.get("area_cliente_autenticado", False)
    
    if not cpf or not autenticado:
        send(chat_id, "❌ Sessão expirada. Digite *menu* para fazer login novamente.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    t = (t or "").strip()
    
    if t == "1":
        # Histórico de agendamentos
        historico = es.buscar_historico_completo(cpf)
        
        if not historico:
            send(chat_id,
                 "📋 *Histórico de Agendamentos*\n\n"
                 "Você ainda não possui agendamentos registrados.\n\n"
                 "Digite *menu* para voltar e fazer seu primeiro agendamento!")
            return
        
        # Calcular estatísticas
        total = len(historico)
        confirmados = len([a for a in historico if a.get("Status", "").lower() == "confirmado"])
        cancelados = len([a for a in historico if a.get("Status", "").lower() == "cancelado"])
        
        top = "╔════════════════════════╗"
        titulo = "📋 Histórico Completo"
        sep = "╠════════════════════════╣"
        
        mensagem_parts = [top, titulo, sep, ""]
        mensagem_parts.append(f"  📊 Total: {total} agendamento(s)")
        mensagem_parts.append(f"  ✅ Confirmados: {confirmados}")
        mensagem_parts.append(f"  ❌ Cancelados: {cancelados}")
        mensagem_parts.append("")
        mensagem_parts.append("  📅 Últimos agendamentos:")
        mensagem_parts.append("")
        
        # Mostrar últimos 10 agendamentos
        for idx, ag in enumerate(historico[:10], 1):
            data = ag.get("Data", "")
            hora = ag.get("Hora", "")
            status = ag.get("Status", "")
            
            # Emoji por status
            if status.lower() == "confirmado":
                emoji = "✅"
            elif status.lower() == "cancelado":
                emoji = "❌"
            else:
                emoji = "⏳"
            
            mensagem_parts.append(f"  {emoji} {data} às {hora}")
            mensagem_parts.append(f"     Status: {status}")
            if idx < len(historico[:10]):
                mensagem_parts.append("")
        
        if len(historico) > 10:
            mensagem_parts.append(f"  ... e mais {len(historico) - 10} agendamento(s)")
            mensagem_parts.append("")
        
        bot = "╚════════════════════════╝"
        mensagem_parts.append(bot)
        
        mensagem = "\n".join(mensagem_parts)
        mensagem += _nav_footer(["Digite *menu* para voltar"])
        
        send(chat_id, mensagem)
    
    elif t == "2":
        # Meus dados cadastrais
        cliente = cs.get_by_cpf(cpf)
        
        nome = cliente.get("Nome", "")
        nascimento = cliente.get("Nascimento", "")
        telefone = cliente.get("Telefone", "")
        email = cliente.get("Email", "")
        
        top = "╔════════════════════════╗"
        titulo = "👤 Meus Dados"
        sep = "╠════════════════════════╣"
        
        conteudo = [
            "",
            f"  📛 Nome: {nome}",
            f"  🎂 Nascimento: {nascimento}",
            f"  📱 Telefone: {telefone}",
            f"  📧 Email: {email or 'Não cadastrado'}",
            f"  📋 CPF: {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}",
            ""
        ]
        
        bot = "╚════════════════════════╝"
        
        mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
        mensagem += _nav_footer(["Digite *menu* para voltar"])
        
        send(chat_id, mensagem)
    
    elif t == "3":
        # Alterar PIN
        top = "╔════════════════════════╗"
        titulo = "🔐 Alterar PIN"
        sep = "╠════════════════════════╣"
        
        conteudo = [
            "",
            "  Digite seu novo PIN",
            "  (4 dígitos):",
            "",
            "  ⚠️ Escolha um PIN seguro",
            "  que você possa lembrar!",
            ""
        ]
        
        bot = "╚════════════════════════╝"
        
        mensagem = "\n".join([top, titulo, sep] + conteudo + [bot])
        mensagem += _nav_footer(["Digite *menu* para cancelar"])
        
        send(chat_id, mensagem)
        state_manager.set_state(chat_id, S_AREA_CLIENTE_ALTERAR_PIN_NOVO)
    
    else:
        send(chat_id, "Opção inválida. Digite *1*, *2* ou *3*, ou *menu* para sair.")


def _handle_area_cliente_alterar_pin_novo(send, chat_id, t):
    """Handler para receber novo PIN"""
    import re
    
    dt = state_manager.get_data(chat_id)
    cpf = dt.get("area_cliente_cpf", "")
    autenticado = dt.get("area_cliente_autenticado", False)
    
    if not cpf or not autenticado:
        send(chat_id, "❌ Sessão expirada. Digite *menu* para recomeçar.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    pin = re.sub(r"\D", "", t or "")
    
    if not pin or len(pin) != 4:
        send(chat_id, "❌ PIN deve ter 4 dígitos. Tente novamente ou digite *menu* para cancelar.")
        return
    
    # Validar PIN óbvio
    if pin in ["0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999", "1234"]:
        send(chat_id,
             "⚠️ PIN muito simples!\n\n"
             "Por segurança, escolha um PIN diferente de sequências óbvias.\n"
             "Tente novamente ou digite *menu* para cancelar.")
        return
    
    # Salvar PIN temporário e pedir confirmação
    state_manager.update_data(chat_id, novo_pin_temp=pin)
    
    send(chat_id,
         f"🔐 *Confirme seu novo PIN*\n\n"
         f"Novo PIN: {'*' * len(pin)}\n\n"
         f"Digite novamente para confirmar ou *menu* para cancelar.")
    state_manager.set_state(chat_id, S_AREA_CLIENTE_ALTERAR_PIN_CONF)


def _handle_area_cliente_alterar_pin_conf(send, chat_id, t):
    """Handler para confirmar novo PIN"""
    import re
    from services import clientes_services as cs
    
    dt = state_manager.get_data(chat_id)
    cpf = dt.get("area_cliente_cpf", "")
    autenticado = dt.get("area_cliente_autenticado", False)
    pin_temp = dt.get("novo_pin_temp", "")
    
    if not cpf or not autenticado or not pin_temp:
        send(chat_id, "❌ Sessão expirada. Digite *menu* para recomeçar.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    pin_conf = re.sub(r"\D", "", t or "")
    
    if pin_conf != pin_temp:
        send(chat_id,
             "❌ PINs não conferem!\n\n"
             "Os PINs digitados são diferentes.\n"
             "Digite *menu* para voltar e tentar novamente.")
        state_manager.set_state(chat_id, S_MENU)
        return
    
    # Atualizar PIN
    sucesso = cs.set_pin_for_cpf(cpf, pin_conf)
    
    if sucesso:
        send(chat_id,
             "✅ *PIN alterado com sucesso!*\n\n"
             "Seu PIN foi atualizado.\n"
             "Use-o na próxima vez que acessar a área do cliente.\n\n"
             "Digite *menu* para voltar ao menu principal.")
    else:
        send(chat_id,
             "❌ Erro ao alterar PIN.\n\n"
             "Tente novamente mais tarde.\n"
             "Digite *menu* para voltar.")
    
    # Limpar dados temporários
    state_manager.update_data(chat_id, 
                              novo_pin_temp="",
                              area_cliente_autenticado=False)
    state_manager.set_state(chat_id, S_MENU)


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
