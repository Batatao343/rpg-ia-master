---
name: wrap-up
description: Ritual obrigatório de fim de tarefa do projeto — suíte completa verde, ESTADO_ATUAL.md enxuto via /estado, ROADMAP só se o plano mudou, commit. Use quando terminar qualquer tarefa de código, quando o usuário pedir "/wrap-up", "finaliza", "fecha a tarefa" ou "commita o trabalho".
---

# /wrap-up — ritual de fim de tarefa

Não declarar a tarefa concluída sem todos os passos. Funciona em qualquer worktree.

1. **Suíte completa** (camada 2 do `/qa`), em background com timeout longo:
   `bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n auto 2>&1 | tail -15`.
   Vermelho → corrigir e repetir. Nunca seguir com falha.
2. **Spec**: status final no cabeçalho da spec (fonte única); `specs/index.yaml` é
   gerado (`scripts/spec_index.py build`), nunca editado à mão.
3. **ESTADO_ATUAL.md**: rode `/estado` — substituir, nunca anexar; teto 8 KB.
   Detalhe de entrega vai para `CHANGELOG.md` (`## AAAA-MM-DD — título`).
   Subagente em onda paralela **não** edita ESTADO/ROADMAP/index: devolve o
   parágrafo (≤ 6 linhas) no hand-back.
4. **ROADMAP.md**: só se o plano mudou (fase, ordem, item novo/cancelado).
5. **RAG**: mudou `lore_nova/`, `data/codex/` ou `data/rules.txt` → `uv run python rag.py`.
6. **Commit**: staging seletivo (`git status --short` antes; nunca `git add -A` cego),
   Conventional Commits, linha `Co-Authored-By` do sistema. Nada de `.env`/`saves/`.
7. **Report**: uma linha — contagem de testes + hash curto.
