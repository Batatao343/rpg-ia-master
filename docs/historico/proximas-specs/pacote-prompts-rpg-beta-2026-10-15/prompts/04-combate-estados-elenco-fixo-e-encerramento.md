# PROMPT 04 — Contratos narrador↔combate e integridade da batalha

## Problemas observados no playtest
Transição de chat para combate esquisita; bandidos confundidos com corvos e somem do encontro; estratégia vira spam, inimigos às vezes não causam dano; encerramento não volta ao chat; XP aparece no texto do narrador; ausência de desfecho.

## Requisitos para propor
Manifesto determinístico e canônico do encontro (identidade, espécie, facção, presença, zones, status, rodada), sem reclassificação de combatentes por LLM a cada turno; entrada e saída de state machine, eventos de resultado, XP apenas em UI mecânica, desfecho narrativo e retorno à exploração. Não alterar regras existentes sem provar bug. Combate não pode depender da atualização assíncrona de Codex.

## Inspeção
`agents/combat.py`, `services/conflict_scene.py`, `services/conflict_summary.py`, `services/conflict_orchestrator.py`, projection `api.py`/`types.ts`, saves/round-trip, dados de bestiário e fixtures.

## Aceite
Fluxo completo ameaça→encontro confirmado→2 rodadas→reação/dano→derrota/vitória→evento XP→narração de fim→exploração, salvar/recarregar entre fases, estado terminal não preso e elenco sem aves metamorfoseando em bandidos. Testes que verificam causalidade, não strings do mock.

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
