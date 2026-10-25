# SPEC-315 — Rumores adotados pelo motor (a LLM inventa o conteúdo; o motor decide se é verdade e o materializa)

> **Status:** `done` (aprovada 25/10 nos padrões; D6-rev1 do dono; revisão Sol 2 rodadas; smoke real 25/10)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Origem:** pedido do dono (25/10): "o motor decide e a LLM narra, mas o mundo tem que ser vivo".
> O motor tem um conjunto fechado de **tipos** de desfecho; a LLM pode inventar o **conteúdo**, que o
> motor adota e pode tornar **verdadeiro**.
> **Depende de:** SPEC-312 (`in-progress`, revisada, pousando: `services/rumors.py`, `ProposedRumor`,
> `StoryUpdateWithRumors`, `investigable`/`truth_of`/`mark_resolved`), SPEC-313 (`approved`: quest
> `investigar_rumor`, prova 223, `outcome`), SPEC-304 (`done`: `npc_world`, `npc_sim`), SPEC-308
> (`done`: regra de ouro dos eventos do motor), SPEC-302 (`done`: `day_rng`, pressões).
> **Interface paralela:** SPEC-314 (`draft`: gate de fação secreta; usar o helper dela se pousar antes,
> senão o fallback do R9).
> **Desbloqueia:** pistas com verdade (N5), entidades novas propostas pela LLM via pool (SPEC-297, v2).
> **EXECUTOR_MODEL:** `Opus` (Sol: cross-domain, writers em loot/encontro/NPC, regra de ouro) ·
> **REVIEW_MODEL:** `Opus` independente · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `false`.

---

## 1. Contexto & Objetivo

A SPEC-312 deixou a LLM propor um boato (`ProposedRumor`), mas todo boato proposto nasce **falso**,
fora de quest e com o modo desligado por padrão (`rpg-spec-312/services/rumors.py:726-727`,
`:46-48`; decisão D4 da 312, `SPEC-312:794-795`). Resultado: o que a LLM inventa nunca muda o mundo;
o mundo "vivo" é só o que as tabelas escritas à mão permitem.

Esta spec dá à LLM um canal **estruturado e fechado**: além do texto do boato, o narrador pode anexar
uma **alegação** (`RumorClaim`) num vocabulário de 5 tipos que o motor sabe materializar. O motor
valida a alegação (grafo, lore, segredos, regra de ouro), **sorteia a verdade** de forma determinística
e, se for verdadeira, materializa a consequência **com os writers que já existem** (achado de
exploração, encontro forçado, agenda de NPC) — e só quando o herói chega lá ou investiga. Se for falsa,
continua um boato da 312 e nunca vira fato. A resolução usa a quest `investigar_rumor` da 313.

Princípios: mecânica em Python (verdade, tetos, recompensa); a LLM só nomeia **o quê** e **onde**,
nunca **quanto**; zero chamada LLM nova (o campo vai no mesmo `StoryUpdate`); regra de ouro;
determinismo por `day_rng` (`services/world_engine.py:47-50`).

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | Boato proposto é sempre falso e fora de quest | `rpg-spec-312/services/rumors.py:719-734` (`truth: False`, `quest_eligible: False`) |
| P2 | `ProposedRumor` só tem `text`/`entity_ids`/`location_id`: não diz **o que** seria verdade | `rpg-spec-312/services/structured_outputs.py:115`; `SPEC-312:363-369` |
| P3 | O teto da proposta é só "não no mesmo dia" (`== day`), enquanto o rumor de semente respeita `RUMOR_MIN_GAP_DAYS=2` | `rpg-spec-312/services/rumors.py:689` vs `:504-506`; `SPEC-312:729-731` (D-2) |
| P4 | O invariante `rumor.became_fact` acusa qualquer `rumor_id`/assinatura em fato canônico, sem exceção para rumor verdadeiro materializado | `rpg-spec-312/playtest/invariants.py:2450-2472` |
| P5 | Já existem writers seguros para cada consequência, mas nenhum aceita "origem: rumor": achado (`services/exploration.py:37-59`, `:99-148`), encontro forçado com dica injetada (`world_utils.py:1137-1145`, `law_hint`; chamado em `agents/storyteller.py:1156-1171`), agenda de NPC (`services/npc_world.py:548`, `_step_position`; `:458` `_start_trip`) | idem |
| P6 | Texto do provider já não pode conceder moeda; esse princípio precisa valer para o rumor | `agents/storyteller.py:196`, `:1940-1943` |
| P7 | Entidade nova proposta pela LLM tem pipeline próprio (hold 24 h + avaliação) no pool | `services/shared_pool.py:155` (`submit`), `:496` (`promote_due`) |

## 2. Requisitos

Constantes `[BALANCEAR]` vivem em `data/world/rumor_adopt_config.json`.

### 2.1 Alegação estruturada (mesma chamada)

- **R1 — `RumorClaim` fechado.** `ProposedRumor` ganha `claim: RumorClaim | None = None` com
  `kind ∈ {esconderijo, item_perdido, perigo_na_estrada, criatura_avistada, npc_em_local}`
  (`Literal`), `location_id: str`, `entity_id: str = ""`. Nenhum campo de quantidade, raridade, item
  ou ouro existe no schema. Item com `kind` fora da lista ou malformado → `claim=None` (o boato segue
  pela 312), nunca derruba o `StoryUpdate` (coerção como `coerce_proposed_rumors`,
  `rpg-spec-312/services/structured_outputs.py:126`).
- **R2 — Sem chamada nova.** O campo só aparece no schema quando `RPG_RUMORS_ADOPTED ∈ {shadow, on}`
  (mesmo padrão de `StoryUpdateWithRumors`, `rpg-spec-312/agents/storyteller.py:178-193`, `:1654`).
  Teste: contagem de invokes por ação igual ao baseline da 312.
- **R3 — `entity_id` por tipo.** `criatura_avistada` exige id do bestiário; `npc_em_local` exige NPC
  conhecido (grafo público ou `state.npcs`); `esconderijo`/`item_perdido`/`perigo_na_estrada` exigem
  vazio. Divergência → `claim` rejeitada (`reason="entity_kind"`).

### 2.2 Validação (Python, antes da verdade)

O boato precisa primeiro passar na validação da 312 (`_validate_proposal`,
`rpg-spec-312/services/rumors.py:667-691`). Depois, a alegação passa por:

- **R4 — Local real e distante.** `location_id` existe em `world_map.json`; não é o local atual nem da
  família dele (`world_perception._family`); `travel_periods(aqui, alvo)` não é `None`
  (`services/world_distance.py:44`). Uma alegação sobre "aqui" é rejeitada (`reason="here"`): não há
  tesouro que nasce debaixo do pé do herói.
- **R5 — Coerência com o cânone, por tipo** (rejeição = `reason="canon"`):
  - `esconderijo`/`item_perdido`: alvo fora de `world.looted_locations`
    (`services/exploration.py:72`), sem baú curado (`treasure`) e sem outra alegação de achado ativa
    no mesmo local;
  - `perigo_na_estrada`: alvo sem tag de povoado (`settlement_tags` da 312) — é estrada ou ermo;
  - `criatura_avistada`: criatura do bestiário com o filtro de porte da família `avistamento` da 312
    (sem BOSS, `SPEC-312:93-98`);
  - `npc_em_local`: NPC vivo (`npc_layers.npc_alive`, `npc_world.dead_graph_npc`,
    `services/npc_world.py:392`), não capturado, fora da party, sem escolta da 313, sem perigo aberto
    (`npc_perils.has_open`, `services/npc_perils.py:152`), não é líder (`npc_world.is_leader`,
    `:112`, decisão D5), `RPG_NPC_WORLD=on`.
- **R6 — Segredo e lore oculta.** Rejeita (`reason="secret"`) se o alvo ou a entidade tem
  `visibility ≠ public` no grafo, se o texto + nomes da alegação casam assinatura secreta não revelada
  (`memory_provenance.find_strict_unrevealed`, já usado pela 312), ou se a entidade tem aresta oculta
  (`world_validators.canonical_secret_detail`, `services/world_validators.py:320`).
- **R7 — Fação secreta (SPEC-314).** Entidade que é fação, ou NPC cuja fação é secreta e desconhecida
  do jogador, só passa se o gate da 314 a mostraria (R1/R9 da 314). Sem a 314 pousada: fallback =
  rejeita qualquer fação secreta sem `faction_intel[f].known`.
- **R8 — Anti-direção pelo jogador.** Para `esconderijo`/`item_perdido`, rejeita
  (`reason="player_steered"`) se o nome do local alvo aparece nas últimas 3 entradas do jogador
  (mesma ideia de `shared_pool.name_typed_by_player`, `services/shared_pool.py:650`). O jogador não
  "encomenda" um tesouro dizendo ao taverneiro onde ele está. (Decisão D3.)
- **R9 — Quarentena.** Com `quarantine_llm_payload` verdadeiro no turno
  (`rpg-spec-312/agents/storyteller.py:1707`), nenhuma alegação é aceita.

### 2.3 Verdade (determinística) e orçamento

- **R10 — Sorteio único na adoção.** `truth = rng.random() < p(kind, estado)`, com
  `rng = day_rng(game_id, day, "rumor_adopt:" + rumor_id)`. Sorteio feito **uma vez**, gravado na
  instância; nunca re-sorteado. Bases `[BALANCEAR]`: `esconderijo` 0,35; `item_perdido` 0,30;
  `perigo_na_estrada` 0,40; `criatura_avistada` 0,50; `npc_em_local` 0,40.
- **R11 — Viés pelo estado do mundo (nunca pelo herói).**
  - `perigo_na_estrada`: +0,25 se a pressão `guerra` da região do alvo está em `sinal`/`crise`
    (`services/world_pressures.py:17`, `:116-128`) ou há rota bloqueada tocando o alvo
    (`world_validators._route_pair_blocked`, `services/world_validators.py:188`); teto 0,85;
  - `criatura_avistada`: `p = 0` se a região do alvo não está nas `regions` da criatura (mesma regra
    regional da 312, `SPEC-312:130-131`) ou se a criatura está rareada/suprimida na região
    (`services/ecology.py`, `suppressed_loot`/`hunt_pressure`);
  - `npc_em_local`: `p = 0` se a viagem do NPC até o alvo não cabe no TTL (`npc_world._travel`,
    `services/npc_world.py:448`).
  Teste: mesmo estado com `player.level` 1 e 20, ouro 0 e 5.000 → mesma verdade.
- **R12 — Mesmo orçamento da 312.** Alegação aceita **é** o rumor do dia: conta para
  `rumor_last_perceived_day` e passa a exigir o mesmo intervalo `RUMOR_MIN_GAP_DAYS` dos rumores de
  semente (corrige P3 só quando `RPG_RUMORS_ADOPTED ≠ off`). Decisão D2.
- **R13 — Tetos próprios.** `ADOPTED_PER_WINDOW` (2) alegações adotadas a cada `ADOPT_WINDOW_DAYS`
  (10); `ADOPTED_ACTIVE_MAX` (2) adotadas sem desfecho; `LOOT_TRUE_PER_WINDOW` (1) achado verdadeiro
  (`esconderijo`+`item_perdido`) a cada 20 dias. Estourou → alegação descartada
  (`reason="budget"`), boato segue pela 312. O teto de achado é aplicado **antes** do sorteio (vira
  rejeição), para a taxa de verdade observável não depender do teto.

### 2.4 Materialização (só ao chegar ou investigar; uma vez)

- **R14 — Gatilho.** Uma alegação verdadeira materializa **no máximo uma vez**, entre
  `born_day + 1` e `expires_day` (TTL da 312), quando:
  - achado: o herói está no `location_id` **e** a ação casa `SEARCH_VOCAB` (`procur`, `vasculh`,
    `cav`, `revir`, `busc`, `investig`) **ou** a quest `investigar_rumor` conclui lá;
  - encontro (`perigo_na_estrada`, `criatura_avistada`): o herói **viaja** para o alvo
    (`travel_periods ≥ 1`, mesmo ponto de `agents/storyteller.py:1131`);
  - `npc_em_local`: o NPC já está agendado desde a adoção (R17); a "materialização" é o herói chegar e
    o NPC estar lá (`npc_world.present_here`, `services/npc_world.py:405`).
  Grava `materialized_day` e `materialization` na instância (owner: `services/rumors.py`).
- **R15 — Achado limitado pela economia (anti-abuso).** Materializador novo
  `exploration.grant_rumor_cache(player, world, loc, rng, projection)` reusa `roll_loot`
  (`services/economy.py:956-990`) com o perigo **do alvo**, `boost=False`, ~~sem único (mesma regra R2b
  de `services/exploration.py:52-55`), e ouro ≤ `ADOPTED_GOLD_MAX` (40)~~ *(substituído em 25/10, ver
  **D6-rev1**)*: o tamanho do achado vem da **loteria de tier** (`find_tiers`, §8 D6-rev1): raridade
  subida/piso e teto de ouro por tier; único só no tier `excepcional` e só se livre `[BALANCEAR]`.
  `item_perdido` = só item (sem ouro); `esconderijo` = item ou ouro. O alvo entra em
  `world.looted_locations` (não rende baú nem achado de novo). A LLM nunca escolhe item, raridade ou
  valor. RNG = `day_rng(game_id, day, "rumor_cache:" + rumor_id)`.
- **R16 — Encontro pelo caminho existente.** `check_encounter` (`world_utils.py:1069`) ganha
  `rumor_hint: dict | None` com a mesma forma e precedência de `law_hint` (`:1137-1145`):
  `reason="rumor"`, `enemy_id` (`criatura_avistada`: o da alegação; `perigo_na_estrada`:
  `pick_encounter_enemy(loc, eff, …)`), força por `forced_encounter_danger` (`:1055-1066`, escala pelo
  nível; apex não). Ignora o cooldown de encontro **só esta vez**; respeita `_rest_recovers`. Tipo do
  encontro sorteado por `roll_encounter_type` (nem todo perigo é combate), salvo `criatura_avistada`
  (sempre combate).
- **R17 — NPC agendado pelo dono do domínio.** Na adoção verdadeira, `npc_world.schedule_visit(sim,
  ref, location_id, from_day, until_day, rumor_id)` grava `npc_sim.npcs[ref].rumor_visit`;
  `_step_position` respeita a visita com `_start_trip` (viaja de verdade, nunca teleporta, 304 R8) e
  libera em `until_day = expires_day`. Fuga/perigo da 304 cancelam a visita (a alegação vira
  `inconclusivo`). Writer único: `npc_world`.
- **R18 — Verdade falsa nunca materializa.** Nenhum materializador é chamado para `truth=false`,
  para `adopted=false` (shadow, rejeitada) nem fora da janela. Teste de propriedade (R30).
- **R19 — Sem fato retroativo.** A materialização nunca cria evento datado antes de
  `materialized_day`, nunca altera local já visitado no passado e nunca contradiz a projection
  (alvo saqueado, criatura extinta, NPC morto entre adoção e chegada → `inconclusivo`, nada acontece).
- **R20 — Regra de ouro.** Eventos gerados pela materialização (combate, item, NPC em cena) nascem do
  turno do herói, no local dele: são testemunho direto pelo filtro da 308
  (`SPEC-308:41-49`). Nada é materializado off-screen, exceto a viagem agendada do NPC, que já segue as
  regras da 304.

### 2.5 Resolução (SPEC-313)

- **R21 — Elegível a quest.** Alegação **adotada** (verdadeira ou falsa) tem `quest_eligible=true`,
  para que a oferta não revele a verdade (313 R23). Rejeitada ou em shadow: comportamento 312
  (`quest_eligible=false`).
- **R22 — Desfecho.** Na conclusão da quest: `truth=false` → `desmentido`; `truth=true` e materializada →
  `confirmado`; `truth=true` não materializada (R19 ou janela) → `inconclusivo`. Sempre via
  `rumors.mark_resolved` (`rpg-spec-312/services/rumors.py:790-803`). Sem quest, a alegação expira com
  o TTL e recebe o mesmo desfecho.

### 2.6 Estado, rollout, telemetria e prova

- **R23 — Schema aditivo.** `RumorInstance` ganha `claim`, `adopted`, `materialized_day`,
  `materialization`; `npc_sim.npcs[ref]` ganha `rumor_visit`; `world_sim` ganha `adopt_log` (lista de
  `born_day` de adoções, teto 20, para R13). Sem bump de versão. Save sem as chaves carrega como 312
  pura. Teste de round-trip save/load de cada chave.
- **R24 — Determinismo.** Sem `random` global no módulo novo (teste AST). Mesma seed + mesmas ações →
  mesma verdade, mesmo achado, mesmo encontro.
- **R25 — Flag `RPG_RUMORS_ADOPTED=off|shadow|on`**, default **`shadow`**; exige
  `RPG_RUMORS=on` **e** `RPG_RUMORS_PROPOSED=on` (senão vale `off`). `shadow`: valida, sorteia e loga
  `rumor_adopt.shadow{kind, truth, reason}`, grava a instância como 312 pura (`truth=false`,
  `adopted=false`); nenhum materializador roda. Passar de `shadow` para `on` não adota instâncias
  antigas.
- **R26 — Verdade nunca vaza.** `truth`, `claim`, `adopted`, `materialization`, `rumor_visit` nunca em
  prompt, API ou `world.news` (estende o R17 da 312 e o invariante `rumor.truth_leak`).
- **R27 — Telemetria.** `log_event("rumor_adopt", proposed|rejected|adopted|shadow|materialized|
  expired_unmaterialized, kind=, reason=)`; `truth` só agregado no `report` (taxa por tipo). Playtest
  grava por campanha: propostas, adotadas por tipo, verdadeiras, materializadas, ouro concedido por
  achado.
- **R28 — Invariantes de playtest (`error`).** `rumor_adopt.false_materialized`;
  `rumor_adopt.double_materialized`; `rumor_adopt.loot_over_cap` (ouro > teto **do tier** sorteado (D6-rev1), único fora do tier
  `excepcional`, ou > `LOOT_TRUE_PER_WINDOW` em `world_sim.find_log`); `rumor_adopt.npc_teleport` (NPC agendado em dois lugares ou sem
  viagem). `rumor.became_fact` passa a ignorar instâncias com `truth=true` **e** `materialized_day`
  (único ajuste no invariante da 312; corrige P4).

### Fora de escopo

- Entidade **nova** proposta pela alegação (NPC/criatura inventada): v2 via pool da 297
  (`shared_pool.submit`, hold + avaliação). Na v1, só ids existentes (decisão D1).
- Tipos de desfecho além dos 5 (preço, reputação, pressão, crise, controle de local, segredo).
- Alegação vinda de semente da 312 (sementes não têm `claim`); "eco distorcido" (312 D5).
- Qualquer item único, carta, XP ou ouro fora de `roll_loot`; encontro BOSS.
- Mudar `SUBJECT_PARAMS`, a propagação da 215, ou a recompensa da 313.
- UI nova: o jogador continua vendo só "boato" (312 R17).

## 3. Design técnico

### 3.1 Vocabulário fechado → materializador → dono

| `kind` | `entity_id` | Verdade base | Materializa quando | Writer (dono canônico) | Round-trip |
|---|---|---|---|---|---|
| `esconderijo` | vazio | 0,35 | no alvo + busca, ou quest conclui | `exploration.grant_rumor_cache` → `player.inventory/gold`, `world.looted_locations` | já persistidos; `RumorInstance.materialized_day` |
| `item_perdido` | vazio | 0,30 | idem (só item) | idem | idem |
| `perigo_na_estrada` | vazio | 0,40 (+0,25 guerra/rota) | viagem ao alvo | `world_utils.check_encounter(rumor_hint=)` → `combat`/encontro do storyteller | `combat` já persiste; marca na instância |
| `criatura_avistada` | id do bestiário | 0,50 (0 fora da região) | viagem ao alvo | idem, `enemy_id` fixo | idem |
| `npc_em_local` | ref de NPC | 0,40 (0 se não chega) | adoção agenda; herói chega | `npc_world.schedule_visit` → `npc_sim.npcs[ref].rumor_visit` | `npc_sim` já persiste; teste novo |

`services/rumors.py` (312) continua owner de `world_sim.rumors`; o módulo novo só calcula e chama os
writers acima. Nenhum writer novo de `event_log`/projection.

### 3.2 Arquivos

- **Novo** `services/rumor_adoption.py`: `mode()`, `validate_claim`, `truth_p`, `adopt`,
  `due_materialization`, `materialize`, `resolve_outcome`. Puro, sem LLM, sem RNG global.
- **Novo** `data/world/rumor_adopt_config.json`: bases, vieses, tetos, `SEARCH_VOCAB`,
  `find_tiers` (D6-rev1; `ADOPTED_GOLD_MAX` = teto do tier `comum`).
- **Alterados:** `services/structured_outputs.py` (`RumorClaim`, campo em `ProposedRumor`, coerção);
  `agents/storyteller.py` (classe de schema com `claim` só com a flag; `_apply_proposed_rumors` chama
  `rumor_adoption.adopt`; gatilho de achado perto de `:952`; `rumor_hint` em `:1156-1171`);
  `services/rumors.py` (`_apply_proposal` aceita `adopted/truth/claim`; gap de R12;
  `is_quest_eligible` lê `adopted`); `services/exploration.py` (`grant_rumor_cache`);
  `world_utils.py` (`rumor_hint`); `services/npc_world.py` (`schedule_visit`, `_step_position`);
  `services/world_quests.py`/313 (`resolve_outcome` no desfecho); `playtest/invariants.py`,
  `telemetry.py`, `report.py`; `state.py` (tipos).

### 3.3 Schemas

```python
# services/structured_outputs.py
ClaimKind = Literal[
    "esconderijo", "item_perdido", "perigo_na_estrada", "criatura_avistada", "npc_em_local"
]


class RumorClaim(BaseModel):
    kind: ClaimKind
    location_id: str = Field(description="Id EXATO de local do mapa, diferente do local atual.")
    entity_id: str = Field(
        default="",
        description="criatura_avistada: id do bestiário; npc_em_local: id do NPC; demais: vazio.",
    )


class ProposedRumor(BaseModel):  # campos da 312 + :
    claim: RumorClaim | None = None


# state.py (aditivo em RumorInstance)
claim: dict  # {kind, location_id, entity_id} — INTERNO
adopted: bool  # False em shadow/rejeição
materialized_day: int  # 0 = não materializado
materialization: (
    dict  # {"kind": "cache"|"encounter"|"npc", "item_id"?, "gold"?, "enemy_id"?, "npc_ref"?}
)
```

Exemplo (dia 31, herói em `brekmar`): o taverneiro conta que "viram ratos da peste perto da muralha
de Nova Arcádia"; `claim={kind:"criatura_avistada", location_id:"nova_arcadia",
entity_id:"enemy_rato_peste_anel_lama"}` → região bate (R11), `p=0,50`, `day_rng(…, "rumor_adopt:<id>")`
→ 0,31 → `truth=true`. No dia 33 o herói viaja a `nova_arcadia` → `rumor_hint` → combate com ratos da
peste (força pelo nível) → `materialized_day=33`; a quest, se aceita, conclui `confirmado`.

### 3.4 Assinaturas

```python
# services/rumor_adoption.py
def mode() -> str                                      # off|shadow|on (R25)
def validate_claim(state: dict, claim: dict, day: int) -> str   # "" ou reason (R3-R9, R13)
def truth_p(state: dict, claim: dict) -> float         # R10-R11, nunca lê o herói
def adopt(state: dict, inst: dict, claim: dict, day: int) -> tuple[dict, dict | None]
    # -> (instância com adopted/truth/claim, npc_sim novo | None)
def due_materialization(state: dict, trigger: Literal["search", "travel", "quest"],
                        location_id: str, day: int) -> dict | None   # instância elegível (R14, R18)
def materialize(state: dict, inst: dict, day: int) -> tuple[dict, dict]  # (updates, instância)
def resolve_outcome(inst: dict) -> str                 # R22
```

## 4. Plano passo a passo

Pré-requisito: 312 na `main`. Testes de escopo `-q --lf -x`, no máximo `-n 2`.

### Etapa 0 — Sondas
Confirmar: helper de fação secreta da 314; `ecology` (supressão por região); nome final do desfecho
na 313 (`outcome`); onde `quarantine_llm_payload` é calculado após o pouso da 312. Divergência →
seção 10 "Desvios" no mesmo commit.

### Etapa 1 — Schema e validação
1. **Testes** (`tests/test_spec315_claim.py`): `test_claim_kind_closed_invalid_dropped_keeps_rumor`;
   `test_schema_has_claim_only_with_flag` (R2); `test_entity_kind_mismatch_rejected` (R3);
   `test_here_and_family_rejected` (R4); `test_canon_by_kind` (R5, um caso por tipo, incl. NPC morto,
   baú, povoado); `test_secret_and_hidden_rejected` (R6); `test_secret_faction_gate` (R7);
   `test_player_steered_loot_rejected` (R8); `test_quarantine_rejects` (R9);
   `test_fallbackllm_without_field_is_safe`.
2. **Implementação:** `RumorClaim`, `validate_claim`.

### Etapa 2 — Verdade e orçamento
1. **Testes** (`tests/test_spec315_truth.py`): `test_truth_deterministic_and_never_resampled`;
   `test_truth_rate_per_kind` (5.000 sorteios sintéticos, ±0,03); `test_road_bias_guerra_and_route`;
   `test_creature_outside_region_always_false`; `test_independent_of_player_stats` (R11);
   `test_shares_312_gap` (R12); `test_window_active_and_loot_caps_before_roll` (R13);
   `test_no_global_random` (AST).
2. **Implementação:** `truth_p`, `adopt`, `adopt_log`, ajuste do gap em `rumors`.

### Etapa 3 — Materializadores
1. **Testes** (`tests/test_spec315_materialize.py`): `test_cache_uses_roll_loot_no_unique_gold_cap`
   (R15); `test_cache_marks_looted_and_never_repeats`; `test_search_vocab_or_quest_triggers`;
   `test_encounter_hint_like_law_hint_scaled_by_level` (R16); `test_rest_safety_respected`;
   `test_npc_schedule_travels_never_teleports` (R17); `test_npc_peril_cancels_visit_inconclusivo`;
   `test_target_looted_or_npc_dead_after_adoption_is_inconclusivo` (R19);
   `test_materialized_events_pass_308_filter` (R20).
2. **Teste de propriedade** (`tests/test_spec315_property.py`, `hypothesis` se já na dev-dep, senão
   200 seeds parametrizados): para sequências aleatórias de ações (viajar, buscar, descansar, aceitar
   quest) sobre alegações de todos os tipos: **(a)** `truth=false` ou `adopted=false` → zero chamada a
   materializador e nenhuma mudança em inventário/ouro/`combat`/`rumor_visit` atribuível; **(b)**
   `truth=true` dentro da janela e com gatilho → exatamente 1 materialização; **(c)** nunca 2.
3. **Implementação:** `grant_rumor_cache`, `rumor_hint`, `schedule_visit`, ganchos no storyteller.

### Etapa 4 — Resolução, saves e prova
1. **Testes** (`tests/test_spec315_resolution.py`): `test_adopted_is_quest_eligible_true_or_false`
   (R21, payload de oferta idêntico); `test_outcome_mapping` (R22); `test_roundtrip_all_new_keys`
   (R23); `test_legacy_save_behaves_as_312`; `test_shadow_writes_no_adoption` (R25);
   `test_truth_and_claim_never_in_api_or_prompt` (R26); `test_invariants_detect_false_double_cap_teleport`
   (R28); `test_became_fact_exempts_materialized_true`.
2. **Verificação:** `python -m playtest run --all --turns 50` (MockLLM, flags `on`, MockLLM injeta
   alegações): 0 violação `error`; ruff nos arquivos tocados.

## 5. Critérios de aceite

- [ ] R1–R3: `RumorClaim` fechado, só com a flag, coerção sem derrubar o turno
- [ ] R4–R9: validação por tipo, segredo, fação secreta, anti-direção, quarentena
- [ ] R10–R13: verdade determinística por tipo/estado, independente do herói; orçamento 312 + tetos
- [ ] R14–R20: materialização uma vez, só no alvo, via writers existentes; achado dentro de `roll_loot` e da loteria de tier (D6-rev1)
- [ ] R21–R22: quest elegível sem vazar verdade; desfechos corretos
- [ ] R23–R28: saves antigos, round-trip, flag `shadow` default, telemetria, invariantes
- [ ] Teste de propriedade (falso nunca materializa; verdadeiro materializa exatamente 1×)
- [ ] Guard de FallbackLLM no caminho de `claim`
- [ ] `uv run pytest` verde (suíte completa, no pouso pelo coordenador)
- [ ] Revisão independente Opus sem P0/P1 (`handoffs/SPEC-315-review.md`)
- [ ] Smoke real §6 registrado na §9 "Evidência" (criada na implementação)

## 6. Smoke test com LLM real (DeepSeek, teto US$ 0,40)

Flags: `RPG_WORLD_ENGINE=on RPG_RUMORS=on RPG_RUMORS_PROPOSED=on RPG_RUMORS_ADOPTED=on
RPG_NPC_WORLD=on RPG_NPC_KNOWLEDGE=on`, DeepSeek nas `ROUTES`. O MockLLM não mostra se o provider
preenche `claim` com ids válidos, nem se a prosa "confirma" o boato antes da hora.

1. `uv run python -m playtest run --profile diplomatico --turns 15 --real --max-cost 0.20 --seed 41`:
   registrar alegações propostas/adotadas/rejeitadas por `reason`. Rejeição de 100 % por
   `location`/`entity_kind` = bug de mapeamento → corrigir antes de `done`. Leitura humana de 3
   adotadas (local real, distante, sem segredo).
2. Cenário dirigido (`--scenario mundo --turns 12 --real --max-cost 0.15 --seed 42`, com
   `world_sim["forced_adopt"]` do harness, padrão `npc_sim["forced"]` de
   `services/npc_perils.py:184`, só no playtest): 1 alegação verdadeira de `esconderijo` e 1 falsa;
   viajar e buscar nas duas. Asserta: verdadeira materializa 1× com ouro ≤ teto do tier sorteado (D6-rev1) e sem único duplicado; falsa não
   muda inventário; narração da chegada não inventa achado na falsa; `/game/state` sem
   `truth`/`claim`; 0 violação `error`; `mock=False`.
3. Invokes por ação = baseline da 312 (contador do harness).

Custo esperado ≤ US$ 0,35. Estourou → parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** todas as chaves opcionais; instância sem `claim` = 312 pura; `npc_sim` sem
  `rumor_visit` = 304 pura. Rollback de código: chaves ignoradas; uma visita agendada vira entrada
  inerte (o `_step_position` antigo não a lê).
- **Farm de tesouro:** limitado por R4 (não aqui), R8 (não encomendado), R13 (1 achado verdadeiro a
  cada 20 dias), R15 (`roll_loot` + loteria de tier, D6-rev1: ouro ≤ 400 só no tier excepcional, 3 %, único só se livre) e pelo orçamento compartilhado da 312.
  Esperado: ≤ ~2 % do ouro de uma campanha de 50 dias (medir no playtest, R27).
- **Encontro "encomendado" para matar o herói:** força por `forced_encounter_danger`, descanso seguro
  respeitado, sem BOSS.
- **Conflito com a 304:** visita agendada é a única escrita nova em `npc_sim`, sempre por
  `npc_world`; fuga/perigo têm precedência (R17).
- **Invariante da 312:** o ajuste do R28 é estreito (só `truth` + `materialized_day`); boato falso
  continua acusado.
- **MockLLM/FallbackLLM:** sem `claim` o caminho é a 312; o MockLLM não preenche `claim` por padrão (o
  teste injeta). Quota/latência: zero chamada nova; schema do `StoryUpdate` cresce 1 objeto opcional.

## 8. Decisões do dono (recomendação em negrito; vale até ele dizer o contrário)

- **D1 — Entidade nova na alegação.** **Fora da v1: só ids existentes.** Na v2, NPC/criatura nova
  passa pelo pool da 297 (hold 24 h + avaliação) antes de poder ser verdade.
- **D2 — Orçamento.** **Alegação conta como o rumor do dia e respeita o mesmo intervalo de 2 dias da
  312**, mais o teto próprio de 2 adoções a cada 10 dias. Alternativa: orçamento separado (mais
  rumores, mais spam).
- **D3 — Anti-direção.** **Rejeitar achado cujo local o jogador digitou nas últimas 3 ações.**
  Alternativa: aceitar e reduzir a chance de verdade pela metade.
- **D4 — Taxas de verdade.** **35 / 30 / 40 (+25 com guerra ou rota) / 50 / 40 %**, `[BALANCEAR]`.
- **D5 — `npc_em_local` com líderes** (Valerius etc.). **Não**: líder nunca é agendado por boato.
- ~~**D6 — Achado.** **Ouro ≤ 40 por achado, sem único, 1 achado verdadeiro a cada 20 dias.**~~
  *(substituída em 25/10, ver D6-rev1; o limite de frequência de 1 achado verdadeiro a cada 20 dias
  **permanece**.)*
- **D6-rev1 — Achado com loteria de tamanho (dono, 25/10/2026).** Palavras do dono: "gosto do
  limite, mas acho melhor colocar um sorteador. ter chance de aparecer coisas maiores ou não ter.
  limitando assim fica chato que sempre vai ter um loot ruim".
  - **Antes:** ouro ≤ 40, sem único, sempre `roll_loot` comum.
  - **Depois:** tier sorteado 1x por `day_rng(game_id, born_day, "rumor_tier:"+rumor_id)` (nunca
    influenciado pelo herói): **comum 55 %** (`roll_loot`, ouro ≤ 40) · **bom 30 %** (raridade +1
    degrau, ouro ≤ 90) · **raro 12 %** (raridade ≥ raro, ouro ≤ 180) · **excepcional 3 %**
    (raridade ≥ épico, ouro ≤ 400; único só se não reclamado, não colocado em baú curado e não do
    herói, com claim na projection; senão cai para raro). Local de perigo ≥ 4 sobe 1 tier
    (determinístico). Ouro do tier = ouro do `roll_loot` × multiplicador (1/2/4/8) limitado ao teto.
    A narração mostra o tamanho pelo que foi achado, nunca rótulo/número de tier.
  - **Racional:** teto fixo de 40 tornava todo achado pobre; a loteria dá chance real de coisas
    grandes sem mexer na frequência (1 achado verdadeiro / 20 dias) nem criar economia nova (reusa
    `roll_loot`, a escada de raridade e as regras de único). Constantes `[BALANCEAR]` em
    `data/world/rumor_adopt_config.json` (`find_tiers`).
- **D7 — Rollout.** **`shadow` por padrão (local, suíte e staging) até o smoke §6; depois `on` local e
  na suíte, staging `on` após 1 semana de shadow com taxa de rejeição < 60 %.**
- **D8 — Revogar a D4 da 312** ("boato do narrador é sempre falso") **só quando
  `RPG_RUMORS_ADOPTED=on`**; com `off`/`shadow` a 312 fica como está. **Sim.**

## 9. Evidência

Smoke real §6 **não rodado** (fora do escopo do executor; custo US$ 0,40). Cenário do harness
criado: `python -m playtest run --scenario rumor_adotado --turns 10` (MockLLM) passa com oráculo
(achado verdadeiro materializa 1x, falso não); para o smoke real use `--real --max-cost 0.15`.

## 10. Desvios (implementação)

- **D-1 — Schema por subclasse.** `ProposedRumor` fica intacto; `ProposedRumorWithClaim` (com `claim`) e
  `StoryUpdateWithRumorClaims` só entram com `RPG_RUMORS_ADOPTED != off` (R2: o campo não existe no
  schema com a flag desligada). `coerce_proposed_rumors(raw, model)` aceita o modelo.
- **D-2 — Gap (R12) só na alegação.** Intervalo de `RUMOR_MIN_GAP_DAYS` vira `reason="gap"` em
  `validate_claim` (a alegação é descartada e o boato segue pela 312); `_validate_proposal` da 312 não
  muda (boato sem `claim` mantém o `daily_cap`).
- **D-3 — NPC fora do elenco.** `npc_em_local` exige o NPC em `npc_sim.npcs` (elenco simulado); fora
  dele, `reason="canon"`. Líder, capturado, ferido/congelado, escoltado ou com perigo aberto: rejeitado.
- **D-4 — Gatilho `quest`.** Com quest `investigar_rumor` ativa ancorada no rumor, o herói no alvo
  materializa o achado em qualquer ação (a conclusão da quest é decidida pelo event processor, que não
  escreve em `player`); sem quest, exige `SEARCH_VOCAB`.
- **D-5 — Rota LOOT.** `loot_node` (TREASURE) também chama `due_materialization` e entrega o achado do boato no lugar do sorteio genérico.
- **D-6 — Visibilidade.** Aresta oculta (`canonical_secret_detail`) só barra a **entidade** da alegação;
  local com aresta oculta (quase todos têm) só é barrado por `visibility != public` ou assinatura secreta.
- **D-7 — Fação secreta (R7).** Chama `services.faction_gate` (SPEC-314) direto.
- **D-8 — Cenário.** `--scenario rumor_adotado` (instâncias adotadas pré-injetadas + `world_sim["forced_adopt"]`
  para alegações emitidas pela LLM) em vez de reaproveitar `mundo`.
- **D-9 — Revisão sol.** Teto de achado verdadeiro em `world_sim.find_log` (fora do ledger);
  gatilho `present` para NPC que chega depois; `forced_adopt` só com `RPG_PLAYTEST_FORCED_ADOPT=1`;
  invariante `npc_teleport` compara `prev`→atual no mesmo dia.
- **D-10 — Revisão sol P1/P2 (25/10).** Ver *Histórico de mudanças*. `loot_node` ganhou gancho
  (`_rumor_cache_find`); `economy.roll_loot` **mantém a assinatura original** (guarda de `test_conflito_resumo`); o miolo foi
  extraído para `_roll_loot_impl` e `economy.roll_loot_tiered(..., *, step_up, min_rarity)` é o único
  caminho com tier (só a SPEC-315 o usa); `_rumor_cache_trigger` devolve `(player, nota, eventos)` (claim de único).

## Histórico de mudanças

- **2026-10-25 — Aprovação.** Dono aprovou via `/goal` ("execute e suba todas as specs em draft a
  partir do número 300") com os padrões recomendados D1–D8.
- **2026-10-25 — Implementação inicial** (commit `f1a37de1`): `rumor_adoption`, materializadores,
  invariantes, cenário `rumor_adotado`; desvios D-1..D-8 acima.
- **2026-10-25 — Revisão independente: `CHANGES_REQUIRED`** (`handoffs/SPEC-315-sol-review.md`).
  - P1-1 anti-direção morto (`pst` perdia o histórico do jogador) → `_apply_proposed_rumors` preserva
    `state["messages"]`; teste via `_apply_proposed_rumors`.
  - P1-2 teto de 1 achado/20 dias vazava com o ledger → `world_sim.find_log` (fora do ledger,
    `LOOT_TRUE_PER_WINDOW`), invariante e teste de save/limpeza.
  - P1-3 teste vermelho pós-rebase → mocka/usa `faction_gate` real.
  - P2-1 fallback morto de `_faction_hidden` removido (chama `faction_gate`).
  - P2-2 fallback de exceção do LLM leva `world`; nota do achado diegética (`Ao explorar X, o jogador
    ENCONTROU:` → 2ª pessoa via `_player_facing_note`).
  - P2-3 eventos `rumor_adopt.*` com `log_event` literal + catálogo regenerado.
  - P2-4 gancho em `loot_node` (TREASURE) para busca roteada a LOOT.
  - P2-5 gatilho `present` (NPC chega depois do herói) e invariante `npc_teleport` por `prev`→atual
    no mesmo dia.
  - P2-6 `forced_adopt` só com `RPG_PLAYTEST_FORCED_ADOPT=1` (setado pelo cenário do harness).
- **2026-10-25 — D6-rev1** (decisão do dono): loteria de tamanho do achado; ver §8. Código:
  `find_tier`, `exploration.grant_rumor_cache(tier=)`, `economy.roll_loot(step_up, min_rarity)`,
  `_placed_uniques`; testes `tests/test_spec315_tiers.py` (distribuição ±3 pp, único nunca duplicado,
  teto por tier, frequência 1/20 dias).
- **2026-10-25 — Re-review: `CHANGES_REQUIRED`** (R-P1-1, R-P2-1..3). R-P1-1: `roll_loot` voltou à
  assinatura original e o tier passou para `roll_loot_tiered` (decisão do coordenador; a guarda de
  `test_conflito_resumo` não foi tocada). R-P2-1: a flag `RPG_PLAYTEST_FORCED_ADOPT` é limpa por
  `scenarios.cleanup` ao fim da campanha (`runner.run_campaign`). R-P2-2: `loot_node` não desvia para o
  achado do boato quando há corpo a saquear (`conflict_summary.mortos`): o corpo vem primeiro, o achado
  na busca seguinte (ou pelo storyteller). R-P2-3: `blocked` do achado inclui `player.equipment`.
- **D-11 — Smoke real: `find_log` e narração (25/10).** (1) Achado materializado de linha adotada sem
  registro (ex.: injetada pelo harness) não entrava em `find_log`: `rumors.mark_materialized` agora
  grava o dia do achado **uma única vez** (`find_logged` evita duplicar com o registro da adoção).
  (2) No alvo de uma alegação de achado adotada que não entrega nada agora (falsa, ou verdadeira fora
  da janela), a busca passa ao narrador o fato `<RESULTADO_DA_BUSCA>` (nada do boato está aqui) e a
  prosa que afirma esconderijo/baú/tesouro encontrado é neutralizada (`_neutralize_false_find`).

- **2026-10-25 — Smoke real (DeepSeek, `rumor_adotado`, seed 42): 2 falhas** — `find_log` ausente após
  achado real e narrador inventando achados no alvo falso (turnos 4–12). Corrigidas em D-11; testes:
  integração pelo nó real + save/load (`find_log == [5]`, 2º achado < 20 d recusado) e prompt capturado
  com `<RESULTADO_DA_BUSCA>` + prosa neutralizada.

## Smoke real §6 (25/10, coordenador, DeepSeek, ~US$ 0,05)

- Passo 1 (`--profile diplomatico --seed 41`, `20261025-163904-599140`): 15 turnos, 0 violação; 4 `rumor.proposed_seen`, nenhuma alegação (perfil roteia quase tudo para NPC).
- Passo 2 (`--scenario rumor_adotado --seed 42`): 1ª rodada `20261025-164246-215872` achou 2 falhas (find_log vazio; narrador inventando achados no alvo falso) → corrigidas em `a1719a46` (D-11). Repetido `20261025-164857-590593`: 12 turnos, 0 violação; alegação verdadeira em `na_anel_ferro` materializou 1× (tier `comum`, `pocao_cura`, ouro 0), `find_log=[1]`; alegação falsa em `na_anel_lama` não materializou e a narração diz "O esconderijo que o boato prometia não está aqui" / "Não há alçapão. Não há baú."; 5 propostas extras recusadas `daily_cap`.
- Suíte completa no pouso: verde exceto 1 teste de prazo sob carga (`test_jev_router_port::test_shadow_late_jev_within_deadline_is_still_observed`), que passou 3/3 isolado; a 315 não toca o roteador.
