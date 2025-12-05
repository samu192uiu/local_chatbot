# services/excel_services.py
import os
from datetime import datetime
from typing import Iterable, Dict, List, Optional, Tuple, Any
from openpyxl import Workbook, load_workbook

# =========================================================
# Config
# =========================================================
FILE_PATH = os.getenv("AGENDAMENTOS_XLSX", "/app/data/agendamentos.xlsx")
SHEET_AG = os.getenv("AG_SHEET_NAME", "Agendamentos")
SHEET_CLIENTES = os.getenv("CLIENTES_SHEET_NAME", "Clientes")  # opcional (para _read_rows_clientes)

HEADERS_AG = [
    "Chave",         # chave única do lançamento
    "Data",          # DD/MM/AAAA
    "Hora",          # HH:MM
    "ChatId",        # jid/whatsapp do cliente
    "ClienteID",     # << NOVO: ID único vindo do clientes_services
    "ClienteNome",
    "Nascimento",
    "CPF",
    "Status",        # Pendente Pagamento | Confirmado | Remarcado | Cancelado | etc.
    "ValorPago",
    "CriadoEm",      # timestamp
]

# estados que bloqueiam o mesmo slot (Data+Hora)
BLOCKING_STATUSES = set([
    "Pendente Pagamento",
    "Confirmado",
    "Reagendado",
    "Remarcado",
])

# =========================================================
# Helpers de planilha
# =========================================================
def _ensure_file_and_sheet():
    """Cria arquivo/sheet se não existirem; garante cabeçalho da aba de Agendamentos."""
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    if not os.path.exists(FILE_PATH):
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_AG
        for idx, h in enumerate(HEADERS_AG, 1):
            ws.cell(row=1, column=idx, value=h)
        wb.save(FILE_PATH)
        return

    wb = load_workbook(FILE_PATH)
    if SHEET_AG not in wb.sheetnames:
        ws = wb.create_sheet(SHEET_AG)
        for idx, h in enumerate(HEADERS_AG, 1):
            ws.cell(row=1, column=idx, value=h)
        wb.save(FILE_PATH)
        return

    # garantir cabeçalhos na aba
    ws = wb[SHEET_AG]
    _ensure_headers(ws, HEADERS_AG)
    wb.save(FILE_PATH)

def _open_ws():
    _ensure_file_and_sheet()
    wb = load_workbook(FILE_PATH)
    ws = wb[SHEET_AG]
    return wb, ws

def _get_header_map(ws) -> dict:
    """nome_coluna -> índice (1-based)"""
    m = {}
    for c in range(1, ws.max_column + 1):
        name = str(ws.cell(row=1, column=c).value or "").strip()
        if name:
            m[name] = c
    return m

def _ensure_headers(ws, headers: List[str]):
    """Garante que todas as colunas de headers existam; se faltarem, adiciona ao final."""
    header_map = _get_header_map(ws)
    changed = False
    for h in headers:
        if h not in header_map:
            new_col = ws.max_column + 1 if ws.max_column >= 1 else 1
            ws.cell(row=1, column=new_col, value=h)
            header_map[h] = new_col
            changed = True
    return changed

def _row_to_dict(ws, row_idx: int) -> dict:
    hm = _get_header_map(ws)
    out = {}
    for h in HEADERS_AG:
        col = hm.get(h)
        out[h] = ws.cell(row=row_idx, column=col).value if col else None
    return out

def _make_row(
    ws,
    chave: str,
    data_str: str,
    hora_str: str,
    chat_id: str,
    cliente_id: Optional[str],
    cliente_nome: Optional[str],
    nasc: Optional[str],
    cpf: Optional[str],
    status: str,
    valor_pago: Optional[Any]
):
    hm = _get_header_map(ws)
    r = ws.max_row + 1
    def setv(colname, val):
        col = hm.get(colname)
        if col:
            ws.cell(row=r, column=col, value=val)

    setv("Chave", chave)
    setv("Data", data_str)
    setv("Hora", hora_str)
    setv("ChatId", chat_id)
    setv("ClienteID", cliente_id or "")
    setv("ClienteNome", cliente_nome or "")
    setv("Nascimento", nasc or "")
    setv("CPF", cpf or "")
    setv("Status", status or "")
    setv("ValorPago", valor_pago)
    setv("CriadoEm", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return r

# =========================================================
# API pública usada pelo fluxo
# =========================================================
def make_key(data_str: str, hora_str: str, chat_id: str) -> str:
    """Gera uma chave canônica a partir do trio (data, hora, chat)."""
    return f"{data_str}|{hora_str}|{chat_id}"

def verificar_disponibilidade(data_str: str, hora_str: str) -> bool:
    """
    Um slot (Data+Hora) é considerado indisponível se já houver
    um lançamento nessa Data+Hora com Status bloqueante.
    """
    _, ws = _open_ws()
    hm = _get_header_map(ws)
    c_data = hm.get("Data")
    c_hora = hm.get("Hora")
    c_status = hm.get("Status")

    for r in range(2, ws.max_row + 1):
        d = str(ws.cell(row=r, column=c_data).value or "").strip()
        h = str(ws.cell(row=r, column=c_hora).value or "").strip()
        if d == data_str and h == hora_str:
            st = str(ws.cell(row=r, column=c_status).value or "").strip()
            if st in BLOCKING_STATUSES:
                return False
    return True

def adicionar_agendamento(
    data_str: str,
    hora_str: str,
    chat_id: str,
    status: str = "Pendente Pagamento",
    cliente_nome: Optional[str] = None,
    data_nasc: Optional[str] = None,
    cpf: Optional[str] = None,
    valor_pago: Optional[Any] = None,
    cliente_id: Optional[str] = None,   # << NOVO: aceita ClienteID vindo do clientes_services
) -> str:
    """
    Cria linha na planilha de agendamentos e retorna a 'Chave'.
    Se já houver bloqueio no slot, levanta ValueError.
    """
    if not verificar_disponibilidade(data_str, hora_str):
        raise ValueError("Horário indisponível")

    wb, ws = _open_ws()
    _ensure_headers(ws, HEADERS_AG)
    chave = make_key(data_str, hora_str, chat_id)

    _make_row(
        ws=ws,
        chave=chave,
        data_str=data_str,
        hora_str=hora_str,
        chat_id=chat_id,
        cliente_id=cliente_id,
        cliente_nome=cliente_nome,
        nasc=data_nasc,
        cpf=cpf,
        status=status,
        valor_pago=valor_pago,
    )
    wb.save(FILE_PATH)
    return chave

def _find_row_by_key(ws, chave: str) -> Optional[int]:
    hm = _get_header_map(ws)
    c_key = hm.get("Chave")
    if not c_key:
        return None
    chave = str(chave or "").strip()
    for r in range(2, ws.max_row + 1):
        v = str(ws.cell(row=r, column=c_key).value or "").strip()
        if v == chave:
            return r
    return None

def _find_row_by_triplet(ws, data_str: str, hora_str: str, chat_id: str) -> Optional[int]:
    hm = _get_header_map(ws)
    c_data = hm.get("Data"); c_hora = hm.get("Hora"); c_chat = hm.get("ChatId")
    if not (c_data and c_hora and c_chat):
        return None
    ds = str(data_str or "").strip()
    hs = str(hora_str or "").strip()
    jid = str(chat_id or "").strip()
    for r in range(2, ws.max_row + 1):
        d = str(ws.cell(row=r, column=c_data).value or "").strip()
        h = str(ws.cell(row=r, column=c_hora).value or "").strip()
        j = str(ws.cell(row=r, column=c_chat).value or "").strip()
        if d == ds and h == hs and j == jid:
            return r
    return None

def atualizar_status_por_chave(*args) -> bool:
    """
    Modo 1 (recomendado): atualizar_status_por_chave(chave, novo_status)
    Modo 2 (compat):      atualizar_status_por_chave(data, hora, chat_id, novo_status)
    """
    wb, ws = _open_ws()
    _ensure_headers(ws, HEADERS_AG)
    hm = _get_header_map(ws)
    c_status = hm.get("Status")

    row = None
    new_status = None

    if len(args) == 2:
        chave, new_status = args
        row = _find_row_by_key(ws, chave)
    elif len(args) == 4:
        data_str, hora_str, chat_id, new_status = args
        row = _find_row_by_triplet(ws, data_str, hora_str, chat_id)
    else:
        raise TypeError("Uso: atualizar_status_por_chave(chave, status) OU atualizar_status_por_chave(data,hora,chat_id,status)")

    if row is None:
        return False

    ws.cell(row=row, column=c_status, value=str(new_status or "").strip())
    wb.save(FILE_PATH)
    return True

def atualizar_status(chave: str, new_status: str) -> bool:
    """Fallback simples por chave."""
    try:
        return atualizar_status_por_chave(chave, new_status)
    except Exception:
        return False

# =========================================================
# Leitura (para painéis/relatórios)
# =========================================================
def _read_rows(sheet: str = SHEET_AG) -> Iterable[Dict[str, Any]]:
    """
    Itera linhas como dicionário (apenas colunas conhecidas do respectivo sheet).
    Para Agendamentos, usa HEADERS_AG; para outros, devolve todas as colunas encontradas.
    """
    _ensure_file_and_sheet()
    wb = load_workbook(FILE_PATH)
    if sheet not in wb.sheetnames:
        return []
    ws = wb[sheet]
    header_map = {}
    headers = []

    # detecta cabeçalho
    for c in range(1, ws.max_column + 1):
        name = str(ws.cell(row=1, column=c).value or "").strip()
        if name:
            header_map[name] = c
            headers.append(name)

    def row_to_dict_row(r: int) -> Dict[str, Any]:
        d = {}
        for h in headers:
            col = header_map[h]
            d[h] = ws.cell(row=r, column=col).value
        return d

    out = []
    for r in range(2, ws.max_row + 1):
        # ignora linhas totalmente vazias
        empty = True
        for c in range(1, ws.max_column + 1):
            if ws.cell(row=r, column=c).value not in (None, ""):
                empty = False
                break
        if empty:
            continue
        out.append(row_to_dict_row(r))
    return out

def _read_rows_clientes() -> Iterable[Dict[str, Any]]:
    """
    Opcional: se você mantiver a aba 'Clientes' dentro deste MESMO arquivo,
    esta função ajuda o painel admin a listar vínculos.
    Cabeçalhos esperados: ['CPF','Nome','Nascimento','Telefone','Email','ChatId','PinHash','UltimoLogin','ClienteID']
    """
    _ensure_file_and_sheet()
    wb = load_workbook(FILE_PATH)
    if SHEET_CLIENTES not in wb.sheetnames:
        return []  # se você guarda clientes em outro arquivo (clientes.xlsx), tudo bem
    ws = wb[SHEET_CLIENTES]

    # coleta cabeçalhos dinamicamente
    header_map = {}
    headers = []
    for c in range(1, ws.max_column + 1):
        name = str(ws.cell(row=1, column=c).value or "").strip()
        if name:
            header_map[name] = c
            headers.append(name)

    out = []
    for r in range(2, ws.max_row + 1):
        d = {}
        for h in headers:
            col = header_map[h]
            d[h] = ws.cell(row=r, column=col).value
        out.append(d)
    return out
