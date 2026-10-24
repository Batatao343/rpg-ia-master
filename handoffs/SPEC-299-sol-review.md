# SPEC-299 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (re-revisão de `c67a7bb5`: P1-1/2/3 resolvidos; 1 P1 novo, P1-4, introduzido pela correção do P2-4)
> **Revisor:** Opus (Sol, revisão independente) · **Data:** 2026-10-24 · **Commits revisados:** `fa05d92c` (1ª) e `fa05d92c..c67a7bb5` (re-revisão)

## Escopo

Branch `spec-299` (worktree `rpg-spec-299`), diff `main...fa05d92c`, 33 arquivos. Li por
inteiro `services/law.py`, e também `data/law_codes.json`, os pontos de integração (`agents/router.py`,
`agents/storyteller.py`, `agents/npc.py`, `agents/turn_finalizer.py`, `world_utils.check_encounter`,
`combat_origin`, `world_validators`, `structured_outputs`, `persistence`, `reputation.add_location_fame`,
`mock_llm`, `playtest/profiles`) e os testes `tests/test_spec299_*`. Não revisei: o balanceamento
numérico (`[BALANCEAR]`), o smoke real da §6 (não foi executado) e a medição longa off/on, que
não rodei porque long-run é opt-in. Para essa medição, aceito o número do executor.

O que está correto:
- **Regra de ouro.** A party não testemunha. A vítima de homicídio não relata. Testemunha morta
  ou recrutada é descartada na entrega. A patrulha relata na hora e o civil com atraso. A
  notícia se espalha por `world_distance` mais o tempo do mensageiro. `crime_witnessed`/`law_resolved`
  só passam com `source="law"`.
- **Sem vazamento.** `GameResponse`, codex e dossiês ficam sem estado da lei. `render_event`
  devolve `""` para os tipos novos, então nada da lei entra no `context_builder`.
- **Validador R6.** Exige o tipo no catálogo, vítima em cena, suporte lexical no
  `HumanMessage` do turno, respeito à quarentena e 1 crime por tipo.
- **Guard de FallbackLLM.** O default é `[]`, a leitura usa `getattr(..., [])` e o
  `coerce_crime_claims` descarta o item inválido sem derrubar a resposta.
- **Flag `off`.** Router, storyteller, npc, finalizer, save e encontro estão todos atrás de `mode()`.
- **Caçadores.** Só aparecem depois do sinal `perguntaram_por_voce` e respeitam o cooldown
  global de `check_encounter`. A força vem do preço pela cabeça, não do nível.
- **Contrato da SPEC-298.** `add_location_fame` está consistente com ele: é idempotente por
  `crime:<tipo>:<crime_id>` e só aparece no local do crime, na primeira entrega.
- **Save.** O round-trip está testado e o save antigo carrega sem a chave.
- **Prisão.** Tem 4 saídas e nenhuma trava: esperar sempre solta. Não há execução nem mutilação.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/law.py:1483-1543` (`_prison_choice`), `services/law.py:794`, `agents/storyteller.py:557-588` | **A prisão se contorna com um comando de viagem.** Preso no Oubliette, o jogador escreve "vou para o Anel de Lama". O gate cai no default e devolve `next=storyteller`. O storyteller aplica a viagem normalmente (sonda: `na_anel_ferro → na_anel_lama`), sem rolagem de fuga e sem crime `evasao`. O confronto `imprisoned` continua gravado, porque o finalizer não o limpa fora da jurisdição. Em todo turno seguinte, em qualquer lugar, o gate força a rota STORY (bloqueia NPC e loot) e o bloco diz "Você está preso numa cela" mesmo com o jogador na praça. A fuga com destino ("fujo para o Anel de Lama") tem o mesmo defeito: o router move o jogador para `_exit_location` e o storyteller viaja de novo, inclusive quando a fuga falha. | Preso, a intenção de viagem (`find_travel_destination`/`is_travel_intent`) deve virar `_escape_prison(rescued=False)`. O storyteller não pode aplicar viagem nem descanso no turno em que o `law_gate` resolveu: marque o payload (ex.: `law_gate_consumed=True`, ou relance `law_state.confrontation.reason=="imprisoned"`) e pule o bloco de viagem. Testes: preso + "viajo para X" ⇒ continua em `na_anel_ferro` ou rola fuga; fuga falha + destino ⇒ não sai do lugar. |
| P1-2 | P1 | `services/law.py:73-80`, `services/law.py:1431-1468` (`resolve_choice`) | **O gate do confronto ignora negação e pune contra a intenção explícita.** Na sonda, "Não me rendo! Saco a espada." e "Jamais me entrego a vocês" levaram a 6 dias de pena e à prisão. "não vou pagar nada" e "eu me recuso a pagar, ataco o guarda" debitaram a multa. "não fujo, explico que foi legítima defesa" virou `evasao` mais combate com soldado Elite. Isso contraria o espírito do R6/§7 ("nunca punir por algo que não tentou") num gate determinístico que roda antes do LLM. | Adicionar uma checagem de negação local (`\b(?:nao|jamais|nunca|recuso|me\s+recuso)\b` até ~3 tokens antes do verbo) a cada léxico do gate (render, pagar, subornar, fugir). Em ambiguidade, a prioridade deve ser ataque explícito > conversa. Testes parametrizados com as 5 frases acima. |
| P1-3 | P1 | `agents/storyteller.py:981-983` | **Bloco `<LEI_NA_CENA>` e dica de `crime_claims` calculados no local de origem em turno de viagem.** `scene_block(state)` e `crime_hint_enabled(state)` usam o `world` anterior à viagem. Na sonda, saindo de Nova Arcádia com patrulha para o Anel de Lama (sem lei), o prompt da chegada recebeu "Soldados da Legião de Ferro patrulham o local à vista de todos". Os sinais (`perguntaram_por_voce`, `cartaz:<origem>`) são marcados como mostrados num turno em que a cena é outra, e esse sinal destrava os caçadores (R18). A patrulha que testemunha um claim no destino (`apply_claims` usa `world` novo) também não foi a mostrada na cena (R9). | Passar `{**state, "world": world, "npcs": scene_npcs}` para `scene_block` e `crime_hint_enabled`, igual ao que `apply_claims` já recebe. Teste: viagem de um local com patrulha para um local sem lei ⇒ bloco vazio e sinais não marcados. |
| P2-1 | P2 | `services/law.py:48-68` (`_LEXICON`) | Léxico do R6.4 com falsos positivos: `furt\w*` casa "furtivamente", `encant\w*` casa "fico encantado", `golpe\w*` casa "golpe de sorte" e `magi\w*` casa "pergunto sobre magia". Hoje o LLM também precisa emitir o claim, mas o léxico é a principal defesa contra acusação falsa. | Formas verbais fechadas (`furt(?:o|ar|ei|amos|ando)\b`, `encant(?:o|ar)\s+`, etc.) e testes negativos com as frases acima. |
| P2-2 | P2 | `services/law.py:1232-1246`, `data/law_codes.json` (`lei_dos_clas.punishment="multa"`) | Em códigos com `punishment="multa"` (Lei dos Clãs, "branda"), quem se rende cai no ramo de **expulsão** e recebe `heat=70`, ou seja `cacado`, o que habilita caçadores. A spec só define expulsão para a colmeia. | Com `multa`, render-se e não ter ouro deve virar dívida ou expulsão sem `cacado`. A outra saída é documentar a decisão na spec (D1). |
| P2-3 | P2 | `services/law.py:768-775`, `:818-819` | Em `shadow`, a lei grava `location_fame` (infâmia, visível ao narrador por `<FAMA_LOCAL>` e ao jogador por `reputation_notices`) e emite `crime_witnessed`, que se propaga a NPCs com a SPEC-215 ligada. Assim `shadow` não é só observacional, o que pesa no D9 (shadow 1 playtest no staging). | Restringir `_fame_bridge.write` e a emissão de eventos a `on`, ou registrar na spec que o shadow já mexe na fama. |
| P2-4 | P2 | `services/law.py:1549` (`buy_license`) | `magia_ilegal` está ligada no Código de Ferro e a licença não tem chamador. D2 do dono: "licença obtida por **custo**/patente (SPEC-301) ou usar escondido". Sem fiação, o único caminho legal é o escondido, e nada no jogo diz que existe registro. Não é P1 porque a flag vem `off` e o plano é `shadow` primeiro, mas **bloqueia `RPG_LAW=on`**. | Ligar a licença por um gesto diegético (ex.: léxico "registro meu Éter"/"pago a licença" falando com a Legião num local da jurisdição) ou pela SPEC-301, e dar um sinal diegético na 1ª magia testemunhada ("Sem registro, isso dá fogueira aqui"). |
| P2-5 | P2 | `services/law.py:1469-1472`, `:1375-1386` | Três falas sem palavra-chave (`max_talk_turns=2`) abrem combate com `enemy_soldado_legiao_ferro` (Elite). Fugir também leva a esse combate. Derrota nesse combate não leva à prisão, segue o desfecho padrão de combate, inclusive morte. O efeito na letalidade só existe para quem comete crime, mas a §8 diz "ver hand-back" em vez de registrar os números da SPEC-285. | Registrar na §8 a medição off/on (combate de 200 turnos, seeds 21-22). Como follow-up, estudar derrota em `law_enforcement` ⇒ prisão, em vez de morte (coerente com D5). |
| P2-6 | P2 | `services/law.py:345-349`, `:966-970`, `:1358` | Concordância: "Soldados de A Legião de Ferro", "Guarda de A Legião de Ferro". | Tirar o artigo inicial do nome da fação ou usar "da". |
| P2-7 | P2 | `agents/storyteller.py` e `agents/npc.py` (`{lei_block}`) | Em `off` o prompt ganha uma linha em branco a mais e o schema de `StoryUpdate`/`NPCResponse` cresce. O comportamento não muda, mas o request ao provider não fica "byte a byte" idêntico. | Documentar na §8 que "byte a byte" vale para estado e saída, não para o texto do prompt, ou omitir a linha quando vazia. |

## Correções aplicadas

Commit `c67a7bb5` (executor), conferido na re-revisão abaixo: P1-1, P1-2, P1-3, P2-1, P2-2, P2-3, P2-4 (com regressão, ver P1-4), P2-5 (números na §8), P2-6, P2-7 (documentado).

## Pendências

- P1-1, P1-2 e P1-3 bloqueiam o pouso. Depois da correção, nova revisão focada nesses três
  (sem refazer o resto).
- P2-4 bloqueia `RPG_LAW=on` (coordenador ou SPEC-301). P2-5 é registrar a medição na §8 antes do pouso.
- Smoke real da §6 pendente (coordenador, com chave), exigido pelos critérios de aceite.
- `criminoso` entra em `PROFILES` (15 perfis), então `playtest run --all` muda de denominador.
  Deixar claro na spec e no CHANGELOG que comparações com baselines de 14 perfis devem
  excluí-lo.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec299_*.py tests/test_npc_knowledge*.py tests/test_spec298_fama_local.py tests/test_spec298_visibilidade.py → 155 passed
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_fase51.py tests/test_playtest_profiles.py → 30 passed
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_combat_lifecycle.py tests/test_encounter_lifecycle_reload.py tests/test_router_interlocutor.py → 40 passed
sonda (scratchpad/probe_prison.py): preso + "vou para o Anel de Lama" → loc na_anel_lama, conf "imprisoned" mantido (P1-1)
sonda (scratchpad/probe_neg.py): "Não me rendo! Saco a espada." → served sentence, na_anel_ferro; "não vou pagar nada" → multa debitada (P1-2)
sonda (scratchpad/probe_travel.py): viagem nova_arcadia→na_anel_lama → scene_block calculado em nova_arcadia com patrulha (P1-3)
```

## Re-revisão — delta `fa05d92c..c67a7bb5`

Escopo: só o delta (`agents/router.py`, `agents/storyteller.py`, `agents/turn_finalizer.py`,
`state.py`, `services/law.py`, a §8 da spec e `tests/test_spec299_review_fixes.py`).

| ID | Status | Evidência |
|---|---|---|
| P1-1 | **resolvido** | Preso, a intenção de viagem/fuga vira `_escape_prison` (rolagem + `evasao`), `law_gate_consumed` desliga viagem e descanso no storyteller, e o `imprisoned` deixa de valer fora da prisão. Sonda refeita: "vou para o Anel de Lama", "viajo para a Nova Arcadia" e "descanso" mantêm o jogador em `na_anel_ferro`, sem viagem grátis. O transitório é zerado no `turn_finalizer`. |
| P1-2 | **resolvido** | `_affirmed` aplica negação por oração. Sonda: "Não me rendo! Saco a espada." → `combat_agent` (resistência), "não vou pagar nada" → conversa, sem débito, "não fujo, explico…" → conversa, "não tenho escolha, me rendo" → pena, "eu pago a multa" → multa. |
| P1-3 | **resolvido** | `scene_block`/`crime_hint_enabled` recebem `{**state, "world": world, "npcs": scene_npcs}`. Sonda: viagem para `na_anel_lama` → bloco calculado no destino, vazio. |
| P2-1 | resolvido | Léxico com formas fechadas ("furtivamente", "encantado" e "golpe de sorte" não casam mais). |
| P2-2 | resolvido | Em `multa`, render-se paga a multa. Sem ouro, expulsão com `heat=30` (suspeito), sem caçadores. |
| P2-3 | resolvido | Em `shadow`, sem fama e sem `crime_witnessed`. |
| P2-4 | resolvido **com regressão** | Fiação router → `resolve_license_request` → `buy_license`, mais o sinal diegético do registro. Ver P1-4. |
| P2-5/6/7 | resolvidos | Números da SPEC-285 na §8, concordância "da Legião de Ferro", ressalva do "byte a byte" documentada. |

### Achado novo

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-4 | P1 | `services/law.py:92-95` (`_LICENSE_RE`), `agents/router.py:136-150` (`_law_gate`) | **"Pedir licença" é expressão comum ("com licença") e hoje compra a licença de magia.** O regex aceita qualquer verbo (`peço/pago/faço/tiro…`) seguido de `registro\|licenca` na mesma frase, sem exigir magia/Éter. Sonda em Nova Arcádia com `RPG_LAW=on` e sem confronto: "Peço licença ao mercador e entro na loja", "Com licença, peço licença para passar" e "Faço o registro na estalagem" debitaram **250 de ouro** cada (500 → 250), gravaram `licenses=["codigo_de_ferro"]` e consumiram o turno (`law_gate_consumed=True`, rota STORY no lugar de NPC). É o mesmo tipo de defeito do P1-2: o gate determinístico cobra do jogador contra a intenção dele. | Exigir o objeto mágico na mesma oração, ex.: `\b(?:registro\|licenca)\s+(?:para\s+(?:usar\s+)?\|d[eo]\s+(?:meu\s+\|minha\s+)?)?(?:magia\|eter\|feiticaria)\b` (e "registro meu Éter"), mantendo o `_affirmed`. Testes negativos com as 3 frases acima e positivos com "peço o registro do meu Éter" e "compro a licença de magia". |

Veredito da re-revisão: **CHANGES_REQUIRED**, só por causa do P1-4. A correção é local (regex
mais 2 testes). Depois dela o coordenador pode conferir os testes novos e pousar como
`APPROVED_WITH_FOLLOWUPS` sem outra rodada minha. Os follow-ups que continuam: smoke real da
§6, derrota em `law_enforcement` → prisão (sugestão) e o denominador de 15 perfis.

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec299_*.py tests/test_npc_knowledge*.py tests/test_spec298_fama_local.py tests/test_spec298_visibilidade.py tests/test_combat_lifecycle.py tests/test_router_interlocutor.py tests/test_fase51.py → 242 passed (c67a7bb5)
sonda probe_prison.py (c67a7bb5): viagem/descanso preso → permanece em na_anel_ferro (P1-1 ok)
sonda probe_lic.py (c67a7bb5): negações ok (P1-2); "Peço licença ao mercador…" → gold 250, licenses=[codigo_de_ferro] (P1-4)
sonda probe_travel.py (c67a7bb5): scene_block em na_anel_lama, vazio (P1-3 ok)
```
