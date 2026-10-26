# SPEC-323 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Claude Opus (papel Sol) · **Data:** 2026-10-26 · **Commit revisado:** `a5f5d241`

## Escopo

Branch `spec-323` (`git diff main...spec-323`, 33 arquivos, só `web/` + a spec). Revisei:
renomeação do produto (index.html, capacitor.config.ts, AuthScreen, títulos de `web/legal/*`),
`Sigil.tsx` e a remoção do `Medallion`, a copy (D1/D4, estados vazios, custo em US$ atrás de `?debug=1`),
as sugestões de contexto (`contextSuggestions.ts`, `ContextSuggestions.tsx`, montagem no `Composer`),
as listas do HUD e o CSS, o fallback `WorldMap` e o `MapTab`, as edições de e2e e os testes novos.
Não rodei Playwright nem build, por instrução. `web/e2e/contracts` e `evals/` não foram tocados.

Pontos conferidos e OK:
- Legal: só o H1 das 5 páginas mudou. Dados do prestador e disclosures da SPEC-222 continuam intactos,
  incluindo o aviso formal de IA (`web/legal/terms.md:13`, "Conteúdo gerado por IA").
- `appId` não mudou (testado em `build.test.mjs`). Não há manifest PWA no repo.
- Sigilo: desenho original (anel, 5 pontos em pentágono e fenda em losango). Herda `currentColor` e
  fica `aria-hidden`, o que é correto para ornamento ao lado de um título. Zero "lobo"/"wolf"/"witcher"
  em `web/src` (testado). O `Medallion` saiu de todos os usos.
- D1: o kicker "Dark Fantasy · Narrado por um mestre artificial" aparece em toda a tela de criação,
  e a meta description também cita o mestre artificial. É honesto e suficiente com o aviso formal nos termos.
- Custo: só o texto técnico em US$ ficou atrás de `debugEnabled()` (`StoryLog.tsx:133`). O
  "Débito liquidado: … Estilhas" e o saldo "Conta · N Estilhas" continuam visíveis. As edições de
  `account.spec.ts` (`/?debug=1`) só cobrem as asserções do US$, o que é legítimo. A troca do headline
  em `critical-journeys` também é legítima.
- Sugestões: o toque só chama `setInput` e foca o campo, sem `onAction` e sem LLM. Elas somem em
  combate, game over, morte pendente, simulação, busy ou fora da superfície. NPCs vêm de
  `visible_npc_view` (só `known_by_player`, com `in_scene` já combinado com vivo).
- A11y: grupo "Sugestões de ação", `aria-current` no item equipado, o selo "boato" em texto e
  `--faint`/`--muted` com AA garantido pelo `contrast.test`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/src/contextSuggestions.ts:15-19` + `api.py:2852` | "Seguir objetivo" lê `quest.main.beats[current_step].description`, mas a API redige os beats como `"Etapa N"` (regra de ouro, `api.py:2852`). Com dados reais, o chip preenche "Sigo o objetivo: Etapa 2", que não ajuda o jogador nem o router. O teste unitário usa uma descrição crua ("Achar o sino") que a API nunca envia: é o padrão "o mock esconde o bug". | Usar `quest.main.objective`, o objetivo público já filtrado por `public_objective` (se vazio, não sugerir). Ajustar o fixture do teste para o formato real (beats "Etapa N" + `objective`) e afirmar que "Etapa" nunca aparece no texto. |
| P1-2 | P1 | `web/src/components/CombatSimulatorScreen.tsx:66` + `web/tests/copy.test.mjs:19` | O kicker "Motor real · Zero LLM" continua na tela da Arena de treino, que o jogador abre pelo link novo. Isso contraria R3/D1 ("zero LLM sai sempre") e o critério de aceite "sem LLM/zero LLM". O teste `/zero LLM/` diferencia maiúsculas e não pega "Zero". | Trocar a copy (ex.: "Arena de treino · combate de verdade, sem história") e tornar o teste `/\bLLM\b/i` sobre literais de UI, como pede a Etapa 2 ("nenhum LLM"). |
| P1-3 | P1 | `web/src/components/WorldMap.tsx:117-121` | No fallback, o `aria-label` de nós **não visitados** (adjacentes ou de missão) agora anuncia `perigo ${danger}`. Para adjacentes, `legacy_filtered_map` manda `danger: 0` como placeholder (`services/map_view.py:220`), então o leitor de tela ouve "perigo 0", que é falso. Se houver `danger_overrides[loc.id]` para o adjacente, o número real e não percebido vaza. O `MapTab` principal nunca manda perigo de adjacente (`map_view.py:157-159`). R6 pede o mesmo `aria-label` do `MapTab`. | Incluir `, perigo N` só quando `known`. Teste unitário ou e2e: um nó adjacente no fallback não contém "perigo" no `aria-label`. |
| P2-1 | P2 | `web/src/styles.css:621` | Os nós adjacentes agora mostram o nome, mas `.is-fog .worldmap__label` mantém `--faint` com `opacity: 0.5`, o que fica abaixo de 4,5:1 e anula parte do objetivo de legibilidade de R6. | Tirar a opacidade do rótulo (manter só no ponto tracejado) ou usar `--muted`. |
| P2-2 | P2 | `web/e2e/map-tab.spec.ts`, Etapas 3/4/5 da spec | Faltam os e2e pedidos: névoa sem nome + `aria-label` com perigo + `font-size` do rótulo ≥ 13,6 px (Etapa 5); inventário com o equipado marcado + urgente ≥ 4,5 (Etapa 4); arte ao lado do detalhe a 1440×900 (Etapa 3). Nenhum critério marcado afirma isso hoje. | Estender `map-tab.spec.ts`/`livro.spec.ts` ou registrar o desvio na spec. |
| P2-3 | P2 | `web/capacitor.config.ts:21` vs `android/app/src/main/res/values/strings.xml:3-4` | `appName` virou "Crônicas de Valoria", mas o rótulo do launcher do Android vem do `strings.xml` ("Valoria (staging)"), e o `cap sync` não o reescreve. Para staging é aceitável, porque o sufixo distingue o build, mas as duas fontes divergem em silêncio. | Anotar no comentário do `capacitor.config.ts` (e na SPEC-198) que o `strings.xml` precisa virar `PRODUCT_NAME` em produção, ou acrescentar uma asserção em `build.test.mjs` de que o `app_name` começa com "Crônicas de Valoria" ou termina em "(staging)". |
| P2-4 | P2 | `web/src/styles.css:699` | `.person__rel::before { content: "◆ " }`: leitores de tela leem o conteúdo de `::before` ("losango preto"). | `content: "◆ " / ""` (texto alternativo vazio) ou um `<span aria-hidden>`. |
| P2-5 | P2 | `web/src/components/Hud.tsx:19` | Formatação: `EquipFn =(pick`. | `EquipFn = (pick`. |

## Correções aplicadas

(nenhuma ainda; aguardando o executor)

## Pendências

- P2-3 vai para a SPEC-198 (identidade da loja).
- R7 (mapa pintado) ficou fora por D5, conforme a spec.

## Comandos rodados

```text
cd web && npm test           → 203 pass, 0 fail
cd web && npx tsc --noEmit   → sem erros
cd web && npm run lint       → eslint ok; css-lint + contrast 13/13 pass
```
