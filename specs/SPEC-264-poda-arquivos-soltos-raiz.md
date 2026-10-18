# SPEC-264 — Remover arquivos soltos versionados por engano

> **Status:** `draft` · **Revisão independente 2026-10-18:** SAFE as written (ver §8)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Luna` (≡ Haiku) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Dois arquivos entraram no repo sem dono nem referência:

- `pytest216.log` (1,5 KB, só os pontos de progresso do pytest), adicionado no commit
  `565a04d` (SPEC-216, feat web). `git grep pytest216` só encontra o próprio arquivo.
- `assets/gallery/20251205_6e7458.png` (828 KB). Nenhum código, teste, doc ou catálogo
  visual referencia `assets/gallery/` nem o nome do arquivo.

## 2. Requisitos

- **R1** — `git rm pytest216.log`; adicionar `pytest*.log` ao `.gitignore`.
- **R2** — `git rm assets/gallery/20251205_6e7458.png` (e a pasta, que fica vazia), depois
  de reconfirmar `git grep -n "gallery/\|20251205_6e7458"` vazio (inclusive `docs/`).

### Fora de escopo

Reescrever histórico (`filter-repo`). Os blobs continuam no histórico.

## 3–4. Design e plano

Só remoção de arquivo + uma linha no `.gitignore`. Testes: nenhum novo.

## 5. Critérios de aceite

- [ ] Os dois `git grep` acima voltam vazios
- [ ] `uv run pytest` verde; `uv run python scripts/validate_content.py` sem erro
  (o lint de conteúdo checa o catálogo visual)
- [ ] Project Index regenerado em checkout limpo

## 6. Smoke

Nenhum smoke LLM necessário (não toca runtime).

## 7. Riscos & compatibilidade

Risco **nulo** para o runtime. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE as written.**

- `git grep "pytest216\|gallery\|20251205_6e7458"` fora do relatório/spec: vazio.
- Nenhum código varre `assets/` por glob (`rglob/glob/iterdir/listdir/walk` + `asset` em `.py`: vazio);
  o catálogo visual é explícito (`services/visual_catalog.py`, `scripts/import_visual_assets.py`).
  O PNG veio do primeiro commit (`cc49748`).
- `project_index/generator.py:33` exclui `assets` do índice: sem efeito no grafo, mas regenerar o índice
  segue no aceite.
