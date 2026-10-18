# SPEC-216 Etapa 0 — eval authoring (mobile single-pane)

Autor: tarefa de eval (separada do executor de produto). Régua congelada: o executor NÃO edita
`web/e2e/mobile-single-pane.spec.ts`, `critical-journeys.yaml`, `evals/metrics-registry.yaml`,
`scripts/frontend_eval_report.py` nem o lock. Evaluator 1.14.0 -> **1.15.0**, lock refeito pelo comando
oficial (`python -m evals.core.governance lock --dataset ...`), `governance check` verde.
Publicar exige aprovação do environment `eval-governance`.

## Decisões
- IDs **M01-M07** (não F41+): `scripts/beta_gameplay_gate.py` e `summarize()` exigem EXATAMENTE `JOURNEY_IDS`
  por viewport desktop; ids F novos quebrariam o gate desktop da SPEC-212. Suíte própria `--suite mobile`
  (`summarize_mobile`, `MOBILE_IDS`, `MOBILE_VIEWPORTS`), métrica bloqueante `mobile_journey_pass_rate`.
- Projetos Playwright `mobile-320` (320x568) e `mobile-390` (390x844): Pixel 5 (toque + isMobile), `actionTimeout` 8 s.
  O projeto `chromium` ignora o spec mobile. Rodado com o Chromium EMPACOTADO (config temporária sem `executablePath`).
- CI: passo extra `frontend_eval_report.py --suite mobile --check` no `eval-gates.yml`.
- `fixtures.ts`: gatilho aditivo `/emboscada/` (combate falso->verdadeiro com 2 inimigos) em `actionResult`.
- Sem hover/drag/sleep fixo (testado em `tests/test_eval_frontend.py`).

## Contrato de UI que as jornadas exigem (nomes acessíveis)
- `navigation "Superfícies"` com botões `Chat|Codex|Personagem|Combate|Bestiário|Mapa`, >=44px, `aria-current="page"` só no ativo.
  Sem `tablist "Abas do painel"` no mobile; sem `aside.hud`/`.tactical-dock`.
- Exatamente uma região visível: `Chat da aventura` OU `Painel de contexto`. Topbar não intersecta a barra; barra dentro da viewport.
- `data-testid="surface-title"` (heading, tabindex -1) recebe foco a cada troca, texto = nome da superfície (inclui "Chat").
- Combate: narração no chat + botão `Ir para o combate` (>=44px); troca automática para `#ws-panel-combate` só DEPOIS da narração no DOM.
  Desfecho: região `Desfecho do combate` na superfície Combate; narração (sem XP) no chat.
- Mira por toque (mesma máquina `useTargeting`): `Jogar Carta X` -> `Alvo: Y`; botão `Cancelar mira` (>=44px); botão `Detalhes de <Carta>`
  abre `.card-detail` sem hover. Payload do POST igual ao desktop (exceto `action_id`).
- Voz: botão `Gravar ação por voz` >=44px; trocar de superfície gravando libera o microfone (`track.stop`) e não envia ação.
- Composer: input >=16px, campo e Agir inteiros dentro de `visualViewport` com teclado simulado (320: -260px, 390: -336px).

## Resultado atual (sem produto) — 7 jornadas x 2 viewports
| Jornada | Estado | Onde falha / observação |
|---|---|---|
| M01 one_surface_visible | FALHA | `navigation "Superfícies"` inexistente (0 botões) |
| M02 switch_and_back_preserves_state | FALHA | `tap` na barra (Codex). Validado com a UI antiga (modo Painel + abas): passo a passo passa -> a asserção de estado é alcançável |
| M03 composer_visible_with_virtual_keyboard | 390 PASSA / **320 FALHA** | 320x568: botão/campo termina em 322.9px > visualViewport 308 (composer vaza sob o teclado); falha real de produto (R4) |
| M04 voice_flow_and_mic_release | FALHA | barra inferior; com UI antiga o fluxo voz->Parar->transcript->Agir passa, mas `releases` NÃO sobe ao trocar de superfície gravando (R5: produto deve liberar o mic ao trocar) |
| M05 combat_own_screen_and_outcome_in_chat | FALHA | `aria-current` em Combate (barra ausente); a troca para a superfície Combate já ocorre hoje |
| M06 touch_targeting_same_payload_as_desktop | FALHA | `Cancelar mira` inexistente; a referência desktop (clique, 1440x900, contexto isolado) e o toque carta->alvo antes disso funcionam |
| M07 reduced_motion_focus_aria_and_a11y | FALHA | barra ausente / `surface-title` ausente |

Passos além da primeira falha (M01 resto, M05 desfecho, M06 após cancelar/detalhes, M07 axe por superfície) não foram
exercitados contra produto; revalidar após implementar a barra.

## Verificação
- `tests/test_eval_frontend.py` (+2 testes: manifesto/spec/disjunção F-V-M; relatório exige as 7 jornadas em ambos viewports) e `test_ci_eval_gates.py`.
- Regressão (Chromium empacotado, projeto `chromium`): F01-F30/F35-F40 verdes exceto 2 testes `account-lifecycle` (SPEC-190 recovery token / verification link),
  que falham igual em `main` limpo (pré-existentes); F36 oscilou sob carga e passou isolado. J-V1 ignorado (exige stack real).
- `npm test`: 119 passed. `pytest`: verde exceto `test_eval_harness::...identity_drift` (pré-existente: worktree temp não identificado) e 2 de `test_project_index` (staleness aceita).
- `evals.core.governance check`: valid, 11 datasets.
