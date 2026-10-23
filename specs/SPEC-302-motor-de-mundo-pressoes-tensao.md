# SPEC-302 — Motor de mundo: tick diário, pressões regionais e curva de tensão

> **Status:** `done` (2026-10-23) — M1+M2 na main (`0433070`); revisão Sol APPROVED_WITH_FOLLOWUPS (`handoffs/SPEC-302-sol-review.md`; F-1 corrigido; F-2 `brekmar` C1 15–16 no limite, aceito pela D4). Smoke real §6 DeepSeek (cenário `mundo`, 15 turnos, seed 11): 6 dias, 1 crise iniciada e percebida, 4 sinais, 0 erros (28 `rag.persistence_error` = FAISS local com acento no caminho, não relacionado). Staging `RPG_WORLD_ENGINE=on` em `834f8d7` (`e2e_session` verde).
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-23
> **Origem:** `docs/mundo-vivo/VISAO.md` (decisões 2–5, "A. Mundo autônomo", "Calibração", "Regra de ouro")
> **Depende de:** SPEC-215 (`done`, propagação de notícias), SPEC-233 (`done`, perigo efetivo), SPEC-003 (`done`, eventos estruturados), SPEC-285 (`done`, metas de letalidade que não podem regredir). SPEC-296 item 5 (`world.news`) é dependência **fraca**: se ainda não tiver pousado, esta spec cria `world.news` com o contrato da §3.7, e a 296 reusa.
> **Desbloqueia:** SPEC-298 (fama por local), SPEC-299 (lei/notoriedade com decaimento diário), SPEC-300 (morte off-screen de companheiro), SPEC-301 (relações fação-fação), e as specs filhas propostas na §9 (calendário, agenda de NPCs, quests de mundo com prazo)
> **EXECUTOR_MODEL:** `Opus` (Sol: estado, cross-domain) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (novo writer persistente, novos tipos de GameEvent, mexe em perigo/economia)
> **EVAL_AUTHORING_REQUIRED:** `false` (a calibração usa um simulador determinístico em `docs/spec302/`, não dataset de eval)

---

## 1. Contexto & Objetivo

O mundo de Valoria **reage**, mas não **vive**. O relógio só anda em viagem e
descanso (decisão do dono, mantida). Quando anda, porém, só três coisas
acontecem: o progresso linear das fações, o clima da região atual e um "pulso"
de 1 chamada LLM que inventa um rumor e **decide** se o perigo sobe ou desce. Não
existe "dia" como unidade de simulação. Locais não têm estado (cerco, praga,
escassez). Fações não guerreiam nem se aliam. Nada no motor limita quantas
crises acontecem ao mesmo tempo.

Esta spec cria o **motor de mundo**: um núcleo determinístico (seed por jogo e
dia) que roda **1× por dia de jogo virado**. Ele mantém **pressões regionais**
(guerra, fome, praga, Abismo), que sobem e descem por causas; dispara evento
**só ao cruzar limiar**; e passa tudo por um **diretor de tensão** (calmo →
tensão → crise → recuperação), um orçamento global que limita crises
simultâneas. Fatos do mundo (estado de local, relação entre fações) viram
`GameEvent` com `source="engine"`, entram no `event_log` e se propagam pela
SPEC-215. O jogador só fica sabendo do que viu ou ouviu. A LLM faz **no máximo 1
chamada por ação que vira dia** e **só narra** um resumo já filtrado pelo motor.
Ela nunca decide.

É a spec **fundacional** do pilar A. Ela entrega o núcleo e os **pontos de
extensão** (hooks diários, slot de crise do diretor, leitura de
pressão/estado/relação) que as specs consumidoras usam. Calendário/estações,
agenda e morte off-screen de NPCs e quests de mundo com prazo ficam em **specs
filhas** (§9), que dependem desta.

Princípios: mecânica em Python e determinística por seed; LLM propõe ou narra, o
motor aplica; "o mundo não escala com o herói"; não-onisciência; sem regressão
nas metas da SPEC-285.

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | Não existe tick por dia; tudo anda por **período**, e só em viagem/descanso | `agents/storyteller.py:532-543` (viagem), `:583-596` (descanso); `world_utils.py:64-73` (`advance_clock` só conta períodos) |
| P2 | O progresso das fações é linear, sem RNG, sem regressão e satura. Com 5 períodos/dia, `pace` 4 conclui o objetivo em ~5 dias de jogo e `pace` 2 em ~10. Depois disso a fação fica parada (`completed`), exceto `expandir_regiao` | `world_utils.py:351-380`; `data/factions.json:8,24,41…` (`pace` 2–4); terminalidade em `world_utils.py:429-434` vs `:435-453` |
| P3 | **A LLM decide o perigo**: `WorldPulse.danger_shift` é aplicado pelo motor (viola "a LLM nunca decide") | `agents/world_simulator.py:46-48`, `:154`, `:168` |
| P4 | O fato off-screen é descartado e o rumor vive só um turno | `agents/world_simulator.py:171-183` |
| P5 | O pulso LLM roda em **toda** viagem/descanso sem encontro, mesmo que o dia não vire: o custo acompanha as ações, não os dias | `agents/storyteller.py:789-796` |
| P6 | O perigo decai por **turnos**, não por dias: o relógio do mundo fica misturado com o contador de ações | `world_utils.py:628`, `:643` |
| P7 | Viagem com clima ruim avança o relógio além do custo, mas as fações avançam só o custo-base | `world_utils.py:239-241` vs `agents/storyteller.py:535,540` |
| P8 | As regras sistêmicas são rasas: 6 regras, 1 componente (`power_vacuum_trigger`), todas reativas a evento, nenhuma temporal | `data/graph/world_rules.json:3-96` |
| P9 | Locais não têm estado. `WorldState` e a projection só guardam controle, rotas e únicos | `state.py:229-260`; `services/event_processor.py:127-217` |
| P10 | Relação entre fações: só 5 arestas `enemy_of` estáticas, nenhum tipo de aliança. `faction_relation_changed` existe, mas o motor não emite | `data/graph/edges.json:94-112,199,388`; `data/graph/relation_types.json:1-9`; `services/structured_outputs.py:22`; `services/event_processor.py:168-179` |
| P11 | O preço só reage a rota bloqueada ou controlador hostil | `services/economy.py:161-189` |
| P12 | O `region` das fações é nome de exibição, não `region_id` do mapa | `data/factions.json:6` ("Nova Arcádia") vs `data/world_map.json:30` (`nova_arcadia`) |
| P13 | A API já expõe `danger_overrides` de **todos** os locais (vazamento de onisciência preexistente; aqui só é registrado) | `api.py:2820` |
| P14 | A lore não tem calendário: nenhum festival ou feriado datado (a única ocorrência de "feriado" é negativa). Só há eras candidatas a aniversário | `lore_nova/npcs.txt:88`; `lore_nova/timeline_completa.txt:218` (Era 5, "Dia sem Sombra"), `:318` (Era 6, Pacto de Valerius) — insumo da spec filha de calendário |

## 2. Requisitos

### Tick diário

- **R1 — Unidade = dia virado.** `world_engine.advance_days` é chamado pelo
  storyteller depois de `apply_travel`/`apply_rest`. Ele roda um tick por dia de
  `world_clock.day` que passou desde `world_sim.last_ticked_day`, em ordem
  crescente. Uma ação que não vira o dia roda 0 ticks.
- **R2 — Idempotência.** Repetir a chamada com o mesmo estado (retry de turno,
  replay) não roda o mesmo dia duas vezes (`last_ticked_day`). O resultado é
  idêntico byte a byte.
- **R3 — Determinismo.** Toda aleatoriedade vem de
  `day_rng(game_id, day, salt)` = `random.Random(sha256(game_id|day|salt)[:8])`.
  Nenhum uso de `random` global nos módulos novos (teste por AST/grep, como na
  SPEC-295 R3). Mesmas entradas, mesmo `world_sim`, mesmos eventos.
- **R4 — Teto por ação.** No máximo `MAX_DAYS_PER_ACTION = 10` ticks por ação.
  Acima disso, simula os 10 dias mais recentes, avança `last_ticked_day` e
  registra `world.tick_capped`.
- **R5 — O mundo não escala com o herói.** Nenhuma função do motor lê nível,
  ficha, inventário, ouro ou tamanho da party. Teste: o mesmo estado com
  `player.level` 1 e 20 (e fichas diferentes) produz `world_sim` e eventos
  idênticos. A localização do jogador só afeta a **percepção** (R22–R25), nunca
  a simulação.

### Pressões regionais

- **R6 — Modelo.** Cada uma das 12 regiões (`region_id` de
  `data/world_map.json`) tem 4 pressões inteiras em [0, 100]: `guerra`, `fome`,
  `praga`, `abismo`. Baseline e parâmetros ficam em `data/world/pressures.json`
  (§3.5).
- **R7 — Dinâmica diária**, nesta ordem: (a) causas do `event_log` desde o
  último tick; (b) causas de estado (cerco ativo, guerra entre fações presentes,
  ameaça iminente); (c) deriva rumo à baseline (`drift_per_day`); (d) ruído
  seeded em ±`noise`; (e) contágio de `praga` (R8); (f) clamp [0, 100]. As
  causas são uma tabela de dados, não código ad hoc.
- **R8 — Praga espalha por conexões.** Região com `praga ≥ spread_threshold`
  contagia cada região **adjacente** (adjacência derivada das `connections`
  entre locais de `region_id` diferentes) com probabilidade seeded `spread_p`.
  O ganho é `floor(praga × spread_factor)`. Rota bloqueada (`blocked_routes`) não
  propaga.
- **R9 — Limiar com histerese.** Cada pressão tem bandas `normal` → `sinal`
  (≥ `SINAL`) → `crise` (≥ `CRISE`) e volta a `normal` só abaixo de `RECUPERA`
  (< `SINAL`). Só a **subida** de banda gera evento. Ficar na banda não gera
  repetição. Oscilar em torno do limiar não gera spam (teste com série
  sintética).
- **R10 — Sinais pequenos.** Uma região em banda `sinal`, ou com variação diária
  ≥ `signal_delta`, pode emitir **1 sinal/dia** (preço, rumor, patrulha,
  refugiados, fumaça), escolhido de `data/world/signals.json`. Teto global de
  `MAX_SIGNALS_PER_DAY = 4`. Sinal não consome orçamento de crise e não entra no
  `event_log`: vive em `world_sim.signals` (anel de 60).

### Diretor de tensão (orçamento global)

- **R11 — Fases.** `world_sim.phase ∈ {calmo, tensao, crise, recuperacao}`:
  - `crise`: há ≥ 1 crise ativa;
  - `recuperacao`: durante `RECOVERY_DAYS` depois que a última crise acaba;
  - `tensao`: há ≥ 1 região com crise **anunciada** (R13);
  - `calmo`: nenhum dos casos acima.
  O jogo novo (ou o save migrado) começa `calmo` por `INITIAL_CALM_DAYS`, sem
  crise anunciada nesse período.
- **R12 — Orçamento.** Uma crise nova só abre se: crises ativas <
  `MAX_ACTIVE_CRISES` (2); a região não tem crise ativa e passou
  `REGION_COOLDOWN_DAYS` (12) desde a última crise dela; passou
  `GLOBAL_GAP_DAYS` (3) desde a última crise aberta no mundo; e a fase não é
  `recuperacao`. Com mais candidatas que vagas, o diretor ordena por (pressão
  desc, `region_id`) e desempata pelo rng do dia.
- **R13 — Telegrafado sempre.** Nenhuma crise abre sem **aviso** prévio
  (`world_crisis_warning`) na mesma região e do mesmo tipo, emitido ≥
  `MIN_WARNING_DAYS` (2) antes. Pressão que cruza `CRISE` sem aviso emite o aviso
  nesse dia, e a crise só pode abrir depois do prazo. Invariante de playtest:
  `world.crisis_without_warning` = `error`.
- **R14 — Ciclo da crise.** Cada crise tem `start_day`, `escalation_day =
  start + ESCALATION_DAYS` (6) e `severity` 1–3:
  - ela **encerra** quando a pressão causadora cai abaixo de `RECUPERA` e já
    durou ≥ `MIN_CRISIS_DAYS` (3);
  - no `escalation_day`, se a pressão continua ≥ `CRISE`, ela **escala**:
    `severity +1`; cerco de severidade 3 → `ocupado` (atacante é fação) ou
    `ruina` (atacante é criatura/Abismo);
  - o `escalation_day` é o contrato de prazo que a spec filha de quests usa
    (§9).
- **R15 — Slot público.** `request_crisis_slot(sim, day, region_id, kind) ->
  bool` é a única porta para abrir crise. As specs filhas (morte off-screen,
  calendário) usam essa mesma porta, então o orçamento é global de verdade.

### Estados de local

- **R16 — Estados.** `cerco`, `escassez`, `praga`, `ocupado`, `ruina` (das
  crises) e `festa` (reservado: só a spec filha de calendário escreve). Opcional
  `corrompido`, para crise de `abismo` (decisão D2). Um estado principal por
  local. Interior (`kind: interior`) herda o estado do `parent_id`.
- **R17 — Fonte da verdade = projection.** Estado de local nasce e acaba só por
  `GameEvent` `location_state_changed` (`source="engine"`), aplicado por
  `event_processor.apply_event` em `world_projection.location_states`. O
  `world_sim` guarda só pressões, diretor, sinais e o registro de crises, nunca
  o estado do local.
- **R18 — Alvo da crise.** O local é escolhido de forma determinística entre os
  locais **não-interiores** da região, por peso de tags: `cerco` → `cidade` e
  `vila`/povoado; `escassez` → locais com `economy_tags`; `praga` → qualquer
  povoado; `corrompido` → não-`cidade`. Desempate pelo rng do dia.
- **R19 — Efeitos lidos (sem duplicar estado).**
  `location_effects(state, location_id)` devolve `{price_mult, danger_delta,
  restock_mult, merchant_closed}` a partir de `data/world/location_states.json`.
  Consumidores nesta spec:
  - `economy.price` multiplica `price_mult`;
  - `economy.restock` usa `restock_mult`/`merchant_closed`;
  - `world_utils._effective_danger` soma `danger_delta`, clamp [0, 4] (continua
    sendo a fonte única da SPEC-233);
  - o cerco emite 1 `route_blocked` (conexão do local na direção da região do
    atacante) e `route_cleared` ao terminar.
- **R20 — Permanente, mas recuperável.**
  - `ruina` recupera depois de `RUIN_RECOVERY_DAYS` (40) sem crise na região e
    com todas as pressões < `SINAL`. Passa por `escassez` de severidade 1 por 5
    dias e depois volta a nenhum estado.
  - `ocupado` termina quando a fação ocupante é `defeated`, ou quando a pressão
    `guerra` da região fica < `RECUPERA` por 10 dias. Nesse caso o controlador
    anterior retoma com chance seeded `REOCCUPY_P`/dia, por
    `location_control_changed` `source="engine"`.
  - Ação do jogador que remove a causa recupera mais rápido. Nesta spec só
    contam os eventos que já existem: `route_cleared`, `npc_killed` de líder,
    `location_control_changed`.

### Fações

- **R21 — Relações contínuas.**
  - `world_sim.faction_relations["a|b"]` (ids ordenados das 19 fações de
    `data/factions.json`) fica em [-100, 100]. A semente vem das arestas
    `enemy_of` (-60) e da `disposition` (hostil×hostil -20, neutro 0).
  - Deriva diária por causas: inimigo comum (+), região disputada (-),
    `location_control_changed` entre elas (-15), e deriva lenta à semente.
  - Cruzar −`WAR_THRESHOLD` (−70) é crise do tipo `guerra`: passa pelo diretor
    (R12) e emite `faction_relation_changed` `relation="enemy_of"`.
  - Cruzar +`ALLIANCE_THRESHOLD` (+60) emite `relation="allied_with"`. Conta
    como sinal, não como crise. É preciso um novo tipo `allied_with` em
    `relation_types.json`.
  - Voltar para a faixa neutra emite `relation="neutral"`, que desativa a aresta
    dinâmica.
  - Guerra ativa entre fações presentes na mesma região soma
    `war_presence_per_day` à `guerra` dessa região.
  - As fações de grafo que não estão em `data/factions.json`
    (`resistencia_operaria_martelos_partidos`, `encapuzados_fornalha`,
    `clas_tecnologicos`) ficam fora da matriz.
- **R21b — Progresso de fação no tick (decisão D1).** `advance_factions` passa
  a rodar dentro do tick diário (`pace` por dia × `FACTION_DAY_FACTOR`) e deixa
  de rodar por período no storyteller.
  - A **ascensão** (`resolve_faction_completions`) vira candidata a crise do tipo
    `ascensao` e só acontece se `request_crisis_slot` conceder vaga. Com
    `progress ≥ 80` ela emite aviso (R13).
  - Fação com `progress = 100` sem vaga espera, sem perder progresso.
  - O mapeamento `region` (nome) → `region_id` (P12) fica em uma função única,
    `world_engine.faction_region_id`.

### Percepção e narração (regra de ouro)

- **R22 — Resumo do dia (digest).** Cada tick produz `DigestItem`s: sinal, aviso,
  início/escala/fim de crise, relação, ascensão. Cada item é renderizável por
  template determinístico em pt-BR (`data/world/signals.json`), sem números de
  pressão.
- **R23 — Filtro de percepção.** Um item só chega ao jogador por:
  - (a) **testemunho local**: o local do item é o atual (ou o pai/filho
    interior);
  - (b) **testemunho regional**: a região do item é a atual e o template tem
    `visibility: "regional"` (fumaça, refugiados, patrulhas, preço);
  - (c) **rumor**: o item tem `subject_id` de evento e esse id está em
    `location_heard[local atual]` (SPEC-215 com `RPG_NPC_KNOWLEDGE=on`). Com a
    SPEC-215 `off`/`shadow`, só (a) e (b).
  Para viagem de vários dias, a posição de referência é o destino.
- **R24 — Nomes.** Fação só aparece com nome se `faction_intel[id].known`. Senão
  o template usa o rótulo percebido (reuso de `world_utils.concealed_faction`/
  `public_encounter_hint`). NPC só aparece com nome se estiver em `state.npcs`.
  O teste varre todos os templates com todas as fações desconhecidas.
- **R25 — Notícias persistem como fato do motor.** Itens percebidos são gravados
  em `world.news` (anel de 12) com o **texto do template**, nunca com o texto da
  LLM. Rumor percebido não some no turno seguinte (P4).
- **R26 — LLM só narra, no máximo 1 vez.**
  - `agents/world_simulator.py` vira narrador: recebe só os itens percebidos e
    devolve `WorldDayNarration(text)`.
  - Chamada **apenas** se a ação virou ≥ 1 dia, há ≥ 1 item percebido e o turno
    não caiu em encontro. No máximo 1 chamada por ação (logo ≤ 1 por dia).
  - **Remove** `danger_shift` (P3): nenhum campo vindo da LLM altera estado.
  - Guard de FallbackLLM (`isinstance`); falha ou saída inválida → texto dos
    templates.
  - Saída: `sanitize_meta_preamble` e checagem de nomes (nome de fação/NPC do
    catálogo fora do conjunto permitido → templates). Teto de 600 caracteres.
- **R27 — Propagação.** Os tipos novos entram em `npc_knowledge.SUBJECT_PARAMS`:
  - `location_state_changed` (0,9; 20; 2);
  - `world_crisis_warning` (0,8; 20; 2);
  - `faction_relation_changed` (0,7; 20; 2).
  Valores iniciais `[BALANCEAR]`.

### Eventos, persistência, rollout

- **R28 — Tipos de evento.** `EventType` ganha `location_state_changed` e
  `world_crisis_warning`. Esses dois, mais `faction_relation_changed` e
  `location_control_changed` emitidos pelo motor, exigem
  `source ∈ {"engine"}`: a mesma barreira de `unique_item_*`. Proposta da LLM
  desses dois tipos novos é rejeitada. Todo evento emitido pelo motor passa
  `validate_proposal` (teste por propriedade sobre 120 dias × 10 seeds).
- **R29 — Saves antigos.** `world_sim` ausente → no primeiro `advance_days`
  inicializa com `enabled_from_day = last_ticked_day = dia atual`, pressões na
  baseline, fase `calmo` e calma inicial contada a partir daí. **Sem simulação
  retroativa.** Chave aditiva, sem bump de `SCHEMA_VERSION` (mesmo padrão da
  SPEC-215). O round-trip save/load preserva `world_sim` e
  `world_projection.location_states`.
- **R30 — Rollout `RPG_WORLD_ENGINE=off|shadow|on`.**
  - `off`: comportamento atual (o caminho legado de `simulate_world` com
    `danger_shift`, para rollback).
  - `shadow`: o motor roda e grava em `world_sim_shadow`. Não emite eventos, não
    aplica efeitos, não muda a narração e loga `world.tick`.
  - `on`: tudo ligado. A transição `shadow` → `on` inicializa `world_sim` do
    zero (R29), sem herdar crises sombra.
  - Default: decisão D5.
- **R31 — Privacidade da API.** `world_sim` nunca sai pela API. `_world_block`
  (`api.py:2792`) ganha só `location_state` do local **atual** (rótulo vago,
  ex.: "sitiada"; sem severidade numérica) e `news` (R25). Teste: nenhuma
  resposta contém `pressures`, `world_sim`, `faction_relations` ou `severity`.
- **R32 — Telemetria e playtest.**
  - Log JSON `world.tick` com `{day, phase, active, started, ended, signals,
    perceived, mode}`.
  - O playtest grava, por campanha: dias decorridos, crises iniciadas/percebidas
    e sinais percebidos. O `report` ganha a seção "Mundo", que mede quantos dias
    passam por perfil (pedido do dono).
  - Invariantes novos: `world.crisis_cap_exceeded` (error),
    `world.crisis_without_warning` (error), `world.pressure_out_of_range`
    (error), `world.day_ticked_twice` (error).
- **R33 — Calibração (meta do dono).** Simulador offline
  `docs/spec302/world_engine_sim.py` (sem LLM, sem grafo), 120 dias × 20 seeds:
  - **C1** — crises **perceptíveis** (na região ou em região adjacente) por
    região: mediana do intervalo entre inícios ∈ [10, 15] dias nas regiões de
    partida e nas mais visitadas pelos perfis (`nova_arcadia`, `brekmar`,
    `pradaria_ruinas`, `pantano_melancolia`);
  - **C2** — sinais testemunháveis (R23 a/b) nessas regiões: mediana do intervalo
    ≤ 2 dias;
  - **C3** — crises simultâneas ≤ `MAX_ACTIVE_CRISES` em 100 % dos dias;
  - **C4** — dias com ≥ 1 crise ativa no mundo ≤ 50 %; nenhuma região passa mais
    de 35 % dos dias em crise;
  - **C5** — 100 % das crises com aviso ≥ `MIN_WARNING_DAYS` antes;
  - **C6** — sem `ruina` permanente: toda ruína tem dia de recuperação dentro do
    horizonte ou pressão que a sustenta registrada.
  Tabela em `docs/spec302/README.md`. As constantes `[BALANCEAR]` são ajustadas
  até fechar C1–C6.
- **R34 — Letalidade.** Playtest `combate` seeds 21–32 × 200 turnos (MockLLM),
  matriz SPEC-056 e `--start-level 5`: M1 (≤ 0,564), M2 (mediana da 1ª queda
  ≥ 20) e M5 (0 `combat.no_progress`) da SPEC-285 continuam valendo com
  `RPG_WORLD_ENGINE=on`. Se `danger_delta` piorar alguma, a correção é no
  `danger_delta`/alvo da crise, nunca no combate.

### Fora de escopo

- **Calendário, estações e festas** (passos de montanha, seca, datas da lore):
  spec filha **302-B** (§9). Aqui só ficam reservados o estado `festa` e o hook
  de modificador de pressão.
- **Agenda, viagem, troca de lado e morte off-screen de NPCs** (inclusive da
  party): spec filha **302-C**. Aqui ficam o hook pós-tick e `request_crisis_slot`.
- **Quests nascidas do estado com prazo** (`deadline_day` no `quest_log`): spec
  filha **302-D**. Aqui fica `escalation_day` como contrato.
- Contra-jogo novo do jogador (romper cerco, curar praga): só as causas de
  eventos que já existem (R20). Ações dedicadas ficam na 302-D.
- Viagem bloqueada por `route_blocked` (hoje só afeta economia; o
  `world_utils` não lê `blocked_routes`).
- Tornar o clima determinístico (`world_utils.py:1179-1181` usa `random`
  global) e acoplar Abismo ao clima/criaturas: follow-up (D. Presença / B.
  Combate).
- Vazamento de `danger_overrides` na API (P13): registrado para a SPEC-296 ou a
  frente D.
- UI web além dos campos de API (R31): rótulo no HUD e aba de notícias ficam na
  SPEC-296 (news) e na frente D.
- Ascensão de fação via eventos (hoje ela escreve `world["controlled"]` e
  `danger_overrides` direto): mantida como está, só passa a ser gateada.
- Pool compartilhado (SPEC-297), reputação (298), lei (299), companheiros (300),
  patentes (301): consomem esta spec, não fazem parte dela.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/world_engine.py` | **Owner canônico de `world_sim`.** `advance_days`, `day_rng`, ordem do tick, registro de hooks, migração (R29), modo (R30), `faction_region_id` |
| `services/world_pressures.py` | Modelo puro de pressão: causas, deriva, ruído, contágio, bandas/histerese, sinais |
| `services/world_director.py` | Fases, orçamento, avisos, ciclo de crise (abrir, escalar, encerrar), `request_crisis_slot` |
| `services/location_states.py` | Leitura: `location_state`, `location_effects` (interior → pai); escolha de alvo; regras de recuperação |
| `services/faction_relations.py` | Matriz de relações, semente, deriva, cruzamentos; `faction_relation(state, a, b)`, `relation_label` |
| `services/world_perception.py` | `DigestItem`, filtro de percepção (R23), nomes (R24), render de template, gravação em `world.news` |
| `data/world/pressures.json` | Baselines por região, constantes, tabela de causas |
| `data/world/location_states.json` | Efeitos por estado e severidade, rótulo público, regras de recuperação |
| `data/world/signals.json` | Templates pt-BR por (tipo, pressão, severidade) com `visibility` |
| `docs/spec302/world_engine_sim.py` | Simulador de calibração (R33) |
| `docs/spec302/README.md` | Tabelas de calibração e evidência |
| `tests/test_spec302_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `agents/storyteller.py`:
  - guarda `day_before` antes de `apply_travel` (`:539`) e de `apply_rest`
    (`:591`) e chama `world_engine.advance_days(...)` depois;
  - com o modo `on`, remove as chamadas por período de `advance_factions`/
    `resolve_faction_completions` (`:540-543`, `:593-596`), que passam para o
    tick (R21b; corrige P7);
  - troca `simulate_world` (`:789-796`) pela narração do digest (R26);
  - devolve `world_sim` e `pending_world_events` (o motor anexa os seus) no dict
    parcial.
- `agents/world_simulator.py`: novo `WorldDayNarration` e `narrate_day(state,
  items) -> str`. O caminho legado (`simulate_world`, `WorldPulse`) fica só para
  o modo `off`.
- `mock_llm.py`: ramo `WorldDayNarration` (junto de `:636`).
- `services/structured_outputs.py`: `EventType` + `location_state_changed`,
  `world_crisis_warning`.
- `services/world_validators.py`: validadores dos tipos novos e barreira
  engine-only (R28).
- `services/event_processor.py` (`apply_event`):
  - `location_state_changed` → `proj["location_states"][target]` (estado vazio
    remove);
  - `world_crisis_warning` → sem efeito na projection;
  - `faction_relation_changed` com `relation="neutral"` → desativa arestas
    dinâmicas do par.
- `data/graph/relation_types.json`: `allied_with` (simétrico).
- `services/npc_knowledge.py`: `SUBJECT_PARAMS` (R27).
- `services/economy.py`: `price` (`:176-189`) e `restock` (`:263`) leem
  `location_effects`.
- `world_utils.py`: `_effective_danger` (`:606-616`) soma `danger_delta` com
  clamp; `ensure_world` cria `news` se faltar.
- `state.py`: `GameState.world_sim: WorldSimState`, `world_sim_shadow`;
  `WorldProjection.location_states`; `WorldState.news`.
- `api.py` (`_world_block`, `:2792-2836`): `location_state` (rótulo) e `news`
  (R31).
- `playtest/invariants.py`, `playtest/telemetry.py`, `playtest/report.py`,
  `playtest/__main__.py`: R32 + `--scenario mundo` (§4, Etapa 7).
- `tests/test_world_sim.py`, `tests/test_fase2.py`: os asserts de
  `danger_shift` e de `advance_factions` por período passam a valer só no modo
  `off`. O modo `on` ganha testes próprios. A mudança é intencional (D1) e fica
  documentada no commit.

### 3.3 Schemas (`state.py`)

```python
PressureKind = Literal["guerra", "fome", "praga", "abismo"]
Band = Literal["normal", "sinal", "crise"]
Phase = Literal["calmo", "tensao", "crise", "recuperacao"]
CrisisKind = Literal["guerra", "fome", "praga", "abismo", "ascensao"]
LocState = Literal["cerco", "escassez", "praga", "ocupado", "ruina", "festa", "corrompido"]


class CrisisRecord(TypedDict, total=False):
    crisis_id: str  # sha256(game_id|kind|region|warned_day)[:16]
    kind: CrisisKind
    region_id: str
    location_id: str  # alvo (R18); "" enquanto só anunciada
    loc_state: LocState
    faction_id: str  # atacante/ascendente, se houver
    warned_day: int
    start_day: int | None  # None = anunciada, ainda não aberta
    escalation_day: int | None
    severity: int  # 1..3
    end_day: int | None
    resolution: str  # "" | "recuperou" | "escalou" | "intervencao" | "expirou_aviso"


class WorldSignal(TypedDict):
    signal_id: str
    day: int
    region_id: str
    location_id: str
    pressure: PressureKind
    template_id: str
    visibility: Literal["local", "regional"]


class DigestItem(TypedDict, total=False):
    item_id: str
    day: int
    kind: Literal["sinal", "aviso", "crise", "escala", "fim", "relacao", "ascensao"]
    region_id: str
    location_id: str
    template_id: str
    params: dict[str, str]  # só ids; nomes resolvidos no render (R24)
    subject_id: str  # event_id quando há GameEvent (R23c)


class WorldSimState(TypedDict, total=False):
    version: int  # 1
    mode: str  # modo que gerou o estado
    enabled_from_day: int
    last_ticked_day: int
    last_event_seq: int  # índice no event_log já lido como causa
    pressures: dict[str, dict[str, int]]  # region_id -> kind -> 0..100
    bands: dict[str, dict[str, str]]  # region_id -> kind -> Band
    phase: str
    phase_since_day: int
    calm_until_day: int
    last_crisis_start_day: int
    region_last_crisis_end: dict[str, int]
    crises: list[CrisisRecord]  # ativas + anunciadas + últimas 30 encerradas
    faction_relations: dict[str, int]  # "a|b" (ordenado) -> -100..100
    relation_bands: dict[str, str]  # "a|b" -> "guerra"|"neutra"|"alianca"
    signals: list[WorldSignal]  # anel 60
    pending_digest: list[DigestItem]  # anel 20 (consumido pela percepção)
    tick_log: list[dict]  # anel 30 (telemetria/debug)


class LocationStateRow(TypedDict, total=False):  # em WorldProjection.location_states
    state: LocState
    severity: int
    since_day: int
    crisis_id: str
    cause: str  # CrisisKind
    faction_id: str


class NewsItem(TypedDict):  # WorldState.news (anel 12)
    day: int
    text: str  # render do template (nunca texto da LLM)
    channel: Literal["testemunho", "rumor"]
    item_id: str
```

Tamanho máximo estimado de `world_sim`: 12×4 pressões, 171 relações, anéis de
60/30/20/30. Fica abaixo de 30 KB, e um teste de teto garante isso.

### 3.4 Assinaturas públicas

```python
# services/world_engine.py
MODES = ("off", "shadow", "on")
def mode() -> str
def day_rng(game_id: str, day: int, salt: str) -> random.Random
def faction_region_id(faction: dict) -> str | None
def ensure_world_sim(state: dict, current_day: int) -> dict          # R29
def advance_days(state: dict, world_before: dict, world_after: dict,
                 factions: list, intel: dict) -> WorldTickResult
@dataclass(frozen=True)
class WorldTickResult:
    world: dict; factions: list; world_sim: dict
    pending_events: list[dict]      # propostas source="engine"
    digest: list[DigestItem]; days_ticked: int
DayHook = Callable[["DayContext"], "DayHookResult"]
def register_day_hook(name: str, fn: DayHook, *, stage: Literal["pre", "post"], order: int) -> None
def region_pressure(state: dict, region_id: str, kind: str) -> int   # leitura p/ specs consumidoras

# services/world_director.py
def request_crisis_slot(sim: dict, day: int, region_id: str, kind: str) -> bool
def announce(sim: dict, day: int, region_id: str, kind: str, rng) -> CrisisRecord | None
def step_crises(sim: dict, day: int, projection: dict, rng) -> tuple[dict, list[dict], list[DigestItem]]
def update_phase(sim: dict, day: int) -> dict

# services/location_states.py
def location_state(state: dict, location_id: str) -> LocationStateRow | None
def location_effects(state: dict, location_id: str) -> dict           # neutro se modo != on
def pick_target(region_id: str, kind: str, projection: dict, rng) -> str | None
def public_label(row: LocationStateRow | None) -> str                 # "sitiada", "em escassez"…

# services/faction_relations.py
def seed_relations(factions: list) -> dict[str, int]
def faction_relation(state: dict, a: str, b: str) -> int
def relation_label(value: int) -> Literal["guerra", "hostil", "neutra", "cordial", "alianca"]

# services/world_perception.py
def perceivable(state: dict, items: list[DigestItem]) -> list[DigestItem]
def render(state: dict, item: DigestItem) -> str
def record_news(world: dict, state: dict, items: list[DigestItem]) -> dict

# agents/world_simulator.py
class WorldDayNarration(BaseModel):
    text: str = Field(description="2-4 frases do que o personagem viu/ouviu; só os fatos dados.")
def narrate_day(state: dict, items: list[DigestItem]) -> str          # R26; nunca levanta
```

Ordem fixa do tick (`advance_days`, por dia `d`):

1. hooks `pre` (calendário entra aqui no futuro);
2. causas do `event_log[last_event_seq:]`;
3. pressões (R7–R8);
4. relações (R21);
5. progresso de fação (R21b);
6. bandas → sinais (R10) e avisos (R13);
7. diretor: abre, escala e encerra crises (R12, R14) e emite eventos;
8. recuperação de `ruina`/`ocupado` (R20);
9. hooks `post` (NPCs no futuro);
10. `update_phase`;
11. `tick_log`.

A projection usada entre os dias de uma mesma ação é uma **cópia local** com
`apply_event` aplicado aos eventos emitidos. A projection real só muda quando o
arquivista processa `pending_world_events` (`agents/archivist.py:301,403`). Como
o motor é determinístico, as duas convergem (teste).

### 3.5 Formatos de dados (exemplos com IDs reais)

`data/world/pressures.json`. Baselines **propostas** para revisão do dono (D6).
Todas ficam abaixo de `SINAL`, então o mundo nasce calmo.

```json
{
  "constants": {"SINAL": 40, "CRISE": 70, "RECUPERA": 35, "drift_per_day": 2, "noise": 3,
                "signal_delta": 6, "spread_threshold": 50, "spread_p": 0.5, "spread_factor": 0.08},
  "regions": {
    "nova_arcadia":       {"guerra": 20, "fome": 15, "praga": 10, "abismo": 10},
    "pantano_melancolia": {"guerra": 10, "fome": 20, "praga": 30, "abismo": 25},
    "deserto_zhur":       {"guerra": 20, "fome": 30, "praga": 5,  "abismo": 20},
    "floresta_sussurros": {"guerra": 5,  "fome": 10, "praga": 10, "abismo": 30},
    "selva_xylos":        {"guerra": 10, "fome": 10, "praga": 30, "abismo": 15},
    "skallgard":          {"guerra": 30, "fome": 25, "praga": 5,  "abismo": 20},
    "aethelgard":         {"guerra": 10, "fome": 15, "praga": 10, "abismo": 35},
    "ophidia":            {"guerra": 10, "fome": 10, "praga": 15, "abismo": 20},
    "costa_negra":        {"guerra": 25, "fome": 15, "praga": 10, "abismo": 10},
    "montanhas_afiadas":  {"guerra": 30, "fome": 20, "praga": 5,  "abismo": 10},
    "pradaria_ruinas":    {"guerra": 30, "fome": 20, "praga": 10, "abismo": 15},
    "brekmar":            {"guerra": 20, "fome": 10, "praga": 15, "abismo": 10}
  },
  "causes": [
    {"on_event": "route_blocked", "pressure": "fome", "delta": 8, "scope": "endpoint_regions"},
    {"on_event": "route_cleared", "pressure": "fome", "delta": -8, "scope": "endpoint_regions"},
    {"on_event": "location_control_changed", "if": "new_controller_hostile", "pressure": "guerra", "delta": 15, "scope": "target_region"},
    {"on_event": "npc_killed", "if": "target_leads_faction", "pressure": "guerra", "delta": 10, "scope": "faction_region"},
    {"per_day": "active_loc_state", "state": "cerco", "pressure": "fome", "delta": 3, "scope": "region"},
    {"per_day": "pressure_band", "pressure_src": "fome", "band": "crise", "pressure": "praga", "delta": 2, "scope": "region"},
    {"per_day": "looming_threat", "pressure": "abismo", "delta": 3, "scope": "threat_faction_region"},
    {"per_day": "faction_war_presence", "pressure": "guerra", "delta": 4, "scope": "shared_region"}
  ]
}
```

`data/world/location_states.json` (valores `[BALANCEAR]`):

```json
{
  "cerco":      {"label": "sitiada",       "price_mult": [1.5, 1.8, 2.2], "danger_delta": 1, "restock_mult": 0.5, "merchant_closed_at": 3, "blocks_route": true},
  "escassez":   {"label": "em escassez",   "price_mult": [1.3, 1.5, 1.8], "danger_delta": 0, "restock_mult": 0.5},
  "praga":      {"label": "tomada pela praga", "price_mult": [1.1, 1.2, 1.4], "danger_delta": 0, "restock_mult": 0.7},
  "ocupado":    {"label": "ocupada",       "price_mult": [1.2, 1.2, 1.2], "danger_delta": 1, "restock_mult": 0.8},
  "ruina":      {"label": "em ruínas",     "price_mult": [2.0, 2.0, 2.0], "danger_delta": 1, "restock_mult": 0.0, "merchant_closed_at": 1},
  "corrompido": {"label": "tocada pelo Abismo", "price_mult": [1.1, 1.2, 1.3], "danger_delta": 1, "restock_mult": 0.8},
  "festa":      {"label": "em festa",      "price_mult": [1.1, 1.1, 1.1], "danger_delta": 0, "restock_mult": 1.2}
}
```

Mapa crise → estado: `guerra` → `cerco`; `fome` → `escassez`; `praga` →
`praga`; `abismo` → `corrompido` (ou só sinal, se D2 = não); `ascensao` → o
efeito autorado em `data/factions.json` (`ascension`), sem estado de local
novo.

`data/world/signals.json` (trecho):

```json
{
  "fome.sinal.preco":      {"visibility": "regional", "text": "Os preços do pão subiram de novo em {local}; os mercadores falam em estradas vazias."},
  "guerra.sinal.patrulha": {"visibility": "regional", "text": "Patrulhas armadas cruzam a estrada com mais frequência que o normal."},
  "guerra.aviso.cerco":    {"visibility": "regional", "text": "Refugiados chegam de {local} dizendo que {faccao} acampa diante dos muros."},
  "praga.crise.inicio":    {"visibility": "local",    "text": "Portas marcadas com cal em {local}: a febre chegou."}
}
```

`{faccao}` vira o nome só se a fação for conhecida (R24); senão vira
"homens sem insígnia que ninguém sabe nomear".

### 3.6 Eventos novos (payload)

- `location_state_changed`: `target_id=<location_id>`, `payload={state: LocState
  | "", previous: str, severity: int, crisis_id: str, cause: CrisisKind,
  faction_id?: str}`, `source="engine"`.
- `world_crisis_warning`: `target_id=<location_id alvo provável ou o primeiro
  local da região>`, `payload={kind, region_id, crisis_id, earliest_day}`,
  `source="engine"`.
- `faction_relation_changed` (motor): `target_id=<faction a>`,
  `payload={other_faction_id, relation: "enemy_of"|"allied_with"|"neutral"}`,
  `source="engine"`.

### 3.7 `world.news` (contrato compartilhado com a SPEC-296)

Anel de 12 `NewsItem`, mais recente por último, gravado só por
`world_perception.record_news`. Vai para o contexto do narrador (as 3 últimas) e
para a API (R31).

## 4. Plano passo a passo

Marco **M1** = Etapas 0–4 (motor em `shadow`, pousável sozinho). Marco **M2** =
Etapas 5–8 (`on`, narração, calibração, letalidade). Cada marco tem `/spec-land`
próprio.

### Etapa 0 — Ownership e baseline

1. Consultar `project_index` (`state_ownership`) para os writers de `world`,
   `world_projection` e `factions`. Registrar no PR que `world_sim` tem dono
   único em `services/world_engine.py` e que `location_states` é escrito só por
   `event_processor.apply_event`.
2. Baseline: playtest `combate` seeds 21–32 × 200 (MockLLM), matriz SPEC-056 e
   `--all --turns 50`, com a contagem de dias por perfil. Guardar em
   `docs/spec302/README.md`.

### Etapa 1 — Tick diário, seed e migração

1. **Testes** (`tests/test_spec302_tick.py`):
   - `test_no_tick_when_day_unchanged`;
   - `test_one_tick_per_day_turned` (descanso que vira 1 dia → 1; viagem de 3
     períodos cruzando a noite → 1);
   - `test_multi_day_ticks_in_order`;
   - `test_idempotent_replay` (R2);
   - `test_cap_max_days_per_action` (R4);
   - `test_same_seed_same_world_sim` (R3);
   - `test_no_global_random_in_world_modules` (AST);
   - `test_legacy_save_without_world_sim_initializes_at_current_day` (R29: sem
     retroativo, calma inicial);
   - `test_save_load_roundtrip_world_sim`;
   - `test_world_sim_size_bound`;
   - `test_mode_off_is_legacy_path` (o storyteller chama `simulate_world`
     antigo).
2. **Implementação:** `world_engine.py` (modo, `day_rng`, `ensure_world_sim`,
   esqueleto de `advance_days` com hooks); integração no storyteller; `state.py`.

### Etapa 2 — Pressões

1. **Testes** (`tests/test_spec302_pressures.py`):
   - `test_drift_to_baseline`;
   - `test_cause_route_blocked_raises_fome_both_regions` (com evento real de
     `blocked_routes`);
   - `test_cause_applied_once_per_event` (`last_event_seq`);
   - `test_plague_spreads_only_to_adjacent_regions`;
   - `test_plague_does_not_cross_blocked_route`;
   - `test_hysteresis_no_repeat_events` (série sintética oscilando em 69/71/69);
   - `test_signal_cap_per_region_and_global` (R10);
   - `test_pressures_clamped`;
   - `test_region_adjacency_derived_from_map` (12 regiões, simétrica);
   - `test_independent_of_player` (R5).
2. **Implementação:** `world_pressures.py`, `data/world/pressures.json`,
   `data/world/signals.json`.

### Etapa 3 — Diretor de tensão

1. **Testes** (`tests/test_spec302_director.py`):
   - `test_initial_calm_blocks_announcements`;
   - `test_max_active_crises`;
   - `test_region_cooldown`;
   - `test_global_gap`;
   - `test_no_crisis_during_recuperacao`;
   - `test_crisis_requires_prior_warning_min_days` (R13);
   - `test_warning_then_open_after_delay`;
   - `test_crisis_ends_below_recupera_after_min_days`;
   - `test_escalation_on_escalation_day` (cerco sev 3 → ocupado com fação /
     ruína sem fação);
   - `test_phase_transitions`;
   - `test_request_crisis_slot_shared_budget` (slot externo consome o mesmo
     orçamento);
   - `test_tiebreak_deterministic`.
2. **Implementação:** `world_director.py`.

### Etapa 4 — Estados de local e eventos (fecha M1, em `shadow`)

1. **Testes** (`tests/test_spec302_location_states.py`):
   - `test_event_types_engine_only` (proposta LLM de `location_state_changed`/
     `world_crisis_warning` é rejeitada);
   - `test_apply_event_sets_and_clears_location_state`;
   - `test_interior_inherits_parent_state`;
   - `test_pick_target_never_interior` e `test_pick_target_by_tags`;
   - `test_every_engine_event_passes_validator` (120 dias × 10 seeds);
   - `test_local_projection_converges_with_archivist` (simula o motor e depois
     `process_pending_events`: mesma projection);
   - `test_siege_blocks_one_route_and_clears_on_end`;
   - `test_ruin_recovers_after_quiet_days`;
   - `test_occupation_ends_when_occupier_defeated`;
   - `test_shadow_mode_emits_nothing_and_writes_shadow_key`;
   - `test_npc_knowledge_subject_params_include_new_types`.
2. **Implementação:** `location_states.py`, `data/world/location_states.json`,
   validators/`apply_event`/`EventType`, `SUBJECT_PARAMS`.

### Etapa 5 — Efeitos e fações

1. **Testes** (`tests/test_spec302_effects_factions.py`):
   - `test_price_mult_from_location_state` (compra em `escassez` sev 2 = base ×
     1,5; neutro em `off`/`shadow`);
   - `test_restock_respects_state`;
   - `test_effective_danger_adds_delta_clamped` (SPEC-233: continua a fonte
     única; os testes da 233 seguem verdes);
   - `test_relations_seeded_from_enemy_edges` (`filhos_chama_azul|legiao_ferro`
     = −60);
   - `test_war_crossing_goes_through_director`;
   - `test_alliance_is_signal_not_crisis`;
   - `test_neutral_disables_dynamic_edge`;
   - `test_faction_progress_daily_and_ascension_gated` (D1: `progress=100` sem
     vaga não ascende e não perde progresso);
   - `test_ascension_warned_at_80`;
   - `test_faction_region_id_mapping` (19 fações → `region_id` válido).
2. **Implementação:** consumidores em `economy.py`/`world_utils.py`;
   `faction_relations.py`; `relation_types.json`; progresso de fação no tick.

### Etapa 6 — Percepção, notícias e narração

1. **Testes** (`tests/test_spec302_perception.py`):
   - `test_local_witness_only_current_location`;
   - `test_regional_visibility_rule`;
   - `test_far_crisis_invisible_without_propagation` (SPEC-215 `off`);
   - `test_far_crisis_heard_via_location_heard` (SPEC-215 `on`);
   - `test_unknown_faction_never_named_in_any_template` (varre todos os
     templates);
   - `test_news_ring_persists_template_text_not_llm`;
   - `test_narrator_called_at_most_once_and_only_when_day_turned` (contador no
     MockLLM);
   - `test_no_call_on_encounter_turn`;
   - `test_narrator_fallback_on_aimessage` (FallbackLLM → templates);
   - `test_narrator_rejects_unlisted_names`;
   - `test_no_llm_field_mutates_state` (nenhum `danger_shift`);
   - `test_api_world_block_has_label_and_news_only` (R31: sem `pressures`/
     `world_sim`/`severity`).
2. **Implementação:** `world_perception.py`, `narrate_day`, ramo no MockLLM,
   `_world_block`.

### Etapa 7 — Playtest e calibração

1. **Testes:**
   - `tests/test_spec302_playtest.py`: `test_invariants_detect_cap_and_unwarned`
     (estado sintético); `test_report_has_world_section`; `test_scenario_mundo_
     forces_crisis_within_5_days` (oráculo: aviso → crise → `location_state` no
     local da região inicial, MockLLM);
   - `tests/test_spec302_calibration.py` (rápido, 30 dias × 3 seeds): C3 e C5
     sempre valem.
2. **Implementação:** invariantes, telemetria e relatório (R32);
   `--scenario mundo` (save com `nova_arcadia.guerra = 66` e aviso já emitido no
   dia 1); `docs/spec302/world_engine_sim.py`; ajustar `[BALANCEAR]` até fechar
   C1–C6 e registrar a tabela em `docs/spec302/README.md`.

### Etapa 8 — Letalidade e prova

1. Repetir as medições da Etapa 0 com `RPG_WORLD_ENGINE=on` (R34) e registrar
   antes/depois na §8.
2. Ruff nos arquivos tocados. Suíte completa (`-n auto`) 1× no pouso.

## 5. Critérios de aceite

- [x] R1–R5: tick por dia, idempotente, seeded, com teto, independente do herói
- [x] R6–R10: pressões com causas por tabela, contágio por adjacência,
      histerese, teto de sinais
- [x] R11–R15: fases, orçamento, aviso ≥ 2 dias antes de toda crise, ciclo com
      `escalation_day`, slot público
- [x] R16–R20: estados de local via `GameEvent` na projection, efeitos em
      preço/estoque/perigo/rota, recuperação de `ruina`/`ocupado`
- [x] R21/R21b: relações contínuas; progresso de fação diário com ascensão
      gateada (conforme D1)
- [x] R22–R27: percepção pela regra de ouro, nomes protegidos, `world.news` com
      texto de template, ≤ 1 chamada LLM por ação que vira dia, sem
      `danger_shift`
- [x] R28: tipos novos engine-only; todo evento do motor passa no validator
- [x] R29: saves antigos carregam e o mundo liga no próximo dia virado;
      round-trip ok
- [x] R30: `off` = caminho legado; `shadow` sem efeito; `on` completo
- [x] R31: a API não vaza pressões nem severidade
- [x] R32: invariantes, telemetria e seção "Mundo" com dias por perfil
- [x] R33: C1–C6 fechadas no simulador (tabela na §8 e em `docs/spec302/README.md`; C4 no pior seed = 62,5 %, média 34,5 %)
- [x] R34: M1/M2/M5 da SPEC-285 valem com `on` (0,505 / 43 / 0)
- [x] Guard de FallbackLLM no `WorldDayNarration` (isinstance + try)
- [x] `uv run pytest` verde (suíte completa offline; exceto 3 testes de índice gerado, que o `/spec-land` regenera)
- [x] Revisão independente Opus (`handoffs/SPEC-302-sol-review.md`) sem P0/P1
- [x] Smoke real (§6) executado e registrado

## 6. Smoke test com LLM real

Teto do dono: US$ 3/dia, só campanhas curtas. Pré-requisito: `RPG_WORLD_ENGINE=on`,
`RPG_NPC_KNOWLEDGE=on`, DeepSeek nas `ROUTES`.

1. `uv run python -m playtest run --scenario mundo --turns 20 --real --max-cost 0.40 --seed 21`.
   Asserta: `mock=False`; aviso e depois crise no transcrito; `location_state`
   na `/game/state`; ≤ 1 invoke de `WorldDayNarration` por ação que virou dia
   (telemetria `set_llm_telemetry_hook`); 0 violação `error`.
2. `uv run python -m playtest transcript <run_id>`: a narração diária não cita
   fação desconhecida nem fato fora do digest (leitura humana de 5 trechos).
   `world.news` tem texto de template.
3. `uv run python -m playtest run --profile explorador --turns 30 --real --max-cost 0.60 --seed 22`:
   dias decorridos, sinais percebidos e crises percebidas aparecem no `report`.
   Nenhum `structured_invalid` repetido do narrador.
4. Staging (depois do pouso, com o modo `shadow` primeiro): 1 sessão manual de
   ~10 ações com descanso. Conferir nos logs `world.tick` (`mode=shadow`), sem
   mudança visível. Depois do OK do dono, `on` e repetir.

Custo esperado: ≤ US$ 1,10 no total. Se algum passo estourar o teto, parar e
registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** `world_sim` ausente inicializa no dia atual, sem
  retroativo. `world_projection.location_states` ausente = `{}`. Sem bump de
  schema. `danger_overrides` legados continuam valendo e o `danger_delta` soma
  por cima com clamp.
- **MockLLM/FallbackLLM:** a narração cai nos templates. O motor não depende de
  LLM, então a suíte offline exercita tudo. O MockLLM esconde erro de campo do
  `WorldDayNarration`, e por isso o smoke §6 é obrigatório.
- **Quota/latência:** a contagem de chamadas **cai** em relação a hoje (P5:
  hoje é 1 por viagem/descanso sem encontro; depois, só quando vira dia e há algo
  percebido). O tick é Python puro, O(regiões + 171 relações + locais) por dia,
  com teto de 10 dias por ação.
- **Letalidade (SPEC-285):** `danger_delta` +1 em cerco/ocupado/ruína/corrompido
  pode tirar o descanso seguro do early game (`world_utils.py:594-603`, perigo ≤
  3). A mitigação é medir na Etapa 8 e, se preciso, zerar `danger_delta` em
  locais com tag `cidade`/`seguro` ou limitar crises com alvo `cidade` nos
  primeiros dias (sem ler o herói).
- **Machine of crises:** o risco principal do pedido do dono. Ele é coberto por
  R11–R13, pelo teto global e pelas metas C3/C4 no simulador. Se C1 e C4
  conflitarem, vale C4 ("comportar como um mundo") e o dono decide.
- **Progresso de fação (D1):** muda o ritmo das ascensões que os playtests
  atuais observam. Testes de `advance_factions` passam a valer só em `off`.
  Avaliar efeito em `looming_threat` (SPEC-289).
- **Concorrência/retry:** idempotência por `last_ticked_day` e
  `crisis_id`/`event_id` determinísticos. `test_turn_pipeline_concurrency` tem
  de seguir verde.
- **Onisciência:** `world_sim` é privado. A API ganha só rótulo e notícias. O
  vazamento preexistente de `danger_overrides` (P13) fica registrado.
- **Rollback:** `RPG_WORLD_ENGINE=off` volta ao caminho atual sem migração
  reversa (as chaves novas ficam inertes).

## 8. Evidência

### 8.1 Calibração C1–C6 (120 dias × 20 seeds, `docs/spec302/world_engine_sim.py`)

Tabela completa em `docs/spec302/README.md` (60 seeds, pós-revisão Sol; `ophidia`/`costa_negra` com peso 1,0, `brekmar` 2,5). C1 = 10 / 15 / 10 / 11,5 dias (`nova_arcadia` /
`brekmar` / `pradaria_ruinas` / `pantano_melancolia`); C2 = 1 dia; C3 e C5 = 100 %; C4 =
média 34,5 %, p90 47,5 %, pior seed 62,5 % (região máx. 27,5 %); C6 sem violações; 0 eventos do
motor rejeitados pelo validator.

### 8.2 Letalidade (R34), `combate`, MockLLM, 12 seeds (21–32) × 200 turnos

| Medida | `off` | `on` | Meta SPEC-285 |
|---|---|---|---|
| M1 mortes / combates iniciados | 98/197 = 0,497 | 101/200 = 0,505 | ≤ 0,564 |
| M2 mediana da 1ª queda (seeds 21–32) | 35 | 43 | ≥ 20 |
| M2 matriz SPEC-056 (5 classes × seeds 42/43 × 50 turnos) | 24 | 25,5 | ≥ 20 |
| M5 `combat.no_progress` | 0 | 0 | 0 |
| `--start-level 5` (seeds 21–23): mortes/combates | 25/34 = 0,735 | 17/27 = 0,630 | sem piora |

Observação: `off` e `on` divergem de trajetória porque o pulso legado consome o `random`
global do MockLLM; por isso a comparação usa 12 seeds, não 1.

### 8.3 Desvios da spec (decididos na implementação)

1. `pick_target` → **`pick_crisis_target`** (o teste de cutover SPEC-xxx proíbe o nome do motor antigo).
2. R7 ganha causa `surge` (surto seeded por região/dia, com `surge_weight`) e `crisis_relief_per_day`
   (resposta do mundo enquanto há crise ativa): sem elas a deriva+ruído nunca cruza `CRISE`.
   Ambos são dados em `pressures.json`.
3. R19: `_effective_danger(world, loc)` não recebe a projection; o motor escreve o cache derivado
   `world.location_danger_delta` (só no modo `on`). Locais com tag `seguro` têm `danger_delta` 0
   (mitigação R34). A fonte da verdade continua `world_projection.location_states`.
4. R21: ao cruzar −70 o `faction_relation_changed(enemy_of)` é emitido na hora e a pressão `guerra`
   da região ganha `WAR_BOOST`; o **cerco** (a crise) passa pelo diretor (aviso, vaga, teto).
5. R28: só `location_state_changed`/`world_crisis_warning` são engine-only; `faction_relation_changed`
   e `location_control_changed` continuam proponíveis (comportamento pré-existente).
6. R25: `NewsItem` segue o contrato da SPEC-296 (`day, period, location_id, location_name, text,
   source="world_engine", turn`), sem `channel`/`item_id`; `world_perception` usa
   `services.ambient.append_news` quando existe e um fallback idêntico antes do pouso da 296.
7. `_build_event` aceita `event_id` determinístico quando `source == "engine"` (R2).
8. Shadow mantém projection própria (`shadow_location_states`/`shadow_blocked_routes`) e não simula
   progresso de facção nem ascensão.
9. Tamanho de `world_sim` < 40 KB (medido 35,7 KB; a estimativa de 30 KB não considerou as 171
   relações).
10. C4 avaliado por média/p90 além do pior seed (pior seed 62,5 %). Por D4 (ritmo vence), não se
    reduziu a frequência.
11. D5: default do código = `on`; o staging deve exportar `RPG_WORLD_ENGINE=shadow` até o smoke §6.
12. Testes legados que dependem do pulso/progresso por período
    (`test_fase2::test_graph_rest_advances_factions`, `test_grounding_boundaries::..._canonical_only`)
    rodam com `RPG_WORLD_ENGINE=off`.
13. Smoke real §6 **não executado** (sem chave/orçamento neste ambiente): pendente.

## 9. Fatiamento recomendado (specs filhas)

Recomendação: **SPEC-302 = núcleo** (esta spec, dois marcos M1/M2) mais **três
specs filhas**, a reservar pelo coordenador. Todas dependem da 302 `done` (M2) e
usam só os pontos de extensão daqui.

- **302-B — Calendário e estações.**
  - Ano e estações com duração em dias (decisão do dono; não assumir a duração
    da campanha). Hook `pre` modifica pressões: inverno → `fome` em `skallgard`
    e `montanhas_afiadas` mais `route_blocked` dos passos de montanha; seca →
    `fome` em `deserto_zhur`.
  - Festas e datas: a lore quase não tem (P14). É preciso autorar a lista, por
    exemplo os aniversários do "Dia sem Sombra" (Era 5) e da fundação de Nova
    Arcádia / Pacto de Valerius (Era 6), e o dono aprova.
  - Festa = estado `festa` (sinal, não crise). Sem lua e sem dia de mercado.
- **302-C — Agenda de NPCs e morte off-screen.**
  - 40–60 NPCs simulados: os conhecidos pelo jogador mais os líderes (21 arestas
    `leads` em `data/graph/edges.json`) e NPCs-chave.
  - Agenda e viagem (hook `post`). Troca de lado por `member_of` via evento do
    motor.
  - Morte off-screen de qualquer um, inclusive companheiro afastado em local
    perigoso. Sempre com aviso (`world_crisis_warning`-like, ou pedido de ajuda)
    e janela para intervir. Usa `request_crisis_slot`.
  - Depende também da SPEC-300 (companheiros).
- **302-D — Quests de mundo com prazo.**
  - A crise anunciada ou aberta gera um gancho de quest com `deadline_day =
    escalation_day`; o `quest_log` ganha `deadline_day`/`fail_consequence`.
  - Falha = a escalada que o motor já decidiu.
  - Ações de contra-jogo dedicadas: romper cerco, levar suprimentos, conter a
    praga.

Alternativa, se o dono preferir menos specs: juntar 302-B e 302-D numa spec
"calendário e quests". 302-C fica separada por depender da SPEC-300 e mexer em
NPC (risco alto).

## 10. Decisões do dono

- **D1 — Progresso de fação no tick diário, com ascensão gateada pelo diretor
  (R21b).** Recomendado: **sim**. Hoje todas as fações saturam em 5–10 dias de
  jogo (P2), o que contradiz "~1 crise a cada 10–15 dias".
- **D2 — Crise de Abismo vira o estado `corrompido` (7º estado, fora da lista
  original).** Recomendado: **sim**. A alternativa é a crise de Abismo ser só
  sinal + perigo, sem estado visível.
- **D3 — Narração diária.** Opção (a), recomendada: chamada própria, que
  substitui o pulso atual com o mesmo custo ou menos e cai nos templates se
  falhar. Opção (b): injetar o resumo no prompt do storyteller, com 0 chamadas
  extras e mais carga no prompt.
- **D4 — Calibração.** Definição de "crise perceptível" (região atual ou
  adjacente, ou ouvida por rumor), `MAX_ACTIVE_CRISES = 2` e calma inicial de 5
  dias sem crise. Se C1 (frequência) e C4 (mundo não vira máquina de crises)
  conflitarem, qual vence (recomendado: C4).
- **D5 — Default de `RPG_WORLD_ENGINE`.** Recomendado: `on` local e na suíte;
  `shadow` no staging até o smoke §6; `on` no staging depois do OK.
- **D6 — Baselines por região (§3.5).** Revisão de coerência com a lore.
- **D7 — Fatiamento da §9.** Reservar 302-B/C/D (ou a alternativa de 2 specs).


## Decisões do dono (2026-10-23)

Todas as decisões abertas desta spec seguem o **default recomendado pelo autor**, exceto/explicitando:

- D1: sim — progresso de fação no tick diário; ascensão consome vaga do diretor.
- D4 (substitui a recomendação): RITMO DE CRISE VENCE — garantir a cadência C1 (~1 crise perceptível a cada 10-15 dias por região frequentada); o teto de crises SIMULTÂNEAS continua valendo.
- D7: filhas reservadas — calendário/estações, agenda e morte off-screen de NPCs, quests de mundo com prazo.
