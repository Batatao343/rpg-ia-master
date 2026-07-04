# SPEC — Fase 4.1: Progressão — XP, level up e árvore de habilidades

> **Status:** `in-progress` — **Etapas 1–7 implementadas** (2026-07-04, suíte 357
> verde + smoke_api ok); falta SÓ o smoke com LLM real (§6, pendente de quota)
> para virar `done`.
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** Fase 2.6 (structured events, `done`) · Fase 3.1 (crônica, `done`)
> **Desbloqueia:** Fase 4.1b (conteúdo das árvores), 4.2 (buffs mecânicos), 4.5 (party), 4.6 (orçamento de encontro por nível)
>
> **Ordem de execução acoplada à 4.1b:** Etapas 1–2a desta spec (motor + schema +
> validadores) → **spec 4.1b inteira** (autoria das árvores lore-driven — executor
> obrigatório: modelo **Fable**) → Etapas 3–7 desta spec. Os testes de conteúdo
> (árvore completa por classe) moram na 4.1b.

---

## 1. Contexto & Objetivo

Auditoria de 2026-07-03: `XP_TABLE` (gamedata.py:141, 20 níveis) não tem **nenhum
consumidor** — `player.xp` nasce 0 e nunca incrementa. Não existe progressão no jogo.
Além disso, `known_abilities` guarda **texto livre** (inclusive a string
`"[Passiva] ..."` injetada pelo character_creator), casado por substring em
`combat.py:_ability_catalog_for` — frágil e impossível de validar. As 45 habilidades
de `player_abilities.json` são flat: sem dono (classe), sem tier, sem pré-requisito.

Esta spec entrega o ciclo completo: **matar/completar objetivos → XP determinístico →
level up determinístico → escolha de habilidade nova na árvore da classe**.

Princípio (ROADMAP § Princípios / CLAUDE.md): **mecânica é Python, não LLM**. O LLM
nunca decide valor de XP, nem ganho de status, nem o que pode ser aprendido. Zero
structured output novo nesta spec — nenhum guard de FallbackLLM necessário (padrão
da Fase 3.4: eventos gerados 100% em Python).

## 2. Requisitos

- **R1** — XP por kill é determinístico, calculado em Python no fim do round de
  combate a partir do `type` do inimigo (bestiário): `minion=50`, `elite=200`,
  `boss=1000` (case-insensitive; ausente → minion). Inimigos que **fugiram** não dão XP.
- **R2** — XP por progresso narrativo: beat concluído (`beat_completed`) = 150 XP;
  `quest_completed` aplicado no pipeline 2.6 = 200 XP. Sempre Python, nunca proposto
  pelo LLM.
- **R3** — Ao cruzar limiar da `XP_TABLE`, level up determinístico: HP/mana/stamina
  máximos sobem conforme `level_gains` da classe (`classes.json`); cura o valor ganho
  (não full heal). Multi-level em um ganho só (ex.: boss no nível 1) processa todos os
  níveis em sequência.
- **R4** — Nível par concede **1 ponto de atributo** (alocação do jogador); todo
  nível concede **1 escolha de habilidade** dentre as elegíveis da árvore da classe.
  Escolhas pendentes ficam em `player["pending_choices"]` até o jogador decidir —
  o jogo continua jogável com escolha pendente (não bloqueia o loop).
- **R5** — `player_abilities.json` ganha campos de árvore: `classes` (lista de nomes
  de classe, ou `["all"]`), `branch` (id do ramo, `null`/ausente = tronco comum),
  `tier` (1–3), `level_req` (int), `requires` (lista de ids), `effects` (lista tipada
  opcional — ver §3). Elegível = classe do jogador (ou `all`) ∧ nível ≥ `level_req` ∧
  `requires` ⊆ conhecidas ∧ não conhecida ∧ **regra de ramo (R5b)**. O CONTEÚDO das
  árvores (ramos por classe, habilidades novas) é a spec **4.1b** — aqui só schema,
  validadores e motor.
- **R5b** — **Ramos são subclasses mutuamente exclusivas:** aprender a primeira
  habilidade com `branch` X trava as habilidades de qualquer outro ramo da mesma
  classe (inelegíveis para sempre nesta ficha). A subclasse é **derivada** das
  conhecidas (`progression.player_branch(player)`), sem campo novo de estado. Tronco
  comum (`branch` ausente) nunca trava.
- **R6** — `known_abilities` passa a conter **apenas ids canônicos** de
  `player_abilities.json`. Character creator seta ids iniciais de
  `classes.json → starting_abilities` (novo campo) + `ataque_basico`. A string
  `"[Passiva] ..."` sai de `known_abilities` (a passiva já vive em
  `CLASSES[class]["passive"]`; exibição busca lá).
- **R7** — `combat.py:_ability_catalog_for` e o gate de uso passam a casar por **id
  exato** (`aid in known_abilities`), fim do substring matching. Habilidade não
  conhecida e não universal → `is_allowed=False` determinístico (não depende do LLM
  respeitar o catálogo).
- **R8** — Saves antigos carregam: backfill em `persistence.load_game_state` converte
  `known_abilities` texto-livre → ids (match por nome, case/acento-insensitive);
  não-mapeáveis são descartados; garante `ataque_basico`; remove `"[Passiva] ..."`;
  `pending_choices` default `[]`.
- **R9** — Level up gera evento `level_up` no `event_log` (Python puro, padrão
  `reputation_changed` da 3.4) e vira milestone da crônica: "Alcançou o nível N."
- **R10** — API: `GET /game/state` expõe `xp`, `xp_next_level`, `pending_choices`;
  novo `POST /game/levelup` aplica escolha (`{choice_id, ability_id | attr}`) com
  validação server-side (escolha inexistente/inelegível → 400, estado intocado).
  CLI (`game_engine.py`): prompt de escolha ao detectar `pending_choices` no fim do
  turno. Frontend: tela de level up (modal) + visualização da árvore da classe.

### Fora de escopo

- **Autoria das árvores** (ramos, âncoras de lore, ~80 habilidades novas) — spec
  **4.1b**, executor obrigatório: modelo Fable.
- **Classes novas** (ROADMAP menciona "mais classes" — fica para spec própria).
- Respec/desaprender habilidade; multiclasse.
- Efeito mecânico de buffs/passivas (Fase 4.2 — aqui passiva continua texto).
- XP para companions (Fase 4.5).
- Rebalancear custos/dano das 45 habilidades existentes.

## 3. Design técnico

### Arquivos novos

- **`progression.py`** (raiz, 100% puro, sem LLM — irmão de `combat_mechanics.py`):

```python
XP_BY_TIER = {"minion": 50, "elite": 200, "boss": 1000}
XP_PER_BEAT = 150
XP_PER_QUEST = 200

def xp_for_kills(dead_enemies: list[dict]) -> int: ...
    # soma XP_BY_TIER[e.get("type","minion").lower()], desconhecido -> minion

def xp_to_next(level: int) -> int | None: ...
    # limiar do próximo nível na XP_TABLE; None se level >= 20

def grant_xp(player: dict, amount: int) -> tuple[dict, list[dict]]: ...
    # devolve (player_atualizado, level_up_events)
    # processa multi-level; por nível: aplica level_gains da classe,
    # cura o delta de max_hp/max_mana/max_stamina, appenda pending_choices

def player_branch(player: dict) -> str | None: ...
    # subclasse derivada: branch da primeira habilidade conhecida com branch
    # (None = ainda no tronco). Sem campo novo de estado.

def eligible_abilities(player: dict) -> list[str]: ...
    # ids elegíveis na árvore (R5 + R5b lock de ramo);
    # usa ABILITIES + class_name/level/known + player_branch

def apply_choice(player: dict, choice_id: str, *,
                 ability_id: str | None = None, attr: str | None = None
                 ) -> tuple[dict, str | None]: ...
    # valida e consome UMA pending_choice; devolve (player, erro|None)
    # attr usa chaves curtas (str/dex/...) via combat_mechanics.normalize_attr
```

- **`tests/test_fase41.py`** — suíte da fase (ver plano).

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `state.py` | `PlayerStats` ganha `pending_choices: List[Dict]` (docstring do formato) |
| `data/classes.json` | cada classe ganha `level_gains: {hp, mana, stamina}`, `starting_abilities: [ids]` e `branches: {id: {name, theme, lore_ref?, identity, description}}` (conteúdo: spec 4.1b) |
| `data/player_abilities.json` | cada habilidade ganha `classes`, `branch`, `tier`, `level_req`, `requires`, `effects` opcional (conteúdo: spec 4.1b) |
| `agents/combat.py` | fim de round: `xp_for_kills(dead)` → `grant_xp`; catálogo/gate por id exato (R7) |
| `agents/storyteller.py` | `beat_done` → `grant_xp(player, XP_PER_BEAT)` |
| `services/event_processor.py` | `quest_completed` aplicado → XP (retorno para o nó chamador aplicar no player, mesmo padrão dos milestones) |
| `services/chronicle.py` | `level_up` entra em `CHRONICLE_EVENT_TYPES` + template "Alcançou o nível {n}." |
| `services/structured_outputs.py` | **nada** — `level_up` NÃO entra nos tipos propostos pelo LLM (validator rejeita se propuser) |
| `character_creator.py` | `known_abilities` = `starting_abilities` + `ataque_basico`; remove `"[Passiva] ..."` |
| `persistence.py` | backfill R8 no load |
| `api.py` | `xp_next_level`/`pending_choices` no state; `POST /game/levelup` |
| `game_engine.py` | prompt CLI de level up |
| `web/src/...` | modal LevelUp + `AbilityTree` (aba ou seção da ficha) |

### Formato de dados

`pending_choices` (no player, persiste no save):

```json
[
  {"id": "lvl2-ability", "level": 2, "kind": "ability"},
  {"id": "lvl2-attr",    "level": 2, "kind": "attribute"}
]
```

`classes.json` (exemplo real — Cavaleiro da Vigília; `branches` autorados na 4.1b):

```json
"level_gains": {"hp": 7, "mana": 0, "stamina": 3},
"starting_abilities": ["investida_do_touro", "pele_de_ferro"],
"branches": {
  "muralha": {"name": "...", "theme": "<pilar + postura (obrigatório)>",
              "lore_ref": "<opcional, resolve no grafo>",
              "identity": "...", "description": "..."}
}
```

`player_abilities.json` (exemplo real; `branch`/`effects` autorados na 4.1b):

```json
"estocada_renal": {
  "name": "Estocada Renal",
  "classes": ["Batedor das Fronteiras", "Sombra da Corte"],
  "branch": null,
  "tier": 1, "level_req": 2, "requires": [],
  "effects": [],
  ...campos existentes inalterados...
}
```

`effects` (tipado — inerte até a Fase 4.2, que o torna mecânico; definir AQUI evita
retrabalho de formato na autoria da 4.1b):

```json
{"kind": "buff" | "debuff" | "dot" | "control" | "heal",
 "stat": "damage" | "ac" | "attack" | "save" | null,
 "delta": 5, "duration": 3}
```

Evento `level_up` (gerado em `grant_xp`, appendado a `pending_world_events` pelo nó
que chamou — combat/storyteller — e aplicado pelo pipeline 2.6 normal; `apply_event`
já tem fallthrough no-op para tipo sem handler de projection):

```json
{"type": "level_up", "actor_id": "player", "target_id": "player",
 "payload": {"new_level": 2}}
```

### Decisões

1. **Escolha não bloqueia o loop** — level up no meio do combate não pausa o jogo;
   escolha fica pendente e o jogador resolve quando quiser (CLI pergunta no fim do
   turno; frontend mostra badge/modal). Evita estado "travado esperando input" na API
   stateless.
2. **`type` do bestiário É o tier** — dado já existe (Minion/Elite/BOSS, 84 entradas);
   nenhum campo novo no bestiário.
3. **Cura só o delta no level up** (não full heal) — level up em combate não vira
   botão de cura grátis.
4. **`ataque_basico` e `improvisado`** continuam universais (`classes: ["all"]`,
   `level_req: 1`).
5. **Subclasse = ramo, derivada e irreversível** — sem campo `subclass` no estado
   (deriva de `known_abilities`, à prova de save antigo); lock na primeira habilidade
   de ramo torna a escolha um momento narrativo real (a 4.1b ancora cada ramo em
   fação/tradição do Codex — escolher ramo = escolher um lado do mundo).
6. **Schema aqui, conteúdo na 4.1b** — motor e autoria têm perfis diferentes
   (engenharia vs escrita criativa com pesquisa de lore); a 4.1b exige executor
   Fable, esta não.

## 4. Plano passo a passo

### Etapa 1 — Núcleo `progression.py` (TDD)

1. **Testes** (`tests/test_fase41.py`):
   - `test_xp_for_kills_por_tier` — minion/elite/boss/BOSS/ausente somam certo
   - `test_grant_xp_sem_level` — xp acumula, nível não muda, sem pending_choices
   - `test_grant_xp_level_up` — cruza 300: level 2, max_hp += gains, hp += delta,
     pending_choices = [ability] (nível par também attr)
   - `test_grant_xp_multi_level` — 1000 XP no nível 1 → processa 2 e 3 em sequência
   - `test_grant_xp_nivel_20_cap` — no cap, xp acumula mas não sobe
   - `test_level_up_event_gerado` — level_up event no retorno com payload correto
2. **Implementação:** `progression.py` completo.
3. **Verificação:** `uv run pytest tests/test_fase41.py` verde.

### Etapa 2a — Schema da árvore + validadores + curvas (SEM conteúdo)

1. **Testes:** `test_schema_arvore` — toda habilidade tem `classes`/`tier`/`level_req`/
   `requires` válidos, `requires` referencia ids existentes e sem ciclo, `branch`
   declarado existe em `branches` da classe; `test_starting_abilities_validas` — ids
   existem e têm `level_req` 1; `test_level_gains_presentes` — 10 classes com
   `level_gains` numérico; `test_effects_tipado` — `effects` (quando presente) segue
   o schema.
2. **Implementação:** `level_gains` + `starting_abilities` em `classes.json`;
   campos default (`classes: ["all"]` provisório, `branch: null`, `effects: []`)
   nas 45 habilidades existentes só para o schema validar.
3. **Verificação:** suíte verde.

### Etapa 2b — CONTEÚDO das árvores → **executar spec 4.1b** (modelo Fable)

Gate: 4.1b `done` (10 classes × 2 ramos, ~120 habilidades, testes de conteúdo
verdes) antes de seguir para a Etapa 3.

### Etapa 3 — Elegibilidade + escolha

1. **Testes:** `test_eligible_filtra_classe_nivel_prereq`;
   `test_lock_de_ramo` (aprendeu ramo A → ramo B inelegível; tronco segue elegível);
   `test_player_branch_derivada` (None no tronco; id do ramo após primeira);
   `test_apply_choice_ability` (consome pending, adiciona id);
   `test_apply_choice_attr` (chave curta, +1);
   `test_apply_choice_invalida` (id inexistente/inelegível/de outro ramo → erro,
   player intocado).
2. **Implementação:** `player_branch` / `eligible_abilities` / `apply_choice`.

### Etapa 4 — Ids canônicos (R6/R7/R8)

1. **Testes:** `test_creator_ids_canonicos` (mock: known_abilities ⊆ ABILITIES, sem
   "[Passiva]"); `test_catalogo_por_id_exato` (habilidade de outra classe não entra);
   `test_gate_uso_deterministico` (id não conhecido → is_allowed False);
   `test_backfill_save_antigo` (save com texto livre + "[Passiva] X" carrega → ids).
2. **Implementação:** `character_creator.py`, `combat.py`, `persistence.py`.
3. **Atenção:** `tests/` existentes que criam player com `known_abilities` texto
   livre podem precisar de ajuste — rodar suíte completa.

### Etapa 5 — Hooks de XP no grafo

1. **Testes:** `test_combat_kill_da_xp` (combate determinístico mata minion → xp+50);
   `test_fugitivo_nao_da_xp`; `test_beat_da_xp` (LLM controlado com
   `beat_completed=True`, padrão de `test_mvp.py:147`); `test_quest_da_xp`
   (pipeline 2.6 com quest_completed); `test_level_up_vira_milestone` (chronicle).
2. **Implementação:** hooks em `combat.py`, `storyteller.py`, `event_processor.py`,
   `chronicle.py`; validator rejeita `level_up` proposto pelo LLM.

### Etapa 6 — API + CLI

1. **Testes:** `test_state_expoe_xp_e_pending`; `test_levelup_endpoint_aplica`;
   `test_levelup_endpoint_invalido_400`.
2. **Implementação:** `api.py`, `game_engine.py`.
3. **Verificação:** `bash scripts/smoke_api.sh`.

### Etapa 7 — Frontend

1. Modal de level up (escolha de habilidade elegível + alocação de atributo) +
   visualização da árvore da classe organizada por **ramo** (tronco + 2 ramos lado a
   lado; estados: conhecida/elegível/bloqueada-por-nível/**trancada-por-ramo-rival**).
   Nome e lore do ramo (`branches` da classe) visíveis — a escolha de subclasse tem
   que se apresentar como decisão narrativa, não checkbox.
2. **Verificação:** `npm run build` ok; jogo manual no MockLLM sobe de nível e
   tranca ramo rival.

## 5. Critérios de aceite

- [ ] Matar inimigo dá XP visível no HUD; beat/quest concluídos dão XP
- [ ] Cruzar 300 XP sobe para nível 2, máximos sobem conforme a classe, crônica registra
- [ ] Escolha de habilidade aparece (CLI e web), só lista elegíveis, e a habilidade
      escolhida funciona em combate no turno seguinte
- [ ] Aprender habilidade de um ramo tranca o ramo rival (subclasse); tronco comum
      segue disponível
- [ ] Spec 4.1b `done` (árvores lore-driven autoradas por Fable) — gate da Etapa 3
- [ ] `known_abilities` só contém ids canônicos; save antigo (texto livre) carrega e joga
- [ ] LLM propondo `level_up` em `proposed_events` é rejeitado pelo validator
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A — zero structured output novo (verificar que continua zero)
- [ ] Saves antigos continuam carregando
- [ ] `ESTADO_ATUAL.md` + `ROADMAP.md` atualizados

## 6. Smoke test com LLM real

1. `/game/new` → matar 1 inimigo minion → conferir XP no state (+50) e narração coerente.
2. Forçar beat concluído (jogar o objetivo do beat) → XP +150 e crônica com milestone.
3. Acumular até nível 2 → `POST /game/levelup` escolhendo habilidade → usar a
   habilidade nova em combate real (parser Gemini deve mapear a fala para o id novo —
   ponto onde MockLLM esconderia bug de catálogo).
4. Carregar um save pré-4.1 real → jogar 1 turno de combate sem crash.

(≈ 6–8 requests, dentro da quota de 20/dia.)

## 7. Riscos & compatibilidade

- **Saves antigos:** backfill R8 obrigatório; risco maior é habilidade de flavor não
  mapear para id — mitigação: descartar silenciosamente e garantir `ataque_basico`
  (jogador antigo perde flavor text, não funcionalidade — nada dele funcionava
  mecanicamente antes).
- **MockLLM:** devolve `CombatAction` válida — gate determinístico do R7 protege
  contra id alucinado tanto no mock quanto no real.
- **Quota/latência:** zero requests novos por turno (tudo Python).
- **Testes existentes:** fixtures com `known_abilities` texto livre (`test_mvp`,
  `test_fase0`, `test_combat_heal`...) podem quebrar na Etapa 4 — ajustar junto.
- **Balanceamento:** valores (50/200/1000/150/200, curvas por classe) são chute
  inicial deliberado; ajustar depois do playtest é mudar constante, não arquitetura.
