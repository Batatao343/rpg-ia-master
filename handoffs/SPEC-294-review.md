# SPEC-294 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (revisão independente) · **Data:** 2026-10-19 · **Commits revisados:** `1aae65a`, `2fadf55` (sobre `main` `0712b29`)

## Escopo

`services/faction_display.py` (`_fold`, `_oracle_regex`, `concealed_name_problems`),
`persistence.py` (`backfill_enemy_ids`, `_rewrite_refs`, `_legacy_archetype` e a chamada em
`_raw_to_state`), dataset `evals/datasets/regression/player_knowledge.jsonl` (5 casos
`faction-label`) + `evals/manifest.lock.json`, testes `tests/test_spec294_followups.py`
e ajustes em `test_spec293_rotulo_faccao.py`/`test_eval_player_knowledge.py`.
Conferi R1–R7 contra o código e as interações com `encounter_manifest.normalize_combat`/
`build_manifest`/`_participant`, `agents/combat.py` (`_sync_enemy_knowledge` respeita
`archetype_id` já preenchido; `_killer_identity`/`species_label_for` caem no nome como
antes), `services/discovery.normalize_bestiary_id` (mesmo fallback por slug do nome),
`bestiary_knowledge._archetype_id` e o caminho de banco (`game_serialization.
deserialize_game_state` → `_raw_to_state`, logo coberto).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/faction_display.py:200` | `_fold` usa **NFKD**, que transforma símbolos sem `\w` em letras (`™`→`tm`, `℡`→`tel`, `ⓘ`→`i`). A projeção roda no texto original, onde esses símbolos são fronteira, e troca o nome; o oráculo roda no texto dobrado, onde a fronteira some, e **não acusa**. Reproduzido: `"o Iniciado da Chama Azul™ ataca"` → projeção `"o Iniciado™ ataca"`, oráculo `[]`; idem `"ⓘIniciado da Chama Azul"`, `"…Azul℡"`. Viola R2 ("não perde variante que a projeção trocaria") e é regressão frente ao oráculo de substring antigo, que pegava. Impacto real baixo (exige superfície sem projeção **e** símbolo de compatibilidade colado ao nome). | Trocar `NFKD` por `NFD` em `_fold` (só tira acento, não decompõe compatibilidade). Fuzz com NFD: 0 perdas em ~2.000 variantes × 24 fronteiras. Acrescentar `™`/`ⓘ` aos parametrizados de R1 e ao corpus de R2. |
| P2-2 | P2 | `persistence.py:902-916` | `_rewrite_refs` reescreve **todo** item de lista igual ao nome e todo valor em chave `*_id`/`id`/`ids` na subárvore `combat`. Não achei campo de exibição em lista nem `*_id` que guarde nome com outro sentido (`combat.result.participants[].species_label`, `death_context`, `phase_violations` ficam intactos), então hoje é correto; mas é uma heurística por igualdade de string, sem lista de caminhos. Também: `events[].event_id` do manifesto continua o hash do `participant_id` antigo (opaco, sem vazamento; só a idempotência de `apply_composition` para o mesmo evento/rodada deixaria de casar). | Opcional: documentar a heurística no docstring e, se aparecer campo novo de lista com nomes, restringir a caminhos conhecidos. Sem ação agora. |
| P2-3 | P2 | `persistence.py:946` | `setdefault("archetype_id", …)` ignora um `archetype` legado: como `_archetype_id` prefere `archetype_id`, um inimigo legado com `archetype` e sem `archetype_id` passa a usar a chave do bestiário/nome. Não achei produtor de `archetype` em inimigos atuais. O overlay de conhecimento gravado antes sob o nome com sufixo (`"Iniciado … 2"`) fica órfão — melhora deliberada da R5. | Opcional: `fixed.setdefault("archetype_id", enemy.get("archetype") or _legacy_archetype(name))`. |
| Nota | — | `services/faction_display.py:_name_regex` | O fuzz mostra que a projeção não tolera acento no sufixo de plural (`"…Azulês"`), e o oráculo acusa. É a direção segura (mais estrito) e não é português real; só registro. | — |

Sem P0/P1.

### Conferido e ok

- **R1**: os 8 positivos e 6 negativos da spec batem; `(?<!\w)`/`(?!\w)` sobre o texto dobrado; conectores sem plural, igual à projeção; `_text_of` mantém o separador ` ¦ ` (não casa entre campos).
- **R2 (fuzz próprio)**: 9 nomes ocultos × ~30 variantes (caixa, acento, `\s`/`\n`/`\t`/NBSP/em-space/hífen, plural) × 24 caracteres de fronteira. Sem fronteira exótica: **0 perdas** e o texto projetado nunca é acusado (exceto o sufixo acentuado da Nota). As únicas perdas são P2-1.
- **R3**: `governance check` válido (11 datasets), lock regenerado. Mutação: projeção desligada → falham `pk.faction.concealed_creature_label`, `pk.oracle.concealed_faction_name` e `…_plural_spacing`. Ramo (e) desligado → falham os dois casos de oráculo. Os casos limpos (`word_boundary`, `revealed`) esperam `[]`. A régua prova a detecção.
- **R4/R5**: id `enemy_legacy_<posição>` determinístico, pula colisão, não toca inimigo com id, devolve o mesmo objeto se nada muda (idempotente), não muta a entrada (cópia profunda dos inimigos, reconstrução da subárvore `combat`), roda antes de `_normalize_combat_on_load`, de modo que o manifesto `legacy_migrated` já nasce com o id opaco. `positions`, `engaged_with`, `hidden_from`, `participants[].participant_id`, `order` e perseguidores são reescritos; `name`/`species_label` ficam.
- **R6**: coberto por teste (`format_response` + `valid_targets`, sem nome canônico em ids).
- **R7**: registrado na spec (laboratório mantém nomes canônicos).
- Sem structured output/LLM novo, sem segredo em log; `evals/` protegido só com dataset + lock regenerados pelo comando oficial.

## Pendências

- P2-1: trocar NFKD→NFD em `_fold` e acrescentar 2 casos (barato; recomendo antes do pouso, sem mexer no dataset).
- P2-2/P2-3: opcionais.
- Publicar o dataset exige aprovação do environment `eval-governance`.

## Comandos rodados

```text
git diff 0712b29..HEAD --stat / diffs de faction_display.py, persistence.py, dataset, lock, testes
bash scripts/dev/py.sh -m pytest -p no:cacheprovider tests/test_spec294_followups.py tests/test_spec293_rotulo_faccao.py tests/test_eval_player_knowledge.py tests/test_encounter_manifest.py tests/test_player_knowledge.py tests/test_combat_targeting.py tests/test_hardening_persistencia_sse.py tests/test_dossier_leak.py → 180 passed
bash scripts/dev/py.sh -m evals.core.governance check --root . → eval governance valid: 11 dataset(s)
scratchpad probe2.py (fuzz projeção × oráculo) → 0 perdas sem fronteira exótica; perdas só com ™/ⓐ (P2-1)
scratchpad p3.py → reprodução de P2-1 (™, ⓘ, ℡)
scratchpad p4.py (fuzz com _fold em NFD) → 0 perdas
scratchpad probe_eval.py (run_eval com mutações: projeção off / oráculo (e) off) → casos novos falham como esperado; base verde
```
