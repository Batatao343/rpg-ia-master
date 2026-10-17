# SPEC-208 — Revisão independente Sol (2026-10-16)

- **Revisor:** Sol (≡ Opus, contexto separado; não escreveu a implementação).
- **Escopo:** diff não commitado da branch `spec-208` (worktree `rpg-spec-208`) + `docs/spec208/README.md` + matriz `docs/spec201/`.
- **Veredito:** **APPROVED_WITH_FIXES** — defeitos encontrados foram corrigidos nesta revisão (com testes); todos os
  critérios de §5 atendidos; spec → `done`. Efeitos de §3.4 não entregues ficam como desvio explícito (§3.4 é [R]
  substituível; nenhum critério de §5 os exige).

## Achados e correções

| # | Severidade | Achado | Correção | Teste |
|---|---|---|---|---|
| 1 | Alta (R8/R9, critério de aceite) | O relatório atribuía as long tasks de 52–109 ms à "montagem de aba do shell 204, também com efeitos desligados". Medição A/B por variante mostrou outra causa: **qualquer animação contínua** na tela de combate (pulso do `combat-veil`, `throb` da bandeira "Em combate" e do ponto da aba). Com uma delas ativa, p90 7→14 ms e long tasks 50–90 ms; sem elas, 0. O "efeitos desligados" do teste antigo desligava também essas animações. R9 já proíbe efeito contínuo atrás do chat em combate. | Véu estático com uma entrada curta de `opacity`; bandeira/ponto estáticos (informação = texto/cor); farol do mapa parado em combate; alertas de HP baixo/Carga severa com 3 pulsos; território disputado sem `box-shadow` em loop. | `e2e/effects.spec.ts` › `R9: em combate nenhuma animação contínua…` (`document.getAnimations()` sem `iterations: Infinity`) |
| 2 | Média (R8) | Bloco SPEC-208 transitava `box-shadow`, `border-color`, `background`, `filter` e **`width`** (barra de Vitalidade = layout). R8: só `transform`/`opacity`. | Cor/sombra/borda trocam no ato; barra por `transform: scaleX()`; `.btn` só transita `transform`. | `tests/design.test.mjs` › `R8: no bloco SPEC-208 só transform/opacity transitam…` (lint do CSS + keyframes) |
| 3 | Média (R8, fluxo chat) | A fade do bloco novo (`chat.entry`) + o fade de opacidade do botão ao (des)habilitar somavam ~1 vsync ao p95 do chat (20,8–27,7 vs 13,9 ms). Remover só um não bastava. | `chat.entry` rejeitado com medição (M09 segue: histórico/reload sem animação, sem blur); registry 19→18. | `M09: entradas do chat não animam…` |
| 4 | Média (honestidade do gate) | O teste de perf media só o fluxo combate+abas, comparava "não piora" (`off+20`) e o modo `off` só mudava o atributo CSS (o hook `useEffectsEnabled` não era notificado). | Três fluxos (criação, chat, combate+abas); `off` real via `localStorage`+`storage`; contra o build o gate é **absoluto** (long task ≤ 50 ms, p95 ≤ 16,7 ms); contra o dev server é alarme grosseiro e diz isso. Long tasks agora vêm com a fase (`59ms@aba Mapa`). | `perf: 4x CPU — criação…`, `perf: 4x CPU — chat … e combate…` |
| 5 | Baixa (R10) | `rpg.effects` mudado em outra aba não valia sem recarregar quando nenhum primitivo estava montado. | Listener global de `storage` em `initEffects()` + reaplicação no `subscribe`. | coberto pelos testes de perf (modo `off`) |
| 6 | Baixa (R8) | `Reveal` animava `y` via `motion` (JS, main thread) e mantinha o `fill`. | Animação CSS de compositor decidida na montagem, `fill: backwards`. | `codex.entry.reveal` |

Verificado sem achado: `MotionConfig reducedMotion="user"` e bloco global de reduced-motion intactos; nenhum `role="status"` novo
em UI sempre montada; foco/hitbox independem de hover (`ctrl.focus`, `choice.select` por `elementFromPoint`, `card.arm` por
teclado/Esc); R7 (Codex/Mapa sem sentinela no DOM, `<link>` ou rede); kill switch `?effects=off`; nenhuma dependência nova;
`critical-journeys.yaml`/`metrics-registry.yaml`/`evals/` intocados.

## Medições (build, CDP CPU 4×, 1440×900, monitor 144 Hz)
5 execuções finais, efeitos **ligados** (bruto: `docs/spec208/evidence/perf-runs.jsonl`): criação p95 7,1–13,7 ms; chat
p95 13,9–14,0 ms; combate+abas p95 13,9–14,0 ms; **0 long task > 50 ms em todas**. Efeitos desligados: p95 7,1–13,9 ms, 0 long
task. Mais 4 execuções chat+combate durante a revisão: idem. Antes da última correção, 2 de ~8 execuções tiveram uma long task
de 51–59 ms no combate — não reapareceu nas 9 finais; o fluxo está perto do limite de 50 ms sob 4×.
Bundle (gzip -6, vs `ceadfe1`): JS +1 701 B, CSS +1 092 B (teto +15 KB / +3 KB).

## Evidência §6
`docs/spec208/evidence/smoke-{normal,reduced,effects-off}.webm` (+ `.png`), gerados por `RPG_EFFECTS_EVIDENCE=1 npx playwright
test e2e/effects.spec.ts -g smoke --project=chromium-motion`. `trace.zip` (6–12 MB cada) não versionados — reproduzíveis.

## Desvios explícitos (não bloqueiam `done`)
- `passive.trigger`: não há campo de gatilho de passiva no payload; a spec proíbe prever no cliente.
- `reaction.present`: M18 pede painel só com gatilho real do backend; hoje a reação é declarada junto da ação → SPEC-209.
- `encounter.enter/exit`: M36 é P2 → default §8.2 (fora).
- Linha de mira SVG: opcional na própria spec.
- `chat.entry`: rejeitado por medição (achado 3).

## Execução
- `cd web && npm test` → exit 0 (101/101, 10 em `tests/design.test.mjs`); `npm run build` → exit 0.
- Playwright completo (`--workers=1`, dev server): 185 passed, 29 skipped, 2 failed (exit 1) — ambos pré-existentes:
  `voice-input` "native Chromium MediaRecorder" (falha igual no HEAD) e `account-lifecycle` SPEC-190 (`orderPolls` 2≠1,
  janela de 5,3 s; reproduzido também no HEAD via `git stash`: 1 de 3 execuções falha). Intermitência de
  `fonts.googleapis.com` (rede externa) aparece em ambos.
- `effects.spec.ts` completo nos dois projetos: 88 passed, 4 skipped; perf contra o build 5/5 exit 0.
- `uv run --frozen pytest -q -p no:warnings --ignore=tests/test_project_index.py` → exit 0 (nenhum backend alterado).

## Eval
`EVAL_AUTHORING_REQUIRED: false`; nenhuma jornada crítica nova exigida pela spec; `web/e2e/critical-journeys.yaml` não muda.
Sem handoff de eval-authoring.
