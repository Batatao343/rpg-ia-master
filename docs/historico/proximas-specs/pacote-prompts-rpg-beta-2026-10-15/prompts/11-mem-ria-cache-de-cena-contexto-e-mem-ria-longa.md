# PROMPT 11 — Investigar hierarquia de memória baseada em relevância

## Visão
Metáfora do usuário: cache/RAM/HD. Não adotar três bancos distintos por metáfora. Avaliar uma **projeção enxuta da cena ativa**, contexto de NPC/assunto relevante e arquivo histórico consultado sob demanda. A cena deve saber local, atores canônicos, memória relevante do interlocutor, relação, objetivo, ameaças, eventos recentes e segredos acessíveis, sem reconstruir tudo a cada turno.

## Estratégia de comparação
Baselines: builder/RAG atual vs snapshot de cena vs hibrido. Inspecionar custos de manutenção, invalidação de cache ao mudar localização/interlocutor/quest, mudanças de save e revisão de turnos. Estados essenciais duráveis; 'cache' é aceleração e nunca fonte exclusiva de verdade. Orçamento explícito de tokens e recuperação fallback se cache desatualizado.

## Gate
Sem ganho medido de TTFT/TTLT/custo mantendo zero regressão crítica de identidade/segredo/causalidade, não promover; fixtures para cenários de longa duração são curtas/determinísticas na primeira rodada. JEV como classificador de necessidade de memória é **experimento posterior** com avaliação separada, não adição automática à rota.

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
