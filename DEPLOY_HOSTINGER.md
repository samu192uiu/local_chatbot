# 🚀 Deploy do Bot na Hostinger VPS

## 📋 Informações Importantes da Hostinger

A Hostinger VPS geralmente vem com:
- **Ubuntu 20.04/22.04 LTS** pré-instalado
- **Acesso root** via SSH
- **Painel hPanel** para gerenciamento
- **IP dedicado**

---

## 🔑 Passo 1: Acessar a VPS Hostinger

### 1.1 Obter credenciais SSH
1. Acesse o **hPanel** da Hostinger: https://hpanel.hostinger.com
2. Vá em **VPS** → Selecione sua VPS
3. Anote:
   - **IP da VPS** (ex: 123.45.67.89)
   - **Porta SSH** (geralmente 22)
   - **Usuário root** e senha (ou configure chave SSH)

### 1.2 Conectar via SSH
No seu terminal local:
```bash
ssh root@SEU_IP_DA_VPS
# Digite a senha quando solicitado
```

Exemplo:
```bash
ssh root@123.45.67.89
```

---

## 🔧 Passo 2: Instalar Docker na Hostinger VPS

### 2.1 Atualizar sistema
```bash
apt update && apt upgrade -y
```

### 2.2 Instalar Docker
```bash
# Script oficial do Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verificar instalação
docker --version
```

### 2.3 Instalar Docker Compose
```bash
# Baixar versão mais recente
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão de execução
chmod +x /usr/local/bin/docker-compose

# Verificar instalação
docker-compose --version
```

---

## 📁 Passo 3: Transferir Arquivos para a VPS

### Opção 1: Via Git (Recomendado)

#### 3.1 No seu computador local
```bash
# Criar repositório Git (se ainda não tiver)
cd "C:\Users\samue\OneDrive\Desktop\veinho corts"
git init
git add .
git commit -m "Initial commit"

# Criar repositório no GitHub/GitLab (privado)
# Depois:
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

#### 3.2 Na VPS Hostinger
```bash
# Instalar git
apt install git -y

# Criar diretório do projeto
mkdir -p /opt/barbearia-bot
cd /opt/barbearia-bot

# Clonar repositório
git clone https://github.com/SEU_USUARIO/SEU_REPO.git .
```

### Opção 2: Via SCP/FileZilla (Mais Simples)

#### 3.2.1 Usando WinSCP (Windows)
1. Baixe: https://winscp.net/eng/download.php
2. Configure conexão:
   - **Protocolo**: SFTP
   - **Host**: SEU_IP_DA_VPS
   - **Porta**: 22
   - **Usuário**: root
   - **Senha**: sua_senha
3. Arraste toda pasta `veinho corts` para `/opt/barbearia-bot`

#### 3.2.2 Ou via PowerShell (SCP)
```powershell
# No seu PowerShell local
scp -r "C:\Users\samue\OneDrive\Desktop\veinho corts\*" root@SEU_IP:/opt/barbearia-bot/
```

---

## ⚙️ Passo 4: Configurar Ambiente na VPS

### 4.1 Verificar arquivos transferidos
```bash
cd /opt/barbearia-bot
ls -la
```

Você deve ver:
```
docker-compose.yml
Dockerfile.api
.env
app.py
requirements.txt
src/
services/
config/
tenants/
...
```

### 4.2 Configurar arquivo .env
```bash
# Editar .env
nano .env
```

Conteúdo do `.env` (já deve estar correto):
```env
# WAHA Configuration
WAHA_API_KEY=barbearia2025_api_key_fixa

# Dashboard WAHA
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=1234

# Swagger credentials
WHATSAPP_SWAGGER_USERNAME=admin
WHATSAPP_SWAGGER_PASSWORD=1234
```

**⚠️ IMPORTANTE**: Para produção, altere as senhas:
```env
WAHA_DASHBOARD_PASSWORD=SUA_SENHA_FORTE_AQUI
WHATSAPP_SWAGGER_PASSWORD=OUTRA_SENHA_FORTE_AQUI
```

Salvar: `Ctrl+O` → Enter → `Ctrl+X`

---

## 🚀 Passo 5: Iniciar o Bot

### 5.1 Buildar e iniciar containers
```bash
cd /opt/barbearia-bot
docker-compose up -d --build
```

### 5.2 Verificar containers rodando
```bash
docker ps
```

Você deve ver:
```
CONTAINER ID   IMAGE                          PORTS                    STATUS
xxxxx          devlikeapro/waha:latest       0.0.0.0:3000->3000/tcp   Up
xxxxx          barbearia-bot-api             0.0.0.0:5000->5000/tcp   Up
```

### 5.3 Ver logs em tempo real
```bash
# Logs do bot
docker logs -f wpp_bot_api

# Logs do WAHA
docker logs -f wpp_bot_waha

# Todos os logs
docker-compose logs -f
```

---

## 📱 Passo 6: Conectar WhatsApp

### 6.1 Acessar Dashboard WAHA
No seu navegador:
```
http://SEU_IP_DA_VPS:3000
```

Exemplo: `http://123.45.67.89:3000`

Login:
- **Usuário**: admin
- **Senha**: 1234 (ou a que você configurou)

### 6.2 Criar sessão e escanear QR Code
1. Vá em **Sessions** → **+ Add Session**
2. Nome da sessão: `default`
3. Clique em **Start**
4. Abra WhatsApp no celular → **Aparelhos conectados** → **Conectar aparelho**
5. Escaneie o QR Code que aparece no dashboard
6. Aguarde status: **WORKING** ✅

### 6.3 Testar o bot
- Envie mensagem para o número conectado: `oi`
- Você deve receber o menu da barbearia

---

## 🔒 Passo 7: Configurar Firewall na Hostinger

### 7.1 Via hPanel (Interface Web)
1. Acesse **hPanel** → **VPS** → Sua VPS
2. Vá em **Firewall** ou **Security**
3. Adicione regras:
   - **Porta 22** (SSH) - Permitir seu IP
   - **Porta 3000** (WAHA Dashboard) - Permitir temporariamente
   - **Porta 5000** (API) - Permitir temporariamente

### 7.2 Via UFW (Linha de comando)
```bash
# Instalar UFW
apt install ufw -y

# Permitir SSH (CUIDADO: não se bloqueie!)
ufw allow 22/tcp

# Permitir portas do bot
ufw allow 3000/tcp
ufw allow 5000/tcp

# Ativar firewall
ufw enable

# Ver status
ufw status
```

**⚠️ SEGURANÇA**: Após conectar WhatsApp, você pode restringir acesso às portas 3000/5000 apenas ao seu IP:
```bash
ufw delete allow 3000/tcp
ufw allow from SEU_IP_PESSOAL to any port 3000 proto tcp
```

---

## 🌐 Passo 8: Domínio e SSL (Opcional)

### 8.1 Configurar domínio na Hostinger
1. No **hPanel**, vá em **Domínios**
2. Aponte domínio para IP da VPS:
   - Tipo **A Record**
   - Nome: `bot` ou `@`
   - Aponta para: `SEU_IP_DA_VPS`

Exemplo: `bot.seudominio.com` → `123.45.67.89`

### 8.2 Instalar Nginx como reverse proxy
```bash
# Instalar Nginx
apt install nginx -y

# Criar configuração
nano /etc/nginx/sites-available/barbearia-bot
```

Conteúdo:
```nginx
server {
    listen 80;
    server_name bot.seudominio.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Ativar site
ln -s /etc/nginx/sites-available/barbearia-bot /etc/nginx/sites-enabled/

# Testar configuração
nginx -t

# Recarregar Nginx
systemctl reload nginx
```

### 8.3 Instalar SSL com Let's Encrypt
```bash
# Instalar Certbot
apt install certbot python3-certbot-nginx -y

# Obter certificado SSL
certbot --nginx -d bot.seudominio.com

# Renovação automática já está configurada
```

Agora acesse: `https://bot.seudominio.com` 🔒

---

## 🛠️ Comandos Úteis de Gerenciamento

### Ver logs
```bash
docker logs wpp_bot_api --tail=50 -f
docker logs wpp_bot_waha --tail=50 -f
```

### Reiniciar bot
```bash
docker-compose restart
```

### Parar tudo
```bash
docker-compose down
```

### Iniciar novamente
```bash
docker-compose up -d
```

### Atualizar código
```bash
cd /opt/barbearia-bot
git pull  # Se usando Git
docker-compose up -d --build
```

### Ver uso de recursos
```bash
docker stats
```

### Backup dos dados
```bash
# Backup do volume de dados do Excel
docker run --rm -v barbearia-bot_agdata:/data -v $(pwd):/backup ubuntu tar czf /backup/backup-agendamentos-$(date +%Y%m%d).tar.gz /data

# Backup da sessão WAHA
docker run --rm -v barbearia-bot_waha_data:/data -v $(pwd):/backup ubuntu tar czf /backup/backup-waha-$(date +%Y%m%d).tar.gz /data
```

---

## 🔍 Troubleshooting Hostinger

### Container não inicia
```bash
docker-compose logs wpp_bot_api
docker-compose logs wpp_bot_waha
```

### Porta já em uso
```bash
# Ver o que está usando a porta 3000
netstat -tulpn | grep 3000

# Matar processo
kill -9 PID
```

### Sem espaço em disco
```bash
# Ver espaço
df -h

# Limpar containers e imagens antigas
docker system prune -a

# Limpar logs do Docker
journalctl --vacuum-time=3d
```

### WhatsApp desconecta
```bash
# Ver logs do WAHA
docker logs wpp_bot_waha --tail=100

# Reiniciar apenas WAHA
docker-compose restart wpp_bot_waha
```

### Erro de memória (Hostinger VPS pequena)
Se sua VPS tem pouca RAM (< 2GB):
```bash
# Adicionar swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Tornar permanente
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
```

---

## 📊 Monitoramento

### Configurar monitoramento automático
```bash
# Criar script de monitoramento
nano /opt/monitor-bot.sh
```

Conteúdo:
```bash
#!/bin/bash
cd /opt/barbearia-bot

# Verificar se containers estão rodando
if [ $(docker ps -q -f name=wpp_bot_api | wc -l) -eq 0 ]; then
    echo "API container parado! Reiniciando..."
    docker-compose up -d wpp_bot_api
fi

if [ $(docker ps -q -f name=wpp_bot_waha | wc -l) -eq 0 ]; then
    echo "WAHA container parado! Reiniciando..."
    docker-compose up -d wpp_bot_waha
fi
```

```bash
# Dar permissão
chmod +x /opt/monitor-bot.sh

# Adicionar ao cron (verificar a cada 5 minutos)
crontab -e
```

Adicione:
```cron
*/5 * * * * /opt/monitor-bot.sh >> /var/log/bot-monitor.log 2>&1
```

---

## 🎯 Checklist Final

- [ ] VPS Hostinger acessível via SSH
- [ ] Docker e Docker Compose instalados
- [ ] Arquivos transferidos para `/opt/barbearia-bot`
- [ ] Arquivo `.env` configurado com senhas fortes
- [ ] Containers iniciados: `docker ps` mostra 2 containers
- [ ] WhatsApp conectado: Dashboard mostra status **WORKING**
- [ ] Bot respondendo mensagens de teste
- [ ] Firewall configurado (portas 22, 3000, 5000)
- [ ] Backup configurado (opcional)
- [ ] Monitoramento ativo (opcional)
- [ ] Domínio e SSL configurados (opcional)

---

## 🆘 Suporte

### Logs importantes
```bash
# Ver tudo
docker-compose logs --tail=100

# Apenas erros
docker-compose logs | grep -i error
```

### Reiniciar do zero
```bash
cd /opt/barbearia-bot
docker-compose down -v  # ⚠️ APAGA DADOS!
docker-compose up -d --build
```

### Contato Hostinger
- **Suporte 24/7**: Chat no hPanel
- **Documentação**: https://support.hostinger.com

---

## 🔐 Segurança Pós-Deploy

1. **Alterar senha root da VPS** (via hPanel)
2. **Alterar senhas no .env** (WAHA_DASHBOARD_PASSWORD, etc.)
3. **Restringir acesso SSH** apenas ao seu IP
4. **Fechar portas 3000/5000** ao público após setup
5. **Habilitar autenticação de dois fatores** no hPanel
6. **Backups automáticos** da Hostinger (verificar se está ativo)

---

**✅ Pronto! Seu bot está no ar 24/7 na Hostinger VPS! 🎉**
