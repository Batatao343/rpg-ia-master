# SPEC-424 — revisão terra (review)

> **Veredito:** `APPROVED`
> **Revisor:** Terra (Sonnet) · **Data:** 2026-11-22 · **Commit revisado:** `f84665da`

## Escopo

Diff `791ffaa1..HEAD` (2cc406ac, 7b95924e, f84665da) em `services/economy.py`, `tests/` e a spec. Ignoradas a ausência de SPEC-425 e as diferenças de `specs/index.yaml`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| (nenhum P0/P1) | | | | |
| P2-1 | P2 | services/economy.py:788-790 | Só `merchant_stocks` e `merchant_restock_day` são copiados fundo. Os demais dicts aninhados que `execute_trade` toca já são copiados pelos helpers: `add_item`/`remove_item` (`dict(e)` por entrada), `reconcile_equipment` (copia `equipment`), `_persist_keeper` (copia `npcs` antes de `ensure_keeper`). `_keeper_refusal`/`price` são leitura. Sem mutação residual achada; é só um registro. | Nenhuma. |

Conferido:
- R1: nenhum caminho (buy, sell comum, sell de único, recusas, modo desconhecido) escreve em `state`. As entradas de `player["inventory"]` não são mutadas, porque os helpers fazem `dict(e)` antes de alterar. `state["npcs"]` é protegido por `_persist_keeper`.
- R4: o deepcopy só roda `if key in world`, então nenhuma chave nova aparece. O `setdefault` da venda de único age sobre a cópia local. O `TradeOutcome` não mudou.
- Os 2 testes novos falham na `main` e passam na branch (tabela abaixo). O R3 compara `st == snapshot` inteiro, e o R2 confere identidade e valor. O xfail saiu, mantendo o `@example`. O `import pytest` removido não tem mais uso no arquivo, porque a execução passou.
- R5: `economy.py` tem 1071 linhas (não cresceu). A única mudança em `size_budget.json` é remover `execute_trade`, que agora tem ≤ 100 linhas e passa no gate.
- Hoist de `is_unique`: `inventory.py` importa só `gamedata` e `services.text` (linhas 19-20). Não há ciclo com `services.economy`, que já importava `inventory` no topo.

## Evidência verificada

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_bug_economia_integridade.py::test_buy_does_not_touch_input_stock | vermelho | verde | OK |
| tests/test_bug_economia_integridade.py::test_sell_unique_does_not_touch_input_stock | vermelho | verde | OK |

red_green: 2/2 OK

`test_p4_trade_does_not_mutate_input` (xfail removido) passa na branch.

## Correções aplicadas

Nenhuma necessária.

## Pendências

Suíte completa fica com o coordenador no pouso (critério aberto na spec). O item "loot_node chama restock sobre cópia rasa" já está registrado em "Fora de escopo" na spec.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest tests/test_mechanics_properties.py tests/test_bug_economia_integridade.py tests/test_size_budget.py -n 0 → verde (34 passed)
bash scripts/dev/red_green.sh 424 → 2/2 OK
```
