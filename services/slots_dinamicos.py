# services/slots_dinamicos.py
"""
Sistema de Slots Dinâmicos Inteligentes

Gera slots de agendamento baseado em:
1. Duração do serviço escolhido
2. Agendamentos já existentes
3. Serviços fracionados em andamento (com pausas aproveitáveis)
4. Horários de funcionamento da barbearia

Permite máximo aproveitamento da agenda.
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# =========================================================
# Configuração
# =========================================================
GRANULARIDADE_MINUTOS = 10  # Slots de 10 em 10 minutos
MIN_DURACAO_SERVICO = 10    # Serviço mínimo: 10min

# =========================================================
# Funções Auxiliares
# =========================================================

def _parse_time(time_str: str) -> datetime:
    """Converte HH:MM para datetime de hoje."""
    hora, minuto = map(int, time_str.split(':'))
    hoje = datetime.now().replace(hour=hora, minute=minuto, second=0, microsecond=0)
    return hoje


def _time_to_str(dt: datetime) -> str:
    """Converte datetime para HH:MM."""
    return dt.strftime("%H:%M")


def _carregar_servicos() -> Dict:
    """Carrega configuração de serviços."""
    try:
        servicos_path = os.path.join(os.path.dirname(__file__), "..", "config", "servicos.json")
        with open(servicos_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"servicos": []}


def _obter_duracao_servico(servico_id: str) -> int:
    """Retorna duração do serviço em minutos."""
    config = _carregar_servicos()
    for servico in config.get("servicos", []):
        if servico.get("id") == servico_id:
            return servico.get("duracao_minutos", 40)
    return 40  # Default


def _servico_eh_fracionado(servico_id: str) -> bool:
    """Verifica se serviço tem etapas fracionadas."""
    config = _carregar_servicos()
    for servico in config.get("servicos", []):
        if servico.get("id") == servico_id:
            return servico.get("fracionado", False)
    return False


def _obter_etapas_servico(servico_id: str) -> List[Dict]:
    """Retorna etapas de um serviço fracionado."""
    config = _carregar_servicos()
    for servico in config.get("servicos", []):
        if servico.get("id") == servico_id:
            return servico.get("etapas", [])
    return []


# =========================================================
# Geração de Slots Base
# =========================================================

def gerar_slots_base_dia(
    data_str: str,
    inicio: str = "08:00",
    fim: str = "18:00",
    granularidade: int = GRANULARIDADE_MINUTOS
) -> List[str]:
    """
    Gera lista de slots base para um dia (grade de horários).
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        inicio: Horário de início (HH:MM)
        fim: Horário de término (HH:MM)
        granularidade: Intervalo entre slots em minutos
    
    Returns:
        Lista de horários no formato HH:MM
    """
    slots = []
    
    try:
        inicio_dt = _parse_time(inicio)
        fim_dt = _parse_time(fim)
        
        current = inicio_dt
        while current <= fim_dt:
            slots.append(_time_to_str(current))
            current += timedelta(minutes=granularidade)
    except Exception:
        pass
    
    return slots


# =========================================================
# Análise de Ocupação
# =========================================================

def calcular_intervalos_ocupados(
    data_str: str,
    agendamentos: List[Dict]
) -> List[Tuple[datetime, datetime, str]]:
    """
    Calcula todos os intervalos de tempo ocupados no dia.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        agendamentos: Lista de agendamentos do dia
    
    Returns:
        Lista de tuplas (inicio, fim, tipo) onde tipo = 'ocupado' ou 'pausa'
    """
    intervalos = []
    
    for ag in agendamentos:
        # Pular agendamentos cancelados/expirados
        status = ag.get("Status", "").lower()
        if status in ["cancelado", "expirado"]:
            continue
        
        hora_str = ag.get("Hora", "")
        servico_id = ag.get("ServicoID", "")
        duracao = ag.get("ServicoDuracao", 0)
        
        if not hora_str:
            continue
        
        try:
            inicio = _parse_time(hora_str)
            
            # Se não tem duração salva, calcular do serviço
            if not duracao:
                duracao = _obter_duracao_servico(servico_id or "cabelo_sobrancelha")
            
            # Se é fracionado, calcular intervalos detalhados
            if _servico_eh_fracionado(servico_id):
                etapas = _obter_etapas_servico(servico_id)
                current_time = inicio
                
                for etapa in etapas:
                    etapa_duracao = etapa.get("duracao_minutos", 0)
                    fim_etapa = current_time + timedelta(minutes=etapa_duracao)
                    
                    # Se etapa permite outro atendimento = pausa aproveitável
                    if etapa.get("permite_outro_atendimento", False):
                        intervalos.append((current_time, fim_etapa, "pausa"))
                    else:
                        intervalos.append((current_time, fim_etapa, "ocupado"))
                    
                    current_time = fim_etapa
            else:
                # Serviço simples: bloqueia do início até o fim
                fim = inicio + timedelta(minutes=duracao)
                intervalos.append((inicio, fim, "ocupado"))
        
        except Exception:
            continue
    
    return intervalos


def slot_esta_livre(
    slot_inicio: datetime,
    duracao_necessaria: int,
    intervalos_ocupados: List[Tuple[datetime, datetime, str]]
) -> bool:
    """
    Verifica se um slot específico está completamente livre.
    
    Args:
        slot_inicio: Horário de início do slot
        duracao_necessaria: Duração do serviço em minutos
        intervalos_ocupados: Lista de intervalos ocupados
    
    Returns:
        True se o serviço completo cabe sem conflitos
    """
    slot_fim = slot_inicio + timedelta(minutes=duracao_necessaria)
    
    for ocupado_inicio, ocupado_fim, tipo in intervalos_ocupados:
        # Ignorar pausas (são aproveitáveis)
        if tipo == "pausa":
            continue
        
        # Verificar sobreposição
        if (slot_inicio < ocupado_fim and slot_fim > ocupado_inicio):
            return False
    
    return True


# =========================================================
# API Principal
# =========================================================

def gerar_slots_disponiveis_para_servico(
    data_str: str,
    servico_id: str,
    agendamentos_existentes: List[Dict],
    inicio: str = "08:00",
    fim: str = "18:00"
) -> List[Dict]:
    """
    Gera lista de slots disponíveis para um serviço específico.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        servico_id: ID do serviço (cabelo_sobrancelha, barba, etc)
        agendamentos_existentes: Lista de agendamentos já feitos
        inicio: Horário de início da agenda
        fim: Horário de término da agenda
    
    Returns:
        Lista de dicts: [{"hora": "08:00", "disponivel": True, "motivo": ""}]
    """
    # Obter duração do serviço
    duracao = _obter_duracao_servico(servico_id)
    
    # Gerar slots base
    slots_base = gerar_slots_base_dia(data_str, inicio, fim, GRANULARIDADE_MINUTOS)
    
    # Calcular intervalos ocupados
    intervalos_ocupados = calcular_intervalos_ocupados(data_str, agendamentos_existentes)
    
    # Verificar cada slot
    slots_disponiveis = []
    
    for hora_str in slots_base:
        try:
            slot_dt = _parse_time(hora_str)
            disponivel = slot_esta_livre(slot_dt, duracao, intervalos_ocupados)
            
            slots_disponiveis.append({
                "hora": hora_str,
                "disponivel": disponivel,
                "motivo": "" if disponivel else "Horário ocupado"
            })
        except Exception:
            continue
    
    return slots_disponiveis


def obter_proximo_slot_disponivel(
    data_str: str,
    servico_id: str,
    agendamentos_existentes: List[Dict],
    apos_horario: str = "08:00"
) -> Optional[str]:
    """
    Retorna o próximo horário disponível após um determinado horário.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        servico_id: ID do serviço
        agendamentos_existentes: Lista de agendamentos
        apos_horario: Buscar após este horário (HH:MM)
    
    Returns:
        Próximo horário disponível ou None
    """
    slots = gerar_slots_disponiveis_para_servico(
        data_str, 
        servico_id, 
        agendamentos_existentes
    )
    
    try:
        apos_dt = _parse_time(apos_horario)
        
        for slot in slots:
            if slot["disponivel"]:
                slot_dt = _parse_time(slot["hora"])
                if slot_dt >= apos_dt:
                    return slot["hora"]
    except Exception:
        pass
    
    return None


def calcular_total_slots_disponiveis(
    data_str: str,
    servico_id: str,
    agendamentos_existentes: List[Dict]
) -> int:
    """
    Conta quantos slots estão disponíveis para um serviço.
    
    Returns:
        Número de slots disponíveis
    """
    slots = gerar_slots_disponiveis_para_servico(
        data_str,
        servico_id,
        agendamentos_existentes
    )
    
    return sum(1 for slot in slots if slot["disponivel"])
