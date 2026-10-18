# Auditoria de poda (ponytail), 2026-10-18

> Pedido do dono (2026-10-18): rodar a skill de terceiros **ponytail** sobre o repo inteiro
> e listar o que pode ser podado, sem mudar código de produto. Saída: este relatório +
> SPEC-263 a SPEC-274 (`draft`).

## Método

- **Skill:** [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT), commit
  `09c434ab73ca43761c5d8b0c5d341926c2fba710` (2026-10-18). Clone raso numa pasta de scratch;
  os 6 `skills/*/SKILL.md` foram lidos antes do uso. São instruções de revisão em texto,
  sem nada suspeito, e nenhum script do repo foi executado. Cópias de `ponytail`,
  `ponytail-audit`, `ponytail-review` e `ponytail-debt` foram usadas só no worktree isolado
  `ponytail-audit` (em `.claude/skills/`, que o `.gitignore:35` já ignora); não foram commitadas.
  Observação: o perfil do usuário já tinha a skill instalada globalmente (`~/.claude/skills/ponytail*`,
  desde 2026-07-02); isso não foi tocado.
- **Metodologia seguida:** a de `ponytail-audit` §1–3, ou seja, mapear entradas e fluxos,
  procurar *delete / reuse / stdlib / yagni / merge*, exigir um caso concreto por achado e
  "antes de chamar de não usado, grep da árvore inteira, inclusive testes, fixtures, config e
  referências por string". As seções de bug, segurança e escala da skill ficaram fora: o pedido era poda.
- **Ferramentas:**
  1. Scan por AST de todo símbolo público de topo nos `.py` de produto (raiz, `agents/`,
     `services/`, `infrastructure/`, `observability/`, `workers/`, `playtest/`, `scripts/`),
     contando tokens em todos os arquivos versionados (py/ts/tsx/js/json/yaml/toml/sql/sh/md/jsonl,
     sem `docs/`, `specs/`, `handoffs/`, lore e o `repo_graph.json`). Classes: *DEAD* (zero hits
     fora da definição) e *TESTONLY* (só testes ou evals usam).
  2. Grep de import por módulo (módulos que nada de produto importa).
  3. Variáveis de ambiente lidas no código e citadas em um arquivo só.
  4. Rotas FastAPI × chamadores em `web/src`, `scripts`, `.github` e `supabase` (todas têm chamador).
  5. Sete varreduras Sonnet paralelas, só leitura (services, raiz+agents, infra/obs/workers,
     scripts+playtest, web+frontend, tests+evals, docs/artefatos). Achado de subagente só entrou
     depois de reconfirmado com `git grep -w` neste relatório.
- **Carga assumida:** jogo de um jogador por sessão; staging Vercel + Supabase serverless.

## Resumo

O código é grande (≈62k LOC de testes, 26k em `services/`, 4,9k em `api.py`), mas **pouco
morto**: só ~30 símbolos de produto não têm nenhuma referência. O volume real de poda está em:
(1) **~410 linhas de capacidades do motor de conflito que só os testes exercitam**, que
pedem decisão (ligar ou apagar); (2) o **frontend vanilla** (950 linhas), que o deploy nunca
serve; (3) **~44 MB de mídia** de marketing versionada; (4) deps e extras duplicados no
`pyproject.toml` e dois `requirements*.txt` idênticos.

## Candidatos

| # | Área | Local | Evidência de não-uso | Risco | LOC | Spec |
|---|---|---|---|---|---|---|
| 1 | Deps | `pyproject.toml` extras `openai`/`postgres`, `pillow` no grupo dev, `langchain`, `google-genai` | os extras repetem deps core (SPEC-192); nenhum `import langchain`/`google.genai` (só `langchain_core` ×131, `langchain_text_splitters` ×2) | baixo | ~10 cfg | SPEC-263 |
| 2 | Deps | `requirements.txt` | byte-idêntico a `requirements-vercel.txt` (`diff` vazio, 280 linhas) | baixo | 280 | SPEC-263 |
| 3 | Raiz | `pytest216.log` | entrou por engano no `565a04d`; nenhuma referência | nulo | 1 arq | SPEC-264 |
| 4 | Assets | `assets/gallery/20251205_6e7458.png` (828 KB) | `git grep "gallery/\|20251205_6e7458"` vazio | nulo | 1 arq | SPEC-264 |
| 5 | Jogo/API/web | mana/stamina do jogador: `state.py:129-131`, `world_utils.py:290`, `api.py:1520-1523`, `web/src/types.ts:76-78`, `Hud.tsx:40-46` | Entropia substituiu (SPEC-048); saves pré-v4 arquivados; valores sempre 0 | médio | ~60 | SPEC-265 |
| 6 | Docs | `docs/descricao_projeto/**` mp4/mp3 (≈44 MB) + `proximas-specs/.../previas` (3,1 MB) | só `.gitignore`/`.gitleaks.toml`/`docs/README.md` citam; deploy exclui `docs/**` | baixo | 4–15 arq | SPEC-266 |
| 7 | Front legado | `frontend/` (950 linhas) + fallback em `api.py:4929` | `vercel.json` sempre gera `web/dist`; nenhum teste usa a pasta; cliente sem auth/CSRF/SSE | baixo | ~952 | SPEC-267 |
| 8 | Jogo | `last_safe_location`, `make_armor/shield`, `cards_at_patamar`, `FactionIntel`, `last_stand_roll`, `abyss_signature`, `pending_projections`, `_write_checkpoint_if_due`, `save_custom_artifact` (só teste), 6 constantes | zero hits fora da definição (grep `-w`) | baixo | ~100 | SPEC-268 |
| 9 | Infra | `infrastructure/testing.py`, `infrastructure/file_blob.py`, `FinopsReader`, `ensure_binary_stream`, `require_unique_document_ids`, `PersistenceUnavailable`, `timeline_scope`, `sweep_synthetic_users`, 8 constantes | zero hits fora da definição; módulos sem import | baixo | ~75 | SPEC-269 |
| 10 | Playtest | `check_zero_vitality_outside_terminal` (`playtest/invariants.py:1063`) | saiu de `CHECKS` no `2bbfd57` (substituto: `check_actor_lifecycle`); só 2 testes chamam | nulo | ~20 | SPEC-270 |
| 11 | Web | `chronicleExportUrl`, `LEGACY_ATTACK`, `currentPurchaseAdapter`, `AbilityRef` | 0 refs nos 423 exports varridos | nulo | ~11 | SPEC-271 |
| 12 | Conflito | funções só-teste em `conflict_scene`, `chase`, `death_flow`, `conflict_resolution`, `bestiary_knowledge`, `conflict_summary`, `tactical_profile`, `encounter_preparation`, `cards`, `combat_mechanics.resolve_damage_formula` | nenhum chamador de produto; só testes unitários | médio | ~410 | SPEC-272 |
| 13 | Scripts | `gen_world_living_npcs.py`, `gen_tiers_5_plus.py`; leitores de `.env` duplicados (`checklist.py:340`, `s192.py:26`) | sem teste/CI/guia; dados já curados | baixo | ~340 | SPEC-273 |
| 14 | Config | 6 env vars citadas só no arquivo que lê (`RPG_CRON_MAX_*`, `RPG_FINOPS_*`, `RPG_PLAYTEST_STALE_SECONDS`, `RPG_BACKUP_ROOT`) | ausentes de `.env.example`, workflows, staging, testes | baixo | ~6 | SPEC-274 |

**Total possível:** cerca de **-2.300 linhas** (≈1.400 de código/texto + 280 do requirements
duplicado + os testes que só cobrem código apagado), **-2 deps diretas** e **~47 MB** de binários
fora do checkout.

## Não podar (e por quê)

- **`persistence._MIGRATIONS`**: saves antigos precisam migrar, mesmo os que tocam mana/stamina.
- **`wallet_spend_scope`** (`infrastructure/wallet.py:687`): sem chamador hoje, mas é o gancho
  planejado para ligar reserve→settle às jogadas (pendência da SPEC-185).
- **Adapters `portable`/OIDC/S3** (`s3_blob.py`, `oidc_identity.py`): perfil documentado e
  suportado (SPEC-181). Podar exige decisão de produto, não grep.
- **`services/gameplay_oracles.py`**: contrato nominal da SPEC-212 sobre a régua; testado por paridade.
- **Fakes dentro de módulos de produto** (`FakeFinopsReader`, `MemorySwitchStore`, `MemoryDailyQuota`)
  e seams de teste (`reload_cards`, `reset_text_cap_cache`, `set_switches`): baratos e usados pela suíte.
- **Símbolos que parecem órfãos mas são usados no próprio arquivo:** `_native_tracer`,
  `image_defer_max_age`, `PurchaseStore`, `accept_test_purchases` (SPEC-225 R8), `_legacy_shape`,
  `ProjectionRetry`, `ImageGenerationRefused`.
- **`tests/test_mvp.py`, `test_fase0.py`, `test_fase25.py`**: única cobertura de dados MVP,
  persistência e router; não há teste duplicado de verdade (6 nomes repetidos, corpos distintos).
- **`tests/test_cutover_audit.py`**: guarda a lista MORRE/SOBREVIVE; sai junto com a SPEC-272, se ela apagar tudo.
- **Régua de evals** (`evals/`): protegida. `evals/experiments/{jev_router_ab,jev_router_hybrid,spec217_corpus_check}.py`
  podem ser arquivados depois do fechamento da SPEC-217, **só por proposta ao papel de autoria**;
  hashes de evidência podem citá-los. `evals/runs/` não é versionado.
- **Índices FAISS** (≈10 MB): lidos em runtime na Vercel.
- **`project_index/repo_graph.json`** (12 MB): o gate `project_index check` do CI compara com a
  cópia versionada. Gerar no CI exige redesenhar o gate (spec própria, se valer).
- **`handoffs/`** (81 arquivos, 481 KB): 37 specs e ~79 docs linkam como evidência de revisão.
- **Evidências de spec** (`docs/spec*/evidence`, webm/png/zip): linkadas pelos READMEs.
- **`langchain-community`**: só FAISS + TextLoader, mas puxa sqlalchemy/aiohttp/requests/langchain-classic.
  Trocar mexe no formato pickled dos índices: spec própria com teste de compatibilidade de leitura.
- **`scripts/staging/*`**: ferramentas de runbook da SPEC-197 (incident drill, smokes de voz).
- **`CLASS_THEMES`/`class_themes.json`**: ainda usado pelo prólogo (`services/prologue.py:88`).
- **Rotas FastAPI**: todas as 43 têm chamador em `web/src`, `scripts` ou CI.

## Ordem sugerida

1. **SPEC-264** (arquivos soltos), **SPEC-270** (invariante), **SPEC-271** (exports web): nulo risco, minutos.
2. **SPEC-268** e **SPEC-269** (símbolos mortos): mecânico, grep + ruff.
3. **SPEC-263** (deps): mede bundle Vercel antes/depois.
4. **SPEC-267** (frontend legado) e **SPEC-273** (geradores).
5. **SPEC-274** (env knobs): depende de checar o painel da Vercel.
6. **SPEC-265** (mana/stamina): muda o contrato JSON, com revisão.
7. **SPEC-266** (mídia): depende de o dono escolher onde guardar.
8. **SPEC-272** (capacidades só-testadas): decisão do dono, item por item.

Toda spec que mexe em `.py` termina com o Project Index regenerado em checkout limpo
(o gate de CI acusa staleness).

## Não verificado

- Linhas e módulos privados (`_x`) só foram checados quando um subagente apontou.
- Provedores de `llm_setup.py` (GLM/Kimi/MiniMax/Qwen/Ollama) não foram auditados para poda:
  são roteamento configurável por `RPG_ROUTES`, documentado.
- Duplicação de helpers HTTP/JSON entre `scripts/` além dos leitores de `.env`.
- Chamadas montadas em string ou por `getattr` dinâmico podem escapar ao grep; cada spec repete o grep antes de apagar.
- Nenhuma suíte foi rodada nesta auditoria (só leitura).
