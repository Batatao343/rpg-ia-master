# SPEC-426 — medições da Etapa 0

Windows 11, 16 GB, worktree `rpg-spec-426` sobre `main` `61b2f96b`. Checador medido por `type_gate`/`scope_run` (soma do working set da árvore de processos, amostrada a cada 0,4 s). **Havia pytest de outra sessão (checkout principal) rodando em todas as medições** (2 a 4 processos `pytest`) e a RAM livre antes de cada rodada ficou entre 1,0 e 2,5 GB (< 3 GB; piso liberado pelo coordenador em 22/11, registrado ao lado de cada número). Tempos, portanto, são pessimistas e muito ruidosos; o pico de RAM é o número confiável (pode estar subestimado com a máquina paginando).

## E0.1 Opção de interpretador (basedpyright 1.40.2)

`--pythonpath <FILE>  Path to the Python interpreter` (também `-v,--venvpath`). R7 usa `--pythonpath`.

## E0.2 `.venv` velho

Criado `uv venv .tmp/spec426/stale` (Python 3.13, sem dependências) e junção como `.venv` do worktree. Arquivo-sonda com `from pydantic import BaseModel` e `from llm_setup import ...`, checado por `python -m basedpyright --outputjson` **sem** `--pythonpath`: rc 0, 0 `reportMissingImports`. Com `--pythonpath`: rc 0. **Não reproduziu** (o checador, aqui, não escolheu o `.venv` do worktree). R7 mantido mesmo assim (determinismo barato). Junção removida.

## E0.3 Contagem no escopo de R5 (config provisória, baseline copiada em `.tmp`)

Escopo atual (9 itens): `--check` OK (baseline justa). Escopo R5 completo, com as anotações de R3 e a correção de R4 aplicadas: **153 erros novos em 11 arquivos** (sem as anotações/R4 eram 154; só `character_creator.py` 3 → 2).

| Arquivo | Erros |
|---|---|
| agents/archivist.py | 7 |
| agents/bestiary.py | 1 |
| agents/campaign_manager.py | 29 |
| agents/combat.py | 43 |
| agents/librarian.py | 4 |
| agents/loot.py | 18 |
| agents/npc.py | 25 |
| agents/router.py | 14 |
| agents/storyteller.py | 4 |
| character_creator.py | 2 |
| services/encounter_preparation.py | 6 |
| agents/world_simulator.py, services/death_flow.py, narrative_sink.py, tactical_profile.py, llm_protocol.py | 0 |

Por regra: reportArgumentType 116, reportOptionalMemberAccess 10, reportCallIssue 7, reportAttributeAccessIssue 5, reportReturnType 4, reportTypedDictNotRequiredAccess 4, reportGeneralTypeIssues 3, reportPossiblyUnboundVariable 2, reportOptionalSubscript 2.

Diagnósticos que citam `object`/`AIMessage` (R4):

| arquivo:linha | classificação | destino |
|---|---|---|
| agents/librarian.py:91,92,94,95 (`match_found`/`existing_id` em `object`) | guard fraco (`not isinstance(result, BaseMessage)`) | **não corrigido**: `tests/test_efficiency.py:65-75` usa `_FakeMatch` (não `EntityMatch`); trocar por `isinstance(result, EntityMatch)` quebraria o teste (critério R4b). Follow-up |
| character_creator.py:417-418 (`stats.model_dump()` em `object`) | guard fraco (só `if stats:`) | **corrigido**: `isinstance(stats, PlayerFlavorSchema)`; novo `tests/test_character_creator_flavor.py` cobre o caminho `AIMessage` e o caminho estruturado (passam antes e depois, mesma saída) |
| agents/archivist.py:1007 (`with_structured_output` em `None`) | `llm` Optional no chamador, legado | baseline/follow-up |
| agents/campaign_manager.py:424,425,464,465; agents/loot.py:670,715,716,739,743,871; agents/bestiary.py:302 (`object` em argumento) | falso positivo quanto ao LLM: `object` vem de dict/estado, não do cliente | baseline |
| combat.py (490,549,696,697,1300,3786,3795), router.py:388, npc.py:753-755 | legado sem relação com o guard | baseline |

Nenhum `AIMessage` aparece por causa de `narrate_structured -> object` (os chamadores em `agents/` já usam `isinstance`); `storyteller.py` só 4 erros, o narrador segue cego pelo `Any` de `_StoryTurn.llm`.

## E0.4 Tempo e RAM

| Escopo | Rodada | Tempo | Pico | RAM livre antes / pytest alheio |
|---|---|---|---|---|
| atual (9 itens) | fria | 82,8 s | 749 MB | 1,8 GB / 2 |
| atual | quente | 188,0 s | 747 MB | 1,8 GB / 2 (máquina paginando) |
| R5 completo (sem anotações) | fria | 395,9 s | 1 081 MB | 2,1 GB / 4 |
| R5 completo (final) | quente | **34,5 s** | **1 083 MB** | 1,0 GB / 2 |

Critério R6: pico 1,08 GB ≤ 2,0 GB; quente 34,5 s ≤ 60 s (a única rodada sem paginação pesada). **Nenhum corte**: `storyteller.py` e `combat.py` ficam no `include`. O pico fica a ~0,3 GB do escopo atual. A medição do job de CI (≤ 5 min) e uma rodada quente na máquina quieta ficam para o coordenador (§6.1/6.4).

## E0.5 Baseline projetada (cópia em `.tmp`, sem `--update`)

247 entradas (eram 94 na baseline atual; +153), **57,2 KB** (≪ 500 KB). Os 153 erros por arquivo estão na tabela de E0.3 (cada um vira uma entrada de baseline por arquivo+regra).

## E0.6 `types_e2e`

`pytest tests/test_type_gate.py -m types_e2e`: 8 passed em 37 s (inclui os 4 novos, máquina carregada).

## `include` final para o commit de R9 (sem corte)

```toml
include = [
    "infrastructure",
    "state.py",
    "state_archive.py",
    "persistence.py",
    "character_creator.py",
    "agents/archivist.py",
    "agents/bestiary.py",
    "agents/campaign_manager.py",
    "agents/combat.py",
    "agents/librarian.py",
    "agents/loot.py",
    "agents/npc.py",
    "agents/router.py",
    "agents/storyteller.py",
    "agents/world_simulator.py",
    "services/chronicle_compression.py",
    "services/creature_gen.py",
    "services/daily_spend_cap.py",
    "services/death_flow.py",
    "services/encounter_preparation.py",
    "services/llm_protocol.py",
    "services/narrative_sink.py",
    "services/prologue.py",
    "services/shared_pool.py",
    "services/tactical_profile.py",
]
```

Comando de R9: `type_gate.py --update --reason "SPEC-426 escopo agents + services LLM"` (+153 entradas); mais a asserção de R10 sobre o `include` em `test_basedpyright_config_matches_spec`.

## Follow-ups (R4)

- `agents/librarian.py:89-95`: trocar `not isinstance(result, BaseMessage)` por `isinstance(result, EntityMatch)` e ajustar o `_FakeMatch` de `tests/test_efficiency.py:65`.
- `agents/archivist.py:1007`: `llm` possivelmente `None` no ramo sem registro.
- `_StoryTurn.llm` / `mediated_stream.narrate` (storyteller), já previsto na spec.
