# SPEC — Latência do turno: experimento concorrente e decisão de rollout

> **Status:** `done` — experimento concluído com **no-go** para promoção do fan-out LLM
> **Criada:** 2026-08-27 · **Atualizada:** 2026-09-17
> **Depende de:** observabilidade-latencia-nos, streaming-turno-sse
> **Evidência:** [gate R28/R29](../docs/latencia-turno-r29-2026-08-28.md)

## 1. Resultado e escopo efetivamente entregue

O benchmark controlado mostrou overlap, mas o DeepSeek real piorou sob fan-out.
`RPG_TURN_EXECUTION=sequential` é o default de produção; `concurrent` permanece
experimental. O status `done` encerra a avaliação e seu rollback previsto,
**não certifica ganho de latência real nem entrega toda a arquitetura inicialmente
proposta**. A revisão de 17/09 corrige essa ambiguidade documental.

O arquivista continua inline: resumo, fatos e memória são processados antes da
resposta. Não há novo worker de derivação, cursor eventual, outbox ou migração
de memória introduzidos por esta spec.

## 2. Contratos mantidos

1. `turn_prepare` incrementa turno/continuidade uma vez. O DTO imutável contém
   game_id, turn, timeline_epoch e in_active_combat. Controle de versão do save
   continua sendo responsabilidade do coordenador de persistência existente.
2. Plano e rota escrevem canais disjuntos; o dispatch aguarda ambos na topologia
   experimental. Replan SMART é diferido durante combate.
3. Aquisição de contexto mantém ordem lore/sessão/NPC e isola falha de fonte.
   Um vetor pode ser compartilhado quando os perfis dos índices são compatíveis.
   Metadata de modelo incompatível ou dimensão explicitamente divergente
   recusa o compartilhamento. Índices antigos sem dimensão declarada mantêm a
   validação do adapter FAISS.
4. Leituras e embeddings têm limites por processo; limite 1 serializa a operação.
   Esses limites não substituem controle distribuído de capacidade.
5. WorldPulse separa proposta de aplicação Python. Mecânica e aplicação de
   eventos permanecem sequenciais.
6. `RoutedLLM.ainvoke` e a fachada async de contexto delegam ao caminho síncrono
   via `asyncio.to_thread`. Assim reutilizam os mesmos guards e fallback.
   Cancelar a coroutine **não interrompe** a request HTTP já iniciada na thread;
   ela termina pelo timeout do provider. Não se afirma suporte async nativo.
7. Eventos, recompensas, memória e recibo continuam no fechamento inline.
   Os contratos existentes de POST/SSE/CLI e de idempotência continuam aplicáveis.

## 3. Arquivos e verificação local

- `services/turn_pipeline.py`: preparação, adapters disjuntos e métricas de
  intervalos (critical_path_ms, work_ms, overlap_ms).
- `services/context_sources.py`: vetor compartilhado, limites e join ordenado.
- `rag.py`, contratos/adapters de memória: consulta por vetor e APIs textuais.
- `agents/world_simulator.py`: proposta pura e aplicação.
- `llm_setup.py`: fachada async sobre a máquina síncrona e limiters.
- `scripts/benchmark_turn_pipeline.py` e `benchmark_turn_pipeline_real.py`:
  benchmarks controlado e real.
- `tests/test_turn_pipeline_concurrency.py`,
  `test_context_sources_concurrency.py`, `test_turn_latency_contract.py`:
  preparação única, barriers, ordem, isolamento de falha, limites e paridade
  nas fixtures disponíveis.

A matriz completa de async nativo/cancelamento proposta inicialmente não foi
entregue. Também não foram entregues DTOs adicionais de branch com hash/versão,
spans de enqueue de derivação ou CAS de resumo eventual. Essas partes foram
retiradas do escopo efetivo após o no-go; não constituem capacidade certificada.

## 4. Gates e decisão

- **R28 controlado:** 12 repetições, serial 140,97 ms e concorrente 81,55 ms;
  redução de 42,1%, acima do limiar de 30%; zero request de provider.
- **R29 real:** 18 turnos pareados, três repetições de replan/viagem/arquivo por
  modo; 51 requests, US$ 0,014280. p95 serial 21.863,38 ms e concorrente
  40.068,19 ms. Concorrente fez 26 requests contra 25 e houve duas falhas de
  conexão. Gate reprovado.
- **Rollout:** manter sequential. Qualquer promoção futura exige novo R29,
  capacidade real comprovada, nenhuma regressão e revisão dos contratos
  adicionais; o benchmark controlado sozinho não permite promoção.

## 5. Critérios de encerramento do experimento

- [x] Benchmark controlado executado e resultados registrados.
- [x] Benchmark real executado, inclusive falhas e aumento de requests.
- [x] Rollback para sequential aplicado como consequência do gate.
- [x] Memória mantida inline e limitações async documentadas.
- [x] Testes locais de preparação/contexto/limites presentes.
- [x] Infra local validada em 28/08: 13/13, conforme relatório.
- [x] Relatório versionado com decisão explícita de não promover.

## 6. Limitações

A concorrência experimental não é recomendação de produção. A comparação real
é uma amostra limitada: aponta contenção nessa configuração, sem demonstrar que
todo provider se comportaria igual. Ganho entre campanhas, streaming percebido
e redução do tempo de um turno são métricas diferentes. A certificação cloud
continua em sua spec própria.
