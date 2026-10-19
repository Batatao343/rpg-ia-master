# PROMPT 09 — Instrumentar latência percebida, custo e gargalos

## Pergunta
Por que uma ação até parecer começar a responder demora tanto, e como reduzir isso sem estragar jogo? Antes de propor paralelismo ou Jev, medir.

## Métricas com definição
`time_to_ack_ui`, `TTFT` (primeiro token **narrativo percebido**; separar SSE heartbeat/metadata), `time_to_first_meaningful_content`, `TTLT` (último token visível), duração total do turno, custos reais/estimados por provider/agente/tier, chamadas, fallback, queue, cache hit/miss, archivist/projeções, falha e retry. Distribuições p50/p95 por jornada e tamanho de entrada. Não comparar ambientes distintos sem ressalva.

## Investigar
`api.py` SSE e status, fluxo LangGraph, `agents/archivist.py`, `services/context_builder.py`, hook llm telemetry, evals R29 (fan-out anterior piorou p95); SPEC-177–180 Jev concluiu **NO_GO** de promoção, default off, e não deve ser tratado como solução já provada.

## Aceite
Spec determina baseline repetível offline para instrumentação e experimento pago **separado** somente com autorização/teto. Não aprovar nova chamada só para descobrir qual memória consultar se ela aumentar latência sem reduzir busca e sem demonstração A/B. Sem modificar evals congelados na mesma tarefa.

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
