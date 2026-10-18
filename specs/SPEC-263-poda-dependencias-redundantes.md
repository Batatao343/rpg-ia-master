# SPEC-263 — Poda de dependências e extras redundantes

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false` — mudança de manifesto verificável por `uv tree` + suíte
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A SPEC-192 moveu `langchain-openai` e `psycopg[binary,pool]` para `[project].dependencies`,
mas os extras `openai` e `postgres` continuam declarando as mesmas dependências. `pillow`
está no core e de novo no grupo `dev`. `langchain` (meta) e `google-genai` são deps
diretas, mas nenhum `.py` os importa: o código usa só `langchain_core` (131 imports),
`langchain_text_splitters` (2) e os pacotes de provider, e `google-genai` vem transitivo
de `langchain-google-genai`. Por fim, `requirements.txt` e `requirements-vercel.txt` são
**byte-idênticos** (280 linhas, mesmo comando de `uv export` no cabeçalho).

Objetivo: o manifesto declara exatamente o que o código importa, sem duplicata.

## 2. Requisitos

- **R1** — Remover os extras `openai` e `postgres` de `pyproject.toml` e o `pillow` do grupo `dev`.
- **R2** — Trocar `langchain` por `langchain-core` + `langchain-text-splitters` explícitos
  (os pacotes que o código importa) e remover `google-genai` das deps diretas, **somente se**
  `uv tree` mostrar que continuam resolvidos (transitivos) com versões iguais às do lock atual.
  Se `uv tree` mostrar que `langchain` é necessário em runtime, manter e registrar o porquê.
- **R3** — Atualizar as referências a `--extra openai`/`--extra postgres`:
  `.github/workflows/validate.yml:19`, `audit-local.yml:24`, `eval-protected.yml:30`,
  `.env.example:73,99`, mensagens `llm_setup.py:296` e `infrastructure/postgres.py:66`,
  `docs/evals-plan-v4/ci/evals-workflow-draft.yml:13`.
- **R4** — Manter um único arquivo exportado. Proposta: manter `requirements-vercel.txt`
  (o nome que `scripts/vercel_bundle_check.py:3,53` usa) e apontar `validate.yml:21-22`
  (pip-audit) para ele; remover `requirements.txt`. Regerar com o comando do cabeçalho,
  sem os `--extra` removidos.
- **R5** — `uv.lock` regenerado só por `uv lock` (sem `--upgrade`); o diff do lock não pode
  mudar a versão de nenhum pacote que já estava resolvido.

### Fora de escopo

Trocar `langchain-community` (FAISS/TextLoader) por FAISS direto: a mudança mexe em
índices pickled e merece spec própria. Extras `anthropic`, `ollama`, `portable`, `browser`
e `observability` continuam (opcionais de verdade).

## 3. Design técnico

Arquivos alterados: `pyproject.toml`, `uv.lock`, `requirements-vercel.txt`, os três
workflows, `.env.example`, duas mensagens de erro, um rascunho de workflow em docs.
Arquivo removido: `requirements.txt`.

## 4. Plano passo a passo

1. `uv tree --depth 3` antes da mudança e guardar a saída no scratchpad.
2. Editar o `pyproject.toml` (R1/R2), rodar `uv lock`, `uv tree` de novo e diffar: nenhum
   pacote de runtime pode sumir.
3. Regerar `requirements-vercel.txt`, remover `requirements.txt`, atualizar referências (R3/R4).
4. `git grep -n "extra openai\|extra postgres\|requirements.txt"` (fora de `docs/spec*`) deve voltar vazio.

## 5. Critérios de aceite

- [ ] `uv sync` limpo (`.venv` recriado) + `uv run pytest` verde
- [ ] `uv sync --extra anthropic --extra browser` funciona (CI usa)
- [ ] `uv run python scripts/vercel_bundle_check.py` dentro do teto de 500 MB, sem crescer
- [ ] `pip-audit -r requirements-vercel.txt` sem regressão
- [ ] CI `validate`, `audit-local` e `eval-gates` verdes no PR
- [ ] Project Index regenerado em checkout limpo (o gate `project_index check` acusa staleness)

## 6. Smoke

`uv run uvicorn api:app --port 8000` → `/health` 200; 1 turno MockLLM via `bash scripts/smoke_api.sh`.
Deploy de preview na Vercel com `/health` exibindo o `git_sha` novo.

## 7. Riscos & compatibilidade

Risco **baixo**. A Vercel instala do `uv.lock` (só deps core); se o R2 tirar algo usado em
runtime, o preview quebra no import. Rollback: `git revert` do commit (manifesto + lock).
