# SPEC-267 — Remover o frontend vanilla legado

> **Status:** `draft` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (`.vercelignore`, CI roda pytest sem `web/dist`; ver §8)
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
- **R4** — *(revisado)* `scripts/vercel_bundle_check.py:21` (`SKIP_TOP`), `project_index/generator.py:37`
  e `.vercelignore:24` listam `frontend` como **exclusão** (não categoria). Opcional: deixar como
  guarda inerte é inofensivo; se tirar, tirar dos três e regenerar o índice (o `manifest.json:27`
  muda).

### Fora de escopo

`web/`; os rótulos `frontend` do CI (`scripts/ci_eval_scope.py`), que são escopo de mudança, não a pasta.

## 3. Design técnico

```python
_WEB_DIST = os.path.join(_ROOT, "web", "dist")
if os.path.isdir(_WEB_DIST):
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="frontend")
```

## 4. Plano passo a passo

1. **Teste** (novo; nenhum teste cobre a montagem hoje): sem `web/dist`, `GET /` devolve 404 e
   `/health` 200; com `web/dist` presente, `GET /` serve `index.html`.
   *(revisão)* No CI `validate.yml` o `pytest` roda **antes** do `npm run build` (sem `web/dist`),
   ou seja, hoje a suíte de CI roda com o fallback `frontend/` montado em `/` e, depois desta spec,
   sem mount nenhum. Rotas não-API passam de 404 texto do `StaticFiles` para 404 JSON do FastAPI e
   método não-GET em caminho desconhecido passa de 405 para 404. Nenhum teste atual depende disso
   (grep de `get("/")`, `== 405`, `"Not Found"` em `tests/` vazio; `test_abuse_policy:65` itera
   `app.routes` e ignora o mount), mas rodar a suíte local **sem** `web/dist` antes do PR.
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

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Verificado: nenhum teste, script, workflow ou config usa os arquivos de `frontend/`; `.vercelignore:24`
já exclui a pasta do upload e `vercel.json` sempre gera `web/dist`. O Android carrega o staging hospedado.
O `Procfile` (contingência Railway, não provisionada) não faz build web; com o fallback ele serviria um
cliente que não funciona contra a API autenticada, então nada se perde.

Achados:
1. **No CI a suíte roda hoje COM o fallback montado**: `validate.yml` executa `pytest` antes de
   `npm run build`, então `web/dist` não existe e `frontend/` é servido em `/`. Depois da spec, o CI roda sem
   mount. Grep de testes que dependem de 404 texto/405 em rota desconhecida: vazio, mas o passo 1 agora exige
   rodar a suíte localmente sem `web/dist`.
2. `.vercelignore:24` também lista `frontend` (exclusão inerte); R4 reescrito como opcional.
