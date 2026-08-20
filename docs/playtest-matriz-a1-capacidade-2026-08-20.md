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

## Dependência externa para retomar

O ambiente não possui Ollama nem LM Studio. As outras rotas configuradas estavam
sem saldo/crédito válido na descoberta A0; Claude Sonnet disponível é caro
demais para o teto atual. Para produzir A1 e B válidas é necessário um provider
com capacidade para milhares de invocações ou instalar/configurar um modelo
local compatível com structured output.
