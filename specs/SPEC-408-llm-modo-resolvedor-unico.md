# SPEC-408 — llm-modo-resolvedor-unico

> **Status:** `approved` (11/11: aprovada pelo coordenador por delegação do dono, "as decisões deixo para vc"; decisões do §8 = recomendações; veto do dono segue possível) · antes `draft`
> **Criada:** 2026-11-11 · **Atualizada:** 2026-11-11
> **Depende de:** nenhuma (independente de SPEC-405/406/407)
> **Desbloqueia:** nada (follow-up de qualidade, SPEC-405..408)
> **Risco:** `médio` (seleção de LLM; não é combate/persistência/API pública, mas o valor aparece no log de boot e em `simulated`) → revisor Sonnet.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **REVIEW_MODEL:** Sonnet (`spec-reviewer` ou revisor Sonnet).
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum arquivo de `evals/` é tocado).
> **Evidência:** teste-tabela que falha antes (provider desconhecido: `llm_mode()` diz `legacy:x`, `get_llm()` devolve `FallbackLLM`); depois, as três funções derivam do mesmo resolvedor e o teste fica verde em toda linha. Testes de log existentes (`tests/test_llm_logging.py`) travam eventos e níveis.

---

## 1. Contexto & Objetivo

`llm_setup.py` decide "qual LLM estamos usando" em três lugares, reescritos à mão: `get_llm` (`llm_setup.py:1831-1860`, mais `_legacy_get_llm` `:1811-1828`), `is_simulated` (`:1863-1875`) e `llm_mode` (`:1878-1891`). As duas últimas "espelham a ordem de resolução" da primeira (docstrings `:1866`, `:1881`), sem nenhuma garantia de que continuem espelhando.

Tabela-verdade real hoje (lida no source em 11/11; `F`=`RPG_FORCE_MOCK`, `N`=`RPG_NO_MOCK`, `P`=`LLM_PROVIDER` já com `strip().lower()`, os três normalizam igual):

| Caso | `get_llm()` | `is_simulated()` | `llm_mode()` | Coerente? |
|---|---|---|---|---|
| `F` | MockLLM | True | `mock` | sim |
| `P=gemini`, sem `GOOGLE_API_KEY`, sem `N` | MockLLM (`:1818`) | True | `mock` | sim |
| idem com `N` | FallbackLLM (`:1817`) | False | `fallback` | sim |
| `P=gemini` com chave | RoutedLLM | False | `legacy:gemini` | sim |
| `P` ∈ {ollama, openai, openai_compat} (com ou sem a chave própria) | RoutedLLM (1 candidato) | False | `legacy:<p>` | sim (falta de chave só estoura no invoke) |
| **`P` desconhecido** (ex.: `foo`) | **FallbackLLM** (`:1825-1826`) | False | **`legacy:foo`** (`:1888`) | **NÃO: único desacordo de `llm_mode`** |
| sem `P`, sem nenhuma chave, sem `N` | MockLLM | True | `mock` | sim |
| idem com `N` | FallbackLLM | False | `fallback` | sim |
| sem `P`, com chave | RoutedLLM (rotas) | False | `routes` | sim |
| `RPG_ROUTES` custom | RoutedLLM com `_load_routes().get(tier, [])` | False | `routes` | sim (rotas não mudam o modo; tier ausente dá lista vazia, fora de escopo) |

Resultado: **1 divergência real** (provider desconhecido em `llm_mode`). `F`+`N` juntos, espaços e maiúsculas em `LLM_PROVIDER`, `gemini` com chave e legacy sem chave própria já concordam. Duas armadilhas que a derivação deve preservar, não mudar: `os.getenv("RPG_FORCE_MOCK")` é truthy para qualquer string não vazia, inclusive `"0"` (`:1841`, `:1868`, `:1882`), e `is_simulated()` é falso para `FallbackLLM` (a docstring diz "True quando `get_llm()` devolveria MockLLM").

Consumidores (grep `-w` no repo, 11/11):
- `llm_mode()`: **só** `observability/boot.py:72` → evento `runtime.boot`, campo `llm_mode` (allowlist em `observability/events.py:475`). Teste `tests/test_boot_log.py:37` fixa `"routes"`. Não está em `/health` nem em rota da API. A correção é observável **só** no log de boot (`legacy:foo` passa a `fallback`); ninguém compara a string em código.
- `is_simulated()`: `api_presenters.py:185` (campo `simulated` da resposta), `api.py:64` (re-export), `routes/turn.py:1124,1139` (label de métrica), `services/shared_pool.py:401-403`, `scripts/bestiario/eval_geracao.py:409,448`, `tests/test_audit_fixes.py:129-161`. **O valor não muda em nenhuma linha da tabela** (provider desconhecido já dá False).

Objetivo: um resolvedor puro único do qual as três derivam, para o desacordo não poder reaparecer. Sem mudar eventos, níveis de log, nem o caminho feliz com chave.

## 2. Requisitos

- **R1 — Resolvedor puro.** `resolve_mode()` devolve um `LlmMode` congelado (`NamedTuple`/`dataclass(frozen=True)`) com `kind` ∈ {`mock`, `fallback`, `legacy`, `routes`}, `provider: str` (normalizado; `""` fora de `legacy`) e `reason: str`. Só lê `os.environ`; não instancia LLM, não loga, não toca `_ANNOUNCED`. Ordem idêntica à de hoje: `RPG_FORCE_MOCK` → `LLM_PROVIDER` → sem chave → rotas.
- **R2 — Razões = as já anunciadas.** `reason` ∈ {`force_mock`, `legacy_gemini_no_key`, `unknown_provider`, `no_keys`, `""` (legacy/routes)}; são exatamente os `reason` de hoje em `_announce_once` (`:1816`, `:1818`, `:1825`, `:1842`, `:1853`, `:1855`).
- **R3 — `get_llm` deriva e instancia.** `get_llm` chama `resolve_mode()` e faz só: `mock` → `_announce_once("mock_selected", reason, level=_mock_level())` + `MockLLM(temperature)`; `fallback` → `_announce_once("fallback_llm_selected", reason, level="error")` + `FallbackLLM` com a **mesma mensagem** de hoje por razão (`"GOOGLE_API_KEY não configurada"`, `"Provider desconhecido: 'foo'"`, `"Nenhuma key de provider configurada"`); `legacy` → `RoutedLLM(tier, temperature, [(provider, _legacy_model(provider, tier))])`; `routes` → `RoutedLLM(tier, temperature, _load_routes().get(tier, []))`. `_legacy_model`, `_load_routes`, `ROUTES` e `RoutedLLM` não mudam.
- **R4 — Provider desconhecido.** Provider fora do conjunto aceito por `_legacy_model` (`gemini`, `ollama`, `openai`, `openai_compat`) resolve `kind="fallback"`, `reason="unknown_provider"`. O resolvedor recebe esse predicado de fora (`_legacy_model(p, ModelTier.FAST) is not None`) ou usa constante única derivada; **não** duplica a lista à mão em dois lugares sem teste de paridade (R9).
- **R5 — `llm_mode()` deriva.** Retorna `"mock"`, `"fallback"`, `f"legacy:{provider[:24]}"` ou `"routes"` a partir de `resolve_mode()`. Formato das strings inalterado (o corte em 24 caracteres fica).
- **R6 — `is_simulated()` deriva.** `resolve_mode().kind == "mock"`. Valores idênticos aos de hoje em toda linha da tabela do §1.
- **R7 — Coerência por teste-tabela.** Novo teste parametrizado (§4 Etapa 1) afirma, em toda combinação, que `llm_mode()`, `is_simulated()` e o tipo de `get_llm()` concordam: `mock` ⇔ `MockLLM` ⇔ `simulated True`; `fallback` ⇔ `FallbackLLM`; `legacy:*`/`routes` ⇔ `RoutedLLM`.
- **R8 — Eventos e níveis travados.** Antes de refatorar, teste de caracterização (ou os de `tests/test_llm_logging.py:119-142` estendidos) cobre: `llm.mock_selected` com reason `force_mock`, `legacy_gemini_no_key`, `no_keys` (nível `warning` no perfil `legacy`, `error` fora dele, `_mock_level` `:259`); `llm.fallback_llm_selected` com `legacy_gemini_no_key`, `unknown_provider`, `no_keys` (nível `error`); uma vez por processo e motivo.
- **R9 — Tamanho.** `llm_setup.py` (1896 linhas, acima de 1.000) **não cresce**: saldo de linhas `git diff --stat` ≤ 0 (`tests/test_size_budget.py` verde). Função nova ≤ 60 linhas. Se houver módulo novo, teste de paridade entre o predicado de provider conhecido e `_legacy_model` (todo nome de `PROVIDER_KEY_ENV` mais `ollama` é conhecido ou não, igual nos dois).
- **R10 — Contrato de log.** O valor de `llm_mode` em `runtime.boot` muda só para provider desconhecido (`legacy:<x>` → `fallback`). `tests/test_boot_log.py` segue verde; allowlist de `events.py` intacta.

### Fora de escopo (com motivo)

- Unificar a leitura de `LLM_TIMEOUT_SECONDS`, mexer em `_legacy_model`/dicts por tier, `ROUTES`, `_load_routes`, streaming ou qualquer outra parte de `llm_setup.py` (a revisão independente de 11/11 descartou esses).
- Mudar a semântica de `RPG_FORCE_MOCK="0"` ser truthy (comportamento atual, preservado; mudar seria outra spec).
- Fazer `is_simulated()` verdadeiro para `FallbackLLM`: mudaria o campo `simulated` da API.
- Tier ausente em `RPG_ROUTES` custom gerar `RoutedLLM` com lista vazia.
- Expor `llm_mode` em `/health` ou rota nova.

## 3. Design técnico

- **Onde mora o resolvedor (decisão do executor, com preferência).** Preferência: módulo novo `services/llm_mode.py`, **sem importar `llm_setup`** (evita ciclo; `llm_setup` já importa `observability.telemetry` de forma lazy). Recebe por parâmetro o que hoje vem de `llm_setup`: `resolve_mode(key_envs: Iterable[str], is_known_provider: Callable[[str], bool]) -> LlmMode`. Em `llm_setup.py`, três wrappers finos passam `set(PROVIDER_KEY_ENV.values())` e `lambda p: _legacy_model(p, ModelTier.FAST) is not None`. Justificativa: três funções somem de 1896 linhas e o resolvedor vive em arquivo pequeno; saldo de `llm_setup.py` fica negativo. Alternativa aceita só se medir saldo ≤ 0: `_resolve_mode()` dentro de `llm_setup.py` (menos um arquivo, sem parâmetros). O executor mede e registra a escolha no hand-back.
- **Arquivos novos:** `services/llm_mode.py` (`LlmMode`, `resolve_mode`); teste novo (abaixo).
- **Arquivos alterados:** `llm_setup.py` (`get_llm`, `_legacy_get_llm` absorvido ou reduzido, `is_simulated`, `llm_mode`); `tests/test_llm_logging.py` (R8, só acrescenta casos).
- **Assinaturas públicas inalteradas:** `get_llm(temperature=0.1, tier=ModelTier.FAST)`, `is_simulated() -> bool`, `llm_mode() -> str`.
- **Teste-tabela:** em `tests/test_routing.py` (já trata `RPG_FORCE_MOCK` em `:101` e `:669`) ou arquivo novo `tests/test_llm_mode.py`; preferência: `tests/test_llm_mode.py` (assunto próprio; `test_audit_fixes.py` já tem os `test_is_simulated_*` e fica como está). Isolamento: helper local igual a `_limpa_env_llm` (`tests/test_audit_fixes.py:122-126`) removendo `RPG_FORCE_MOCK`, `RPG_NO_MOCK`, `LLM_PROVIDER`, `RPG_ROUTES` e todas as variáveis de `PROVIDER_KEY_ENV.values()` (as que `_any_key_available` consulta, `llm_setup.py:1756-1757`: `GOOGLE_API_KEY`, `GROQ_API_KEY`, `QWEN_API_KEY`, `GLM_API_KEY`, `MINIMAX_API_KEY`, `KIMI_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), via `monkeypatch.delenv(..., raising=False)`. O `conftest.py:10` usa `os.environ.setdefault("RPG_FORCE_MOCK","1")`; o `monkeypatch.delenv` o retira só dentro do teste e o restaura ao fim. Não instancia provider real: com chave fake (`"fake"`), `get_llm` devolve `RoutedLLM`, que só constrói o cliente ao invocar (conferir; se o construtor do `RoutedLLM` instanciar cliente, o teste apenas checa `type(llm).__name__`/`isinstance` e nunca chama `invoke`). Também zera `llm_setup._ANNOUNCED` por teste para não vazar entre casos.
- **Matriz do teste:** `F` ∈ {ausente, `1`} × `N` ∈ {ausente, `1`} × `P` ∈ {ausente, `gemini`, ` Gemini ` (espaços/maiúsculas), `ollama`, `foo`} × chave ∈ {nenhuma, só `GOOGLE_API_KEY`, só `GROQ_API_KEY`}. Para cada linha: três afirmações do R7 mais, para o caso `P=foo`, `llm_mode()=="fallback"`. Hoje falha em `P=foo` (e só nele).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos
1. `tests/test_llm_mode.py`: teste-tabela do §3 (R7). Falha hoje em toda linha `P=foo` (`llm_mode` devolve `legacy:foo`).
2. Estender `tests/test_llm_logging.py` com os casos de R8 que faltam (`legacy_gemini_no_key` mock e fallback; `unknown_provider`). Estes passam com o código atual (caracterização) e **precisam continuar passando** depois.
3. Verificação: `bash scripts/dev/pt.sh tests/test_llm_mode.py tests/test_llm_logging.py` → só as linhas `P=foo` do R7 vermelhas.

### Etapa 2 — Resolvedor
1. Criar `services/llm_mode.py` (ou `_resolve_mode` no `llm_setup.py`, conforme a medição) com `LlmMode` e `resolve_mode`. Teste unitário puro do resolvedor (sem `llm_setup`) no mesmo `tests/test_llm_mode.py`: `kind`/`provider`/`reason` por linha.
2. Verificação: testes do resolvedor verdes.

### Etapa 3 — Derivar as três
1. `get_llm` com `match`/`if` sobre `kind` (R3); remover `_legacy_get_llm` ou reduzi-lo a nada; `is_simulated` e `llm_mode` viram uma linha cada (R5, R6). Docstrings: apontar para o resolvedor, tirar "espelha".
2. Verificação: `bash scripts/dev/pt.sh tests/test_llm_mode.py tests/test_llm_logging.py tests/test_audit_fixes.py tests/test_boot_log.py tests/test_routing.py tests/test_day_digest_inline.py` verde.

### Etapa 4 — Limpeza
1. Imports órfãos, `ruff format`/`ruff check`, `git diff --stat llm_setup.py` (saldo ≤ 0, R9), `bash scripts/dev/py.sh -m pytest tests/test_size_budget.py -q`, `scripts/dev/dup_helpers.py --diff main...HEAD` (sem helper novo).
2. Registrar no hand-back a escolha de lugar do resolvedor e o saldo de linhas.

## 5. Critérios de aceite

- [ ] `tests/test_llm_mode.py` falhou antes da Etapa 3 (linhas `P=foo`) e passa depois, em toda a matriz.
- [ ] `llm_mode()` com `LLM_PROVIDER=foo` devolve `fallback`; demais strings iguais às de hoje (`mock`, `routes`, `legacy:<p>`, `fallback`).
- [ ] `is_simulated()` com valores idênticos em toda linha (os `test_is_simulated_*` de `tests/test_audit_fixes.py` seguem verdes sem edição).
- [ ] Eventos `llm.mock_selected` / `llm.fallback_llm_selected`: mesmos `reason`, mesmos níveis, 1× por processo e motivo (R8).
- [ ] `get_llm`, `is_simulated`, `llm_mode` não leem env fora do resolvedor, exceto o que `_legacy_model`/`_load_routes` já leem.
- [ ] `git diff --stat llm_setup.py`: saldo ≤ 0; `tests/test_size_budget.py`, `ruff format --check`, `ruff check` verdes.
- [ ] `tests/test_boot_log.py` verde (`"routes"` mantido).
- [ ] Revisão Sonnet APPROVED.
- [ ] `uv run pytest` verde (suíte completa offline, 1× pelo coordenador no pouso).

## 6. Smoke test com LLM real

Não necessário. A mudança é só de seleção: nenhum prompt, `with_structured_output`, roteamento por tier, mapeamento de campo ou caminho `RoutedLLM` com chave muda (o ramo `routes`/`legacy` continua montando o mesmo `RoutedLLM` com os mesmos candidatos). O teste-tabela cobre o tipo devolvido em toda combinação de env, e o MockLLM não esconde nada aqui porque o risco é de decisão de ramo, não de campo. Verificação offline equivalente: `bash scripts/smoke_api.sh` (modo simulado, confere `simulated`).

## 7. Riscos & compatibilidade

- **Observável:** só o campo `llm_mode` do log `runtime.boot` para provider desconhecido (`legacy:foo` → `fallback`), que é a correção pretendida. Nenhum dashboard/alerta no repo compara a string (grep: só `observability/boot.py`, `events.py` allowlist e `tests/test_boot_log.py`); alertas externos (Axiom, ainda não ligado) não existem.
- **Predicado de provider conhecido:** se o resolvedor duplicar a lista de `_legacy_model`, os dois podem divergir de novo; por isso o predicado é injetado (ou há teste de paridade, R9).
- **Ciclo de import:** `services/llm_mode.py` não importa `llm_setup`; só `os` e `typing`.
- **Eventos:** `_announce_once` continua sendo chamado só por `get_llm`; `is_simulated`/`llm_mode` seguem sem efeito colateral (chamados em rota quente `routes/turn.py:1124`).
- Saves, persistência, quota, latência: sem impacto. MockLLM/FallbackLLM: mesma escolha em toda linha.

## 8. Decisões do dono

- **D1** — Aceitar que `llm_mode` de provider desconhecido passe a ser `fallback` no log de boot (mudança observável mínima, só log)? Proposta: sim.
- **D2** — Resolvedor em módulo próprio `services/llm_mode.py` (preferência, saldo de `llm_setup.py` negativo e sem ciclo) ou dentro de `llm_setup.py` se o saldo medido for ≤ 0? Proposta: módulo próprio, executor mede e justifica.
- **D3** — Manter `is_simulated()` falso para `FallbackLLM` e `RPG_FORCE_MOCK="0"` truthy (preservados, fora de escopo)? Proposta: sim.
