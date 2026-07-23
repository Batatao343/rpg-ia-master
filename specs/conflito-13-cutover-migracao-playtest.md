# SPEC — Conflito v2 #13: Cutover, Remoção do Motor Antigo e Playtest Estruturado

> **Status:** `in-progress` (2026-07-23) — Etapa 1 (auditoria) `done`; R6 decidido.
> Cutover executado em ESTÁGIOS commitados verdes na branch
> `refactor/reestruturacao-combate` (só o merge final pra `main` é atômico).
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-23
> **Depende de:** `conflito-01` a `conflito-12` (TODAS `done` antes de iniciar)
> **Desbloqueia:** fecha tecnicamente o motor do épico; `conflito-16` (frontend)
> pode consumir a API estabilizada por esta spec
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Decisão fechada com o usuário (2026-07-22): **cutover atômico**. Todas as specs
`conflito-01` a `12` constroem o motor novo em módulos isolados (`services/
conflict_scene.py`, `services/cards.py`, `services/reactions.py`,
`services/tactical_profile.py`, `services/chase.py`, `services/abyss_events.py`,
`services/encounter_preparation.py`, `services/conflict_summary.py`,
`services/death_flow.py`) sem religar o grafo principal. Esta spec faz a troca
final: liga o roteamento (`dm_router`/`agents/combat.py`) ao motor novo, remove o
motor antigo, e adapta tudo que dependia do formato antigo — principalmente o
**playtest harness**, cuja premissa central (perfis mandam texto livre tipo
"Ataco X", parseado por LLM) deixa de existir: combate agora é 100% sem LLM,
então os perfis precisam falar a API estruturada do motor novo diretamente.

## 2. Requisitos

- **R1** — `dm_router`/grafo principal passam a chamar o motor novo
  (`ConflictScene`, `services/*` das specs 01-12) no lugar de
  `combat_mechanics.py`/`agents/combat.py` antigos.
- **R2** — Remoção do código morto: `combat_mechanics.py` antigo (pipeline
  d20+AC+cooldowns), lógica velha de `agents/combat.py` (`_spawn_enemies_integrated`
  antigo, `resolve_player_action`/`resolve_enemy_turn` antigos, 4 perfis fixos de
  comportamento), `data/player_abilities.json` antigo (substituído por
  `data/cards/` de `conflito-02`/`14`). Auditoria de "código morto" nos moldes de
  `fiacao-regras-orfas-classes` (varrer funções sem callsite novo).
- **R3** — Migração v3→v4 (`conflito-01` R9-R10) entra em vigor: saves antigos
  ficam órfãos/arquivados, sem tentativa de conversão.
- **R4** — `playtest/runner.py`/`playtest/profiles.py` reescritos: perfis param de
  gerar texto livre pra combate e passam a emitir decisões estruturadas
  (`TurnDeclaration` de `conflito-04`: Pré-Ação/Ação/Pós-Ação com `card_id`/
  `target_id`/manobra) direto contra o motor novo. Fora de combate (roleplay),
  perfis continuam com texto livre normalmente.
- **R5** — `playtest/invariants.py` ganha invariantes novas equivalentes às
  antigas mas adaptadas ao schema novo: `check_vitals` vira checagem de
  Vitalidade+Ferimentos; `check_combat_zombie` adapta pra `ConflictScene.frozen`/
  timeout; `check_phantom_ally` adapta pra `combat_party`/`scene_allies` novo (se
  a estrutura mudar de nome); novo invariante `check_effect_catalog_violation`
  (nenhum efeito fora do catálogo fechado escapou pra produção); novo
  `check_reproducibility` (mesma seed + mesmo estado inicial = mesmo resultado,
  doc 03 Cenário 53).
- **R6** — `services/checkpoints.py` reconciliado com o fluxo de morte novo
  (`conflito-07`): decisão explícita de como `death_pending`/Última Ação/Estado
  Terminal se encaixam no ciclo de checkpoint existente (`should_checkpoint`/
  `resolve_death_choice`) — documentar a decisão nesta spec antes de implementar.
- **R7** — Suíte de testes: os ~199+ testes de combate hoje espalhados (ver
  inventário: `test_classes_refactor`, `test_arvores_classes`, `test_fase42/43`,
  `test_combat_lifecycle`, `test_checkpoints`, `test_death_flow` etc.) são
  auditados um a um — mantidos se testam comportamento que sobrevive
  (ex. persistência genérica), removidos/reescritos se testam mecânica extinta
  (ex. d20 vs AC, 4 perfis fixos).
- **R8** — `uv run pytest` verde com a suíte pós-cutover; nenhum teste órfão
  testando código removido.

### Fora de escopo

Autoria de conteúdo (`conflito-14`/`15`, podem rodar em paralelo às specs
01-12, mas só entram em produção depois deste cutover); frontend
(`conflito-16`).

## 2.1. Decisão do R6 — reconciliação com checkpoints (FECHADA 2026-07-23: Opção A)

Decidido com o usuário: **death_flow resolve o fluxo terminal INTEIRO dentro do
conflito; só a morte REAL aciona `death_pending`/tela de escolha.**

- último Ferimento Crítico → **Última Ação** → **Estado Terminal** → estabilização
  rodam 100% determinístico, SEM pausa e SEM tocar checkpoint.
- `death_flow.attempt_stabilization` devolve `dead=True` (sem aliado capaz ou 2
  falhas) → só aí o nó de combate seta `death_pending=True` e cai no fluxo
  existente `checkpoints.resolve_death_choice` (**Continuar**=restaura checkpoint /
  **Aceitar**=memorial, sessão 23 preservada — sem permadeath, memorial voluntário).
- sobreviver ao Estado Terminal (`revived=True`) → aplica a **Cicatriz** obrigatória
  (`death_flow.generate_scar`) e o combate CONTINUA; nunca aciona checkpoint.
- `should_checkpoint` já ignora `death_pending`/`game_over` — nada muda ali.

## 2.2. Auditoria de código morto (Etapa 1 `done`, 2026-07-23)

Fronteira de remoção verificada por `tests/test_cutover_audit.py`. Fora de
`agents/combat.py`, a ÚNICA chamada de produção de função "que morre" é
`combat_suggestions` em `api.py` (adaptada na Etapa 2). Todo o resto das
referências externas é comentário de docstring.

**MORRE (motor d20+AC do turno — substituído por `services/*` novos):**
`resolve_player_action`, `resolve_enemy_turn`, `resolve_ally_turn`, `roll_initiative`
(→ `conflict_resolution.roll_initiative_by_side`), `get_behavior`/`choose_enemy_attack`/
`pick_target`/`check_morale`/`_avg_damage`/`_attack_applies_condition`/`_target_ac`/
`_apply_attack_conditions` (→ `tactical_profile`/`death_flow`), `usable_enemy_abilities`/
`_pick_enemy_ability`/`_resolve_enemy_ability`/`apply_boss_phase`, `combat_suggestions`,
`_find_target`, `_healing_consumable`.

**SOBREVIVE (helpers genéricos + sistema de classes Entropia/Carga da v4 + condições
+ passivas — reusados pelo motor novo e por api/progression/inventory/world_utils):**
`get_mod`/`normalize_attr`/`attr_mods`/`virtude_mods`/`actor_mods`, dados
(`roll_dice_numeric`/`resolve_damage_formula`/`roll_magnitude`/`_heal`), condições
(`parse_condition`/`condition_modifiers`/`has_control`/`is_condition_resisted`/
`apply_condition`/`tick_conditions`), passivas (`class_passives`/`learned_passives`/
`item_passives`/`player_passives`), Entropia/Carga (`entropy_config`/`abyss_tier`/
`reset_entropy_turn`/`apply_entropy_trigger`/`taunt_aggro_multiplier`/`apply_blood_leak`/
`arm_boiler`/`tick_boiler`/`reduce_ally_abyss`/`apply_scar`/`dependencia_cost`/
`apply_transformacao`/`apply_entropy_on_kill`/`entropy_max_bonus_of`/`check_recidiva`/
`HANDLED_KINDS`), recursos (`is_on_cooldown`/`spend_resources`/`tick_cooldowns`),
dano (`damage_bonus`/`early_game_damage_bonus`/`_split_typed_effects`), e
`compute_player_combat_stats`.

## 3. Design técnico

Esta spec é primariamente de **integração e remoção**, não de novo módulo. Pontos
de corte:
- `main.py` (`build_game_graph`) — nó de combate aponta pro motor novo.
- `combat_mechanics.py` — arquivo pode ser deletado ou esvaziado pros helpers
  puros que sobrevivem (ex. `roll_dice_numeric` genérico, se ainda usado).
- `agents/combat.py` — reescrito para orquestrar `services/*` novos.
- `playtest/runner.py`/`profiles.py`/`invariants.py` — reescrita coordenada.
- `state.py` — remove campos mortos (`ability_cooldowns` antigo se
  `conflito-02` já não o tiver removido, `combat` dict antigo se `ConflictScene`
  o substitui integralmente — decisão explícita nesta spec).

## 4. Plano passo a passo

### Etapa 1 — Auditoria de código morto (pré-remoção)
1. **Testes:** script/teste de auditoria (nos moldes de `HANDLED_KINDS`) que lista
   funções de `combat_mechanics.py` sem callsite novo.
2. **Implementação:** relatório antes de deletar nada.

### Etapa 2 — Religar o roteamento
1. **Testes:** e2e mínimo — `dm_router` → combate → resolução → loot → resumo →
   narrativa, tudo com o motor novo, no mock.
2. **Implementação:** `main.py`/`agents/combat.py`.

### Etapa 3 — Remoção do motor antigo
1. **Testes:** suíte roda verde sem os arquivos/funções antigos.
2. **Implementação:** deletar `combat_mechanics.py` antigo (ou reduzir a helpers
   puros), `data/player_abilities.json` antigo.

### Etapa 4 — Migração v3→v4 em vigor
1. **Testes:** `test_save_v3_fica_orfao_sem_crash` (já coberto em `conflito-01`,
   reconfirmar em integração).
2. **Implementação:** `persistence.py`.

### Etapa 5 — Reescrita do playtest harness
1. **Testes:** 12+ perfis rodam N turnos no motor novo com `TurnDeclaration`
   estruturado, 0 erro.
2. **Implementação:** `playtest/runner.py`/`profiles.py`.

### Etapa 6 — Invariantes novas
1. **Testes:** cada invariante nova (R5) testada isoladamente.
2. **Implementação:** `playtest/invariants.py`.

### Etapa 7 — Reconciliação de checkpoints/morte
1. **Testes:** fluxo completo morte→Última Ação→Estado Terminal→checkpoint
   funciona sem regressão do comportamento de `checkpoints-morte` (sessão 23).
2. **Implementação:** `services/checkpoints.py`.

### Etapa 8 — Auditoria final de testes órfãos
1. **Testes:** suíte completa, zero teste testando código removido.
2. **Implementação:** remoção/reescrita coordenada dos ~199+ testes antigos de
   combate.

## 5. Critérios de aceite

- [ ] Grafo principal usa só o motor novo — nenhum caminho de produção chama
  `combat_mechanics.py` antigo.
- [ ] Playtest harness roda 12+ perfis no motor novo, 0 erro, `erros=0/violações=0`
  nas novas invariantes.
- [ ] Saves pré-v4 ficam órfãos sem crash, comunicados claramente.
- [ ] `npm run build` verde (frontend ainda não migrado, mas não pode quebrar
  build — `conflito-16` decide se adapta types.ts nesta etapa ou na própria 16).
- [ ] `uv run pytest` verde (suíte completa offline, pós-remoção).

## 6. Smoke test com LLM real

1. Campanha completa real (DeepSeek): criação → exploração → preparação de
   encontro → combate completo (turnos/reações/dano/Ferimento) → morte OU vitória
   → loot → resumo → retomada narrativa, sem nenhum erro.
2. Confirmar zero chamada de LLM durante a resolução do conflito em si (só
   preparação antes + narração depois).
3. Rodar `playtest run --all --turns 30 --real` com teto de custo e confirmar 0
   erro nas 12+ campanhas.

## 7. Riscos & compatibilidade

- Maior ponto de risco do épico inteiro: é o momento em que o jogo fica
  "injogável até terminar" (decisão de rollout do usuário) — não fazer merge
  parcial pra `main`/branch principal antes desta spec fechar.
- R6 (reconciliação com checkpoints) precisa de decisão explícita documentada
  ANTES da implementação — não inferir silenciosamente.
- Volume de testes a auditar (~199+) é grande — não pular a Etapa 1
  (auditoria) achando que "dá pra ver na hora".
