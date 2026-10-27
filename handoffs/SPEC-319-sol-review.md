# SPEC-319 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-25 · **Commit revisado:** `2666aaf6`

## Escopo

Revisei `git diff main...spec-319` (34 arquivos, +1835/−31): `services/partial_narrative.py`,
`services/narrative_sink.py`, `llm_setup.py` (`stream_structured`/`stream_text`/`_stream_attempt`/
`_hedged_first`), `api.py` (sink + `_stream_turn_events` + `turn_delivery`), os 4 agentes
narradores, `mock_llm.py`, `playtest/latency_llm.py`, `usage_metering`/`audit_trace`,
`scripts/staging/vercel_env.py`, e o cliente `web/src` (`api.ts`, `App.tsx`, `useTypewriter.ts`).
Também li a cadeia final de guards dos narradores (storyteller 2091-2135, npc 1318-1486,
combat 984-1001/1541, loot 185-196) para responder à pergunta principal. Ficou de fora:
smoke real §6 (é do coordenador/dono) e Playwright/build.

### Pergunta principal: o que o jogador VÊ no stream e o pipeline final remove

Em fluxo só rodam o filtro de `[RESULTADO]` e o véu SPEC-293 (`StreamGuard`). O "flash" **não dura ms**:
o texto sai durante toda a geração (2–4 s no DeepSeek), e o `replace` só chega quando o nó
termina (evento `early_narrative` da 316) ou, com `RPG_EARLY_NARRATIVE` ≠ `on`, só no `state`
(depois do archivist/commit, segundos a mais). Classificação de cada guard:

| Guard final (prosa) | Onde | O que aparece no stream | Classificação |
|---|---|---|---|
| Segredo em narração mediada (SPEC-202 R11, `find_unrevealed`) | storyteller.py:2129 | frase-assinatura de segredo não revelado (ex.: "pacto com Valerius") | **Precisa de guard no stream** (P1-1). Spoiler é irreversível depois de lido. |
| Achado falso em boato (SPEC-315 §6.2, `_neutralize_false_find`) | storyteller.py:2100 (`rumor_nothing` já é conhecido na 1449, antes do LLM) | "você encontra o esconderijo/tesouro" → depois "nada" | Deveria ter guard (P2-1); é barato porque a condição é conhecida antes. |
| Eventos inválidos → narração inteira trocada por fallback + `[SISTEMA]` | storyteller.py:2104 | a mudança permanente inventada inteira (ex.: morte de NPC) | Flash aceitável pela D3, mas é o pior caso de UX; medir a taxa por motivo (P2-4). |
| Preâmbulo meta / imperativo ecoado / espaços e pontuação normalizados (`sanitize_player_facing`) | storyteller.py:2098, npc/combat/loot `sanitize_meta_preamble` | "Aqui está a narração:", "Descreva…", espaço duplo | Cosmético, mas gera `replace` falso; dá para tratar no stream (P2-3). |
| Ouro do jogador (`reconcile_player_gold_claims`) | storyteller.py:2101 | saldo errado por alguns segundos | Flash aceitável. |
| Abertura repetida (`vary_repeated_opening`) | storyteller.py:2122, npc 1324 | o texto sem o prefixo neutro → `replace` do texto todo | Flash aceitável, mas infla `replace` e derruba o `identical_to_final` (P2-5). |
| Combate: `species_drift`, `narrative_or_fallback` (números do log) | combat.py:994, 1541 | dano/espécie errados → troca pelo log determinístico | Flash aceitável (números corrigidos pelo Python). |
| Loot: `_validated_narrative` (itens/ouro inventados) | loot.py:193 | item/quantia inventados | Flash aceitável. |
| Regra de ouro (SPEC-308) / fações ocultas (SPEC-314) | contexto do prompt (`perceived_world`, `context_builder`), não prosa | só se o LLM inventar; nomes ocultos já passam pelo véu SPEC-293 em fluxo | OK, sem guard de prosa contornado. |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | services/narrative_sink.py:168-203; agents/storyteller.py:2019 e 2129 | `_guard_mediation_secret` (SPEC-202 R11) só roda no texto final. Com `interlocutor_reason ∈ MEDIATION_REASONS` o stream mostra ao vivo a frase-assinatura do segredo não revelado, por segundos, até o `replace`. É vazamento de segredo, não um flash cosmético. | Com mediação, não streamar (passar `invoke` no storyteller) **ou** dar ao `StreamGuard` um verificador de assinaturas: janela do tamanho da maior frase de `SECRET_SIGNATURES`; quando `find_unrevealed` acerta, `broken=True` (o `replace` final corrige). Teste: narração mediada com assinatura → nenhum delta contém a assinatura. |
| P1-2 | P1 | agents/npc.py:1314-1315 vs 1484 | O stream da NPC sai como `"` + fala, mas a mensagem final é `**{nome}:** "fala"\n*(ação)*`. `final.startswith(shown)` nunca é verdade, então **todo turno de NPC com tokens vira `replace`** (confirmei com um probe: `StreamGuard(prefix='"')`). O comentário "a mensagem final abre com aspas" está errado; isso quebra o critério de `replace` < 5 % e faz a fala "pular" no fim de todo diálogo. Não há teste de NPC com tokens. | `prefix=f'**{npc_data["name"]}:** "'` (o `npc_data` já existe antes da chamada) e um teste SSE de rota NPC com `RPG_TOKEN_STREAM=on` que verifique ausência de `replace` no caminho feliz. |
| P2-1 | P2 | agents/storyteller.py:1449/2019 | Achado falso em boato (SPEC-315) aparece ao vivo e depois é neutralizado. `rumor_nothing` é conhecido antes da chamada. | Não streamar quando `rumor_nothing` (ou aplicar `_neutralize_false_find` por frase fechada no guard). Dá para fazer junto com o P1-1 usando um parâmetro `stream=False` em `narrate_structured`. |
| P2-2 | P2 | llm_setup.py:1573-1590 (`abandon`) e 1637 | `abandon()` marca `hedge_lost` em **todo** candidato iniciado ≠ vencedor, inclusive o que já terminou com falha. Probe: 1º dá `stream_error` antes de qualquer chunk → 2º começa na hora (não é hedge) → telemetria `[m1 stream_error, m2 success, m1 hedge_lost]`. A tentativa conta duas vezes, e o `hedge_lost` é "recebido" em `usage_metering`, o que gera gasto estimado fantasma para um 429. | Pular em `abandon` os índices em `ended`. Emitir `hedge_lost` só se a tentativa ainda estava viva (e só quando `hedged=True`). Teste do cenário. |
| P2-3 | P2 | services/narrative_sink.py:87-148 | O `StreamGuard` não reproduz as transformações baratas e determinísticas do final: preâmbulo meta no início, normalização de espaço/pontuação de `sanitize_player_facing`. Cada uma gera `replace` falso. | Segurar o 1º trecho até `_META_PREAMBLE` não poder mais casar (~120 chars ou 1ª quebra de linha) e aplicar o mesmo colapso de espaços no texto limpo. |
| P2-4 | P2 | api.py:6479-6496 | `token_replace` é um booleano sem motivo; a §6 não consegue separar replace por guard × por formatação. | Logar `replace_reason` (prefixo/abertura/guard/fallback) ou ao menos `shown_len`/`common_prefix_len`. |
| P2-5 | P2 | api.py:6577 | Em `shadow`, `identical_to_final` é igualdade estrita após `strip`, mas o `on` decide pelo `startswith`. Final que só estende o texto (sufixo) conta como "diferente" sem gerar `replace`, e NPC (P1-2) e abertura anti-repetição sempre dão `false`. A meta D1 de ≥ 95 % mede outra coisa. | Logar também `would_replace = not final.startswith(shadow)` e usar esse campo como critério do D1 (atualizar §6). |
| P2-6 | P2 | api.py:1500, 5517, 5544 | `hedge_lost` entra como falha em `llm_failures`, `llm_failed_attempts` e `llm_by_tier.failed` (e como `fallbacks` quando o perdedor é o índice 1), mas o `audit_trace.turn_errors` o ignora. Os contadores ficam inconsistentes e os painéis de taxa de falha sobem com o hedge ligado. | Excluir `hedge_lost` de falha/fallback nos três pontos (ou contar à parte em `llm_hedge_lost`). |
| P2-7 | P2 | llm_setup.py:1608-1617 | O teto de 10 % é por processo e libera 1 hedge no 1º call (`max(1.0, …)`). No Vercel cada instância fria pode fazer hedge na 1ª chamada, então com tráfego baixo a razão real pode passar bem de 10 %. | Documentar na spec/§6 que o teto é melhor-esforço por instância e conferir `hedged`/turnos no smoke 3. Opcional: exigir `calls ≥ 10` antes do 1º hedge. |
| P2-8 | P2 | llm_setup.py:1369 (`_stream_attempt`) | O caminho de stream (que vale por default em `shadow`) não chama `_input_for_provider` (instrução quando a última mensagem é `AIMessage`), não faz a regeneração semântica no mesmo provider e não confere `wrong_tool`, ao contrário do `invoke`. O desvio está registrado (Histórico §2), mas com o default `shadow` todo turno SSE de staging muda de caminho LLM ao pousar. | Aplicar `_input_for_provider(input, provider)` no stream (custo zero) e medir `invalid_structured` por candidato no smoke 1 contra o baseline. |
| P2-9 | P2 | web/src/hooks/useTypewriter.ts:62-68 | Num `reset`, o texto vazio cai no ramo `!text` e chama `onDone`. Hoje as entradas de stream não têm `onTypewriterDone`, então é inofensivo, mas é frágil. | Tratar o plano `clear` antes do ramo `!text` sem chamar `onDone`. |
| P2-10 | P2 | playtest/latency_llm.py:183-189 | `stream_structured`/`stream_text` sempre existem no wrapper, mesmo quando o `inner` não os tem (FallbackLLM), o que daria `AttributeError` se houvesse sink. Hoje não acontece porque o playtest não liga sink. | Delegar só se `hasattr(self._inner, …)`, senão cair no `with_structured_output(...).invoke`. |

### O que está correto (conferido)

- **Extrator (R1/R10):** máquina O(n) correta para `\" \\ \/ \b \f \n \r \t \uXXXX`, pares surrogate,
  escapes cortados entre deltas, chave fora da 1ª posição e valor não-string (→ `_DEAD`).
  Probe com 1 char por delta (`ensure_ascii` true/false, emoji, `ç`) bate com `json.loads`.
  Surrogate órfão vira U+FFFD no stream, enquanto o final mantém o surrogate cru; isso só gera
  `replace`, aceitável. `test_schema_order` trava `narrative` (3 variantes) e `dialogue`.
- **`stream_structured`:** inválido → `invalid_structured` + `on_reset` + próximo candidato, sem
  efeito colateral duplicado. O resultado é validado uma vez com `model_validate_json`/`model_validate`.
  Exausto → `AIMessage("")`, e o `isinstance` dos nós continua valendo. FallbackLLM sem
  `stream_structured` → `invoke`.
- **Hedge:** o perdedor é cancelado no próximo chunk (`cancelled()` + `close()` do iterador).
  Só os deltas do vencedor chegam ao sink, o estruturado é aplicado uma vez (pelo coordenador)
  e há no máximo 1 hedge por chamada. O contexto vai para a thread por `copy_context`. Os
  deltas são emitidos na thread do nó, onde o contextvar do sink vale. O `action_id`
  idempotente não é afetado (o replay não chama o LLM). Ressalva: o perdedor segura um slot de
  `_provider_slot` até o 1º chunk/timeout, o que é aceitável com o default `0`.
- **SSE/cliente (com a SPEC-320 já em `web/src`):** `reset` limpa a entrada (`resetStreamText`).
  Quando o final só estende o texto, `_finish_tokens` manda apenas o sufixo (correto, porque o
  `tok["text"]` é exatamente o que foi exibido). Divergência → `replace` com `done:true`.
  O `follow` não tem atraso artificial e o markdown parcial cai em `jump`, que é inofensivo.
  O `narrative_shown` considera `tok["text"]`.
- **Shadow:** nada visível muda (os deltas são descartados no SSE e o `pseudo_streaming`
  continua `true`). O caminho de LLM muda, ver P2-8.
- **`vercel_env`:** `RPG_LLM_HEDGE_MS` aceita só `0/3000/4000/6000/8000`, com teste.
  `RPG_TOKEN_STREAM` aceita off|shadow|on.
- Segurança/integridade: nenhum arquivo em `evals/` mudou, não há writer persistente novo,
  nada novo no save. Erro de stream registra `str(e)` só em `stream_interrupted`, igual ao
  `stream()` da SPEC-236, e a API reduz a `_safe_error_type`.

## Correções aplicadas

P1-1, P1-2 e P2-1…P2-10 corrigidos no commit de correção (ver Histórico de mudanças da spec).

## Pendências

- §6 (smoke real) segue com coordenador/dono. Ligar `RPG_TOKEN_STREAM=on` no staging **só com
  `RPG_EARLY_NARRATIVE=on`**: sem isso o `replace` só chega no `state` e o flash dura o turno inteiro.
- P2-2, P2-4…P2-10 podem virar follow-up se o coordenador preferir; P1-1, P1-2 (e P2-1, mesmo
  mecanismo do P1-1) antes do pouso.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_partial_narrative.py tests/test_schema_order.py tests/test_stream_structured.py tests/test_llm_hedge.py tests/test_streaming.py tests/test_latency_timeline.py tests/test_spec192_vercel_env.py → exit 0 (96 passed)
cd web && npm test → 169 pass, 0 fail
probe (scratchpad, fora do repo): hedge 1º-falha → [m1 stream_error, m2 success, m1 hedge_lost]; extrator 1-char == json.loads; NPC prefix nunca é prefixo do final → 5 passed
```

## Re-review (delta `2666aaf6..2b368347`)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (papel Sol) · **Data:** 2026-10-25 · **Commit revisado:** `2b368347`

### Conferência dos achados

| ID | Status | Evidência |
|---|---|---|
| P1-1 | **Resolvido** | agents/storyteller.py:2013-2032: `_stream_ok = not rumor_nothing and interlocutor_reason ∉ MEDIATION_REASONS` → `narrate_structured(..., stream=False)` → `invoke` (narrative_sink.py:192). Probe de ponta a ponta (scratchpad): narração mediada com "pacto com valerius" → **0 deltas**, final neutralizado ("A cena não deixa transparecer…"); controle sem mediação → a assinatura streama (o probe é sensível). **Outros caminhos:** `find_unrevealed` só é usado como guard de prosa em storyteller.py:2138. NPC, combate (`stream_text`) e loot (`stream_text`) não têm guard de segredo no texto final, então o stream não expõe nada que o final não exporia (beats são saneados no planner por `sanitize_beat`, e o resto é auditoria). |
| P1-2 | **Resolvido** | agents/npc.py:1315 `prefix=f'**{npc_data["name"]}:** "'`; o `StreamGuard` só aplica o prefixo com texto não vazio. `test_npc_stream_is_prefix_of_final_message` (nó) e `test_npc_route_tokens_do_not_replace` (SSE; rodou, não pulou) confirmam: `live` presente e 0 `replace`. |
| P2-1 | Resolvido | mesmo gate do P1-1 (`rumor_nothing`). |
| P2-2 | Resolvido | llm_setup.py `abandon`: pula `i in ended`. Probe: `[m1 stream_error, m2 success]`, sem `hedge_lost`; teste `test_failed_first_is_not_reported_as_hedge_lost`. |
| P2-3 | Resolvido (ver F-2) | `HOLD_CHARS=120`/newline + `sanitize_player_facing` no texto limpo + corte antes do espaço; `test_stream_guard_normalizes_like_final_text`. |
| P2-4 | Resolvido | api.py `sse.token_replace` com `reason`/`shown_len`/`final_len`/`common_prefix_len` (sem conteúdo). |
| P2-5 | Resolvido | `would_replace = not narrative.startswith(shadow)` no `sse.token_stream_shadow`; spec atualizada. |
| P2-6 | Resolvido | api.py `_NOT_A_FAILURE` em `llm_failures`, `by_tier.failed` e `llm_failed_attempts`; `hedge_lost` fora de `fallbacks`. |
| P2-7 | Resolvido | `HEDGE_MIN_CALLS=10` + razão de 10 %; teste de instância fria; §7 diz que é melhor-esforço por instância. |
| P2-8 | Resolvido (ver F-1) | instrução neutra quando a última mensagem é `AIMessage`; JSON inválido → `_invoke_single` (invoke com regeneração semântica no mesmo candidato). |
| P2-9 | Resolvido | useTypewriter.ts:62: `reset` limpa sem `onDone`; teste node. |
| P2-10 | Resolvido | latency_llm.py: `hasattr` antes de delegar. |

### Follow-ups (não bloqueiam)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| F-1 | P2 | llm_setup.py:1504; services/narrative_sink.py:208 | Fallback de JSON inválido para `_invoke_single`: o stream do mesmo candidato já pode ter emitido deltas, e o retorno não-`None` não dispara o `reset()` do `_stream_route`. O `narrate_structured` ainda chama `guard.finish()` e emite o **resto retido do texto inválido**. O jogador vê o parcial da tentativa inválida e depois recebe um `replace` com a narração regenerada (diferente). Não vaza nada, mas contraria o R4 ("falha no meio ⇒ reset"). | Antes de `_invoke_single`, sinalizar o reset (ex.: devolver um sentinel ou chamar o `reset` do `_stream_route` via callback) e não chamar `finish()` quando o resultado não veio do stream. Teste: fake com stream inválido + invoke válido → `reset` antes do final e nenhum delta do texto inválido depois dele. |
| F-2 | P2 | services/narrative_sink.py:113-121 vs agents/npc.py:1319 | O guard aplica `sanitize_player_facing` (remove frases "Descreva…/Narre…", marcadores e espaço antes de pontuação) também para NPC/combate/loot, cujo texto final só passa por `sanitize_meta_preamble`. Diálogo com "Narre-me o que viu." ou espaço duplo → stream ≠ final → `replace` espúrio (raro). | Parametrizar a normalização por nó (`normalize=sanitize_meta_preamble` para NPC/combate/loot) ou aceitar e acompanhar pelo `sse.token_replace.reason`. |
| F-3 | — | §6 | Ligar `on` no staging só com `RPG_EARLY_NARRATIVE=on`; critério D1 = `would_replace` < 5 %. | Coordenador/dono. |

### Comandos rodados (re-review)

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_partial_narrative.py tests/test_schema_order.py tests/test_stream_structured.py tests/test_llm_hedge.py tests/test_streaming.py tests/test_latency_timeline.py tests/test_spec192_vercel_env.py → exit 0 (103 passed, 0 skipped)
cd web && npm test → 170 pass, 0 fail
probe scratchpad (mediado com assinatura / controle / hedge 1º-falha / extrator) → 7 passed
```


## Revisão do follow-up loot (27/10, commit 2300913d)


> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / papel Sol · **Data:** 2026-10-27 · **Commit revisado:** `2300913d`

## Escopo

Branch `fix-319-loot`, 1 commit sobre a `main` (`2300913d`): `agents/loot.py` (`_narrate`
passa `stream=False` sempre), `tests/test_streaming.py` (teste novo parametrizado) e
nota no histórico da `specs/SPEC-319-*.md`. Também li o caminho SSE em `api.py`
(`_timeline_progress`, `_emit_early`, `_finish_tokens`, tratamento de `early_narrative`
e `response`), `services/narrative_sink.narrate_text`, `services/turn_delivery.early_narrative`
e `agents/combat.py::_narrate` e o pós-processamento dele. Fora do escopo: o `tail` do
storyteller (1/58), que a spec deixa em observação.

## Verificações pedidas

1. **A narração chega cedo e o estado final é idêntico: OK.** Com `stream=False`,
   `narrate_text` cai direto em `llm.invoke(messages)` (`services/narrative_sink.py:376-377`),
   que é o mesmo caminho do POST/CLI. Assim não sai nenhum `narrative_delta`/`reset` e
   `tok["text"]` fica vazio. `loot_agent` está em `NARRATING_NODES`
   (`services/turn_delivery.py:13`), então `_timeline_progress` calcula `early_narrative`
   na update do nó (`api.py:5870-5879`). Com `tok["text"]` vazio, `api.py:6666-6675` vai
   para `_emit_early(text)`, não para `_finish_tokens`, e nunca dá `replace` por `tail`. O
   `res.content` passa pelo mesmo `sanitize_meta_preamble` → `_validated_narrative` de
   antes, e o estado não depende do sink. O hedge (`llm_setup.py:1321`) vale só para
   chamadas com schema no tier FAST, então o loot plain não perde hedge.
2. **Nenhum outro caminho de loot streama tokens: OK.** `agents/loot.py` só importa o sink
   em `_narrate` (linha 177). O `TradeIntent` estruturado (linha 152) usa
   `with_structured_output(...).invoke`, sem `stream_structured`/`stream_text`. Os 4
   pontos de chamada (`263`, `379`, `408`, `512`) passam todos por `_narrate`.
3. **O combate tem o mesmo risco de `tail`/`replace`: SIM (só apontado).** Ver P2-1.
4. **O teste falha sem o fix: OK.** Troquei `agents/loot.py` pela versão da `main` e as 2
   parametrizações falharam (`seen == [True]`). Restaurei o arquivo e o `git status`
   ficou limpo. O teste só é válido porque o MockLLM não é `is_fallback`. Se fosse, `seen`
   ficaria `[]` e o teste falharia, então não há falso verde silencioso.

Guard de structured output: inalterado (o `TradeIntent` mantém o guard). Valor de LLM sem
validação: nenhum novo. Writer persistente: nenhum. Segredo em log: nenhum. `evals/`:
não tocado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `agents/combat.py:1506` (+ `2111-2112`, `1513-1517`) | O combate streama tokens (`narrate_text` com `stream=True` por padrão), mas o texto final é reescrito depois do stream: `summ.narrative_or_fallback(conflict_sum, narrative)` no fim do combate (`combat_over`), fallback determinístico inteiro quando `species_drift` dispara, e `sanitize_meta_preamble`. É a mesma classe de causa do loot: `replace` (`tail`/`start`) nos turnos de vitória/fim e no drift de espécie. | Follow-up, não corrigir aqui: medir `token_replace` por rota `combat` no staging. Se aparecer, passar `stream=not combat_over` (o resumo canônico só existe no fim) e/ou mover o guard de espécie para o `StreamGuard` (`risk`). |
| P2-2 | P2 | `tests/test_streaming.py:743-763` | O teste prova só o argumento `stream=False`. Não há teste de integração SSE da rota loot que confirme `early_narrative` sem `live`/`replace`, no estilo de `test_npc_route_tokens_do_not_replace`. | Opcional: acrescentar um teste SSE de rota loot que confira ausência de `live` e de `replace` e presença do chunk antecipado. |
| P2-3 | P2 | `handoffs/SPEC-319-loot-stream-review.md` | O nome pedido pelo coordenador (`-loot-stream-review`) não segue o padrão `SPEC-NNN[-papel]-<tipo>` do template. `scripts/check_handoff_names.py` pode rejeitar. | Renomear no pouso se o lint reclamar (ex.: `SPEC-319-sol-review.md`, se não colidir). |

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

- P2-1 → coordenador decide se vira nota na SPEC-319 (observação de staging) ou uma spec nova.
- P2-2 → opcional, junto do P2-1.

## Comandos rodados

```text
git diff main...HEAD --stat → 3 arquivos (+30/-3)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -W ignore tests/test_streaming.py tests/test_stream_structured.py tests/test_loot*.py -n 2 → todos verdes
(agents/loot.py da main) pytest tests/test_streaming.py::test_loot_narration_never_streams_tokens → 2 failed (esperado); arquivo restaurado, git status limpo
```
