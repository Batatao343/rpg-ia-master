# SPEC-346 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (final, após a re-verificação; 1ª rodada em `3951602f`: `CHANGES_REQUIRED`)
> **Revisor:** Opus / Sol · **Data:** 2026-10-28 · **Commits revisados:** `3951602f` (1ª rodada) e `bc97cdd0` (re-verificação, branch `spec-346`)

## Escopo

Revisei `git diff main...spec-346`: 9 commits, de `c28d6364` a `3951602f`, 45 arquivos. Li o código
alterado em `agents/combat.py`, `agents/router.py`, `agents/loot.py`, `services/round_log.py`,
`services/conflict_orchestrator.py`, `services/combat_preview.py`, `services/turn_outcome.py`,
`services/prose_guard.py`, `services/encounter_manifest.py`, `services/presentation_history.py`,
`services/death_flow.py`, `llm_setup.py` e `observability/events.py`. Também li os testes novos
(`tests/test_spec346_*.py`), os 5 testes antigos que mudaram, `docs/spec346/arena*` e o §8/§9 da spec.

Ficaram fora: `web/` (é da SPEC-347), o smoke real do §6 (ainda não executado) e a suíte completa (é do
coordenador, no pouso).

Verifiquei também:
- `evals/` protegido, `tests/fixtures/spec330_legacy_golden.json`, `config/flags.yaml`, `data/` e `web/`:
  **nenhuma mudança**.
- Nenhum `with_structured_output` novo. O resumo e a entrada passam por `_fast_text`, que trata
  `is_fallback`, `try/except`, texto vazio (`RoutedLLM` esgotado devolve `""`) e troca de espécie.
- `provider_error_code` só entra se casar com `_IDENT_RE`. Nenhum segredo vai para log.
  `diag_groq_router.py` lê a chave via dotenv e não a imprime.
- Sem writer persistente novo fora de `combat.result.loot_*`, que é opcional; o save antigo é coberto por
  `test_spec346_saves`/`test_spec346_loot_once`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:2290-2297` (+ `_board_opening_result`, que não devolve `world`) | **A Vigília Ciumenta não funciona na rodada 1.** Com a vigília, a abertura grava `initiator=None` (`ambush_negated_vigilia`). Mas `world.encounter_surprise == "enemy"` continua no estado até a rodada 1, e ali a regra antiga converte a surpresa em `initiator="enemy"`. Como `locked` é `None`, nada sobrescreve. Resultado: no nível ≥ 3 os inimigos agem primeiro **com ou sem vigília**. Provei com um teste ad-hoc (nível 3, emboscada, vigília nas preparadas): `run_round(initiator='enemy')`. `test_spec346_vigilia` só confere o `combat_meta` da abertura, nunca a rodada 1. | Na rodada 1, quando `"initiator_reason" in combat_meta`, a cena manda: `base = combat_meta["initiator"]`. Se `base is None`, usar `_early_game_reaction_initiator(state, player, None, …)`, ignorando `encounter_surprise`. Senão, `initiator = base`. Teste: nível 3 + emboscada + vigília → `run_round` recebe `initiator=None`; sem vigília → `"enemy"`. |
| P1-2 | P1 | `agents/router.py:329-361` (`_hostility_fallback`), com `_EXPLICIT_HOSTILITY_RE` `:40` e `_THREAT_NARRATED_RE` `:522` | **Falsos positivos do fallback de hostilidade.** Com o CLASSIFY esgotado (o modo que o smoke encontrou), 5 de 5 frases não hostis que testei abriram COMBAT: "Enfrento meu medo e atravesso a ponte" (alvo `medo`), "Disparo pela porta rumo à praça", "Golpeio a mesa com o punho e exijo o preço justo" (alvo `mesa com punho`), "Conto ao capitão que fui atacado na estrada", "Enfrento a subida da montanha". Dois motivos: (a) o regex de verbo casa sentidos não hostis (`enfrent*`, `dispar*`, `golpe*`) e o particípio passivo `atacado`; (b) o sinal `_THREAT_NARRATED_RE` casa `perig*`/`armad*`, presentes em quase toda narração dark fantasy. Com `RPG_CARD_DECK=on` o dano piora, porque o texto livre passa a ser recusado (D5): o jogador fica preso num tabuleiro contra um "medo"/"Inimigo Sombrio" até conseguir fugir. | Aceitar só verbo em 1ª pessoa com objeto (`ataco|golpeio|apunhalo|disparo contra|saco a arma|enfrento`) e excluir particípio (`atacad[oa]s?`) e `disparo (pela\|para\|rumo)`. Exigir que o núcleo do alvo (R23) case um NPC em cena, uma espécie do bestiário ou um participante já citado na última narração. Ameaça narrada genérica sem alvo nomeado cai em STORY. Acrescentar estas 5 frases como negativos em `test_spec346_router_fallback.py`. |
| P2-1 | P2 | `services/conflict_orchestrator.py:2590` (`_resolve_last_stands(..., rng)` sem `preferred_targets`) | R9 pede o alvo **declarado**. A implementação usa o último ataque **executado**. Na emboscada (inimigo age primeiro), o herói cai antes de agir: sem ataque em `out["attacks"]`, a Última Ação cai em `_nearest_target` mesmo havendo uma jogada declarada. É justamente o caso que o smoke reportou (item 6). | Passar `preferred_targets={"player": <target_id da última jogada ofensiva da TurnDeclaration>}` a partir de `run_round`/`_run_round`. Teste com `initiator="enemy"` derrubando o herói antes da vez dele. |
| P2-2 | P2 | `services/conflict_orchestrator.py:1982-1984` | O rótulo "Última Ação" vai em `out["attacks"][-1]` sem conferir que `_basic_attack` acrescentou um ataque. Se o ataque não for registrado (alvo inválido/recusa), o rótulo e o `alvo_declarado` caem no ataque **anterior** da rodada. | Guardar `n = len(out["attacks"])` antes e rotular só se `len(out["attacks"]) > n`. |
| P2-3 | P2 | `agents/loot.py:500` | O bloqueio de "revistar o corpo" só vale com `not conflict_summary`. Quando o arquivista não limpa `conflict_summary` no turno da vitória (falha de RAG, `post_response`, gate do arquivista), o turno seguinte "revisto o corpo" passa pelo ramo pós-vitória e rola `roll_loot` de novo. Volta o loot duplo do item 9. | Bloquear também quando `combat.result.loot_claimed` e `loot_turn < turn_count` atual, independentemente de `conflict_summary`. Teste com `conflict_summary` residual no turno N+1. |
| P3-1 | P3 | `services/turn_outcome.py:81-104` · spec `:639` (D6) | A junção R17 no turno storyteller→combate (encontro de viagem) quebra a premissa de D6 ("o final estende o mostrado"). `narrate_text` faz `reset()` antes da entrada, então o cliente fica com B e o final é A+B. Resultado: `replace` com motivo `start`. Funciona (a API manda `replace: True`), mas com um "pisca". | Registrar na spec ou, na 347, não resetar entre nós do mesmo turno (separador `\n\n` emitido como delta). |
| P3-2 | P3 | `tests/test_spec346_mech_log.py:178-212` | O oráculo R10 soma `out["attacks"]`/`out["ticks"]`, não as **linhas** do `last_mech_log`. Além disso, só cobre ataque básico + DoT (sem dano de efeito de Carta via `_fx_damage`). | Parsear `mech_log(...)` (o `· N dano`) e incluir uma rodada com Carta de dano. |
| P3-3 | P3 | `specs/SPEC-346-cartas-smoke-narracao.md:73` · `docs/spec346/arena.md:29` | Texto desatualizado. A spec (R1) e a arena ainda dizem que a vigília "não está implementada/ainda não existe", mas o §9 e o commit `3951602f` a implementam. | Atualizar os dois textos. |
| P3-4 | P3 | `services/round_log.py:318,354` | `re.sub(r"\d+", "", …)` em fatos e no fallback pode deixar "Saqueador , Saqueador" e espaço duplo quando há nomes de instância numerados. | Remover o dígito junto com o espaço que vem antes e colapsar `\s{2,}`/`\s+,`. |
| P3-5 | P3 | spec R11 vs. grafo | No turno de vitória, o arquivista (que tem `conflict_summary` pendente) ainda pode fazer a sua chamada de LLM. Então "única chamada do turno" vale para o combate, não para o grafo. Não é regressão (já era assim). | Ajustar o texto do R11 ou cobrir com um spy no grafo no turno final. |

## Foco pedido: o que conferi e está OK

1. **Zero LLM por rodada `on`:** `test_round_with_jogadas_makes_zero_llm_calls_in_the_whole_graph` faz o
   spy de `get_llm` em 14 módulos + `llm_setup` e roda `main.app.invoke`. O router usa `_combat_gate` (sem
   CLASSIFY), o campaign_manager adia com combate ativo e a Cicatriz recebe `llm=None` (D11). A abertura dá
   a mão com `round == 0`, sem `run_round` e sem parser. O resumo final é uma só chamada FAST
   (`stream=False`) e passa por `strip_mechanic_numbers` → `validate_narrative_text` → R15. Com `off`/`shadow`
   a rodada continua narrada. Mudou só o desfecho (queda via `_narrate` + Roda; fallback R15) e o loot (R18).
2. **Iniciativa:** emboscada → inimigo (vence a proteção de herói novo), provocado/emboscou → herói,
   neutro → regra atual. Todos testados na rodada 1. O sinal de surpresa **não vem do LLM**: vem de
   `detection_check` determinístico no storyteller (`agents/storyteller.py:1605`). A vigília está quebrada
   (P1-1).
3. **mech_log:** tick de DoT com linha (inclusive com 0 de dano), crítico por dupla rotulado, Última Ação com
   alvo e "(alvo declarado)". Exceções: P2-1 e P2-2.
4. **Router:** o fallback age só nos dois ramos de esgotamento, e a negação funciona. Os falsos positivos
   estão em P1-2. O spawn não vaza mais frase crua: `_display_enemy_name` (núcleo, ≤ 3 palavras, `fallback_`
   pelo núcleo) + espécie da narração (R25).
5. **Loot uma vez:** está implementado por `combat.result.loot_claimed/loot_turn/location_id`; o `loot_ref`
   do manifesto não é consumido, e é equivalente. Exceção em P2-3. A junção R17 mantém byte a byte o turno
   com uma só `AIMessage`. O playtest herda a regra via `player_facing_message`, e a API/stream continuam
   corretos via `replace` (P3-1).
6. **Testes antigos:** as 5 mudanças são justificadas por decisão do dono, não afrouxam nada:
   - `test_api_jogadas`: a rodada `on` não narra (D-dono-1); o teste ficou **mais** estrito (`calls == []`).
   - `test_spec345_mech_log` e `test_wound_status_cards`: o texto livre agora é recusado (D-dono-7), então
     passam a declarar a ação estruturada; os asserts de conteúdo ficaram intactos.
   - `test_review_high_integration` e `test_spec345_player_text`: R18 (o loot pós-vitória não chama LLM e não
     repete o resumo canônico). Os asserts anti-alucinação (`Espada Solar`, `9999`, `Espólio:`) foram mantidos.

   O golden da 330 e os evals estão intactos.
7. **Arena:** `docs/spec346/arena.md` é coerente com os JSON. A base fica dentro de 45–85 %. O pior caso de
   emboscada tira Corruptor (42,7 %) e Arcanista (39,2 %) da faixa, e o coordenador aceitou (§9). O texto
   sobre a vigília está desatualizado (P3-3). Se P1-1 for corrigido, a vigília passa a valer de fato também
   no nível ≥ 3.

## Correções aplicadas

Ver "Re-verificação (bc97cdd0)" abaixo.

## Pendências

- P1-1 e P1-2: devolver ao executor (Terra) antes do pouso.
- P2-1..P2-3: corrigir na mesma rodada (são baratos) ou aceitar como follow-up explícito.
- Critérios ainda abertos na spec: o smoke real do §6 (`docs/spec346/smoke-final.md` não existe) e a suíte
  completa (coordenador).
- O front (botão Fugir, esconder o input no `on`) fica com a SPEC-347.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 4 tests/test_spec346_*.py tests/test_api_jogadas.py tests/test_review_high_integration.py tests/test_spec345_mech_log.py tests/test_spec345_player_text.py tests/test_wound_status_cards.py tests/test_log_event_registry.py → 207 passed in 22 s
pytest (ad-hoc, scratchpad) vigília nível 3 rodada 1 → FAIL: run_round(initiator='enemy') com a vigília (P1-1)
pytest (ad-hoc, scratchpad) 5 frases não hostis + CLASSIFY esgotado → 5/5 roteadas para combat_agent (P1-2)
git diff main...spec-346 --stat -- evals/ data/ config/flags.yaml web/ tests/fixtures/spec330_legacy_golden.json → vazio
```

## Re-verificação (bc97cdd0)

Revisei `git diff c3bae0d6..bc97cdd0`, que tem 3 commits do executor: `17d54226`, `4c21f388` e `bc97cdd0`.
Repeti as sondas avulsas da 1ª rodada (ficam no scratchpad e não foram commitadas).

| Item | Estado | Evidência |
|---|---|---|
| P1-1 vigília | **Fechado** | Sonda com nível 3 + emboscada. Com vigília, `run_round(initiator=None)`; sem vigília, `"enemy"`. A correção está em `agents/combat.py:2292-2295`: na rodada 1 manda a decisão da abertura. O teste novo está em `test_spec346_vigilia.py`. |
| P1-2 router | **Fechado como P1; o resto vira P2-5** | As 5 frases da 1ª rodada agora vão para STORY. Os verdadeiros positivos (smoke, "Ataco a criatura", "Sem hesitar, ataco o saqueador") seguem em COMBAT. Na bateria nova, 5 de 10 frases ainda viram falso positivo (ver P2-5). |
| P2-1 alvo declarado | Fechado | `_run_round` passa `preferred_targets` da `TurnDeclaration` (`conflict_orchestrator.py:2593-2599`). Há teste novo. |
| P2-2 rótulo da Última Ação | Fechado | O rótulo só é aplicado se `len(attacks)` cresceu. Há teste novo. |
| P2-3 loot residual | Fechado | O bloqueio não depende mais de `conflict_summary`. Usa `loot_turn < turn_count` (`agents/loot.py:89-93`). Há teste novo. |
| P3-1/3/5 | Fechados | Spec e `arena.md` atualizadas. |
| P3-2 oráculo | Fechado, com ressalva (P3-7, P3-8) | O oráculo agora soma as **linhas** do `mech_log` e roda com inimigos do bestiário. |
| P3-4 dígitos | **Regrediu** (ver P2-4) | |

### Achados novos

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-4 | P2 | `services/round_log.py:325` | O `_no_digits` novo usa como substituição o **byte de controle U+0001** (o `\1` virou `\x01` ao ser escrito). Sonda: `_no_digits("Alvo 3 , ok.")` devolve `'Alvo\x01 ok.'`, e `"Você tomba .  Fim 2"` devolve `'Você tomba\x01 Fim'`. A função roda sempre em `deterministic_outcome_text` (texto que o jogador lê, salvo no histórico e em JSON). Há também um TAB literal na `:324` (inofensivo). | Trocar a substituição por `r"\1"` (1 linha) e incluir esses 2 casos no teste. **Corrigir antes do pouso.** |
| P2-5 | P2 | `agents/router.py:353` (`if threat and tokens & set(em.name_tokens(ai))`) | **Falsos positivos que sobraram no fallback de hostilidade** (só com o CLASSIFY esgotado). Basta qualquer substantivo do objeto aparecer numa narração com palavra de ameaça. Viram COMBAT: "Golpeio a porta para arrombá-la" ("algo rosna do outro lado"), "Enfrento a tempestade a pé" ("A tempestade ameaça a estrada"), "Ataco o problema de frente e negocio", "Atiro em direção à árvore para treinar". Há um quinto caso pelo bestiário: "Enfrento o goblin numa partida de dados" (o alvo sai cru, `goblin numa partida de dados`, porque `hint_core` não corta `numa`/`num`). Com `on`, o jogador fica preso no tabuleiro. É bem mais estreito que o P1-2 original, por isso P2. | Retirar o caminho "token presente na narração". Exigir NPC em cena, espécie do bestiário, inimigo de `state["enemies"]` ou substantivo de pessoa/criatura de uma lista fechada (bandido, guarda, saqueador, soldado, vulto, criatura…). Acrescentar `num/numa/durante/para` aos cortes do objeto. Incluir as 5 frases como negativos. |
| P3-6 | P3 | `agents/router.py:290` (`_NEGATION_BEFORE_RE`) | Falso negativo: "sem pensar ataco o saqueador" fica em STORY, porque "sem" a até 2 tokens do verbo é lido como negação. Com vírgula funciona. Aceitável no modo degradado. | Tratar `sem` como negação só se seguido de `atacar/golpear…` no infinitivo, ou documentar. |
| P3-7 | P3 | `tests/test_spec346_mech_log.py:256` | `enemy_cultista_encapuzado` não está no bestiário, então 10 casos do oráculo fazem `pytest.skip` em silêncio. | Trocar por um id que exista, ou falhar em vez de pular. |
| P3-8 | P3 | `tests/test_spec346_mech_log.py` (oráculos R10) | **Reação/contra-ataque do herói fora do oráculo.** Nos dois oráculos, `declarations={}`: o herói nunca joga Carta nem Reação. Ficam sem cobertura três situações: custo em Vitalidade de Carta do herói (ex.: Sangromante), dano refletido/Espinhos e auto-dano de Reação, e cura/mitigação de Reação. Todas mexem na Vitalidade do herói sem uma linha "→ Você · N dano", e R10 pede "cura e ganho de Vitalidade como linha própria". **Classificação: P3 (lacuna de teste, sem bug demonstrado).** O contra-ataque em si mira o inimigo e não entra na conta do herói. | Follow-up: um oráculo parametrizado com o herói declarando Carta de custo em Vitalidade + Reação (bloqueio/reflexo). Se a igualdade quebrar, criar uma linha própria no `mech_log` para custo/cura/reflexo. |

### Integridade de eval: `_BOOKKEEPING` em `tests/spec330_equivalence.py` (commit `4c21f388`)

Sou a revisão independente desta exclusão. Arquivo do fixture protegido
(`tests/fixtures/spec330_legacy_golden.json`): **intocado**. O harness `tests/spec330_equivalence.py` não
está em `evals/protected-paths.txt`, mas é o evaluator do golden, então tratei a mudança como mudança de
exclusão.

**(a) As chaves são só registro?** Sim. Hoje cada uma é cópia derivada de algo que **continua no hash**:
- `ferimento` (por ataque, `conflict_orchestrator.py:1257`, `conflict_turn.py:586`) é um resumo de
  `dres["wound"]`. A mecânica real (o ferimento aplicado) segue no ator, em `ferimentos` (plural, que
  continua no hash), e o texto do dano segue em `out["logs"]`.
- `ticks` (`conflict_orchestrator.py:334`) é o registro do tick de DoT. O efeito (Vitalidade do ator) e a
  linha `"… sofre N de X (Vit V)."` em `out["logs"]` continuam no hash.
- `scene_logs` é uma fatia copiada de `out["logs"]`, que segue hasheado.

Fiz um grep: nenhuma outra estrutura do motor, das Cartas ou de `data/` usa essas três chaves com
mecânica.

**(b) A exclusão mascara regressão?** **Hoje, não.** Uma regressão no dano de ferimento ou no tick de DoT
muda `actors[*].vitalidade`/`ferimentos` e `out["logs"]`, que seguem no hash.

O risco é **futuro e estrutural**: `_strip` remove essas chaves **por nome, em qualquer profundidade** de
`[out, actors, scene]`. Se um campo mecânico futuro usar `ticks` (ex.: duração de condição) ou
`ferimento` dentro do ator ou da cena, ele sai do golden sem ninguém perceber.

**Decisão: APROVADA a exclusão** (o golden volta a provar equivalência mecânica). Fica o follow-up
**P3-9**: restringir a exclusão ao caminho exato, sem nada global por nome:
- `out["ticks"]` e `out["scene_logs"]` no 1º nível de `out`;
- `out["attacks"][i]["ferimento"]`.

Por exemplo, um `_strip_out(out)` antes do `json.dumps`, mantendo `_BOOKKEEPING` só para `_cartas_rodada`.
Mais um teste que falha se `ticks`/`ferimento` aparecerem em `actors` ou `scene`. Esse follow-up também
precisa de revisão independente (não é o executor que se autoaprova).

### Veredito final

**`APPROVED_WITH_FOLLOWUPS`.** Nenhum P0/P1 aberto.
- **P2-4** (byte `\x01` no texto do jogador) é 1 linha e deve ser corrigido **antes do pouso**. O
  coordenador pode conferir sem nova revisão: basta `_no_digits("Alvo 3 , ok.") == "Alvo, ok."`.
- **P2-5** (falsos positivos que sobraram no fallback do router, só no modo degradado): corrigir na mesma
  rodada se for barato. Senão, follow-up explícito antes de ligar `RPG_CARD_DECK=on` no staging.
- **P3-6..P3-9**: follow-ups.
- Continuam abertos os critérios do smoke real (§6) e da suíte completa (coordenador).

### Comandos da re-verificação

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 4 tests/test_spec346_*.py tests/test_card_effects_grammar.py tests/test_card_acervo_reparo.py tests/test_spec341_balanco.py tests/test_api_jogadas.py tests/test_review_high_integration.py tests/test_spec345_mech_log.py tests/test_spec345_player_text.py tests/test_wound_status_cards.py tests/test_log_event_registry.py tests/test_fase64.py → 354 passed, 10 skipped (P3-7) in 28 s
sonda vigília nível 3, rodada 1 → com vigília None, sem vigília "enemy" (P1-1 fechado)
sonda router (15 frases, CLASSIFY esgotado) → 5 falsos positivos novos (P2-5), 2 falsos negativos ("ataco o lobo", "sem pensar ataco…")
sonda _no_digits → '\x01' no texto (P2-4)
```
