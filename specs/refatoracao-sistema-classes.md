# SPEC — Refatoração do Sistema de Classes (Cinco Posturas diante do Abismo)

> **Status:** `in-progress` (2026-07-18 — **Etapa 1/8 DONE** e commitada:
> recurso Entropia (`entropy`/`max_entropy`/`abyss_charge` no `PlayerStats`,
> `_resource_field`→entropy, `apply_rest` recompõe integral; +5
> `test_classes_refactor`, 881 verdes). Etapa 2 (dados das 5 classes) PRONTA em
> `scripts/gen_classes_v2.py` (gera `classes.json`+`player_abilities.json`: 5
> classes × 3 branches, 41 habilidades, todos os blocos tipados; validado). **NÃO
> aplicada ainda** — o rollout troca as 10 classes antigas pelas 5 e derruba **41
> testes em 10 arquivos** (test_fase42 buffs=14, fase41/41b árvore=13,
> combat_heal=5, polish_sessao=3, onboarding=2, +4). Muitos testam PASSIVAS/
> habilidades das classes antigas (hp_as_mana, party_active AC) que o novo sistema
> SUBSTITUI por gatilhos de Entropia (etapas 3/4) — precisam ser reescritos, não
> só ajustados. Plano abaixo (§4) segue válido; falta 2–8 num passe focado.)
> **Criada:** 2026-07-17 · **Atualizada:** 2026-07-18
> **Depende de:** Fase 4.1 (`progression.py` — árvore/ramos) · 4.1b (árvores de Valoria) ·
> 4.2 (buffs/passivas tipadas) · 2.5b (traits raciais) — todas `done`
> **Desbloqueia:** rebalanceamento de combate · reautoria de conteúdo (onboarding, bestiário de aliados)
> **Fonte de design:** `VALORIA_spec_sistema_classes.md` (documento do usuário). Onde o
> documento marca `[A BALANCEAR]`, esta spec **propõe** um número inicial e o marca
> `[BALANCEAR]` — placeholder consciente, não valor final canonizado.
> **▶ RETOMAR:** o handoff operacional (comandos, inventário das 41 falhas, plano
> etapa a etapa) está em [docs/HANDOFF-sistema-classes.md](../docs/HANDOFF-sistema-classes.md).

---

## 1. Contexto & Objetivo

O sistema atual tem **10 classes** (`data/classes.json`, `class_themes.json`,
onboarding, 111 habilidades em 20 ramos da Fase 4.1b). O usuário decidiu
substituí-lo por **5 classes, cada uma com 3 subclasses**, ancoradas num conceito
único: cada classe é uma **postura filosófica diante do Abismo** (a entropia que
consome Valoria), não uma profissão. As 10 antigas saem do sistema ativo.

A mudança **não é cosmética**: introduz dois recursos novos, unificados para as
cinco classes:

1. **Entropia** — recurso de curto prazo (por combate), pool tipo mana/ki que
   **substitui a dupla mana+stamina do jogador**. Todas as habilidades custam
   Entropia. Recompõe **integral** no descanso.
2. **Carga do Abismo** — recurso de longo prazo (por campanha), acumulado pelo
   uso do *gatilho alternativo* de cada classe; não cai no descanso; tem
   consequência mecânica própria por classe.

Princípio de arquitetura (ROADMAP § "Mecânica é Python, não LLM"): **tudo aqui é
determinístico**. Gatilhos, conversões, patamares de Carga e consequências
resolvem em `combat_mechanics.py` / `world_utils.py` lendo **config tipada** em
`data/classes.json`. A LLM só narra o que o motor decidiu — nunca escolhe número,
nunca decide se um gatilho disparou.

Realidade do motor que esta spec explora (não reinventa):
- **Recurso de habilidade** é `cost` + `resource_type` → `combat_mechanics._resource_field`
  → `try_pay_ability_cost` deduz e arma cooldown. Entropia entra como novo
  `resource_field`.
- **Subclasse = branch DERIVADA de `known_abilities`** (`progression.player_branch`);
  ramo rival tranca para sempre (`eligible_abilities`). 3 subclasses = 3 branches.
  **Zero campo de estado novo para subclasse.**
- **Passivas** são triggers tipados em `CLASSES[classe]["passive_effects"]`
  (`combat_mechanics.class_passives`). Gatilho de Entropia, regra especial e
  consequência de Carga entram como **novos triggers tipados** + config dedicada.

## 2. Requisitos

- **R1 — Recurso Entropia.** `PlayerStats` ganha `entropy` / `max_entropy`. Toda
  habilidade do jogador custa Entropia (`resource_type: "Entropia"`).
  `try_pay_ability_cost` deduz de `entropy`. Sem Entropia → ação recusada
  (mesma mensagem-padrão de recurso insuficiente).
- **R2 — Entropia recompõe integral no descanso.** `apply_rest` seta
  `entropy = max_entropy` (diferente de HP, que segue em ~metade). Sem clima
  `rest_block`.
- **R3 — Recurso Carga do Abismo.** `PlayerStats` ganha `abyss_charge: int`
  (default 0). Não cai no descanso. É lido para consequências por patamar.
- **R4 — Gatilho alternativo por classe.** Cada classe tem UM gatilho que gera
  Entropia extra durante o combate (5 tipos, seção 3). **Toda ativação do gatilho
  soma `+charge_per` a `abyss_charge`** — automático, mesmo turno, nunca escolha
  separada. Entropia por descanso normal **nunca** gera Carga.
- **R5 — Regra especial por classe.** Cada classe tem uma regra de interação
  determinística própria (seção 3), lida em Python.
- **R6 — Consequência de Carga por classe.** Patamares discretos
  (`leve` 1–3 · `moderado` 4–6 · `severo` 7+ — proposta) disparam um efeito
  mecânico específico por classe (Insônia / Cicatriz / Transformação /
  Dependência / Recidiva).
- **R7 — Cinco classes com 3 subclasses cada.** `data/classes.json` reescrito:
  Devoto do Abismo · Sangromante · Corruptor · Arcanista Cinzento · Médico de
  Campo. Cada subclasse é um `branch`. `class_themes.json` e `onboarding.json`
  refletem as 5.
- **R8 — Árvore de habilidades das 5 classes.** `data/player_abilities.json`
  reautorado: ≥2 habilidades iniciais por classe + tronco/ramos por subclasse
  (tiers 1–4, o suficiente para jogar até ~nível 8). `resource_type: "Entropia"`.
  Ramos derivam subclasse via `player_branch` (mecânica da 4.1 intacta).
- **R9 — Médico reduz Carga alheia.** Única classe que pode gastar Entropia para
  **reduzir `abyss_charge` de outro personagem da party** — mecânica exclusiva.
- **R10 — Migração das 10 classes.** Saves com `class_name` antigo carregam sem
  crash (mapa determinístico antigo→nova classe + backfill de `entropy`/
  `max_entropy`/`abyss_charge`; `known_abilities` não-mapeáveis descartadas via
  `canonicalize_known_abilities`). Conteúdo das 10 antigas arquivado, não ativo.
- **R11 — HUD.** Frontend mostra Entropia (barra) e Carga do Abismo (indicador
  por patamar). Barras mana/stamina do jogador saem da ficha.
- **R12 — Resiliência.** Todo `with_structured_output` novo com guard
  (`isinstance`/try). Nenhum número vem do LLM sem validação em Python.

### Fora de escopo

- **Balanceamento final** dos números (pool, custos, taxas, patamares). Esta spec
  fixa proposta inicial jogável; ajuste fino é tarefa posterior (`[BALANCEAR]`).
- **Árvore completa até nível 20** por subclasse. Autora-se o suficiente para
  playtest (tiers 1–4); completar tiers 5+ é fast-follow.
- **Novos inimigos/aliados** desenhados para os gatilhos (ex.: encontros que
  fabriquem "aliado sofrendo" para o Médico). Reaproveita party/bestiário atuais.
- **Reescrever lore do Codex/timeline.** A palavra "Abismo" já é canônica no
  mundo; nada de re-indexar FAISS.

## 3. Design técnico

### 3.1. Recursos — schema de estado (`state.py`)

`PlayerStats` (TypedDict, `total=False`) ganha:

```python
    entropy: int          # pool de curto prazo (substitui mana/stamina do jogador)
    max_entropy: int
    abyss_charge: int      # Carga do Abismo — longo prazo, não cai no descanso
```

`mana`/`max_mana`/`stamina`/`max_stamina` **permanecem no TypedDict** (save
back-compat e inimigos usam), mas para jogadores novos ficam `0`. Entropia é o
recurso real. Inimigos (`EnemyStats`) **não mudam** — seguem em mana/stamina.

### 3.2. `data/classes.json` — nova forma (por classe)

Mantém os campos que `progression`/`character_creator` já leem (`base_stats`,
`level_gains`, `starting_abilities`, `starting_equipment`, `passive`,
`passive_effects`, `branches`) e **adiciona** os blocos de recurso. Exemplo real
(Devoto do Abismo):

```json
{
  "Devoto do Abismo": {
    "description": "Ama o Abismo: avança na direção da incerteza porque a deseja.",
    "role": "tank",
    "posture": "ama",
    "guide_quote": "Vocês seguram a linha com medo. Eu seguro porque quero que ele me escolha primeiro.",
    "passive": "Convite: provocações escalam com a Entropia acumulada no combate.",
    "base_stats": {
      "hp": 38, "entropy": 14, "mana": 0, "stamina": 0, "defense": 16,
      "attributes": { "str": 16, "dex": 10, "con": 16, "int": 8, "wis": 12, "cha": 14 }
    },
    "level_gains": { "hp": 7, "entropy": 2, "mana": 0, "stamina": 0 },
    "starting_abilities": ["provocacao_do_abismo", "encaixe_do_golpe"],
    "entropy_trigger": {
      "kind": "on_damage_taken",
      "damage_divisor": 4,     "min_gain": 1,
      "charge_per": 1,         "per_turn_cap": 1,
      "note": "[BALANCEAR] +1 Entropia por 4 de dano recebido; +1 Carga/turno"
    },
    "special_rule": {
      "kind": "taunt_scales_with_entropy",
      "per_entropy": 0.05,     "cap": 0.6,
      "note": "[BALANCEAR] eficácia de aggro sobe 5%/ponto de Entropia, teto 60%"
    },
    "abyss": {
      "consequence": "insonia",
      "thresholds": { "leve": 1, "moderado": 4, "severo": 7 },
      "hidden": false, "mitigable_by_ally": true,
      "params": { "rest_penalty": { "leve": 0.1, "moderado": 0.25, "severo": 0.5 } }
    },
    "branches": {
      "consagrado": { "name": "O Consagrado", "identity": "Ritualiza o amor ao Abismo; marca o corpo antes da luta." },
      "zeloso":     { "name": "O Zeloso", "identity": "Amor possessivo; puxa aggro por ciúme." },
      "enlutado":   { "name": "O Enlutado", "identity": "Amou quem o Abismo levou; tom melancólico." }
    },
    "starting_equipment": ["espada_gasta", "escudo_amassado", "pocao_cura"]
  }
}
```

**Configs tipadas por classe** (consumidas só por Python):

| Bloco | Campos | Lido por |
|---|---|---|
| `entropy_trigger` | `kind`, params, `charge_per`, `per_turn_cap` | `combat_mechanics.apply_entropy_trigger` |
| `special_rule` | `kind` + params | `combat_mechanics` (ponto específico por kind) |
| `abyss` | `consequence`, `thresholds`, `hidden`, `mitigable_by_ally`, `params` | `combat_mechanics.abyss_tier` + consumidores |

`entropy_trigger.kind` ∈ `{on_damage_taken, on_self_harm, on_decay_nearby, on_channel, on_ally_suffer}`.
`abyss.consequence` ∈ `{insonia, cicatriz, transformacao, dependencia, recidiva}`.

**Subclasse muda config?** Sim, via `branches[key].overrides` (merge raso sobre a
config da classe quando `player_branch` resolve). Ex.: Corruptor domínio define
qual decomposição conta:

```json
"branches": {
  "biologia":   { "name": "Biologia",   "overrides": { "entropy_trigger": { "decay_kind": "flesh" } } },
  "alma":       { "name": "Alma",       "overrides": { "entropy_trigger": { "decay_kind": "morale" } } },
  "inorganica": { "name": "Inorgânica", "overrides": { "entropy_trigger": { "decay_kind": "gear" } } }
}
```

### 3.3. As cinco classes (config mecânica — proposta inicial `[BALANCEAR]`)

Todos os números abaixo são **proposta jogável, não final**.

| Classe | Papel | Postura | base HP / Entropia / Def | Gatilho (`kind`) | Regra especial | Carga (`consequence`) |
|---|---|---|---|---|---|---|
| **Devoto do Abismo** | tank | ama | 38 / 14 / 16 | `on_damage_taken` (+1/4 dano) | aggro escala c/ Entropia | **insonia** — descanso rende menos; mitigável por aliado |
| **Sangromante** | dano corpo-a-corpo | negocia | 26 / 16 / 12 | `on_self_harm` (auto-dano vira Entropia) | acerto inimigo **vaza** fração da Entropia de sangue não gasta | **cicatriz** — hab. de pico reduz `max_hp` permanente; não mitigável |
| **Corruptor** | controle / DoT | trabalha junto | 28 / 18 / 13 | `on_decay_nearby` (algo perto se desfaz) | domínio (subclasse) define o que conta como decadência | **transformacao** — debuff por domínio (bio/alma/inorg) |
| **Arcanista Cinzento** | dano/controle à distância | manipula | 22 / 20 / 11 | `on_channel` (usar hab. gera Entropia p/ a próxima) | Entropia não "vazada" em N turnos → instrumento estoura (auto-dano) | **dependencia** — sem instrumento + Carga alta, custo sobe/gate |
| **Médico de Campo** | suporte / cura | nega | 28 / 16 / 14 | `on_ally_suffer` (aliado toma dano/condição) | **pode gastar Entropia p/ reduzir Carga de aliado** | **recidiva** — invisível até estourar (gatilho de colapso oculto) |

`level_gains.entropy` proposto: Devoto 2 · Sangromante 3 · Corruptor 4 ·
Arcanista 6 · Médico 3 (frágeis à distância acumulam pool maior; tanque menos).

Subclasses (todas via `branch`):
- **Devoto:** Consagrado · Zeloso · Enlutado
- **Sangromante:** Exposto · Avaro · Silencioso
- **Corruptor:** Biologia · Alma · Inorgânica (= domínio do gatilho)
- **Arcanista:** Calibrado · Descoberto · Improvisador
- **Médico:** Cirurgião de Trincheira · Boticário · Cirurgião de Ferro

### 3.4. Gatilhos de Entropia — assinaturas (`combat_mechanics.py`)

```python
def entropy_config(player: Dict, *, classes_db=None, abilities_db=None) -> Dict:
    """Merge da entropy_trigger/special_rule/abyss da classe com overrides do branch
    (player_branch). Fonte única de números — nunca hardcode em callsite."""

def apply_entropy_trigger(player: Dict, event: Dict, logs: List[str]) -> None:
    """Aciona o gatilho da classe se `event` casa com o kind. Soma Entropia
    (clamp em max_entropy) e Carga (charge_per, respeitando per_turn_cap por turno).
    `event` = {"kind": ..., "amount"?: int, "decay_kind"?: str, ...}. Muta player."""

def abyss_tier(player: Dict, *, classes_db=None) -> str:
    """'nenhum'|'leve'|'moderado'|'severo' a partir de abyss_charge + thresholds da classe."""
```

**Onde cada gatilho é acionado** (pontos já existentes no loop de combate):
- `on_damage_taken` (Devoto): dentro da resolução do ataque do inimigo ao jogador
  (após aplicar dano ao `player["hp"]`). `amount` = dano aplicado.
- `on_self_harm` (Sangromante): em `_apply_self_costs` quando o custo textual
  tira HP do conjurador (auto-dano deliberado). `amount` = HP pago.
- `on_decay_nearby` (Corruptor): no tick de DoT dos inimigos e em morte de inimigo;
  filtra por `decay_kind` do branch (flesh = DoT de veneno/fungo; morale = debuff
  mental aplicado; gear = corrosão de equipamento).
- `on_channel` (Arcanista): em `resolve_player_action` após pagar o custo de uma
  habilidade (canalizar). Também arma o timer de "vazão" da regra especial.
- `on_ally_suffer` (Médico): quando um membro da `party`/companheiro toma dano ou
  ganha condição no turno inimigo.

**Contador por turno** (`per_turn_cap`): usar campo transitório
`player["_entropy_trigger_turn"]` (contagem no turno atual, zerado no início do
turno do jogador) — não persiste no save (prefixo `_`, saneado no serialize).

### 3.5. Regras especiais — resolução (`combat_mechanics.py`)

- **Devoto `taunt_scales_with_entropy`:** habilidades de provocação leem
  `entropy_config().special_rule` → bônus na duração/DC do taunt =
  `min(cap, per_entropy * entropy)`. Determinístico.
- **Sangromante `blood_leak`:** ao jogador ser acertado, se houver Entropia
  marcada como "de sangue" não gasta, perde `leak_frac` dela. Rastreada em
  `player["_blood_entropy"]` (transitório), incrementada pelo gatilho
  `on_self_harm`, zerada ao gastar Entropia numa habilidade.
- **Corruptor:** sem regra numérica extra além do `decay_kind` (o domínio já é a
  regra); documentado como no-op mecânico separado.
- **Arcanista `boiler`:** `player["_uncooled_entropy"]` + `player["_cool_deadline"]`.
  Se passar o prazo sem gastar em habilidade marcada `cools: true`, aplica
  auto-dano (`overload_damage`) e zera. Config em `special_rule`.
- **Médico `heal_abyss`:** habilidade dedicada (`purga_da_carga`) chama
  `reduce_ally_abyss(target, amount)` gastando Entropia — ver R9.

### 3.6. Consequências de Carga

- **Insônia (Devoto):** `world_utils.apply_rest` lê `abyss_tier` + `params.rest_penalty`
  e reduz a fração de cura de HP no descanso. Se `mitigable_by_ally` e há aliado
  ativo na party, reduz `abyss_charge` em 1 por descanso ("alguém insistiu em ficar").
- **Cicatriz (Sangromante):** habilidades marcadas `peak: true` somam Carga e
  reduzem `max_hp` permanentemente (`scar_hp_loss` por uso). Irreversível.
- **Transformação (Corruptor):** por patamar, um debuff conforme `decay_kind`
  (bio: recebe +X% de DoT; alma: −save de vontade; inorg: −defense). Lido em
  `condition_modifiers`/aplicação de dano.
- **Dependência (Arcanista):** se `equipment.weapon` ausente **e** `abyss_tier ≥ moderado`,
  custo de Entropia das habilidades sobe (`no_instrument_cost_mult`) ou gate. Lido
  em `try_pay_ability_cost`.
- **Recidiva (Médico):** `abyss.hidden = true` → HUD não expõe número. Ao cruzar
  `severo`, dispara UMA vez um "colapso" (evento determinístico: condição debilitante
  forte + entrada de crônica). Flag `player["_recidiva_fired"]`.

### 3.7. R9 — Médico reduz Carga alheia

```python
def reduce_ally_abyss(medic: Dict, ally: Dict, amount: int) -> Tuple[bool, str]:
    """Gasta Entropia do Médico p/ reduzir abyss_charge do aliado. Só classe Médico.
    Retorna (ok, log). Determinístico; alvo é membro da party."""
```

### 3.8. `character_creator.py`

- Preencher `entropy`/`max_entropy` de `base_stats.entropy` (escala com nível como
  hp hoje: `base + gains.entropy*(level-1)`). `abyss_charge = 0`.
- `mana`/`stamina` do jogador → `0` (recurso morto para as 5 classes).
- `CLASS_ATTR_MAP` reescrito para as 5 classes (atributo primário: Devoto str,
  Sangromante dex, Corruptor wis, Arcanista int, Médico int).

### 3.9. `data/player_abilities.json` (R8)

Cada habilidade nova: `resource_type: "Entropia"`, `classes: ["<Classe>"]`,
`branch: <subclasse|null>`, `tier`, `level_req`, `requires`. Marcadores novos
opcionais lidos pela mecânica: `peak: true` (Sangromante — Cicatriz),
`cools: true` (Arcanista — vazão da caldeira), `self_harm: <int>` (auto-dano que
alimenta `on_self_harm`). Meta mínima: **≥2 iniciais + ≥1 por subclasse por tier
1–3** (≈ 5 classes × [2 + 3 subclasses × 3 tiers] ≈ 55 habilidades) para um
playthrough completo. As 111 antigas saem.

### 3.10. Migração (R10) — `persistence.py` `_MIGRATIONS`

Mapa antigo→nova classe (do doc, "Reaproveitamento"):

| Classe antiga | Nova classe |
|---|---|
| Cavaleiro da Vigília, Inquisidor da Cinza | Devoto do Abismo |
| Sombra da Corte, Sangromante | Sangromante |
| Pastor de Pragas, Guardião Selvagem | Corruptor |
| Arcanista Cinzento, Batedor das Fronteiras | Arcanista Cinzento |
| Médico de Campo, Sapador da Fuligem | Médico de Campo |

Migration nova (`schema_version` bump): se `class_name` ∈ antigas, mapeia; seta
`entropy=max_entropy` de `base_stats.entropy` da nova classe; `abyss_charge=0`;
roda `canonicalize_known_abilities` (descarta habilidades que não existem mais).
Saves ficam narrativamente órfãos (aceito, como pré-2.5b) — arquivar recomendado.

### 3.11. Frontend (R11)

- `PlayerStats` (TS `types.ts`) ganha `entropy`, `max_entropy`, `abyss_charge`,
  `abyss_tier`.
- `api.py` `/game/state` expõe os campos + `abyss_tier` (oculto se
  `abyss.hidden`: manda label vago, ex. `"?"`).
- `Hud.tsx` FichaTab: barra **Entropia** no lugar de mana/stamina; **Carga do
  Abismo** como chip por patamar (`leve/moderado/severo`), com tom crescente. Para
  o Médico (`hidden`), mostrar "—" ou um selo enigmático, sem número.

## 4. Plano passo a passo (TDD — testes primeiro)

### Etapa 1 — Recurso Entropia (núcleo)
1. **Testes** (`tests/test_classes_refactor.py`): `test_entropy_resource_field`
   asserta `_resource_field("Entropia") == "entropy"`; `test_pay_from_entropy`
   deduz de `entropy`; `test_rest_refills_entropy_full` asserta
   `entropy == max_entropy` pós-`apply_rest` (HP segue ~metade).
2. **Impl:** `_resource_field` + `try_pay_ability_cost` (entropy); `apply_rest`
   refill integral de Entropia.
3. **Verificação:** `uv run pytest -k classes_refactor` verde.

### Etapa 2 — Dados das 5 classes
1. **Testes:** `test_five_classes_load` (exatamente 5 chaves esperadas);
   `test_each_class_three_branches`; `test_base_stats_have_entropy`;
   `test_onboarding_matches_classes` (anti-drift onboarding↔classes↔themes);
   `test_class_attr_map_covers_five`.
2. **Impl:** reescrever `classes.json`, `class_themes.json`, `onboarding.json`
   (bloco `classes`), `character_creator.CLASS_ATTR_MAP` + preenchimento de
   Entropia; `mana/stamina` do jogador → 0.
3. **Verificação:** suíte de criação verde.

### Etapa 3 — Gatilhos de Entropia + Carga
1. **Testes:** um por `kind` — `test_devoto_entropy_on_damage`,
   `test_sangromante_entropy_on_self_harm`, `test_corruptor_entropy_on_decay`
   (com `decay_kind` do branch), `test_arcanista_entropy_on_channel`,
   `test_medico_entropy_on_ally_suffer`; `test_trigger_adds_charge` e
   `test_per_turn_cap`; `test_rest_entropy_never_adds_charge`.
2. **Impl:** `entropy_config`, `apply_entropy_trigger`, `abyss_tier` + pontos de
   acionamento no loop de combate (seção 3.4).
3. **Verificação:** verde.

### Etapa 4 — Regras especiais + consequências de Carga
1. **Testes:** `test_devoto_taunt_scales`; `test_sangromante_blood_leak`;
   `test_arcanista_boiler_overload`; `test_medico_recidiva_hidden_then_collapse`;
   `test_insonia_reduces_rest` (+ mitigação por aliado);
   `test_cicatriz_reduces_max_hp`; `test_dependencia_raises_cost`;
   `test_transformacao_debuff_by_domain`; `test_reduce_ally_abyss` (só Médico).
2. **Impl:** seções 3.5–3.7.
3. **Verificação:** verde.

### Etapa 5 — Árvore de habilidades (subclasses)
1. **Testes:** `test_abilities_use_entropy` (nenhuma player ability em
   mana/stamina); `test_branch_derivation_per_class` (3 ramos por classe,
   `player_branch` resolve); `test_rival_branch_locked`; `test_starting_abilities_exist`.
2. **Impl:** reautorar `player_abilities.json` (seção 3.9). Sem re-index FAISS
   (habilidades não vão pro RAG).
3. **Verificação:** verde.

### Etapa 6 — Migração + limpeza
1. **Testes:** `test_old_save_loads` (save com classe antiga carrega, sem crash);
   `test_old_class_maps_to_new`; `test_backfill_entropy_fields`;
   `test_no_old_class_in_active_data` (grep-assert: nenhuma das 10 antigas em
   `classes.json`/`class_themes.json`/`onboarding.json`).
2. **Impl:** `_MIGRATIONS` + arquivar `docs/CLASSES*.md` (mover p/ `docs/legacy/`
   ou marcar arquivado); atualizar `playtest/profiles.py`/`runner.py` (classes dos
   perfis).
3. **Verificação:** verde.

### Etapa 7 — Frontend
1. **Impl:** `types.ts` + `api.py` view + `Hud.tsx` (barra Entropia, chip Carga,
   caso `hidden` do Médico). `cd web && npm run build` verde.
2. **Verificação:** smoke de UI manual (barra Entropia enche no descanso; chip de
   Carga muda de patamar).

### Etapa 8 — Suíte + smoke real + docs
1. `uv run pytest` verde (suíte completa offline).
2. Smoke real (seção 6).
3. Atualizar `ESTADO_ATUAL.md` + `ROADMAP.md` + `CLAUDE.md` (§ classes/recursos).

## 5. Critérios de aceite

- [ ] R1–R12 implementados e cobertos por teste.
- [ ] `data/classes.json` tem exatamente as 5 classes, 3 branches cada, com
  `entropy_trigger`/`special_rule`/`abyss` tipados.
- [ ] Nenhuma habilidade do jogador usa mana/stamina (todas Entropia).
- [ ] Gatilho gera Entropia **e** Carga; descanso recompõe Entropia integral e
  **nunca** gera Carga.
- [ ] Cada consequência de Carga tem efeito mecânico verificável por patamar.
- [ ] Médico é a única classe que reduz Carga alheia.
- [ ] Saves com classe antiga carregam (migração) — teste verde.
- [ ] Nenhuma das 10 classes antigas nos dados ativos.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] `cd web && npm run build` verde.
- [ ] Guard de FallbackLLM em todo `with_structured_output` novo.

## 6. Smoke test com LLM real

(DeepSeek primário; dentro do orçamento — sem structured output novo pesado, mas
o `character_creator` usa SMART: validar mapeamento de campo, que o MockLLM esconde.)

1. `/game/new` criando um **Sangromante** — conferir ficha com `entropy/max_entropy`
   preenchidos, `mana/stamina = 0`, `abyss_charge = 0`; narração coerente.
2. Entrar em combate, usar habilidade de auto-dano — conferir no log que
   `on_self_harm` somou Entropia **e** Carga; barra reflete.
3. Descansar — Entropia volta ao máximo, Carga **não** cai.
4. Criar um **Devoto** e apanhar — `on_damage_taken` soma Entropia/Carga; após
   descanso, Insônia reduz a cura de HP (patamar leve).
5. Confirmar que um save de classe antiga (fixture) carrega mapeado para a nova
   classe sem exceção.

## 7. Riscos & compatibilidade

- **Saves antigos:** carregam via migração, mas ficam órfãos de mecânica (recurso
  e árvore diferentes) — mesma política do corte 2.5b (arquivar). Novos jogos
  intactos.
- **MockLLM esconde mapeamento:** `character_creator` (SMART) precisa de validação
  real (seção 6) — o mock sempre devolve Pydantic válido.
- **Escopo de conteúdo:** reautorar a árvore é a maior fatia; a spec limita a
  tiers 1–4 para virar `done` jogável. Tiers 5+ ficam de fast-follow explícito.
- **Party rara em solo:** gatilho do Médico (`on_ally_suffer`) e mitigação do
  Devoto dependem de aliados; em jogo solo disparam pouco — aceitável (descanso
  recompõe Entropia). Marcar em balanceamento.
- **Quota/latência:** sem impacto (nada de RAG novo; mesma quantidade de chamadas
  ao LLM por turno).

## 8. Decisões em aberto (para a aprovação)

Resolvidas por padrão sensato; sinalizadas para o usuário confirmar na revisão:

1. **Entropia substitui mana+stamina (recomendado)** vs. terceiro pool paralelo.
   Proposta: substitui (doc trata Entropia como o pool único das 5 classes).
2. **Carga em patamares discretos (recomendado)** vs. escala contínua. Proposta:
   discretos (leve/moderado/severo) — mais fácil de comunicar e implementar.
3. **Todos os números `[BALANCEAR]`** desta spec são proposta inicial jogável, não
   canonizados; fecham em tarefa de balanceamento após playtest.
4. **Ordem de implementação:** as 4 classes "não-Médico" primeiro, Médico por
   último (depende da Carga alheia estar viva), conforme o doc-fonte.
