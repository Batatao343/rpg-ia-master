# SPEC-166 — Project Index Core + Repository Graph

> **Status:** `done`
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

- [x] mesmo SHA produz índice determinístico;
- [x] queries bounded localizam memory/context/state/test paths relevantes;
- [x] ownership curado preservado;
- [x] comportamento do RPG não muda;
- [x] revisão Sol aprovada.

## Execução — 2026-09-28

- Execução no contexto ativo `gpt-6`, acima do mínimo Terra; custo de roteamento
  não otimizado registrado.
- Nenhuma reorganização física, graph database ou mudança de runtime autorizada.
- Entregas: gerador AST Python, file map TS/JS, manifest com SHA Git + hash da
  árvore, grafo com proveniência/confidence, mapas curados e CLI bounded.
- Gate: build/check frescos com 5.252 nodes e 13.406 edges; 5 testes focados e
  Ruff verdes, sem provider.
- `MODEL_HANDOFF_REQUIRED: gpt-5.6-sol`; revisão independente solicitada.
- Primeira revisão Sol `SPEC-166-SOL-20260928-01`: `CHANGES_REQUESTED` por ciclo
  infinito de SHA, inclusão de arquivos ignorados, import relativo falso e TS/JS
  classificados como artefatos. Correções implementadas, incluindo hash do
  schema, payloads nested bounded e decorators HTTP restritos; re-review pendente.
- Segunda revisão Sol `SPEC-166-SOL-20260928-02`: `CHANGES_REQUESTED` porque um
  objeto arbitrário chamado `app`/`router` ainda podia virar endpoint exato.
  A extração agora exige binding estático criado por `FastAPI`/`APIRouter`.
  Também foram fechados os riscos residuais de `from . import módulo`, validação
  estrutural do schema e limite de `matched_nodes`; 7 testes focados + Ruff e
  build/check verdes com 5.258 nodes e 13.449 edges. Terceira revisão pendente.
- Terceira revisão Sol `SPEC-166-SOL-20260928-03`: `CHANGES_REQUESTED` por
  sombreamento de um construtor local chamado `FastAPI` e aceitação de hash não
  hexadecimal/boolean como integer. A extração passou a rastrear origem e
  rebinding em ordem lexical, e o validador foi alinhado aos tipos JSON Schema.
  Build/check, 7 testes focados e Ruff novamente verdes; quarta revisão pendente.
- Quarta revisão Sol `SPEC-166-SOL-20260928-04`: `CHANGES_REQUESTED` por mutação
  de atributo do objeto FastAPI ainda preservar autoridade exata e por campos
  não hashable escaparem como `TypeError`. A análise agora invalida de forma
  conservadora nomes e raízes mutadas em atribuições, deletes, loops, with,
  handlers e blocos de controle; o validador checa strings antes de consultar
  enums/referências. Gate focado novamente verde; quinta revisão pendente.
- Quinta revisão Sol `SPEC-166-SOL-20260928-05`: `CHANGES_REQUESTED` por captures
  `MatchStar`/`MatchMapping` e efeitos imediatos de defaults/decorators não serem
  visitados. Ambos passaram a invalidar bindings; headers de funções/classes são
  analisados sem descer em corpos diferidos. Relações `route_to` foram ainda
  rebaixadas para `static_best_effort`, eliminando a alegação de exatidão em uma
  linguagem dinâmica. Gate focado verde; sexta revisão pendente.
- Sexta revisão Sol `SPEC-166-SOL-20260928-06`: `APPROVED`, sem bloqueadores.
  Gate final: índice fresco com 5.277 nodes/13.482 edges, 7 testes focados e Ruff
  verdes; suíte offline completa **1.832 passed, 35 skipped, 15 deselected**, zero
  falhas. Nenhuma chamada a provider ou long-run.
