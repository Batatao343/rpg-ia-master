# SPEC-331 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / papel Sol · **Data:** 2026-10-27 · **Commit revisado:** `fc514f4a`

## Escopo

Branch `spec-331`, `main...HEAD` (1 commit, 11 arquivos): `services/scene_cards.py` (novo),
`services/encounter_preparation.py`, `services/conflict_orchestrator.py`, `agents/combat.py`,
`observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `data/combat/cartas_de_cena.json`,
3 arquivos de teste e a §8 da spec (D-331-1..3). Fora: frontend (SPEC-334), espólio (SPEC-333),
smoke com LLM real (o executor não rodou; os critérios de aceite seguem sem marcação).

Conferido e OK:
- **(a) `off` idêntico.** `PreparedScene` e o prompt seguem iguais (`_scene_cards_prompt` devolve
  `""`; o schema só vira `PreparedSceneWithCards` com `shadow`/`on`). `_run_round` não toca em nada
  com `off` (`_scene_ctx=None`). A chave `allies` nova no `ctx` de `_prepare_scene` não chega ao
  prompt nem a `fallback_safe_scene`. Desfecho: `objective_result=None` cai no caminho de antes.
- **(b) Structured output.** Guard mantido (`isinstance(result, PreparedScene)`, que cobre a subclasse;
  `FallbackLLM`/exceção levam a `fallback_safe_scene`, sem cartas e com objetivo padrão). Os nomes
  dos campos batem com o prompt (`cartas_de_cena`, `objetivo.tipo/alvo/n`). Os ids passam por
  `sanitize_choices` (catálogo + elegibilidade, no máx. 2) e o objetivo por `sanitize_objective`
  (catálogo fechado; alvo validado; `n` limitado). Nenhum número de efeito vai ao prompt. Todos os
  35 locais do mapa têm de 2 a 5 cartas elegíveis; o catálogo passa no validador.
- **(c) Sem dupla resolução.** `check_objective` não age de novo quando `objetivo_resultado` já
  existe; roda depois de `combat_should_end` e só se o jogador não morreu. `capturar_vivo` lê o
  `dead`/`morto` e aceita o `incapacitated`/`surrendered` do não-letal da 325.
- **(d) Teto de 12** (`clock_hard_stop`): só com `on`, pelo caminho `fled` do stalemate. Testado.
- **(e) Save/load:** todos os campos novos (`cartas_de_cena`, `objetivo`, `cena_estado`,
  `objetivo_resultado`, `pressagios_cena`) são JSON puro, e a ausência deles é tratada
  (`scene.get(...)`). Não há teste de round-trip (ver P2-5).
- Eventos de log registrados e documentados; nenhum segredo em log; `evals/` intocado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:1232,1245`; `agents/combat.py:1785,2283`; `services/scene_cards.py:653` | **R6 não funciona no caminho real.** (1) No caminho CLASSIFY, a jogada só é aceita se `res.card_id in player["prepared_cards"]`. A carta temporária `cena_*` nunca está lá, então a escolha da LLM é descartada e vira ataque básico; só o casamento exato por nome a encontra. (2) A carta temporária só existe no `_CARDS` em memória, e `sync_hand` só roda no spawn e **depois** da rodada. Num processo novo (cold start do Vercel, reload do save), `get_card("cena_…")` volta `None` antes da jogada: ela some do prompt (`_prepared_cards_catalog`), não casa por nome e `play_to_pile` a trata como `livre`. O teste só cobre `sync_hand` isolado. | Chamar `sync_hand(scene, pilhas, _PLAYER_ID)` no início do nó, antes de interpretar a ação, sempre que `combat_meta["pilhas"]` existir. Aceitar `cena_*` presentes em `pilhas["mao"]` nas linhas 1232/1245. Teste de nó: carta de objeto jogada após `cards.reload_cards()` (simula processo novo). |
| P1-2 | P1 (decisão do dono) | `services/scene_cards.py:455-476` (+ carta `vigilia_druidas`) | **O Relógio dá +1 Entropia, que é ganho, não pressão.** Entropia é o combustível das Cartas: `custo_entropia` é descontado em `use_enemy_card` e checado em `can_use_*`. Nos gatilhos de classe, o ganho de Entropia vem junto com `abyss_charge` (Carga do Abismo), que é o custo real. Do jeito que está, o Relógio dá recurso a todos que têm Entropia (jogador e inimigos com reserva). Isso até encurta a luta (mais cartas jogadas), mas não é "o Abismo se aproxima". A implementação segue a letra de R7. | Levar ao dono: (a) manter +1 Entropia; (b) **+1 Carga do Abismo** no jogador (e aliados), opcionalmente junto com a Entropia, como fazem os gatilhos de classe (recomendado); ou (c) outro custo. Registrar como D-331-4 e ajustar o teste `test_relogio_so_a_partir_da_rodada_5`. Não ligar `on` antes. |
| P1-3 | P1 | `api.py:2919-2920` (não alterado) | **R3 não chega ao jogador.** A view de combate da API é uma lista fechada: `pressagios_publicos` (329) é exposto, mas `pressagios_cena` e o `objetivo` da cena não. O presságio de cena é calculado e persistido, e ninguém o vê. A SPEC-334 é a UI; o contrato da API pertence a esta spec, assim como na 329. | Em `api.py`, com `scene_cards.active()`, expor `view["pressagios_cena"]` e um `view["objetivo"]` público (`{tipo, alvo_nome?, n?, rodada}`, sem números de efeito). Teste de API como o da 329. |
| P2-1 | P2 | `agents/combat.py:2177,2327` × `agents/combat.py:1625-1628` | Desfecho e espólio incoerentes. `victory` (que leva ao nó `loot`) depende de `dead or downed`, não do desfecho. Resultado: `interromper_ritual` que falhou com um inimigo derrubado vira `outcome="defeat"` **com** `next="loot"`; `capturar_vivo` em que o jogador matou todos vira `"defeat"` com loot. Já `sobreviver_n_rodadas` cumprido sem nenhuma queda vira `victory` sem loot. | Quando houver `objetivo_resultado`, derivar `victory` do desfecho, ou registrar a regra para a SPEC-333. Rever se `capturar_vivo` com todos mortos deve ser `defeat` ou `victory` sem bônus. Teste de nó cobrindo desfecho, `next` e `result.loot_ref`. |
| P2-2 | P2 | `services/scene_cards.py:401` | O dano/efeito do ambiente usa `source=target=aid`. Isso dispara `ao_receber_dano` com `alvo_id` = a própria vítima (uma retaliação pode acertar o próprio ator), consome a Marca do Abismo da vítima como se fosse dela mesma, usa o `damage_pct("dealt")` da vítima e credita a queda a ela própria (`by=aid`). | Usar uma fonte neutra (por exemplo, `source_id=None` ou um id `cena:<card>` fora de `actors_by_id`) e pular `consume_marca_abismo` e `damage_pct` quando a fonte for a cena. |
| P2-3 | P2 | `agents/combat.py:1786-1787,2269-2274` | Com `shadow`, o estado é alterado: `combat_meta["pressagios_cena"] = []` é gravado, mas `shadow` deveria só registrar. | Gravar só com `active()` (ou só quando a lista não estiver vazia). |
| P2-4 | P2 | `services/scene_cards.py:653-655` | As cartas temporárias são injetadas no catálogo global `cards._CARDS`, que vale para o processo todo e é compartilhado entre partidas. `cards_for_class("")` as listaria, porque não têm `classe`, e o catálogo cresce sem limite. | Marcar as temporárias (`basica`/`cena` filtrados em `cards_for_class`) ou resolvê-las pela cena em vez de pelo catálogo global. |
| P2-5 | P2 | `tests/` | Faltam: o round-trip save→load de um combate em curso com `cartas_de_cena`/`objetivo`/`cena_estado`/`pressagios_cena`; um teste de nó (`combat_node`) com objetivo resolvendo; e um teste de byte-identidade do prompt com `off` contra o texto anterior (o atual só verifica a ausência de `cartas_de_cena`). | Adicionar os três testes. |
| P2-6 | P2 | `services/encounter_preparation.py:520-536` | O prompt não lista alvos válidos para `objetivo.alvo`: nem ids de aliados, nem a orientação "zona/objeto que você criou". Com a LLM real, `proteger`, `alcancar_zona` e `destruir_objeto` tendem a ser descartados para `derrotar_todos`. O MockLLM preenche o schema genérico e esconde isso. | Incluir no trecho do objetivo: `alvo` = id de aliado (lista), id de zona ou id de objeto criados nesta resposta. Validar no smoke real §6.2. |
| P2-7 | P2 | `services/scene_cards.py:308-326` | `forecast` não prevê o redisparo da carta mais forte pelo Relógio (rodada ≥ 5). R3 pede o presságio uma rodada antes de cada disparo. | Incluir `strongest(scene)` no `forecast` quando `rnd >= ABYSS_CLOCK_START`. |

## Correções aplicadas

Nenhuma ainda (revisão inicial).

## Pendências

- O dono precisa decidir P1-2 (efeito do Relógio) antes de `RPG_SCENE_CARDS=on` no staging.
- O dono ainda precisa revisar os 24 nomes do catálogo (critério de aceite, já previsto na spec).
- Smoke real §6 e p95 de rodadas na arena: ainda não executados.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_scene_cards.py tests/test_objectives.py tests/test_abyss_clock.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_error_envelope.py → 52 passed (rc=0)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_card_piles.py tests/test_conflito_preparacao.py tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec275_stalemate.py → 78 passed (rc=0)
script ad hoc (scratchpad): eligible() nos 35 locais → mín. 2, máx. 5, zero vazios; validate_catalog → []
```
