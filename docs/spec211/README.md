# SPEC-211 — Evidência: dossiês do Codex e do Bestiário

Status: `in-progress`. Implementação e testes entregues; pendentes: autoria do eval de leak
(`handoffs/SPEC-211-eval-authoring.md`), revisão Sol independente e captura em save real.

## O que mudou
- Backend (somente leitura, zero LLM, sem migração, `SCHEMA_VERSION` intacto):
  `services/dossiers.py` (build_dossiers sobre `discovery.player_codex`, já projetado/fail-closed pela
  SPEC-206), `services/dossier_visibility.py` (modelos `extra="forbid"` = allowlist,
  `assert_no_private_fields`, `leak_view` p/ o oráculo `assert_no_player_leak`), rota aditiva
  `GET /game/codex/dossiers` (`Cache-Control: private, no-store`). `GET /game/codex` e rotas de crônica inalterados.
- Frontend: `components/tabs/` (`DossierBrowser`, `DossierDetail`, `CertaintyBadge`, `BestiaryTab`,
  `useDossiers`, `tabs.css`), `src/dossiers.ts` (marcadores novo/atualizado por `version` do servidor,
  `safeStorage`), `CodexTab`/`ContextSurface` consomem dossiês com fallback ao Codex antigo.

## Testes
- Python: `tests/test_dossiers.py`, `tests/test_dossier_leak.py`, `tests/test_dossiers_api.py` (60).
- Node: `web/tests/dossiers.test.mjs`. Playwright (executor): `web/e2e/dossiers.spec.ts` (5);
  `workspace-shell`/`critical-journeys`/`effects` seguem verdes (fixture ganhou a rota `/game/codex/dossiers`).

## Decisões (defaults do §8) e desvios
- D1: Facções e Crônica seguem como seções do Codex; D2: `appears_to_know` só de `player_observation`
  (perception/suspicion, nunca fact/confirmed); D3: "visto" em `localStorage`; D4: arte só de asset público.
- Desvio: `PeopleTab`/`FactionsTab`/`ChronicleTab` NÃO foram extraídos do `Hud.tsx` (o shell da SPEC-204
  já os monta; extração só moveria código e arriscaria conflito com 209/210). A Crônica mantém busca/export e
  navegação por capítulo existentes; `chronicle_index` está na API para vínculo `entity_id`.
- Desvio: `encounters[]` usa `primeiro contato` (created_turn) + eventos canônicos públicos
  (npc_killed/quest_*); `encounter_id`/`combat_result` por NPC não é persistido por SPEC-203, então não é preenchido.
- Arte curada é estática (sem URL assinada): "refetch único" da R9 não se aplica; `onError` cai no placeholder.
- Cartas/resistências reveladas vêm do overlay `bestiary_knowledge` (legacy owner), como já ocorria no combate.

## Notas de compatibilidade
- Pessoas mantém a lista legada do HUD enquanto o servidor não devolve NPC em dossiê (endpoint indisponível ou
  nenhum NPC visível); `_npcs_block` agora também omite NPC `hidden/secret` não revelado (fail-closed SPEC-206).
  A jornada F07 (`critical-journeys`, protegida) depende desse caminho legado: ao adaptá-la ao dossiê, o
  fallback pode ser removido.
- Payload com forma inesperada em `/game/codex/dossiers` = indisponível (fallback ao `GET /game/codex`).
- Suíte final: pytest exit 0; Node 107/107; Playwright (chromium, 1 worker): dossiers + workspace-shell +
  critical-journeys 39 passed / 1 flake de Google Fonts (F22, rede); effects codex.entry.reveal 4/4.

## Revisão Sol independente (17/10)
Parecer: `handoffs/SPEC-211-SOL-independent-review.md`. Correções com teste:
- JSON da API mandava `description/max_hp/behavior/loot/revealed_*: null` acima do tier (R6 exige chave
  ausente): rota agora usa `model_dump(exclude_unset=True)` (`test_api_json_criatura_tier*`).
- Cartas/resistências reveladas liam o overlay do dono LEGADO também em perfil com banco (escopo
  compartilhado entre contas): fora do `legacy` o dossiê não revela nada do overlay
  (`test_perfil_com_banco_nao_le_overlay_legado_compartilhado`).

Evidência em save realista (API real legacy + MockLLM, 6 turnos com NPC e combate), em `evidence/`:
`dossiers_realistic_save.json` (allowlist e `assert_no_player_leak` = `[]`), `split50-1440-codex-npc.png`,
`full-1440-bestiario.png`, `full-1440-bestiario-after-reload.png` (dossiê reaberto após reload); axe
WCAG 2 A/AA no painel = 0 serious/critical nos dois modos.
