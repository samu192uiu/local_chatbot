#!/usr/bin/env python3
"""
Teste de Sistema Anti-Conflito
Simula múltiplos clientes tentando agendar o mesmo horário simultaneamente.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from datetime import datetime, timedelta
import services.excel_services as excel
import threading
import time

# Configurar ambiente de teste
os.environ['AGENDAMENTOS_XLSX'] = '/opt/barbearia-bot/services/agendamentos.xlsx'

def limpar_teste():
    """Limpa agendamentos de teste."""
    print("🧹 Limpando agendamentos de teste...")
    try:
        import openpyxl
        wb = openpyxl.load_workbook('/opt/barbearia-bot/services/agendamentos.xlsx')
        ws = wb.active
        
        # Deletar todas as linhas exceto cabeçalho
        for _ in range(ws.max_row - 1):
            ws.delete_rows(2)
        
        wb.save('/opt/barbearia-bot/services/agendamentos.xlsx')
        wb.close()
        print("✅ Agendamentos limpos\n")
    except Exception as e:
        print(f"❌ Erro ao limpar: {e}\n")

def testar_reserva_simultanea():
    """Testa 3 clientes tentando reservar o mesmo horário ao mesmo tempo."""
    print("=" * 60)
    print("🧪 TESTE: Reserva Simultânea do Mesmo Horário")
    print("=" * 60)
    
    # Dados do teste
    amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    horario = "08:00"
    
    clientes = [
        {"chat_id": "5511111111111@c.us", "nome": "Cliente A", "servico": "barba"},
        {"chat_id": "5511222222222@c.us", "nome": "Cliente B", "servico": "barba"},
        {"chat_id": "5511333333333@c.us", "nome": "Cliente C", "servico": "barba"},
    ]
    
    resultados = {}
    
    def reservar_cliente(cliente):
        """Função executada por cada thread."""
        chat_id = cliente["chat_id"]
        nome = cliente["nome"]
        
        print(f"⏳ {nome} tentando reservar {horario}...")
        
        resultado = excel.reservar_slot_temporario(
            data_str=amanha,
            hora_str=horario,
            chat_id=chat_id,
            servico_id=cliente["servico"],
            servico_duracao=20,
            cliente_nome=nome
        )
        
        resultados[chat_id] = resultado
        
        if resultado["sucesso"]:
            print(f"✅ {nome}: RESERVADO! Expira em {resultado['expira_em']}")
        else:
            print(f"❌ {nome}: FALHOU - {resultado['mensagem']}")
    
    # Criar threads para simular requisições simultâneas
    threads = []
    for cliente in clientes:
        t = threading.Thread(target=reservar_cliente, args=(cliente,))
        threads.append(t)
    
    # Iniciar todas as threads ao mesmo tempo
    print(f"\n🚀 Iniciando 3 reservas simultâneas para {amanha} às {horario}...\n")
    for t in threads:
        t.start()
    
    # Aguardar todas terminarem
    for t in threads:
        t.join()
    
    # Análise dos resultados
    print("\n" + "=" * 60)
    print("📊 RESULTADO DO TESTE")
    print("=" * 60)
    
    sucessos = sum(1 for r in resultados.values() if r["sucesso"])
    falhas = sum(1 for r in resultados.values() if not r["sucesso"])
    
    print(f"✅ Reservas bem-sucedidas: {sucessos}")
    print(f"❌ Reservas bloqueadas: {falhas}")
    
    if sucessos == 1 and falhas == 2:
        print("\n🎉 TESTE PASSOU! Sistema anti-conflito funcionando corretamente!")
        print("   ✓ Apenas 1 cliente conseguiu reservar")
        print("   ✓ Os outros 2 foram bloqueados")
        return True
    else:
        print("\n⚠️  TESTE FALHOU! Esperado: 1 sucesso e 2 falhas")
        return False

def testar_expiracao_reserva():
    """Testa se reservas expiram corretamente."""
    print("\n" + "=" * 60)
    print("🧪 TESTE: Expiração de Reservas")
    print("=" * 60)
    
    amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    horario = "09:00"
    
    print(f"⏳ Criando reserva com expiração de 1 segundo...")
    
    resultado = excel.reservar_slot_temporario(
        data_str=amanha,
        hora_str=horario,
        chat_id="5511999999999@c.us",
        servico_id="barba",
        servico_duracao=20,
        cliente_nome="Cliente Teste Expiração",
        duracao_reserva_min=0.016  # ~1 segundo
    )
    
    if not resultado["sucesso"]:
        print(f"❌ Falha ao criar reserva: {resultado['mensagem']}")
        return False
    
    print(f"✅ Reserva criada: {resultado['chave']}")
    print(f"⏰ Aguardando 2 segundos para expirar...")
    time.sleep(2)
    
    print(f"🔄 Executando limpeza de reservas expiradas...")
    liberados = excel.liberar_slots_expirados()
    
    print(f"\n📊 Slots liberados: {liberados}")
    
    if liberados > 0:
        print("\n🎉 TESTE PASSOU! Reserva expirou corretamente!")
        return True
    else:
        print("\n⚠️  TESTE FALHOU! Reserva não expirou")
        return False

def testar_slot_ainda_reservado():
    """Testa verificação de reserva ativa."""
    print("\n" + "=" * 60)
    print("🧪 TESTE: Verificação de Reserva Ativa")
    print("=" * 60)
    
    amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    horario = "10:00"
    chat_id = "5511888888888@c.us"
    
    print(f"⏳ Criando reserva com 10 minutos de validade...")
    
    resultado = excel.reservar_slot_temporario(
        data_str=amanha,
        hora_str=horario,
        chat_id=chat_id,
        servico_id="barba",
        servico_duracao=20,
        cliente_nome="Cliente Teste Verificação"
    )
    
    if not resultado["sucesso"]:
        print(f"❌ Falha ao criar reserva")
        return False
    
    print(f"✅ Reserva criada")
    
    print(f"🔍 Verificando se reserva está ativa...")
    ativa = excel.verificar_reserva_ativa(amanha, horario, chat_id)
    
    if ativa:
        print("✅ Reserva detectada como ATIVA")
        print("\n🎉 TESTE PASSOU! Verificação funcionando!")
        return True
    else:
        print("❌ Reserva NÃO foi detectada")
        print("\n⚠️  TESTE FALHOU!")
        return False

def main():
    print("\n" + "🧪" * 30)
    print("  TESTE DE SISTEMA ANTI-CONFLITO  ")
    print("🧪" * 30 + "\n")
    
    # Limpar antes de testar
    limpar_teste()
    
    # Executar testes
    testes_passados = 0
    total_testes = 3
    
    if testar_reserva_simultanea():
        testes_passados += 1
    
    if testar_expiracao_reserva():
        testes_passados += 1
    
    if testar_slot_ainda_reservado():
        testes_passados += 1
    
    # Resultado final
    print("\n" + "=" * 60)
    print("📈 RESUMO FINAL")
    print("=" * 60)
    print(f"Testes executados: {total_testes}")
    print(f"Testes passados: {testes_passados}")
    print(f"Testes falhados: {total_testes - testes_passados}")
    
    if testes_passados == total_testes:
        print("\n🎉🎉🎉 TODOS OS TESTES PASSARAM! 🎉🎉🎉")
        print("✅ Sistema anti-conflito está funcionando perfeitamente!")
        return 0
    else:
        print(f"\n⚠️  {total_testes - testes_passados} teste(s) falharam")
        print("❌ Revisar implementação necessário")
        return 1

if __name__ == "__main__":
    exit(main())
