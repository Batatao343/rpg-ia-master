# SPEC-330 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão de `b3e4d3c0`; 1ª rodada: `CHANGES_REQUIRED` em `87716758`)
> **Revisor:** Sol (Opus, contexto separado) · **Data:** 2026-10-27 · **Commit revisado:** `b3e4d3c0` (1ª rodada: `87716758`)

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
