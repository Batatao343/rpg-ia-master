# SPEC-409 — revisão terra (review)

> **Veredito:** APPROVED_WITH_FOLLOWUPS
> **Revisor:** spec-reviewer · **Data:** 2026-11-11 · **Commit revisado:** `70fecadb`

## Escopo

Pouso A (Etapas 0–1): `git diff main...HEAD` (16 arquivos, só testes/fakes/docs). Etapas 2–6 fora.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | tests/test_image_pricing.py, test_shard_pricing.py, test_shard_pricing_local.py, test_bug_finops_wallet_jobs_local.py, test_image_quotes_local.py, test_rls_effective.py, test_spec236_races_local.py, test_speech_finance_local.py, test_wallet_local.py (imports no topo) | Imports não usados após trocar a data literal (`UTC`, `datetime`, `timezone`; `UUID` em 237). `ruff --isolated --select F401` acusa 24 ocorrências em 11 arquivos; `timezone` já era morto antes em parte. O ruff do projeto passa (F401 fora do select). | `ruff check --isolated --select F401 --fix` nesses arquivos (só tests), ou aceitar como dívida. |
| P2-2 | P2 | tests/fakes/local_pricing.py:pin_card_clock | Não limpa `RPG_FINOPS_BLOCK_STALE`; com `=0` no shell o gate vira no-op e o teste passa sem exercer a janela. Não afeta o cenário atual. | `monkeypatch.delenv("RPG_FINOPS_BLOCK_STALE", raising=False)` junto das outras. |
| P3-1 | P3 | tests/test_local_pricing_fixture.py | `test_pinned_card_clock_does_not_disable_the_window` chama `require_paid_effect` direto com `now=` (não passa pelo pin); prova a janela real, mas não que o pin não a desliga. | Opcional: chamar após `pin_card_clock` via `finops_alerts.require_paid_effect` com o `now` explícito (partial deixa o kwarg do chamador prevalecer). |

## Respostas às perguntas

1. Pin = `functools.partial(require_paid_effect, now=card_epoch())` setado em `services.finops_alerts`. Os 3 chamadores (`portrait_offer.py:44`, `routes/art.py:70`, `scripts/staging/art_preflight.py:112`) importam dentro da função, então resolvem o atributo na hora da chamada: pegam o patch, sem referência antiga. monkeypatch desfaz no teardown; sem vazamento. A lógica (`stale_rate_cards`, janela de 30 d) segue real; `now` explícito do chamador prevalece sobre o partial.
2. `card_epoch` = max(observed_at)+12 h: idade de cada card em [0, 30 d] (provado por `test_card_epoch_is_inside_every_installed_window`). Card renovado: epoch anda junto; idades dos demais só crescem até o limite de 30 d (se um card antigo ficar >30 d atrás do mais novo, o teste de epoch acusa, bom sinal). Nenhuma idade negativa: todo uso é ≥ epoch ou usa o próprio observed_at +12 h.
3. Recusa continua provada com produto real: imagem (+31 d sobre observed_at do card), 196 (+400 d), shard_pricing (fail-closed) e o novo teste (imagem/STT, epoch+31 d). Nenhum tautológico.
4. Trocas de literal: `AT`/`at`/`TEST_AT` viraram epoch ou installed+12 h, sem corte semântico dependente da data antiga (revisão por leitura dos `*_local`: usadas como "agora" fixo + `installed_card_max_age_seconds`, que já era relativo ao card). Sem mudança de significado. `test_spec237` passa a usar `_INSTALLED_CARD_PATH` (mesmo arquivo, mais robusto à renovação).
5. Ver P2-1.
6. Escopo: nenhum arquivo em `data/pricing/`, `services/`, `infrastructure/`, `scripts/`; só `tests/`, `docs/spec409/` e a spec (cabeçalho/status, +8 −4). README condiz; o desvio (função em vez de fixture) está declarado.

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

P2-1/P2-2/P3-1 podem ir no commit do Pouso A ou na Etapa 2.

## Comandos rodados

```text
pt.sh (5 arquivos sem Postgres) -n 2, sem env → rc=0
mesmos + test_spec196_finops com RPG_RATE_CARD_MAX_AGE_DAYS=1 RPG_FINOPS_LLM_CARD_MAX_AGE_DAYS=1 → rc=0
test_spec196_finops sem env → rc=0
ruff check (projeto) → All checks passed; ruff --isolated --select F401 → 24 achados
```
