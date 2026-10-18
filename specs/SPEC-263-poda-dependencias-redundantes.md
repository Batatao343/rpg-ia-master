# SPEC-263 — Poda de dependências e extras redundantes

> **Status:** `done` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (R4 invertido; drift do requirements tratado em R4b; ver §8)
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
- **R4** — *(revisado 2026-10-18)* Manter um único arquivo exportado: **manter
  `requirements.txt`** e remover `requirements-vercel.txt` (não o contrário).
  `requirements.txt` é o nome que `tests/test_spec192_vercel_packaging.py:53` documenta
  ("Vercel lê requirements.txt"), o alvo do `pip-audit` em `validate.yml:22` e o manifesto
  que o Dependabot `pip` (`.github/dependabot.yml`, SPEC-225 R3) varre em `/`.
  Atualizar `scripts/vercel_bundle_check.py:3,53` e `tests/test_spec192_vercel_packaging.py:41,53`
  para o nome mantido. Regerar com o comando do cabeçalho **sem** `--extra postgres --extra openai`
  e com `-o requirements.txt` (os extras deixam de existir e o `uv export` falha com eles).
- **R4b** — *(novo, revisão)* O `requirements-vercel.txt` atual **já está defasado** do `uv.lock`:
  falta `pillow==12.3.0` (core desde a SPEC-192). Regerar inclui `pillow`, o que quebra a assert
  `for banned in (..., "pillow")` em `tests/test_spec192_vercel_packaging.py:50`. Tirar `pillow`
  da lista de banidos (é dep core; a Vercel já o instala via `uv.lock`). Consequência: o
  `pip-audit` passa a auditar `pillow` pela primeira vez; advisory encontrado se resolve no lock
  antes de fechar, sem allowlist.
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
4. `git grep -n "extra openai\|extra postgres\|requirements-vercel"` fora de `docs/`, `specs/`,
   `handoffs/`, `proximas-specs/`, `ESTADO_ATUAL.md` e `CHANGELOG.md` deve voltar vazio.
   Atenção: `uv sync --extra openai` passa a **falhar** ("Extra `openai` is not defined"), não a
   ser ignorado; registrar no `ESTADO_ATUAL.md` (o bloco da sessão 49 ensina
   `uv sync --extra openai --extra anthropic`).

## 5. Critérios de aceite

- [ ] `uv sync` limpo (`.venv` recriado) + `uv run pytest` verde
- [ ] `uv sync --extra anthropic --extra browser` funciona (CI usa)
- [ ] `uv run python scripts/vercel_bundle_check.py` dentro do teto de 500 MB, sem crescer
- [ ] `pip-audit -r requirements.txt` sem advisory aberto (agora inclui `pillow`)
- [ ] `tests/test_spec192_vercel_packaging.py` verde com o arquivo regerado
- [ ] CI `validate`, `audit-local` e `eval-gates` verdes no PR
- [ ] Project Index regenerado em checkout limpo (o gate `project_index check` acusa staleness)

## 6. Smoke

`uv run uvicorn api:app --port 8000` → `/health` 200; 1 turno MockLLM via `bash scripts/smoke_api.sh`.
Deploy de preview na Vercel com `/health` exibindo o `git_sha` novo.

## 7. Riscos & compatibilidade

Risco **baixo**. A Vercel instala do `uv.lock` (só deps core); se o R2 tirar algo usado em
runtime, o preview quebra no import. Rollback: `git revert` do commit (manifesto + lock).

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Verificado:
- `langchain` (meta) e `google-genai` sem uso direto: `git grep` de `from/import langchain.`,
  `google.genai`, `from google`, strings `"langchain."` e `importlib` em py/json/toml/yml → vazio.
  Os índices FAISS pickled referenciam `langchain_community`/`langchain_core`, não `langchain`.
- `uv tree --invert`: só a raiz exige `langchain`; `google-genai` segue transitivo via
  `langchain-google-genai` (provider Gemini do `llm_setup` e fallback de embeddings do `rag.py` intactos);
  `langchain-text-splitters` já vem via `langchain-classic`.
- Simulação em cópia de scratch (`uv lock --offline` com R1+R2): saída `Removed langchain v1.3.15`,
  nenhuma outra versão muda. R2 e R5 confirmados.
- `uv export --extra openai` sem o extra → `error: Extra openai is not defined` (falha dura).

Achados que mudaram a spec:
1. **R4 escolhia o arquivo errado.** `tests/test_spec192_vercel_packaging.py:53` registra que a Vercel lê
   `requirements.txt`; Dependabot `pip` e `pip-audit` também usam esse nome. Agora: manter
   `requirements.txt`, apagar `requirements-vercel.txt`.
2. **Drift preexistente (R4b):** os dois requirements não têm `pillow` (core desde a SPEC-192). O `pip-audit`
   do CI nunca auditou `pillow` e o `vercel_bundle_check` subestima o bundle. Regerar quebra a lista de
   banidos do teste da SPEC-192; a spec agora manda corrigir a lista e tratar advisory, sem allowlist.
3. `uv sync --extra openai|postgres` vira erro, inclusive em receitas de docs/handoffs; registrar no ESTADO.
