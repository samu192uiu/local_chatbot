# services/mercadopago_service.py
"""
Serviço de integração com Mercado Pago para pagamentos de agendamentos.
"""
import os
import logging
import mercadopago
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger("ZapWaha")

# Configurações do Mercado Pago
ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "")
PUBLIC_KEY = os.getenv("MERCADO_PAGO_PUBLIC_KEY", "")
WEBHOOK_URL = os.getenv("MERCADO_PAGO_WEBHOOK_URL", "")
TEST_MODE = os.getenv("MERCADO_PAGO_TEST_MODE", "true").lower() == "true"

# Inicializar SDK
sdk = None
if ACCESS_TOKEN:
    try:
        sdk = mercadopago.SDK(ACCESS_TOKEN)
        logger.info(f"[MERCADOPAGO] SDK inicializado - Modo: {'TEST' if TEST_MODE else 'PRODUÇÃO'}")
    except Exception as e:
        logger.error(f"[MERCADOPAGO] Erro ao inicializar SDK: {e}")


def criar_pagamento_pix(
    valor: float,
    descricao: str,
    email_pagador: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Cria um pagamento PIX no Mercado Pago.
    
    Args:
        valor: Valor do pagamento em reais (ex: 0.01)
        descricao: Descrição do pagamento (ex: "Agendamento - Corte de Cabelo - 10/12/2025 às 14:00")
        email_pagador: Email do cliente
        metadata: Dados adicionais (chave_agendamento, chat_id, data, hora, servico_id)
    
    Returns:
        Dict com:
            - sucesso: bool
            - payment_id: str (ID do pagamento no MP)
            - qr_code: str (código PIX copia e cola)
            - qr_code_base64: str (imagem QR code em base64)
            - ticket_url: str (URL para visualizar o pagamento)
            - expira_em: str (data/hora de expiração)
            - mensagem: str (mensagem de erro se houver)
    """
    if not sdk:
        return {
            "sucesso": False,
            "mensagem": "Mercado Pago não configurado. Configure MERCADO_PAGO_ACCESS_TOKEN."
        }
    
    try:
        # Calcular expiração (30 minutos)
        expiracao = datetime.now() + timedelta(minutes=30)
        
        # Preparar dados do pagamento
        payment_data = {
            "transaction_amount": float(valor),
            "description": descricao,
            "payment_method_id": "pix",
            "payer": {
                "email": email_pagador,
                "first_name": metadata.get("cliente_nome", "Cliente") if metadata else "Cliente"
            },
            "notification_url": WEBHOOK_URL,
            "metadata": metadata or {},
            "date_of_expiration": expiracao.isoformat()
        }
        
        # Criar pagamento
        logger.info(f"[MERCADOPAGO] Criando pagamento PIX: R$ {valor:.2f} - {descricao}")
        response = sdk.payment().create(payment_data)
        
        if response["status"] == 200 or response["status"] == 201:
            payment = response["response"]
            payment_id = payment.get("id")
            
            # Extrair dados do PIX
            pix_data = payment.get("point_of_interaction", {}).get("transaction_data", {})
            qr_code = pix_data.get("qr_code", "")
            qr_code_base64 = pix_data.get("qr_code_base64", "")
            ticket_url = pix_data.get("ticket_url", "")
            
            logger.info(f"[MERCADOPAGO] Pagamento criado com sucesso: ID {payment_id}")
            
            return {
                "sucesso": True,
                "payment_id": str(payment_id),
                "qr_code": qr_code,
                "qr_code_base64": qr_code_base64,
                "ticket_url": ticket_url,
                "expira_em": expiracao.strftime("%d/%m/%Y %H:%M"),
                "status": payment.get("status", "pending"),
                "mensagem": "Pagamento PIX criado com sucesso"
            }
        else:
            erro = response.get("response", {})
            mensagem_erro = erro.get("message", "Erro desconhecido")
            logger.error(f"[MERCADOPAGO] Erro ao criar pagamento: {mensagem_erro}")
            
            return {
                "sucesso": False,
                "mensagem": f"Erro ao criar pagamento: {mensagem_erro}"
            }
    
    except Exception as e:
        logger.exception(f"[MERCADOPAGO] Exceção ao criar pagamento: {e}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao processar pagamento: {str(e)}"
        }


def verificar_status_pagamento(payment_id: str) -> Dict[str, Any]:
    """
    Verifica o status de um pagamento no Mercado Pago.
    
    Args:
        payment_id: ID do pagamento
    
    Returns:
        Dict com:
            - sucesso: bool
            - status: str (pending, approved, rejected, cancelled, etc.)
            - status_detail: str
            - mensagem: str
    """
    if not sdk:
        return {
            "sucesso": False,
            "status": "error",
            "mensagem": "Mercado Pago não configurado"
        }
    
    try:
        response = sdk.payment().get(payment_id)
        
        if response["status"] == 200:
            payment = response["response"]
            status = payment.get("status", "unknown")
            status_detail = payment.get("status_detail", "")
            
            logger.info(f"[MERCADOPAGO] Status do pagamento {payment_id}: {status}")
            
            return {
                "sucesso": True,
                "status": status,
                "status_detail": status_detail,
                "transaction_amount": payment.get("transaction_amount"),
                "date_approved": payment.get("date_approved"),
                "mensagem": f"Status: {status}"
            }
        else:
            return {
                "sucesso": False,
                "status": "error",
                "mensagem": "Pagamento não encontrado"
            }
    
    except Exception as e:
        logger.exception(f"[MERCADOPAGO] Erro ao verificar pagamento {payment_id}: {e}")
        return {
            "sucesso": False,
            "status": "error",
            "mensagem": f"Erro ao verificar pagamento: {str(e)}"
        }


def processar_webhook_notificacao(data: Dict) -> Dict[str, Any]:
    """
    Processa notificação de webhook do Mercado Pago.
    
    Args:
        data: Dados recebidos do webhook
    
    Returns:
        Dict com informações do pagamento processado
    """
    try:
        # Extrair dados da notificação
        action = data.get("action")
        notification_type = data.get("type")
        
        logger.info(f"[MERCADOPAGO] Webhook recebido - Tipo: {notification_type}, Ação: {action}")
        
        # Se é notificação de pagamento
        if notification_type == "payment":
            payment_id = data.get("data", {}).get("id")
            
            if payment_id:
                # Buscar detalhes do pagamento
                return verificar_status_pagamento(str(payment_id))
        
        return {
            "sucesso": False,
            "mensagem": f"Tipo de notificação não processada: {notification_type}"
        }
    
    except Exception as e:
        logger.exception(f"[MERCADOPAGO] Erro ao processar webhook: {e}")
        return {
            "sucesso": False,
            "mensagem": f"Erro ao processar webhook: {str(e)}"
        }


def cancelar_pagamento(payment_id: str) -> bool:
    """
    Cancela um pagamento pendente.
    
    Args:
        payment_id: ID do pagamento
    
    Returns:
        True se cancelado com sucesso
    """
    if not sdk:
        return False
    
    try:
        response = sdk.payment().update(payment_id, {"status": "cancelled"})
        
        if response["status"] == 200:
            logger.info(f"[MERCADOPAGO] Pagamento {payment_id} cancelado")
            return True
        else:
            logger.error(f"[MERCADOPAGO] Erro ao cancelar pagamento {payment_id}")
            return False
    
    except Exception as e:
        logger.exception(f"[MERCADOPAGO] Erro ao cancelar pagamento {payment_id}: {e}")
        return False


def formatar_mensagem_pix(dados_pagamento: Dict, agendamento_info: Dict) -> str:
    """
    Formata mensagem com dados do PIX para enviar ao cliente.
    
    Args:
        dados_pagamento: Dados retornados por criar_pagamento_pix()
        agendamento_info: Informações do agendamento (data, hora, serviço, valor)
    
    Returns:
        String formatada para WhatsApp
    """
    qr_code = dados_pagamento.get("qr_code", "")
    expira_em = dados_pagamento.get("expira_em", "")
    
    data = agendamento_info.get("data", "")
    hora = agendamento_info.get("hora", "")
    servico = agendamento_info.get("servico_nome", "Serviço")
    valor = agendamento_info.get("valor", 0.0)
    
    mensagem = f"""╔════════════════════════╗
  💰 *PAGAMENTO PIX*
╠════════════════════════╣

📅 *Agendamento:*
• Data: {data}
• Hora: {hora}
• Serviço: {servico}
• Valor: R$ {valor:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Como pagar:*
1. Abra o app do seu banco
2. Escolha "Pix Copia e Cola"
3. Cole o código abaixo
4. Confirme o pagamento

━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 *Código PIX:*
```{qr_code}```

━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ *Expira em:* {expira_em}

╚════════════════════════╝

⚠️ *Importante:*
• Pagamento confirmado em até 1 minuto
• Guarde este código para pagamento
• Após o pagamento, seu agendamento será confirmado automaticamente

💡 *Dúvidas?* Digite *ajuda*"""
    
    return mensagem.strip()
