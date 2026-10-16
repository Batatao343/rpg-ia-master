# PROMPT 10 — Separar hot path de arquivamento assíncrono

## Contrato
O usuário espera resposta narrativa sem aguardar o arquivista terminar Codex/Bestiário/Crônica/projeções de menu. Entretanto **fatos canônicos** (NPC morto, relação, consumo, combate, presença, segredo descoberto) devem estar persistidos antes de concluir o turno. Atualizações derivadas podem acontecer depois.

## Auditagem de riscos
Verificar `GameState` canonical, ownership, persistence, transaction, outbox/job queue, idempotência, turn version, retries, concorrência no mesmo save, sessão trocada em meio a streaming, fallbacks e crashes. Propor estados `pending/completed/failed/stale`, cursor para projeções, versão monotônica e reconciliação em restart. Não perder eventos com reboot, não duplicar RAG writes, não introduzir corrida de memória na próxima ação.

## Escolhas arquiteturais
Deixar o agente comparar: (A) arquivista pós-resposta mas antes de permitir próximo turno, (B) job desacoplado com outbox persistente e leitura de state canônico, (C) processamento incremental. Decidir por invariantes e latência medida, nunca apenas thread fire-and-forget.

## Aceite
Fatos essenciais visíveis no próximo turno mesmo se arquivista falhar; eventual consistency em menus sinalizada; reexecução idempotente; save/load round-trip; duas mensagens rápidas; SSE drop; dois clientes; sem leak de segredos nem crash da fila.

### Contrato obrigatório deste prompt
- **Missão: investigar e escrever uma SPEC em `draft`; NÃO implementar código de produto nesta execução.** Não abrir PR de implementação, não mudar runtime, nem afirmar testes que não rodaram.
- Antes de atuar, ler `AGENTS.md`, `ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml`, `specs/TEMPLATE.md`, `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md` e `12_MODEL_EXECUTION_POLICY.md`. Fonte canônica é o source do HEAD, não este pacote.
- Verificar specs existentes e suas dependências; **NÃO reutilizar IDs 176–198** nem assumir que SPEC-199 continua livre. Obter próximo número não usado no HEAD, registrar em `specs/index.yaml` só quando apropriado. Não duplicar SPECS já `done`/`approved`.
- Toda a proposta deve distinguir **fato observado no código**, **decisão de produto fechada**, **hipótese técnica** e **recomendação**. Citar paths/símbolos reais auditados e lacunas.
- A spec deve conter escopo/não-escopo, contratos de dados e de UI, state ownership, degradação/fallback, etapas, risco de migração/saves, criterios de aceite observáveis, comandos de testes mínimos, evidência requerida, dependências e pontos de decisão genuínos.
- Respeitar integridade de eval: uma tarefa define/fixa novos avaliadores; outra otimiza produto. Não editar evaluator, expected ou dataset protegido na mesma tarefa de implementação; quando precisar de novos evals, registrar `EVAL_AUTHORING_REQUIRED` e um handoff separado.
- Sem provider real pago, campanhas longas ou experimentos 100/200 turnos por padrão. Ações com custo exigem autorização e teto explícitos. Não consultar Project Index sem hipótese cross-file específica e verificação no source.
- Material em `design-html/` é **referência de comportamento, não especificação mecânica**. Danos, cartas extras, retratos e falas fictícias nesses HTMLs são mock; as regras vêm do repo.
- Produzir, ao final, resumo de até uma página: diagnóstico, o que a spec cobre, dependências, riscos, como aceitar/rejeitar. Parar em `draft` e aguardar aprovação da spec; não pedir aprovação para cada microefeito.
