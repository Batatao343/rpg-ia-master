# PROMPT 00 — Orquestrar a nova onda sem implementar

## Objetivo
Você recebeu um pacote de **prompts de autoria de specs**, não specs aprovadas. Leia `README_COMECE_AQUI.md`, `DECISOES_PRODUTO.md`, `referencias/ARSENAL_VISUAL.md` e este arquivo. Audite o HEAD do GitHub/checkout: estado de 01–15, specs já existentes, riscos e dependências. Entregue matriz priorizada para **redigir specs uma por vez** e apenas lance o prompt seguinte quando suas dependências de diagnóstico forem satisfeitas.

## Política de precedência
1. Source canônico + documentos governados do repo.
2. Decisões de produto desta conversa neste pacote.
3. Referências e protótipos, sempre interpretados e adaptados.
4. Propostas novas do agente, explicitamente rotuladas.

## Entregáveis
- Mapa `prompt -> spec existente que cobre parte -> lacuna -> novo draft necessário? -> dependências -> tier mínimo`.
- Alertas de colisão de IDs e de documentação stale. Em 15/10/2026 o índice consultado já continha SPEC-198; **nenhum número neste pacote é SPEC-ID**.
- Roadmap em fases: beta desktop primeiro, latência segundo, consistência aprofundada terceiro; coleta de dados de beta transversal.
- Definição operacional de pronto para beta e quais protótipos são demonstrativos.
- **Não executar os prompts seguintes automaticamente nesta primeira chamada**; preparar plano de autoria e parar.

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
