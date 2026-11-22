# SPEC-421 — latencia-fala-mediada-texto-ao-vivo

> **Status:** `in-progress` (aprovada pelo dono em 13/11; código pousado em 22/11 com a flag `off`; revisão Sol APPROVED na re-revisão; faltam o smoke §6 e a fase `shadow` no staging, que dependem de deploy)
> **Criada:** 2026-11-13 · **Atualizada:** 2026-11-13
> **Depende de:** SPEC-319 (`done`: stream de tokens, `StreamGuard`, `risk` por frase), SPEC-202 (`done`: mediação do narrador, R11 guard de segredo), SPEC-316 (`done`: `replace` silencioso, D4)
> **Desbloqueia:** —
> **Risco:** `alto` (toca o caminho do filtro de segredo da narração mediada e o que chega ao cliente ao vivo) → `spec-reviewer` (Opus) obrigatório
> **Requer:** staging (medição `shadow` → `on`, §6); nada de web
> **Domínios de revisão:** llm-structured, api (guia: `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`)
> **Evidência:** teste que falha antes: turno mediado (`interlocutor_reason=meta_to_narrator`) com LLM de stream roteirizado e sink ligado emite ≥ 1 delta antes do fim da chamada (hoje 0: `tests/test_stream_structured.py:236` afirma o contrário); bateria adversarial de assinaturas prova que nenhum delta passa do início da frase que o filtro final reprova.
> **Decisão do dono (13/11):** aprovou "o filtro passa a liberar frase por frase"; segredo não pode vazar na tela; revisor obrigatório; qualidade acima de velocidade.

---

## 1. Contexto & Objetivo

Na medição de 13/11 (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:22-23` e item 3 em `:54`), a fala
em que o narrador responde **sem** texto ao vivo teve o 1º texto aos **7,0 s** (n = 8); com texto ao vivo,
**3,6 s** (n = 5). Nesses turnos a narração chega inteira no fim (`first_token_server_ms: null`,
`pseudo_streaming: true` em `docs/auditorias/latencia-l0-2026-11-13/resultado.json:150-158`).

Causa no código: `agents/storyteller.py:2298-2300` desliga o stream quando
`interlocutor_reason ∈ MEDIATION_REASONS` (`services/interlocutor.py:53`: `meta_to_narrator`,
`ambiguous_multi_mediated`) ou quando `rumor_nothing`. Isso veio da revisão da SPEC-319
(`handoffs/SPEC-319-sol-review.md:26,40`, P1-1): o guard de segredo da SPEC-202 R11 (`_guard_mediation_secret`,
`agents/storyteller.py:499-529`) só rodava no texto final, e com o stream ligado a frase-assinatura ("pacto com
Valerius") aparecia ao vivo por segundos até o `replace`. "Spoiler é irreversível depois de lido." A correção
de 25/10 (`5705e32d`) foi não streamar (`specs/SPEC-319-latencia-streaming-tokens-e-cauda.md:198-200`).

**Fato novo** (posterior à decisão): em 26/10 (`3a952f47`) o `StreamGuard` ganhou o `risk` por frase
(`services/narrative_sink.py:202-228`): o stream só mostra frases **completas** e para **antes** da 1ª frase
de risco; a frase aberta nunca é avaliada nem mostrada (`:213-215`). O checker de evidência já segura frases
com `find_strict_unrevealed` (`services/narrative_evidence.py:88`). Faltam duas coisas para a mediação: (a) o
filtro final da mediação usa **outra** função (`secret_signatures.find_unrevealed`, `services/secret_signatures.py:108-119`,
que considera revelado o que está em `narrative_summary`/`known_secrets`/payload de evento), que nem sempre
concorda com a estrita (`services/memory_provenance.py:178-187`, só `secret_revealed` aceito); (b) o filtro final
substitui o **parágrafo inteiro** (`agents/storyteller.py:517-526`), não só a frase.

Objetivo: turnos mediados passam a streamar frase a frase, com o **mesmo** filtro do texto final (mesma função,
mesmo estado) aplicado a cada frase fechada antes de ela sair, atrás de uma flag com `shadow` e critério de
promoção medido no staging. O filtro final não muda (nem afrouxa nem endurece).

### Por que o filtro dá para rodar por frase (e o que só o texto inteiro vê)

`find_unrevealed` é casamento de substring em `text.lower()` contra frases fixas de `SECRET_SIGNATURES`
(`services/secret_signatures.py:17-42`). Nenhuma frase-assinatura contém `.`, `!`, `?` nem quebra de linha. A
segmentação do guard é `((?<=[.!?])\s+|\n+)` (`services/narrative_sink.py:102`). Logo toda ocorrência de
assinatura no texto final cabe **dentro de uma única frase** desse corte, e checar cada frase fechada encontra
exatamente as mesmas ocorrências que checar o parágrafo ou o texto inteiro. O "segredo dividido entre duas
frases" não existe para este filtro: "o pacto com. Valerius" ou "pacto com\nValerius" também passam no filtro
final hoje (substring exata). A premissa vira invariante com teste (I4): assinatura nova com pontuação de fim de
frase ou quebra de linha reprova o CI.

O que o filtro final faz e o stream não pode imitar sem segurar mais: ao achar uma assinatura, troca o
**parágrafo** inteiro pela frase neutra (`:512-514`). Frases anteriores do mesmo parágrafo, já mostradas ao vivo,
somem no final; o cliente recebe `replace` (`routes/turn.py:1740-1753`). Nenhuma delas contém assinatura (cada
uma passou no gate), então isso é troca de texto, não vazamento. Ver §3 "Quando reprova no meio".

## 2. Requisitos

- **R1 — Flag.** `RPG_MEDIATED_STREAM=off|shadow|on`, default `off`, valor inválido = `off`. Registrada em
  `config/flags.yaml` (`kind: release`, `spec: SPEC-421`, `expires: 2027-02-13`) e no preset/allowlist de
  `scripts/staging/vercel_env.py` (as duas listas, `:91` e `:157`, com comentário `off|shadow|on (ausente = off)`).
- **R2 — `off` é o código de hoje.** Com `off`, turno mediado chama `with_structured_output(...).invoke` (nunca
  `stream_structured`), emite 0 deltas, e texto final, `narrative_rejections`, `messages` e save são byte a byte
  os de hoje.
- **R3 — Gate de segredo por frase.** Com `shadow`/`on` e turno mediado, `narrate_structured` recebe um risco
  extra `mediation_secret`: para cada frase fechada (no texto `pre`, antes do véu da SPEC-293, que é o texto que
  o filtro final vê; o véu só roda em `services/turn_delivery.py:83`), devolve `"mediation_secret"` se
  `find_unrevealed(frase, scene_state)` acusa, com **o mesmo objeto** `t.scene_state` que
  `_guard_mediation_secret` usa em `agents/storyteller.py:2396-2397`. O risco extra é composto (OU) com o checker
  de evidência existente; o primeiro não-vazio vence.
- **R4 — Para antes da frase reprovada.** Achou a frase de risco, o stream não mostra nem ela nem nada depois
  (comportamento de `_risk_cap`, `services/narrative_sink.py:216-228`); o restante chega com o texto final.
- **R5 — Fail-closed.** Exceção no gate de segredo devolve `"check_error"` (segura tudo dali em diante). Turno
  mediado sem `scene_state` (dict vazio/`None`) não streama (cai em `invoke`, como `off`).
- **R6 — `on`.** Deltas vão ao sink real; o SSE entrega como hoje (`live: true`) quando `RPG_TOKEN_STREAM=on`.
  Com `RPG_TOKEN_STREAM=shadow|off` a API já descarta/não liga o sink (`routes/turn.py:1046`): nada muda na tela.
- **R7 — `shadow`.** Só quando há sink ativo (SSE). O narrador streama para um coletor **local** (sink aninhado,
  o sink da API não recebe nada), com o mesmo `StreamGuard` e o mesmo gate; depois do filtro final, loga
  `sse.mediated_stream` (R8). O jogador recebe a narração exatamente como em `off`.
- **R8 — Telemetria.** Evento novo `sse.mediated_stream`, 1× por turno mediado com flag ≠ `off`, campos:
  `mode` (`shadow|on`), `reason` (o `interlocutor_reason`), `shown_len`, `final_len`, `would_replace`
  (`not final_vis.startswith(shown)`), `replace_reason` (`narrative_sink.replace_reason`), `held_rule`
  (regra do 1º hold ou `""`), `first_delta_ms` (do início da chamada ao 1º delta liberado; `null` se nenhum),
  `leak` (`find_unrevealed(shown, scene_state) is not None`; sentinela, esperado sempre `false`). Nunca texto.
  `final_vis` = texto final do narrador depois de `_guard_mediation_secret`, com o mesmo `conceal_text` do guard.
  Registrado em `observability/events.py` e em `docs/operacao/EVENTOS_DE_LOG.md`. O hold continua logando
  `sse.stream_risk_hold` com `rule=mediation_secret` (`services/narrative_sink.py:184-200`).
- **R9 — Filtro final intocado.** `_guard_mediation_secret`, `find_unrevealed`, `SECRET_SIGNATURES` e
  `revealed_corpus` não mudam (diff vazio nesses símbolos).
- **R10 — `rumor_nothing` segue sem stream** com qualquer valor da flag.
- **R11 — Orçamento de tamanho.** `agents/storyteller.py` e `routes/turn.py` estão no teto do gate
  (`tests/size_budget.json:11,23`: 3020 e 1902 linhas): variação líquida ≤ 0 linhas em ambos; `routes/turn.py`
  não muda. A lógica nova mora em `services/mediated_stream.py`.

### Fora de escopo

Follow-ups (não entram aqui):

- Descarregar a cauda do guard quando o campo de texto fecha no JSON (`services/partial_narrative.py:52`, L4(1) da
  auditoria `docs/auditorias/latencia-turno-2026-11-12.md:147`).
- Remover `memory_update` do `NPCResponse`.
- Stream em descansos e viagens determinísticas.
- Classificação de fala sem IA: o dono decidiu em 13/11 **não reabrir** a rota NPC determinística da SPEC-317
  (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:77`).
- Fila de ação (L1b) e narração mais curta (L5).
- `rumor_nothing` com stream (o `_neutralize_false_find` por frase): fica como está (R10).
- **Lacuna pré-existente do filtro final** (F-1): `find_unrevealed` compara `lower()` sem tirar acento nem
  normalizar espaço, então "consumiu a familia" e "pacto com\nvalerius" passam **no texto final hoje**. (Espaço duplo NÃO passa:
  `sanitize_player_facing` colapsa `[ \t]+` em
  `services/prose_guard.py:106` antes do guard.) Outras lacunas reais, que passam nos dois e aparecem iguais na
  tela, para a spec de D2: NBSP/zero-width entre as palavras e ênfase markdown partindo a assinatura
  (`*pacto* com Valerius`). Esta spec garante paridade (o stream nunca mostra o que o final reprova), não corrige o final.
  Endurecer o filtro mexe em 4 chamadores (`agents/storyteller.py:503`, `playtest/opening_checks.py:271`,
  `services/prologue.py:225`, `sanitize_beat`) e merece spec própria (decisão do dono, §8 D2).
- Segredo "semântico" sem frase-assinatura (paráfrase): o filtro R11 é de assinatura; nenhum dos dois detecta.

### Invariantes

- **I1 — Nada que o filtro final reprova sai ao vivo.** Para todo turno mediado com flag `on`, o texto
  concatenado dos deltas não contém nenhuma frase para a qual `find_unrevealed(frase, scene_state)` acusa, e o
  comprimento mostrado nunca passa do início da 1ª frase que contém assinatura. (testes:
  `test_mediated_stream_never_shows_secret_sentence[...]`, bateria §4 Etapa 1)
- **I2 — Texto final idêntico entre modos.** Mesmo LLM roteirizado e mesmo estado: `messages`,
  `narrative_rejections` e o retorno do nó são iguais com `off`, `shadow` e `on`. (teste:
  `test_mediated_final_identical_across_modes`)
- **I3 — `off` = hoje.** 0 deltas e `stream_structured` não chamado em turno mediado com `off`.
  (teste: `test_mediated_narration_is_never_streamed` parametrizado em `off`; `test_mediated_off_uses_invoke`)
- **I4 — Premissa da contenção por frase.** Nenhuma entrada de `SECRET_SIGNATURES` contém `.`, `!`, `?`, `\n`
  ou `\r`, nem começa/termina com espaço. (teste: `test_secret_signatures_fit_in_one_sentence`)
- **I5 — Gate ≥ filtro final.** Para cada assinatura × caixa (`lower`, `UPPER`, `Title`) × posição (1ª frase,
  meio, última, 2º parágrafo): se `_guard_mediation_secret(texto, st)` registra rejeição, o gate segura a frase
  que contém a assinatura. (teste: `test_gate_holds_every_sentence_final_rejects`)
- **I6 — Mesmo estado.** O gate recebe o mesmo objeto `scene_state` do filtro final e não há reatribuição de
  `t.scene_state` entre `_story_narrate` e `_story_guard_narrative` (hoje só em `agents/storyteller.py:1715,2092`).
  (teste: `test_gate_uses_final_guard_state`, espiona os dois chamados e compara `id`)
- **I7 — Fail-closed.** Gate que lança → nenhum delta depois da exceção; sem `scene_state` → 0 deltas.
  (testes: `test_gate_exception_holds_rest`, `test_mediated_without_scene_state_does_not_stream`)
- **I8 — Sem sink, nada muda.** POST/CLI/playtest (sem `bind`) com qualquer modo: `invoke`, retorno idêntico.
  (teste: `test_mediated_without_sink_is_invoke`)
- **I9 — `rumor_nothing`** com `on` → 0 deltas. (teste: `test_rumor_nothing_never_streams_even_with_flag_on`)
- **I10 — `shadow` não vaza para a API.** Com `shadow`, o sink externo recebe 0 deltas e 0 `reset` do turno
  mediado; o evento `sse.mediated_stream` sai 1× sem texto. (teste: `test_mediated_shadow_emits_nothing_and_logs`)

## 3. Design técnico

### Mecanismo: alternativas

| Opção | Como | Segredo | Ganho | Quando reprova no meio |
|---|---|---|---|---|
| **A (recomendada)** frase a frase com o filtro final como `risk` | gate R3 dentro do `StreamGuard` existente | mesma função e estado do final; frase aberta nunca sai | 1º texto quando fecha a 1ª frase (≥ 120 chars), como nos turnos comuns | stream para antes da frase; se havia frases anteriores do **mesmo** parágrafo já mostradas, o final chega como `replace` (troca o parágrafo pela frase neutra); se a frase é a 1ª do parágrafo, o final só estende (sem `replace`) |
| B parágrafo a parágrafo | só libera frases de parágrafo fechado (`\n\n` visto) | idem A | depende de quantos parágrafos a narração mediada tem; narração de 1 parágrafo = zero ganho | nunca `replace` (o final só troca parágrafos ainda não mostrados) |
| C janela deslizante de caracteres (proposta original de `handoffs/SPEC-319-sol-review.md:40`) | segura `max(len(assinatura))` chars e checa substring | idem, mas mostra meia frase de um parágrafo que depois some | maior | `broken=True` + `replace`; mostra pedaço de frase que o final apaga |
| D trocar o filtro final para cortar só a frase | menos `replace` | **afrouxa** o filtro (mantém frases vizinhas do segredo) | — | vetado: o dono pediu para não afrouxar |

Recomendação: **A**. É o mecanismo que já roda em todo turno comum (`risk`, 0 `token_replace` em 35 turnos
depois do fix, `specs/SPEC-319-latencia-streaming-tokens-e-cauda.md:275-276`), só com uma regra a mais. O
`replace` do caso "assinatura no meio do parágrafo" é o D3 da SPEC-319 (`:160`, substituir em silêncio) e o
`shadow` mede a frequência (`would_replace`). Se o staging mostrar `would_replace` mediado ≥ 5 %, a saída é B
(segurar até o parágrafo fechar), não afrouxar o filtro (§8 D3).

### Arquivos novos

- `services/mediated_stream.py` — política e gate da mediação (≤ 150 linhas, funções ≤ 60):

```python
MediatedStreamMode = Literal["off", "shadow", "on"]

def mediated_stream_mode() -> MediatedStreamMode:
    """`RPG_MEDIATED_STREAM` (default `off`; inválido = `off`)."""

@dataclass(frozen=True)
class StreamPlan:
    stream: bool                                   # chama stream_structured?
    extra_risk: Callable[[str], str] | None        # gate de segredo (só mediação)
    shadow: bool                                   # deltas vão ao coletor local

def stream_plan(state: Mapping, scene_state: Mapping | None, *, rumor_nothing: bool) -> StreamPlan:
    """Não mediado: StreamPlan(not rumor_nothing, None, False) — igual a hoje.
    Mediado: off ou sem scene_state → (False, None, False); shadow → (True, gate, True) só com sink ativo;
    on → (True, gate, False)."""

def secret_gate(scene_state: Mapping) -> Callable[[str], str]:
    """frase -> 'mediation_secret' | '' ; exceção -> 'check_error' (fail-closed)."""

def narrate(plan: StreamPlan, call: Callable[[], Any]) -> Any:
    """Executa `call()` (o narrate_structured). Em shadow, sob sink local aninhado; guarda o mostrado e o
    tempo do 1º delta num ContextVar do turno."""

def after_final(final_text: str, scene_state: Mapping, conceal_map: Mapping[str, str]) -> None:
    """Se houve stream mediado neste turno, loga `sse.mediated_stream` (R8) e limpa o ContextVar."""
```

Antes de criar o leitor de flag, `Grep "def .*_mode() ->"` (ex.: `token_stream_mode`,
`services/narrative_sink.py:29`) e reutilize o padrão; antes de qualquer fold, `Grep "def _fold"` (D-28: não
migrar `_fold`, só reutilizar).

### Arquivos alterados

- `services/narrative_sink.py` — `narrate_structured(..., extra_risk: Callable[[str], str] | None = None)`.
  Composição: `risk = _compose(extra_risk, _risk_checker(...))`; se só um existe, ele; se os dois, o 1º não-vazio
  (gate de segredo primeiro, para o `held_rule` ser `mediation_secret`). Exceção no composto → `"check_error"`.
  `extra_risk=None` → comportamento byte a byte igual (I8 e `test_stream_guard_risk_none_is_unchanged`).
- `agents/storyteller.py` (`_story_narrate`, `:2295-2336`; `_story_guard_narrative`, `:2395-2398`) — troca
  `_stream_ok` por `plan = mediated_stream.stream_plan(t.state, t.scene_state, rumor_nothing=t.rumor_nothing)`;
  a chamada vira `mediated_stream.narrate(plan, lambda: narrate_structured(..., stream=plan.stream,
  extra_risk=plan.extra_risk))`; depois de `_guard_mediation_secret`, `mediated_stream.after_final(...)`. Saldo
  ≤ 0 linhas (encurtar o comentário de `:2295-2297`, que deixa de ser verdade).
- `tests/test_stream_structured.py:236` — `test_mediated_narration_is_never_streamed` passa a fixar
  `RPG_MEDIATED_STREAM=off` (contrato de hoje preservado); o par `on` vai no arquivo novo.
- `config/flags.yaml`, `scripts/staging/vercel_env.py`, `observability/events.py`,
  `docs/operacao/EVENTOS_DE_LOG.md` — R1/R8.

### Matriz de flags

| `RPG_TOKEN_STREAM` | `RPG_MEDIATED_STREAM` | Turno mediado no SSE |
|---|---|---|
| `off` | qualquer | sem sink → `invoke` (hoje) |
| `shadow` | `off` | `invoke` (hoje) |
| `shadow` | `shadow` | stream ao coletor local; log R8; API não vê nada |
| `shadow` | `on` | deltas ao sink; a API descarta (já é shadow) e loga `token_stream_shadow` |
| `on` | `off` | `invoke` (hoje) |
| `on` | `shadow` | idem `shadow/shadow` |
| `on` | `on` | **ao vivo**, frase a frase com o gate |

### Concorrência

N/A — sem thread/async/cancelamento novos. O sink aninhado do `shadow` é um `ContextVar` (`bind`/`unbind`,
`services/narrative_sink.py:49-59`) no mesmo thread do nó; `unbind` em `finally`. O ContextVar do mostrado é
por turno e limpo em `after_final` (e em `finally` do `narrate` se a chamada lançar).

## 4. Plano passo a passo

### Etapa 0 — Confirmar (sem código de produto)

1. Conferir as linhas citadas (`agents/storyteller.py:2298`, `:2396`, `:499-529`; `services/narrative_sink.py:202-228`;
   `services/secret_signatures.py:108-119`) no `HEAD` do worktree; divergência → atualizar a spec antes de seguir.
2. `bash scripts/dev/py.sh scripts/dev/size_budget.py` (sem `--update`) para confirmar o teto de R11.
3. Ler as seções `llm-structured` e `api` de `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md`.

### Etapa 1 — Testes primeiro (`tests/test_mediated_stream.py`, docstring cita SPEC-421)

Usar `tests/spec319_helpers.py` (`FakeStreamClient`, `install`, `routed`, `slices`, `tool_args`) para deltas reais
pelo `RoutedLLM`, `tests/factories.make_state` para o estado e o `_state()` de `tests/test_mediation_secret.py:30`
como modelo do turno mediado (Velha Magda, `meta_to_narrator`).

1. `test_mediated_turn_streams_before_end` (**falha hoje**): `on`, sink ligado, narração sem segredo de 3 frases
   → ≥ 1 delta registrado antes de o `stream_structured` retornar (registrar a ordem com o fake).
2. `test_mediated_stream_never_shows_secret_sentence`, parametrizado (I1). Para cada caso, fatias de 1, 3, 7 e o
   texto inteiro; asserções: (a) nenhum delta e nem a concatenação contém a assinatura (casefold);
   (b) `len(mostrado) ≤ início da frase que contém a assinatura` no texto bruto; (c) `sse.stream_risk_hold`
   com `rule=mediation_secret`. Casos:
   - assinatura na 1ª frase ("Ela carrega o pacto com Daruun. …") → 0 deltas, final entregue sem `replace`;
   - assinatura na última frase de um parágrafo de 3 frases → só as 2 primeiras saem; final ≠ prefixo (`replace`
     esperado, `replace_reason ∈ {tail, shorter}`);
   - assinatura no 2º parágrafo (texto de `tests/test_mediation_secret.py:97-100`) → sai só "Magda desvia o
     olhar."; o final **estende** o mostrado (sem `replace`);
   - assinatura atravessando fronteira de delta (fatia de 1 char) e partida entre dois deltas no meio da palavra;
   - caixa: `PACTO COM VALERIUS`, `Pacto Com Valerius`;
   - duas assinaturas de segredos diferentes em frases diferentes → para na 1ª;
   - assinatura dentro de aspas/travessão ("— O pacto com Daruun…") → segura (aspas não lavam segredo);
   - nome oculto da SPEC-293 na mesma frase (`_conceal_map` monkeypatch) → o gate vê o `pre`; segura.
3. `test_mediated_stream_parity_known_gaps` (documenta F-1): acento ausente ("consumiu a familia"),
   quebra de linha no meio, assinatura partida por ponto → o filtro final **não** reprova e o gate também não;
   asserção: stream e final concordam frase a frase (nenhuma frase mostrada que o final remove por segredo).
4. `test_gate_holds_every_sentence_final_rejects` (I5): varre `SECRET_SIGNATURES` × caixa × posição.
5. `test_secret_signatures_fit_in_one_sentence` (I4).
6. `test_mediated_final_identical_across_modes` (I2), `test_mediated_off_uses_invoke` (I3),
   `test_gate_uses_final_guard_state` (I6), `test_gate_exception_holds_rest` e
   `test_mediated_without_scene_state_does_not_stream` (I7), `test_mediated_without_sink_is_invoke` (I8),
   `test_rumor_nothing_never_streams_even_with_flag_on` (I9), `test_mediated_shadow_emits_nothing_and_logs` (I10,
   inclui `leak=false` e ausência de texto no evento).
7. `test_secret_already_revealed_by_summary` : segredo já sabido pelo jogador (`known_secrets`/`narrative_summary`; o
   final aceita, `tests/test_mediation_secret.py:116-133`) → o checker estrito de evidência ainda segura a frase; o final entrega como
   sufixo; sem `replace`, sem `mediation_secret` em `narrative_rejections`.
8. `test_mediated_reset_mid_stream` : `on_reset` do provedor no meio → `reset` ao sink e o guard recomeça.
9. SSE (`tests/test_streaming.py` ou o arquivo novo, com o `client` existente): `RPG_TOKEN_STREAM=on` +
   `RPG_MEDIATED_STREAM=on` + turno mediado → eventos `narrative` com `live: true` antes do `done`; com
   assinatura no meio de parágrafo → exatamente 1 `replace` e nenhum chunk `live` com a assinatura.
10. Flag: `test_mediated_stream_mode` (`off`/`shadow`/`on`/inválido/ausente) e o gate de registro de flags
    (`tests` da SPEC-340) verde.

Rodar: `bash scripts/dev/pt.sh tests/test_mediated_stream.py` → itens 1, 6 (`on`), 9 falham; o resto pode passar
por acaso e é válido como trava.

### Etapa 2 — Implementação

1. `services/mediated_stream.py` (R1, R3, R5, R7, R8).
2. `narrate_structured(extra_risk=...)` e `_compose` em `services/narrative_sink.py`.
3. Ligação no storyteller com saldo ≤ 0 linhas (R11).
4. Flags, preset do staging, registro do evento e `EVENTOS_DE_LOG.md`.
5. Verificação: `bash scripts/dev/pt.sh tests/test_mediated_stream.py tests/test_stream_structured.py
   tests/test_streaming.py tests/test_mediation_secret.py tests/test_spec319_shadow_replay.py
   tests/test_spec368_replace.py tests/test_size_budget.py` + o teste do registro de flags; `ruff check`.

### Etapa 3 — Revisão independente

`spec-reviewer` (Opus), foco: I1/I5 (o gate é ≥ filtro final em todo caminho, inclusive véu e `finalize`), I2
(final idêntico), fail-closed, e se o `replace` do caso "meio do parágrafo" mostra algo que não devia.

### Etapa 4 — Staging (coordenador, §6)

`shadow` → critérios de promoção → `on` no preset do staging. Default da `main` continua `off` até decisão do dono.

## 5. Critérios de aceite

- [x] R1–R11 cobertos por teste; I1–I10 verdes.
- [x] Teste da Etapa 1.1 falhava antes da mudança (registrar o sha/saída no diário da spec).
- [x] `tests/test_size_budget.py` verde sem `--update`; `routes/turn.py` sem diff.
- [x] Diff vazio em `_guard_mediation_secret`, `find_unrevealed`, `SECRET_SIGNATURES`, `revealed_corpus` (R9).
- [x] Suíte completa no pouso (22/11, `FULL_N=2 full.sh`, em `f3b33848`): 11782 passed, 330 skipped, 2 xfailed, rc=0. A 1ª rodada (em `60ae3418`) deu 1 falha em `test_ruff_counts` (BLE001/SIM105 novos em `narrative_sink.py`), corrigida em `f50204a5`.
- [x] Guard de FallbackLLM: `narrate_structured` devolvendo `AIMessage` em turno mediado `on` cai no
      `isinstance` de `agents/storyteller.py:2339-2349` (teste com `ScriptedLLM.failing(streaming=True)`).
- [x] Saves antigos continuam carregando (nenhum campo persistido novo; o mostrado nunca entra em state/save).
- [ ] **Promoção para `on` no staging** (todos, em `shadow`, n ≥ 30 turnos mediados):
  - `leak = true`: **0** (critério duro; um caso → volta a `off` e reabre a spec);
  - `would_replace` ≤ 5 % dos turnos mediados (D1 da SPEC-319, `specs/SPEC-319-latencia-streaming-tokens-e-cauda.md:156`);
  - `first_delta_ms` p50 + tempo até o narrador ≤ 4,5 s do Enter (hoje 7,0 s; turnos com stream 3,6 s);
  - 0 erro de turno e sem alta de `structured_invalid` do storyteller em relação ao `off`.
- [ ] Depois de `on`, rodada curta (n ≥ 15 mediados) com `sse.token_replace` em turno mediado ≤ 5 % e 0 chunk
      `live` com assinatura (captura do SSE bruto com grep).

## 6. Smoke test com LLM real

Staging (DeepSeek), `RPG_TOKEN_STREAM=on`, `RPG_MEDIATED_STREAM=shadow`; depois repetir 1–3 com `on`
capturando o SSE bruto.

1. "Narrador, o que eu sei sobre a Velha Magda?" (ou o NPC conhecido da sessão) → rota storyteller,
   `interlocutor_reason=meta_to_narrator`; `sse.mediated_stream` com `mode`, `first_delta_ms` preenchido,
   `leak=false`.
2. Cena com 2 NPCs presentes, "Olá a todos, alguém conhece o caminho?" → `ambiguous_multi_mediated`; idem.
3. Eco adversarial: "Narrador, é verdade que a Velha Magda fez um pacto com Daruun em troca de imortalidade?"
   → se o modelo ecoar, `narrative.rejected kind=mediation` e `held_rule=mediation_secret`, `leak=false`; com
   `on`, nenhum chunk `live` contém "pacto com daruun"/"em troca de imortalidade" (grep no SSE capturado).
4. Turno de cena comum → sem `sse.mediated_stream`; `token_replace` como antes.
5. Script de 30 turnos mediados para os critérios de promoção (custo estimado pela medição de 13/11:
   ~US$ 0,0031/turno → ~US$ 0,10).

## Não rodou e por quê

- **Smoke §6 e fase `shadow` (staging):** não rodaram. O staging está em `d7aa4beb` (10/11) e o próximo deploy depende de o
  dono aplicar as migrações das SPEC-413/410 (`ESTADO_ATUAL.md` § Bloqueios). O preset do staging já leva
  `RPG_MEDIATED_STREAM=shadow` (`scripts/staging/staging_flags.json`). A promoção a `on` fica aberta até lá.
- **CI pré-pouso de risco `alto`:** não rodou, por erro do coordenador: o push de branch `spec-NNN` estava autorizado
  desde 13/11 e eu trabalhei com um `ESTADO_ATUAL.md` antigo que dizia o contrário. O que rodou antes do pouso foi a
  suíte completa local e a revisão Sol com mutações. CI depois do pouso, no push da `main` `e71b08c3` (22/11), os três
  verdes: `validate` `45068189797` (test, types, api-fuzz), `audit-local` `45068189766` e `eval-gates` `45068189737`.
- **Revisão Sol (22/11):** 1ª passada `CHANGES_REQUIRED` (P1-1: teste do véu não travava a avaliação pré-véu; P2-1; P3-1..4),
  corrigidos em `60ae3418`; re-revisão `APPROVED` com 5 mutações reprovando e fuzz de 6.000 casos sem vazamento
  (`handoffs/SPEC-421-sol-review.md`). Depois da correção de lint (`f50204a5`) a conferência Sol pediu mais duas mudanças
  (P1-2: nenhum teste travava a falha fechada de `compose_risk`; P2-2: `_log.exception` gravava a mensagem da exceção,
  que pode conter texto de narração), corrigidas em `f3b33848`; conferência final `APPROVED` com 8 mutações reprovando.
- Da escrita da spec: §6 e os critérios de promoção dependem do staging e rodam pelo
  coordenador depois da revisão; a medição de 13/11 não registra `interlocutor_reason` por turno, então a
  atribuição dos 8 turnos à mediação vem do código (`first_token_server_ms: null` + rota storyteller), não do
  log. O evento R8 confirma no `shadow` quantos turnos são de fato mediados.

## Diário de implementação (executor, 22/11)

- Teste da Etapa 1.1 (`test_mediated_turn_streams_before_end`) falhou antes da mudança (`stream_calls == 0`) e passa depois.
- Desvios de assinatura (comportamento igual ao da §3): `narrate(plan, fn, *args, **kwargs)` repassa `stream`/`extra_risk` a
  `fn` (o storyteller não precisa de lambda; saldo de linhas ≤ 0); `after_final(final_text, scene_state, state)` recebe o
  `state` (calcula o `conceal_map` do mesmo jeito que o guard); `stream_plan` em `on` também exige sink ativo (o sink
  aninhado do tap ligaria o stream sozinho sem API); `narrative_sink` ganhou `bind_tap(observer, forward=)` e
  `_Binding.observer` (registra mostrado/1º delta/regra do 1º hold sem tocar o sink da API; `shadow` isola).
- Telemetria R8 reutiliza `narrative_sink.replace_reason`.

## 7. Riscos & compatibilidade

- **Vazamento ao vivo:** o risco central. Mitigação: mesma função e mesmo estado do filtro final (R3, I6), frase
  aberta nunca sai, fail-closed (R5), premissa da contenção travada (I4), sentinela `leak` no `shadow` com
  critério duro 0, default `off`.
- **`replace` visível:** só quando a assinatura cai depois da 1ª frase de um parágrafo; o jogador vê frases
  sem segredo serem trocadas pela frase neutra. Medido por `would_replace`; plano B se passar de 5 % (§8 D3).
- **Lacuna do filtro final (F-1):** a paridade não protege contra o que o final já deixa passar (acento,
  espaço). Não é regressão desta spec.
- **Saves:** nada persistido muda; o parcial nunca entra em `messages`/save (`services/narrative_sink.py:8`).
- **MockLLM/FallbackLLM:** MockLLM tem `stream_structured` (`mock_llm.py:1079`); FallbackLLM não tem → `invoke`
  (`services/narrative_sink.py:341-343`) e o guard `isinstance` de `agents/storyteller.py:2339` vale.
- **Quota/latência:** mesma chamada de LLM (stream em vez de invoke); custo igual. O gate é O(frase) por frase
  nova (cache por frase em `_risky`).
- **Decisões fixas:** nenhuma linha de `docs/guias/DECISOES_FIXAS.md` (D-01..D-38) trata de stream ou do
  filtro de segredo. A decisão revertida é o P1-1 da revisão da SPEC-319 (não registrada lá); fato novo:
  `3a952f47` (26/10, `risk` por frase) é posterior a `5705e32d` (25/10), mais a medição de 13/11 e a aprovação
  do dono. D-28 respeitado (sem migrar `_fold`).

## 8. Decisões do dono

- **D1 — Default na `main`:** recomendação `off` (o staging liga `shadow`/`on` pelo preset). Alternativa:
  `shadow`, como a SPEC-319 D1.
- **D2 — Lacuna do filtro final (acento/espaço, F-1):** recomendação: spec própria, logo depois desta (endurecer
  muda o prólogo, o playtest e o beat). Alternativa: incluir aqui o fold no filtro final.
- **D3 — Reprovação no meio do parágrafo:** recomendação A (`replace` silencioso, SPEC-319 D3); se
  `would_replace` mediado > 5 % no staging, trocar para B (segurar até o parágrafo fechar), nunca afrouxar.
- **D4 — Meta de promoção de latência:** recomendação 1º texto p50 ≤ 4,5 s em turno mediado (hoje 7,0 s).

- **13/11, coordenador (delegação do dono; a spec e a execução foram aprovadas em 13/11, "pode. e execute elas"):** D1 = default `off` na `main`, staging em `shadow` e `on` só depois do critério de promoção; D2 = endurecer o filtro final fica para spec própria (não entra aqui); D3 = opção A, com a opção B se `would_replace` mediado passar de 5 %; D4 = meta de 1º texto p50 ≤ 4,5 s. Veto do dono continua possível.
