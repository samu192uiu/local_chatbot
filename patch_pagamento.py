#!/usr/bin/env python3
"""
Script para modificar o fluxo de agendamento e adicionar pagamento PIX.
"""
import re

# Ler o arquivo
with open('/opt/barbearia-bot/src/zapwaha/flows/agendamento.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Bloco antigo (sem pagamento)
old_block = '''    # CRIAR AGENDAMENTO (já com status Confirmado)
    ok = _pre_reservar(send, chat_id, data_str, hora_str)
    if not ok:
        return
    
    # CONFIRMAR AGENDAMENTO (atualizar status para garantir)
    _update_status_confirmado(chat_id)

    # MENSAGEM DE CONFIRMAÇÃO'''

# Novo bloco (com pagamento PIX)
new_block = '''    # CRIAR RESERVA TEMPORÁRIA
    ok = _pre_reservar(send, chat_id, data_str, hora_str)
    if not ok:
        return
    
    # OBTER DADOS DO AGENDAMENTO
    dados = state_manager.get_data(chat_id)
    chave = dados.get("ag_chave")
    servico_id = dados.get("servico_escolhido", "corte_simples")
    nome = dados.get("nome", "Cliente")
    
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
    
    # CRIAR PAGAMENTO PIX
    if mp and chave:
        try:
            # Preparar metadata
            metadata = {
                "chave_agendamento": chave,
                "chat_id": chat_id,
                "data": data_str,
                "hora": hora_str,
                "servico_id": servico_id,
                "cliente_nome": nome
            }
            
            # Gerar email temporário se não tiver
            email_pagador = f"{chat_id.replace('@c.us', '')}@temp.barbearia.com"
            
            # Criar pagamento
            logger.info(f"[FLOW] Criando pagamento PIX para {chave}")
            resultado_pix = mp.criar_pagamento_pix(
                valor=valor_servico,
                descricao=f"Agendamento - {nome_servico} - {data_str} {hora_str}",
                email_pagador=email_pagador,
                metadata=metadata
            )
            
            if resultado_pix.get("sucesso"):
                payment_id = resultado_pix.get("payment_id")
                
                # Salvar PagamentoID no Excel
                if payment_id and excel:
                    try:
                        excel.atualizar_pagamento_id(chave, payment_id, "pending")
                        logger.info(f"[FLOW] PagamentoID {payment_id} salvo para {chave}")
                    except Exception as e:
                        logger.error(f"[FLOW] Erro ao salvar PagamentoID: {e}")
                
                # Enviar mensagem com código PIX
                mensagem_pix = mp.formatar_mensagem_pix(
                    resultado_pix,
                    {
                        "data": data_str,
                        "hora": hora_str,
                        "servico_nome": nome_servico,
                        "valor": valor_servico
                    }
                )
                
                send(chat_id, mensagem_pix)
                
                # Aguardando pagamento
                send(chat_id, "⏳ *Aguardando confirmação do pagamento...*\\n\\nAssim que o pagamento for confirmado, você receberá uma notificação automática!")
                
                state_manager.set_state(chat_id, S_MENU)
                return
                
            else:
                # Erro ao gerar pagamento - confirmar sem pagamento
                logger.error(f"[FLOW] Erro ao criar pagamento: {resultado_pix.get('mensagem')}")
                send(chat_id, "⚠️ Não foi possível gerar o pagamento PIX.\\nSeu agendamento será confirmado para pagamento no local.")
                _update_status_confirmado(chat_id)
        
        except Exception as e:
            logger.exception(f"[FLOW] Exceção ao criar pagamento PIX: {e}")
            send(chat_id, "⚠️ Erro ao processar pagamento.\\nSeu agendamento será confirmado para pagamento no local.")
            _update_status_confirmado(chat_id)
    else:
        # Mercado Pago não disponível - confirmar sem pagamento
        logger.warning("[FLOW] Mercado Pago não disponível - confirmando sem pagamento")
        _update_status_confirmado(chat_id)

    # MENSAGEM DE CONFIRMAÇÃO (apenas se não gerou PIX)'''

# Substituir
content = content.replace(old_block, new_block)

# Salvar
with open('/opt/barbearia-bot/src/zapwaha/flows/agendamento.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Arquivo modificado com sucesso!")
print("   - Adicionado fluxo de pagamento PIX")
print("   - Reserva aguarda pagamento antes de confirmar")
print("   - Fallback para pagamento no local em caso de erro")
