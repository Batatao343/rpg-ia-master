# SPEC-281 — revisão (review)

> **Veredito:** `APPROVED` (após 1 correção P1 aplicada na branch)
> **Revisor:** Opus (revisor independente) · **Data:** 2026-10-19 · **Commit revisado:** `0356b63`

## Escopo

Branch `spec-281` (`git diff main...spec-281`): `services/jev_rollout.py` (`warm_client`,
`_default_backend`, `begin`), `tests/test_jev_client_warm.py`, cabeçalho da spec. Fora:
staging/medição real do cold start (a spec exclui).

## Verificação dos pontos pedidos

1. **`off` byte-idêntico:** `begin` retorna em `mode == "off"` antes de qualquer coisa; o
   `import httpx` foi movido para dentro do `if _client is None` em `warm_client`, então `off`
   nem importa nem constrói. Coberto por `test_off_does_not_build_client`. OK.
2. **Thread-safety:** `warm_client` usa o mesmo `_lock` de `_pool()` (double-check sob lock,
   sem reentrância — `warm_client` não chama `_pool`). O worker do pool e o thread do SSE
   chegam no mesmo singleton; `httpx.Client` é thread-safe para requisições concorrentes.
   Custo: a 1ª construção segura o lock alguns ms e pode atrasar um `_pool()` concorrente,
   só uma vez por processo. OK.
3. **Warm-up vs turno:** a construção passou a ser síncrona no thread do router (1×/processo).
   Em `primary` o turno paga a construção uma vez, mas não perde mais o Jev por timeout falso.
   Em `shadow` o 1º turno fica um pouco mais lento do que antes (antes a construção corria
   inteira no worker). Aceitável, e o `_frozen()` já tem o mesmo perfil. **Defeito achado
   (P1-1, corrigido):** falha na construção (`OSError` de SSL, por exemplo) levantava de dentro
   de `begin`, e o router (`agents/router.py:246`) não protege a chamada. Antes da spec, essa
   falha ficava dentro do `try` de `_evaluate`, virava outcome `error` e caía no CLASSIFY.
4. **Kill switch/aprovação antes da construção:** `warm_client()` roda depois de off, kill
   switch, `approval_required` e `uncalibrated_threshold`. OK (R2).
5. **Client/vazamento entre testes:** a fixture `monkeypatch` restaura `_client` e
   `httpx.Client`. Havia uma corrida: o worker submetido em
   `test_client_built_before_deadline_clock` podia rodar depois do teardown e construir um
   `httpx.Client` real no global (P2-1, corrigido: o teste espera o future). O client de
   produção nunca é fechado, por design. É o mesmo comportamento que já existia antes, um
   por processo e no mesmo padrão do `_executor`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | services/jev_rollout.py:427 | `warm_client()` sem `try` em `begin`: falha de construção derruba o turno (regressão: antes caía no CLASSIFY) | `try/except` com `# silent-ok:`; o worker refaz a construção e cai em `error` → CLASSIFY. Teste `test_build_failure_does_not_break_turn` (falha sem o fix) |
| P2-1 | P2 | tests/test_jev_client_warm.py:52 | worker podia sobreviver ao teste e gravar `httpx.Client` real no global; classe `_Backend` morta | espera `pending._future.result(timeout=10)`; `_Backend` removida |

## Correções aplicadas

- P1-1 e P2-1 no commit de revisão `fix(jev): never let client warm-up break the turn (SPEC-281 review)`.

## Pendências

Nenhuma bloqueante. Observação: `_frozen()` em `begin` também não tem `try` (pré-existente,
SPEC-217, fora do escopo). Vale um follow-up pequeno se o dono quiser simetria.

## Comandos rodados

```text
py.sh -m pytest -q tests/test_jev_client_warm.py tests/test_jev_rollout.py tests/test_jev_router_port.py tests/test_jev_decision_backend.py tests/test_spec217_j2.py → 99 passed
(sem o fix em jev_rollout.py) py.sh -m pytest tests/test_jev_client_warm.py → test_build_failure_does_not_break_turn FAILED
```
