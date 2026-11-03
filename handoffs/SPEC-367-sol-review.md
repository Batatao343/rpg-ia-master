# SPEC-367 — revisão sol (review)

> **Veredito:** `APPROVED` (rodada 2, `505b41bd`; rodada 1 `5f05a60c`: `CHANGES_REQUIRED`)
> **Revisor:** Sol (Opus) · **Data:** 2026-11-03 · **Commit revisado:** `5f05a60c` (rodada 1), `505b41bd` (rodada 2)

## Escopo

Branch `spec-367`, `git diff main...spec-367` (base `eec75ef5`), commits `9efc97a9..5f05a60c`
(spec + 7 commits do executor), 26 arquivos. Conferi R1–R25 contra o código e os testes, os
desvios do §9, `scripts/staging/ops_pool.py`, `retire_creature_portrait.py --dry-run/--env-file`,
a trava `portraitInFlight` em `App.tsx`, o 409 novo contra o catálogo de erros e o guarda de
`except` silencioso. Ficou de fora: o smoke real §6 (é do coordenador), o e2e Playwright (não
rodado; li o spec) e a suíte completa.

Conferido e sem achado:
- **Integridade de eval:** sem diff em `evals/`, arenas/sim, golden 330 (`tests/spec330_equivalence.py`,
  `tests/fixtures/spec330_legacy_golden.json`), `web/e2e/contracts` e specs existentes de `web/e2e/`. Também sem diff em
  `config/flags.yaml`, `services/conflict_orchestrator.py`, `services/scene_cards.py`, `agents/combat.py`,
  `services/card_piles.py` e `data/cards/`.
- **`tests/test_spec364_market.py`:** a mudança é só a assinatura do `fake` (`gold_check=None`). O
  `seen.append((context, fallback))` e todas as asserções ficam iguais, então o oráculo não ficou mais fraco.
- **`ops_pool.py`:** não imprime segredo (só `attempt` e `error_class`). O pool é fechado no `finally` nos
  dois scripts. O `peek_ceiling` do preflight continua best-effort. A saída é `3` com `error: db_unavailable`.
- **`--dry-run`:** é só leitura (um `select status, store, object_keys`). Não chama `registry.retire` nem
  `shared.delete`. `--env-file` usa `load_dotenv(..., override=False)` antes de `build_runtime()` e não imprime valores.
- **Front:** `portraitInFlight` (`useRef`) é ligado antes do 1º `await` e solto no `finally`.
  `withPortraitPending` é imutável e devolve o mesmo objeto quando nada muda. O teste unitário dá 3/3.
- **Voz (R7, R8, R13):** a implementação está correta. O lint do catálogo cobre `de/do/da {alvo}`, `{alvo}`
  no início e clítico depois de `{alvo}`.
- **Prefixo (R1):** a implementação está correta. Tem ≥ 2 tokens significativos, o prefixo mais longo ganha e
  empate dá `None`. Nenhum `with_structured_output` novo e nenhuma chamada de LLM nova por rodada (R20, R21).
- **V-G:** o evento `loot.trade_prose_rejected` não leva o texto. O desvio de "um/uma" (só colado a moeda) é
  aceitável.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `api.py:4946` (+ `services/error_codes.py:~110`) | O código novo `creature_portrait_not_offered` não está no catálogo. `tests/test_error_envelope.py::test_every_http_exception_has_catalog_code` **falha** (`[('api.py:4946', 'creature_portrait_not_offered')]`), e a suíte do pouso fica vermelha. R23 pede um contrato aditivo, ou seja, o código precisa estar registrado | Registrar em `services/error_codes.py` (junto de `creature_portrait_exists`). Regenerar `docs/operacao/CODIGOS_DE_ERRO.md` (`scripts/gen_error_codes_doc.py`, `test_docs_are_fresh`) e `web/src/lib/errorCodes.json` (`test_web_code_list_is_fresh`). Acrescentar a mensagem em `web/src/lib/errorMessages.ts` e, se fizer sentido, tratar o código em `shouldHidePortraitOffer`/`portraitErrorBanner` (409 de fallback → esconder a oferta) |
| P1-2 | P1 | `tests/test_spec367_guards.py:18-49` | O guarda compara `merge-base(HEAD, 9efc97a9)..HEAD` sem se limitar à branch. Depois do pouso, **qualquer** spec futura que mexa de forma legítima em `config/flags.yaml`, `conflict_orchestrator.py`, `scene_cards.py`, `conflict_turn.py`, no golden 330 ou num spec de `web/e2e` quebra esse teste na `main`. Depois de um `wt.sh sync` com rebase, o commit fixado sai do histórico, e o diff passa a incluir commits da `main` | Rodar o guarda só na branch da spec (precedente: `_on_branch()`/`_tem_base_fixada()` em `tests/test_spec362_arcanista.py:54-68`) com `merge-base main HEAD`, e `skip` fora dela. Alternativa: pôr o guarda como checagem de pouso, fora da suíte permanente |
| P2-1 | P2 | `scripts/staging/ops_pool.py:15,24-40` | `_is_checkout_failure` decide "foi no checkout" pela **ausência** de frames de comando. Um `OperationalError` no **commit** (`Transaction.__exit__` → `wait` → `_commit_gen`, depois do `insert` de `store.set`) não tem frame `execute`, então é repetido. Testei um `store.set` falso que falha no `__exit__`: foi chamado **3 vezes**. Se o commit chegou ao servidor e só a resposta se perdeu, a auditoria fica duplicada. Isso fere R18 ("só no checkout, quando nenhum comando chegou ao banco") | Detecção positiva: `OperationalError` só conta como checkout se o traceback passa por `getconn` (psycopg_pool) ou `connect` e não por nenhum frame de comando/commit. Ou incluir `commit`, `__exit__`, `wait`, `_commit_gen` e `_exit_gen` na lista de exclusão. Acrescentar `test_no_retry_on_commit_error` com `store.set` chamado 1 vez |
| P2-2 | P2 | `services/prose_guard.py:510-514` | A regra (b) de V-G tem dois furos que testei. (i) "Você entrega as últimas **quarenta e cinco** moedas" passa (`True`), enquanto a mesma frase com "45" é rejeitada. O LLM escreve número por extenso com frequência. (ii) "Você fica **sem moedas**" passa, porque `sem (?:nenhuma )?moeda\b` não aceita o plural | Aceitar número por extenso entre "últimas" e "moedas" (reusar `_GOLD_WORD_NUM`, com o "e unidade" opcional) e trocar para `sem (?:nenhuma )?moedas?`. Acrescentar as duas frases a `test_vg_*` como rejeitadas com `gold_after=5` |
| P2-3 | P2 | `tests/test_spec367_omen_voice.py:72-84` | O teste de R9 não cobre o que R9 pede. `_rounds` (de `test_enemy_intent_node`) monta 1 encontro de Bandido, com o nome de herói da fixture: não usa "Smoke5A"/"Mirela5", não garante 2 inimigos e não usa as famílias `fera`/`morto_inquieto`. O `parametrize("fam")` só alimenta um `sinal_for(..., "você")` que já recebe "você" pronto, então é vácuo. O laço da view também passa sem nada se `pressagios_publicos` vier vazio. O desvio declarado no §9 era só "sem TestClient" | Semear o combate com 2 inimigos de `fera` e de `morto_inquieto` (hint/bestiary id dessas famílias ou inimigos injetados), herói "Smoke5A" e "Mirela5", 2 rodadas, e afirmar que `pressagios_publicos` da view de `api._combat_block` **não é vazio** e que nenhum `sinal`/`prenuncio` contém o nome |
| P3-1 | P3 | `tests/test_spec367_cites_prefix.py:34-40` | R2 diz que "N é o `sell_price` da cotação dessa entrada", mas o teste só confere o começo e o fim da frase. Um N de outra entrada ou do catálogo passaria | Calcular a cotação esperada da entrada (o mesmo helper do caminho de R7 da 364) e afirmar a string exata `"[SISTEMA] …: o mercador paga {N} moedas. …"` |
| P3-2 | P3 | `tests/test_spec367_condition_end.py:32-42` | R14 pede uma luta semeada em que Cego termina e a checagem de registro, `mech_log`, mensagem do turno e `/game/history`, uma vez por evento. O teste cobre só `round_registry` e `_normalize_status_logs` com entrada sintética | Acrescentar o caso com o nó de combate (como `_rounds`) e uma condição de inimigo que expira. Afirmar a frase de R13 uma vez em `mech_log` e na mensagem do turno, e nenhuma linha crua no histórico montado (`_game_history`/view do Livro) |
| P3-3 | P3 | `services/creature_art.py:209-213` | `except Exception: pass` novo em `is_fallback_enemy`, marcado `silent-ok`. É redundante: `normalize_bestiary_id` já é chamado sem guarda em `portrait_for` (`:247`) e em `portrait_key`. E é fail-open: se levantar, o inimigo deixa de ser tratado como fallback, que é o lado que oferece a geração paga. O coordenador pediu nenhum `except` silencioso novo | Tirar o `try/except` e chamar `normalize_bestiary_id(enemy)` direto |
| P3-4 | P3 | `scripts/retire_creature_portrait.py:66-69` | `--env-file` com caminho errado ou inexistente passa calado (`load_dotenv` devolve `False`) e o script roda contra o ambiente do processo. No §6.1 a retirada real roda da estação, que pode ter outro `DATABASE_URL` | Antes de carregar, testar se o arquivo existe: `parser.error("--env-file não encontrado")` se não existir. Acrescentar um teste |

## Correções aplicadas

Rodada 2: commit `505b41bd`. Revisei `git diff 7ef7862b..spec-367` contra os 9 achados e todos estão fechados.

| ID | Status | Verificação |
|---|---|---|
| P1-1 | fechado | `creature_portrait_not_offered` está em `services/error_codes.py`, `CODIGOS_DE_ERRO.md`, `errorCodes.json` e `errorMessages.ts`. O front esconde a oferta e mostra um aviso `info` sem custo (`portraitOrder.ts`, com teste unitário). `test_error_envelope` está verde |
| P1-2 | fechado | O guarda roda só com `HEAD == spec-367`, contra `merge-base main HEAD`, e faz `skip` fora da branch. Na branch ele roda de fato (sem skip) e passa |
| P2-1 | fechado | Detecção positiva: o erro só conta como checkout se houver frame `getconn`/`connection`/`connect` e nenhum frame de comando ou commit (`__exit__`, `wait`, `commit`, `_commit_gen`, `_exit_gen`). `test_no_retry_on_commit_error` dá 1 escrita. Uma falha no corpo do `with` passa por `__exit__` do contextmanager e não é repetida. O efeito colateral possível é um falso negativo, ou seja, deixar de repetir uma falha de checkout, o que é seguro |
| P2-2 | fechado | A regra (b) aceita número por extenso com "e unidade" depois de "últimas" e aceita `sem moedas?`. As duas frases da sonda entram em `test_vg_number_words` como rejeitadas. O corpus benigno segue verde |
| P2-3 | fechado (com desvio aceito) | O teste roda um combate real pelo nó, com heróis "Smoke5A" (`enemy_lobo_sombrio`, fera) e "Mirela5" (`enemy_esqueleto`, morto_inquieto), 2 rodadas. Ele exige que a lista da view não venha vazia, que haja ≥ 2 atores, que algum ator seja da família pedida, que nenhum `sinal`/`prenuncio` traga o nome e que apareça "você". **Desvio:** o encontro do esqueleto sai misturado, então o teste exige só "ao menos um" da família. **Aceito.** O requisito de R9 é a invariante de voz (nome do herói ausente em toda a view, 2 inimigos, 2 rodadas), e ela vale para **todas** as linhas, de qualquer família. As duas famílias do smoke estão representadas, uma em cada caso, e o `random.seed(9)` torna o encontro determinístico (verde em `-n 2` e em série). Forçar um encontro 100 % de uma família só para o teste não dá cobertura de voz a mais. O catálogo das duas famílias já é coberto frase a frase com nome e com "você" (`test_every_phrase_formats_with_name_and_voce`) |
| P3-1 | fechado | Afirma a string exata, com N igual ao `sell_price` da entrada em `public_market_snapshot` |
| P3-2 | fechado | `test_spec367_condition_node.py` passa pela API real (`/game/action` + `/game/history`). Em `mech_log`, registro, mensagem e Livro: nenhuma linha crua `X: y terminou`, e a frase de R13 aparece no máximo 1 vez por superfície e em pelo menos uma delas. Observação, sem achado: a linha "terminou" é injetada no `run_round`, porque não dá para semear a expiração natural sem mexer no motor (R24). Por isso o teste prova a apresentação, que é o escopo de A5 |
| P3-3 | fechado | O `try/except` saiu de `is_fallback_enemy`; `normalize_bestiary_id` é chamado direto |
| P3-4 | fechado | Um `--env-file` inexistente dá `parser.error` antes de `build_runtime` (`test_retire_missing_env_file_is_error`) |

Regressão nova: nenhuma encontrada. O evento `loot.trade_prose_rejected` agora está registrado em
`observability/events.py` e `EVENTOS_DE_LOG.md` (`test_log_event_registry` verde). Continua sem diff em
`evals/`, no golden 330, nos specs existentes de `web/e2e`, em `config/flags.yaml` e no motor.

## Pendências

Nenhuma. Veredito final da rodada 2: **APPROVED**.

## Comandos rodados

```text
git diff main...spec-367 --stat → 26 arquivos, +1673/−74
py.sh -m pytest -n 2 test_error_envelope test_no_silent_except test_spec367_* test_spec363_ids test_spec364_market → 1 failed (catálogo, P1-1), 101 passed
py.sh -m pytest -n 2 test_spec363_*.py test_spec364_*.py test_enemy_intent*.py test_spec353_misc test_spec352_creature_quote_api test_spec196_finops test_spec346_board_no_llm → 410 passed, 4 skipped
node --test web/tests/spec367-portrait-pending.test.mjs → 3/3 pass
sonda gold_claims_ok (scratchpad) → "últimas quarenta e cinco moedas" e "sem moedas" aceitas com depois=5 (P2-2)
sonda with_checkout_retry com OperationalError no __exit__ do commit → store.set chamado 3x (P2-1)
git diff main...spec-367 -- evals/ web/e2e/contracts golden-330 flags orquestrador scene_cards combat card_piles data/cards → vazio
[rodada 2] py.sh -m pytest -n 2 test_error_envelope test_no_silent_except test_log_event_registry test_spec367_*.py test_spec363_ids test_spec364_market test_spec352_creature_quote_api test_spec196_finops test_spec363_portrait_offer test_enemy_intent test_enemy_intent_node → 263 passed, 1 skipped (fora da 367)
[rodada 2] py.sh -m pytest (em série) test_spec367_guards test_spec367_omen_voice test_spec367_condition_node → 12 passed (guarda executado, sem skip)
[rodada 2] node --test web/tests/spec367-portrait-pending.test.mjs → 4/4 pass
```

## Rodada 3: `848a63cb` (`--dsn-env` no `retire_creature_portrait.py`, na `main`)

**Veredito da rodada 3:** `CHANGES_REQUIRED`

Segurança, conferida no código e sem achado:
- Nada de DSN ou chave é impresso. O `parser.error` mostra só o **nome** da variável. A saída JSON tem `portrait_key`, status e object keys.
- `--dry-run` continua só leitura: o mesmo `_dry_report`, um `select` via `admin_connection` no pool de operação. Não exige o bucket.
- Sem shared store, a retirada pelo `--dsn-env` dá `parser.error` (`:114-115`) **antes** de `retire()`, ou seja, antes de `registry.retire` e de qualquer `update`. O `finally` fecha o pool também nesse caminho (o `SystemExit` passa pelo `finally`).
- O bucket `rpg-shared-art` com `shared=True` é o mesmo de `infrastructure/runtime.py:782-783`.
- O pool vem de `open_ops_pool`, com o mesmo timeout tolerante da R18.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R3-P2-1 | P2 | `tests/test_spec367_fallback_portrait.py:147-181` | O teste vaza variáveis de ambiente para o resto do processo de teste. O `monkeypatch.delenv(k, raising=False)` de uma variável **ausente** não registra nada para restaurar, e depois o `load_dotenv` grava `SPEC367_DSN`, `SUPABASE_URL=https://s` e `SUPABASE_SERVICE_ROLE_KEY=k` em `os.environ`. Uma sonda rodada em seguida no mesmo processo leu `SUPABASE_URL=https://s`, chave presente e `SPEC367_DSN` presente. Como `infrastructure/runtime.py` valida essas variáveis (`:158-178`, `:94-104`, `:279-281`), os testes seguintes do mesmo worker xdist ficam sujeitos a flake por ordem | Registrar a restauração antes do `load_dotenv`: `monkeypatch.setenv(k, "")` seguido de `monkeypatch.delenv(k)`, ou `monkeypatch.setattr(os, "environ", os.environ.copy())`. Aplicar o mesmo em `test_retire_env_file_and_dry_run` (`:83`), que só limpa `SPEC367_ONLY_HERE` quando o teste passa |
| R3-P3-1 | P3 | `scripts/retire_creature_portrait.py:114-115` (sem teste) | O ramo que falha fechado (`--dsn-env` sem `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`) está correto, mas nenhum teste o cobre. É exatamente a garantia de "retire sem shared store falha antes de mexer" | Acrescentar um teste com `_ops_runtime` falso devolvendo `shared_blob_store=None`: afirmar `SystemExit != 0`, `reg.calls == []` e `pool.close()` chamado 1 vez. E um caso `--dry-run` sem bucket, que deve concluir com 0 |

Comandos (rodada 3):

```text
git show 848a63cb → 3 arquivos (+94/−9): script, teste, §9 da spec
py.sh -m pytest -s tests/test_spec367_fallback_portrait.py tests/test_no_silent_except.py + sonda de ambiente (scratchpad) → todos verdes; sonda: "LEAK https://s True True" (R3-P2-1)
```
