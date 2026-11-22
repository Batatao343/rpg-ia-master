# SPEC-421 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Rodadas:** 3ª conferência em `f50204a5` (abaixo); a re-revisão de `60ae3418` aprovou; a 1ª rodada, em `1e72a00b`, pediu mudanças.
> **Revisor:** Opus 5.5 / Sol (`spec-reviewer`) · **Data:** 2026-11-22 · **Commit revisado:** `f50204a5`

## Conferência de `f50204a5` (`git diff 356ca5a0..f50204a5 -- services/ tests/`)

O commit move `_compose_risk` para `services/mediated_stream.py` como `compose_risk` e troca dois
`try/except: pass` por `swallow(...)`, para devolver as contagens de ruff do baseline.

1. **Falha fechada no produto: preservada.** `compose_risk` (`services/mediated_stream.py:166-181`) tem a mesma
   lógica de antes, e `narrate_structured` o chama no mesmo ponto (`services/narrative_sink.py:389`). Sondei com
   `compose_risk`: `extra` que lança dá `check_error`, `base` que lança dá `check_error`, e `compose_risk(None, b)`
   é o próprio `b`. Um `StreamGuard` cujo `base` lança mostrou `''`.
   - **Mas nenhum teste trava isso (P1-2).** Com o mutante `mut_compose_open` (a exceção dentro de `composed`
     vira `""`, falha aberta), `tests/test_mediated_stream.py` fica **0 falhas**. `test_gate_exception_holds_rest`
     (`tests/test_mediated_stream.py:366-378`) só exercita o gate, que engole a própria exceção
     (`services/mediated_stream.py:52-56`). Por isso o `except` do `composed` nunca roda em teste. A lacuna já
     existia em `1e72a00b` e eu não a peguei na 1ª rodada.
2. **`swallow`: não derruba o turno nem libera texto.**
   - Não libera texto: o `StreamGuard` decide o que sai antes do `emit`. Uma exceção no sink externo só deixa de
     entregar aquele delta, e uma no observer só deixa de medir.
   - Não derruba o turno: `test_tap_observer_e_sink_externo_que_lancam_nao_derrubam_o_stream` está verde.
   - **Mas pode logar conteúdo (P2-2).** `_log.exception` grava a mensagem da exceção e o traceback, a cada
     chamada. Na sonda, `RuntimeError("pacto com valerius")` vindo do `base` apareceu inteiro na saída do log.
   - Isso fere a convenção do projeto. `log_fallback` (`observability/telemetry.py:242-256`) existe para isso:
     "só a classe, nunca a mensagem", 1× por (nó, motivo) no turno, e já conta em `rpg.turn.fallbacks`.
   - Há ainda o volume: `swallow` roda por delta. Um sink externo que lança em todo delta (cliente que caiu)
     gera um traceback por token.
   - Não é aceitável como está. Deve logar só o tipo.
3. **Import no topo de `narrative_sink`: sem ciclo e sem efeito.**
   - `services/mediated_stream.py` só importa stdlib no topo (`:12-20`). O resto é import tardio dentro das
     funções.
   - Importar os dois módulos nas duas ordens, em processo limpo, funciona.
   - No turno não mediado, `compose_risk(None, base)` devolve `base` e `_observe` não faz nada com
     `observer=None`, então o caminho fica idêntico ao de antes.
4. **Mutantes e fuzz.** Os seis mutantes anteriores dão os mesmos resultados da re-revisão: I1 cai 32/32 nos três
   do gate, `post_veil` derruba o teste do véu e os dois do `_RUN` derrubam o teste de P3-4. O fuzz de 6.000
   casos deu 0 vazamentos. `pt.sh -n 0 tests/test_mediated_stream.py tests/test_ruff_counts.py` deu 97 passed.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-2 | P1 | `tests/test_mediated_stream.py:366-378` | A falha fechada de `compose_risk` (R5/I7) não tem trava: o mutante de falha aberta passa 100 % verde. | Teste novo: `compose_risk(lambda s: "", boom)` e `compose_risk(boom, lambda s: "")` devolvem `"check_error"`, e um `StreamGuard(risk=compose_risk(lambda s: "", boom))` com `feed(CLEAN) + finish() == ""`. Conferir que reprova com `mut_compose_open`. |
| P2-2 | P2 | `services/mediated_stream.py:163,178` | `_log.exception` grava a mensagem da exceção (pode conter frase da narração ou assinatura) e o traceback, sem dedup, por delta no `swallow`. | Trocar por `log_fallback("sse", "stream_observer_failed", exc)` no `swallow` e `log_fallback("sse", "stream_risk_compose_failed", exc)` no `composed` (import tardio, como no resto do módulo). Isso grava só a classe, 1× por turno, e mantém o `noqa: BLE001` justificado. |

Evidência desta conferência:

```text
compose_probe.py → extra lança: check_error · base lança: check_error · extra None é base: True · guard com base que lança mostra: ''
compose_probe.py → o log de _log.exception trouxe "RuntimeError: pacto com valerius" (mensagem inteira)
mut_compose_open → 0 FAILED em tests/test_mediated_stream.py (P1-2)
mut_post_veil 1 · mut_gate_off 51 · mut_no_gate 36 · mut_find_never 56 · mut_no_clear 1 · mut_no_except_reset 1 (iguais à re-revisão)
fuzz421.py (6000 casos) → 0 vazamentos
pt.sh -n 0 tests/test_mediated_stream.py tests/test_ruff_counts.py → 97 passed
import nas duas ordens (processo limpo) → ok
```

## Re-revisão (`git diff fb7ccb4f..60ae3418`)

| Achado | Estado | Evidência |
|---|---|---|
| P1-1 | corrigido | `tests/test_mediated_stream.py:228-244`: o mapa `{"Valerius": "o Regente"}` põe o nome oculto dentro da assinatura. As fatias são 1, 7 e 100000. Asserções: houve hold com `rule == "mediation_secret"`, nenhum delta contém "Regente", "Valerius" nem "pacto com", e a 1ª frase saiu. Sem mutação: verde. Com `mut_post_veil`: **reprova**. |
| P2-1 | corrigido | `:306-322`: `_comparable(out)` compara o retorno inteiro do nó; as mensagens entram como (tipo, conteúdo). |
| P3-1 | corrigido | `git diff main -- tests/size_budget.json` mostra uma única linha, `agents/storyteller.py` 3020 → 3017. `size_budget.py` passa (rc 0). |
| P3-2 | corrigido | Spec F-1: o espaço duplo saiu da lista de lacunas, com a razão (`prose_guard.py:106`). NBSP/zero-width e markdown foram levados para D2. |
| P3-3 | corrigido | `:530`: `assert llm.stream_calls == 1 and llm.invokes == 0`. |
| P3-4 | corrigido | `services/mediated_stream.py:106,109,114`: o caminho sem gate começa limpando o `_Run` (`_RUN.set(None)`). O caminho com gate guarda o token e dá `reset(run_token)` no `except`. O código está certo: o `reset` só restaura o valor anterior num turno que já está lançando, e o próximo `narrate` limpa ou substitui. |

**P3-4, o teste.** O executor alegou que o teste não prova a limpeza no início de `narrate`. A alegação está
errada. Rodei duas mutações em `test_failed_turn_does_not_leak_run_into_next_after_final`:

- `mut_no_clear` tira o `_RUN.set(None)` do caminho sem gate. O teste reprova em `:607`: o `_Run` plantado gera
  um `sse.mediated_stream` falso.
- `mut_no_except_reset` tira a limpeza no `except`. O teste reprova em `:602`: o `_Run` sobra depois do nó que
  falhou, porque a exceção atravessa `narrate` antes de o nó engoli-la.

O teste cobre as duas metades e é aceitável como está. Não falta caso.

**`staging_flags.json`.** Ganhou `"RPG_MEDIATED_STREAM": "shadow"`, o que bate com D1. O default da `main`
continua `off`: `config/flags.yaml` tem `default: "off"` e `mediated_stream_mode()` lê `off` quando a variável
falta. O preset só vale para `vercel_env.py` no staging. Os testes `test_spec192_vercel_env.py` e
`test_spec325_flags.py` passaram.

**Regressão.** Nenhuma. Os mutantes `mut_gate_off`, `mut_no_gate` e `mut_find_never` continuam derrubando os 32
casos de I1, agora também com o teste do véu. O fuzz de 6.000 casos no HEAD novo deu 0 vazamentos.

Achados restantes: nenhum. `APPROVED`.

---

## 1ª rodada (`1e72a00b`): `CHANGES_REQUIRED`

## Escopo

Branch `spec-421`, `git diff main...HEAD` (merge-base `84a3266a`): `services/mediated_stream.py` (novo),
`services/narrative_sink.py`, `agents/storyteller.py`, `config/flags.yaml`, `observability/events.py`,
`docs/operacao/EVENTOS_DE_LOG.md`, `scripts/staging/vercel_env.py`, `tests/size_budget.json`,
`tests/test_mediated_stream.py` (novo), `tests/test_stream_structured.py`, spec. Fora: staging/§6 (não rodei
nada contra staging nem com chave real), suíte completa (coordenador).

### Pontos pedidos pelo coordenador

1. **I1 / I4 (contenção por frase).** Vale. `SECRET_SIGNATURES` (`services/secret_signatures.py:17-42`) é
   estático, sem `.!?`, `\n`, `\r` nem espaço nas pontas. O corte é `((?<=[.!?])\s+|\n+)`
   (`services/narrative_sink.py:137`): só quebra em espaço precedido de `.!?` ou em `\n`, então nenhuma
   ocorrência de assinatura atravessa frases. Abreviação (`Sr. Valerius`) quebra antes do nome, e as
   assinaturas não têm ponto. Reticências `…`, `."`, `!"` e travessão não quebram, então a frase só fica
   maior e continua contendo a assinatura. Texto com menos de 120 caracteres ou sem ponto final: a última
   parte nunca é avaliada nem mostrada antes de `finish()` (`:270-272`). `finish()` avalia a última com
   `final=True` (`:268-276`). O mostrado é sempre `conceal(pre_t)[:safe]` com `safe ≤ cap`, e `cap` só cobre
   frases fechadas e já avaliadas (`:294-310`). Rodei um fuzz próprio com 6.000 casos: 4 caixas,
   aspas/travessão/markdown/`Sr.`/`…`/`?!`, recibo `[RESULTADO]`, `[SISTEMA]`, separadores `\n`, `\n\n`,
   `\r\n`, `\t` e espaço duplo, véu, fatias de 1 a 10.000 caracteres, só com o gate (sem o checker de
   evidência). Resultado: **0 vazamentos**.
2. **Mesmo estado.** Sim. `secret_gate(t.scene_state)` sai de `agents/storyteller.py:2295` e o filtro final
   usa o mesmo objeto em `:2392-2393`. `t.scene_state` só é reatribuído em `:1715` e `:2092`, os dois antes
   do narrador. O gate avalia o `pre` (antes do véu), como o final. Nada muda o estado entre as duas
   chamadas. O stream só aplica a mais que o final o `remove_receipts`/`_SYSTEM_PREFIX`, que apaga texto e
   nunca cria uma assinatura invisível ao gate. O final checa `interlocutor_reason` no `scene_state`, que é
   `{**t.state, ...}`, então o gate nunca é mais permissivo que o final.
3. **Desvios declarados.** Aceitáveis.
   - `stream_plan` exige sink ativo (`services/mediated_stream.py:71`), o que evita que o tap ligue o
     stream sozinho em POST/CLI.
   - `bind_tap` é um `ContextVar.set` com `unbind(token)` em `finally` (`:113-117`): não vaza para outra
     requisição nem outra thread.
   - Turno não mediado: `narrate` chama `fn` direto (`:107-108`) e `_observe` não faz nada com
     `observer=None`. O stream comum fica byte a byte igual.
   - Em `shadow`, `forward=False` (`services/narrative_sink.py:70`): o externo não recebe delta nem
     `reset`. Coberto por I10 e verde.
   - Em `off`, sai `_NO_STREAM` (`invoke`), como antes. `test_mediated_narration_is_never_streamed` está
     verde.
4. **Falha fechada.** O gate devolve `check_error` (`services/mediated_stream.py:52-56`) e o composto também
   (`services/narrative_sink.py:367-371`). Uma regra não vazia para o stream naquela frase e segura o resto.
   `test_gate_exception_holds_rest` está verde. O `noqa: BLE001` acompanha `log_fallback`, como pede a
   convenção do `pyproject.toml:83`.
5. **R9.** `git diff main...HEAD -- services/secret_signatures.py` vem vazio, e `_guard_mediation_secret`
   (`agents/storyteller.py:499-529`) também não mudou. O filtro continua sendo chamado sempre, em
   `:2392-2394`, antes de `after_final`.
6. **Testes.** As mutações estão abaixo. Tirar o gate ou fazer `find_unrevealed` nunca reprovar derruba I1.
   Um teste passa com o produto quebrado: P1-1.
7. **`size_budget.json`.** O gate (SPEC-407) só exige `--tighten` quando a folga passa de `SLACK_FILE = 25`
   (`scripts/dev/size_budget.py:29,109`). As folgas de combat (2), llm_setup (1), rag (6) e
   `_chase_party_choices` (3) estavam dentro da tolerância. Baixar esses tetos não era exigido e fica fora do
   escopo (P3-1). Os valores novos batem com o que a `main` mede hoje, então não quebram a `main`.
8. **`vercel_env.py`.** Só põe o nome nas duas listas (`:92`, `:159`). `scripts/staging/staging_flags.json`
   não tem `RPG_MEDIATED_STREAM`. Como a flag está em `OPTIONAL_FLAGS`, um push **apaga** a variável no
   Vercel e o staging roda `off`. Isso bate com o default da `main` (D1), mas não com "staging `shadow`":
   falta a Etapa 4 do coordenador, `"RPG_MEDIATED_STREAM": "shadow"` em `staging_flags.json`. Um valor posto
   à mão some no próximo push.
9. **Guard, saldo, registros.** Um `AIMessage` vindo do stream cai em `on_reset` e volta como está
   (`services/narrative_sink.py:432-436`). O `isinstance` em `agents/storyteller.py:2333-2345` continua
   valendo. `storyteller.py` tem saldo de −3 linhas (3020 → 3017) e `routes/turn.py` não tem diff. A flag
   está em `config/flags.yaml` e o evento em `observability/events.py` e em `EVENTOS_DE_LOG.md`. Os testes
   de registro estão verdes.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_mediated_stream.py:228-236` | `test_concealed_name_gate_sees_pre_veil` não prova o nome. O nome oculto (`Corvo Negro`) fica fora da assinatura, então a frase é segurada pela assinatura tanto no texto pré-véu quanto no pós-véu. Com a mutação D (o risco avalia o texto **depois** do véu), `test_mediated_stream.py` + `test_stream_structured.py` ficam 100 % verdes. E o produto mutado vaza pelo apelido: com mapa `{"Valerius": "o Regente"}`, o stream mostrou ao vivo "Ela diz que o velho fez um pacto com o Regente em troca de ouro." (o correto mostra só a 1ª frase). Hoje o código está certo (`_risk_cap(cleaned, pre)`), mas nada trava isso, e é exatamente o caso que a spec pediu (§4 Etapa 1.2, último item). | Pôr o nome oculto **dentro** da assinatura: `monkeypatch` de `_conceal_map` → `{"Valerius": "o Regente"}`, frase "…fez um pacto com Valerius…". Afirmar que nenhum delta contém "Regente" nem "pacto com" e que houve `stream_risk_hold` com `rule=mediation_secret`. Conferir que reprova com a mutação D (o plugin está abaixo). |
| P2-1 | P2 | `tests/test_mediated_stream.py:298-306` | I2 promete "retorno do nó igual", mas o teste compara `sorted(out)`, só as chaves. Valores fora de `messages`/`narrative_rejections` (ex.: um campo derivado do caminho stream vs `invoke`) podem divergir sem reprovar. | Comparar o retorno inteiro (ou os campos persistidos, `messages` em `.content`), tirando só o que é não determinístico por natureza. |
| P3-1 | P3 | `tests/size_budget.json:9,15,22,48` | `--tighten` baixou tetos de arquivos que a spec não toca. O gate não exigia (folga ≤ 25), e isso tira a margem de branches paralelas que mexem em combat/llm_setup/rag. | Manter só `agents/storyteller.py: 3017` e reverter as outras quatro linhas. |
| P3-2 | P3 | `specs/SPEC-421-…md:109-111` | O F-1 diz que "pacto  com valerius" (espaço duplo) passa no final hoje. Não passa: `sanitize_player_facing` colapsa `[ \t]+` (`services/prose_guard.py:106`) antes do guard, e o teste de paridade cai no ramo "final reprovou". Faltam também lacunas reais que passam nos dois: NBSP/zero-width entre palavras e ênfase markdown partindo a assinatura (`*pacto* com Valerius`), que aparecem iguais na tela. | Corrigir o texto do F-1 e levar NBSP/zero-width/markdown para a spec de D2 (endurecer o filtro final). |
| P3-3 | P3 | `tests/test_mediated_stream.py:497-513` | O teste do guard de FallbackLLM só afirma que há mensagem. Não prova que o `AIMessage` veio do caminho stream. | Acrescentar `assert llm.stream_calls == 1 and llm.invokes == 0` (ou o equivalente no fake). |
| P3-4 | P3 | `services/mediated_stream.py:110` | `_RUN.set(run)` sem token. Se o turno lança entre `narrate` e `after_final` fora do `except` de `narrate`, o `_Run` velho fica no contexto e o próximo `after_final` no mesmo contexto loga um evento falso. Afeta só telemetria, nada vai ao cliente. | Opcional: guardar o token e dar `reset` em `after_final`, ou limpar no início de `narrate` sem gate. |

Nenhum caminho encontrado em que texto reprovado pelo filtro final chegue ao cliente antes da verificação,
no código como está. O P1 é de trava: o teste que deveria segurar uma regressão silenciosa no ponto mais
sensível (véu × assinatura) passa com o produto quebrado.

## Evidência verificada

### Re-revisão (`60ae3418`)

Mutações com `pytest -n 0 -rf tests/test_mediated_stream.py`, contagem de FAILED por teste:

```text
sem mutação          → 0 falhas
mut_post_veil        → test_concealed_name_gate_sees_pre_veil (1)
mut_gate_off         → concealed_name (1), gate_exception (1), gate_holds_every_sentence (15), shadow_logs (1), never_shows_secret (32)
mut_no_gate          → concealed_name (1), first_delta_ms (1), on_logs_replace (1), shadow_logs (1), never_shows_secret (32)
mut_find_never       → concealed_name (1), gate_exception (1), gate_holds (15), on_logs (1), shadow_logs (1), never_shows_secret (32), parity_gaps (1), first_sentence (1), second_paragraph (1), sse_no_live_leak (1)
mut_no_clear         → test_failed_turn_does_not_leak_run_into_next_after_final (:607)
mut_no_except_reset  → test_failed_turn_does_not_leak_run_into_next_after_final (:602)
fuzz421.py (6000 casos, só o gate) → 0 vazamentos
pt.sh -n 0 test_mediated_stream test_stream_structured test_size_budget test_flag_registry test_spec192_vercel_env test_spec325_flags → 179 passed
size_budget.py → rc 0 · ruff check → limpo
```

O `red_green` da 1ª rodada segue válido para os testes que não mudaram. O teste do véu continua verde também
na `main`: lá o turno mediado não streama e passa sem nada para mostrar. Por isso a prova que vale para ele é
a mutação acima, não a tabela.

### 1ª rodada

`bash scripts/dev/red_green.sh 421` (worktree, `1e72a00b`):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_mediated_stream.py::test_concealed_name_gate_sees_pre_veil | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_first_delta_ms_uses_injected_clock | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_gate_exception_holds_rest | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_gate_holds_every_sentence_final_rejects | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_gate_uses_final_guard_state | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_aimessage_result_falls_into_isinstance_guard | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_mediated_final_identical_across_modes | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_mediated_off_uses_invoke | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_mediated_on_logs_event_with_replace | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_reset_mid_stream | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_shadow_emits_nothing_and_logs | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_stream_mode | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_stream_never_shows_secret_sentence | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_stream_parity_known_gaps | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_mediated_turn_streams_before_end | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_without_scene_state_does_not_stream | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_mediated_without_sink_is_invoke | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_off_and_unmediated_log_no_mediated_event | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_plan_unmediated_is_unchanged | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_rumor_nothing_never_streams_even_with_flag_on | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_secret_already_revealed_by_summary | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_secret_in_first_sentence_has_no_deltas_and_final_extends | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_secret_last_sentence_of_paragraph_needs_replace | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_secret_second_paragraph_final_extends_shown | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_secret_signatures_fit_in_one_sentence | verde | verde | FAIL: nao prova a mudanca |
| tests/test_mediated_stream.py::test_sse_mediated_live_chunks_before_done | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_sse_mediated_secret_mid_paragraph_one_replace_no_live_leak | vermelho | verde | OK |
| tests/test_mediated_stream.py::test_stream_guard_risk_none_is_unchanged | verde | verde | FAIL: nao prova a mudanca |

red_green: 16/28 OK

Os 12 "verde/verde" são, em 11 casos, travas de contrato que a spec prevê ("o resto pode passar por acaso e é
válido como trava", §4 Etapa 1): off/`invoke`, sem sink, boato, I4, risco `None`, paridade F-1, AIMessage. A
exceção é `test_concealed_name_gate_sees_pre_veil`, que deveria discriminar e não discrimina (P1-1).

Mutações (plugins `-p` no scratchpad, `pytest -n 0` em `tests/test_mediated_stream.py`):

- **A, gate nunca reprova:** 40+ falhas. Os 32 casos de I1 caem em `:197` (`rule=mediation_secret`); o checker
  de evidência ainda segura o texto. I5 (`test_gate_holds_every_sentence_final_rejects`) e I10 também caem.
- **B, mediado streama sem gate** (o estado anterior ao P1-1 da 319): os 32 de I1 caem, mais I10, o log do
  `replace` e o `first_delta_ms`.
- **C, gate e checker de evidência desligados:** os 32 de I1 caem em `:192` (vazamento real afirmado), mais
  os de 1ª frase/2º parágrafo e o SSE `no_live_leak`.
- **D, risco avaliado no texto pós-véu:** 0 falhas em `test_mediated_stream.py` e `test_stream_structured.py`
  (P1-1). Uma sonda direta no `StreamGuard` com `{"Valerius": "o Regente"}` mostrou "…pacto com o Regente em
  troca de ouro." ao vivo.

## Correções aplicadas

—

## Pendências

- Etapa 4, coordenador: `"RPG_MEDIATED_STREAM": "shadow"` em `scripts/staging/staging_flags.json` antes do
  smoke §6. Sem isso o push apaga a variável e o staging fica `off`.
- D2, spec própria: além de acento, incluir NBSP/zero-width e ênfase markdown partindo a assinatura (P3-2).

## Comandos rodados

```text
git diff main...HEAD --stat → 11 arquivos, +1150/−74
bash scripts/dev/red_green.sh 421 → 16/28 OK (12 verde/verde: 11 travas previstas + P1-1)
pytest -n 0 -p mut_gate_off|mut_no_gate|mut_find_never tests/test_mediated_stream.py → I1 reprova nas três
pytest -n 0 -p mut_post_veil tests/test_mediated_stream.py tests/test_stream_structured.py → tudo verde (P1-1)
py.sh fuzz421.py (6000 casos, só o gate) → 0 vazamentos
bash scripts/dev/pt.sh -n 0 test_mediated_stream test_stream_structured test_streaming test_mediation_secret test_spec319_shadow_replay test_spec368_replace test_size_budget test_flag_registry test_log_event_registry → 187 passed
bash scripts/dev/pt.sh -n 0 (6 arquivos que importam vercel_env) → 97 passed
ruff check / format --check (arquivos alterados) → limpo
py.sh scripts/dev/size_budget.py → sem problemas
py.sh scripts/dev/dup_helpers.py --diff main...HEAD → 2 nomes de closure/método (gate, observe), falso positivo
```
