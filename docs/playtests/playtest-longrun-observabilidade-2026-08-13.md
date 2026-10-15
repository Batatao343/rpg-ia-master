# Playtest longo com observabilidade — 2026-08-13

## Escopo

Foram executados dois runs com o perfil `normal`, seed `20260813`:

- **LLM real:** `20260813-002535-998525`, solicitado 200 turnos; 80 turnos úteis
  + linha 81 de timeout, `mock=false`.
- **Matriz mecânica completa:** `20260813-011902-138686`, 200/200 turnos,
  MockLLM, invariantes ligados.

Uma segunda tentativa real, seed `20260814`, produziu mais 34 turnos úteis +
linha 35 de timeout (`20260813-012402-094797`) antes de outra suspensão longa.
Somadas, as duas amostras reais cobrem **114 ações úteis**, 336 tentativas de
rede, 331 sucessos e US$ 0,097784. Nenhuma chegou a 200 por limite ambiental.

O run real foi interrompido corretamente pelo watchdog após uma suspensão longa
do notebook: a tentativa DeepSeek ficou 2.144 s pendente e o deadline absoluto
rejeitou o resultado tardio (`observado 2.166 s`, teto 120 s). Portanto ele é
válido para qualidade/latência nos 80 turnos anteriores, mas não equivale a uma
campanha real completa de 200 turnos.

## Resultado real (80 turnos úteis)

- zero violações de estado; quatro rotas cobertas;
- 227 tentativas de rede, 225 sucessos (99,1%), dois fallbacks; US$ 0,06384;
- p50 9,1 s e p95 35,3 s; combate foi o nó mais caro (p95 34,6 s);
- 33,3% dos turnos em combate, cinco conflitos iniciados e encerrados;
- uma morte, um rollback: 80 ações de sessão, turno canônico 72, época 1;
- uma quest criada e progredida, mas zero conclusão/recompensa;
- 27 memórias finais, todas `inference/speculative`; autoridade 0%, 16 antigas;
- nenhuma instrução privada/meta, terceira pessoa ou narrativa exatamente repetida.

### Segunda amostra real (34 turnos úteis)

- zero mortes/violações, quatro rotas, cinco locais e nível 2;
- p50 10,4 s/p95 29,0 s; novamente combate foi o nó mais caro (p95 27,3 s);
- 42,9% combate; uma quest criada, ainda sem progresso/conclusão;
- memória final: 10/10 inferências especulativas, autoridade 0%, seis antigas;
- 109 tentativas, 106 sucessos e US$ 0,033944.

A repetição confirma que autoridade zero da memória e causa única
`player_provoked` não dependem da primeira seed. Também mostra recuperação
saudável: o personagem chegou a 1/18 e voltou a 17/18 sem morrer; a espiral de
mortes do mock está ligada ao checkpoint em combate, não à letalidade isolada.

## Resultado mecânico (200 turnos)

- 200/200, zero erros e zero violações `error`;
- warning: 68% dos turnos em combate;
- 27 mortes/restores; 200 ações, turno canônico 110, época 27;
- oito quests criadas, progredidas, concluídas e recompensadas (160 ouro);
- nível 4, ouro 389, seis locais;
- nove conflitos iniciados, mas 33 encerramentos contabilizados;
- memória final 100% canônica no mock, em contraste direto com o run real.

## Achados priorizados

### P0 — checkpoint pode aprisionar o jogador em um combate letal

`should_checkpoint` não exclui `combat.active`. O run de 200 turnos restaurou
repetidamente o mesmo conflito: o par checkpoint 70 → morte 73 ocorreu dez
vezes. Isso gerou 27 mortes, 68% de combate e apenas 110 turnos canônicos para
200 ações. Checkpoint deve ser sempre fora de combate; slots legados ativos
precisam ser saneados ou substituídos pelo último snapshot pré-conflito.

### P1 — origem do combate é herdada da cena anterior

Todos os inícios foram classificados como `player_provoked`. No real, dois dos
cinco começaram ao descansar; no mock há viagens e ações explícitas de evitar
conflito com a mesma causa. `combat_origin.materialize` preserva a origem antiga
de `combat` mesmo quando uma cena nova começa. A causa atual deve vencer no
início da cena; histórico anterior deve viver em campo separado ou ser limpo.

### P1 — memória real não consolida autoridade

O run real escreveu ao RAG 27 inferências, dois relatos de NPC e um evento
canônico, mas o ledger final contém somente 27 inferências especulativas, sem
promoção. É necessário auditar a ponte RAG → `memory_facts`, preservar relatos e
eventos no ledger e definir poda/expiração para especulações antigas. Repetição
especulativa não deve promover fatos.

### P1 — quest progride, mas não fecha no LLM real

O pedido converteu em quest e a chegada ao local marcou progresso. Mesmo após
seis ações explícitas de retomada/investigação, a missão permaneceu ativa. O mock
fecha 8/8, mostrando que ele é otimista demais. A conclusão precisa de critérios
verificáveis em Python ou de etapas estruturadas que deem evidência concreta ao
validador, sem depender só de `quest_completed` espontâneo da LLM.

### P2 — telemetria de morte mistura os três relógios

O summary chama `turn=68` o índice de ação do harness, enquanto o histórico de
continuidade registra `death_turn=69` canônico. `downed_count` fica zero porque
é calculado sobre o `event_log` restaurado. O relatório deve expor
`session_action`, `canonical_turn` e `timeline_epoch` em cada morte e derivar
contagens do ledger não restaurável.

### P2 — encerramentos de combate inflam sob rollback

No mock: nove inícios e 33 encerramentos. Cada repetição restaurada é contada
como novo fim, então a métrica não representa conflitos únicos. Agregar por
`conflict_id`/época e distinguir `ended`, `rolled_back` e `replayed`.

### P2 — primeiro turno de combate concentra latência

Os três inícios reais mais lentos levaram 35–37 s. O nó fez múltiplos parses
CLASSIFY e chamadas FAST; uma narração chegou a 23,6 s. Priorizar cache/reuso da
preparação e eliminar classificações redundantes, guiado pela nova latência por
nó. Storyteller p95 foi 10,2 s; router 2,0 s; loot 2,9 s.

### P2 — artefato abortado é marcado como estruturalmente inválido

A linha de timeout usa rota vazia, latência total e nenhum timing por nó, embora
os nós executados já estejam presentes. A validação também reporta a ausência
dos 119 turnos como três erros de JSONL além do status abortado. Runs abortados
devem aceitar prefixo válido, usar rota `timeout`/última rota observada e manter
timings parciais.

## O que funcionou

- O watchdog recusou corretamente resultado tardio após suspensão.
- A separação dos três relógios tornou o rollback imediatamente auditável.
- Latência por nó localizou o custo no combate, em vez de culpar o turno inteiro.
- O objetivo privado não vazou e a voz permaneceu em segunda pessoa.
- O ciclo completo de quest/recompensa é idempotente no teste mecânico.
- Origem, autoridade de memória e stale speculation tornaram falhas antes
  invisíveis mensuráveis.

## Próximas specs recomendadas

1. `checkpoint-seguro-fora-combate` (P0);
2. `origem-combate-por-cena` (P1);
3. `memoria-autoridade-ledger-real` (P1);
4. `quest-etapas-verificaveis` (P1);
5. `telemetria-rollback-tres-relogios` (P2);
6. `latencia-start-combate` e `artefato-run-abortado` (P2).
