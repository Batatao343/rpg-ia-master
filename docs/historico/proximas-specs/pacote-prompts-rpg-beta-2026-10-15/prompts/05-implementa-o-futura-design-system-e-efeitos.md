# PROMPT 05 — Redigir spec de implementação dos efeitos mapeados

## Pré-condição
Executar **depois** de aprovar a spec originada do PROMPT 01 (matriz de efeitos) e conciliar arquitetura dos prompts 02/03. Não implementar nesta tarefa; produzir spec de execução com iterações verticais.

## Padrão de movimento
Feedback de input -> seleção/estado preparado -> execução/consequência -> atualização de UI -> retorno. Animações curtas, interrompíveis, sem bloquear input/SSE, com reduced-motion; foco e hitbox independem de hover. Reutilizar `motion` existente antes de aceitar GSAP, shaders, Canvas/WebGL; incluir orçamento de bundle e CPU/GPU para cada biblioteca adicional.

## Cobertura candidata
Criação de personagem (hover e confirmação de raça/classe), microinteração cards, transição split↔full, aba selecionada, revelação Codex/Bestiário, movimento no mapa, carregamento do chat, NPC portrait, entrada/saída do encontro, dano/passiva/reação e estados de erro/retry. Não fazer tudo simultaneamente: priorizar primeiro fluxo de beta.

## Especificação de efeito por efeito
Cada efeito deve ter `trigger, start/end states, duração/easing propostos, fallback estático, feedback sonoro opcional não obrigatório, custo estimado, teste e razão de existir`. Não copiar bibliotecas/efeitos externos sem checar licença e adequação, não baixar arte de jogos como assets do RPG.

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
