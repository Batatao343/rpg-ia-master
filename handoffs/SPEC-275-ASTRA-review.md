# SPEC-275 — revisão independente Astra (Opus)

**Veredito:** `APPROVED` com 4 correções aplicadas nesta revisão.
**Data:** 2026-10-19 · **Branch:** `spec-275` (rebaseada sobre `main` 1ec47be) · **Commit revisado:** `100a392` (→ `78d07ce` após rebase)

## Achados e correções

| # | Gravidade | Achado | Correção |
|---|---|---|---|
| 1 | média | **R5 anulado pelo `esconder`.** Na quebra, o inimigo não-covarde era revelado e marcado `_forced_attack`, mas `_enemy_offensive_card` ainda podia devolver `esconder` (ex.: `bst_mimetismo_morto`, custo 0, frequência por turno). Ele se escondia de novo em vez de atacar. | `enemy_declaration` passa `allow_hide=not forced_attack`. Teste `test_forced_attack_is_not_cancelled_by_hide_card`. |
| 2 | média | **Tokens técnicos chegavam à narração.** `"conflict_stalemate_broken: …"`, `"enemy_declaration_fallback: ataque básico."` e o motivo de recusa (`"… é hostil — Carta de suporte recusada."`) iam para `out["logs"]`. Esse texto vai cru ao narrador LLM e aparece em bullets no laboratório de combate. | O guard devolve eventos estruturados `{event, actor_id, outcome, log}`. Só `log` em pt-BR entra na prosa. `run_round` expõe `out["stalemate_events"]`. Fallback de inimigo vira `out["enemy_fallbacks"]`, propagado de `resolve_turn` para a rodada (antes era descartado no merge), mais `logger.info`. Testes `test_run_round_stalemate_break_is_structured_and_narratable` e `test_enemy_refused_declaration_falls_back_once` reforçado. |
| 3 | média | **R6 contaminava `--real`.** `--seed` tem default 0, então o `game_id` virou determinístico em **toda** campanha. Em `--real`, a memória vetorial da sessão fica fora de `saves_playtest` (`data/saves_memory/{game_id}`). Duas campanhas reais com o mesmo perfil, seed, classe e nível (ex.: matriz A × B) herdariam os fatos uma da outra. | `_build_initial_state(random_game_id=use_real_llm)`: id por seed só no mock, onde o LLM é reproduzível e a memória é efêmera. Teste `test_real_llm_campaign_keeps_random_game_id`. |
| 4 | baixa | Faltava teste de persistência do contador. | `test_stalemate_counter_survives_save_load_roundtrip`, roundtrip JSON. |

## Pontos atacados sem defeito

- **R1 / `esconder`:** a exceção se justifica (Mimetismo Morto da matriz A), já filtrada quando o ator está oculto. Nenhum arquétipo fica sem ação legal: sem Carta ofensiva, cai em ataque básico. O fallback R3 revalida **uma** vez no bloco final de `_invalid_target_reason` (sem recursão). Uma segunda recusa só registra o motivo e o turno passa.
- **R2:** como R1 descarta toda Carta de suporte, o redirecionamento ao próprio ator só vale para `esconder`. Antes da spec, as Cartas de suporte do inimigo (protecao/buff_*/reposicionar, 9 de 38 no bestiário) já eram sempre recusadas, porque miravam o jogador. Não há regressão, mas esse conteúdo segue sem uso (follow-up de conteúdo/IA, fora de escopo). O suporte a aliado do inimigo continua pelo fluxo tático `support` (sem Carta), que não foi tocado.
- **R5:** é determinístico (sem RNG). O contador `scene["stalemate"]` persiste com a cena e zera quando muda a Vitalidade, o status, os Ferimentos ou os flags dead/fled/surrendered. Na quebra, o covarde segue o mesmo caminho da fuga tática (`fled` + `status=fugiu`). `combat_should_end` → "todos os hostis fugiram". A XP só sai para `newly_dead` (fugitivo não dá XP, como na fuga existente). O resumo canônico lista `fugitivos`. Em lutas lentas legítimas (7 rodadas seguidas sem dano), a quebra é benigna: o não-covarde já atacaria, e o covarde que desiste é coerente com o perfil. Rendido/fugido não age (`_can_act`). Limite aceito: se o **jogador** fica oculto e passa a vez indefinidamente, nada termina o conflito. Mas isso é escolha do jogador, não impasse do motor.
- **R6:** `_seeded_random_factory` só é instalado em `run_campaign` (playtest) e é restaurado no `finally`. `api.py` usa `uuid4`, e nenhum caminho de produção importa o runner.
- **R7:** não implementado. Ele é opcional e o aceite R1–R4 era medido sem ele.

## Evidência (pós-correções)

- `uv run pytest`: **3.914 passed, 229 skipped, 15 deselected**. As 2 falhas restantes são `test_project_index` (índice stale, esperado com código novo); após o rebuild do índice no checkout limpo, ficam verdes (ver commit seguinte). Ruff verde.
- `evals.core.governance check`: 11 datasets válidos. `evals run --suite encounter_manifest --suite state_rules`: `passed`, `hard_failures=[]`.
- `playtest run --all --turns 3`: 14 perfis, 0 erros, 0/0 violações.
- `playtest run --profile combate --turns 200`, 3× (seeds 21–23, saves/runtime isolados): **0/0** violações nos três. Baseline `main`, mesmo comando e seeds: **138**/0/0 (bug reproduzido em 1 de 3).
- **Smoke real §6 (DeepSeek, 32 chamadas, 2 cenários):**
  1. Viúva do Lodo + Cervo Afogado ocultos, com as Cartas ofensivas gastas. "Ataco a Viúva do Lodo." ×3 mais "Procuro…": os inimigos atacam da ocultação, o jogador vai de 11 → 0 na 1ª rodada, depois Última Ação e queda. A narração descreve golpes reais, sem rodada inerte.
  2. Jogador também oculto, com K forçado a 0: a quebra é narrada de forma coerente ("A paciência deles se esgota… a Viúva rompe a superfície"). Nenhum token técnico aparece na prosa.
- **Letalidade:** o smoke 1 confirma que inimigos antes inertes agora matam. Mortes em 200 turnos `combate`: branch 2/14/9 vs main 0(travado)/9/11. Não é comparável por seed, porque o `game_id` da main é aleatório. Encaminhar à SPEC-049.

## Follow-ups (não bloqueiam)

1. Cartas de suporte do bestiário seguem sem uso pela IA. Uma spec de IA/conteúdo pode deixar o inimigo usá-las em si ou num aliado.
2. Rebalanceamento de letalidade: SPEC-049.
