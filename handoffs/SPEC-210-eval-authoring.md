# SPEC-210 - handoff de autoria de eval (EVAL_AUTHORING_REQUIRED)

O executor nao editou `web/e2e/critical-journeys.yaml`, `critical-journeys.spec.ts`, `fixtures.ts` nem `evals/`.

## O que mudou para as jornadas
- A aba Mapa busca `GET /game/map?game_id=` (view com fog server-side). Se falhar, cai no legado `GET /data/map?game_id=`.
- O `DeterministicBackend` (`web/e2e/fixtures.ts`) NAO serve `/game/map` (responde erro) -> hoje F06/F13 continuam verdes pelo fallback legado (clique no no = viagem imediata). Isso NAO exercita o caminho novo.

## Autoria necessaria (tarefa de eval separada)
1. `DeterministicBackend`: servir `GET /game/map` (payload com `nodes[state atual|visitado|adjacente|bloqueado]`, `edges`, `travel_options[{location_id,name,periods,reachable,blocked,reason}]`, `travel_gate`, `interiors`, `map_version`) derivado de `states.get(gid).world.visited`; adjacente apenas com `id/coords/name`.
2. F06 `map_travel`: clicar o no "Brumalta" agora SELECIONA (painel de detalhe); a viagem exige clicar `Viajar · N periodos` (botao separado). Adaptar o passo sem relaxar asserts (a acao enviada continua `Viajo para Brumalta`).
3. F13 (expiracao concorrente com `GET /data/map`): trocar/adicionar `/game/map` na lista de rotas concorrentes.
4. Novo caso de privacidade: resposta de `/game/map` de jogo novo nao contem nome/lore/perigo de local nao visitado (referencia: `tests/test_map_view.py::test_payload_nao_vaza_nomes_de_locais_nao_alcancados` e `web/e2e/map-tab.spec.ts`).
5. `effects.spec.ts` `map.marker` (fog no DOM) segue valido apenas no fallback legado; com a view nova nao existe no `fog` no DOM (nao e enviado) - reescrever o teste para: adjacente tem `data-effect-state="travelable"` e nada de nome nao descoberto no DOM/rede.

Registry/lock/manifest: nenhum arquivo protegido foi tocado; relock fica com a tarefa de eval.

## ATENCAO - jornadas hoje VERMELHAS ate a tarefa de eval
Como o fixture responde 404 a `GET /game/map`, o guard global de console do `fixtures.ts` (l.390) reprova qualquer teste que abra a aba Mapa: **F06 map_travel, F13 session_expiry, F17 workspace_modes, F18 tabs_history e F19 workspace_preservation** falham (revisao Sol confirmou F17-F19 tambem: todas abrem a aba Mapa) ate o `DeterministicBackend` servir `/game/map` (item 1 acima) ou aceitar o 404. Nao ha regressao de produto: o fallback legado funciona e o clique no no continua viajando. `workspace-shell.spec.ts` (nao protegido) agora serve `/game/map` via `page.route` derivado de `backend.states` (revisao Sol trocou o `allowConsole(404)`, que mascarava falha de contraste da aba nova); o fixture protegido pode reutilizar o mesmo formato.
