# SPEC-408 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet 5.5 (revisor independente) · **Data:** 2026-11-11 · **Commit revisado:** `f008ba68` (testes `83a41b1b`)

## Escopo

`git diff main...HEAD`: `llm_setup.py`, `services/llm_mode.py`, `tests/test_llm_mode.py`, `tests/test_llm_logging.py`, `tests/size_budget.json`, spec. Sem tocar em `evals/`.

## Equivalência (tabela-verdade, código antigo vs novo)

- `get_llm`: ordem FORCE_MOCK > LLM_PROVIDER (strip/lower) > sem chave > rotas preservada. Gemini sem chave: mock/fallback conforme RPG_NO_MOCK; provider sem modelo: `FallbackLLM("Provider desconhecido: 'foo'")`; legacy: `RoutedLLM(tier, temperature, [(p, modelo do tier)])`; sem chave: mensagens idênticas; rotas: `_load_routes().get(tier, [])`. `tier`/`temperature` repassados.
- `_any_key_available` == `any(getenv(e) for e in set(PROVIDER_KEY_ENV.values()))`: o resolvedor recebe o mesmo conjunto.
- Desconhecido testado com `ModelTier.FAST`; `_legacy_model` devolve None por provider e não por tier, então equivale ao teste antigo por tier.
- `is_simulated`: antigo (FORCE_MOCK → True; NO_MOCK → False; provider → gemini sem chave; senão sem chave) == `kind == "mock"` em todas as combinações (gemini sem chave + NO_MOCK → fallback → False; provider desconhecido → fallback → False).
- `llm_mode`: única diferença é `legacy:<x>` → `fallback` para provider desconhecido (D1). Nenhuma outra diferença encontrada.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `llm_setup.py` get_llm (~linha 1838) | `get_llm` relê `LLM_PROVIDER` só para a mensagem "Provider desconhecido". Duplica a normalização do resolvedor e pode divergir dele (leitura dupla de env). | Preencher `provider` em `LlmMode("fallback", provider, "unknown_provider")` e usar `m.provider` na mensagem (recomendado, 2 linhas; `llm_mode()` só usa provider quando `kind == "legacy"`, então sem efeito observável). Atualizar a linha do `test_resolve_mode` e o comentário do campo. Não bloqueia: aceitável como está. |
| P3-1 | P3 | `tests/test_llm_mode.py:_expected` | Oráculo cobre `ollama`, mas `openai`/`openai_compat` só entram no teste de paridade do predicado. | Opcional: incluir `openai` na lista `_PROVIDERS`. |

Sem achados P0/P1.

## Verificações

- Efeitos colaterais: `_announce_once` só é chamado em `get_llm`, com mesmos eventos/razões/níveis; `is_simulated`/`llm_mode` não logam nem instanciam. Os 5 testes novos de `test_llm_logging.py` foram executados contra `main:llm_setup.py` (cópia via `git archive` fora do repo, já removida): 5 passed, logo travam o comportamento pré-existente.
- `services/llm_mode.py`: função de 17 linhas, type hints, só lê `os.getenv` (no resolvedor), sem import de `llm_setup` (sem ciclo), sem log/instância.
- `tests/test_llm_mode.py`: oráculo independente (reimplementado por regra, não chama o resolvedor); isola env (RPG_FORCE_MOCK, RPG_NO_MOCK, LLM_PROVIDER, RPG_ROUTES e todas as chaves limpos por teste); sem rede/provider real (RoutedLLM só é construído); matriz 2×2×5×3 inclui `" Gemini "`.
- Consumidores: `observability/boot.py` envia `llm_mode` como string livre (`events.py:475` só lista o campo); nenhum código de produção compara `legacy:`; `fallback` já era valor documentado.
- Size budget: `size_budget.py` rc 0; `llm_setup.py` 1862 no JSON (catraca apertada). Fim de linha: `.gitattributes` `* text=auto eol=lf`, `autocrlf=false`; numstat +30/−64 coerente, sem mudança em massa (o aviso do git é só normalização de CRLF do working tree).
- ruff check/format limpos; `dup_helpers.py`: nenhuma duplicata.

## Pendências

P2-1 e P3-1 (opcionais, podem entrar no mesmo pouso ou virar nada).

## Comandos rodados

```text
pt.sh test_llm_mode test_llm_logging test_routing test_boot_log test_audit_fixes test_size_budget → 150 passed, 1 skipped, rc=0
pytest tests/test_llm_logging.py -k spec408 contra main (git archive, fora do repo) → 5 passed
size_budget.py → rc 0 · ruff check/format → limpo · dup_helpers --diff → nenhuma duplicata
```
