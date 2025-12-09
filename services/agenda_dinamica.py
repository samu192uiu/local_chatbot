# services/agenda_dinamica.py
"""
Sistema de Agenda Dinâmica para Barbeiro.

Permite configuração flexível de horários através de 3 níveis:
1. Padrão Semanal (horario_funcionamento) - raramente muda
2. Exceções Mensais (bloqueios_pontuais, slots_personalizados) - onde está o poder
3. Slots Auto-gerados - combinação dos níveis anteriores

Substitui DEFAULT_SLOTS hardcoded por geração dinâmica baseada em JSON.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# =========================================================
# Configuração
# =========================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "agenda_config.json")

# Cache em memória (evita ler JSON toda vez)
_config_cache: Optional[Dict] = None
_cache_timestamp: Optional[datetime] = None
CACHE_DURATION_SECONDS = 60  # Recarregar config a cada 1 minuto

# =========================================================
# Carregamento de Configuração
# =========================================================

def carregar_config(force_reload: bool = False) -> Dict:
    """
    Carrega configuração da agenda do arquivo JSON.
    Usa cache em memória por 60 segundos para performance.
    
    Args:
        force_reload: Se True, ignora cache e recarrega do arquivo
    
    Returns:
        Dict com configuração completa da agenda
    """
    global _config_cache, _cache_timestamp
    
    # Verifica se pode usar cache
    agora = datetime.now()
    if not force_reload and _config_cache and _cache_timestamp:
        if (agora - _cache_timestamp).total_seconds() < CACHE_DURATION_SECONDS:
            return _config_cache
    
    # Carrega do arquivo
    if not os.path.exists(CONFIG_PATH):
        # Retorna configuração padrão se arquivo não existir
        return _get_default_config()
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Atualiza cache
        _config_cache = config
        _cache_timestamp = agora
        
        return config
    except Exception as e:
        print(f"Erro ao carregar agenda_config.json: {e}")
        return _get_default_config()


def _get_default_config() -> Dict:
    """Retorna configuração padrão caso arquivo não exista."""
    return {
        "horario_funcionamento": {
            "segunda": {"ativo": True, "inicio": "08:00", "fim": "18:00", "intervalos": [{"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}]},
            "terca": {"ativo": True, "inicio": "08:00", "fim": "18:00", "intervalos": [{"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}]},
            "quarta": {"ativo": True, "inicio": "08:00", "fim": "18:00", "intervalos": [{"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}]},
            "quinta": {"ativo": True, "inicio": "08:00", "fim": "18:00", "intervalos": [{"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}]},
            "sexta": {"ativo": True, "inicio": "08:00", "fim": "18:00", "intervalos": [{"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}]},
            "sabado": {"ativo": True, "inicio": "08:00", "fim": "14:00", "intervalos": []},
            "domingo": {"ativo": False, "inicio": "08:00", "fim": "18:00", "intervalos": []},
        },
        "configuracoes_gerais": {
            "duracao_slot_minutos": 60,
            "buffer_entre_atendimentos": 0,
            "permitir_agendamento_mesmo_dia": True,
            "horario_limite_mesmo_dia": "18:00",
            "dias_antecedencia_maximo": 30,
        },
        "bloqueios_pontuais": [],
        "slots_personalizados": {},
    }


def salvar_config(config: Dict) -> bool:
    """
    Salva configuração no arquivo JSON e invalida cache.
    
    Args:
        config: Dicionário com configuração completa
    
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    global _config_cache, _cache_timestamp
    
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # Invalida cache
        _config_cache = None
        _cache_timestamp = None
        
        return True
    except Exception as e:
        print(f"Erro ao salvar agenda_config.json: {e}")
        return False


# =========================================================
# Geração de Slots
# =========================================================

def gerar_slots_dia(data_str: str, incluir_ocupados: bool = False) -> List[str]:
    """
    Gera lista de horários disponíveis para uma data específica.
    
    Lógica:
    1. Verifica se dia está bloqueado pontualmente
    2. Checa se tem slots personalizados para o dia
    3. Caso contrário, usa horário padrão do dia da semana
    4. Aplica intervalos (almoço, pausas)
    5. Opcionalmente verifica disponibilidade no Excel
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        incluir_ocupados: Se False, filtra horários já agendados
    
    Returns:
        Lista de horários no formato HH:MM (ex: ["08:00", "09:00", ...])
    """
    config = carregar_config()
    
    # 1. Verificar bloqueio pontual
    if eh_dia_bloqueado(data_str, config):
        return []
    
    # 2. Verificar se tem slots personalizados para este dia
    slots_personalizados = config.get("slots_personalizados", {})
    if data_str in slots_personalizados:
        return slots_personalizados[data_str]
    
    # 3. Usar horário padrão do dia da semana
    try:
        data_obj = datetime.strptime(data_str, "%d/%m/%Y")
        dia_semana = _get_nome_dia_semana(data_obj.weekday())
    except Exception:
        return []
    
    horario_funcionamento = config.get("horario_funcionamento", {})
    horario_dia = horario_funcionamento.get(dia_semana, {})
    
    # Se dia não está ativo, retorna vazio
    if not horario_dia.get("ativo", False):
        return []
    
    # 4. Gerar slots baseado em início, fim e duração
    inicio_str = horario_dia.get("inicio", "08:00")
    fim_str = horario_dia.get("fim", "18:00")
    intervalos = horario_dia.get("intervalos", [])
    
    cfg_gerais = config.get("configuracoes_gerais", {})
    duracao_slot = cfg_gerais.get("duracao_slot_minutos", 60)
    
    slots = _gerar_slots_entre_horarios(inicio_str, fim_str, duracao_slot, intervalos)
    
    # 5. Filtrar ocupados (se solicitado)
    if not incluir_ocupados:
        slots = _filtrar_slots_disponiveis(data_str, slots)
    
    return slots


def _get_nome_dia_semana(weekday: int) -> str:
    """Converte número do dia da semana para nome."""
    dias = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    return dias[weekday]


def _gerar_slots_entre_horarios(
    inicio: str,
    fim: str,
    duracao_minutos: int,
    intervalos: List[Dict]
) -> List[str]:
    """
    Gera lista de horários entre início e fim, excluindo intervalos.
    
    Args:
        inicio: Horário inicial (HH:MM)
        fim: Horário final (HH:MM)
        duracao_minutos: Duração de cada slot em minutos
        intervalos: Lista de intervalos a excluir (ex: almoço)
    
    Returns:
        Lista de horários (HH:MM)
    """
    try:
        hora_inicio = datetime.strptime(inicio, "%H:%M")
        hora_fim = datetime.strptime(fim, "%H:%M")
    except Exception:
        return []
    
    slots = []
    hora_atual = hora_inicio
    
    while hora_atual < hora_fim:
        hora_str = hora_atual.strftime("%H:%M")
        
        # Verificar se horário está dentro de algum intervalo
        if not _horario_em_intervalo(hora_str, intervalos):
            slots.append(hora_str)
        
        hora_atual += timedelta(minutes=duracao_minutos)
    
    return slots


def _horario_em_intervalo(horario: str, intervalos: List[Dict]) -> bool:
    """
    Verifica se horário está dentro de algum intervalo (ex: almoço).
    
    Args:
        horario: Horário a verificar (HH:MM)
        intervalos: Lista de dicts com 'inicio' e 'fim'
    
    Returns:
        True se horário está em algum intervalo, False caso contrário
    """
    try:
        hora_obj = datetime.strptime(horario, "%H:%M")
    except Exception:
        return False
    
    for intervalo in intervalos:
        try:
            intervalo_inicio = datetime.strptime(intervalo["inicio"], "%H:%M")
            intervalo_fim = datetime.strptime(intervalo["fim"], "%H:%M")
            
            if intervalo_inicio <= hora_obj < intervalo_fim:
                return True
        except Exception:
            continue
    
    return False


def _filtrar_slots_disponiveis(data_str: str, slots: List[str]) -> List[str]:
    """
    Filtra slots removendo horários já ocupados no Excel.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        slots: Lista de horários candidatos
    
    Returns:
        Lista de horários disponíveis
    """
    try:
        from services import excel_services as exc
    except ImportError:
        return slots  # Se não conseguir importar, retorna todos
    
    disponiveis = []
    for slot in slots:
        # Usa verificar_disponibilidade que já considera serviços fracionados
        if exc.verificar_disponibilidade(data_str, slot):
            disponiveis.append(slot)
    
    return disponiveis


# =========================================================
# Verificações
# =========================================================

def eh_dia_bloqueado(data_str: str, config: Optional[Dict] = None) -> bool:
    """
    Verifica se um dia específico está bloqueado.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        config: Configuração (opcional, carrega se não fornecido)
    
    Returns:
        True se dia está bloqueado, False caso contrário
    """
    if config is None:
        config = carregar_config()
    
    bloqueios = config.get("bloqueios_pontuais", [])
    
    # Bloqueio pode ser string (data) ou dict com data e motivo
    for bloqueio in bloqueios:
        if isinstance(bloqueio, str):
            if bloqueio == data_str:
                return True
        elif isinstance(bloqueio, dict):
            if bloqueio.get("data") == data_str:
                return True
    
    return False


def horarios_disponiveis_com_verificacao(data_str: str) -> List[str]:
    """
    Retorna horários disponíveis já verificando ocupação no Excel.
    
    Esta é a função principal para usar no fluxo de agendamento,
    substituindo DEFAULT_SLOTS.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
    
    Returns:
        Lista de horários disponíveis (HH:MM)
    """
    return gerar_slots_dia(data_str, incluir_ocupados=False)


# =========================================================
# Gerenciamento de Bloqueios
# =========================================================

def adicionar_bloqueio_pontual(data_str: str, motivo: Optional[str] = None) -> bool:
    """
    Adiciona bloqueio para um dia específico.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        motivo: Motivo do bloqueio (opcional)
    
    Returns:
        True se adicionou com sucesso, False caso contrário
    """
    config = carregar_config(force_reload=True)
    
    bloqueios = config.get("bloqueios_pontuais", [])
    
    # Verificar se já existe bloqueio para esta data
    for bloqueio in bloqueios:
        data_bloqueio = bloqueio if isinstance(bloqueio, str) else bloqueio.get("data")
        if data_bloqueio == data_str:
            return False  # Já bloqueado
    
    # Adicionar bloqueio
    if motivo:
        bloqueios.append({"data": data_str, "motivo": motivo})
    else:
        bloqueios.append(data_str)
    
    config["bloqueios_pontuais"] = bloqueios
    return salvar_config(config)


def remover_bloqueio_pontual(data_str: str) -> bool:
    """
    Remove bloqueio de um dia específico.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
    
    Returns:
        True se removeu com sucesso, False caso contrário
    """
    config = carregar_config(force_reload=True)
    
    bloqueios = config.get("bloqueios_pontuais", [])
    bloqueios_novos = []
    removeu = False
    
    for bloqueio in bloqueios:
        data_bloqueio = bloqueio if isinstance(bloqueio, str) else bloqueio.get("data")
        if data_bloqueio != data_str:
            bloqueios_novos.append(bloqueio)
        else:
            removeu = True
    
    if removeu:
        config["bloqueios_pontuais"] = bloqueios_novos
        return salvar_config(config)
    
    return False


def listar_bloqueios() -> List[Dict[str, str]]:
    """
    Lista todos os bloqueios pontuais.
    
    Returns:
        Lista de dicts com 'data' e 'motivo'
    """
    config = carregar_config()
    bloqueios = config.get("bloqueios_pontuais", [])
    
    resultado = []
    for bloqueio in bloqueios:
        if isinstance(bloqueio, str):
            resultado.append({"data": bloqueio, "motivo": ""})
        else:
            resultado.append({
                "data": bloqueio.get("data", ""),
                "motivo": bloqueio.get("motivo", "")
            })
    
    return resultado


# =========================================================
# Gerenciamento de Horários Semanais
# =========================================================

def atualizar_horario_dia_semana(
    dia: str,
    ativo: Optional[bool] = None,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    intervalos: Optional[List[Dict]] = None
) -> bool:
    """
    Atualiza configuração padrão de um dia da semana.
    
    Args:
        dia: Nome do dia ('segunda', 'terca', etc.)
        ativo: Se dia está ativo (True/False)
        inicio: Horário de início (HH:MM)
        fim: Horário de término (HH:MM)
        intervalos: Lista de intervalos (almoço, pausas)
    
    Returns:
        True se atualizou com sucesso, False caso contrário
    """
    config = carregar_config(force_reload=True)
    
    dias_validos = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    if dia not in dias_validos:
        return False
    
    horario_funcionamento = config.get("horario_funcionamento", {})
    
    # Garantir que dia existe na configuração
    if dia not in horario_funcionamento:
        horario_funcionamento[dia] = {
            "ativo": True,
            "inicio": "08:00",
            "fim": "18:00",
            "intervalos": []
        }
    
    # Atualizar campos fornecidos
    if ativo is not None:
        horario_funcionamento[dia]["ativo"] = ativo
    if inicio is not None:
        horario_funcionamento[dia]["inicio"] = inicio
    if fim is not None:
        horario_funcionamento[dia]["fim"] = fim
    if intervalos is not None:
        horario_funcionamento[dia]["intervalos"] = intervalos
    
    config["horario_funcionamento"] = horario_funcionamento
    return salvar_config(config)


def adicionar_slots_personalizados(data_str: str, slots: List[str]) -> bool:
    """
    Define slots específicos para um dia (sobrescreve padrão semanal).
    
    Args:
        data_str: Data no formato DD/MM/YYYY
        slots: Lista de horários personalizados (HH:MM)
    
    Returns:
        True se adicionou com sucesso, False caso contrário
    """
    config = carregar_config(force_reload=True)
    
    slots_personalizados = config.get("slots_personalizados", {})
    slots_personalizados[data_str] = slots
    
    config["slots_personalizados"] = slots_personalizados
    return salvar_config(config)


def remover_slots_personalizados(data_str: str) -> bool:
    """
    Remove slots personalizados de um dia (volta a usar padrão semanal).
    
    Args:
        data_str: Data no formato DD/MM/YYYY
    
    Returns:
        True se removeu com sucesso, False caso contrário
    """
    config = carregar_config(force_reload=True)
    
    slots_personalizados = config.get("slots_personalizados", {})
    if data_str in slots_personalizados:
        del slots_personalizados[data_str]
        config["slots_personalizados"] = slots_personalizados
        return salvar_config(config)
    
    return False


# =========================================================
# Utilitários
# =========================================================

def obter_configuracao_dia(data_str: str) -> Dict[str, Any]:
    """
    Retorna configuração completa de um dia específico.
    
    Útil para exibir no painel ou para debugging.
    
    Args:
        data_str: Data no formato DD/MM/YYYY
    
    Returns:
        Dict com: ativo, bloqueado, slots, tipo_fonte
    """
    config = carregar_config()
    
    # Verificar bloqueio
    bloqueado = eh_dia_bloqueado(data_str, config)
    
    # Verificar slots personalizados
    slots_personalizados = config.get("slots_personalizados", {})
    tem_personalizado = data_str in slots_personalizados
    
    # Obter dia da semana
    try:
        data_obj = datetime.strptime(data_str, "%d/%m/%Y")
        dia_semana = _get_nome_dia_semana(data_obj.weekday())
    except Exception:
        return {"ativo": False, "bloqueado": True, "slots": [], "tipo_fonte": "erro"}
    
    horario_funcionamento = config.get("horario_funcionamento", {})
    horario_dia = horario_funcionamento.get(dia_semana, {})
    
    # Determinar tipo de fonte
    if bloqueado:
        tipo_fonte = "bloqueado"
        slots = []
        ativo = False
    elif tem_personalizado:
        tipo_fonte = "personalizado"
        slots = slots_personalizados[data_str]
        ativo = len(slots) > 0
    else:
        tipo_fonte = "padrao_semanal"
        ativo = horario_dia.get("ativo", False)
        slots = gerar_slots_dia(data_str, incluir_ocupados=True) if ativo else []
    
    return {
        "ativo": ativo,
        "bloqueado": bloqueado,
        "slots": slots,
        "tipo_fonte": tipo_fonte,
        "dia_semana": dia_semana,
        "horario_inicio": horario_dia.get("inicio", ""),
        "horario_fim": horario_dia.get("fim", ""),
        "intervalos": horario_dia.get("intervalos", []),
    }


def limpar_bloqueios_antigos(dias_atras: int = 30) -> int:
    """
    Remove bloqueios de datas antigas (limpeza de manutenção).
    
    Args:
        dias_atras: Remove bloqueios anteriores a X dias atrás
    
    Returns:
        Número de bloqueios removidos
    """
    config = carregar_config(force_reload=True)
    bloqueios = config.get("bloqueios_pontuais", [])
    
    data_limite = datetime.now() - timedelta(days=dias_atras)
    bloqueios_novos = []
    removidos = 0
    
    for bloqueio in bloqueios:
        data_str = bloqueio if isinstance(bloqueio, str) else bloqueio.get("data", "")
        
        try:
            data_obj = datetime.strptime(data_str, "%d/%m/%Y")
            if data_obj >= data_limite:
                bloqueios_novos.append(bloqueio)
            else:
                removidos += 1
        except Exception:
            # Se não conseguir parsear, mantém
            bloqueios_novos.append(bloqueio)
    
    if removidos > 0:
        config["bloqueios_pontuais"] = bloqueios_novos
        salvar_config(config)
    
    return removidos
