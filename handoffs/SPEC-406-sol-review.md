# SPEC-406 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol (`spec-reviewer`) · **Data:** 2026-11-11 · **Commit revisado:** `58e52531` (base `3082b857`)

## Escopo

Revisei `git diff 3082b857...HEAD` na branch `spec-406`, 7 commits (`9f0d1427`..`58e52531`): `api.py`, `ruff-baseline.toml`, `tests/size_budget.json`, `tests/test_api_surface.py`, os 3 testes migrados para `gamedata` (`test_combat_simulator.py`, `test_hardening_persistencia_sse.py`, `test_latency_metrics_compat.py`), `docs/spec406/README.md` e a spec. Nada mudou em `evals/`, `playtest/`, `routes/`, `services/`, `agents/` nem no código de produto fora de `api.py`. Ficaram de fora: a suíte completa (cabe ao coordenador no pouso), um novo `patch_liveness`, evals e playtest. Para esses três, conferi o que o executor escreveu, sem rodar de novo.

Foco: um nome removido que alguém ainda lê como `api.<nome>` sumiria sem erro.

## Verificação independente

1. **Consumidores dos 91 removidos (busca AST própria, sem usar a tabela do executor).** O conjunto de removidos é calculado assim: nomes ligados no `api.py` da base menos os nomes ligados no da HEAD. Isso dá **91**, e bate com a lista do README. O scanner percorreu **1.380 arquivos `.py`** do worktree inteiro, menos `.venv`, `node_modules` e `.git`. Isso inclui `workers/`, `docs/**`, `project_index/`, `.claude/`, `conftest.py` e `vercel_app.py`. Formas cobertas:
   - aliases `import api [as x]`, inclusive dentro de função;
   - `x = importlib.import_module("api")` / `reload(api)`;
   - `sys.modules["api"].X`;
   - `from api import X` / `*`;
   - `f(api, "X")` (`getattr`/`setattr`/`patch.object`);
   - strings `"api.X"` (`mock.patch`/`monkeypatch.setattr`);
   - `api.__dict__["X"]`;
   - `vars(api)`/`dir(api)`.

   Resultado: **0 acertos**. Controle positivo com os nomes que ficaram (`format_response`, `_npcs_block`, `_world_block`, `_combat_block`, `gamedata`, `_enforce_owner_budget`): o scanner acha `playtest/invariants.py:2177/2528/2630/2901`, `evals/core/adapters.py:1194`, `tests/test_spec304_playtest.py:85` (a forma `call2`) e dezenas de testes. Ele enxerga leituras dentro de `try/except`. Arquivos que não são Python (`git grep -E "api\.(<91 nomes>)\b" -- ':!*.py'`): só aparecem `openapi.json` (falso positivo do nome `json`) e menções históricas em `docs/spec188`/`specs/SPEC-233`. Nenhum runbook executável usa os nomes. **Nenhum P0.**
2. **`tests/test_api_surface.py` pega a regressão.** Ele descobre consumidores por AST estática, não por lista fixa. Cobre `api.X`, aliases locais, `from api import X` e `f(api, "X")` com string constante, em qualquer ponto da árvore, `except` incluído. Prova negativa feita numa cópia da HEAD fora do repo (`git archive HEAD` no scratchpad, já apagada): tirei `_inventory_block as _inventory_block`, cujo único consumidor é `tests/test_fase43.py:306` por `import api as api_mod`, e o teste reprovou com `tests/test_fase43.py:306 _inventory_block`. As lacunas estão em P3-1.
3. **Efeito colateral.** `scripts/dev/api_surface_dump.py` mede `sys.modules` adicionados por `import api`, mais OpenAPI, rotas, middleware, handlers e lifecycle, em subprocesso limpo, nos perfis `legacy` e `hosted-supabase`. Rodei o dump da base (extraída por `git archive 3082b857`) e o da HEAD: `diff -r` **IDENTICAL** nos 12 arquivos. `vercel_app` só faz `from api import app`, então o conjunto de módulos é o mesmo. Nenhum dos 91 era o único import de um módulo com registro no import.
4. **Ordem e ciclos.** O bloco de reexports da SPEC-381 R9 continua no mesmo lugar. Só ganhou linhas dentro dos `from` que já existiam. `sys.path.append` e `import main  # noqa: F401` ficam onde estavam. `import api, vercel_app` funciona em `legacy` (`vercel_app.app is api.app` True) e em `hosted` com o `HOSTED_ENV` do dump (rc 0). O ruído de conexão ao pooler no stderr do perfil hosted também aparece na base, então não é regressão.
5. **Baseline do ruff.** `ruff_baseline.py` (lido antes de rodar) recompõe a baseline a partir de `ruff check .` e a restaura depois. `--check` → `ruff-baseline.toml is current`. As entradas `C901` de `agents/storyteller.py` e de `scripts/bestiario/calibrar.py` já estavam defasadas na base. Os dois arquivos não mudam no diff, e `ruff check --isolated --select C901` neles dá `All checks passed`. A remoção só aperta o gate. `size_budget`: `api.py` tem 984 linhas, abaixo de 1.000, e `test_size_budget.py` passa.
6. **Testes migrados.** Sete trocas de prefixo `api.gamedata.X` → `gamedata.X` e `api.load_json_data` → `gamedata.load_json_data`. É o mesmo objeto, porque a base fazia `import gamedata` / `from gamedata import load_json_data`. Nenhuma asserção mudou de sentido.
7. **Escopo e regras.** `ruff check` e `ruff format --check` passam nos arquivos do diff. A função mais longa de `test_api_surface.py` tem ~20 linhas. Não há helper novo de produto nem `except` largo: o `except (SyntaxError, UnicodeDecodeError)` do scanner é estreito. Os 18 reexports novos passam em `test_reexports_are_identical_and_not_rebound`: mesmo objeto do módulo de origem, nenhum nome patchado (`LARS`) e nenhum religado por `global`. Os consumidores de `_enforce_owner_budget`, `_begin_state_mutation` etc. só chamam essas funções, sem patchá-las.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-1 | P3 | `tests/test_api_surface.py:19-35,38-44` | O scanner deixa de fora `workers/`, `docs/**` (onde existe um `import api` em `docs/spec397/smoke/smoke397_driver.py`), `project_index/` e `.claude/`. Também não reconhece `importlib.import_module("api")`, `sys.modules["api"]` nem strings `"api.X"` em `mock.patch`. Hoje não há nenhuma ocorrência dessas formas (`git grep` vazio; o meu scan do repo inteiro deu 0), então o teste não deixa nada passar agora. Só vale para o futuro. | Follow-up opcional: varrer `git ls-files '*.py'` em vez de `_DIRS` e acrescentar as formas `"api.X"` e `import_module("api")`. |
| P3-2 | P3 | `docs/spec406/README.md:9` | O texto da Etapa 0 diz "Os outros 19 viram `X as X`" e "Mortos: 89". O resultado final (README § Execução e spec §9) é 18 reexports e 91 removidos, porque `gamedata` e `load_json_data` também saíram via D2. Esse trecho ficou inconsistente com o fechamento. | Ajustar a frase para "18 viram `X as X`; `gamedata` e `load_json_data` saem via D2; 91 removidos". Só documentação. |
| P3-3 | P3 | `specs/SPEC-406-api-imports-mortos.md` §5 (critério do baseline) | O critério marcado diz "mais nenhuma entrada alterada", mas duas outras entradas mudaram. A spec §9 registra o desvio, e o desvio é correto (só aperta). | No pouso, reescrever o critério ou acrescentar "(ver §9)". |

Nenhum P0, P1 ou P2.

## Correções aplicadas

Nenhuma até agora: a revisão é só leitura.

## Pendências

- P3-1: follow-up opcional de endurecimento do scanner (coordenador decide se vira spec ou entra numa onda de tooling).
- P3-2/P3-3: ajuste de texto no pouso pelo coordenador.
- Ainda pendentes na spec: a suíte completa 1× no pouso, depois do rebase sobre `0b00fe9a`. Nessa base, `test_spec352…::test_view_offer_present_when_eligible` já deve passar com o conserto da 409.

## Comandos rodados

```text
scan.py (AST próprio, base×HEAD) → removidos 91 · arquivos 1380 · hits 0
scan.py com controle positivo → acha playtest/invariants.py:2177/2528/2630/2901, evals/core/adapters.py:1194, tests/test_spec304_playtest.py:85
git grep -E "api\.(<91>)\b" -- ':!*.py' → só openapi.json (falso positivo) e docs históricos
git grep "patch('api.|import_module('api')|sys.modules['api']" → vazio
api_surface_dump base(3082b857) × HEAD, legacy+hosted → diff -r IDENTICAL (12 arquivos)
import api, vercel_app (legacy / hosted HOSTED_ENV) → ok / rc 0 (ruído de pooler igual na base)
cópia HEAD sem `_inventory_block` → pytest tests/test_api_surface.py rc=1 "tests/test_fase43.py:306 _inventory_block"
ruff_baseline.py --check → ruff-baseline.toml is current
ruff check --isolated --select C901 agents/storyteller.py scripts/bestiario/calibrar.py → All checks passed
ruff check / ruff format --check (arquivos do diff) → All checks passed / 5 files already formatted
pt.sh (-n 2) test_api_surface, spec381_*, spec387_text, boot_policy, http_security_headers, os 3 migrados, size_budget, abuse_policy, api_attempt_telemetry, fase43, fase61, streaming, fallback_logging, spec235_reclaim_local, bug_api_pending_erros, spec304_playtest, image_quotes, spec353_misc, spec197_daily_cap, llm_logging, bug_finops_wallet_jobs, fase2, weather_global, spec307_display_api → 507 passed, 5 skipped, rc=0
```
