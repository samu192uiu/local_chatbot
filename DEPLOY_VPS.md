# 🚀 Deploy do Bot na VPS

## 📋 Pré-requisitos na VPS

1. **Ubuntu/Debian** (recomendado) ou CentOS
2. **Docker** e **Docker Compose** instalados
3. **Porta 3000 e 5000** liberadas no firewall
4. **Acesso SSH** à VPS

---

## 🔧 Passo 1: Preparar a VPS

### 1.1 Conectar via SSH
```bash
ssh root@SEU_IP_DA_VPS
# ou
ssh usuario@SEU_IP_DA_VPS
```

### 1.2 Atualizar sistema
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Instalar Docker
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adicionar seu usuário ao grupo docker (opcional)
sudo usermod -aG docker $USER

# Verificar instalação
docker --version
```

### 1.4 Instalar Docker Compose
```bash
# Versão mais recente
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão de execução
sudo chmod +x /usr/local/bin/docker-compose

# Verificar instalação
docker-compose --version
```

---

## 📦 Passo 2: Transferir arquivos para VPS

### Opção A: Via Git (Recomendado)

```bash
# Na VPS
cd /home/seu-usuario
git clone https://github.com/samu192uiu/local_chatbot.git
cd local_chatbot
```

### Opção B: Via SCP (do seu PC)

```powershell
# No seu PC (PowerShell)
scp -r "C:\Users\samue\OneDrive\Desktop\veinho corts" usuario@SEU_IP:/home/usuario/chatbot-barbearia
```

### Opção C: Via FTP/SFTP
Use **FileZilla** ou **WinSCP** para transferir os arquivos.

---

## ⚙️ Passo 3: Configurar na VPS

### 3.1 Criar diretórios de dados
```bash
cd /home/usuario/chatbot-barbearia
mkdir -p data
mkdir -p tenants/cliente_barbearia/templates/pt-BR
```

### 3.2 Verificar arquivo .env
```bash
cat .env
```

Deve conter:
```env
WAHA_API_KEY=barbearia2025_api_key_fixa
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=1234
WHATSAPP_SWAGGER_USERNAME=admin
WHATSAPP_SWAGGER_PASSWORD=1234
```

### 3.3 Ajustar permissões
```bash
chmod -R 755 .
chmod 644 .env
```

---

## 🐳 Passo 4: Iniciar containers

### 4.1 Build e start
```bash
docker-compose up -d --build
```

### 4.2 Verificar logs
```bash
# Logs do WAHA (WhatsApp)
docker logs wpp_bot_waha --tail=50 -f

# Logs da API
docker logs wpp_bot_api --tail=50 -f
```

### 4.3 Verificar containers rodando
```bash
docker ps
```

Você deve ver:
- `wpp_bot_waha` (porta 3000)
- `wpp_bot_api` (porta 5000)

---

## 📱 Passo 5: Conectar WhatsApp

### 5.1 Ver QR Code
```bash
docker logs wpp_bot_waha --tail=100
```

Você verá um **QR Code ASCII** nos logs.

### 5.2 Escanear QR Code
1. Abra WhatsApp no celular
2. Menu → **Aparelhos conectados**
3. **Conectar um aparelho**
4. Escaneie o QR Code

### 5.3 Confirmar conexão
```bash
docker logs wpp_bot_waha | grep "authenticated"
```

Deve aparecer: `Session has been authenticated!`

---

## 🔒 Passo 6: Configurar Firewall

### 6.1 Ubuntu/Debian (UFW)
```bash
# Permitir SSH
sudo ufw allow 22/tcp

# Permitir portas do bot (opcional - apenas se precisar acessar externamente)
sudo ufw allow 3000/tcp
sudo ufw allow 5000/tcp

# Ativar firewall
sudo ufw enable

# Verificar status
sudo ufw status
```

### 6.2 CentOS/RHEL (firewalld)
```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

**⚠️ IMPORTANTE:** Se você não vai acessar o WAHA dashboard ou API de fora, **NÃO** abra as portas 3000 e 5000 no firewall. O WhatsApp se conecta de dentro do container.

---

## 🔄 Comandos úteis para gerenciar

### Parar containers
```bash
docker-compose down
```

### Reiniciar containers
```bash
docker-compose restart
```

### Ver logs em tempo real
```bash
docker-compose logs -f
```

### Atualizar código
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Limpar volumes (CUIDADO: apaga dados!)
```bash
docker-compose down -v
```

---

## 🌐 Passo 7: Domínio e SSL (Opcional)

Se quiser acessar o dashboard do WAHA via domínio (ex: `waha.seubarbearia.com`):

### 7.1 Instalar Nginx
```bash
sudo apt install nginx -y
```

### 7.2 Configurar reverse proxy
```bash
sudo nano /etc/nginx/sites-available/waha
```

Adicione:
```nginx
server {
    listen 80;
    server_name waha.seubarbearia.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 7.3 Ativar site
```bash
sudo ln -s /etc/nginx/sites-available/waha /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7.4 Instalar SSL (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d waha.seubarbearia.com
```

---

## 📊 Monitoramento

### Ver uso de recursos
```bash
docker stats
```

### Ver espaço em disco
```bash
df -h
du -sh /var/lib/docker
```

### Logs do sistema
```bash
journalctl -u docker -f
```

---

## 🆘 Troubleshooting

### Container não inicia
```bash
docker-compose logs wpp_bot_waha
docker-compose logs wpp_bot_api
```

### QR Code não aparece
```bash
docker-compose restart waha
docker logs wpp_bot_waha --tail=100
```

### WhatsApp desconectou
```bash
# Reiniciar container WAHA
docker-compose restart waha

# Ver novo QR Code
docker logs wpp_bot_waha --tail=50
```

### Porta em uso
```bash
# Ver processos usando porta 3000
sudo lsof -i :3000

# Matar processo
sudo kill -9 PID
```

---

## 🔐 Segurança

### Mudar senhas padrão
Edite o arquivo `.env`:
```env
WAHA_API_KEY=SUA_CHAVE_SUPER_SECRETA_AQUI
WAHA_DASHBOARD_PASSWORD=senha_muito_forte_123
```

Depois:
```bash
docker-compose down
docker-compose up -d
```

### Backup automático
Crie um script de backup:
```bash
nano /home/usuario/backup.sh
```

Conteúdo:
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /backups/chatbot_$DATE.tar.gz /home/usuario/chatbot-barbearia/data
find /backups -name "chatbot_*.tar.gz" -mtime +7 -delete
```

Agendar no cron:
```bash
crontab -e
```

Adicione:
```
0 3 * * * /home/usuario/backup.sh
```

---

## ✅ Checklist Final

- [ ] VPS com Ubuntu/Debian atualizado
- [ ] Docker e Docker Compose instalados
- [ ] Código transferido para VPS
- [ ] Arquivo `.env` configurado
- [ ] Containers iniciados (`docker-compose up -d`)
- [ ] QR Code escaneado
- [ ] WhatsApp conectado
- [ ] Firewall configurado
- [ ] Backup configurado (opcional)
- [ ] SSL configurado (opcional)

---

## 💡 Dica: Auto-start na inicialização

Para os containers iniciarem automaticamente quando a VPS reiniciar:

```bash
# Já configurado no docker-compose.yml com:
# restart: unless-stopped
```

Verificar:
```bash
cat docker-compose.yml | grep restart
```

---

## 🎯 Próximos passos

1. **Monitoramento**: Configurar Uptime Kuma ou similar
2. **Notificações**: Alertas quando WhatsApp desconectar
3. **Dashboard**: Implementar painel de controle
4. **Analytics**: Métricas de uso do bot

---

**Precisa de ajuda?** 
- Verifique os logs: `docker-compose logs -f`
- Reinicie: `docker-compose restart`
- Suporte: Abra uma issue no GitHub
