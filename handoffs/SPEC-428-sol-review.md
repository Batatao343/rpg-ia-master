# SPEC-428 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / sol (spec-reviewer) · **Data:** 2026-11-23 · **Commit revisado:** `928e04e7`

## Confirmação 3 (23/11, `faa9805a..928e04e7`)

O P1-1 está corrigido. O diff toca só `scripts/dev/narration_pairs.py`, `tests/test_narration_pairs_script.py` e a spec. A branch **não** foi rebaseada: a `main` andou (SPEC-426, `e2e9e254`, include do basedpyright) e o rebase fica para o pouso.

1. **`_sweep_fakes`.**
   - Restaura por identidade só os falsos deste guard: o `foreign` e a lambda do narrador.
   - Ignora entradas `None` de `sys.modules`.
   - Roda no `finally`, então também quando o corpo levanta.
   - Um `get_llm` trocado de propósito fica intocado (`test_guard_keeps_get_llm_replaced_on_purpose`).
   - Com o plugin de sessão, já ampliado para qualquer falso com `__qualname__` começando por `_llm_guard`, nenhum módulo fica com `get_llm` falso depois de `tests/test_narration_pairs_script.py`.
   - As 4 ordens rodaram com rc 0 e sem sobra: pares→enrich, enrich→pares, enrich→pares→archive_record, pares→archive_record→enrich.
2. **Mutante `_sweep_fakes` no-op.**
   - É morto por `test_guard_restores_imported_during_body_and_on_exception`, que **trava** o defeito com um módulo sintético que liga o falso durante o guard.
   - `test_run_leaves_no_fake_get_llm_in_any_module` **passa com o mutante**. A confirmação do executor é real: o teste usa `_cases()[:1]` (`cena-1`), que não chega ao import preguiçoso de `agents.campaign_manager` (`agents/storyteller.py:1720`, caminho de viagem).
   - Medi num teste de rascunho: com o caso `local-visitado`, o mesmo teste falha com o mutante (`['agents.campaign_manager'] == []`) e passa sem ele. Ver P3-4.
3. **Outro estado global.**
   - O script restaura `check_encounter`, `roll_encounter_type`, `_story_world_pulse`, `RPG_NARRATION_SIZE` (agora com o valor anterior) e o nível do logger `rpg.provider`.
   - Não há cache de flag: `narration_size.mode()` e `latency_flags` leem o env a cada chamada (`env_choice`), e `RPG_NARRATION_SIZE` só é lida em `services/narration_size.py`.
   - Sobra `random.seed(1)` no `random` global, sem restaurar. O `run_node` dos testes faz o mesmo; não vaza flag. Ver P3-5.
4. **P3-3.** Os três trechos batem com o código: §3.4 com a armadilha, "seria idêntico", e o passo 1 local com chave. Resta o status `approved` no cabeçalho, que o coordenador ajusta no pouso.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-4 | P3 | `tests/test_narration_pairs_script.py` (`test_run_leaves_no_fake_get_llm_in_any_module`) | `_cases()[:1]` não exercita o import preguiçoso; o teste passa com `_sweep_fakes` no-op. | Usar o caso `local-visitado` (`[c for c in _cases() if c["id"] == "local-visitado"]`), que reprovou o mutante na medição. |
| P3-5 | P3 | `scripts/dev/narration_pairs.py:286` (`random.seed(1)`) | Estado do `random` global não é devolvido depois do run. | Opcional: `state = random.getstate()` antes e `random.setstate(state)` no `finally` do `run`. |
| P3-6 | P3 | `specs/SPEC-428-latencia-narracao-tamanho-alvo.md:3` | Status `approved`; o §5 pede `in-progress` até a promoção. | Coordenador, no pouso. |

## Reconferência 2 (23/11, `9c8e40ec..eecda1b7`)

O produto não mudou: `git diff 9c8e40ec..HEAD -- agents/ services/ tests/fixtures/` vazio. Mudaram
`scripts/dev/narration_pairs.py`, `tests/test_narration_pairs_script.py`, `docs/spec428/pares_casos.json`
e a spec. A branch está rebaseada (`git merge-base --is-ancestor main HEAD` = 0).

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `scripts/dev/narration_pairs.py:199-221` (`_llm_guard`) | O guard troca `get_llm` só nos módulos já carregados na entrada e restaura só esses. Um módulo importado **durante** o guard (import preguiçoso dentro do nó) faz `from llm_setup import get_llm`, prende o `foreign` e o `finally` não o restaura. Medido: depois de `tests/test_narration_pairs_script.py`, `agents.campaign_manager.get_llm` continua `foreign` no processo (plugin de sessão: `campaign_manager carregado no inicio: False` → `foreign get_llm apos a sessao: ['agents.campaign_manager']`). `pytest -n 0 tests/test_narration_pairs_script.py tests/test_enrich_node.py` → 7 falhas `RuntimeError: chamada de LLM fora do narrador no pacote de pares` em `test_enrich_node.py`, que sozinho passa (9 passed). É poluição dependente de ordem: a suíte completa com xdist falha conforme a distribuição. | No `finally`, além de `saved`, varrer `sys.modules` e devolver o `llm_setup.get_llm` original a todo módulo cujo `get_llm is foreign`. Teste: `monkeypatch.delitem(sys.modules, "agents.campaign_manager", raising=False)` antes de `np_.run(...)`; depois, nenhum módulo com `getattr(m, "get_llm", None) is` o falso (ou `__name__ == "foreign"`). |
| P3-3 | P3 | `specs/SPEC-428-latencia-narracao-tamanho-alvo.md:3`, `:257`, `:395` | Restos de texto: o status continua `approved` (o §5 diz `in-progress` até a promoção); §3.4 `:257` ainda diz "1 `revelacao` com `<GANCHO_NOVO>`", embora o diário diga "§3.4 reflete a armadilha"; o "Não rodou" diz que o compare "seria vazio" (ele rodaria os suítes e daria idêntico, porque nenhum adapter chama o narrador) e "§6 passos 2–3 (e o 1) dependem de deploy no staging", mas o passo 1 é local. | Status `in-progress`; trocar `:257` por "1 `revelacao` com armadilha `ENCONTRO NA ESTRADA`"; "seria idêntico" no lugar de "seria vazio"; passo 1 = "local, com chave, coordenador". |

**Conferido e certo:**
- **(a) Pulso do mundo.** `_story_world_pulse` vira no-op nos dois braços (`:269`). O mutante `pulse_on` (linha removida) é morto por `test_world_pulse_llm_is_neutralised`.
- **(b) Contagem de LLM.** Todo `get_llm` fora do narrador é contado e levanta, inclusive em módulo importado durante o guard, que liga o `llm_setup.get_llm` já trocado. Não há alias (`get_llm as`, `= get_llm`) em `agents/`, `services/` nem na raiz. O vazamento é só na **saída** do guard (P1-1). Um `introduced_npcs` vindo do LLM não chama `get_llm` (medido: 4 chamadas, sem `SystemExit`). O mutante `narrator_only` é morto por `test_zero_llm_calls_outside_narrator`.
- **(c) Teto antes da 1ª chamada.** `check_budget` roda antes de qualquer chamada. O mutante `budget_late` é morto por `test_budget_refuses_before_any_call` (`assert 4 == 0`).
- **(d) `input_hash`.** Comparei os prompts `off` × `on` dos 10 casos linha a linha (`difflib`). As únicas linhas diferentes são a regra de parágrafos (`-`/`+`) e, nas 7 encurtadas, a linha `TAMANHO DA RESPOSTA` (`+`); nos 2 controles, só a regra de parágrafos. O hash ignora exatamente isso. O mutante `hash_blind` é morto por `test_fingerprint_ignores_only_size_lines`.
- **(2) Sem chamada paga em teste.** Durante o run, o guard troca todo `get_llm` carregado. `--mock` não chama `get_llm`. Os embeddings ficam fora pelo `_no_real_embeddings` do conftest. O caminho "sem chave" para antes da 1ª chamada. O `.json` só leva contagens, `input_hash`, `provider/model/outcome` e `git_sha`; o `.md` leva as narrações.
- **(3) P3-1.** `cena-2` e `fala-mediada-1/2` têm Velha Magda presente e `legiao_ferro` conhecida, e as duas chegam ao prompt: "NPCs na cena: ['Velha Magda']", `id=legiao_ferro · ... · disposição=neutro` em FAÇÕES. As classes continuam certas (`test_mock_run_makes_ten_pairs_with_expected_classes`) e `pares_casos.json` bate com o gerador.
- **(4) Spec.** Os desvios, a nota da Etapa 0, o "Não rodou" e o P3-2 estão registrados e fiéis ao código; só sobram os restos de texto do P3-3.
- **(5) Preset.** O `_updated` novo começa exatamente com o da `main` e a única outra linha a mais é `"RPG_NARRATION_SIZE": "shadow"`.

## Escopo

Branch `spec-428`, merge-base `acb4fd56` .. `ba4bc3ff` (`91c3e11e` golden, `62e53c17` produto,
`ba4bc3ff` script de pares; `b413a707` só aprova a spec). **A `main` andou** para `e87d0769`
(`git merge-base --is-ancestor main HEAD` = 1): 12 commits da SPEC-425 (`services/art_brief.py`,
`services/image_pricing.py`) e docs/handoffs, sem arquivo em comum com esta branch. Revisado assim
mesmo; o `wt.sh sync` do pouso resolve.

Lido: diff inteiro de `agents/storyteller.py`, `services/narration_size.py`, `config/flags.yaml`,
`scripts/staging/*`, `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`,
`scripts/dev/narration_pairs.py`, `docs/spec428/pares_casos.json`, os dois testes novos e a spec.
Fora: smoke com chave, staging, `evals run/compare` (não pedidos neste brief).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/dev/narration_pairs.py:117-131`, `:168-182`, `:245` | O teto de 30 conta só as chamadas do narrador (`st.get_llm` trocado). O turno de descanso/viagem roda `_story_world_pulse` (`agents/storyteller.py:1405`, `:2062-2067`), que chama `agents/world_simulator.get_llm` (`:130`, `:298`) por fora do contador e **sem fixar o resultado entre `off` e `on`**. Com `RPG_WORLD_ENGINE=off` no `.env` (ou dia virado com algo percebido em `on`), os casos `descanso-1/2`, `local-visitado`, `controle-local-novo` e `controle-revelacao` recebem `[ECOS DO MUNDO]` diferentes em `off` e `on`: o par deixa de ser "mesmo estado, mesma ação" e o dono compara prosa de entradas distintas. Além disso `--samples N≥2` dá 10×2×N ≥ 40 > 30: aborta no meio depois de gastar, sem gravar nada. O teste não pega nada disso: só roda com `RPG_FORCE_MOCK=1` do `conftest` e nada afirma "nenhuma outra chamada de LLM". | Em `_run_one`, fixar o pulso: trocar `st._story_world_pulse` por no-op (ou `st.simulate_world`/`st._narrate_world` por stub determinístico) durante o par; contar no `llm_setup.get_llm` (todo LLM, não só o do narrador). Recusar antes da 1ª chamada quando `20 × samples > MAX_CALLS`. Teste novo: com `--mock`, `world_simulator.get_llm` trocado por um que levanta, o run conclui 10 pares. |
| P2-2 | P2 | `specs/SPEC-428-latencia-narracao-tamanho-alvo.md:3`, `:257`, `:384-389`, §5 | A spec não foi tocada depois da aprovação (`git diff b413a707 HEAD -- specs/` vazio). Desvios sem registro: o controle `revelacao` é a armadilha `ENCONTRO NA ESTRADA` e não `<GANCHO_NOVO>` (§3.4 `:257`; o golden também); os estados vêm de `_base_state()` do script, não de `tests/factories.make_state` (§3.4); a confirmação da Etapa 0 (ordem de `closing_clause` em `_story_prompt_blocks`) não foi escrita; "Não rodou" ainda diz "Esta é a spec (`draft`)"; status `approved` em vez de `in-progress`; R11/Etapa 6.1 (`evals compare` off × on = 0) sem evidência registrada. | Atualizar a spec: status `in-progress`; registrar os dois desvios (a troca do controle é aceitável: armadilha com números já resolvidos é o subtipo de `revelacao` mais comum em jogo e não depende de quest de mundo; `<GANCHO_NOVO>` exige tick de quest e é coberto por `test_classify_priority`); nota da Etapa 0; marcar critérios; rodar e registrar o compare off × on (ou mover para "Não rodou" com motivo). |
| P3-1 | P3 | `scripts/dev/narration_pairs.py:37-68`, `:92-98` | Estados magros: sem NPC presente, sem facção conhecida. As duas `fala_mediada` perguntam ao narrador numa cena vazia, o que tende a texto curto também em `off` e não mostra o risco real (fala com informação sendo cortada). | Pôr 1 NPC já criado e presente (sem ficha a gerar) e 1 facção conhecida em `fala-mediada-1` e `cena-2`; regenerar `pares_casos.json` com `--write-cases`. |
| P3-2 | P3 | `services/prose_guard.py:258-264`; `agents/storyteller.py:499-527` | Com 1–2 parágrafos, os dois guards que apagam parágrafo inteiro (ouro rejeitado, SPEC-091 R6; segredo mediado, SPEC-202 R11) pesam mais; a spec §7 cita só o da mediação. Comportamento existente, não regressão. | Na medição de staging (§6 P3), separar `narrative.rejected` por `kind` (incluindo o monetário). Sem mudança de código. |

Nenhum P0/P1.

## Conferência dos 11 pontos do coordenador

1. **Golden veio do código antigo: sim.** `91c3e11e` não muda nenhum arquivo de produto em relação
   à merge-base (`git diff --stat acb4fd56 91c3e11e` só lista a spec e o teste/fixtures). Worktree
   descartável na `main` `e87d0769` + `tests/test_narration_size.py` de `91c3e11e` + as 12
   fixtures da HEAD: **12 passed** (6 classes × `RPG_PROMPT_STATIC_FIRST` off/on). As fixtures não
   mudaram depois de `91c3e11e` (`git diff --stat 91c3e11e HEAD -- tests/fixtures/` vazio).
   Estáveis com `PYTHONHASHSEED=7` e `4242`. Nota: `abertura-*` = `cena-*` byte a byte (o
   turno 1 não muda o SystemMessage hoje); a classe do caso é garantida por
   `test_golden_cases_hit_their_class`.
2. **`off`/`shadow` = hoje: sim.** Ausente/`off`/inválido: golden verde. `shadow`:
   `test_shadow_prompt_equals_off` nas 12 combinações; `test_near_valid_values_keep_todays_prompt`.
   A linha estática fica byte a byte (`PARAGRAPH_RULE_OFF` com o mesmo recuo de 4 espaços do f-string).
   `git diff --stat main...HEAD -- tests/fixtures` só mostra `narration_size_off/`;
   `spec382_node_golden.json` sem diff e `tests/test_spec382_node_golden.py` -n 0 verde. Em
   `shadow` só sai `narration.size_class` com `mode`, `size_class`, `shortened`, `chars_max`
   (`services/narration_size.py:125-132`); nenhum texto; `off` retorna antes do log (`:121-123`;
   `test_off_logs_nothing` em DEBUG).
3. **Leitura da flag: coerente, não é achado.** `services.env.env_choice` (strip + lower,
   inválido = default) é o mesmo helper de `services/latency_flags.py` (`_choice = env_choice`) e
   das irmãs `RPG_ARCHIVE_RECORD`/`RPG_MEDIATED_STREAM`, que também são `off|shadow|on`, default
   `off`, `kind: release` com `expires`. `"true"`/`"1"`/`"yes"`/`"onn"`/`""` → `off` (testado).
4. **Classificação.** Procurado ativamente: turno 1 → `abertura` (`campaign_manager` incrementa
   antes, `agents/storyteller.py:2626`); local novo e interior novo → `local_novo` (regra de
   `first_visit`; `apply_travel` copia `visited`, `world_utils.py:216-219`); local visitado com
   tesouro → `discovery_events` → `revelacao`; quest nova de mundo → `<GANCHO_NOVO>`; desfecho de
   lore quest → `<DESFECHO_DE_QUEST>`; armadilha/rastro/social/sinal de fauna → `ENCONTRO NA
   ESTRADA` (`:1848`, `:2005`, `:2034`, `:2047`). `<BOATOS>` sempre presente com rumores `on` não
   contém a tag de gancho (`:355`). Fora do nó (sem alvo, sem LLM do narrador): início de combate
   (`return _story_combat_start`, `:1402`), `npc_actor`, resumo de fim de combate, oferta de lore
   quest (`<GANCHOS_POSSIVEIS>` só em `agents/npc.py:1189`). `rumor_nothing` → `cena` por decisão
   da spec (R4.6), com `NOTHING_FOUND_FACT` em `EVENTOS_DESTE_TURNO`, protegido pela linha de
   tamanho. NPC ausente (`ABSENT_REASONS`) → `cena`: aceitável (ninguém responde). Prioridade:
   descanso em local novo → `local_novo`; mediação com revelação → `revelacao`; mediação + descanso
   → `fala_mediada`: bate com R4 e está em `test_classify_priority`. Não achei turno de informação
   que caia em classe encurtada fora das decisões da spec.
5. **Texto da instrução.** Só tamanho (parágrafos + faixa de palavras) e a regra "nunca corte"
   (eventos, fato novo, fala com informação, oferta de missão, consequência); não mexe em pessoa,
   tempo verbal, estilo nem opções. Única outra regra de tamanho no prompt é a linha estática, que
   em `on` vira "salvo quando TAMANHO DA RESPOSTA, abaixo, pedir menos": sem contradição. "abaixo"
   vale nas duas ordens (`test_on_mode_prompt_has_class_target` confere a posição). Specs 043, 091,
   309, 346: nenhuma regra de prompt de tamanho (só os guards de parágrafo, P3-2). `<GANCHO_NOVO>`
   diz "de forma breve", só em `revelacao`, que não é encurtada.
6. **Motor intacto.** Nenhum diff em `llm_setup.py`, `agents/npc.py`, `routes/turn.py`, `StoryUpdate*`;
   nenhum `max_tokens`; `with_structured_output` e guard intactos (I3, I4 cobertos).
   `agents/storyteller.py` 3016 → 3012; `baseline_growth.py --base main` rc 0 ("nenhum baseline cresceu").
7. **Preset e env: ok.** `staging_flags.json:26` `"RPG_NARRATION_SIZE": "shadow"`; o novo `_updated`
   começa exatamente com o antigo (inclui as notas de `RPG_RLS_STRICT_PRINCIPAL` e
   `RPG_ARCHIVE_RECORD`) e só acrescenta a linha de 22/11. `vercel_env.py` nas duas listas com o
   comentário de R1. `flags.yaml:673-678` default `"off"`, `expires: 2027-02-22`.
8. **Script de pares.** Sem chave/`RPG_FORCE_MOCK=1` sem `--mock` recusa antes de chamar
   (testado). Saída `.json` só contagens + `provider/model/outcome`; nenhum segredo. Casos
   reprodutíveis (`test_committed_cases_match_generator`). Problemas em P2-1 (teto e A/B) e P3-1.
   Troca do caso `revelacao`: aceitável no mérito, mas precisa constar na spec (P2-2).
9. **Mutantes (plugin `-p`, sem editar o worktree): 10/10 mortos** — tabela abaixo.
10. **Gates: verdes** (comandos abaixo). `git diff --stat main...HEAD -- evals/` vazio; nenhum
    caminho de `evals/protected-paths.txt` (lista atual relida) está no diff.
11. **"Nenhum adapter de `evals/` chama o narrador": confirmado.** `grep storyteller evals/**/*.py`
    só acha nomes de rota em `evals/experiments/jev_router_*.py`/`spec217_corpus_check.py` (strings
    de rota, não import). `evals/core/adapters.py` importa `agents.router`, `services.*`,
    `persistence`, `rag`, `playtest.invariants` e `api.format_response` (só formatação); nenhum
    importa `main`, `agents.storyteller` nem roda o grafo. Logo quem decide ligar fora do staging é
    o dono (D2), como a spec diz.

## Evidência verificada

### Confirmação 3 (`928e04e7`)

`bash scripts/dev/red_green.sh 428` → **red_green: 34/34 OK** (os 30 da reconferência 2 mais estes 4):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_narration_pairs_script.py::test_guard_keeps_get_llm_replaced_on_purpose | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_guard_restores_imported_during_body_and_on_exception | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_run_leaves_no_fake_get_llm_in_any_module | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_run_restores_env_and_world_pulse | vermelho (import) | verde | OK |

```text
pytest -n 0 -p leak428 tests/test_narration_pairs_script.py → 15 passed; falsos após a sessão: []
pytest -n 0 -p leak428 pares→enrich | enrich→pares | enrich→pares→archive_record | pares→archive_record→enrich → rc 0 nas 4; falsos: [] nas 4
MUTS=1 (_sweep_fakes no-op) -k test_guard_restores_imported_during_body_and_on_exception → FAILED (morto)
MUTS=1 -k test_run_leaves_no_fake_get_llm_in_any_module → 1 passed (não trava; P3-4)
rascunho test_a_full com o caso local-visitado: MUTS=0 → 1 passed; MUTS=1 → FAILED ['agents.campaign_manager'] == []
```

### Reconferência 2 (`eecda1b7`)

`bash scripts/dev/red_green.sh 428` → **red_green: 30/30 OK** (são os 25 da tabela abaixo mais estes 5 novos, todos `vermelho (import)` na `main` e `verde` na branch):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_narration_pairs_script.py::test_budget_refuses_before_any_call | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_fingerprint_ignores_only_size_lines | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_pairs_carry_input_hash_and_fail_on_divergence | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_world_pulse_llm_is_neutralised | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_zero_llm_calls_outside_narrator | vermelho (import) | verde | OK |

Mutantes do script (plugin `mutpairs428`, `MUTP=<nome>`) → **4/4 mortos**:

| mutante | morto por |
|---|---|
| `pulse_on` (sem o no-op do pulso) | `test_world_pulse_llm_is_neutralised` |
| `narrator_only` (o guard não troca os outros `get_llm`) | `test_zero_llm_calls_outside_narrator` |
| `budget_late` (`check_budget` depois do 1º par) | `test_budget_refuses_before_any_call` (`assert 4 == 0`) |
| `hash_blind` (hash constante) | `test_fingerprint_ignores_only_size_lines` |

Comandos e resultados:

```text
git diff 9c8e40ec..HEAD -- agents/ services/ tests/fixtures/ → vazio
git diff --stat main...HEAD -- evals/ → vazio
pt.sh tests/test_narration_pairs_script.py tests/test_narration_size.py -n 2 → 94 passed
pt.sh tests/test_ruff_counts.py tests/test_clock_asserts.py tests/test_size_budget.py tests/test_spec192_vercel_env.py tests/test_flag_registry.py -n 0 → 68 passed
pt.sh tests/test_spec382_node_golden.py -n 0 → 66 passed
baseline_growth.py --base main → "nenhum baseline cresceu", rc 0
diff off × on dos prompts dos 10 casos (scratch chk428.py) → só a regra de parágrafos e a linha TAMANHO DA RESPOSTA
pytest -n 0 -p leak428 tests/test_narration_pairs_script.py → 11 passed; foreign get_llm após a sessão: ['agents.campaign_manager']
pytest -n 0 tests/test_enrich_node.py → 9 passed (sozinho)
pytest -n 0 tests/test_narration_pairs_script.py tests/test_enrich_node.py → 7 FAILED em test_enrich_node.py (RuntimeError do guard)
```

### Revisão 1 (`ba4bc3ff`)

`bash scripts/dev/red_green.sh 428`:

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_narration_pairs_script.py::test_call_budget_aborts | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_committed_cases_match_generator | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_json_has_only_counts | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_mock_run_makes_ten_pairs_with_expected_classes | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_refuses_with_force_mock | vermelho (import) | verde | OK |
| tests/test_narration_pairs_script.py::test_refuses_without_key_and_without_mock | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_classify_priority | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_golden_cases_hit_their_class | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_log_for_unshortened_class_has_zero_chars_max | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_log_never_carries_narration_text | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_mode_parsing | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_narrator_prompt_off_matches_golden | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_near_valid_values_keep_todays_prompt | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_off_logs_nothing | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_on_mode_prompt_has_class_target | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_on_mode_unshortened_classes_have_no_size_line | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_opcoes_clause_is_todays_literal | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_options_clause_unchanged_every_class | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_shadow_and_on_log_size_class | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_shadow_prompt_equals_off | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_size_mode_does_not_change_engine_output | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_size_mode_keeps_story_schema | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_size_on_does_not_touch_npc_or_combat_prompt | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_size_on_fallback_llm_aimessage_guard | vermelho (import) | verde | OK |
| tests/test_narration_size.py::test_targets_table | vermelho (import) | verde | OK |

red_green: 25/25 OK

O "vermelho (import)" do golden na `main` é do arquivo da HEAD (importa `services.narration_size`);
a prova de que o golden reproduz a `main` é a execução separada do item 1 (12 passed na `main`).

Mutantes (plugin `mut428`, `MUT428=<nome>`, `tests/test_narration_size.py`):

| mutante | morto por |
|---|---|
| `off_injects` (alvo com `off`) | `test_narrator_prompt_off_matches_golden[cena-off]` |
| `newloc_gets_cena` (local novo recebe alvo) | `test_classify_priority[...local_novo]`, `test_on_mode_unshortened_classes_have_no_size_line[local_novo]` |
| `mediated_absent` (fala mediada sem alvo em `on`) | `test_classify_priority[...fala_mediada]` |
| `rest_cena_swap` (descanso ↔ cena) | `test_classify_priority[...cena]` |
| `true_is_on` (`"true"`/`"1"` = on) | `test_mode_parsing[true-off]` |
| `shadow_injects` (`shadow` lido como `on`) | `test_mode_parsing[shadow-shadow]` |
| `shadow_closing` (linha de tamanho em `shadow`) | `test_shadow_prompt_equals_off[cena-off]` |
| `shadow_no_log` (sem evento em `shadow`) | `test_shadow_and_on_log_size_class[shadow]` |
| `newloc_short` (`local_novo` encurtada) | `test_targets_table` |
| `paragraph_rule_off_changed` (linha estática de `off` muda) | `test_narrator_prompt_off_matches_golden[abertura-off]`, `[revelacao-on]` |

## Correções aplicadas

Nenhuma ainda (revisão sem edição de código).

## Pendências

- P2-1 e P2-2: corrigir **antes de rodar o pacote de pares com chave** e antes do pouso (executor ou
  coordenador; mesma SPEC-428). Não bloqueiam o código de produto, que entra com a flag `off`.
- P3-1, P3-2: opcionais; P3-2 vira item da medição de staging (§6 P3).
- Ligar fora do staging: dono (D2), lendo o pacote de pares.

## Comandos rodados

```text
git merge-base --is-ancestor main HEAD → 1 (main andou para e87d0769; sem arquivo em comum)
git diff --stat acb4fd56 91c3e11e (sem spec/teste/fixtures) → vazio (golden capturado sem produto alterado)
worktree descartável em main e87d0769 + teste de 91c3e11e + fixtures: pt.sh tests/test_narration_size.py -n 0 → 12 passed
PYTHONHASHSEED=7 e 4242: pt.sh tests/test_narration_size.py -k "golden or shadow_prompt" -n 0 → 25 passed (2x)
bash scripts/dev/red_green.sh 428 → 25/25 OK
10 mutantes via -p mut428 → 10/10 mortos
pt.sh tests/test_ruff_counts.py tests/test_clock_asserts.py tests/test_size_budget.py tests/test_flag_registry.py tests/test_log_event_registry.py tests/test_spec192_vercel_env.py -n 0 → 72 passed
pt.sh tests/test_spec382_node_golden.py -n 0 → 66 passed
pt.sh tests/test_mediated_stream.py tests/test_spec309_prompts.py tests/test_ambient_consumers.py -n 2 → 111 passed
scripts/dev/baseline_growth.py --base main → "nenhum baseline cresceu", rc 0
scripts/dev/dup_helpers.py --diff main...HEAD → só homônimos (_count, _git_sha, classify, mode), sem duplicação real
ruff check / format --check nos 5 arquivos .py tocados → limpo
git diff --stat main...HEAD -- evals/ → vazio; nenhum caminho de evals/protected-paths.txt no diff
worktree descartável removido (git worktree list sem goldchk)
```
