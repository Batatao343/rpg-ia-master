# SPEC — Renovação de leases e recuperação segura de workers

> **Status:** `in-progress`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** auditoria-2026-09-operacoes-turno; integrar efeitos-transacionais
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

Heartbeats existem nos adapters mas não nos executores. JobWorker reserva até dez jobs e executa em série, permitindo expiração antes do início. Arte possui estado generating que requer reconciliação após crash.

## 2. Requisitos

- **R1** — Renovar lease do turno/job enquanto estiver ativo; perda de fencing impede publicação tardia. Renovação encerra em sucesso, erro e shutdown.
- **R2** — Reservar somente capacidade disponível (default serial: 1), ou renovar também todos os jobs já reservados. Evitar threads sem limite.
- **R3** — Falha de complete/fail após perder lease não derruba worker inteiro nem modifica resultado de novo dono.
- **R4** — Crash em arte após provider tem estado recuperável; não repetir geração paga cegamente quando sucesso é incerto. Retry distingue falha pré-provider e efeito externo possivelmente ocorrido.
- **R5** — Métricas de lease perdida/renovação/fila sem IDs de alta cardinalidade; shutdown para novas reservas e finaliza/abandona trabalho conforme política documentada.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

Novo services/lease_heartbeat.py: contextmanager keep_lease_alive(renew:Callable[[],None], *, interval_seconds:float) com stop Event e sinal de perda. JobWorker/run_worker e executor de turno consomem; interval < TTL/3, relógio injetável em testes. Estado durável de geração distingue generating/reconcile_required/ready sem prometer exactly-once de serviço externo. Port/adapters devem compartilhar contrato de fencing.

## 4. Plano passo a passo

1. tests/test_worker_lease_lifecycle.py usa relógio/eventos falsos: tarefa >TTL, lote aguardando, perda de token e complete falhando.
2. Implementar reserva por capacidade e heartbeat.
3. Crash-restart e dois workers em Postgres local com gerador falso; nenhuma chamada de imagem real.
4. Testar shutdown e reconciliação.

## 5. Critérios de aceite

- [ ] R1–R5 verdes em testes e integração local.
- [ ] Não existem threads de heartbeat órfãs.
- [ ] Zero geração automática repetida diante de resultado externo incerto.

## 6. Smoke test com LLM real / integração aplicável

Gate real de infraestrutura local, não LLM. Usar latência simulada/eventos, sem sleeps longos na suíte offline.

## 7. Riscos & compatibilidade

Não trocar fila nem acrescentar serviço pago. Garantia de idempotência do provider precisa verificação específica antes de uso; até lá, reconciliação explícita.

## Execução — 26/09 (prevalece sobre as pendências históricas)

Heartbeat no escopo de operação e job, reserva serial de um job, publicação de arte/crônica com token vigente e parada sem novas reservas. Dois workers reais locais: execução >2 TTL sem roubo e token antigo rejeitado. Arte com resultado incerto fica failed/external_result_uncertain (persistido) e é apresentada como reconcile_required; geração órfã sem lease ativa também exige conferência. Não foi criada coluna/status SQL novo: esta projeção pública é desvio explícito do design inicial. Regressão prova uma chamada ao gerador falso mesmo após retry. Falta teste de kill/restart do processo e procedimento operacional de reconciliação; nunca retornar a pending cegamente.
