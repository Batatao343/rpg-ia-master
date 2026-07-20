# SPEC — Polish de frontend: leitura iluminada + distribuição de telas

> **Status:** `done`
> **Criada:** 2026-07-19 · **Atualizada:** 2026-07-20
> **Depende de:** onboarding-valoria `done`, inicio-personalizado `done`,
> polish-sessao `done` (telas React existentes), refatoracao-sistema-classes `done` (HUD Entropia/Carga)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Auditoria visual do frontend React (`web/`) com skills de design (`impeccable` +
refs de UI: bestiário/journal do The Witcher 3, leitura imersiva de Baldur's Gate 3)
achou dois eixos de problema que os testes offline (backend) e o `npm run build`
não pegam — só aparecem renderizando pixels de verdade:

1. **Superfície de leitura tratada como chat, não como livro.** O rótulo
   "Narrador" era carimbado acima de TODO bloco de narração (o "eyebrow repetido"
   que o impeccable proíbe) e a coluna mais lida do app era a mais fria/sem foco.
   Num RPG de texto, a leitura é o herói — deve ler como diário iluminado.

2. **Telas escuras demais + distribuição errada.** A tela de criação renderizava
   quase preta (painel não separava do fundo) por um bug de camada; a barra de 8
   abas do HUD cortava "Codex"; a criação no mobile mostrava o meio do texto com o
   título clipado acima da dobra.

Objetivo: subir a barra visual das telas-herói (leitura + criação) e corrigir
distribuição/fluxo, mantendo a identidade (The Witcher dark fantasy, OKLCH,
Cinzel/EB Garamond, bronze fosco como único acento, sangue = perigo).

Princípio de arquitetura relevante: **mecânica é Python; frontend é só
apresentação** — nenhuma mudança de estado/regra aqui, puro CSS/markup.

## 2. Requisitos

- **R1 — Sem eyebrow repetido.** Blocos de narração `STORY` NÃO exibem o rótulo
  "Narrador". Rótulo só quando muda o sentido: fala do jogador ("Você"), NPC
  ("Diálogo"), combate ("Combate"), espólio ("Espólio").
- **R2 — Capitular iluminada por cena.** Todo bloco de narração `STORY` abre com
  drop-cap (Cinzel Decorative); a 1ª cena da sessão recebe a maior, com glow.
- **R3 — Fleuron entre beats.** Dois turnos de narração seguidos são separados por
  um ornamento `❧` centrado (ritmo de livro no lugar do rótulo removido).
- **R4 — Coluna de leitura iluminada.** A `.story` recebe um glow quente vindo do
  topo (luz de tocha); combate sobrescreve com o brilho de sangue.
- **R5 — Fundo sempre atrás do conteúdo.** `.atmosphere`/`.ember-canvas` ficam em
  `z-index:-1`; nenhuma tela é escurecida pela vinheta quando o `motion` zera o
  transform.
- **R6 — Painel de criação iluminado.** `.create__frame` lê como pergaminho à luz
  (lift real do surface + glow de tocha no topo + borda bronze), não bloco chapado;
  texto de leitura do wizard (`.wizard__para`) com tom mais claro que `--muted`.
- **R7 — Abas não transbordam.** As 8 abas do HUD quebram em 2 linhas de 4
  (`flex-wrap`), todas visíveis e legíveis em 360px (nada de "Codex" cortado).
- **R8 — Criação usável no mobile.** Frame ancora no topo (título/stepper visíveis)
  e `width:100%` respeita o padding do container (sem overflow horizontal).

### Fora de escopo

- Redesenhar estrutura de telas (wizard de 5 passos, grade de abas, HUD): só
  aparência/distribuição, não fluxo de navegação.
- Reescrever o card do jogador (bolha à direita) — decisão de identidade, mantida.
- Combate/SaveScreen/LevelUpModal: herdam os fixes de R5/R6/R7 mas não foram
  reauditados pixel a pixel.
- Tiers de acessibilidade além de contraste (screen reader, ARIA extra).

## 3. Design técnico

Puro apresentação. **Sem mudança de estado, schema, API ou regra.**

### Arquivos alterados

- **`web/src/components/StoryLog.tsx`**
  - `import { Fragment, ... }`; no `.map`, computa `sceneBreak = prev?.role ===
    "narrator" && e.role === "narrator"` e renderiza `<div class="scene-break">
    <span>❧</span></div>` antes da entrada (R3).
  - `LogEntryItem`: `showRole = entry.role === "player" || (entry.role ===
    "narrator" && entry.type !== "STORY")`; rótulo `.msg__role` só quando
    `showRole` (R1). Resto inalterado (typewriter, motion, `mdLite`).

- **`web/src/styles.css`**
  - `.atmosphere`, `.ember-canvas` → `z-index: -1` (R5).
  - `.story` → `position: relative` + `background: radial-gradient(92% 56% at 50%
    -6%, oklch(0.42 0.06 72 / 0.07), transparent 62%)` (R4); combate já
    sobrescreve `.play.is-combat .story`.
  - `.msg--story .msg__body::first-letter` → drop-cap 2.7rem; `:first-child` →
    3.6rem + `text-shadow` de glow (R2).
  - `.scene-break` (+ `::before/::after` fios + `span` acento) — novo (R3).
  - `.create__frame` → `background` com `radial-gradient` quente no topo +
    `linear-gradient(oklch(0.30…), oklch(0.235…))` + `border: 1px solid
    var(--line)` + `box-shadow` com inset highlight (R6).
  - `.wizard__para` → `color: oklch(0.85 0.022 82)` (era `--muted`) (R6).
  - `.tabs` → `flex-wrap: wrap; gap: 3px`; `.tab` → `flex: 1 1 calc(25% - 3px);
    min-width: 0`; override antigo de 6 abas relaxado p/ `font-size: 0.62rem` (R7).
  - `@media (max-width:480px)`: `.create { place-items: start center; padding:
    1.4rem 0.8rem }` + `.create__frame, .lvlup { width: 100%; padding: 1.15rem
    1rem }` (R8).

### Fonte da verdade de tokens

`web/src/styles.css` `:root` — OKLCH. Nenhum token novo criado; valores literais
`oklch(...)` usados nos glows/drop-cap seguem a paleta (bronze hue ~74, quente).

## 4. Plano passo a passo

Trabalho já executado (spec retroativa p/ registro). Ordem seguida:

### Etapa 1 — Superfície de leitura (R1–R4)
1. **Verificação:** `npm run build` (tsc) verde; screenshot headless do harness de
   play (desktop): drop-cap "O"/"A", fleuron `❧`, rótulo só em Você/Diálogo.
2. Editar `StoryLog.tsx` (R1, R3) + `styles.css` (R2, R4).

### Etapa 2 — Fundo + criação iluminada (R5, R6)
1. Diagnóstico: `.play` é `position:relative` (acima da atmosfera) mas `.create`
   não → atmosfera pintava por cima ao fim da animação. Fix `z-index:-1` (R5).
2. Painel de criação ainda murcho (surface escuro chapado) → lift + glow + borda
   (R6). **Verificação:** screenshot real (uvicorn MockLLM, Edge headless,
   `--force-prefers-reduced-motion`): pergaminho iluminado, título bone, prosa
   nítida.

### Etapa 3 — Distribuição (R7, R8)
1. Abas: `flex-wrap` 2 linhas de 4. **Verificação:** screenshot desktop — 8 abas
   visíveis, "Codex" inteiro.
2. Mobile criação: top-align + `width:100%`. **Verificação:** lógica de CSS
   (`width:100%` respeita padding; `overflow-x:hidden` já presente no bloco 480px).

## 5. Critérios de aceite

- [x] R1 — narração `STORY` sem rótulo "Narrador"; rótulo nas outras rotas
- [x] R2 — drop-cap por cena (1ª maior + glow)
- [x] R3 — fleuron `❧` entre narrações seguidas
- [x] R4 — coluna de leitura com glow de tocha; combate sobrescreve
- [x] R5 — `atmosphere`/`ember-canvas` em `z-index:-1`; criação não escurece
- [x] R6 — `.create__frame` lê como pergaminho iluminado; `.wizard__para` mais claro
- [x] R7 — 8 abas em 2 linhas, nada cortado em 360px
- [x] R8 — criação mobile: topo ancorado + `width:100%` sem overflow
- [x] `npm run build` verde (tsc + vite)
- [ ] `uv run pytest` — **N/A** (mudança só-frontend; suíte é backend, não exercita o React)
- [x] Guard de FallbackLLM — **N/A** (sem `with_structured_output` novo)
- [x] Saves antigos carregam — **N/A** (sem mudança de schema/estado)

## 6. Smoke test (visual, no lugar do LLM real)

Frontend não usa LLM — smoke é visual via Edge headless (`msedge --headless=new
--screenshot`, servidor uvicorn com `RPG_FORCE_MOCK=1`):

1. [x] Landing/criação desktop (1440): painel de pergaminho iluminado, título bone
   de alto contraste, stepper e prosa legíveis.
2. [x] Play desktop (1440, harness fiel): drop-cap + fleuron + rótulos semânticos;
   HUD com abas em 2 linhas ("Codex" inteiro); barras Vida/Entropia + chip Carga.
3. [~] Mobile (390–412): top-align confirmado; overflow do frame corrigido por
   lógica de CSS — headless não emula device de forma 100% confiável p/ o SPA
   (layout-viewport largo em estados de conteúdo longo). Reverificar em device real
   quando possível.

## 7. Riscos & compatibilidade

- **Saves antigos:** sem impacto — nenhuma mudança de estado/schema.
- **MockLLM/FallbackLLM:** sem impacto — nenhum caminho de LLM tocado.
- **Quota/latência:** nenhum.
- **Regressão de identidade:** o painel de criação ficou mais claro (pergaminho
  iluminado) — decisão deliberada p/ casar com a superfície de leitura; ainda dark
  fantasy, não clareou o mundo frio (bg/atmosfera intactos).
- **Mobile não 100% verificado em pixel:** o fix (`width:100%`) é estritamente mais
  seguro que o `min(96vw,680px)` antigo (que ignorava o padding e estourava);
  `overflow-x:hidden` no bloco 480px contém qualquer sobra. Confirmar em device
  real é o único item pendente.
- **Fleuron `❧` entre narrações seguidas:** dispara raramente (jogador costuma
  alternar com a narração) — baixa frequência, ornamento discreto.
