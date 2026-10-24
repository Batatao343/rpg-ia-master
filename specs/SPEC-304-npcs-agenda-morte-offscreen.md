# SPEC-304 — NPCs off-screen: agenda, viagem, troca de lado e morte telegrafada

> **Status:** `in-progress` (aprovada pelo dono 2026-10-23; etapas 0–8 implementadas em 2026-10-24, falta revisão independente Opus + smoke real §6 — sem chave neste ambiente)
> **Criada:** 2026-10-23 · **Atualizada:** 2026-10-24
> **Origem:** `docs/mundo-vivo/VISAO.md` (decisão 3 "move NPCs (agenda, viagem, troca de lado, morte off-screen)", decisão 5 "duro, mas telegrafado", § C "NPCs simulados off-screen" e "Morte off-screen", Regra de ouro); SPEC-302 §9 (filha 302-C).
> **Depende de:** SPEC-302 (`approved`; precisa estar `done` no marco M2: `advance_days`, hook `post`, `day_rng`, `request_crisis_slot`, `location_effects`, `world_perception`, `world.news`), SPEC-300 (`approved`; interface §3.8 `companions_exposed`/`telegraph_companion_danger`/`apply_companion_fate`), SPEC-298 (`approved`; `npc_tier`, `apply_npc_delta`), SPEC-215 (`done`; propagação), SPEC-230 (`done`; `npc_alive`/`apply_npc_death`).
> **Desbloqueia:** SPEC-305 (resgate com prazo a partir de `NpcPeril.deadline_day`); pilar B (prisioneiro capturado; desafeto da SPEC-300 D3 que "entrega" o jogador).
> **EXECUTOR_MODEL:** `Opus` (Sol: estado novo com writer único, cross-domain NPC/party/eventos/percepção) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo writer persistente, novos tipos de GameEvent, morte de companheiro, filtro de onisciência na API)
> **EVAL_AUTHORING_REQUIRED:** `false` (calibração por simulador determinístico em `docs/spec304/`)

---

## 1. Contexto & Objetivo

Hoje um NPC só existe enquanto o jogador olha para ele. Ele fica preso ao
`home_location_id` (`services/npc_layers.py:72`, `:159-184`). A única forma de
"se mover" é o narrador reintroduzi-lo em outro local, o que **relocaliza** o
NPC sem nenhuma regra (`agents/storyteller.py:433-442`). Ninguém viaja, muda de
lado ou morre fora da cena. A morte só nasce de combate com prova
(`services/world_validators.py:213`, `:322-337`) ou de cascata de regra
(`services/rule_engine.py`). O companheiro deixado "esperando" fica congelado
para sempre (`party.py:392-400`).

Esta spec liga a **sociedade** ao motor de mundo da SPEC-302. Um módulo
determinístico, seeded por `(game_id, dia)`, roda no hook `post` do tick diário
e simula um **elenco de até 60 NPCs**: a party, os conhecidos pelo jogador, os
21 líderes de fação (`data/graph/edges.json`, arestas `leads`) e NPCs-chave
curados. Cada dia ele resolve: (1) **agenda e viagem** (onde o NPC está);
(2) **troca de lado** por causas do mundo; (3) **perigo e destino** de quem está
num lugar perigoso. A morte de **qualquer um**, inclusive de companheiro
afastado, é sempre **telegrafada**: abre um `NpcPeril` com aviso (rumor ou pedido
de ajuda), espera pelo menos `TELEGRAPH_MIN_DAYS` e dá ao jogador a chance de
intervir. Só então o motor sorteia o destino.

O jogador só fica sabendo do que viu ou ouviu. Por isso a spec separa a
**verdade** (o estado do NPC, usado para regras e cena) da **crença do jogador**
(o que a API, o dossiê, a crônica e o narrador mostram). Hoje esse vazamento já
existiria: a API mostra `status: "morto"` direto da verdade
(`services/npc_layers.py:262`, `services/dossiers.py:160`); a crônica grava todo
`npc_killed` aplicado (`services/chronicle.py:26-43`,
`services/event_processor.py:425`); e o contexto do narrador renderiza os últimos
100 eventos sem filtro (`services/context_builder.py:268-274`). A LLM não decide
nada aqui. Ela só narra os itens que a SPEC-302 já filtrou, na mesma chamada
diária (≤ 1 por ação que vira o dia).

Princípios: mecânica em Python e determinística; o motor aplica e a LLM narra;
"o mundo não escala com o herói"; não-onisciência; migração suave; sem regressão
nas metas da SPEC-285.

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | NPC não tem posição além do `home_location_id`; contexto e cena só filtram por ele | `services/npc_layers.py:72`, `:130-156`, `:159-184` |
| P2 | O narrador relocaliza qualquer NPC conhecido para o local atual, sem regra (inclusive quem "deveria" estar longe) | `agents/storyteller.py:426-443`, `:450-460` |
| P3 | NPC de grafo morto fora de `state.npcs` pode ser reintroduzido vivo: `is_in_scene`/`npc_alive` sem projection não veem `alive=False` | `services/npc_layers.py:87-99`, `:121-127`; `agents/storyteller.py:444-480` |
| P4 | Morte só por combate com prova ou por cascata; não existe morte off-screen | `services/world_validators.py:213`, `:322-346`; `agents/combat.py:109-124` |
| P5 | `npc_killed` exige entidade do grafo; NPC gerado (só em `state.npcs`) não tem evento de morte possível | `services/world_validators.py:30-38`; `agents/combat.py:97-106` |
| P6 | Companheiro em espera congela; `waiting_at` guarda o **nome de exibição**, não o id | `party.py:392-400`; `agents/npc.py:595`, `:647` |
| P7 | Vazamento de verdade na API: `status` "morto" sai direto do estado | `services/npc_layers.py:262`; `services/dossiers.py:160`, `:37` |
| P8 | Crônica grava milestone de todo `npc_killed` aplicado (o jogador "leria" a morte que não viu) | `services/chronicle.py:26-43`; `services/event_processor.py:425`, `:436`, `:450` |
| P9 | O contexto do narrador renderiza os 100 últimos eventos sem filtro de conhecimento (só o NPC actor tem filtro) | `services/context_builder.py:258-274`, `:599`, `:615` |
| P10 | `_event_origin` cai no local **atual** quando o evento não traz local válido: evento off-screen sem `payload.location_id` "aconteceria" ao lado do jogador | `services/npc_knowledge.py:276-283` |
| P11 | Morte de líder com `power_vacuum_trigger` dispara cascata de controle de local; sem gate, uma morte off-screen viraria crise fora do orçamento da SPEC-302 | `data/graph/world_rules.json:2-27`; `services/rule_engine.py:186-204` |
| P12 | Filiação de NPC quase não está no grafo (1 aresta `member_of`); vive em `components.faction`/`npcs[*].faction`, sem writer de troca de lado | `data/graph/edges.json` (1× `member_of`); `data/graph/entities.json:7545-7549` (Brunna) |
| P13 | Notícias entregues pela SPEC-215 caem em `_residents` pelo `home_location_id`: um NPC viajando "ouve" em casa | `services/npc_knowledge.py:181-212` |

## 2. Requisitos

### 2.1 Elenco simulado

- **R1 — Elenco determinístico com teto.** `npc_world.roster(state)` devolve até
  `ROSTER_CAP = 60` ids, nesta prioridade:
  1. membros da party (ativos e em espera);
  2. NPCs de `state.npcs` com `known_by_player` e `npc_tier ∈ {amistoso, leal}`
     (SPEC-298);
  3. os 21 líderes (`leads` em `data/graph/edges.json`);
  4. os demais conhecidos, por `last_seen_turn` desc;
  5. a lista curada `key_npcs` de `data/world/npc_world.json` (proposta: os 36
     `npc_mv_*`).
  Desempate por id. NPC morto não entra. O elenco é recalculado só quando o
  conjunto de entrada muda (NPC conhecido novo, morte, entrada/saída da party).
  Quem sai do elenco **congela** (posição e estado mantidos, sem simulação).
  Teste: mesmo estado → mesma lista; nunca > 60.
- **R2 — Fora do elenco, nada muda.** Nenhuma função desta spec escreve em NPC
  fora do elenco. O jogador e a ficha dele não entram em nenhum cálculo (R5 da
  SPEC-302). A posição do jogador só conta para **intervenção** (R16) e
  **percepção** (R20–R23).

### 2.2 Agenda e viagem

- **R3 — Arquétipos de agenda (dados).** `data/world/npc_agendas.json` define
  arquétipos fechados: `sedentario`, `mercador_itinerante`, `patrulheiro`,
  `peregrino`, `mensageiro`, `lider_residente`, `lider_em_campanha`. Cada um tem
  `p_leave` (chance diária de sair de casa), `stay_days` [min, max], `route`
  (`home_region` | `adjacent_regions` | `faction_locations` | `list`) e
  `avoid_states` (estados de local da SPEC-302 que ele evita).
- **R4 — Atribuição de arquétipo.** NPC de grafo: pelo mapa curado
  `agenda_by_npc` (ids reais). NPC gerado: por tabela fechada de radicais do
  `role` (`mercador|caravan` → `mercador_itinerante`; `guarda|soldad|patrulh` →
  `patrulheiro`; `peregrin|sacerdot` → `peregrino`; `mensageir|correio` →
  `mensageiro`). Sem casamento, fica `sedentario`. Companheiro em espera fica
  `sedentario` no `waiting_at`. Companheiro ativo não é simulado: ele está com o
  jogador.
- **R5 — Passo diário de posição.** Para cada NPC do elenco, na ordem do id:
  - em casa: com `rng < p_leave` escolhe um destino da `route` que não esteja
    bloqueado (`blocked_routes` da projection) nem em `avoid_states`. Parte e
    chega em `day + ceil(travel_periods / PERIODS_PER_DAY)`
    (`services/world_distance.travel_periods`);
  - em viagem: chega no `arrive_day`. Antes disso não está em local nenhum;
  - fora de casa: volta quando passa `stay_days`.
  Tudo grava em `npc_sim.npcs[id].pos` (§3.3). Nada vira `GameEvent`. Movimento
  diário não entra no `event_log`.
- **R6 — Fuga de crise (o mundo empurra).** NPC cuja casa entra em `cerco`,
  `praga`, `ocupado`, `ruina` ou `corrompido` (`location_state` da SPEC-302)
  vira refugiado com chance seeded `p_flee` por dia: vai para o local mais
  próximo de outra região sem estado de crise. Volta quando a casa fica sem
  estado de crise por `RETURN_AFTER_CALM_DAYS` (5). Líder `lider_residente` não
  foge (é alvo de perigo, R12).
- **R7 — Posição é a verdade para a cena.** Com `RPG_NPC_WORLD=on`,
  `npc_layers.npcs_in_scene`, `npc_layers.npcs_for_context` e
  `npc_knowledge._residents` passam a usar `npc_world.location_of(state, key)`
  (posição simulada se o NPC está no elenco; senão `home_location_id`) em vez de
  `home_location_id` (corrige P1 e P13). `home_location_id` continua sendo a
  casa.
- **R8 — O narrador não teleporta.** Em `agents/storyteller._with_new_npc`, com
  o modo `on`, um NPC conhecido cuja `location_of` ≠ local atual (ou que está em
  viagem, ou morto, ou `capturado`) **não** é relocalizado nem posto `in_scene`.
  A cena segue sem ele e o motor registra `npc.reintroduction_blocked`. Exceção:
  membro ativo da party. NPC de grafo morto na projection nunca é criado vivo
  (corrige P3; o teste cobre NPC fora de `state.npcs`).
- **R9 — Ausência é perceptível.** Quando o jogador chega ao `home_location_id`
  de um NPC **conhecido** que está fora, o digest do dia ganha um item
  `npc_ausente` (testemunho local): "Dizem que {npc} partiu para {destino}." O
  destino só aparece se o NPC o "contou" a alguém do local: o arquétipo não é
  `mensageiro` e o destino é público. Senão, "ninguém sabe para onde".

### 2.3 Troca de lado

- **R10 — Filiação dinâmica por evento.** `npc_defected` (novo, engine-only):
  `target_id=<npc>`, `payload={from_faction_id, to_faction_id, location_id,
  cause}`. `apply_event` grava `projection.npc_affiliations[npc] =
  to_faction_id`. A leitura única fica em `npc_world.npc_faction(state, npc)`:
  override da projection → `npcs[*].faction` → `components.faction` →
  `member_of`/`leads` (corrige P12).
- **R11 — Causas (tabela de dados), nunca texto.** Candidatos a desertar por dia,
  com probabilidade seeded da tabela `defection_causes`:
  - o local da casa mudou de controlador para a fação G
    (`location_control_changed` desde o último tick) → membros da fação anterior
    ali podem passar a G;
  - a fação do NPC está `defeated`/`completed` com ascensão rival → passa à rival;
  - a relação entre a fação do NPC e G está em `guerra` (SPEC-302 R21) e o NPC
    está numa região controlada por G (pressão de sobrevivência);
  - os traços de `hidden_traits` + `revealed_traits` multiplicam a chance
    (`lingua_dupla`, `desertor_envergonhado`, `guarda_subornavel`: ×2; os
    `BETRAYAL_BLOCKERS` da SPEC-300: ×0).
  **Líderes nunca desertam.** Companheiro na party nunca deserta (a saída dele é
  da SPEC-300). Teto: `MAX_DEFECTIONS_PER_DAY = 1` no mundo.

### 2.4 Perigo e destino (morte off-screen telegrafada)

- **R12 — Exposição.** Um NPC do elenco está **exposto** no dia `d` se a posição
  dele é um local com:
  - `_effective_danger(world, loc)` + `danger_delta` da SPEC-302 ≥
    `PERIL_MIN_DANGER` (3); ou
  - estado de local de crise (`cerco`, `praga`, `ocupado`, `ruina`,
    `corrompido`); ou
  - é viajante numa conexão em que uma das pontas tem perigo ≥ 4.
  O companheiro em espera usa `companion_soul.companions_exposed(state)`
  (SPEC-300 §3.8) com `waiting_at` resolvido para `location_id` (P6) por
  `npc_world.resolve_location_ref`. NPC no local atual do jogador **nunca** está
  exposto off-screen (lá ele está "em cena").
- **R13 — Abertura de perigo (hazard seeded).** Para cada exposto sem perigo
  aberto: `p = BASE_HAZARD[danger] × CRISIS_MULT[estado] × ROLE_MULT[arquétipo]`
  (tabela em `data/world/npc_world.json`; `[BALANCEAR]`). Com `rng < p`, abre um
  `NpcPeril` com `kind` ∈ `{emboscada, cerco, praga, abismo, cativeiro}`,
  derivado do motivo da exposição. Tetos:
  - perigos ativos no mundo ≤ `MAX_ACTIVE_PERILS` (3);
  - ≤ 1 por NPC ao mesmo tempo;
  - cooldown por NPC de `PERIL_COOLDOWN_DAYS` (15) depois de resolvido.
- **R14 — Perigos maiores passam pelo diretor.** Um perigo é **maior** se o alvo
  é líder, membro da party ou NPC querido (`npc_tier ∈ {amistoso, leal}`). Perigo
  maior só abre se `world_director.request_crisis_slot(sim, d, region_id,
  "npc_perigo")` conceder vaga. O orçamento global da SPEC-302 R15 vale de
  verdade, e o tipo `npc_perigo` entra em `CrisisKind` sem estado de local.
  Perigo menor tem só os tetos da R13 (decisão D2). Além disso, só **1 morte de
  líder** a cada `LEADER_DEATH_GAP_DAYS` (**60**, calibrado em N3; a spec previa 30) no mundo.
  **Implementação:** `request_crisis_slot` exige uma crise ANUNCIADA há ≥ `MIN_WARNING_DAYS`
  (SPEC-302 R15). Então o perigo maior **anuncia** a vaga (`wd.announce`, que já respeita
  `MAX_ACTIVE_CRISES`, calma inicial e cooldown) no dia do telegrama e **abre** a vaga com
  `request_crisis_slot` a partir de `earliest_day`; o ciclo do registro é do `npc_world`
  (`world_director` ignora o tipo no vencimento de avisos e no cooldown/recuperação). Sem vaga
  no prazo, o prazo estende até `MAX_EXTENSION_DAYS` (como na R17) e depois o destino exclui
  `morto`.
- **R15 — Telegrama sempre.** Abrir um perigo emite **no mesmo dia**
  `npc_peril_warning` (engine-only): `target_id=<npc>`, `payload={peril_id, kind,
  location_id, region_id, opened_day, earliest_day, deadline_day, channel}`, com
  `location_id` sempre preenchido (corrige P10). Prazos:
  - `earliest_day = opened_day + TELEGRAPH_MIN_DAYS` (2; ≥ o mínimo de 1 da
    SPEC-300 R26);
  - `deadline_day = earliest_day + rng(PERIL_WINDOW)` ([1, 3]).
  `channel` é:
  - `rumor` (perigo menor): propaga pela SPEC-215 com `SUBJECT_PARAMS`
    (0,9; 20; 2);
  - `pedido_de_ajuda` (perigo maior): a R21(d) entrega um mensageiro ao jogador
    em `opened_day + ceil(travel_periods(peril_loc, player_loc) /
    PERIODS_PER_DAY)`, limitado ao `deadline_day − 1`.
  Para companheiro, chama também `telegraph_companion_danger(state, cid,
  channel, d)` (SPEC-300). Invariante: `npc.fate_without_warning` = `error`.
- **R16 — Chance de intervir.** O perigo vira `resolution="intervencao"` (o NPC
  vive) se, entre `opened_day` e `deadline_day`, acontece qualquer um destes:
  - o jogador chega ao `location_id` do perigo (para viagem de vários dias, o
    destino conta, como na SPEC-302 R23);
  - para companheiro: `set_following` depois do telegrama, ou a recusa
    `FateNotTelegraphed` da SPEC-300.
  Na intervenção por chegada, o digest ganha `npc_resgate` e o narrador recebe a
  cena: o NPC está ali, ferido ou acuado, e a mecânica já decidiu que ele
  sobrevive. Efeito social pela SPEC-298: `apply_npc_delta(+1, source="engine",
  reason="resgate")`. Combate na chegada fica fora de escopo.
- **R17 — Perigo maior exige telegrama percebido.** Perigo maior só pode
  terminar em `morto` se o telegrama foi **percebido** pelo jogador (R20–R23) pelo
  menos 1 dia de jogo antes do `deadline_day` (o mínimo da SPEC-300 R26). Se
  não foi:
  - o `deadline_day` estende até `MAX_EXTENSION_DAYS` (3);
  - se ainda assim não foi percebido, o destino sorteado exclui `morto`
    (decisão D3).
  Perigo menor pode matar com telegrama emitido e não percebido: o mundo é duro.
- **R18 — Destino determinístico.** No `deadline_day`, sem intervenção, sorteia
  um destino seeded em `{morto, ferido, capturado, escapou}` com pesos por `kind`
  e `danger` (`fate_weights` em `npc_world.json`). Aplicação:
  - **NPC de grafo, `morto`**: `npc_killed` (`actor_id="world"`,
    `source="engine"`, `payload={offscreen: true, peril_id, location_id,
    cause}`). O caminho é o canônico: `apply_npc_death`
    (`services/event_processor.py:487-497`), `fail_orphan_quests` (`:443-450`),
    cascata de `world_rules` (líder) e propagação SPEC-215 (`npc_killed` já está
    em `SUBJECT_PARAMS`, `services/npc_knowledge.py:49`);
  - **NPC gerado (fora do grafo)**: `npc_offscreen_fate` (novo, engine-only,
    `target_id=<id runtime>`). Com `morto`, entra em `killed_targets` do
    `process_pending_events` (mesmo `apply_npc_death`; não há quest órfã, porque
    `origin_entity_id` só aceita ids do grafo, `services/quest_log.py:55-59`,
    `:79-80`);
  - **companheiro**: chama `apply_companion_fate(state, cid, fate, d)` da
    SPEC-300 (a alma registra `departed="dead"` e a missão pessoal falha). Se o
    `origin_npc` é do grafo, emite também o `npc_killed` do primeiro item.
    `apply_npc_death` é idempotente (teste);
  - **`ferido`**: `npcs[*].status="ferido"` até `d + WOUND_DAYS` (5);
  - **`capturado`**: `status="capturado"`, com `captor_faction_id` e
    `held_at_location_id` (contrato para a SPEC-305 e o pilar B);
  - **`escapou`**: vira refugiado (R6).
  `ferido`, `capturado` e `escapou` emitem `npc_offscreen_fate` para todo NPC.
  Nenhum destino lê o jogador. Ninguém morre enquanto o jogador está no local
  (invariante `npc.fate_while_player_present` = `error`).
- **R19 — Ator nunca é o jogador.** Os eventos desta spec usam `actor_id ∈
  {"world", <fação captora>}`. Assim a SPEC-298 R13 (feito do jogador por
  `npc_killed` com `actor_id="player"`) e a SPEC-300 (`matou_nomeado`/
  `matou_inocente`) **não** contam mortes off-screen. Os testes cobrem os dois
  casos.

### 2.5 Percepção, crença do jogador e não-onisciência

- **R20 — Itens de digest novos.** `npc_perigo`, `npc_destino`, `npc_ausente`,
  `npc_resgate` e `npc_lado` são `DigestItem`s da SPEC-302 (R22) com
  `subject_id` = `event_id`. Templates pt-BR em `data/world/npc_templates.json`,
  sem números. Usam o nome do NPC só se ele está em `state.npcs` e conhecido
  (SPEC-302 R24); senão, um rótulo ("um mercador de Brekmar", "o líder dos
  {rótulo percebido da fação}").
- **R21 — Canais.** Um item é percebido pelos canais (a), (b) e (c) da SPEC-302
  R23, mais um canal novo:
  - **(d) mensageiro dirigido**: o item `npc_perigo` com `channel =
    "pedido_de_ajuda"` chega ao jogador onde ele estiver, no dia de entrega da
    R15. É testemunho: alguém veio contar. Esta spec estende
    `world_perception.perceivable` com o canal (d).
- **R22 — Crença do jogador (`npc_beliefs`).** Nova chave `GameState.npc_beliefs:
  dict[npc_key, NpcBelief]`. O único writer é
  `npc_world.record_beliefs(state, perceived_items)`. Ela é atualizada por:
  - item percebido (R21);
  - encontro em pessoa: o NPC `in_scene`, ou a chegada ao local de morte com
    testemunho dos locais.
  A crença guarda `{status_known, location_known, faction_known, as_of_day,
  channel, source_event_id}`.
- **R23 — Superfícies leem a crença, não a verdade.** Com o modo `on`:
  - `visible_npc_view` (`services/npc_layers.py:262`) e o dossiê
    (`services/dossiers.py:160`) mostram `status` = `npc_beliefs.status_known`
    (vazio = o último status que o jogador viu);
  - `location` mostra `location_known`;
  - os `encounters` do dossiê (`_events_about`) e o contexto do narrador
    (`services/context_builder.py:268-274`) pulam eventos com `payload.offscreen
    = true` (e todo `npc_peril_warning`/`npc_offscreen_fate`/`npc_defected`)
    cujo `event_id` não é `source_event_id` de alguma crença;
  - o milestone de crônica de `npc_killed` off-screen **não** é gravado na
    aplicação (`services/event_processor.py:425`). Ele é gravado quando a morte
    é percebida, pelo evento `npc_fate_learned` (novo, engine-only, sem efeito
    na projection, fora de `SUBJECT_PARAMS`), com o template "Chegou a notícia:
    {target} morreu em {local}." (corrige P7–P9).
  Teste-oráculo: com um NPC morto off-screen e não percebido, nenhum payload de
  `/game/state`, `/dossiers` ou da resposta de turno, e nenhum prompt do
  narrador, contém "morto"/"morreu" para ele, nem o local da morte.
- **R24 — Narração sem chamada nova.** Os itens entram no `narrate_day` da
  SPEC-302 R26 (≤ 1 chamada por ação que vira o dia). Esta spec não cria
  `get_llm`/`invoke` nem structured output novo (teste conta invokes com e sem
  NPCs simulados). A checagem de nomes da R26 da SPEC-302 passa a aceitar os
  nomes de NPC dos itens percebidos e rejeitar os demais.

### 2.6 Eventos, persistência, rollout e prova

- **R25 — Tipos de evento engine-only.** `EventType` ganha `npc_peril_warning`,
  `npc_offscreen_fate`, `npc_defected` e `npc_fate_learned`. Todos exigem
  `source="engine"`, com a mesma barreira de `unique_item_*`
  (`services/world_validators.py:508-512`). Os validadores:
  - `npc_offscreen_fate`/`npc_fate_learned` aceitam alvo em `state.npcs` ou no
    grafo;
  - `npc_defected` exige as duas fações em `data/factions.json` e um alvo que não
    é líder;
  - `npc_killed` off-screen passa pelo `_v_npc_killed` atual e pula a prova
    (`is_engine_proposal`, `:543`).
  Teste por propriedade: 120 dias × 10 seeds, todo evento emitido passa
  `validate_proposal`.
- **R26 — Writer único e estado.** `services/npc_world.py` é o **owner** de
  `npc_sim` e `npc_beliefs`. Ele roda como hook `post` registrado em
  `world_engine.register_day_hook("npc_world", ..., stage="post", order=10)`.
  Escreve `npcs`/`party` **só** por eventos (`process_pending_events`) ou pela
  interface da SPEC-300, nunca direto. Exceção: `status` `ferido`/`capturado` e
  as chaves `captor_faction_id`/`held_at_location_id`, que `apply_event`
  aplica a partir do `npc_offscreen_fate`. Antes de implementar, confirmar os
  owners em `project_index/state_ownership` e registrar o novo owner no PR.
- **R27 — Idempotência e determinismo.** Toda aleatoriedade vem de
  `world_engine.day_rng(game_id, day, f"npc:{id}:{purpose}")`. `peril_id =
  sha256(game_id|npc|opened_day)[:16]`. Replay do mesmo dia não reabre nem
  reaplica nada (via `last_ticked_day` da SPEC-302). Nenhum `random` global nos
  módulos novos (teste AST).
- **R28 — Saves antigos.** `npc_sim`/`npc_beliefs` ausentes → `{}`, a
  inicialização acontece no primeiro tick ligado (todo NPC "em casa", sem
  perigos, sem simulação retroativa). Crenças nascem do estado visível atual (o
  NPC já morto continua `morto`). Sem bump de `SCHEMA_VERSION`
  (`persistence.py:85`); default em `_raw_to_state` (`persistence.py:972`); as
  chaves entram no `TypedDict` do `GameState`. Round-trip save/load preserva
  tudo.
- **R29 — Rollout `RPG_NPC_WORLD=off|shadow|on`.**
  - `off`: no-op byte a byte (testes atuais verdes).
  - `shadow`: simula e grava em `npc_sim_shadow`, sem eventos, sem crença, sem
    efeito em cena/API; loga `npc_world.tick`.
  - `on`: tudo.
  Exige `RPG_WORLD_ENGINE=on`; com o motor `off`/`shadow`, a spec fica `off`
  efetivo. Default: D5. **Implementação:** o default do CÓDIGO é `off` (`npc_world.DEFAULT_MODE`):
  ligar `on` por padrão muda o comportamento de toda a suíte e a suíte completa é do `/spec-land`;
  o coordenador vira o default para `on` (uma linha) depois de rodá-la. Nos testes e no playtest o
  modo vem de `RPG_NPC_WORLD`.
- **R30 — Telemetria e invariantes.**
  - Log `npc_world.tick` `{day, roster, moved, travelling, perils_open,
    perils_resolved{fate→n}, defections, mode}`.
  - Invariantes novos em `playtest/invariants.py`, todos `error`:
    `npc.roster_cap_exceeded`, `npc.fate_without_warning`,
    `npc.major_death_unperceived`, `npc.fate_while_player_present`,
    `npc.dead_in_scene`, `npc.leader_defected`, `npc.belief_leak` (payload da
    API com status/local que não vem da crença).
  - O `report` ganha, na seção "Mundo", "NPCs": perigos abertos/percebidos/
    resolvidos por destino, intervenções e mortes por categoria.
- **R31 — Calibração (simulador offline).** `docs/spec304/npc_world_sim.py` (sem
  LLM), 120 dias × 20 seeds, elenco sintético de 60 NPCs, das quais 3
  companheiros deixados num local de perigo 3 por 10 dias, no mundo da SPEC-302:
  - **N1** — perigos: mediana ≥ 1 perigo percebível a cada 20 dias na região
    frequentada;
  - **N2** — mortes de NPCs do elenco ≤ 1 a cada 15 dias (mediana) e ≥ 1 em 120
    dias (o mundo é duro);
  - **N3** — líderes: ≤ 2 mortes em 120 dias; nunca 2 dentro de 30 dias;
  - **N4** — companheiro deixado em perigo 3 por 10 dias: P(perigo) ∈
    [0,25; 0,60]; P(morte | perigo maior sem intervenção e com telegrama
    percebido) ∈ [0,30; 0,50];
  - **N5** — 0 mortes em local com perigo ≤ 2 sem estado de crise;
  - **N6** — 100 % das mortes com telegrama ≥ `TELEGRAPH_MIN_DAYS`; 100 % das
    mortes de perigo maior com telegrama percebido;
  - **N7** — o orçamento C3 da SPEC-302 continua valendo com `npc_perigo` usando
    as vagas.
  As constantes `[BALANCEAR]` são ajustadas até fechar N1–N7. Tabela em
  `docs/spec304/README.md`.
- **R32 — Sem regressão.** `--all --turns 50` (14 perfis, MockLLM) com
  `RPG_WORLD_ENGINE=on` e `RPG_NPC_WORLD=on`: zero erro e zero violação `error`.
  M1/M2/M5 da SPEC-285 inalteradas: esta spec não toca combate, e o perfil
  `combate`, seeds 21–32 × 200, prova isso.

### Fora de escopo

- Combate ou cena dedicada na intervenção: aqui ela só garante a sobrevivência.
  O resgate como quest com prazo fica na SPEC-305, que lê `NpcPeril`.
- Fluxo de prisioneiro capturado (resgate, troca, interrogatório): pilar B. Aqui
  só ficam `status="capturado"` + `captor_faction_id`/`held_at_location_id`.
- O desafeto da SPEC-300 (D3 "traços rancorosos entregam o jogador",
  emboscada): spec própria do pilar B/SPEC-299. Aqui só a filiação dinâmica
  (R10) que ela pode usar.
- Deserção ou morte de líder escolhida por narrativa; sucessão de liderança além
  da cascata existente (`rule_faction_leader_death`).
- Agenda por período (hora do dia), rotinas dentro da cidade, horário de loja.
- NPCs fora do elenco, criaturas do bestiário e NPCs do pool compartilhado
  (SPEC-297) além de serem tratados como "conhecidos" quando já estão em
  `state.npcs`.
- Propagar notícia **para** companheiro em espera (fora de escopo também na
  SPEC-300).
- Mudar `relationship`/aprovação além do +1 de resgate (R16).
- UI web nova: aqui só os campos de API (R23). Rótulo "em perigo"/"desaparecido"
  no HUD/dossiê com o texto atual; tela de notícias na SPEC-296/frente D.
- Corrigir `danger_overrides` exposto na API (SPEC-302 P13).

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/npc_world.py` | **Owner de `npc_sim` e `npc_beliefs`.** `mode`, `roster`, `location_of`, `resolve_location_ref`, `npc_faction`, hook diário (`day_hook`), agenda, deserção, perigo/destino, `record_beliefs`, `belief_view` |
| `services/npc_perils.py` | Puro: exposição (R12), hazard (R13), abertura com slot (R14), telegrama (R15), intervenção (R16/R17), destino (R18) |
| `data/world/npc_world.json` | Constantes, `key_npcs`, `agenda_by_npc`, `BASE_HAZARD`, `CRISIS_MULT`, `ROLE_MULT`, `fate_weights`, `defection_causes` |
| `data/world/npc_agendas.json` | Arquétipos (R3) e tabela de radicais de `role` (R4) |
| `data/world/npc_templates.json` | Templates pt-BR dos itens `npc_*` (R20), com `visibility` |
| `docs/spec304/npc_world_sim.py`, `docs/spec304/README.md` | Calibração (R31) |
| `tests/test_spec304_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `services/npc_layers.py`:
  - `npcs_in_scene`/`npcs_for_context` usam `npc_world.location_of` com o modo
    `on` (R7);
  - `visible_npc_view` recebe `state` opcional e lê `belief_view` (R23).
- `services/npc_knowledge.py`:
  - `_residents` usa `location_of` (R7);
  - `SUBJECT_PARAMS` ganha `npc_peril_warning` (0,9; 20; 2),
    `npc_offscreen_fate` (0,8; 15; 2) e `npc_defected` (0,6; 15; 1)
    `[BALANCEAR]`.
- `agents/storyteller.py` (`_with_new_npc`, `:414-481`): o bloqueio de
  teletransporte e o de NPC morto da R8.
- `services/structured_outputs.py`: `EventType` + 4 tipos (R25).
- `services/world_validators.py`: os validadores dos 4 tipos e a barreira
  engine-only.
- `services/event_processor.py`:
  - `apply_event`: `npc_defected` → `npc_affiliations`; `npc_offscreen_fate` →
    nada na projection;
  - `process_pending_events`: `npc_offscreen_fate` `morto` → `killed_targets`;
    `ferido`/`capturado` → patch de `npcs`;
  - `_chronicle_milestone`: pula `payload.offscreen`, grava `npc_fate_learned`.
- `services/chronicle.py`: `npc_fate_learned` em `CHRONICLE_EVENT_TYPES` +
  template.
- `services/context_builder.py` (`:268-274`): filtro de eventos off-screen não
  percebidos (R23).
- `services/dossiers.py` (`:154`, `:160`): `encounters` e `status` pela crença.
- `services/world_director.py` (SPEC-302): `CrisisKind` + `npc_perigo` (sem
  `loc_state`).
- `services/world_perception.py` (SPEC-302): o canal (d) mensageiro e os itens
  `npc_*`.
- `state.py`: `NpcSimEntry`, `NpcPeril`, `NpcSimState`, `NpcBelief`;
  `GameState.npc_sim`, `npc_sim_shadow`, `npc_beliefs`;
  `WorldProjection.npc_affiliations`.
- `persistence.py` (`_raw_to_state`): defaults `{}`.
- `api.py` (`_npcs_block`, `:2565-2583`): passa `state` para
  `visible_npc_view`.
- `playtest/invariants.py`, `playtest/report.py`, `playtest/scenarios.py`
  (cenários `npc_perigo` e `companheiro_exposto`, §4 Etapa 7), `.env.example`
  (`RPG_NPC_WORLD`).

### 3.3 Schemas (`state.py`)

```python
NpcFate = Literal["morto", "ferido", "capturado", "escapou"]
PerilKind = Literal["emboscada", "cerco", "praga", "abismo", "cativeiro"]


class NpcPos(TypedDict, total=False):
    location_id: str  # "" enquanto em viagem
    travel_from: str
    travel_to: str
    arrive_day: int | None
    since_day: int
    return_day: int | None
    refugee_from: str  # casa em crise (R6)


class NpcPeril(TypedDict, total=False):
    peril_id: str  # sha256(game_id|npc|opened_day)[:16]
    npc_id: str
    major: bool  # R14
    kind: str  # PerilKind
    location_id: str
    region_id: str
    opened_day: int
    earliest_day: int
    deadline_day: int
    extensions: int  # R17, ≤ MAX_EXTENSION_DAYS
    channel: Literal["rumor", "pedido_de_ajuda"]
    warning_event_id: str
    perceived_day: int | None
    resolution: str  # "" | "intervencao" | NpcFate
    resolved_day: int | None


class NpcSimEntry(TypedDict, total=False):
    archetype: str
    pos: NpcPos
    status: str  # "" | "ferido" | "capturado" (espelho do evento)
    status_until_day: int | None
    last_peril_end_day: int | None
    frozen: bool  # saiu do elenco (R1)


class NpcSimState(TypedDict, total=False):
    version: int  # 1
    enabled_from_day: int
    roster: list[str]
    roster_fingerprint: str
    npcs: dict[str, NpcSimEntry]
    perils: list[NpcPeril]  # ativos + últimos 30 resolvidos
    last_leader_death_day: int | None
    tick_log: list[dict]  # anel 30


class NpcBelief(TypedDict, total=False):
    status_known: (
        str  # "" | "ausente" | "em_perigo" | "ferido" | "capturado" | "morto" | "desaparecido"
    )
    location_known: str  # location_id ou ""
    faction_known: str
    as_of_day: int
    channel: Literal["testemunho", "rumor", "mensageiro"]
    source_event_id: str
```

O teto de tamanho é de 60 entradas × ~250 B + 30 perigos: < 25 KB. Um teste de
teto garante isso.

### 3.4 Assinaturas públicas

```python
# services/npc_world.py
MODES = ("off", "shadow", "on")
def mode() -> str
def roster(state: dict) -> list[str]
def location_of(state: dict, npc_key: str) -> str                 # "" = em viagem
def resolve_location_ref(ref: str) -> str                          # nome ou id -> location_id (P6)
def npc_faction(state: dict, npc_key: str) -> str
def day_hook(ctx: "DayContext") -> "DayHookResult"                 # registrado na SPEC-302
def record_beliefs(state: dict, perceived: list[DigestItem]) -> dict[str, NpcBelief]
def belief_view(state: dict, npc_key: str) -> dict                 # {status, location} p/ API/dossiê
def active_perils(state: dict) -> list[NpcPeril]                   # contrato p/ SPEC-305 (sem verdade de destino)

# services/npc_perils.py
def exposure(state: dict, npc_key: str, pos: NpcPos, day: int) -> tuple[bool, str, int]  # (exposto, motivo, perigo)
def maybe_open(state: dict, sim: dict, npc_key: str, day: int, rng) -> tuple[NpcPeril | None, list[dict]]
def check_intervention(state: dict, peril: NpcPeril, day: int, player_ref_loc: str) -> bool
def resolve(state: dict, peril: NpcPeril, day: int, rng) -> tuple[NpcPeril, list[dict], dict]  # (perigo, eventos, patch SPEC-300)
```

**Contrato com o hook da SPEC-302 (confirmado na Etapa 0 e ajustado).** O `DayContext` real
tinha `game_id, day, sim, projection, world, factions, rng`. Foram acrescentados, de forma
aditiva: `state` (o `GameState` + os patches dos dias anteriores da MESMA ação) e `events` (os
eventos do log desde o último tick + os já aplicados no dia). O destino da ação do jogador é
`ctx.world["current_location_id"]` e a vaga do diretor é `world_director.request_crisis_slot(ctx.sim,
…)` (não há `request_crisis_slot` no contexto). O `DayHookResult` real tinha `pressure_deltas, events,
digest, baseline_offsets`; ganhou `state_patch` (chaves do `GameState` que o hook escreve:
`npc_sim`/`npc_sim_shadow`, e — via interface da SPEC-300 — `party`, `npcs`, `companion_souls`,
`quests`, `event_log`). `WorldTickResult.state_patch` leva o patch ao storyteller, que o mescla
no `sim_updates` E no `state` do turno antes de todo o resto (`agents/storyteller.py`). O
registro do hook é `register_day_hook("npc_world", day_hook, stage="post", order=10)`.

Ordem do hook por dia `d`:

1. elenco (R1);
2. status vencidos (`ferido` → "");
3. intervenção nos perigos abertos (R16);
4. resolução dos que vencem em `d` (R17/R18);
5. agenda/fuga (R5/R6);
6. deserção (R10/R11);
7. exposição → abertura com telegrama (R12–R15);
8. itens do digest.

Resolver antes de mover impede que o NPC "fuja" do próprio perigo.

### 3.5 Dados (exemplos com IDs reais; valores `[BALANCEAR]`)

`data/world/npc_world.json` (trecho):

```json
{
  "constants": {"ROSTER_CAP": 60, "PERIL_MIN_DANGER": 3, "MAX_ACTIVE_PERILS": 3,
                "PERIL_COOLDOWN_DAYS": 15, "TELEGRAPH_MIN_DAYS": 2, "PERIL_WINDOW": [1, 3],
                "MAX_EXTENSION_DAYS": 3, "LEADER_DEATH_GAP_DAYS": 30, "WOUND_DAYS": 5,
                "RETURN_AFTER_CALM_DAYS": 5, "MAX_DEFECTIONS_PER_DAY": 1},
  "BASE_HAZARD": {"3": 0.02, "4": 0.05},
  "CRISIS_MULT": {"cerco": 3.0, "praga": 2.0, "ocupado": 1.5, "ruina": 2.0, "corrompido": 2.5, "": 1.0},
  "ROLE_MULT": {"sedentario": 1.0, "mercador_itinerante": 1.3, "patrulheiro": 1.5,
                "lider_residente": 0.5, "lider_em_campanha": 1.0},
  "fate_weights": {
    "emboscada": {"morto": 3, "ferido": 4, "capturado": 1, "escapou": 2},
    "cerco":     {"morto": 2, "ferido": 3, "capturado": 3, "escapou": 2},
    "praga":     {"morto": 3, "ferido": 5, "capturado": 0, "escapou": 2},
    "abismo":    {"morto": 4, "ferido": 3, "capturado": 0, "escapou": 3},
    "cativeiro": {"morto": 1, "ferido": 1, "capturado": 6, "escapou": 2}
  },
  "agenda_by_npc": {
    "npc_mv_brunna_ponte_alta": "sedentario",
    "npc_comandante_thrace": "lider_em_campanha",
    "npc_groth_algema_fria": "mercador_itinerante",
    "npc_durgrim_ultimo_martelo": "lider_residente"
  },
  "key_npcs": ["npc_mv_brunna_ponte_alta", "npc_mv_skek_eco_curto", "npc_mv_odrin_calcario",
               "npc_mv_lio_bandeira_vazia"],
  "defection_causes": [
    {"on_event": "location_control_changed", "scope": "home_location", "p": 0.25},
    {"per_day": "faction_defeated", "p": 0.15},
    {"per_day": "faction_war_occupied_region", "p": 0.03}
  ],
  "defection_trait_mult": {"lingua_dupla": 2.0, "desertor_envergonhado": 2.0,
                           "guarda_subornavel": 2.0, "honesto_demais": 0.0, "leal_a_familia": 0.0}
}
```

`data/world/npc_templates.json` (trecho):

```json
{
  "npc_perigo.rumor":           {"visibility": "regional", "text": "Viajantes contam que {npc} está encurralado em {local}; ninguém sabe por quanto tempo aguenta."},
  "npc_perigo.pedido_de_ajuda": {"visibility": "dirigido", "text": "Um mensageiro sem fôlego te encontra: {npc} pede ajuda em {local}, e o tempo é curto."},
  "npc_destino.morto":          {"visibility": "regional", "text": "A notícia chega seca: {npc} não sobreviveu em {local}."},
  "npc_destino.capturado":      {"visibility": "regional", "text": "Dizem que levaram {npc} preso de {local}."},
  "npc_ausente.sabido":         {"visibility": "local",    "text": "Dizem que {npc} partiu para {destino} faz alguns dias."},
  "npc_ausente.ignorado":       {"visibility": "local",    "text": "{npc} não está; ninguém sabe dizer para onde foi."},
  "npc_resgate.chegada":        {"visibility": "local",    "text": "Você encontra {npc} acuado, ferido, mas vivo."},
  "npc_lado.mudou":             {"visibility": "regional", "text": "Correm boatos de que {npc} agora anda com {faccao}."}
}
```

Exemplo de evento (Brunna esperando em Saídas Baixas, perigo 3, emboscada):

```json
{"type": "npc_peril_warning", "actor_id": "world", "target_id": "npc_mv_brunna_ponte_alta",
 "source": "engine",
 "payload": {"peril_id": "9f2c…", "kind": "emboscada", "location_id": "ma_saidas_baixas",
             "region_id": "montanhas_afiadas", "opened_day": 14, "earliest_day": 16,
             "deadline_day": 18, "channel": "pedido_de_ajuda"}}
```

## 4. Plano passo a passo

Marco **M1** = Etapas 0–3 (elenco, agenda, deserção em `shadow`, pousável
sozinho). Marco **M2** = Etapas 4–8 (perigo/destino, crença, `on`, calibração).
Cada marco tem `/spec-land` próprio. Pré-requisito: SPEC-302 M2, SPEC-300 e
SPEC-298 `done`.

### Etapa 0 — Ownership e sondas

1. Consultar `project_index/state_ownership` para os writers de `npcs`, `party`,
   `world_projection`, `chronicle`. Registrar no PR o novo owner (`npc_sim`,
   `npc_beliefs` → `services/npc_world.py`).
2. Confirmar no source da SPEC-302 o contrato real de
   `DayContext`/`DayHookResult` (§3.4) e de `request_crisis_slot`. Se divergir,
   atualizar a §3 desta spec no mesmo commit.
3. Baseline: `--all --turns 50` e `combate` seeds 21–32 × 200 com
   `RPG_WORLD_ENGINE=on`, `RPG_NPC_WORLD=off`. Guardar em
   `docs/spec304/README.md`.

### Etapa 1 — Estado, modo, elenco

1. **Testes** (`tests/test_spec304_roster.py`):
   - `test_roster_priority_order` (party > querido > líder > conhecido > chave);
   - `test_roster_cap_60`;
   - `test_roster_excludes_dead`;
   - `test_roster_stable_same_inputs`;
   - `test_out_of_roster_frozen_untouched`;
   - `test_mode_off_noop_byte_identical` (os updates do turno são iguais aos de
     hoje);
   - `test_engine_off_forces_npc_world_off`;
   - `test_legacy_save_initializes_all_home_no_retro`;
   - `test_save_load_roundtrip_npc_sim_and_beliefs`;
   - `test_npc_sim_size_bound`;
   - `test_keys_in_gamestate_typeddict`;
   - `test_no_global_random_in_npc_modules` (AST).
2. **Implementação:** `state.py`, `persistence._raw_to_state`,
   `npc_world.mode/roster`, registro do hook, dados mínimos.

### Etapa 2 — Agenda, viagem e posição na cena

1. **Testes** (`tests/test_spec304_agenda.py`):
   - `test_sedentary_never_moves`;
   - `test_itinerant_leaves_and_returns_within_stay_days`;
   - `test_travel_duration_from_world_distance`;
   - `test_travel_avoids_blocked_route`;
   - `test_refugee_flees_siege_and_returns_after_calm` (com `location_state`
     sintético da SPEC-302);
   - `test_leader_residente_does_not_flee`;
   - `test_archetype_from_role_closed_table` (inclui "mercadora" e um `role` sem
     casamento → `sedentario`);
   - `test_npcs_in_scene_uses_location_of`;
   - `test_npcs_for_context_hides_absent_npc`;
   - `test_residents_uses_location_of` (SPEC-215: a notícia é entregue onde o
     NPC está);
   - `test_storyteller_does_not_teleport_absent_npc` (R8);
   - `test_storyteller_never_revives_dead_graph_npc` (P3, NPC fora de
     `state.npcs` com `alive=False`);
   - `test_absence_digest_on_arrival_home` (R9);
   - `test_same_seed_same_positions`;
   - `test_independent_of_player` (o mesmo estado com `level` 1/20 e ouro
     diferente dá o mesmo `npc_sim`).
2. **Implementação:** agenda/fuga em `npc_world.py`, `location_of`,
   `resolve_location_ref`, alterações em `npc_layers`/`npc_knowledge`/
   `storyteller`.

### Etapa 3 — Troca de lado (fecha M1 em `shadow`)

1. **Testes** (`tests/test_spec304_defection.py`):
   - `test_defection_on_home_control_change`;
   - `test_trait_multiplier_and_blocker_zero`;
   - `test_leader_never_defects`;
   - `test_party_member_never_defects`;
   - `test_max_one_defection_per_day`;
   - `test_npc_defected_engine_only` (a proposta da LLM é rejeitada);
   - `test_apply_event_sets_npc_affiliation`;
   - `test_npc_faction_resolution_order`;
   - `test_shadow_writes_shadow_key_only`.
2. **Implementação:** deserção, `npc_defected` (EventType, validator,
   `apply_event`), `npc_faction`.

### Etapa 4 — Exposição, perigo e telegrama

1. **Testes** (`tests/test_spec304_perils.py`):
   - `test_exposure_by_danger_state_and_route`;
   - `test_never_exposed_at_player_location`;
   - `test_waiting_at_name_resolved_to_id` (P6);
   - `test_hazard_seeded_deterministic`;
   - `test_caps_active_per_npc_cooldown`;
   - `test_major_peril_requires_crisis_slot` (sem vaga → não abre; o slot
     consome o orçamento da 302);
   - `test_leader_death_gap_30_days`;
   - `test_warning_emitted_same_day_with_location_id` (P10);
   - `test_warning_propagates_via_spec215` (`location_heard` do destino);
   - `test_help_request_delivered_to_player_location_before_deadline`;
   - `test_companion_telegraph_calls_spec300_interface` (dublê da SPEC-300).
2. **Implementação:** `npc_perils.exposure/maybe_open`, `npc_peril_warning`,
   `SUBJECT_PARAMS`, `CrisisKind npc_perigo`, canal (d) em `world_perception`.

### Etapa 5 — Intervenção e destino

1. **Testes** (`tests/test_spec304_fate.py`):
   - `test_intervention_by_arrival_saves`;
   - `test_intervention_by_multi_day_travel_destination`;
   - `test_companion_set_following_cancels_fate`;
   - `test_no_fate_before_earliest_day`;
   - `test_major_unperceived_extends_then_non_lethal` (R17);
   - `test_minor_can_die_unperceived`;
   - `test_fate_weights_seeded`;
   - `test_graph_npc_death_uses_npc_killed_canonical_path` (`apply_npc_death` +
     `fail_orphan_quests` + `alive=False`);
   - `test_runtime_npc_death_uses_offscreen_fate`;
   - `test_companion_death_via_apply_companion_fate_and_npc_killed_idempotent`
     (sem `quest_failed` duplicado);
   - `test_leader_death_triggers_world_rules_cascade`;
   - `test_captured_sets_captor_and_location`;
   - `test_wounded_expires`;
   - `test_offscreen_actor_is_world_not_player` (a SPEC-298 não conta como feito;
     a SPEC-300 não gera `matou_*`);
   - `test_rescue_relationship_plus_one_via_spec298`;
   - `test_every_npc_event_passes_validator` (120 dias × 10 seeds).
2. **Implementação:** `check_intervention`, `resolve`, `npc_offscreen_fate`
   (EventType, validator, `process_pending_events`), integração com a SPEC-300.

### Etapa 6 — Crença do jogador e não-onisciência

1. **Testes** (`tests/test_spec304_beliefs.py`):
   - `test_belief_from_perceived_item_only`;
   - `test_belief_on_meeting_in_person`;
   - `test_api_npc_status_from_belief_not_truth`;
   - `test_dossier_status_and_encounters_filtered`;
   - `test_context_builder_skips_unperceived_offscreen_events`;
   - `test_chronicle_milestone_only_on_fate_learned`;
   - `test_oracle_no_death_leak_anywhere` (varre `/game/state`, `/dossiers`, a
     resposta de turno e o prompt montado do storyteller com MockLLM);
   - `test_unknown_npc_never_named_in_templates`;
   - `test_unknown_faction_label_in_defection_item`;
   - `test_zero_new_llm_calls` (conta invokes com e sem elenco);
   - `test_narrator_name_check_accepts_perceived_npc_names_only`.
2. **Implementação:** `record_beliefs`, `belief_view`, `npc_fate_learned`,
   alterações em `npc_layers.visible_npc_view`, `dossiers`, `context_builder`,
   `chronicle`, `event_processor._chronicle_milestone`, `api._npcs_block`.

### Etapa 7 — Playtest e calibração

1. **Testes:**
   - `tests/test_spec304_playtest.py`:
     - `test_invariants_detect_each_violation` (estado sintético para cada um
       dos 7 invariantes);
     - `test_report_has_npc_section`;
     - `test_scenario_companheiro_exposto` (oráculo: Brunna esperando em
       `ma_saidas_baixas` com perigo 3 e crise forçada → `npc_peril_warning`
       ≤ 5 dias → mensageiro percebido → sem intervenção, o destino aplica no
       `deadline_day`; com chegada antes, `intervencao`);
   - `tests/test_spec304_calibration.py` (rápido, 30 dias × 3 seeds): N5 e N6
     sempre valem.
2. **Implementação:** invariantes, relatório, cenários `npc_perigo` e
   `companheiro_exposto` em `playtest/scenarios.py`, `docs/spec304/
   npc_world_sim.py`; ajuste de `[BALANCEAR]` até fechar N1–N7.

### Etapa 8 — Prova

1. Repetir a baseline da Etapa 0 com `RPG_NPC_WORLD=on` (R32) e registrar o
   antes/depois na §8.
2. Ruff nos arquivos tocados. Suíte completa (`-n auto`) 1× no pouso.

## 5. Critérios de aceite

- [ ] R1–R2: elenco ≤ 60, determinístico, congelamento fora do elenco
- [ ] R3–R9: agenda/viagem/fuga; cena e SPEC-215 usam a posição; o narrador não
      teleporta nem revive; ausência perceptível
- [ ] R10–R11: deserção por causas da tabela, nunca de líder nem da party
- [ ] R12–R19: exposição, hazard com tetos, perigo maior via
      `request_crisis_slot`, telegrama sempre com `location_id`, intervenção,
      morte maior só com telegrama percebido, destino pelo caminho canônico,
      ator nunca o jogador
- [ ] R20–R24: itens de digest, canal mensageiro, `npc_beliefs`, nenhuma
      superfície vaza a verdade (teste-oráculo), zero chamada LLM nova
- [ ] R25: 4 tipos engine-only; todo evento passa no validator
- [ ] R26–R28: writer único, determinismo/idempotência, saves antigos e
      round-trip
- [ ] R29: `off` byte a byte; `shadow` sem efeito; `on` completo
- [ ] R30: 7 invariantes e seção "NPCs" no relatório
- [ ] R31: N1–N7 fechadas no simulador (tabela em `docs/spec304/README.md` e §8)
- [ ] R32: `--all --turns 50` sem erro; M1/M2/M5 da SPEC-285 inalteradas
- [ ] Nenhum `with_structured_output` novo (o guard de FallbackLLM continua só
      no `narrate_day` da SPEC-302)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando
- [ ] Revisão independente Opus (`handoffs/SPEC-304-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado na §8

## 6. Smoke test com LLM real

Teto do dono: US$ 3/dia, só campanhas curtas. Pré-requisito: `RPG_WORLD_ENGINE=on`,
`RPG_NPC_WORLD=on`, `RPG_NPC_KNOWLEDGE=on`, `RPG_COMPANION_SOUL=on`, DeepSeek nas
`ROUTES`. O MockLLM esconde a qualidade da narração e a checagem de nomes do
`narrate_day` com itens `npc_*`, por isso este passo é obrigatório.

1. `uv run python -m playtest run --scenario companheiro_exposto --turns 15 --real --max-cost 0.40 --seed 21`
   (ações de descanso/viagem longe de Brunna). Assertar:
   - `mock=False`;
   - `npc_peril_warning` e depois o mensageiro percebido no transcrito;
   - o destino aplicado no `deadline_day`;
   - ≤ 1 invoke de `WorldDayNarration` por ação que virou o dia (telemetria);
   - 0 violação `error`.
2. O mesmo cenário com `--seed 22` e a ação de viajar até `ma_saidas_baixas`
   antes do prazo → `resolution="intervencao"`, narração da chegada com Brunna
   viva, sem combate inventado pela LLM.
3. `uv run python -m playtest transcript <run_id>`: leitura humana de 5 trechos.
   A narração não cita morte, local de morte nem NPC que não estão nos itens
   percebidos. `/game/state` e o dossiê de Brunna só mostram "em perigo"/"morta"
   depois da percepção.
4. `uv run python -m playtest run --profile explorador --turns 30 --real --max-cost 0.60 --seed 23`:
   a seção "NPCs" do relatório tem perigos/destinos/ausências e nenhum
   `structured_invalid` repetido.
5. Staging (depois do pouso, `shadow` primeiro): 1 sessão manual de ~10 ações
   com descanso. Conferir `npc_world.tick` (`mode=shadow`) nos logs, sem
   mudança visível. Depois do OK do dono, `on` e repetir.

Custo esperado: ≤ US$ 1,20 no total. Se algum passo estourar o teto, parar e
registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** as chaves novas têm default `{}`; o primeiro tick ligado põe
  todos em casa, sem perigos e sem retroativo. As crenças nascem do visível
  atual. Sem bump de schema.
- **Dependência de contrato da SPEC-302:** `DayContext`/`DayHookResult` ainda não
  existem no código. A Etapa 0 confirma o contrato. Se a 302 não aceitar
  `state_patch` de `npc_sim`, a alternativa é o hook devolver o patch e o
  storyteller mesclar (o mesmo ponto onde a 302 já devolve `world_sim`,
  `agents/storyteller.py:532-596`).
- **Teletransporte vs. narrativa:** o bloqueio da R8 pode frustrar o narrador
  que "chama" um NPC conhecido. Mitigação: o contexto já não lista ausentes
  (R7), e o log `npc.reintroduction_blocked` mede a frequência no playtest.
- **Mortes injustas:** perigo menor pode matar sem o jogador saber (decisão D3).
  Perigo maior, não: R17 + N6. A ausência de onisciência faz o jogador descobrir
  a morte tarde (pela notícia), o que é intencional.
- **Orçamento de crise:** com `npc_perigo` usando vagas, as crises regionais
  ficam um pouco mais raras. N7 mede isso. Se a C1 da SPEC-302 cair (o dono
  definiu que o ritmo de crise vence, D4 da 302), perigo maior passa a ter
  orçamento próprio (D2).
- **Cascata de líder:** a morte off-screen de líder com `power_vacuum_trigger`
  dispara `location_control_changed` (`data/graph/world_rules.json:2-27`).
  Isso é intencional (o mundo muda) e é limitado por `LEADER_DEATH_GAP_DAYS`, o
  slot do diretor e N3.
- **Propagação com relógio da ação:** eventos de dias anteriores da mesma ação
  são agendados pela SPEC-215 a partir do relógio final
  (`services/npc_knowledge.py:649-660`), o que pode atrasar um pouco a notícia.
  É aceitável e fica registrado.
- **Duplicidade com a SPEC-300:** companheiro de grafo morto gera
  `companion_fate` e `npc_killed`. A idempotência de `apply_npc_death` e o teste
  de `quest_failed` único cobrem isso.
- **MockLLM/FallbackLLM:** não há LLM nova. A narração cai nos templates da
  SPEC-302. A suíte offline exercita toda a mecânica.
- **Quota/latência:** zero chamadas novas. O hook é O(60 NPCs) por dia, com o
  teto de 10 dias por ação da 302.
- **Letalidade (SPEC-285):** sem efeito no combate. O NPC ferido ou capturado
  não entra em combate. R32 mede.
- **Rollback:** `RPG_NPC_WORLD=off` desliga sem migração reversa (as chaves
  ficam inertes; as crenças são ignoradas e as superfícies voltam à verdade).

## 8. Evidência

- **Etapa 0 (ownership/contrato):** writers de `npcs`/`party`/`world_projection`/`chronicle`
  conferidos no source; novo owner de `npc_sim`/`npc_sim_shadow`/`npc_beliefs` =
  `services/npc_world.py` (para registrar no PR). Contrato real do hook da 302 divergia: ver §3.4.
- **Vazamentos de regra de ouro corrigidos (§1.1):** P7 (status `morto` na API/dossiê →
  `npc_world.visible_status`/`belief_view`), P8 (crônica só em `npc_fate_learned`), P9 (contexto
  do narrador sem eventos off-screen não percebidos, inclusive a linha "X: morto" de
  `projection.entities`), P3 (NPC de grafo morto nunca é recriado/reintroduzido), P2/P6 (o
  narrador não relocaliza; `waiting_at` resolvido por `resolve_location_ref`), P10
  (`_event_origin` sem fallback ao local do jogador para eventos off-screen) e P13 (`_residents`
  pela posição simulada).
- **Calibração N1–N7:** `docs/spec304/README.md` (40 seeds × 120 dias; todas as metas fechadas).
- **R32:** `--all --turns 50` (`RPG_WORLD_ENGINE=on RPG_NPC_WORLD=on`, MockLLM): 16 perfis, 0 erro,
  0 violação `error`. `combate` 200 turnos, seeds 21–22, `off` vs `on`: 0 mortes e 0 quedas do
  jogador nos dois (a spec não toca o combate).
- **Testes:** `tests/test_spec304_{roster,agenda,defection,perils,fate,beliefs,playtest}.py`
  (+ `spec304_helpers.py`). Ligou-se o tipo `resgate` da SPEC-305 (`_item_matches` casa o item
  `npc_perigo`); `test_resgate_off_without_spec304` virou `test_resgate_on_with_spec304_but_no_perils`.
- **Pendências:** revisão independente Opus; smoke real §6 (sem chave); D5 (flip do default);
  `project_index` stale até o `/spec-land`.

## 9. Decisões do dono

- **D1 — Composição do elenco (R1).** Proposto: party > queridos > 21 líderes >
  conhecidos > 36 `npc_mv_*`, teto 60. Alternativa: só conhecidos + líderes
  (sem `key_npcs`).
- **D2 — Orçamento dos perigos.** Proposto: só o perigo **maior** (líder, party,
  querido) usa `request_crisis_slot`; o menor tem teto próprio (3 ativos).
  Alternativa: todos usam o slot (o mundo fica mais calmo, mas a C1 da 302 pode
  cair) ou nenhum usa (risco de "máquina de crises").
- **D3 — Morte sem telegrama percebido.** Proposto: perigo maior só mata se o
  jogador percebeu o aviso (com extensão de prazo até 3 dias); perigo menor pode
  matar com aviso só emitido. Alternativa: exigir percepção para todo NPC
  conhecido.
- **D4 — Pedido de ajuda por mensageiro (canal d).** Proposto: perigo maior manda
  mensageiro que encontra o jogador onde ele estiver (é testemunho). Alternativa:
  só rumor pela SPEC-215 (mais fiel ao "ninguém sabe onde você está", mas o
  jogador perde mais companheiros).
- **D5 — Default de `RPG_NPC_WORLD`.** Proposto: `on` local e na suíte; `shadow`
  no staging até o smoke §6; `on` no staging depois do OK.
- **D6 — Líder pode morrer off-screen?** Proposto: sim, com perigo maior + slot
  + 1 a cada 30 dias. Alternativa: líderes imunes (só morrem em cena).
- **D7 — Bloqueio de teletransporte (R8).** Proposto: o narrador não traz NPC
  ausente. Alternativa: permitir e "puxar" a agenda (o NPC volta para onde o
  jogador está), o que é mais permissivo e quebra a agenda.
- **D8 — Pesos de destino e hazard (§3.5).** Aceitar os defaults `[BALANCEAR]` e
  calibrar por N1–N7, ou fixar metas diferentes (ex.: P(morte | perigo maior)
  maior que 0,50).


## Decisões do dono (2026-10-23)

Todas as decisões abertas seguem o **default recomendado pelo autor**, exceto/explicitando:

- D4: pedido de ajuda por MENSAGEIRO que encontra o jogador onde ele estiver (conta como testemunho/ouvido).

## Desvios e decisões de implementação (2026-10-24)

- `BASE_HAZARD` 0,06/0,10, `HOME_MULT` 0,05 (novo), `fate_weights.emboscada.morto` 6,
  `LEADER_DEATH_GAP_DAYS` 60: ver `docs/spec304/README.md` (N1–N7).
- Perigo maior anuncia a vaga no telegrama e a abre em `earliest_day` (ver R14 acima).
- Destino de companheiro afastado: `apply_companion_fate` sem o `chronicle` (a morte só entra
  na crônica quando PERCEBIDA, via `npc_fate_learned`); recusa `FateNotTelegraphed` vira
  intervenção. **Limitação conhecida:** o companheiro morto some da lista de `party` da API na hora
  (a verdade da SPEC-300), antes de o jogador saber; o texto de morte não vaza, a ausência sim.
- `npc_ferido`: a expiração é só de leitura (`wounded_until_day` na ficha); a ficha não tem writer
  de expiração. O `npc_sim` zera o status no hook.
- Cenários dirigidos (`npc_perigo`, `companheiro_exposto`) usam o único gancho de teste do
  motor, `npc_sim["forced"]` (o sorteio de abertura vira acerto); ausente em jogo normal.
- `data/world/npc_world.json` tem a tabela `agenda_by_npc` com os 21 líderes + 12 `npc_mv_*`
  (os demais caem na tabela de radicais do `role`) e `key_npcs` = os 36 `npc_mv_*`.
