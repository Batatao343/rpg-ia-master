# SPEC-210 - Menu Mapa e viagem como turno

**Backend:** `services/map_view.py` (`build_map_view`, `legacy_filtered_map`, `travel_gate`, `interiors_block`), `GET /game/map?game_id=`, `GET /data/map?game_id=` (filtrado), `visual_catalog.location_visual`.
**Frontend:** `web/src/workspace/tabs/MapTab.tsx` (+`mapModel.ts`, `map.css`), `getGameMap`, tipos `MapView`; `WorldMap` vira fallback (R12) com `gameId`.
**Fog:** o payload so tem visitados (completos) e adjacentes (`id/coords/name`); nenhum nome/perigo/lore/arte de local nao alcancado trafega. Teste: `tests/test_map_view.py` (17 casos, inclui API fim a fim com `TestClient`).
**Viagem:** botao `Viajar` envia `Viajo para <nome>` por `onAction` (turno normal); desabilitado com razao em combate/queda/memorial/arquivado/rota bloqueada/sem rota direta.
**Animacao:** nenhuma nova; o farol do local atual e o de styles.css (so transform/opacity, parado em `.play.is-combat`); `map.css` sem `animation`.
**Testes:** pytest `tests/test_map_view.py`; Node `web/tests/mapTab.test.mjs`; Playwright `web/e2e/map-tab.spec.ts` (full, split, combate, sem rota, fallback; axe sem serious/critical). Screenshots em `web/test-results/spec210/`.
**Limites:** imagem expirada cai para monograma (sem refetch de URL); sem zoom/pan.
**Revisao Sol (17/10):** whitelist no legado filtrado (sem `treasure`/`travel_times`), `/data/map?game_id=` dentro da fronteira de sessao + `no-store`, saida de interior pelo botao, contraste da razao de bloqueio; `workspace-shell.spec.ts` serve `/game/map` em vez de `allowConsole(404)`. Status `done` apos a tarefa de eval.

**Eval (17/10):** `DeterministicBackend` serve `GET /game/map` (grafo do fixture com no nao alcancado sentinela); F06 seleciona o no e envia `Viajo para Brumalta` pelo botao Viajar; F13 expira `/game/map`; F17-F19 voltam a passar; nova jornada **F30 map_fog_privacy** (rede/DOM sem nome/lore/id/tesouro/travel_times de no nao alcancado; adjacente so nome); `effects.spec.ts` map.marker reescrito (sem `fog` no DOM). Evaluator 1.13.0 (rebase sobre SPEC-209/211), lock relocked (10 datasets), 36 jornadas verdes. Publicar exige aprovacao do environment `eval-governance`.
