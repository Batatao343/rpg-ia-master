# SPEC-199 - evidencia

## O que mudou
- `agents/combat.py`: `+N XP`/`NIVEL` nao entram mais em `logs` (prompt de `_narrate`, `_narrate_fall`, fallbacks, modo laboratorio). `grant_xp` e level-up inalterados.
- `services/turn_outcome.py`: `render_player_message` nao anexa mais `[RESULTADO]`; novos `strip_receipt`, `public_outcome` (whitelist R4), `level_after`/`source` no `finalize_outcome`; `player_facing_message` re-sanitiza saves legados (R7).
- `api.py`: `GameResponse.turn_outcome` (vazio em simulacao e em saves sem `last_turn_outcome`). POST, SSE (`state`), replay por `action_id` e `/game/state` passam todos por `format_response`, logo herdam o mesmo campo/`receipt_id`.
- Web: `TurnOutcome` em `types.ts`, `outcomeToast.ts` (puro), `OutcomeToast.tsx` (chip `aria-live`, so para `receipt_id` novo; 1a projecao da sessao nao anima), CSS minimo, montado em `PlayScreen`.

## Inventario R10 (vazamentos de numero de recompensa na mensagem)
| Ponto | Estado |
|---|---|
| combate `logs` +XP/NIVEL | corrigido aqui |
| recibo `[RESULTADO]` (turn_outcome.py) | corrigido aqui |
| `loot.py` `[SISTEMA] +Nx item / Ouro` (compra/venda/saque) | adiado (D-B): spec sucessora "recibo de economia na UI" |
| storyteller beat/armadilha, `event_processor` quest | so chegavam pelo recibo; cobertos |

## Decisoes
D-A, D-B, D-C: defaults da spec. R12 (cura sem alvo) movido para SPEC-232.

## Testes
`tests/test_combat_xp_outside_prose.py` (9), `web/tests/outcome.test.mjs` (2). Testes legados atualizados ao novo contrato (nao estao em `evals/`): `test_matriz_a_contratos.py`, `test_pre_matrix_contracts.py`.
Suite completa offline verde; `npm run build` e 45 testes Node verdes; ruff verde.

## Fechamento (coordenador)
- Red-before: com o codigo de main (combat/api/turn_outcome revertidos) e os testes novos, 7 de 9 testes de `test_combat_xp_outside_prose.py` falham (os 2 restantes sao negativos que ja passavam).
- `source` preciso: `record_gain(..., origin)` grava `gain_origins` (combat|beat|quest|loot|exploration) nos 5 callsites (combat, loot, storyteller beat/armadilha/descoberta, event_processor); `finalize_outcome` deriva `source` disso (beat->story). Testes em `tests/test_turn_outcome_endpoints.py`.
- TestClient: SSE `state` == `/game/state` (campo `turn_outcome`), POST replay por `action_id` (1 invoke, mesmo receipt_id, XP uma vez, prosa sem `+N XP`).
- Playtest offline 40 turnos: combate `20261016-033050-219754`, quester `20261016-033053-079576`; 0 erros, 0 violacoes; grep `\+\d+ XP|[RESULTADO]` = 0 (jsonl, summary, transcript.md).
- Browser: `web/e2e/outcome-toast.spec.ts` (390/1440) - chip `+50 XP` aparece uma vez, so no chip (nao na prosa), sem overflow, nao reanima apos reload. Fixture `gameState`: `turn_outcome` em input "vitoria".
- Handoff de eval: `handoffs/SPEC-199-eval-authoring.md`.
- Suite completa exit 0 (sem pipe), ruff verde, `npm run build` e 45 testes Node verdes.

## Limites
- Chip de nivel nao foi exercitado no browser (so XP).
