# SPEC-229 — Parsers de intenção em Python: viagem, fuga e pré-classificação do router

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · Fase 0 (viagem, anterior às specs; `world_utils`), SPEC-038 combate-lifecycle e SPEC-100 chase-progresso-e-fuga `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-202, SPEC-210, SPEC-212 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-01-03, 06-01, 06-02, 01-04, 02-08, 02-12 (`achados/01-grafo-turno.md`, `06-mundo.md`, `02-combate.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false` — escopo: três funções puras de parsing + um validador de prosa, com corpus de teste fechado
> **EVAL_AUTHORING_REQUIRED:** `true` — o corpus de routing/action (`evals/` SPEC-169) deve ganhar os casos negativos desta spec (autoria separada; o implementador NÃO edita o dataset)

---

## 1. Contexto & Objetivo

Três heurísticas Python decidem, ANTES do LLM, se a frase do jogador é viagem, fuga ou "história", e um
validador decide se a narração de fim de combate é descartada. Todas usam regex por prefixo/substring sem
fronteira e produzem **ações perdidas** (o turno é consumido, nada acontece) ou **ações trocadas** (ataque vira
fuga; conversa vira história). Reproduções executadas pelo orquestrador no HEAD `d6af933`:

- [F] `world_utils.is_travel_intent` (`world_utils.py:69-98`): `(vou|entro|saio|volto|sigo|atravesso|...)
  (\w+){0,5} (para|ate|a|em|n[oa]s?) \S+` casa **movimento dentro da cena** — "Entro na taverna e peço uma
  bebida", "Vou até a fogueira", "Vou em direção ao mercador", "Sigo em frente", "Volto a falar com o guarda",
  "Atravesso a ponte devagar" → `True`; `find_travel_destination` → `None`; `agents/storyteller.py:306-319`
  devolve a recusa canônica "Não há rota direta a partir de X. Saídas conectadas: …" **sem chamar o LLM**, com
  `turn_count` já incrementado. 3 de 5 frases cotidianas testadas foram recusadas.
- [F] A mesma regex NÃO reconhece a contração **"ao"**: "Vou ao Pântano da Melancolia" → `is_travel_intent
  False` enquanto `find_travel_destination` acha o destino. O storyteller então não chama `apply_travel`
  (relógio, `visited`, `current_location_id`, clima, replan e reset de cena ficam parados) mas o LLM narra o turno
  normal — pode descrever a chegada. "Vou ao mercado/porto/templo" é a forma mais comum em pt-BR.
- [F] `agents/router.py:29-32,144-146` `_EXPLICIT_STORY_RE = \b(descans\w*|durm\w*|acamp\w*|viaj\w*|vou\s+para|
  sigo\s+para)\b` roda ANTES do classificador e de `_EXPLICIT_HOSTILITY_RE`: "Pergunto ao **viajante**" → STORY
  (rota NPC perdida); "Ataco o **acampamento**" → STORY; "Compro uma barraca de **acampar**" → STORY (LOOT perdida);
  "Vou para cima do goblin e ataco" → STORY + recusa de rota.
- [F] `agents/combat.py:741` `flee_requested = re.search(r"\bfuj|fugir|escap|retir|recu|corr[oe]\b", intent)`:
  só `\bfuj` e `corr[oe]\b` têm fronteira. "Uso a poção para **recu**perar", "**Retir**o a espada e ataco",
  "**Recu**so a oferta e ataco" → fuga: a ação declarada vira `TurnDeclaration(kind="pass")`, inicia `chase`
  (consome 1 das 6 tentativas; na 6ª escapa automaticamente) e os inimigos agem.
- [F] `services/conflict_summary.validate_narrative_text` (`:306-325`) descarta a narração inteira do fim de
  combate quando "escapa/foge/vivo" aparece a ≤80 chars do nome de um morto: "Goblin 1 desaba…; o vento
  **escapa** pelas frestas…" → substituída por "Mortos: Goblin 1.".

Objetivo: parsers de intenção com **fronteiras de palavra, formas verbais fechadas e destino resolvível**;
precedência hostilidade > NPC/loot > história; e um corpus negativo congelado que impeça regressão.

## 2. Requisitos

- **R1** — [R] `is_travel_intent(text)` só devolve `True` quando (a) há verbo de deslocamento em forma fechada
  (`vou|vamos|viajo|viajamos|sigo|parto|me dirijo|retorno|volto|atravesso|caminho` + infinitivos após auxiliar
  "quero/vou/pretendo") E (b) o destino após a preposição resolve para um nó do mapa (`find_travel_destination`
  ≠ `None`) OU parece topônimo desconhecido (palavra capitalizada / ≥2 tokens capitalizados). Preposições aceitas:
  `para|pra|pro|até|a|ao|aos|à|às|rumo a|em direção a|em|no|na|nos|nas`. Nova assinatura:
  `is_travel_intent(text, world=None) -> bool` (sem `world`, mantém só (a) + topônimo). Corpus de teste (ver §3)
  com ≥ 12 positivos e ≥ 12 negativos; os 6 negativos da auditoria e "Vou ao Pântano da Melancolia" obrigatórios.
- **R2** — [R] O storyteller só emite a recusa "Não há rota direta…" quando `is_travel_intent(text, world)` é
  `True` E o texto cita um nome de local do mapa (ou topônimo desconhecido) que não é saída; caso contrário a
  ação segue como história livre (LLM chamado). Teste de reprodução: "Entro na taverna e peço uma bebida" em
  `nova_arcadia` → hoje recusa; depois narração normal (MockLLM) e `turn_count` avança 1.
- **R3** — [R] "Vou ao <saída conectada>" executa `apply_travel` (relógio, `visited`, `current_location_id`,
  `needs_replan` se região mudou). Teste: `nova_arcadia` → "Vou ao Pântano da Melancolia" → `current_location_id
  == "pantano_melancolia"` e `world_clock` avançou `travel_cost`.
- **R4** — [R] Router: `_EXPLICIT_HOSTILITY_RE` é avaliada ANTES de `_EXPLICIT_STORY_RE`; `_EXPLICIT_STORY_RE`
  usa formas verbais de 1ª pessoa com fronteira (`\b(descanso|durmo|acampo|viajo|vou para|sigo para)\b`), nunca
  prefixos `\w*`. Testes: "Pergunto ao viajante sobre a estrada" → NPC; "Ataco o acampamento dos bandidos" →
  COMBAT; "Compro uma barraca de acampar" → LOOT; "Vou para cima do goblin e ataco" → COMBAT; "Descanso aqui" →
  STORY; "Viajo para Skallgard" → STORY.
- **R5** — [R] Fuga em combate: `flee_requested` deriva de (a) `declaration.acao.kind == "flee"`, (b)
  `combat_flee_attempt` setado pelo router (`_combat_gate`), ou (c) regex fechada `\b(fujo|fugir|fugimos|foge|
  escapo|escapar|escapamos|recuo|recuar|me retiro|retirada|corro para longe|bato em retirada)\b`. Teste: as 3 frases
  da auditoria → `False`; "Fujo pela porta" → `True`; "Recuo para o corredor" → `True`.
- **R6** — [R] `validate_narrative_text` só rejeita quando o VERBO de sobrevivência tem como sujeito o nome do morto
  na mesma oração (padrão `nome(,|\s)(ainda\s)?(vivo|escapa|foge|se ergue|sobrevive)` com ≤ 3 tokens entre nome e
  verbo e sem ponto/`;` entre eles). Teste: a frase da auditoria é ACEITA; "Goblin 1 ainda vivo rasteja" é REJEITADA.
- **R7** — [R] Telemetria: toda recusa pré-LLM (viagem inválida, fuga detectada por regex, narração descartada) emite
  `rpg.intent_guard` com `{kind, matched, text_hash}` (sem texto cru em produção) para medir falsos positivos no playtest.
- **R8** — [R] Playtest offline (`uv run python -m playtest run --profile explorador,normal --turns 40`): zero
  ocorrências de "Não há rota direta" para ações do perfil `normal` que não citam local do mapa; `routes` do
  `normal` incluem NPC e LOOT.

### Fora de escopo

- Reescrever o classificador LLM do router ou o corpus protegido de `evals/` (handoff separado, §9).
- Viagem como turno dedicado/UI de mapa (SPEC-210); gesto de alvo (SPEC-205); desfecho/manifesto (SPEC-203).
- `blocked_routes` para o jogador (SPEC-017 fora de escopo por decisão).

## 3. Design técnico

### Arquivos alterados

- `world_utils.py` — `is_travel_intent(text, world=None)` (R1); `_TRAVEL_VERBS`, `_TRAVEL_PREPS` como constantes
  exportadas; `looks_like_toponym(text_after_prep) -> bool`.
- `agents/storyteller.py:299-319` — recusa condicionada a R2; chamada com `world`.
- `agents/router.py:29-32,144-146` — ordem hostilidade → NPC/loot explícitos → história; regex fechada (R4).
- `agents/combat.py:741` — `flee_requested` por R5 (regex em constante `_FLEE_RE` em `services/chase.py`).
- `services/conflict_summary.py:306-325` — `validate_narrative_text` por oração (R6).
- `services/turn_effects.py`/telemetria — evento `rpg.intent_guard` (R7).
- `tests/test_bug_intencao_parsers.py` — corpus fechado (dados em `tests/data/intent_corpus.json`, NÃO em `evals/`).

### Corpus mínimo (`tests/data/intent_corpus.json`)

```json
{"travel_pos": ["Vou para o Pântano da Melancolia", "Vou ao Pântano da Melancolia", "Viajo até Skallgard",
                "Sigo rumo a Brekmar", "Parto para as Profundezas", "Volto para Nova Arcádia"],
 "travel_neg": ["Entro na taverna e peço uma bebida", "Vou até a fogueira observar o fogo",
                "Vou em direção ao mercador", "Sigo em frente", "Volto a falar com o guarda",
                "Atravesso a ponte devagar", "O que sabe sobre Skallgard?"],
 "story_not_story": {"Pergunto ao viajante sobre a estrada": "npc", "Ataco o acampamento dos bandidos": "combat",
                     "Compro uma barraca de acampar": "loot", "Vou para cima do goblin e ataco": "combat"},
 "flee_neg": ["Uso a poção de cura para recuperar minhas forças", "Retiro a espada da bainha e ataco",
              "Recuso a oferta e ataco o goblin"],
 "flee_pos": ["Fujo pela porta", "Recuo para o corredor", "Bato em retirada"]}
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
1. `tests/test_bug_intencao_parsers.py`: parametrizado pelo corpus — `test_travel_intent_corpus` (R1),
   `test_storyteller_local_movement_not_refused` (R2), `test_vou_ao_applies_travel` (R3), `test_router_precedence`
   (R4), `test_flee_regex_corpus` (R5), `test_narrative_validator_sentence_scope` (R6).
### Etapa 1 — `world_utils` + storyteller (R1–R3)
### Etapa 2 — router + combate + validador (R4–R6) + telemetria (R7)
### Etapa 3 — regressão `uv run pytest` + playtest offline (R8) + handoff do corpus de eval (§9)

## 5. Critérios de aceite

- [ ] Corpus: 100% nos positivos/negativos listados; testes vermelhos no HEAD → verdes.
- [ ] `tests/test_fase0.py`, `test_mapa_interiores.py`, `test_grounding_boundaries.py`, `test_combat_lifecycle.py`,
      `test_router*.py`, `test_conflict_summary_lifecycle.py` verdes (ou diff justificado — ex.: teste que
      afirmava recusa para "entro na…").
- [ ] `uv run pytest` verde; playtest offline R8 com run_id registrado.
- [ ] Guard de FallbackLLM: não se aplica.

## 6. Smoke test com LLM real

1. "Entro na taverna e peço uma bebida" → narração de cena, sem recusa de rota.
2. "Vou ao <saída>" → HUD muda o local e a hora.
3. Em combate: "Uso a poção para recuperar forças" → poção usada, sem perseguição.
4. "Pergunto ao viajante sobre a estrada" → rota NPC (log `[ROUTER] npc_actor`).

## 7. Riscos & compatibilidade

- Falsos negativos de viagem (frase criativa) caem na história livre — o LLM pode narrar deslocamento sem mover
  o estado (já acontece hoje com "ao"); mitigado por R1(b) + SPEC-210 (viagem pela UI).
- Perfis do playtest que dependem de "Vou para X": continuam válidos (positivos do corpus).
- Eval SPEC-169: matriz de confusão pode mudar — registrar como mudança de produto, não de régua.

## 8. Pontos de decisão do dono

- **D-A (topônimo desconhecido):** recusar com mensagem de mapa (default) ou deixar o LLM narrar como lugar
  fictício dentro do local atual.
- **D-B (fuga só estruturada):** desligar a regex (c) de R5 e depender só de router/declaração (mais seguro,
  perde "fujo!" em texto livre sem router) — default: manter regex fechada.

## 9. Evidência requerida

- `uv run pytest` completo; saída vermelha/verde do corpus; run_id do playtest offline com grep de
  `rpg.intent_guard` e de "Não há rota direta".
- **Handoff de eval (EVAL_AUTHORING_REQUIRED):** adicionar ao dataset de routing (SPEC-169) os casos de
  `story_not_story`/`travel_neg` como variantes metamórficas — autoria por quem não implementa, com relock de hash.
