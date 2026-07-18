# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-17 (sessão 18: 10 specs `approved` + ordem;
> **embeddings-provider `done`** (Jina) + **playtest-stop-gameover `done`**
> (smoke real 3/3) + **combate-lifecycle `done`** + **pos-saque-recuperacao
> `done`** (poção+carência+beat de recuperação; smoke real ✓); 835 offline verdes)

---

## TL;DR — Em que pé está

**Sessão 2026-07-17 (18): 10 SPECS APROVADAS + ORDEM + EMBEDDINGS MULTI-PROVIDER** —
1. **Todas as specs pendentes viraram `approved` com ordem de dev cravada no
   header de cada uma.** Duas fases:
   - **Sistema de classes (2 specs, ordem #1→#2):**
     [refatoracao-sistema-classes](specs/refatoracao-sistema-classes.md) →
     [arvores-habilidade-classes](specs/arvores-habilidade-classes.md)
     (a 2ª depende do motor de Entropia/Carga da 1ª).
   - **Playtest longo (8 specs, ordem #1→#8):**
     [embeddings-provider](specs/embeddings-provider.md) →
     [playtest-stop-gameover](specs/playtest-stop-gameover.md) →
     [combate-lifecycle](specs/combate-lifecycle.md) →
     [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) →
     [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) →
     [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) →
     [encontros-dedupe](specs/encontros-dedupe.md) →
     [polish-prosa](specs/polish-prosa.md).
2. **[embeddings-provider](specs/embeddings-provider.md) `done`:** `rag.py`
   ganhou cadeia multi-provider
   `EMBEDDING_ROUTES = [jina, openai, ollama, gemini]` (Gemini é o ÚLTIMO
   fallback). Cada índice FAISS grava `embeddings_meta.json` e fica **PINADO**
   ao provider que o gerou (nunca mistura vetores); provider indisponível →
   índice DESATIVADO com warning (nunca crash). `RPG_EMBEDDINGS=<p>` força.
   `get_embeddings_for(p)` abre índice pinado; write deriva provider de
   `_resolve_provider()` (puro, sem global vazável). `codex_loader.ingest_codex`
   grava meta também. **+12 `test_embeddings_provider`**; seam de
   `test_npc_memory` migrado p/ `_EMBEDDING_BUILDERS` (pin não passa mais por
   `get_embeddings`). `.env.example` ganhou `JINA_API_KEY`/`RPG_EMBEDDINGS`.
   **RAG VIVO:** re-index real com Jina executado (lore 2203 chunks + regras,
   meta jina); smoke §6 3/3 (queries PT-BR sem 429 + memória de sessão).
   ⚠️ Free tier Jina = **100k tokens/min**: re-index do Codex esgota o minuto,
   regras precisaram de ~70s de espera (não é erro).
3. **[playtest-stop-gameover](specs/playtest-stop-gameover.md) `done`:**
   harness agora PARA no `game_over` (turno da morte é o
   último; `aborted_reason="player_death (turno N)"`) — antes rodava 140/300
   turnos mortos poluindo p50/rotas/custo. **Rota fiel:** `_run_turn` captura a
   decisão do `dm_router` via streaming multi-modo (`updates`+`values`), não o
   `next` final (combate/loot sobrescreviam); combate ativo na entrada = rota
   `combat_agent`. Fallback pro `invoke` quando o grafo não tem `.stream`
   (wrappers de teste). `telemetry` ganhou `death_location`/`death_cause`;
   `report` ganhou seção **Mortes** (turno/local/causa). **+8
   `test_playtest_harness`.** Validação mock: 12 perfis × 50t = **552 turnos
   vivos, 0 rota vazia** (antes o perfil `combate` registrava só storyteller).
   ⚠️ Fix colateral: run mock agora desliga embeddings reais
   (`_offline_embeddings`) — com Jina viva no `.env`, o archivist batia na API a
   cada turno (rede/rate limit → timeout). **Smoke §6 real 3/3:** combate morreu
   no t14, run PAROU (aborted player_death), routes com combat_agent=6, p50=14s
   sem turnos de 1ms, $0.04 (deepseek 49 + groq 5).
4. **[combate-lifecycle](specs/combate-lifecycle.md) `done`:**
   o router ganhou **gate determinístico de combate**
   (`_combat_gate`): com `combat.active`, viagem NÃO teleporta — vira tentativa
   de fuga (R1: flag `combat_flee_attempt`+destino; sucesso aplica
   `apply_travel` no mesmo turno, enredado falha e inimigos agem); npc/loot são
   bloqueados → `combat_agent` (R2); combate órfão (idle_turns) expira em 3
   turnos (R3). `combat_node` zera `idle_turns` e SEMPRE zera `active` no fim
   (R5 — antes fuga com inimigo vivo deixava flag zumbi). Nova invariante
   `combat.zombie` (R4, `error`, idle≥5). `state.py` documenta `combat.idle_turns`
   + `combat_flee_attempt`/`combat_flee_destination`. **+10
   `test_combat_lifecycle`.** Harness mock 12×50t: **492 turnos, 0 combat.zombie,
   maior sequência de combate ativo = 4t (era 59)**. Smoke §6 real: "Viajo para
   X" em combate → narrou FUGA e viajou só após escapar (nunca teleporte),
   combate limpo.
5. **[pos-saque-recuperacao](specs/pos-saque-recuperacao.md) `done`:** o Saque
   deixa de ser espiral de morte. `apply_downed` agora deixa **1 poção de cura**
   (R1) + marca `downed_recente` (R4) + **carência de 1 dia** no local seguro
   (`downed_grace_until_day`, R2: storyteller não sorteia encontro em zona segura
   durante a carência; ir pro perigo cancela). `campaign_manager` prefixa um
   **beat de recuperação determinístico** ("Recupere forças em {local}", R3);
   `apply_rest` remove a marca; storyteller ganha cláusula de prompt de
   recuperação (R4). Invariante `downed.no_recovery_path` (R5, warning).
   **+13 `test_pos_saque`.** Harness 3 seeds: 0 violações, sobrevivência muito
   além do baseline 1-4t. Smoke real: poção+beat+narração ✓.
6. **Suíte:** 822 → **835 offline verdes** + 1 skip.

**Próximo:** ordem de dev #5 —
[npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) (fim do "Ninguém responde.").

---

**Sessão 2026-07-17 (17): CRIAÇÃO DE PERSONAGEM IMERSIVA ENTREGUE** —
1. **[onboarding-valoria](specs/onboarding-valoria.md) `done`:** criação virou
   wizard de 5 passos com lore curado — `data/onboarding.json` (intro de
   Valoria + 12 regiões + 10 classes + 6 raças; cards de região com
   `name`/`bonus` espelhados de `origins.json`, teste anti-drift),
   `GET /data/onboarding`, `CreateScreen.tsx` reescrito (cards clicáveis,
   stepper com navegação livre, fallback pro form clássico se o endpoint
   faltar). Smoke de UI: **15/15 checks** via Playwright (estado preservado ao
   voltar, "Pular introdução", mobile 390px sem overflow). Autoria dos cards:
   `docs/AUTORIA.md` § Fluxo D.
2. **[inicio-personalizado](specs/inicio-personalizado.md) `done`:**
   `POST /game/prologue` (1 chamada SMART + guard → template determinístico,
   nunca 500; entra no rate-limit) gera prólogo confirmável;
   `/game/new` com `scenario` (re-validado na borda — 422 p/ excedente) semeia
   `campaign_plan` pessoal que sobrevive ao 1º invoke, capítulo 1 da crônica
   com o arco pessoal, NPCs `in_scene`/`known_by_player` (alvo válido da rota
   NPC no turno 1) e a `HumanMessage` de abertura com o brief da cena. Passo 6
   do wizard: loading temático + **Refinar** + **Começar a jornada**. Sem
   scenario = fluxo clássico byte a byte (CLI intacta).
3. **Achado do smoke real (padrão p/ TODO schema novo de structured output):**
   `max_length` duro no schema voltado ao LLM derruba TODOS os candidatos por
   validação — DeepSeek escreveu `climax` > 300, Anthropic `attitude` livre
   ("ambígua e transacional"), Groq 400 `tool_use_failed` — e o guard caía
   sempre no template. Fix: schema do LLM com tamanho só na *description*;
   truncagem/normalização determinística em `_normalize`; limites ESTRITOS só
   na borda da API (`StartScenarioIn`). **MockLLM não pega isso** (fixture
   sempre válida) — validar schema novo com chave real segue obrigatório.
4. **Suíte:** 769 → **792 offline verdes** (+10 `test_onboarding`, +13
   `test_prologue`; 1 skip pré-existente). `npm run build` verde. Smoke real
   §6 no DeepSeek executado (~$0.02): arco "O Nome Manchado" com 2 NPCs,
   abertura NA cena do brief, NPC semeado responde no turno 1.

**Sessão 2026-07-14→16 (16): DEEPSEEK PRIMÁRIO + PLAYTEST LONGO + 8 SPECS** —
1. **Roteamento:** DeepSeek agora é o candidato Nº 1 em **TODOS os tiers**
   (`llm_setup.ROUTES`; decisão do usuário pós-playtest — prosa muito melhor,
   ~$0.001/turno). Groq free segue de fallback vivo em todos.
2. **Playtest longo REAL** (explorador/combate/quester × 100 turnos, ~$0.25,
   zero erro de turno): análise completa em
   **[docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md)**.
   Destaque: quester 7/7 quests, level 5, arco da Thrace excelente — mas 1
   local em 100 turnos. 7 defeitos priorizados (harness sem stop no game_over,
   espiral pós-Saque, combate zumbi 59 turnos, segredo vazando via beat,
   "Ninguém responde." com aliado em cena, beat em inglês, NPC reciclado).
3. **Todos os achados viraram specs `draft` (aguardando aprovação):**
   [playtest-stop-gameover](specs/playtest-stop-gameover.md) ·
   [combate-lifecycle](specs/combate-lifecycle.md) ·
   [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) ·
   [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) ·
   [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) ·
   [encontros-dedupe](specs/encontros-dedupe.md) ·
   [polish-prosa](specs/polish-prosa.md) ·
   [embeddings-provider](specs/embeddings-provider.md).
4. **Embeddings:** Google 429 "prepayment credits depleted" desde 2026-07-14 —
   RAG global + memória de sessão MORTOS. Pesquisa feita (DeepSeek NÃO tem
   embeddings): recomendação = **Jina v3** ($0.02/M + 10M tokens grátis,
   PT-BR forte) com opção local Ollama `bge-m3` — spec embeddings-provider.

5. **Criação de personagem imersiva (2026-07-16): 2 specs `approved`** —
   viraram `done` na sessão 17 (ver TL;DR acima).

**Histórico recente** (detalhe SÓ no `CHANGELOG.md`):
- 2026-07-13 (15): ciclo de produto EXECUTADO — balanceamento-early-game
  ("O Saque" + tuning nível 1 + replan por região) · streaming-turno-sse ·
  polish-sessao, todas `done`; 729 → 769 offline verdes
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
uv run pytest                        # 792 testes offline verdes (contratos de LLM ficam fora)
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

**LLM providers:** default = `ROUTES` multi-provider com fallback — **DeepSeek
é o primário em TODOS os tiers** (2026-07-16; tem saldo e roda o jogo inteiro a
~$0.001/turno); Groq free é o fallback vivo. `LLM_PROVIDER=gemini` força
só-Gemini; sem chave nenhuma → MockLLM (jogável sem rede). Contas: minimax 402,
qwen 401 — OPCIONAL resolver (assumem quando tiverem saldo/key; não é bug).
Ver `.env.example`.

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
- **Criação imersiva (sessão 17):** wizard 5 passos com lore curado de Valoria
  (`data/onboarding.json` + `GET /data/onboarding`) + prólogo confirmável
  (`POST /game/prologue`) que semeia arco pessoal, NPCs da história e cena de
  abertura no `/game/new` — fluxo sem scenario/CLI intactos
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

**Achado (pré-existente, agora visível com RAG vivo):** o archivist às vezes
recebe do LLM `MemoryUpdate.important_facts` como lista de **dicts**
(`{role,content}`) em vez de strings → 4 validation errors do Pydantic, cai no
**fallback de texto** (fatos/crônica do turno perdidos). Não derruba o turno
(guard OK), mas perde memória. Candidato a fix num passe do archivist (coagir
para string no schema/normalização). Visto nos smokes reais do #2 e #3.

**Pendências abertas (não são bugs de código):**

- Action `validate.yml` verde no primeiro push (conferir no GitHub)
- Lote 2 de traits (40 → 80 em `data/traits.json`)
- 1 flaky isolado na suíte (sessão 8; 3 runs verdes depois — observar)
- Curadoria: NPCs públicos do norte citam a Rede Carmesim (timeline era-7 é
  `hidden`) — ver ROADMAP § Fase 7
- Cache runtime (`data/bestiary.json`/`npc_database.json`) é gravado por suíte/
  smokes com entradas mock (ex.: HP regredido, "Unknown") — hoje é `git checkout`
  manual antes do commit; considerar isolar cache de teste (observado na sessão 15;
  re-confirmado na 16: run real gravou "Afogado" com região fora do grafo →
  2 testes de `test_fase25b` vermelhos até o checkout)
- **Achados do playtest longo (sessão 16)** — 7 defeitos/melhorias priorizados
  em [docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md):
  harness sem stop no game_over · espiral pós-Saque · combate zumbi (59 turnos
  ativo) / viagem durante combate · vazamento de segredo via beat do
  campaign_manager · "Ninguém responde." com aliado em cena · beat em inglês ·
  encontro reciclado. **Todos viraram specs `draft` em 2026-07-16** (ver TL;DR).
- **Embeddings:** ✅ RESOLVIDO (spec embeddings-provider `done`). Jina é o
  primário; índices lore/regras re-indexados com meta jina, RAG vivo. Free tier
  Jina = 100k tokens/min (re-index do Codex esgota o minuto — espaçar). Trocar
  provider = re-rodar `uv run python rag.py`.

Fechadas na sessão 15: confirmação real do Verme ✔ · mortes nível 1 do
`combate`/`agressivo` ✔ (spec balanceamento; nota: 2ª queda DELIBERADA sem cura
segue matando — por design) · replan em toda viagem ✔ · **spec 2.5b virou
`done`** (2026-07-14: smoke real §6 3/3 — raça Cinzéu com traits, viagem com
lore de Skallgard, tático foge com HP baixo + alerta; era a última spec não-done).

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
