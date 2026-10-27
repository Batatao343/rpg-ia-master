# SPEC-330 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (Grupo B, `81afd2a7`) · Grupo A + intérprete: `APPROVED_WITH_FOLLOWUPS` (re-revisão de `b3e4d3c0`; 1ª rodada: `CHANGES_REQUIRED` em `87716758`)
> **Revisor:** Sol (Opus, contexto separado) · **Data:** 2026-10-27 · **Commit revisado:** `81afd2a7` (Grupo B); antes `b3e4d3c0`/`87716758`

## Escopo

Branch `spec-330`, `main...HEAD` (b98a6918, bdf6bda0, 87716758) rebaseada sobre `8bd4f384`:
`services/card_effects.py`, ligações em `conflict_turn`, `conflict_orchestrator`,
`conflict_damage`, `combat_mechanics`, `cards`, `content_validator`, `data/cards/_glossario.json`,
`data/cards/_orcamento.json`, os testes novos e as fixtures. Conferido contra R1–R11, §5 e
§8 D-1..D-10. Fora do escopo: Grupo B no motor (D-10, depende da 328) e o smoke real (§6).

O que está correto:
- **Equivalência (D-3).** Gerei o golden de novo a partir de um `git archive 8bd4f384`, sem
  nenhum `card_effects` no código: 308/308 iguais ao `tests/fixtures/spec330_legacy_golden.json`
  commitado. O golden é honesto. As exclusões não escondem nada: `_cartas_rodada` só é escrito
  pelo `record_play` novo, e os stats zerados só tiram do dict de modificadores as chaves novas
  com valor 0. As 222 ativas/reações passam de fato pelo `resolve_turn`/`_resolve_reaction_effect`
  (todas acertam e produzem log de efeito). Limite em P2-4.
- **Interromper em `off`/`shadow`.** É inerte: `ctx.pressagios` só é preenchido com
  `intent_mode == "on"`, e o `_frustrate` só roda em `on`. Sem gatilho duplo na rodada
  simples (o teste ponta a ponta confere `count == 1`). O cursor é o mesmo dict mutado pelo
  `_next_intent`.
- **Fila FIFO, profundidade 3.** Está correta: o 4º disparo é descartado e registrado, e
  `depth`/`draining` são resetados no `finally`. O teste de laço força o eco com patch; no
  motor real, o dano disparado por gatilho não re-dispara `ao_receber_dano` (ver P2-3).
- **D-4.** Os extras só rodam dentro de `if atk["acerto"]`. No erro, a Carta só arma os
  gatilhos. As chaves novas (`keywords`, `gatilhos`, …) sobem por `TURN_EVENT_KEYS`.
  `agents/combat.py` só consome chaves conhecidas, então narrador e telemetria não quebram.
  A narração recebe os eventos pelos logs em pt-BR.
- **Validador.** O acervo real passa. Vocabulário fora do catálogo, palavra-chave
  desconhecida e Carta fora do orçamento são rejeitados (testes dedicados).
- Writers persistentes: `scene["gatilhos_armados"]`, a condição Vigília e `_cartas_rodada`
  são dicts JSON puros, sem tipo não serializável. `evals/` não foi tocado. Não há segredo
  em log.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/card_effects.py:849-868` × `services/conflict_orchestrator.py:2204-2213` | **Interromper com `acoes_por_rodada` > 1.** O Chefe age, o herói atordoa com Interromper e o presságio pendente (idx 1) é marcado `interrompido_por`, disparando `ao_pressagio_frustrado`. Só que a ação extra do Chefe ainda roda: pela SPEC-295, atordoamento no meio da rodada só vale na próxima, e `still_possible` não olha `interrompido_por`. O mesmo presságio sai em `pressagios_cumpridos` e o ataque acontece. Reproduzido: `KW interromper` + `GAT ao_pressagio_frustrado`, depois "e age de novo. e cumpre o que o presságio anunciava." e o golpe no herói. O gatilho recompensa um presságio que se cumpriu. | Em `interrupt`, atordoamento (alvo vivo e não terminal) só conta se a ação pendente for de fato negada, ou seja, cursor == 0 (1ª ação). Queda real (morte/terminal/incapaz) conta sempre. Alternativa: em `_enemy_decl` (`on`), intent com `interrompido_por` → `_frustrate` e a ação não executa. Teste: `acoes_por_rodada=2`, `initiator="enemy"`, dois presságios de ataque. |
| P1-2 | P1 | `services/conflict_orchestrator.py:1513-1521` | **`ao_derrubar` nunca dispara para alvo de fluxo completo** (Elite/Chefe/Nomeado/companheiro/jogador). O `was_down` é medido depois de `ct.resolve_turn`, cujo `_check_death` já pôs `last_stand_pending`. Reproduzido com o mesmo golpe letal: `lacaio` e `padrao` disparam, `elite` não (gatilhos `None`). Também falta teste de integração do `ao_derrubar` no `run_round`. | Medir o estado de queda de cada alvo ANTES de `ct.resolve_turn` e comparar depois do `_check_terminal`. Usar um predicado "caiu" sem atordoamento, porque R3 diz "alvo cai" e atordoar não deve contar como derrubar. Teste parametrizado por categoria. |
| P2-1 | P2 | `services/conflict_turn.py:477` + `services/card_effects.py:621` | Carta com principal de suporte passa `step.target_id or actor_id` aos extras. Um extra hostil sem `alvo` (ex.: Torpor depois de uma Vigília) é aplicado no próprio conjurador. | Kind hostil sem `alvo` cai no 1º oponente, ou o validador passa a exigir `alvo` em extra hostil de Carta de suporte. |
| P2-2 | P2 | `tests/test_keywords_valoria.py` / `test_card_effects_grammar.py` | O caminho de erro do D-4 não tem teste: todos os cenários usam Mira +40. | Teste com erro forçado: extras não rodam, gatilhos `quando` armam, `record_play` registra. |
| P2-3 | P2 | `services/conflict_orchestrator.py:1515-1519`, `card_effects.py:701-720` | `ao_receber_dano`, `ao_aliado_sofrer` e `ao_entrar_carga` não têm teste no `run_round`. `ao_receber_dano` só sai de `_hit_events`: dano de Sangria/DoT, de efeito extra ou de gatilho não dispara. Isso é coerente com o anti-loop, mas não está documentado. | Registrar em D-5 quais fontes de dano disparam o gatilho e adicionar um teste de integração por gatilho ligado. |
| P2-4 | P2 | `tests/spec330_equivalence.py:94-98` | Para as 86 utilitárias/passivas/virtudes, a equivalência compara só o snapshot de modificadores (logs vazios). Gatilhos `on_hit`/`on_attack` dessas passivas e o caminho de erro e crítico não são exercitados (uma seed só, acerto garantido). O risco é baixo, porque o diff não toca esses ramos, mas o §5 diz "resultado idêntico" para as 308. | Anotar o limite em D-3, ou acrescentar uma segunda passada com seed de erro. |
| P2-5 | P2 | `services/card_effects.py:687-693` | `revelar` grava `_revelado` na ficha e nada lê o campo. R7 pede `bestiary_knowledge`. | Follow-up: ligar ao `bestiary_knowledge` (SPEC-332/335) ou anotar o desvio em §8. |
| P2-6 | P2 | `services/card_effects.py:720` | O extra `dano` chama `_check_terminal` sem `nonlethal`: golpe declarado não-letal (SPEC-325) com dano extra pode matar. | Propagar o modo não-letal da declaração, ou documentar. |
| P2-7 | P2 | `services/card_effects.py:1401-1404` | O argumento de `alvo_tem`/`eu_tenho` aceita qualquer texto, sem passar pelo catálogo de condições. É o vocabulário de R2 parcialmente aberto. | Validar contra `NAMED_CONDITIONS` + controles + palavras-chave. |


## Correções aplicadas

Tudo em `b3e4d3c0`. Re-revisão do delta `96054968..b3e4d3c0`:

- **P1-1 — ok.** Agora há `has_fallen` (queda real, sem atordoamento). Em `interrupt`, o
  atordoamento só interrompe se for a 1ª ação (cursor == 0). Em `_enemy_decl` (`on`), um intent
  com `interrompido_por` vira frustrado e não age (nunca aparece nos dois). Na ação extra de
  quem caiu, o intent interrompido é registrado como frustrado.
  Testes: `test_atordoar_depois_da_1a_acao_do_chefe_nao_interrompe`,
  `test_atordoar_antes_da_1a_acao_interrompe_uma_vez`,
  `test_queda_real_depois_da_1a_acao_interrompe_a_extra`, `test_presagio_interrompido_nunca_se_cumpre`.
- **P1-2 — ok.** `fallen_before` é medido antes de `ct.resolve_turn`. `ao_derrubar` dispara
  para quem caiu no turno (golpe, extra ou gatilho) e atordoar não conta. Teste parametrizado
  com 7 categorias (lacaio, padrão, elite, chefe, nomeado, companheiro, jogador) + `test_atordoar_nao_e_derrubar`.
- **P2-1 — ok.** `_targets_for`: hostil sem `alvo` só usa `target_id` se ele for oponente;
  senão cai no 1º oponente. Teste dedicado.
- **P2-2 — ok.** `test_caminho_de_erro_nao_roda_extras_mas_arma_e_registra`.
- **P2-3 — ok.** `fx.on_damage` centraliza `ao_receber_dano`/`ao_aliado_sofrer`: golpe
  (`_hit_events`), dano extra/de gatilho (`_apply_on`) e DoT (`_tick_conditions_v4` → `_fx_damage`).
  Não conta duas vezes, porque o extra vai para `extra_hits` e não para `attacks`, que é o que
  `_hit_events` lê. O teste de laço ficou sem patch (eco real pelo motor) e continua `[1, 2, 3]`
  com o 4º descartado. Todo disparo aninhado entra na fila com profundidade +1, então nenhum
  caminho escapa do teto 3. As Cartas legadas não armam gatilho e não há passiva legada com
  `quando`, logo o efeito é no-op. O golden das 308 segue idêntico (fixture intocada no delta,
  teste de equivalência verde).
- **P2-6 — ok.** `Ctx.nonlethal`/`nonlethal_actor` são ligados durante o `resolve_turn` do ator
  (e limpos no `finally`); o dano extra repassa `nonlethal` ao `_check_terminal`.
  Teste: `test_dano_extra_respeita_golpe_nao_letal`.
- **P2-7 — ok.** `known_condition_names()` (NAMED_CONDITIONS + controles + marca/sangramento +
  palavras-chave) valida `alvo_tem`/`eu_tenho`. Teste parametrizado.
- **`off`/`shadow` (SPEC-329):** continuam inertes. Conferi com um teste scratch (apagado) no
  `run_round` com Chefe `acoes_por_rodada=2` e a Carta de Interromper: nos dois modos não houve
  keyword `interromper`, nem `ao_pressagio_frustrado`, nem `pressagios_frustrados`.

Sem achado novo bloqueante. Observação P3: a ação extra de quem não pode agir agora consome o
cursor sem frustrar quando não houve Interromper. Não muda nada observável (o ator está fora), mas
vale lembrar se a 329 passar a relatar intents não executados.

## Pendências

- P2-4 (cobertura das 86 utilitárias/passivas/virtudes no golden) e P2-5 (`revelar` →
  `bestiary_knowledge`) ficam como follow-up, registrados na spec §8 D-11.
- Sugestão P3: transformar a checagem scratch de `off`/`shadow` num teste de integração no `run_round`.

## Comandos rodados

```text
git diff main...HEAD --stat → 16 arquivos, +5545/−14
golden regen a partir de git archive 8bd4f384 (scratchpad) → 308 308 equal []
pytest -n 2 test_card_effects_grammar test_keywords_valoria test_log_event_registry test_no_silent_except test_enemy_intent test_enemy_intent_node test_mecanica_orfa → 194 passed
repro P1-1 (Chefe acoes_por_rodada=2, initiator=enemy) → interromper + gatilho, e depois "cumpre o presságio" (teste scratch, apagado)
repro P1-2 (golpe letal por categoria) → lacaio/padrão disparam ao_derrubar; elite não (teste scratch, apagado)
re-revisão b3e4d3c0: pytest -n 2 test_card_effects_review_spec330 test_card_effects_grammar test_keywords_valoria test_log_event_registry test_no_silent_except test_enemy_intent test_enemy_intent_node test_mecanica_orfa test_spec325_intents + scratch off/shadow → 241 passed, rc=0
```

---

# Grupo B (2ª passada) — `81afd2a7`

> **Veredito do Grupo B:** `CHANGES_REQUIRED` (1 P1, 5 P2)

## Escopo (Grupo B)

`main...HEAD` = `81afd2a7` sobre a `main` com 328/329/330A. Arquivos revisados:
`services/card_effects.py` (`_apply_pile`, `pile_trigger`, `prepare_play`/Ressoar, `echo`/Eco,
`_persist_revelation`), `services/card_piles.py` (`is_fardo`, `FOLEGO_MAX`, `gain_folego`,
`add_card`, `purge_fardos`, `pick_discards`, `discard_cards`, `mark_guardadas`, Exaurir em
`play_to_pile`), `services/card_deck_round.py` (`ao_exaurir`, `end_round`), as ligações em
`conflict_orchestrator` e `conflict_turn`, o evento `combat.revelar_knowledge_failed`,
`tests/spec330_equivalence.py` com o golden regerado, `tests/test_card_effects_piles.py` e a
spec §8 (D-10, D-12, D-11). Conferido contra R6, R7 e os follow-ups P2-4 e P2-5.

O que está correto:
- **Golden das 308 (a).** Regerei de forma independente: `git archive 8bd4f384` no scratchpad
  (sem `services/card_effects.py`) mais o `tests/spec330_equivalence.py` do HEAD. Deu 308/308
  iguais ao `tests/fixtures/spec330_legacy_golden.json` commitado, com a chave `extra` nas 308.
  O golden é honesto. O teste compara as formas legada e `efeitos=[efeito]`. O limite está em
  B-P2-1.
- **`off`/`shadow` inertes nas pilhas (a/b).** `ctx.piles` só é ligado quando
  `deck_mode(state) == "on"`. Sem ele, `_apply_pile` devolve False e o efeito vai para
  `pendente_pilhas`, como antes. `end_round` retorna cedo fora de `on`. `ao_exaurir` depende de
  `play_to_pile`, que só roda no `resolve_player_plays` (`on`). Os testes paramétricos de
  `off`/`shadow` conferem as pilhas byte a byte.
- **Fardo pelo inimigo (b).** Só acontece com as pilhas ligadas (`on`) e só para `gerar_carta`
  de Carta `is_fardo`. Qualquer outro efeito de pilha vindo de quem não é o jogador vira
  `pendente_pilhas`. Em `off`/`shadow` nada muda. `is_fardo` reconhece o id base, `injogavel` e a
  palavra-chave. A troca em `plan_plays`, `can_pay` e `public_view` não altera o acervo atual,
  porque nenhuma Carta do catálogo tem `injogavel` nem `fardo`.
- **Teto e anti-loop (c).** `gain_folego` limita o Fôlego a `FOLEGO_MAX` = 6. `pile_trigger`
  tem profundidade própria (`pile_depth` ≤ 3, com reset no `finally`). Eco chama `apply_effect`
  uma vez só e nunca volta a `resolve_extras`. Ressoar só conta em `record_play` e não dispara
  nada. Não encontrei caminho de loop.
- **`descartar` determinístico, com RNG persistido (c).** Em produção o `rng` do nó é o módulo
  `random`, que não é instância de `random.Random`. Por isso `_rng_of` devolve None, e
  `pick_discards`/`draw` usam `_rng(piles)` = `Random(f"{seed}:{embaralhos}")`, com o contador
  guardado nas próprias pilhas (JSON puro). Conferi num scratch: três execuções, com `json`
  round-trip das pilhas e o `random` global semeado de forma diferente em cada uma, deram o
  mesmo descarte e `embaralhos == 2`. O teste correspondente está em B-P2-3.
- **`revelar` grava no `bestiary_knowledge` (d).** Só o perfil `legacy` chama `bk.reveal_*`,
  que persiste em disco. Nos outros perfis o efeito só marca `revealed_*` na ficha, sem I/O. O
  formato (`tipo:imune|resiste|vulneravel`) é o mesmo do `_reveal_resistances` da SPEC-325. Uma
  exceção vira `combat.revelar_knowledge_failed`, registrado em `observability/events.py` e
  `EVENTOS_DE_LOG.md`. Nenhuma Carta do acervo usa `revelar` hoje.
- **Writers persistentes.** `scene["ressoar"]` (str→int) e os campos novos de `piles` são JSON
  puro. `evals/` não foi tocado, não há segredo em log e não entrou structured output novo.

## Achados (Grupo B)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| B-P1-1 | P1 | `services/card_effects.py:860-881` × `agents/combat.py:2261` + `services/card_piles.py:219-226` | **`comprar` e `ganhar_folego` não têm efeito útil no jogo real.** As `jogadas` da rodada são fechadas e validadas por `plan_plays` antes de resolver. Logo depois do `run_round`, o nó de combate chama `begin_round`, que descarta a mão inteira (menos as guardadas) e devolve o Fôlego a `FOLEGO_BASE`. Reproduzi num scratch. Com `t_comprar` e o monte com 8 Cartas, a mão termina a rodada como `['bas_san_golpe','bas_san_guarda']`, e na rodada seguinte as duas compradas estão no **descarte**. Com `t_folego`, o Fôlego termina em 4 e volta a 3 na rodada seguinte. Na prática `comprar` só tira 2 Cartas do monte. Se o monte esvaziar, ainda reembaralha e acrescenta um Fardo, o que piora a situação. `ganhar_folego` só reduz o Pacto de uma jogada posterior da mesma lista. O texto gerado promete compra e Fôlego que o jogador não consegue usar, contra R8 ("o texto nunca mente sobre a mecânica"). Os testes conferem a pilha no meio da rodada e nunca passam por `begin_round`. Por enquanto o problema não aparece (flag `off` por padrão e nenhuma Carta do acervo usa esses efeitos), mas a SPEC-335 vai criar Cartas em cima disso. | Decidir a semântica no modelo de declaração em lote e registrá-la em D-12. Sugestão: (1) as Cartas compradas por efeito entram num orçamento de retenção (como `guardadas`, consumido por `discard_hand`) e chegam à mão da próxima rodada; (2) `ganhar_folego` vira `folego_bonus`, que `begin_round` soma até `FOLEGO_MAX`. A alternativa é `plan_plays` simular o ganho, se ele valer na própria rodada. Faltam testes que passem por `run_round` → `begin_round` e provem que a Carta comprada e o Fôlego ganho estão disponíveis na declaração seguinte. |
| B-P2-1 | P2 | `tests/spec330_equivalence.py:36` + spec §8 D-11 | **P2-4 não está fechado.** D-11 diz que as seeds 21 e 1337 sem Mira cobrem "erro/acerto/crítico". Instrumentei `ct.resolve_turn` nas 2×308 execuções de `extra`: houve 270 ataques, **todos com `resultado == "acerto"`**, nenhum `erro` e nenhum `critico`/`supercritico`. Como todas as Cartas usam a mesma seed, todas tiram a mesma rolagem. O golden continua honesto, mas não cobre os ramos que o follow-up pedia. Os gatilhos `on_attack`/`on_hit` e o `use_card` das utilitárias (seed 7) estão cobertos. | Escolher seeds que produzam de fato `erro` e `critico` (ou forçar as rolagens) e regerar o golden a partir de `8bd4f384`. Acrescentar ao teste um assert de cobertura: entre os cenários `extra`, pelo menos um ataque `erro` e um `critico`. Se isso não for feito, corrigir o texto de D-11 e reabrir P2-4. |
| B-P2-2 | P2 | `services/conflict_turn.py:411`, `services/card_effects.py:952-990` × spec D-12 | **Eco e Ressoar não dependem de `RPG_CARD_DECK`.** `prepare_play`, `record_play(..., scene)` e `echo` também rodam em `off`/`shadow`, o que contradiz o "só `RPG_CARD_DECK=on`" do título de D-12. Hoje nada muda (nenhuma Carta tem `eco`/`ressoar` e o golden é idêntico), mas uma Carta com Ressoar já escalaria em `off`. | Documentar em D-12 que Eco e Ressoar independem das pilhas (o mais coerente, já que nenhum dos dois precisa delas) ou condicioná-los a `deck_mode`. Nos dois casos, um teste em `off` com uma Carta Ressoar fixa o comportamento escolhido. |
| B-P2-3 | P2 | `tests/test_card_effects_piles.py:175` | `test_descartar_ao_acaso_e_deterministico_pela_semente` muda `piles["seed"]`, mas passa `rng=random.Random(5)` ao `run_round`. Assim `_rng_of` usa o RNG da rodada, e o caminho de produção (RNG persistido em `seed`/`embaralhos`) nunca é exercitado. O teste também não faz round-trip de save/load. | Chamar `run_round(..., rng=random)`, como o nó faz, com `json` round-trip das pilhas entre duas execuções. Verificar `embaralhos` e o mesmo descarte com o `random` global semeado de forma diferente, como no scratch desta revisão. |
| B-P2-4 | P2 | `tests/test_card_effects_piles.py:235` | O Fardo plantado pelo inimigo só é testado chamando `fx.apply_effect` à mão, com `ctx.piles` ligado pelo próprio teste. Falta o teste de integração: Carta de inimigo com `gerar_carta` de Fardo, resolvida pelo `run_round` em `on`, chegando à mão, e a mesma rodada em `off`/`shadow` virando só `pendente_pilhas`. | Teste ponta a ponta via `run_round`, com o inimigo tendo a Carta em `cartas`, nos 3 modos. |
| B-P2-5 | P2 | spec §5 (critério "14 palavras-chave…") | O critério de aceite ainda diz "efeito no motor depois da 328". Com o Grupo B ligado, o critério e o smoke real do §6 precisam refletir o estado novo. | Atualizar o §5 junto com a correção de B-P1-1. |

Observações P3 (não bloqueiam):
- Se `before > FOLEGO_MAX`, `gain_folego` devolveria ganho negativo. Hoje isso não acontece,
  porque o Fôlego só sobe por esse caminho, mas `max(before, min(...))` elimina o risco.
- No modelo atual, `descartar` quase não tem custo, porque a mão inteira já é descartada no fim
  da rodada. Na prática ele só dispara Vazão ou tira da mão uma Carta com Guardar. Vale registrar
  em D-12 junto com B-P1-1.
- `_bump` altera a primeira chave que encontra entre `valor`, `dano_base` e `n`. Numa Carta cujo
  efeito principal tenha `valor` (por exemplo, uma duração) e `dano_base`, Eco e Ressoar mexeriam
  em `valor`. Fixar isso na autoria (SPEC-335).
- Um aliado que não é o jogador também passa no filtro "não-dono + Fardo" de `_apply_pile` e
  poderia plantar um Fardo na mão do herói. Se não for intencional, restringir a
  `sides["enemy"]`.

## Comandos rodados (Grupo B)

```text
git diff main...HEAD --stat → 12 arquivos, +5698/−120 (1 commit 81afd2a7)
golden regen: git archive 8bd4f384 (scratch, sem card_effects) + spec330_equivalence.py do HEAD → 308 308 equal [] (todas com extra)
instrumentação das seeds extra (21, 1337, sem Mira) → 270 ataques, todos "acerto"; 0 erro, 0 crítico
repro B-P1-1 (scratch): comprar 2 → na rodada seguinte as 2 estão no descarte; ganhar_folego deixa 4 → na rodada seguinte 3
RNG de produção (rng=random, json round-trip, random global variando) → descarte idêntico 3×, embaralhos=2
pytest -n 2 -p no:cacheprovider test_card_effects_piles test_card_effects_grammar test_card_effects_review_spec330 test_card_piles test_keywords_valoria test_log_event_registry test_no_silent_except test_error_envelope test_deck_migration test_enemy_intent test_enemy_intent_node → 186 passed, rc=0
```
