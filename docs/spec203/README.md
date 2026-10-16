# SPEC-203 — evidência

## O que mudou
- **Etapa 0** (`tests/test_encounter_identity_repro.py`, [repro.md](repro.md)): H1, H2, H2b, H3, H4
  reproduziram bugs de estado no HEAD `50d4620`; H5 é só narrativo; H6/H7 não reproduziram.
  D-A não se aplica — R3/R4 implementados.
- **`services/encounter_manifest.py`** (novo, puro): `EncounterManifest`/participantes/eventos,
  `resolve_canonical_source`, `build_manifest`, `validate_roster`/`reconcile_roster`,
  `apply_composition`/`sync_statuses` (idempotentes por `event_id`), state machine
  `transition`/`safe_transition`/`end_combat`, `normalize_combat` (load aditivo),
  `public_view`, `build_result`, `result_view`.
- **Spawn** (`agents/combat._spawn_v4_enemies`): ordem (a) `enemy_id` sistêmico → (b) NPC em cena
  → (c) nome exato do bestiário → (d) scanner validado contra a dica (fauna fora da dica
  descartada); trava de identidade no retorno do bestiário/librarian (`_grounded_template`);
  `source=fallback` visível. `agents/bestiary.template_by_id` (sem LLM).
- **Orçamento** (`encounter_budget.clamp_encounter(..., protected=)`): alvo canônico entra antes
  da variedade; regra numérica inalterada. Cortes/reforços viram eventos `cut`/`joined`
  (reforço com `presence=arrived`).
- **combat_node**: grava manifesto congelado (`entering`), confirma `active` após a narração de
  entrada, valida o elenco a cada rodada (intruso → `cut roster_violation`), registra saídas por
  evento e encerra em `ended` com `combat.result`. Outcomes: victory/fled/surrendered_enemy/
  defeat/death/expired. `_narrate` recebe espécies canônicas; prosa que troca espécie é
  neutralizada (`prose_guard.species_drift`).
- **Router**: `combat_target_ref` (NPC em cena), expiração vira `outcome=expired` com resultado;
  1º turno após `ended` (≠ death) roteia exploração (`explore_resumed`).
- **Storyteller**: `combat_encounter_hint` (`encounter_handoff`) com `enemy_id`.
- **turn_finalizer**: carimba `combat.result.xp_event_ref = receipt_id` (uma vez).
- **API**: `combat.phase/outcome/encounter_id/encounter_view`; `GameResponse.combat_result`
  (só no turno de término; sobrevive a reload). Simulador recebe `source=simulation`.
- **Persistência**: **sem bump** (`SCHEMA_VERSION` = 8, por instrução do coordenador — o caso
  protegido `state.persistence.migration-idempotent` fixa v8). Normalização aditiva e
  idempotente em `_raw_to_state`: combate ativo legado → manifesto `legacy_migrated` +
  `phase=active`; inativo → `phase=ended`/`outcome` preservado; `{}` permanece `{}`.
- **Playtest**: invariantes `encounter.identity_drift` e `encounter.phase_stuck` (`error`).
- **Frontend**: `CombatOutcomePanel.tsx` (componente isolado), `combatOutcome.ts` (puro),
  tipos em `types.ts`; "Continuar" é estado local (não chama a API, preserva draft).

## Testes
- Novos: `tests/test_encounter_identity_repro.py` (10), `tests/test_encounter_manifest.py` (21),
  `tests/test_encounter_lifecycle_reload.py` (10), `web/tests/combat-outcome.test.mjs` (1),
  `web/e2e/combat-outcome.spec.ts` (390/1440).
- Suíte Python completa (`pytest -q -p no:warnings --ignore=tests/test_project_index.py`):
  **2815 passed, 168 skipped, 0 failed** (exit 0). `tests/test_eval_state_rules.py` verde.
- `npm run build` verde; Node tests verdes; Playwright `combat-outcome` 2/2 e F08 verdes.
  F12 (`getByRole('status')` com 2 elementos) e requisição de Google Fonts falham também no
  HEAD sem estas mudanças (pré-existente/rede), não relacionados.
- Playtests offline: `combate` 30t (`20261016-041113-970390`) e `fujao` 30t
  (`20261016-041139-989702`): 0 erros, 0 violações (inclui zero `encounter.*`).
- Ruff verde nos arquivos tocados.

## Smoke real (DeepSeek, `RPG_NO_MOCK=1`, autorizado ≤10 turnos)
- Playtest `combate` 10t (`20261016-084246-334450`): 35 requests deepseek-v4-flash, 0 falhas,
  US$ 0,0098, 0 violações — **nenhum combate disparou** (descanso seguro early-game), então não
  exercitou o spawn.
- Smoke dirigido do `combat_node` (2×3 rodadas): encontro sistêmico `enemy_bandido` →
  `source=systemic`, elenco `Bandido` + `Zumbi Blindado` (`joined budget_fill`, `arrived`),
  **zero chamada de scanner** (CLASSIFY só no parse da fala livre do jogador); dica livre
  "os saqueadores encapuzados" → `source=scanner`, elenco `Saqueador Encapuzado ×2` + 2 eventos
  `cut budget_clamp`; 0 violações de elenco, manifesto imutável em todas as rodadas, prosa
  sem troca de espécie. 14 invokes deepseek nesta execução (uma 1ª execução idêntica com 4
  rodadas falhou só no `json.dumps` final após ~14 invokes). Custo total do smoke < US$ 0,02.

## Limites / pendências
- Revisão independente Astra **não executada** (REVIEW_REQUIRED) e evals novos aguardam autoria
  separada ([handoff](../../handoffs/SPEC-203-eval-authoring.md)).
- Parse de fala livre do jogador continua CLASSIFY (identifica a ação, não o elenco); "zero
  CLASSIFY nas rodadas ≥1" vale com declaração estruturada (UI/harness) — interpretação registrada.
- Store Postgres (perfis não-legacy) não passa por `_raw_to_state`; `combat_node` reconstrói
  manifesto `legacy_migrated` na 1ª rodada se faltar.
- Screenshot 1440 do painel: `web/test-results/spec203-outcome-1440.png` (gerado pelo e2e, não versionado).
