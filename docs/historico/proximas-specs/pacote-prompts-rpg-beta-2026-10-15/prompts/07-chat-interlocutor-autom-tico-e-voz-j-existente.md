# PROMPT 07 — Narrador e NPC com roteamento de fala natural

## Regra de produto
NÃO introduzir botão obrigatório 'falar com narrador / falar com NPC'. Inferir interlocutor pela semântica e pelo contexto; se jogador escreve 'Pergunto ao narrador o que Halveth sente', deve receber mediação de narrador, não fala da Halveth. Se fala diretamente com NPC presente, NPC responde. Perguntas de descrição de cena ao narrador não podem ser respondidas por NPC. Em caso de ambiguidade real: política definida, com esclarecimento apenas quando necessário.

## Inspecionar
`agents/router.py`, `agents/npc.py`, `agents/storyteller.py`, apresentação de speaker, `services/npc_layers.py`, identidade NPC/aliases (SPEC-149 e posteriores), STT já entregue em **SPEC-186/187** e seus testes. Não recriar Whisper nem autoenviar transcrição: transcript editável, envio explícito continua.

## Critérios
Cases de narrador, fala entre aspas, 'pergunto a Halveth', 'sobre Halveth', NPC ausente, ambiguidade pronominal, múltiplos NPCs, narrador revelando spoiler, voz transcrita e pausas; nunca criar identidade NPC divergente, pronomes inconsistentes ou role de speaker errado. Evals de semântica em tarefa independente da otimização.

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
