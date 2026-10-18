# SPEC-232 — Motor de conflito: modificadores de condição, passivas/Virtudes/Reações inertes, custo de Carta, Guarda, DoT × armadura

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-231 `done` (mesmos arquivos de combate) · absorve a SPEC-199 R12 (alvo default de carta benéfica) junto com `_default_card_target` (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-205, SPEC-212; balanceamento das classes (SPEC-049 `[BALANCEAR]`) (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-02-05, 02-06, 02-09, 02-10, 02-11, 02-13, 02-14, 02-15, 02-19, 02-20 (`achados/02-combate.md`)
> **EXECUTOR_MODEL:** `Sol` (≡ Opus) — regressão de spec `done` (SPEC-047 árvore rica, conflito-02/06/14) com decisão de arquitetura (onde as passivas vivem após o cutover)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — motor determinístico; o harness de balanceamento (SPEC-049) é remedido após a correção

---

## 1. Contexto & Objetivo

O cutover do motor de conflitos (conflito-13) deixou **mecânica declarada nos dados sem consumidor no motor** —
o mesmo padrão dos 3 bugs da SPEC-050, mas em escala maior. Reproduções executadas pelo orquestrador
(`combate/r4.py`, `r2.py`) e leituras confirmadas no HEAD `d6af933`:

- [F] **Condições tipadas não afetam rolagens** — `services/conflict_turn.py:354-362` cria condições `{stat:
  attack|ac|damage|protection|advantage, delta}`; `combat_mechanics.condition_modifiers` (`:233`) as agrega, mas os
  únicos consumidores são `api.py:3523` (HUD) e `inventory.py:255` (save de item). `conflict_resolution.resolve_attack`
  (`:135-170`), `compute_esquiva` (`:47-49`) e `_damage_from` ignoram. Repro: 200 ataques, mesmo seed — base
  `(138 acertos, 2646)`, `attack +20` `(138, 2646)`, `ac +20 no alvo` `(138, 2646)`. Mortos por tabela: buffs/debuffs de
  ≈38 Cartas ativas, Medo (−2), Colapso da Recidiva (−4), Transformação do Corruptor, consumíveis de buff.
- [F] **Passivas de árvore, Cartas de Virtude e efeito de Reação sem consumidor** — `combat_mechanics.learned_passives`
  (`:194-200`) devolve `[]` ("resolvidas pelo motor de Cartas"), mas `services/cards.py` não trata `tipo in
  {"passiva","virtude"}`; `_open_reaction_window` (`conflict_orchestrator.py:569-572`) só concede `protected` — o
  `efeito` da Reação (contra_ataque/dano/cura/aplicar_condicao/empurrão, 27 cartas) nunca roda, mas a Entropia é
  debitada. Catálogo: 38 passivas + 6 Virtude + 27 reações sem efeito. O teste anti-órfão (`HANDLED_KINDS`) dá falsa
  segurança porque só compara nomes. **Regressão de SPEC-047 (`done`).**
- [F] **Custo/uso da Carta cobrado antes de validar alvo** — `conflict_turn.py:211-245` cobra Entropia e marca
  `used_this_scene` antes de `:247-259` detectar alvo inexistente/oculto. Repro: `arc_descarga` em `target_id="ghost"`
  → "Ataque sem alvo válido", `entropy 10→9`, `used_this_scene 1`. Em `combat_node:837-843` o alvo só é validado contra
  `set(actors_by_id)` (inclui mortos e o próprio player).
- [F] **Guarda nunca expira** — `conflict_scene.guard` (`:409-441`) seta `guarding=True`; só `stop_guard` limpa e não há
  caller em produção; `reset_turn_budget` não zera → Desvantagem permanente nos ataques do guardião (e proteção eterna).
- [F] **DoT/clima atravessam armadura** — `conflict_damage.py:239` `if compativel and (defensavel or not use_shield)`:
  com `use_shield=False`, `defensavel=False` nunca desliga a armadura. Repro: DoT 1 vs Proteção 2 → `Vitalidade 10→10`.
  Sangramento nunca fere quem usa armadura.
- [F] **Preparação de cena por LLM nunca roda** — `agents/combat.py:286` usa `fallback_safe_scene`; `prepare_encounter`
  sem callsite de produção → `objects=[]`, `abyss_events=[]`, sem reforços nem `ending_conditions` (conflito-03/10/11
  `done` sem efeito em jogo real). Decisão D-A.
- [F] **Engajamento nunca criado** — `combat.py:289-296` `engaged_with: []`; só a manobra explícita "engajar" cria; ataque
  corpo a corpo não engaja → AoO (R5 conflito-06) é inerte; e `_declaration_leaves_engagement` roda ANTES de resolver
  `pre_acao=desengajar` → AoO indevido em Desengajar+afastar.
- [F] Menores: `_early_game_reaction_initiator` vale 2 rodadas (`round <= 1` antes do incremento, `combat.py:248-267`);
  `_maybe_abyss` debita Cargas/usos antes de `apply_effect_spec` rejeitar (`conflict_orchestrator.py:1087-1111`);
  `_default_card_target` não inclui `reduzir_carga_aliado` (`combat.py:330-338`, adendo à SPEC-199 R12).

Objetivo: todo `kind`/`stat`/`tipo` declarado nos dados tem um consumidor no motor (ou é removido dos dados), com
um teste anti-órfão que exige **efeito observável**, não presença em lista.

## 2. Requisitos

- **R1** — [R] `resolve_attack` soma `condition_modifiers(actor)["attack"]` ao total; `compute_esquiva(target)` soma
  `["ac"]`; `_damage_from` soma `["damage"]`; `protection` entra em `conflict_damage` como Proteção extra; `advantage`
  conta em `net_advantage`. Durações respeitadas (`duration` decresce por rodada; expira ao chegar a 0). Teste de
  reprodução: `r4.py` → `attack +20` ≥ 190/200 acertos; `ac +20` ≤ 10/200.
- **R2** — [R] `combat_mechanics.learned_passives(entity)` agrega `known_cards` com `tipo in {"passiva","virtude"}`
  (catálogo v4) em efeitos normalizados; `player_passives` as inclui; consumidores: `resolve_attack`/dano/iniciativa/
  Esquiva/cura/Entropia conforme `kind` (`buff_defesa`, `buff_dano`, `vantagem`, `aplicar_condicao`, `contra_ataque`,
  `buff_iniciativa`, `buff_dot`, `buff_cura`, `perception`, `bonus_*_por_estagio`). Teste: personagem com passiva
  `buff_dano +2` → dano médio +2 vs sem passiva (mesmo seed).
- **R3** — [R] `_open_reaction_window` resolve `reaction.efeito` além de `protected`: `contra_ataque` rola ataque do
  reagente contra o atacante; `dano`/`cura`/`aplicar_condicao`/`empurrao` aplicam pelo mesmo pipeline das ações.
  Entropia só é debitada se o efeito resolveu (ou reembolsada). Teste: Reação `contra_ataque` → atacante perde
  Vitalidade com seed fixo.
- **R4** — [R] Teste anti-órfão v2 (`tests/test_mecanica_orfa.py`): para cada `kind`/`stat`/`tipo` presente em
  `data/cards/`, `data/classes.json`, `data/traits.json`, `data/artifacts.json`, existe um teste de efeito (registro
  `EFFECT_TESTS[kind]`) que muda uma rolagem/estado com seed fixo; `kind` sem teste → falha. Substitui a varredura por
  `HANDLED_KINDS`.
- **R5** — [R] Validação de alvo/mira ANTES de cobrar: `use_card`/`use_ruptura` só debitam Entropia e marcam uso quando
  o alvo é válido (vivo, hostil para ofensivas/aliado para suporte, `can_target`); em `combat_node` o alvo hostil é
  restrito a `active` ids e nunca `player`. Teste de reprodução: `r2.py` → `entropy 10`, `used_this_scene 0`.
- **R6** — [R] `guarding` expira em `reset_turn_budget` do próprio ator (início do seu turno), a menos que guarde de
  novo. Teste: guardar na rodada 1 → rodada 2 ataca sem Desvantagem.
- **R7** — [R] `apply_damage(..., bypass_armor: bool)` explícito; DoT (`_apply_dot_v4`), clima e `defensavel=False`
  passam `bypass_armor=True` (ignora armadura E escudo; Integridade intacta). Teste de reprodução: DoT 1 vs Proteção 2
  → `Vitalidade 10→9`.
- **R8** — [R] Engajamento: ataque corpo a corpo bem-sucedido ou recebido cria `engaged_with` mútuo; `_declaration_
  leaves_engagement` considera `pre_acao == desengajar` da mesma declaração (sem AoO). Teste: atacar → engajado; mover
  sem desengajar → AoO; desengajar+mover → sem AoO.
- **R9** — [R] `_early_game_reaction_initiator` só na rodada 1 (`round == 1` pós-incremento). `_maybe_abyss` só debita
  Carga/uso após `apply_effect_spec` aceitar. `_default_card_target` inclui `reduzir_carga_aliado` no conjunto amigável.
- **R10** — [R] Preparação de encontro: conforme D-A, OU `prepare_encounter` é chamado na 1ª rodada (guard existente;
  `fallback_safe_scene` em falha; custo de 1 invoke FAST) OU os módulos `abyss_events`/objetos/reforços/`ending_
  conditions` são declarados desativados em `docs/design/` e nos chips/lore que os prometem. Teste conforme decisão.

### Fora de escopo

- Fluxo de morte/aliados (spec `SPEC-231`); gesto de alvo (SPEC-205). (Alvo de cura sem alvo — ex-SPEC-199 R12 — agora ESTÁ no escopo desta spec: borda `api.py::_apply_action_options` usa `_default_card_target` para carta benéfica sem `target_id`; teste de reprodução primeiro.)
- Rebalancear números das cartas (SPEC-049 remede DEPOIS desta spec).
- Reescrever `tactical_profile` (IA inimiga) além de respeitar os modificadores.

## 3. Design técnico

### Arquivos alterados

- `services/conflict_resolution.py` — `resolve_attack`, `compute_esquiva`, `_damage_from` com `condition_modifiers` +
  passivas (R1/R2). `combat_mechanics.py:194-200,233` — `learned_passives` real; `tick_conditions` por rodada (R1).
- `services/conflict_orchestrator.py:569-572` — resolução de `efeito` da Reação (R3); `:1087-1111` Abismo (R9);
  `_open_reaction_window` com reembolso.
- `services/conflict_turn.py:211-259` — ordem validar→cobrar (R5); `agents/combat.py:837-843,330-338,248-267` (R5/R9).
- `services/conflict_scene.py:57,409-441` — expiração de `guarding` (R6); `engage` automático (R8).
- `services/conflict_damage.py:239` + chamadores — `bypass_armor` (R7).
- `agents/combat.py:286-296` — preparação conforme D-A (R10).
- `tests/test_mecanica_orfa.py` — registro `EFFECT_TESTS` (R4).

### Assinaturas

```python
def learned_passives(entity: dict, *, cards_db=None) -> list[dict]        # [{kind, value, source_card}]
def apply_damage(target, amount, *, damage_type, bypass_armor: bool = False, ...) -> DamageResult
def use_card(state, actor, card_id, *, target_id, scene) -> CardUse       # valida antes de cobrar; .charged: bool
def resolve_reaction(scene, reactor, card, trigger, rng) -> list[str]     # efeitos reais
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_combate_modificadores.py`: `test_attack_condition_changes_hit_rate` (R1), `test_learned_passive_buff_dano`
(R2), `test_reaction_contra_ataque_damages_attacker` (R3), `test_card_cost_not_charged_on_invalid_target` (R5),
`test_guard_expires_next_turn` (R6), `test_dot_bypasses_armor` (R7), `test_melee_attack_engages_and_disengage_avoids_aoo` (R8),
`test_early_game_initiator_only_round_1` (R9).
### Etapa 1 — R1, R5, R6, R7, R9 (cirúrgicos, baixo risco)
### Etapa 2 — R2, R3 (passivas/reações) + R4 (anti-órfão v2)
### Etapa 3 — R8 (engajamento) + R10 (decisão D-A)
### Etapa 4 — regressão `uv run pytest`; playtest offline `agressivo`/`combate` 40 turnos com `--class` × 5: `%ativa`
e `gasto/turno` de Entropia (SPEC-059) registrados como novo baseline para a SPEC-049.

## 5. Critérios de aceite

- [x] 8 testes vermelhos → verdes; `tests/test_conflito_*.py`, `test_cutover_audit.py`, `test_arvores_classes.py`,
      `test_classes_refactor.py`, `test_cards_v4*.py` verdes ou diff justificado (ex.: expectativas que assumiam
      modificador inerte).
- [x] Anti-órfão v2 cobre 100% dos `kind`/`stat`/`tipo` dos dados.
- [x] `uv run pytest` verde; playtest offline com run_ids e baseline de Entropia.
- [x] Guard de FallbackLLM mantido em `prepare_encounter` se R10 o ativar.

## 6. Smoke test com LLM real

1. Carta de buff de ataque → log mecânico mostra bônus e a taxa de acerto muda visivelmente em 3 ataques.
2. Reação de contra-ataque → inimigo perde Vitalidade na janela de reação.
3. Guardar → próxima rodada atacar sem Desvantagem no chip.

## 7. Riscos & compatibilidade

- Letalidade muda nos dois sentidos (buffs do jogador E debuffs/condições inimigas passam a valer): remedir
  `letalidade-early-game-v2` após esta spec; manter os knobs `[BALANCEAR]` como estão até o novo baseline.
- Saves em combate ativo com condições antigas: compatível (mesmo schema de condição).
- R10 (preparação por LLM) adiciona 1 invoke FAST por encontro se ativado — medir no playtest real da SPEC-200.

## 8. Pontos de decisão do dono

- **D-A (preparação de cena por LLM):** (1) ativar `prepare_encounter` (objetos/Abismo/reforços voltam; +1 invoke);
  (2) declarar desativado e limpar promessas. Default recomendado: (1) só quando `abyss_charge ≥ patamar leve` ou
  categoria ≥ Elite; senão `fallback_safe_scene` — custo controlado, Abismo volta a disparar quando importa.
- **D-B (passivas no motor de Cartas vs `combat_mechanics`):** default: agregar em `combat_mechanics.learned_passives`
  (um ponto de verdade com `class_passives`/`item_passives`); alternativa: resolver dentro de `services/cards.py`.

## 9. Evidência requerida

- `uv run pytest` completo; testes antes/depois; relatório do anti-órfão v2 (lista kind→teste).
- `docs/<spec>/README.md` com `combate/r4.py`/`r2.py` transcritos, run_ids do playtest por classe e revisão `Sol`.

## 10. Execução (2026-10-16)

- **Defaults do dono usados:** D-A = opção (1) recomendada (`prepare_encounter` só com Carga ≥ leve ou inimigo
  Elite/Chefe/Nomeado; demais em `fallback_safe_scene`); D-B = agregar em `combat_mechanics.learned_passives`.
- **Desvios:** (a) R1 `ac +20` → ≤30/200 (não ≤10): Crítico por dupla sempre acerta (conflito-04 R5); o teste exige que
  todo acerto seja Crítico. (b) Anti-órfão v2 aceita 3 lacunas FORA do combate (`trait.dc:comercio|insight|intimidacao`,
  sem consumidor social determinístico) — explicitadas em `KNOWN_GAPS`; qualquer chave de combate sem teste falha.
  (c) Escopo ampliado pelo próprio anti-órfão: catálogo fechado de condições nomeadas (`NAMED_CONDITIONS`), semântica
  dos 8 gatilhos de Reação autorados fora do vocabulário + `allies_of`, Marca dá Vantagem, Silenciado bloqueia Cartas,
  purga remove condição nociva, passiva de item `damage_type`. (d) Buff/debuff tipado expira ao fim do turno do
  portador (não no início), para `duracao: 1` valer.
- **Ex-SPEC-199 R12:** borda `api._apply_action_options` usa `_default_card_target` (teste de reprodução incluso).
- **Revisão Sol (2026-10-16):** (e) `_expire_stat_conditions` guarda refs (não `id()`, reusável após GC); (f) revide de
  Reação (`contra_ataque`/`dano`) sem atacante vivo na cena não cobra Entropia/uso. (g) **R10 após smoke real:** o
  schema antigo (dicts abertos + posições/inimigos/NPCs/reforços, prompt com o `ctx` cru) gerava ~1,8k tokens fora do
  contrato — DeepSeek estourava o timeout de 12 s e a resposta vinha sem `base_narrativa` (sempre fallback). Agora
  `PreparedScene` é enxuto e tipado (zonas, objetos com interação do catálogo, ≤1 evento do Abismo, objetivos), sem
  limites duros (truncagem em Python, `gatilho` do evento fixado em Python), prompt compacto com ids válidos e teto
  dedicado `RPG_PREP_TIMEOUT_SECONDS` (default 12 s; estouro → `fallback_safe_scene`). Reforços/condições de fim
  saíram do pedido (sem consumidor no loop). Smoke real: 3/3 cenas válidas em 7,2 / 2,8 / 2,9 s.
- Evidência e playtest antes/depois: [docs/spec232/README.md](../docs/spec232/README.md).

---

## Adendo SPEC-272 (2026-10-18)

SPEC-272: o R1 cita `net_advantage`; o helper foi removido (nunca chamado). O `advantage` das condições já entra somado no `roll_kept`, que só considera o sinal — o comportamento descrito no R1 não muda.
