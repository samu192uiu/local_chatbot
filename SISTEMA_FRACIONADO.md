# 💈 Sistema de Agendamento Fracionado

## 🎯 Objetivo

Permitir que serviços longos (luzes, platinado, coloração) sejam agendados de forma que o barbeiro possa atender outros clientes durante as pausas do produto.

---

## 📊 Como Funciona

### Exemplo Prático: Platinado às 10h

```
⏰ 10:00 - 10:40 🔒 Aplicação do Descolorante (40min)
                    └─ Barbeiro OCUPADO

⏰ 10:40 - 11:30 ⏳ Ação do Produto (50min)
                    └─ Cliente aguarda
                    └─ Barbeiro LIVRE → Pode cortar outro cabelo!

⏰ 11:30 - 12:00 🔒 Verificação e 2ª Aplicação (30min)
                    └─ Barbeiro OCUPADO

⏰ 12:00 - 12:40 ⏳ Ação do 2º Produto (40min)
                    └─ Cliente aguarda
                    └─ Barbeiro LIVRE → Pode cortar outro cabelo!

⏰ 12:40 - 13:30 🔒 Matização e Finalização (50min)
                    └─ Barbeiro OCUPADO

✅ Finalizado às 13:30 (3h30 de duração total)
```

**Durante as pausas (⏳):**
- Cliente do platinado fica aguardando
- Barbeiro pode atender cortes rápidos
- Sistema permite novos agendamentos nesses horários!

---

## 🔧 Estrutura Técnica

### Arquivo: `config/servicos_detalhados.json`

Define os serviços e suas etapas:

**Serviços Simples:**
```json
{
  "id": "corte_simples",
  "tipo": "simples",
  "duracao_minutos": 40,
  "barbeiro_ocupado": true
}
```

**Serviços Fracionados:**
```json
{
  "id": "platinado",
  "tipo": "fracionado",
  "etapas": [
    {
      "ordem": 1,
      "nome": "Aplicação",
      "duracao_minutos": 40,
      "barbeiro_ocupado": true
    },
    {
      "ordem": 2,
      "nome": "Pausa - Produto",
      "duracao_minutos": 50,
      "barbeiro_ocupado": false  ← PERMITE OUTROS AGENDAMENTOS
    }
  ]
}
```

### Arquivo: `services/servicos_fracionados.py`

Funções principais:

1. **`calcular_slots_ocupados()`**
   - Calcula todos os intervalos de tempo
   - Marca quais têm barbeiro ocupado

2. **`get_slots_bloqueados()`**
   - Retorna APENAS horários onde barbeiro está ocupado
   - Usado para validar conflitos

3. **`verificar_disponibilidade_fracionado()`**
   - Verifica se novo agendamento conflita
   - Considera apenas slots com barbeiro ocupado

4. **`horarios_conflitam()`**
   - Detecta sobreposição de horários
   - Lógica: (início1 < fim2) AND (início2 < fim1)

---

## 📋 Serviços Configurados

### ✂️ Serviços Rápidos (Simples)
- **Corte de Cabelo** - 40min - R$ 35,00
- **Barba** - 30min - R$ 25,00
- **Corte + Barba** - 60min - R$ 55,00

### ✨ Serviços Especiais (Fracionados)

#### 1. Luzes no Cabelo (135min total / 90min ocupado)
- Aplicação: 30min 🔒
- Ação: 45min ⏳ (barbeiro livre)
- Verificação: 20min 🔒
- Finalização: 40min 🔒
- **Valor:** R$ 150,00

#### 2. Platinado Completo (210min total / 120min ocupado)
- Aplicação: 40min 🔒
- Pausa 1: 50min ⏳ (barbeiro livre)
- Verificação + 2ª mão: 30min 🔒
- Pausa 2: 40min ⏳ (barbeiro livre)
- Matização: 50min 🔒
- **Valor:** R$ 200,00

#### 3. Coloração (100min total / 60min ocupado)
- Aplicação: 25min 🔒
- Fixação: 40min ⏳ (barbeiro livre)
- Lavagem: 35min 🔒
- **Valor:** R$ 120,00

---

## 🧪 Cenários de Teste

### Cenário 1: Platinado sem conflitos
```
10:00 - Platinado inicia (Cliente A)
10:40 - Cliente A aguarda → Barbeiro LIVRE
10:45 - Corte simples agendado (Cliente B) ✅ PERMITIDO
11:20 - Corte B finaliza
11:30 - Platinado continua (Cliente A)
```

### Cenário 2: Tentativa de conflito
```
10:00 - Platinado inicia (Cliente A)
10:20 - Tentativa de agendar corte ❌ BLOQUEADO
         (Barbeiro ocupado até 10:40)
10:40 - Agora sim pode agendar ✅
```

### Cenário 3: Múltiplos fracionados
```
09:00 - Luzes (Cliente A)
09:30 - A aguarda, barbeiro livre
09:35 - Corte (Cliente B) ✅
10:10 - Luzes de A continua
10:30 - Platinado (Cliente C) ❌ BLOQUEADO
         (Conflito com finalização de A)
```

---

## 🔄 Próximos Passos

### Etapa 1: Integração com Agendamento (PRÓXIMO)
- [ ] Adicionar campo `ServicoID` em agendamentos
- [ ] Modificar fluxo para escolher serviço
- [ ] Usar `verificar_disponibilidade_fracionado()` antes de confirmar

### Etapa 2: Interface no Chat
- [ ] Menu de seleção de serviços
- [ ] Mostrar resumo com etapas
- [ ] Alertar sobre duração total

### Etapa 3: Visualização de Agenda
- [ ] Mostrar horários com "janelas livres"
- [ ] Indicar quando barbeiro estará livre
- [ ] Sugerir melhores horários

### Etapa 4: Notificações
- [ ] Avisar cliente quando barbeiro voltar
- [ ] Lembrete de próxima etapa
- [ ] Estimativa de finalização

---

## 💡 Vantagens do Sistema

✅ **Para o Barbeiro:**
- Aproveita tempo ocioso
- Mais agendamentos por dia
- Maior faturamento

✅ **Para o Cliente:**
- Agendamento mais flexível
- Serviços premium disponíveis
- Transparência no processo

✅ **Para o Sistema:**
- Otimização automática
- Evita conflitos
- Escalável para múltiplos profissionais

---

## 🎨 Exemplos Visuais

### Agenda do Dia (Exemplo)

```
08:00 ███████████████ Corte (João)
09:00 ███████████████ Barba (Maria)
09:30 ████▓▓▓▓▓▓████ Luzes (Ana)
      ████           Aplicação
          ▓▓▓▓▓▓     Pausa (livre!)
                ████ Finalização
10:00 ░░░░░░░░░░░░░░░ LIVRE
10:30 ███████████████ Corte (Carlos) ← Agendado na pausa!
11:00 ░░░░░░░░░░░░░░░ LIVRE
```

**Legenda:**
- █ Barbeiro ocupado
- ▓ Cliente aguardando (barbeiro livre)
- ░ Horário disponível

---

## 📱 Como o Cliente Verá

**Ao escolher "Luzes":**
```
✨ LUZES NO CABELO

💰 Valor: R$ 150,00

⏱️ Etapas do Serviço:

🔒 Aplicação do Produto
   09:00 - 09:30 (Barbeiro ocupado)

⏳ Ação do Produto
   09:30 - 10:15 (Aguardando - barbeiro livre)

🔒 Verificação
   10:15 - 10:35 (Barbeiro ocupado)

🔒 Finalização
   10:35 - 11:15 (Barbeiro ocupado)

🏁 Horário de finalização: 11:15

💡 Durante a pausa, você aguarda confortavelmente
   enquanto o produto age!
```

---

**Status:** ✅ Sistema base implementado e testado  
**Próximo:** Integrar com fluxo de agendamento
