# SPEC-418 — workspace-gate-de-tipos

> **Status:** `done`
> **Criada:** 2026-11-12 · **Atualizada:** 2026-11-12
> **Depende de:** nenhuma em código. Ordem: a ligação ao `land_check` (R14) é uma linha no `scripts/dev/land_check.py` da SPEC-415 feita pelo coordenador depois que as duas pousarem (mesmo arranjo de D-416-3); a guarda de hook e o relatório de crescimento da baseline (R12) são emenda de uma linha cada em SPEC-416 R28/R29 (D-418-6).
> **Desbloqueia:** degraus seguintes do gate de tipos (§2 "Degraus seguintes"): `agents/`, `routes/` + `api.py`, protocolo tipado do cliente LLM.
> **Risco:** `médio` — nenhum comportamento de produto muda (só configuração, um script de tooling, uma dependência do grupo `dev` e um job de CI; a única exceção possível é a anotação de tipo de retorno em `llm_setup.py` de D-418-2, sem efeito em runtime). Não é `baixo` porque cria um gate que pode recusar pouso e CI (falso positivo trava a onda), muda `uv.lock` e acrescenta um job de CI. Não é `alto`: nada de combate, persistência, auth, API pública, estado de jogo ou eval muda. Revisor Sonnet (`AGENTS.md` § Qualidade, revisão e evidência).
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Evidência:** teste que falha antes: `tests/test_type_gate.py::test_unguarded_structured_output_is_rejected` escreve em `tmp_path` um módulo que faz `get_llm(...).with_structured_output(X).invoke(...).campo` sem `isinstance` e afirma `type_gate.py --files <arquivo>` com rc 1 e diagnóstico `reportAttributeAccessIssue` citando `AIMessage` na linha do acesso; o par guardado (`isinstance`) sai rc 0. Hoje falha: não existe checador nem `scripts/dev/type_gate.py`. Mais: rodada inicial do escopo com rc 0 sobre a baseline gravada, e o job `types` verde no CI (§6).

---

## 1. Contexto & Objetivo

O projeto exige "type hints em tudo" (`AGENTS.md:145`), mas nada verifica tipos: não há pyright/mypy em `pyproject.toml` (`[dependency-groups].dev`, `pyproject.toml:48-55`), nem passo no CI (`.github/workflows/validate.yml:61-95` roda pip-audit, ruff, conteúdo, pytest e o frontend, sem checador Python), nem hook de pre-commit (`.pre-commit-config.yaml:4-35`). A auditoria de linters já registrou "Type checker: nenhum" (`docs/melhorias_workspace/02-linters-e-checks.md:13`) e propôs a L2 (`:82-87`, "pyright em modo `basic` só em `services/`, `infrastructure/`, `state.py`, `persistence.py`; `continue-on-error` por 2 semanas, depois bloquear"; custo/benefício em `:163`).

O bug que motiva a spec é o do guard crítico: `FallbackLLM.with_structured_output()` devolve o próprio fallback (`llm_setup.py:415-416`) e `invoke()` devolve `AIMessage` (`llm_setup.py:421-422`), não o schema pedido; `RoutedLLM` também pode terminar em `AIMessage(content="")` (`llm_setup.py:816-817`). Acesso a campo sem `isinstance` estoura só com provider real, porque o `MockLLM` devolve instâncias Pydantic válidas (`mock_llm.py:1036-1068`; `AGENTS.md:151-160`). `get_llm` não tem anotação de retorno (`llm_setup.py:1827`) e devolve `MockLLM | FallbackLLM | RoutedLLM` (`:1834-1845`); um checador infere essa união e reprova `resultado.campo` no ramo `AIMessage`, sem LLM. Hoje o escopo inicial tem 9 chamadas `with_structured_output(` (`services/chronicle_compression.py:86`, `creature_gen.py:1454`, `death_flow.py:356`, `encounter_preparation.py:455`, `narrative_sink.py:343`, `prologue.py:518`, `shared_pool.py:471`, `tactical_profile.py:618`, mais o docstring em `narrative_sink.py:337`); as que vi estão guardadas (`prologue.py:517-524`, `chronicle_compression.py:84-98`). O valor do gate é **preventivo** (código novo) e a spec mede quantos casos reais existem (R18), sem prometer achados.

Limite conhecido, declarado de antemão: o checador só vê o tipo quando ele flui de `get_llm`. Quem recebe `llm` como parâmetro sem anotação ou `Any` é ponto cego: `services/death_flow.py:348` (`llm` sem tipo), `services/tactical_profile.py:605` (idem), `services/narrative_sink.py:374` (`llm: Any`). Tipar esse parâmetro (protocolo do cliente LLM) é degrau seguinte, não esta spec.

Objetivo: ligar um checador de tipos com versão fixada, num escopo estreito, com legado congelado numa baseline que só encolhe (mesma catraca do `size_budget.py`, SPEC-407), erro novo bloqueando no CI depois de uma rodada de calibração e um comando que o `land_check` da SPEC-415 possa chamar. Os degraus seguem o desenho do ruff (SPEC-388: famílias novas valem para código novo, legado em baseline; `pyproject.toml:74-82`).

## 2. Requisitos

Linhas citadas = `main` em `312222db`.

### Ferramenta e versão

- **R1 — basedpyright, versão exata.** O checador é o `basedpyright` (fork do pyright), pinado com `==` no grupo `dev` (`pyproject.toml:49-55`) e travado no `uv.lock`. Versão: a mais recente publicada no PyPI há ≥ 7 dias na data da Etapa 0 (medido, 1.40.2, publicada em 2026-10-04 (`docs/spec418/medicao.md` E0.1)). `requirements.txt` não muda (é exportado sem `dev`; `tests/test_spec192_vercel_packaging.py:41` segue verde). Justificativa (D-418-1):
  1. **Instalação hermética nas duas máquinas.** O pacote do PyPI traz o Node via `nodejs-wheel-binaries`; entra por `uv sync` como qualquer dependência, com hash no lock, e roda igual no Windows de 16 GB e no runner Linux. O `pyright` do PyPI é um invólucro que baixa o pacote npm na primeira execução (rede em runtime, cache fora do lock, versão por variável de ambiente); o `npx pyright` exigiria Node pinado também no job Python.
  2. **Baseline nativa** (`--writebaseline`), casada por arquivo + regra + intervalo de colunas, tolerante a deslocamento de linha; com pyright puro seria um script próprio de comparação (~150 linhas a manter), com o risco de casamento frágil.
  3. **Regra `reportIgnoreCommentWithoutRule`**, exclusiva do basedpyright: barra `# type: ignore` sem regra em código novo, o que cumpre "ruído tratado por configuração, não por `# type: ignore` em massa".
  4. Mesmo motor e mesmas regras do pyright (`standard` idêntico), então o que o plugin `pyright-lsp` do editor mostra é um subconjunto compatível.
- **R2 — Saída de emergência escrita.** Se a Etapa 0 mostrar que a baseline nativa não é estável (critério: E0.5 falha, ou E0.8 Windows × Linux diverge), o `type_gate.py` passa a usar baseline própria por contagem `(arquivo, regra) -> n` sobre `--outputjson`, com a mesma interface de R9–R13. A decisão e o motivo vão para `docs/spec418/medicao.md`; o resto da spec não muda.

### Escopo e configuração

- **R3 — Escopo.** `[tool.basedpyright].include = ["services", "infrastructure", "state.py", "persistence.py"]` na redação original; **valor final após o corte de E0.7.3** (pico 2,4-2,7 GB > 2 GB): `infrastructure`, `state.py`, `persistence.py` e os 5 arquivos de `services/` que importam `llm_setup` (`chronicle_compression`, `creature_gen`, `daily_spend_cap`, `prologue`, `shared_pool`); o resto de `services/` é degrau seguinte. Ficam fora: `agents/`, `routes/`, `api.py`, `tests/`, `evals/`, `playtest/`, `scripts/`, `web/`, `data/`. Módulos fora do escopo continuam sendo **lidos** para inferência (ex.: `llm_setup.py`, `mock_llm.py`), mas não geram diagnóstico.
- **R4 — Plataforma fixa.** `pythonVersion = "3.13"` e `pythonPlatform = "Linux"`, para que Windows e CI produzam o mesmo conjunto de diagnósticos e a mesma baseline. Sem `venvPath`/`venv` na configuração: o comando roda via `uv run`/`py.sh`, que põe o venv do checkout (ou do worktree, SPEC-414) no `PATH`.
- **R5 — Modo `standard`, gate nas 7 regras.** `typeCheckingMode = "standard"` (não `strict`: `strict` liga `reportUnknown*` e `reportMissingTypeStubs`, que no LangChain/LangGraph/FAISS produziriam milhares de achados sem bug). Ficam `"error"` explicitamente: `reportOptionalMemberAccess`, `reportAttributeAccessIssue`, `reportCallIssue`, `reportArgumentType`, `reportReturnType`, `reportOptionalSubscript`, `reportPossiblyUnboundVariable` (nome na 1.40.2; `reportPossiblyUnbound` é rejeitado), mais `reportIgnoreCommentWithoutRule` (R1.3). Toda outra regra que o `standard` reporta como erro segue este critério, aplicado com os números da Etapa 0 (não um número fixado agora):
  - contagem **zero** no escopo → fica `"error"` (ligar não custa baseline);
  - contagem > 0 → `"warning"` na primeira rodada (aparece no relatório, não bloqueia, **não** entra na baseline), registrada em `docs/spec418/medicao.md` para o degrau 2.
  As regras exclusivas do basedpyright que não são do `standard` do pyright (`reportAny`, `reportUnusedCallResult`, `reportImplicitOverride` etc.) ficam `"none"`.
- **R6 — Ruído de biblioteca por configuração.** `useLibraryCodeForTypes = true`, `reportMissingTypeStubs = "none"`, `reportUnnecessaryTypeIgnoreComment = "none"` nesta rodada. O job de CI e o comando local rodam com **todos** os extras instalados (`uv sync --all-extras`), para que `boto3` (`portable`), `opentelemetry`, `langchain-anthropic`/`ollama` e `playwright` resolvam e não virem `reportMissingImports`. Ruído que sobrar, por biblioteca, segue esta ordem: (1) stubs do typeshed já embutidos no checador; (2) pacote de stubs no grupo `dev`, pinado; (3) stub local mínimo em `typings/<lib>/` (`stubPath`) só com os símbolos usados; (4) último recurso, o diagnóstico legado vai para a baseline e código novo usa a biblioteca por um adaptador tipado. Proibido: `# type: ignore`/`# pyright: ignore` em massa e desligar uma das 7 regras de R5 por causa de uma biblioteca. Os 43 `type: ignore` já existentes no escopo (23 arquivos) continuam valendo; sem regra, entram na baseline via `reportIgnoreCommentWithoutRule`.
- **R7 — Configuração em `[tool.basedpyright]`** no `pyproject.toml` (não `pyrightconfig.json`, não `[tool.pyright]`; D-418-4). O plugin `pyright-lsp` do editor não lê esta seção e segue com o padrão dele.

### Baseline e catraca

- **R8 — Baseline versionada.** `.basedpyright/baseline.json` (local padrão do checador), versionada, gerada na Etapa 2. Só contém diagnósticos de nível `error` (R5). Se ela passar de 500 KB, o `check-added-large-files` do pre-commit (`.pre-commit-config.yaml:18-20`) recusa: isso é sinal de que a baseline esconde demais e dispara o critério de corte de E0.7, não uma exceção no hook.
- **R9 — `type_gate.py --check` (padrão).** Roda o checador no escopo contra uma **cópia temporária** da baseline (`--baselinefile <tmp>` se a versão fixada tiver a opção; senão salvar e restaurar o arquivo como `scripts/dev/ruff_baseline.py:40-54`), de modo que o arquivo versionado nunca muda num check. rc 1 se houver erro novo (fora da baseline); a saída lista `arquivo:linha regra mensagem`, no máximo 40 linhas e o total. rc 0 sem erro novo.
- **R10 — Catraca: baseline folgada falha.** No mesmo `--check`, regrava a baseline **na cópia temporária** com o estado atual e compara o multiconjunto `(arquivo, regra)` com o versionado. Se o atual tiver **menos** entradas (erro legado consertado ou arquivo apagado), sai rc 1 com `baseline folgada: <arquivo> <regra> <n_base> -> <n_atual>; rode type_gate.py --tighten` (mesma regra de `scripts/dev/size_budget.py:96-114`, SPEC-407 R1/R2; sem tolerância, porque cada entrada é um erro discreto; D-418-5).
- **R11 — `--tighten`.** Recusa com rc 1 se houver erro novo (imprime a lista e "conserte ou peça `--update` ao coordenador"). Sem erro novo, regrava a baseline versionada só descendo: o resultado tem de ser sub-multiconjunto do anterior (verificado pelo script antes de gravar; se não for, não grava e sai rc 1). Imprime `removida: <arquivo> <regra> (-n)`. Idempotente. Livre para executor.
- **R12 — `--update --reason "<texto>"` é do coordenador.** Única operação que acrescenta entrada. Exige `--reason` não vazio; grava a baseline e acrescenta uma linha `AAAA-MM-DD · +N entradas · <motivo>` em `docs/spec418/baseline_log.md`. Mecanismo de "só o coordenador regrava", em três camadas:
  1. **Pouso:** `type_gate.py --land --base main` (R14) falha se a baseline do branch tiver qualquer entrada que a de `main` não tem (crescimento). Logo, nenhum branch de executor pousa com a baseline maior; o coordenador sobe a baseline, quando precisar, num commit próprio na `main` (`chore(types): raise baseline: <motivo>`).
  2. **Hook:** emenda de uma linha em SPEC-416 R28 para o `guard_tools.py` negar `type_gate.py --update` em subagente (D-418-6; esta spec não toca `guard_tools.py`).
  3. **Relatório:** emenda de uma linha em SPEC-416 R29 para `baseline_growth.py` incluir `.basedpyright/baseline.json` (pega edição à mão do JSON, que o hook não vê).
- **R13 — Erro em arquivo novo não tem baseline.** Arquivo criado depois da baseline recebe todas as regras de R5 (mesma semântica do `ruff-baseline.toml`, `scripts/dev/ruff_baseline.py:4-7`).

### Onde roda

- **R14 — Comando para o `land_check`.** `bash scripts/dev/py.sh scripts/dev/type_gate.py --land --base main` imprime **uma** linha no formato da SPEC-415 R1 (`OK|WARN|FAIL types: <detalhe>`) e sai 0/1:
  - `OK types: nada a checar` se `git diff --name-only <base>...HEAD` não tiver `.py`, nem `pyproject.toml`, `uv.lock` ou `.basedpyright/baseline.json` (mudança fora do Python não altera tipos; mudança em qualquer `.py`, mesmo fora do escopo, pode, porque o escopo importa `llm_setup.py` etc.);
  - senão roda R9 + R10 + o teste de crescimento de R12.1 e resume (`FAIL types: 2 erros novos (services/x.py:12 reportAttributeAccessIssue …)`).
  A linha que chama isto dentro do `land_check.py` é do coordenador, depois do pouso da 415 (esta spec não toca `scripts/dev/land_check.*`).
- **R15 — Sem hook de edição e sem pre-commit.** Nenhuma entrada nova em `.claude/settings.json`, `.claude/hooks/` ou `.pre-commit-config.yaml`. Localmente, o gate roda só por comando explícito (`type_gate.py`) e no pouso (R14). Subagente que tocar o escopo pode rodar `type_gate.py --check` uma vez antes do hand-back se a RAM livre for ≥ 3 GB (`bash scripts/dev/ram.sh`); senão registra "não rodei, CI cobre".
- **R16 — Job `types` no CI.** Novo job em `.github/workflows/validate.yml`, irmão do `api-fuzz` (`:97-124`): `needs: scope`; `if: github.event_name != 'schedule' && needs.scope.outputs.docs_only != 'true'`; `runs-on: ubuntu-24.04`; `timeout-minutes` = 10 (mínimo; medido: 13 s locais, o ×3 dá < 1 min); `actions/checkout` e `astral-sh/setup-uv` com os mesmos SHAs pinados e `persist-credentials: false` (zizmor, `:158-167`); passos: `uv sync --all-extras`, `uv run python scripts/dev/type_gate.py --check`, `uv run pytest tests/test_type_gate.py -m types_e2e -p no:cacheprovider --tb=short`. Herda `permissions: contents: read` (`:8-9`).
- **R17 — Calibração, depois bloqueante.** Na primeira rodada o job tem `continue-on-error: true`. O coordenador remove essa linha (commit `ci(types): make type gate blocking`) quando, juntos: (a) o job rodou em ≥ 3 commits distintos (push na `main` ou PR); (b) todo vermelho nesses runs foi erro novo verdadeiro, nenhum por divergência Windows × Linux, casamento de baseline ou instalação; (c) a duração ficou dentro do `timeout-minutes`. Cada run da calibração vai numa linha de `docs/spec418/medicao.md` (run id, duração, rc, motivo de vermelho). Como o push depende do dono (`ESTADO_ATUAL.md` § Bloqueios), ver D-418-3 sobre quando a spec vira `done`.

### Prova de valor

- **R18 — Casos reais no escopo.** A rodada inicial (Etapa 0) conta os diagnósticos de `reportAttributeAccessIssue`/`reportOptionalMemberAccess` cuja mensagem cita `AIMessage` (classe do guard). Cada um é classificado em `docs/spec418/medicao.md` como bug real (acesso alcançável sem `isinstance`) ou falso positivo (ex.: narrowing que o checador não acompanha); bug real **não** é consertado aqui: vira linha de follow-up (spec própria). A mesma tabela lista as 8 chamadas reais de `with_structured_output(` do escopo (§1) e, para cada uma, se o receptor é visível ao checador (tipo flui de `get_llm`) ou ponto cego (parâmetro sem tipo/`Any`).
- **R19 — Teste do gate.** `tests/test_type_gate.py`, com marcador `types_e2e` (registrado em `[tool.pytest.ini_options].markers`, `pyproject.toml:126-134`, e excluído do `addopts`, `:122`, como `api_fuzz`), roda o checador de verdade:
  - `test_unguarded_structured_output_is_rejected` — módulo em `tmp_path` com `from llm_setup import get_llm, ModelTier`, um `BaseModel` `Cena(titulo: str)` e `get_llm(0.1, ModelTier.FAST).with_structured_output(Cena).invoke("x").titulo`; `type_gate.py --files <arq>` → rc 1, diagnóstico `reportAttributeAccessIssue` na linha do acesso e "AIMessage" na mensagem.
  - `test_guarded_structured_output_passes` — mesmo módulo com `if isinstance(r, Cena): r.titulo` → rc 0.
  - `test_self_contained_fallback_pattern_is_rejected` — sem importar o repo: classe local `Fallback` com `with_structured_output(self, *a) -> "Fallback"` e `invoke(self, x) -> AIMessage`, acesso a `.titulo` → rc 1. Prova que a configuração pega a classe mesmo se a inferência de `get_llm` mudar.
  - `test_bare_type_ignore_is_rejected` — `x: int = "a"  # type: ignore` em arquivo novo → rc 1 por `reportIgnoreCommentWithoutRule`.
  `--files` checa só os arquivos dados, sem baseline, com a configuração do `pyproject.toml` e raiz de execução no repo (para `import llm_setup` resolver). Se `basedpyright` não estiver instalado, os testes falham (não pulam) quando o marcador é pedido.
- **R20 — Testes puros na suíte default.** `tests/test_type_gate.py` também tem testes sem marcador (rodam na suíte default, sem subprocesso do checador), sobre funções puras com JSON sintético: multiconjunto, folga (R10), sub-multiconjunto do `--tighten` (R11), crescimento contra base (R12.1), filtro de arquivos do `--land` (R14), formato da linha `OK|FAIL types:`. E um teste de configuração: `tomllib` em `pyproject.toml` afirma `include` (R3), `pythonPlatform == "Linux"` (R4), `typeCheckingMode == "standard"` e as 8 regras `"error"` (R5), `basedpyright==` com versão exata no grupo `dev` (R1); `yaml` em `validate.yml` afirma o job `types` com o `if` de `docs_only` e o passo `type_gate.py --check` (R16).

### Degraus seguintes (listados, não implementados)

1. Regras que ficaram `warning` em R5 passam a `error` com baseline, uma família por vez, pelo mesmo critério.
2. Protocolo tipado do cliente LLM (`invoke -> AIMessage | BaseModel`) e anotação dos parâmetros `llm` em `services/` (fecha os pontos cegos de §1).
3. `agents/` (11 arquivos com `with_structured_output(`, a maior concentração do guard).
4. `routes/` + `api.py`.
5. `reportUnnecessaryTypeIgnoreComment` ligado, para limpar os 43 `type: ignore` antigos.
6. Fora de cogitação até nova spec: `tests/`, `evals/` (protegido), `strict`.

### Fora de escopo

- Consertar qualquer erro legado (cada conserto relevante vira spec própria; R18 só lista).
- mypy, `ty`, tipos do frontend (já cobertos por `tsc`, `validate.yml:89-95`).
- Hook de edição, pre-commit, `.claude/settings.json`, `.claude/hooks/guard_tools.py` (SPEC-414/416; R12.2 é emenda na 416).
- `scripts/dev/land_check.*` (SPEC-415; R14 só expõe o comando), `scripts/dev/baseline_growth.py` (SPEC-416; R12.3 é emenda).
- Catraca de relógio, baseline do ruff por contagem, `audit-local.yml` (SPEC-416); oráculos de teste/Hypothesis (SPEC-417).
- Qualquer arquivo de `evals/` (`evals/protected-paths.txt`); o escopo não os inclui.
- Mudar `agents/`, `routes/`, `api.py` ou qualquer código de produto, salvo a anotação condicional de D-418-2.

## 3. Design técnico

### 3.1 Arquivos novos

- `scripts/dev/type_gate.py` (≤ 220 linhas; funções ≤ 60) — CLI `--check` (padrão) | `--tighten` | `--update --reason TEXTO` | `--land --base REF` | `--files ARQ...`; invoca `sys.executable -m basedpyright` (ou o executável do venv) com `--outputjson`, `subprocess.run(..., encoding="utf-8", timeout=<R16>)`.
- `.basedpyright/baseline.json` — gerado pelo checador (Etapa 2).
- `tests/test_type_gate.py` — R19 (marcador `types_e2e`) e R20 (default).
- `docs/spec418/medicao.md` — tabelas da Etapa 0, critério aplicado em R5/E0.7, classificação de R18, linhas da calibração (R17).
- `docs/spec418/baseline_log.md` — cabeçalho + linha da baseline inicial (R12).

### 3.2 Arquivos alterados

- `pyproject.toml` — `basedpyright==X.Y.Z` no grupo `dev` (`:49-55`); seção `[tool.basedpyright]` nova (R3–R7); marcador `types_e2e` em `markers` (`:126-134`) e `and not types_e2e` no `addopts` (`:122`).
- `uv.lock` — regravado por `uv lock`.
- `scripts/dev/land_check.py` (+ `tests/test_wt_sh.py`, `tests/test_land_check.py`) — check `types` ligado a pedido do coordenador (WARN se o venv não tiver basedpyright; só roda se o diff toca `.py`/config). `.github/workflows/validate.yml` — job `types` novo, acrescentado **depois** de `api-fuzz` (`:124`), sem tocar os jobs existentes.
- `docs/guias/TESTES.md` — seção nova "Tipos (basedpyright)" logo depois de "Ruff (incremental)" (`:69-80`), ≤ 8 linhas: escopo, os três comandos, quem pode `--update`, catraca.
- Condicional (D-418-2; **não acionado**, E0.6 mostrou que o checador enxerga `AIMessage`): `llm_setup.py` — só anotações de retorno em `get_llm` (`:1827`), `FallbackLLM.invoke` (`:421`) e `FallbackLLM.with_structured_output` (`:415`), sem mudar linhas de lógica nem o tamanho do arquivo além de 0 linhas (o arquivo está na baseline de tamanho).
- Condicional (R8/E0.7): nada no `.pre-commit-config.yaml`; se a baseline passar de 500 KB, o corte é de escopo/regra, não exceção no hook.

### 3.3 Configuração (forma; os níveis finais saem da Etapa 0)

```toml
[tool.basedpyright]
include = ["infrastructure", "state.py", "persistence.py", "services/..."]  # corte E0.7.3, ver R3
pythonVersion = "3.13"
pythonPlatform = "Linux"
typeCheckingMode = "standard"
useLibraryCodeForTypes = true
reportMissingTypeStubs = "none"
reportUnnecessaryTypeIgnoreComment = "none"
reportIgnoreCommentWithoutRule = "error"
reportOptionalMemberAccess = "error"
reportAttributeAccessIssue = "error"
reportCallIssue = "error"
reportArgumentType = "error"
reportReturnType = "error"
reportOptionalSubscript = "error"
reportPossiblyUnboundVariable = "error"
# demais regras do standard: "error" se contagem 0 na Etapa 0, senão "warning" (R5): InvalidTypeForm, OptionalCall,
# IncompatibleVariableOverride, AssignmentType, OperatorIssue, Redeclaration ficaram "warning"
# regras só do basedpyright fora do standard: "none" (R5)
```

### 3.4 Assinaturas (`type_gate.py`, funções puras testáveis)

- `run_checker(paths: list[str] | None, baseline: Path | None) -> list[Diag]` — único ponto que chama o subprocesso. `Diag = tuple[str, int, str, str]` (`arquivo posix relativo, linha, regra, mensagem`).
- `entries(baseline_json: dict) -> Counter[tuple[str, str]]` — multiconjunto `(arquivo, regra)` lido do formato do checador (formato confirmado em E0.4).
- `slack(base: Counter, current: Counter) -> list[str]` — R10.
- `is_shrink_only(old: Counter, new: Counter) -> bool` — R11.
- `growth(base_ref_entries: Counter, head_entries: Counter) -> list[str]` — R12.1.
- `needs_check(changed: list[str]) -> bool` — R14.
- `land_line(status: str, detail: str) -> str` — `f"{status} types: {detail}"`.

## 4. Plano passo a passo

Executor: só `tests/test_type_gate.py` (e `tests/test_spec192_vercel_packaging.py`, `tests/test_ci_docs_only.py`, `tests/test_size_budget.py`) via `bash scripts/dev/pt.sh`, `-n 2` no máximo; o checador no escopo inteiro **uma vez por vez**, nunca em paralelo com pytest, e só com RAM livre ≥ 3 GB (`bash scripts/dev/ram.sh`). Worktree fora do OneDrive (`wt.sh new 418`).

### Etapa 0 — Medição (sem gate, sem baseline gravada no repo)

Instalação provisória no worktree (`uv add --dev basedpyright==<versão de R1>`) e uma configuração provisória **sem** baseline, com R3–R7 e todas as regras do `standard` em `error` (para medir tudo). Saída em `.tmp/spec418/` (não versionado). Resultados em `docs/spec418/medicao.md`.

- **E0.1 Versão.** medido: `basedpyright==1.40.2` (pyright 1.1.414), publicada em 2026-10-04; resultado em `docs/spec418/medicao.md`.
- **E0.2 Contagem.** medido: escopo cheio 325 erros em 72 de 246 arquivos; escopo final 66 erros em 10 arquivos; tabelas em `docs/spec418/medicao.md` — por regra × severidade e por pasta (`services`, `infrastructure`, `state.py`, `persistence.py`); também total de arquivos no escopo e arquivos com ≥ 1 erro.
- **E0.3 Tempo e RAM, Windows.** medido: escopo cheio 108 s frio / 62 s quente e pico 2,4-2,7 GB; escopo final 13 s e 1,8 GB. Repetir 2× (frio/quente).
- **E0.4 Formato da baseline e opções da CLI.** medido: `--baselinefile` e `--writebaseline` existem; baseline de 66 entradas = 16 KB; a CLI não encolhe sozinha sem `--writebaseline` (existe `--baselinefile`?); gravar uma baseline numa cópia (`--writebaseline` em `.tmp/`) e registrar o formato do JSON (chaves por arquivo, `code`, `range`) e o tamanho em KB. Confirmar se a CLI **encolhe sozinha** a baseline quando um erro some (R9 não depende disso, mas o `--tighten` pode usar).
- **E0.5 Estabilidade do casamento.** Na cópia: inserir 5 linhas em branco no topo de 3 arquivos com erro baselinado, rodar com a baseline → 0 erros novos esperados. Trocar o nome de uma variável numa linha com erro baselinado → registrar se vira erro novo. Falha do primeiro caso aciona R2.
- **E0.6 Prova de valor real.** Rodar os testes de R19 contra a configuração provisória (escrevê-los já aqui, Etapa 1 adiantada). Se `test_unguarded_structured_output_is_rejected` **não** reprovar (inferência de `get_llm` vira `Unknown`), registrar o tipo revelado (`reveal_type` no arquivo do teste) e aplicar D-418-2. Contar os casos de R18 (medido: 0 diagnósticos citam `AIMessage` no repo; tabela das 8 chamadas em `docs/spec418/medicao.md`) e preencher a tabela das 8 chamadas.
- **E0.7 Critério de corte (escrito; os números saem de E0.2).** Para cada uma das 7 regras de R5 com contagem > 0: amostrar min(20, n) diagnósticos e classificar cada um em **bug real**, **hint faltando/errado no nosso código** ou **ruído de biblioteca**. Decisão:
  1. ruído de biblioteca ≥ metade da amostra → aplicar a ordem de R6 para aquela biblioteca e medir de novo (a regra **não** é desligada);
  2. depois de R6, se a regra ainda tiver 0 bug real **e** ruído ≥ metade, ela fica `warning` nesta rodada (registrado, volta no degrau 1), exceto `reportAttributeAccessIssue` e `reportOptionalMemberAccess`, que são a razão da spec e ficam `error` de qualquer jeito;
  3. tempo de E0.3 > 120 s em quente **ou** pico > 2 GB → cortar o escopo para `infrastructure/`, `state.py`, `persistence.py` e os arquivos de `services/` que importam `llm_setup` (medido: `chronicle_compression`, `creature_gen`, `daily_spend_cap`, `prologue`, `shared_pool`), registrando o restante de `services/` como degrau;
  4. baseline de E0.4 > 500 KB → aplicar 1–2 e, se ainda passar, o corte de escopo de 3;
  5. em nenhum caso o corte é "subir o limite" ou ignorar arquivo por glob para esconder contagem.
  "A baseline esconde quase tudo" deixa de ser problema por si: ela congela o legado e o gate vale para código novo e para arquivos novos (R13); o que o critério barra é regra sem sinal (2) e custo que inviabiliza rodar (3, 4).
- **E0.8 Windows × Linux.** Sem push (bloqueado no dono), a comparação real fica para o primeiro run da calibração (R17 b). Localmente: medido: 66 contagens idênticas entre `Linux` e `Windows` no escopo final — se divergir, confirma a necessidade de R4.

### Etapa 1 — Testes primeiro

1. `tests/test_type_gate.py` com os testes de R19 (marcados) e R20 (default). Vermelhos: `type_gate.py` não existe; `pyproject.toml` não tem a seção nem o marcador; `validate.yml` não tem o job.
2. Verificação: `bash scripts/dev/pt.sh tests/test_type_gate.py` → falhas esperadas listadas.

### Etapa 2 — Configuração, script e baseline

1. `pyproject.toml` (R1, R3–R7 com os níveis decididos em E0.7, marcador) + `uv lock`; conferir `git diff --exit-code requirements.txt` e `tests/test_spec192_vercel_packaging.py` verde.
2. `scripts/dev/type_gate.py` (§3.4).
3. Baseline inicial: `bash scripts/dev/py.sh scripts/dev/type_gate.py --update --reason "baseline inicial SPEC-418"` (o executor faz esta única vez, na branch; é o "--update do coordenador" delegado por esta spec). `docs/spec418/baseline_log.md` com a linha.
4. Verificação: `type_gate.py --check` rc 0; `type_gate.py --tighten` sem mudança; `pt.sh tests/test_type_gate.py` verde; `bash scripts/dev/pt.sh tests/test_type_gate.py -m types_e2e` verde (uma vez, sozinho); `size_budget.py` limpo.

### Etapa 3 — Condicional: anotação em `llm_setup.py` (só se E0.6 mandar e D-418-2 = a)

1. Teste: `test_unguarded_structured_output_is_rejected` vermelho com a inferência atual (registrado em E0.6).
2. Anotar os retornos (§3.2). `type_gate.py --check` rc 0 (a anotação pode criar erro novo no escopo: se criar, é bug real do guard e vai para R18, com a entrada adicionada pelo `--update` com motivo).
3. `pt.sh tests/test_llm_*.py` do escopo de `llm_setup` (medido: não acionada, D-418-2 sem efeito), sem mudança de comportamento.

### Etapa 4 — CI e documentação

1. Job `types` (R16) com `continue-on-error: true` (R17). `actionlint` e `zizmor` limpos: zizmor 1.32.0 offline: sem achados (rodado pelo executor). `pt.sh tests/test_ci_docs_only.py tests/test_type_gate.py`.
2. `docs/guias/TESTES.md` (§3.2). Se o checkout principal tiver edição não commitada nesse arquivo (o `land_check` `collision` da 415 acusa), as linhas ficam fora deste pouso como na SPEC-407 e viram follow-up.
3. Hand-back com: números de E0, níveis finais de R5, versão, tamanho da baseline, tabela de R18, comando de R14 para o coordenador ligar no `land_check`.

## 5. Critérios de aceite

- [x] `docs/spec418/medicao.md` com E0.1–E0.8 preenchidos e o critério de E0.7 aplicado (nenhum `<MEDIR:` restante na spec; o `measure` do `land_check` da 415 cobra).
- [x] `basedpyright==X.Y.Z` exato no grupo `dev`; `uv.lock` regravado; `requirements.txt` idêntico.
- [x] `[tool.basedpyright]` com R3–R7; as 7 regras e `reportIgnoreCommentWithoutRule` em `error`.
- [x] `.basedpyright/baseline.json` versionada, ≤ 500 KB; `type_gate.py --check` rc 0 na branch; `--tighten` idempotente.
- [x] `type_gate.py --land --base main` imprime uma linha `OK|FAIL types:` e reprova crescimento de baseline (teste R20).
- [x] `tests/test_type_gate.py` verde na suíte default e com `-m types_e2e`; o caso sem `isinstance` reprovado e o guardado aprovado.
- [x] Tabela de R18 (casos com `AIMessage`, 8 chamadas visíveis × pontos cegos); bugs reais só listados como follow-up.
- [x] Job `types` no `validate.yml` com `continue-on-error: true`, zizmor limpo.
- [x] Run verde no CI (D-418-3): aguarda push autorizado pelo dono.
- [x] `docs/guias/TESTES.md` com a seção nova (ou follow-up registrado, Etapa 4.2).
- [x] `uv run pytest` verde (suíte completa offline, coordenador no pouso).
- [x] Nenhum arquivo de `evals/`, `agents/`, `routes/`, `api.py`, `.claude/` ou `.pre-commit-config.yaml` alterado; `llm_setup.py` só se D-418-2 = a, só anotações.

## 6. Smoke test real (sem LLM; infra = CI e a máquina local)

1. Worktree limpo, RAM ≥ 3 GB: `bash scripts/dev/py.sh scripts/dev/type_gate.py --check` → rc 0. medido: 13 s e 1,8 GB, igual à E0.3.
2. Num arquivo real do escopo, na cópia de trabalho (sem commit): acrescentar no fim de `services/chronicle_compression.py` uma função que faz `get_llm().with_structured_output(ChronicleDigestLLM).invoke([]).summary` sem `isinstance` → `--check` rc 1 apontando a linha; `git checkout -- services/chronicle_compression.py` → rc 0. (Usar o nome de campo real do schema: medido: campo `summary`.)
3. `type_gate.py --land --base main` na branch → `OK types: …`; num branch de teste com uma entrada extra na baseline → `FAIL types: baseline cresceu …`.
4. CI (depende do push autorizado pelo dono): job `types` verde no run do branch ou da `main`; registrar run id, duração e se o conjunto de diagnósticos bate com o local (R17 b) em `docs/spec418/medicao.md`.

## 7. Riscos & compatibilidade

- **Saves, MockLLM, FallbackLLM, quota:** nada muda em runtime. Sem LLM, sem custo.
- **RAM/tempo local:** o checador sobe um processo Node que lê LangChain/LangGraph inteiros para inferência. Mitigação: só por comando explícito e no pouso (R14, R15), nunca em paralelo com pytest, corte de escopo de E0.7.3.
- **Divergência Windows × Linux:** `pythonPlatform = "Linux"` (R4) e extras completos nos dois lados (R6); o resíduo aparece na calibração (R17 b) antes de o job bloquear.
- **Baseline em branches paralelos:** dois branches que consertam erros diferentes regravam o mesmo JSON → conflito no rebase. Resolução: aceitar o da `main` e rodar `type_gate.py --tighten` de novo (documentado em `TESTES.md`).
- **Conflitos com specs da onda:**
  - SPEC-416: `validate.yml` só se o R26 dela cair no ramo > 5 s (um passo no job `test`, perto de `:65`); esta spec só **acrescenta** um job depois de `api-fuzz` → hunks diferentes, rebase sem conflito esperado. `audit-local.yml`: esta spec não toca. `docs/guias/TESTES.md`: a 416 mexe em `:77-78`, esta acrescenta seção depois de `:80` → hunk adjacente, rebase manual trivial. `guard_tools.py`/`baseline_growth.py`: só emendas na 416 (D-418-6).
  - SPEC-417: `pyproject.toml` grupo `dev` (`:49-55`) e `uv.lock` → conflito textual certo na lista do grupo; resolver mantendo as duas linhas e rodando `uv lock`.
  - SPEC-415: `pyproject.toml:71` (format exclude), seção diferente; `land_check.*` não é tocado.
  - SPEC-414: venv por worktree quando o `uv.lock` difere (D6 da 414) — esta spec muda o lock, então o worktree dela ganha venv próprio; esperado.
- **Dependência nova sem auditoria:** o `pip-audit` do CI (`validate.yml:63-64`) audita só `requirements.txt` (sem `dev`); o `basedpyright` e o `nodejs-wheel-binaries` ficam fora, como `ruff` e `pytest` hoje. Registrado, sem mudança aqui.
- **Falso senso de segurança:** os pontos cegos de §1 continuam cegos até o degrau 2; a seção nova do `TESTES.md` diz isso em uma linha.

## 8. Decisões para o dono (recomendação primeiro)

- **D-418-1 — Ferramenta.** basedpyright pinado no grupo `dev` (R1). Alternativa: pyright do PyPI + baseline por script (R2 vira o caminho principal).
- **D-418-2 — Se a inferência de `get_llm` não expuser `AIMessage` (E0.6).** (a) anotar só os tipos de retorno em `llm_setup.py` nesta spec (zero mudança de runtime; prova de valor fica no repo real); (b) aceitar só o teste autocontido e abrir spec para a anotação. Recomendação: (a).
- **D-418-3 — Quando vira `done`.** (a) com o job em calibração e ≥ 1 run verde no CI (depende do push); a virada para bloqueante (R17) é commit de uma linha do coordenador, acompanhado no `ESTADO_ATUAL.md`; (b) só depois de bloqueante. Recomendação: (a).
- **D-418-4 — Seção de configuração.** `[tool.basedpyright]` (editor não muda) contra `[tool.pyright]` (o plugin `pyright-lsp` do editor passaria a mostrar o mesmo escopo e regras, com aviso para as chaves exclusivas do basedpyright). Recomendação: `[tool.basedpyright]`.
- **D-418-5 — Baseline folgada.** `FAIL` (catraca como a SPEC-407) contra `WARN`. Recomendação: `FAIL`; consertar um erro legado custa um `--tighten` no mesmo commit.
- **D-418-6 — Emendas na SPEC-416** (R28: negar `type_gate.py --update` em subagente; R29: incluir `.basedpyright/baseline.json` no `baseline_growth.py`). Recomendação: o coordenador aplica as duas linhas depois que 416 e 418 pousarem, como em D-416-3; até lá vale só a camada R12.1 (pouso).
- **Aprovação (2026-11-12):** aprovada pelo coordenador por delegação do dono ("executa as mudanças", 12/11). D-418-1: basedpyright. D-418-2: sim, anotar só os tipos de retorno em `llm_setup.py` se a Etapa 0 mostrar que o checador não enxerga `AIMessage`. D-418-3: pode pousar com o job em calibração; o run verde no CI fica em "Não rodou e por quê" até o dono autorizar o push, e o `done` espera esse run. D-418-4, D-418-5: aceitas. D-418-6: emendas na 416 pelo coordenador. Executa por último na onda (depois da 417, conflito em `pyproject.toml`/`uv.lock`).
- **Fechamento (2026-11-12):** revisão `terra` APPROVED_WITH_FOLLOWUPS (`handoffs/SPEC-418-terra-review.md`). Suíte completa local 11631 passed. CI de `46fed109` (run `validate` 43240617142): job `types` verde em ~29 s, `OK types: nenhum erro novo, baseline justa`, 4 `types_e2e` passed. D-418-6 aplicada em `f8d35514` (hook nega `type_gate.py --update` em subagente). Limite conhecido: o escopo final cobre 4 dos ~19 arquivos de produção que chamam `with_structured_output` e nenhum de `agents/`; o degrau seguinte exige tipar o parâmetro `llm`. Pendente: tirar o `continue-on-error` do job depois de 3 runs verdes.
