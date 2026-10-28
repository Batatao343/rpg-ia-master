# SPEC-346 — revisão sol (review)

> **Veredito:** `APPROVED` (final, passe em `8c0b0904`; 1ª rodada `3951602f`: `CHANGES_REQUIRED`; 2ª `bc97cdd0`: `APPROVED_WITH_FOLLOWUPS`)
> **Revisor:** Opus / Sol · **Data:** 2026-10-28 · **Commits revisados:** `3951602f`, `bc97cdd0`, `8c0b0904` (branch `spec-346`)

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

## Passe final (8c0b0904)

Revisei `git diff 4a40b489..8c0b0904`, que tem 5 commits: `9e2e2110`, `1390e70e`, `8f7f0ac2`, `ac893ecb` e `8c0b0904`.

| Item | Estado | Evidência |
|---|---|---|
| P2-4 `_no_digits` | **Fechado** | Sonda: `"Alvo 3 , ok."` vira `"Alvo, ok."` e `"Você tomba .  Fim 2"` vira `"Você tomba. Fim"`. Sem `\x01`. |
| P2-5 router | **Fechado** | As 5 frases da bateria anterior agora vão para STORY. Das 5 novas, 3 vão para STORY ("lobo da minha própria raiva", "boneco de palha do treino", "apunhalo o mapa… para marcar a rota"). Ainda viram COMBAT 2 frases forçadas que citam uma criatura real do bestiário: "Ataco o goblin assado com garfo e faca" e "Enfrento o bandido no tribunal com provas". Ficam como risco residual P3-10, só no modo degradado. |
| P3-6 negação | Fechado em parte | O `sem` saiu da lista de negação. "sem pensar ataco o saqueador" ainda vai para STORY, agora porque `saqueador` não está no bestiário, nem em cena, nem no manifesto. Isso é falso negativo, o lado seguro (STORY). |
| P3-7 skips | Fechado | O id inexistente agora faz o teste falhar em vez de pular (`assert template`). Zero skips. |
| P3-8 oráculo | Fechado | Novo oráculo com o herói jogando Cartas (golpe, cura `bas_med_pressao`, guarda) + Reação (`san_esquiva`, `san_troco_carmesim`) em 12 seeds. Ele confere `ganho = cura − dano + excedente` e exige que a cura e a Carta tenham sido jogadas. A cura de apoio de aliado também tem linha (`out["heals"]` → `mech_log` "… · cura · N Vitalidade"). |
| P3-9 exclusão do golden | **Fechado, aprovado** | Ver abaixo. |

### Integridade de eval: exclusão restrita do golden da 330 (`8f7f0ac2`, `8c0b0904`)

`_BOOKKEEPING` voltou a ter só `_cartas_rodada`. A exclusão da SPEC-346 agora vale **só nos caminhos
exatos**, via `strip_record_paths(out)`:
- `out["ticks"]`, `out["scene_logs"]` e `out["heals"]`;
- `out["attacks"][i]["ferimento"]`.

O resto do `out`, `actors` e `scene` entra inteiro no hash.

Testes que travam a exclusão:
- `test_strip_record_paths_e_exato`: `out["outro"]["ticks"]` continua no hash.
- `test_chaves_de_registro_da_346_nao_vazam_para_actors_nem_scene`: roda as 308 Cartas × 4 seeds e falha
  se alguma dessas chaves aparecer em `actors`/`scene`.

O fixture protegido continua intocado.

**`heals` é só registro?** Sim. Conferi os 4 pontos que escrevem a chave:
- `_resolve_reaction_effect`, `conflict_orchestrator.py:1098`;
- apoio tático, `:1579`;
- agregação, `:1686`;
- `_resolve_support_card`, `conflict_turn.py:647`.

Em todos, a mecânica é aplicada **antes**, em `target["vitalidade"]` (que fica em `actors`, hasheado), e a
mesma quantia vai para `out["logs"]` ("recupera N Vitalidade…", também hasheado). `heals` é só uma cópia
`{actor_id, card, amount}`.

Uma regressão de cura muda a Vitalidade do ator e o log, logo muda o hash. Nada mecânico fica escondido.
**Exclusão aprovada.**

### Achados residuais (follow-up, não bloqueiam)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-10 | P3 | `agents/router.py:320-364` | O fallback de hostilidade ainda abre combate quando o objeto contém uma criatura do bestiário num contexto não violento ("goblin assado com garfo e faca", "bandido no tribunal"). Só acontece com o CLASSIFY esgotado e frase forçada. | Opcional: lista de contextos não violentos (`tribunal`, `assad*`, `prato`…), ou aceitar o risco. |
| P3-11 | P3 | `agents/router.py:294` (`_NON_COMBAT_CONTEXT_RE`) | Falso negativo: "Ataco o guarda para abrir caminho" vai para STORY, porque `para abr*` é lido como contexto não violento e isso é checado antes de tudo. O lado é seguro. | Aplicar o contexto não violento só quando o alvo não for NPC/criatura presente. |

### Veredito final (substitui o anterior)

**`APPROVED`.** Todos os P1/P2 estão fechados. A exclusão do golden ficou restrita aos caminhos exatos e
foi aprovada por esta revisão independente. Os P3-10/P3-11 são follow-ups opcionais do modo degradado.

Continuam abertos, fora desta revisão: o smoke real do §6 e a suíte completa (coordenador).

### Comandos do passe final

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n auto -rs tests/test_spec346_*.py tests/test_card_effects_grammar.py tests/test_card_acervo_reparo.py tests/test_spec341_balanco.py tests/test_api_jogadas.py tests/test_review_high_integration.py tests/test_spec345_mech_log.py tests/test_spec345_player_text.py tests/test_wound_status_cards.py tests/test_log_event_registry.py tests/test_fase64.py → 401 passed, 0 skipped in 56 s
sonda router (15 frases, CLASSIFY esgotado) → 10/10 negativos anteriores + 3/5 novos em STORY; 2 frases forçadas com criatura real em COMBAT (P3-10); 2 falsos negativos seguros (P3-6, P3-11)
sonda _no_digits → sem \x01 (P2-4 fechado) · sonda vigília nível 3 → None / "enemy" (P1-1 segue fechado)
```
