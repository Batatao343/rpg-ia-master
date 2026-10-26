# SPEC-324 — Front: a11y estrutural (headings) e atalhos de teclado

> **Status:** `in-progress` (aprovada 25/10; implementada + revisão Sol (P1 + P2 corrigidos em `13797308`, e2e verdes); pousada na main 26/10; falta smoke §6 no staging (comparação visual, leitor de tela))
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-26
> **Depende de:** nenhuma em código. Pode correr em paralelo com a 322 ou a 323 (arquivos TSX diferentes, quase nada de CSS). Não corre em paralelo com a 321, que também mexe em `Workspace.tsx`.
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

**A tela de jogo não tem estrutura de headings.**
- O local é um `<span className="topbar__place">` (`web/src/components/PlayScreen.tsx:73`).
- Os rótulos de seção são `<p className="hud__label">`, usados 22 vezes em `web/src/components/Hud.tsx`, `CharacterTab.tsx`, `ContextSurface.tsx` e outros.
- O único heading é o `h2` do título mobile (`web/src/workspace/Workspace.tsx:282`).
- Usuário de leitor de tela não consegue pular entre "Inventário", "Missões" e "Ouvi dizer" (WCAG 1.3.1 / 2.4.6).

**Os atalhos colidem com o navegador.** Usam Ctrl/⌘+1 (compositor) e Ctrl/⌘+2…6 (painéis) (`Workspace.tsx:170-190`). No Chrome e no Edge, Ctrl+1…8 trocam de aba do navegador e não chegam à página. Não existe `aria-keyshortcuts`, dica nem folha de ajuda.

**Objetivo:** navegação por headings e atalhos que funcionem e possam ser descobertos, sem mudança visual.

## 2. Requisitos

- **R1 — hierarquia de headings.**
  - O nome do local na tela de jogo é o `h1`.
  - Títulos de painel/aba são `h2`; no celular, o `h2` existente do título da surface continua.
  - Os rótulos de seção (`.hud__label`) viram `h3`, com a mesma classe e a mesma aparência.
  - Nenhum nível é pulado.
- **R2 — sem mudança visual.** Os headings novos herdam o estilo atual (reset de margem e fonte na classe). A comparação de screenshot antes/depois tem diff ≤ limiar do Playwright (`maxDiffPixelRatio` 0,01).
- **R3 — atalhos novos.**
  - Alt+1 foca o compositor; Alt+2…6 abrem os painéis, na mesma ordem de hoje.
  - Alt+←/→ continua.
  - Ctrl+\ é substituído por Alt+\ (ou mantido, se funcionar no Chrome/Edge/Firefox; testar).
  - No macOS, Option+dígito gera caractere, então lá vale `Ctrl+Option+dígito` ou sequência (ver D1).
  - Os atalhos de dígito não disparam com o foco num `input`/`textarea`, exceto Alt+1.
- **R4 — atalhos descobríveis.**
  - Cada aba e botão com atalho tem `aria-keyshortcuts` e a tecla no `title`.
  - `?` (com o foco fora de campo de texto) abre uma folha "Atalhos", um modal com foco preso via `useModalFocus` que lista todos e fecha com `Esc`.
- **R5 — skip link.** "Pular para a ação" (âncora para o compositor) é o primeiro elemento focável da tela de jogo.

### Fora de escopo

- Status de turno e `aria-live` (SPEC-320). Contraste (SPEC-322). Rótulos de mapa (SPEC-323).

## 3. Design técnico

**Arquivos novos**
- `web/src/workspace/shortcuts.ts`: tabela única `SHORTCUTS: { id; keys: string; aria: string; label: string; run(ctx) }[]` + `matchShortcut(event, platform): id | null` (pura, testável).
- `web/src/components/ShortcutsSheet.tsx`: modal da folha.

**Arquivos alterados**
- `web/src/workspace/Workspace.tsx:167-197`: o handler passa a usar `matchShortcut`; `aria-keyshortcuts` e `title` nas abas e botões (`:282-298`).
- `web/src/components/PlayScreen.tsx:73`: `<h1 className="topbar__place">`.
- `web/src/components/Hud.tsx`, `CharacterTab.tsx`, `ContextSurface.tsx`, `QuestsTab.tsx` e demais com `hud__label`: `<p>` → `<h3>`. Títulos de painel → `<h2>`.
- `web/src/styles.css`: `h1.topbar__place, h2.panel-title, h3.hud__label { margin: 0; font: inherit; … }` para preservar o visual. Ajuste mínimo, sem conflito real com a 322.

## 4. Plano passo a passo

### Etapa 1 — `matchShortcut`
1. **Testes:** `web/tests/shortcuts.test.mjs`:
   - Alt+2 → painel 2 (Windows e Linux);
   - Ctrl+2 → null;
   - Alt+3 com o foco em input → null;
   - Alt+1 em input → foco no compositor;
   - `?` fora de input → folha;
   - mac: a combinação de D1 → o id esperado.
2. **Implementação:** `shortcuts.ts` + a troca no `Workspace`.

### Etapa 2 — headings
1. **Testes:**
   - e2e `web/e2e/a11y-headings.spec.ts` (novo): na tela de jogo existe exatamente um `h1` com o nome do local; todo `.hud__label` é `h3`; existe um `h2` antes de cada `h3`; nenhum nível pulado (varrer `h1..h6` em ordem).
   - axe `heading-order` sem violação.
   - Screenshot 1440×900 e 390×844 com diff ≤ 1 %.
2. **Implementação:** trocas de tag + CSS de reset.

### Etapa 3 — folha de atalhos e skip link
1. **Testes:** e2e: `?` abre a folha, o foco fica preso e `Esc` fecha e devolve o foco; Alt+3 abre o painel 3 no Chromium; o 1º Tab na tela de jogo foca "Pular para a ação".
2. **Implementação:** `ShortcutsSheet`, skip link.

**Verificação:** `cd web && npm test && npm run lint && npm run test:e2e -- a11y-headings workspace-shell mobile-single-pane`.

## 5. Critérios de aceite

- [x] Um `h1` (local), `h2` por painel e `h3` por seção; axe `heading-order` limpo (inclusive em combate ativo).
- [ ] Sem mudança visual (diff ≤ 1 %): comparação visual antes/depois fica para o smoke do staging (§6), não automatizada.
- [x] Atalhos fora de Ctrl/⌘+dígito; funcionam no Chromium e no Firefox (e2e); não disparam em campo de texto (exceto o foco no compositor).
- [x] `aria-keyshortcuts` e a tecla no `title` de cada aba e botão com atalho; folha "?" lista todos.
- [x] Skip link "Pular para a ação".
- [ ] `npm test` e o e2e do escopo verdes; `uv run pytest` verde.

## 6. Smoke test real

Staging, conta logada, 1–2 turnos.

1. **Antes do deploy:** screenshots a 1440×900 e 390×844 da tela de jogo, mais a lista de headings exportada (NVDA, ou a extensão HeadingsMap).
2. **Depois do deploy:** os mesmos screenshots (sem diferença visível) e a lista de headings com h1/h2/h3.
3. No Chrome: Alt+2…6 trocam de painel e o navegador não troca de aba. Alt+1 foca o compositor e um turno é enviado só pelo teclado.
4. `?` abre a folha; com NVDA, se disponível, navegar por `H` entre Inventário, Missões e Ouvi dizer.
5. Anexar ao handoff.

## 7. Riscos & compatibilidade

- **Trade-off conhecido de D1 (decisão do dono):** no Linux, Chrome/Firefox usam Alt+1…8 para trocar de aba do navegador; no macOS, Ctrl+Option é o modificador do VoiceOver. Anotado também na folha "?". Se o smoke acusar conflito, follow-up: sequências estilo Gmail (alternativa prevista em D1).

- **Alt no Windows:** Alt sozinho foca a barra de menu em alguns navegadores. Usar `preventDefault` só quando houver match e testar no Edge.
- **macOS:** Option+dígito produz caractere (ex.: "¡"), daí D1.
- **Testes que dependem de Ctrl+dígito:** procurar em `web/e2e` (incluindo `contracts`, que é protegido: `/eval-publish`) e adaptar.
- **Conflito de arquivo:** `Workspace.tsx` também é tocado pela 321 (rótulos e cabeça). Rodar depois da 321 ou rebasear com cuidado.
- **Backend e saves:** sem impacto.

## 8. Decisões do dono

- **D1 — combinação de atalhos.** **Recomendado: Alt+1…6 no Windows/Linux e Ctrl+Option+1…6 no macOS, com folha "?".** Alternativa: sequências estilo Gmail (`g` depois `c`/`p`/`m`) fora de campos de texto, que são iguais em qualquer SO, porém menos óbvias.

## Histórico de mudanças

- 2026-10-26 · implementação (spec-executor). Desvios: (1) `run(ctx)` não está na tabela `SHORTCUTS`; a execução fica no `Workspace` (switch por id), a tabela guarda id/tecla/rótulo. (2) Atalhos de seta ficam em Alt+←/→ em todos os SO; só dígitos e `\` usam Ctrl+Option no macOS. (3) Ctrl+\ virou Alt+\ (Ctrl+Option+\ no mac). (4) h2 de painel no desktop é `sr-only` (sem mudança visual); no celular vale o h2 visível da cabeça. (5) Diff de screenshot não automatizado: sem baseline versionada, o e2e confere computed style do h3 (peso 400, margem 0, 0,8rem). (6) e2e `workspace-shell` e `critical-journeys` adaptados de Ctrl+dígito para Alt+dígito (fora de `e2e/contracts`). Testes: `web/tests/shortcuts.test.mjs` (7), `web/e2e/a11y-headings.spec.ts` (6).
- 2026-10-26 · correções da revisão (sol): zonas da Arena h4→h3 (heading-order em combate; e2e novo); foco no compositor adiado ao commit da troca de superfície (skip link/Alt+1 no celular); `split` aceita IntlBackslash/`\` (ABNT2); IME ignorado; `ariaShortcut(help)`=`?`; Alt+←/→ com foco no body também com preventDefault; critério de diff visual desmarcado; trade-off Linux/VoiceOver documentado.
