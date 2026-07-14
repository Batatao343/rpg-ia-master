# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-13 (sessão 15: ciclo de produto executado —
> 3 specs `done`, **769 offline verdes**)

---

## TL;DR — Em que pé está

**Sessão 2026-07-13 (15): CICLO DE PRODUTO INTEIRO ENTREGUE** — as 3 specs
`approved` da sessão 14 viraram `done` (+40 testes → **769 offline verdes**;
registro de execução no §8 de cada spec):
1. **[balanceamento-early-game](specs/balanceamento-early-game.md) `done`** —
   métricas novas no harness (`first_death_turn`/`downed_count`/
   `avg_hp_pct_after_combat`/`replan_count` + deltas no report); baseline ANTES
   do tuning (mock `20260713-160458` + real); knobs data-driven: **máx 1 elite
   no nível 1** (mata o burst que matou o `combate` real) + **piso de HP das
   frágeis** (Batedor 22→27 etc.; cap novo de budget PULADO — dados não pediam);
   **"O Saque"** (`death_outcome`/`apply_downed`: 1ª queda fora de apex/boss =
   acorda 1 dia depois no último local seguro, HP 25%, ouro 0, só a arma
   básica, únicos voltam ao pool via `holder="world"`; `player_downed` com gate
   `source="combat"`; invariante `downed.*`); **replan por REGIÃO + intervalo
   10→15** — explorador: 50 → 4 replans (−92%). **Verme confirmado no REAL**
   (`secret_rusher` 30t, 0 vazamentos) — pendência fechada.
2. **[streaming-turno-sse](specs/streaming-turno-sse.md) `done`** —
   `POST /game/action/stream` (accepted → phase/route → narrative em chunks →
   state; keepalive; memorial = `error` 409 semântico); frontend com indicador
   de fase + typewriter dirigido pelo servidor + **fallback automático** pro
   POST clássico; **smoke real: `accepted` 0.09s, `route` 0.66s num turno de
   20.2s**; log `rpg.turn` ganhou `llm_calls/llm_providers/fell_back/
   cost_usd_est` (turno real: 5 calls ≈ $0.0036; ContextVar, sem vazamento).
3. **[polish-sessao](specs/polish-sessao.md) `done`** — `GET /game/saves` +
   `DELETE /game/save/{id}` (remove memória da sessão junto); tela "Continuar
   jornada" (⚰ memorial em modo leitura, exclusão com confirmação); **chips de
   combate 100% mecânicos** (`combat_suggestions` pura, máx 5; smoke real:
   "Estocada Renal" → `estocada_renal`); export .txt + busca local da crônica;
   onboarding do 1º turno; passe mobile 390px (**Playwright 14/14**, overflow 0).

**Próximo:** decidir pós-ciclo com o usuário — **Fase 8 (arte) vs 10b
(público)** (decisão adiada de propósito, com dados do ciclo em mãos).
Backlog v2: só Crônica avançada sobrevive.

**Histórico recente** (detalhe SÓ no `CHANGELOG.md`):
- 2026-07-13 (14): sync de docs + auditoria A1–A8 corrigida (729 verdes) +
  3 specs do ciclo refinadas com o usuário e `approved`
- 2026-07-13 (13): fix-playtest-achados `done` — 6 defeitos do transcrito real +
  fuga do jogador implementada; 715 verdes; perfis 11º/12º (`quester`/`fujao`)
- 2026-07-06/07 (12): **Fase 5 inteira** (harness 12 perfis + invariantes +
  telemetria); suíte `-m llm_playtest` (4 VITAIS × 30t); bugs reais: rota NONE,
  vazamento do Verme (curado), teto de sobrevivência no budget
- 2026-07-06 (11): **roteamento multi-provider** — `RoutedLLM`/`ROUTES`, Groq
  grátis em TODOS os tiers (`function_calling`), telemetria por invoke
- 2026-07-06 (10): Fase 10 local (UUID/migrations/CORS/rate-limit/log) + Fase 11
  (9 contratos LLM reais) + mapa interiores + NPCs 3 camadas
- 2026-07-05 (9/8): Fase 7 (autoria+validação) · Fase 6 (conteúdo sistêmico)
- 2026-07-04/05 (7): Fase 4 (gameplay core, 7 specs)

**⚠️ Saves pré-2.5b:** carregam sem crash (migrations), mas locais/fações antigos
não existem mais no mapa — sessões antigas ficam narrativamente órfãs. Arquivar.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 769 testes offline verdes (contratos de LLM ficam fora)
uv run pytest -m llm_contract -v -s  # 9 contratos contra o Gemini REAL (~13 req; requer chave)
uv run pytest -m llm_playtest -v -s  # Fase 5: 4 perfis VITAIS × 30 turnos no LLM REAL (RPG_PLAYTEST_TURNS encurta)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python -m playtest run --all --turns 50   # Fase 5: harness offline (MockLLM, 12 perfis)
uv run python -m playtest report <run_id>        # Fase 5: relatório agregado
uv run python -m playtest transcript <run_id>    # transcrito ação→narração (julgar prompt)
uv run python rag.py                 # reindexar lore (data/codex/) + regras (data/rules.txt)
uv run python scripts/migrate_lore_nova.py  # regerar Codex de lore_nova/ (SOBRESCREVE curadoria)
bash scripts/smoke_api.sh [porta]    # smoke da API (health, map, /game/new, /game/action)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na
raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers:** default = `ROUTES` multi-provider com fallback (Groq free cobre
tudo). `LLM_PROVIDER=gemini` força só-Gemini; sem chave nenhuma → MockLLM (jogável
sem rede). Contas: minimax/deepseek 402, qwen 401 — OPCIONAL resolver (assumem
quando tiverem saldo/key; não é bug). Ver `.env.example`.

**Quota:** Gemini free = 20 req/dia por modelo; Groq free = 100k tokens/dia (esgota
numa sessão real longa — espalhar por dias ou tier pago). `get_llm()` é fail-fast
(`max_retries=0`). **MockLLM esconde bugs de mapeamento** — validar nós novos com
chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate:** IA identifica/narra; Python resolve tudo (`combat_mechanics.py`) —
  iniciativa, DoT/condições, custos, cooldowns, saves + perfis de comportamento (2.5b)
  + fuga do jogador real (fix-playtest)
- **Mundo:** mapa de Valoria 35 nós (30 + 5 interiores), relógio, viagem (fog of war),
  descanso, gating por classe; raças com traits mecânicos (2.5b); clima mecânico (6.5)
- **Fase 2/2.5:** fações com objetivos/reputação/ascensão, memória de NPC, Codex
  Valoria + grafo (558 entidades) + `event_log`/`world_projection` + RAG com
  visibilidade (`secret`/`hidden` não vaza)
- **Fase 3 (completa):** crônica por capítulos, codex do jogador + bestiário
  progressivo, quest log, visualização de estado (controladores/ameaças/reputação)
- **Fase 4 (completa):** progressão/XP/level-up (111 habilidades, 20 ramos), buffs
  mecânicos, inventário `{id,qty}`+slots, economia determinística, party,
  dificuldade/morte digna (memorial 409)
- **Fase 6 (completa):** economia viva (rotas/escassez), 20 itens únicos (claim
  engine), migração de monstros, encontros sistêmicos, clima com efeito
- **Fase 7 (completa):** lint de conteúdo + CI, curadoria migration-safe
  (`codex_overrides.yaml`), segredos de NPC em docs `hidden`
- **Fase 5 (completa):** playtest agêntico (`playtest/`, 12 perfis), invariantes
  por turno, telemetria JSONL + relatório com custo, `--real` com tetos,
  `transcript` por turno
- **Fase 10 local + Fase 11:** UUID/migrations/CORS/rate-limit/log JSON; 9 contratos
  LLM reais (`-m llm_contract`)
- **Roteamento multi-provider:** 3 tiers, fallback vivo, Groq grátis em todos;
  NPCs 3 camadas com traits
- **Ciclo de produto (sessão 15):** "O Saque" (1ª queda ≠ memorial) + tuning de
  spawn nível 1 + replan por região; streaming SSE do turno (fases + chunks +
  fallback) com custo real no log; tela de saves (listar/continuar/excluir),
  chips mecânicos de combate, export/busca da crônica, onboarding, mobile 390px
- Multi-provider LLM + typewriter no frontend React; memória híbrida (resumo + RAG
  por sessão); persistência JSON por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância
de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Auditoria 2026-07-13: **12/12 sites de produção blindados** (verificado).

---

## Bugs conhecidos

Bugs históricos: TODOS fechados (4 da sessão 2026-06-26 → Fases 4.3/4.6 e spec
npcs-3-camadas; 6 do transcrito real → fix-playtest-achados; 8 da auditoria de
segurança → sessão 14, tabela completa no `CHANGELOG.md`).

**Pendências abertas (não são bugs de código):**

- Action `validate.yml` verde no primeiro push (conferir no GitHub)
- Lote 2 de traits (40 → 80 em `data/traits.json`)
- 1 flaky isolado na suíte (sessão 8; 3 runs verdes depois — observar)
- Curadoria: NPCs públicos do norte citam a Rede Carmesim (timeline era-7 é
  `hidden`) — ver ROADMAP § Fase 7
- Cache runtime (`data/bestiary.json`/`npc_database.json`) é gravado por suíte/
  smokes com entradas mock (ex.: HP regredido, "Unknown") — hoje é `git checkout`
  manual antes do commit; considerar isolar cache de teste (observado na sessão 15)

Fechadas na sessão 15: confirmação real do Verme ✔ · mortes nível 1 do
`combate`/`agressivo` ✔ (spec balanceamento; nota: 2ª queda DELIBERADA sem cura
segue matando — por design) · replan em toda viagem ✔.

## Limitações conhecidas

- **API stateless por save** — sem sessão concorrente; Postgres+auth = Fase 10b
- **Saves antigos** carregam via `schema_version` + `_MIGRATIONS` (v0→v2);
  pré-2.5b ficam narrativamente órfãos — arquivar
- **Free tier não sustenta playtest real longo** — Groq 100k tokens/dia; espalhar
  por dias ou tier pago
- **Latência real:** p50 ≈ 15s, p95 33-46s por turno — o custo do LLM continua,
  mas o streaming SSE (spec `done`) mostra fase em <1s e narra em chunks; a
  espera cega acabou

---

## Checklist ao começar a próxima tarefa

0. Feature/fase nova? **Spec primeiro** — `specs/` (CLAUDE.md § spec-driven)
1. `/qa` verde antes de mexer
2. Nó novo com `with_structured_output`? Guard de fallback (seção CRÍTICA)
3. Mudou schema do player/estado? Atualizar `state.py` + `game_engine.py` + `api.py` + creator
4. Novo agente no grafo? Conectar ao `archivist` no fim (REFERENCE.md)
5. Editou `lore_nova/`, `data/codex/` ou `data/rules.txt`? Rodar `uv run python rag.py`
6. Mecânica nova (números)? Python determinístico, não LLM
7. **Ao finalizar:** `/wrap-up` — suíte completa verde + ESTADO_ATUAL.md + ROADMAP.md + commit
