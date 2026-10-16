# PROMPT 12 — Persistência de fatos e propagação de informação

## Regras narrativas obrigatórias
Uma morte ocorre para testemunhas/engine; NPC distante não sabe automaticamente. Distinguir `world_truth`, `observed_by`, `told_to`, `believed_by`, `rumor`, `unknown` e `secret_visibility`, alinhados ao sistema de secrets atual; não construir ontologia paralela sem mapear ownership existente. Quem viu, ouviu, mentiu ou soube por terceiros importa. Memória e relação da Halveth devem manter identidade, pronomes e acontecimentos.

## Inspecionar
`state.py`, `services/npc_layers.py`, NPC secrets, event processor, world validators, knowledge visibility / memory provenance, projection pública da API, specs `149`, `171` e outras atuais. Delimitar que jogador não pode consultar visão interna do NPC por ser informação oculta: Codex apresenta inferências conhecidas ou percepções que o jogador pode saber, não dump de private state.

## Testes
Testemunha sabe da morte; cidade distante não; mensageiro leva notícia depois; mentira e boato não se tornam fato automaticamente; carga de save não teleporta conhecimento; spoiler não vaza em resposta/tooltip/arte; relação mantém cronologia.

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
