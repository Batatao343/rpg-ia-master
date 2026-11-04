# SPEC-383 - matriz de caracterizacao do turno (Etapa 0/1)

Base: main 52b7a994. Ramo -> e2e que o cobre (arquivo:teste). `turn-retry` = web/e2e/turn-retry.spec.ts (novo).

| Ramo de handleAction / retryTurnInner | Cobertura |
|---|---|
| operacao `completed` ao consultar (restaura estado) | turn-wait (retry sem novo envio, 25 s); pending-discard |
| `running` (throw "ainda sendo processada" / banner no retry) | turn-retry: operacao 'running' |
| `narrativeShown` nao definitivo (nao salvo, mesmo action_id) | turn-wait: 316 erro com narrative_shown |
| `narrativeShown` definitivo (4xx) | spec364-409 / spec363-board (erro com narracao) |
| 4xx com `shouldClearPending` | pending-discard: 409 definitivo; turn-retry: invalid_target |
| `invalid_target` (refaz mira) | turn-retry (descarta + libera); spec363-board (mira) |
| falha do stream -> POST de fallback | turn-retry: stream que cai; pending-discard |
| retry `unknown` (abandona SSE, mesmo action_id) | turn-wait: 316 stream pendurado; turn-retry: 'unknown' |
| descarte | pending-discard |
| (a) 401 no meio do turno | turn-retry + critical-journeys F15 |
| (b) logout / Nova jornada com turno em voo | turn-retry: botoes travados enquanto voa |
| (c) retry com `running` | turn-retry |
| (d) duplo envio por "Consultar / retomar" | turn-retry (consulta lenta, 2o clique com busy) |
