# SPEC-202 — evidência (interlocutor automático narrador × NPC)

## O que mudou
- `services/interlocutor.py` (novo, Python puro): `pre_classify` (meta ao narrador /
  OOC / "sobre <NPC>" sem verbo de fala / descrição de cena → STORY sem CLASSIFY),
  `post_classify` (vocativo, verbo de fala + alias, aspas + alias, alvo do CLASSIFY
  só se dito pelo jogador e resolvido em cena, conhecido fora de cena, papel
  genérico só em assentamento, continuidade ≤ 2 ações, ambiguidade → narrador),
  `speaker_for_turn`/`response_speaker` (R9).
- `agents/router.py`: `pre_classify` após o gate Jev; prompt CLASSIFY lista NPCs em
  cena + regra "pergunta ao narrador = STORY" (mesma chamada, `RouterDecision`
  intacto); **removido `chosen = decision.target`**; transitórios
  `interlocutor_reason`/`mediated_subject_id` zerados em toda rota; falha do
  CLASSIFY → `classify_fallback`.
- `agents/npc.py`: nome sem ficha só gera NPC com `generic_role_spawn`; senão delega
  ao narrador (`npc_fallback_hint`). Caminhos "não está aqui"/morto marcam
  `npc_absent_known`. Fala grava `active_npc_name` = chave canônica.
- `agents/storyteller.py`: `_mediation_clause` (só `visible_npc_view`, nunca
  `hidden_traits`) + `_guard_mediation_secret` (`find_unrevealed` → parágrafo neutro
  + `narrative_rejections: mediation_secret:<id>`).
- `turn_finalizer`/`action_guard` escrevem `last_speaker`; `finalize_outcome` inclui
  `speaker` (fora do `receipt_id`); `record_history` grava `speaker_kind/id/name`;
  `history_page` deriva rótulo para linhas legadas; `GameResponse.speaker`.
- Save **aditivo, sem bump** (`SCHEMA_VERSION` segue 8): `last_speaker` default `{}` no
  load; linha legada recebe rótulo derivado na leitura (NPC legado sem id).
- Web: `Speaker` em types, `roleLabel(role, type, speaker)`, `speakerFromHistory`,
  StoryLog mostra o nome do NPC (sem seletor; composer/voz intocados).

## Testes
- Novos: `tests/test_interlocutor.py` (29), `tests/test_router_interlocutor.py` (17),
  `tests/test_mediation_secret.py` (5), `tests/test_speaker_contract.py` (7),
  `web/tests/speaker.test.mjs` (4), `web/e2e/interlocutor-speaker.spec.ts` (390/1440).
- Fixture `tests/fixtures/save_v8_pre_spec202.json`: save real gerado pelo jogo
  (MockLLM) e rebaixado ao formato v8 (sem `last_speaker`/`speaker_*`).
- `evals run --suite routing`: route/target accuracy 1.0, sem hard failures.
- Playwright: `critical-journeys` 16/16 + speaker 2/2. `npm run build` verde.
- Playtest offline `npc_only`/`diplomatico` 10 turnos: 0 erro, 0 violação. NPCs
  criados só via `generic_role_spawn` em Nova Arcádia ("guarda", "taverneiro");
  "Valerius"/"Daruun" (fora do estado) não foram criados.
- Capturas: `speaker-390.png`, `speaker-1440.png`.

## Tabela caso → rota → speaker → invokes (CLASSIFY fake)
Ver `handoffs/SPEC-202-eval-authoring.md` (mesma tabela, 18 casos; meta/descrição = 0).

## Smoke real (DeepSeek, API legacy, `RPG_NO_MOCK=1`)
Game `d8ef6d5c-0b2e-4928-959a-bbaad5f2b77e` (Brekmar, Brunna + Velha Magda em cena),
`simulated=false`, 10 requests DeepSeek, custo estimado US$ 0,0139:

| entrada | speaker | requests do turno |
|---|---|---|
| Brunna, você viu o barco? | npc `npc_mv_brunna_ponte_alta` / direct_address | 3 |
| Pergunto ao narrador o que a Velha Magda sente | narrator / meta_to_narrator | 1 (0 router) |
| E você? | npc Brunna / continuity_last_speaker | 3 |
| Falo com Halveth | narrator / npc_unknown_absent (nenhum NPC novo) | 2 |
| Descreva quem está aqui | narrator / scene_description | 1 (0 router) |

Uma rodada anterior idêntica (5 turnos, ~10 requests) mostrou o narrador dizendo que
Magda "nem está aqui" na mediação; a cláusula passou a incluir `presente na cena`.
Total do smoke: ~20 requests, < US$ 0,03.

## Limites / pendências
- Suíte completa offline exit 0 após a conversão aditiva (revisão Astra); `test_eval_state_rules` verde.
- Revisão Astra independente: APPROVED com 2 correções (sem bump; falso positivo "mestre <nome>").
- Concordância de pronome na prosa livre não é gate (P4).
