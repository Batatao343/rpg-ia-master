# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-13 (sessão 14: auditoria A1–A8 corrigida — 729 verdes;
> ciclo de produto: 3 specs `approved`)

---

## TL;DR — Em que pé está

**Sessão 2026-07-13 (14):** três entregas (detalhe no `CHANGELOG.md`):
1. **Sync de docs** — ESTADO_ATUAL/ROADMAP/CLAUDE.md tinham 8+ divergências com o
   código (contagens, "Groq só em CLASSIFY" falso, bugs já fechados listados como
   abertos, traits 80 vs 40) — tudo corrigido contra o estado real.
2. **Auditoria de bugs/vulnerabilidades — 8 achados (A1–A8), TODOS corrigidos**
   (+14 testes `tests/test_audit_fixes.py` → **729 offline verdes**). Destaques:
   `/game/new` validava nada (ouro NEGATIVO com level negativo); equip/levelup sem
   gate de memorial; `save_game_state` com `game_id` cru; flag `simulated` mentia
   com Groq; bind `0.0.0.0` → `127.0.0.1` (`RPG_HOST` p/ expor). Verificado limpo:
   XSS (mdLite escapa), path traversal, guards 12/12, sem eval/pickle, .env fora do git.
3. **Ciclo de produto — 3 specs `approved`** (refinadas com o usuário; ver ROADMAP
   § Próximo ciclo): balanceamento early game (+ derrota narrada "O Saque"
   1x/campanha + replan por REGIÃO), streaming SSE de fases (+ custo no log de
   produção), polish de sessão (saves/chips mecânicos de combate/crônica/
   onboarding/mobile). Pós-ciclo (arte vs público): decidir com dados. Backlog v2
   enxuto: só Crônica avançada sobrevive.

**Próximo:** implementar o ciclo na ordem 1 → 2 → 3, começando pela Etapa 1 da
spec [balanceamento-early-game](specs/balanceamento-early-game.md) (métricas +
baseline de playtest). A confirmação real do Verme (`secret_rusher --real` 30t)
pega carona na rodada de baseline.

**Histórico recente** (detalhe SÓ no `CHANGELOG.md`):
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
uv run pytest                        # 729 testes offline verdes (contratos de LLM ficam fora)
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

- Confirmação real do fix do Verme-Primordial: `secret_rusher --real` 30 turnos
  (cerca já verificada via `query_rag`; carona na baseline da spec de balanceamento)
- Balanceamento: `agressivo`/`combate` morrem no nível 1 no playtest REAL —
  **objeto da spec [balanceamento-early-game](specs/balanceamento-early-game.md)**
- Replan em toda viagem (plot twists demais) — idem, R4 da mesma spec
- Action `validate.yml` verde no primeiro push (conferir no GitHub)
- Lote 2 de traits (40 → 80 em `data/traits.json`)
- 1 flaky isolado na suíte (sessão 8; 3 runs verdes depois — observar)
- Curadoria: NPCs públicos do norte citam a Rede Carmesim (timeline era-7 é
  `hidden`) — ver ROADMAP § Fase 7

## Limitações conhecidas

- **API stateless por save** — sem sessão concorrente; Postgres+auth = Fase 10b
- **Saves antigos** carregam via `schema_version` + `_MIGRATIONS` (v0→v2);
  pré-2.5b ficam narrativamente órfãos — arquivar
- **Free tier não sustenta playtest real longo** — Groq 100k tokens/dia; espalhar
  por dias ou tier pago
- **Latência real:** p50 ≈ 15s, p95 33-46s por turno — objeto da spec
  [streaming-turno-sse](specs/streaming-turno-sse.md)

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
