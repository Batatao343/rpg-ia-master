# SPEC-211 — handoff de autoria de eval (leak de dossiê + jornadas)

O implementador NÃO criou dataset, evaluator, registry, lock nem jornadas (evals/ e
`web/e2e/critical-journeys.yaml` são protegidos). Autoria em tarefa separada, revisada por
Sol/Astra, com relock no manifesto.

## Superfície sob teste

- `services.dossiers.build_dossiers(state)` / `GET /game/codex/dossiers` (JSON do payload).
- Oráculos: `services.dossier_visibility.assert_no_private_fields(payload)` (allowlist estrita
  `extra="forbid"` + chaves proibidas) e `services.player_knowledge.assert_no_player_leak(
  services.dossier_visibility.leak_view(payload), state)` (oráculo SPEC-206 sobre o payload inteiro).
- Entrada do caso = save sintético (dict GameState mínimo); saída = JSON do endpoint.
- Fixtures de referência já escritas pelo executor: `tests/test_dossier_leak.py`,
  `tests/test_dossiers.py`, `tests/test_dossiers_api.py` (não substituem o corpus oficial).

## Casos mínimos (dataset `dossier_leak`, hard gate `leak_count = 0`)

1. Entidade `hidden` visitada sem reveal (`mon_verme_primordial_das_raizes_do_mundo`) → ausente
   de `sections.locations`, de `chronicle_index[].entity_ids`, de `art`, de qualquer string do JSON.
2. NPC com `hidden_traits`, `npc_secrets` e `memory` privada → nenhuma dessas chaves/strings no payload;
   `appears_to_know == []` quando só há `npc_claim`/`inference` (nunca `fact`, nunca `confirmed`).
3. `appears_to_know` com `player_observation` → só `perception|suspicion`, `certainty != confirmed`.
4. Criatura tier 1/2/3: chaves acima do tier AUSENTES (não vazias); `revealed_cards` só com
   overlay do bestiário e nunca cartas em `variant_exclusive_cards`; tier 1 nunca revela cartas.
5. Facção com `intel_turn` antigo → `progress == null`, `intel_stale`, `stale_label` presente;
   `goal == ""` sem `knows_goal`.
6. Oculto vs inexistente: dois saves idênticos exceto pela entidade oculta → payloads
   byte-idênticos (sem diferença de contagem/versão).
7. Reveal canônico (`secret_revealed` do alvo + do segredo mapeado, ex.: `mon_rei_subterraneo`) →
   entidade aparece e o oráculo SPEC-206 permanece verde.
8. Mutação: injetar `hidden_traits`/campo novo no payload → `assert_no_private_fields` precisa reprovar.

## Jornadas Playwright sugeridas (autoria separada, fixture `web/e2e/fixtures.ts` já tem
`backend.dossiers`)

- Codex › Pessoas: lista → dossiê (Relação, "O que ele parece saber" com "Nada percebido ainda"
  quando vazio) → Esc volta sem fechar o painel → reload mantém o dossiê aberto.
- Marcadores "Novo"/"Atualizado" por `version` sem contador agregado de categorias bloqueadas.
- Bestiário nos 4 tiers; DOM sem `title`/`data-*` com texto de dossiê oculto.
- Corpo com `<img onerror>`/`<script>` renderizado como texto (mdLite).
- Endpoint novo com 500 → cai para o Codex antigo sem erro de console bloqueante.
- 1440 e split ~50%; teclado (setas na lista, Enter, Esc), alvo >= 44px, reduced-motion.

## Métricas

- `leak_count` = nº de casos com problema em `assert_no_private_fields` ou `assert_no_player_leak` → `= 0`.
- `tier_key_accuracy` = acerto de presença/ausência de chaves por tier (esperado 100%).
