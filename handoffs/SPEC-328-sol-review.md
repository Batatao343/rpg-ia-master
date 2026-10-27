# SPEC-328 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (pouso com `off` bloqueado só por P1-1, que é trivial; P1-2/P1-3 bloqueiam `shadow`/`on`)
> **Revisor:** Opus / Sol · **Data:** 2026-10-27 · **Commit revisado:** `79c391ea`

## Escopo

`git diff main...HEAD` da branch `spec-328` (1 commit, 16 arquivos): `services/card_piles.py`,
`services/card_deck_round.py`, `services/cards.py`, `services/conflict_orchestrator.py`,
`services/conflict_turn.py`, `services/content_validator.py`, `agents/combat.py`, `api.py`,
`data/cards/basicas.json`, os 4 testes novos, a arena (`docs/spec328/`) e o §5b da spec.
Fora do escopo: front (SPEC-334), jornadas e2e (autoria separada), suíte completa.

Pontos pedidos pelo coordenador:

- **(a) `off` byte a byte:** o motor, a narração e o save ficam iguais. `deck_mode()` devolve `""`
  sem `_piles`; `refusal`/`shadow`/`reaction_gate`/`reaction_commit` viram no-op; o nó só cria
  `pilhas` com flag != `off`; `use_card` só ganha `| deck` (vazio em `off`);
  `TurnDeclaration.jogadas` vazio não muda `acao` e o playtest serializa com `exclude_defaults`.
  `all_cards()` passa a ter 15 básicas, mas nenhum consumidor em `off` muda: `cards_for_class`
  as exclui, a subclasse vem de `subclasse` (vazia nas básicas) e o MockLLM acha `arc_vazao` antes
  de `bas_arc_vazao` pela ordem dos arquivos. **Exceção:** o schema CLASSIFY (P1-1).
- **(b) save/load:** `persistence` grava `combat` inteiro e `normalize_combat`/`_rewrite_refs` não
  tocam `pilhas`. O replay por `seed:embaralhos` está certo. O teste de round-trip, porém, só faz
  `json.dumps` do dict: não passa por `save_game_state`/`load_game_state` nem pelo spawn real do
  nó (P2-4). Combate antigo sem `pilhas` está coberto (`test_combate_antigo_sem_pilhas_segue_no_modo_atual`).
- **(c) recusa sem efeito colateral:** OK. `plan_plays` trabalha numa `deepcopy`. A recusa
  retorna em `run_round` antes de `reset_card_usage`, `reset_entropy_turn`, `tick_boiler` e de
  qualquer uso do `rng`. O nó devolve a rodada, preserva `flee_attempts` e não chama
  `begin_round`. Testado no orquestrador e no nó.
- **(d) Pacto via `on_channel`: é bug** (P1-2, com reprodução abaixo).
- **(e) determinismo:** OK. A semente é `crc32(game_id:epoch:action_count)` e cada embaralho usa
  `Random(f"{seed}:{n}")` com `n` persistido. O RNG global do combate fica intocado.
- **(f)** `test_log_event_registry.py` e `test_no_silent_except.py` passam. O único `except`
  novo (`card_deck_round.py:76`) faz `logger.debug(..., exc_info=True)` e não é silencioso.
  Nenhum evento de log novo.
- **(g) arena:** ver Pendências.

Sem segredo em log, sem mudança em `evals/`. O guard de FallbackLLM no parser está presente e testado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:1147` | `extra_card_ids` entra no schema `PlayerMove` **sempre**, inclusive em `off`. O request CLASSIFY (tool schema e tokens) muda para todo jogador, e o provider pode preencher o campo. O valor é ignorado em `off`, mas isso quebra o "byte a byte" do critério (a). | Adicionar o campo só quando `piles is not None`, no mesmo padrão do `object` da SPEC-325 R14 (subclasse/`create_model` condicional). Teste: em `off`, o schema enviado não tem `extra_card_ids`. |
| P1-2 | P1 | `services/card_deck_round.py:130` | Pacto do Abismo dispara `_entropy_event(on_channel)`, que só casa com o Arcanista (`gain 2`, `charge_per 1`, `per_turn_cap 1`). Reprodução (ataque com 1 Fôlego emprestado, Entropia 8): **Arcanista termina com Entropia 8 e Carga +1, ou seja, o Pacto sai de graça**; Sangromante/Devoto pagam −2 e não ganham Carga. Além disso, o Pacto gasta o `per_turn_cap` e a canalização da própria Carta do Arcanista na rodada não dispara mais. R8 pede "tentação com preço real… pode disparar Carga/Abismo" para todas as Posturas, e hoje ninguém paga Carga a mais. | Não usar `on_channel`. Definir a consequência do Pacto explicitamente para todas as classes (ex.: `+1 abyss_charge` por Fôlego emprestado via helper em `combat_mechanics`, ou só o débito de Entropia, sem gatilho). É decisão do dono [D?] de R8; registrar no §5b. Teste parametrizado pelas 5 Posturas. |
| P1-3 | P1 | `services/card_piles.py:113-114` + `agents/combat.py:1746` | Em `shadow` (e em `on`), `start_piles` chama `migrate_deck(player)`, que **reescreve `prepared_cards`** (básicas + até 24 ids) na ficha persistida. Em `shadow` isso muda o catálogo do prompt CLASSIFY, o atalho por nome do parser e `api._cards_block`: o resultado muda, violando R17. Se o dono voltar o flag para `off`, a ficha fica com `prepared_cards` acima do limite de Preparação e com básicas usáveis no modo antigo (rollback sujo). | Em `shadow`, montar as pilhas a partir de uma cópia (`migrate_deck(deepcopy(player))`) sem tocar a ficha. Em `on`, manter `prepared_cards` original e derivar `set(deck)` só onde R4 exige, ou guardar `prepared_cards_pre328` para rollback. Teste: `shadow` não altera `player`. |
| P2-1 | P2 | `agents/combat.py:1094-1106` | O atalho por nome casa substrings sobrepostas. "uso Vazão Controlada" vira `jogadas=[arc_vazao, bas_arc_vazao]` (reproduzido): o jogador joga 2 cartas e paga 2 Fôlego sem querer. | Resolver sobreposição: o match mais longo vence e se descartam matches contidos em outro intervalo já aceito. Teste com Vazão/Vazão Controlada. |
| P2-2 | P2 | `services/card_deck_round.py:97-132` + `services/conflict_turn.py:102` / `conflict_scene.py:75` | Cada jogada roda `resolve_turn`, que chama `reset_turn_budget` e zera `pos["guarding"]`. A manobra `guardar` (custa 1 Fôlego em `on`) seguida de outra jogada perde a Guarda. Gatilhos "por turno" do jogador também rodam N vezes por rodada. | Resetar o budget/guarda só na 1ª sub-jogada (flag em `resolve_turn` ou guardar/restaurar `guarding`). Teste "guardar + golpe mantém Guarda". |
| P2-3 | P2 | `services/card_deck_round.py:140-146` | No reembolso (Carta não resolveu depois do Pacto), a Entropia e o Fôlego voltam, mas o efeito do `_entropy_event` não é desfeito. Para o Arcanista, o resultado líquido é +2 Entropia e +1 Carga. | Some com P1-2; senão, aplicar o gatilho só depois de a Carta resolver. |
| P2-4 | P2 | `tests/test_round_multi_play.py:234` | O round-trip "no meio do conflito" é só `json.dumps` do dict. Faltam: (i) spawn real do nó criando `pilhas` com a semente derivada; (ii) `save_game_state` → `load_game_state` (perfil legacy) no meio do conflito, seguido de outra rodada pelo nó, com mão/monte idênticos a uma execução sem reload; (iii) mesma coisa pela API (`/game/action` com `jogadas`). | Adicionar os 3 testes (critério (b) do coordenador e R16). |
| P2-5 | P2 | `agents/combat.py:2072` (`_canonical_player_action`) | `last_player_action` (contrato do harness) reflete só `jogadas[0]`. O playtest/evals não enxergam a 2ª carta em diante. | Incluir `plays: [...]` no contrato com `on` (aditivo) ou registrar no §5b como dívida da SPEC-334. |

## Correções aplicadas

Nenhuma até aqui (revisão inicial).

## Pendências

- **Arena (g):** a causa principal é a economia de ações, não o detalhe da derivação de R6.
  Com Fôlego 3, quase tudo custa 1: as básicas têm `custo_folego: 1` explícito, `attack` custa 1
  e R6 manda "comum → 1". O herói faz ~3 ações por rodada contra 1 dos inimigos, que seguem com
  `enemy_declaration`. A tabela confirma: Fôlego 1 reproduz o `off`. Some-se a isso P2-2 (cada
  jogada é um "turno" completo, com reação e gatilhos). Para calibrar, as alavancas são: ataque
  básico/golpe a 1 com as demais cartas de dano a 2 (derivar 2 para `dano_base ≥ 5`, não `≥ 8`),
  ou `FOLEGO_BASE = 2`, ou esperar a pressão inimiga da SPEC-329. Não bloqueia o pouso em `off`;
  é decisão do dono (critério de aceite da arena segue aberto).
- Status da spec segue `in-progress` (arena + flag `on` só com SPEC-334). Não promover a `shadow`
  no staging antes de P1-2/P1-3.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_card_piles.py tests/test_deck_migration.py tests/test_round_multi_play.py tests/test_api_jogadas.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_conflito_cartas.py tests/test_mecanica_orfa.py tests/test_conflito_autoria_bestiario.py tests/test_balance_classes_v4_runtime.py tests/test_spec285_lethality.py tests/test_classes_refactor.py tests/test_bug_combate_modificadores.py tests/test_combat_simulator.py tests/test_conflito_autoria_cartas.py tests/test_tiers_5_plus_content.py → 323 passed
probe (scratchpad, MockLLM): Pacto 1 Fôlego em ataque, Entropia 8 → Arcanista 8 / Carga 1; Sangromante 6 / 0; Devoto 6 / 0
probe: _parse_turn_declaration("uso Vazão Controlada", piles on) → ['arc_vazao', 'bas_arc_vazao']
```
