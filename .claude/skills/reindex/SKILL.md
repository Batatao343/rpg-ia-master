---
name: reindex
description: Reconstrói o Project Index (project_index/) no checkout atual e commita se mudou. Use em "/reindex", "rebuild do project index", ou quando o CI acusar "project index is stale". Normalmente o /spec-land já faz isso na branch.
---

# /reindex

O índice hasheia **só arquivos rastreados**: arquivo solto (zip, scratch) não o
deixa stale, então não precisa de clone limpo. Precisa só de árvore sem mudanças
rastreadas não commitadas.

```bash
bash scripts/dev/reindex.sh
```

Saída: `reindexed: <sha> …` ou `index already fresh`, e `project_index check: fresh`.
Se o CI ainda acusar stale, rode `git status` — algum arquivo rastreado foi editado
sem commit, ou o fim de linha no disco não é LF (`git add --renormalize .`).
Para RAG/lore (`faiss_*`) o comando é outro: `uv run python rag.py`.
