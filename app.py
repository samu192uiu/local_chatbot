# app.py (na raiz do projeto - ATUALIZADO com fluxo de agendamento)
from flask import Flask, request, jsonify
import logging
import os
import re # Para extrair data/hora
from datetime import datetime

# Importa o serviço WAHA da pasta 'services'
from services.waha import Waha # Assumindo que está em ZapWaha/services/waha.py

# --- Configurações ---
CONFIG = {
    "CLIENT_NAME": "ClinicaXYZ_Prototipo",
    "WAHA_API_URL": os.getenv("WAHA_API_URL", "http://localhost:3000"),
    "VALOR_CONSULTA": 150.00, # Exemplo de valor
    "GREETING_MESSAGE": "Olá! 👋 Bem-vindo(a) à Clínica.",
    "MAIN_MENU_TEXT": (
        "Como podemos te ajudar hoje?\n\n"
        "*Digite o número da opção desejada:*\n"
        "1️⃣ Agendar ou Gerenciar Aulas\n"
        "2️⃣ Informações e Valores\n"
        "3️⃣ Dúvidas Frequentes\n"
        "4️⃣ Pagamentos"
    ),
    "INVALID_OPTION_MESSAGE": "Opção inválida. Por favor, digite um número do menu ou 'menu'.",
    "ERROR_MESSAGE": "Desculpe, ocorreu um erro interno. Tente novamente mais tarde ou digite 'menu'.",
    "BACK_TO_MENU_KEYWORDS": ['menu', 'voltar', 'início', 'inicio', 'sair'],
}

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(CONFIG["CLIENT_NAME"])

app = Flask(__name__)

# --- Gerenciador de Estado Simples em Memória ---
user_states = {} # Dicionário guarda o estado atual e dados temporários

class MemoryStateManager:
    def get_state(self, chat_id):
        # Retorna o estado ('MENU_PRINCIPAL', 'PEDINDO_DATA_HORA', etc.)
        return user_states.get(chat_id, {}).get('state', 'MENU_PRINCIPAL')

    def set_state(self, chat_id, state, data=None):
        # Atualiza o estado e opcionalmente guarda dados temporários
        current_data = user_states.get(chat_id, {})
        current_data['state'] = state
        if data:
            current_data.update(data) # Adiciona/atualiza dados temporários
        user_states[chat_id] = current_data
        logger.debug(f"Estado de {chat_id} definido na memória para '{state}' com dados: {data}")

    def get_data(self, chat_id):
        # Retorna os dados temporários guardados para o usuário
        return user_states.get(chat_id, {})

    def clear_data(self, chat_id):
        # Limpa dados temporários, mantendo apenas o estado (ou resetando)
        state = self.get_state(chat_id)
        user_states[chat_id] = {'state': state} # Mantém só o estado atual
        logger.debug(f"Dados temporários de {chat_id} limpos.")

    def delete_state(self, chat_id):
        if chat_id in user_states:
            del user_states[chat_id]
            logger.debug(f"Estado de {chat_id} removido da memória")

# --- Instanciação dos Serviços ---
try:
    waha_service = Waha(api_url=CONFIG["WAHA_API_URL"])
except TypeError:
    logger.warning("Tentando instanciar Waha sem api_url.")
    waha_service = Waha()

state_manager = MemoryStateManager()

# --- Funções de Fluxo ---

def send_main_menu(chat_id):
    """Envia o menu principal e define o estado."""
    menu_message = f"{CONFIG['GREETING_MESSAGE']}\n\n{CONFIG['MAIN_MENU_TEXT']}"
    waha_service.send_message(chat_id=chat_id, message=menu_message)
    state_manager.set_state(chat_id, 'ESPERANDO_OPCAO_MENU')

def handle_main_menu_option(chat_id, message):
    """Processa a opção do menu principal."""
    if message == '1':
        sub_menu = (
            "Certo! O que você gostaria de fazer com suas aulas?\n\n"
            "1. Agendar nova aula/consulta\n"
            "2. Confirmar minha próxima aula\n"
            "3. Remarcar aula\n"
            "4. Cancelar aula"
        )
        waha_service.send_message(chat_id=chat_id, message=sub_menu)
        state_manager.set_state(chat_id, 'AGENDAMENTO_ESCOLHER_ACAO')
    elif message == '2':
        waha_service.send_message(chat_id=chat_id, message="Opção 2 (Informações) - Em construção...")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL') # Volta ao menu
    elif message == '3':
        waha_service.send_message(chat_id=chat_id, message="Opção 3 (Dúvidas) - Em construção...")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL') # Volta ao menu
    elif message == '4':
        waha_service.send_message(chat_id=chat_id, message="Opção 4 (Pagamentos) - Em construção...")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL') # Volta ao menu
    else:
        waha_service.send_message(chat_id=chat_id, message=CONFIG['INVALID_OPTION_MESSAGE'])
        # Mantém o estado ESPERANDO_OPCAO_MENU

def handle_agendamento_escolha(chat_id, message):
    """Processa a escolha dentro do sub-menu de agendamento."""
    if message == '1':
        waha_service.send_message(chat_id=chat_id, message="Ótimo! Para qual data e horário você gostaria de agendar? (Ex: DD/MM/AAAA HH:MM)")
        state_manager.set_state(chat_id, 'AGENDAMENTO_PEDINDO_DATA_HORA')
    # Adicionar lógica para opções 2, 3, 4 depois...
    else:
        waha_service.send_message(chat_id=chat_id, message=CONFIG['INVALID_OPTION_MESSAGE'])
        # Mantém o estado AGENDAMENTO_ESCOLHER_ACAO

def parse_datetime(text):
    """Tenta extrair data (DD/MM/AAAA) e hora (HH:MM) do texto."""
    # Regex simples para DD/MM/AAAA HH:MM
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*.*?(\d{1,2}:\d{2})', text)
    if match:
        data_str = match.group(1)
        hora_str = match.group(2)
        # Tenta validar a data/hora (opcional mas recomendado)
        try:
            datetime.strptime(f"{data_str} {hora_str}", "%d/%m/%Y %H:%M")
            return data_str, hora_str
        except ValueError:
            logger.warning(f"Formato data/hora inválido detectado: {data_str} {hora_str}")
            return None, None
    logger.warning(f"Não foi possível extrair data/hora de: '{text}'")
    return None, None

def handle_agendamento_data_hora(chat_id, message):
    """Recebe a data/hora, verifica disponibilidade e pede pagamento."""
    data_str, hora_str = parse_datetime(message)

    if not data_str or not hora_str:
        waha_service.send_message(chat_id=chat_id, message="Não consegui entender a data e hora. Por favor, use o formato DD/MM/AAAA HH:MM (ex: 28/10/2025 14:00).")
        # Mantém o estado AGENDAMENTO_PEDINDO_DATA_HORA
        return

    logger.info(f"Verificando disponibilidade para {data_str} às {hora_str}")
    disponivel = excel_service.verificar_disponibilidade(data_str, hora_str)

    if disponivel:
        valor_str = f"{CONFIG['VALOR_CONSULTA']:.2f}".replace('.', ',')
        msg = (
            f"Perfeito! O horário de {data_str} às {hora_str} está disponível. ✅\n\n"
            f"Para garantir sua vaga, o pagamento no valor de R$ {valor_str} deve ser feito antecipadamente.\n\n"
            "Como prefere pagar?\n"
            "1. PIX (Copia e Cola)\n"
            "2. Cartão de Crédito (Link)"
        )
        waha_service.send_message(chat_id=chat_id, message=msg)
        # Guarda data e hora nos dados do estado antes de mudar o estado
        state_manager.set_state(chat_id, 'AGENDAMENTO_ESCOLHENDO_PAGAMENTO', data={'data': data_str, 'hora': hora_str})
    else:
        waha_service.send_message(chat_id=chat_id, message=f"Poxa, o horário de {data_str} às {hora_str} não está mais disponível. 😕\nPor favor, sugira outra data/hora (DD/MM/AAAA HH:MM).")
        # Mantém o estado AGENDAMENTO_PEDINDO_DATA_HORA

def handle_escolha_pagamento(chat_id, message):
    """Envia as instruções de pagamento conforme a escolha."""
    user_data = state_manager.get_data(chat_id)
    data_agendamento = user_data.get('data')
    hora_agendamento = user_data.get('hora')

    if not data_agendamento or not hora_agendamento:
        logger.error(f"Erro: Faltando data/hora ao escolher pagamento para {chat_id}")
        waha_service.send_message(chat_id=chat_id, message="Ocorreu um erro ao processar seu pedido. Por favor, digite 'menu' e tente novamente.")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL')
        return

    if message == '1': # PIX
        # Simulação - Na real, chamaria API de pagamento para gerar código
        pix_code = "00020126...chave_aleatoria_pix...5303986..." # Placeholder
        msg = (
            "Ok, aqui está o código PIX Copia e Cola:\n\n"
            f"`{pix_code}`\n\n" # Usar crases para formatar como código no WhatsApp
            "Por favor, realize o pagamento e *me envie o comprovante* ou digite 'paguei' para que eu possa verificar.\n"
            "_O horário fica pré-reservado por 10 minutos._"
        )
        waha_service.send_message(chat_id=chat_id, message=msg)
        # Adiciona agendamento preliminar na planilha
        excel_service.adicionar_agendamento(data_agendamento, hora_agendamento, chat_id, status="Pendente Pagamento")
        state_manager.set_state(chat_id, 'AGENDAMENTO_AGUARDANDO_COMPROVANTE_PIX') # Não limpar dados aqui
    elif message == '2': # Cartão
        # Simulação - Na real, chamaria API de pagamento para gerar link
        link_pagamento = "https://pagamento.simulado/link123" # Placeholder
        msg = (
            "Ok, aqui está o link para pagamento com Cartão de Crédito:\n"
            f"{link_pagamento}\n\n"
            "Após confirmar o pagamento no link, digite 'paguei' aqui para eu verificar.\n"
            "_O horário fica pré-reservado por 10 minutos._"
        )
        waha_service.send_message(chat_id=chat_id, message=msg)
        # Adiciona agendamento preliminar na planilha
        excel_service.adicionar_agendamento(data_agendamento, hora_agendamento, chat_id, status="Pendente Pagamento")
        state_manager.set_state(chat_id, 'AGENDAMENTO_AGUARDANDO_PAGAMENTO_LINK') # Não limpar dados aqui
    else:
        waha_service.send_message(chat_id=chat_id, message=CONFIG['INVALID_OPTION_MESSAGE'] + " Escolha 1 para PIX ou 2 para Cartão.")
        # Mantém o estado AGENDAMENTO_ESCOLHENDO_PAGAMENTO

def handle_confirmacao_pagamento(chat_id, message):
    """Processa a confirmação de pagamento (simulada)."""
    user_data = state_manager.get_data(chat_id)
    data_agendamento = user_data.get('data')
    hora_agendamento = user_data.get('hora')

    if not data_agendamento or not hora_agendamento:
        logger.error(f"Erro: Faltando data/hora ao confirmar pagamento para {chat_id}")
        waha_service.send_message(chat_id=chat_id, message="Ocorreu um erro. Digite 'menu'.")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL')
        return

    # SIMULAÇÃO: Assume que se o usuário mandou "paguei" ou um comprovante (não vamos processar imagem agora)
    # o pagamento foi feito. Na real, precisaria de uma checagem via API ou manual.
    pagamento_confirmado = True # Simulação

    if pagamento_confirmado:
        # Tenta atualizar o status na planilha (se não conseguir, o agendamento já existe como pendente)
        atualizou = excel_service.atualizar_status(f"{data_agendamento}_{hora_agendamento}_{chat_id}", "Confirmado") # Precisamos de uma forma de identificar a linha
        if not atualizou:
            # Se não conseguiu atualizar (função não implementada ou erro), tenta adicionar como confirmado
            # Isso pode duplicar se a atualização falhar mas o add funcionar. Ideal é implementar update.
            logger.warning("Não foi possível ATUALIZAR status para Confirmado, tentando ADICIONAR novamente.")
            # excel_service.adicionar_agendamento(data_agendamento, hora_agendamento, chat_id, status="Confirmado", valor_pago=CONFIG['VALOR_CONSULTA'])
            # Por segurança, vamos apenas avisar o admin por enquanto se a atualização falhar
            waha_service.send_message(chat_id=chat_id, message=f"Pagamento recebido! 🎉 Seu agendamento para {data_agendamento} às {hora_agendamento} está PRÉ-CONFIRMADO! Um atendente finalizará a confirmação.")
        else:
            waha_service.send_message(chat_id=chat_id, message=f"Pagamento confirmado! 🎉 Seu agendamento para {data_agendamento} às {hora_agendamento} está confirmado com sucesso!")

        waha_service.send_message(chat_id=chat_id, message="Algo mais em que posso ajudar? (Digite 'menu')")
        state_manager.set_state(chat_id, 'MENU_PRINCIPAL') # Reseta o estado
        state_manager.clear_data(chat_id) # Limpa data/hora guardados
    else:
        # Simulação de falha
        waha_service.send_message(chat_id=chat_id, message="Ainda não localizei seu pagamento. Poderia verificar ou tentar enviar o comprovante novamente?")
        # Mantém o estado AGUARDANDO_COMPROVANTE/PAGAMENTO

# --- Webhook Principal (com Roteamento Atualizado) ---
@app.route('/chatbot/webhook/', methods=['POST'])
def webhook():
    try:
        data = request.json
        # ... (validação do payload e checagem de grupo como antes) ...
        chat_id = data['payload']['from']
        received_message = data['payload']['body'].strip()
        is_group = '@g.us' in chat_id

        logger.info(f"Mensagem de {chat_id}: '{received_message}'")
        if is_group: return jsonify({'status': 'success', 'message': 'Ignorado.'}), 200
        if not waha_service: return jsonify({'status': 'error', 'message': 'Erro: WAHA off.'}), 500

        waha_service.start_typing(chat_id=chat_id)

        # Voltar ao menu
        if received_message.lower() in CONFIG.get("BACK_TO_MENU_KEYWORDS", ['menu']):
            send_main_menu(chat_id) # send_main_menu já define o estado
            waha_service.stop_typing(chat_id=chat_id)
            return jsonify({'status': 'success'}), 200

        current_state = state_manager.get_state(chat_id)
        logger.info(f"Estado atual ({chat_id}): {current_state}")

        # --- Roteamento para o fluxo correto baseado no estado ---
        if current_state == 'MENU_PRINCIPAL':
            send_main_menu(chat_id)
        elif current_state == 'ESPERANDO_OPCAO_MENU':
            handle_main_menu_option(chat_id, received_message)
        elif current_state == 'AGENDAMENTO_ESCOLHER_ACAO':
            handle_agendamento_escolha(chat_id, received_message)
        elif current_state == 'AGENDAMENTO_PEDINDO_DATA_HORA':
            handle_agendamento_data_hora(chat_id, received_message)
        elif current_state == 'AGENDAMENTO_ESCOLHENDO_PAGAMENTO':
            handle_escolha_pagamento(chat_id, received_message)
        elif current_state == 'AGENDAMENTO_AGUARDANDO_COMPROVANTE_PIX':
            handle_confirmacao_pagamento(chat_id, received_message) # Trata "paguei" ou comprovante
        elif current_state == 'AGENDAMENTO_AGUARDANDO_PAGAMENTO_LINK':
            handle_confirmacao_pagamento(chat_id, received_message) # Trata "paguei"
        # --- Adicionar outros estados aqui ---
        else:
            logger.warning(f"Estado desconhecido '{current_state}'. Enviando menu.")
            send_main_menu(chat_id)

        waha_service.stop_typing(chat_id=chat_id)
        return jsonify({'status': 'success'}), 200

    # ... (Bloco try...except como antes) ...
    except Exception as e:
        logger.error(f"Erro no webhook: {e}", exc_info=True)
        try:
            chat_id_on_error = request.json.get('payload', {}).get('from', None)
            if chat_id_on_error and waha_service:
                waha_service.send_message(chat_id=chat_id_on_error, message=CONFIG.get('ERROR_MESSAGE'))
        except Exception as notify_error:
            logger.error(f"Erro ao notificar usuário sobre erro: {notify_error}")
        return jsonify({'status': 'error', 'message': 'Erro interno.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)