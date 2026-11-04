# SPEC-384 — Poda que depende do dono: flags aposentáveis, reforços, combate sem tabuleiro, perfis portable/hosted, CLI, `set_deck`, aliases e métrica antiga

> **Status:** `approved` (04/11: dono decidiu D1–D9, ver "Decisões do dono"; cada D com a sua trava no §4)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de 03/11 (`docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md`
> §4.1 itens 2, 4 e 9 · §4.2 item 5 · §4.3 item 1 · §4.4 item 5 · §5 letras K, L, M e N · §6 W1–W8)
> **Depende de:** nenhum item depende de outro. Cada D tem a sua própria trava (ver §4, "Pode começar quando").
> Resumo: D1/D3 esperam a **SPEC-371** pousar (`config/flags.yaml`, `agents/combat.py`); D4 espera o
> smoke §6 real de **342–357/362** e a decisão de default `on`; D7 está **destravado** (a 368 pousou e a
> SPEC-376 exclui `set_deck`); D8/D9 esperam a **SPEC-381** (`api.py` em routers). D1/D3 também esperam a
> SPEC-374 (W1 de 03/11: `config/flags.yaml`).
> **Desbloqueia:** nada obrigatório. A SPEC-378 já exclui as flags do D1 (`specs/SPEC-378-…md:199-201`).
> **Decisões do dono (04/11):** D1 = recomendação [R] (aposentar LORE_QUESTS, WORLD_QUESTS, RUMORS, CALENDAR, COMPANION_SOUL, NPC_TWO_PHASE, REPLAN_AFTER; reclassificar COMPANION_ROMANCE e NPC_SELF `kill_switch`, CONTEXT_PREFETCH `ops`; adiar WORLD_ENGINE e OPENING_THREAD) · D2 = recomendação [R] (9 → `on` em spec futura; ROUTER_DETERMINISTIC_NPC fica `shadow`; RUMORS_ADOPTED junto com RUMORS_PROPOSED) · D3 = **não** (dono quer a mecânica: código fica desligado e preservado; reforço no tabuleiro de cartas vira spec própria) · D4 = **apagar** o combate sem tabuleiro (dono, 04/11, contra a recomendação; só depois das travas G1–G4 e numa etapa própria, após a SPEC-382 Etapa 4) · D5 = manter · D6 = apagar o CLI (dono não joga no terminal) · D7/D8 (só `/art/player/confirm`)/D9 = apagar, **com prova de zero chamadores** (grep de produção + scripts + web no pré-voo; dono: "garanta que ninguém chama"; conferido pelo coordenador em 04/11: só testes próprios)
> **Revisão:** `handoffs/SPEC-384-independent-review.md` (CHANGES_REQUIRED, 03/11). Correções aplicadas;
> ver "Resposta à revisão" no fim.
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato conferido no source em 03/11 (arquivo:linha; números de linha de `api.py` e
`agents/combat.py` são aproximados (≈), porque esses arquivos estavam sendo editados por outras sessões
durante a leitura) · **[H]** hipótese ou estimativa a confirmar pelo executor · **[D]** decisão do dono
(pendente até ele marcar) · **[R]** recomendação desta spec.

---

## 0. Quadro de decisões (o dono preenche; o executor só executa linha marcada "sim")

| D | Item | Recomendação [R] | Raio medido [F] (produção · testes) | Decisão do dono |
|---|---|---|---|---|
| D1 | Aposentar flags `release` com default `on` (12) | **Aposentar 6** (LORE_QUESTS, WORLD_QUESTS, RUMORS, CALENDAR, COMPANION_SOUL, NPC_TWO_PHASE + REPLAN_AFTER = 7 nomes); **reclassificar 3** como `kill_switch`/`ops` (COMPANION_ROMANCE, NPC_SELF, CONTEXT_PREFETCH); **adiar 2** (WORLD_ENGINE por último, em lote próprio; OPENING_THREAD inelegível) | 2–14 arquivos de produção por flag; 1–57 arquivos de teste por flag (tabela §3.1) | por flag: ☐ aposentar ☐ reclassificar ☐ manter |
| D2 | 11 flags `release` com default `shadow` | só decidir (on / off / manter shadow); a execução vira spec própria | 0 nesta spec | por flag (tabela §3.2) |
| D3 | Apagar reforços de combate (`RPG_COMBAT_REINFORCEMENTS`) | **Apagar** a lógica de disparo (SPEC-325 R16); **preservar** as primitivas de cena (SPEC-272) e o encontro de mundo `reason="reinforcements"` | 1 arquivo apagado + 10 de produção/config + 3 do web + 1 doc · 1 teste apagado + 3 editados (+ 1 web) | ☐ sim ☐ não |
| D4 | Apagar o caminho de combate sem tabuleiro | **Não agora.** Só registrar as 4 travas (G1–G4); quando passarem, vira spec própria | ≈ 450 linhas em `agents/combat.py` + 4 sites em `api.py` + modo `shadow` de `card_piles`; 29 arquivos de teste citam `RPG_CARD_DECK` e quase toda a suíte de combate roda o caminho `off` por default (33 arquivos em 03/11, recontar) | ☐ registrar travas ☐ não |
| D5 | Perfis `portable` e `hosted` (S3 + OIDC) | **(a) manter.** Custo de manter é baixo, o adaptador S3 ganhou consumidor novo há uma semana (SPEC-352) e "estacionar" toca 11 arquivos de teste, não 5 | (c) estacionar: 2 arquivos apagados + 5 editados + extra `portable` · 11 arquivos de teste | ☐ (a) manter ☐ (b) fundir ☐ (c) estacionar |
| D6 | CLI `game_engine.py` | **Apagar**, se o dono não joga no terminal (o harness `playtest/` cobre o jogo sem interface; o CLI está defasado em cartas, cobrança e flags) | 1 arquivo apagado (477 l.) + 7 referências em docs/config · 1 arquivo de teste (2 testes) + 1 allowlist | ☐ apagar ☐ cliente fino ☐ manter |
| D7 | `services/cards.py::set_deck` (sem endpoint) | **Apagar** (promessa da SPEC-328 que a SPEC-334 não cumpriu; o balanço da arena pressupõe baralho inicial fixo) | 1 função (≈ 55 l.) · 2 arquivos de teste (5 testes) | ☐ apagar ☐ ligar (nova spec) |
| D8 | Aliases de rota | **Apagar só `/art/player/confirm`. Manter `/auth/logout`**: é o nome canônico (SPEC-220) e 3 scripts de staging usam | 1 decorador cada · `/art/player/confirm`: 3 testes · `/auth/logout`: 3 scripts de staging + 6 testes + 1 fixture e2e (+ build Android local, não versionado) | ☐ só art ☐ os dois ☐ nenhum |
| D9 | Métrica DEPRECATED `rpg_sse_first_event_seconds` | **Apagar** (nenhum painel nem alerta lê a métrica) | 2 arquivos de produção · 1 arquivo de teste (≈ 40 l.) | ☐ sim ☐ não |

---

## 1. Contexto & Objetivo

A auditoria de 03/11 separou o que dá para cortar sem perguntar (SPEC-375 a 383) do que só o dono pode
decidir: tirar uma alavanca de rollback, abandonar um perfil de deploy, apagar um cliente ou uma
função "para depois". Esta spec é o **cardápio** desses itens. Cada D é independente: tem evidência,
raio de impacto medido por grep, recomendação, plano, testes, trava W1 e aceite próprios. O executor
**só executa os D (e, no D1, as flags) que o dono marcar "sim" no §0**. Item não marcado fica como está,
e a spec pode fechar com itens recusados (ver §5).

O dono pediu "muito cuidado": outras sessões estão editando agora `config/flags.yaml` e `agents/combat.py`
(SPEC-371), `api.py` (367/368), `services/cards.py` (368). Por isso toda etapa começa pela trava **W1**
da auditoria (§6.2) e cada mudança mecânica sai num commit revertível sozinho (**W4**).

A verificação feita para esta spec **corrigiu a auditoria** em seis pontos (detalhe no §3):
1. **D3:** 3 dos 12 "ganchos" de reforço que a auditoria listou (`agents/storyteller.py`,
   `services/combat_origin.py`, `services/encounter_manifest.py`), mais `world_utils.py:1318`, são outra
   coisa: o **encontro de mundo** "o fugitivo voltou com reforços" (R10 de `check_encounter`). Esse fica.
   `state.py:99` é `ConflictScene.reinforcement_triggers`, primitiva mantida pela SPEC-272. Também fica.
2. **D1:** aposentar uma flag "folha" da cadeia (LORE_QUESTS → WORLD_QUESTS → WORLD_ENGINE) só apaga a
   leitura da env e o ramo `shadow`. O ramo `off` continua alcançável enquanto a flag-mãe puder ser
   `off`. O corte grande (o pulso legado `simulate_world`, `world_sim_shadow`) só sai com WORLD_ENGINE.
3. **D1:** `RPG_CONTEXT_PREFETCH` vale `off` **na suíte** (`services/context_prefetch.py:36`, com
   `RPG_FORCE_MOCK=1`). Aposentar a flag mudaria o comportamento de todos os testes. `RPG_OPENING_THREAD`
   pousou em 02/11 e o staging (`cc31a6c1`, 02/11, segundo `docs/spec364/achados-smoke4.md:5`; o
   `ESTADO_ATUAL` ainda diz `fae9a4e`) não tem `services/opening_threads.py`.
   Também `RPG_CALENDAR` não segue o padrão das outras folhas: com o motor em `shadow`, ele devolve `shadow`
   e grava `world_sim.calendar_shadow` (R1.5).
4. **D5:** o raio é de 11 arquivos de teste, não 5. O nome de perfil `hosted` é usado como "perfil
   endurecido genérico" em testes de boot e de log, e `tests/test_spec352_creature_portraits.py:438`
   exercita o `S3BlobStore` (prefixo `shared/` da SPEC-352, de 1 semana atrás).
5. **D8:** `/auth/logout` não é alias, é o nome canônico. O alias é `/auth/refresh/logout`
   (`docs/spec220/README.md:11`). Três scripts de staging usam o canônico.
6. **D9:** confirmado que nada lê a métrica: `observability/dashboards/valoria-local.json` e
   `observability/alerts/` têm 0 ocorrências.

## 2. Requisitos

### Regras comuns (valem para todo D executado)

- **R0.1 — Só item aprovado.** O executor não toca em nenhum D, nem em nenhuma flag do D1, sem "sim"
  do dono no §0, registrado pelo coordenador com data no cabeçalho desta spec (linha "Decisões do dono").
- **R0.2 — W1 revisada antes de cada etapa** (auditoria §6.2). A etapa só começa com a interseção vazia
  entre os arquivos dela (§3.3) e três fontes: (1) branches **vivas**, isto é, à frente da `main` e com
  commit nos últimos 7 dias; (2) mudanças não commitadas em todos os worktrees, inclusive o checkout
  principal; (3) arquivos de specs `in-progress` que trabalham direto na `main`
  (`git log --since=2.days --name-only main`). Branches paradas (ex.: `spec-214`, `spec-349-pre-sync`, que
  prendem `api.py` e `observability/metrics.py`) ficam fora e são listadas no hand-back para o dono
  arquivar. Interseção não vazia: a etapa espera, e as outras seguem.
- **R0.3 — W4: um commit por mudança mecânica.** D1 sai com um commit por flag. D3, D5, D6, D7, D8 e D9
  saem com um commit cada (D3 pode ter um segundo commit só para o web). Cada commit passa
  `uv run pytest` nos testes do escopo e é revertível com `git revert <sha>`.
- **R0.4 — Registro de flags consistente no mesmo commit.** Quem apaga a leitura `RPG_X` do código
  apaga ou reclassifica a entrada em `config/flags.yaml` no mesmo commit, e `tests/test_flag_registry.py`
  continua verde. Atenção: o gate varre todo `.py` versionado fora de `tests/`, mais
  `scripts/staging/staging_flags.json` e `.env.example` (`scripts/flag_registry.py:27-38`). Menção que
  sobrar em script, docstring ou `docs/**/*.py` conta como "flag sem registro".
- **R0.5 — Saves antigos carregam.** Nenhum D muda o formato do save. Campo de save que perder o escritor
  (ex.: `world_sim_shadow`, `world_sim.calendar_shadow`, `combat_meta["reinforcement"]` de combate ativo)
  continua aceito na carga: é ignorado ou preservado, nunca vira erro.
- **R0.6 — W2 onde o default não muda.** D1 e D3 não mudam o caminho default. Antes e depois de cada
  lote, o oráculo W2 dá igual: 12 suítes de eval `--seed 7` sem diff; `playtest run --all --turns 10
  --seed 0` com a mesma contagem de violações e o mesmo desfecho por perfil; e
  `tests/test_spec360_flags_off.py::test_golden_flags_off_byte_identico` verde. Esse golden roda 30 turnos
  do `explorador` com os defaults de hoje, portanto com o mundo vivo `on`.
- **R0.7 — W3.** Teste que só exercita o ramo removido (`off`/`shadow` da flag aposentada) é apagado, e
  o commit lista quais. Teste que usa o ramo removido **por conveniência**, para outra asserção (ex.:
  `tests/test_spec360_caca.py:15` põe `RPG_WORLD_ENGINE=off` porque "o sim do teste não é um sim do
  motor"), precisa ser reescrito. Isso torna a etapa **não pura**: o executor registra no hand-back e
  o revisor confere a asserção nova.
- **R0.8 — §6 após cada lote que muda flag no ambiente.** D1 e D3: deploy no staging + smokes (§6) antes
  de o próximo lote começar.
- **R0.9 — W7.** Revisão independente (`spec-reviewer`, Opus) por D. O revisor roda o W2 de novo em pelo
  menos 1 flag do D1.

### D1 — Aposentar flags `release` com default `on`

- **R1.1** — [F] As 12 flags com `kind: release` e `default: "on"` em `config/flags.yaml` são exatamente:
  `RPG_CALENDAR`:119, `RPG_COMPANION_ROMANCE`:200, `RPG_COMPANION_SOUL`:206, `RPG_CONTEXT_PREFETCH`:222,
  `RPG_LORE_QUESTS`:600, `RPG_NPC_SELF`:632, `RPG_NPC_TWO_PHASE`:638, `RPG_REPLAN_AFTER`:792,
  `RPG_RUMORS`:825, `RPG_OPENING_THREAD`:900, `RPG_WORLD_ENGINE`:1109, `RPG_WORLD_QUESTS`:1115.
  Todas vencem em 25/01/2027. No staging, nenhuma está `off`: `RPG_RUMORS`/`RPG_LORE_QUESTS` estão
  explícitas `on` (`scripts/staging/staging_flags.json:13-14`), `world_engine: "on"` (:7) é sempre
  enviada (`scripts/staging/vercel_env.py:300`), e as outras ficam ausentes. As que estão em
  `OPTIONAL_FLAGS` (`vercel_env.py:67-111`) são apagadas do projeto quando não estão no preset, e o
  código cai no default `on`.
- **R1.2 — Critério de elegibilidade** (o executor confere e registra por flag antes de pedir o commit):
  (a) `on` no staging há ≥ 7 dias, com data conferida por `git log -S` no default do código e pelo
  `_updated` do preset. O SHA do staging é o do último deploy registrado (Vercel ou handoff do smoke
  mais recente), e o executor o confere antes de cada lote. Em 03/11 era `cc31a6c1`, e o `ESTADO_ATUAL`
  estava atrasado; (b) coberta por um smoke real verde **no deploy atual do staging**, porque o staging
  tem pouco tráfego e "7 dias sem incidente" sozinho é evidência fraca; (c) nenhum bug aberto citando a flag
  em `ESTADO_ATUAL.md`, `CHANGELOG.md` dos últimos 7 dias ou spec `in-progress`/`approved`; (d) nenhuma spec
  em voo dependendo do modo `off`/`shadow` (grep `specs/` por `RPG_X`; em 03/11 só a SPEC-361:757 cita
  `RPG_OPENING_THREAD`, e só como registro de rebase). Flag que falha um critério não é aposentada.
- **R1.3 — Aposentar** = a leitura da env sai e o comportamento fica igual ao `on` de hoje. A função
  `mode()`/`*_on()` vira constante ou some, com os chamadores simplificados. Exceção: função que é alvo de
  `monkeypatch.setattr` em teste fica como função que devolve a constante. Exemplo:
  `latency_flags.two_phase_on`/`replan_after_on`, alvos de `tests/test_spec363_latency.py:79-80`, viram
  funções que devolvem `True`; se o executor preferir apagá-las, ajusta o teste no mesmo commit. O ramo
  `shadow` é apagado; o
  ramo `off` só é apagado quando ficar inalcançável, ou seja, quando nenhuma flag-mãe ainda puder desligá-lo
  (ver R1.5). A entrada some de `config/flags.yaml` e as menções somem de `vercel_env.py` (`OPTIONAL_FLAGS`,
  `WORLD_FLAGS`, `WORLD_FLAG_VALUES`), `staging_flags.json` e `.env.example`.
- **R1.4 — Nome que hoje existe no projeto Vercel** (`RPG_RUMORS`, `RPG_LORE_QUESTS`, `RPG_WORLD_ENGINE`)
  vai para `REMOVED_NAMES` (`vercel_env.py:62`), para o próximo deploy apagá-lo. Isso é necessário porque
  o upsert não apaga variável. Para o gate R0.4 continuar verde, a entrada no registro vira
  `kind: dev`, com `note: "aposentada (SPEC-384); só listada em REMOVED_NAMES até o deploy seguinte"`.
  Depois de 1 deploy verde, um commit de limpeza tira o nome dos dois lugares.
- **R1.5 — Ordem da cadeia.** [F] `lore_quests.mode()` só vale com `world_quests.mode()=="on"`
  (`services/lore_quests.py:53-59`), que só vale com `world_engine.mode()=="on"`
  (`services/world_quests.py:70-76`). `rumors` (`services/rumors.py:35-43`), `world_calendar`
  (`services/world_calendar.py:36-47`) e `npc_world` (`services/npc_world.py:53`) também dependem do motor.
  A ordem é das folhas para a raiz: LORE_QUESTS → WORLD_QUESTS → RUMORS → CALENDAR → (WORLD_ENGINE, em
  lote próprio e por último). Ao aposentar uma folha, a dependência da mãe **permanece** do jeito que é
  hoje:
  - LORE_QUESTS, WORLD_QUESTS e RUMORS já rebaixam para `off` quando a mãe não está `on`. Para elas,
    `mode()` passa a devolver `"on" if mae.mode()=="on" else "off"`;
  - **CALENDAR é diferente** [F]: `services/world_calendar.py:36-47` devolve `shadow` quando o motor está
    `shadow` e grava `world_sim.calendar_shadow` (`tests/test_spec303_hook.py:113-117`). Ao aposentar,
    `mode()` passa a devolver `world_engine.mode()` (repassa `off`/`shadow`/`on`), e não a fórmula acima.
    O motor em `shadow` ainda é o que `vercel_env.py` envia com `--no-preset` (≈266/530).
- **R1.6 — Reclassificar** (alternativa a aposentar, para alavanca que vale a pena manter): `kind` muda
  para `kill_switch` (desligamento de emergência) ou `ops` (ajuste operacional), sem `expires`. O ramo
  `shadow`, se houver, é apagado. O ramo `off` fica. É 1 commit por flag.
- **R1.7 — Recomendação por flag** [R] (tabela §3.1): aposentar LORE_QUESTS, WORLD_QUESTS, RUMORS,
  CALENDAR, COMPANION_SOUL, NPC_TWO_PHASE e REPLAN_AFTER; reclassificar COMPANION_ROMANCE (`kill_switch`:
  alavanca de conteúdo e classificação etária para a loja), NPC_SELF (`kill_switch`: apagar ganha ≈ 5
  linhas) e CONTEXT_PREFETCH (`ops`: botão de concorrência, como `RPG_CONTEXT_MAX_CONCURRENCY`, e a suíte
  depende do `off`); adiar WORLD_ENGINE (lote próprio, depois das quatro folhas) e OPENING_THREAD
  (inelegível por R1.2a).

### D2 — Decidir as 11 flags `release` com default `shadow`

- **R2.1** — [F] Lista exata (`config/flags.yaml`): `RPG_CHASE_ABANDON`:137, `RPG_CHASE_APPROACH`:143,
  `RPG_CHASE_ATTACK`:149, `RPG_COMBAT_NONLETHAL`:170, `RPG_COMBAT_OBJECTS`:176,
  `RPG_COMBAT_REVEAL_RESIST`:188, `RPG_COMPANION_ORDERS`:194, `RPG_EARLY_NARRATIVE`:334,
  `RPG_ROUTER_DETERMINISTIC_NPC`:808, `RPG_RUMORS_ADOPTED`:831, `RPG_TOKEN_STREAM`:1048.
- **R2.2** — Esta spec **só registra a decisão** (on, off ou manter shadow) por flag, na tabela §3.2. A
  execução fica para uma spec própria: promover o default do código para `on` muda o caminho da suíte.
  Flag promovida a `on` entra no D1 de uma rodada futura, quando cumprir R1.2.

### D3 — Reforços de combate

- **R3.1** — [F] Decisão de abandono: `staging_flags.json:3` (`_updated`, 26/10: "reforços (D) abandonados
  pelo dono"). O default no código é `off` (`services/combat_flags.py:47`), e
  `tests/test_enemy_decks.py:311-316` já garante que nenhuma carta inimiga invoca reforço.
- **R3.2 — Apagar** a lógica de disparo da SPEC-325 R16: `services/reinforcements.py` (224 l., segundo a
  auditoria; confirmar com `wc -l`); `agents/combat.py` `_plan_reinforcements` (≈383-405),
  `_advance_reinforcements` (≈408-435) e as duas chamadas (≈1080 e ≈2732); o bloco
  `reinforcement_warning` de `api.py` (≈3269-3276); o cap `"reinforcements"` de
  `services/combat_flags.py:26` e `:47`; os 4 eventos de `observability/events.py:151-154` e as linhas de
  `docs/operacao/EVENTOS_DE_LOG.md:117-120`; o cenário `combate_reforco` em `playtest/scenarios.py:44` e
  `:413`, `playtest/capability_bots.py:137` (`seed_reforco`), `:201` (`decide_aguarda_reforco`) e `:219`,
  `playtest/capabilities.py:34-36`; a checagem `conflict.golden_reinforcement` de
  `playtest/invariants.py:2912-2916` (fica vazia sem o aviso); o ramo `reinforce` de
  `docs/spec285/arena_lethality.py:249`; `RPG_COMBAT_REINFORCEMENTS` de `vercel_env.py:103,167` e de
  `config/flags.yaml:182-187`. Atenção [F]: sem o cap, `combat_flags.mode("reinforcements")` **não**
  levanta erro. Cap desconhecido cai em `_DEFAULT_MODE.get(cap, "shadow")` (`services/combat_flags.py:50-55`)
  e devolve `shadow` em silêncio. Por isso um teste garante que não sobra chamador (§4, Etapa D3).
  Efeitos derivados: `playtest/capabilities.py:39` deriva `KEYS` de `CAPS`; `tests/test_spec325_flags.py:9-10`
  conta 8 caps e 8 envs (passa a 7); `tests/test_spec325_playtest.py:38` confere o conjunto.
- **R3.3 — Preservar** (são outra coisa; teste de não-regressão no §4):
  - primitivas de cena mantidas pela SPEC-272 (tabela "(c) manter",
    `specs/SPEC-272-capacidades-conflito-so-testadas.md:122`): `conflict_scene.add_reinforcement_trigger`
    (`services/conflict_scene.py:436`), `fire_reinforcement` (`:445`), o efeito `spawn_reinforcement` em
    `EFFECT_KINDS` (`:30`) e `reinforcement_triggers` na cena (`:176`);
  - schema: `state.py:70` (`spawn_reinforcement` no catálogo) e `state.py:99`
    (`ConflictScene.reinforcement_triggers`). Saves com o campo continuam carregando;
  - normalização da cena preparada: `services/encounter_preparation.py:111, 225-231, 423`;
  - o **encontro de mundo** `reason="reinforcements"` (o fugitivo volta acompanhado): `world_utils.py:1310-1321`,
    `agents/storyteller.py:584` e `:1657`, `services/combat_origin.py:31`, `services/encounter_manifest.py:362`,
    testado por `tests/test_flee_alert_wiring.py:100-103`, `test_fase32.py:310`,
    `test_bug_mundo_perigo_luz_clima.py:99`, `test_spec299_hunters.py:89` e `test_melhorias_longrun_v2.py:90`;
  - `encounter_manifest.add_joined(..., "reinforcement", ...)`: o rótulo é genérico e a função tem outros usos;
  - `reforco_proprio` nas fichas do bestiário (`data/bestiario/fichas/*.yaml`) e em `padrao` de inimigo: é
    intenção do inimigo, outra coisa. **Não tocar.**
- **R3.4 — Web** (commit separado, com W1 próprio: `web/src/types.ts` está quente por 368/371): apagar
  `REINFORCEMENT_NOTE`/`reinforcementNote` (`web/src/combat/conflictChips.ts:11, 31-32`), o uso em
  `web/src/workspace/tabs/CombateTab.tsx:24, 356-357`, `reinforcement_warning` em `web/src/types.ts:425` e
  os casos em `web/tests/conflict-chips.test.mjs`. Essa parte fica nesta spec: a SPEC-383 a deixou de fora
  de propósito.

### D4 — Caminho de combate sem tabuleiro (gated)

- **R4.1** — Esta spec **não apaga** nada do D4. Ela só registra as travas. O corte vira spec própria
  quando **todas** passarem:
  - **G1** — smoke §6 real verde das specs de cartas 342–357 e 362, com cartas `on` no staging (passo 1 de
    "Próximos 3 passos" no `ESTADO_ATUAL.md`);
  - **G2** — decisão do dono de virar o default de `RPG_CARD_DECK` para `on` no código
    (`services/card_piles.py:80-82`; registro `config/flags.yaml:125-130`), seguida de ≥ 7 dias sem
    incidente (R1.2);
  - **G3** — o modo simulação de combate (`combat_simulation`, `is_simulation` em `agents/combat.py:≈2223`)
    migrado para o tabuleiro. Hoje ele força o caminho antigo mesmo com deck `on`:
    `opening_board = ... and not is_simulation` (≈2286) e
    `board_on = _deck_mode_now() == "on" and not is_simulation` (≈2803);
  - **G4** — suíte e playtest com deck `on` por default. [F] Hoje 33 arquivos de teste citam
    `RPG_CARD_DECK`, e o resto da suíte de combate (e os perfis de `playtest/`, que não setam a flag) roda o
    caminho `off`. `tests/fixtures/spec330_legacy_golden.json` + `tests/spec330_equivalence.py` são o golden
    do caminho legado e se aposentam junto (decisão explícita do dono, porque é um golden).
- **R4.2** — Quando G1–G4 passarem, o corte é: `_parse_turn_declaration` (`agents/combat.py:≈1177-1385`),
  `_narrate` por rodada (≈1716-1819), os ramos `if not board_on`/`elif player_dead and not is_simulation`
  (≈2803-2904), o modo `shadow` de `card_piles.mode()` (`services/card_piles.py:80-82`) e os 4 sites de
  `card_piles.mode()` em `api.py` (≈2456, 3248, 3263, 6062), que passam a assumir `on`.

### D5 — Perfis `portable` e `hosted` (S3 + OIDC)

- **R5.1** — [F] `infrastructure/runtime.py:225-226`: as tuplas de `portable` e `hosted` são idênticas.
  Os dois diferem só em `pooled` (:248), no endurecimento (:343-355, `HOSTED_PROFILES` :465) e na regra de
  exposição (:666-667). Nenhum deploy usa esses perfis: staging = `hosted-supabase`
  (`scripts/staging/vercel_env.py:40`), local = `local`. A SPEC-104 (Railway) está em espera. A auditoria
  de 18/10 pôs esses adaptadores em "Não podar" (`docs/auditorias/ponytail-poda-2026-10-18.md:72-73`:
  "perfil documentado e suportado (SPEC-181). Podar exige decisão de produto"), e a SPEC-181 R1 promete
  "sem mudar o significado atual de `portable`/`hosted` OIDC+S3".
- **R5.2 — Opção (a) manter** [R]: nada muda. A justificativa é registrada no cabeçalho.
- **R5.3 — Opção (b) fundir `portable` em `hosted`**: `portable` vira alias que levanta erro claro
  ("use `hosted`"). Muda `runtime.py:225, 314, 373, 666-667`, `infrastructure/postgres_shared_pool.py:3`
  (docstring) e `services/google_play_fake.py:3` (docstring). Testes: `test_boot_policy.py:311, 393-395`,
  `test_context_identity.py:31`, `test_hosted_supabase_contract.py:73-83`, `test_oidc_identity.py:165`,
  `test_runtime_profiles.py:39-41`, `test_spec194_native_backend.py:65`. O ganho é ≈ 10 linhas [H].
- **R5.4 — Opção (c) estacionar**: apagar `infrastructure/s3_blob.py` (69 l.) e
  `infrastructure/oidc_identity.py` (207 l.); tirar `portable` e `hosted` de `runtime.py` (:225-226, 248,
  314, 343-355, 373-383, 465, 666-667, 785-803, 816-824), deixando `RPG_BLOB_STORE=s3` e
  `RPG_AUTH_MODE=oidc` com erro claro; tirar `scripts/cloud_doctor.py:30-36, 49, 79, 91, 111`, o extra
  `portable = ["boto3"]` (`pyproject.toml:36` + `uv.lock`) e as 7 entradas `RPG_OIDC_*`/`RPG_S3_*` de
  `config/flags.yaml:650-669, 868-882`. **11 arquivos de teste**: `test_oidc_identity.py`,
  `test_s3_blob.py` (apagados); `test_runtime_profiles.py`, `test_hosted_supabase_contract.py`,
  `test_boot_policy.py`, `test_context_identity.py`, `test_spec194_native_backend.py`,
  `test_api_access_log.py:152`, `test_spec297_review_fixes.py:247`, `test_card_effects_piles.py:484`
  (usam `hosted` como perfil endurecido genérico e passariam a usar `hosted-supabase`) e
  `test_spec352_creature_portraits.py:438-442` (contrato do `shared/` sobre `S3BlobStore`: reescrever
  sobre outro BlobStore). Como `api.py:866` e `google_play_fake.py:26` testam `startswith("hosted")`,
  continuam certos. A volta seria recuperar do git quando a 104 voltar.
- **R5.5** — [R] Recomendo **(a)**. Manter custa pouco: ≈ 280 linhas isoladas, 1 extra opcional, testes
  baratos e sem rede. O risco de apodrecer existe, mas é medido pelos testes de contrato que já rodam. E
  (c) mexe em 11 arquivos de teste e no endurecimento de boot (código de segurança) para ganhar ≈ 350
  linhas. Se o dono quiser limpar, (b) é o meio-termo seguro.

### D6 — CLI `game_engine.py`

- **R6.1** — [F] `game_engine.py` (477 l.) é citado em `AGENTS.md:77, 261`, `README.md:38, 102`,
  `REFERENCE.md:13`, `main.py:179` (mensagem `print`), `ruff-baseline.toml:22`,
  `tests/test_no_print_in_production.py:4, 15` (allowlist), `docs/melhorias_workspace/02-linters-e-checks.md:14, 70`,
  `docs/spec223/README.md:14` e `docs/descricao_projeto/**` (guia interativo, `explore_01_nucleo.md`). Só é
  testado por `tests/test_bug_morte_checkpoint.py:339-387` (2 testes: ordem checkpoint→save e loop de morte
  do CLI). O mesmo arquivo já tem testes de API para checkpoint e morte (`:139, 164, 224`).
- **R6.2 — Apagar** [R]: apagar o arquivo e os 2 testes, tirar da allowlist e do `ruff-baseline.toml`,
  trocar a mensagem de `main.py:179` e as linhas de `README.md`/`REFERENCE.md`. A troca em `AGENTS.md` sai
  num parágrafo do hand-back para o coordenador aplicar: o arquivo é fonte única de instruções. O
  comportamento equivalente da API (checkpoint de morte) segue coberto por
  `tests/test_bug_morte_checkpoint.py:139, 164, 224`. As docs de `docs/descricao_projeto/**` ganham uma
  nota "removido (SPEC-384)"; o histórico fica como está.
- **R6.3 — Cliente fino** (alternativa): reescrever como cliente `httpx` de `/game/new` e `/game/action`
  (≈ 120-150 l. novas [H]), só para o perfil `legacy`, porque o hosted exige login e CSRF. [R] Não recomendo:
  é código novo para um uso que ninguém relatou.

### D7 — `services/cards.py::set_deck`

- **R7.1** — [F] `set_deck` (`services/cards.py:≈493`, depois do pouso da 368) não tem chamador de produção. A SPEC-328 deixou
  o endpoint para depois (`specs/SPEC-328-cartas-01-baralho-mao-folego.md:92`: "a UI/endpoint entra com a
  SPEC-334"), e a SPEC-334 não o incluiu. Testes: `tests/test_card_piles.py:299-324` (2) e
  `tests/test_forge.py:190-199, 349-351` (3; asseguram que a maldição de Cicatriz não sai do baralho
  **via `set_deck`**).
- **R7.2 — Apagar** [R]: apagar a função e os 5 testes. As constantes `DECK_MIN`/`DECK_MAX` só saem se
  ficarem sem uso (grep). Ligar o recurso (endpoint + UI de montar baralho) vira spec de feature própria,
  com rebalanço da arena: o piso de 45–85 % foi calibrado com o baralho inicial fixo.
- **R7.3** — Resolvido: a SPEC-376 exclui `set_deck` do escopo dela (`specs/SPEC-376-…md:42, 226, 244`).
  O D7 é o único dono do item.

### D8 — Aliases de rota

- **R8.1** — [F] `api.py:≈5053`: `/game/{id}/art/player/confirm` e `/game/{id}/art/confirm`
  apontam para o mesmo handler. O web usa só `/art/confirm` (`web/src/api.ts:432`). O build Android local
  (`web/android/app/src/main/assets/public/`, **não versionado**: `web/android/.gitignore:96`; build de
  15/10) não contém `art/player/confirm`. Testes que chamam o alias: `test_abuse_policy.py:45`,
  `test_api_fuzz_schemathesis.py:176`, `test_audit_browser_local.py:80`. Docs: `docs/spec188/README.md:20`
  e `docs/descricao_projeto/**`.
- **R8.2** — [F] `api.py:≈1274-1276`: `/auth/logout` é a rota **canônica**. `/auth/refresh/logout` é o
  alias da SPEC-220 R1 (o cookie de refresh tem path `/auth/refresh`), e o web usa o alias
  (`web/src/api.ts:68`). Usam o canônico: 3 scripts de staging (`scripts/staging/e2e_session.py:285`,
  `measure.py:74`, `two_user_smoke.py:206`), `web/e2e/fixtures.ts:301` e um build Android local **não
  versionado** (`index-CUkFp7vO.js`, de 15/10, que pode estar instalado em aparelho de teste). Também os testes `test_session_hardening.py` (8 chamadas),
  `test_http_cookie_flags.py:128`, `test_http_error_leakage.py:46`,
  `test_account_lifecycle_security.py:458` e `test_api_fuzz_schemathesis.py:185`.
- **R8.3** [R] — Apagar só o decorador `/art/player/confirm` e ajustar os 3 testes. **Manter
  `/auth/logout`**: apagar ganha 1 linha e quebra 3 scripts de staging (e um eventual build Android antigo).
- **R8.4** — Só **depois** da SPEC-381 pousar, nunca dentro dela: o oráculo da 381 é OpenAPI byte-igual, e
  rota removida quebraria esse oráculo. O executor regenera o snapshot de OpenAPI, se houver, no mesmo commit.

### D9 — Métrica `rpg_sse_first_event_seconds`

- **R9.1** — [F] A métrica é observada em `api.py:≈7139` e registrada em `observability/metrics.py:15-17`.
  A substituta `rpg_sse_ack_seconds` existe (:19). A SPEC-200 R7 manteve a métrica antiga "para não abrir
  buraco em séries", mas nenhum painel nem alerta a lê: `observability/dashboards/valoria-local.json` e
  `observability/alerts/*` têm 0 ocorrências, e a SPEC-200:23 já dizia isso. Teste:
  `tests/test_latency_metrics_compat.py:158-197`.
- **R9.2** — Apagar a observação e o registro, e ajustar o teste para afirmar que a métrica **não** aparece
  em `/metrics` e que `rpg_sse_ack_seconds` continua. Só depois da SPEC-381 (W1 em `api.py`).

### Fora de escopo

- Promover default de qualquer flag (D2 só decide). Ligar `RPG_PLOT_THREADS`, `RPG_FAUNA*` ou
  `RPG_CREATURE_GEN` (bloqueio do dono no ESTADO).
- Flags `release` com default não binário (`RPG_DAY_DIGEST`=`inline`, `RPG_CREATURE_GEN`=`legacy`,
  `RPG_LLM_HEDGE_MS`=`0`) e as `off` (cartas, lei, NPC_WORLD etc.).
- O corte do D4 (vira spec própria após G1–G4).
- Helper `services.env.env_choice` e unificação das funções `mode()` (SPEC-378).
- Primitivas da SPEC-272 "(c) manter", inclusive `add_reinforcement_trigger`/`fire_reinforcement`
  (auditoria §6.4: "não reabrir").
- Formato antigo de mensagem em `_deserialize_messages` (auditoria §4.1 item 9, resto): não é decisão do
  dono; fica para a SPEC-378.
- **`/game/map` vs `/data/map`** (passado para cá pela SPEC-381:202-203): **não se apaga nenhuma**. São
  rotas distintas, cada uma com consumidor vivo: o web usa `/game/map` (`web/src/api.ts:117`), e o
  `scripts/smoke_api.sh` e o legado usam `/data/map` (`api.py:≈4080`). Fica registrado para fechar o laço
  com a 381.
- Editar `ESTADO_ATUAL.md`, `ROADMAP.md`, `AGENTS.md`, `specs/index.yaml` ou `project_index/` (o
  executor devolve o texto no hand-back).

## 3. Design técnico

### 3.1 D1 — raio por flag (produção · testes) e recomendação

Contagem por grep em 03/11. As linhas andam com os pousos (368 já mudou várias), então o executor
reconta na Etapa 0. "Testes" = arquivos em `tests/` que citam o nome. "off/shadow" = arquivos
que setam a flag em `off`/`shadow` (são os que mudam, por R0.7).

| Flag | Default on desde [H] | Gates de produção [F] | Config [F] | Testes (off/shadow) [F] | [R] |
|---|---|---|---|---|---|
| `RPG_LORE_QUESTS` | 25/10 (preset) | `services/lore_quests.py:53-59` (mode); ramos `shadow` em `services/world_quests.py:428, 773, 836` | `vercel_env.py:82,148` · `staging_flags.json:14` · `.env.example:268` · `flags.yaml:600` | 2 (`spec313_helpers.py`; `test_spec192_vercel_env.py:241`) + `test_spec313_playtest.py:42-47` | aposentar (1º) |
| `RPG_WORLD_QUESTS` | 24/10 | `services/world_quests.py:70-76`; `agents/turn_finalizer.py:78` (`in ("on","shadow")`); `agents/storyteller.py:≈1038` | `vercel_env.py:77,143` · `.env.example:266` · `flags.yaml:1115` | 5 (4: `test_spec305_perception.py:171-175`, `test_spec305_review.py:135`, `test_spec311_planner.py:224`, `test_spec313_playtest.py:43`) | aposentar (2º) |
| `RPG_RUMORS` | 25/10 (preset) | `services/rumors.py:35-43`. `rumor_adoption.py:44` continua lendo `rumors.mode()` | `vercel_env.py:80,146` · `staging_flags.json:13` · `flags.yaml:825` · `docs/spec302/world_engine_sim.py:186-199, 302-309` | 9 (3: `test_spec312_birth.py:201-216`, `test_spec312_review.py:126`, `test_spec192_vercel_env.py:241`) | aposentar (3º) |
| `RPG_CALENDAR` | 24/10 | `services/world_calendar.py:36-47` (repassa o modo do motor, inclusive `shadow`, que grava `calendar_shadow`; R1.5); chamadores `api.py:≈3420, 3447`, `services/lore_query.py:141` | `flags.yaml:119` · `docs/spec302/world_engine_sim.py:186-199, 302-309, 356` (`--calendar off`: tirar a opção ou deixá-la como no-op, no mesmo commit) | 14 (6: `test_spec303_hook.py:95-118`, `test_spec303_perception_api.py:122`, `test_spec303_weather_encounters.py:56`, `test_spec307_display_api.py:72,103,192`, `test_spec311_lore_query.py:55`) | aposentar (4º) |
| `RPG_WORLD_ENGINE` | 24/10 | `services/world_engine.py:8-44` (`mode`, `sim_key`→`world_sim_shadow`) + 12 arquivos chamadores: `agents/storyteller.py:13, 850-854, ≈1810-1817` (pulso legado `simulate_world`), `world_utils.py:694`, `services/location_states.py:47`, `npc_self.py:216, 254`, `perceived_world.py:147`, `lore_query.py:171`, `fauna.py:443`, `npc_world.py:53`, `rumors.py:43`, `world_quests.py:76`, `world_calendar.py:42`; `agents/world_simulator.py:186` (`simulate_world`); `persistence.py`/`state.py` (`world_sim_shadow`, ler e ignorar) | `vercel_env.py:134-136, 300` + argumento `--world-engine` · `staging_flags.json:7` · `.env.example:259` · `flags.yaml:1109` | **57** (17 off/shadow: `test_ambient_consumers.py:73`, `test_fase2.py:173`, `test_grounding_boundaries.py:447`, `test_spec302_location_states.py:240`, `test_spec302_effects_factions.py:75`, `test_spec302_tick.py:137,147`, `test_spec302_review_fixes.py:77`, `test_spec303_hook.py:115-117`, `test_spec304_roster.py:113-116`, `test_spec305_perception.py:171`, `test_spec310_npc_self.py:391`, `test_spec311_lore_query.py:49-54`, `test_spec311_planner.py:223`, `test_spec311_price_reasons.py:383`, `test_spec312_birth.py:210`, `test_spec313_playtest.py:46`, `test_spec360_sinais.py:267`, `test_spec360_caca.py:15`) + `test_world_sim.py` (6 usos de `simulate_world`) | **adiar**: lote próprio, depois das 4 folhas; **não é puro** (R0.7) |
| `RPG_COMPANION_SOUL` | ≤ 24/10 | `services/companion_soul.py:73-75`; `agents/turn_finalizer.py:24`; `services/companion_prompt.py:327`; `api.py:≈2353, 2369`; `services/combat_flags.py:84-88` (`chase_abandon` desliga sem a alma) | `vercel_env.py:76,142` · `.env.example:255` · `flags.yaml:206` | 4 com o nome literal (`test_spec300_persistence_api.py:63,72`, `test_spec300_prompt.py:43,253`, `test_spec325_abandon_review.py:125`, `test_spec325_playtest.py:18`) | aposentar |
| `RPG_COMPANION_ROMANCE` | ≤ 24/10 | `services/companion_soul.py:78-79, 460, 475, 734`; `services/companion_prompt.py:105, 159, 252, 318` | `.env.example:256` · `flags.yaml:200` | 2 (`test_spec300_romance.py:72`, `test_spec300_prompt.py:153`) | **reclassificar `kill_switch`**: alavanca de conteúdo para a loja (SPEC-198) |
| `RPG_NPC_SELF` | ≤ 24/10 | `services/npc_self.py:12, 48-50, 440` (1 gate) | `vercel_env.py:79,145` · `.env.example:263` · `flags.yaml:632` | 6 (1 off: `test_spec310_npc_prompt.py:95`; os outros só `delenv`) | **reclassificar `kill_switch`** (o docstring já diz "kill switch"; apagar ganha ≈ 5 linhas) |
| `RPG_NPC_TWO_PHASE` | 26/10 (318) | `services/latency_flags.py:22-23`; `agents/archivist.py:457, 573`; `agents/enrich.py:232`; `agents/storyteller.py:≈2396`; `agents/npc.py:≈1400` | `vercel_env.py:91,154,179` · `flags.yaml:638` | 5 (todos `off`: `test_conflict_summary_lifecycle.py:489` "contrato legado da fila", `test_enrich_node.py:17`, `test_npc_two_phase.py:73,299`, `test_review_blockers_npc_preparation.py:318`) + `test_spec192_vercel_env.py:272,290` + `test_spec363_latency.py:79-80` (`monkeypatch.setattr` em `two_phase_on`/`replan_after_on`; R1.3) | aposentar; **não é puro** (3 testes usam `off` para outra asserção) |
| `RPG_REPLAN_AFTER` | 26/10 (318) | `services/latency_flags.py:26-27`; `agents/campaign_manager.py:246`; `agents/enrich.py:237`; `main.py:101-107` | `vercel_env.py:92,155,180` · `flags.yaml:792` | 3 (`test_enrich_node.py:18`, `test_replan_after_delivery.py:85,163`) + `test_spec192_vercel_env.py:273,290` | aposentar (junto com TWO_PHASE, commits separados) |
| `RPG_CONTEXT_PREFETCH` | — | `services/context_prefetch.py:31-36`: **`off` na suíte** (`RPG_FORCE_MOCK=1`) | `flags.yaml:222` | 1 (`test_context_prefetch.py:29,99`) | **reclassificar `ops`**. Aposentar ligaria o pool de threads em toda a suíte |
| `RPG_OPENING_THREAD` | 02/11 (main) | `services/opening_threads.py:50-51`; `services/prologue.py:162, 434`; `api.py:≈5474`; `scripts/smoke/spec351_opening.py:78, 110, 114` | `.env.example:245` · `flags.yaml:900` | 1 (`test_spec351_prologue.py:128,139,147`) | **inelegível** (R1.2a: o staging `cc31a6c1` não tem `services/opening_threads.py`) |

O ganho estimado em linhas não foi medido ramo a ramo [H]. A auditoria estima ≈ −300 para as 12 flags, e
a maior parte é WORLD_ENGINE (pulso legado + sombra).

### 3.2 D2 — as 11 flags `shadow` (decisão por flag)

| Flag | Staging [F] | Observação [F] | [R] | Dono |
|---|---|---|---|---|
| `RPG_CHASE_ABANDON` | `on` desde 26/10 (325 fase C) | efetiva só com `RPG_COMPANION_SOUL≠off` (`combat_flags.py:84-88`) | on | ☐ on ☐ off ☐ shadow |
| `RPG_CHASE_APPROACH` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_CHASE_ATTACK` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_COMBAT_NONLETHAL` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_COMBAT_OBJECTS` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_COMBAT_REVEAL_RESIST` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_COMPANION_ORDERS` | `on` 26/10 | — | on | ☐ ☐ ☐ |
| `RPG_EARLY_NARRATIVE` | `on` 25/10 (316) | latência | on | ☐ ☐ ☐ |
| `RPG_TOKEN_STREAM` | `on` 26/10 (319 D1) | `would_replace` 4 % < 5 % | on | ☐ ☐ ☐ |
| `RPG_ROUTER_DETERMINISTIC_NPC` | ausente = `shadow` | nunca ligada no staging | manter shadow até medir | ☐ ☐ ☐ |
| `RPG_RUMORS_ADOPTED` | ausente = `shadow` | **efetivamente `off`**: exige `RPG_RUMORS_PROPOSED=on` (`services/rumor_adoption.py:44`), que é `off` no default e no staging | decidir junto com `RPG_RUMORS_PROPOSED` | ☐ ☐ ☐ |

"on" = promover o default do código numa spec futura (muda o caminho da suíte; precisa de W2 com o novo
default como baseline). Depois de ≥ 7 dias, a flag entra no D1.

### 3.3 Arquivos por D (para a trava W1)

| D | Arquivos tocados |
|---|---|
| D1 (por flag) | os da linha da flag em §3.1 + `config/flags.yaml` + `scripts/staging/vercel_env.py` + `scripts/staging/staging_flags.json` + `.env.example` + `tests/test_spec192_vercel_env.py` · CALENDAR/RUMORS: + `docs/spec302/world_engine_sim.py` · TWO_PHASE/REPLAN: + `tests/test_spec363_latency.py` |
| D3 | `services/reinforcements.py` (apagado), `agents/combat.py`, `api.py`, `services/combat_flags.py`, `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `playtest/{scenarios,capability_bots,capabilities,invariants}.py`, `docs/spec285/arena_lethality.py`, `scripts/staging/vercel_env.py`, `config/flags.yaml`, `tests/test_spec325_{reinforcements,flags,playtest}.py` (flags `:9-10, 13, 57-60`; playtest `:38, 156`) · web: `web/src/combat/conflictChips.ts`, `web/src/workspace/tabs/CombateTab.tsx`, `web/src/types.ts`, `web/tests/conflict-chips.test.mjs` |
| D5 (c) | `infrastructure/{s3_blob,oidc_identity,runtime,postgres_shared_pool}.py`, `scripts/cloud_doctor.py`, `pyproject.toml`, `uv.lock`, `config/flags.yaml`, `.env.example`, 11 testes do R5.4 |
| D6 | `game_engine.py`, `main.py`, `README.md`, `REFERENCE.md`, `ruff-baseline.toml`, `tests/test_no_print_in_production.py`, `tests/test_bug_morte_checkpoint.py` |
| D7 | `services/cards.py`, `tests/test_card_piles.py`, `tests/test_forge.py` |
| D8 | `api.py` (ou o router de arte após a 381), `tests/test_abuse_policy.py`, `tests/test_api_fuzz_schemathesis.py`, `tests/test_audit_browser_local.py`, `docs/spec188/README.md` |
| D9 | `api.py` (ou `routes/turn.py` após a 381, onde SSE e pipeline do turno ficam juntos), `observability/metrics.py`, `tests/test_latency_metrics_compat.py` |

## 4. Plano passo a passo

Ordem sugerida depois das decisões: D3 → D1 (folhas) → D9 → D8 → D7 → D6 → D5 → D1 (WORLD_ENGINE). D2 e D4
não têm execução aqui. **W6:** um D em voo por vez, com no máximo 1 executor + 1 revisor.

### Etapa 0 — Pré-voo (toda etapa)

1. Ler o "sim" do dono no cabeçalho (R0.1). Sem "sim", pular o D.
2. W1 revisada (auditoria §6.2, R0.2): branches vivas + não commitado em todos os worktrees + commits de
   2 dias na `main`, contra a lista da etapa (§3.3). Se a interseção não for vazia, registrar "esperando
   <origem>" e seguir para outro D. Branches paradas excluídas vão listadas no hand-back.
3. Conferir o SHA atual do staging (R1.2a) e recontar as linhas citadas em §3.1/§3.3.
4. D1/D3: gravar o baseline W2 (evals A, playtest A) **antes** do primeiro commit do lote.

### Etapa D1.n — Aposentar/reclassificar uma flag (1 commit por flag)

Pode começar quando: SPEC-371 e SPEC-374 pousadas (`config/flags.yaml`) e R1.2 conferido para a flag.

1. **Testes primeiro:**
   - `tests/test_spec384_flags_aposentadas.py::test_flag_<x>_ignora_env` asserta que, com `RPG_X=off` (e
     `shadow`) no ambiente, o comportamento é o do `on` (mesmo retorno da função-porta pública). Para
     folha, asserta também que a dependência da mãe continua: com `RPG_WORLD_ENGINE=off`,
     `lore_quests.mode()=="off"`. Para CALENDAR: com `RPG_WORLD_ENGINE=shadow`, `world_calendar.mode()=="shadow"`
     e `calendar_shadow` ainda é gravado (`tests/test_spec303_hook.py:113-117` fica intacto).
   - `::test_flag_<x>_fora_do_registro` asserta que `RPG_X` não está em `config/flags.yaml`, ou está com
     `kind: dev`/`kill_switch`/`ops` conforme R1.4/R1.6, e que não aparece em `vercel_env.OPTIONAL_FLAGS`/`WORLD_FLAGS`.
   - Reclassificar: `::test_flag_<x>_kill_switch` asserta que `off` ainda desliga e que `shadow` vira o default.
2. **Implementação:** R1.3 a R1.6 para a flag. Apagar os testes que só exercitam o ramo removido, com a
   lista no corpo do commit. O corpo do commit também diz qual rollback documentado (§7) passa a ser
   `git revert`. Os testes "por conveniência" (R0.7) são reescritos e anotados como "não puro".
3. **Verificação:** testes da linha da flag em §3.1 + `tests/test_flag_registry.py` +
   `tests/test_spec192_vercel_env.py` + `tests/test_spec360_flags_off.py` (`-n 2` no máximo). No fim do
   lote: W2 (evals B, playtest B, comparação sem diff) e §6.

### Etapa D1.WE — `RPG_WORLD_ENGINE` (lote próprio, por último)

Pode começar quando: as 4 folhas estiverem aposentadas e pousadas, com §6 verde, e R1.2 conferido.

1. **Testes primeiro:** `test_world_engine_sem_modo` asserta que a env não muda nada e que
   `sim_key()=="world_sim"`. `test_save_com_world_sim_shadow_carrega` asserta que um save com
   `world_sim_shadow` carrega sem erro e que o campo é ignorado (fixture mínima nova em `tests/fixtures/`).
   `test_pulso_legado_removido` asserta que `agents.storyteller` não importa mais `simulate_world`.
2. **Implementação:** o ramo `off` de cada chamador em §3.1 vira o do `on`. Apagar `simulate_world`
   (`agents/world_simulator.py:186`), se não sobrar chamador (grep), e `world_sim_shadow` como destino de
   escrita. Remover `--world-engine`, `WORLD_ENGINE_MODES` e a chave `world_engine` do preset.
   Reescrever os 17 testes off/shadow (R0.7) e apagar `test_world_sim.py`, se ele só testa o pulso legado.
3. **Verificação:** como D1.n, mais revisão W7 com W2 rodado pelo revisor.

### Etapa D3 — Reforços

Pode começar quando: SPEC-371 pousada (`agents/combat.py`, `playtest/invariants.py`, `web/src/types.ts`) e
SPEC-374 pousada (`config/flags.yaml`).

1. **Testes primeiro** (`tests/test_spec384_reforcos.py`):
   - `test_modulo_reforcos_nao_existe`: `importlib.util.find_spec("services.reinforcements") is None`;
   - `test_combat_flags_sem_cap_reforco`: `"reinforcements" not in combat_flags.CAPS`;
   - `test_nenhum_chamador_de_cap_reforco`: varre os `.py` versionados fora de `tests/` (`git ls-files`) e
     falha se sobrar `mode("reinforcements")` ou `active("reinforcements")`. Isso é necessário porque o cap
     desconhecido cai em `shadow` em silêncio (R3.2);
   - `test_primitivas_de_cena_preservadas`: `cs.add_reinforcement_trigger`/`cs.fire_reinforcement` existem
     e `"spawn_reinforcement" in cs.EFFECT_KINDS` (o comportamento já é coberto por
     `tests/test_conflito_zonas.py:157-186`, que fica intacto);
   - `test_encontro_de_mundo_reforcos_preservado`: reaproveitar
     `tests/test_flee_alert_wiring.py:100-103` (fica intacto) e só referenciá-lo no aceite;
   - `test_payload_sem_reinforcement_warning`: com um `lider_matilha` a ≤ 50 % e `RPG_COMBAT_REINFORCEMENTS=on`
     no ambiente (env órfã), a resposta de combate não tem `reinforcement_warning` e não nasce inimigo `_r1`.
2. **Implementação:** R3.2 num commit; R3.4 (web) num segundo commit, com W1 próprio. Apagar
   `tests/test_spec325_reinforcements.py`. Editar `tests/test_spec325_flags.py:9-10` (8 → 7), `:13` e
   `:57-60`, e `tests/test_spec325_playtest.py:38` e `:156`. Se algum teste conferir o catálogo de eventos contra
   `EVENTOS_DE_LOG.md`, a doc é atualizada no mesmo commit.
3. **Verificação:** os testes acima + `tests/test_conflito_zonas.py`, `test_flee_alert_wiring.py`,
   `test_fase32.py`, `test_spec299_hunters.py`, `test_enemy_decks.py`, `test_spec325_*.py`,
   `test_flag_registry.py`; web `npm test` só de `conflict-chips`. W2 + §6.

### Etapa D5 — só se o dono escolher (b) ou (c)

1. **Testes primeiro:** (b) `test_portable_vira_erro_claro` (a mensagem cita `hosted`). (c)
   `test_perfis_estacionados_erro_claro` (`portable`/`hosted`/`RPG_BLOB_STORE=s3`/`RPG_AUTH_MODE=oidc` →
   `ValueError` com "SPEC-104"); `test_hosted_supabase_inalterado` (as tuplas de `hosted-supabase`,
   `local` e `legacy` continuam byte-iguais).
2. **Implementação:** R5.3 ou R5.4. Em (c), migrar os 9 testes que usam `hosted` como perfil genérico
   para `hosted-supabase`, conferindo que a asserção é a mesma (W3).
3. **Verificação:** os 11 arquivos de teste do R5.4 + `scripts/cloud_doctor.py --help` +
   `uv sync --all-extras` sem o extra `portable`.

### Etapa D6 — CLI

1. **Testes primeiro:** os testes de API de checkpoint e morte já existem
   (`tests/test_bug_morte_checkpoint.py:139, 164, 224`); rodá-los verdes antes de apagar.
2. **Implementação:** R6.2.
3. **Verificação:** `tests/test_bug_morte_checkpoint.py`, `tests/test_no_print_in_production.py`, `ruff check`.

### Etapa D7 — `set_deck`

Pode começar quando: já (368 pousada; a 376 exclui `set_deck`) e a W1 estiver limpa.

1. **Testes primeiro:** `test_set_deck_removido`: `not hasattr(cards, "set_deck")`.
2. **Implementação:** R7.2.
3. **Verificação:** `tests/test_card_piles.py`, `tests/test_forge.py`, `tests/test_mecanica_orfa.py`.

### Etapa D8 / D9 — rotas e métrica

Pode começar quando: SPEC-381 pousada e nenhuma branch tocando no router afetado.

1. **Testes primeiro:** D8 `test_alias_art_player_confirm_removido` (POST → 404/405) e
   `test_auth_logout_canonico_mantido` (204). D9 `test_metrica_sse_first_event_removida` (ausente em
   `/metrics`) e `test_sse_ack_mantida`.
2. **Implementação:** R8.3 e R9.2. Regenerar o snapshot de OpenAPI da 381, se houver (D8 muda rotas; D9 não).
3. **Verificação:** os testes citados em R8.1 e R9.1 + `tests/test_api_fuzz_schemathesis.py`.

## 5. Critérios de aceite

A spec vira `done` quando **cada D** estiver em um de três estados: executado com os critérios dele
marcados, recusado pelo dono, ou (D2/D4) com a decisão/travas registradas. O registro fica no cabeçalho,
com data.

- [ ] Decisões do dono registradas por D (e por flag no D1/D2) no cabeçalho
- [ ] D1: cada flag aposentada/reclassificada em commit próprio; R1.2 conferido e citado no corpo do
      commit; `test_flag_registry.py` verde; W2 sem diferença por lote; golden 360 byte-igual
- [ ] D1: nome antigo apagado do projeto Vercel (R1.4) e limpeza do `REMOVED_NAMES` feita depois de 1 deploy
- [ ] D2: tabela §3.2 preenchida
- [ ] D3: `services/reinforcements.py` apagado; primitivas da SPEC-272 e encontro de mundo
      `reason="reinforcements"` intactos (testes do §4 verdes); web sem `reinforcement_warning`
- [ ] D4: G1–G4 registradas; nada apagado
- [ ] D5: opção registrada; se (b)/(c), `hosted-supabase`/`local`/`legacy` byte-iguais
- [ ] D6/D7/D8/D9: conforme R6.2/R7.2/R8.3/R9.2, cada um em commit próprio
- [ ] Parágrafo para `AGENTS.md` (D6, D1 se mudar comandos) e para `ESTADO_ATUAL.md` entregue no hand-back
- [ ] `uv run pytest` verde (suíte completa, coordenador, 1×, no pouso)
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo)
- [ ] Saves antigos continuam carregando (R0.5; `test_save_com_world_sim_shadow_carrega` se D1.WE rodar)
- [ ] Revisão independente APPROVED por D (W7)

## 6. Smoke test com LLM real

Obrigatório depois de cada lote que muda o comportamento disponível no ambiente (D1, D3). D5–D9 não
mudam o jogo; para eles, o smoke é o item 4.

1. **Deploy** do staging com o lote (`/staging-deploy`, preset atual) e os 3 smokes do staging verdes.
2. **D1 (mundo vivo):** campanha real de ~10 turnos no staging que vire pelo menos 1 dia (descanso). No
   `/game/state`: `world_sim` preenchido, rótulo de estação no calendário, ≥ 1 rumor ouvido e ≥ 1 quest de
   mundo/lore oferecida no período; companheiro com rótulos de alma; 0 erro 5xx; 0 violação `error` no
   `rpg.turn`. Com `RPG_RUMORS=off` posto à mão no Vercel (env órfã), o comportamento continua igual.
3. **D3:** um combate real com `lider_matilha`, levado a ≤ 50 %: nenhum aviso "Passos se aproximam", nenhum
   inimigo `_r1`, 0 erro. E um encontro de mundo com fugitivo que volta continua com `reason="reinforcements"`.
4. **D5–D9:** boot do staging (`hosted-supabase`) e do local sem erro; logout pelo web; geração de
   retrato pelo `/art/confirm`; `/metrics` sem `rpg_sse_first_event_seconds` e com `rpg_sse_ack_seconds`.
5. Custo esperado: < US$ 0,02 por lote (DeepSeek), dentro dos tetos atuais do staging.

## 7. Riscos & compatibilidade

- **Perda do rollback (D1):** sem a flag, voltar ao comportamento antigo exige `git revert` + deploy, em
  vez de trocar a env. Por isso existem o critério R1.2, o lote pequeno e um commit por flag. A
  reclassificação (R1.6) existe para quem quiser manter a alavanca sem prazo. As specs `done` que
  documentam `RPG_X=off` como rollback são SPEC-302:865, 303:698, 305:625, 307:614 e 313:792. Nenhum
  runbook (`docs/spec197`, `docs/operacao`, `docs/guias`, `.github`, `.claude`) manda desligá-las. O
  commit de cada flag registra que aquele rollback passa a ser `git revert`.
- **Cadeia de flags (D1):** aposentar a mãe antes das folhas deixa folha sem efeito; aposentar a folha
  esperando apagar o `off` não apaga nada (R1.5). A ordem está fixada.
- **Suíte com defaults diferentes de produção:** `RPG_CONTEXT_PREFETCH` (off na suíte) e `RPG_CARD_DECK`
  (off no código, on no staging) fazem a suíte não exercitar o caminho de produção. É a razão de
  reclassificar a primeira e de travar o D4 em G4.
- **Conflito com outras sessões (W1):** `config/flags.yaml` (371), `agents/combat.py` (371), `api.py`
  (367/368, depois 381), `services/cards.py` (368), `web/src/types.ts` (368/371). Etapa com interseção
  espera; nada de "resolver no rebase".
- **SPEC-378 (`services.env.env_choice`):** já exclui as flags do D1 (`specs/SPEC-378-…md:199-201`); sem trabalho em dobro.
- **SPEC-376:** exclui `set_deck` (R7.3).
- **Cap desconhecido vira `shadow`** (`services/combat_flags.py:50-55`): um chamador de reforço que sobrar
  não quebra, só muda de ramo em silêncio. Por isso existe `test_nenhum_chamador_de_cap_reforco`. Fazer
  `mode()` levantar com cap desconhecido muda o contrato e fica fora daqui.
- **Saves:** nenhum D muda o formato. `world_sim_shadow` e `reinforcement_triggers` continuam aceitos na carga.
- **MockLLM/FallbackLLM:** nenhum nó novo; nenhum structured output novo.
- **Quota/latência:** D1 não muda chamadas de LLM no caminho `on`. A reclassificação de
  CONTEXT_PREFETCH mantém o comportamento atual.
- **Build Android local** (`web/android/app/src/main/assets/public/`, ignorado pelo git em
  `web/android/.gitignore:96`; build de 15/10) chama `/auth/logout`. [H] Pode haver aparelho de teste com
  esse build. O motivo principal para manter a rota são os 3 scripts de staging (R8.2).

## Resposta à revisão (`handoffs/SPEC-384-independent-review.md`, 03/11)

| Achado | Resposta |
|---|---|
| P1-1 calendário sob motor `shadow` | **Aceito.** R1.5 ganhou a exceção do CALENDAR: `mode()` repassa `world_engine.mode()`. `calendar_shadow` entrou na R0.5, e a Etapa D1.n ganhou o teste correspondente. |
| P1-2 SHA do staging | **Aceito.** Os fatos agora citam `cc31a6c1` (`docs/spec364/achados-smoke4.md:5`), e o R1.2a manda conferir o SHA real antes de cada lote. A conclusão sobre OPENING_THREAD não muda. |
| P1-3 bundle Android não versionado | **Aceito.** A evidência foi reescrita (build local, `.gitignore:96`) e passou a citar 3 scripts de staging, incluindo `e2e_session.py:285`. A decisão de manter `/auth/logout` não muda. |
| P2-1 `test_spec363_latency.py:79-80` | **Aceito.** Entrou na R1.3 (funções viram constante, não somem) e na linha TWO_PHASE/REPLAN do §3.1/§3.3. |
| P2-2 `docs/spec302/world_engine_sim.py` | **Aceito.** Entrou no §3.1 (CALENDAR/RUMORS) e no §3.3, com a decisão de tirar a opção ou deixá-la como no-op no mesmo commit. |
| P2-3 `test_spec325_flags.py:9-10`, `capabilities.py:39`, `test_spec325_playtest.py:38` | **Aceito.** Entraram em R3.2, §3.3 e na Etapa D3. |
| P2-4 cap desconhecido → `shadow` | **Aceito.** O texto do `KeyError` foi corrigido e entrou `test_nenhum_chamador_de_cap_reforco`. Mudar `mode()` para levantar foi **rejeitado** aqui: muda o contrato de `combat_flags`, que tem outros chamadores. Se o dono quiser, vira item próprio. |
| P2-5 branches mortas na W1 | **Aceito**, pela W1 revisada da auditoria (branches vivas em 7 dias + worktrees + `main`), em R0.2 e na Etapa 0. Arquivar `spec-214`/`spec-349-pre-sync` fica com o coordenador e o dono (fora desta spec). |
| P2-6 docs do CLI | **Aceito.** Entraram no R6.1; a Etapa D6 usa os testes de API já existentes (`:139, 164, 224`). |
| P2-7 `/game/map` vs `/data/map` | **Aceito.** Registrado em "Fora de escopo": as duas rotas ficam, porque cada uma tem consumidor. |
| P2-8 rollbacks documentados | **Aceito.** As linhas foram citadas no §7, e o corpo de cada commit do D1 anota a troca por `git revert`. |
| P2-9 contagens/linhas | **Aceito.** COMPANION_SOUL = 4, NPC_SELF = 6, CARD_DECK = 33, e as linhas foram atualizadas (`cards.py:≈493`, `api.py:≈5053/≈7139`). A Etapa 0 manda recontar. |

## Execução (04/11, executor Sonnet)

Provas de zero chamadores = grep em toda a árvore (produção, scripts/, web/src, playtest/, config, workflows, `.env.example`), excluindo só `specs/`, `docs/`, `handoffs/` (histórico).

- **D7 `set_deck`** — grep `set_deck`: 0 ocorrências fora de `services/cards.py` (definição) e dos 5 testes próprios. Apagados: `services/cards.py::set_deck`; `tests/test_card_piles.py::test_set_deck_valida_tamanho_copias_e_acervo`, `::test_set_deck_recusa_em_combate` (+ helper `_state`, usado só por eles); `tests/test_forge.py::test_maldicao_da_cicatriz_nao_se_esquece_nem_sai_do_baralho_por_set_deck`; e o trecho final de `test_purgar_tambem_limpa_prepared_cards` (3 linhas que só exercitavam `set_deck`; asserções anteriores intactas). `DECK_MIN/DECK_MAX` e `_DECK_TIPOS/_COMMON_PATAMARES` ficam (usados por `api_presenters`, `card_piles`, `card_rewards`, `scripts/cards/sim.py`). Novo: `test_set_deck_removido`.
- **D6 `game_engine.py`** — grep `game_engine` (fora de `docs/`, `specs/`, `handoffs/`, `CHANGELOG`, `uv.lock`): nenhum import nem invocação em produção, `scripts/`, `playtest/`, `web/`, workflows, `Procfile`, `vercel.json`. Só referências textuais, ajustadas: `main.py:179` (mensagem), `README.md`, `REFERENCE.md`, `ruff-baseline.toml`, `pyproject.toml` (`[tool.coverage] source`), `tests/size_budget.json` (2 entradas), `tests/test_no_print_in_production.py` (allowlist). Testes apagados: `tests/test_bug_morte_checkpoint.py::test_cli_persist_turn_checkpoint_before_save`, `::test_cli_resumed_death_pending_opens_death_flow`. `AGENTS.md:77-78, 261` fica para o coordenador (fonte única). Notas "removido" em `docs/descricao_projeto/**` não aplicadas (histórico).
