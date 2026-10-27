# SPEC-337 — revisão sol (review) — correção do audit-local

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol · **Data:** 2026-10-27 · **Commit revisado:** `c96924c1`

> Nome pedido pelo coordenador. `scripts/check_handoff_names.py` **rejeita** este nome
> (`ci-fix` não é papel nem tipo). Antes do commit: anexe o texto a
> `handoffs/SPEC-337-sol-review.md` ou renomeie para `SPEC-337-sol-independent-review.md`.

## Escopo

Escopo: `git show c96924c1`, que altera `tests/test_http_idor_local.py` (+14/−4) e
`tests/test_storage_security_local.py` (+3/−1). Também conferi `services/account_security.py`,
`scripts/audit_local_gate.py`, `tests/test_http_idor_offline.py` (`_ROUTES`) e todas as
migrations de `supabase/migrations/` que tocam `storage.objects` ou `rpg-dynamic`.
Ficou fora: a execução real contra o Supabase local. Esta máquina não tem Docker, então os
testes locais pulam.

## Respostas às 3 perguntas

1. **Fixture `duo` com escopo de módulo.** Não há vazamento que mascare resultado.
   - Cada teste parametrizado continua com o próprio controle positivo, na linha 109: A faz
     `GET /game/state` e recebe 200.
   - O snapshot `before`/`after` da versão (linhas 116 e 124–125) também é por teste, então
     uma mutação feita por B continua sendo detectada no próprio caso.
   - Se uma regressão deixasse B apagar `game_a` (linha `DELETE /game/save/{g}`), esse caso
     falharia na hora (`after is None`). Os casos seguintes falhariam no controle positivo:
     isso é ruído, não falso negativo.
   - `test_delete_key_reuse_conflicts_on_postgres` é o último do arquivo. Ele faz claim e
     complete de um turno em `game_a`, sem mudar o save, e as duas tentativas de DELETE em
     `game_a` recebem 409. O jogo continua existindo.
   - O gate roda pytest em série. Não há `-n` em `audit_local_gate.py:89-107` e o
     pytest-randomly não está instalado, então a ordem é a do arquivo. Com xdist, cada worker
     instanciaria o próprio `duo`: seriam 2 logins por worker, e o bucket continuaria bem
     abaixo do limite.
   - O teardown (linhas 93–100) fecha os clientes, apaga os jogos e os usuários e fecha o
     pool. Antes, o fechamento do pool era feito pelo fixture `infra`, que foi removido.
2. **Limiter de produção intacto.** O commit não toca `services/account_security.py`; o
   último commit nesse arquivo é `2d12c577` (ruff format). `IP_ATTEMPTS = (20, 900)`
   (linha 138) e o 429 `auth_rate_limit` (linha 158) estão inalterados. A correção ficou
   do lado do teste: o número de logins caiu de 2×N para 2.
3. **Storage.**
   - A política está confirmada.
     `20261017120000_rls_effective_storage_no_client_write.sql` (comentário no ponto 3 e
     bloco final) remove `rpg_dynamic_select_own/insert/update/delete`. Com RLS ativa e sem
     policy, o acesso é negado inclusive ao dono.
   - Nenhuma migration posterior toca `storage.*`. Verifiquei `20261019100000`,
     `20261019150000`, `20261019151000` e `20261024100000`.
   - A nova asserção (A recebe 400/403/404) reflete o contrato SPEC-224 D-B. Se uma
     regressão reabrisse a leitura (policy de SELECT para `authenticated`, por dono ou
     aberta), A passaria a receber 200 e o teste falharia. Uma policy aberta também é pega
     pela asserção de B.
   - As asserções de B negado (linha 91), anon `!= 200` (linha 92) e signed URL 200
     (linhas 93–94) seguem presentes.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | tests/test_storage_security_local.py:85-92 | Com o 200 de A removido, nenhuma asserção prova que `object_url` aponta para o objeto. Um path malformado também devolve 400/404, então as negações de A, B e anon passariam trivialmente. A signed URL prova a key, mas não o formato de `object_url`. | Adicionar um controle positivo no mesmo `object_url` com o service role (`apikey`/`Authorization: Bearer {service}`): esperar 200 e conferir o corpo contra `payload`. |
| P2-2 | P2 | tests/test_http_idor_local.py:53-92 | `game_a` é compartilhado por 22 casos e o isolamento depende da ordem do arquivo (o teste de DELETE fica por último). Hoje é seguro, mas é frágil se surgir ordenação aleatória ou um teste novo depois dele. | Manter os logins com escopo de módulo e criar `game_a` em um fixture com escopo de função. `/game/new` não passa pelo limiter de auth. |
| P2-3 | P2 | scripts/audit_local_gate.py:89-107 | O bucket de IP (20 a cada 15 min) é dividido por todo o gate: 2 logins aqui e 1 em `test_mutation_api_local.py`. Funciona, mas não há guarda contra um arquivo novo que faça login em loop. | Opcional: comentário no gate sobre o orçamento de logins, ou um config de teste do servidor local com limite maior. Nunca alterar o limiter de produção. |

Nenhum achado P0 ou P1. Itens da checklist sem ocorrência: guard de structured output (não se
aplica), valor do LLM sem validação (não se aplica), writer persistente (não há), segredo em
log (não há; as chaves vêm do env e não são impressas), `evals/` protegido (não foi tocado).

## Correções aplicadas

Nenhuma. Revisão só de leitura.

## Pendências

P2-1, P2-2 e P2-3 como follow-ups da SPEC-337. Dono: coordenador.

## Comandos rodados

```text
git show c96924c1 → 2 arquivos de teste; account_security.py não tocado
bash scripts/dev/py.sh -m pytest -p no:cacheprovider tests/test_http_idor_local.py tests/test_storage_security_local.py tests/test_http_idor_offline.py -n 2 -rs → 28 passed, 23 skipped (locais pulam sem stack: esperado)
```
