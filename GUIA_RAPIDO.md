# 💈 Barbearia Veinho Corts - Guia Rápido

## 🚀 Como Iniciar o Chatbot

### 1. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# WhatsApp/WAHA
WAHA_API_URL=http://localhost:3000
WAHA_SESSION=default
WAHA_API_KEY=sua_chave_aqui

# Admin
ADMIN_CHAT_IDS=5511999999999@c.us
ADMIN_TOKEN=seu_token_admin

# Arquivos
AGENDAMENTOS_XLSX=/app/data/cliente_barbearia/agendamentos.xlsx
CLIENTES_XLSX=/app/data/clientes.xlsx

# Segurança
PIN_SALT=barbearia_salt
REQUIRE_CHATID_BIND=true
```

### 2. Executar com Docker

```bash
docker-compose up -d
```

### 3. Executar Localmente (Desenvolvimento)

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar
python app.py
```

O servidor iniciará em `http://localhost:5000`

---

## 📱 Fluxo de Uso do Cliente

### Menu Principal
```
1️⃣ Agendar Corte ou Serviço
2️⃣ Serviços e Valores
3️⃣ Dúvidas Frequentes
4️⃣ Falar com Atendente
```

### Opção 1: Agendar
1. **Fazer Login ou Cadastro**
   - Login: CPF + PIN (4 dígitos)
   - Cadastro: Nome completo, Data de nascimento, CPF, Email, PIN

2. **Submenu de Agendamento**
   - 1. Agendar novo corte/serviço
   - 2. Consultar próximo horário
   - 3. Remarcar horário
   - 4. Cancelar horário

3. **Processo de Agendamento**
   - Informar data (DD/MM/AAAA ou DD/MM)
   - Escolher horário disponível
   - Confirmar reserva

4. **Pagamento**
   - PIX (Copia e Cola)
   - Cartão de Crédito (Link)
   - Responder "paguei" após realizar

5. **Confirmação**
   - Status: CONFIRMADO
   - Data e horário salvos

### Opção 2: Serviços e Valores
```
✂️ Corte de Cabelo - R$ 50,00
🧔 Barba - R$ 40,00
💯 Combo (Corte + Barba) - R$ 80,00
👁️ Sobrancelha - R$ 20,00
💧 Hidratação Capilar - R$ 60,00
🎨 Luzes/Coloração - R$ 120,00

Horário: Seg a Sex 9h-19h, Sáb 9h-17h
```

### Opção 3: Dúvidas Frequentes
- 📍 Localização
- ⏰ Horário de funcionamento
- 💳 Formas de pagamento
- 📱 Como remarcar
- ⚠️ Política de cancelamento

### Opção 4: Falar com Atendente
- Cliente descreve a dúvida
- Sistema cria ticket
- Admin recebe notificação
- Admin aceita com `/aceitar #ticket`
- Conversa em tempo real
- Encerrar com `/encerrar`

---

## 🛠️ Painel Administrativo

### Acesso
Adicione seu WhatsApp em `ADMIN_CHAT_IDS` no `.env`

### Menu Admin
```
1️⃣ Ver agendamentos do dia
2️⃣ Assumir próximo cliente
3️⃣ Chamados abertos
4️⃣ Logins (vínculos e sessões)
```

### Comandos Rápidos
- `/aceitar #123` - Assumir ticket específico
- `/aceitar 5511999999999@c.us` - Assumir por chat ID
- `/encerrar` - Finalizar atendimento
- `/logins` - Ver 20 últimos logins
- `/logins 50` - Ver 50 últimos logins
- `menu` - Voltar ao menu admin

---

## 🔧 Manutenção

### Estrutura de Arquivos

```
veinho corts/
├── app.py                          # Entrada principal
├── requirements.txt                # Dependências Python
├── docker-compose.yml              # Configuração Docker
├── Dockerfile.api                  # Imagem Docker
│
├── config/
│   └── servicos.json              # Lista de serviços
│
├── data/
│   ├── cliente_barbearia/
│   │   └── agendamentos.xlsx      # Planilha de agendamentos
│   └── clientes.xlsx              # Planilha de clientes
│
├── tenants/
│   └── cliente_barbearia/
│       ├── config.yml             # Config do tenant
│       └── templates/pt-BR/
│           ├── menu.txt           # Template do menu
│           ├── confirmado.txt     # Template de confirmação
│           └── pagamento.txt      # Template de pagamento
│
├── src/zapwaha/
│   ├── app.py                     # Aplicação Flask
│   ├── flows/
│   │   └── agendamento.py         # Lógica principal do fluxo
│   ├── services/
│   │   └── servicos.py            # Gerenciamento de serviços
│   ├── state/
│   │   └── memory.py              # Gerenciamento de estado
│   └── web/
│       ├── webhooks.py            # Recebimento de mensagens
│       └── debug.py               # Endpoints de debug
│
└── services/
    ├── clientes_services.py       # CRUD de clientes
    ├── excel_services.py          # Manipulação de planilhas
    └── waha.py                    # Cliente WhatsApp API
```

### Adicionar Novo Serviço

Edite `config/servicos.json`:

```json
{
  "id": "platinado",
  "nome": "Platinado",
  "preco": 150.0,
  "unidade": "serviço",
  "agendavel": true,
  "observacao": "Serviço premium"
}
```

### Ajustar Horários Disponíveis

Em `src/zapwaha/flows/agendamento.py`:

```python
DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00",
    "13:00", "14:00", "15:00", "16:00", "17:00"
]
```

### Alterar Preço Padrão

Em `src/zapwaha/flows/agendamento.py`:

```python
VALOR_SERVICO_PADRAO = 50.00
```

E em `tenants/cliente_barbearia/config.yml`:

```yaml
price: 50.00
```

---

## 🐛 Troubleshooting

### Problema: Mensagens não chegam
- Verificar `WAHA_API_URL` no `.env`
- Verificar se WAHA está rodando: `docker ps`
- Verificar logs: `docker logs waha`

### Problema: Agendamentos não salvam
- Verificar permissões da pasta `data/`
- Verificar se arquivo Excel existe e não está corrompido
- Ver logs do app: `docker logs chatbot-api`

### Problema: Admin não recebe notificações
- Verificar `ADMIN_CHAT_IDS` no `.env`
- Formato correto: `5511999999999@c.us`
- Reiniciar container após alterar `.env`

### Problema: Login não funciona
- Verificar se `data/clientes.xlsx` existe
- Verificar se PIN foi cadastrado corretamente
- Testar criar novo cadastro

---

## 📊 Planilhas Excel

### Clientes (`data/clientes.xlsx`)

| Coluna | Descrição |
|--------|-----------|
| ID | Identificador único |
| CPF | CPF do cliente (apenas números) |
| Nome | Nome completo |
| Nascimento | Data de nascimento (DD/MM/AAAA) |
| Telefone | Telefone (apenas números) |
| Email | Email do cliente |
| ChatId | WhatsApp ID (ex: 5511999999999@c.us) |
| PinHash | Hash do PIN (SHA256) |
| UltimoLogin | Data/hora do último login |
| CriadoEm | Data/hora de criação |
| AtualizadoEm | Data/hora de atualização |

### Agendamentos (`data/cliente_barbearia/agendamentos.xlsx`)

| Coluna | Descrição |
|--------|-----------|
| Chave | Identificador único do agendamento |
| Data | Data do agendamento (DD/MM/AAAA) |
| Hora | Horário (HH:MM) |
| ChatId | WhatsApp ID do cliente |
| ClienteID | ID do cliente (FK) |
| ClienteNome | Nome do cliente |
| Nascimento | Data de nascimento |
| CPF | CPF do cliente |
| Status | Pendente/Confirmado/Cancelado/etc |
| ValorPago | Valor pago pelo serviço |
| CriadoEm | Data/hora de criação |

---

## 🔐 Segurança

### Boas Práticas

1. **Variáveis de Ambiente**
   - NUNCA commitar `.env` no Git
   - Usar senhas fortes para `ADMIN_TOKEN`
   - Rotacionar `PIN_SALT` periodicamente

2. **Backups**
   - Fazer backup diário das planilhas Excel
   - Guardar em local seguro
   - Testar restauração regularmente

3. **Monitoramento**
   - Verificar logs regularmente
   - Monitorar uso de recursos
   - Alertar em caso de erros

---

## 📞 Suporte e Contribuição

Para dúvidas ou sugestões:
- Consulte o `CHANGELOG_BARBEARIA.md`
- Revise a documentação inline no código
- Verifique os logs em caso de erro

**Desenvolvido por:** Samuel  
**Versão:** 1.0 - Barbearia  
**Data:** Dezembro 2025
