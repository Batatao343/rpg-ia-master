# SPEC — Fase 6.4: Encontros sistêmicos — detecção, surpresa e variedade

> **Status:** `draft`
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 4.6 (orçamento de encontro, `done`) · 6.3 (sorteio ponderado — integrar, não duplicar)
> **Desbloqueia:** viagem com tensão real (nem todo perigo é combate)

---

## 1. Contexto & Objetivo

Hoje encontro de viagem = combate, sempre, sem chance de evitar: `maybe_encounter`
(world_utils) decide SE, e o resultado é sempre luta com a criatura sorteada. O
jogador não usa percepção, não há armadilha, não há encontro social hostil-mas-
negociável. O backlog previa `encounter_agent` LLM; a fundação 4.6 tornou isso
desnecessário — dá pra fazer MELHOR com Python + os hooks existentes.

Esta spec: **detection check** determinístico (d20 + WIS vs DC do perigo) decide
se o jogador é SURPREENDIDO ou percebe antes; **tipo de encontro** sorteado por
danger/região (combate | armadilha | social | rastro); armadilha e rastro
resolvem em Python; social vira cena de NPC/storyteller com contexto injetado.
Sem nó novo no grafo — tudo passa pelos nós existentes com flags.

## 2. Requisitos

- **R1 (detecção)** — `world_utils.detection_check(player, danger, rng) ->
  {"perceived": bool, "roll", "dc"}`: d20 + mod WIS (+ bônus racial de save WIS)
  vs DC = 8 + 2×danger. Percebeu → escolha narrada (evitar caminho MAIS LONGO =
  +1 período de relógio, ou emboscar = player age primeiro no round 1).
  Surpreendido → inimigos agem primeiro no round 1 (iniciativa deles +5).
- **R2 (tipos)** — sorteio determinístico por danger (rng injetável):
  danger 1–2: combate 50% · rastro 30% · social 20%;
  danger 3–4: combate 60% · armadilha 20% · social 10% · rastro 10%.
- **R3 (armadilha)** — resolve 100% Python: save DEX vs DC = 10 + 2×danger;
  falha = dano `{danger}d6` + condição temática da região (veneno no pântano,
  sangramento nas montanhas — tabela curada `data/traps.json`, ~6 entradas);
  sucesso = nada + XP de esquiva (25). Narrador só descreve o resultado.
- **R4 (rastro)** — pista mecânica de valor: revela no Codex a criatura da
  região (grau "rumores" da 3.2 sem precisar encontrá-la) OU marca `hint` de
  tesouro (próximo TREASURE na região rola com +1 banda de raridade, uma vez).
- **R5 (social)** — encontro social hostil-mas-negociável: injeta NPC gerado
  (pipeline existente do npc_actor) com `disposition` derivada da fação
  dominante; a cena roteia pra NPC, não pra combate — brigar continua possível
  pela fala do jogador.
- **R6 (surpresa no combate)** — `combat_node` respeita `encounter_surprise`
  (flag transitória no state): surpreendido → ordem de iniciativa penalizada;
  emboscando → bônus. Flag consumida no primeiro round.
- **R7 (integração 6.3)** — a criatura do encontro vem do sorteio PONDERADO da
  6.3 (pressão de caça/fação) — esta spec não cria segundo sorteio.
- **R8** — Zero chamada LLM nova: detecção/tipo/armadilha/rastro são Python;
  social/combate usam os nós que já existem.

### Fora de escopo

- `encounter_agent` como nó LLM (descartado — Python cobre).
- Perseguição/fuga em mapa (fica narrativo).
- Armadilhas COLOCADAS pelo jogador (Sapador tem kit — gancho 4.x futuro).
- Encontros noturnos diferenciados (entra com a 6.5 clima/período).

## 3. Design técnico

| Arquivo | Mudança |
|---|---|
| `world_utils.py` | `detection_check`, `roll_encounter_type`, integração no fluxo de viagem (`travel`/`maybe_encounter`) |
| `data/traps.json` | ~6 armadilhas por região (dc_mod, damage, condition, descrição curta) |
| `state.py` | `WorldState.encounter_surprise: Optional[str]` ("player"\|"enemy"\|None, transitório) |
| `agents/storyteller.py` | viagem com encontro: injeta resultado mecânico no prompt (percebeu/armadilha/rastro) |
| `agents/combat.py` | round 1 lê `encounter_surprise` (iniciativa ±5), consome a flag |
| `agents/router.py`/`npc.py` | social: rota NPC com `active_npc_name` do gerado |
| `services/discovery.py` | rastro → grau "rumores" da criatura (3.2) |
| `tests/test_fase64.py` | suíte |

Decisões:
1. **Sem nó novo no grafo** — checklist CLAUDE.md intacto; flags transitórias +
   nós existentes.
2. **Percepção usa WIS de verdade** — primeiro uso mecânico de WIS fora de save;
   classes sábias (Pastor, Guardião) viajam mais seguras — identidade grátis.
3. **Armadilha dá XP na esquiva** — esquivar não pode ser pior que apanhar.

## 4. Plano passo a passo

1. **Etapa 1 (TDD):** `detection_check` (faixas, racial save bonus, rng);
   `roll_encounter_type` (distribuições semeadas).
2. **Etapa 2:** armadilha (`data/traps.json` + resolução + condição 4.2 +
   XP de esquiva); testes por região.
3. **Etapa 3:** rastro (codex 3.2 + hint de tesouro one-shot); testes.
4. **Etapa 4:** surpresa no combate (iniciativa ±5, flag consumida); social
   roteando pra NPC; testes de integração.
5. **Etapa 5:** storyteller ciente (prompt) + suíte completa + smoke offline.

## 5. Critérios de aceite

- [ ] Viagem em danger alto: às vezes percebe (escolha), às vezes é surpreendido (iniciativa)
- [ ] Armadilha causa dano/condição no save falho e XP na esquiva — números 100% Python
- [ ] Rastro alimenta o Codex 3.2 ou banda de tesouro (one-shot)
- [ ] Encontro social roteia pra NPC (não vira combate automático)
- [ ] Nenhuma chamada LLM adicionada (contar antes/depois)
- [ ] `uv run pytest` verde; saves antigos ok (flag transitória default None)

## 6. Smoke test com LLM real

1. Viagem com armadilha (rng forjado) → narração descreve a armadilha com os
   números do log. 2. Encontro social → NPC responde em persona. (≈3 requests.)

## 7. Riscos & compatibilidade

- `maybe_encounter` muda de forma — call sites/testes da Fase 2 revisados junto.
- Balance das distribuições/DCs: constantes nomeadas, playtest calibra.
- MockLLM: tudo determinístico; smoke real só valida narração.
