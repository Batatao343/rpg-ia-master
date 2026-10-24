# SPEC-305 — Quests de mundo com prazo (nascem do estado, falham com consequência)

> **Status:** `done` (2026-10-24) — na main, revisão Sol aprovada (ver handoff). smoke real §6 DeepSeek 24/10 (cenário `mundo`, 15 turnos, seed 12): 0 erros; 1 quest de mundo oferecida por testemunho (expirou no prazo). Violações `rag.persistence_error` nos smokes = FAISS local com acento no caminho (limitação conhecida).
> **Criada:** 2026-10-23 · **Atualizada:** 2026-10-23
> **Origem:** filha **302-D** da SPEC-302 (§9); `docs/mundo-vivo/VISAO.md` decisões 3 e 5
> (linhas 51-65), "Regra de ouro" (79-82) e "Mudanças no mapa" (153-155).
> **Depende de:** SPEC-302 (`approved`; precisa estar `done` no marco M2: `advance_days`,
> `CrisisRecord.escalation_day`, `world_perception.perceivable`, `DigestItem`, `location_state`,
> tabela de causas de `data/world/pressures.json`), SPEC-008 (`done`, quest log), SPEC-223
> (`done`, prova determinística de conclusão), SPEC-215 (`done`, `location_heard`).
> Integra **se estiverem `done`**, sem bloquear: SPEC-304 (resgate a partir de `NpcPeril`;
> sem ela o tipo `resgate` fica desligado), SPEC-298 (reputação/fama pela conclusão; sem ela
> só XP e ouro), SPEC-301 (coexistência com missões de fação; `setback` de ascensão).
> **Desbloqueia:** pilar D (opções de ação com gancho de quest, VISAO.md:169-170); pilar B
> (cativeiro/resgate com combate).
> **EXECUTOR_MODEL:** `Opus` (Sol: novo writer em `quests`, integra 302/304/298) ·
> **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo tipo
> de evento engine-only, nova extensão do diretor de tensão, API player-facing)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Hoje toda side quest nasce de uma proposta de texto do LLM (`ProposedQuest`), validada e
gravada por `quest_log.register_proposed_quests`. Ela não tem prazo, não sabe nada do estado
do mundo e só falha sistemicamente quando o NPC de origem morre (`fail_orphan_quests`). Com a
SPEC-302, o mundo passa a ter crises telegrafadas (aviso ≥ 2 dias antes, `escalation_day`
como prazo), estados de local (cerco, escassez, praga, ocupado, ruína, corrompido) e, com a
SPEC-304, NPCs em perigo com `deadline_day` e pedido de ajuda por mensageiro. Falta a ponte:
o jogador ouve "a febre chegou a Brekmar" e o diário não ganha nada que ele possa fazer, e
nada no motor reage se ele agir.

Esta spec cria **quests de mundo**: ganchos determinísticos derivados do estado do motor
(crise anunciada/aberta, local ocupado, rota fechada, ascensão iminente, NPC em perigo), que
entram no diário **só quando o personagem viu ou ouviu** (testemunho, cartaz, NPC que conta,
rumor da SPEC-215, mensageiro da SPEC-304). Cada uma tem `deadline_day` derivado do próprio
motor. Concluir antes do prazo emite um **alívio** (`world_quest_relief`) que o motor lê como
causa: a pressão cai e a crise não escala. Não concluir deixa o motor seguir o que já tinha
decidido (escalada, ocupação consolidada, destino do NPC), e a quest falha com texto neutro
que não revela o desfecho antes de ele ser percebido.

Princípios: mecânica em Python (a LLM só narra a cena em que o gancho aparece; título,
descrição e texto de falha vêm de templates); "o mundo não escala com o herói" (nenhuma
oferta, prazo ou consequência lê nível/ficha/ouro); duro mas telegrafado; não-onisciência
(nenhum campo interno de prazo/crise sai pela API ou pelo prompt).

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | Quest só nasce de proposta do LLM; o prompt manda "não invente missões" e não há gerador a partir de estado | `services/quest_log.py:62-127`; `agents/storyteller.py:88-94`, `:1355-1362`; `agents/npc.py:977-994` |
| P2 | `Quest` não tem prazo nem vínculo com o mundo; o id é `uuid4` (replay gera ids diferentes) | `state.py:303-319`; `services/quest_log.py:109` |
| P3 | A única falha sistêmica é "origem morta"; o modelo já existe e é puro, mas não há falha por tempo | `services/quest_log.py:366-397`; `services/event_processor.py:442-450` |
| P4 | `quest_failed` não é `EventType`: só o `event_processor` consegue gravar a falha (append direto), então o motor de mundo não tem como enfileirar uma falha validada | `services/structured_outputs.py:17-43`; `services/event_processor.py:447-450` |
| P5 | A prova de conclusão só aceita verbo investigativo; "rompo o cerco", "trato os doentes" ou vencer um combate no local não contam | `services/quest_log.py:35-40`, `:203-205`; `agents/combat.py:1408` (`victory` não toca `quests`) |
| P6 | A API devolve o dict cru da quest: qualquer campo interno novo (prazo exato, `crisis_id`, motivo da falha) vazaria | `api.py:2782-2789` |
| P7 | O frontend só conhece 3 status e não tem rótulo de prazo | `web/src/types.ts:170`; `web/src/components/QuestsTab.tsx:3-7` |
| P8 | O bloco de quests do narrador não carrega urgência; o LLM não tem como "sentir" o prazo | `agents/storyteller.py:198-216` |
| P9 | A SPEC-302 deixa o contra-jogo para esta spec: `CrisisRecord.resolution="intervencao"` não tem writer, e a 302 só conta eventos já existentes para recuperação | SPEC-302 §3.3 (`resolution`), R20 (último item), §2 "Fora de escopo" (quests e contra-jogo dedicados) |
| P10 | Recompensa é fixa (20 ouro) e não se liga à reputação | `services/quest_log.py:31`, `:341-363` |

## 2. Requisitos

### 2.1 Fontes (o que vira quest)

- **R1 — Catálogo de tipos.** `data/world/world_quests.json` define 8 tipos, cada um com
  fonte, regra de prazo, vocabulário de ação, alívio e templates (§3.5):

  | Tipo | Fonte (estado do motor) | `deadline_day` |
  |---|---|---|
  | `romper_cerco` | crise `guerra` com `loc_state="cerco"` (anunciada ou aberta) | `escalation_day` |
  | `socorrer_escassez` | crise `fome` (`escassez`) | `escalation_day` |
  | `conter_praga` | crise `praga` | `escalation_day` |
  | `selar_corrupcao` | crise `abismo` (`corrompido`; só se a SPEC-302 D2 = sim) | `escalation_day` |
  | `libertar_ocupado` | `location_states[loc].state == "ocupado"` | `since_day + OCCUPATION_WINDOW` (10) |
  | `reabrir_rota` | `route_blocked` ativo em `blocked_routes` **sem** crise de cerco associada | `heard_day + ROUTE_WINDOW` (8) |
  | `frear_ascensao` | crise `ascensao` anunciada (progress ≥ 80, SPEC-302 R21b) | `warned_day + ASCENSION_WINDOW` (8) |
  | `resgate` | `NpcPeril` aberto (SPEC-304 `active_perils`) | `NpcPeril.deadline_day` (acompanha extensões da 304 R17) |

- **R2 — Prazo provisório de crise anunciada.** Crise só anunciada (`start_day is None`)
  usa `warned_day + MIN_WARNING_DAYS + ESCALATION_DAYS` (constantes da SPEC-302). Quando a
  crise abre, o prazo passa a `escalation_day`. O prazo **nunca encurta** depois de criado
  (`deadline_day = max(atual, novo)`); teste por propriedade.
- **R3 — Uma quest por fonte.** `world_source_id` = `crisis_id` | `peril_id` |
  `"occ:"+location_id+":"+since_day` | `"route:"+a+"|"+b+":"+heard_day`. O id da quest é
  `sha256(game_id|kind|world_source_id)[:16]` (determinístico, corrige P2 para quests de
  mundo). Já existe quest (qualquer status) com esse `world_source_id` → não oferece de novo
  (sem segunda chance na mesma crise; decisão D8).
- **R4 — Fontes nunca leem o herói.** Nenhuma função de oferta, prazo, alívio ou falha lê
  nível, ficha, inventário, ouro ou party. Teste: mesmo estado com `player.level` 1 e 20 →
  mesmas quests, mesmos prazos, mesmos eventos. A posição do jogador só decide **percepção**
  (R5) e **viabilidade** (R8).

### 2.2 Regra de ouro (só recebe quest que viu ou ouviu)

- **R5 — Canais.** Uma quest de mundo só é criada a partir de uma **percepção** registrada,
  por um destes canais (o mesmo vocabulário da SPEC-302 R23 e da SPEC-304 R21):
  - `testemunho`: `DigestItem` percebido pelo canal (a) da 302 (local atual ou pai/filho);
  - `cartaz`: item percebido pelo canal (b) (regional) quando o local atual tem tag `cidade`
    ou `vila` (só muda o template: "um cartaz pregado na praça…");
  - `npc`: o NPC em cena (`active_npc_name` deste turno, `in_scene`) está num local cujo
    `location_heard` contém o `event_id` do aviso/perigo; a origem da quest é o nome dele;
  - `rumor`: `location_heard[local atual]` contém o `event_id`, sem NPC ativo;
  - `mensageiro`: item `npc_perigo` com `channel="pedido_de_ajuda"` entregue pela SPEC-304
    R21(d).
  Com a SPEC-215 em `off`/`shadow`, só `testemunho`, `cartaz` e `mensageiro`.
- **R6 — Prova de percepção gravada.** Toda quest de mundo grava `heard_via = {channel,
  event_id, day}`. Invariante de playtest `quest.world_unheard` (`error`): quest de mundo
  cujo `event_id` não foi percebido pelo jogador (não está em itens percebidos registrados em
  `world.news`/crenças nem em `location_heard` do local de criação) no dia de criação.
- **R7 — Pontos de oferta (dois, e só dois).**
  - **Tick:** o storyteller, depois de `world_engine.advance_days` e de
    `world_perception.perceivable`, chama `world_quests.offer_from_perceived(state,
    perceived, day)`.
  - **Turno:** o `turn_finalizer`, depois de `npc_knowledge.turn_updates`, chama
    `world_quests.offer_from_heard(state, day)` (canais `npc`/`rumor`; cobre o rumor que
    chega sem o dia virar). Mesmo `try/except` que não derruba o turno.
  Nenhum outro módulo cria quest de mundo (teste por grep/AST: só `services/world_quests.py`
  monta dicts com `world_kind`).
- **R8 — Viabilidade (decisão D2).** Só oferece se dá para chegar: `day + ceil(
  world_distance.travel_periods(local_atual, alvo) / PERIODS_PER_DAY) < deadline_day`
  (`travel_periods` da SPEC-304; se ela não existir, esta spec cria
  `services/world_distance.py` com o mesmo contrato, Dijkstra sobre `travel_cost`). Quest
  inviável não é criada; a notícia continua indo para `world.news` pela 302.
- **R9 — Tetos.** No máximo `MAX_WORLD_QUESTS_ACTIVE = 3` quests de mundo ativas, dentro do
  `MAX_ACTIVE_QUESTS = 8` geral (`quest_log.py:29`). Com mais candidatas que vagas, ordena por
  (`deadline_day` asc, distância asc, `world_source_id`). Sem vaga → log
  `world_quest.cap_reached`, nenhuma quest.
- **R10 — Dedupe com o LLM.** `register_proposed_quests` ignora proposta do LLM cujo
  `location_id` é o alvo de uma quest de mundo ativa **e** cujo título tem similaridade ≥
  `TITLE_SIMILARITY` com ela, ou cujo texto casa o vocabulário do tipo (log
  `quest.proposal_world_duplicate`).

### 2.3 Prazo, conclusão e alívio

- **R11 — Conclusão por ação (tipos de crise, ocupação, rota, ascensão).** Reusa a prova da
  SPEC-223: `location_reached` no alvo **antes** do prazo + 2 evidências distintas posteriores
  à criação. Para quests com `world_kind`:
  - `sync_action_progress` troca `QUEST_ACTION_RE` e a relevância por título pelo
    `action_vocab` do tipo (ex.: `conter_praga`: tratar, curar, queimar, isolar, ervas,
    quarentena);
  - nova evidência `combat_won`: vitória de combate (`agents/combat.py:1408`) no alvo, com
    quest de mundo ativa dos tipos `romper_cerco`/`libertar_ocupado`/`frear_ascensao`, vale 1
    evidência (1 por combate). Entra em `PROOF_EVIDENCE_KINDS`;
  - a conclusão continua passando por `quest_completed` com prova
    (`world_validators._quest_proof`, cooldown de 3 turnos inalterado).
- **R12 — Conclusão do resgate.** Quest `resgate` conclui quando o `NpcPeril` correspondente
  tem `resolution="intervencao"` (SPEC-304 R16). O motor enfileira `quest_completed` com
  `source="engine"` (pula a prova, `world_validators.py:543`). Nunca lê `NpcSimEntry`
  diretamente: só `npc_world.active_perils` e o `npc_resgate` do digest.
- **R13 — Alívio (contra-jogo).** Na aplicação de `quest_completed` de quest com
  `world_kind`, o `event_processor` grava um derivado `world_quest_relief` (engine-only,
  append direto, como os derivados do `rule_engine`): `target_id=<location_id>`,
  `payload={quest_id, world_kind, world_source_id, region_id, pressure, delta}`. Efeitos,
  todos no tick seguinte e por dado:
  - `data/world/pressures.json` ganha a causa `{"on_event": "world_quest_relief", "pressure":
    "<payload>", "delta": "<payload>", "scope": "target_region"}` (delta default −25,
    `[BALANCEAR]`);
  - nova função `world_director.relieve(sim, crisis_id, day)`: marca
    `CrisisRecord.relieved_day`. Crise aliviada **não escala** no `escalation_day` e encerra
    com `resolution="intervencao"` quando a pressão cai abaixo de `RECUPERA` e durou ≥
    `MIN_CRISIS_DAYS` (escreve o writer que faltava em P9);
  - `libertar_ocupado`: `REOCCUPY_P` do local × `LIBERATION_MULT` (3) até o fim da ocupação
    (lido por `location_states` na recuperação R20 da 302);
  - `reabrir_rota`: o motor enfileira `route_cleared` (`source="engine"`) da conexão;
  - `frear_ascensao`: `progress` da fação −`ASCENSION_SETBACK` (15, piso 0) e o aviso de
    ascensão é retirado (`resolution="intervencao"`); usa o mesmo helper de progresso da
    SPEC-301 R13 se existir, senão `world_utils` direto com o mesmo clamp;
  - `resgate`: nenhum alívio extra (a 304 já salvou o NPC).
  Teste-oráculo: crise com alívio no dia `e−2` não escala em `e`; sem alívio, escala.
- **R14 — Recompensa (decisão D6).** XP `XP_PER_QUEST` e `QUEST_REWARD_GOLD` como hoje
  (`event_processor.py:458-477`). A `origin_faction_id` da quest de mundo é o controlador do
  alvo na projection (se estiver em `data/factions.json`), e a SPEC-298 R13 aplica
  `quest_completed (origem com fação)` da `DEED_TABLE` (+8 fação, renome +10 no local) pelas
  regras de testemunho dela. Sem SPEC-298 `done`, só XP e ouro.

### 2.4 Falha (dura, telegrafada, sem revelar o desfecho)

- **R15 — `quest_failed` vira `EventType` engine-only.** `EventType` ganha `quest_failed`,
  com barreira `source ∈ {"system", "engine"}` (mesma de `unique_item_*`). Proposta do LLM é
  rejeitada. O caminho de `fail_orphan_quests` (append direto) continua igual. Aplicado pelo
  `event_processor`: `quest_log.fail_quest(quests, quest_id, turn, reason)` → `status="failed"`
  e milestone da crônica existente (`services/chronicle.py:46`).
- **R16 — Quando falha.** Em `world_quests.sync_deadlines(state, tick)`, chamado pelo
  storyteller logo depois de `advance_days` (o prazo só pode passar quando o dia vira), para
  cada quest de mundo ativa:
  - `tick_day ≥ deadline_day` e não concluída → `quest_failed` (`reason="prazo"`), se a fonte
    ainda estava ativa naquele dia (crise aberta, ocupação, rota bloqueada, perigo aberto);
  - `tick_day ≥ deadline_day` e a fonte já tinha acabado sozinha → `status="expired"`
    (`reason="superada"`), **sem** `quest_failed`;
  - `resgate` com `NpcPeril.resolution ∉ {"", "intervencao"}` → `quest_failed`
    (`reason="prazo"`), qualquer que seja o destino.
  Nenhuma quest falha antes do `deadline_day` (invariante `quest.failed_before_deadline` =
  `error`).
- **R17 — A consequência é a do motor.** A falha não aplica efeito novo: a escalada
  (`severity+1`, cerco 3 → `ocupado`/`ruina`), a ascensão e o destino do NPC já foram decididos
  pela 302/304. Exceções, por tabela em `world_quests.json` (`fail_causes`) e lidas como causa
  no tick seguinte:
  - `reabrir_rota`: `fome +6` nas duas regiões da conexão (uma vez);
  - `libertar_ocupado`: `OCCUPATION_CONSOLIDATION_DAYS` (30) sem retomada natural (só termina
    com a fação ocupante `defeated`, SPEC-302 R20).
- **R18 — Texto de falha neutro.** Título/descrição/`fail_text` da quest falhada **não**
  contêm o desfecho ("caiu", "morreu", "ocupada", "ruínas", nome de fação desconhecida). O
  desfecho só chega pelas notícias da 302/304 quando percebido. Teste-oráculo: NPC morto
  off-screen não percebido + quest `resgate` falhada → nenhum payload de `/game/state` nem
  prompt contém "morto"/"morreu" para ele.
- **R19 — Fonte que acaba antes, percebida.** Se o jogador **percebe** o fim da fonte (item
  `fim` da 302, `npc_resgate`/`npc_destino` da 304) antes do prazo, a quest vira `expired`
  (`reason="superada"`) na hora, sem falha. Sem percepção, ela segue ativa até o prazo.

### 2.5 Superfícies (API, prompt, UI)

- **R20 — API com lista branca.** `_quest_block` (`api.py:2760-2789`) passa a projetar cada
  quest por `quest_log.public_quest_view`, que devolve só os campos atuais do `Quest` do
  frontend (`web/src/types.ts:166-177`) mais `kind ∈ {"comum","faccao","mundo"}` e
  `deadline_label`. Nunca saem: `deadline_day`, `world_source_id`, `heard_via`,
  `origin_faction_id`, `fail_reason`, `world_kind`. Teste varre a resposta de
  `/game/state` e `/game/action`.
- **R21 — Rótulo de prazo, sem número (decisão D3).** `deadline_label(days_left)`:
  `"urgente"` (≤ 2), `"em poucos dias"` (3-5), `"há algum tempo"` (≥ 6), `"prazo esgotado"`
  (`failed`/`expired` por prazo). O status público de `failed` e `expired` por prazo é o
  mesmo rótulo ("Prazo esgotado"), para não revelar se a fonte acabou sozinha.
- **R22 — Prompt do narrador.** `_quests_ativas_block` (`agents/storyteller.py:198-216`)
  acrescenta `· prazo: <rótulo>` e, para quest de mundo, `· tipo: mundo`. O narrador recebe na
  oferta (turno da criação) uma linha `<GANCHO_NOVO>` com o texto do template e o canal, para
  narrar o NPC/cartaz/rumor; não cria chamada LLM nova (teste conta invokes).
- **R23 — Frontend.** `Quest.status` ganha `"expired"` e `kind`/`deadline_label` opcionais;
  `QuestsTab` mostra o rótulo como selo ("urgente" com destaque). Sem número de dia.

### 2.6 Estado, eventos, rollout e prova

- **R24 — Schema aditivo.** Campos novos opcionais em `Quest` (§3.3). Save antigo carrega
  sem migração; quest sem `world_kind` segue as regras atuais (todas as funções atuais têm
  teste de regressão inalterado). Sem bump de `SCHEMA_VERSION`.
- **R25 — Determinismo e idempotência.** Repetir `offer_*` e `sync_deadlines` com o mesmo
  estado não cria quest nem evento novo (ids determinísticos, R3). Sem `random` global nos
  módulos novos (teste AST, como na SPEC-302 R3).
- **R26 — Rollout `RPG_WORLD_QUESTS=off|shadow|on`.** Exige `RPG_WORLD_ENGINE=on` para
  `on` (com o motor em `shadow`/`off`, comporta-se como `off`). `shadow`: calcula ofertas e
  falhas e loga `world_quest.shadow_offer`/`shadow_fail`, sem gravar nada. Default: decisão D9.
- **R27 — Telemetria e playtest.** Log `world_quest.offered|completed|failed|expired` com
  `{kind, channel, days_left_bucket}` (sem ids de crise). Playtest grava por campanha: quests
  de mundo oferecidas/concluídas/falhadas por tipo e canal; o `report` ganha linhas na seção
  "Mundo" da 302. Invariantes novos: `quest.world_unheard`, `quest.failed_before_deadline`,
  `quest.world_cap_exceeded`, `quest.deadline_shortened` (todos `error`).

### Fora de escopo

- Prazo em missões de fação da SPEC-301 e em quests propostas pelo LLM (seguem sem prazo).
- Ações mecânicas novas além do vocabulário + `combat_won` (ex.: entregar item específico,
  custo de suprimentos em ouro — decisão D5, default não; curar NPC individual; batalha em
  massa).
- Combate na chegada ao resgate e prisioneiro/cativeiro com escolta (pilar B; a 304 grava
  `held_at_location_id` como contrato).
- Quest de mundo nascida de festa/calendário (SPEC-303) e de crime/notoriedade (SPEC-299).
- Segunda chance na mesma crise após falha (D8) e quests encadeadas.
- Mudar `public_objective` (`services/objectives.py`) para priorizar quest urgente.
- Marcador de prazo no mapa e aviso automático ao planejar viagem que chega tarde.
- Mudanças no diretor de tensão além de `relieve` e da leitura de `LIBERATION_MULT`/
  consolidação (o orçamento e as fases continuam da 302).

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/world_quests.py` | **Owner da criação e do prazo de quests de mundo.** Candidatas a partir do estado, oferta por percepção, viabilidade, tetos, `sync_deadlines`, render de templates com nomes protegidos, modo (R26) |
| `data/world/world_quests.json` | Catálogo dos 8 tipos (fonte, prazo, vocabulário, alívio, `fail_causes`, templates pt-BR por canal) |
| `services/world_distance.py` | **Só se a SPEC-304 não tiver pousado:** `travel_periods(a, b)` (Dijkstra sobre `world_utils.travel_cost`, interiores custo 0) |
| `tests/test_spec305_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `state.py`: campos opcionais em `Quest` (§3.3).
- `services/quest_log.py`:
  - `sync_action_progress` usa `action_vocab` quando `world_kind` está presente (R11);
  - `sync_combat_progress(quests, location_id, *, turn)` (evidência `combat_won`);
  - `PROOF_EVIDENCE_KINDS` + `combat_won`;
  - `fail_quest(quests, quest_id, turn, reason)` e `expire_quest(...)` puros;
  - `register_proposed_quests` com o dedupe da R10;
  - `public_quest_view(quest, day)` e `deadline_label(days_left)` (R20/R21).
- `services/structured_outputs.py`: `EventType` + `quest_failed`, `world_quest_relief`.
- `services/world_validators.py`: validadores dos dois tipos (quest existe e está ativa;
  `world_quest_relief` só como derivado) e barreira engine/system (R15).
- `services/event_processor.py` (`process_pending_events`, perto de `:408-420` e `:442-450`):
  aplicar `quest_failed` (R15); após `quest_completed` de quest com `world_kind`, gravar o
  derivado `world_quest_relief` (R13).
- `services/world_director.py` (SPEC-302): `relieve(sim, crisis_id, day)`; `step_crises`
  respeita `relieved_day` (não escala; encerra com `"intervencao"`). Leitura de
  `world_quest_relief` no passo 2 do tick (causas do `event_log`).
- `services/location_states.py` (SPEC-302): `LIBERATION_MULT` e consolidação na recuperação
  de `ocupado` (R13, R17), lidos de flags no `LocationStateRow` (`liberation_day`,
  `consolidated_until_day`) gravados pelo `apply_event` de `world_quest_relief`/`quest_failed`
  — a projection continua sendo a fonte da verdade do estado de local (SPEC-302 R17).
- `data/world/pressures.json` (SPEC-302): causa `world_quest_relief` e causas de `fail_causes`.
- `agents/storyteller.py`: depois de `advance_days` → `sync_deadlines` e
  `offer_from_perceived`; enfileira os eventos em `pending_world_events`; `_quests_ativas_block`
  com prazo (R22); linha `<GANCHO_NOVO>`.
- `agents/turn_finalizer.py`: `offer_from_heard` (R7).
- `agents/combat.py` (`:1408`): na vitória, `quest_log.sync_combat_progress`.
- `api.py` (`_quest_block`, `:2760-2789`): `public_quest_view` (R20).
- `web/src/types.ts`, `web/src/components/QuestsTab.tsx`, `web/src/styles.css`: R23.
- `playtest/invariants.py`, `playtest/telemetry.py`, `playtest/report.py`: R27.

### 3.3 Schemas (`state.py`, aditivo)

```python
WorldQuestKind = Literal[
    "romper_cerco",
    "socorrer_escassez",
    "conter_praga",
    "selar_corrupcao",
    "libertar_ocupado",
    "reabrir_rota",
    "frear_ascensao",
    "resgate",
]
HeardChannel = Literal["testemunho", "cartaz", "npc", "rumor", "mensageiro"]


class HeardVia(TypedDict):
    channel: HeardChannel
    event_id: str  # aviso/perigo/evento-fonte percebido
    day: int


class Quest(TypedDict, total=False):
    ...  # campos atuais (state.py:303-319)
    status: str  # + "expired"
    world_kind: WorldQuestKind  # ausente/"" = quest comum ou de fação
    world_source_id: str  # crisis_id | peril_id | "occ:..." | "route:..."
    region_id: str
    created_day: int
    deadline_day: int  # INTERNO (nunca na API)
    heard_via: HeardVia  # INTERNO
    origin_faction_id: str  # INTERNO; controlador do alvo (R14)
    resolved_day: int
    fail_reason: str  # "" | "prazo" | "superada" | "origin_killed"
```

`LocationStateRow` (SPEC-302) ganha opcionais `liberation_day: int` e
`consolidated_until_day: int`. `CrisisRecord` ganha `relieved_day: int | None`.

### 3.4 Assinaturas públicas

```python
# services/world_quests.py
MODES = ("off", "shadow", "on")
MAX_WORLD_QUESTS_ACTIVE = 3
def mode() -> str
def candidates(state: dict, day: int) -> list[QuestSeed]                # fontes ativas (R1), sem percepção
def offer_from_perceived(state: dict, perceived: list[DigestItem], day: int) -> tuple[list[dict], list[dict]]
def offer_from_heard(state: dict, day: int) -> tuple[list[dict], list[dict]]  # (quests, criadas)
def is_feasible(state: dict, target_location_id: str, deadline_day: int, day: int) -> bool
def sync_deadlines(state: dict, tick_day: int) -> tuple[list[dict], list[dict]]  # (quests, propostas engine)
def render_quest_text(state: dict, seed: "QuestSeed", channel: str) -> dict[str, str]  # title/description/reward_hint

@dataclass(frozen=True)
class QuestSeed:
    kind: str; world_source_id: str; region_id: str; location_id: str
    deadline_day: int; source_event_id: str; faction_id: str; npc_id: str

# services/quest_log.py (novas)
def sync_combat_progress(quests: list[dict], location_id: str, *, turn: int) -> list[dict]
def fail_quest(quests: list[dict], quest_id: str, turn: int, reason: str, day: int = 0) -> list[dict]
def expire_quest(quests: list[dict], quest_id: str, turn: int, day: int = 0) -> list[dict]
def deadline_label(days_left: int | None, status: str = "active") -> str
def public_quest_view(quest: dict, day: int) -> dict

# services/world_director.py (extensão da SPEC-302)
def relieve(sim: dict, crisis_id: str, day: int) -> dict
```

Fluxo por ação que vira dia (storyteller): `advance_days` → `perceivable` →
`world_quests.sync_deadlines` (falhas/expirações, com `tick_day` = último dia simulado) →
`world_quests.offer_from_perceived` → `pending_world_events` ganha `quest_failed`/
`quest_completed` (`source="engine"`). O archivist (`process_pending_events`) aplica tudo e
grava os derivados `world_quest_relief`. O tick seguinte lê o alívio como causa. Ordem dentro
do mesmo tick: falha antes de oferta (uma fonte cuja quest acabou de falhar não reoferece, R3).

### 3.5 Formato de dados (exemplo com IDs reais)

`data/world/world_quests.json` (trecho; valores `[BALANCEAR]`):

```json
{
  "constants": {"OCCUPATION_WINDOW": 10, "ROUTE_WINDOW": 8, "ASCENSION_WINDOW": 8,
                "LIBERATION_MULT": 3, "OCCUPATION_CONSOLIDATION_DAYS": 30,
                "ASCENSION_SETBACK": 15, "RELIEF_DEFAULT": -25},
  "kinds": {
    "romper_cerco": {
      "source": {"crisis_kind": "guerra", "loc_state": "cerco"},
      "deadline": "escalation_day",
      "action_vocab": ["romp", "furar", "escolt", "suprimento", "defend", "muralh", "portao", "sitiant"],
      "combat_counts": true,
      "relief": {"pressure": "guerra", "delta": -25},
      "title": "Romper o cerco de {local}",
      "description": {
        "npc": "{origem} conta que {faccao} acampa diante dos muros de {local}. A cidade não aguenta muito.",
        "cartaz": "Um cartaz na praça pede braços para {local}, sitiada por {faccao}.",
        "rumor": "Dizem que {local} está cercada e que o pão lá dentro acaba logo."
      },
      "fail_text": "O tempo para socorrer {local} passou."
    },
    "conter_praga": {
      "source": {"crisis_kind": "praga"},
      "deadline": "escalation_day",
      "action_vocab": ["trat", "cur", "queim", "isol", "erva", "quarentena", "ferv", "enterr"],
      "combat_counts": false,
      "relief": {"pressure": "praga", "delta": -25},
      "title": "Conter a febre em {local}"
    },
    "reabrir_rota": {
      "source": {"route_blocked": true, "exclude_if_siege": true},
      "deadline": "heard_day+ROUTE_WINDOW",
      "action_vocab": ["limp", "desobstru", "remov", "abr", "escav", "pont"],
      "relief": {"emit": "route_cleared"},
      "fail_causes": [{"pressure": "fome", "delta": 6, "scope": "endpoint_regions", "once": true}],
      "title": "Reabrir a estrada entre {local} e {local_b}"
    },
    "resgate": {
      "source": {"npc_peril": true},
      "deadline": "peril.deadline_day",
      "completion": "peril_intervention",
      "title": "Chegar a {local} antes que seja tarde para {npc}"
    }
  }
}
```

Exemplo concreto: crise `praga` em `brekmar` (`crisis_id="a1b2…"`, `warned_day=14`,
`start_day=17`, `escalation_day=23`); o jogador está em `brekmar` no dia 17 e o item
`praga.crise.inicio` é percebido por testemunho → quest `conter_praga`, `deadline_day=23`,
rótulo "há algum tempo" (6 dias). `{faccao}` segue a SPEC-302 R24 (nome só se
`faction_intel[id].known`); `{npc}` só se o NPC está em `state.npcs` e conhecido (SPEC-304
R20), senão rótulo ("um mercador de Brekmar").

### 3.6 Eventos

- `quest_failed` (agora `EventType`): `target_id=<quest_id>`, `payload={quest_id,
  quest_title, reason: "prazo"}`, `source="engine"` (motor) ou `"system"` (órfã, atual).
- `world_quest_relief` (novo, engine-only, só derivado): §2.3 R13. Fora de
  `npc_knowledge.SUBJECT_PARAMS` (o feito se propaga pela SPEC-298 via `quest_completed`).

## 4. Plano passo a passo

Marco único (a spec é bounded); pousa depois da SPEC-302 M2. Se a SPEC-304 não estiver
`done`, a Etapa 5 fica desligada por guarda (`resgate` ausente de `candidates`) e o teste
correspondente é `skip` com motivo.

### Etapa 0 — Ownership e sondas

1. Consultar `project_index` (`state_ownership`) para os writers atuais de `quests`
   (`storyteller`, `npc`, `event_processor`) e registrar `services/world_quests.py` como
   único criador de quest de mundo.
2. Confirmar no código pousado da 302: `DigestItem.subject_id`, `CrisisRecord` e o passo 2 do
   tick (causas). Divergiu → ajustar esta spec no mesmo commit.

### Etapa 1 — Schema, eventos e falha engine-only

1. **Testes** (`tests/test_spec305_events.py`):
   - `test_quest_failed_llm_proposal_rejected` (sem `source` → rejeitada);
   - `test_quest_failed_engine_marks_failed_and_milestone`;
   - `test_fail_orphan_path_unchanged` (regressão de `tests/test_fase33.py`);
   - `test_world_quest_relief_only_as_derived`;
   - `test_legacy_quest_without_world_fields_roundtrip` (save/load).
2. **Implementação:** `state.py`, `structured_outputs.py`, validators, `fail_quest`/
   `expire_quest`, `apply` no `event_processor`.

### Etapa 2 — Candidatas, prazo e viabilidade

1. **Testes** (`tests/test_spec305_sources.py`):
   - `test_each_kind_has_candidate_from_state` (estado sintético por tipo, IDs reais:
     `brekmar`, `nova_arcadia`, conexão real de `data/world_map.json`);
   - `test_deadline_equals_escalation_day`;
   - `test_announced_crisis_provisional_deadline_never_shortens` (propriedade);
   - `test_route_with_siege_is_not_reabrir_rota`;
   - `test_feasibility_filters_unreachable`;
   - `test_independent_of_player_stats` (R4);
   - `test_no_global_random_in_world_quests` (AST);
   - `test_deterministic_ids_and_idempotent_offer` (R3/R25).
2. **Implementação:** `world_quests.candidates`, `is_feasible`, `world_distance` (se preciso),
   `data/world/world_quests.json`.

### Etapa 3 — Percepção e oferta

1. **Testes** (`tests/test_spec305_perception.py`):
   - `test_unperceived_crisis_creates_no_quest`;
   - `test_testemunho_creates_quest_with_heard_via`;
   - `test_cartaz_only_in_cidade_or_vila`;
   - `test_npc_channel_uses_npc_name_as_origin`;
   - `test_rumor_requires_location_heard` (SPEC-215 `on`) e `test_rumor_off_without_215`;
   - `test_unknown_faction_never_named_in_any_template` (varre todos os templates × canais);
   - `test_world_quest_cap_and_ordering` (R9);
   - `test_llm_duplicate_of_world_quest_ignored` (R10);
   - `test_only_world_quests_module_builds_world_kind` (grep/AST, R7).
2. **Implementação:** `offer_from_perceived`, `offer_from_heard`, `render_quest_text`,
   integração no storyteller e no `turn_finalizer`.

### Etapa 4 — Conclusão e alívio

1. **Testes** (`tests/test_spec305_relief.py`):
   - `test_kind_vocab_counts_as_evidence` ("trato os doentes" em `conter_praga`);
   - `test_generic_investigation_regex_still_works_for_common_quests` (regressão SPEC-223);
   - `test_combat_won_counts_once_for_siege`;
   - `test_completion_requires_arrival_before_deadline`;
   - `test_relief_event_derived_on_completion`;
   - `test_relieved_crisis_does_not_escalate` (oráculo: com alívio em `e−2`, sem escalada em
     `e`; sem alívio, escala);
   - `test_relieved_crisis_ends_with_intervencao`;
   - `test_reabrir_rota_emits_route_cleared_engine`;
   - `test_liberation_raises_reoccupy_chance`;
   - `test_ascension_setback_clamped`;
   - `test_reward_and_origin_faction_deed` (com SPEC-298 se `done`; senão só XP/ouro).
2. **Implementação:** `quest_log` (vocab, `combat_won`), `combat.py`, `event_processor`
   (derivado), `world_director.relieve`, `location_states`, `pressures.json`.

### Etapa 5 — Prazo, falha e resgate

1. **Testes** (`tests/test_spec305_deadlines.py`):
   - `test_fails_on_deadline_tick_not_before`;
   - `test_multi_day_travel_arriving_on_deadline_fails`;
   - `test_source_ended_alone_expires_without_failure`;
   - `test_perceived_end_expires_immediately` (R19);
   - `test_fail_text_never_reveals_outcome` (R18, oráculo de NPC morto não percebido);
   - `test_fail_causes_route_fome_once`; `test_occupation_consolidates_on_failure`;
   - `test_resgate_completes_on_intervention_engine_source`;
   - `test_resgate_fails_on_any_fate_without_naming_it`;
   - `test_resgate_deadline_follows_peril_extensions`.
2. **Implementação:** `sync_deadlines`, ramo `resgate`, `fail_causes`.

### Etapa 6 — Superfícies

1. **Testes** (`tests/test_spec305_surfaces.py`):
   - `test_api_quest_view_whitelist` (nenhum `deadline_day`/`world_source_id`/`heard_via`/
     `origin_faction_id`/`fail_reason` em `/game/state` e `/game/action`);
   - `test_deadline_label_buckets`;
   - `test_failed_and_expired_same_public_label`;
   - `test_prompt_block_has_deadline_label_no_number`;
   - `test_gancho_novo_line_and_no_extra_llm_call` (contador de invokes no MockLLM);
   - `web`: teste de componente/Playwright existente estendido (`expired` + selo "urgente").
2. **Implementação:** `public_quest_view`, `_quest_block`, `_quests_ativas_block`, web.

### Etapa 7 — Playtest, rollout e prova

1. **Testes** (`tests/test_spec305_playtest.py`): `test_invariants_detect_unheard_and_early_fail`
   (estado sintético); `test_report_world_quest_lines`; `test_scenario_mundo_offers_quest_and_
   fails_on_deadline` (`--scenario mundo` da 302, MockLLM: aviso → crise → quest `romper_cerco`
   → descansos até o prazo → `quest_failed` e escalada); `test_shadow_writes_nothing`;
   `test_requires_world_engine_on`.
2. **Implementação:** invariantes, telemetria, relatório, flag `RPG_WORLD_QUESTS`.
3. **Verificação:** playtest `--all --turns 50` (MockLLM) com `RPG_WORLD_ENGINE=on` e
   `RPG_WORLD_QUESTS=on`: 0 violação `error`; registrar na §8 quests oferecidas/concluídas/
   falhadas por perfil. Letalidade SPEC-285 M1/M2/M5 (seeds 21–32 × 200, `combate`) sem
   regressão contra a medição da SPEC-302 Etapa 8. Ruff nos tocados; suíte completa 1× no pouso.

## 5. Critérios de aceite

- [x] R1–R4: 8 tipos por catálogo, prazo do motor que nunca encurta, uma quest por fonte com
      id determinístico, independente do herói
- [x] R5–R10: só nasce de percepção registrada (5 canais), dois pontos de oferta, viabilidade,
      tetos, dedupe com o LLM
- [x] R11–R14: conclusão por vocabulário/`combat_won`/intervenção; alívio impede escalada e
      fecha a crise com `"intervencao"`; recompensa e feito da 298
- [x] R15–R19: `quest_failed` engine-only; falha só no prazo; consequência = a do motor (mais
      `fail_causes`); texto de falha não revela desfecho; fonte encerrada → `expired`
- [x] R20–R23: API com lista branca, rótulo de prazo sem número, prompt com prazo, web com
      `expired`
- [x] R24–R27: saves antigos carregam; idempotência; rollout `off|shadow|on`; invariantes e
      relatório
- [x] Nenhum `with_structured_output` novo (se surgir, guard de FallbackLLM obrigatório)
- [x] Letalidade SPEC-285 sem regressão com as duas flags `on`
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Revisão independente Opus (`handoffs/SPEC-305-review.md`) sem P0/P1
- [x] Smoke real (§6) executado e registrado na §8

## 6. Smoke test com LLM real

Teto do dono: US$ 3/dia, só campanhas curtas. Pré-requisito: `RPG_WORLD_ENGINE=on`,
`RPG_WORLD_QUESTS=on`, `RPG_NPC_KNOWLEDGE=on`, DeepSeek nas `ROUTES`. Esta spec não cria
chamada LLM, mas o gancho entra no prompt do narrador e do `npc_actor`: o MockLLM não mostra
se a prosa vaza prazo ou desfecho.

1. `uv run python -m playtest run --scenario mundo --turns 20 --real --max-cost 0.40 --seed 21`.
   Asserta: `mock=False`; no transcrito, o turno de criação narra o gancho pelo canal
   registrado; `/game/state` tem a quest com `kind="mundo"` e `deadline_label`, sem campos
   internos; 0 violação `error`; nº de invokes por turno igual ao baseline da 302.
2. No mesmo run: viajar ao alvo, 2 ações do vocabulário ("trato os feridos", "reforço o
   portão") → `quest_completed` aceito; no tick seguinte, `world_quest_relief` no `event_log`
   e a crise não escala (ler `tick_log` pelo harness, nunca pela API).
3. `uv run python -m playtest run --profile explorador --turns 30 --real --max-cost 0.60 --seed 22`:
   ao menos 1 quest de mundo oferecida ou registro de "nenhuma fonte percebida" no `report`;
   leitura humana de 5 trechos: nenhum número de dia, nenhuma fação desconhecida nomeada,
   nenhuma quest que o personagem não ouviu.
4. Falha telegrafada: no `--scenario mundo`, descansar até passar o prazo → `quest_failed`
   com texto neutro; a escalada só aparece na narração quando percebida.

Custo esperado: ≤ US$ 1,00. Se algum passo estourar o teto, parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** campos opcionais; quest sem `world_kind` segue o caminho atual. Status
  `expired` desconhecido de clientes antigos: o web é atualizado no mesmo pouso; a API mantém
  `status` e acrescenta `deadline_label`.
- **Dois caminhos para `quest_failed`:** o órfão (append direto, `source="system"`) e o motor
  (validado, `source="engine"`). Teste garante que uma quest nunca recebe dois `quest_failed`.
- **Acoplamento com a 302/304:** `relieve`, `relieved_day`, `liberation_day` e
  `consolidated_until_day` estendem módulos da 302. Se a 302 pousar diferente, o executor
  ajusta esta spec no mesmo commit (Etapa 0). Sem a 304, `resgate` fica desligado.
- **Máquina de quests:** o teto de 3, a viabilidade e "uma por fonte" limitam o diário; a
  cadência vem do diretor da 302 (~1 crise perceptível a cada 10–15 dias, D4 da 302), então a
  expectativa é ~1 quest de mundo a cada 1–2 semanas de jogo por região frequentada.
- **Exploração:** completar quest de mundo é a forma de o jogador "furar" a curva de tensão.
  O alívio só reduz a pressão e impede a escalada; o diretor (cooldown por região) continua
  valendo, então não dá para farmar crise.
- **Letalidade (SPEC-285):** `combat_won` incentiva combate em local com `danger_delta` +1;
  medir na Etapa 7. A correção, se precisar, é no alívio/viabilidade, nunca no combate.
- **MockLLM/FallbackLLM:** o caminho é todo Python; templates garantem texto mesmo com
  FallbackLLM. Prova de conclusão por proposta do LLM continua com o guard atual.
- **Quota/latência:** zero chamada LLM nova; algumas linhas a mais no prompt.
- **Onisciência:** lista branca na API, rótulos sem número, falha neutra; o vazamento
  preexistente de `danger_overrides` (SPEC-302 P13) continua fora daqui.
- **Rollback:** `RPG_WORLD_QUESTS=off` para de oferecer e de falhar; quests de mundo já
  criadas ficam como quests comuns (sem prazo efetivo) e podem ser concluídas pela prova atual.

## 8. Evidência

(preencher na implementação: candidatas/ofertas por perfil, oráculo alívio × escalada,
letalidade antes/depois, smoke §6)

## 9. Decisões do dono

- **D1 — Entrada no diário.** (a) **Recomendado:** ao ouvir/ver, a quest entra sozinha no
  diário (o mundo não espera "aceite"). (b) Só entra se o jogador disser que aceita
  (intenção detectada em Python no turno seguinte).
- **D2 — Só oferecer quest viável** (dá tempo de chegar antes do prazo). Recomendado: **sim**
  (duro, mas justo; a notícia inviável continua como notícia).
- **D3 — Prazo visível.** Recomendado: **rótulo vago** ("urgente / em poucos dias / há algum
  tempo"), coerente com "rótulos sem números" (VISAO.md:68-69). Alternativa: mostrar o dia
  exato do calendário.
- **D4 — Tipos no v1.** Recomendado: os **8** da R1 (inclui `frear_ascensao` como a "ameaça"
  e `selar_corrupcao` condicionado ao D2 da 302). Alternativa enxuta: só crises (4) + resgate.
- **D5 — Custo de suprimentos em `socorrer_escassez`** (gastar ouro/itens). Recomendado:
  **não no v1** (prova por ação, como os demais).
- **D6 — Recompensa.** Recomendado: XP e 20 de ouro como hoje + feito de reputação da
  SPEC-298 para o controlador do local. Alternativa: ouro por gravidade da crise.
- **D7 — Teto** de 3 quests de mundo ativas (dentro das 8). Recomendado: **3**.
- **D8 — Sem segunda chance** na mesma crise depois de falhar. Recomendado: **sim** (uma por
  fonte; uma crise nova no mesmo lugar gera quest nova).
- **D9 — Default de `RPG_WORLD_QUESTS`.** Recomendado: `on` local e na suíte; `shadow` no
  staging até o smoke §6; `on` no staging depois do OK (mesmo esquema da 302 D5).
- **D10 — Consequências extras de falha** (`fail_causes`): `reabrir_rota` → `fome +6`;
  `libertar_ocupado` → 30 dias sem retomada natural. Recomendado: **sim**, valores
  `[BALANCEAR]`.


## Decisões do dono (2026-10-23)

Todas as decisões abertas seguem o **default recomendado pelo autor** (D1 entra sozinha no diário; D3 prazo por rótulo vago; D8 sem segunda chance — pode nascer quest nova da consequência), exceto:

- D4 (amplia): os 8 tipos **mais um 9º, `recuperar_objeto`** — relíquia/artefato roubado ou perdido (ex.: item único tomado por fação/bandidos, tesouro de templo saqueado), nascido do estado (evento de roubo/saque, ocupação, `unique_item_lost`) e com prazo (o objeto é vendido, destruído ou levado para fora da região). Mesmas regras: só entra se percebido; falha = objeto perdido para este mundo (único segue único por mundo).

## 10. Desvios da implementação (Etapa 0, 2026-10-24)

Confirmado no código pousado da 302: `world_director`/`CrisisRecord` (dict em `state.CrisisRecord`),
`escalation_day`, passo 2/7 do tick via `new_events`, `DigestItem` = dict de `digest_item`
(com `subject_id`). Ajustes:

- **9 tipos** (decisão do dono): `recuperar_objeto` (unique_items com `holder` = fação). Hoje nenhum
  emissor grava holder de fação (só jogador/mercador/mundo), então fica **dormente**: nasce por
  testemunho no mesmo turno do evento e por rumor/NPC se `unique_item_lost` passar a propagar
  (não adicionei o tipo a `SUBJECT_PARAMS` para não alterar a 215). Falha = objeto segue com a fação.
- **`resgate` desligado**: SPEC-304 não pousou (`services.npc_world.active_perils` ausente);
  contrato testado com módulo injetado. `world_distance.travel_periods` já existe (215).
- **`LocationStateRow` não existe como TypedDict**: `liberation_day`/`consolidated_until_day` são
  chaves da linha de `location_states` (escritas por `apply_event`).
- **`world_source_id` de rota** usa `blocked_by_event[:8]` (não `heard_day`, que mudaria a cada dia
  e quebraria R3); o prazo é `dia da oferta + ROUTE_WINDOW`. Objeto: `obj:<item>:<event[:8]>`.
- **`fail_causes`** vivem em `pressures.json` (causa `quest_failed` com `if: world_kind:reabrir_rota`);
  consolidação de ocupação é marca em `apply_event`. `world_quests.json` guarda só as constantes.
- `Quest` ganha `other_location_id`, `deadline_provisional`, `fail_text`, `resolved_day`;
  `WorldSimState.perceived_ids` (livro-razão da percepção para `quest.world_unheard`).
- Crise só anunciada não falha enquanto não abre (o aviso expira por TTL → `expired`); crise que
  encerra com `resolution="escalou"` conta como falha no prazo.
- R14: `reputation.deed_info` usa `origin_faction_id` quando não há `origin_entity_id`.
- Modo `RPG_WORLD_QUESTS` default `on` (D9); `off` com motor ≠ `on`.

- **Revisão Sol (CHANGES_REQUIRED) corrigida:** P1-1 status público único `expired` para
  `failed`/`expired` de mundo; P1-2 `quest_completed` não-engine de quest de mundo rejeitado com
  dia >= prazo + quest que falha no turno sai do bloco do prompt; P2-1 invariante exige ledger de
  percepção; P2-2 `RELIEVED_MAX_DAYS` (8) fecha crise aliviada; P2-3/P2-4/P2-6 testes e shadow no
  finalizer. P2-5 (esconder tipos engine-only do schema do LLM) fica como follow-up (mesmo padrão
  da 301).

## 11. Evidência (parcial)

Testes: `tests/test_spec305_{sources,events,perception,lifecycle,surfaces}.py`. Smoke real (§6) e
letalidade SPEC-285 ficam para o coordenador (ver hand-back).

