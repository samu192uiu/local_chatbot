#!/bin/bash
# Script de deploy automático para Hostinger VPS
# Servidor: srv1017248.hstgr.cloud (212.85.21.122)
# OS: Ubuntu 24.04 with Docker
# Execute como root: bash deploy-hostinger.sh

set -e  # Parar em caso de erro

echo "🚀 Iniciando deploy do Bot Barbearia na Hostinger VPS..."
echo ""

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Atualizar sistema
echo -e "${BLUE}[1/7]${NC} Atualizando sistema Ubuntu..."
apt update && apt upgrade -y

# 2. Verificar se Docker já está instalado
echo -e "${BLUE}[2/7]${NC} Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker não encontrado. Instalando..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo -e "${GREEN}✓${NC} Docker já instalado: $(docker --version)"
fi

# 3. Verificar se Docker Compose está instalado
echo -e "${BLUE}[3/7]${NC} Verificando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose não encontrado. Instalando..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo -e "${GREEN}✓${NC} Docker Compose já instalado: $(docker-compose --version)"
fi

# 4. Instalar Git se necessário
echo -e "${BLUE}[4/7]${NC} Verificando Git..."
if ! command -v git &> /dev/null; then
    echo "Git não encontrado. Instalando..."
    apt install git -y
else
    echo -e "${GREEN}✓${NC} Git já instalado: $(git --version)"
fi

# 5. Criar diretório e clonar repositório
echo -e "${BLUE}[5/7]${NC} Clonando repositório..."
mkdir -p /opt/barbearia-bot
cd /opt/barbearia-bot

# Se já existe, fazer pull. Senão, clonar
if [ -d ".git" ]; then
    echo "Repositório já existe. Atualizando..."
    git pull origin main
else
    echo "Clonando repositório..."
    git clone https://github.com/samu192uiu/local_chatbot.git .
fi

# 6. Verificar arquivo .env
echo -e "${BLUE}[6/7]${NC} Verificando arquivo .env..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} Arquivo .env encontrado"
    cat .env
else
    echo -e "${YELLOW}⚠${NC} Arquivo .env não encontrado! Criando..."
    cat > .env << 'EOF'
# WAHA Configuration
WAHA_API_KEY=barbearia2025_api_key_fixa

# Dashboard WAHA
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=1234

# Swagger credentials
WHATSAPP_SWAGGER_USERNAME=admin
WHATSAPP_SWAGGER_PASSWORD=1234
EOF
    echo -e "${YELLOW}⚠ IMPORTANTE: Altere as senhas no arquivo .env antes de usar em produção!${NC}"
fi

# 7. Iniciar containers
echo -e "${BLUE}[7/7]${NC} Iniciando containers Docker..."
docker-compose down 2>/dev/null || true  # Parar containers antigos se existirem
docker-compose up -d --build

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Deploy concluído com sucesso!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}📱 Próximos passos:${NC}"
echo ""
echo "1. Acesse o dashboard WAHA:"
echo -e "   ${BLUE}http://212.85.21.122:3000${NC}"
echo ""
echo "2. Faça login com:"
echo "   Usuário: admin"
echo "   Senha: 1234"
echo ""
echo "3. Crie uma sessão chamada 'default' e escaneie o QR Code"
echo ""
echo "4. Aguarde status WORKING e teste enviando 'oi' no WhatsApp"
echo ""
echo -e "${YELLOW}📊 Comandos úteis:${NC}"
echo ""
echo "   Ver logs em tempo real:"
echo -e "   ${BLUE}docker-compose logs -f${NC}"
echo ""
echo "   Ver apenas logs do bot:"
echo -e "   ${BLUE}docker logs -f wpp_bot_api${NC}"
echo ""
echo "   Ver status dos containers:"
echo -e "   ${BLUE}docker ps${NC}"
echo ""
echo "   Reiniciar tudo:"
echo -e "   ${BLUE}docker-compose restart${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
