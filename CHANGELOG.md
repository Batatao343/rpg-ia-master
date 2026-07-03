# CHANGELOG — histórico de sessões

> Histórico detalhado das sessões de desenvolvimento. NÃO é carregado automaticamente
> no contexto — consultar sob demanda. Estado atual: `ESTADO_ATUAL.md`.

---

## 2026-07-02 — DX: tooling do Claude Code (auditoria de fricção)

Auditoria de 20 sessões de transcripts achou: prefixo de PATH repetido 180×, ~36KB de
docs carregados toda sessão, leituras de lore de 30–56KB, 120 runs de pytest verbosos.
Entregas:

- **Docs de sessão em dieta:** `@REFERENCE.md` removido do auto-load do `CLAUDE.md`
  (leitura sob demanda); `ESTADO_ATUAL.md` de 13.3KB → ~5.5KB; histórico de sessões
  movido para este `CHANGELOG.md` (não carregado). Economia ~6-7K tokens/sessão.
- **Skills de projeto:** `/qa` (pytest token-lean, só falhas + resumo; `--lf` p/ iteração)
  e `/wrap-up` (ritual de fim de tarefa: suíte + docs + commit via caveman-commit).
- **`scripts/smoke_api.sh`:** smoke da API (health, options, map, /game/new, /game/state,
  /game/action + limpeza do save) — substitui loops de curl reescritos a cada sessão.
- **Hook `reindex-reminder.js`** (PostToolUse Edit|Write): editar `lore_nova/`,
  `data/codex/` ou `data/rules.txt` injeta lembrete de rodar `uv run python rag.py`
  (1x por sessão). Ativação junto com a allowlist em `.claude/settings.proposed.json`
  (renomear para `settings.json` após revisão — escrita direta bloqueada em auto mode).
- **Regra anti-leitura-gigante** no `CLAUDE.md`: lore/codex/JSONs grandes = Grep ou
  Read parcial, nunca Read inteiro.
- Pendente (ação manual, bloqueada em auto mode): PATH permanente do uv —
  `[Environment]::SetEnvironmentVariable('Path', "$env:APPDATA\Python\Python314\Scripts;" + [Environment]::GetEnvironmentVariable('Path','User'), 'User')`.

## 2026-07-02 — Fase 2.5b: Valoria nos dados mecânicos + combate com comportamento

- **Mapa** (`data/world_map.json`): 30 nós — 12 macro-regiões do grafo + 18 sublocais
  (anéis de Nova Arcádia, Fortaleza de Vorr, O Trono...). Grafo conexo (teste BFS),
  `region_id` em todo nó, 1 `start: true` por região. Start global: `nova_arcadia`.
- **Fações** (`data/factions.json`): 18 fações de Valoria (legiao_ferro, mao_sombria,
  filhos_chama_azul, tribos_devoradores_sol...) com goal/pace/ascension derivados do
  Codex; targets de ascensão apontam para o mapa novo.
- **Raças** (`data/origins.json`): 6 jogáveis (Humano, Elfo, Anão da Fuligem, Vrel,
  Cinzéu, Osshari) com **traits mecânicos** da lore — `apply_racial_traits()` em
  `character_creator.py` aplica bônus de atributo/recursos/defesa/ouro/itens em Python;
  `condition_resists` (ex.: Anão ignora veneno) e `racial_save_bonus` respeitados por
  `combat_mechanics`. Ficha ganha `racial_traits`/`condition_resists`/`racial_save_bonus`
  (`state.py`; saves antigos: campos ausentes = sem efeito, sem crash).
- **Bestiário** (`data/bestiary.json`): 84 entradas curadas com `regions` e `behavior`;
  criaturas do grafo usam `mon_<slug>`, combatentes de fação `enemy_<slug>` + campo
  `faction` (mapeia fação → soldado no encontro).
- **Combate com personalidade (R8):** perfis `tatico` (escolhe ataque por situação, foge
  por moral — `flee_below`/`pack_morale`), `feroz` (maior dano, frenesi +2 com HP<50%,
  NUNCA foge — urso-titã), `covarde` (foge cedo), `implacavel` (rotaciona ataques, nunca
  foge) — determinístico em `combat_mechanics.py` (`choose_enemy_attack`, `check_morale`,
  `get_behavior`). Status novo `"fugiu"`: não conta como vitória nem loot; combate sem
  mortos (todos fugiram) NÃO roteia para loot. Ataques de inimigo aplicam condições
  embutidas na string de dano ("+ veneno" → Condition no player, respeitando resist racial).
- **Fuga → alerta (R10):** `world["threat_alerts"]` (`world_utils.register_flee_alert`,
  chamado pelo combat_node); alerta ativo na REGIÃO dispara encontro de reforços 1x
  (validade 6 turnos, consumido ao disparar, expira sozinho). Backfill em `ensure_world`.
- **Encontro por região (R11):** `world_utils.pick_encounter_enemy()` sorteia criatura
  CONCRETA do bestiário por região/perigo/fação (BOSS nunca sai aleatório) —
  `check_encounter` devolve hint com o nome exato → spawn cai no cache (menos 1 LLM call).
- **Identidade:** `data/graph/entities_extra.json` (curadoria manual: sublocais +
  combatentes de fação; `migrate_lore_nova.py` NÃO o toca) mergeado em
  `graph_resolver.load_entities()` — canônico vence conflito. Teste de integridade
  cruzada cobre os 4 JSONs mecânicos.
- **Limpeza (R5):** `data/world_lore.txt` REMOVIDO; `mock_llm.py` agora usa `legiao_ferro`
  como fação simulada (era `selo_palido`).
- Testes: `tests/test_fase25b.py` (novo, 24 testes: integridade, mapa conexo, traits,
  moral/fuga/frenesi, alertas, sorteio regional) + repin de `test_fase0`/`test_fase2`/
  `test_world_sim` para os dados novos.

## 2026-07-02 — Limpeza de deps

Removidas do `pyproject.toml` deps sem nenhum `import` no código — `chromadb`, `graphviz`,
`kuzu`, `langchain-chroma`, `langchain-experimental`, `langsmith`, `streamlit` — leftovers
de planejamento anterior à 2.5 (o grafo de mundo virou JSON puro em
`services/graph_resolver.py`, não kuzu). `uv sync` + `uv run pytest` (116 verdes)
confirmaram nada quebrou. `stream_ctx.py` intocado — infra planejada pela spec 2.5b/2.8
(streaming futuro), não código morto.

## 2026-07-02 — Timeline de Valoria no Codex

`lore_nova/timeline_completa.txt` (Codex Omnia — 8 eras, da criação ao presente) ingerido
no Codex. Novo handler `parse_timeline()` em `scripts/migrate_lore_nova.py` gera
`data/codex/timeline/*.md` (1 doc por run de visibilidade, `type: timeline`, NÃO registra
entidade no grafo). Os 4 clusters de reveal que `secrets.txt` já protege (aprendiz→Arauto,
Rei Subterrâneo, pacto Valerius↔Daruun, Rede Carmesim) saem como `visibility: hidden` —
não vazam ao narrador público (`query_rag(max_visibility="public")`); o resto da história
é `public`. Curadoria explícita em `_TIMELINE_HIDDEN_CLUSTERS` (pares frase-inicial→
frase-final). 4 testes novos em `tests/test_fase25.py`. Codex reindexado (2579 chunks).

## 2026-07-02 — Fase 2.5: Codex + grafo de mundo

Lore REESCRITO em `lore_nova/` (universo **Valoria**, ~690KB), SUBSTITUI o lore antigo.
Spec `specs/fase-2.5-codex-world-state.md` → `done`:

- `scripts/migrate_lore_nova.py` → gera `data/codex/` (635 .md com frontmatter
  `id/type/name/tags/visibility`) + `data/graph/entities.json` (558 entidades: 12 regiões,
  28 fações, 141 NPCs, 10 raças, 340 monstros, 27 artefatos únicos).
  ⚠️ Re-rodar o script SOBRESCREVE curadoria manual no codex/entities.
- `data/graph/edges.json` (~70 edges curadas à mão) + `relation_types.json` (7 tipos).
  Estes o script NÃO toca.
- `services/graph_resolver.py` — edges efetivas = base − disabled + dynamic, com
  visibilidade; `get_current_controller`, `is_alive`. `services/codex_loader.py` —
  ingestão FAISS com metadados. `query_rag(..., max_visibility="public")` filtra
  `hidden`/`secret` do contexto do narrador (default preserva comportamento).
- `GameState` ganhou `event_log` / `world_projection` / `pending_world_events`
  (persistidos em `persistence.py`; saves antigos carregam com defaults vazios).
- Smoke real OK: reindex do Codex (2297 chunks), 1 turno real narrando lore de Valoria,
  chunks `secret` fora do contexto público.

## 2026-07-01 — Projeto vira spec-driven

`specs/` + convenção no `CLAUDE.md`; specs 2.5–2.8 criadas.

## 2026-06-26 — Multi-provider LLM + typewriter

- `get_llm()` suporta Gemini, Ollama, OpenAI e endpoints OpenAI-compatíveis (Qwen,
  LM Studio) via `LLM_PROVIDER` + vars no `.env`. Sem tocar nos agentes.
- Narrativa com efeito typewriter (palavra a palavra) no frontend React.
- `stream_ctx.py` criado com ContextVar SSE (infra para streaming real futuro).
- `MockLLM.stream()` adicionado para compatibilidade.

## 2026-06-26 — Otimização de turno

Turno reduzido de ~5-6 para ~2-3 LLM calls (commit `fcb14c0`).
