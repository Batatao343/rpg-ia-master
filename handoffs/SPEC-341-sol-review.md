# SPEC-341 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sol (spec-reviewer, Opus) · **Data:** 2026-10-27 · **Commit revisado:** `4da6ca9e`

## Escopo

Branch `spec-341`, `main...spec-341` (9 commits, `01f21781`..`4da6ca9e`, 12 arquivos): as 4 Cartas JSON
alteradas, `docs/spec341/*` (orquestrador, JSON da arena, RELATORIO), `tests/test_spec341_balanco.py` e a spec.
Decisões do dono aplicadas: D1–D8 recomendadas; D4-bis/D4-ter opção A (exceções silencioso, avaro held-out e
todas). A arena não foi rerodada. A conferência foi feita sobre os JSON gravados, recontando as células.

## Verificação por foco

1. **Avaliador e legadas congelados (R1/R2): OK.** `git diff --exit-code main...spec-341` está vazio em `scripts/cards/sim.py`,
   `docs/spec335/arena_posturas.py`, `data/cards/_orcamento.json`, `tests/test_card_sim.py`,
   `tests/fixtures/spec330_legacy_golden.json`, nos 10 JSON legados e em `evals/`. `test_legadas_intactas` (308 Cartas contra o golden) e
   `test_card_effects_grammar` estão verdes.
2. **Exceções restritas: OK.** `tests/test_spec341_balanco.py:215` traz `EXCECAO_ACEITA = {silencioso: 0.762, todas: 0.754}` (D4-bis, 0–19).
   `:219` traz `EXCECAO_HELD_OUT = {avaro: 0.752, silencioso: 0.766, todas: 0.756}` (D4-ter). Os valores são exatamente os
   dos JSON, sem folga, e o teto de cada sub é `max(0.75, exceção)` (`:226`). O exposto, os pisos de total ≥ 45 % e a faixa
   45–75 % de alma/boticário seguem com os limites originais. Não sobrou nenhum `xfail` no arquivo.
3. **Protocolo (R3/R6/R7): OK.** O orquestrador (`48524934`, 20:06) é anterior às Cartas (`55e6cba6`/`f5edb938`, 20:28) e nenhum
   commit posterior o altera. `arena-confirmacao.json` aparece uma única vez no histórico, em `2851ec8e` (21:49), depois do pacote,
   e não foi tocado de novo. O R8 (`r8-bandeiras-…json`) gravou `versoes` v1, ou seja, rodou antes das mudanças. As tentativas
   descartadas e a curva exploratória do RELATORIO são todas 0–19. Recontei as células: 181/240 = 75,4; 179 = 74,6; 183 = 76,2;
   169 = 70,4; held-out 726/960 = 75,6; 722 = 75,2; 735 = 76,6; 688 = 71,7; alma 50,7; boticário 63,0. Tudo bate com
   `RELATORIO.md:45-76`, assim como os deltas das Cartas e a atribuição (top avaro/silencioso = `atribuicao.json`).
   Em `arena-final.json`, as Posturas sem Carta alterada estão idênticas às de `docs/spec339/arena-depois.json`. Só divergem
   Sangromante todas/avaro/silencioso (L5) e Médico todas/boticário (L1/L3, efeito do Giz), como esperado.
4. **Cartas: OK.** Só onda 1, `versao` 1 → 2 e um passo cada: `cobranca_adiada` `dano_base` 4 → 3, e `juros_do_primeiro`,
   `corte_sem_aviso` e `ponto_cego` com Fôlego 1 → 2 (2 Cartas por subclasse, ≤ 3). Nenhuma mudança em `tier`, `level_req`,
   `patamar` ou `raridade`. Giz Vermelho e Dívida Gravada perderam `duracao: 2`; a ausência vale 1 (`_duracao_efetiva`), o que está
   coerente com a SPEC-339 e com a tabela do R14. `budget_error` é `None` nas 6.
5. **Lint e validação: OK.** `card_lint.lint_card` está limpo nas 6. A exceção é `juros_do_primeiro`, que tem um aviso `voz`
   pré-existente (a descrição não mudou). O teste filtra só esse código. `validate_content` deu 0 erros e 0 avisos.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `docs/spec341/RELATORIO.md:1-4`, `:61-65`, `:77` | O cabeçalho ainda diz "parcial… a confirmação 20–99 não foi rodada"; as pendências mandam "remover os `xfail`"; e falta a seção D4-ter (aceite das 3 exceções held-out). O registro da arena contradiz a si mesmo. | Só no documento: reescrever o cabeçalho como final, trocar as pendências pelo D4-bis/D4-ter e pelo follow-up P2-3. Sem rerodar a arena. |
| P2-2 | P2 | `specs/SPEC-341-balanco-sangromante.md:299-312`, `:349` | A spec está `done`, mas nenhum critério de aceite está marcado, e o parágrafo "Execução" ainda fala de `xfail(strict)`. | Marcar os critérios cumpridos e anotar o R9 como "cumprido com as exceções D4-bis/D4-ter". Atualizar `:349`. |
| P2-3 | P2 | `docs/spec341/arena-confirmacao.json` (`cartas.san1_sil_corte_sem_aviso`); spec `:353` | Na held-out, `corte_sem_aviso` v2 recebeu a bandeira `dominante` (+9,1 pp, uso 52 %). O smoke §6.2 pede "nenhuma bandeira `dominante` nova entre as alteradas", e nenhum teste guarda isso. Hoje o caso aparece só como frase dentro do D4-ter. | Coordenador: confirmar que o dono viu essa bandeira junto com o D4-ter. Registrar como follow-up da próxima onda de balanço (336), com a Carta já no limite de 1 passo. |
| P2-4 | P2 | `tests/test_spec341_balanco.py:174-176` | Para `marca`, o teste mede a presença da condição no alvo durante o turno do aplicador, que é o mesmo proxy da 339. Ele não observa a Vantagem num ataque: nas rodadas 2–4 o jogador não declara ação. Rodei o `run_round` de Giz e de Marca de Unha nas duas ordens: a condição aparece e termina uma vez, mas não há ataque do aplicador no log. O R15 pede "o próximo ataque tem Vantagem e o seguinte não". | Follow-up: declarar um ataque básico do jogador nas rodadas 2–3 e assertar a Vantagem só na 2. Ou anotar na spec que o proxy da 339 foi aceito. |
| P2-5 | P2 | `docs/spec341/RELATORIO.md:38-39` | Os deltas 0–19 de Giz (+3,7) e Dívida (−1,2/−3,7) não têm JSON bruto: `arena-final.json` não tem a chave `cartas`. O R17 pede os dados brutos. | Opcional: gravar a saída de `cartas --seeds 0:20` dessas 2 Cartas. Se não, citar no relatório que esses números vieram do console. |
| P2-6 | P2 | `data/cards/posturas/sangromante_avaro.json:100` | A descrição de `juros_do_primeiro` diz "O corte inicial não custa nada", mas agora a Carta custa Fôlego 2 + Entropia 1. A coerência pedida no R5 fica fraca, embora seja uma frase de sabor. | Follow-up de voz na esteira (336), com `nota_voz`. Não bloqueia. |
| P2-7 | P2 | `docs/spec341/arena_spec341.py` | Não há o subcomando `report` do §3.1: o RELATORIO foi escrito à mão (está declarado na docstring `:10`). `arena-confirmacao.json` junta a saída de `posturas` e de `cartas`, que o script grava em separado. Os dados conferem. | Só registrar o desvio na spec. |
| — | info | `r8-…json` × `arena-confirmacao.json` | O Giz com `duracao` 2 (R8) e com `duracao` 1 (final) dá vitórias idênticas (0,797/0,769, 334 jogadas). `vezes_na_mao` difere, então as rodadas foram de fato distintas. Isso sugere que, com o bot solo, a duração da Marca quase não move a taxa. | Nenhuma: só leitura para a próxima arena. |

Não houve P0 nem P1. O guard de structured output, valores do LLM e writers persistentes não se aplicam: a mudança é só de dados de Carta e teste. Nenhum segredo aparece em log.

## Correções aplicadas

Nenhuma até a data da revisão.

## Pendências

- P2-1 e P2-2: o executor ou o coordenador corrige antes do `/spec-land`. É só documento.
- P2-3: o coordenador confirma com o dono; depois vira item da SPEC-336 (próxima onda de balanço).
- P2-4, P2-5, P2-6 e P2-7: follow-ups da SPEC-336 ou anotação na spec.

## Comandos rodados

```text
git diff --exit-code main...spec-341 -- sim.py arena_posturas.py _orcamento.json test_card_sim.py golden evals/ + 10 JSON legados → vazio (FROZEN_OK)
git log main..spec-341 -- <arquivos> → orquestrador 20:06 < Cartas 20:28 < confirmação 21:49 (único commit)
py.sh -m pytest -q -n 2 test_spec341_balanco test_card_lint test_card_effects_grammar test_card_sim test_spec339_duracao_condicoes test_card_acervo_reparo test_balance_classes test_balance_classes_v4_runtime → rc=0 (~299 passed, 4 skipped)
py.sh scripts/validate_content.py → 0 erros, 0 avisos
script de conferência dos JSON (recontagem das células + comparação com spec339/arena-depois.json) → bate com o RELATORIO
run_round de Giz v2 e de Marca de Unha nas duas ordens → condição aplicada e expirada 1×; sem ataque do aplicador nas rodadas seguintes (P2-4)
```
