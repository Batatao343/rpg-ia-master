# SPEC-378 — Refatoração: helpers comuns (fold, leitor de flag, structured output, telemetria do LLM, memória do RAG, perfil runtime)

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de código de 03/11 ([docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md](../docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md)): §3 R6; §4.1 itens 3, 5 e 7; §4.2 itens 3 e 6; §4.3 itens 2 a 4; regras da onda §6 (W1–W8). Letra **D** do §6.1.
> **Depende de:** SPEC-376 e SPEC-377 pousadas (W6: uma spec de refatoração em voo por vez; a 377 mexe em `services/law.py`, `faction_gate.py` e `faction_display.py`, que têm cópias de `_fold`). Por etapa: `agents/loot.py` espera a SPEC-367; `persistence.py`, `services/card_piles.py` e `services/card_effects.py` esperam a SPEC-368; `agents/combat.py`, `services/enemy_*.py` e `playtest/*` esperam a SPEC-371 (W1).
> **Desbloqueia:** SPEC-381 (`api.py` em routers pode usar `is_database_profile()`); SPEC-382 (nós grandes extraídos com o guard de structured output já num helper).
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez, um commit por mudança mecânica (W4) · **REVIEW_MODEL:** `Sol` (Opus): estado, telemetria do roteador, guard de FallbackLLM · **REVIEW_REQUIRED:** `true` (W7; o revisor roda o W2 de novo em pelo menos 1 etapa)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected, dataset, baseline ou exclusão muda. `evals/**` fica fora do escopo inteiro (W5), inclusive as cópias de fold que moram lá.

Rótulos: **[F]** fato no source da `main` em `5fd2e920` (arquivo:linha) · **[H]** hipótese que a Etapa 0 confirma ou derruba · **[D]** decisão do dono (§8, com recomendação).

---

## 1. Contexto & Objetivo

A auditoria de 03/11 achou o mesmo trecho pequeno copiado dezenas de vezes: tirar acento e
caixa (`_fold`), ler flag `off|shadow|on`, proteger `with_structured_output(...).invoke()`
contra o `AIMessage` do FallbackLLM, montar `LLMAttemptEvent` no roteador, gravar memória
de sessão ou de NPC no RAG e perguntar se o perfil runtime tem banco. Cada cópia é um lugar a
mais para divergir. Nas cópias de `_fold` isso já aconteceu: elas **não são iguais** (R6
da auditoria), e a mesma entidade pode casar num módulo e falhar em outro.

Esta spec é **refatoração pura**. Ela junta só as cópias que se provam equivalentes, com um
oráculo gravado antes da troca, e deixa as divergentes onde estão, listadas. Unificar a
semântica das divergentes mudaria comportamento: isso fica fora, porque ids derivados por
fold podem estar em saves e no pool compartilhado (`shared_pool_models.fold_name`), e o
lugar de mudança intencional é uma spec como a SPEC-377.

O dono pediu muito cuidado para não quebrar nada, e há sessões em paralelo (367, 368, 371).
Por isso cada etapa lista seus arquivos, roda a trava W1 antes de começar e, se travar,
espera sem bloquear as outras.

## 2. Requisitos

### Regras gerais (valem para todas as etapas)

- **R1** — Cada etapa é refatoração pura: roda o oráculo **W2** completo antes e depois (suíte
  completa pelo coordenador no pouso; `python -m evals run` nas 12 suítes do `eval-gates.yml`
  com `--seed 7` e `evals compare` **sem diferença**; `python -m playtest run --all --turns 10
  --seed 0` com a mesma contagem de violações por perfil e o mesmo desfecho).
- **R2** — **W3:** nenhuma asserção de teste existente muda. Só podem mudar alvos de
  `monkeypatch`/import. Se um teste existente precisar de asserção nova, a etapa para, é
  registrada no §9 e reportada. Testes **novos** desta spec (oráculos, goldens) são acréscimos
  e não contam como mudança de asserção.
- **R3** — **W1** antes de cada etapa: a lista de arquivos da etapa (§3.7) não pode cruzar com
  arquivos de nenhuma branch aberta. Se cruzar, só o sub-item afetado espera; o resto segue.
- **R4** — **W4:** um commit por mudança mecânica, revertível sozinho. Nas Etapas 1 e 3, um
  commit por módulo ou por site migrado.
- **R5** — Nenhum nome público ou privado que hoje é importado ou alvo de `monkeypatch` some.
  Ele vira um wrapper fino ou um alias (`_fold = fold`). Exemplos [F]: `card_effects._fold` é
  importado por `card_lint`, `card_shop` e `card_rewards` (`services/card_rewards.py:68-71`);
  `shared_pool_models.fold_name` por `shared_pool*.py` e `creature_*`; `api._database_profile`
  é alvo de `monkeypatch` em 22 arquivos de teste.
- **R6** — O catálogo de eventos de log fica **byte-igual**: `observability/events.py` e
  `docs/operacao/EVENTOS_DE_LOG.md` regenerados por `scripts/gen_event_catalog.py` não mudam
  (`tests/test_log_event_registry.py` verde). Um helper que passe a emitir um evento que
  antes era literal no site precisa de entrada em `WRAPPERS`/`MANUAL` do gerador, com os mesmos
  nomes e campos. Nenhum evento novo, nenhum renomeado.
- **R7** — Helpers novos são stdlib-only e importáveis sem efeito colateral (não importam
  `infrastructure`, que puxa `infrastructure/runtime.py` e os adapters no topo;
  `infrastructure/__init__.py:3-9`). `rag.py`/`persistence.py` importam o runtime de forma
  lazy de propósito (`rag.py:1002`, `persistence.py:389`), por causa do cold start.
- **R8** — Saves e ids persistidos não mudam: nenhuma string que vira id, chave de save,
  `document_id` ou nome no pool compartilhado muda para nenhuma entrada do corpus.

### E1 — `fold` (tirar acento e caixa)

- **R9** — A Etapa 0 entrega uma tabela de **todas** as funções de fold e slug em código de
  produto, com a semântica exata de cada uma: forma Unicode (NFKD/NFD/NFKC), como tira o acento
  (`combining`/`category=="Mn"`/`encode("ascii","ignore")`), caixa (`lower`/`casefold`) e
  ordem (antes ou depois de normalizar), `strip`, colapso de espaço, troca por `_`/`-`,
  tratamento de `None`/falsy (`str(x or "")` vs `str(x)`).
- **R10** — Novo `services/text.py` com `fold(text, *, case="casefold", strip=False,
  collapse=False) -> str` (§3.1). Uma só função. As variantes `ascii-ignore` e as de slug
  **não** entram ([D] D2).
- **R11** — Uma cópia só migra se um teste de propriedade provar `old(x) == fold(x, **opts)`
  para todo `x` do corpus (§3.1), com `old` copiado **verbatim** para o teste antes de apagar a
  original. Cópia que falha em uma entrada que seja fica, e entra na lista de divergentes da §9.
- **R12** — Ficam fora, sem discussão: `playtest/opening_checks.py:53` (oráculo congelado da
  SPEC-348/366), `evals/**` (W5), `project_index/query.py` (gerado), `tests/**` e
  `scripts/**` (não são produto; [D] D2 se o dono quiser incluir `scripts/`).

### E2 — leitor de flag por escolha

- **R13** — Novo `env_choice(name, choices, default) -> str` em `services/env.py`, que reproduz
  `raw = os.getenv(name, default).strip().lower(); return raw if raw in choices else default`.
  Ele **não** lê `config/flags.yaml` (ler o registro em runtime acopla o boot ao YAML; a
  auditoria §4.3 item 3 propunha isso, e a proposta foi rejeitada).
- **R14** — Dependências encadeadas (`requires`) continuam explícitas no chamador. Exemplos [F]:
  `lore_quests.mode` exige `world_quests.mode()=="on"` (`services/lore_quests.py:53-59`);
  `npc_world.mode`/`rumors.mode` exigem `world_engine.mode()=="on"`
  (`services/npc_world.py:45-53`, `services/rumors.py:35-43`). As funções `mode()`/`enabled()`
  continuam existindo com o mesmo nome e retorno.
- **R15** — Prova por golden parametrizado: para cada leitor migrado × valores {ausente, `""`,
  `"ON"`, `" shadow "`, `"off"`, `"on"`, `"lixo"`, `"\ton\n"`} e, quando houver `requires`, ×
  estado da dependência, o retorno gravado com a função antiga antes da troca é igual ao de
  depois.
- **R16** — Leitores de outra forma ficam como estão: booleanos `in {"1","true","yes"}`
  (`api.py:2864`, `services/shared_pool.py:97`, `services/latency_flags.py:45`), `!= "off"`
  (`rag.py:752`, `services/file_cache.py:22`, `services/companion_soul.py:79`), `== "on"`
  (`agents/router.py:598`, `services/prompt_layout.py:28`, `services/creature_art.py:72`) e o
  perfil runtime (E6).

### E3 — `invoke_structured`

- **R17** — Novo `invoke_structured(llm, schema, messages, *, node=None, event="failed",
  level="warning") -> schema | None` em `llm_setup.py` (§3.3). Contrato: instância de `schema`
  → devolve a instância; qualquer outra coisa (inclusive o `AIMessage` do FallbackLLM e o
  `AIMessage(content="")` de cadeia esgotada, `llm_setup.py:1187`) → `None`; exceção em
  `with_structured_output` ou em `invoke` → `None` e, se `node` foi passado,
  `_log_event(node, event, level=level, error=type(e).__name__)`. Sem `node`, não loga.
- **R18** — Cada site mantém o próprio fallback. Só migra o site cujo comportamento cabe
  **exatamente** no contrato: o mesmo fallback para exceção e para não-instância, e um log que
  bate com o do helper em área, evento, nível e campos (ou nenhum log). Site que distingue os
  dois casos fica. Exemplos [F]: o router marca `invoke_exception` vs `not_router_decision`
  (`agents/router.py:689-710`); o archivist loga `structured_output_unexpected` com
  `result_type` (`agents/archivist.py:1023-1031`); `world_simulator` usa `log_fallback` com
  códigos distintos (`agents/world_simulator.py:141-149`).
- **R19** — `agents/librarian.py:89-91` faz o teste **invertido** (`not isinstance(result,
  BaseMessage)`), que aceita qualquer não-mensagem. Um teste de caracterização fixa o
  comportamento atual (dict, `SimpleNamespace`, instância, `AIMessage`, exceção). O site só migra
  se a caracterização provar que nada muda; o default é ficar ([D] D3).
- **R20** — Um site por commit. Sites em `agents/combat.py` esperam a SPEC-371 e o de
  `agents/loot.py` espera a SPEC-367 (W1).
- **R21** — Se a Etapa 0 achar menos de 5 sites aptos, a E3 é cancelada: o helper não é criado
  (YAGNI) e o resultado fica registrado no §9 ([D] D3).

### E4 — telemetria e preparação de candidato no `RoutedLLM`

- **R22** — As 19 montagens manuais de `LLMAttemptEvent(...)` (`llm_setup.py:1030-1713`) passam
  por um construtor privado `_attempt(...)`, e a preparação de candidato (kill switch, circuito,
  `_cached_for_tier`, `_apply`) duplicada em `invoke` (`:1018-1088`), `stream` (`:1203-1249`) e
  `_stream_attempt` (`:1426` em diante) passa por `_prepare_candidate(...)`.
- **R23** — Golden de telemetria: para cada desfecho (sucesso; `invalid_structured` com retry
  semântico; `invoke_error` 429; 400 `tool_use_failed` com 1 regeneração; timeout; `build_error`;
  erro em `_apply`; `kill_switch`; `circuit_open`; cadeia esgotada; `stream` ok; `stream` com
  erro antes do 1º token; `stream_structured`), a lista de `LLMAttemptEvent` emitida
  (`set_llm_attempt_telemetry_hook`), as chamadas do hook legado (`set_llm_telemetry_hook`), os
  eventos de log e o valor devolvido são **idênticos** antes e depois. O `latency_ms` é
  estabilizado com `time.perf_counter` fixo no teste.
- **R24** — A semântica de `attempt_index` não muda: em `invoke` ela é um contador que avança
  a cada tentativa (`:1016`, `:1042`); em `stream` é o índice do candidato (`:1203-1207`). O
  `_prepare_candidate` recebe o índice de fora e não o recalcula.
- **R25** — Os helpers leem por global de módulo, na hora da chamada, tudo o que a suíte
  substitui: `_get_cached_client`, `_build_client`, `_kill_switch_disabled`,
  `_ATTEMPT_TELEMETRY_HOOK`, `STRUCTURED_SEMANTIC_MAX_ATTEMPTS`, `_log_hedge`, `_ANNOUNCED`,
  `_OPEN_CIRCUITS` (49 `setattr(llm_setup, ...)` em 22 arquivos de teste [F]). Nada capturado
  em default de argumento ou closure no import.

### E5 — memória de sessão e de NPC no `rag.py`

- **R26** — `add_memory_to_session` (`rag.py:1352-1498`) e `add_npc_memory` (`rag.py:1511-1658`)
  delegam a um `_add_memory(scope, game_id, npc_id, texts, *, metadatas)` privado;
  `query_session_by_vector` (`rag.py:1135-1166`) e `query_npc_by_vector` (`rag.py:1169-1201`)
  delegam a `_query_by_vector(scope, vector, game_id, npc_id, *, k)`. As 4 funções públicas
  ficam com a mesma assinatura, o mesmo default de `k` (6 e 3) e a mesma docstring.
- **R27** — As diferenças reais entre as cópias são preservadas, uma a uma [F]: o nome da
  operação (`"add_session_memory"`/`"add_npc_memory"`); a validação de entrada (`npc_id`
  obrigatório só no NPC; `npc_id=str(npc_id) if npc_id else None` no resultado inválido); o
  **digest** do `document_id` (`f"{game_id}:{text}:{metadata}"` vs
  `f"{game_id}:{npc_id}:{text}:{metadata}"`; muda o id no Postgres, então é R8); o prefixo
  (`session:`/`npc:`); `npc_id` no `MemoryWriteIntent` e no `MemoryQuery` só no NPC; o
  `makedirs` (`SAVES_DIR` vs `dirname(npc_path)`); o `source` da evidência e o
  `_note_degraded` (`"session"`/`"npc"`); e os eventos literais `rag.session_memory_saved`,
  `rag.session_memory_failed`, `rag.npc_memory_saved` e `rag.npc_memory_failed` (R6).
- **R28** — Golden por ramo × escopo: entrada inválida; perfil com banco ok; perfil com banco e
  exceção; índice existente; embeddings indisponíveis (índice existente e novo); índice novo;
  exceção no FAISS. Grava o retorno, os argumentos de `_rag_operation_result`, os
  `MemoryWriteIntent`/`MemoryQuery` montados (com `document_id`), os diretórios criados e os
  eventos de log. Antes e depois, idênticos.

### E6 — perfil runtime com banco

- **R29** — Novo `is_database_profile() -> bool` em `services/env.py`, que reproduz
  **exatamente** `os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"`,
  inclusive `""` → `True` (§7, risco E6-a).
- **R30** — Migram só os sites com essa expressão literal ou a negação exata (`== "legacy"` →
  `not is_database_profile()`). Sites que fazem `... or "legacy"` (`""` → legacy) ficam e entram
  na lista de divergentes: `llm_setup.py:250,259` e `services/shared_pool.py:134`. Sites que
  usam o nome do perfil, e não um booleano, também ficam: `api.py:3494`,
  `services/kill_switches.py:116`, `services/google_play_fake.py:22`,
  `services/cron_internal.py:211`, `observability/boot.py` e `infrastructure/runtime.py`.
- **R31** — `api._database_profile` (`api.py:308-309`) não muda nesta spec ([D] D5); ele fica para
  a SPEC-381.

### Fora de escopo

- `_load_or_404` e qualquer outra mudança em `api.py` (SPEC-381), inclusive `_database_profile` (D5).
- Migrar leitores de JSON para `services/file_cache.py` (§6.4: 19 seams `reload()`/`cache_clear`;
  a semântica de mtime não é a do `lru_cache`).
- Tabela única de campos em `persistence.py` (§6.4).
- Subir os imports locais de `api.py` (§6.4; R8 da auditoria).
- Trocar FAISS/JSON por um adapter de `runtime.memory_store` (projeto maior, exige spec).
- Unificar a semântica das cópias divergentes de fold, de flag ou de perfil: isso **muda
  comportamento** e vai para uma spec própria (follow-up no §9).
- `flags.mode(..., requires=...)` lendo `config/flags.yaml` (rejeitado; R13).
- Podar ramos `shadow`/`off` de flags `release` (§4.3 item 1; SPEC-384, decisão do dono).
  **Cruzamento com a SPEC-384 D1:** a E2 não migra o `mode()` de flag que a 384 vai aposentar
  (lista na 384 D1). Se a 384 D1 já tiver sido decidida, a E2 roda **depois** dela; senão, essas
  flags ficam fora da E2 e são listadas no handoff.
- Cópias de fold em `evals/**`, `tests/**`, `playtest/opening_checks.py` e `project_index/`.
- `_last_human_text` ×3, `_pool_enabled` ×2, `_infer_tier_from_name` e fallbacks `try/except
  ImportError` (§4.2 item 6): pequenos e com chamadores em arquivos travados; podem entrar numa
  spec de acabamento.
- `services/narrative_sink.narrate_structured` (`services/narrative_sink.py:321-343`): já é um
  helper com streaming e devolve `AIMessage` por contrato; não vira `invoke_structured`.

## 3. Design técnico

### 3.1 `services/text.py` (E1)

```python
import unicodedata
from typing import Literal

def fold(
    text: object,
    *,
    case: Literal["casefold", "lower"] = "casefold",
    strip: bool = False,
    collapse: bool = False,
) -> str:
    """NFKD, sem marcas combinantes, caixa dobrada. `collapse` = " ".join(s.split())."""
```

Ordem fixa: `str(text or "")` → NFKD → remove `unicodedata.combining` → `lower`/`casefold` →
`strip` → `collapse`. Cópia com outra ordem (caixa antes de NFKD, `strip` antes) só migra se o
teste de propriedade provar que a ordem não importa no corpus.

**Corpus do teste de propriedade** (`tests/test_spec378_text_fold.py`, determinístico, sem
dependência nova, porque `hypothesis` não está no `pyproject.toml` [F]):
1. todas as strings de `data/**/*.json` e `data/**/*.yaml` (valores e chaves; dedup; corte em 300
   caracteres);
2. um conjunto adversarial fixo: `"Pântano"`, `"ÁGUA  Viva "`, `" nbsp "`,
   `" em-space"`, `"ß"`, `"ẞ"`, `"ς"`, `"ﬁ"`, `"İstanbul"`, `"¨"`, `"´"`, `"Ⅻ"`, `"①"`,
   `"™"`, `"—"`, `"🐺"`, `"é"` (decomposto), `"́"` solto, `"a_b-c"`, `"\t\n"`, `""`;
3. 2.000 strings geradas com `random.Random(378)` de um alfabeto com letras acentuadas pt-BR,
   maiúsculas, espaços variados, `_`, `-` e os itens do item 2;
4. não-strings: `None`, `0`, `False`, `[]`, `123`.

O item 4 é o que separa `str(x or "")` de `str(x)`. `mock_llm.py:846-848` usa `str(s)` [F], então
`None` vira `"none"` nele: ou fica, ou migra com um wrapper que preserve isso.

**Tabela de partida da Etapa 0** (funções de fold em código de produto, grep
`unicodedata.normalize` excluindo `tests/`, `evals/`, `docs/`, `specs/`, `project_index/`;
[F] para a linha, [H] para a classe até o teste de propriedade rodar):

| Classe | Semântica | Sites [F] | Opção de `fold` | Trava W1 |
|---|---|---|---|---|
| A | NFKD/NFD + combining + `lower`, sem strip | `party.py:94`, `world_utils.py:81`, `services/combat_intents.py:29`, `services/companion_tags.py:33`, `services/fauna.py:697`, `services/rumors.py:74`, `mock_llm.py:846` (`str(s)`), `agents/loot.py:256` (inline, caixa antes) | `case="lower"` | loot (367) |
| B | A + `strip` | `inventory.py:34`, `services/reputation.py:74`, `gamedata.py:379` (strip/lower **antes** do NFKD), `services/npc_world.py:76`, `services/world_engine.py:53` | `case="lower", strip=True` | — |
| C | NFKD + combining + `casefold`, sem strip | `agents/router.py:312`, `services/death_flow.py:407`, `services/bestiary_lint.py:173`, `services/conflict_summary.py:423`, `services/encounter_manifest.py:165`, `services/faction_gate.py:168`, `services/leak_phrases.py:19` (público), `services/law.py:161`, `services/memory_provenance.py:241`, `services/npc_knowledge.py:123`, `services/lore_quests.py:76`, `services/scene_cards.py:77` | default | faction_gate/law (377) |
| D | C + `strip` | `services/faction_membership.py:122` | `strip=True` | — |
| E | C + colapso de espaço | `services/plot_threads.py:157`, `services/plot_threads_lint.py:51`, `services/shared_pool_models.py:135` (`fold_name`, nome no pool), `services/quest_log.py:334`, `services/world_validators.py:300` | `collapse=True` | — |
| F | A + colapso | `services/opening_threads.py:55` | `case="lower", collapse=True` | — |
| G (fica) | `encode("ascii","ignore")` ± troca por `_` | `combat_mechanics.py:467`, `services/card_effects.py:151`, `services/enemy_decks.py:139`, `services/tactical_profile.py:513`, `services/creature_art.py:75`, `services/prologue.py:634` | — (D2) | card_effects (368), enemy_decks (371) |
| H (fica) | slug/tokenizador/ id seguro, outra função | `agents/bestiary.py:84`, `services/lore_query.py:28`, `rag.py:231`, `services/entity_identity.py:14`, `services/chronicle_search.py:29`, `services/quest_log.py:200,209`, `world_utils.py:827`, `services/actor_lifecycle.py:177`, `services/conflict_damage.py:39`, `services/body_limit.py:141`, `services/content_validator.py:96,1541`, `services/faction_display.py:105,198` (NFD de propósito, comentário em `:200`) | — | faction_display (377) |

Contagem corrigida [F]: 63 ocorrências de `unicodedata.normalize` em 57 arquivos `.py` fora de
`tests/`/`evals/`/`docs/`/`project_index/`. Em código de produto (sem `scripts/` e `playtest/`),
são **38 funções de fold** (classes A–G, sendo 32 candidatas A–F) e **16 slugs/tokenizadores**
(H). Não são "~60 cópias de `_fold`". Em `scripts/` há mais 7 (fora; D2).

### 3.2 `services/env.py` (E2 e E6)

```python
import os

def env_choice(name: str, choices: tuple[str, ...] | frozenset[str], default: str) -> str:
    raw = os.getenv(name, default).strip().lower()
    return raw if raw in choices else default

def is_database_profile() -> bool:
    return os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"
```

O `env_choice` usa `os.getenv` (o mesmo objeto global que `monkeypatch.setattr(dossiers.os,
"getenv", ...)` substitui em `tests/test_eval_dossier_leak.py:142` [F]). As variantes
`str(os.getenv(X, d) or d)` (`services/card_piles.py:81`) e `str(os.getenv(X, d) or "")`
(`services/law.py:157`) dão o mesmo resultado para toda string: o golden R15 prova isso por site.
O literal `"RPG_X"` continua no chamador, então o gate de flags (`scripts/flag_registry.py:25`,
regex `RPG_[A-Z0-9_]+`) segue vendo todos.

**Candidatos E2 [F]/[H]** (leitores com a forma `raw in CHOICES else DEFAULT`; a Etapa 0 confirma
cada um): `services/world_engine.py:37`, `world_quests.py:70`, `lore_quests.py:53`,
`npc_world.py:45`, `rumors.py:35,46`, `world_calendar.py:40`, `rumor_adoption.py:38`,
`npc_self.py:49`, `npc_knowledge.py:101`, `law.py:157`, `plot_threads.py:111`, `fauna.py:61,69`,
`opening_threads.py:51`, `companion_soul.py:74`, `context_prefetch.py:33`, `scene_cards.py:58`,
`shared_pool.py:50`, `narrative_sink.py:31`, `turn_delivery.py:23`, `jev_rollout.py:126`,
`account_security.py:46`, `creature_gen.py:347`, `card_rewards.py:64`, `card_piles.py:81` (368),
`enemy_decks.py:86` (371), `enemy_intent.py:44` (371), `combat_flags.py:50` (`mode(cap)`, por
dicionário) e `agents/router.py:561`. São **cerca de 29**, não 25.

**Candidatos E6 [F]** (expressão exata): `rag.py` ×9 (`:999, 1021, 1087, 1136, 1170, 1234, 1373,
1533, 1668`), `persistence.py` ×8 (`:387, 445, 783, 843, 1198, 1263, 1297, 1327`; esperam a 368),
`agents/combat.py:165,763` (`== "legacy"`; esperam a 371), `services/card_effects.py:806`
(espera a 368), `services/dossiers.py:301`, `services/kill_switches.py:153`. Total **23
equivalentes** de 39 ocorrências de `RPG_RUNTIME_PROFILE` em 14 arquivos; a auditoria falava
em 32. `infrastructure/runtime.py:487` já tem `_profile_of(env)`, mas com `or "legacy"` (semântica
de `""` diferente) e dentro do pacote que puxa os adapters (R7): não serve de reuso.

### 3.3 `llm_setup.invoke_structured` (E3)

```python
def invoke_structured(
    llm, schema: type[T], messages, *, node: str | None = None,
    event: str = "failed", level: str = "warning",
) -> T | None:
    try:
        result = llm.with_structured_output(schema).invoke(messages)
    except Exception as e:
        if node:
            _log_event(node, event, level=level, error=type(e).__name__)
        return None
    return result if isinstance(result, schema) else None
```

`scripts/gen_event_catalog.py` ganha em `WRAPPERS` um tipo que lê `node=`/`event=` literais na
chamada e registra o campo `error`, para o catálogo ficar byte-igual (R6). Se o executor não
conseguir isso sem mudar o `observability/events.py`, os sites migrados passam `node=None` e
mantêm o `_log_event` literal no `except` (R18 decide caso a caso).

**Sites [F]** (19 chamadas de `with_structured_output` em código de produto, mais
`narrate_structured`): `character_creator.py:363`, `agents/archivist.py:1019`,
`agents/bestiary.py:677`, `agents/campaign_manager.py:248` (retry de idioma; `_info`),
`agents/combat.py:857,1322` (371), `agents/librarian.py:86`, `agents/loot.py:305` (367),
`agents/router.py:685`, `agents/npc.py:542`, `agents/world_simulator.py:140,307`,
`services/chronicle_compression.py:86`, `services/creature_gen.py:1404`,
`services/death_flow.py:355`, `services/encounter_preparation.py:455` (dentro de
`_invoke_with_deadline` e com `isinstance(result, PreparedScene)`, superclasse do schema pedido;
fica), `services/shared_pool.py:471`, `services/prologue.py:518`,
`services/tactical_profile.py:596` (engole a exceção sem log; migraria com `node=None`).
A auditoria falava em "~30 guards". Pelas leituras acima, os que distinguem exceção de
não-instância (router, archivist, world_simulator, campaign_manager) ficam. A estimativa
honesta é de **5 a 9 sites aptos** [H].

### 3.4 `llm_setup` — `_attempt` e `_prepare_candidate` (E4)

```python
def _attempt(
    provider: str, model: str, tier: ModelTier, attempt_index: int, *,
    latency_ms: int, fell_back: bool, outcome: LLMAttemptOutcome,
    error: str | None, structured: bool, **extra,
) -> None:
    _emit_attempt_telemetry(LLMAttemptEvent(provider=provider, model=model, tier=tier,
        attempt_index=attempt_index, latency_ms=latency_ms, fell_back=fell_back,
        outcome=outcome, error=error, structured=structured, **extra))
```

`RoutedLLM._prepare_candidate(provider, model, attempt_index, fell_back, structured, errors)
-> tuple[client | None, int]` faz kill switch → circuito → build → `_apply` e devolve o cliente
(ou `None` para `continue`) e o `attempt_index` atualizado. Os textos de `errors.append(...)`
(`"kill_switch"`, `"circuit"`, `"build:<Exc>"`, `"apply:<Exc>"`) ficam idênticos, porque
`_log_exhausted` os registra. O `_log_attempt(..., "kill_switch", ...)` também. Se `stream` e
`invoke` divergirem num detalhe que o golden mostre, o detalhe vira parâmetro, e não "correção".

### 3.5 `rag._add_memory` e `rag._query_by_vector` (E5)

O escopo é `Literal["session", "npc"]`. As diferenças da R27 viram uma tabela privada
`_SCOPE = {"session": {...}, "npc": {...}}` com `op`, `doc_prefix`, `path_fn`, `mkdir_fn` e
`digest_fn`. Os eventos de log ficam como **duas chamadas literais** num `if scope == "session"`
(o scanner do catálogo lê só constantes, `scripts/gen_event_catalog.py:154-155`), ou entram em
`MANUAL` com os mesmos campos (R6). O `import hashlib` local de `add_memory_to_session`
(`rag.py:1375`) some, porque `hashlib` já é do topo do módulo (`rag.py:1543` usa sem import
local).

### 3.6 Arquivos

- **Novos:** `services/text.py`, `services/env.py`; testes `tests/test_spec378_text_fold.py`,
  `tests/test_spec378_env_choice.py`, `tests/test_spec378_invoke_structured.py`,
  `tests/test_spec378_llm_attempt_golden.py`, `tests/test_spec378_rag_memory_golden.py`,
  `tests/test_spec378_database_profile.py`; goldens em `tests/fixtures/spec378/*.json`.
- **Alterados:** os sites listados em 3.1–3.5, `llm_setup.py`, `rag.py` e, se preciso,
  `scripts/gen_event_catalog.py` (só `WRAPPERS`/`MANUAL`).
- **Não alterados:** `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`,
  `config/flags.yaml`, `api.py`, `evals/**`, `playtest/opening_checks.py`.

### 3.7 Arquivos por etapa (entrada do W1)

| Etapa | Arquivos | Travado hoje por |
|---|---|---|
| E4 | `llm_setup.py`, `tests/test_spec378_llm_attempt_golden.py` | — |
| E5 | `rag.py`, `tests/test_spec378_rag_memory_golden.py` | — |
| E2 | `services/env.py` + os ~29 leitores da 3.2 | `card_piles.py` (368), `enemy_decks.py`/`enemy_intent.py` (371) |
| E1 | `services/text.py` + os sites A–F da 3.1 | `agents/loot.py` (367), `law.py`/`faction_gate.py` (377) |
| E3 | `llm_setup.py` + sites aptos | `agents/combat.py` (371), `agents/loot.py` (367) |
| E6 | `services/env.py` + os 23 sites da 3.2 | `persistence.py`, `card_effects.py` (368), `agents/combat.py` (371) |

## 4. Plano passo a passo

Ordem: **E4 → E5** (arquivos livres hoje) **→ E2 → E1 → E3 → E6**. Antes de cada etapa:
W1 (R3) e medir RAM livre (regra do dono; < 3 GB enfileira). Subagente roda só os testes do
escopo, com `-n 2` no máximo. Suíte completa e W2 completo ficam com o coordenador.

### Etapa 0 — Inventário (sem código de produto)

1. Preencher as três tabelas (fold 3.1, flags 3.2, structured 3.3) com a semântica exata de
   cada site, conferida no source. Registrar no §9 da spec.
2. Rodar o W2 "antes" (A): evals `--seed 7` e playtest `--turns 10 --seed 0`, e guardar as
   saídas fora do repo (scratchpad do coordenador).
3. Decidir o corte da E3 (R21).

### Etapa 1 (E4) — `_attempt` e `_prepare_candidate`

1. **Testes primeiro** (`tests/test_spec378_llm_attempt_golden.py`): fakes de cliente por
   desfecho (R23), `time.perf_counter` fixo, hook de tentativa e hook legado capturados, caplog.
   Grava `tests/fixtures/spec378/llm_attempts.json` com o código **atual**. Commit só do teste
   e do golden.
2. **Implementação:** `_attempt` (1 commit) e depois `_prepare_candidate` (1 commit).
3. **Verificação:** golden idêntico; `tests/test_routing.py`, `test_usage_capture.py`,
   `test_llm_logging.py`, `test_llm_hedge.py`, `test_stream_structured.py`,
   `test_spec346_provider_error_code.py`, `test_audit_real_contracts.py` e
   `test_log_event_registry.py` verdes.

### Etapa 2 (E5) — memória do RAG

1. **Testes** (`tests/test_spec378_rag_memory_golden.py`): FAISS e embeddings falsos, um
   `memory_store` falso com `stage`/`query` gravando argumentos, `RPG_RUNTIME_PROFILE`
   alternado; grava `rag_memory.json` com o código atual (R28). Commit.
2. **Implementação:** `_query_by_vector` (1 commit), `_add_memory` (1 commit).
3. **Verificação:** golden idêntico; `test_npc_memory.py`, `test_bug_memoria_resiliencia.py`,
   `test_playtest_observability_hardening.py`, `test_conflict_summary_lifecycle.py`,
   `test_embeddings_provider.py` e `test_log_event_registry.py` verdes.

### Etapa 3 (E2) — `env_choice`

1. **Testes** (`tests/test_spec378_env_choice.py`): `env_choice` isolado; golden parametrizado
   (R15) gravado com as funções atuais em `flag_readers.json`. Commit.
2. **Implementação:** `services/env.py`; depois um commit por módulo leitor, pulando os
   travados.
3. **Verificação:** golden idêntico; testes de cada módulo tocado; gate de flags
   (`docs/guias/TESTES.md` § Flags) verde.

### Etapa 4 (E1) — `fold`

1. **Testes** (`tests/test_spec378_text_fold.py`): corpus da 3.1; para cada site candidato, a
   função antiga copiada verbatim como `_legacy_<modulo>_<nome>` e um caso
   `assert all(_legacy(x) == fold(x, **opts) for x in CORPUS)` com o primeiro contraexemplo na
   mensagem. Esses `_legacy_*` ficam no teste depois da migração: são o oráculo permanente.
   Commit.
2. **Implementação:** `services/text.py`; depois um commit por módulo cujo caso passou, trocando
   o corpo por `fold(...)` ou por um alias (R5). Site que falhou fica e vai para o §9.
3. **Verificação:** testes de cada módulo tocado, `test_spec348*`, `test_spec350*`,
   `test_spec366_followups.py`, testes do pool compartilhado (`test_spec297_*`).

### Etapa 5 (E3) — `invoke_structured` (só se a R21 deixar)

1. **Testes** (`tests/test_spec378_invoke_structured.py`): fake que devolve instância, fake que
   devolve `AIMessage`, fake que devolve `AIMessage(content="")`, fake que levanta em `invoke`,
   fake que levanta em `with_structured_output`, `FallbackLLM` real; asserta o retorno, o log
   (com `node` e sem) e que `MockLLM` devolve a instância. Caracterização do librarian (R19).
   Commit.
2. **Implementação:** helper (1 commit) + `WRAPPERS` do catálogo, se usado; depois um commit
   por site apto.
3. **Verificação:** testes do nó de cada site; `test_log_event_registry.py`.

### Etapa 6 (E6) — `is_database_profile`

1. **Testes** (`tests/test_spec378_database_profile.py`): tabela {ausente, `""`, `"legacy"`,
   `" LEGACY "`, `"local"`, `"hosted-supabase"`, `"lixo"`} → o mesmo booleano da expressão
   antiga, incluindo `""` → `True`. Commit.
2. **Implementação:** um commit por arquivo (`rag.py`, `dossiers.py`, `kill_switches.py`;
   depois `persistence.py`, `card_effects.py` e `combat.py`, quando destravarem).
3. **Verificação:** testes de perfil (`test_projection_db_local.py`, `test_http_idor_offline.py`,
   `test_eval_dossier_leak.py`, `test_session_hardening_local.py`) e os do escopo.

### Etapa 7 — Pouso

W2 "depois" (B) e comparação com A; revisão independente (W7); `/spec-land`.

## 5. Critérios de aceite

- [ ] Etapa 0: as 3 tabelas de inventário no §9, com a semântica de cada site
- [ ] E4: golden de telemetria idêntico; 19 `LLMAttemptEvent(` viram 1 (no `_attempt`)
- [ ] E5: golden do RAG idêntico; as 4 funções públicas com a mesma assinatura
- [ ] E2: golden de flags idêntico; nenhum leitor lê `config/flags.yaml`
- [ ] E1: um caso de propriedade por site migrado, verde; lista de divergentes no §9
- [ ] E3: migrada (≥ 5 sites aptos) ou cancelada com registro (R21)
- [ ] E6: tabela de perfil idêntica; divergentes (`or "legacy"`) listadas
- [ ] `observability/events.py` e `docs/operacao/EVENTOS_DE_LOG.md` byte-iguais (R6)
- [ ] W2: `evals compare` sem diferença; playtest 10 turnos com as mesmas violações e desfechos
- [ ] W3: `git diff main -- tests/` não altera nenhuma linha de `assert` de teste existente
- [ ] `uv run pytest` verde (suíte completa offline, coordenador)
- [ ] Guard de FallbackLLM preservado em todo site migrado (`AIMessage` → `None`; exceção → `None`)
- [ ] Saves antigos continuam carregando (nenhum id derivado muda; R8)
- [ ] Revisão independente `Sol` aprovada, com o W2 refeito pelo revisor em ≥ 1 etapa
- [ ] Smoke real §6 executado

## 6. Smoke test com LLM real

Necessário porque E3 e E4 tocam o caminho do LLM (`RoutedLLM.invoke/stream` e o guard dos
nós). Local, perfil `legacy`, `ROUTES` default (DeepSeek primário), chave real do `.env`
(lida só por nome de variável). Cinco requests no máximo.

1. API local (`uvicorn api:app`) com `set_llm_attempt_telemetry_hook` gravando num JSONL do
   scratchpad. `POST /game/new`, depois 1 turno de **história** ("olho em volta"): narração em
   pt-BR, ao menos 1 evento `outcome="success"` com `structured=True` no roteador e
   `fell_back=False`.
2. 1 turno de **NPC** (falar com o NPC da cena): resposta do NPC; se `npc.py` migrou para
   `invoke_structured`, o NPC gerado tem nome e campos preenchidos (MockLLM esconde erro de
   campo).
3. 1 turno de **combate** ("ataco a criatura"): o tabuleiro abre ou o combate resolve; eventos
   de tentativa coerentes (`attempt_index` crescente no `invoke`).
4. **Fallback:** repetir 1 turno com `RPG_ROUTES` pondo um candidato inválido na frente (modelo
   inexistente no mesmo provider): o evento do 1º candidato sai com `outcome` de erro, o do 2º
   sai `success` com `fell_back=True`, e o turno é narrado.
5. Conferir no JSONL que os campos de `LLMAttemptEvent` (`http_status`, `provider_error_code`,
   `usage`, `structured_failure_code`) vêm preenchidos como antes. A referência é o mesmo
   roteiro rodado na `main` antes da E4, na Etapa 0, se a quota permitir.

## 7. Riscos & compatibilidade

- **E1-a: fold vira id persistido.** `fold_name` dá nome no pool compartilhado; folds de
  `enemy_decks`/`tactical_profile`/`card_effects` dão chaves. Mitigação: classe G fica de
  fora; o teste de propriedade cobre o corpus de `data/` inteiro (R8, R11).
- **E1-b: diferenças sutis de Unicode.** `lower` ≠ `casefold` em `ß`/`ς`; `ascii-ignore` apaga
  `ß`, `—` e emoji, enquanto `combining` os mantém; `strip` antes ou depois do NFKD diverge em
  `"¨"`; `str(x)` ≠ `str(x or "")` para `None`/`0`. O corpus adversarial existe para pegar isso.
  Com entrada livre do jogador (router, loot), "equivalente no `data/`" não basta (D1).
- **E2-a: a semântica de `""`.** `os.getenv(X, d)` com `X=""` devolve `""`, que cai no default
  em todos os leitores atuais. O golden inclui `""`.
- **E3-a: o guard de FallbackLLM é crítico (AGENTS.md).** Trocar `isinstance` por um helper que
  aceite mais ou menos tipos muda qual fallback roda. O librarian aceita qualquer
  não-`BaseMessage` (R19). O `encounter_preparation` compara com a superclasse. Ambos ficam
  fora, salvo prova.
- **E3-b: catálogo de log.** Um helper que emita evento com nome variável some do scanner e
  quebra `test_log_event_registry.py` (R6).
- **E4-a: os monkeypatches da suíte.** São 49 `setattr(llm_setup, ...)`. Um helper que capture
  `_get_cached_client` ou `_ATTEMPT_TELEMETRY_HOOK` no import faz o patch falhar em silêncio
  (R25).
- **E4-b: `attempt_index`.** Ele já tem duas semânticas (`invoke` × `stream`), e unificar seria
  mudança de telemetria (R24). Fica registrado como follow-up, não corrigido.
- **E5-a: `document_id` no Postgres.** Um digest diferente duplica memória no staging. O golden
  grava o `document_id` (R27).
- **E6-a: perfil `""`.** Com `RPG_RUNTIME_PROFILE=""`, `rag`/`persistence` acham que há banco
  (`!= "legacy"`), `llm_setup`/`shared_pool` acham que é legacy (`or "legacy"`) e
  `RuntimeConfig.from_env` levanta `ValueError` (`infrastructure/runtime.py:213,237-238`). Não
  há caso real hoje, porque o boot falha antes. A spec preserva as duas semânticas (pura) e
  registra o follow-up (D4).
- **Sessões paralelas:** cada sub-item travado espera (W1). Nada de "resolver no rebase".
- **MockLLM/FallbackLLM:** o comportamento não muda. O MockLLM devolve instâncias, então só os
  testes com fake de `AIMessage` e de exceção provam a E3.
- **Quota/latência:** nenhuma chamada nova; o §6 gasta até 5 requests.
- **Saldo de linhas (honesto):** E4 ≈ −120 a −180; E5 ≈ −110 a −140; E1 ≈ −60 a −90 (alias por
  módulo, tabelas de prova grandes nos testes); E2 ≈ −15 a −25; E3 ≈ −30 a −60 se migrar;
  E6 ≈ 0 (troca 1:1; o ganho é uma semântica só). **Total no produto: ≈ −330 a −500**, mais
  ~+600 de testes e goldens. Não chega a −1.500.

## 8. Decisões do dono

- **D1 — Domínio da prova de equivalência do fold.** (a) estrito: o corpus de `data/` mais o
  conjunto adversarial Unicode mais as strings geradas e as não-strings; (b) só o corpus de
  `data/`. **Recomendação: (a).** Router, loot e `combat_intents` dobram a entrada livre do
  jogador. Com (b), uma cópia `lower` poderia virar `casefold` e mudar o casamento de `ß`, por
  exemplo.
- **D2 — Alcance do `fold`.** (a) `fold` com `case`/`strip`/`collapse` (até 32 candidatas A–F);
  (b) um `fold` fixo sem opções (só as 12 da classe C); (c) também `ascii=True` para a classe G
  e `scripts/`. **Recomendação: (a).** A classe G produz chaves (cartas, famílias de inimigo,
  arquétipos), e `scripts/` não é produto.
- **D3 — Corte da E3.** Migrar só se ≥ 5 sites couberem exatamente no contrato; abaixo disso,
  cancelar e não criar o helper. O librarian fica de fora, salvo prova. **Recomendação: sim,
  com corte em 5.** Um helper usado por 2 sites é mais um lugar para ler, não menos.
- **D4 — Perfil `""` (E6-a).** (a) preservar as duas semânticas e abrir um follow-up para
  unificar (`""` → erro de boot em todos); (b) unificar já. **Recomendação: (a).** (b) muda
  comportamento e não cabe numa spec pura. O boot já falha com `""`, então o risco real é baixo.
- **D5 — `api._database_profile`.** (a) não mexer agora (fica para a SPEC-381, que reorganiza
  `api.py`); (b) delegar o corpo a `is_database_profile()` quando 367/368 pousarem.
  **Recomendação: (a).** `api.py` está quente em duas branches, e a 381 vai mexer em tudo ali.
- **D6 — Paralelismo com 376/377.** (a) seguir o W6: a 378 começa só depois de 376 e 377
  pousadas; (b) liberar E4/E5 (`llm_setup.py`/`rag.py`, que nenhuma das duas toca) em paralelo.
  **Recomendação: (a).** Foi a regra pedida para a onda. Se o dono quiser velocidade, (b) é
  seguro do ponto de vista de arquivos, mas custa RAM (1 executor + 1 revisor a mais).

## 9. Notas de pouso e follow-ups

(Preenchido na execução: tabelas da Etapa 0, sites divergentes que ficaram, sites travados que
esperaram, resultado do W2 A×B.)

Follow-ups já conhecidos (cada um muda comportamento e precisa de spec própria): unificar a
semântica das cópias de fold divergentes (R6 da auditoria); semântica de `RPG_RUNTIME_PROFILE=""`
(D4); `attempt_index` com duas semânticas (E4-b).
