# SPEC — Checkpoint transacional de estado e memória

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `checkpoints-morte` e memória híbrida (`done`)
> **Desbloqueia:** continuidade após morte sem fatos de linhas temporais descartadas

---

## 1. Contexto & Objetivo

O checkpoint restaurava o JSON do `GameState`, mas não o índice FAISS associado
ao mesmo `game_id`. No playtest, após “Continuar”, o ledger não continha a morte,
enquanto a consulta semântica ainda recuperava o fato canônico de que o jogador
morreu. Estado e memória deixavam de representar a mesma linha temporal.

O checkpoint passa a tratar o save JSON e toda a árvore de memória da sessão
(inclusive subíndices de NPC) como uma única unidade lógica.

## 2. Requisitos

- **R1** — `save_checkpoint` deve gravar um snapshot substituível da memória inteira do `game_id`.
- **R2** — “Continuar” a partir do checkpoint em disco deve restaurar estado e memória do mesmo instante.
- **R3** — Um checkpoint criado quando não havia memória deve restaurar ausência de memória, removendo fatos posteriores.
- **R4** — A escrita/restauração deve usar diretório temporário e troca atômica, sem aceitar caminhos fora das raízes configuradas.
- **R5** — Deleção de save deve remover também o snapshot de memória do checkpoint.
- **R6** — Checkpoints em memória usados pelo harness devem carregar a memória junto, sem contaminar campanhas.

### Fora de escopo

Múltiplos slots, branching de timelines ou sincronização distribuída.

## 3. Design técnico

- **`persistence.py`** — `save_checkpoint_memory`, `restore_checkpoint_memory` e remoção composta; snapshot em `<SAVES_DIR>/<game_id>.checkpoint.memory/`.
- **`services/checkpoints.py`** — `Snapshot` contém estado e bytes/arquivos da memória; compatibilidade com snapshots dict antigos.
- **`playtest/runner.py`** — usa o snapshot transacional da camada de checkpoint.
- **`tests/test_checkpoint_memoria_transacional.py`** — cobre raiz, NPC, snapshot vazio e compatibilidade.

## 4. Plano passo a passo

### Etapa 1 — Snapshot externo

1. **Testes:** criar arquivos sentinela na memória, sobrescrever após checkpoint e confirmar restauração exata.
2. **Implementação:** cópia atômica validada e integração com persistência.
3. **Verificação:** testes de checkpoint e hardening verdes.

### Etapa 2 — Harness

1. **Testes:** snapshot em memória restaura arquivo descartado.
2. **Implementação:** snapshot composto e cleanup de temporários.
3. **Verificação:** campanha curta com morte e continuação.

## 5. Critérios de aceite

- [x] Fato indexado após checkpoint desaparece depois de “Continuar”.
- [x] Memória existente no checkpoint permanece, inclusive a de NPC.
- [x] Snapshot vazio restaura sessão vazia.
- [x] Deleção remove o artefato adicional.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum structured output/LLM novo.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Criar checkpoint, gerar memória canônica, morrer e escolher “Continuar”.
2. Consultar o fato descartado e confirmar ausência.

Validado com RAG real no smoke `20260812-172526-505951` e com rollback integral
determinístico (raiz + NPC + snapshot vazio + falha parcial) na suíte offline.

## 7. Riscos & compatibilidade

- Checkpoints antigos sem snapshot externo continuam restaurando o estado; a memória é reconstruída/limpa de forma conservadora.
- I/O cresce com a memória da sessão, mas permanece local e sem custo de provider.
