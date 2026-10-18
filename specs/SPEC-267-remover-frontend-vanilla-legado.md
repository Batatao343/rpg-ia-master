# SPEC-267 — Remover o frontend vanilla legado

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

`frontend/` (`app.js` 394 + `index.html` 174 + `styles.css` 382 = **950 linhas**, último commit
2026-06-25) é o cliente da Fase 0. Ele só é servido quando `web/dist` não existe
(`api.py:4929`). O deploy (`vercel.json` `buildCommand: cd web && npm ci && npm run build`)
sempre gera `web/dist`, e o cliente legado não conhece login, CSRF, SSE, Cartas nem a
carteira, ou seja, não funciona contra a API atual. Nenhum teste referencia o diretório:
os hits de "frontend" em `tests/` são rótulos de escopo do CI.

## 2. Requisitos

- **R1** — `git rm -r frontend/`.
- **R2** — `api.py:4924-4931`: montar só `web/dist` quando existir (sai o ramo de fallback).
  Sem `web/dist`, a API sobe sem UI (comportamento local documentado: rodar `npm run build`).
- **R3** — Atualizar o texto que descreve o fallback: `CLAUDE.md:58,202,204`,
  `AGENTS.md:94,238,240`, `README.md` se citar.
- **R4** — `scripts/vercel_bundle_check.py:21` e `project_index/generator.py:37`: retirar
  `"frontend"` da lista de diretórios **somente se** a entrada só existe por causa da pasta
  (no generator ela pode ser a categoria "frontend" do índice: conferir antes).

### Fora de escopo

`web/`; os rótulos `frontend` do CI (`scripts/ci_eval_scope.py`), que são escopo de mudança, não a pasta.

## 3. Design técnico

```python
_WEB_DIST = os.path.join(_ROOT, "web", "dist")
if os.path.isdir(_WEB_DIST):
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="frontend")
```

## 4. Plano passo a passo

1. **Teste** (`tests/test_api_static.py` ou o existente que cobre a montagem, se houver):
   sem `web/dist`, `GET /` devolve 404 e `/health` 200.
2. R1–R4.

## 5. Critérios de aceite

- [ ] `git grep -n "frontend/"` fora de `docs/` e `specs/` só encontra rótulos de CI
- [ ] `uv run pytest` verde; `cd web && npm run build` verde
- [ ] Preview Vercel serve a SPA em `/` (smoke `scripts/staging/vercel_smoke.py` ou equivalente)
- [ ] Project Index regenerado em checkout limpo

## 6. Smoke

`npm run build` → `uv run uvicorn api:app` → abrir `/` e jogar 1 turno com MockLLM.

## 7. Riscos & compatibilidade

Risco **baixo**: quem roda a API sem build perde a UI de fallback, que já não funcionava
contra a API autenticada. Rollback: `git revert`.
