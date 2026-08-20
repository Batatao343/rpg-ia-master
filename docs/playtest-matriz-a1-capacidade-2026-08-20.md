# Matriz A1 interrompida por capacidade LLM — 2026-08-20

Run: `20260820-155300-494278`  
Status final: `aborted` / `llm_only_capacity_exhausted`  
Escopo persistido: 1 de 10 campanhas.

## Conclusão

A1 não é um baseline válido. O par normal chegou a 200 turnos, mas somente 89
das 796 tentativas LLM tiveram sucesso. Houve 707 falhas e 146 turnos sem nenhum
sucesso de rede. Os guards resilientes do produto mantiveram o jogo funcional,
porém isso converteu grande parte da campanha em fallback determinístico —
explicitamente fora do contrato deste experimento.

O processo foi interrompido assim que o summary revelou a perda de capacidade;
os nove pares restantes não foram executados.

## Métricas do par persistido

| Métrica | Valor |
|---|---:|
| Perfil / classe / nível | normal / Devoto do Abismo / 1 |
| Turnos | 200/200 |
| Tentativas LLM | 796 |
| Sucessos LLM | 89 |
| Falhas LLM | 707 |
| Turnos sem sucesso de rede | 146 |
| Limite diário — 120b | 305 falhas |
| Limite diário — 20b | 378 falhas |
| Rate limit — 20b | 20 falhas |
| Tool call inválido | 4 falhas |
| Mortes/restores | 2 |
| Invariantes `error` | 0 |
| Warnings | 20, todos de latência |
| Custo estimado pelo harness | US$ 0,25044 |

O custo é uma estimativa conservadora por tentativa de rede, não uma fatura do
free tier. A cota diária já estava parcialmente consumida antes de A1: o 120b
registrou limite diário desde o primeiro turno; o 20b perdeu capacidade no
turno 30.

## Correções do motor confirmadas antes da invalidação qualitativa

- Dois combates observados encerraram em 6 e 4 rodadas, sem `combat.no_progress`.
- Vitalidade chegou a 0 duas vezes apenas dentro de combate; ambos os casos
  seguiram para morte/restore seguro, nunca exploração viva a 0.
- O relatório preservou as duas mortes, com turno, epoch, local e causa.
- Os 20 warnings eram exclusivamente `performance.turn_latency`; menções
  memoriais de NPC não voltaram a gerar `narrative.recycled_npc`.

Essas verificações são de mecânicas Python e observabilidade. A qualidade
narrativa após a perda de provider não pode ser usada como evidência.

## Nova proteção

A spec [playtest real LLM-only fail-closed](../specs/playtest-real-llm-fail-closed.md)
faz a matriz agrupar candidatos pelo `attempt_index`. Se uma invocação inteira
terminar sem `success`, a campanha grava `llm_terminal_failure`, aborta no mesmo
turno e não inicia o próximo par. A política vale apenas para a matriz real;
resiliência do jogo de produção e campanhas offline permanece inalterada.

Validação pós-fix: 1594 testes verdes e matriz offline 10×3
`20260820-171103-075466` com 30/30, zero erro/violação.
O smoke dirigido `20260820-171220-525250` enfrentou três Cervos Afogados em
dois conflitos ao longo de 30 turnos; ambos encerraram e não houve
`combat.no_progress`.

## Retomada com DeepSeek e achado de contrato

Após a recarga do DeepSeek, o preflight real dos tiers CLASSIFY, FAST e SMART
passou com `deepseek-v4-flash`. A tentativa `20260820-180632-012432` foi
encerrada pelo fail-closed no turno 2 do primeiro par: o planner retornou seis
beats válidos, enquanto `CampaignPlanModel` rejeitava qualquer lista acima de
cinco. Nenhum outro par foi iniciado.

Esse run também não é baseline. O achado é tratado pela spec
[`campaign-beats-overflow-provider`](../specs/campaign-beats-overflow-provider.md):
a borda aceita excesso recuperável e trunca deterministicamente para os cinco
primeiros beats não vazios, sem fabricar conteúdo ausente. A1 será reiniciada
desde o par 1 depois da regressão e da suíte completa.

A retomada seguinte, `20260820-181149-643772`, também encerrou antes de formar
baseline: no turno 1, o `world_simulator` recebeu `None` em vez de `WorldPulse`.
As outras seis invocações reais do turno/startup tiveram sucesso, confirmando
que não era perda geral de capacidade. O comportamento resiliente do jogo fez
no-op, mas o fail-closed corretamente recusou esse fallback determinístico e
não iniciou os nove pares restantes.

A spec [`structured-output-retry-provider`](../specs/structured-output-retry-provider.md)
adiciona uma única regeneração semântica no mesmo provider/modelo quando houve
resposta de rede, mas o payload Pydantic foi inválido. Erros HTTP, timeout, quota
e saldo permanecem fail-fast (`max_retries=0`). A telemetria usa índices
monotônicos na mesma invocação, portanto um `invalid_structured` recuperado por
`success` não vira falso terminal. Gate: 1600 testes verdes; preflight real
DeepSeek CLASSIFY/FAST/SMART 3/3.

## A1 de 150 turnos e terceira geração semântica

O run `20260820-182003-393045` avançou 150 turnos do par normal antes de
encerrar. Foram 374 sucessos reais em 382 tentativas, custo estimado de
US$ 0,10696, p95 de 21,8 s, zero invariante `error`, zero warning e zero erro de
observabilidade. Sete combates encerraram corretamente; houve duas mortes com
restore seguro. O erro terminal ocorreu em um replan: duas gerações SMART
consecutivas retornaram `None` para `CampaignPlanModel`; CLASSIFY e FAST do
mesmo turno tiveram sucesso.

Um replay imediato de `_build_plan` sobre o save exato teve sucesso na primeira
geração e retornou cinco beats. A falha era transitória, não incompatibilidade
de schema. O limite passou a três gerações totais — no máximo duas
regenerações — no mesmo provider/modelo. O client continua `max_retries=0` para
HTTP/quota/timeout. A suíte permanece em 1600 testes verdes e o novo preflight
DeepSeek passou 3/3.

Durante o monitoramento também foi encontrado um processo Groq antigo ainda
vivo, referente à matriz invalidada `20260820-155300-494278`. Ele foi encerrado
por PID sem tocar na árvore DeepSeek. O harness hoje não impede duas matrizes
ativas ao mesmo tempo; isso fica registrado como achado operacional de
single-flight para a rodada formal de specs pós-A.

## A1 de 200 + 71 turnos: timeout e memória de perigo

A tentativa `20260820-185627-750638` completou o par normal em 200/200: 542
sucessos reais em 548 tentativas, custo estimado de US$ 0,15344, 24 replans,
zero erro, zero invariante `error` e zero erro de observabilidade. Três warnings
foram instâncias de `narrative.recycled_npc` para Mara do Sétimo Sino fora do
local de origem; a evidência será preservada para a análise formal da matriz A.

O par explorador chegou ao turno 71, com 170 sucessos em 175 tentativas, dez de
dez conflitos encerrados e zero invariante `error`. No turno terminal, quatro
chamadas tiveram sucesso, porém três invocações lógicas independentes expiraram
entre 12,0 e 12,5 s (FAST structured, SMART structured e SMART plain). O limite
de produção de 12 s é deliberadamente fail-fast para permitir fallback, mas é
curto para o preset isolado sem fallback e para o watchdog experimental de
120 s. A spec [`deepseek-paid-timeout-longrun`](../specs/deepseek-paid-timeout-longrun.md)
define 40 s somente dentro do contexto `deepseek-paid` e restaura a env ao sair.

Antes da falha de capacidade, o explorador morreu nove vezes. As últimas cinco
mortes ocorreram na Fortaleza de Vorr: o checkpoint retornava a Skallgard e o
perfil voltava a classificar Vorr como fronteira desejável. A spec
[`explorador-aprende-com-mortes`](../specs/explorador-aprende-com-mortes.md)
adiciona `location_id` ao ledger de morte, resolve registros legados por nome e
exclui destinos fatais das viagens do agente. Sem saída segura ele observa em
vez de repetir uma viagem suicida; fuga de combate continua permitida.

Por fim, o processo Groq órfão deixou de ser apenas um achado: a spec
[`playtest-matrix-single-flight`](../specs/playtest-matrix-single-flight.md)
adiciona lock atômico por PID/host/token antes do preflight. Locks mortos ou
inválidos são recuperados, e somente o dono remove o arquivo. Gate combinado:
**1608 passed, 16 skipped, 14 deselected**. Como o perfil e a política do agente
mudaram, essa tentativa não é baseline; A1 reinicia integralmente pelo par 1.

## Dependência externa histórica

O ambiente não possui Ollama nem LM Studio. As outras rotas configuradas estavam
sem saldo/crédito válido na descoberta A0; Claude Sonnet disponível é caro
demais para o teto atual. Naquele momento era necessário um provider com
capacidade para milhares de invocações. O saldo DeepSeek foi posteriormente
recarregado; a dependência está resolvida para a retomada descrita acima.
