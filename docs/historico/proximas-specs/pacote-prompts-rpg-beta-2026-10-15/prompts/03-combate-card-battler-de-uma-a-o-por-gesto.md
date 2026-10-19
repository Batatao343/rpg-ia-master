# PROMPT 03 — UX do combate por cartas, alvo e posição

## Produto
Chat dispara encontro e narra desfecho. Ao entrar, contexto vira combate (chat+combate 50/50 por default, batalha expansível). Combate deve ser **jogável sem tutorial a cada clique**: carta alvo dirigida = selecionar carta, clicar alvo válido e executar; carta sem alvo/ação básica imediata = um gesto; Esc cancela mira. Confirmar apenas ação excepcionalmente irreversível, explicada.

## UI
Definir layout das posições/zones, inimigos e aliados, quem está agindo, HP/ferimentos, Entropia, recursos, cartas preparadas, básico vs cartas, intenção inimiga observável, passivas e reações. Hover da carta informa custo/efeito/limites reais; seleção indica alvos válidos; não inventar números do HTML. Cartas não podem ficar ocultas atrás do log; evitar shakes que escondam decisões.

## Investigação de contrato
Inspecione `services/conflict_orchestrator.py`, `services/cards.py`, `data/cards`, `agents/combat.py`, `api.py` action_kind, `web/src/components/CardHand.tsx`, `ReactionPrompt.tsx`, `SceneZones.tsx`, `PlayScreen.tsx`, e tests relevantes. Apontar se ação básica 'Atacar' está restrita por equívoco no frontend, quais regras de alvo/custo/frequência e o que servidor retorna.

## Aceite
Carta sem alvo, com alvo, inválida, alvo morto, Entropia insuficiente, reação, passiva, combate encerrado, escape, keyboard, idempotência pós-timeout. Verificar usabilidade com tempo até ação correta e clicks falhos; feedback imediato mas alteração de HP somente quando servidor confirmou. Referência `design-html/rpg-combate-experiencia-v03.html`.

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
