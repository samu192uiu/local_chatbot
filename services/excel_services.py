# services/excel_services.py
from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

# Caminho absoluto da planilha dentro do container (e refletido no host)
BASE_DIR = os.path.dirname(__file__)
PLAN_PATH = os.path.join(BASE_DIR, "agendamentos.xlsx")
SHEET_NAME = "Agendamentos"

COLS = [
    "Data", "Hora", "ClienteNome", "DataNascimento", "CPF",
    "ChatID", "Status", "ValorPago", "CriadoEm", "Chave"
]

def _ensure_wb():
    """Garante que a planilha exista com as colunas corretas."""
    if not os.path.exists(PLAN_PATH):
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(COLS)
        wb.save(PLAN_PATH)

def _load_ws():
    _ensure_wb()
    wb = load_workbook(PLAN_PATH)
    if SHEET_NAME not in wb.sheetnames:
        ws = wb.create_sheet(SHEET_NAME)
        ws.append(COLS)
        wb.save(PLAN_PATH)
    return wb, wb[SHEET_NAME]

def _row_to_dict(row) -> Dict[str, Any]:
    return {COLS[i]: (row[i].value if i < len(row) else None) for i in range(len(COLS))}

def _find_row_index_by_key(ws, chave: str) -> Optional[int]:
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row and len(row) >= len(COLS) and row[COLS.index("Chave")] == chave:
            return idx
    return None

def make_key(data_str: str, hora_str: str, chat_id: str) -> str:
    return f"{data_str}_{hora_str}_{chat_id}"

# ----------------- API pública usada no fluxo -----------------

def listar_horarios_disponiveis(data_str: str,
                                inicio: str = "08:00",
                                fim: str = "18:00",
                                passo_min: int = 30) -> List[str]:
    """
    Gera horários de 'inicio' a 'fim' pulando 'passo_min', e remove os já ocupados na data.
    """
    wb, ws = _load_ws()
    ocupados = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] == data_str:  # Data
            ocupados.add(row[1])        # Hora

    def _to_dt(hhmm: str) -> datetime:
        return datetime.strptime(hhmm, "%H:%M")

    t = _to_dt(inicio)
    end = _to_dt(fim)
    slots = []
    while t <= end:
        hhmm = t.strftime("%H:%M")
        if hhmm not in ocupados:
            slots.append(hhmm)
        t += timedelta(minutes=passo_min)
    return slots

def verificar_disponibilidade(data_str: str, hora_str: str) -> bool:
    wb, ws = _load_ws()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        if row[0] == data_str and row[1] == hora_str:  # Data, Hora
            return False
    return True

def adicionar_agendamento(data_str: str,
                        hora_str: str,
                        chat_id: str,
                        status: str = "Pendente Pagamento",
                        cliente_nome: Optional[str] = None,
                        data_nasc: Optional[str] = None,
                        cpf: Optional[str] = None,
                        valor_pago: Optional[float] = None) -> str:
    """
    Adiciona uma linha de agendamento e retorna a 'chave' (Data_Hora_ChatID).
    """
    wb, ws = _load_ws()
    chave = make_key(data_str, hora_str, chat_id)
    criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ws.append([
        data_str, hora_str, cliente_nome, data_nasc, cpf,
        chat_id, status, valor_pago, criado_em, chave
    ])
    wb.save(PLAN_PATH)
    return chave

def atualizar_status_por_chave(chave: str, novo_status: str, valor_pago: Optional[float] = None) -> bool:
    """
    Atualiza o 'Status' (e opcionalmente 'ValorPago') da linha com a 'chave' informada.
    Retorna True se atualizou; False se não encontrou.
    """
    wb, ws = _load_ws()
    row_idx = _find_row_index_by_key(ws, chave)
    if not row_idx:
        return False

    status_col = COLS.index("Status") + 1
    ws.cell(row=row_idx, column=status_col).value = novo_status

    if valor_pago is not None:
        pago_col = COLS.index("ValorPago") + 1
        ws.cell(row=row_idx, column=pago_col).value = float(valor_pago)

    wb.save(PLAN_PATH)
    return True

# ----------------- Helpers de debug -----------------

def _read_rows() -> List[Dict[str, Any]]:
    wb, ws = _load_ws()
    out = []
    for row in ws.iter_rows(min_row=2):
        out.append(_row_to_dict(row))
    return out
