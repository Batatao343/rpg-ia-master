# SPEC-201 — Índice de capturas

Commit auditado: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6`. Fixture: `web/e2e/fixtures.ts` (`DeterministicBackend`, sem rede/provider/custo); estados de combate/morte/level-up injetados no próprio spec de diagnóstico (opção (a) da spec §3.2; **opção (b) via simulador real com `RPG_FORCE_MOCK=1` não foi usada**, sem alteração de `fixtures.ts`).

**Reprodução** (a partir de `web/`):

```bash
RPG_SPEC201=1 npx playwright test e2e/diagnostics --grep @spec201 --workers=1
# Chromium local: RPG_BROWSER_EXECUTABLE=<caminho> se necessário
```

Sem `RPG_SPEC201=1` o arquivo se auto-pula (não entra no gate F01–F16/`npm run test:e2e`).
Viewports: **1440x900** e **1280x800**. Sufixo `--motion` = `reducedMotion: no-preference` (estados com motion); sem sufixo = baseline `reduce`.

| PNG (em `capturas/<viewport>/`) | superfície | estado / fixture | viewports |
|---|---|---|---|
| `account-default.webp` | account | fixture sem /account/* → estado de erro (reduce) | 1440x900, 1280x800 |
| `auth-default.webp` | auth | backend.authenticated=false (DeterministicBackend) (reduce) | 1440x900, 1280x800 |
| `auth-error.webp` | auth | /auth/login → 401 {"detail":"bad"} (reduce) | 1440x900, 1280x800 |
| `combat-active--motion.webp` | combate | fixture combat.active=true (2 inimigos, 4 cartas, zonas, Ferimento leve) (no-preference) | 1440x900, 1280x800 |
| `combat-active.webp` | combate | fixture combat.active=true (2 inimigos, 4 cartas, zonas, Ferimento leve) (reduce) | 1440x900, 1280x800 |
| `combat-card-focus.webp` | combate | foco "Jogar Carta" (reduce) | 1440x900, 1280x800 |
| `combat-card-hover.webp` | combate | hover "Jogar Carta" (reduce) | 1440x900, 1280x800 |
| `combat-card-pressed.webp` | combate | mouse.down sem up (reduce) | 1440x900, 1280x800 |
| `combat-hud-tab--motion.webp` | combate | aba Combate do Hud (no-preference) | 1440x900, 1280x800 |
| `combat-hud-tab.webp` | combate | aba Combate do Hud (reduce) | 1440x900, 1280x800 |
| `create-card-focus.webp` | create | foco no botão do cartão (reduce) | 1440x900, 1280x800 |
| `create-card-hover.webp` | create | hover cartão de classe (reduce) | 1440x900, 1280x800 |
| `create-card-selected.webp` | create | clique no botão do cartão (reduce) | 1440x900, 1280x800 |
| `create-step1-mundo--motion.webp` | create | /game/saves=[] (no-preference) | 1440x900, 1280x800 |
| `create-step1-mundo.webp` | create | /game/saves=[] (reduce) | 1440x900, 1280x800 |
| `create-step2-origem-default--motion.webp` | create | 1 raça fixture (no-preference) | 1440x900, 1280x800 |
| `create-step2-origem-default.webp` | create | 1 raça fixture (reduce) | 1440x900, 1280x800 |
| `create-step3-vocacao-default.webp` | create | 2 classes fixture (reduce) | 1440x900, 1280x800 |
| `create-step5-identidade-empty.webp` | create | passo Identidade vazio (reduce) | 1440x900, 1280x800 |
| `hud-tab-codex.webp` | hud | aba codex (reduce) | 1440x900, 1280x800 |
| `hud-tab-combate.webp` | hud | aba combate (reduce) | 1440x900, 1280x800 |
| `hud-tab-cronica.webp` | hud | aba cronica (reduce) | 1440x900, 1280x800 |
| `hud-tab-faccoes.webp` | hud | aba faccoes (reduce) | 1440x900, 1280x800 |
| `hud-tab-ficha.webp` | hud | aba ficha (reduce) | 1440x900, 1280x800 |
| `hud-tab-mapa.webp` | hud | aba mapa (reduce) | 1440x900, 1280x800 |
| `hud-tab-missoes.webp` | hud | aba missoes (reduce) | 1440x900, 1280x800 |
| `hud-tab-personagens.webp` | hud | aba personagens (reduce) | 1440x900, 1280x800 |
| `overlay-death--motion.webp` | overlay | death_pending + DeathView (no-preference) | 1440x900, 1280x800 |
| `overlay-death.webp` | overlay | death_pending + DeathView (reduce) | 1440x900, 1280x800 |
| `overlay-gameover--motion.webp` | overlay | game_over=true (no-preference) | 1440x900, 1280x800 |
| `overlay-gameover.webp` | overlay | game_over=true (reduce) | 1440x900, 1280x800 |
| `overlay-levelup--motion.webp` | overlay | pending_choices carta nível 2 (no-preference) | 1440x900, 1280x800 |
| `overlay-levelup.webp` | overlay | pending_choices carta nível 2 (reduce) | 1440x900, 1280x800 |
| `play-after-turn.webp` | play | turno concluído (reduce) | 1440x900, 1280x800 |
| `play-composer-error.webp` | play | failNextTurn → banner + pendência (reduce) | 1440x900, 1280x800 |
| `play-composer-focus.webp` | play | foco no input (reduce) | 1440x900, 1280x800 |
| `play-composer-hover.webp` | play | hover em Agir (reduce) | 1440x900, 1280x800 |
| `play-composer-pending.webp` | play | delayStream (SSE pendente) (reduce) | 1440x900, 1280x800 |
| `play-default--motion.webp` | play | game-a (combat.active=false) (no-preference) | 1440x900, 1280x800 |
| `play-default.webp` | play | game-a (combat.active=false) (reduce) | 1440x900, 1280x800 |
| `saves-default--motion.webp` | saves | 2 saves fixture (no-preference) | 1440x900, 1280x800 |
| `saves-default.webp` | saves | 2 saves fixture (reduce) | 1440x900, 1280x800 |
| `saves-focus.webp` | saves | Tab → foco (reduce) | 1440x900, 1280x800 |
| `saves-hover.webp` | saves | hover no 1º save (reduce) | 1440x900, 1280x800 |
| `simulator-default.webp` | laboratório | /data/combat-simulator stub (2 inimigos) (reduce) | 1440x900, 1280x800 |

Total: 90 PNGs. Dados brutos em `../dados/*.json`.

Limites: Google Fonts pode estar indisponível offline (fallback serif do sistema); as capturas não são baseline visual (dependem de fonte/GPU).
