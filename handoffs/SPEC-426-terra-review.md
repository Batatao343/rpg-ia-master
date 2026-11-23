# SPEC-426 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet/terra (independente do executor) · **Data:** 2026-11-23 · **Commit revisado:** `a8d4d678` (base `61b2f96b`)

## Escopo

Branch `spec-426`, 3 commits (b2d6f50c, a5f8a06f, a8d4d678), 14 arquivos. R9 fora de propósito (commit do coordenador). Domínio llm-structured.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/test_character_creator_flavor.py:41-45` | O teste do caminho `AIMessage` passa **antes e depois** da correção de R4 (verde/verde no red_green). É o que R4(b) exige e é coerente (o resultado observável não muda: `AIMessage.model_dump()` não tem `inventory`), mas o teste não prova a correção; quem prova é o gate de tipos (`character_creator.py` cai de 3 para 2 erros na medição). | Nenhuma; só registrar que a defesa do guard é o checador, não o teste. |
| P2-2 | P2 | `docs/spec426/medicao.md` E0.5 vs `type_gate.py --land` | A medição diz baseline atual de 94 entradas (+153 = 247); o `--land` imprime "baseline com 66 entradas". Unidades de contagem diferentes (por diagnóstico vs por arquivo+regra), sem explicação. | O coordenador confere a contagem ao fazer R9 (`--update`) e registra a unidade no `baseline_log.md`. |
| P2-3 | P2 | `docs/spec426/medicao.md` E0.4 | Medições com pytest alheio e RAM livre 1,0-2,5 GB: o tempo frio (396 s) e o quente do escopo atual (188 s) são lixo por paginação. Isso **não invalida** a decisão de não cortar: o pico (1.083 MB) é por árvore de processos e tem 0,9 GB de folga sob o teto de 2,0 GB; o quente de 34,5 s foi medido com a máquina sob carga e ainda ficou em 60 % do teto de 60 s. O risco restante é só tempo frio no CI. | Rodada quente com a máquina quieta e o job `types` do CI (§6.1/6.4) confirmam no pouso de R9; se o job passar de 5 min, aplicar o corte de R6.2. |
| P2-4 | P2 | `scripts/dev/red_green.sh 426` | Os 4 testes `types_e2e` aparecem como `error` na branch (o script não passa `-m types_e2e`; o marcador os exclui), então a tabela fica 4/8. Os mesmos testes passam em `pytest -m types_e2e` (8 passed). Falha de ferramenta, não da branch. | O coordenador deve ter ciência ao rodar o `land_check`; evidência de verde está abaixo. |

Nenhum P0/P1.

## Verificação por ponto do pedido

1. **Runtime inalterado.** Anotações com aspas ou `from __future__ import annotations` (`chronicle_compression`, `shared_pool`, `narrative_sink`), import só sob `TYPE_CHECKING` (nenhum import novo em runtime; sem ciclo `services` ↔ `llm_setup`). Oráculo AST de I1 refeito por mim (remove `arg.annotation`, `returns`, bloco `if TYPE_CHECKING` e o nome `TYPE_CHECKING` do import de `typing`): os 6 services iguais à `main` (`True` ×6). R4 em `character_creator.py:417`: `if stats:` vira `isinstance(stats, PlayerFlavorSchema)`. Caminho MockLLM: `_StructuredMock` devolve instância Pydantic do schema, mesmo resultado. Caminho `FallbackLLM`/`AIMessage`: antes `AIMessage` truthy → `model_dump()` sem `inventory` → `flavor_data` fica vazio; agora pula direto, mesmo resultado (`Kit Básico`). `except Exception` com log já existente.
2. **R1/R2.** `llm_protocol.py` com 24 linhas, só `typing`/`__future__`, sem `runtime_checkable`. `test_llm_param_unguarded_is_rejected`, `…_guarded_passes`, `test_untyped_llm_param_is_blind` e `test_real_clients_satisfy_protocol` passam com `-m types_e2e` (8 passed; `get_llm(...)`, `MockLLM()`, `FallbackLLM("x")` aceitos sem `cast`).
3. **R7.** `checker_cmd` é pura e passa `--pythonpath <python>`; a opção existe na 1.40.2 (o `run_checker` real roda nos e2e com ela). O `.venv` velho não reproduziu (E0.2); manter R7 é inofensivo (mesmo interpretador que já era o implícito). Ressalva da spec §7 (land_check usa o Python do principal) continua válida.
4. **R8.** `.basedpyright/baseline.json` fora do diff; `include` ganhou só `services/llm_protocol.py` (`pyproject.toml:175`); `type_gate.py --land --base main` → `OK types: nenhum erro novo, baseline com 66 entradas`.
5. **medicao.md.** Números batem com a spec (R6: 1.083 MB, 34,5 s quente, 153 erros em 11 arquivos, 247 entradas/57,2 KB); `include` final proposto bate com R5 (14 novos: 4 services + llm_protocol + `character_creator` + 10 agents, sem corte). Ver P2-3 sobre carga.
6. **Tamanho/lint.** `tests/test_size_budget.py` verde; `ruff check` e `ruff format --check` limpos; nenhum `noqa`/`type: ignore` novo no diff. Follow-ups de R4 (librarian `:89-95` com ajuste do `_FakeMatch` em `tests/test_efficiency.py:65`; archivist `:1007`; `_StoryTurn.llm`) estão em `medicao.md` § Follow-ups. A decisão de não corrigir `librarian` segue R4(b).

## Evidência verificada

`bash scripts/dev/red_green.sh 426 --allow-green <controles e os 2 de R4>` (RAM livre 1,1-1,9 GB, ver P2-4):

| teste | main | branch | veredito |
|---|---|---|---|
| test_character_creator_flavor::test_aimessage_result_falls_back_without_flavor | verde | verde | OK (allow-green, R4b) |
| test_character_creator_flavor::test_flavor_from_structured_result_is_used | verde | verde | OK (allow-green) |
| test_type_gate::test_checker_cmd_pins_interpreter | vermelho | verde | OK |
| test_type_gate::test_llm_protocol_has_only_typing_imports | vermelho | verde | OK |
| test_type_gate::test_llm_param_unguarded_is_rejected | vermelho (import) | error (sem `-m types_e2e`) | ver abaixo |
| test_type_gate::test_llm_param_guarded_passes | vermelho (import) | error (idem) | ver abaixo |
| test_type_gate::test_real_clients_satisfy_protocol | vermelho (import) | error (idem) | ver abaixo |
| test_type_gate::test_untyped_llm_param_is_blind | vermelho (import) | error (idem) | ver abaixo |

`red_green: 4/8 OK`. Os 4 `error` são artefato do marcador `types_e2e`; rodados com `pytest -m types_e2e tests/test_type_gate.py` na branch: 8 passed.

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

- Follow-ups de R4 (librarian, archivist, `_StoryTurn.llm`): spec própria (coordenador).
- R9 na `main`: conferir a contagem 66 vs 94 (P2-2) e medir quente/CI (P2-3).

## Comandos rodados

```text
pytest tests/test_type_gate.py tests/test_character_creator_flavor.py tests/test_size_budget.py -n 0 → verde
pytest -m types_e2e tests/test_type_gate.py → 8 passed
type_gate.py --land --base main → OK types
ruff check . / ruff format --check → limpos
red_green.sh 426 (ver tabela) → 4/8 (artefato do marcador)
oráculo AST de I1 (6 services) → iguais
```
