# Sistema de Classes — Valoria (Cinco Posturas diante do Abismo)

> **Documento histórico do sistema pré-Cartas.** Desde o cutover de Conflitos v2,
> `data/player_abilities.json` e `known_abilities` foram removidos. As fontes da
> verdade atuais são `data/classes.json`, `data/cards/*.json`,
> `services/cards.py`, `services/conflict_orchestrator.py` e `progression.py`.
> Autoria e regras atuais: [CARTAS.md](CARTAS.md). As seções abaixo permanecem
> apenas como registro da evolução de Entropia/Carga e não devem orientar código novo.

---

## 1. Visão geral

O jogo tem **5 classes jogáveis**, cada uma com **3 subclasses**. Cada classe é uma
**postura filosófica diante do Abismo** (a entropia que consome Valoria), não uma
profissão. Tudo é 100% data-driven + determinístico: a IA narra, o motor decide os
números (`combat_mechanics.py`).

Cada classe define:

- **Ficha base** (`base_stats`): HP, **Entropia**, defesa e os 6 atributos
  (`str/dex/con/int/wis/cha`). `mana`/`stamina` do jogador = 0.
- **Gatilho de Entropia** (`entropy_trigger`): como gera Entropia extra no combate.
- **Regra especial** (`special_rule`): uma interação determinística própria.
- **Consequência de Carga** (`abyss`): o efeito do acúmulo de longo prazo.
- **Ganhos por nível** (`level_gains`): HP/Entropia por level up.
- **2 habilidades iniciais** + equipamento inicial.
- **3 subclasses** (`branches`) = ramos derivados de `known_abilities`.

---

## 2. Os dois recursos

### Entropia (curto prazo)
Pool único das 5 classes (**substitui mana+stamina do jogador**). Toda habilidade
custa Entropia (`resource_type: "Entropia"` → `combat_mechanics._resource_field`).
**Recompõe INTEGRAL no descanso** (diferente do HP, que fica em ~metade).
Cada classe tem um **gatilho alternativo** que gera Entropia extra durante o combate.

### Carga do Abismo (longo prazo)
`abyss_charge: int`. Acumula pelo uso do gatilho (**toda ativação soma `charge_per`**;
descanso normal **nunca** gera Carga). **Não cai no descanso.** Tem patamares
discretos — `leve` (1–3) · `moderado` (4–6) · `severo` (7+) — e cada classe sofre uma
**consequência** diferente ao subir de patamar (`combat_mechanics.abyss_tier`).

---

## 3. As cinco classes

| Classe | Papel · Postura | HP / Entropia / Def | Attr | Gatilho | Regra especial | Consequência |
|---|---|---|---|---|---|---|
| **Devoto do Abismo** | tank · ama | 38 / 14 / 16 | str | `on_damage_taken` (+1/4 dano) | provocação escala com Entropia | **Insônia** — descanso rende menos HP; aliado mitiga |
| **Sangromante** | dano cac · negocia | 26 / 16 / 12 | dex | `on_self_harm` (auto-dano→Entropia) | `blood_leak` (ser acertado vaza Entropia de sangue) | **Cicatriz** — golpe de pico reduz max_hp permanente |
| **Corruptor** | controle/DoT · trabalha junto | 28 / 18 / 13 | wis | `on_decay_nearby` (algo apodrece) | domínio (subclasse) define a decadência | **Transformação** — debuff por domínio (bio/alma/inorg) |
| **Arcanista Cinzento** | dist · manipula | 22 / 20 / 11 | int | `on_channel` (canalizar) | `boiler` (Entropia sem vazão estoura em auto-dano) | **Dependência** — sem instrumento + Carga alta, custo dobra |
| **Médico de Campo** | suporte/cura · nega | 28 / 16 / 14 | int | `on_ally_suffer` (aliado sofre) | pode gastar Entropia p/ purgar Carga de aliado | **Recidiva** — oculta até estourar num colapso |

`level_gains.entropy`: Devoto 2 · Sangromante 3 · Corruptor 4 · Arcanista 6 · Médico 3.
Números calibrados na grade pós-playtest de 2026-08-02. Gatilhos passivos de
Devoto e Médico geram Carga só até 6 (`moderado`); `severo` exige outra escolha
abissal, em vez de surgir apenas por apanhar ou proteger um aliado.

### Subclasses (branches derivados de `known_abilities`)
- **Devoto:** Consagrado · Zeloso · Enlutado
- **Sangromante:** Exposto · Avaro · Silencioso
- **Corruptor:** Biologia · Alma · Inorgânica (= domínio do gatilho; `overrides.decay_kind`)
- **Arcanista:** Calibrado · Descoberto · Improvisador
- **Médico:** Cirurgião de Trincheira · Boticário · Cirurgião de Ferro

Ramo = branch da 1ª habilidade conhecida com branch (`progression.player_branch`);
ramo rival tranca para sempre (`eligible_abilities`). Zero campo de estado novo.

---

## 4. Config tipada (lida SÓ por Python — `combat_mechanics`)

| Bloco | Lido por | O que faz |
|---|---|---|
| `entropy_trigger` | `apply_entropy_trigger` | soma Entropia (clamp em max) + Carga (respeita `per_turn_cap`/round) |
| `special_rule` | `taunt_aggro_multiplier` / `apply_blood_leak` / `tick_boiler` / `reduce_ally_abyss` | a interação própria da classe |
| `abyss` | `abyss_tier` + `apply_rest` (Insônia) / `apply_scar` (Cicatriz) / `dependencia_cost` / `apply_transformacao` / `check_recidiva` | consequência por patamar |

`entropy_config(player)` faz o merge da config da classe com os `overrides` do branch —
**fonte única de números, nunca hardcode em callsite**. Campos transitórios
(prefixo `_`: `_entropy_trigger_turn`, `_blood_entropy`, `_cool_deadline`,
`_recidiva_fired`) não persistem no save.

### Pontos de acionamento no loop de combate
- `on_damage_taken` / `blood_leak` / `on_ally_suffer`: em `resolve_enemy_turn`, após o dano.
- `on_self_harm` / `on_channel` / Cicatriz / caldeira: em `resolve_player_action`
  (via `_entropy_on_ability_use`, após pagar o custo).
- `on_decay_nearby` / caldeira (tick) / Recidiva / reset por round: em `agents/combat.combat_node`.
- Insônia + mitigação por aliado: em `world_utils.apply_rest`.
- Dependência (custo): em `spend_resources`.

---

## 5. Habilidades antigas (schema aposentado no cutover)

`data/player_abilities.json` — cada habilidade: `resource_type: "Entropia"`,
`classes: ["<Classe>"]`, `branch`, `tier` (1–3), `level_req`, `requires` e
**`ability_kind`** ∈ `{active, passive, utility}` (ausente = active).
**Cura** = `damage_type: "Cura"` + fórmula positiva (`_is_healing`); efeitos usam
`effects: [{"kind": buff|debuff|dot|control, ...}]` (nunca `type`). Marcadores lidos
pela mecânica: `self_harm: <int>` (Sangromante), `peak: true` (Cicatriz),
`cools: true` (caldeira do Arcanista), `taunt: true`, `decay_kind`.

### Passivas na árvore (`ability_kind: "passive"`)
Efeito permanente ao aprender: `passive_effects` tipado, MESMO vocabulário de
`classes.json` + 5 triggers de Entropia/Carga. `combat_mechanics.player_passives`
= passivas da classe **+** aprendidas — lida em TODOS os callsites do jogador
(dano, AC, iniciativa, resist, retaliação, cura, custo). Inimigo segue em
`class_passives` (sem árvore). Cada subclasse tem ≥2; cada tronco ≥1.

| Trigger novo | Efeito | Aplicado em |
|---|---|---|
| `entropy_max_bonus` +delta | +max_entropy permanente | `progression.apply_choice` (aprendizado) |
| `entropy_on_kill` +amount | Entropia ao matar (sem Carga) | `combat_node` (`apply_entropy_on_kill`) |
| `entropy_cost_reduction` category/delta | −custo de Entropia da categoria (piso 1) | `spend_resources` |
| `charge_discount` delta | −Carga por ativação do gatilho (piso 0) | `apply_entropy_trigger` |
| `carga_embrace` stat/per_tier | patamar de Carga vira bônus (abraço do Abismo) | `damage_bonus` / `compute_player_combat_stats` |

### Utilitárias (`ability_kind: "utility"`)
Capacidade FORA de combate: `out_of_combat: {label, scope, prompt_hint}`
(`scope` ∈ social/investigation/detection/engineering/medical). O gate é
determinístico (conhece/não conhece); o storyteller recebe o bloco
`<CAPACIDADES_DO_HEROI>` (`utility_context_block`) e NARRA o uso — nunca concede
capacidade fora da lista. Cada tronco tem 2 (do doc-fonte); cada subclasse ≥1.
Passiva/utilitária ficam FORA dos chips de combate e do catálogo do parser
(`_allowed_ability_ids`); no HUD levam selo ✦ (passiva) / ⚒ (utilitária).

> ⚠️ Não execute `scripts/gen_classes_v2.py` como fluxo de autoria atual: o
> catálogo jogável é o de Cartas e segue `docs/CARTAS.md`.

---

## 6. Migração de saves antigos (R10)

`persistence._migrate_v2_to_v3` (schema v3): as 10 classes antigas mapeiam para as 5
(tabela em `_OLD_TO_NEW_CLASS`), backfilla `entropy`/`max_entropy`/`abyss_charge`,
zera mana/stamina, descarta `known_abilities` inexistentes e soma as iniciais da nova
classe. Saves ficam narrativamente órfãos (mesma política do corte 2.5b) — arquivar.

| Antiga → Nova |  |
|---|---|
| Cavaleiro da Vigília · Inquisidor da Cinza | **Devoto do Abismo** |
| Sombra da Corte · Sangromante | **Sangromante** |
| Pastor de Pragas · Guardião Selvagem | **Corruptor** |
| Arcanista Cinzento · Batedor das Fronteiras | **Arcanista Cinzento** |
| Médico de Campo · Sapador da Fuligem | **Médico de Campo** |
