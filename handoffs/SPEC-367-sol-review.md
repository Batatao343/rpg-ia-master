# SPEC-367 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus) · **Data:** 2026-11-03 · **Commit revisado:** `5f05a60c`

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

(vazio: 1ª rodada)

## Pendências

Nenhuma aceita como follow-up. Pela política do dono (zero pendência), todos os itens acima são para esta spec.

## Comandos rodados

```text
git diff main...spec-367 --stat → 26 arquivos, +1673/−74
py.sh -m pytest -n 2 test_error_envelope test_no_silent_except test_spec367_* test_spec363_ids test_spec364_market → 1 failed (catálogo, P1-1), 101 passed
py.sh -m pytest -n 2 test_spec363_*.py test_spec364_*.py test_enemy_intent*.py test_spec353_misc test_spec352_creature_quote_api test_spec196_finops test_spec346_board_no_llm → 410 passed, 4 skipped
node --test web/tests/spec367-portrait-pending.test.mjs → 3/3 pass
sonda gold_claims_ok (scratchpad) → "últimas quarenta e cinco moedas" e "sem moedas" aceitas com depois=5 (P2-2)
sonda with_checkout_retry com OperationalError no __exit__ do commit → store.set chamado 3x (P2-1)
git diff main...spec-367 -- evals/ web/e2e/contracts golden-330 flags orquestrador scene_cards combat card_piles data/cards → vazio
```
