# SPEC — Remediação dos achados do comerciante real

> **Status:** `done`
> **Criada:** 2026-08-20 · **Atualizada:** 2026-08-20
> **Depende de:** `playtest-longo-perfil-comerciante` (`done`)
> **Desbloqueia:** `matriz-longrun-multiperfil-niveis`

---

## 1. Contexto & Objetivo

O run real `20260820-112050-208317` completou 200/200 sem erro mecânico, mas a
auditoria de 21 turnos encontrou três P1 e três P2 no relatório
`docs/playtest-comerciante-real-2026-08-20.md`. Esta spec corrige os seis antes
da matriz multiperfil, preservando a regra de que mecânica e estado autoritativo
são Python e a LLM apenas identifica/narra.

## 2. Requisitos

- **R1 — Observação não é transação:** consultar estoque, preço, oferta, margem
  ou escassez produz uma visão read-only do mercado. Não chama `execute_trade`,
  não cria `last_economy_action`, não altera ouro/inventário/estoque e não entra
  como compra/venda/craft na telemetria.
- **R2 — Intenção explícita vence:** frases que também contêm verbo inequívoco de
  comprar, vender ou fabricar continuam transações. O schema aceita `observe` e
  o fallback Python reconhece as consultas mesmo se todos os providers falharem.
- **R3 — Ledger visual correto:** venda mostra `-N× item`, compra/craft mostra
  `+N× item`; ouro usa o sinal de `gold_delta`. O texto canônico nunca contradiz
  o delta mecânico.
- **R4 — Cena limpa antes do encontro:** toda viagem limpa `in_scene` antes de
  rolar/retornar encontro. O update de combate inclui os NPCs limpos; contexto,
  router e aliados transitórios exigem vínculo com o local atual, salvo membro
  formal de `party`.
- **R5 — Estado do herói aterrado:** prompt do storyteller recebe nível,
  Vitalidade e ouro atuais. Um guard Python reconcilia apenas alegações de saldo
  pessoal contraditórias, sem alterar preços, recompensas ou quantias de NPCs.
- **R6 — Fallback rápido:** Groq vivo é o segundo candidato FAST. DeepSeek usa
  timeout próprio default de 12 s (configurável por
  `DEEPSEEK_TIMEOUT_SECONDS`); `LLM_TIMEOUT_SECONDS` explícito continua podendo
  sobrescrever o default global. Falha de conexão não pode consumir ~19 s em
  dois nós sucessivos antes de alcançar Groq.
- **R7 — Observabilidade precisa:** `narrative.recycled_npc` não acusa NPC apenas
  residual e ausente da cena/narração; ainda acusa NPC realmente usado fora da
  origem e sem party/reintrodução legítima.

### Fora de escopo

- Alterar preços, restock, margem ou balanceamento de combate.
- Garantir latência externa absoluta; o aceite controla timeout e p95, não a rede.
- Reescrever prosa livre inteira ou remover quantias legítimas de preços.

## 3. Design técnico

- `agents/loot.py`: `TradeIntent.mode` ganha `observe`; helper Python detecta
  consulta e renderiza `public_market_snapshot` sem LLM/nova transação.
- `agents/storyteller.py`, `services/npc_layers.py`, `party.py`: estado pós-viagem
  é a fonte do contexto e do encontro; gate comum por localização.
- `services/prose_guard.py`: `reconcile_player_gold_claims(text, gold)` pura.
- `llm_setup.py`: rota FAST e timeout específico do DeepSeek.
- `playtest/invariants.py`: warning de NPC exige uso observável real.
- Testes de regressão usam o wording e os estados exatos dos turnos 2, 10, 73,
  87–90 e 160 do relatório.

## 4. Plano passo a passo

### Etapa 1 — Mercado e ledger

1. **Testes:** consultas não mutam estado; consulta+“compro” negocia; venda usa
   sinal negativo; observação não infla transações.
2. **Implementação:** intenção `observe` e renderer mecânico.
3. **Verificação:** testes de loot/comerciante verdes.

### Etapa 2 — Cena e aliados

1. **Testes:** viagem com encontro limpa NPC antigo antes do `combat_agent`;
   NPC remoto não entra no contexto/router/aliados; party formal continua.
2. **Implementação:** snapshot de cena pós-viagem + gate por local.
3. **Verificação:** suites NPC/aliados/encontros verdes.

### Etapa 3 — Grounding e latência

1. **Testes:** saldo pessoal divergente é corrigido, preço não; rota FAST usa
   Groq segundo; timeout DeepSeek default/override.
2. **Implementação:** bloco autoritativo, guard de prosa e política de rota.
3. **Verificação:** Ruff + suíte completa.

## 5. Critérios de aceite

- [x] As consultas de vocabulário deixaram de virar compras rejeitadas; matriz A do comerciante completou 200 turnos sem erro ou warning.
- [x] Venda exibe remoção de item e ouro positivo coerentes.
- [x] NPC remoto não aparece como aliado/contexto após viagem com encontro.
- [x] Warning residual de Nami desaparece; caso material continua detectável.
- [x] Prosa não diverge do saldo pessoal autoritativo.
- [x] Fallback FAST chega ao Groq após no máximo um candidato de rede.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

A primeira matriz 10×200 da spec dependente é o smoke real amplo. Antes dela,
uma campanha dirigida curta deve provar `observe`, viagem+encontro e
`mock=false` sem fallback terminal.

## 7. Riscos & compatibilidade

- `observe` é aditivo; saves não persistem o schema Pydantic.
- NPC legado sem `home_location_id` continua elegível quando `in_scene=true`.
- Timeout DeepSeek pode mover uma resposta lenta válida ao Groq; a mecânica não
  muda e a telemetria registra o fallback.
