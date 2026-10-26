# SPEC-323 — Front: livro, não chat (marginália, HUD, copy, criação, mapa, sigilo)

> **Status:** `done` (aprovada 25/10; revisão Sol; pousada 26/10; conferência visual no staging `7520848`/`15f14f8` em 390×844 e 1440×900 — 6 de 7 itens corrigidos no round 2 e o 7º (rótulo de oferta de NPC) corrigido em `15f14f8`)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-26
> **Depende de:** SPEC-322 (ícones e tokens), SPEC-321 (casca mobile e rótulos "Crônica")
> **Desbloqueia:** release do beta (SPEC-197) e a loja (SPEC-198), pelo item do medalhão

---

## 1. Contexto & Objetivo

A narração é encenada como um livro: capitular, fleurons ❧ e a decisão de não carimbar "Narrador" (`web/src/components/StoryLog.tsx:102-105`). Mas o resto contradiz isso.

**Ação do jogador como bolha de chat.** A fala do jogador é uma bolha de chat alinhada à direita, em caixa (`.msg--player` em `web/src/styles.css:440-448`: `align-self: flex-end; max-width: 85%`).

**Listas do HUD.** Toda lista do HUD usa o mesmo card em caixa: mesmo fundo `--bg-deep`, borda `--line-soft` e `--r-sm`. Isso vale para `.inv li` (`:541`) e para `.abilities li`, `.person`, `.chron`, `.faction`, `.quest`, `.codex-entry` e `.dossier-row`. Não há hierarquia por tipo de conteúdo.

**Copy de dev/IA visível ao jogador.**
- `web/src/components/CreateScreen.tsx:164`: "Dark Fantasy · Narração por IA"; `:165`: "Forje sua lenda".
- `:180`: "Entrar direto na arena · zero LLM".
- "Custo técnico registrado: US$ …" (`StoryLog.tsx:96`).
- O padrão "— ainda." nos estados vazios (`web/src/components/Hud.tsx:234,297,359`; `web/src/components/QuestsTab.tsx:56`).

**Hierarquia invertida na criação.** O atalho "Simular combate", em vermelho (`CreateScreen.tsx:178-181`; estilo em `styles.css:227-240`), vem antes do wizard, que é o caminho principal.

**Mapa de fallback.**
- Rótulos de 0,6rem em Cinzel `--faint` (`styles.css:591`).
- Nós de 9 px.
- Nós de névoa ainda nomeados.
- `aria-label` sem perigo nem missão (`web/src/components/WorldMap.tsx:120-121`).
- Não existe arte de mapa, embora haja 90 artes de local em `web/public/art/v1/location/`.

**Medalhão.** O medalhão é declaradamente "alusão ao medalhão de lobo" com "focinho de lobo estilizado" (`web/src/components/ornaments.tsx:46,61`), o que traz risco de trade dress com a CD Projekt na loja.

**Nome do produto inconsistente.** `<title>` diz "Crônicas — RPG de Texto" (`web/index.html:6`), e a tela de auth diz "Crônicas de Valoria" (`web/src/components/AuthScreen.tsx:111`).

**Sem sugestões fora do combate.** Fora do combate o jogador só tem o campo vazio, embora `data.npcs`, o beat atual da quest e os interiores já existam no estado.

**Objetivo:** fechar a metáfora de livro, dar a cada lista do HUD uma forma própria, limpar a copy, endireitar a criação, deixar o mapa legível e dar ao jogo identidade própria.

## 2. Requisitos

- **R1 — ação do jogador como marginália.** A ação do jogador sai alinhada à esquerda na coluna de leitura: Garamond itálico `--muted`, com um marcador "›" em bronze (ou o sigilo da classe, da SPEC-322), sem caixa, sem borda e sem `align-self: flex-end`. Continua distinguível da narração por estilo, não por posição. O nome acessível do bloco continua indicando "Você".
- **R2 — listas do HUD diferenciadas.**
  - **Inventário:** grade de slots com ícone de item (SPEC-322) e marcador de equipado.
  - **Pessoas:** nome, glifo de atitude e memória citada, separados por filetes finos, sem caixa.
  - **Missões:** título + prazo como etiqueta (pílula de status permitida pela SPEC-322 R7); urgente em `--danger-text`.
  - **Boatos ("Ouvi dizer"):** estilo de mural (itálico, selo "boato").
  - Crônica e codex podem continuar em card.
- **R3 — copy sem jargão.**
  - "zero LLM" sai.
  - "Simular combate" vira "Arena de treino".
  - O kicker da criação segue D1.
  - "Custo técnico registrado: US$" passa a aparecer só com `?debug=1`. Para o jogador fica só o débito em Estilhas.
  - "Forje sua lenda" vira uma frase ancorada em Valoria (ver D4).
- **R4 — estados vazios ensinam.** Cada estado vazio diz como preencher o painel ("Converse com alguém numa taverna para ouvir boatos.", "Aceite um pedido de um morador para abrir uma missão."), sem o padrão "— ainda.".
- **R5 — criação.**
  - "Arena de treino" vira link ghost **abaixo** das ações do wizard.
  - O wizard ganha a arte da classe em destaque: no desktop, layout dividido com a arte à esquerda e o detalhe à direita (≥ 768 px); abaixo disso, uma coluna.
- **R6 — legibilidade do mapa.**
  - Rótulos ≥ 0,8rem em Garamond itálico com halo.
  - Nós de névoa mostram "?" sem nome.
  - Só são rotulados os nós visitados, adjacentes ou de missão.
  - `aria-label` dos nós do fallback igual ao do `MapTab` (perigo, missão, estado).
  - Um ícone por estado (família da SPEC-322), sem empilhar glifos.
- **R7 — mapa pintado (opcional, D5).** Se aprovado: uma imagem-base de Valoria com coordenadas calibradas para os 35 nós de `data/world_map.json`, estradas desenhadas a tinta e estradas bloqueadas em traço quebrado vermelho, mais pan e zoom no celular (`transform` num wrapper).
- **R8 — sigilo próprio (D2).** O medalhão de lobo (`ornaments.tsx:46-74`) é substituído por um sigilo de Valoria: Abismo e/ou Cinco Sinos. O comentário que menciona o lobo sai.
- **R9 — nome do produto (D3).** Um só nome em `<title>`, na meta description, na tela de auth, no manifest/PWA e no `capacitor.config.ts` `appName`.
- **R10 — sugestões de contexto.**
  - Fora do combate, uma linha rolável de 3–4 sugestões acima do compositor: "Falar com {NPC em cena}", "Seguir objetivo: {beat atual}", "Descansar", mais o chip "Locais daqui" (SPEC-321).
  - Um toque **preenche** o input e não envia.
  - As sugestões vêm só do estado atual (`data.npcs` com `in_scene`, `campaign_plan.beats[current_step]`), sem chamada de LLM.

### Fora de escopo

- Tokens, ícones e tipografia em si (SPEC-322). Headings e atalhos (SPEC-324).
- Texto legal formal sobre IA (SPEC-222). Aqui só a copy de produto.
- Gerar a arte do mapa: se D5 for "sim", a geração da arte é tarefa separada (pipeline em `docs/guias/ARTE_VISUAL.md`), e esta spec só integra.

## 3. Design técnico

**Arquivos novos**
- `web/src/components/ContextSuggestions.tsx`: deriva as sugestões de `GameStateView` (função pura `suggestionsFor(data): Suggestion[]` exportada para teste).
- `web/src/components/Sigil.tsx`: o sigilo novo em SVG (substitui o `Medallion` de `ornaments.tsx`).
- Se D5 for sim: `web/public/art/v1/map/valoria.webp` + `web/src/components/mapCalibration.ts` (coordenadas por id de nó de `data/world_map.json`).

**Arquivos alterados**
- `web/src/styles.css`: `.msg--player` (`:440-448`); listas do HUD (`:541`, `.person`, `.quest`, `.faction`, `.heard-news__item`); `.worldmap__label` (`:591`); remoção do vermelho saturado do atalho da arena (`:227-240`).
- `web/src/components/StoryLog.tsx:95-99`: custo técnico só com `?debug=1`.
- `web/src/components/Hud.tsx`, `web/src/components/QuestsTab.tsx`, `web/src/components/CharacterTab.tsx`, `web/src/components/ContextSurface.tsx`: marcação nova das listas e estados vazios.
- `web/src/components/CreateScreen.tsx:160-181`: ordem, layout e copy.
- `web/src/components/WorldMap.tsx` e `web/src/components/MapTab.tsx`: rótulos, névoa e `aria-label`.
- `web/src/components/ornaments.tsx:46-74`: `Medallion` → `Sigil` (e quem o usa: `AuthScreen`, `CreateScreen`).
- `web/index.html:6-7`, `web/src/components/AuthScreen.tsx:111`, `web/capacitor.config.ts`: nome.
- `web/src/workspace/ChatSurface.tsx`: monta `ContextSuggestions`.

## 4. Plano passo a passo

### Etapa 1 — marginália do jogador
1. **Testes:** e2e (`web/e2e/visual-surfaces.spec.ts`, estender): a entrada do jogador tem `align-self` computado diferente de `flex-end`, borda 0 e alinhamento à esquerda com a narração (mesmo `left` ± 4 px).
2. **Implementação:** CSS e o rótulo acessível.

### Etapa 2 — copy e estados vazios
1. **Testes:**
   - `web/tests/copy.test.mjs` (novo): nenhum `LLM`, `zero LLM` ou `Custo técnico` em strings de `web/src` fora de `debug`/`legal`;
   - nenhum estado vazio terminando em "— ainda.".
2. **Implementação:** copy em `CreateScreen`, `StoryLog`, `Hud`, `QuestsTab`.

### Etapa 3 — criação
1. **Testes:** e2e (`critical-journeys` / `vertical-journey`, adaptar seletor): "Arena de treino" aparece depois do botão principal do wizard na ordem do DOM; a 1440×900 a arte da classe fica ao lado do detalhe.
2. **Implementação:** `CreateScreen`.

### Etapa 4 — listas do HUD
1. **Testes:**
   - e2e: inventário renderiza `role="grid"` ou lista de slots com o item equipado marcado (`aria-current` ou rótulo);
   - pessoas sem borda de caixa; prazo urgente com classe `--urgent` e contraste ≥ 4,5 (reaproveitar `web/scripts/contrast.mjs` da SPEC-322).
2. **Implementação:** componentes + CSS.

### Etapa 5 — mapa
1. **Testes:**
   - e2e `web/e2e/map-tab.spec.ts` (estender): nós de névoa sem nome visível; `aria-label` de nó de fallback contém o perigo quando houver;
   - `font-size` computado do rótulo ≥ 13,6 px.
2. **Implementação:** `WorldMap`/`MapTab`. Se D5 for sim, sub-etapa 5b com a imagem-base e pan/zoom (e2e: o pinch e o arrastar mudam o `transform`).

### Etapa 6 — sigilo e nome
1. **Testes:** `web/tests/build.test.mjs`: `<title>` e o `appName` do Capacitor iguais à constante `PRODUCT_NAME`; grep de "lobo" em `web/src` com zero ocorrências.
2. **Implementação:** `Sigil.tsx`, trocas.

### Etapa 7 — sugestões de contexto
1. **Testes:**
   - `web/tests/contextSuggestions.test.mjs`: `suggestionsFor` com NPC em cena devolve "Falar com X"; sem NPC não devolve; com beat ativo devolve "Seguir objetivo"; no máximo 4 itens.
   - e2e: um toque preenche o input e **não** dispara POST de turno.
2. **Implementação:** `ContextSuggestions` + `ChatSurface`.

**Verificação final:**
- `cd web && npm test && npm run lint && npm run test:e2e -- visual-surfaces map-tab critical-journeys vertical-journey dossiers deck-character`.
- Screenshots 390×844 e 1440×900, antes e depois.

## 5. Critérios de aceite

- [ ] Ação do jogador como marginália à esquerda, sem caixa (e2e).
- [ ] Inventário, pessoas, missões e boatos com formas distintas; prazo urgente legível (≥ 4,5:1).
- [ ] Sem "LLM"/"zero LLM"/custo em US$ na UI do jogador; o kicker segue D1; estados vazios ensinam.
- [ ] "Arena de treino" como link secundário abaixo do wizard; arte da classe em destaque no desktop.
- [ ] Mapa: rótulos ≥ 0,8rem, névoa sem nome, `aria-label` completo; mapa pintado só se D5 for sim.
- [ ] Medalhão de lobo substituído pelo sigilo de Valoria; zero "lobo" em `web/src`.
- [ ] Um único nome de produto em title, auth e Capacitor.
- [ ] Sugestões de contexto que preenchem sem enviar (unit + e2e).
- [ ] `npm test` e o e2e do escopo verdes; `uv run pytest` verde.

## 6. Smoke test real

Staging, conta logada, ~4 turnos (um com NPC em cena e um com missão ativa).

1. **Antes do deploy:** screenshots a 390×844 e 1440×900 de: criação, história (com fala do jogador), Personagem/inventário, Codex/pessoas, missões, boatos, mapa.
2. **Depois do deploy:** os mesmos screenshots.
3. Tocar em "Falar com {NPC}", conferir que o input foi preenchido, editar e enviar. A rota NPC responde normalmente.
4. Criar um personagem novo do zero: a ordem do wizard e a arte da classe estão visíveis; a arena de treino fica como link secundário.
5. Anexar antes/depois ao handoff.

## 7. Riscos & compatibilidade

- **Depende de 321 e 322:** não começar antes de a 322 pousar (ícones e tokens), para não refazer CSS.
- **Copy sobre IA:** a remoção total pode conflitar com exigências de transparência (lojas e regulação). Por isso a recomendação de D1 é uma menção discreta, mais o aviso formal no texto legal da SPEC-222.
- **Mapa pintado:** custo de arte e calibração; fica opcional e em sub-etapa separada.
- **Seletores de e2e:** `critical-journeys`, `vertical-journey` e `dossiers` vão precisar de ajuste. `web/e2e/contracts` é caminho protegido (`/eval-publish`).
- **Sugestões de contexto:** só preenchem o input, sem efeito mecânico. O texto final continua passando pelo router normal (mecânica é Python).
- **Backend e saves:** sem impacto (só leitura de campos que já existem no estado).

## 8. Decisões do dono

- **D1 — "Narração por IA".** **Recomendado: menção discreta e honesta na criação, com formulação de mundo (ex.: "Narrado por um mestre artificial"), mais o aviso formal no texto legal (SPEC-222); "zero LLM" sai sempre.** Alternativas: tirar da criação e deixar só em Sobre/legal, ou manter como está.
- **D2 — medalhão de lobo.** **Recomendado: trocar por um sigilo próprio de Valoria (Abismo / Cinco Sinos) antes do beta e da loja, e tirar "The Witcher" da copy de marketing e loja (pode continuar como referência interna de tom).**
- **D3 — nome do produto.** **Recomendado: "Crônicas de Valoria"** em todo lugar (title, PWA, loja). Alternativa: "Crônicas — RPG de Texto".
- **D4 — headline da criação.** **Recomendado: uma frase ancorada na lore no lugar de "Forje sua lenda"**, a escolher pelo dono a partir de 2–3 opções que o executor propõe.
- **D5 — mapa pintado (opcional).** **Recomendado: não nesta spec. Fazer só a legibilidade (R6) agora e decidir a arte depois do beta.** Se for sim, a geração da arte tem custo e passa por spec ou tarefa de arte separada.

## Histórico de mudanças

- 2026-10-26 — implementação (SPEC-323, branch spec-323). Decisões do dono aplicadas nos padrões recomendados: D1 kicker "Narrado por um mestre artificial" (aviso formal de IA permanece em `web/legal/terms.md`); D2 sigilo próprio (`Sigil.tsx`: anel do Abismo com fenda + Cinco Sinos em pentágono; `Medallion` removido); D3 "Crônicas de Valoria" (`src/product.ts` `PRODUCT_NAME`, `<title>`, meta description, auth, Capacitor `appName`, títulos das páginas legais); D4 headline "Valoria te espera à beira do Abismo" (alternativas propostas ao dono: "Quem responde quando Valoria chama?", "Escreva seu nome na borda do Abismo"); D5 sem mapa pintado (R7 fora; só R6).
- Desvios: (a) `ContextSuggestions` é montado dentro do `Composer` (e não no `ChatSurface`), porque o campo de texto e o rascunho vivem lá; a lógica pura está em `src/contextSuggestions.ts` (`suggestionsFor`). (b) `NpcView` ganhou `in_scene?`/`status?` (a API já os enviava). (c) Ícones de item usam só a família da SPEC-322 (`unique`, `card-active`, `card-reaction`, `prepared`) por slot; arte nova por item exigiria vendorar ícones e atualizar créditos. (d) A etapa 1 e a 3 ganharam spec e2e nova `web/e2e/livro.spec.ts` (o `visual-surfaces` só roda em Linux pinado). (e) `account.spec.ts` usa `/?debug=1` onde afirma o custo técnico. (f) P2-2 da revisão: sem e2e novo para mapa/inventário/palco da classe (cobertos por unit + e2e existentes); registrado como desvio. (g) Revisão: sugestões usam `quest.main.objective` (a API redige os beats como "Etapa N"); aria-label do mapa só traz perigo de nó visitado; "Zero LLM" removido da arena. (h) `android/.../strings.xml` (`app_name` "Valoria (staging)") e o package id ficam intocados.
