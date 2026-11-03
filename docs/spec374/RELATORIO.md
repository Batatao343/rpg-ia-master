# SPEC-374 — relatório do executor de produto (Etapa 0 + rodadas de ajuste)

## Etapa 0 — diagnóstico das 3 rodadas reais da 361 (sem LLM)

Fonte: `docs/spec361/eval-depois-2026-11-02{,b,c}.json`. Limite honesto: os registros guardam só a
ficha **final** e a lista de códigos acumulada das tentativas (não a mensagem do lint, nem o termo do
R20, nem a ficha reprovada). Por isso a tabela é por **código × ficha**, não por tentativa; a linha
de `eixos_livres` mais próxima e o termo de cada R20 **não são recuperáveis** dos JSON gravados.

Fichas `nova`/`fallback` que falharam em `lint_primeira` (15 de 33 pedidos `nova`):

| rodada | região | códigos |
|---|---|---|
| a | nova_arcadia | R20, U3 |
| a | skallgard | R20 |
| a | montanhas_afiadas | R20, U13, U3 |
| a | pradaria_ruinas | R20 |
| b | deserto_zhur | PRAZO (fallback) |
| b | nova_arcadia | R20, U2, U3 |
| b | skallgard | R20 |
| b | costa_negra | U13 (reparado) |
| b | montanhas_afiadas | U13, U3 |
| b | pradaria_ruinas | R20, U3, PRAZO (fallback) |
| c | nova_arcadia | U2, U3 |
| c | pantano_melancolia | R20 |
| c | skallgard | U3 |
| c | costa_negra | R20, U3 |
| c | montanhas_afiadas | U3 |

Por código (fichas): **R20 = 9, U3 = 9, U2 = 2, U13 = 3, PRAZO = 2**. Fichas com U2 ou U3 = 9 de 15
(60 %); fichas com R20 = 9 de 15. Ponto de decisão da §4 (Etapa 0.2): U2/U3 são maioria simples, mas
R20 empata. O R10 (eixos fechados) segue por desenho; o gargalo declarado é **U2/U3 + R20** e o R12
atacou os dois (linha numerada no lugar de eixos livres; léxico de jargão e a palavra "dragão" na regra;
`{nome}` do telégrafo normalizado pelo Python).

## Rodadas de ajuste (set `spec374_pedidos_ajuste.yaml`, DeepSeek `deepseek-v4-flash`, `mock=False`)

| rodada | mudança que a motivou | lint_primeira | fallback | falhas | job p50 / p95 |
|---|---|---|---|---|---|
| ajuste-1 | produto das Etapas 1-4 (linha de eixos, forma, reparo, prompt) | 8/11 (72,7 %) | 1 | U13 reparado; selva_xylos R20+U5+U5 (fallback); aethelgard U1 | 6,8 s / 9,8 s |
| ajuste-2 | + linha "primeira palavra do nome já usada" (U1/U4) | 10/11 (90,9 %) | 1 | ophidia SCHEMA+PRAZO (fallback) | 7,1 s / 21,7 s |
| ajuste-3 | (mesmo código; variância) | 7/11 (63,6 %) | 0 | U13 reparado; U4+U5; R20; U1+U13 | 7,2 s / 12,4 s |
| ajuste-4 | + `<padroes_livres>` (padrões que ninguém usa na região, por cadência) | 8/11 (72,7 %) | 0 | U5; U13 reparado; U1 | 6,9 s / 10,4 s |

Agregado do ajuste: 33/44 = 75,0 %. Referência da 361 nas 3 rodadas: 63,6 / 45,5 / 54,5 %. **U2/U3 sumiram
de `lint_primeira` nas 4 rodadas** (a linha numerada vem conferida pelo Python); sobraram U13 (padrão),
U1/U4/U5 (nome e silhueta) e R20 (1 caso em 4 rodadas, contra 9 em 3). O teto D5 (4 rodadas de ajuste) foi
usado. Variância entre rodadas de 11 pedidos é grande (7 a 10 de 11).

Risco §7 ("linha escolhida contradiz o pedido" > 2 de 11): lendo as 11 fichas da ajuste-4 contra o pedido,
nenhuma contradiz o corpo pedido (a prosa serve à linha); o risco não se materializou.

Latência do job: p50 caiu de ~8,6 s (361) para ~7 s (saída menor: seis enums a menos no schema).

## Honestidade sobre o `lint_primeira`

`info["lint_primeira"]` é o resultado do 1º lint **depois** de linha→eixos e da forma (D3: ambos rodam
antes do lint e não escolhem conteúdo) e **antes** de qualquer reparo (padrão U13, troca de linha U2/U3,
correção curta). `test_reparo_eixos_nao_conta_lint_primeira` e `test_lint_primeira_conta_linha_e_forma`
travam a fronteira.
