# SPEC-275 — evidência

Decisão do dono (2026-10-18): "Corrige com R5". Default do R5: após 6 rodadas
seguidas sem dano, inimigos `covarde*` fogem; os demais perdem a ocultação e
atacam na rodada seguinte (determinístico, evento `conflict_stalemate_broken`).

## O que mudou
- `conflict_orchestrator._enemy_offensive_card`: só Carta de ataque (ou `esconder`, Mimetismo Morto) (R1).
- `enemy_declaration`: Carta de suporte mira o próprio ator (R2).
- `conflict_turn._resolve_attack_step`: declaração de inimigo recusada cai UMA vez em ataque básico, log `enemy_declaration_fallback`; jogador mantém recusa sem custo (R3). R4 resolvido por R1 (testado).
- `_stalemate_guard` (R5): contador em `scene["stalemate"]` (persistido com a cena; ausente = 0; sem bump de schema). Fingerprint só de dano/estado vital, pois esconder/revelar em ciclo é o impasse.
- `playtest/runner`: `campaign_game_id` (uuid5 de perfil/seed/classe/nível) e `_seeded_random_factory` (`random.Random()` sem seed deriva do `random` global semeado) (R6). Produção (`api.py`) intocada, ids seguem aleatórios.
- R7 (perfil `combate` procurar/fugir): NÃO implementado — as 10 corridas ficaram limpas sem ele e a spec o define como opcional/exercício.

## Evidência
- `tests/test_spec275_stalemate.py` (10) + 1 em `test_playtest_harness.py`; vistos falhando antes do código.
- 10x `playtest run --profile combate --turns 200` (seeds 0-9, saves/runtime isolados e limpos): 0 erros, 0/0 violações, 0 `combat.no_progress`.
- `--seed 0 --turns 60` 3x: JSONL e summary idênticos (ignorando latência/save_path).
- `--all --turns 3`: 14 perfis, 0 erros/violações. Suíte completa exit 0; ruff verde; `evals.core.governance check` ok; eval `encounter_manifest`/`state_rules` passed.

## Limites
Letalidade efetiva sobe (inimigos antes inertes agora atacam) — medir via SPEC-049.

## Revisão Astra (2026-10-19) — APPROVED
Corrigidos: quebra R5 anulada por `esconder`; tokens técnicos (`conflict_stalemate_broken`/`enemy_declaration_fallback`/motivo de recusa) fora da prosa — agora `out["stalemate_events"]`/`out["enemy_fallbacks"]` estruturados; `game_id` por seed só no mock (em `--real` a memória vetorial ficaria compartilhada entre campanhas de mesmo seed). Smoke real §6 (DeepSeek, 32 chamadas) verde. Detalhes: [handoff](../../handoffs/SPEC-275-ASTRA-review.md).
