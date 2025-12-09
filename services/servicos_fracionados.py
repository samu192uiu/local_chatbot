# services/servicos_fracionados.py
"""
Gerenciamento de serviços fracionados (luzes, platinado, etc)
que permitem agendamentos intercalados durante pausas.
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# Caminho para configuração
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "servicos_detalhados.json")


def carregar_servicos() -> Dict:
    """Carrega configuração de serviços do JSON."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"servicos": [], "configuracoes": {}}


def listar_servicos() -> List[Dict]:
    """Retorna lista de todos os serviços disponíveis."""
    config = carregar_servicos()
    return config.get("servicos", [])


def get_servico_por_id(servico_id: str) -> Optional[Dict]:
    """Busca serviço específico por ID."""
    servicos = listar_servicos()
    for s in servicos:
        if s.get("id") == servico_id:
            return s
    return None


def servico_eh_fracionado(servico_id: str) -> bool:
    """Verifica se um serviço é fracionado (tem etapas)."""
    servico = get_servico_por_id(servico_id)
    if not servico:
        return False
    return servico.get("tipo") == "fracionado"


def calcular_slots_ocupados(servico_id: str, horario_inicio: str, data: str) -> List[Dict]:
    """
    Calcula todos os slots de tempo que serão ocupados por um serviço.
    
    Args:
        servico_id: ID do serviço
        horario_inicio: Hora inicial (HH:MM)
        data: Data do agendamento (DD/MM/YYYY)
    
    Returns:
        Lista de dicts com: {
            "inicio": "HH:MM",
            "fim": "HH:MM", 
            "barbeiro_ocupado": bool,
            "etapa": str,
            "ordem": int
        }
    """
    servico = get_servico_por_id(servico_id)
    if not servico:
        return []
    
    try:
        # Parsear data e hora inicial
        dt_inicio = datetime.strptime(f"{data} {horario_inicio}", "%d/%m/%Y %H:%M")
    except Exception:
        return []
    
    slots = []
    
    if servico.get("tipo") == "simples":
        # Serviço simples: um slot único
        duracao = servico.get("duracao_minutos", 40)
        dt_fim = dt_inicio + timedelta(minutes=duracao)
        
        slots.append({
            "inicio": dt_inicio.strftime("%H:%M"),
            "fim": dt_fim.strftime("%H:%M"),
            "barbeiro_ocupado": True,
            "etapa": servico.get("nome"),
            "ordem": 1
        })
    
    elif servico.get("tipo") == "fracionado":
        # Serviço fracionado: múltiplas etapas
        etapas = servico.get("etapas", [])
        dt_atual = dt_inicio
        
        for etapa in etapas:
            duracao = etapa.get("duracao_minutos", 0)
            dt_fim_etapa = dt_atual + timedelta(minutes=duracao)
            
            slots.append({
                "inicio": dt_atual.strftime("%H:%M"),
                "fim": dt_fim_etapa.strftime("%H:%M"),
                "barbeiro_ocupado": etapa.get("barbeiro_ocupado", True),
                "etapa": etapa.get("nome"),
                "ordem": etapa.get("ordem", 0)
            })
            
            dt_atual = dt_fim_etapa
    
    return slots


def get_slots_bloqueados(servico_id: str, horario_inicio: str, data: str) -> List[Tuple[str, str]]:
    """
    Retorna apenas os slots onde o barbeiro está OCUPADO.
    Usado para verificar conflitos de agendamento.
    
    Returns:
        Lista de tuplas (hora_inicio, hora_fim) onde barbeiro está ocupado
    """
    todos_slots = calcular_slots_ocupados(servico_id, horario_inicio, data)
    
    slots_bloqueados = []
    for slot in todos_slots:
        if slot.get("barbeiro_ocupado", True):
            slots_bloqueados.append((slot["inicio"], slot["fim"]))
    
    return slots_bloqueados


def horarios_conflitam(hora_inicio_1: str, hora_fim_1: str, 
                       hora_inicio_2: str, hora_fim_2: str) -> bool:
    """
    Verifica se dois intervalos de horário se sobrepõem.
    
    Args:
        hora_inicio_1, hora_fim_1: Primeiro intervalo (HH:MM)
        hora_inicio_2, hora_fim_2: Segundo intervalo (HH:MM)
    
    Returns:
        True se há conflito, False caso contrário
    """
    try:
        # Usar uma data fixa só para comparação de horas
        data_ref = "01/01/2025"
        
        dt1_inicio = datetime.strptime(f"{data_ref} {hora_inicio_1}", "%d/%m/%Y %H:%M")
        dt1_fim = datetime.strptime(f"{data_ref} {hora_fim_1}", "%d/%m/%Y %H:%M")
        dt2_inicio = datetime.strptime(f"{data_ref} {hora_inicio_2}", "%d/%m/%Y %H:%M")
        dt2_fim = datetime.strptime(f"{data_ref} {hora_fim_2}", "%d/%m/%Y %H:%M")
        
        # Conflito se: (início1 < fim2) E (início2 < fim1)
        return (dt1_inicio < dt2_fim) and (dt2_inicio < dt1_fim)
    
    except Exception:
        return True  # Em caso de erro, assume conflito por segurança


def verificar_disponibilidade_fracionado(
    servico_id: str,
    data: str,
    horario_inicio: str,
    agendamentos_existentes: List[Dict]
) -> Tuple[bool, Optional[str]]:
    """
    Verifica se um serviço fracionado pode ser agendado sem conflitos.
    
    Args:
        servico_id: ID do serviço a agendar
        data: Data desejada (DD/MM/YYYY)
        horario_inicio: Hora inicial (HH:MM)
        agendamentos_existentes: Lista de agendamentos já confirmados
    
    Returns:
        (disponivel: bool, mensagem_erro: str ou None)
    """
    # Calcular slots que o novo serviço ocupará
    slots_novo = get_slots_bloqueados(servico_id, horario_inicio, data)
    
    if not slots_novo:
        return False, "Erro ao calcular slots do serviço"
    
    # Verificar cada agendamento existente na mesma data
    for ag in agendamentos_existentes:
        ag_data = ag.get("Data") or ag.get("data", "")
        if ag_data != data:
            continue
        
        ag_servico_id = ag.get("ServicoID") or ag.get("servico_id", "corte_simples")
        ag_hora = ag.get("Hora") or ag.get("hora", "")
        
        # Calcular slots do agendamento existente
        slots_existente = get_slots_bloqueados(ag_servico_id, ag_hora, data)
        
        # Verificar conflito entre cada slot novo e existente
        for novo_inicio, novo_fim in slots_novo:
            for exist_inicio, exist_fim in slots_existente:
                if horarios_conflitam(novo_inicio, novo_fim, exist_inicio, exist_fim):
                    servico = get_servico_por_id(ag_servico_id)
                    nome_servico = servico.get("nome", "Serviço") if servico else "Serviço"
                    
                    return False, (
                        f"Conflito com agendamento existente:\n"
                        f"{nome_servico} às {ag_hora}\n"
                        f"Horário ocupado: {exist_inicio} - {exist_fim}"
                    )
    
    return True, None


def formatar_resumo_servico(servico_id: str, horario_inicio: str, data: str) -> str:
    """
    Formata um resumo visual do serviço com suas etapas.
    
    Returns:
        String formatada para exibir ao cliente
    """
    servico = get_servico_por_id(servico_id)
    if not servico:
        return "Serviço não encontrado"
    
    slots = calcular_slots_ocupados(servico_id, horario_inicio, data)
    
    linhas = []
    
    if servico.get("tipo") == "fracionado":
        linhas.append("⏱️ *Duração do serviço:*")
        linhas.append("")
        
        for slot in slots:
            linhas.append(f"• {slot['etapa']}")
            linhas.append(f"  {slot['inicio']} às {slot['fim']}")
            linhas.append("")
        
        # Calcular horário final
        if slots:
            hora_final = slots[-1]["fim"]
            linhas.append(f"🏁 *Previsão de término:* {hora_final}")
    else:
        duracao = servico.get("duracao_minutos", 0)
        linhas.append(f"⏱️ Duração: {duracao} minutos")
    
    return "\n".join(linhas)


def listar_servicos_formatado() -> str:
    """
    Retorna lista de serviços formatada para exibição no chat.
    """
    # Carregar do servicos.json
    try:
        import os
        servicos_path = os.path.join(os.path.dirname(__file__), "..", "config", "servicos.json")
        with open(servicos_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            servicos = data.get("servicos", [])
    except Exception:
        return "Nenhum serviço disponível no momento."
    
    if not servicos:
        return "Nenhum serviço disponível no momento."
    
    # Mapeamento de emojis por ID
    emojis = {
        "cabelo_sobrancelha": "💇🏽",
        "barba": "🧔🏻‍♂️",
        "sobrancelha": "👁️",
        "platinado": "👨🏽‍🦳"
    }
    
    top = "╔════════════════════════╗"
    titulo = "║  💈 SERVIÇOS E VALORES  ║"
    sep = "╠════════════════════════╣"
    bot = "╚════════════════════════╝"
    
    linhas = [top, titulo, sep, "║                        ║"]
    
    # Separar por tipo
    simples = [s for s in servicos if not s.get("fracionado", False)]
    fracionados = [s for s in servicos if s.get("fracionado", False)]
    
    numero = 1
    
    if simples:
        for s in simples:
            sid = s.get("id", "")
            emoji = emojis.get(sid, "•")
            nome = s.get("nome")
            valor = s.get("preco", 0)
            duracao = s.get("duracao_minutos", 0)
            linhas.append(f"║ {numero}️⃣ {emoji} {nome}")
            linhas.append(f"║    R$ {valor:.2f} - {duracao} minutos")
            linhas.append("║                        ║")
            numero += 1
    
    if fracionados:
        for s in fracionados:
            sid = s.get("id", "")
            emoji = emojis.get(sid, "✨")
            nome = s.get("nome")
            valor = s.get("preco", 0)
            duracao = s.get("duracao_minutos", 0)
            linhas.append(f"║ {numero}️⃣ {emoji} {nome} *")
            linhas.append(f"║    R$ {valor:.2f} - ~{duracao} min")
            linhas.append("║                        ║")
            numero += 1
    
    linhas.append(bot)
    
    mensagem = "\n".join(linhas)
    
    if fracionados:
        mensagem += "\n\n* _Serviços fracionados permitem_\n  _outros atendimentos durante pausas_"
    
    return mensagem
