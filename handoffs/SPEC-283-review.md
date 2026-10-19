# SPEC-283 — revisão Astra (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Astra, subagente independente) · **Data:** 2026-10-19 · **Commit revisado:** `0a86a22`

## Escopo

Branch `spec-283`, intervalo `c56dd09..0a86a22` (commits `a4ea15b` spec + `0a86a22` código/testes):
`services/conflict_orchestrator.py` (`enemy_declaration`, `_enemy_support_card`, `_has_condition_from`,
`_extend_ally_defense`, `_own_side_support`, `_resolve_actor_turn`), `services/conflict_turn.py`
(frase pt-BR, telemetria `enemy_support_cards`, log do `reposicionar`), `tests/test_spec283_enemy_support_cards.py`,
adaptação de `tests/test_spec275_stalemate.py`. Fora: smoke real DeepSeek (§6), suíte completa.

## Respostas aos pontos de ataque

1. **Carta de suporte mirando o jogador/aliado dele:** não encontrei combinação. O alvo vem só de
   `own_side = _same_side_ids(actor) ∪ {actor}` menos `hostile`, com `_available_for_aid`; e
   `_invalid_target_reason(support=True)` segue barrando hostil na resolução. Se a validação de suporte
   recusar, o fallback SPEC-275 R3 cai em ataque básico no MESMO alvo (próprio lado), que é recusado
   (`Ataque sem alvo válido.` / `é aliado — ataque recusado`) — sem fogo amigo. Varredura do teste
   cobre 6 Cartas × ferido/saudável × aliado ferido × distância × arquétipo.
2. **Impasse SPEC-275:** fechado. `_damage_fingerprint` não inclui condições/posição, então reforço
   não zera o contador; `_forced_attack` desliga o suporte (testado); Cartas `cena` esgotam;
   `poeira_pradaria` (`turno`) só dispara fora de `proximo` e converge. Rodei `combate --turns 200`
   nas seeds 21/22/23: **0 erro, 0/0 violações** nas três (sem `combat.no_progress`).
3. **Economia/determinismo:** `can_use_enemy_card(..., "ativa")` na escolha e `use_enemy_card` na
   resolução (Entropia + frequência cobradas; teste `entropy == 8`). Nenhum RNG novo (o único
   consumo é o `_taunt_target` pré-existente, antes da escolha). Teste de determinismo ok.
4. **R6 para o JOGADOR:** a mudança também deixa de abrir a janela de Reação inimiga quando o
   jogador usa Carta de suporte em si/aliado. Considero **correção**, não regressão: antes um
   reforço/esconder/cura do jogador em si mesmo virava "ataque declarado" e inimigos podiam gastar
   Reação (até `contra_ataque`) contra ele. Falta teste do lado do jogador (P2-4).
5. **`_extend_ally_defense` × SPEC-232:** coerente. A expiração é no fim do turno do portador e só
   para condições presentes no início do turno; proteção posta em aliado que ainda vai agir nesta
   rodada expiraria antes de qualquer ataque do lado oposto. O +1 só vale para aliado ≠ ator ainda
   fora de `resolved_turns`, igualando a defesa posta em si mesmo. O teste
   `test_defensive_card_protects_ally_in_danger` exercita o caso (guard age antes de hurt). Assimetria
   pré-existente: o JOGADOR protegendo aliado ainda não ganha o +1 (P2-5).
6. **Vazamento de id/token:** frase `"{nome} usa {Carta} [em {alvo}]."`; `reposicionar` sem
   `id -> estágio (via)`. No playtest saiu "Mosquito de Éter usa Coro da Colmeia." Resíduo: em falha
   de `move_distance` a mensagem `"{participant_id} não está na cena."` ainda carrega id — inalcançável
   pela IA (exige posição para `far`), pré-existente.
7. **Saves antigos:** nada novo persistido; `enemy_support_cards` é só da rodada. OK.
8. **Testes:** cobrem R1–R7 do lado inimigo; lacunas em P1-1, P2-3/4/5.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/conflict_orchestrator.py:539` (+ `services/conflict_turn.py:337`) | **Inimigo silenciado perde o turno inteiro.** `enemy_declaration` não olha `silence`; declara Carta de suporte em si mesmo; na resolução o silêncio anula a Carta e o passo vira ataque básico no próprio ator → `Ataque sem alvo válido.` (reproduzido: `NOITE` + `control: silence` → logs `['Wolf está silenciado — sem Cartas.', 'Ataque sem alvo válido.']`, 0 ataques). Como nada é cobrado, a escolha se repete a cada turno do silêncio: o silêncio vira atordoamento para toda criatura com Carta de suporte (antes da 283 ela atacava básico). Também põe a frase técnica na prosa. | Pular `_enemy_support_card` quando `cm.has_control(actor, "silence")` (ou fazer o fallback do silêncio redirecionar para o alvo hostil). Teste: inimigo silenciado com Carta de suporte declara/realiza ataque básico no jogador. |
| P1-2 | P1 | `specs/SPEC-283-ia-inimiga-cartas-suporte.md` §5/§8 | Critérios R8/R9 sem evidência: §8 está "(preenchido na execução)", caixas de aceite desmarcadas, medição de letalidade antes/depois (insumo da SPEC-285) não registrada, smoke real §6 não feito. | Registrar em §8. Minha medição (mock, `combate --turns 200`, branch `0a86a22`): seeds 21/22/23 → mortes **11/7/6**, 0 erro, 0/0 violações. Falta o "antes" em `main` nas mesmas seeds (game_id já é por seed desde a 275, então agora é comparável) e o smoke DeepSeek. |
| P2-3 | P2 | `services/conflict_orchestrator.py:492-555` | Provocação ignorada: com `_taunt_target` bem-sucedido (telemetria `special:taunt` registrada), o inimigo ainda pode se reforçar em vez de atacar o Devoto. Mesma lacuna já existia nas manobras táticas, mas aqui o evento de taunt é contabilizado sem efeito. | Com `taunted_target` definido, pular a família ofensiva/movimento (manter só a defensiva, se desejado) ou documentar na spec. |
| P2-4 | P2 | `services/conflict_orchestrator.py:1323` / testes | R6 também muda o comportamento do jogador (correto, item 4) sem teste. | Teste: jogador com Carta de suporte em si/aliado não abre `_open_reaction_window`. |
| P2-5 | P2 | `services/conflict_orchestrator.py:1308`, `services/conflict_orchestrator.py:539` | (a) `_extend_ally_defense` só vale para inimigos; proteção do jogador em aliado que não agiu ainda expira cedo (pré-existente). (b) `enemy_declaration` também decide NPC aliado do jogador sem declaração; se a ficha tiver `cartas`, ele usa Carta de suporte (reproduzido: aliado com `MURALHA` protege o jogador) e a telemetria sai como `enemy_support_card`. Hoje latente (companheiro não recebe `cartas`), mas a spec declara IA de aliado fora de escopo. | (a) follow-up SPEC-285/049. (b) guard `actor_id in sides["enemy"]` antes de `_enemy_support_card`, ou renomear/escopar. |
| P2-6 | P2 | `tests/test_spec275_stalemate.py:77` | Asserção condicional (`if decl.acao.kind == "card"`) não falha se a Carta deixar de ser usada. | Fixar o esperado (a Carta de `buff_acerto` mira `viuva`). |

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

- P1-1 e P1-2 antes de `done`. P2-3/P2-4/P2-6 baratos, recomendados no mesmo pouso. P2-5(a) → SPEC-285.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider <24 arquivos de conflito/combate/reação, incl. test_spec283 e test_spec275> → 438 passed
bash scripts/dev/py.sh -m playtest run --profile combate --turns 200 --seed 21|22|23 → 200t cada, erros=0, violações 0/0, mortes 11/7/6
probe (scratchpad): silêncio + Carta de suporte → turno perdido; aliado do jogador com MURALHA → protege o jogador; taunt → Carta ainda escolhida
```

## Correções aplicadas pelo executor (pós-revisão, 2026-10-19)

| Achado | Correção |
|---|---|
| P1-1 silêncio | `enemy_declaration` pula `_enemy_support_card` quando `cm.has_control(actor, "silence")`. Teste: `test_silenced_enemy_skips_support_and_attacks`. |
| P1-2 §8 vazia | §8 da spec preenchida com R8 (9 seeds × 2 builds, 0 `combat.no_progress`), R9 (playtest 0,564 → 0,598; arena 0,707 → 0,730), smoke DeepSeek e suíte. |
| P2-3 Provocação | com `taunted_target` definido, o inimigo não usa suporte e ataca a fonte. Teste: `test_taunted_enemy_attacks_taunt_source_instead_of_buffing`. |
| P2-4 R6 do jogador | correção mantida e coberta por teste: `test_player_own_side_support_card_is_not_a_declared_attack`. |
| P2-5 aliado do jogador | guard `actor_id in sides["enemy"]`. Teste: `test_player_side_actor_never_uses_bestiary_support_cards`. O +1 só para inimigo fica para a SPEC-285. |
| P2-6 asserção condicional | `test_spec275_stalemate.py` agora exige `bst_coro_colmeia` em si mesma. |

Pós-correção: os testes focados `test_spec283` + `test_spec275` passam (32), a suíte completa tem só as 3 falhas de índice stale e o playtest `combate` 200t nas seeds 21–29 dá 0 erro/0 violação.
