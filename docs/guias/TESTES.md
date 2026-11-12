# Testes, lint e CI — como rodar sem desperdício

> Workspace #5/#10 (`docs/melhorias_workspace/04-testes-e-ci.md`, `02-linters-e-checks.md`).
> Todos os comandos a partir da raiz (ou via `bash scripts/dev/py.sh …`).

## Camadas da suíte

| Camada | Comando | Quem | Tempo |
|---|---|---|---|
| 0 | `ruff check <arquivos>` + `pytest -q --lf -x` | executor, a cada iteração (`/qa`) | < 30 s |
| 1 | `pytest -q -p no:cacheprovider tests/test_<escopo>*.py` | executor, antes do hand-back | 1–2 min |
| 2 | `bash scripts/dev/full.sh` | **coordenador**, 1× por spec no `/spec-land`, em background | ~2 min local (antes ~11 min serial) |
| 3 | suíte completa `-n auto` + evals + Playwright | CI | como hoje |

Regras: executor **não** roda a camada 2; comando > 2 min vai para background com
`timeout` explícito; espere com uma notificação, nunca `sleep` em loop.

## Paralelismo (pytest-xdist) e timeout

- `-n auto` é opt-in (o default local segue serial para não disputar CPU com
  agentes paralelos). Medido em 19/10: suíte inteira em 1m44s com `-n auto`.
- No Windows, `tests/conftest.py` aponta o `basetemp` para `%TEMP%\pt-<hash do
  checkout>-<pid>` quando há `-n`: o `popen-gwN` estourava o MAX_PATH de 260 chars; o PID
  evita que duas execuções no mesmo checkout se apaguem. `pt-*` com mais de 6 h são
  removidos no início da execução.
- `full.sh` (SPEC-414): `-n` pela RAM livre (rc 3 abaixo de 3 GB; `FULL_N=<n>` força);
  worker morto é re-rodado em série (até 20 ids); rc é o da pytest.
- Worktree usa o venv do principal quando o `uv.lock` é igual (`env.sh`); não rode
  `uv sync` nele. `wt.sh new` avisa em stderr.
- `timeout = 300` por teste (`pytest-timeout`) — nada pendura a suíte.
- Coleta tem de ser determinística (ids de `parametrize` sem `time()`/uuid), senão o
  xdist recusa ("Different tests were collected").
- Teste que grava em diretório fixo precisa de `tmp_path`/monkeypatch (o
  `conftest.py` já isola saves, memória, cache de runtime e `saves_playtest/`).
- Markers `infra_local`/`security_local`/`browser_local`/`chaos_local` pulam sem a
  stack local; com stack, rode-os **sem** `-n` (compartilham Postgres/porta).
- Fuzz da API (SPEC-338, `api_fuzz`, fora do default): `uv sync --all-extras --group fuzz` e `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p no:cacheprovider` (~20 s; `RPG_API_FUZZ_MAX_EXAMPLES=5` para iterar). Job `api-fuzz` do CI é bloqueante.
- `project_index/repo_graph.json`/`manifest.json` são artefatos locais não versionados;
  `python -m project_index check` acusa "stale" com arquivo **rastreado** editado (rode
  `build`). Os testes do índice real constroem em diretório temporário (`index_dir`).

## Cobertura (SPEC-379)

Cobertura real da suíte roda **semanal no CI** (`.github/workflows/coverage.yml`, também
`workflow_dispatch`), sem gate de porcentagem: é medida, não trava. O artefato traz
`coverage.xml`/`coverage.json`/log e o resumo (20 módulos menos cobertos) vai no
`$GITHUB_STEP_SUMMARY`. Resumo local de um `coverage.json`:
`bash scripts/dev/py.sh scripts/dev/coverage_summary.py coverage.json --top 20`.

Local, **sempre com escopo** (cobertura da suíte completa é do coordenador ou do CI,
nunca de subagente — regra de RAM):

```bash
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 --cov=<pacote> --cov-branch --cov-report=term-missing:skip-covered tests/test_<escopo>*.py
```

Limites conhecidos: subprocessos não são medidos (D5); testes de tempo (ex.:
`test_spec361_integracao.py`) podem falhar só sob o tracer, que custa 1,5 a 3x.
A baseline fica em `docs/spec379/coverage-baseline.md`.

## Onde mora um teste novo (SPEC-379)

- Teste novo vai para `tests/test_<modulo>.py` (ex.: `tests/test_conflict_orchestrator.py`)
  ou para um arquivo de **feature** (`tests/test_<feature>.py`) — nunca para um
  `tests/test_specNNN_*.py` novo.
- O número da spec vai na docstring do teste (`"""SPEC-379 R2.3: ..."""`).
- Estado vem de `tests/factories.py` (`make_state`/`make_player`/`make_world`, compostos
  das peças canônicas do produto) e LLM vem de `tests/fakes/scripted_llm.py`
  (`ScriptedLLM`, `patch_get_llm`).
- Helper local só entra quando a fábrica não serve, com uma linha de comentário dizendo por quê.
- Teste que lê código-fonte só entra no caso (c) de `docs/spec379/fonte_inventario.md`
  (proibição de import/chamada, segurança/RLS, CSP, integridade de eval, contrato entre
  linguagens), com a justificativa no docstring. Comportamento se testa por comportamento.
- Propriedade (Hypothesis, `tests/fakes/property_settings.py`) em vez de exemplo quando o código é writer persistente (round-trip save/load) ou mecânica numérica com faixa ou conservação (dano, ouro, estoque, dados); exemplo fixo continua para regra de negócio pontual. Pouso: `scripts/dev/weak_tests.py` (check `weak-tests` do `land_check`) recusa skip/xfail novo sem motivo e teste sem assert.

## Ruff (incremental)

- Regras: `F`, `B`, `E4/E7/E9`, `I` (isort), `UP` (py313) e, desde a SPEC-388, `C90` (complexidade ≤ 15),
  `SIM`, `PERF`, `C4`, `PIE`, `RET`, `ERA`, `BLE` em `pyproject.toml` (testes isentos de `C90`/`PERF`;
  avaliadores protegidos isentos das famílias novas, gate `tests/test_ruff_protected_exempt.py`).
  `E501` fora; `B905` depois. `ruff format` é obrigatório (`ruff format --check .` no CI e
  no pre-commit); `evals/core`, `evals/evaluators`, `evals/__main__.py`, `evals/datasets` e
  `web/e2e/contracts` ficam fora do format e de `I`/`UP` (hashes travados da régua).
- Dívida antiga congelada em `ruff-baseline.toml` + `ruff-baseline-counts.json` (gerados; só
  encolhem, contagem por arquivo × regra, SPEC-416): conserte um arquivo e rode
  `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py --tighten`; `--check` confere (gate
  `tests/test_ruff_counts.py`). Regravação sem flag sobe a dívida: é do coordenador.
- Catraca de relógio real (SPEC-416): `assert` que depende de `time.time`/`perf_counter`/`datetime.now`
  em `tests/` não cresce (`tests/clock_asserts.json`, gate `tests/test_clock_asserts.py`). Use relógio
  fixo (`monkeypatch`); encolheu = `clock_asserts.py --tighten`; subir é `--update` do coordenador.
  Arquivo novo recebe todas as regras.
- Degraus 1–3 concluídos (I, UP, format). Antes de commitar: `ruff check --fix` + `ruff format`.

## Frontend

- `npm run typecheck` (src, bloqueante via build), `npm run typecheck:e2e`
  (e2e/tests) e `npm run lint` (ESLint: typescript-eslint, react-hooks, jsx-a11y).
  Os dois últimos são bloqueantes no CI (zerados em 19/10, SPEC-284).
- **e2e novo (SPEC-383):** vai no arquivo da **feature** (tabuleiro, Livro, retrato, loja…), não num
  `specNNN-*.spec.ts`; prints de evidência ficam fora do repo ou num script opt-in em `scripts/`, nunca em
  `web/e2e/`; o título de teste novo não começa por `F01`/`V01`/`M01` (prefixos do
  `scripts/frontend_eval_report.py`).

## pre-commit (opcional)

`uv tool install pre-commit && pre-commit install` — ruff, fim de linha LF, YAML,
arquivo > 500 KB, marcador de conflito, `spec_index.py check` e teto do ESTADO,
só nos arquivos staged.

## Flags

Toda variável `RPG_*` lida pelo código mora em `config/flags.yaml` (SPEC-340); o teste
`tests/test_flag_registry.py` (suíte default) falha com flag nova sem registro, entrada órfã ou
flag `release` vencida.

- **Registrar:** adicione a entrada (`kind`, `default`, `spec`, `note`; `release` exige
  `expires: AAAA-MM-DD`, ~90 dias). Nome montado em runtime: entrada com `pattern: true` e regex.
- **Renovar:** mude `expires` e justifique no `note`. **Remover:** apague a leitura no código e a entrada.
- CLI: `uv run python scripts/flag_registry.py check | list [--kind K] | expiring --days N`.
