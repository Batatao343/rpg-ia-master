# SPEC-414 — workspace-pytest-confiavel

> **Status:** `approved`
> **Criada:** 2026-11-12 · **Atualizada:** 2026-11-12
> **Depende de:** nenhuma (SPEC-386 `done` é a base dos hooks; não é reaberta). Mesma onda de 415–418, sem arquivo em comum (ver Fora de escopo).
> **Desbloqueia:** SPEC-415 (o `land_check.sh` pode chamar `full.sh`), auditoria W-A fechada.
> **Risco:** `médio`. Motivo: além de tooling, muda `tests/conftest.py` (o `basetemp` de toda execução paralela da suíte), `scripts/dev/env.sh` (qual venv todo worktree usa) e põe um hook que pode **negar chamadas `Agent` do coordenador**. Bug em qualquer um trava ou falseia o trabalho de todas as sessões. → revisor Sonnet (`spec-reviewer` com `model: sonnet`), não só testes + lint.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Evidência:** um teste que falha antes por item (R1–R6), listados em §4; mais smoke real (§6) de `full.sh`, de dois pytest simultâneos e do hook `Agent` numa sessão do Claude Code.

---

## 1. Contexto & Objetivo

A auditoria de 11/11 (`docs/auditorias/auditoria-workspace-2026-11-11.md:12-15`, achados B1 e B4 em `:30-31` e `:36`) achou cinco formas de o pytest local mentir ou atrapalhar:

- **Exit code mascarado.** As skills mandam `pytest … 2>&1 | tail -15` (`.claude/skills/qa/SKILL.md:12-14`, `.claude/skills/wrap-up/SKILL.md:11`). Sem `pipefail`, o rc é o do `tail` (0). `pt.sh` acerta o rc (`scripts/dev/pt.sh:11-16`), mas fixa `-x` e `-n 2` (`:9-11`) e não serve para a suíte completa.
- **Worker morto vira `FAILED`.** `-n auto` com pouca RAM mata worker do xdist; 12 falsos numa rodada de 11/11. Nenhum wrapper escolhe `-n` pela RAM nem distingue crash de falha real (`.claude/skills/spec-land/SKILL.md:23` manda `-n auto` cru).
- **`basetemp` compartilhado.** `tests/conftest.py:55-56` usa `%TEMP%\pt-<sha1 do checkout>`: dois pytest no mesmo checkout usam o mesmo diretório, e o pytest apaga um `basetemp` explícito ao começar, então o segundo apaga o primeiro.
- **Venv errado em worktree.** `scripts/dev/env.sh:13-16` só usa o venv do principal quando o worktree **não** tem `.venv`. Se um `uv run` cria `.venv` no worktree, ele fica sem extras (`AGENTS.md:78` e `README.md:26` ensinam `uv sync` sem `--all-extras`) e passa a ser o preferido. `scripts/dev/wt.sh:90-96` não avisa nada.
- **Guarda com falso positivo (B1).** `.claude/hooks/guard_tools.py:95-97` nega quando o comando inteiro contém "pytest" **e** um `-n <x>` em qualquer lugar: `sed -n 80,200p f | grep pytest`, `git log -n 5 --grep pytest` e até `uv run pytest tests/x.py | tail -n 40` (o `-n 40` é do `tail`) são negados. B4: `/qa` camada 2 e `/wrap-up` passo 1 mandam `-n auto`, que o hook nega em subagente, sem dizer que são do coordenador.

E um sexto, de processo: `general-purpose`/sem tipo só com motivo é regra em texto (`CLAUDE.md:19-26`); medido em 04–11/11: 34 de 166 chamadas `Agent` sem tipo (`scripts/dev/agent_stats.py:82-83` conta por `subagent_type`). Nada cobra.

Objetivo: a suíte completa local passa a ter um único caminho (`scripts/dev/full.sh`) com rc real e `-n` pela RAM; execuções simultâneas não colidem; worktree usa um venv conhecido; a guarda deixa de negar comando que não é pytest; e o hook cobra o motivo do `Agent` sem tipo. Preservar (auditoria `:50-51`): `pt.sh`, regra de `-n 2` em subagente, hooks da SPEC-386, `wt.sh`.

## 2. Requisitos

Linhas citadas = `main` em `ef5d1607`.

- **R1 — `scripts/dev/full.sh` (suíte completa do coordenador).**
  - **R1.1** `-n` escolhido por `scripts/dev/full_plan.py workers`: `n = floor((livre_gb − RESERVA_GB) / POR_WORKER_GB)`, limitado a `[2, min(cpus, MAX_WORKERS)]`. Livre < `PISO_GB` ⇒ não roda, imprime a RAM livre e "feche processos ou use FULL_N=<n>", sai com **rc 3**. RAM ilegível ⇒ `n = 2`. `FULL_N=<inteiro>` no ambiente pula o cálculo (e o piso) e é impresso. Constantes iniciais: `PISO_GB = 3.0`, `RESERVA_GB = 2.0`, `MAX_WORKERS = 6`, `POR_WORKER_GB = <MEDIR: pico de RSS por worker, ver Etapa 0.2>`.
  - **R1.2** RAM livre medida sem dependência nova: Windows via `ctypes` `GlobalMemoryStatusEx` (`ullAvailPhys`); Linux via `MemAvailable` de `/proc/meminfo`; outro SO ⇒ `None`.
  - **R1.3** Saída da pytest vai inteira para `${TMPDIR:-${TEMP:-/tmp}}/rpg-full-$$.log`; na tela só as linhas de falha + resumo (mesmo filtro de `pt.sh:13-14`) e uma linha final `full rc=<rc> · n=<n> · mortos=<k> · log: <caminho>`. O rc do script é o da pytest (capturado antes de qualquer filtro), nunca o de `grep`/`tail`. Sem `-x`.
  - **R1.4** Worker morto: `full_plan.py crashed <log>` extrai os ids de `worker 'gwN' crashed while running '<nodeid>'` (formato do xdist instalado, confirmado na Etapa 0.3). Se houver 1 ≤ k ≤ `MAX_RERUN` (20) ids, re-roda **só esses** em série (`-n 0 -p no:cacheprovider`), log em `rpg-full-$$-rerun.log`. rc final: 0 só se as falhas da 1ª rodada eram todas de crash **e** o rerun passou; qualquer `FAILED`/`ERROR` fora dos ids de crash ⇒ rc 1 (o rerun ainda roda, para informar). k > 20 ⇒ não re-roda, rc 1, mensagem "N workers morreram: RAM; rode com FULL_N menor".
  - **R1.5** Argumentos extras passam para a pytest (`bash scripts/dev/full.sh -k foo`). `FULL_PYTEST` (só para teste) troca o comando da pytest; default `uv run --frozen python -m pytest -p no:cacheprovider --tb=short -W ignore`.
  - **R1.6** Em subagente, `guard_tools.py` nega `scripts/dev/full.sh` com "suíte completa é do coordenador; use `bash scripts/dev/pt.sh <testes>`" (ver D5).
- **R2 — Skills.** `/qa` camada 0 e 1 passam a usar `bash scripts/dev/pt.sh` (`--lf` / `tests/test_<escopo>*.py`), camada 2 e `/wrap-up` passo 1 e `/spec-land` passo 3 passam a `bash scripts/dev/full.sh` (background, `timeout: 1200000`). `/qa` camada 2 e `/wrap-up` passo 1 dizem literalmente "suíte completa: só coordenador". Nenhuma das três skills contém `pytest … | tail` nem `-n auto`.
- **R3 — `basetemp` por execução.** Quando `tests/conftest.py` define o `basetemp` (mesmas condições de hoje, `:51-54`), o nome passa a `pt-<sha8 do checkout>-<pid do controlador>`. Antes de defini-lo, remove de `tempfile.gettempdir()` os diretórios que casam `^pt-[0-9a-f]{8}(-\d+)?$` (inclui o formato antigo sem PID) com mtime mais velho que `MAX_IDADE_S = 6 h` (D7); erro de remoção é ignorado (`# silent-ok: limpeza best-effort`). Nunca toca outro nome; nunca usa `os.kill` para testar PID (no Windows `os.kill(pid, 0)` chama `TerminateProcess`). Lógica em função pura testável (`tests/basetemp_support.py`), `conftest.py` só chama.
- **R4 — Venv em worktree.**
  - **R4.0 (gate)** A Etapa 0.1 verifica que reusar o venv do principal é seguro (critérios lá). Se algum critério falhar, R4.1 não é implementado: só R4.2/R4.3, e a spec registra o motivo.
  - **R4.1** `env.sh`: se `RPG_ROOT` ≠ checkout principal (1ª entrada de `git worktree list`) e `UV_PROJECT_ENVIRONMENT` não veio do ambiente: se `uv.lock` do worktree é idêntico ao do principal (`cmp -s`) e `$RPG_MAIN/.venv` existe ⇒ exporta `UV_PROJECT_ENVIRONMENT=$RPG_MAIN/.venv` **mesmo que o worktree tenha `.venv`** (avisa em stderr: "ignorando <wt>/.venv; venv do principal"). `uv.lock` diferente ⇒ não exporta e avisa em stderr: "uv.lock difere do principal: este worktree usa venv próprio; rode `uv sync --all-extras --frozen` aqui" (D6). No checkout principal, comportamento inalterado. `UV_PROJECT_ENVIRONMENT` já definido é respeitado sempre.
  - **R4.2** `wt.sh new`: depois de criar o worktree, avisa **em stderr** (stdout continua só o caminho, que chamadores capturam): "venv: <MAIN>/.venv (não rode `uv sync` no worktree)"; se `$MAIN/.venv` não existe: "sem venv no principal: rode `uv sync --all-extras` em <MAIN>".
  - **R4.3** Docs: `AGENTS.md:78` e `README.md:26` passam a `uv sync --all-extras`; `docs/guias/TESTES.md:31` (`uv sync --group fuzz`) passa a `uv sync --all-extras --group fuzz` (o `uv sync` é exato e removeria os extras do venv compartilhado).
- **R5 — B1: guarda só casa pytest de verdade.** `check_shell` (`guard_tools.py:94-101`) aplica a regra de `-n` por **parte de pipeline** (reusa `SEGMENT_SPLIT` e `_split_pipeline`): a parte é pytest quando, nas suas palavras (`_words`), aparece `pytest`/`py.test` (basename, sem `.exe`), a sequência `-m pytest`, ou `pt.sh`/`full.sh` como basename; o `-n`/`-nX`/`--numprocesses[=]X` só conta se vier **depois** desse token na mesma parte. Negar continua: `auto`, `logical` ou > 2. Coordenador (`agent_id` ausente) continua livre.
- **R6 — Hook `Agent` sem tipo.** `guard_tools.py` ganha `check_agent(ti)` para `tool_name == "Agent"` (e `"Task"`, nome antigo): se `subagent_type` é ausente, vazio, `general-purpose` ou `claude` (comparação sem caixa), exige no `prompt` uma linha que case `^\s*Motivo sem tipo:\s*(.{10,})$` (multiline; ≥ 10 caracteres não brancos após o rótulo). Sem ela ⇒ nega com: "Agent sem tipo exige linha `Motivo sem tipo: <por quê>` no prompt. Tipos do repo: spec-executor, spec-reviewer, spec-author, code-locator, audit-reader, ci-watcher (ver CLAUDE.md)." Qualquer outro `subagent_type` (tipos do repo, `Explore`, `Plan`, `claude-code-guide`, desconhecidos) passa. Vale para coordenador e subagente. Erro interno ⇒ permite (contrato do hook, `guard_tools.py:5`). `settings.json:55` matcher vira `Read|Bash|PowerShell|Agent|Task`. `CLAUDE.md:24` ganha "(linha `Motivo sem tipo: …`; o hook nega sem ela)".

### Fora de escopo

- `specs/TEMPLATE.md`, `scripts/dev/land_check.sh`, preflight de colisão em `wt.sh sync/land`, `/estado --handoff` (SPEC-415). Esta spec toca `wt.sh` **só** no ramo `new` (R4.2).
- `DECISOES_FIXAS.md`, pgTAP no CI, catraca de relógio, baseline do ruff por contagem (SPEC-416); teste enfraquecido e Hypothesis (SPEC-417); gate de tipos (SPEC-418).
- Mudar `pt.sh` (preservado; `-x`/`-n 2` seguem certos para iteração).
- Cobrar `model` no `Agent`, ou limitar quantidade de agentes por hook.
- Lock entre sessões, hook que bloqueie todo `| tail` (auditoria `:47-48`, "não fazer").
- Rerun genérico de flake (`pytest-rerunfailures`): só crash de worker é re-rodado.
- CI (camada 3): continua com `-n auto` e `PIPESTATUS` próprios.

## 3. Design técnico

### Arquivos novos

| Caminho | Responsabilidade |
|---|---|
| `scripts/dev/full.sh` | wrapper da suíte completa (R1); ≤ 50 linhas de bash, lógica no `.py` |
| `scripts/dev/full_plan.py` | `free_ram_gb() -> float \| None`, `pick_workers(free_gb: float \| None, cpus: int, env_n: str \| None) -> int \| None` (`None` = abaixo do piso), `crashed_ids(log: str) -> list[str]`, `failed_ids(log: str) -> list[str]`, `verdict(failed: list[str], crashed: list[str], rerun_rc: int \| None) -> int`; CLI `workers` (imprime n ou sai 3) e `crashed <log>` (um id por linha) e `verdict …` |
| `tests/basetemp_support.py` | `basetemp_name(checkout: Path, pid: int) -> str`, `prune_old_basetemps(tmpdir: Path, now: float, max_age_s: float) -> list[Path]` |
| `tests/test_full_plan.py` | testes de R1 (Python + `full.sh` com `FULL_PYTEST` fake) |
| `tests/test_basetemp.py` | testes de R3 |
| `tests/test_dev_env.py` | testes de R4 (`env.sh` e `wt.sh new` num repo git temporário) |
| `docs/spec414/medicoes.md` | resultados da Etapa 0 e do smoke §6 |

### Arquivos alterados

| Caminho | Mudança |
|---|---|
| `.claude/hooks/guard_tools.py` | R5 (`_is_pytest_part`, `_xdist_after`), R1.6, R6 (`check_agent`, ramo em `main`) |
| `.claude/settings.json` | matcher `:55` (R6); allowlist `Bash(bash scripts/dev/full.sh:*)` |
| `.claude/skills/qa/SKILL.md`, `wrap-up/SKILL.md`, `spec-land/SKILL.md` | R2 |
| `tests/conftest.py` | `:46-56` chama `tests/basetemp_support.py` (R3); docstring cita PID |
| `scripts/dev/env.sh` | `:5` comentário e `:13-16` (R4.1) |
| `scripts/dev/wt.sh` | ramo `new` `:90-96` (R4.2) |
| `tests/test_workspace_hooks.py` | casos de R5, R6, R1.6; matcher no teste de settings |
| `tests/test_dev_tooling.py` | teste de R2 |
| `docs/guias/TESTES.md` | `:12` camada 2 = `bash scripts/dev/full.sh`; `:22-23` basetemp com PID e limpeza; `:31` (R4.3); 2 linhas: `full.sh` (piso, `FULL_N`, rerun) e venv em worktree |
| `docs/guias/BRIEF_SUBAGENTE.md` | `:47` "(o coordenador roda `full.sh` no `/spec-land`; o hook nega em subagente)" |
| `AGENTS.md:78`, `README.md:26` | R4.3 |
| `CLAUDE.md:24` | R6 (uma frase) |

### Formatos

Saída de `full.sh` (exemplo):

```
full: RAM livre 7.9 GB -> n=4 (FULL_N para forçar)
FAILED tests/test_x.py::test_a - worker 'gw2' crashed while running 'tests/test_x.py::test_a'
full: 1 worker morto; rerun serial de 1 id -> rc=0
full rc=0 · n=4 · mortos=1 · log: /tmp/rpg-full-1234.log
```

Prompt de `Agent` aceito sem tipo (exemplo):

```
SPEC-414 · worktree … · decisões do dono: …
Motivo sem tipo: precisa de WebFetch e Edit juntos; nenhum tipo do repo tem os dois.
```

## 4. Plano passo a passo

Executor: só os testes do escopo via `bash scripts/dev/pt.sh` (`-n 2`); nunca `full.sh` nem a suíte completa (o coordenador roda no pouso, já com `full.sh` como smoke).

### Etapa 0 — Medições e verificação do venv (sem código; resultado colado em `docs/spec414/medicoes.md`)

0.1 **Segurança de reusar o venv do principal (gate de R4.1).** Num worktree descartável (`bash scripts/dev/wt.sh new spec-414-venv`, removido no fim com `drop`), com `UV_PROJECT_ENVIRONMENT=<MAIN>/.venv`:
  1. Projeto não é instalado no venv: `<MEDIR: grep -n "build-system\|^package" pyproject.toml>` (esperado: nada; projeto virtual) e `<MEDIR: ls <MAIN>/.venv/Lib/site-packages/*.pth; grep -il "rpg\|Trabalho" <MAIN>/.venv/Lib/site-packages/*.pth>` (esperado: nenhum `.pth` aponta para o checkout).
  2. Import resolve no worktree: `<MEDIR: bash scripts/dev/py.sh -c "import api, state, sys; print(api.__file__, state.__file__)">` (esperado: caminhos sob o worktree).
  3. Sem fallback para o principal: no worktree, `git rm -q world_utils.py` (sem commit) e `<MEDIR: bash scripts/dev/py.sh -c "import world_utils">` ⇒ `ModuleNotFoundError`; depois `git checkout -- world_utils.py`.
  4. `uv run --frozen` com lock igual não altera o venv: `<MEDIR: uv pip freeze --python <MAIN>/.venv antes e depois de bash scripts/dev/py.sh -c "pass" no worktree; diff vazio>`.
  5. Lock diferente altera o venv do principal (prova a necessidade do `cmp`): só leitura, `<MEDIR: uv --version; uv run --help | grep -i -- "--exact\|--inexact">`; registrar se o sync do `uv run` é inexato (instala sem remover).
  6. Concorrência: `<MEDIR: (cd <MAIN> && bash scripts/dev/py.sh -c "import api") & (cd <WT> && bash scripts/dev/py.sh -c "import api"); wait>` ⇒ ambos rc 0.
  - Critério: 1–4 e 6 como esperado ⇒ R4.1 segue. Qualquer falha ⇒ registrar, pular R4.1, manter R4.2/R4.3.
0.2 `POR_WORKER_GB`: pico de RSS de um worker durante a suíte: `<MEDIR: rodar bash scripts/dev/ram.sh a cada ~20 s durante 1 suíte -n 4 do coordenador; maior WorkingSet de "python … -c … xdist"/gwN>`. Valor = pico arredondado para cima em 0,25 GB. Só o coordenador mede (é uma suíte completa).
0.3 Formato do crash no xdist instalado: `<MEDIR: grep -n "crashed while running" .venv/Lib/site-packages/xdist/dsession.py>`; o teste da Etapa 3 também captura o formato real.
0.4 Lixo atual: `<MEDIR: ls -d "$TEMP"/pt-* | wc -l; du -sh "$TEMP"/pt-*>` (antes de R3, para o critério de limpeza).
0.5 Base de comparação do hook `Agent`: `<MEDIR: bash scripts/dev/py.sh scripts/dev/agent_stats.py --help>` para o comando que reproduz "34 de 166" (04–11/11); registrar o comando para a re-medição pós-pouso.

### Etapa 1 — R5 (B1), testes primeiro

1. **Testes** (`tests/test_workspace_hooks.py`, padrão `_run`/`_sh(agent=True)` de `:17-61`), vermelhos hoje:
   - `test_subagent_non_pytest_dash_n_is_allowed` (parametrize): `sed -n 80,200p tests/x.py | grep pytest`; `git log -n 5 --grep pytest`; `uv run pytest tests/x.py | tail -n 40`; `echo pytest && head -n 50 README.md` ⇒ `None`. (Os três primeiros são negados hoje; o 4º também.)
   - `test_subagent_heavy_pytest_is_denied` ganha: `bash scripts/dev/pt.sh tests/ -n 4`; `bash scripts/dev/py.sh -m pytest -n auto`; `PYTHONUTF8=1 uv run --frozen python -m pytest --numprocesses 4`; `cd sub && uv run pytest -nauto | tail -n 5` ⇒ negados (os que já passam seguem passando).
   - `test_pytest_light_or_coordinator_is_allowed` ganha `uv run pytest -n 2 tests | tail -n 40` (agente) ⇒ `None`.
2. **Implementação:** R5 em `guard_tools.py`; `XDIST_RE` vira checagem por palavras.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_workspace_hooks.py`.

### Etapa 2 — R6 e R1.6 (hook `Agent`, `full.sh` em subagente)

1. **Testes** (`tests/test_workspace_hooks.py`), vermelhos hoje:
   - `test_agent_without_type_needs_reason` (parametrize `subagent_type` ∈ {ausente, `""`, `general-purpose`, `claude`, `General-Purpose`}): prompt sem marcador ⇒ negado e o motivo contém `Motivo sem tipo:`; prompt com `Motivo sem tipo: precisa de web e edição juntos` ⇒ `None`; `Motivo sem tipo: ok` (curto) ⇒ negado; marcador no meio de linha (`x Motivo sem tipo: …`) ⇒ negado.
   - `test_agent_typed_or_builtin_is_free` (parametrize `spec-executor`, `code-locator`, `Explore`, `Plan`, `claude-code-guide`, `tipo-novo`) ⇒ `None`; idem com `tool_name: "Task"`.
   - `test_agent_guard_never_crashes`: `tool_input` sem `prompt`, `prompt` não string ⇒ sem exceção (rc 0; decisão conforme regra).
   - `test_subagent_cannot_run_full_suite`: `bash scripts/dev/full.sh` com `agent=True` ⇒ negado; sem `agent` ⇒ `None`.
   - `test_settings_register_every_hook_checkout_relative` (`:199`) ganha: o grupo de `guard_tools.py` tem matcher com `Agent`.
2. **Implementação:** `check_agent` (≤ 30 linhas), ramo em `main()` (`:146-149`), R1.6 em `check_shell`, matcher e allowlist em `settings.json`.
3. **Verificação:** idem Etapa 1.

### Etapa 3 — R1 (`full.sh`/`full_plan.py`)

1. **Testes** (`tests/test_full_plan.py`), vermelhos hoje (módulo não existe):
   - `test_pick_workers_table`: `(None, 8) → 2`; `(2.9, 8) → None`; `(3.0, 8) → 2`; valor alto com `cpus=4 → 4`; valor alto com `cpus=16 → MAX_WORKERS`; monotônico em `free_gb`; `env_n="5"` ⇒ 5 mesmo com `free_gb=1.0`; `env_n="x"` ⇒ ignora.
   - `test_crashed_ids_from_real_xdist_crash`: escreve em `tmp_path` um teste com `os._exit(1)` e outro verde; roda `sys.executable -m pytest -n 1 -p no:cacheprovider -o addopts= --basetemp <tmp>/bt <arquivo>` (subprocess, `timeout=120`); `crashed_ids(stdout)` == `[nodeid do teste que sai]`. Oráculo do formato real (Etapa 0.3). Um só worker: compatível com a regra de RAM.
   - `test_verdict`: só crash + rerun 0 ⇒ 0; crash + falha real ⇒ 1; crash + rerun 1 ⇒ 1; nenhum crash e falha ⇒ 1; verde ⇒ 0; > 20 crashes ⇒ 1 sem rerun.
   - `test_full_sh_propagates_rc_and_reruns_crash` (skip sem `bash`): `FULL_PYTEST` aponta para um script Python fake que, na 1ª chamada, imprime uma linha `FAILED …` + `worker 'gw0' crashed while running 'tests/t.py::test_a'` e sai 1, e na 2ª (recebe `tests/t.py::test_a`) sai 0; `FULL_N=2`; asserta rc 0 e `mortos=1` na saída. Variantes: fake que sai 1 sem crash ⇒ rc 1 e nenhuma 2ª chamada; fake verde ⇒ rc 0. Garante que nenhum pipe engole o rc.
   - `test_full_sh_refuses_below_floor`: `FULL_PLAN_FREE_GB=1.0` (seam de teste lido por `free_ram_gb`) ⇒ rc 3, fake nunca chamado.
2. **Implementação:** `full_plan.py` (funções ≤ 60 linhas, sem dependência nova), `full.sh` com `set -uo pipefail`, `. env.sh`, rc capturado logo após a pytest.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_full_plan.py`.

### Etapa 4 — R3 (`basetemp`)

1. **Testes** (`tests/test_basetemp.py`), vermelhos hoje:
   - `test_basetemp_name_has_pid`: `basetemp_name(Path("C:/x"), 4242)` casa `^pt-[0-9a-f]{8}-4242$`; dois PIDs ⇒ nomes diferentes; mesmo checkout ⇒ mesmo prefixo.
   - `test_prune_removes_only_old_pt_dirs`: em `tmp_path`, cria `pt-0123abcd` (antigo, formato velho), `pt-0123abcd-77` (antigo), `pt-0123abcd-88` (novo), `pt-zz` e `outro` (antigos, nome fora do padrão); ajusta mtime com `os.utime`; `prune_old_basetemps(tmp_path, now, 6*3600)` remove só os dois primeiros e devolve-os.
   - `test_prune_survives_locked_dir`: monkeypatch de `shutil.rmtree` lançando `OSError` ⇒ não propaga.
   - `test_choose_basetemp_rules`: a decisão do `conftest` vira a função pura `choose_basetemp(platform: str, is_worker: bool, has_basetemp: bool, numprocesses: object, checkout: Path, tmpdir: Path, pid: int) -> str | None` em `tests/basetemp_support.py`; casos: `win32` + `-n` ⇒ `<tmpdir>/pt-<sha8>-<pid>`; worker xdist ⇒ `None`; `--basetemp` explícito ⇒ `None`; sem `-n` ⇒ `None`; `linux` ⇒ `None`. (Prova ponta a ponta fica no smoke §6.2.)
2. **Implementação:** `tests/basetemp_support.py`; `conftest.py:46-56` só chama `prune_old_basetemps` e `choose_basetemp`.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_basetemp.py tests/test_workspace_hooks.py`.

### Etapa 5 — R4 (venv em worktree), condicionada a 0.1

1. **Testes** (`tests/test_dev_env.py`; skip se faltar `bash` ou `git`), em repo git temporário (`git init`, commit de `uv.lock` e de cópias de `scripts/dev/env.sh` e `wt.sh`, `git worktree add`), vermelhos hoje:
   - `test_worktree_prefers_main_venv_even_with_own`: `main/.venv` e `wt/.venv` existem, lock igual ⇒ `bash -c '. scripts/dev/env.sh; echo "$UV_PROJECT_ENVIRONMENT"'` no worktree imprime `<main>/.venv`; stderr cita "ignorando". (Hoje imprime vazio.)
   - `test_worktree_with_different_lock_keeps_own_env`: lock alterado no worktree ⇒ vazio; stderr cita `uv sync --all-extras`.
   - `test_main_checkout_and_explicit_env_untouched`: no principal ⇒ vazio; `UV_PROJECT_ENVIRONMENT=/x` pré-definido ⇒ `/x`.
   - `test_wt_new_warns_on_stderr_only`: `RPG_WT_ROOT=<tmp> bash scripts/dev/wt.sh new 999` sem `main/.venv` ⇒ stdout == caminho do worktree (uma linha), stderr contém `uv sync --all-extras`; com `main/.venv` ⇒ stderr contém "não rode `uv sync`".
   - Comparar caminhos normalizados (`cygpath`/`/c/…` × `C:/…`): helper local no teste, justificado na docstring.
2. **Implementação:** `env.sh` (R4.1), `wt.sh new` (R4.2), docs (R4.3).
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_dev_env.py`.

### Etapa 6 — R2 (skills) e docs

1. **Testes** (`tests/test_dev_tooling.py`), vermelhos hoje:
   - `test_test_skills_use_wrappers` (parametrize `qa`, `wrap-up`, `spec-land`): o `SKILL.md` não casa `pytest[^\n`]*\|\s*tail` nem `-n auto`; contém `scripts/dev/full.sh`.
   - `test_full_suite_skills_say_coordinator_only` (`qa`, `wrap-up`): contém "suíte completa: só coordenador".
2. **Implementação:** as três skills; `TESTES.md`, `BRIEF_SUBAGENTE.md`, `AGENTS.md`, `README.md`, `CLAUDE.md` (linhas da §3).
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_dev_tooling.py tests/test_workspace_hooks.py`; `ruff format --check` e `ruff check` nos `.py` tocados; `scripts/dev/dup_helpers.py --diff main...HEAD`.

## 5. Critérios de aceite

- [ ] `docs/spec414/medicoes.md` com 0.1–0.5 preenchidos; veredito de 0.1 explícito (R4.1 implementado ou pulado, com motivo).
- [ ] Cada teste nomeado em §4 foi visto **falhando** antes da implementação (saída colada no hand-back do executor) e passa depois.
- [ ] `bash scripts/dev/pt.sh tests/test_workspace_hooks.py tests/test_full_plan.py tests/test_basetemp.py tests/test_dev_env.py tests/test_dev_tooling.py` verde.
- [ ] `git grep -n -- "-n auto" .claude/skills` vazio; `git grep -n "full.sh" .claude/skills` acha `qa`, `wrap-up`, `spec-land`.
- [ ] `POR_WORKER_GB` em `full_plan.py` é o valor medido em 0.2 (não o placeholder).
- [ ] Funções novas ≤ 60 linhas; `tests/test_size_budget.py` verde; nenhum helper duplicado (`dup_helpers.py`).
- [ ] Smoke §6 itens 1–4 feitos pelo coordenador, saídas coladas na spec.
- [ ] Suíte completa verde **via `bash scripts/dev/full.sh`** no pouso (1×, coordenador).
- [ ] Revisão Sonnet (risco `médio`) sem `CHANGES_REQUIRED` aberto.

## 6. Smoke test real (infra; sem LLM)

Não há LLM. O smoke é de máquina e de Claude Code, só pelo coordenador:

1. **`full.sh` real:** `bash scripts/dev/full.sh` em background (`timeout: 1200000`) no worktree da spec; anotar a linha `full rc=… · n=… · mortos=…` e o tempo. Repetir com `FULL_N=2` e comparar rc.
2. **Dois pytest simultâneos no mesmo checkout:** duas chamadas `bash scripts/dev/pt.sh tests/test_workspace_hooks.py` em paralelo (background) ⇒ ambas rc 0; `ls -d "$TEMP"/pt-*` mostra dois diretórios com PIDs distintos. Antes de R3, o mesmo par deve ser reproduzido na `main` para registrar a falha (ou registrar "não reproduziu" e o porquê).
3. **Hook `Agent` numa sessão real:** do coordenador, `Agent` com `subagent_type: general-purpose` e prompt sem marcador ⇒ negado com a mensagem de R6; mesmo pedido com `Motivo sem tipo: …` ⇒ sobe; `subagent_type: code-locator` ⇒ sobe. Confirma que o Claude Code entrega `tool_name: "Agent"` e `tool_input.subagent_type` ao hook (se não entregar, o hook é inerte, não nega: registrar).
4. **B1 real:** num subagente (`code-locator` serve), `sed -n 1,5p pyproject.toml | grep pytest` ⇒ executa (hoje negado).
5. **Worktree:** `bash scripts/dev/wt.sh new <descartável>` mostra o aviso de venv em stderr; `bash scripts/dev/py.sh -c "import sys; print(sys.prefix)"` no worktree aponta para `<MAIN>/.venv`; `wt.sh drop`.

## 7. Riscos & compatibilidade

- **Hook `Agent` nega o coordenador por engano:** fail-open em erro; regex só exige uma linha; tipos do repo e embutidos passam. Rollback = tirar `Agent|Task` do matcher (1 linha). Re-medir com o comando de 0.5 uma semana depois (esperado: 0 chamadas sem tipo e sem marcador).
- **Venv compartilhado:** branch que muda `uv.lock` cai no venv próprio (R4.1), não contamina o principal. Risco residual: alguém roda `uv sync` (exato) num worktree com o venv do principal e remove extras; mitigado pelo aviso de R4.2 e pela doc. `.pyc` ficam junto do fonte (worktree), não no venv.
- **`basetemp`:** nome muda só em Windows com `-n`; o pytest continua apagando o próprio `basetemp` no início (agora único por PID). Limpeza só por idade e padrão de nome; uma suíte nunca passa de 6 h (timeout por teste 300 s e camada 2 ~2 min). Linux/CI inalterado.
- **`full.sh` recusa com pouca RAM (rc 3):** proposital (regra de RAM do `CLAUDE.md`); `FULL_N` destrava. Crash de worker re-rodado em série pode esconder bug real que derruba processo: o rerun em série reproduz o `os._exit`/segfault e falha, então não esconde.
- **Teste que roda pytest aninhado** (`test_crashed_ids_from_real_xdist_crash`): 1 worker extra por ~5 s; sob `-n auto` do coordenador é aceitável. Se pesar, marcar `slow` (decisão do revisor).
- **Size budget:** `guard_tools.py` (158 linhas) e `conftest.py` não passam de 1.000; funções novas pequenas.
- Saves, MockLLM, FallbackLLM, quota: nenhum impacto (sem código de produto).

## 8. Decisões do dono

Decididas pelo autor (veto possível na aprovação):

- **D1** — Marcador `Motivo sem tipo: <≥ 10 caracteres>` em linha própria. Alternativa: campo em `description`. Proposta: linha no prompt (fica no transcrito e no `agent_stats`).
- **D2** — `claude` entra junto com `general-purpose`/ausente como "sem tipo". Proposta: sim (pedido do coordenador).
- **D3** — Abaixo de 3 GB livres, `full.sh` não roda (rc 3) em vez de rodar `-n 1`/serial. Proposta: recusar.
- **D4** — Teto `MAX_WORKERS = 6` (as suítes verdes de 11/11 usaram `-n 4`/`-n 6`). Proposta: 6.
- **D5** — Guarda nega `full.sh` em subagente (R1.6). Proposta: sim; é o B4 aplicado ao wrapper novo.
- **D6** — `uv.lock` diferente do principal ⇒ venv próprio do worktree com aviso, em vez de negar a execução. Proposta: venv próprio.
- **D7** — Limpeza de `pt-*` por idade (6 h), não por PID vivo (sem forma segura de testar PID no Windows sem dependência). Proposta: idade.
- **D8** — Risco `médio` (revisor Sonnet) em vez de `baixo`. Motivo no cabeçalho.
- **Aprovação (2026-11-12):** aprovada pelo coordenador por delegação do dono ("executa as mudanças", 12/11; semana de segurança e qualidade). D1–D8 aceitas como escritas. Medição 0.2 (`POR_WORKER_GB`) fica com o coordenador no pouso; o executor usa 1,0 GB provisório.
