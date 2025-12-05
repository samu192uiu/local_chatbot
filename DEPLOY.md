# 🚀 Deploy - Barbearia Veinho Corts

Instruções para colocar o chatbot em produção.

---

## 📋 Pré-requisitos

- [ ] Docker e Docker Compose instalados
- [ ] WhatsApp Business API (WAHA) configurado
- [ ] Número de WhatsApp Business ativo
- [ ] Servidor/VPS com:
  - 2GB RAM mínimo
  - 10GB disco
  - Ubuntu 20.04+ ou similar

---

## 🔧 Passo 1: Configurar Variáveis de Ambiente

Crie `.env` na raiz do projeto:

```bash
# WhatsApp/WAHA
WAHA_API_URL=http://waha:3000
WAHA_SESSION=default
WAHA_API_KEY=sua_chave_secreta_aqui

# Admin (substitua pelo seu número)
ADMIN_CHAT_IDS=5511999999999@c.us
ADMIN_TOKEN=token_admin_super_secreto

# Arquivos
AGENDAMENTOS_XLSX=/app/data/cliente_barbearia/agendamentos.xlsx
CLIENTES_XLSX=/app/data/clientes.xlsx

# Segurança
PIN_SALT=salt_super_secreto_mude_isto
REQUIRE_CHATID_BIND=true

# Ambiente
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

### ⚠️ IMPORTANTE
- **Altere** `WAHA_API_KEY` para uma chave única
- **Altere** `ADMIN_TOKEN` para um token seguro
- **Altere** `PIN_SALT` para um salt único
- **Altere** `ADMIN_CHAT_IDS` para seu WhatsApp real

---

## 🐳 Passo 2: Docker Compose

Verifique o `docker-compose.yml`:

```yaml
version: '3.8'

services:
  waha:
    image: devlikeapro/waha
    container_name: waha
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - WAHA_SESSION=default
    volumes:
      - waha_data:/app/.waha

  chatbot-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: chatbot-api
    restart: unless-stopped
    ports:
      - "5000:5000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./tenants:/app/tenants
    depends_on:
      - waha

volumes:
  waha_data:
```

---

## 🚀 Passo 3: Executar

### Primeira vez

```bash
# 1. Clonar/copiar projeto para servidor
git clone <seu-repo> /opt/barbearia-bot
cd /opt/barbearia-bot

# 2. Criar .env com suas configurações
nano .env

# 3. Criar pastas necessárias
mkdir -p data/cliente_barbearia
chmod -R 755 data

# 4. Build e start
docker-compose up -d --build

# 5. Verificar logs
docker-compose logs -f
```

### Atualizações posteriores

```bash
cd /opt/barbearia-bot
git pull
docker-compose down
docker-compose up -d --build
```

---

## 📱 Passo 4: Configurar WhatsApp

### 4.1. Acessar WAHA

```bash
# Abrir no navegador
http://seu-servidor:3000
```

### 4.2. Escanear QR Code

1. Acesse a interface WAHA
2. Escaneie o QR Code com WhatsApp
3. Aguarde conexão estabelecer

### 4.3. Configurar Webhook

No painel WAHA, configure:

```
Webhook URL: http://chatbot-api:5000/webhook
Events: message
```

Ou via API:

```bash
curl -X POST http://seu-servidor:3000/api/sessions/default/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://chatbot-api:5000/webhook",
    "events": ["message"]
  }'
```

---

## 🔐 Passo 5: Segurança

### 5.1. Firewall

```bash
# Permitir apenas portas necessárias
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (se usar Nginx)
sudo ufw allow 443/tcp   # HTTPS (se usar Nginx)
sudo ufw enable
```

### 5.2. Nginx (Opcional - para HTTPS)

```nginx
# /etc/nginx/sites-available/barbearia-bot

server {
    listen 80;
    server_name bot.barbearia.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Ativar SSL com Let's Encrypt:

```bash
sudo certbot --nginx -d bot.barbearia.com
```

### 5.3. Backup Automático

Crie script `/opt/backup-barbearia.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/barbearia"

mkdir -p $BACKUP_DIR

# Backup das planilhas
cp -r /opt/barbearia-bot/data $BACKUP_DIR/data_$DATE

# Manter apenas últimos 7 dias
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

echo "Backup concluído: $DATE"
```

Adicionar ao crontab:

```bash
# Executar diariamente às 2h da manhã
crontab -e

0 2 * * * /opt/backup-barbearia.sh
```

---

## 📊 Passo 6: Monitoramento

### 6.1. Logs

```bash
# Ver logs em tempo real
docker-compose logs -f chatbot-api

# Ver últimas 100 linhas
docker-compose logs --tail=100 chatbot-api

# Logs de todos os serviços
docker-compose logs -f
```

### 6.2. Status

```bash
# Verificar containers rodando
docker-compose ps

# Verificar uso de recursos
docker stats
```

### 6.3. Health Check

Criar endpoint de health:

```bash
curl http://localhost:5000/health
```

---

## 🔄 Passo 7: Manutenção

### Reiniciar serviço

```bash
docker-compose restart chatbot-api
```

### Limpar logs antigos

```bash
# Limpar logs do Docker
docker system prune -a --volumes
```

### Atualizar dependências

```bash
cd /opt/barbearia-bot
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 🐛 Troubleshooting

### Problema: Container não inicia

```bash
# Ver logs detalhados
docker-compose logs chatbot-api

# Verificar se porta está em uso
sudo netstat -tulpn | grep 5000

# Recriar container
docker-compose down
docker-compose up -d --force-recreate
```

### Problema: WhatsApp desconecta

```bash
# Reconectar WAHA
docker-compose restart waha

# Ver logs
docker-compose logs waha

# Escanear QR Code novamente
# Acessar http://seu-servidor:3000
```

### Problema: Mensagens não chegam

```bash
# Verificar webhook
curl http://localhost:5000/webhook

# Verificar conectividade entre containers
docker exec chatbot-api ping waha

# Verificar logs do WAHA
docker-compose logs waha
```

### Problema: Planilha corrompida

```bash
# Restaurar do backup
cp /opt/backups/barbearia/data_YYYYMMDD/clientes.xlsx \
   /opt/barbearia-bot/data/

# Reiniciar
docker-compose restart chatbot-api
```

---

## 📈 Passo 8: Otimizações

### 8.1. Performance

No `docker-compose.yml`, adicionar limites:

```yaml
services:
  chatbot-api:
    # ... outras configs
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 8.2. Persistência

Garantir volumes persistentes:

```yaml
volumes:
  - ./data:/app/data:rw
  - ./config:/app/config:ro  # read-only
```

---

## ✅ Checklist de Deploy

- [ ] `.env` configurado com valores reais
- [ ] ADMIN_CHAT_IDS com seu WhatsApp
- [ ] Senhas/tokens alterados
- [ ] Docker e Docker Compose instalados
- [ ] Containers iniciados com sucesso
- [ ] WhatsApp conectado e QR Code escaneado
- [ ] Webhook configurado
- [ ] Firewall configurado
- [ ] Backup automático configurado
- [ ] Testado envio de mensagem
- [ ] Testado recebimento de resposta
- [ ] Logs verificados (sem erros)
- [ ] Menu principal funcionando
- [ ] Agendamento funcionando
- [ ] Pagamento funcionando
- [ ] Atendimento humano funcionando

---

## 📞 Suporte

### Comandos úteis

```bash
# Status completo
docker-compose ps && docker-compose logs --tail=50

# Restart completo
docker-compose down && docker-compose up -d

# Rebuild completo
docker-compose down && docker-compose build --no-cache && docker-compose up -d

# Backup manual
tar -czf backup_$(date +%Y%m%d).tar.gz data/

# Monitorar em tempo real
watch -n 5 'docker-compose ps'
```

---

## 🎉 Deploy Concluído!

Seu chatbot está pronto para receber clientes!

**Próximos passos:**
1. Divulgar número do WhatsApp
2. Monitorar primeiros atendimentos
3. Ajustar conforme feedback
4. Adicionar mais funcionalidades

---

**Desenvolvido por:** Samuel  
**Versão:** 1.0 - Barbearia  
**Última atualização:** Dezembro 2025
