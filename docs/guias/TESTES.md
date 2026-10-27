# Testes, lint e CI — como rodar sem desperdício

> Workspace #5/#10 (`docs/melhorias_workspace/04-testes-e-ci.md`, `02-linters-e-checks.md`).
> Todos os comandos a partir da raiz (ou via `bash scripts/dev/py.sh …`).

## Camadas da suíte

| Camada | Comando | Quem | Tempo |
|---|---|---|---|
| 0 | `ruff check <arquivos>` + `pytest -q --lf -x` | executor, a cada iteração (`/qa`) | < 30 s |
| 1 | `pytest -q -p no:cacheprovider tests/test_<escopo>*.py` | executor, antes do hand-back | 1–2 min |
| 2 | `pytest -q -p no:cacheprovider -n auto` | **coordenador**, 1× por spec no `/spec-land`, em background | ~2 min local (antes ~11 min serial) |
| 3 | suíte completa `-n auto` + `project_index check` + evals + Playwright | CI | como hoje |

Regras: executor **não** roda a camada 2; comando > 2 min vai para background com
`timeout` explícito; espere com uma notificação, nunca `sleep` em loop.

## Paralelismo (pytest-xdist) e timeout

- `-n auto` é opt-in (o default local segue serial para não disputar CPU com
  agentes paralelos). Medido em 19/10: suíte inteira em 1m44s com `-n auto`.
- No Windows, `tests/conftest.py` aponta o `basetemp` para `%TEMP%\pt-<hash do
  checkout>` quando há `-n`: o `popen-gwN` estourava o MAX_PATH de 260 chars.
- `timeout = 300` por teste (`pytest-timeout`) — nada pendura a suíte.
- Coleta tem de ser determinística (ids de `parametrize` sem `time()`/uuid), senão o
  xdist recusa ("Different tests were collected").
- Teste que grava em diretório fixo precisa de `tmp_path`/monkeypatch (o
  `conftest.py` já isola saves, memória, cache de runtime e `saves_playtest/`).
- Markers `infra_local`/`security_local`/`browser_local`/`chaos_local` pulam sem a
- Fuzz da API (SPEC-338, `api_fuzz`, fora do default): `uv sync --group fuzz` e `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p no:cacheprovider` (~20 s; `RPG_API_FUZZ_MAX_EXAMPLES=5` para iterar). Job `api-fuzz` do CI é bloqueante.
  stack local; com stack, rode-os **sem** `-n` (compartilham Postgres/porta).
- `tests/test_project_index.py` acusa "stale" com arquivo **rastreado** editado e
  não commitado; arquivo não rastreado não conta mais.

## Ruff (incremental)

- Regras: `F`, `B`, `E4/E7/E9`, `I` (isort) e `UP` (py313) em `pyproject.toml`.
  `E501` fora; `B905` depois. `ruff format` é obrigatório (`ruff format --check .` no CI e
  no pre-commit); `evals/core`, `evals/evaluators`, `evals/__main__.py`, `evals/datasets` e
  `web/e2e/contracts` ficam fora do format e de `I`/`UP` (hashes travados da régua).
- Dívida antiga congelada em `ruff-baseline.toml` (gerado; só encolhe):
  conserte um arquivo e rode `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py`.
  Arquivo novo recebe todas as regras.
- Degraus 1–3 concluídos (I, UP, format). Antes de commitar: `ruff check --fix` + `ruff format`.

## Frontend

- `npm run typecheck` (src, bloqueante via build), `npm run typecheck:e2e`
  (e2e/tests) e `npm run lint` (ESLint: typescript-eslint, react-hooks, jsx-a11y).
  Os dois últimos entram no CI como não bloqueantes até zerar os achados de 19/10
  (25 erros de tsc, ~90 de ESLint); depois remova o `continue-on-error`.

## pre-commit (opcional)

`uv tool install pre-commit && pre-commit install` — ruff, fim de linha LF, YAML,
arquivo > 500 KB, marcador de conflito, `spec_index.py check` e teto do ESTADO,
só nos arquivos staged.
