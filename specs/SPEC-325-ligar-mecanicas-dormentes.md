# SPEC-325 — Ligar as mecânicas de conflito dormentes (fuga com escolhas, golpe não-letal, resistência revelada, objetos de cena, ordens a companheiro, reforços)

> **Status:** `in-progress` (aprovada 25/10; Fase A implementada + revisão Sol aplicada + gate R17 verde; pousada na main 26/10 com flags `shadow`; Fase B revisada + gate R17 verde; Fases C e D implementadas em `shadow` na branch `spec-325` 26/10, sem revisão nem gate)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-26
> **Progresso:** Fase A (R8, R9) pousada em `shadow`. Fase B (R10–R13: abordagem, ataque na fuga, abandono, sacrifício) implementada em `shadow` (26/10); revisão Sol e gate R17 da Fase B pendentes: comandos prontos em §8.2, **ainda não rodados** (coordenador). Fase C (R14 objetos de cena, R15 ordem a companheiro) implementada em `shadow` (26/10); revisão Sol e gate R17 da Fase C pendentes: comandos prontos em §8.3, **ainda não rodados** (coordenador). Fase D (R16 reforço de `lider_matilha`) implementada em `shadow` (26/10); revisão Sol e gate R17 da Fase D (com a célula `lider_matilha` da arena e D5) pendentes: comandos em §8.4, **ainda não rodados** (coordenador). Etapa 8 pendente (ver §9).
> **Origem:** auditoria de regressão de 25/10, "capacidades sem chamador", itens 5 a 8; SPEC-272 §9 (decisão "manter, não ligar")
> **Depende de:** SPEC-064, SPEC-068, SPEC-069, SPEC-070, SPEC-226, SPEC-272, SPEC-285, SPEC-300, SPEC-304 (todas `done`)
> **Desbloqueia:** prisioneiros (consumidor de `law.deliver_prisoner`, SPEC-299 R23); follow-up 299 "derrota → prisão"; follow-up SPEC-226:165 (id único de reforço)
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma fase por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (motor de conflito, letalidade)
> **EVAL_AUTHORING_REQUIRED:** `false`. Esta spec não mexe em evaluator, expected nem baseline. A SPEC-285 é usada só como medida.

---

## 1. Contexto & Objetivo

A SPEC-272 (§9, `specs/SPEC-272-capacidades-conflito-so-testadas.md:120-131`) manteve 24 funções `done` sem
chamador. Em quase todas o motivo foi o mesmo: **"exige declaração/escolha do jogador"**. Não houve objeção
de risco nem de balanço. As exceções:
- resistência revelada: falta o sinal no pipeline de dano (`:127`);
- reforços: falta a condição de disparo, e há o follow-up de id único da SPEC-226:165 (`:122`).

O jogador nunca vê essas mecânicas. Estado atual de cada uma:

| Capacidade | Motor pronto | Por que não liga hoje (evidência) |
|---|---|---|
| Resistência revelada (069 R9) | `bestiary_knowledge.reveal_resistance` (`services/bestiary_knowledge.py:130`); a UI já mostra (`web/src/components/Hud.tsx:469-470`, `web/src/combat/Arena.tsx:27`, `api.py:2767`) | `_resolve_damage_and_wounds` aplica imunidade e resistência (`services/conflict_damage.py:229-246`), mas o retorno (`:343-354`) não diz qual delas agiu |
| Golpe não-letal (068 R8) | `death_flow.can_be_nonlethal`/`apply_nonlethal_finish` (`services/death_flow.py:382,391`) | `_check_terminal`/`_mark_dead` sempre matam (`services/conflict_orchestrator.py:1138-1174`). O parser não tem campo para isso (`agents/combat.py:613-622`) |
| Abordagem da fuga (070 R4) | `chase.approach_virtude` (`services/chase.py:118`) | A Virtude é fixa em agilidade (`agents/combat.py:1765`) |
| Ataque durante a fuga (070 R8) | `chase.chase_attack` (`services/chase.py:299`) | Atacar com perseguição ativa não fecha nem bloqueia a trilha (`agents/combat.py:1343-1347`) |
| Abandono e sacrifício (070 R6/R7) | `abandon_companion`, `simulate_abandoned_companion`, `can_volunteer_sacrifice`, `offer_sacrifice` (`services/chase.py:199,221,274,287`) | Não há declaração. Nenhum dado tem o traço `se_sacrifica_pelo_grupo` (grep em `data/`: 0) |
| Objetos de cena (064 R5/R7) | `apply_object_interaction` **já ligado** no resolvedor (`services/conflict_turn.py:109-119`). A preparação cria até 2 objetos (`services/encounter_preparation.py:200-211,369`) | O jogador não declara `kind="object"` (`agents/combat.py:614`). A API não expõe objetos (`api.py:2712-2740`). `visible_objects`/`discover_object` (`services/conflict_scene.py:346,371`) ficam sem uso |
| Ordem a companheiro (069 R3/R4/R6) | `tactical_profile.validate_companion_order` (`services/tactical_profile.py:413`) | Só o jogador declara (`agents/combat.py:1383`). Aliados agem por `enemy_declaration` (`services/conflict_orchestrator.py:1997`). Nenhum perfil tem `restricao` (o grep só acha `tactical_profile.py:422,476`) |
| Reforços (064 R8) | `add_reinforcement_trigger`/`fire_reinforcement` (`services/conflict_scene.py:436,445`) | A LLM deixou de pedir gatilhos (`services/encounter_preparation.py:306-313`). Falta id único (SPEC-226:165). O manifesto do encontro é congelado no spawn (`agents/combat.py:1146-1159`) |

O objetivo é ligar cada uma no pipeline vivo (`agents/combat.py` → `conflict_orchestrator.run_round` →
`conflict_turn`). Regras que valem para todas:
- **Python decide.** A intenção vem de regex ou nome canônico. A LLM só narra.
- **Kill switch por capacidade.** Começa em `shadow`, passa a `on` depois do gate de letalidade.
- **Regra de ouro** (`docs/mundo-vivo/VISAO.md`, SPEC-308). Jogador e narrador só recebem o que o herói
  viu: o efeito de objeto fica oculto até o uso, a resistência só aparece depois que agiu, o destino do
  companheiro abandonado fica selado e o reforço só existe depois do aviso.
- **Letalidade dentro das metas da SPEC-285:** M1 ≤ 0,564, M2 mediana da 1ª queda ≥ 20, M5 = 0
  `combat.no_progress` (`specs/SPEC-285-letalidade-pos-232-275.md:54-68`).

## 2. Requisitos

### Transversais

- **R1 — Flags.** O módulo novo `services/combat_flags.py` expõe `mode(cap) -> "off"|"shadow"|"on"`.
  - Cada capacidade tem sua variável: `RPG_COMBAT_REVEAL_RESIST`, `RPG_COMBAT_NONLETHAL`,
    `RPG_CHASE_APPROACH`, `RPG_CHASE_ATTACK`, `RPG_CHASE_ABANDON` (abandono + sacrifício),
    `RPG_COMBAT_OBJECTS`, `RPG_COMPANION_ORDERS`, `RPG_COMBAT_REINFORCEMENTS`.
  - Default do código: `shadow`. Valor inválido também vira `shadow`. Mesmo padrão de `law.mode()`
    (`services/law.py:156-158`).
- **R2 — Semântica de `shadow`.**
  - Calcula a decisão e registra `mechanics_trace.record_step("<cap>_shadow", …)` e
    `_log_event("combat", "<cap>_shadow")`.
  - **Não muda** `GameState`, cena, ficha, party nem prosa. Se faltar o dado de entrada (sem objeto, sem
    aliado), não registra nada.
  - Teste por capacidade: o `combat_node` produz o mesmo estado em `off` e em `shadow`, com a mesma seed.
- **R3 — `off` = comportamento atual, byte a byte.** Os testes de regressão de combate existentes passam
  sem alteração com tudo em `off`.
- **R4 — Telemetria.** Todo evento novo de `_log_event` entra em `docs/operacao/EVENTOS_DE_LOG.md`
  (`tests/test_log_event_registry.py`).
  - O playtest conta disparos por capacidade no summary (`playtest/telemetry.py`): `capability_counts`
    com chaves `<cap>` e `<cap>_shadow`.
- **R5 — Regra de ouro, com oráculo testável.** As mensagens que vão para `_narrate` (`agents/combat.py:916`)
  e a resposta de `/game/state` não podem conter:
  - `effect` de objeto não usado;
  - resistência ainda não revelada;
  - o `pending_fate` de companheiro abandonado;
  - reforço ainda não avisado.
- **R6 — Saves.** Todo campo novo é opcional (§3, Schemas).
  - Um save sem esses campos carrega e o combate segue.
  - Um save gravado **no meio** de uma perseguição antiga retoma por `chase.can_resume`
    (`services/chase.py:96`) sem erro.
- **R7 — Integração pelo nó real.** Cada capacidade tem pelo menos um teste que passa por
  `agents.combat.combat_node` (MockLLM, seed fixa, padrão de `tests/test_spec272_conflito_ligado.py`), além
  dos unitários. Unitário sozinho não fecha a etapa.

### Fase A — informação e escolha, sem perda de vida (valor alto, risco baixo)

- **R8 — Resistência revelada (`RPG_COMBAT_REVEAL_RESIST`).**
  - `_resolve_damage_and_wounds` passa a devolver `resistance_hit: {"type": dtype, "effect": "imune"|"resiste"|"vulneravel"} | None`.
    Imunidade sai em `:229-242`; modificador diferente de 0 sai em `:243-246`.
  - Os dados do jogo não mudam.
  - Quando o atacante é do lado `hero`/`ally` e o alvo é inimigo, o nó grava `"<dtype>:<effect>"` em
    `enemy["revealed_resistances"]`. No perfil `legacy`, também persiste via `bk.reveal_resistance`, com o
    mesmo fail-closed de `_sync_enemy_knowledge` (`agents/combat.py:220-251`).
  - Ataque de inimigo contra o herói não revela nada.
  - A API traduz o par para rótulo pt-BR, por exemplo `Ígneo (imune)`.
- **R9 — Golpe não-letal (`RPG_COMBAT_NONLETHAL`).**
  - **Declaração.** Regex fechada `NONLETHAL_RE` em `services/death_flow.py` (por exemplo "sem matar",
    "nocautear", "desacordar", "poupar", "não letal", com negação tratada). Ou o chip de UI, com
    `params["nao_letal"]=True`. Vale só para `attack`/`card` do jogador.
  - **Efeito.** Se o golpe declarado não-letal causaria `_mark_dead` no alvo e `can_be_nonlethal(form)`
    permite, entra `apply_nonlethal_finish`. Para Elite/Chefe/Nomeado, a regra vale no golpe que mataria
    depois da Última Ação (`conflict_orchestrator.py:1154-1163`). `form` = `{tipo: efeito.kind, letal_forcado: card.letal}`.
  - **Status.** O alvo fica `status="incapacitado"`. Tratar esse status em:
    - `_mirror_vitals` (`agents/combat.py:685-697`), que hoje faria `setdefault("ativo")`;
    - `_encounter_outcome` (`:1009`), que hoje contaria como "remaining" e daria `defeat`;
    - `death_flow.combat_should_end` (já cobre, `services/death_flow.py:418`);
    - o manifesto (`services/encounter_manifest.py:29`), com novo `EventKind` `"incapacitated"`.
  - **XP.** XP e loot iguais aos do abate (D2), pela mesma transição idempotente `xp_awarded`
    (`agents/combat.py:1434-1447`).
  - **Sem morte registrada.** Não gera `npc_killed` (`_kill_events`, `:109`). NPC nomeado continua vivo
    em `npcs`.
  - **Tag de companheiro.** Nova tag `poupou_inimigo` (`compaixao +1`) em `data/companion_choice_tags.json`,
    detectada em `companion_tags.detect_choice_tags` (`services/companion_tags.py:181-187`) pelo novo
    desfecho `incapacitated_enemy`.
  - **Só o jogador.** Inimigo não declara não-letal (fora de escopo).

### Fase B — escolhas na fuga

- **R10 — Abordagem (`RPG_CHASE_APPROACH`).**
  - Palavras-chave fechadas no texto da fuga escolhem a chave de `APPROACH_VIRTUDE`
    (`services/chase.py:34-45`); o default é `agilidade`.
  - `condutor_virtude = virtude_value(player, approach_virtude(k))` substitui o fixo de
    `agents/combat.py:1765`.
  - A abordagem fica em `chase_state["approach"]` e aparece no `_canonical_player_action`.
- **R11 — Ataque durante a fuga (`RPG_CHASE_ATTACK`).** Com `combat_meta["chase"]` não terminal e uma
  declaração `attack`/`card` do jogador, vale `chase_attack(chase, melee=not params.ranged)`:
  - à distância: Ação normal, a trilha continua;
  - corpo a corpo em `pressionado`: a perseguição fecha (`combat_meta["chase"]` limpo) e o ataque resolve;
  - corpo a corpo em `afastado`/`quase_livre`: a ação é **recusada sem gastar a rodada**, no mesmo padrão
    do item recusado (`services/conflict_orchestrator.py:1895-1901`), com log explicando por quê.
- **R12 — Abandono (`RPG_CHASE_ABANDON`).**
  - **Registro.** A cada rodada de fuga, as rolagens de Sorte por aliado ficam em
    `chase_state["last_luck"] = {ally_id: -1|0|1}`.
  - **Quem pode ser abandonado.** Só um companheiro **formal** (`state["party"]`, não aliado de cena) que
    tirou `-1` na rodada anterior.
  - **Declaração.** Regex fechada (`deixo|abandono <nome>`) mais o chip. O nome é casado com os ids de
    `last_luck`, sem LLM.
  - **Efeito.** `abandon_companion` tira o aliado do pool de Sorte **desta** rodada. O destino é sorteado
    por `simulate_abandoned_companion(seed = hash(instance_id, ally_id, round))` e fica **selado** em
    `party[i]["pending_fate"]`. O companheiro sai ativo e fica `waiting_at = local da fuga`.
  - **Revelação (D1).** O destino aparece pelo pipeline de destino da SPEC-304
    (`companion_soul.apply_companion_fate`, `services/companion_soul.py:958`, gate de telegrama `:950-955`).
    Mapeamento:
    - `captura`/`rendicao` → `capturado`;
    - `combate` → `ferido`;
    - `morte` → `morto`;
    - `fuga`/`esconderijo`/`reencontro_futuro` → volta a esperar sem dano.
  - **Resgate.** O aviso conta como telegrama. Voltar ao local antes de 1 dia permite o resgate (o gate já
    recusa).
  - **Sem LLM.** O narrador recebe só "X ficou para trás".
  - **Evento e tag.** Grava `companion_abandoned` no `event_log` e a tag nova `abandonou_companheiro`
    (`compaixao -2`, `honra -1`, magnitude 3) para **os outros** companheiros.
- **R13 — Sacrifício (`RPG_CHASE_ABANDON`).**
  - **Elegibilidade (D3).** `can_volunteer_sacrifice` ganha o caminho de alma: aprovação ≥ `LOYAL_AT`
    (`services/companion_soul.py:45`) **e** valor `coragem` ≥ 1, ou o traço explícito.
  - **Oferta.** Com a trilha em `pressionado` e um companheiro elegível, o nó publica
    `chase_state["sacrifice_offer"] = ally_id` uma vez por perseguição.
  - **Escolha.** Aceitar (chip ou regex "aceito") chama `offer_sacrifice(..., accept=True)`: o herói
    `escapou` nesta rodada e o companheiro segue o mesmo caminho selado do R12, com o desfecho sorteado
    entre `combate`/`captura`/`morte`.
  - **Recusar ou ignorar** não tem penalidade (070 R7).

### Fase C — cena e party

- **R14 — Objetos de cena (`RPG_COMBAT_OBJECTS`).**
  - **API.** O bloco de combate ganha `scene.objects = cs.visible_objects(scene)`: só `label`/`cost`/usos,
    nunca `effect`; objeto secreto só depois de descoberto.
  - **Declaração.** Nome canônico do objeto mais o rótulo da interação no texto resolve localmente para
    `TurnStep(kind="object", object_id, interaction)`, como as Cartas (`agents/combat.py:587-595`). O
    `PlayerMove` ganha `kind="object"` com `object_id`/`interaction`, validados contra `visible_objects`;
    valor inválido vira ataque básico.
  - **Alvo.** Efeito ofensivo com alvo do próprio lado é recusado (o equivalente de SPEC-232 R5 para
    objeto).
  - **Procurar.** `procurar` sem participante escondido chama `discover_object` no 1º objeto secreto da
    zona do ator.
- **R15 — Ordem a companheiro (`RPG_COMPANION_ORDERS`).**
  - **Declaração.** Regex fechada `<nome do aliado>, <verbo>` (atacar X / proteger / recuar / curar) mais
    o chip. Vira `TurnDeclaration` do aliado em `run_round(declarations=…)`.
  - **Tags da ordem.** Saem do alvo e do verbo, por exemplo: `atacar_rendido` (alvo `surrendered`),
    `atacar_incapacitado`, `abandonar_posto`.
  - **Restrições (D9).** Vêm de uma tabela Python fixa sobre os valores da alma (SPEC-300). Exemplo:
    `honra ≥ 2` bloqueia `atacar_rendido` como `absoluta`; `compaixao ≥ 2` bloqueia `atacar_incapacitado`
    como `resistente`, com `leverage` quando a aprovação é ≥ `LOYAL_AT`.
  - **Recusa.** `validate_companion_order` recusa: o aliado age pelo perfil, como hoje, e a recusa vai
    para o log e para a narração. A ação do jogador continua a mesma.
  - **Perda de comando.** Aliado com `loses_command` (`services/tactical_profile.py:443`) ignora a ordem.

### Fase D — aumenta letalidade (gate mais forte)

- **R16 — Reforços (`RPG_COMBAT_REINFORCEMENTS`, D4).**
  - **Gatilho.** Python, nunca LLM. Na preparação da cena, antes de `cs.freeze`
    (`agents/combat.py:505`), todo inimigo de arquétipo `lider_matilha` (ex.:
    `enemy_soldado_legiao_ferro`, `data/bestiary.json:269`) registra 1 gatilho `add_reinforcement_trigger`.
  - **Aviso.** Na 1ª vez que o líder fica com Vitalidade ≤ 50 %, o log publica o aviso.
  - **Chegada.** Na rodada seguinte, se o líder ainda age, `fire_reinforcement` traz **1** inimigo:
    - o template é um `lacaio` da mesma `faction` que o líder (se não houver, cópia do template do líder
      com `categoria` rebaixada a `lacaio`);
    - posição `distante`;
    - o limite é o orçamento restante do encontro (`_apply_encounter_budget`, `agents/combat.py:356`).
  - **Limite.** 1 vez por conflito.
  - **Id único.** O reforço recebe `"<base>_r<N>"` de um contador em `combat_meta["next_by_template"]`,
    o que fecha a SPEC-226:165. Entra no manifesto como evento `joined` (`services/encounter_manifest.py:29`).
  - **XP.** Pela transição normal.
  - **Silenciar o aviso.** Matar, incapacitar ou fazer o líder fugir antes da chegada cancela o reforço.

### Gate de letalidade (cada fase, antes de qualquer flag ir a `on` no staging)

- **R17 — Medição offline, roda o coordenador e não o subagente.** Todas as flags da fase em `on`.
  - (a) Arena SPEC-285 (`docs/spec285/arena_lethality.py`): M4 sem célula pior que +1,5 pp.
  - (b) Matriz SPEC-056 (5 classes × `combate` × seeds 42/43 × **50** turnos): M2 ≥ 20, 0 `no_progress`.
  - (c) **Opt-in do dono (D5):** `combate` 200 turnos, seeds 21–32, MockLLM: M1 ≤ 0,564, M2 ≥ 20, M5 = 0.
    Sem o OK, a fase só vai a `on` com (a) e (b) e fica registrado no cabeçalho.
  - A Fase D exige (c) **e** uma célula nova da arena "Elite `lider_matilha`": a taxa de morte sobe no
    máximo **+3 pp** sobre a mesma célula com a flag `off`.
- **R18 — Bots que exercitam.** Variantes de bot novas na arena (`nao_letal`, `foge_com_abordagem`, `usa_objeto`)
  e cenários novos no playtest (§6). As células e perfis atuais ficam intactos (integridade de medida).

### Fora de escopo

- Inimigo declarar não-letal / capturar o herói (follow-up 299 "derrota → prisão").
- Fluxo de prisioneiro após o não-letal (entregar à lei, SPEC-299 R23): esta spec só deixa o inimigo
  `incapacitado`.
- Postura declarada pelo jogador (`set_postura`/`consume_postura_on_attack`/`clear_sustained_postura`,
  `services/conflict_scene.py:286-328`) e `alert_party` (`:579`). Guardar, Esconder e os modificadores
  táticos já cobrem o efeito. Seguem adiados.
- **Fases de Chefe** (`behavior.phases`, SPEC-016 R5, removidas em ff018c26, `data/bestiary.json:2067`…).
  A SPEC-295 mediu ≤ 4 pp e descartou (`specs/SPEC-295-chefe-no-topo.md:247-248`). D7.
- **`asset_pipeline.can_serve`** (`services/asset_pipeline.py:96`, SPEC-110): fica fora do conflito. A rota
  `/game/{id}/art/{generation_id}` (`api.py:4543`) não consulta visibilidade; vira auditoria separada (D7).
- `get_or_generate_profile`/`generate_tactical_profile` (LLM), `suggested_virtue_cards` (criação de
  personagem), `validate_narrative_consistency` (pede prosa estruturada), `validate_creature_selection`:
  continuam "manter" (SPEC-272 §9). `general_test` já tem chamador (`services/reputation.py:1146`).
- Inimigo usar objeto de cena; LLM voltar a preparar reforços.

## 3. Design técnico

**Arquivos novos**
- `services/combat_flags.py`: `CAPS: tuple[str, ...]`, `mode(cap: str) -> Literal["off","shadow","on"]`,
  `active(cap) -> bool` (`== "on"`), `shadow(cap) -> bool`.
- `services/combat_intents.py`: regex e casamento por nome, todos puros.
  - `nonlethal_declared(text) -> bool`
  - `chase_approach(text) -> str | None`
  - `abandon_target(text, candidates: dict[str, str]) -> str | None` (id → nome)
  - `accepts_sacrifice(text) -> bool`
  - `object_step(text, visible: list[dict]) -> tuple[str, str] | None`
  - `companion_order(text, allies: dict[str, str], enemies: list[dict]) -> dict | None`
    (`{ally_id, verb, target_id, tags}`)
- `services/companion_orders.py`: `restrictions_from_soul(soul: dict) -> list[dict]` (tabela fixa, D9) e
  `ally_declaration(order, ally, scene, actors_by_id, sides) -> TurnDeclaration | None`.
- `services/reinforcements.py`: `plan_triggers(enemies, budget) -> list[dict]`,
  `check(scene, actors_by_id, combat_meta) -> {"warn": [...], "fire": [...]}`,
  `spawn(trigger, combat_meta) -> list[dict]`.

**Arquivos alterados**
- `services/conflict_damage.py`: campo `resistance_hit` no retorno (R8).
- `services/conflict_orchestrator.py`:
  - propaga `resistance_hit` para `out["attacks"][i]`;
  - `_check_terminal`/`_mark_dead` recebem `nonlethal: bool` (R9);
  - `run_round` aceita declaração de aliado já validada (R15) e recusa sem gastar a rodada (R11).
- `services/conflict_turn.py`: `TurnStep.params["nao_letal"]` chega ao dano; `procurar` sem alvo chama
  `discover_object` (R14).
- `services/chase.py`:
  - `can_volunteer_sacrifice` aceita `soul: dict | None` (R13);
  - nova `fate_to_companion_fate(resultado) -> Literal["ferido","capturado","morto",""]` (R12).
- `agents/combat.py`: ligação de R8–R16 em `_attempt_flee` (`:1726`), na escolha da declaração
  (`:1343-1373`), em `_prepare_scene` (`:463`), `_mirror_vitals`, `_encounter_outcome`, `_kill_events` e
  no `PlayerMove` (`:613`).
- `services/companion_soul.py`: no `apply_turn`, que é o único escritor, consome `pending_fate` vencido
  via `apply_companion_fate`.
- `services/companion_tags.py` e `data/companion_choice_tags.json`: tags `poupou_inimigo` e
  `abandonou_companheiro`; desfecho `incapacitated_enemy`.
- `services/encounter_manifest.py`: `EventKind` ganha `"incapacitated"`; reforço como `joined`.
- `api.py`, bloco de combate (`:2712-2770`): `scene.objects`, `chase.{approach, abandon_candidates,
  sacrifice_offer}`, `nonlethal_available`, rótulo de resistência, `reinforcement_warning`.
- `web/src/combat/` e `web/src/types.ts`: chips de "Sem matar", objeto (rótulo da interação), "Deixar
  <nome>", "Aceitar sacrifício" e ordem a aliado. Cada chip só aparece com a flag `on` (a API manda os
  campos só nesse caso).
- `playtest/scenarios.py` e `playtest/invariants.py`: cenários do §6 e invariantes do R19.
- `scripts/staging/vercel_env.py` (`WORLD_FLAGS`, `:108`) e `scripts/staging/staging_flags.json`: as 8
  flags novas, sem que o script as apague (achado 2 da auditoria). Edita o coordenador.
- `docs/operacao/EVENTOS_DE_LOG.md`.

**Schemas (todos opcionais, `total=False`)**
```python
# combat_meta["chase"] (existente) ganha:
approach: str  # chave de APPROACH_VIRTUDE
last_luck: dict[str, int]  # ally_id -> -1|0|1 (rodada anterior)
sacrifice_offer: str | None  # ally_id; ofertado 1x
sacrifice_offered: bool
abandoned: list[str]
# party[i] ganha:
pending_fate: {"resultado": str, "fate": str, "day": int, "location_id": str, "seed": str}
waiting_at: str  # já usado pela SPEC-300/304
# inimigo ganha:
status: "incapacitado"
incapacitated: bool
nonlethal_by: str
revealed_resistances: list[str]  # "<dtype>:<imune|resiste|vulneravel>"
# combat_meta ganha:
next_by_template: dict[str, int]
reinforcement: {"trigger_id": str, "leader_id": str, "warned_round": int, "fired": bool}
```

**Mecânica de seed:** todo sorteio novo usa `random.Random(f"{instance_id}:{ally_id}:{round}")`, nunca o
`random` global. Assim o mesmo save e a mesma ação dão o mesmo desfecho (070 §7).

## 4. Plano passo a passo

Uma etapa = uma capacidade = um commit. Testes primeiro. Subagente roda só os arquivos da etapa, com
`-n 2` no máximo.

### Etapa 0 — Flags e intents
1. **Testes** (`tests/test_spec325_flags.py`, `tests/test_spec325_intents.py`):
   - `test_default_is_shadow`, `test_invalid_falls_back_to_shadow`;
   - um teste por regex, com casos positivos, negação ("não vou poupar") e falso-positivo
     ("abandono o plano");
   - `test_object_step_only_visible`, `test_abandon_only_candidates`.
2. **Implementação:** `combat_flags.py`, `combat_intents.py`.

### Etapa 1 — Resistência revelada (Fase A)
1. **Testes** (`tests/test_spec325_resist.py`):
   - `test_damage_returns_resistance_hit_imune/resiste/vulneravel/none`;
   - `test_node_reveals_on_hero_hit` (via `combat_node`, `enemy_iniciado_chama_azul`, imune a `igneo`,
     `data/bestiary.json:321,385`);
   - `test_enemy_hit_on_player_reveals_nothing`, `test_shadow_no_state_change`;
   - `test_hosted_profile_does_not_persist_overlay`, `test_api_label_pt_br`, `test_unrevealed_not_in_api`.
2. **Implementação:** R8.

### Etapa 2 — Golpe não-letal (Fase A)
1. **Testes** (`tests/test_spec325_nonlethal.py`):
   - `test_lacaio_nonlethal_incapacitated_not_dead`;
   - `test_elite_nonlethal_after_last_stand`;
   - `test_lethal_form_still_kills` (`letal_forcado`);
   - `test_outcome_victory_not_defeat_with_incapacitated` (protege `_encounter_outcome`);
   - `test_xp_once_on_incapacitation`, `test_no_npc_killed_event`;
   - `test_named_npc_survives_in_npcs`, `test_companion_tag_poupou_inimigo`;
   - `test_manifest_incapacitated_event`, `test_old_save_status_ativo_loads`, `test_shadow_no_state_change`.
2. **Implementação:** R9.
3. **Gate R17 da Fase A** (coordenador), depois staging `on`.

### Etapa 3 — Abordagem e ataque na fuga (Fase B)
1. **Testes** (`tests/test_spec325_chase_choices.py`):
   - `test_approach_keyword_picks_virtude`, `test_default_agilidade`;
   - `test_ranged_attack_keeps_chase`, `test_melee_pressionado_ends_chase`;
   - `test_melee_afastado_refused_without_spending_round`;
   - `test_resume_old_chase_snapshot`, todos via `combat_node`.
2. **Implementação:** R10, R11.

### Etapa 4 — Abandono e sacrifício (Fase B)
1. **Testes** (`tests/test_spec325_abandon.py`):
   - `test_only_complicacao_ally_can_be_abandoned`, `test_scene_ally_cannot_be_abandoned`;
   - `test_abandon_removes_luck_this_round`;
   - `test_fate_sealed_not_in_narration_or_api` (oráculo do R5);
   - `test_fate_applied_after_one_day_via_304`, `test_return_before_day_rescues`;
   - `test_same_seed_same_fate`, `test_other_companions_get_abandon_tag`;
   - `test_sacrifice_offer_once_for_loyal_brave`, `test_no_offer_without_trait_or_soul`;
   - `test_accept_sacrifice_escapes_and_seals_fate`, `test_refuse_no_penalty`.
2. **Implementação:** R12, R13.
3. **Gate R17 da Fase B.**

### Etapa 5 — Objetos de cena (Fase C)
1. **Testes** (`tests/test_spec325_objects.py`):
   - `test_api_objects_hide_effect_and_secret`;
   - `test_chip_name_resolves_object_step_without_llm`;
   - `test_classify_object_invalid_falls_back_to_attack`;
   - `test_object_use_consumes_single_use` (`uses_remaining=1`, `encounter_preparation.py:206`);
   - `test_offensive_object_self_side_refused`, `test_procurar_discovers_secret`;
   - `test_fallback_scene_has_no_objects_no_chip`.
2. **Implementação:** R14.

### Etapa 6 — Ordem a companheiro (Fase C)
1. **Testes** (`tests/test_spec325_orders.py`):
   - `test_order_becomes_ally_declaration`;
   - `test_absolute_restriction_refuses_and_ally_uses_profile`;
   - `test_resistant_yields_with_loyalty`, `test_lost_command_ignores_order`;
   - `test_player_action_unchanged_on_refusal`, `test_restrictions_table_from_soul`.
2. **Implementação:** R15.
3. **Gate R17 da Fase C.**

### Etapa 7 — Reforços (Fase D)
1. **Testes** (`tests/test_spec325_reinforcements.py`):
   - `test_trigger_planned_before_freeze_only_leader`;
   - `test_warn_then_fire_next_round`, `test_once_per_conflict`;
   - `test_unique_instance_id_and_xp` (SPEC-226:165);
   - `test_manifest_joined`, `test_leader_down_cancels`, `test_budget_caps_spawn`;
   - `test_not_in_narration_before_warn`, `test_shadow_logs_would_fire_only`.
2. **Implementação:** R16.
3. **Gate R17 da Fase D**, com a célula `lider_matilha` e D5.

### Etapa 8 — Invariantes e cenários
- **R19.** Invariantes novos em `playtest/invariants.py`:
  - `incapacitado` nunca em `deaths`;
  - companheiro com `pending_fate` nunca `active`;
  - objeto com `uses_remaining < 0` nunca;
  - reforço com id repetido nunca;
  - `revealed_resistances` só com valores do formato.
- Cenários de §6 em `playtest/scenarios.py`. Playtest Mock: `--all --turns 3` e cada cenário novo com 10
  turnos, 0 erro e 0 violação.

## 5. Critérios de aceite

- [ ] R1–R19 cobertos por teste. (Fases A e B: R1–R3, R5, R6, R7, R8–R13 feitos; R4 `capability_counts`, R6 de C–D, R14–R19 pendentes.) Cada capacidade tem teste via `combat_node` (R7).
- [ ] Teste `off` = baseline e `shadow` = sem mudança de estado, por capacidade (R2/R3).
- [ ] Oráculo da regra de ouro verde (R5).
- [ ] Gate R17 registrado no cabeçalho por fase: arena, matriz 50 turnos e, com o OK do dono, 12 × 200.
- [ ] Saves antigos, inclusive em perseguição, carregam (R6).
- [ ] Guard de FallbackLLM no `PlayerMove` estendido (`isinstance`, já existente em `agents/combat.py:649`).
- [ ] `EVENTOS_DE_LOG.md` atualizado; `test_log_event_registry` verde.
- [ ] Testes do escopo verdes com `-n 2`; suíte completa 1× no pouso (coordenador).
- [ ] Revisão independente (Sol) aprovada.
- [ ] Smoke real §6 executado, dentro do teto.
- [ ] Adendos datados em SPEC-064, 068, 069 e 070: "ligado pela SPEC-325", com a flag.

## 6. Smoke test com LLM real

DeepSeek (`ROUTES` default), teto **`--max-cost 0.40`** e `--max-requests 400`. A estimativa é ~60 turnos
≈ US$ 0,05 (base: 10 turnos ≈ US$ 0,005 na SPEC-272). Todas as flags `on`. Um cenário por capacidade, cada um
com estado preparado em Python (`playtest/scenarios.py`) e ações roteirizadas:

1. `combate_resistencia`: herói com Carta `igneo` contra `enemy_iniciado_chama_azul`. Conferir:
   `revealed_resistances` contém `igneo:imune` depois do 1º golpe; o narrador não cita imunidade antes.
2. `combate_nao_letal`: "derrubo o soldado sem matar". Conferir: status `incapacitado`, desfecho `victory`,
   XP 1×, sem `npc_killed`, e a prosa não diz que ele morreu.
3. `fuga_escolhas`: "fujo pelos atalhos" (Mente), depois ataque corpo a corpo em `afastado` (recusado) e
   à distância (segue).
4. `fuga_abandono`: Brunna recrutada (cenário `companheiro`) tira Complicação, depois "deixo a Brunna".
   Conferir: o narrador só diz "ficou para trás"; o `pending_fate` não aparece na prosa nem na API; após
   descanso de 1 dia, o destino sai pela SPEC-304.
5. `combate_objeto`: Elite (cena preparada pela LLM). Usar o chip do objeto. Conferir: a interação
   resolve, o efeito não aparece antes do uso e o mapeamento `object_id`/`interaction` vindo do CLASSIFY
   real é válido. Esse é o ponto que o MockLLM esconde.
6. `combate_reforco`: `enemy_soldado_legiao_ferro` (líder). Conferir: aviso, chegada na rodada seguinte,
   id `_r1`, XP do reforço.

Para todos: 0 erro, 0 violação `error`, `mock=False`. Registrar os run_ids e o custo no cabeçalho.

## 7. Riscos & compatibilidade

- **Letalidade.**
  - A Fase A não pode subir a morte do herói. O não-letal só muda o destino do inimigo.
  - A Fase B pode **baixar** a morte, porque a fuga fica mais fácil com a Virtude alta. A fuga só fecha
    com `escapou`, e o teto `MAX_CONSECUTIVE_FLEE_ATTEMPTS` (`agents/combat.py:774`) continua.
  - A Fase D sobe a morte por construção (corpos são superlineares, SPEC-295:29-33): gate mais forte.
- **`incapacitado` é um status novo.** Qualquer leitor de `status == "ativo"` que não foi revisto conta o
  inimigo como vivo. Grep obrigatório na Etapa 2 (`agents/`, `services/`, `api.py`, `playtest/`).
- **Abandono × SPEC-304.** "Morte só com telegrama" é preservada porque o abandono é o telegrama e o gate
  de 1 dia já existe. Não chamar `apply_companion_fate` no mesmo turno.
- **Único escritor.** `companion_souls` só é escrito em `companion_soul.apply_turn`. O combate grava
  `pending_fate` na party e eventos no `event_log`, nunca na alma.
- **MockLLM:** devolve `PlayerMove` válido, então não pega erro de `object_id`. O smoke 5 é obrigatório.
  FallbackLLM: o parser cai em ataque básico (`agents/combat.py:574-577`).
- **Quota/latência:** nenhum invoke novo. O CLASSIFY de combate ganha 2 campos e um trecho de prompt
  com os objetos visíveis (≤ 2 objetos, ~60 tokens).
- **Staging:** sem as 8 flags em `WORLD_FLAGS`/preset, o `vercel_env.py` as apagaria e o código cairia em
  `shadow`, que é seguro mas invisível. Quem cuida é o coordenador.

## 8. Decisões do dono (aprovadas nos defaults em 25/10)

- **D1 — Destino do companheiro abandonado.** **Selado; revelado pelo pipeline da SPEC-304 depois de ≥ 1 dia;
  voltar antes resgata.** Alternativa: narrar o resultado da simulação na hora (SPEC-070 §6 item 2), o que
  quebra a regra de ouro e o "morte só com telegrama" da 304.
- **D2 — Recompensa do não-letal.** **XP e loot iguais aos do abate; NPC nomeado sobrevive.** Alternativa:
  metade do XP, para não premiar a escolha.
- **D3 — Quem se oferece em sacrifício.** **Aprovação ≥ 70 (leal) e coragem ≥ 1, ou o traço explícito.**
  Alternativa: só o traço explícito em dados (hoje nenhum NPC o tem, então a mecânica ficaria morta).
- **D4 — Reforços.** **Só `lider_matilha`, 1 por conflito, aviso 1 rodada antes, flag `shadow` até o gate
  da Fase D.** Alternativa: deixar reforços fora desta spec.
- **D5 — Long-run.** **Autorizar até 4 campanhas `combate` 12 × 200 MockLLM (offline, US$ 0; uma por
  fase), rodadas pelo coordenador uma por vez.** Sem o OK, as Fases A–C vão a `on` só com arena e matriz
  de 50 turnos, e a Fase D não vai a `on`.
  **Dono 25/10: "ok" — long-run autorizado nos termos acima (até 4 campanhas 12 × 200 MockLLM, uma por fase, uma por vez).**
- **D6 — Rollout.** **Código em `shadow`; staging `on` por fase depois do gate; produção segue o staging.**
- **D7 — Itens fora do combate.** **Fases de Chefe: apagar os blocos `phases` mortos numa spec de poda
  separada** (alternativa: portar o K3 da SPEC-295). **`asset_pipeline.can_serve`: auditoria separada da
  rota de arte.** **Postura declarada, `alert_party` e os helpers `validate_*`: continuam adiados.**
- **D8 — UI.** **Chips mínimos no combate (Sem matar, objeto, Deixar X, Aceitar sacrifício, ordem) dentro
  desta spec.** Alternativa: só texto livre, que é pouco descobrível.
- **D9 — Restrições de ordem.** **Tabela Python fixa sobre os valores da alma (SPEC-300).** Alternativa:
  gerar por LLM (`get_or_generate_profile`), que custa invoke e quebra o determinismo.

## 8.1 Gate de letalidade da Fase A: comandos exatos (coordenador roda; subagente não)

Antes de medir, confirme a branch limpa e rode um de cada vez (máquina de 16 GB; sem `-n`). Em todos, as
flags da Fase A ficam em `on` na linha de comando; a linha de base é a mesma árvore com as duas em `off`.

```bash
# flags da Fase A
ON="RPG_COMBAT_REVEAL_RESIST=on RPG_COMBAT_NONLETHAL=on"
OFF="RPG_COMBAT_REVEAL_RESIST=off RPG_COMBAT_NONLETHAL=off"

# (a) Arena SPEC-285: 10 seeds, 2.250 lutas por célula. Critério: M4, nenhuma célula pior que +1,5 pp vs OFF.
env $OFF bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_off.json
env $ON  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_on.json

# (b) Matriz SPEC-056: 5 classes x combate x seeds 42/43 x 50 turnos. Critério: M2 >= 20, 0 combat.no_progress.
for cls in "Devoto do Abismo" "Sangromante" "Corruptor" "Arcanista Cinzento" "Médico de Campo"; do
  for seed in 42 43; do
    env $ON bash scripts/dev/py.sh -m playtest run --profile combate --class "$cls" --turns 50 --seed $seed
  done
done

# (c) D5 (autorizado pelo dono em 25/10): combate, 200 turnos, seeds 21-32, MockLLM, uma campanha por vez.
# Critério: M1 <= 0,564, M2 mediana da 1a queda >= 20, M5 = 0 combat.no_progress.
for seed in $(seq 21 32); do
  env $ON bash scripts/dev/py.sh -m playtest run --profile combate --turns 200 --seed $seed
done
# agregar cada run_id: bash scripts/dev/py.sh -m playtest report <run_id>
```

Observações honestas sobre a medida:

- Os bots atuais da arena e do perfil `combate` **não declaram** "sem matar", então `on` mede só que a
  fiação (campo `resistance_hit`, `_check_terminal` com `nonlethal`, status `incapacitado`) é neutra para a
  letalidade. O efeito do não-letal fica coberto pelos testes pelo `combat_node`. As variantes de bot
  `nao_letal`/`usa_objeto` do R18 entram na Etapa 8.
- Resultado esperado: Δ = 0 pp em todas as células (a Fase A não muda dano, iniciativa nem alvo). Qualquer
  diferença vira bug, não "ruído".
- Registrar no cabeçalho: SHA medido, `run_id`s e as tabelas (a) a (c). Só depois, `staging_flags.json` com
  as duas flags em `on` (D6).

## 8.2 Gate de letalidade da Fase B: comandos exatos (coordenador roda; subagente não)

Um de cada vez, sem `-n`. Fase A já está `on` no staging, então as duas linhas mantêm as flags da Fase A em
`on`; a linha de base é a mesma árvore com **só as flags da Fase B** em `off`.

```bash
A="RPG_COMBAT_REVEAL_RESIST=on RPG_COMBAT_NONLETHAL=on"
ON="$A RPG_CHASE_APPROACH=on RPG_CHASE_ATTACK=on RPG_CHASE_ABANDON=on"
OFF="$A RPG_CHASE_APPROACH=off RPG_CHASE_ATTACK=off RPG_CHASE_ABANDON=off"

# (a) Arena SPEC-285: sanidade. A arena chama run_round direto (sem combat_node, sem fuga), então a
#     Fase B é neutra por construção: esperado Δ = 0,0 pp nas 32 células. Qualquer diferença é bug.
env $OFF bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_b_off.json
env $ON  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_b_on.json

# (b) Matriz SPEC-056 (5 classes x seeds 42/43 x 50 turnos), perfil `combate` E perfil `fujao`
#     (o único bot que foge de verdade; é ele que exercita R10-R13). Critério: M2 >= 20, 0 no_progress,
#     0 violação (inclui companion.fate_without_telegraph) e morte do herói do `fujao` <= linha de base.
for prof in combate fujao; do
  for cls in "Devoto do Abismo" "Sangromante" "Corruptor" "Arcanista Cinzento" "Médico de Campo"; do
    for seed in 42 43; do
      env $ON bash scripts/dev/py.sh -m playtest run --profile $prof --class "$cls" --turns 50 --seed $seed
      env $OFF bash scripts/dev/py.sh -m playtest run --profile $prof --class "$cls" --turns 50 --seed $seed
    done
  done
done

# (c) D5 (autorizado em 25/10, 1 campanha por fase): combate, 200 turnos, seeds 21-32, MockLLM, uma por vez.
#     Critério: M1 <= 0,564, M2 mediana da 1a queda >= 20, M5 = 0 combat.no_progress; as 2 violações
#     `summary.lifecycle` das seeds 25 e 32 são pré-existentes (Fase A) e não contam.
for seed in $(seq 21 32); do
  env $ON bash scripts/dev/py.sh -m playtest run --profile combate --turns 200 --seed $seed
done
# agregar: bash scripts/dev/py.sh -m playtest report <run_id>
```

Notas honestas sobre a medida:
- Os bots `combate` e `fujao` **não** dizem "deixo <nome>", "aceito" nem palavras de abordagem, e o harness
  não usa o chip: `on` mede que a fiação (rastro `last_luck`, oferta de sacrifício, gate de ataque durante a
  fuga) é neutra/benigna. O efeito de cada escolha fica coberto pelos testes pelo `combat_node`. As variantes
  de bot `foge_com_abordagem`/`deixa_companheiro` do R18 entram na Etapa 8.
- Esperado: Δ = 0 pp de morte no `combate`; no `fujao` o gate de ataque corpo a corpo durante a fuga (R11)
  só atua quando o bot ataca com perseguição ativa, e pode **baixar** a taxa de morte (recusa em vez de
  trocar golpes), nunca subir.

## 8.3 Gate de letalidade da Fase C: comandos exatos (coordenador roda; subagente não)

Um de cada vez, sem `-n`. Fases A e B já estão `on` no staging; a linha de base é a mesma árvore com **só as
flags da Fase C** em `off`.

```bash
AB="RPG_COMBAT_REVEAL_RESIST=on RPG_COMBAT_NONLETHAL=on RPG_CHASE_APPROACH=on RPG_CHASE_ATTACK=on RPG_CHASE_ABANDON=on RPG_COMPANION_SOUL=on"
ON="$AB RPG_COMBAT_OBJECTS=on RPG_COMPANION_ORDERS=on"
OFF="$AB RPG_COMBAT_OBJECTS=off RPG_COMPANION_ORDERS=off"

# (a) Arena SPEC-285: sanidade. A arena chama run_round direto (sem parser, sem chip, sem party formal),
#     então a Fase C é neutra por construção: esperado Δ = 0,0 pp nas 32 células.
env $OFF bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_c_off.json
env $ON  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_c_on.json

# (b) Matriz SPEC-056 (5 classes x seeds 42/43 x 50 turnos), perfis `combate` e `recrutador` (o que leva
#     party formal ao combate; exercita o caminho de ordem quando o texto traz "<aliado>, <verbo>").
#     Critério: M2 >= 20, 0 no_progress, 0 violação; morte do herói <= linha de base.
for prof in combate recrutador; do
  for cls in "Devoto do Abismo" "Sangromante" "Corruptor" "Arcanista Cinzento" "Médico de Campo"; do
    for seed in 42 43; do
      env $ON  bash scripts/dev/py.sh -m playtest run --profile $prof --class "$cls" --turns 50 --seed $seed
      env $OFF bash scripts/dev/py.sh -m playtest run --profile $prof --class "$cls" --turns 50 --seed $seed
    done
  done
done

# (c) D5 (autorizado em 25/10, 1 campanha por fase): combate, 200 turnos, seeds 21-32, MockLLM, uma por vez.
#     Critério: M1 <= 0,564, M2 >= 20, M5 = 0 combat.no_progress; as 2 violações `summary.lifecycle`
#     (seeds 25/32) são pré-existentes.
for seed in $(seq 21 32); do
  env $ON bash scripts/dev/py.sh -m playtest run --profile combate --turns 200 --seed $seed
done
# agregar: bash scripts/dev/py.sh -m playtest report <run_id>
```

Notas honestas sobre a medida:
- Os bots não dizem "<aliado>, <verbo>" nem o rótulo de objeto, e o harness não usa chips: `on` mede que a fiação
  (parser local, `procurar` com objeto secreto, API) é neutra para a letalidade. Cenas de `fallback_safe_scene`
  não têm objetos. O efeito fica coberto pelos testes pelo `combat_node`. As variantes de bot `usa_objeto` e de
  ordem a aliado (R18) entram na Etapa 8.
- Esperado: Δ = 0 pp em todas as células. O objeto pode **baixar** a morte (dano no inimigo), nunca subir, porque
  a recusa de efeito ofensivo contra os seus impede o dano autoinfligido.

## 8.4 Gate de letalidade da Fase D: comandos exatos (coordenador roda; subagente não)

Um de cada vez, sem `-n`. Fases A–C `on` nas duas pontas; a linha de base é a mesma árvore com **só**
`RPG_COMBAT_REINFORCEMENTS=off`. Fase D sobe a morte por construção: gate mais forte (R17).

```bash
ABC="RPG_COMBAT_REVEAL_RESIST=on RPG_COMBAT_NONLETHAL=on RPG_CHASE_APPROACH=on RPG_CHASE_ATTACK=on RPG_CHASE_ABANDON=on RPG_COMPANION_SOUL=on RPG_COMBAT_OBJECTS=on RPG_COMPANION_ORDERS=on"
ON="$ABC RPG_COMBAT_REINFORCEMENTS=on"
OFF="$ABC RPG_COMBAT_REINFORCEMENTS=off"

# (a) Arena SPEC-285, células atuais (neutras: nenhuma tem `lider_matilha` de reforço) E a célula nova
#     `lider_matilha` (Elite `lider_matilha` sozinho, reforço pelo mesmo `reinforcements.advance` do nó).
#     Critério: células atuais Δ = 0,0 pp; célula `lider_matilha`: morte ON no máximo +3 pp sobre OFF.
env $OFF bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_d_off.json
env $ON  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 > arena_d_on.json
env $OFF bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 --categories lider_matilha > arena_d_lider_off.json
env $ON  bash scripts/dev/py.sh docs/spec285/arena_lethality.py 10 --categories lider_matilha > arena_d_lider_on.json

# (b) Matriz SPEC-056 (5 classes x seeds 42/43 x 50 turnos), perfil `combate`. Critério: M2 >= 20, 0 no_progress.
for cls in "Devoto do Abismo" "Sangromante" "Corruptor" "Arcanista Cinzento" "Médico de Campo"; do
  for seed in 42 43; do
    env $ON  bash scripts/dev/py.sh -m playtest run --profile combate --class "$cls" --turns 50 --seed $seed
    env $OFF bash scripts/dev/py.sh -m playtest run --profile combate --class "$cls" --turns 50 --seed $seed
  done
done

# (c) D5 (autorizado em 25/10, 1 campanha por fase): combate, 200 turnos, seeds 21-32, MockLLM, uma por vez.
#     Critério: M1 <= 0,564, M2 >= 20, M5 = 0 combat.no_progress.
for seed in $(seq 21 32); do
  env $ON bash scripts/dev/py.sh -m playtest run --profile combate --turns 200 --seed $seed
done
# agregar: bash scripts/dev/py.sh -m playtest report <run_id>
```

Notas sobre a medida (smoke do executor após as correções da revisão, 10 seeds, MockLLM, só `lider_matilha`;
**não** é o gate). Relatar `death` **e** `timeout` por célula (D-P2-6): `timeout` conta como não-morte.
- Reforço = Lacaio real (ficha de Lacaio, arquétipo `bruto`, nome genérico "Capanga do bando", cobrado como Lacaio).
  Δ morte ON−OFF (atraso de chegada 1 rodada, valor da spec): basico L1/L3/L5/L8 = 0,0 / +31,0 / +30,0 / +36,0 pp;
  cartas = 0,0 / +26,5 / +28,0 / +37,0 pp. **O gate de +3 pp NÃO passa.** L1 é 0 (orçamento 3 < Elite 5 + Lacaio 2).
- Atraso de chegada 2 e 3 rodadas (`reinforcements.ARRIVAL_DELAY`) quase não muda (basico L3: 84,5 % e 83 % vs 88 %;
  cartas L3: 66,5 % e 62,5 % vs 71,5 %). O efeito é estrutural (corpos extras são superlineares, SPEC-295:29-33; na
  arena, 2 Lacaios sozinhos já matam 45 % no L3). Ajustar por tempo/quantidade dentro do D4 não fecha a conta:
  decisão do dono/coordenador antes de ligar `RPG_COMBAT_REINFORCEMENTS=on` (ver Histórico).
- Os bots do perfil `combate` quase não enfrentam `lider_matilha` onde o reforço cabe; a célula nova existe para medir.

## 9. Próximos passos (Etapa 8 e revisões)

1. ~~**Etapa 3 (Fase B, R10/R11)**~~ feita em `shadow` (26/10); `tests/test_spec325_chase_choices.py`.
2. ~~**Etapa 4 (Fase B, R12/R13)**~~ feita em `shadow` (26/10); `tests/test_spec325_abandon.py`. Falta o
   gate R17 da Fase B (§8.2) e a revisão Sol.
3. ~~**Etapa 5 (Fase C, R14)**~~ feita em `shadow` (26/10); `tests/test_spec325_objects.py`.
4. ~~**Etapa 6 (Fase C, R15)**~~ feita em `shadow` (26/10); `tests/test_spec325_orders.py`,
   `tests/test_spec325_intents_scene.py`. Falta o gate R17 da Fase C (§8.3) e a revisão Sol.
5. ~~**Etapa 7 (Fase D, R16)**~~ feita em `shadow` (26/10); `tests/test_spec325_reinforcements.py`, célula
   `lider_matilha` na arena. Falta o gate R17 da Fase D (§8.4) e a revisão Sol.
6. ~~**Etapa 8 (R4, R18, R19)**~~ feita (26/10, `tests/test_spec325_playtest.py`; ver Histórico). Escopo original: `capability_counts` no `playtest/telemetry.py`, variantes de bot da arena,
   cenários de §6 em `playtest/scenarios.py` e os invariantes restantes. A Fase A já tem
   `check_conflict_capabilities` (incapacitado nunca morto; formato de `revealed_resistances`).
7. **UI (D8):** chips de objeto e ordem a aliado (Fase C, 26/10), "Sem matar" (Fase A) e "Deixar X"/"Aceitar
   sacrifício" (Fase B) existem (`web/src/workspace/tabs/CombateTab.tsx`, só com a flag `on`: a API manda
   `chase.abandon_candidates`/`chase.sacrifice_offer` apenas nesse caso).
8. Adendos datados em SPEC-064/068/069/070 ("ligado pela SPEC-325") quando cada flag for a `on`.

## Histórico de mudanças

- **2026-10-25 — Aprovação.** Dono: "pode ligar", defaults da §8; D5 long-run autorizado ("ok").
- **2026-10-26 — Fase A implementada (shadow).** `services/combat_flags.py`, `services/combat_intents.py`,
  `death_flow.NONLETHAL_RE`/`nonlethal_declared`, `resistance_hit` em `conflict_damage`, `_nonlethal_mode`/
  `_mark_down` no orquestrador, status `incapacitado` (`_mirror_vitals`, `_encounter_outcome`, vitória/XP/loot
  do nó, manifesto `incapacitated`, `_targetable`, listas da API), tag `poupou_inimigo`, rótulo pt-BR da
  resistência na API, chip "Sem matar", 8 flags em `WORLD_FLAGS`/`OPTIONAL_FLAGS` de `vercel_env.py`.
  - **Desvio 1:** o shadow registra só por `_log_event` (`combat.reveal_resist_shadow`,
    `combat.nonlethal_shadow`); `mechanics_trace.KINDS` é um conjunto fechado e descartaria o passo
    `<cap>_shadow` do R2. Estender `KINDS` fica para quando o trace for consumido.
  - **Desvio 2:** o `PlayerMove` (CLASSIFY) **não** ganhou o campo `nao_letal`; a declaração é regex fechada
    no texto (e o chip manda a frase "Sem matar."), o que evita 1 campo a mais no schema do LLM.
  - **Desvio 3:** `staging_flags.json` não foi alterado (as flags ficam no código em `shadow` até o gate).
  - **Desvio 4:** `record_kills` do bestiário continua só para morte; o não-letal rende XP/loot (D2) mas não
    conta como "abate" no conhecimento do bestiário.
- **2026-10-26 — Revisão Sol: `CHANGES_REQUIRED`** (`handoffs/SPEC-325-sol-review.md`). Correções:
  - **P1-1** Elite/Chefe/Nomeado: o golpe não-letal que dispara a Última Ação marca `nonlethal_pending_by`;
    na resolução do Estado Terminal o alvo vira `incapacitado` (sem `deaths`, sem `npc_killed`). Em `shadow`
    só loga.
  - **P1-2** testes pelo `combat_node` real para lacaio/padrão/elite/nomeado/chefe, sem presets.
  - **P2-1** âncora de caça (SPEC-313) incapacitada conta como `hunt_kill` (opção a).
  - **P2-2** `law.supports("homicidio", …)` é falso quando há declaração não-letal.
  - **P2-3** `NONLETHAL_RE`: objeto pessoal após `poup*`, "não mate", "poupe-o", "deixo-o vivo", negação
    limitada à oração (vírgula/conjunção).
  - **P2-4** shadow compara o retorno inteiro e os argumentos da narração; regressão com as flags em `off`.
  - **P2-5/6/7** rótulo `incapacitado` no painel e na união TS, rótulo pt-BR no dossiê, chip "Sem matar"
    reseta após o envio e é ignorado se a flag sair de `on`.
  - **Desvio 5:** a tag `poupou_inimigo` sai de `final_status == "incapacitado"` com desfecho `victory`
    (em vez do desfecho `incapacitated_enemy` descrito no R9). O catálogo de tags passou de 15 para 16.
- 26/10 — **gate R17 da Fase A (coordenador)**, flags `RPG_COMBAT_REVEAL_RESIST=on RPG_COMBAT_NONLETHAL=on`, MockLLM:
  (a) arena SPEC-285, 10 seeds, off vs on: Δ death_rate = **0,0 pp nas 32 células** (basico/cartas × L1/L3/L5/L8 × lacaio/padrão/elite/chefe);
  (b) matriz SPEC-056, 5 classes × seeds 42/43 × 50 turnos: 10/10 com 0 erro, 0 violação, 0 `no_progress`;
  (c) long-run `combate` 12 × 200 (seeds 21–32, autorizado pelo dono em D5): 0 erro em todas; 2 violações `summary.lifecycle` ("conflito encerrou sem ConflictSummary") nas seeds 25 e 32 que **se repetem com as flags off** → pré-existentes, fora da Fase A (follow-up próprio). Os bots não declaram "sem matar", então o gate prova neutralidade da fiação, como previsto.
- 26/10 — Fase A pronta para `on` no staging; Fases B–D seguem pendentes (§9).
- **2026-10-26 — Fase B implementada (shadow).** `combat_intents.chase_approach/abandon_target/accepts_sacrifice`;
  `chase.seal_fate/abandon_candidates/eligible_for_sacrifice/fate_to_companion_fate` (+ `outcomes` na simulação e
  `soul` em `can_volunteer_sacrifice`/`offer_sacrifice`); `_attempt_flee` (abordagem, `last_luck`, `force_escape`),
  `_chase_attack_gate`, `_chase_party_choices`, `_publish_sacrifice_offer` em `agents/combat.py`; `run_round(refusal=)`;
  destino selado em `party[i].pending_fate` e consumido em `companion_soul.apply_turn` (passo 7b, único escritor);
  tag `abandonou_companheiro` (catálogo 17); API `chase.{approach, abandon_candidates, sacrifice_offer}` e chips
  "Deixar X"/"Aceitar sacrifício" só com a flag `on`; eventos novos em `EVENTOS_DE_LOG.md`.
  - **Desvio 6:** `chase.abandon_companion` (que faz `party.pop`) **não** é usado: o companheiro precisa seguir na
    `party` (inativo, `waiting_at` = id do local) para o `apply_companion_fate` da SPEC-304. O aliado sai do pool de
    Sorte/da rodada por remoção de `sides["ally"]`; o selo é `chase.seal_fate`.
  - **Desvio 7:** o aviso (telegrama D1) é registrado por `apply_turn` no 1º turno após o selo
    (`telegraphs[].source == "abandono"`, `day` = dia do abandono), porque o combate nunca escreve na alma. O
    destino sai depois de >= 1 dia, com o jogador fora do local e sem combate ativo; jogador no local (combate
    encerrado) ou companheiro rechamado = resgate (cancela o selo). `fuga`/`esconderijo`/`reencontro_futuro`
    apenas limpam o selo. Companheiro com selo é excluído de `companions_exposed` e da abertura de perigo do
    `npc_world` (um destino só).
  - **Desvio 8:** `companion_abandoned` vai direto ao `event_log` do resultado do nó (o validador de
    `pending_world_events` não conhece o tipo); o payload não carrega o destino e o `event_id` é um hash da seed.
  - **Desvio 9:** em `shadow`, `last_luck` não é persistido (o estado não muda), então o shadow de abandono loga
    quando o texto declara "deixo <companheiro formal ativo>" durante uma fuga, e o de sacrifício loga a cada
    rodada elegível (`sacrifice_offered` não persiste).
  - **Desvio 10:** declarar abandono ou aceitar a oferta conta como rodada de fuga (liga `flee_requested`); a
    abordagem vale só na rodada em que a palavra aparece (sem palavra = Agilidade, `approach` some do estado). O
    ataque corpo a corpo recusado devolve o contador `combat.round` ao valor anterior e reutiliza o caminho do
    item recusado (`run_round(refusal=...)`); o clima da rodada ainda é aplicado, como no item recusado.
  - **Desvio 11:** a arena SPEC-285 chama `run_round` direto, sem fuga: ela é neutra à Fase B por construção. O
    gate (§8.2) usa também o perfil `fujao`, único bot que foge. `capability_counts` (R4) e as variantes de bot
    (R18) seguem na Etapa 8. As 8 flags já estavam em `WORLD_FLAGS`/`OPTIONAL_FLAGS` desde a Fase A (teste novo
    garante).
- **2026-10-26 — Revisão Sol da Fase B: `CHANGES_REQUIRED`** (`handoffs/SPEC-325-sol-review.md` § Fase B). Correções:
  - **B-P1-1** (decisão do coordenador): o resgate só vale depois que o herói **saiu** e **voltou**. `apply_turn` marca
    `pending_fate["left"]` na 1ª vez que vê `here != location`; só `left` + retorno (ou rechamada) resgata. Ficar
    parado no local da fuga (fuga sem destino, caso dos chips) não resgata nem aplica o destino (o gate da 304
    recusa com o herói no local): o destino espera o herói partir e cai ≥ 1 dia depois. Teste ponta a ponta
    `combat_node` → `apply_turn` para abandono e sacrifício, sem editar o local do selo (`tests/test_spec325_abandon_review.py`).
  - **B-P2-1** o selo/telegrama/resgate rodam fora do portão `live`; com `RPG_COMPANION_SOUL=off` o combate recusa
    abandono/sacrifício (`combat_flags.abandon_mode()`) e `apply_turn` ainda libera o selo de quem foi rechamado.
  - **B-P2-2/3** testes de save/load no meio do selo e da exclusão do perigo off-screen (`day_hook`).
  - **B-P2-4** a recusa do corpo a corpo preserva `flee_attempts`. **B-P2-5** a fala do NPC mostra o nome do local.
  - **B-P2-6** (decisão do coordenador): sacrifício aceito grava `companion_sacrificed` no `event_log` e um marco de
    crônica percebido ("X ficou para trás para que o herói escapasse"), sem o destino e sem efeito extra de
    reputação; nenhuma tag nova (o catálogo da SPEC-300 pode etiquetar depois).
- 26/10 — **gate R17 da Fase B (coordenador)**, Fase A `on` nas duas pontas, Fase B off vs on (`RPG_CHASE_APPROACH/ATTACK/ABANDON`), `RPG_COMPANION_SOUL=on`, MockLLM: (a) arena 10 seeds: máx |Δ death_rate| = **0,0 pp** nas 32 células; (b) matriz 5 classes × seeds 42/43 × 50 turnos nos perfis `combate` e `fujao`: 20/20 com 0 erro, 0 violação, 0 `no_progress`; (c) long-run `combate` 12 × 200 (seeds 21–32): 0 erro; as 2 violações `summary.lifecycle` (seeds 25/32) são as pré-existentes. Bots não declaram "deixo"/"aceito" → gate mede neutralidade da fiação.
- **2026-10-26 — Fase C implementada (shadow).** `combat_intents.object_step/companion_order`;
  `services/companion_orders.py` (`restrictions_from_soul` = tabela fixa D9: `honra>=2` bloqueia `atacar_rendido`
  como `absoluta`, `compaixao>=2` bloqueia `atacar_incapacitado` como `resistente`, `coragem>=2` bloqueia
  `abandonar_posto` como `resistente`; `validate_order` soma as restrições ao perfil do aliado e usa
  `leverage = aprovação >= LOYAL_AT`; `ally_declaration`); `agents/combat.py`: `_object_declaration` (nome canônico +
  rótulo, sem CLASSIFY), `PlayerMove` estendido com `object_id`/`interaction` só com a flag `on` e objeto visível,
  `_guard_object_step` (inválido -> ataque básico; ofensivo contra os seus -> recusa sem gastar a rodada),
  `_companion_orders` (recusa/perda de comando viram linha de log); `conflict_turn._search_discovers_object`
  (`procurar` revela o 1º objeto secreto da zona do ator); API `scene.objects` e `companion_orders`; chips de
  objeto e de ordem; eventos novos em `EVENTOS_DE_LOG.md`.
  - **Desvio 12:** o texto do objeto exige o nome canônico **inteiro** do objeto e o rótulo (inteiro ou radical, para
    "derrubo" ~ "derrubar"); nome parcial ("o pilar") não casa. O chip manda `"<rótulo> <nome>."`.
  - **Desvio 13:** "ofensivo" = `damage` ou `apply_condition` nociva (dano contínuo, controle ou redutor). A mensagem
    da recusa é neutra ("Não dá para usar '<rótulo>' assim agora…") e **não** descreve o efeito (regra de ouro).
  - **Desvio 14:** declaração estruturada `object` do harness só é validada/saneada com a flag `on` (com `off`/`shadow`
    segue o caminho anterior, byte a byte).
  - **Desvio 15:** a ordem a aliado não altera a ação do jogador: o texto da ordem segue para o parser como antes
    (ataque básico no 1º inimigo quando o CLASSIFY não acha outra intenção). O chip de ordem manda só a ordem.
    `proteger` = tática `protect` no herói; `curar` = tática `support` no mais ferido; `recuar` = mover `afastar`;
    `atacar` sem alvo nomeado usa o 1º inimigo ativo; alvo rendido/incapacitado (fora do lado inimigo ativo) cai no
    perfil do aliado com a linha "não consegue cumprir a ordem agora".
  - **Desvio 16:** `procurar` só revela o objeto secreto se **ninguém** estava escondido do ator **antes** da busca
    (a busca limpa o `hidden_from`).
  - As 8 flags já estavam em `WORLD_FLAGS`/`OPTIONAL_FLAGS` (verificado: `vercel_env.py:99-101,151-153`).
- **2026-10-26 — Fase D implementada (shadow).** `services/reinforcements.py` (`plan_triggers`, `check`, `spawn`,
  `advance`, a única porta usada pelo nó e pela arena); `_plan_reinforcements` (em `_prepare_scene`, antes de
  `cs.freeze`) e `_advance_reinforcements` (fim da rodada, depois de `_mirror_vitals`) em `agents/combat.py`;
  `encounter_manifest.add_joined` e `_base_id` que também tira `_r<n>`; API `reinforcement_warning` (só entre o
  aviso e a chegada, com a flag `on`); nota na `CombateTab`; célula opcional `lider_matilha` em
  `docs/spec285/arena_lethality.py` (`--categories lider_matilha`; as células atuais seguem intactas).
  - **Fecha o follow-up SPEC-226:165:** o reforço recebe `"<base>_r<N>"` de `combat_meta["next_by_template"]`,
    distinto de `<base>_<n>` do spawn e de cadáveres; XP pela transição normal (`xp_awarded`).
  - **Desvio 17:** o aviso sai no fim da rodada em que o líder cai a ≤ 50 % e a **chegada é no fim da rodada
    seguinte** (não no início), para o jogador ter uma rodada inteira de contra-jogo; se o líder morrer, fugir, se
    render ou cair nesse intervalo, o reforço é cancelado (`reinforcement.cancelled`).
  - **Desvio 18:** o orçamento do gatilho é `encounter_budget(nível, danger_level, nº de aliados)` calculado no
    planejamento (o `encounter_eff_danger` do spawn já foi consumido); "restante" = orçamento − custo dos inimigos
    vivos. Por isso Elite sozinho em nível 1 (orçamento 3) nunca recebe reforço.
  - **Desvio 19:** em `shadow` não há gatilho nem `combat_meta.reinforcement` (o estado não muda): o shadow loga
    `reinforcements_shadow` com `phase=plan` (na preparação) e `phase=would_warn` (a cada rodada em que um líder
    ≤ 50 % ainda age).
  - **Desvio 20:** o template é um Lacaio da mesma `faction` (nenhum bestiário atual tem líder com Lacaio da própria
    facção: `enemy_soldado_legiao_ferro` e a maioria cai na cópia rebaixada); na cópia só `categoria`/`type` mudam, a
    ficha (Vitalidade etc.) é a do template do líder, como na letra do R16.
- **2026-10-26 — Revisão Sol C/D** (`handoffs/SPEC-325-sol-review.md`): Fase C `APPROVED_WITH_FOLLOWUPS`, Fase D
  `CHANGES_REQUIRED`. Correções (decisões do coordenador, **substituem o desvio 20**):
  - **D-P1-1/D-P1-2** o reforço é criatura de combate e Lacaio de verdade: Lacaio da mesma facção que não seja
    `lider_matilha` (nenhum do bestiário atual), senão Lacaio genérico `bruto` ("Capanga do bando", id-base
    `capanga_do_bando`, via `materialize_enemy_concept`, escala de Lacaio, perfil de combate, só a Carta
    `bst_defesa_instintiva`), cobrado como Lacaio no orçamento. Nunca a ficha do Elite nem o nome do líder (D-P2-2).
    Com isso o reforço deixou de **baixar** a morte (loop de apoio mútuo e fuga por `matilha_quebrada` sumiram).
  - **D-P2-1** `discovery.normalize_bestiary_id` usa `archetype_id` e `_r<N>`. **D-P2-3** teste de save/load entre aviso
    e chegada. **D-P2-4** `acts()` respeita `estado_terminal`/`last_stand_pending`. **D-P2-5** o teste de XP exige ganho
    real. **D-P2-6** o gate reporta `timeout` junto de `death` (§8.4).
  - **Medida:** o gate de +3 pp da célula `lider_matilha` NÃO passa (+26 a +37 pp, ver §8.4). `ARRIVAL_DELAY` virou
    constante (1 = spec). Reforço fica `shadow`; decisão pendente do dono/coordenador.
  - **C-P2-1** a oração da ordem sai do texto do jogador antes do CLASSIFY e do `FLEE_RE` ("Brunna, recuar." não
    faz o herói fugir); só a ordem = ataque básico no 1º inimigo, sem CLASSIFY (`combat_intents.split_order`).
    **C-P2-2** chip `Curar`. **C-P2-3** radical de rótulo de 5 letras ("puxar" ~ "puxo"). **C-P2-4** `object` só é
    reportado em `last_player_action` com a flag diferente de `off` (desvio 14 corrigido). **C-P2-5** a linha D9
    `coragem >= 2` -> `abandonar_posto` (resistente) é registrada como regra extra da tabela. **C-P2-6** chips em
    `web/src/combat/conflictChips.ts` com teste (`web/tests/conflict-chips.test.mjs`).
- 26/10 — **gate R17 da Fase C (coordenador)**, A+B `on`, reforço `shadow`, C off vs on (`RPG_COMBAT_OBJECTS`, `RPG_COMPANION_ORDERS`), MockLLM: arena 10 seeds máx |Δ| = **0,0 pp** (32 células); matriz 5 classes × 42/43 × 50 turnos nos perfis `combate` e `recrutador`: 20/20 limpas (0 erro, 0 violação, 0 `no_progress`); long-run 12 × 200: 0 erro, só as 2 `summary.lifecycle` pré-existentes (seeds 25/32). Fase C pronta para `on`.
- 26/10 — **Fase D: gate NÃO passa** (célula `lider_matilha` +26 a +37 pp com o reforço = Lacaio real; atraso de chegada não resolve). `RPG_COMBAT_REINFORCEMENTS` fica `shadow` — **decisão do dono pendente**: (1) reforço só em encontros com folga de orçamento [recomendado], (2) aceitar a letalidade maior, (3) desistir do D4.
- **2026-10-26 — Etapa 8 implementada (R4, R18, R19, §6).** `playtest/capabilities.py` (contador por `log_event` via
  `observability.telemetry.set_event_sink`; `capability_counts` com as 16 chaves `<cap>`/`<cap>_shadow` no summary e
  seção "Capacidades de conflito" no `report.md`); `playtest/capability_bots.py` (7 estratégias: combate pré-armado +
  ação roteirizada) e 7 cenários em `playtest/scenarios.py` (`combate_resistencia`, `combate_nao_letal`,
  `fuga_escolhas`, `fuga_abandono`, `combate_objeto`, `combate_ordem`, `combate_reforco`; perfil `combate`; fora de
  `PROFILES`/`--all`); bot `nao_letal` opcional na arena; invariantes `check_conflict_capabilities_state` e
  `check_conflict_golden_rule` (API pública do combate sem efeito de objeto, resistência não revelada, `pending_fate` nem
  aviso de reforço indevido).
  - **Desvio 21:** três eventos novos só com a flag `on` (para contar o efeito real): `combat.nonlethal`,
    `combat.chase_approach`, `combat.object_used` (catálogo atualizado). Nenhum muda estado.
  - **Desvio 22:** o herói não tem Carta `igneo` nos dados; `combate_resistencia` usa o Iniciado da Chama Azul com
    imunidade a todos os tipos físicos (a 1ª pancada revela `<tipo>:imune`) e arquétipo único por execução (o bestiário
    legado persiste revelações entre campanhas). O combate é armado em `decision_for` (turno 1 e a cada fim de combate,
    para o cenário não derivar a encontros sorteados), não em `prepare`.
  - **Desvio 23:** o oráculo de cada cenário só exige a capacidade primária com a flag `on`; `off`/`shadow` apenas rodam.
    As variantes `foge_com_abordagem`/`usa_objeto` do R18 não cabem na arena (ela chama `run_round`, sem fuga nem texto
    livre): vivem nos cenários; na arena entrou só `nao_letal`.
- 26/10 — **smoke real §6 (coordenador, DeepSeek, ~US$ 0,01)**, 8 flags `on` (reforço só no teste), cenários da Etapa 8, 10 turnos cada: `combate_resistencia` reveal=1, `combate_nao_letal` nonlethal=5, `fuga_escolhas` approach=5 + attack=2, `fuga_abandono` abandon=1, `combate_objeto` objects=2, `combate_ordem` orders=6, `combate_reforco` reinforcements=2; todos `mock=não`, 0 erro, 0 violação `error` (1 warn em `combate_ordem`). Etapa 8 é harness/telemetria (sem mudança de jogo): pousada sem revisão Sol dedicada, por decisão do coordenador.
- 26/10 — **Dono decidiu a Fase D: opção 3 — desistir dos reforços (D4).** Literal: "3". `RPG_COMBAT_REINFORCEMENTS` passa a default `off` em `services/combat_flags.py` (nem shadow; a variável segue aceita só para experimento explícito). Código e testes da Fase D ficam como estão (desligados). R16/D4 encerrados sem ligar.
- 26/10 — Fase C `on` no staging (gate R17 verde), junto com A e B.
