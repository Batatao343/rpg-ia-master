# SPEC-166 — Project Index Core + Repository Graph

> **Status:** `draft`
> **Depende de:** SPEC-165 `done`
> **Modelo executor mínimo:** Terra High
> **Revisão obrigatória:** Sol

## Objetivo

Criar navegação arquitetural determinística sem mover pastas nem criar source of truth concorrente.

## Entregas

`project_index/manifest.json`, `domains.yaml`, `repo_graph.json`, `state_ownership.yaml`, `eval_map.yaml`, gerador e CLI bounded.

## Regras

- AST/static extraction primeiro;
- proveniência/confidence em arestas;
- state ownership curado, nunca sobrescrito por inferência;
- excluir lore/assets/FAISS/saves/generated artifacts do symbol graph;
- source precisa ser aberto antes de editar;
- nenhum graph DB v1;
- índice stale falha/avisa pelo SHA.

## Model routing

Luna pode inventariar paths/símbolos e gerar relatórios. Terra implementa extractors/CLI. Sol revisa modelo de dados, staleness e false-authority risks. Astra só por escalada explícita `ARCHITECTURE_AMBIGUITY`.

## Aceite

- [ ] mesmo SHA produz índice determinístico;
- [ ] queries bounded localizam memory/context/state/test paths relevantes;
- [ ] ownership curado preservado;
- [ ] comportamento do RPG não muda;
- [ ] revisão Sol aprovada.
