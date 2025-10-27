# excel_service.py
import openpyxl
from openpyxl.utils import get_column_letter
import logging
from datetime import datetime

from services import excel_service # Importa o arquivo excel_service.py de DENTRO da pasta services
import os

# Nome do arquivo Excel. Ele será acessado como /app/agendamentos.xlsx dentro do container.
EXCEL_FILE_PATH = '/app/services/agendamentos.xlsx'
# Se rodar localmente fora do Docker, ajuste o caminho ou use:
# EXCEL_FILE_PATH = os.path.join(os.path.dirname(__file__), 'agendamentos.xlsx')

logger = logging.getLogger(__name__) # Usa o logger configurado no app.py

def _carregar_ou_criar_planilha():
    """Carrega a planilha ou cria uma nova com cabeçalhos se não existir."""
    try:
        workbook = openpyxl.load_workbook(EXCEL_FILE_PATH)
        logger.info(f"Planilha '{EXCEL_FILE_PATH}' carregada.")
        # Garante que a planilha 'Agendamentos' exista
        if 'Agendamentos' not in workbook.sheetnames:
            sheet = workbook.create_sheet('Agendamentos')
            headers = ["Data", "Hora", "ClienteID", "Status", "ValorPago", "TimestampRegistro"]
            sheet.append(headers)
            logger.info("Aba 'Agendamentos' criada com cabeçalhos.")
            workbook.save(EXCEL_FILE_PATH)
        else:
            sheet = workbook['Agendamentos']
            # Verifica se os cabeçalhos existem, caso contrário adiciona
            if sheet.max_row == 0 or sheet['A1'].value != "Data":
                headers = ["Data", "Hora", "ClienteID", "Status", "ValorPago", "TimestampRegistro"]
                sheet.append(headers)
                logger.info("Cabeçalhos adicionados à aba 'Agendamentos'.")
                workbook.save(EXCEL_FILE_PATH)

        return workbook, sheet
    except FileNotFoundError:
        logger.warning(f"Arquivo '{EXCEL_FILE_PATH}' não encontrado. Criando um novo.")
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = 'Agendamentos'
        headers = ["Data", "Hora", "ClienteID", "Status", "ValorPago", "TimestampRegistro"]
        sheet.append(headers)
        workbook.save(EXCEL_FILE_PATH)
        logger.info(f"Arquivo '{EXCEL_FILE_PATH}' criado com cabeçalhos.")
        return workbook, sheet
    except Exception as e:
        logger.error(f"Erro ao carregar ou criar a planilha: {e}", exc_info=True)
        return None, None

def verificar_disponibilidade(data_str, hora_str):
    """
    Verifica se a data e hora estão disponíveis na planilha.
    Retorna True se disponível, False se ocupado.
    """
    workbook, sheet = _carregar_ou_criar_planilha()
    if not sheet:
        return False # Indica erro ao carregar planilha

    # Assumindo que Data está na coluna A (1) e Hora na coluna B (2) e Status na D (4)
    # Status considerados como ocupado: "Confirmado" ou "Pendente Pagamento"
    status_ocupado = ["Confirmado", "Pendente Pagamento"]

    try:
        for row in range(2, sheet.max_row + 1): # Começa da linha 2 (abaixo dos cabeçalhos)
            data_planilha = sheet.cell(row=row, column=1).value
            hora_planilha = sheet.cell(row=row, column=2).value
            status_planilha = sheet.cell(row=row, column=4).value

            # Simplificando a comparação - pode precisar de tratamento de formato mais robusto
            # Converte para string para comparar, se não forem string
            data_planilha_str = str(data_planilha) if data_planilha else ""
            hora_planilha_str = str(hora_planilha) if hora_planilha else ""


            # Verifica se data e hora coincidem e se o status indica ocupado
            if data_planilha_str == data_str and hora_planilha_str == hora_str and status_planilha in status_ocupado:
                logger.info(f"Horário {data_str} {hora_str} encontrado como OCUPADO (Status: {status_planilha}).")
                return False # Horário ocupado

        logger.info(f"Horário {data_str} {hora_str} verificado como DISPONÍVEL.")
        return True # Horário disponível
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade na planilha: {e}", exc_info=True)
        return False # Assume indisponível em caso de erro

def adicionar_agendamento(data_str, hora_str, cliente_id, status="Pendente Pagamento", valor_pago=None):
    """
    Adiciona um novo agendamento na próxima linha vazia da planilha.
    Retorna True se adicionado com sucesso, False caso contrário.
    """
    workbook, sheet = _carregar_ou_criar_planilha()
    if not sheet:
        return False

    try:
        timestamp_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nova_linha = [data_str, hora_str, cliente_id, status, valor_pago, timestamp_registro]
        sheet.append(nova_linha)
        workbook.save(EXCEL_FILE_PATH)
        logger.info(f"Agendamento adicionado: {nova_linha}")
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar agendamento na planilha: {e}", exc_info=True)
        return False

# --- Funções futuras (placeholders) ---
def atualizar_status(identificador, novo_status):
    logger.warning("Função atualizar_status ainda não implementada.")
    return False

def listar_agendamentos(data_filtro):
    logger.warning("Função listar_agendamentos ainda não implementada.")
    return "Função de listagem em construção."