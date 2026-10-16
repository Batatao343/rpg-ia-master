# PROMPT 15 — Fechar uma beta desktop instrumentalizada e jogável

## Objetivo
Criar draft da spec de release gate que integra apenas features essenciais aprovadas, sem refazer a cadeia de publicação e cobrança (SPEC-191 a 198 têm aprovações e dependências próprias). Beta desktop jogável não depende de publicação Android.

## Jornada vertical de aceite
Criar personagem (raça/classe selecionáveis) → chat descreve cenário → jogador fala com narrador sobre NPC → conversa direta com NPC → ameaça no chat → transição → cartas/ações sem confirmações repetidas → dano e reação → vitória/derrota → retorno narrativo → consulta Codex/Personagem/Combate/Bestiário/Mapa → salvar/reabrir, com imagens geradas existentes e placeholders honestos para ausentes.

## Guardrails
Build, Playwright jornadas F01–F16 aplicáveis, zero erro de console/req inesperada, zero turno duplicado, nenhum segredo vazado, métricas de latência coletáveis; relatório de sessão exportável sob demanda. Não exigir acabar aprofundamento de memória/Jev antes de convidar testers. Registrar known-issues e critérios de bloqueio vs aceitável na beta.

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
