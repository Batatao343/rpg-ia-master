# SPEC-319 — revisão sol (independent-review) · follow-up `tail`

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-26 · **Commit revisado:** `3a952f47`
>
> Nome: o pedido foi `SPEC-319-sol-review-tail.md`, mas esse nome reprova o lint
> `scripts/check_handoff_names.py` (`tests/test_handoff_names.py`), e `SPEC-319-sol-review.md`
> já existe (revisão de 25/10). Usei o tipo válido `independent-review`.

## Escopo

`git diff main...spec-319-tail` (base `55a81bf`, 1 commit, 5 arquivos, +221/−6):
`services/narrative_sink.py` (`StreamGuard(risk=…)`, `_risk_cap`, `_risk_checker`, `narrate_structured`/
`narrate_text`), `services/narrative_evidence.py` (`stream_risk_checker`, `_ACQUIRE`), `agents/storyteller.py`
(`evidence_state` e `hold_acquisition`), o diário da spec §Histórico e `tests/test_spec319_shadow_replay.py`.
Cruzei com os guards finais que não mudaram: `turn_outcome.render_player_message`
(`_NEGATIVE_REWARD`/`_NEGATIVE_ITEM`), `prose_guard.remove_rejected_claims` e `narrative_evidence._reason`/
`validate_narrative`. Fora do escopo: o cliente web e a medição no staging.

O que confere:
- **Os guards não foram afrouxados.** Nenhum guard final mudou: o diff só acrescenta `stream_risk_checker`, e o
  `risk` só limita até onde vão as emissões ao vivo (`_advance` → `min(safe, cap)`). O retorno de `narrate_*` e o
  texto final saem do mesmo caminho de antes, então ficam byte a byte iguais. Sem `risk` (sem sink, `off`, ou sem estado),
  `_risk_cap` devolve `len(shown)`: é o comportamento antigo (`test_stream_guard_risk_none_is_unchanged`).
- **Segredo/hidden:** o risco é avaliado no texto **antes do véu** (`pre`), como no guard final;
  `find_strict_unrevealed` agora também segura o stream (antes nada ia ao vivo só nos turnos de mediação). Como os
  segredos revelados só aumentam durante o turno, a evidência pré-nó é **mais** estrita que a final: um segredo
  revelado neste turno fica segurado, nunca vaza. Não há segredo em log: `log_fallback` grava só `error_type`.
- **Prefixo:** a segmentação `_SENTENCE_SPLIT` é a mesma de `validate_narrative`; o mapeamento de índice de `pre`
  para `shown` corta antes do separador (`post_parts[:stop-1]`); `stop == 0` dá 0. Frase em aberto nunca é avaliada
  nem mostrada (curto-circuito em `narrative_sink.py:190`), então o cache por frase não fica velho.
- **`hold_acquisition`/estado do storyteller:** `evidence_state` é uma cópia rasa (`build_evidence` faz deepcopy,
  sem mutação). `rested_player`/`discovery_player`/`world` já estão definidos no ponto da chamada
  (`storyteller.py:1186/1252`). Só é avaliado com sink ativo e `_stream_ok`.
- **Custo por delta:** `_risk_cap` faz um `split` O(n) por delta, a mesma ordem do `_cleaned()` que já existia
  (sanitize + finalize sobre o texto bruto inteiro). O `risk` roda 1× por frase completa distinta (cache), então
  o checker não gera O(n²). Nenhum arquivo de `evals/` foi tocado e não há writer persistente novo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/narrative_sink.py:190` | Mudança de granularidade não documentada. Com `risk` presente, que é o caso de **todo** narrador com estado (story, NPC, combate, loot), a frase em aberto é sempre segurada: o stream passa a sair **frase a frase**, não palavra a palavra. Isso afeta o §6.4 ("texto aparece palavra a palavra") e o critério **TTFMC p50 ≤ 3 s**: o 1º delta agora espera a 1ª frase inteira mais o espaço seguinte, depois de `HOLD_CHARS`. Além disso, uma frase de risco cedo (ex.: `_ACQUIRE` casando "Você encontra…" logo na 1ª ou 2ª frase) segura o turno inteiro até o fim. O diário cita só "o stream para antes dessas frases". | Registrar na spec (§3/§7 e diário) que a granularidade virou frase completa. Remedir §6.2 (`ttfmc` p50/p95 com `on`) antes de marcar o critério; se a meta de 3 s cair, considerar um checker de prefixo monotônico para a frase em aberto. |
| P2-1 | P2 | `services/narrative_evidence.py:160`, `services/narrative_sink.py:268,277` | Falha aberta, ao contrário da docstring ("Exceção => frase de risco"). Se `build_evidence` ou o import falhar, `risk=None` e o stream volta a mostrar tudo, sem o guard de segredo ao vivo. Não é regressão (antes era assim), mas é o caminho de menor segurança justamente quando o estado está estranho. | No erro, devolver `lambda _s: True` (segura tudo, o final entrega) em vez de `None`. Manter `None` só para "sem estado". |
| P2-2 | P2 | `services/narrative_sink.py:310` | `build_evidence` faz `deepcopy` de `event_log`/`world_projection`/`npcs` + `capture_baseline` de forma **síncrona antes do 1º token** (dentro de `narrate_structured`, antes do `streamer`). Em save longo isso entra direto no TTFMC. | Construir o checker de forma preguiçosa, na 1ª frase completa (ex.: `risk` como thunk memoizado), ou medir o custo em save de 200 turnos. |
| P2-3 | P2 | `services/narrative_evidence.py:144` | Resíduos da classe `unknown_item` que o checker não cobre. `remove_rejected_claims` corta **qualquer** frase que contenha o nome do item rejeitado ("O Amuleto de Zorn brilha na prateleira." sem verbo de aquisição) e, com termo de ouro/moeda, o **parágrafo inteiro** que menciona ouro/moedas, inclusive frases anteriores já mostradas. As duas continuam gerando `replace` (permitido por D3). Ao contrário, `_ACQUIRE` é amplo (`encontra/acha/descobre`) e também segura frases sem item (custo, ver P1-1). | Documentar os dois resíduos no diário (junto de `proposed_events`/`species_drift`). Opcional: com `items_gained` antes de `narrative` impossível (R10), aceitar o resíduo. |
| P2-4 | P2 | `services/narrative_sink.py:179` | Sem telemetria do custo do hold. Não dá para saber em quantos turnos o risco cortou o stream cedo, nem qual regra (`_reason`/recibo/aquisição) disparou. | Logar `sse.stream_risk_hold` (índice da frase, `chars_shown`, código da regra, sem o texto) uma vez por narração. |
| P2-5 | P2 | `services/narrative_sink.py:200-203` | Fragilidade teórica. Se o véu (`conceal_text`) introduzir ou remover `[.!?]\s`/`\n` num rótulo, as contagens de partes de `pre` e `shown` divergem e o corte cai na frase errada. O `min(stop, len(post_parts)-1)` limita o índice, mas não garante o alinhamento. | Teste com mapeamento cujo rótulo contenha ". " (ou uma asserção de contagem igual, que caia em `cap=0` se divergir). |

As decisões do dono foram respeitadas. **D1**: o critério de `would_replace` < 5 % segue como regra do `on`, e
o fix ataca a principal causa remanescente (`tail` ~9 %). **D3**: os resíduos continuam como `replace`
silencioso, não como bloqueio.

## Correções aplicadas

Nenhuma ainda: revisão do commit `3a952f47`.

## Pendências

- P1-1: executor atualiza a spec 319 (§3/§7 e diário) e o coordenador remede §6.2 no staging (`on`) antes de
  fechar o critério TTFMC. Spec de destino: SPEC-319.
- P2-1 a P2-5: follow-ups em SPEC-319 (podem ir num commit só). Nenhum bloqueia o pouso.

## Comandos rodados

```text
git diff main...HEAD --stat → 5 arquivos, +221/−6
py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec319_shadow_replay.py tests/test_narrative_evidence.py tests/test_stream_structured.py tests/test_streaming.py → 96 passed
py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_llm_hedge.py tests/test_spec192_vercel_env.py → passed (sem falhas)
```
