# 05 — Sistema de evals do frontend

## Objetivo

Garantir que a interface não apenas “builda”, mas que o usuário consegue completar as jornadas principais em desktop/mobile, com estado correto, sem erros de console, requests inesperadas, overlays bloqueando controles ou navegação quebrada.

## Arquitetura de testes

Não usar E2E para tudo.

### Camada 1 — TypeScript/build

Já existe `npm run build`. Continuar blocking.

### Camada 2 — funções/client state

Expandir os atuais Node tests para:

- `http.ts`;
- `pendingOperation.ts`;
- parsing de SSE;
- session refresh;
- history pagination/cursors;
- seleção de game atual;
- reducers/helpers puros.

Pode continuar com `node:test` no primeiro momento.

### Camada 3 — component/integration React

Adicionar Vitest + React Testing Library para componentes que possuem estados complexos e não precisam de browser completo.

Prioridades:

- AuthScreen;
- CreateScreen;
- StoryLog;
- WorldMap;
- LevelUpModal;
- DeathModal;
- ArtworkDialog;
- GeneratedPortrait;
- ReactionPrompt.

Regra: testar pelo que usuário vê/interage, não internals do componente.

### Camada 4 — Playwright E2E

Adicionar `@playwright/test` em `web/` para jornadas do produto. Manter os browser tests Python atuais para integração infra/local enquanto a migração acontece; evitar duplicar cada caso em duas linguagens.

## Jornadas críticas v1

Cada jornada recebe um ID imutável.

### F01 — auth_signup_login

- abre app deslogado;
- cria conta fixture;
- entra;
- não acessa rotas protegidas antes da auth;
- logout retorna à tela correta.

### F02 — character_creation

- seleciona origem/classe/raça/região;
- cria personagem;
- chega ao jogo;
- ficha reflete escolhas.

### F03 — resume_save

- cria jogo;
- reload;
- lista save;
- reabre jogo correto;
- histórico permanece.

### F04 — action_stream

- envia ação;
- botão/input entram em estado esperado;
- SSE termina;
- ação aparece uma vez;
- resposta aparece;
- pending operation some;
- reload preserva histórico.

### F05 — idempotent_replay

- captura payload da ação;
- replay mesmo ID;
- estado/histórico não duplica;
- payload divergente com mesmo ID retorna 409.

### F06 — map_travel

- abre mapa;
- destino disponível é clicável;
- viagem conclui;
- location UI muda;
- back/reload não volta estado indevidamente.

### F07 — npc_interaction

- NPC em cena;
- conversa;
- mensagem exibida sob identidade correta;
- troca de aba/reload preserva contexto visual.

### F08 — combat_core

- entra em combate fixture;
- escolhe ação/carta;
- reação quando aplicável;
- round avança;
- combate encerra;
- controles de combate desaparecem/alteram corretamente.

### F09 — quest_progress

- quest ativa aparece;
- progresso muda após evento fixture;
- concluída não permanece como ativa incorretamente.

### F10 — death_recovery

- estado downed/death fixture;
- UI bloqueia ações incompatíveis;
- fluxo de recuperação/morte resolve;
- tela não fica presa.

### F11 — level_up

- abre modal;
- escolha é aplicável;
- não duplica em reload/replay.

### F12 — art_portrait

Reaproveitar fluxo atual:

- confirmação;
- pending;
- ready;
- signed URL;
- modal ampliar;
- Escape fecha;
- foco retorna;
- imagem `contain`.

### F13 — session_expiry

- 401 concorrentes;
- um refresh;
- request original refeito uma vez;
- refresh falho leva a auth sem loop.

### F14 — network_failure_recovery

- interromper SSE/rede fixture;
- pending operation persiste;
- reload consulta operação;
- usuário não duplica turno.

### F15 — game_switch_inflight

- ação em jogo A;
- usuário troca para B antes da resposta;
- resposta de A não contamina UI de B.

### F16 — responsive_navigation

Viewports mínimas:

```text
320x568
390x844
768x1024
1440x900
```

Verificar:

- zero horizontal overflow;
- HUD/top controls clicáveis;
- logout não sobrepõe controles (bug já conhecido);
- modal cabe no viewport;
- input de ação acessível;
- abas/mapa acessíveis.

## Oráculos frontend

### Hard gates

```text
critical_journey_pass_rate = 100%
uncaught_page_errors = 0
unexpected_console_errors = 0
unexpected_failed_requests = 0
horizontal_overflow_cases = 0
a11y_serious_critical = 0
```

### Visual regression

Usar screenshot somente em superfícies estáveis:

- auth;
- criação;
- HUD;
- modal;
- mapa fixture;
- portrait dialog;
- death/level-up states.

Não snapshotar texto gerado por LLM em tempo real.

Para estabilidade:

- Chromium pinado;
- Linux CI único como autoridade do snapshot;
- fontes e assets locais;
- animações desabilitadas;
- relógio/data mockados;
- viewport fixa;
- nenhuma rede externa;
- snapshots atualizados apenas em PR de visual explicitamente aprovado.

## Acessibilidade

Adicionar `@axe-core/playwright` ou equivalente.

Blocking para `critical` e `serious`; `moderate` inicialmente report-only.

Além de axe, testar teclado nos fluxos principais:

- Tab order;
- foco em modal;
- Escape;
- retorno de foco;
- botão de ação via teclado.

## Console e rede

Cada E2E deve instalar listeners globais:

- `pageerror` -> fail;
- `console.error` -> fail salvo allowlist documentada;
- response >= 500 inesperada -> fail;
- requestfailed inesperado -> fail.

Isso captura bugs que não alteram imediatamente o DOM.

## Performance frontend

Não transformar Lighthouse variável em gate estrito no primeiro ciclo.

Usar duas classes:

### determinísticas

- bundle size;
- número de chunks;
- assets acima de tamanho máximo;
- requests da jornada fixture;
- JS errors.

### observacionais

- LCP;
- INP;
- CLS;
- TTFB.

Registrar baseline em ambiente fixo e alertar por regressão ampla. Depois de coletar distribuição suficiente, promover limites estáveis.
