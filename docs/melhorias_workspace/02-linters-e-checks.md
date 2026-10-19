# 02 — Linters e checks

Foco: Ruff, tipagem, formatação, frontend (tsc/eslint), pre-commit, fim de
linha/encoding no Windows. Números medidos no worktree `b05932e`; contagens de
regras via `uv run --frozen ruff check --select … --statistics`.

## 1. Estado atual

| Item | Hoje | Evidência |
|---|---|---|
| Ruff `select` | **só `E9,F63,F7,F82`** (erros de sintaxe e nome indefinido); 0 achados | `pyproject.toml:76-83` |
| `ruff format` | nunca adotado: **689 de 2.056 arquivos** seriam reformatados | `ruff format --check` |
| Type checker | **nenhum** (sem mypy/pyright/ty); 23 `# type: ignore` soltos | grep pyproject/uv.lock |
| `print(` fora de testes | ~259 (CLIs: `game_engine.py` 55, `playtest/__main__.py` 20…) — ok em CLI, mas sem regra que impeça em `services/`/`agents/` | `--select T201` = 265 |
| `except Exception` amplo | **262** (`BLE001`) — relevante para a convenção "guard do FallbackLLM": hoje nada distingue guard intencional de engolir erro | `--select BLE001` |
| Pre-commit / editorconfig | **nenhum** | ls |
| `.gitattributes` | `eol=lf` para py/ts/js/toml/json/yaml/Procfile; **sem regra para `*.md`**; `core.autocrlf=true` no repo | `.gitattributes`, `git config` |
| Fim de linha real | índice 100 % LF (0 `i/crlf`); mas `CLAUDE.md`/`ESTADO`/`ROADMAP` ficam `w/crlf` no checkout (autocrlf) e `index.yaml` é LF | `git ls-files --eol` |
| Frontend | `tsconfig` estrito (`strict`, `noUnused*`), mas só `src/` é checado e só dentro de `npm run build`; **sem eslint, sem prettier, sem `npm run lint`/`typecheck`**; `web/e2e` e `web/tests` não passam por `tsc` | `web/package.json`, `web/tsconfig.json` |
| Lint de conteúdo | `scripts/validate_content.py` existe e roda no CI (bom) | `validate.yml` |

### O que cada família de regra do Ruff apontaria hoje

| Seleção | Achados | Comentário |
|---|---|---|
| `F` | ~620 (F405 497 = `import *` em testes; **F401 94** import sem uso, autofix; **F811 57** redefinição; F841 11) | bugs latentes reais fora de testes |
| `B` (bugbear) | 60 (B023 20 closure em loop, B905 20 `zip` sem `strict`, B904 8 `raise` sem `from`, B017 7) | barato, alto valor |
| `F401,F811,F841,B,E4,E7` | **445** (~100 autofix) | **primeiro degrau recomendado** |
| `I` (isort) | 480, 100 % autofix | commit mecânico |
| `UP` (pyupgrade) | 2.931 (UP006 1.815 `List`→`list`, UP045 698 `Optional`, UP035 247), ~90 % autofix | commit mecânico, separado |
| `E,W,F` | 3.503 (E501 2.554 linhas > 100) | deixar E501 fora |
| `PT` | 1.143 (PT018 1.021 asserts compostos) | fora |
| `PL*`, `ANN`, `D`, `S` | milhares (PLC0415 2.671 import dentro de função; PLR2004 1.757; S101 9.081; D103 4.030) | inviável/sem valor aqui |

## 2. Por que isso importa para o fluxo com agentes

- Sem regra de import/redefinição, um subagente que esquece um import só descobre
  na suíte completa (6–11 min) — Ruff pega em 2 s.
- **CRLF**: 363 resultados de ferramenta com "LF will be replaced by CRLF"/"CRLF
  will be replaced by LF" em **118 agentes**; o maior tool-result do coordenador
  (14 K) foi um `git add` só de avisos. O brief manda "preservar CRLF" em
  `specs/index.yaml`, mas o `.gitattributes` força LF no mesmo arquivo → aviso em
  todo `git add`. Scripts de scratchpad (`stateline.py`, `resolve_docs.py`,
  `docs_edit.py`) detectam `\r\n` à mão.
- **Encoding**: 27–35 falhas `UnicodeEncodeError: 'charmap'` (cp1252) em 26–33
  agentes ao imprimir `→`/emoji via `python -`/`uv run python`; `python -I`
  ignora `PYTHONIOENCODING`.
- **Caminhos longos**: `git worktree add` falhou 2× com "Filename too long"
  (`proximas-specs/pacote-prompts-…/13-jev-investiga-o-futura-somente-com-justificativa.md`).
- **`python -` fora da raiz**: 27 agentes com `No module named …`.
- Nada impede um `.mp3` de 6,3 MB ou um `.zip` de entrar no repo
  (`docs/descricao_projeto/`, 15,9 MB; `?? docs/PROXIMA_ONDA…zip` na raiz).

## 3. Proposta

### L1 — Ruff em três degraus (cada um = 1 commit mecânico, sem feature junto)

```toml
[tool.ruff]
target-version = "py313"
line-length = 100
extend-exclude = ["project_index/repo_graph.json", "web/", "docs/", "saves*/"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "B", "I", "UP"]       # degrau 1+2
ignore = ["E501", "B905"]                               # B905: ligar depois com --fix
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["F405", "F403", "F811"]                   # import * e fixtures redefinidas
"scripts/**" = ["T201"]
"game_engine.py" = ["T201"]
"playtest/**" = ["T201"]
```

| Degrau | Conteúdo | Achados hoje | Esforço |
|---|---|---|---|
| 1 | `F` (sem F405 em tests) + `B` + `E4/E7` | 445 (~100 `--fix`) | 1–2 h de revisão humana dos ~340 restantes (muitos são F811 em tests → per-file-ignore) |
| 2 | `I` + `UP` via `ruff check --fix` | 3.411, ~95 % autofix | 15 min + rodar suíte |
| 3 | `ruff format` one-shot | 689 arquivos | só quando não houver branch aberta (conflita com worktrees vivos); 30 min |
| 4 (opcional) | `T20` em `services/`, `agents/`, `infrastructure/`, `api.py` (print em caminho quente = log sem estrutura) | medir após degrau 1 | — |
| 5 (opcional) | `BLE001` em `services/`+`agents/` com `# noqa: BLE001  # guard FallbackLLM` nos guards legítimos | 262 | torna a convenção crítica auditável por lint |

### L2 — Tipagem mínima onde dói (opcional, 2 h)

- `pyright` (ou `ty`) em modo `basic` só em `services/`, `infrastructure/`,
  `state.py`, `persistence.py` — é onde os bugs de mapeamento de campo do
  structured output aparecem ("MockLLM esconde bugs de mapeamento").
  Rodar no CI como `continue-on-error` por 2 semanas, depois bloquear.

### L3 — Fim de linha e encoding (30 min, remove uma família inteira de ruído)

```
# .gitattributes (acrescentar)
* text=auto eol=lf
*.md text eol=lf
*.ps1 text eol=crlf
```

```
# .editorconfig (novo)
root = true
[*]
end_of_line = lf
charset = utf-8
insert_final_newline = true
[*.ps1]
end_of_line = crlf
```

- `git config core.autocrlf false` e `git config core.longpaths true` no
  checkout principal (e documentar no CLAUDE.md "Como rodar"); worktrees herdam.
- Depois: `git add --renormalize .` em 1 commit.
- Retirar "preserve CRLF" dos briefs e o tratamento de `\r\n` dos scripts.
- `PYTHONUTF8=1` no ambiente do Claude Code (`.claude/settings.json` →
  `env`) e no `.env.example`; alternativa: `uv run` sempre via
  `scripts/dev/py.sh` que exporta `PYTHONUTF8=1` e faz `cd` para a raiz do repo
  (resolve também os 27 `No module named`).
- Encurtar os nomes em `proximas-specs/pacote-prompts-…` (ou mover para fora do
  repo — ver `05` P7).

### L4 — Pre-commit (local, rápido, só nos arquivos tocados)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{id: ruff, args: [--fix]}, {id: ruff-format}]   # format só após L1 degrau 3
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - {id: end-of-file-fixer}
      - {id: mixed-line-ending, args: [--fix=lf]}
      - {id: check-yaml}
      - {id: check-added-large-files, args: [--maxkb=500]}
      - {id: check-merge-conflict}        # pega "<<<<<<<" que o resolve.sh apagou às cegas
  - repo: local
    hooks:
      - id: spec-index-sync   # scripts/spec_index.py check (header status == index.yaml)
      - id: handoff-name      # padrão handoffs/SPEC-NNN-<papel>-<tipo>.md
      - id: no-secrets        # gitleaks protect --staged (já existe no CI; aqui é antes do commit)
```

Instalar com `uv tool install pre-commit` + `pre-commit install`. Custo por
commit: < 3 s. Ganho: o CI deixa de ser o primeiro lugar onde import sem uso,
YAML inválido, marcador de conflito ou mídia de 6 MB aparecem.

### L5 — Frontend (1 h)

- `web/package.json`: `"typecheck": "tsc -p tsconfig.json --noEmit && tsc -p tsconfig.e2e.json --noEmit"`
  (criar `tsconfig.e2e.json` cobrindo `e2e/` e `tests/`), e rodar no `validate.yml`
  antes do build.
- ESLint flat config com `typescript-eslint` (recommended) + `react-hooks` +
  `jsx-a11y` (o projeto já investe em axe/a11y nas jornadas): `"lint": "eslint src e2e"`.
  Medir achados no primeiro run; ligar no CI como `continue-on-error` até zerar.
- Prettier é opcional; se entrar, junto com o degrau 3 do Ruff (um commit só de formato).

## 4. Resumo

| # | Mudança | Ganho | Esforço | Risco |
|---|---|---|---|---|
| L3 | `.gitattributes` `*.md`/`text=auto`, `.editorconfig`, `autocrlf=false`, `longpaths`, `PYTHONUTF8=1`, `py.sh` | −363 avisos CRLF (118 agentes), −30 agentes com cp1252, −27 `No module named`, −2 falhas de worktree; scripts de docs sem `\r\n` manual | 30 min | baixo (1 commit de renormalização) |
| L1 | Ruff degraus 1–2 | 445 achados de classe-bug visíveis em 2 s em vez de na suíte; imports/estilo uniformes para os agentes | 2 h | baixo |
| L4 | pre-commit | erros triviais param antes do commit; bloqueia mídia > 500 KB e marcador de conflito | 30 min | nenhum |
| L5 | `typecheck` + eslint no web | `e2e/` e `tests/` passam a ser tipados; a11y/hook rules | 1 h | baixo |
| L2 | pyright em `services/`+`infrastructure/` | pega campo errado de structured output sem chave real | 2 h | médio (ruído inicial) |
| L1-3 | `ruff format` one-shot | diffs menores e previsíveis para os agentes | 30 min | conflito com branches abertas — fazer com zero worktrees vivos |
