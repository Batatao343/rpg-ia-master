# PROMPT 01 — Diagnosticar frontend e planejar oportunidades de movimento

## Problema
UI atual é estática, densa, muita informação concorre com o chat, criação de personagem às vezes tem click/seleção imprecisa, cards e abas parecem objetos imóveis. Usuário não quer dez animações por controle; quer **resposta, clareza, vivacidade e atmosfera**.

## Investigação
Inspecione `web/src/`, styles, PlayScreen, StoryLog, CreateScreen, Hud, CardHand, SceneZones, tela de mapa, todas rotas de diálogo, screens de auth/loading/erro; inventarie motion e CSS já instalado. Teste visualmente desktop 1440x900 com fixtures. Consulte `referencias/ARSENAL_VISUAL.md`, `referencias/REFERENCIAS_LINKS.md` e os HTMLs do pacote.

## Saída desejada
Escrever **a primeira spec de diagnóstico/mapeamento**, antes de propor a segunda, de implementação. Incluir matriz completa com `tela | interação | problema atual | efeito/interação sugerido | propósito | prioridade | acessibilidade | performance | risco de confusão | prova de aceite`. Identificar também atrito removível sem animação e gaps de design system (tokens, feedback, focus, disabled, loading, error, revealed/secret).

## Critérios
- Priorizar hover/focus/press, indicação de seleção, confirmação implícita e saída visível antes de transições cosméticas.
- Prévia de todas as interações em HTML/CSS/JS pode ser objeto da futura spec; **não implementá-la nesta tarefa**.
- Evitar frameworks duplicados e UI kits genéricos que descaracterizem o RPG.
- Indicar oportunidades para arte contextual real e contrastar onde imagem não deve carregar informação mecânica.
- Não expor segredos por animação, tooltip, imagem, prefetch ou DOM.

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
