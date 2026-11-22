# SPEC-424 — economia-execute-trade-sem-mutar-entrada

> **Status:** `done` (22/11: revisão `terra` APPROVED, `handoffs/SPEC-424-terra-review.md`; suíte completa 11788 passed. Aprovada em 22/11 pelo coordenador, com a delegação de 13/11 "autorizo tudo")
> **Criada:** 2026-11-13 · **Atualizada:** 2026-11-22
> **Depende de:** SPEC-417 (`done`; o teste de propriedade P4 (c) nasceu lá em `xfail(strict=True)`)
> **Desbloqueia:** nada; fecha o achado 1 da SPEC-417 (`handoffs/SPEC-417-terra-review.md:24,62`)
> **Risco:** `médio` (economia determinística; nenhum schema, save ou contrato de saída muda, só a função deixa de escrever no dict que recebe). Revisor Sonnet.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Requer:** nada
> **Domínios de revisão:** nenhum dos cinco do guia (sem thread, SQL, rota, writer persistente ou LLM)
> **Evidência:** teste que falha antes: `tests/test_mechanics_properties.py::test_p4_trade_does_not_mutate_input` hoje só passa porque está em `xfail(strict=True)`; tirar o marcador sem corrigir o código deixa o teste vermelho no exemplo fixo `location='brekmar', gold=5000, mode='buy', pick=0, qty=1`. Dois testes novos de exemplo (R2, R3) também falham antes.

---

## 1. Contexto & Objetivo

`economy.execute_trade` promete devolver um `TradeOutcome` e deixar o `state` de entrada intacto
(o nó aplica `outcome["player"]`/`outcome["world"]` como update parcial). Hoje a compra escreve
no estado que recebeu: `world = dict(state["world"])` é cópia rasa (`services/economy.py:786`),
`_ensure_stock` devolve `world["merchant_stocks"][mid]`, que com a loja já visitada é o mesmo
dict do chamador, e a linha 812 decrementa nele. A venda de item único faz o mesmo na linha 876.
Com a loja ainda não visitada, `_ensure_stock` grava a data em `world["merchant_restock_day"]`,
que também é o dict do chamador quando a chave já existe.

Efeito no produto: o estoque do mercador some do estado do chamador mesmo quando o resultado do
nó é descartado ou o turno é refeito (retry), sem compra efetivada. O teste de propriedade da
SPEC-417 achou o caso e ficou em `xfail` estrito à espera desta spec.

Princípio: "Mecânica é Python" e cada nó devolve dict parcial, nunca muta a entrada.

## 2. Requisitos

- **R1** — `execute_trade(state, mode, item_ref, qty)` não muta `state` em nenhum caminho
  (`buy`, `sell`, recusa, modo desconhecido): `copy.deepcopy(state)` antes da chamada é igual a
  `state` depois. Prova: `test_p4_trade_does_not_mutate_input` sem o `xfail`.
- **R2** — Compra com a loja já visitada: `out["world"]["merchant_stocks"][mid][iid]` cai `qty`
  e `state["world"]["merchant_stocks"][mid][iid]` fica igual; os dois dicts não são o mesmo
  objeto. Teste de exemplo em `tests/test_bug_economia_integridade.py`.
- **R3** — Venda de item único: `out["world"]["merchant_stocks"][mid]` ganha o item e o
  `state` de entrada não (hoje ganha). Teste de exemplo no mesmo arquivo, reusando `UNIQ`.
- **R4** — O `TradeOutcome` não muda: mesmas chaves e valores de antes para a mesma entrada.
  Em especial, venda de item comum numa `world` sem `merchant_stocks` continua devolvendo
  `world` sem essa chave (não introduzir chave vazia). Prova: os testes atuais de
  `execute_trade` passam sem edição (lista em §4).
- **R5** — `services/economy.py` não cresce (1071 linhas) e `execute_trade` não cresce (101
  linhas): gate `tests/test_size_budget.py`. Sem `size_budget.py --update`.

### Fora de escopo

- `merchant_stock`, `_ensure_stock` e `restock` continuam gravando no `world` que recebem: é o
  contrato atual deles, e quem precisa de leitura pura já copia antes
  (`public_market_snapshot`, `agents/loot.py:119`). Não mexer.
- `loot_node` chama `restock` sobre cópia rasa de `state["world"]` (`agents/loot.py:673-677`),
  então o reabastecimento escreve nos dicts aninhados da entrada. É determinístico e idempotente
  pelo relógio (refazer o turno dá o mesmo estoque), logo sem efeito visível. Fica registrado
  aqui; só vira spec se aparecer efeito.
- `execute_craft` (não escreve em `world`) e `card_shop.buy`.
- Qualquer refatoração de `economy.py`.

### Invariantes

- **I1** — Ouro e estoque conservados na troca (teste: `test_p4_trade_conserves_gold_and_stock`,
  sem edição).
- **I2** — Único vendido fica com o mercador e é recomprável (testes:
  `test_bug_economia_integridade.py` linhas 98-105 e 286-297, sem edição).
- **I3** — Keeper é persistido por `outcome["npcs"]`, nunca por escrita em `state["npcs"]`
  (testes: `test_spec298_economia_keeper.py`, sem edição).

## 3. Design técnico

- **Arquivos alterados**
  - `services/economy.py`, só `execute_trade`: depois da cópia rasa de `world`, trocar por
    cópias próprias os dois dicts aninhados que a função (via `_ensure_stock`) pode escrever,
    **só quando a chave existe** (R4):

    ```python
    for key in ("merchant_stocks", "merchant_restock_day"):
        if key in world:
            world[key] = copy.deepcopy(world[key])
    ```

    `copy` já está importado. Nada mais muda na lógica.
  - Para caber em R5: `is_unique` entra no `from inventory import (...)` do topo
    (`economy.py:23`; `inventory` já é importado ali, sem ciclo) e saem os dois imports locais
    de dentro de `execute_trade` (com a linha em branco de cada um). O import local de
    `restock` pode sair junto. Se ainda faltar linha, encolher dentro da própria função
    (ex.: `_, merchant = mid, MERCHANTS.get(mid, {})` vira `merchant = MERCHANTS.get(mid, {})`).
    Depois, `bash scripts/dev/py.sh scripts/dev/size_budget.py --tighten` se a baseline encolher.
  - `tests/test_mechanics_properties.py`: remover o `@pytest.mark.xfail(...)` de
    `test_p4_trade_does_not_mutate_input` (mantém o `@example`); atualizar o docstring se citar
    número de linha.
  - `tests/test_bug_economia_integridade.py`: dois testes novos (R2, R3).
- **Arquivos novos:** nenhum. **Schemas/assinaturas:** sem mudança.

### Concorrência

N/A — sem thread/async/cancelamento.

## 4. Plano passo a passo

### Etapa 1 — vermelho

1. **Testes:** tirar o `xfail` de `test_p4_trade_does_not_mutate_input`; escrever
   `test_buy_does_not_touch_input_stock` (R2) e `test_sell_unique_does_not_touch_input_stock`
   (R3). Rodar e ver os três falharem pelo motivo certo (estoque da entrada alterado).

### Etapa 2 — correção

1. **Implementação:** o bloco de §3 em `execute_trade` + o ajuste de linhas de R5.
2. **Verificação (escopo, `-n 2`):** `tests/test_mechanics_properties.py`,
   `tests/test_bug_economia_integridade.py`, `tests/test_fase44.py`, `tests/test_fase62.py`,
   `tests/test_spec298_economia_keeper.py`, `tests/test_spec301_perks.py`,
   `tests/test_playtest_scenarios.py`, `tests/test_bug_contabilidade_recompensas.py`,
   `tests/test_size_budget.py` e os testes de `loot` que tocam compra/venda
   (`tests/test_spec311_integration.py`, `tests/test_spec363_rewards_shop.py`).
3. `ruff format` + `ruff check` nos arquivos tocados.

## 5. Critérios de aceite

- [x] `test_p4_trade_does_not_mutate_input` verde sem `xfail` (R1)
- [x] Testes de R2 e R3 falham antes e passam depois
- [x] Nenhum teste existente de `execute_trade` editado (R4)
- [x] `tests/test_size_budget.py` verde sem `--update` (R5)
- [x] `uv run pytest` verde (suíte completa offline, pelo coordenador no pouso): 11788 passed, 330 skipped, 1 xfailed (`FULL_N=3 bash scripts/dev/full.sh`, 22/11)
- [x] Guard de FallbackLLM: N/A (sem `with_structured_output`)
- [x] Saves antigos continuam carregando (nada de formato muda)

## 6. Smoke test com LLM real

N/A: função determinística sem LLM; o caminho de narração do `loot_node` não muda.

## Não rodou e por quê

- A suíte completa do pouso rodou na branch `spec-411` empilhada sobre esta (424 + commit de eval da 411 R5), com base na `main` de antes do pouso da SPEC-422. A 422 pousou com suíte própria (11858 passed); a combinação das duas não rodou junta.
- `size_budget.py --tighten` removeu a entrada de `execute_trade` (ficou <= 100 linhas) e baixou rag.py/combat.py por deriva alheia.

## 7. Riscos & compatibilidade

- Saves antigos: sem impacto (nenhuma chave nova ou removida em `world`).
- MockLLM / FallbackLLM: não envolvidos.
- Custo: um `deepcopy` de dois dicts pequenos (estoque por mercador) por transação.
- Risco real: algum chamador depender da mutação por referência. O único chamador de produção
  é `agents/loot.py:720`, que usa `outcome["world"]`; `public_market_snapshot` do "depois"
  também recebe `outcome["world"]` (`loot.py:803-808`).
