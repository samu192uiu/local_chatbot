# src/zapwaha/web/agenda_panel.py
"""
Painel Web de Gestão de Agenda - Blueprint Flask

Permite ao barbeiro/admin configurar horários de funcionamento através de interface web.
Rotas protegidas por ADMIN_TOKEN.
"""

from flask import Blueprint, request, jsonify, render_template_string
from datetime import datetime, timedelta
from functools import wraps
import os

# Importar módulo de agenda dinâmica
try:
    from services import agenda_dinamica as ag
except ImportError:
    ag = None

# Blueprint
agenda_bp = Blueprint('agenda', __name__, url_prefix='/admin/agenda')

# Token de autenticação
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "default_token_change_me")

# =============================================================================
# Decorador de Autenticação
# =============================================================================

def require_admin_token(f):
    """Decorator para proteger rotas com ADMIN_TOKEN."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar token no header ou query param
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        
        if not token:
            token = request.headers.get('X-Admin-Token')
        
        if not token:
            token = request.args.get('token')
        
        if token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized", "message": "Token inválido ou ausente"}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# =============================================================================
# Rotas de Visualização
# =============================================================================

@agenda_bp.route('/', methods=['GET'])
@require_admin_token
def visualizar_agenda():
    """
    GET /admin/agenda?token=<TOKEN>
    
    Visualiza configuração completa da agenda.
    Retorna JSON com horário de funcionamento, bloqueios e slots personalizados.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    config = ag.carregar_config()
    
    return jsonify({
        "success": True,
        "configuracao": config,
        "observacao": "Use POST /admin/agenda/horario para atualizar horários semanais"
    })


@agenda_bp.route('/dia/<data>', methods=['GET'])
@require_admin_token
def visualizar_dia(data):
    """
    GET /admin/agenda/dia/<DD-MM-YYYY>?token=<TOKEN>
    
    Retorna configuração detalhada de um dia específico.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    # Converter DD-MM-YYYY para DD/MM/YYYY
    data_str = data.replace('-', '/')
    
    try:
        config_dia = ag.obter_configuracao_dia(data_str)
        slots = ag.gerar_slots_dia(data_str, incluir_ocupados=True)
        
        return jsonify({
            "success": True,
            "data": data_str,
            "configuracao": config_dia,
            "slots_totais": slots,
            "total_slots": len(slots)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@agenda_bp.route('/semana', methods=['GET'])
@require_admin_token
def visualizar_semana():
    """
    GET /admin/agenda/semana?data=DD-MM-YYYY&token=<TOKEN>
    
    Retorna configuração de uma semana (7 dias a partir de data).
    Se data não fornecida, usa data atual.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    data_param = request.args.get('data')
    
    if data_param:
        try:
            data_inicial = datetime.strptime(data_param, "%d-%m-%Y")
        except ValueError:
            return jsonify({"error": "Formato de data inválido. Use DD-MM-YYYY"}), 400
    else:
        data_inicial = datetime.now()
    
    # Gerar 7 dias
    dias = []
    for i in range(7):
        data_obj = data_inicial + timedelta(days=i)
        data_str = data_obj.strftime("%d/%m/%Y")
        
        config_dia = ag.obter_configuracao_dia(data_str)
        slots = ag.gerar_slots_dia(data_str, incluir_ocupados=True)
        
        dias.append({
            "data": data_str,
            "dia_semana": config_dia.get("dia_semana"),
            "ativo": config_dia.get("ativo"),
            "bloqueado": config_dia.get("bloqueado"),
            "tipo_fonte": config_dia.get("tipo_fonte"),
            "slots": slots,
            "total_slots": len(slots)
        })
    
    return jsonify({
        "success": True,
        "periodo": f"{dias[0]['data']} a {dias[-1]['data']}",
        "dias": dias
    })

# =============================================================================
# Rotas de Bloqueio
# =============================================================================

@agenda_bp.route('/bloqueio', methods=['POST'])
@require_admin_token
def adicionar_bloqueio():
    """
    POST /admin/agenda/bloqueio
    Body: {"data": "DD/MM/YYYY", "motivo": "Feriado" (opcional)}
    
    Bloqueia um dia específico.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    dados = request.get_json()
    if not dados:
        return jsonify({"error": "JSON inválido"}), 400
    
    data_str = dados.get('data')
    motivo = dados.get('motivo')
    
    if not data_str:
        return jsonify({"error": "Campo 'data' obrigatório (formato DD/MM/YYYY)"}), 400
    
    # Validar formato
    try:
        datetime.strptime(data_str, "%d/%m/%Y")
    except ValueError:
        return jsonify({"error": "Formato de data inválido. Use DD/MM/YYYY"}), 400
    
    # Adicionar bloqueio
    sucesso = ag.adicionar_bloqueio_pontual(data_str, motivo)
    
    if sucesso:
        return jsonify({
            "success": True,
            "message": f"Dia {data_str} bloqueado com sucesso",
            "data": data_str,
            "motivo": motivo or ""
        })
    else:
        return jsonify({
            "success": False,
            "message": "Dia já está bloqueado ou erro ao salvar"
        }), 400


@agenda_bp.route('/bloqueio/<data>', methods=['DELETE'])
@require_admin_token
def remover_bloqueio(data):
    """
    DELETE /admin/agenda/bloqueio/<DD-MM-YYYY>?token=<TOKEN>
    
    Remove bloqueio de um dia específico.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    # Converter DD-MM-YYYY para DD/MM/YYYY
    data_str = data.replace('-', '/')
    
    sucesso = ag.remover_bloqueio_pontual(data_str)
    
    if sucesso:
        return jsonify({
            "success": True,
            "message": f"Bloqueio removido para {data_str}"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Bloqueio não encontrado ou erro ao remover"
        }), 404


@agenda_bp.route('/bloqueios', methods=['GET'])
@require_admin_token
def listar_bloqueios():
    """
    GET /admin/agenda/bloqueios?token=<TOKEN>
    
    Lista todos os bloqueios pontuais.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    bloqueios = ag.listar_bloqueios()
    
    return jsonify({
        "success": True,
        "bloqueios": bloqueios,
        "total": len(bloqueios)
    })

# =============================================================================
# Rotas de Horário Semanal
# =============================================================================

@agenda_bp.route('/horario', methods=['POST'])
@require_admin_token
def atualizar_horario_semanal():
    """
    POST /admin/agenda/horario
    Body: {
        "dia": "segunda",  // segunda, terca, quarta, quinta, sexta, sabado, domingo
        "ativo": true,
        "inicio": "08:00",
        "fim": "18:00",
        "intervalos": [
            {"inicio": "12:00", "fim": "13:00", "tipo": "almoco"}
        ]
    }
    
    Atualiza horário padrão de um dia da semana.
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    dados = request.get_json()
    if not dados:
        return jsonify({"error": "JSON inválido"}), 400
    
    dia = dados.get('dia')
    ativo = dados.get('ativo')
    inicio = dados.get('inicio')
    fim = dados.get('fim')
    intervalos = dados.get('intervalos')
    
    if not dia:
        return jsonify({"error": "Campo 'dia' obrigatório"}), 400
    
    dias_validos = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    if dia not in dias_validos:
        return jsonify({"error": f"Dia inválido. Use: {', '.join(dias_validos)}"}), 400
    
    # Atualizar
    sucesso = ag.atualizar_horario_dia_semana(
        dia=dia,
        ativo=ativo,
        inicio=inicio,
        fim=fim,
        intervalos=intervalos
    )
    
    if sucesso:
        return jsonify({
            "success": True,
            "message": f"Horário de {dia} atualizado com sucesso",
            "dia": dia
        })
    else:
        return jsonify({
            "success": False,
            "message": "Erro ao atualizar horário"
        }), 500

# =============================================================================
# Rotas de Slots Personalizados
# =============================================================================

@agenda_bp.route('/slots-personalizados', methods=['POST'])
@require_admin_token
def adicionar_slots_personalizados():
    """
    POST /admin/agenda/slots-personalizados
    Body: {
        "data": "DD/MM/YYYY",
        "slots": ["08:00", "10:00", "14:00", "16:00"]
    }
    
    Define slots específicos para um dia (sobrescreve padrão semanal).
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    dados = request.get_json()
    if not dados:
        return jsonify({"error": "JSON inválido"}), 400
    
    data_str = dados.get('data')
    slots = dados.get('slots')
    
    if not data_str or not slots:
        return jsonify({"error": "Campos 'data' e 'slots' obrigatórios"}), 400
    
    if not isinstance(slots, list):
        return jsonify({"error": "Campo 'slots' deve ser uma lista"}), 400
    
    # Validar formato de data
    try:
        datetime.strptime(data_str, "%d/%m/%Y")
    except ValueError:
        return jsonify({"error": "Formato de data inválido. Use DD/MM/YYYY"}), 400
    
    # Adicionar slots
    sucesso = ag.adicionar_slots_personalizados(data_str, slots)
    
    if sucesso:
        return jsonify({
            "success": True,
            "message": f"Slots personalizados definidos para {data_str}",
            "data": data_str,
            "slots": slots
        })
    else:
        return jsonify({
            "success": False,
            "message": "Erro ao salvar slots personalizados"
        }), 500


@agenda_bp.route('/slots-personalizados/<data>', methods=['DELETE'])
@require_admin_token
def remover_slots_personalizados(data):
    """
    DELETE /admin/agenda/slots-personalizados/<DD-MM-YYYY>?token=<TOKEN>
    
    Remove slots personalizados (volta a usar padrão semanal).
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    # Converter DD-MM-YYYY para DD/MM/YYYY
    data_str = data.replace('-', '/')
    
    sucesso = ag.remover_slots_personalizados(data_str)
    
    if sucesso:
        return jsonify({
            "success": True,
            "message": f"Slots personalizados removidos para {data_str}"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Slots personalizados não encontrados"
        }), 404

# =============================================================================
# Rotas de Manutenção
# =============================================================================

@agenda_bp.route('/limpar-bloqueios-antigos', methods=['POST'])
@require_admin_token
def limpar_bloqueios_antigos():
    """
    POST /admin/agenda/limpar-bloqueios-antigos
    Body: {"dias_atras": 30} (opcional, padrão: 30)
    
    Remove bloqueios de datas antigas (limpeza de manutenção).
    """
    if not ag:
        return jsonify({"error": "Módulo agenda_dinamica não disponível"}), 500
    
    dados = request.get_json() or {}
    dias_atras = dados.get('dias_atras', 30)
    
    try:
        dias_atras = int(dias_atras)
    except ValueError:
        return jsonify({"error": "Campo 'dias_atras' deve ser um número"}), 400
    
    removidos = ag.limpar_bloqueios_antigos(dias_atras)
    
    return jsonify({
        "success": True,
        "message": f"{removidos} bloqueios antigos removidos",
        "removidos": removidos,
        "dias_atras": dias_atras
    })

# =============================================================================
# Rota de Health Check
# =============================================================================

@agenda_bp.route('/health', methods=['GET'])
def health_check():
    """GET /admin/agenda/health - Verifica se módulo está funcionando."""
    return jsonify({
        "status": "ok" if ag else "error",
        "module": "agenda_dinamica",
        "available": ag is not None
    })
