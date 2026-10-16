# SPEC-199 - handoff de autoria de eval (EVAL_AUTHORING_REQUIRED)

Autoria por quem NAO implementou a SPEC-199; dataset congelado e registro na governanca de `evals/`.

Eval deterministico `narrative-no-mechanical-numbers`:
- Fixtures de turno com XP, ouro, itens e missao concluida (vitoria de combate, beat, quest, venda, saque).
- Assert na prosa visivel (`GameResponse.message`, chunks `narrative` do SSE, fallbacks de `_narrate`/`_narrate_fall`):
  ausencia de `\+\d+\s*XP`, `[RESULTADO]`, `N[ií]vel \d+` de level-up e quantidade de ouro de recompensa.
- Assert em `GameResponse.turn_outcome`: `receipt_id` estavel, `xp_delta`/`gold_delta`/`items_gained[].name`/`quests_completed[].title` corretos e `source` coerente (combat|story|quest|loot|exploration|mixed).
- Fora do escopo: linhas `[SISTEMA]` do `loot` (D-B) - o eval deve whitelistar compra/venda/saque ate a spec de recibo de economia.
- Nao editar evaluator/dataset existentes; entradas novas via governanca (SPEC-165).
