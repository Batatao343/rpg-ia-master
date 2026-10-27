# SPEC-337 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão de `687cba2e` + `1e6ebf6b`; 1ª passada: `CHANGES_REQUIRED`)
> **Revisor:** Claude Opus 5.5 / papel Sol (revisão técnica) · **Data:** 2026-10-27 · **Commit revisado:** `e6621890` → re-revisão `1e6ebf6b`

## Escopo

Branch `spec-337`, intervalo `00765fb3..e6621890` (7 commits): `api.py` (L1 delete, L2 quality, L4 422),
`services/dynamic_art.py` (L2), `scripts/audit_local_gate.py` (R20/R21), `tests/fakes/two_principals.py`
e os 7 arquivos de teste novos, além do cabeçalho e do histórico da spec. Não revisei: a semântica de RLS
de `test_rls_local.py`/`test_storage_security_local.py` (são arquivos antigos que só entraram no gate).
`evals/` não foi tocado.

O que está correto:

- **L1 (R17).** Os dois pontos de consulta usam `_validated_receipt(kind="delete", request_hash=sha256("delete:{uuid}"), game_id=None)`.
  O retry legítimo continua devolvendo o recibo. `PostgresTurnCoordinator.commit_delete` (`infrastructure/postgres_turns.py:575-630`)
  nunca preenche `operations.game_id`, então `row["game_id"] == None` casa com `game_id=None` em `receipt()` (`:651-655`).
  Uma key de outra operação (turno, ou delete de outra campanha, que tem outro hash) dá `Conflict` → 409 `operation_request_mismatch`
  **antes** do `claim`/`commit_delete`, e nada é apagado. O fake offline replica a semântica do Postgres (falhada → `None`; mismatch → `Conflict`).
  Os 3 testes offline provam isso: o 409 vem com a campanha preservada, e o retry dá 200 duas vezes com um único `commit_delete`.
- **L2 (R18).** O `UPDATE` continua atômico, agora com `and game_id=%s`. A coluna existe (`art_generations.game_id uuid not null`).
  O único chamador passa `uuid.UUID(state["game_id"])`. O oráculo 409 de hoje é mantido.
- **L4 (R19).** `detail` passa a ser `[{type, loc, msg}]`. O frontend só lê `loc`/`msg` (`web/src/http.ts:51-61`),
  e nenhum teste lia `input`/`ctx`/`url` do 422. Sem regressão.
- **Controle positivo (R15).** Está presente offline (`/game/state`, `/game/history` e `/game/saves` com o nome semeado)
  e, na matriz local, por caso. Rodei a matriz offline instrumentada: B recebe **404 em 20 de 21 rotas**,
  e em `audit-export` recebe 403 `recent_session_required`.
- **R9 / CORS (desvio do executor).** O desvio está certo e não é problema de segurança. O `CORSMiddleware.preflight_response`
  do Starlette monta o ACAO quando a **origem** é permitida e só depois soma as falhas de método/header, devolvendo 400 com esses headers.
  A origem ecoada já é confiável (está na allowlist), e o navegador reprova o preflight pelo status ≠ 2xx e pela ausência do método em
  `Access-Control-Allow-Methods`. A requisição real não sai. Com origem não listada, não há ACAO. O teste confere o comportamento real (ver P2-3).
- **Segredo.** As chaves do Supabase local só entram no `env` do subprocesso. Não são impressas, e o `summary.json` e o `results.xml` não as contêm.
  A mensagem de skip lista só nomes de teste.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | `scripts/audit_local_gate.py:51` | `from scripts.start_local_api import _supabase_status` falha quando o script roda como no CI (`uv run python scripts/audit_local_gate.py`). `sys.path[0]` é `scripts/`, não a raiz, e `scripts/` não tem `__init__.py` instalado. Reproduzi: `bash scripts/dev/py.sh scripts/audit_local_gate.py` → `ModuleNotFoundError: No module named 'scripts'`. O job `audit-local` quebra antes de subir a API. `test_audit_local_gate_contract.py` não pega isso porque importa o módulo sob o `pythonpath=["."]` do pytest. | Fazer como `scripts/audit_local_server.py:11`: `sys.path.insert(0, str(ROOT))` no topo do módulo (ou dentro de `main()` antes do import). Adicionar ao contrato um teste que rode `subprocess.run([sys.executable, "-c", "import runpy,sys; sys.argv=['x']; ..."])` ou, mais simples, que execute `python scripts/audit_local_gate.py --help`-like / um import em processo filho com `cwd=ROOT` e `sys.path[0]=scripts`, provando que o import resolve. |
| P0-2 | P0 | `tests/test_http_idor_local.py:145-147` | `test_art_quality_cross_game_on_postgres` faz `pytest.skip(...)` **incondicional**. O arquivo está em `SECURITY_TEST_FILES`, e o R21 transforma qualquer `<skipped>` desses arquivos em código 1. Mesmo com o P0-1 corrigido e a stack de pé, o gate falha **sempre**. | Remover o teste (a omissão do L2 no Postgres já está no docstring do módulo e na spec, critério R18) ou marcá-lo de outro jeito que não produza `<skipped>` (por exemplo, nem coletar). Não usar `xfail`/skip dentro dos arquivos do gate. |
| P1-1 | P1 | `specs/SPEC-337-http-security-tests.md:3` | Status `done` com critérios abertos: R20/R21 (gate + job `audit-local` verde), a variante Postgres de R17 e a suíte completa. Com P0-1/P0-2 o job não pode ficar verde. | Voltar para `in-progress` até o `audit-local` passar no PR. Quem marca `done` é o pouso. |
| P2-1 | P2 | `tests/test_http_idor_offline.py:200`, `tests/test_http_idor_local.py:108` | O conjunto aceito `{400, 403, 404, 409}` é mais frouxo que o R14 (404, ou 403/409 onde a rota já responde assim). Um 400 de validação de corpo passaria sem provar ownership. Medido offline: 20 rotas dão 404, e `audit-export` dá 403 por `recent_session_required`, uma pré-condição de sessão e não de ownership, o que deixa essa rota sem prova. | Exigir 404 por padrão e um mapa explícito de exceções por rota (por exemplo `audit-export: 403`, com comentário). Para `audit-export`, marcar `rpg_recent` no client B, de modo que o 404 venha da checagem de dono. |
| P2-2 | P2 | `tests/test_http_idor_offline.py:3-6`, `:209` | O docstring diz que `/game/{g}/operations/{op}` fica só na matriz local, mas a rota está em `_ROUTES` e roda offline (dá 404). `_digest` está morto. | Ajustar o docstring e remover `_digest`. |
| P2-3 | P2 | `tests/test_http_cors.py:66-70` | Nos casos `method`/`header` o teste só confere o 400 e o texto `Disallowed CORS`. Não prova que `PUT` fica fora de `Access-Control-Allow-Methods` nem que `x-evil` fica fora de `Access-Control-Allow-Headers`, que é o que de fato bloqueia o navegador. | Adicionar `assert "PUT" not in out.headers.get("access-control-allow-methods", "")` e o equivalente para `x-evil` em `access-control-allow-headers`. |
| P2-4 | P2 | `scripts/audit_local_gate.py:34` | `f".{stem}" in classname` é casamento por substring. Por exemplo, `tests.test_rls_local_extra` contaria como `test_rls_local`. Hoje é inócuo. | Usar `classname == f"tests.{stem}" or classname.endswith(f".{stem}")` ou comparar o último segmento. |

## Correções aplicadas

Re-revisão (executor, `687cba2e` + `1e6ebf6b`):

- **P0-1 fechado.** `sys.path.insert(0, ROOT)` no topo + import no módulo. `bash scripts/dev/py.sh scripts/audit_local_gate.py` agora passa do import e só para em `npx supabase status` (stack local fora do ar aqui, esperado; nenhum processo sobe antes). Teste novo `test_gate_script_imports_when_run_as_script` (`-I` + `runpy`, cwd=tmp) prova o import em processo filho.
- **P0-2 fechado.** O teste de skip incondicional foi removido; a omissão de L2 no Postgres segue documentada.
- **P1-1 fechado.** Cabeçalho da spec voltou para `in-progress`.
- **P2-2, P2-3, P2-4 fechados.** Docstring corrigido e `_digest` removido; asserts de `PUT`/`x-evil` fora de Allow-Methods/Allow-Headers; `endswith`.
- **P2-1 parcial.** A matriz agora exige 404 (`_EXPECTED_STATUS` vazio) e B tem `rpg_recent`. Mas, para o `audit-export`, o fake `_NoRowsAuditSource.load` (`tests/test_http_idor_offline.py:195-199`) devolve `None` **para qualquer principal**. O 404 sai do fake, não da checagem de dono real (`PostgresAuditSource.load` → `self.store.get(self.principal, game_id)`, `infrastructure/audit_source.py:38`). A rota fica tautológica no offline (`store.pool=None` só serve para o construtor). Não é bug de produto: a checagem real é `store.get` por principal, já coberta pelas outras 20 rotas, e a matriz local (Postgres real, sem fake) cobre `audit-export` de verdade. Fica como follow-up **P2-5**.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-5 | P2 | `tests/test_http_idor_offline.py:195-199` | O fake de `PostgresAuditSource` devolve `None` sem consultar o store, e o 404 do `audit-export` não prova a checagem de dono no offline. | No fake, pular só a consulta de `account_deletions` e delegar para o store: `def __init__(self, pool, store, principal)`; `load` → `return None if self.store.get(self.principal, game) is None else <AuditSource mínimo>`. Com controle positivo: A com `rpg_recent` recebe 200 ou um status ≠ 404. |

## Pendências

- P2-5 (acima): endurecer o fake do `audit-export` no offline (executor da 337 ou da 338).

- Depois de P0-1/P0-2: rodar `scripts/audit_local_gate.py` com a stack local de pé (ou o job `audit-local` no PR) e conferir zero `<skipped>` nos três arquivos. Isso fecha R20/R21 e a variante Postgres de R17.
- L2 contra o Postgres continua sem cobertura local (o SQL só é exercitado em produção). Follow-up: semear uma linha `art_generations` `ready` direto por SQL no teste local, sem rede, já que o `infra` dá acesso ao pool.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_http_security_headers.py tests/test_http_cookie_flags.py tests/test_http_cors.py tests/test_http_error_leakage.py tests/test_http_idor_offline.py tests/test_audit_local_gate_contract.py tests/test_http_idor_local.py → verde; 23 skips só do idor_local (RPG_TEST_DATABASE_URL ausente)
bash scripts/dev/py.sh -m pytest -q -n 2 tests/test_abuse_policy.py tests/test_polish_sessao.py tests/test_turn_trace_logs.py tests/test_error_envelope.py tests/test_dynamic_art_jobs.py tests/test_auth_gotrue_error_mapping.py → 113 passed
pytest tests/test_http_idor_offline.py -k principal_b com plugin de log de status (scratchpad) → 20×404, audit-export 403 recent_session_required
bash scripts/dev/py.sh scripts/audit_local_gate.py → ModuleNotFoundError: No module named 'scripts' (linha 51), antes de subir qualquer processo
# re-revisão (1e6ebf6b)
bash scripts/dev/py.sh scripts/audit_local_gate.py → import OK; CalledProcessError em npx supabase status (stack local fora do ar; esperado)
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 <7 arquivos da spec> → 103 passed, 22 skipped (todos idor_local: RPG_TEST_DATABASE_URL ausente)
```
