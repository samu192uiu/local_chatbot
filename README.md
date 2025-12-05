# 💈 Chatbot WhatsApp - Barbearia Veinho Corts

Sistema completo de agendamento automatizado via WhatsApp para barbearias.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Flask](https://img.shields.io/badge/Flask-2.0+-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Business-25D366)

---

## 🌟 Funcionalidades

### Para Clientes
- ✂️ **Agendamento Online** - Escolha data e horário disponível
- 💳 **Pagamento Integrado** - PIX e Cartão de Crédito
- 🔐 **Cadastro Seguro** - CPF + PIN de 4 dígitos
- 📱 **Notificações** - Confirmação automática via WhatsApp
- 💬 **Atendimento Humano** - Suporte quando necessário
- 📊 **Histórico** - Consulte seus agendamentos

### Para Administradores
- 📅 **Painel Admin** - Gestão completa via WhatsApp
- 🎫 **Sistema de Tickets** - Atendimento organizado
- 📈 **Relatórios** - Agendamentos do dia
- 👥 **Gestão de Clientes** - Visualize cadastros
- ⚡ **Comandos Rápidos** - Produtividade máxima

---

## 🏗️ Arquitetura

```
Cliente WhatsApp
      ↓
   WAHA API (WhatsApp)
      ↓
   Flask Backend
      ↓
  ┌─────────────┐
  │   Estado    │ ← Memory/Redis
  │   Fluxos    │
  │  Serviços   │
  └─────────────┘
      ↓
  Excel (Dados)
```

**Stack:**
- **Backend:** Python 3.9+ / Flask
- **WhatsApp:** WAHA (WhatsApp HTTP API)
- **Armazenamento:** Excel (openpyxl)
- **Deploy:** Docker / Docker Compose

---

## 🚀 Quick Start

### 1. Clone o repositório

```bash
git clone <seu-repositorio>
cd veinho-corts
```

### 2. Configure o `.env`

```bash
cp .env.example .env
nano .env
```

Principais variáveis:
```env
WAHA_API_URL=http://waha:3000
ADMIN_CHAT_IDS=5511999999999@c.us
PIN_SALT=seu_salt_secreto
```

### 3. Execute com Docker

```bash
docker-compose up -d
```

### 4. Configure WhatsApp

1. Acesse `http://localhost:3000`
2. Escaneie o QR Code
3. Configure webhook: `http://chatbot-api:5000/webhook`

### 5. Teste

Envie uma mensagem para o número conectado!

---

## 📚 Documentação

- **[📖 Guia Rápido](GUIA_RAPIDO.md)** - Como usar o sistema
- **[🚀 Deploy](DEPLOY.md)** - Colocando em produção
- **[✅ Testes](CHECKLIST_TESTES.md)** - Validação completa
- **[📝 Changelog](CHANGELOG_BARBEARIA.md)** - Histórico de mudanças

---

## 💈 Serviços Disponíveis

| Serviço | Preço | Duração |
|---------|-------|---------|
| Corte de Cabelo | R$ 50,00 | ~30min |
| Barba | R$ 40,00 | ~20min |
| Combo (Corte + Barba) | R$ 80,00 | ~45min |
| Sobrancelha | R$ 20,00 | ~10min |
| Hidratação Capilar | R$ 60,00 | ~40min |
| Luzes/Coloração | R$ 120,00 | ~90min |

---

## 📂 Estrutura do Projeto

```
veinho-corts/
├── 📄 app.py                      # Entry point
├── 📄 requirements.txt            # Dependências
├── 📄 docker-compose.yml          # Orquestração
├── 📄 Dockerfile.api              # Imagem Docker
│
├── 📁 config/
│   └── servicos.json              # Catálogo de serviços
│
├── 📁 data/
│   ├── cliente_barbearia/
│   │   └── agendamentos.xlsx      # Agendamentos
│   └── clientes.xlsx              # Base de clientes
│
├── 📁 tenants/
│   └── cliente_barbearia/
│       ├── config.yml             # Config do tenant
│       └── templates/pt-BR/       # Templates de mensagens
│
├── 📁 src/zapwaha/
│   ├── app.py                     # Flask app
│   ├── flows/
│   │   └── agendamento.py         # Lógica principal (1500+ linhas)
│   ├── services/
│   │   └── servicos.py            # Gerenciamento de serviços
│   ├── state/
│   │   └── memory.py              # Estado em memória
│   └── web/
│       ├── webhooks.py            # Webhook WhatsApp
│       └── debug.py               # Debug endpoints
│
└── 📁 services/
    ├── clientes_services.py       # CRUD clientes
    ├── excel_services.py          # Manipulação Excel
    └── waha.py                    # Cliente WhatsApp
```

---

## 🎯 Fluxo de Uso

### Cliente

```
1. Enviar mensagem ao bot
   ↓
2. Menu principal (4 opções)
   ↓
3. Escolher "1 - Agendar"
   ↓
4. Login ou Cadastro
   ↓
5. Informar data desejada
   ↓
6. Escolher horário disponível
   ↓
7. Escolher forma de pagamento
   ↓
8. Pagar e confirmar
   ↓
9. Agendamento CONFIRMADO! ✅
```

### Admin

```
1. Receber notificação de tickets
   ↓
2. Aceitar atendimento: /aceitar #123
   ↓
3. Conversar diretamente com cliente
   ↓
4. Finalizar: /encerrar
```

---

## 🔧 Configuração

### Horários Disponíveis

Edite em `src/zapwaha/flows/agendamento.py`:

```python
DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00",
    "13:00", "14:00", "15:00", "16:00", "17:00"
]
```

### Valor Padrão

```python
VALOR_SERVICO_PADRAO = 50.00
```

### Adicionar Serviço

Edite `config/servicos.json`:

```json
{
  "id": "novo_servico",
  "nome": "Novo Serviço",
  "preco": 100.0,
  "unidade": "serviço",
  "agendavel": true
}
```

---

## 🔐 Segurança

- ✅ Autenticação via CPF + PIN
- ✅ Hash SHA256 para PINs
- ✅ Salt configurável via ambiente
- ✅ Validação de CPF
- ✅ Timeout de sessões
- ✅ Controle de acesso admin

---

## 📊 Tecnologias

| Categoria | Tecnologia |
|-----------|------------|
| **Backend** | Python 3.9+, Flask |
| **WhatsApp** | WAHA API |
| **Dados** | Excel (openpyxl) |
| **Estado** | In-Memory (planejado: Redis) |
| **Deploy** | Docker, Docker Compose |
| **Libs** | requests, datetime, logging |

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

---

## 📈 Roadmap

### Em Desenvolvimento
- [ ] Escolha de barbeiro específico
- [ ] Lembretes automáticos (1 dia antes)
- [ ] Integração com gateway de pagamento real
- [ ] Dashboard web para admin

### Planejado
- [ ] Programa de fidelidade
- [ ] Pacotes promocionais
- [ ] Avaliação pós-atendimento
- [ ] Integração com Google Calendar
- [ ] App mobile nativo
- [ ] Multi-unidades

---

## 🐛 Problemas Conhecidos

- [ ] Timeout de pré-reserva fixo em 10 minutos
- [ ] Pagamento ainda é simulado (mock)
- [ ] Sem integração com calendário externo
- [ ] Estado em memória (perde ao reiniciar)

**Soluções planejadas:** Ver roadmap acima

---

## 📞 Suporte

- 📖 Consulte a [documentação](GUIA_RAPIDO.md)
- 🐛 Reporte bugs via Issues
- 💬 Dúvidas: abra uma Discussion

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 👨‍💻 Autor

**Samuel**  
- 📧 Email: [seu-email]
- 💼 LinkedIn: [seu-linkedin]
- 🐙 GitHub: [@samu192uiu](https://github.com/samu192uiu)

---

## 🙏 Agradecimentos

- **WAHA** - WhatsApp HTTP API
- **Flask** - Framework web
- **openpyxl** - Manipulação de Excel
- Comunidade Python

---

## 📊 Status do Projeto

![Status](https://img.shields.io/badge/Status-Produção-success)
![Versão](https://img.shields.io/badge/Versão-1.0-blue)
![Testes](https://img.shields.io/badge/Testes-Passing-success)

**Última atualização:** Dezembro 2025

---

<div align="center">

### ⭐ Se este projeto foi útil, considere dar uma estrela!

**Feito com ❤️ para a Barbearia Veinho Corts**

</div>
