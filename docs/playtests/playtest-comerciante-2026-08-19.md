# Playtest longo — perfil comerciante (2026-08-19)

## Escopo e aceite

Matriz offline formal `20260819-004210-869761`: cinco campanhas de 200 turnos,
seeds 9800–9804 e uma classe-base distinta por campanha. O manifesto terminou
`complete` e `data_complete=true`: 5/5 campanhas, 1.000/1.000 turnos, todos os
JSONL, summaries e saves válidos.

- 0 erros de turno, 0 violações `error`, 0 warnings e 0 erros de observabilidade;
- 18 compras + 18 vendas bem-sucedidas, 36 transações no total;
- 4–5 mercados e 3–4 regiões observadas por campanha;
- cinco restocks observados, um em cada campanha;
- as cinco famílias de ação apareceram em todas as campanhas;
- três campanhas exerceram morte e rollback sem replay de conflito ou loop fatal.

O run usa `MockLLM`; valida mecânica, persistência, observabilidade e política do
perfil, não qualidade de prosa, latência ou custo de providers reais.

## Achados e correções

As matrizes exploratórias anteriores encontraram quatro defeitos reproduzíveis:

1. a palavra `procurando` era classificada como cura por substring;
2. inventário com entradas não empilháveis duplicadas perdia quantidade no
   oráculo de conservação;
3. dano climático imediatamente antes de uma fuga podia preencher o último
   Crítico sem entrar no fluxo de Última Ação/morte;
4. após rollback, o comerciante memorizava o local seguro de retorno, em vez do
   destino da viagem que o matou, e podia repetir a rota fatal.

Todos ganharam regressões curtas. A reprodução adversarial original
(`Arcanista Cinzento`, seed 9803) foi repetida separadamente no run
`20260819-004140-489915`: 200/200, zero erro e zero violação.

## Pendência opt-in

O aceite offline está completo. A campanha `1×200 --real` permanece deliberadamente
pendente: a CLI exige `--max-cost` positivo aprovado, pois usa providers de LLM e
não deve consumir saldo por inferência do agente.
