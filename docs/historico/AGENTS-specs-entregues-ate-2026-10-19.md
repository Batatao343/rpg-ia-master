# Specs entregues por fase/sessão (até 2026-10-19)

> Parágrafo movido sem edição de `AGENTS.md`/`CLAUDE.md` § Desenvolvimento spec-driven
> na reestruturação do workspace. Estado atual: `scripts/spec_index.py summary`.

Specs: 2.5 `done`; 2.5b (dados mecânicos Valoria) `done` (smoke real 2026-07-14); 2.6 (structured events) `done`;
2.7 (rules engine) `done`; 2.8 (context builder) `done`; 3.1–3.4 `done` — **Fase 3 completa**;
4.1–4.6 + 4.1b `done` — **Fase 4 completa**; 6.1–6.5 `done` — **Fase 6 completa**;
7.1 (validadores+CI) · 7.2 (autoria/curadoria) · 7.3 (segredos de NPC) `done` —
**Fase 7 completa** (lint `services/content_validator.py` + CLI
`scripts/validate_content.py`; gate no `rag.py`; autoria em `docs/guias/AUTORIA.md`).
2026-07-06: fase 10 fatia local (hardening: `save_path` UUID, `schema_version`+
migrations, CORS/rate-limit/log) · fase 11 (contratos `-m llm_contract`, 9 verdes
no Gemini real) · mapa (interiores + `travel_times`) · NPCs 3 camadas
(`services/npc_layers.py` + `data/traits.json`) — todas `done`. Roteamento
multi-provider `done`. **Fase 5 (5.1 harness + 5.2 invariantes + 5.3 telemetria)
`done`** — `playtest/`. 2026-07-13: **ciclo de produto `done`** —
balanceamento-early-game ("O Saque" + tuning nível 1 + replan por região) ·
streaming-turno-sse (`POST /game/action/stream` + custo real no log `rpg.turn`) ·
polish-sessao (`GET /game/saves` + DELETE + chips mecânicos de combate +
export/busca da crônica + onboarding + mobile 390px).
2026-07-16: **8 specs `draft`** do playtest longo real (3×100 turnos, análise em
`docs/playtests/playtest-longrun-2026-07-14.md`): playtest-stop-gameover ·
combate-lifecycle · pos-saque-recuperacao · npc-fallback-sem-alvo ·
beats-visibilidade-ptbr · encontros-dedupe · polish-prosa · embeddings-provider
— aguardando aprovação. 2026-07-17: **criação imersiva `done`** —
onboarding-valoria (wizard 5 passos + `data/onboarding.json` +
`GET /data/onboarding`) · inicio-personalizado (`POST /game/prologue` + seed de
arco pessoal/NPCs/cena no `/game/new`; limites de schema viraram truncagem em
Python + `StartScenarioIn` estrito na borda). **792 testes offline.**
2026-07-18: **8 specs do playtest longo `done`** (embeddings-provider Jina ·
playtest-stop-gameover · combate-lifecycle · pos-saque-recuperacao ·
npc-fallback-sem-alvo · beats-visibilidade-ptbr · encontros-dedupe · polish-prosa)
+ archivist fix + NPC relocável. 2026-07-19: **refatoracao-sistema-classes `done`**
— 10 classes → **5 Posturas diante do Abismo** × 3 subclasses; recurso **Entropia**
(pool único, recompõe integral no descanso) + **Carga do Abismo** (longo prazo);
gatilhos/regras/consequências por classe 100% Python (`combat_mechanics`); migração
v3; HUD Entropia/Carga. **Árvore RICA `done` (arvores-habilidade-classes, autoria
Fable):** 101 habilidades (41 ativas + 35 passivas + 25 utilitárias) via
`scripts/gen_classes_v2.py`; `ability_kind` + `player_passives` + 5 triggers de
Entropia/Carga; utilitárias no contexto do storyteller (gate determinístico);
selo ✦/⚒ no HUD (ver [docs/design/CLASSES.md](../design/CLASSES.md)).
2026-07-19 (sessão 20): **revisão pós-épico** — 3 bugs de fiação de classe
corrigidos (taunt/Transformação/Purga estavam mortos; `HANDLED_KINDS` +
teste anti-órfão) · cache runtime isolado em `data/runtime/` (fim do `git
checkout` manual) · harness com `--class` + telemetria de Entropia/Carga
(baseline capturado; tuning dos 8 knobs `[BALANCEAR]` adiado por dado
insuficiente) · traits 40→80 · curadoria da Rede Carmesim (over-share suavizado +
reindex). **945 testes offline.** Próxima: tuning real dedicado + tiers 5+;
Auditoria de mecânica-morta: gating narrativo por classe APOSENTADO
(morto desde a deleção do Ruler; mecânica é Python) · weather GLOBAL fiado
(trigger determinístico em `advance_weather` — Tempestade de Éter/Noite Sem
Estrelas varrem e impactam o jogo). itens-vivos-e-luz: passiva de item fiada
(`item_passives` em `player_passives`), item ativo ofensivo
(`use_item_in_combat` com alvo), **sistema de LUZ** (`light_level` — escuro
penaliza percepção/acerto, tocha anula) + **+22 itens** ancorados na lore.
**970 testes offline.** Fase 8 (arte) vs 10b (público) segue adiada.
2026-07-20 (sessão 22): **5 specs do playtest longo** — agente-curioso-entropia
(perfil de teste usa habilidade + telemetria de GASTO de Entropia; destrava
balanceamento) · npc-in-scene-viagem (fuga reseta cena) · aliados-em-combate
(amigo em cena vira aliado transitório + perfil `recrutador`) · loot-exploracao
(explorar recompensa via escada de raridade + baús curados) — 4 code `done`;
letalidade-early-game-v2 `approved` (medir→decidir). **1001 testes offline.**
