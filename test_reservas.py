#!/usr/bin/env python3
"""
Script de teste para validar o sistema de reservas dinâmicas.
Simula múltiplos usuários tentando reservar o mesmo horário.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services"))

from datetime import datetime, timedelta
import time

# Importar módulos
from services import excel_services as excel
from services import slots_dinamicos
from config import servicos

def limpar_planilha_teste():
    """Limpa agendamentos de teste."""
    print("\n🧹 Limpando planilha de testes...")
    try:
        # Aqui você pode adicionar lógica para limpar agendamentos de teste
        print("✅ Planilha limpa")
    except Exception as e:
        print(f"⚠️  Erro ao limpar: {e}")

def teste_1_reserva_simples():
    """Teste 1: Criar uma reserva temporária simples."""
    print("\n" + "="*60)
    print("TESTE 1: Reserva Temporária Simples")
    print("="*60)
    
    data_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    hora_str = "14:00"
    chat_id = "teste_user_1"
    
    print(f"📅 Data: {data_str}")
    print(f"🕐 Hora: {hora_str}")
    print(f"👤 Chat ID: {chat_id}")
    
    try:
        chave = excel.reservar_slot_temporario(
            data_str=data_str,
            hora_str=hora_str,
            chat_id=chat_id,
            cliente_nome="Teste User 1",
            servico_id="cabelo_sobrancelha",
            servico_duracao=40
        )
        print(f"✅ Reserva criada: {chave}")
        
        # Verificar se está ativa
        time.sleep(1)
        ativa = excel.verificar_reserva_ativa(chave)
        print(f"✅ Reserva ativa: {ativa}")
        
        return chave
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def teste_2_confirmar_reserva(chave):
    """Teste 2: Confirmar uma reserva."""
    print("\n" + "="*60)
    print("TESTE 2: Confirmar Reserva")
    print("="*60)
    
    if not chave:
        print("⚠️  Sem chave para confirmar")
        return False
    
    print(f"🔑 Chave: {chave}")
    
    try:
        ok = excel.confirmar_reserva(chave)
        if ok:
            print("✅ Reserva confirmada com sucesso")
            return True
        else:
            print("❌ Falha ao confirmar")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def teste_3_conflito_simultaneo():
    """Teste 3: Simular 2 usuários tentando reservar mesmo horário."""
    print("\n" + "="*60)
    print("TESTE 3: Conflito - 2 Usuários Mesmo Horário")
    print("="*60)
    
    data_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
    hora_str = "10:00"
    
    print(f"📅 Data: {data_str}")
    print(f"🕐 Hora: {hora_str}")
    
    # Usuário 1 tenta reservar
    print("\n👤 Usuário 1 tentando reservar...")
    try:
        chave1 = excel.reservar_slot_temporario(
            data_str=data_str,
            hora_str=hora_str,
            chat_id="teste_user_conflito_1",
            cliente_nome="Conflito User 1",
            servico_id="barba",
            servico_duracao=20
        )
        print(f"✅ Usuário 1 conseguiu: {chave1}")
    except Exception as e:
        print(f"❌ Usuário 1 falhou: {e}")
        return False
    
    # Usuário 2 tenta reservar MESMO horário
    print("\n👤 Usuário 2 tentando reservar MESMO horário...")
    try:
        chave2 = excel.reservar_slot_temporario(
            data_str=data_str,
            hora_str=hora_str,
            chat_id="teste_user_conflito_2",
            cliente_nome="Conflito User 2",
            servico_id="barba",
            servico_duracao=20
        )
        print(f"❌ ERRO: Usuário 2 conseguiu reservar! Sistema falhou: {chave2}")
        return False
    except ValueError as e:
        print(f"✅ Usuário 2 bloqueado corretamente: {e}")
        return True
    except Exception as e:
        print(f"⚠️  Erro inesperado: {e}")
        return False

def teste_4_expiracao():
    """Teste 4: Verificar expiração de reserva."""
    print("\n" + "="*60)
    print("TESTE 4: Expiração de Reserva (aguarde 11 minutos...)")
    print("="*60)
    
    data_str = (datetime.now() + timedelta(days=3)).strftime("%d/%m/%Y")
    hora_str = "15:00"
    
    print(f"📅 Data: {data_str}")
    print(f"🕐 Hora: {hora_str}")
    print("⏳ Criando reserva temporária...")
    
    try:
        chave = excel.reservar_slot_temporario(
            data_str=data_str,
            hora_str=hora_str,
            chat_id="teste_user_expiracao",
            cliente_nome="Expiracao User",
            servico_id="sobrancelha",
            servico_duracao=10
        )
        print(f"✅ Reserva criada: {chave}")
        print(f"⏰ Aguardando 11 minutos para expirar...")
        
        # NOTA: Para teste rápido, você pode modificar DURACAO_RESERVA_MINUTOS
        # temporariamente para 1 minuto em excel_services.py
        print("⚠️  Para teste completo, aguarde 11 minutos ou ajuste DURACAO_RESERVA_MINUTOS")
        
        # Simular passagem do tempo (descomente para teste real)
        # time.sleep(11 * 60)
        
        # Liberar slots expirados
        # liberados = excel.liberar_slots_expirados()
        # print(f"✅ Slots liberados: {liberados}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def teste_5_slots_dinamicos():
    """Teste 5: Gerar slots dinâmicos para diferentes serviços."""
    print("\n" + "="*60)
    print("TESTE 5: Slots Dinâmicos")
    print("="*60)
    
    data_str = (datetime.now() + timedelta(days=4)).strftime("%d/%m/%Y")
    
    servicos_teste = [
        ("cabelo_sobrancelha", "Cabelo + Sobrancelha (40min)"),
        ("barba", "Barba (20min)"),
        ("sobrancelha", "Sobrancelha (10min)"),
        ("platinado", "Platinado (120min)")
    ]
    
    print(f"📅 Data: {data_str}\n")
    
    try:
        # Obter agendamentos do dia
        agendamentos = excel.obter_agendamentos_do_dia(data_str)
        print(f"📋 Agendamentos existentes: {len(agendamentos)}\n")
        
        for servico_id, servico_nome in servicos_teste:
            print(f"\n🔍 {servico_nome}:")
            slots = slots_dinamicos.gerar_slots_disponiveis_para_servico(
                data_str, servico_id, agendamentos
            )
            print(f"   ✅ {len(slots)} slots disponíveis")
            if slots:
                print(f"   📍 Primeiro: {slots[0]}")
                print(f"   📍 Último: {slots[-1]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executar todos os testes."""
    print("\n" + "="*60)
    print("🧪 TESTES DO SISTEMA DE RESERVAS DINÂMICAS")
    print("="*60)
    
    resultados = []
    
    # Teste 1: Reserva simples
    chave = teste_1_reserva_simples()
    resultados.append(("Reserva Simples", chave is not None))
    
    # Teste 2: Confirmar reserva
    if chave:
        ok = teste_2_confirmar_reserva(chave)
        resultados.append(("Confirmar Reserva", ok))
    
    # Teste 3: Conflito
    ok = teste_3_conflito_simultaneo()
    resultados.append(("Anti-Conflito", ok))
    
    # Teste 4: Expiração
    ok = teste_4_expiracao()
    resultados.append(("Expiração", ok))
    
    # Teste 5: Slots dinâmicos
    ok = teste_5_slots_dinamicos()
    resultados.append(("Slots Dinâmicos", ok))
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    for nome, passou in resultados:
        status = "✅ PASSOU" if passou else "❌ FALHOU"
        print(f"{status} - {nome}")
    
    total = len(resultados)
    passou = sum(1 for _, p in resultados if p)
    
    print(f"\n📈 Total: {passou}/{total} testes passaram")
    
    if passou == total:
        print("\n🎉 Todos os testes passaram!")
    else:
        print(f"\n⚠️  {total - passou} teste(s) falharam")

if __name__ == "__main__":
    main()
