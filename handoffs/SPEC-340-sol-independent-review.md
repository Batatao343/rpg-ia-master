# SPEC-340 — revisão sol (independent-review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Claude Opus 5.5 / Sol · **Data:** 2026-10-27 · **Commit revisado:** `f3961710`

## Escopo

Diff `main...HEAD` (1 commit, `f3961710`): `scripts/flag_registry.py`, `config/flags.yaml`
(205 entradas), `tests/test_flag_registry.py`, `docs/guias/TESTES.md` § Flags, `AGENTS.md` (1 linha)
e o cabeçalho da spec. Conferi R1–R10 contra o código. Também conferi uma amostra de defaults e
kinds contra as leituras reais (`os.getenv`/`_choice`) e a execução no CI (`validate.yml`,
`ci_docs_only.py`). Nada em `evals/` foi alterado. Não há LLM, structured output nem writer
persistente no diff.

O que está certo: `validate` é puro e recebe `today` (R6). A mensagem de vencida contém
"remova a flag ou renove `expires` com justificativa no `note`" (R6). `check` passa no repo real,
o CLI funciona (`check` dá exit 0 e `expiring --days 120` lista as 40 `release`). O teste roda
na suíte default sem marker (`addopts` só exclui `llm_contract`/`llm_playtest`/`api_fuzz`).
Mudança em `.py` ou `config/` nunca cai no caminho docs-only. Nenhum segredo tem valor gravado:
as entradas `*_SECRET`/`*_TOKEN`/`*_PASS`/`*_KEY` estão com `null`, `""` ou com o nome de outra
variável (ver P1-2).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `config/flags.yaml:324` (`RPG_DB_POOL_[A-Z0-9_]*`), `:970` (`RPG_STAGING_SMTP_[A-Z0-9_]*`) | Esses dois padrões não vêm de nomes dinâmicos. Só existem porque o scanner pega o token truncado em texto: `"RPG_DB_POOL_*"` em mensagens de erro (`infrastructure/runtime.py:263,332`) e `RPG_STAGING_SMTP_{HOST,...}` no docstring (`scripts/staging/auth_config.py:10`). Todos os nomes reais são literais e já estão registrados um a um. O efeito é que qualquer `RPG_DB_POOL_X` ou `RPG_STAGING_SMTP_X` novo passa sem registro. É o enfraquecimento do gate que o R7 quer evitar ("só se houver nomes dinâmicos reais"). | Remover as duas entradas `pattern: true`. Para o token truncado, a opção mais limpa é o scanner ignorar nomes que terminam em `_` (prefixo nunca é nome de env). A alternativa é registrar `RPG_DB_POOL_` e `RPG_STAGING_SMTP_` como entradas exatas `kind: dev`, note "token de mensagem, não é flag". Incluir um teste unitário. |
| P1-2 | P1 | `config/flags.yaml:9,19,…,782,950` (≈11 entradas) e defaults de `release` (`:340`, `:633`, `RPG_DAY_DIGEST`, `RPG_LAW`) | O campo `default` (R1) saiu da heurística e está errado em vários pontos. (a) Pelo menos 11 entradas trazem como "default" o **nome de outra variável** ou de uma chave de dict: `RPG_REPLAN_AFTER: "RPG_DAY_DIGEST"` (real: `on`), `RPG_ADMIN_ALLOW_PROFILE: "RPG_KILL_SWITCHES_OFF"`, `RPG_EXPOSE_OPENAPI: "RPG_POOL_ALLOW_MOCK_EVAL"`, `RPG_JEV_ROUTER_PRIMARY_APPROVED: "RPG_NPC_KNOWLEDGE"`, `RPG_STAGING_SMTP_PASS: "smtp_admin_email"`, `RPG_ARCHIVE_POLICY: "RPG_ARCHIVE_POLICY_SHADOW"` (a própria spec dá `legacy` como exemplo), `RPG_ADMIN_DB_PASSWORD`/`RPG_RUNTIME_DB_PASSWORD`, `RPG_ALLOW_INSECURE_HOSTED`, `RPG_IMAGE_PRICE_PROFILE_PORTRAIT`, `RPG_STAGING_TURNSTILE_SECRET`. (b) Há `release` com `null` mas default real no código: `RPG_NPC_TWO_PHASE` (`on`, `latency_flags.py:23`), `RPG_EARLY_NARRATIVE` (`shadow`, `turn_delivery.py:23`), `RPG_DAY_DIGEST` (`inline`, `latency_flags.py:31`), `RPG_LAW` (`off`, `law.py:157`). O registro se apresenta como "documentação verificada", e as `release` são justamente as flags que alguém vai consultar para limpar o caminho `off`. | Revisar à mão **todas as 40 `release`** contra a leitura no código e corrigir `default`. Em todas as entradas, zerar (`null`) ou corrigir os defaults que casam `^[A-Z][A-Z0-9_]+$` ou que são chave de dict (`smtp_*`). Opcional: um teste barato que falhe se `default` casar `^RPG_[A-Z0-9_]+$`. |
| P2-1 | P2 | `config/flags.yaml:541,563,584` | Padrões dinâmicos reais (`RPG_LIMIT_`, `RPG_LLM_MAX_CONCURRENCY_`, `RPG_LOG_LEVEL_`) estão largos demais (`[A-Z0-9_]*`). `RPG_LIMIT_PAYMENTS_OPEN_ORDERS` é literal em `stripe_payments.py` e só é pego porque também tem entrada exata. Um literal novo `RPG_LIMIT_*` passaria calado. | Estreitar para o formato montado: `RPG_LIMIT_(?:[A-Z0-9_]+_(?:IP\|OWNER))?` (`abuse_policy.py:110-113`) e `RPG_LLM_MAX_CONCURRENCY_[A-Z]*` (provider). Se o scanner passar a ignorar tokens terminados em `_` (P1-1), os padrões só precisam cobrir os nomes reais. |
| P2-2 | P2 | `config/flags.yaml:125,362` | A heurística "menor SPEC que cita" aponta para a spec de visão: `RPG_CARD_DECK` e `RPG_ENEMY_INTENT` estão com `SPEC-327`. As specs que criaram as flags são 328 (baralho) e 329 (presságio). | Corrigir para a spec que introduziu a leitura. Vale conferir as outras `release` do épico de cartas. |
| P2-3 | P2 | `config/flags.yaml:515,489` | Kinds discutíveis. `RPG_KILL_SWITCH_TTL_SECONDS` é ajuste de TTL (`ops`), não um desligamento. `RPG_JEV_ROUTER_PRIMARY_APPROVED` é aprovação permanente do dono (SPEC-217), mais `config`/`ops` que rollout com validade. `RPG_PROJECTION_MODE` (staging fica `inline` por limitação conhecida) também tende a `ops`. | Reclassificar ou justificar no `note`. |
| P2-4 | P2 | `scripts/flag_registry.py:42` | `git ls-files` sem `-z` cita caminhos não-ASCII (`core.quotePath`). Um arquivo assim viraria `OSError` e seria pulado em silêncio (`except OSError: continue`). Hoje nenhum arquivo rastreado tem aspas, então não há bug ativo. | Usar `git ls-files -z` e `split("\0")`. |
| P2-5 | P2 | `config/flags.yaml` (143/205 notes) | As notes são templates ("ajuste operacional (x y z)") e não dizem nada além do nome. | Follow-up: melhorar quando cada flag for tocada. Não bloqueia. |

Ponto 3 do coordenador (CI Linux): sem problema. O `checkout` traz `.git`, então `git ls-files`
funciona com profundidade 1. A leitura é UTF-8 com `errors=replace` e o `.gitattributes` força
LF. O teste sintético faz só `git init` e `git add`, sem commit, então não depende de
`user.name`. Ressalva de design, não defeito: em 2027-01-25 as 40 `release` vencem juntas e
derrubam a suíte default de todo PR. Isso é o pretendido pelo R6, mas vale um lembrete no
ESTADO perto de jan/2027 (`expiring --days 30`).

## Correções aplicadas

—

## Pendências

- P1-1 e P1-2 antes do pouso. P2-1 a P2-4 podem ir no mesmo ciclo (são baratos); P2-5 é follow-up.

## Comandos rodados

```text
git diff main...HEAD --stat → 6 arquivos, +1335/-8; nada em evals/
py.sh -m pytest -p no:cacheprovider tests/test_flag_registry.py → 10 passed
py.sh scripts/flag_registry.py check → exit 0
py.sh scripts/flag_registry.py expiring --days 120 → 40 linhas
script de análise (scratchpad): matches por padrão, contagem por kind (ops 80, config 54, release 40, dev 26, kill_switch 5), defaults com formato de nome de env (11)
```

## Re-check do coordenador (47d3fe63)

P1-1, P1-2 e P2-1..P2-4 corrigidos (scanner ignora token terminado em `_`; defaults conferidos por amostra contra o código: RPG_REPLAN_AFTER, RPG_EARLY_NARRATIVE, RPG_CARD_DECK, RPG_LLM_HEDGE_MS, RPG_TOKEN_STREAM). 12 testes do escopo verdes. Veredito final: APPROVED_WITH_FOLLOWUPS (notes genéricas; spec das release do épico de cartas por heurística).
