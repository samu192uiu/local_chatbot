# 🛠️ Comandos Úteis - Administração

## 📦 Gerenciamento de Containers

### Ver status dos containers
```bash
docker ps
```

### Ver logs em tempo real
```bash
# Bot API
docker logs wpp_bot_api -f

# WAHA
docker logs wpp_bot_waha -f

# Filtrar por palavra-chave
docker logs wpp_bot_api -f | grep -i lembrete
docker logs wpp_bot_api -f | grep -i erro
```

### Reiniciar containers
```bash
cd /opt/barbearia-bot
docker-compose restart
```

### Reconstruir após mudanças no código
```bash
cd /opt/barbearia-bot
docker-compose down
docker-compose up -d --build
```

---

## 🔔 Sistema de Lembretes

### Verificar se está rodando
```bash
docker logs wpp_bot_api | grep -i "Sistema de lembretes"
```

**Saída esperada:**
```
✅ Sistema de lembretes automáticos iniciado
```

### Testar lembretes manualmente
```bash
docker exec -it wpp_bot_api python << EOF
from services import reminders
reminders.testar_lembretes_manual()
EOF
```

### Ver histórico de lembretes enviados
```bash
docker exec wpp_bot_api python -c "
from services import excel_services as es
from openpyxl import load_workbook

wb = load_workbook('/app/data/agendamentos.xlsx')
ws = wb['Agendamentos']

print('📊 Agendamentos com lembretes enviados:\n')
for r in range(2, ws.max_row + 1):
    lembrete = ws.cell(row=r, column=13).value  # Coluna LembreteEnviado
    if lembrete:
        nome = ws.cell(row=r, column=6).value
        data = ws.cell(row=r, column=2).value
        hora = ws.cell(row=r, column=3).value
        print(f'  {nome} - {data} {hora} → {lembrete}')
"
```

### Parar sistema de lembretes
```bash
docker exec -it wpp_bot_api python << EOF
from services import reminders
reminders.parar_lembretes()
EOF
```

---

## 🗓️ Gerenciamento de Feriados

### Ver feriados cadastrados
```bash
cat /opt/barbearia-bot/config/feriados.json
```

### Adicionar novo feriado
```bash
# Editar arquivo
nano /opt/barbearia-bot/config/feriados.json

# Adicionar na lista "feriados":
# "DD/MM/AAAA"

# Exemplo: Adicionar 01/05/2027
# "01/05/2027",

# Não precisa reiniciar - arquivo é lido dinamicamente
```

### Testar se data é feriado
```bash
docker exec wpp_bot_api python -c "
from services import excel_services as es
data = '25/12/2026'
print(f'A data {data} é feriado?', es.eh_feriado(data))
"
```

---

## 📊 Consultas de Dados

### Total de clientes cadastrados
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
print(f'Total de clientes: {cs.count_clients()}')
"
```

### Listar todos os clientes
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
clientes = cs.list_all_clients(limit=100)
for c in clientes:
    print(f\"{c.get('Nome', 'N/A'):30} | CPF: {c.get('CPF', 'N/A'):11} | Tel: {c.get('Telefone', 'N/A')}\")
"
```

### Buscar cliente por CPF
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
cpf = '12345678900'  # Substituir pelo CPF desejado
cliente = cs.get_client_by_cpf(cpf)
if cliente:
    print('Cliente encontrado:')
    for k, v in cliente.items():
        print(f'  {k}: {v}')
else:
    print('Cliente não encontrado')
"
```

### Ver histórico de um cliente
```bash
docker exec wpp_bot_api python -c "
from services import excel_services as es
cpf = '12345678900'  # Substituir pelo CPF
historico = es.buscar_historico_completo(cpf)
print(f'Total de agendamentos: {len(historico)}\n')
for ag in historico:
    print(f\"{ag.get('Data')} {ag.get('Hora')} - Status: {ag.get('Status')}\")
"
```

### Contar agendamentos por status
```bash
docker exec wpp_bot_api python -c "
from openpyxl import load_workbook
from collections import Counter

wb = load_workbook('/app/data/agendamentos.xlsx')
ws = wb['Agendamentos']

statuses = []
for r in range(2, ws.max_row + 1):
    status = ws.cell(row=r, column=9).value or 'Desconhecido'
    statuses.append(status.strip())

contador = Counter(statuses)
print('📊 Agendamentos por status:\n')
for status, count in contador.most_common():
    print(f'  {status:20}: {count}')
"
```

---

## 🔒 Segurança e PIN

### Verificar clientes bloqueados
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
from openpyxl import load_workbook

wb = load_workbook('/app/data/clientes.xlsx')
ws = wb.active

print('🔒 Clientes com bloqueio ativo:\n')
bloqueados = 0
for r in range(2, ws.max_row + 1):
    cpf = str(ws.cell(row=r, column=2).value or '').strip()
    if cpf and cs.esta_bloqueado(cpf):
        nome = ws.cell(row=r, column=3).value
        bloqueado_ate = ws.cell(row=r, column=13).value
        print(f'  {nome} (CPF: {cpf}) - Até: {bloqueado_ate}')
        bloqueados += 1

if bloqueados == 0:
    print('  Nenhum cliente bloqueado')
"
```

### Resetar tentativas de PIN de um cliente
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
cpf = '12345678900'  # Substituir pelo CPF
cs.resetar_tentativas_pin(cpf)
print(f'✅ Tentativas de PIN resetadas para CPF: {cpf}')
"
```

### Alterar PIN de um cliente (admin)
```bash
docker exec wpp_bot_api python -c "
from services import clientes_services as cs
cpf = '12345678900'  # Substituir
novo_pin = '1234'    # Substituir
sucesso = cs.set_pin_for_cpf(cpf, novo_pin)
print(f'✅ PIN alterado: {sucesso}')
"
```

---

## 📋 Backup e Restauração

### Backup dos dados
```bash
# Criar diretório de backup
mkdir -p /opt/barbearia-bot/backups

# Backup com data
DATE=$(date +%Y%m%d_%H%M%S)
docker cp wpp_bot_api:/app/data/agendamentos.xlsx \
  /opt/barbearia-bot/backups/agendamentos_$DATE.xlsx

docker cp wpp_bot_api:/app/data/clientes.xlsx \
  /opt/barbearia-bot/backups/clientes_$DATE.xlsx

echo "✅ Backup criado em /opt/barbearia-bot/backups/"
```

### Restaurar backup
```bash
# Listar backups disponíveis
ls -lh /opt/barbearia-bot/backups/

# Restaurar (substituir YYYYMMDD_HHMMSS pela data desejada)
docker cp /opt/barbearia-bot/backups/agendamentos_YYYYMMDD_HHMMSS.xlsx \
  wpp_bot_api:/app/data/agendamentos.xlsx

docker cp /opt/barbearia-bot/backups/clientes_YYYYMMDD_HHMMSS.xlsx \
  wpp_bot_api:/app/data/clientes.xlsx

# Reiniciar container
docker-compose restart
```

### Backup automático (cron)
```bash
# Editar crontab
crontab -e

# Adicionar linha (backup diário às 3h da manhã)
0 3 * * * /opt/barbearia-bot/scripts/backup.sh

# Criar script de backup
cat > /opt/barbearia-bot/scripts/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/opt/barbearia-bot/backups
mkdir -p $BACKUP_DIR

docker cp wpp_bot_api:/app/data/agendamentos.xlsx $BACKUP_DIR/agendamentos_$DATE.xlsx
docker cp wpp_bot_api:/app/data/clientes.xlsx $BACKUP_DIR/clientes_$DATE.xlsx

# Manter apenas últimos 30 backups
cd $BACKUP_DIR
ls -t agendamentos_*.xlsx | tail -n +31 | xargs -r rm
ls -t clientes_*.xlsx | tail -n +31 | xargs -r rm

echo "$(date): Backup criado" >> $BACKUP_DIR/backup.log
EOF

chmod +x /opt/barbearia-bot/scripts/backup.sh
```

---

## 🐛 Debugging

### Ver todos os estados ativos
```bash
docker exec wpp_bot_api python -c "
from zapwaha.state.memory import state_manager
estados = state_manager._states if hasattr(state_manager, '_states') else {}
print(f'Total de sessões ativas: {len(estados)}\n')
for chat_id, state in list(estados.items())[:10]:
    print(f'{chat_id}: {state}')
"
```

### Limpar estados (resetar todas as sessões)
```bash
docker exec wpp_bot_api python -c "
from zapwaha.state.memory import state_manager
if hasattr(state_manager, '_states'):
    state_manager._states.clear()
if hasattr(state_manager, '_data'):
    state_manager._data.clear()
print('✅ Estados limpos')
"
```

### Testar envio de mensagem
```bash
docker exec wpp_bot_api python -c "
from src.zapwaha.web.webhooks import _send
chat_id = '5511999999999@c.us'  # Substituir pelo número
_send(chat_id, '🧪 Teste de mensagem - Sistema OK!')
"
```

---

## 📊 Monitoramento

### Recursos do container
```bash
docker stats wpp_bot_api --no-stream
```

### Espaço em disco
```bash
# Tamanho dos dados
docker exec wpp_bot_api du -sh /app/data/

# Detalhes
docker exec wpp_bot_api ls -lh /app/data/
```

### Saúde do sistema
```bash
curl http://localhost:5000/healthz
```

**Resposta esperada:**
```json
{"ok":true,"session":"default"}
```

---

## 🔄 Atualizações

### Atualizar código
```bash
cd /opt/barbearia-bot
git pull  # Se usando Git

# Ou editar arquivos manualmente
nano src/zapwaha/flows/agendamento.py

# Reconstruir
docker-compose down
docker-compose up -d --build
```

### Adicionar nova dependência
```bash
# Editar requirements.txt
nano requirements.txt

# Adicionar linha
# nome-pacote==versao

# Reconstruir
docker-compose down
docker-compose up -d --build
```

---

## 📞 Comandos de Emergência

### Reiniciar tudo rapidamente
```bash
cd /opt/barbearia-bot && docker-compose restart
```

### Reconstruir do zero
```bash
cd /opt/barbearia-bot
docker-compose down -v  # ⚠️ CUIDADO: Remove volumes
docker-compose up -d --build
```

### Ver erros recentes
```bash
docker logs wpp_bot_api --tail 50 | grep -i error
```

### Acessar container interativamente
```bash
docker exec -it wpp_bot_api bash

# Dentro do container
python
>>> from services import reminders
>>> # testar coisas
>>> exit()
exit
```

---

## 📝 Logs Úteis

### Ver quando lembretes foram enviados
```bash
docker logs wpp_bot_api | grep "Lembrete.*enviado"
```

### Ver agendamentos criados
```bash
docker logs wpp_bot_api | grep "Agendamento.*Confirmado"
```

### Ver acessos à área do cliente
```bash
docker logs wpp_bot_api | grep "Área do Cliente"
```

---

## 💡 Dicas

1. **Sempre faça backup** antes de modificar dados
2. **Teste em horário de baixo movimento**
3. **Monitore os logs** após mudanças
4. **Documente alterações** em `CHANGELOG_BARBEARIA.md`
5. **Mantenha requirements.txt atualizado**

---

**Última atualização:** 05/12/2025  
**Versão do Sistema:** 2.0.0 - Área do Cliente + Lembretes
