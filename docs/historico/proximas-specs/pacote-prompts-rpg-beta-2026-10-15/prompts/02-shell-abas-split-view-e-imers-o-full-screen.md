# PROMPT 02 — Arquitetura de navegação desktop chat + contexto

## Decisões fechadas
**Todo enredo acontece no chat**. No desktop podem coexistir exatamente **duas superfícies principais**: chat + UM menu contextual; início por volta de 50/50, redimensionável. Cada superfície pode ocupar 100% da área útil. Nunca chat + combate + terceiro HUD. Navegação por abas semelhantes a browser; trocar Codex, Personagem, Combate, Bestiário, Mapa sem perder draft, posição do scroll, foco e ação pendente. Mobile depois: apenas UMA superfície por vez.

## Investigação
Inspecione App.tsx, PlayScreen, Hud, estilos, responsive shell, estado de stream/SSE, focus e overlays, testes F04/F08/F15/F16. Audite condições atuais em combate vs exploração, retorno por teclado, full-screen e reload.

## Spec proposta
Separação `ChatSurface` e `ContextSurface`, estado de workspace navegável e acessível, persistência local adequada por save, URL/history apenas se consistente com o app, regras de foco/scroll, layout resize/drag sem roubar cliques. Chat disponível mesmo em combate, porém não vira terceira janela; podem existir indicadores mínimos globais. Não duplicar a fonte de verdade do combate.

## Aceite
Desktop 1440x900: chat solo; 50/50; menu solo; alternar cinco abas; iniciar/encerrar combate; troca de jogo e pending SSE, sem estado vazando. Zero controle fora da tela; teclado e aria; respeitar movimento reduzido.

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
