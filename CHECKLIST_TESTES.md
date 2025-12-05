# ✅ Checklist de Testes - Barbearia Veinho Corts

Use este checklist para validar que todas as funcionalidades estão operando corretamente após a conversão.

---

## 🧪 Testes Básicos

### ✅ 1. Menu Principal
- [ ] Enviar qualquer mensagem para o bot
- [ ] Verificar se recebe menu com 4 opções
- [ ] Verificar emojis: ✂️💈
- [ ] Verificar texto: "Barbearia Veinho Corts"

**Esperado:**
```
👋 Bem-vindo(a) à Barbearia Veinho Corts! ✂️💈

Como podemos te ajudar hoje?

1️⃣ Agendar Corte ou Serviço
2️⃣ Serviços e Valores
3️⃣ Dúvidas Frequentes
4️⃣ Falar com Atendente
```

---

### ✅ 2. Opção 2 - Serviços e Valores
- [ ] Enviar "2" no menu principal
- [ ] Verificar lista de serviços de barbearia
- [ ] Verificar preços corretos
- [ ] Verificar horário de funcionamento

**Esperado:**
```
💈 Serviços e Valores da Barbearia

✂️ Corte de Cabelo - R$ 50,00
🧔 Barba - R$ 40,00
💯 Combo (Corte + Barba) - R$ 80,00
👁️ Sobrancelha - R$ 20,00
💧 Hidratação Capilar - R$ 60,00
🎨 Luzes/Coloração - R$ 120,00

Horário de funcionamento: Seg a Sex 9h-19h, Sáb 9h-17h
```

---

### ✅ 3. Opção 3 - Dúvidas Frequentes
- [ ] Enviar "3" no menu principal
- [ ] Verificar conteúdo completo (não "em construção")
- [ ] Verificar informações: localização, horário, pagamento, etc.

**Esperado:**
```
❓ Dúvidas Frequentes

📍 Onde ficamos?
Rua Exemplo, 123 - Centro

⏰ Horário de funcionamento?
Seg a Sex: 9h às 19h
Sábado: 9h às 17h
Domingo: Fechado

💳 Formas de pagamento?
PIX, Cartão (débito/crédito), Dinheiro
...
```

---

### ✅ 4. Cadastro de Novo Cliente
- [ ] Enviar "1" (Agendar)
- [ ] Sistema pede login → escolher "2" (Criar cadastro)
- [ ] Informar nome completo (ex: João Silva Santos)
- [ ] Informar data nascimento (ex: 15/04/1995)
- [ ] Informar CPF válido (ex: 12345678909)
- [ ] Informar email ou "pular"
- [ ] Criar PIN de 4 dígitos (ex: 1234)
- [ ] Confirmar PIN
- [ ] Verificar mensagem de sucesso

**Esperado no final:**
```
✅ Cadastro criado e login efetuado!
```

---

### ✅ 5. Login Existente
- [ ] Enviar "1" (Agendar)
- [ ] Escolher "1" (Entrar)
- [ ] Informar CPF cadastrado
- [ ] Informar PIN correto
- [ ] Verificar mensagem de sucesso

**Esperado:**
```
✅ Login realizado com sucesso!
```

---

### ✅ 6. Fluxo Completo de Agendamento
- [ ] Fazer login
- [ ] Escolher "1" (Agendar novo corte/serviço)
- [ ] Informar data futura (ex: 15/12/2025)
- [ ] Escolher horário disponível (ex: 1 para 08:00)
- [ ] Verificar mensagem de pré-reserva
- [ ] Verificar valor: R$ 50,00
- [ ] Escolher forma de pagamento (1 = PIX ou 2 = Cartão)
- [ ] Receber instruções de pagamento
- [ ] Enviar "paguei"
- [ ] Verificar confirmação final

**Esperado na confirmação:**
```
✅ Pagamento confirmado!

Seu horário para 15/12/2025 às 08:00 está CONFIRMADO.

💈 Te esperamos na barbearia!
Qualquer dúvida, é só chamar.
```

---

### ✅ 7. Atendimento Humano - Cliente
- [ ] Enviar "4" no menu principal
- [ ] Fazer login (se necessário)
- [ ] Enviar mensagem com dúvida (ex: "Quero saber sobre combos")
- [ ] Verificar mensagem de aguardo

**Esperado:**
```
✅ Pedido enviado! Aguarde, um atendente vai entrar na conversa em instantes. 😉
```

---

### ✅ 8. Atendimento Humano - Admin

**Pré-requisito:** Adicionar seu WhatsApp em `ADMIN_CHAT_IDS`

- [ ] Como admin, enviar qualquer mensagem
- [ ] Verificar menu admin
- [ ] Verificar título: "Painel Admin - Barbearia Veinho Corts"
- [ ] Enviar "3" (Chamados abertos)
- [ ] Verificar ticket criado no teste anterior
- [ ] Enviar `/aceitar #<número_ticket>`
- [ ] Enviar mensagem teste para cliente
- [ ] Cliente deve receber: "👨‍💼 Atendente: <mensagem>"
- [ ] Enviar `/encerrar` para finalizar

**Esperado no menu admin:**
```
🔧 Painel Admin - Barbearia Veinho Corts

1️⃣ Ver agendamentos do dia
2️⃣ Assumir próximo cliente
3️⃣ Chamados abertos
4️⃣ Logins (vínculos e sessões)
```

---

### ✅ 9. Agendamentos do Dia (Admin)
- [ ] Como admin, enviar "1" no menu admin
- [ ] Verificar lista de agendamentos (pode estar vazia)
- [ ] Se houver agendamentos, verificar formato correto

**Esperado (com agendamentos):**
```
🗓️ Agendamentos de hoje (15/12/2025):
• 08:00 — João Silva Santos (Confirmado)
• 14:00 — Maria Souza (Pendente Pagamento)
```

---

### ✅ 10. Comandos de Atalho
- [ ] Enviar "menu" → volta ao menu principal
- [ ] Enviar "voltar" → volta ao menu principal
- [ ] Enviar "inicio" → volta ao menu principal

---

## 🔍 Testes de Validação

### ✅ 11. Validação de CPF
- [ ] Tentar cadastrar com CPF inválido (ex: 11111111111)
- [ ] Verificar mensagem de erro
- [ ] Tentar com CPF válido
- [ ] Deve aceitar

---

### ✅ 12. Validação de Data de Nascimento
- [ ] Tentar data futura
- [ ] Verificar rejeição
- [ ] Tentar formato inválido (ex: 32/13/2020)
- [ ] Verificar rejeição
- [ ] Informar data válida (ex: 15/04/1995)
- [ ] Deve aceitar

---

### ✅ 13. Validação de Horário
- [ ] Tentar agendar horário já ocupado
- [ ] Verificar mensagem de indisponibilidade
- [ ] Tentar horário disponível
- [ ] Deve pré-reservar

---

## 📊 Testes de Planilha

### ✅ 14. Gravação de Cliente
- [ ] Criar novo cadastro
- [ ] Abrir `data/clientes.xlsx`
- [ ] Verificar se linha foi adicionada
- [ ] Verificar campos: ID, CPF, Nome, Nascimento, ChatId, etc.
- [ ] Verificar PinHash (deve estar preenchido)

---

### ✅ 15. Gravação de Agendamento
- [ ] Fazer agendamento completo até confirmação
- [ ] Abrir `data/cliente_barbearia/agendamentos.xlsx`
- [ ] Verificar linha do agendamento
- [ ] Verificar Status = "Confirmado"
- [ ] Verificar Data, Hora, ClienteNome, CPF

---

## 🎨 Testes de Interface

### ✅ 16. Emojis e Formatação
- [ ] Verificar emojis corretos em todas as mensagens
- [ ] Verificar negrito (*texto*)
- [ ] Verificar rodapés com atalhos
- [ ] Verificar separadores visuais

---

### ✅ 17. Consistência de Textos
- [ ] Nenhuma menção a "clínica"
- [ ] Nenhuma menção a "fisioterapia", "osteopatia", etc.
- [ ] Todas as mensagens falam em "barbearia"
- [ ] Valores corretos (R$ 50,00 padrão)
- [ ] Serviços de barbearia listados

---

## 🚨 Testes de Erro

### ✅ 18. Timeout de Pré-reserva
- [ ] Fazer pré-reserva (escolher horário)
- [ ] Aguardar mais de 10 minutos sem pagar
- [ ] Verificar se horário é liberado
- [ ] Verificar se pode agendar novamente

---

### ✅ 19. Timeout de Atendimento Humano
- [ ] Solicitar atendimento humano
- [ ] Aguardar mais de 10 minutos sem admin aceitar
- [ ] Verificar se é encerrado automaticamente
- [ ] Verificar mensagem de timeout

---

### ✅ 20. Opções Inválidas
- [ ] Enviar "999" no menu
- [ ] Verificar mensagem de opção inválida
- [ ] Enviar "abc" no menu
- [ ] Verificar tratamento adequado

---

## ✅ Checklist Final

- [ ] Todos os testes básicos (1-10) passaram
- [ ] Todos os testes de validação (11-13) passaram
- [ ] Testes de planilha (14-15) verificados
- [ ] Interface (16-17) consistente
- [ ] Testes de erro (18-20) cobertos
- [ ] Sem erros nos logs
- [ ] Sem menções a "clínica" nas mensagens
- [ ] Valores e serviços de barbearia corretos

---

## 📝 Registro de Bugs

Use esta seção para anotar problemas encontrados:

```
[ ] Bug 1: _______________________________________
    Descrição: 
    Reproduzir:
    Esperado:
    
[ ] Bug 2: _______________________________________
    Descrição:
    Reproduzir:
    Esperado:
```

---

## 🎉 Resultado Final

**Status:** [ ] ✅ Todos os testes passaram | [ ] ⚠️ Pendências | [ ] ❌ Falhas críticas

**Testado por:** _______________________  
**Data:** _____ / _____ / _____  
**Notas adicionais:**

```
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

---

**Dica:** Execute este checklist sempre que fizer alterações significativas no código!
