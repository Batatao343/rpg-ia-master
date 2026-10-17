# SPEC-210 - revisao independente Sol (2026-10-17)

Revisor: Sol (Opus, contexto separado; nao escreveu a implementacao). Worktree `spec-210` sobre `main` 625540c.

## Veredito
APPROVED_WITH_FIXES. Spec fica `in-progress` apenas pela tarefa de eval separada
(F06/F13 + `DeterministicBackend` servir `GET /game/map`; `handoffs/SPEC-210-eval-authoring.md`).

## Ataques e resultado
| Vetor | Resultado |
|---|---|
| Fog em `/game/map` (nome/perigo/lore/arte/region/edges/ids de nao alcancados) | OK: so visitados + adjacentes; adjacente `id/state/name/coords/reachable/reason`; edges so entre nos enviados; `map_version` = hash do conteudo visivel. Novo teste varre IDs crus de todos os locais nao enviados. |
| `/data/map?game_id=` (fallback R12) | **DEFEITO 1 corrigido:** visitados saiam com o JSON cru (`treasure` do bau curado; `travel_times` citando IDs nao alcancados, ex. brekmar -> costa_negra/ophidia). Agora whitelist. |
| Ownership | `/game/map` passa pela fronteira de sessao (`/game*`) e o load do perfil DB e escopado ao principal. **DEFEITO 2 corrigido:** `/data/map?game_id=` ficava fora da fronteira -> sem principal o load falhava fechado (404 sempre, fallback morto no perfil DB) e sem `Cache-Control: no-store`. `_session_scoped_path` inclui a rota quando ha `game_id`. Legacy: sem auth por design. |
| `/data/map` sem `game_id` | Grafo global mantido so p/ CLI/smoke/`post_deploy_smoke` (spec R1/R12: o cliente React deixa de usa-lo; confirmado: unica chamada e `getMap(gameId)` no fallback). Restringir quebraria o legado - fora do escopo. |
| Custo de viagem | Paridade com `world_utils.travel_cost` (testes assimetria/interior=0) e nome reconhecido por `find_travel_destination`. |
| Interior | **DEFEITO 3 corrigido:** ancora = pai com estado `atual`; a saida (travel_option do pai, custo 0) ficava bloqueada por "Voce ja esta aqui." Agora Viajar envia `Viajo para <pai>`; teste prova que o router reconhece. |
| Gate | combate/simulacao/queda/memorial/arquivado com razao; backend segue autoridade (`_combat_gate`). |
| Refetch | por `turn_count`/`open`; mantem o ultimo mapa ("Atualizando..." / "desatualizado"); troca de save limpa a view; guard `alive`. |
| A11y | estados por icone+texto+`aria-label`; setas entre nos; status com `aria-live` (sem `role=status`); alvos 44px. **DEFEITO 4 corrigido:** razao de bloqueio e rotulo `bloqueado` em vermelho puro (contraste 2,87/4,34:1, axe serious). |
| `allowConsole(404)` | Mascarava o defeito 4: com o 404 a aba caia no `WorldMap` legado e o axe nunca via o `MapTab`. Trocado por `page.route` que serve `/game/map` derivado de `backend.states` (spec nao protegido). |
| R8/R9 animacao | `map.css` sem `animation`/`infinite` (teste Node). |

## Verificacao
- `pytest tests/test_map_view.py`: 21 passed (4 novos). Suite completa offline: exit 0.
- `npm test` 106/106; `npm run build` ok; ruff ok.
- Playwright (config temp porta 4194, `--workers=1`): `map-tab.spec.ts` 5/5 (axe adicionado no caso de combate), `workspace-shell.spec.ts` 11/11.

## Pendente
Somente a tarefa de eval: `DeterministicBackend` servir `/game/map` (sem isso F06, F13, **F17, F18 e F19** reprovam pelo guard de console com o 404 - o executor so listou F06/F13), F06 com selecao + botao Viajar, F13 com `/game/map`, caso de privacidade.

Jornadas no worktree: 105 passed; vermelhas F06/F13/F17/F18/F19 (404 de `/game/map` no fixture protegido) e F02/F16 (rede: `fonts.googleapis.com` ERR_CONNECTION_CLOSED, ambiental, sem relacao com a spec). `effects.spec.ts` verde (inclui `map.marker` no fallback).
