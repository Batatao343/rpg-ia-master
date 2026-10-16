# SPEC-177 — Estado de operação, recuperação e latência do turno

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P0  
> **Depende de:** SPEC-176 `done` · **Desbloqueia:** melhoria do fluxo durante combate e exploração.

## 1. Contexto & objetivo

O cliente já utiliza SSE e `action_id` idempotente, mas pode lançar erro quando uma operação está `running`; o jogador acaba repetindo ações ou não sabe se houve resposta. O backend é sequencial por decisão medida no experimento R29: tornar LLMs concorrentes sem prova pode piorar o p95. Prioridade: transparência do estado da operação, recuperação confiável e diagnóstico de gargalos antes de otimizar.

## 2. Requisitos

- **R1:** separar estados de UI `idle`, `queued`, `executing`, `narrating`, `committing`, `recovering`, `completed`, `failed`; renderizar etapa observável, sem progresso falso (% inventado).
- **R2:** operações `running` não aparecem como erro terminal. Reconexão consulta status com backoff limitado e sempre preserva **o mesmo** `operation_id` e payload hash; `completed` reconcilia via estado/histórico. Falhas definitivas liberam edição quando seguro.
- **R3:** um clique/Enter nunca duplica a ação em request/replay, inclusive quando SSE cai depois do commit. Resposta tardia de jogo A não contamina jogo B.
- **R4:** medir `input_to_ui_ack_ms`, `first_sse_event_ms`, `first_text_ms`, `commit_ms`, timeouts/fallbacks por provider/tier/nó com `action_id` correlacionado e sem dados sensíveis.
- **R5:** desenvolver *fast path* determinístico para comandos já estruturados quando o contrato permitir; nunca pular resolução/save canônico. Qualquer proposta de concorrência deve repetir R29 pareado com gate de p50, p95, custo e erros.
- **R6:** após 8–10s sem narrativa, exibir estado de execução e opção segura "Verificar ação"; nunca pedir para mandar o texto de novo como workaround.

## 3. Design técnico

Arquivos: `web/src/App.tsx`, `web/src/api.ts`, `web/src/pendingOperation.ts`, `web/src/components/PlayScreen.tsx`, `api.py`, `services/turn_execution.py`, camada de operações existente e telemetria. Implementar `OperationLifecycle` no cliente, derivado de eventos/status reais. O `POST` fallback só pode repetir uma operação com a mesma chave; não gerar `action_id` novo. Definir política de polling visível e cancelamento de espera **da UI**, sem prometer cancelar HTTP já iniciado.

## 4. Etapas (testes primeiro)

1. Falhar com fixtures de stream encerrado sem `state`, commit sem ack, status `running`, rede off/on, alternância de saves e double-click.
2. Implementar reducer de operação e reconciliação única; validar refresh e reload.
3. Incluir métricas do caminho crítico e relatório comparável ao baseline.
4. Rodar testes de API idempotência, `web/tests/pending.test.mjs`, Playwright F04/F05/F14/F15/F23, e smoke real curto de latência.

## 5. Aceite

- [ ] Contador de turnos e efeitos executados exatamente uma vez por `action_id` apesar de falhas de rede.
- [ ] `running` não é erro terminal e possui recuperação alcançável sem reenvio textual.
- [ ] p50/p95 de primeiro feedback e commit reportados por cenário/rota e comparados com baseline; qualquer piora de cauda/custo bloqueia rollout.
- [ ] Estado de processamento sempre visível e acessível; nenhuma tela presa ao final do turno.
- [ ] `uv run pytest`, `npm run build`, Node tests e Playwright relevantes verdes.

## 6. Smoke real e riscos

3–5 ações guiadas com degradação de SSE (simulação de transporte); provider real apenas se autorizado. Evitar fan-out SMART/CLASSIFY como "otimização óbvia": R29 anterior foi no-go. Não implementar retries indiscriminados.
