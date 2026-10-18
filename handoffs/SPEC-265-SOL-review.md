# SPEC-265 — revisão independente Sol (REVIEW_REQUIRED) + spot-check SPEC-266/267

- **Revisor:** Opus (Sol ≡ Opus), não autor. Worktree `rpg-prune2`, branch `prune-2`, rebased em `main` `757665f` sem conflito (`project_index/` = o de main).
- **Escopo:** commits `chore(spec266)`, `chore(spec267)`, `chore(spec265)` do lote 2 de podas.
- **Veredito:** **APPROVED** (sem defeito no código; 1 teste de regressão acrescentado; 1 flake pré-existente registrado).

## SPEC-265 — ataques

| Ponto | Resultado |
|---|---|
| Consumidores de `mana/max_mana/stamina/max_stamina` do jogador | `git grep` fora de testes/docs/specs: nenhum. Web (`src/`, `e2e/`), `web/android`, `evals/` (datasets, expected, adapters), `playtest/`, `character_creator.py`, `game_engine.py` (CLI) e `scripts/`: zero leitura. Restam só comentários e os chips `mana_bonus`/`stamina_bonus` da criação (R4, intencionais). |
| Inimigos | `EnemyStats.mana/stamina` (`state.py`) e bestiário intactos; `combat_mechanics`/ponte `actor_mods` não leem mana do jogador (só o nome de trigger `hp_as_mana`). |
| Invariante `bounds()` (R1d) | Roda para party/inimigos, mas nenhum ator tem `max_mana`/`max_stamina` (grep vazio) — sem perda de cobertura. |
| Saves antigos | `persistence._MIGRATIONS` intacto. v3 com mana/stamina → arquivado; v4+ com as chaves → carrega, as chaves ficam inertes (nem recompostas nem removidas pelo descanso) e a view não as expõe. **Teste novo** `tests/test_spec265_legacy_mana_saves.py` (2 casos: v3 arquivado + v4 `_raw_to_state` → `format_response` → `apply_rest`). |
| API (`GameResponse.player_stats`) | Perde 4 chaves que valiam sempre 0; `test_cards_prepare_api` asserta a ausência. Cliente web usa `?? 0`/não lê; Android usa o mesmo bundle. |
| HUD (R1c) | Barra de Entropia sempre desenhada (0/0 sem pool); chip de Carga segue gated por `max_entropy>0`. Tokens `--mana/--stamina` preservados (R1a; `design.test.mjs` verde). |

## SPEC-266/267 — spot-check

- Nenhuma referência a `frontend/` ou aos MP4 removidos em código, CI (`.github/`), `scripts/`, testes ou escopo de evals. Restos só em docs históricas/auditorias e no README de `docs/descricao_projeto` (já com nota "removido do git; re-renderize"). `.vercelignore` ainda lista `frontend` (inofensivo).
- `api.py` monta só `web/dist`; sem build a API sobe sem UI (`/health` 200, `/` 404) — coberto por `test_spec267_static_mount.py` nos dois estados (rodou sem e com `dist`).

## Gates

- `pytest` completo: verde exceto 2 testes de `test_project_index.py` por **índice stale** (esperado: o branch muda fontes). Com `project_index build` local os 7 passam; índice revertido para o de main — **rebuild em checkout limpo antes do push**.
- `ruff check .` verde; `npm test` 126/126; `npm run build` verde.
- Playwright completo (chromium empacotado, 2 workers, todos os projetos, porta 4211): **238 passed, 38 skipped, 3 failed**. Falhas: 2× `account-lifecycle` (conhecidas em main + URL `4173` fixa no spec, porta diferente aqui) e `F06 map_travel` — flake pré-existente: o spec lê `backend.requests` logo após `travel.click()` sem esperar a requisição (`critical-journeys.spec.ts:117`); isolado 2/3 verdes. Não editado (régua de eval protegida). Sugere spec própria: `waitForRequest` antes do assert.
- Evals determinísticos (12 suítes do CI) `passed: true`, `hard_failures: []`; `governance check` 11 datasets válidos.
- `playtest run --all --turns 3`: 14 perfis, 0 erro, 0 violação.
