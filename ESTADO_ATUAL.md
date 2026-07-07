# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-06 (sessão 12: FASE 5 completa —
> harness de playtest + invariantes + telemetria; 3 specs `done`, smoke real OK)

---

## TL;DR — Em que pé está

**Sessão 2026-07-06 (12): FASE 5 (Agentic playtest + telemetria) INTEIRA — 3
specs `done`.** 656 → **699 testes offline verdes** (+43:
`tests/test_fase51/52/53.py`) + build implícito + **smoke com LLM real
executado**. Pacote novo `playtest/`:
- **5.1 harness** ([spec](specs/fase-5.1-playtest-harness.md)): `runner.py`
  (`run_campaign` via `app.invoke` — MESMO caminho da API; saves isolados em
  `saves_playtest/` por monkeypatch de `persistence.SAVES_DIR`; RNG global
  semeado p/ reproduzir MockLLM+combate + `random.Random(seed)` próprio do
  perfil; exceção de turno NÃO derruba a campanha) + `profiles.py` (10 perfis
  determinísticos `next_action(state, rng) -> str`: agressivo/explorador/
  comerciante/diplomatico/troll/mapa_breaker/combate/npc_only/loot_abuser/
  secret_rusher). CLI `python -m playtest run --profile X --turns N [--all]
  [--real]`. Teste permanente na suíte (10 turnos explorador).
- **5.2 invariantes** ([spec](specs/fase-5.2-invariantes.md)): `invariants.py`
  puro — `check_all(state, prev, turn)` + `assert_invariants` (levanta legível).
  Checks: vitals (HP/mana/stamina em [0,max]; hp=0⇒game_over), economia (ouro≥0,
  qty≥1, sem dupe em slot, item único ≤1 lugar no mundo), entidades (NPC/companion
  morto no event_log não fica em cena/ativo), mundo (local existe no grafo, visited
  ⊆ nós, fação `defeated` não controla, relógio monotônico via prev_state),
  conhecimento (frases-assinatura dos 4 segredos canônicos — curadas dos docs
  `hidden`; `secret_revealed`/facts desarmam; severidade `warning` no 1º ciclo),
  roundtrip save→load (fora do loop por-turno; I/O). Plugado no runner
  (`--invariants` default ON; violação vai p/ `CampaignResult.violations`, não para
  a campanha; severidade `error` conta no exit code).
- **5.3 telemetria** ([spec](specs/fase-5.3-telemetria-relatorio.md)):
  `telemetry.py` (JSONL 1 linha/turno com shape do log da Fase 10 + campos de
  playtest + provider/modelo/tier/`fell_back`/`cost_usd`; `summary.json` por
  campanha) + `report.py` (`aggregate` cruza campanhas do run + `render_markdown`
  com per-perfil/violações/erros/custo + `--baseline` → deltas) + `pricing.py`
  (custo ESTIMADO: o hook não dá tokens → tokens fixos/invoke × preço por modelo;
  MockLLM = 0). CLI `python -m playtest report <run_id>`. Tetos
  `--max-requests`/`--max-cost` abortam o `--real` educadamente (`aborted_reason`).
  Runs em `playtest_runs/` (gitignored).

**SMOKE REAL EXECUTADO (2026-07-06):** `run --profile secret_rusher --turns 4
--real` — completou 4 turnos, `erros=0`, `violações=0/0` (R5 vigiou o narrador de
verdade: perguntou direto pelo pacto de Valerius/Rede Carmesim/Arauto/Rei
Subterrâneo e NÃO vazou). Telemetria real: `providers deepseek=5/groq=9`,
`fell_back_turns=4`, custo por tier, latência p50≈15s. **Fallback vivo:**
`minimax` (402 saldo) e `qwen` (401 key) caíram no próximo candidato → turno
completou no Groq/DeepSeek. Falhas de conta conhecidas, NÃO bug (ver ⚠️ da sessão 11).
**Rodada mock `--all --turns 50 --seed 42`:** 10/10 perfis `erros=0` +
`violações=0/0` — motor sólido. Achados (mock, NÃO produção — report marca
`mock: true`): `agressivo` morre no nível 1; `explorador` visita 13 locais/nível 3;
`loot_abuser` acumula 297 ouro; **nenhum perfil completa quest** (created=1/
completed=0 em todos). **Diagnóstico (2 achados = artefato do mock, NÃO bug):**
(a) quests nunca fecham porque `quest_completed` é 100% proposto pelo LLM
(`storyteller.py:356`) e o MockLLM propõe sempre a MESMA quest
(`mock_llm.py:191`, deduplicada) mas nunca a conclusão → **só testável no `--real`**;
(b) letalidade de `agressivo`/`combate` vem do spawn/stats do MockLLM, não da
produção. Ambos: validar no playtest `--real`.

**SUÍTE DE PLAYTEST REAL (`-m llm_playtest`, 700 testes com o +1 de regressão):**
`tests/test_playtest_real.py` — 10 perfis jogam campanha curta no LLM real (ROUTES;
Groq free basta), asserta `mock=False` + `erros=0` + zero violação `error` + R5
sem vazamento. FORA do pytest default (`addopts -m "not llm_playtest"`). **Rodou os
10 perfis (4 turnos, seed 7): 97 req groq / 38 deepseek / 16 gemini, ~US$0.10 total,
fallback vivo em todo turno (minimax 402 / qwen 401 → próximo).** **BUG REAL ACHADO
E CORRIGIDO:** perfil `troll` (emoji/SQL/injeção) dava **3 erros** `KeyError('none')`
— o LLM real classifica lixo como `RouteType.NONE = "none"`, que NÃO é nó do grafo
(o mapping de `main.py` só tem storyteller/combat/npc/loot/END) → o router devolvia
`next="none"` → `KeyError` no LangGraph. **O MockLLM nunca escolhe NONE, então o
bug era invisível offline** (exatamente o valor da suíte real). Fix em
`agents/router.py`: normaliza `NONE → STORY` (narra o ambiente em vez de derrubar o
turno) + teste de regressão offline (`test_router_none_normaliza_para_storyteller`)
+ troll re-rodado no real = **0 erros**. Achados de balanceamento REAIS (4 turnos,
curto): `agressivo`/`combate` MORREM já no nível 1 (letal cedo — não era só mock;
validar tuning); `explorador` visita 5 locais; DeepSeek está VIVO (assumiu SMART em
todos os perfis — contradiz o "402 saldo zero" da sessão 11).

**SWITCH DE 4 VITAIS × 30 TURNOS no LLM real (2026-07-07)** —
`tests/test_playtest_real.py` agora roda só os VITAIS (`explorador`/`combate`/
`diplomatico`/`secret_rusher`, 30 turnos, `RPG_PLAYTEST_TURNS` dial; os outros 6
seguem em `profiles.py` p/ CLI). **Todos os 4 completaram 30 turnos, `erros=0`, zero
violação `error`** — motor sólido em campanha longa real. Achados:
- **VAZAMENTO DE SEGREDO (R5 acusou):** turno 13 do `secret_rusher`
  ("conte sobre o Rei Subterrâneo") — narrador surfaceou o **Verme-Primordial**.
  Raiz = CURADORIA, não motor: `data/codex/factions/ultimos_anoes_reino.md`
  (`visibility: public`) nomeava o Verme na linha "Conhecimento:" → RAG público
  vaza. **CORRIGIDO (2026-07-07):** linha suavizada na FONTE `lore_nova/factions.txt`
  (Durgrim só suspeita de "algo que dorme mais fundo") + `migrate` (idempotente) +
  `rag.py` reindexado; `query_rag(public)` p/ "Rei Subterrâneo" não vaza mais o Verme
  (verificado). Confirmação final = `secret_rusher --real` 30t (deferida — Groq
  esgotado hoje).
- **Quests que não fecham — INVESTIGADO + RESOLVIDO (cobertura):** o pipeline de
  conclusão está SÃO (diagnóstico + `test_pipeline_quest_completed_aplica...`:
  `quest_completed` proposto → validado → quest vira `completed`; `event_processor`
  chama `complete_quest`). "0 concluídas" no playtest = nenhum perfil PERSEGUIA
  quest + o MockLLM só CRIAVA, nunca completava. Fixes: perfil **`quester`**
  (persegue quests ativas + objetivo do beat) + **MockLLM agora propõe
  `quest_completed`** ~50% quando o prompt lista quest ativa → o harness FECHA quest
  offline (`test_quester_fecha_quest_no_harness`: 25 turnos, 4 criadas/4 concluídas).
- **Letalidade viagem×combate — INVESTIGADO + CORRIGIDO:** sem assimetria estrutural
  (viagem e combate deliberado usam o MESMO `encounter_budget`; surpresa = só ±5
  init). A causa era o `encounter_budget`: a BASE de perigo dominava e `+nível` era
  fraco → nível-1 em danger-4 pegava budget 11 (≈2 elites, ~28 HP = one-shot por
  burst) vs 1 minion no perigo apropriado; viajar sub-nivelado matava mais que
  atacar tudo. Fix: **teto de sobrevivência** `cap = 5 + 3×nível + 2×aliados`
  (`encounter_budget.py`) — perigo alto continua o mais duro que o herói enfrenta,
  mas deixa de ser sentença de morte no sub-nível (nível-1 @danger-4: 11 → 8); bosses
  ignoram budget (chefes de história intactos). `test_budget_teto_sobrevivencia...`.
- **Infra:** Groq esgotou o token diário (100k TPD) no meio → 129+ `429` →
  fallback p/ gemini/deepseek em TODO turno (`fell_back=30/30`); tudo completou via
  guard. Custo ~US$0.32 nos 4; latência p95 33-46s (throttling infla). **Lição:**
  free tier não sustenta sessão real de 120 turnos — playtest real grande precisa de
  tier pago ou espalhar por dias.

**Bugs de conteúdo/motor achados pelo playtest e CORRIGIDOS (2026-07-07):**
(1) **rota `NONE` → `KeyError('none')`** no `troll` (LLM real classifica lixo como
`RouteType.NONE`, que não é nó do grafo) — `agents/router.py` normaliza NONE→STORY;
(2) **vazamento do Verme-Primordial** (segredo do Rei Subterrâneo) — 3 causas:
doc de fação `ultimos_anoes_reino` público nomeava o Verme (fonte suavizada);
**bug de parse do migrate** (`parse_categoria_blocks` parava só em `[CATEGORIA:` →
OS GIGANTES engolia 337 `[CRIATURA:]` num doc público de 1613 linhas — agora para
em `[CRIATURA:/MATERIAL:/ITEM:` também, doc caiu p/ 33 linhas); Verme vira
`visibility: hidden` via `codex_overrides.yaml`; (3) **Legião de Ferro** afirmava o
"pacto com Daruun" como fato (fonte reframada p/ suspeita). RAG público reindexado
e verificado limpo nos 3. `validate_content.main` passou a resolver overrides ao
lado do codex (isola fixtures de teste). **703 testes offline verdes.**

**Próximo:** confirmação real do Verme (`secret_rusher --real` 30t, quando Groq
resetar); depois Fases 8+ (arte/sprites) ou Fase 10b (Postgres/auth).

**Sessão 2026-07-06 (11): ROTEAMENTO MULTI-PROVIDER implementado
([spec](specs/roteamento-multi-provider.md) `approved`).** 629 → **656 testes
offline verdes** (+26: `tests/test_routing.py` fakes de fallback +
`tests/test_routing_tiers.py` tier por nó). `llm_setup.py` reescrito:
`ModelTier` ganhou **CLASSIFY** (`CLASSIFY < FAST < SMART`); `get_llm(tier)`
agora devolve um **`RoutedLLM`** que embrulha uma LISTA ordenada de candidatos
`(provider, modelo)` (`ROUTES`) e cai pro próximo em QUALQUER falha
(429/500/timeout/dep faltando/sem key); esgotou todos → `AIMessage(content="")`
(NUNCA levanta — sites plain-invoke caem no fallback determinístico, structured
batem no guard). Convenção CRÍTICA intacta (RoutedLLM `is_fallback=False`, não
mascara nada). `_build_openai` parametrizado por provider (base_url/key própria:
Groq/Qwen/GLM/MiniMax/Kimi/DeepSeek reusam; endpoints em `PROVIDER_ENDPOINTS`);
`_build_anthropic` novo (extra `uv sync --extra anthropic`, ausência da dep =
candidato pulado). **Overrides:** `RPG_FORCE_MOCK` (mock); `LLM_PROVIDER=gemini|
ollama|openai` força provider único p/ TODOS os tiers (ignora ROUTES — use p/
jogo só-Gemini/local); sem key nenhuma → MockLLM (zero-config) ou FallbackLLM
(`RPG_NO_MOCK`); `RPG_ROUTES=<json>` troca a stack sem deploy. **Telemetria:**
`set_llm_telemetry_hook(fn)` → `(provider, model, tier, latency_ms, fell_back)`
por invoke (canal da 5.3; no-op default). **Cache** por `(provider, model,
temp)` (lazy). **Migração de tiers (Etapa 2):** router/combat-parse/loot-parse/
librarian → **CLASSIFY**; storyteller/combat-narração/npc/loot-narração/
world_simulator → **FAST**; campaign/archivist/character_creator seguem **SMART**
(`test_routing_tiers.py` blinda cada nó). **Contratos (Etapa 3):** os 9 da Fase
11 forçam `LLM_PROVIDER=gemini` (ROUTES default não tem Gemini em FAST/SMART);
novo contrato por-provider R10 (`RPG_CONTRACT_PROVIDERS=groq,gemini ...`)
constrói o client direto e asserta instância Pydantic no parse do router.
**SMOKE REAL EXECUTADO (2026-07-06):** contrato R10 por-provider + 1 turno vivo
na stack ROUTES. **Funciona fim a fim** — turno real gerou narração completa
("A névoa fria da manhã que paira sobre Nova Arcádia...") + campanha 5 beats;
telemetria mostrou `classify→groq/gpt-oss-20b`, `fast→gemini-flash` (fell_back),
`smart→anthropic`+`gemini-pro` (fell_back). **Fallback vivo comprovado.**
Achados do smoke que viraram fix/decisão de ROUTES:
- **Groq strict json_schema** rejeitava `StoryUpdate` (payload = dict aberto).
  **FIX:** `RoutedLLM._apply` injeta `method="function_calling"` p/ todo provider
  OpenAI-compat (`_OPENAI_COMPAT_PROVIDERS`) → Groq parseia QUALQUER schema. Com
  isso há candidato **Groq GRÁTIS em todos os tiers** → jogo roda 100% no free
  tier do Groq (2º smoke: turno inteiro em `gpt-oss-20b`/`llama-3.3-70b`/
  `gpt-oss-120b`, gemini/anthropic nem tocados). Não precisa provider pago.
- **Anthropic (claude-sonnet-5)**: rejeita `temperature` (removido do
  `_build_anthropic`) e **prefill** (falha quando o prompt termina em `AIMessage`,
  ex.: archivist → cai no fallback). OK em nós que terminam com humano.
- Groq `moonshotai/kimi-k2*` = 404 (sem acesso nessa conta) → fora do ROUTES.
- **ROUTES final:** CLASSIFY `groq gpt-oss-20b → gemini flash-lite`; FAST
  `minimax → qwen → groq llama-3.3-70b → gemini-flash`; SMART `deepseek → groq
  gpt-oss-120b → anthropic → gemini-pro`. Groq grátis é o fallback de todos.
**⚠️ Contas de provider (ação OPCIONAL do usuário, NÃO é bug de código):**
`groq`/`gemini`/`anthropic` OK; `minimax`+`deepseek` = 402 saldo zero; `qwen` =
401 key/região (endpoint Internacional; key de Pequim é rejeitada). NÃO precisa
resolver p/ jogar — Groq cobre tudo de graça; os pagos só ASSUMEM quando
tiverem saldo/key (são preferidos na ordem do ROUTES).
**⚠️ Jogar só com Gemini:** `LLM_PROVIDER` VAZIO usa ROUTES; p/ forçar só-Gemini
use **`LLM_PROVIDER=gemini`**. **Próximo:** Fase 5 (playtest + telemetria —
roda sobre o hook `set_llm_telemetry_hook`).

**Sessão 2026-07-06 (10): 4 specs implementadas — fase 10 (hardening local),
fase 11 (LLM contract tests), mapa (interiores + viagem variável) e NPCs 3
camadas + traits.** 581 → **629 testes offline verdes** + **9 contratos verdes
contra Gemini REAL** + build web + smoke real de interior.
**Fase 10 (local):** `persistence.save_path()` valida UUID (fecha path
traversal de `game_id=../.env` — endpoints devolvem 400); saves com
`schema_version` + pipeline `_MIGRATIONS` (v0→v1 consolida backfills
3.1/4.1/4.3/4.5 que viviam espalhados no load; v1→v2 = campos de NPC); CORS
por env (`RPG_CORS_ORIGINS`, default localhost); rate limit por IP em memória
(`RPG_RATE_LIMIT`, 0 desliga — conftest desliga na suíte); log JSON por turno
no stderr (logger `rpg.turn`). Postgres/auth = Fase 10b (sem demanda ainda).
**Fase 11:** `uv run pytest -m llm_contract -v -s` = 9 contratos contra o
provider real (router×2, StoryUpdate banal não alucina evento, combate, NPC
não-onisciente com fato sintético, TradeIntent qty=2, e2e+archivist, loot,
fallback RPG_NO_MOCK offline); fora da suíte default via addopts; substitui
`tests/test_real_llm.py` (removido; `--ignore` saiu de /qa, /wrap-up e CI).
Achado do 1º run: fixture legada de inventário (strings) quebrava loot — era
estado de teste (save real chega migrado), corrigido.
**Mapa:** `travel_times` por conexão (anéis de Nova Arcádia custo 0 — relógio
PARADO; Skallgard↔Montanhas 2; Brekmar↔Ophidia 3; default 1) + 5 nós
`kind: interior` (Taverna do Javali Dourado/Grum, Cripta dos Afogados, Salão
do Jarl, Câmara Seca de Aethelgard/Aelwin, Forja Profunda) — custo 0, sem
clima (tag abrigo), sem encontro de viagem, fora do mapa-múndi (aparecem como
chips "Locais daqui" no PlayScreen + "Sair para <pai>"); registrados em
`entities_extra.json`; fações avançam pelo CUSTO real da viagem.
**NPCs 3 camadas:** `services/npc_layers.py` + `data/traits.json` (40 traits,
lote 1) — sorteio seeded por npc_id+game_id (replay estável), revelação por
`interaction_count >= reveal_after` (nota *(Você percebe...)* na resposta),
`trait_dc_modifier` já usado no gate de recrutamento 4.5 (desconfiado exige
mais, sentimental menos — ocultos CONTAM); gate camada 3: NPC `in_scene=False`
→ "X não está aqui" + onde foi visto, SEM request de LLM (fecha o bug "NPC
errado responde"); viagem zera a cena (exceto party); entrada/saída de cena
via `introduced_npcs` (reuso)/`npcs_left_scene` (novo) no StoryUpdate;
`hidden_traits` nunca sai por API/prompt/frontend (testado); aba Personagens
mostra traits revelados + "ouviu falar". Smoke real: entrar na taverna com
Gemini vivo = relógio parado + narração de chegada; Gemini re-introduziu NPC
conhecida na cena nova (canal ok; vigiar em playtest).
**Próximo:** Fase 5 — agentic playtest + telemetria (specs a escrever).
Pendências menores: Action `validate.yml` verde no primeiro push; playtest de
balanceamento da Fase 4; lote 2 de traits (40→80).

**Sessão 2026-07-05 (9): FASE 7 (Pipeline de autoria + validação) INTEIRA — 3 specs `done`.**
520 → **581 testes offline verdes** + lint do repo 0 ERROs + reindex FAISS feito +
**smoke real executado** (não-vazamento fim a fim: narrador Gemini descreveu
Valerius só pela persona pública; `query_rag` public não devolve o pacto, hidden
devolve — a cerca funciona nas duas direções).
**7.1 lint de conteúdo:** `services/content_validator.py` puro (frontmatter, ids
únicos, referências/constraints de edges, aliases normalizados, visibilidade,
encoding UTF-8 + heurística de mojibake) + CLI `scripts/validate_content.py`
(exit 1 com ERRO) + gate `test_repo_content_sem_erros` nos dados reais (repo
passou limpo, whitelist vazia) + CI `.github/workflows/validate.yml` (pytest em
push/PR — conferir Action verde no primeiro push).
**7.2 autoria migration-safe:** `data/codex_overrides.yaml` — patches por id que
o migrate reaplica após regenerar (aliases/tags_extra/visibility/related_entities/
append_body, refletem também em entities.json); arquivos `curated: true`
sobrevivem ao delete loop; validador `overrides` (órfão = ERRO, override em
curated = AVISO, curated registrável sem entidade = AVISO); `rag.py` ganhou
`reindex_global()` com gate de lint — conteúdo inválido nunca entra no FAISS;
6 templates em `docs/templates/codex/` + fluxos em `docs/AUTORIA.md` (CLAUDE.md
aponta). Migrate 2× = idempotente; smoke real: NPC de teste via template passou
no lint, apareceu em `load_entities()` e sobreviveu ao migrate.
**7.3 segredos de NPC:** `split_npc_secrets` no migrate divide o corpo por rótulo
de parágrafo (`NPC_SECRET_LABELS` vive em content_validator, compartilhada com o
lint) → doc paralelo `npcs/segredos/{id}_segredo.md` com `type: npc_secret` /
`visibility: hidden`, sem registrar entidade; 141 NPCs, 14 com doc de segredo;
lint anti-regressão (rótulo secreto em NPC público = ERRO; npc_secret público =
ERRO). **Auditoria achou e fechou vazamento real:** o doc público do Daruun
contava o pacto com Valerius no parágrafo "Natureza:" — corrigido na FONTE
(`lore_nova/npcs.txt`, frase movida p/ parágrafo "Segredo:"); lista de rótulos
cresceu 8→15 na auditoria ("identidade real", "a verdade", "o que nao diz"...).
Pendência de curadoria: NPCs públicos do norte citam a Rede Carmesim enquanto a
timeline era-7 é `hidden` — ver ROADMAP § Fase 7.
**Próximo (na época):** Fase 5 — agentic playtest + telemetria.

**Sessão 2026-07-05 (8): FASE 6 (Conteúdo sistêmico) INTEIRA implementada — 5 fatias.**
461 → **520 testes offline verdes** + build web + smoke_api + **smoke com LLM REAL
executado — 5 specs `done`**. Smoke real validou em jogo vivo: miasma NEGOU o
descanso (HP intacto + noite narrada); viagem transicionou o clima
(miasma→neblina) e disparou encontro com SURPRESA real (neblina −3 derrubou a
detecção; Afogados agiram antes, init 21/13 vs 7); Adaga de Vidro-Dragão obtida
por narrativa → claim engine → milestone "não há outro no mundo"; tentativa de
SEGUNDA adaga barrada pelos DOIS caminhos (items_gained e loot — pool entregou
Musgo Cinzento no lugar); tabelas regionais em uso (Kit Médico do pool do
Pântano). **3 fixes de robustez achados no smoke** (MockLLM escondia):
StoryUpdate.narrative agora tem default + fallback digno com as notas mecânicas
(Gemini às vezes omite o campo — turno não morre mais); _narrate do loot
normaliza content em parts (lista) do Gemini; find_travel_destination faz fold
de acentos ("Pantano" casa "Pântano" — viagem não falha mais silenciosa).
Pendência residual: proposta espontânea de route_blocked pelo LLM não ocorreu no
smoke (canal idêntico ao já validado na 2.6; motor 100% coberto offline);
1 flaky isolado na suíte (3 runs verdes depois — observar).
**6.1 economia viva:** `route_blocked/cleared` no pipeline 2.6 (validator exige
conexão direta do mapa); escassez por ALCANÇABILIDADE (BFS − rotas bloqueadas):
produtor local ×0.6, alcançável ×1.0, isolado ×1.8 e some da loja; regra 2.7
"porto hostil → rotas bloqueadas" (conditions novas `target_map_tag`/
`new_controller_hostile`, targets `map_connections`); WorldMap traceja a rota.
**6.2 itens únicos:** 20 artefatos do Codex (10 raros/7 épicos/3 lendários, ~2 por
região, anti-spoiler) com `unique: true`; posse = fato do mundo
(`unique_item_claimed/lost`, gate `source=engine` — LLM nunca decide); gates em
loot/loja/craft/narrado; vendeu → mercador segura (recompra rastreada); milestone
na crônica; ◆ no HUD.
**6.3 migração de monstros:** `services/ecology.py` — `bestiary_knowledge` (3.2) é
o censo; pressão de caça com decay (6 kills → peso 0.1; parar de caçar devolve),
fação no controle ×2, migrante de região conectada (rotas 6.1 barram); loot
regional perde drops de criatura suprimida; Codex mostra raridade.
**6.4 encontros sistêmicos:** `detection_check` d20+WIS vs DC 8+2×danger →
surpresa (±5 iniciativa, flag one-shot); tipos combate/armadilha/social/rastro
por danger (reforço/fação = combate sempre); armadilha 100% Python (`traps.json`,
condições 4.2, XP 25 na esquiva); rastro alimenta Codex + pista de tesouro
(TREASURE seguinte rola banda alta); social = cena negociável. Zero LLM novo.
**6.5 clima mecânico:** `weather.json` com cadeias de Markov por região; efeito é
LEITURA (`weather_effects`), nunca condição gravada; neblina −detecção, nevasca
+1 período de viagem, miasma NEGA descanso ao relento e morde 1 HP/round outdoor
(abrigo anula), chuva −1 acerto simétrico; fenômeno global de lista curada
(`trigger_global_weather`; canal LLM fica p/ spec de clímax). Clima no topbar.


**Sessão 2026-07-04/05 (7): FASE 4 (Gameplay Core) INTEIRA implementada em uma sessão.**
313 → **461 testes offline verdes** + **smoke com LLM REAL executado (2026-07-05)** —
todas as 7 specs `done`. Smoke real validou em jogo vivo: criação com ids canônicos e
auto-equip; Gemini mapeou HABILIDADE NOVA da árvore ("carga de lança" → cooldown+custo
reais); kill → +50 XP → nível 2 → `/game/levelup` com lock de ramo em produção (ramo
rival 400); compra real no Empório (TradeIntent → preço Python 50×1.2=60, estoque
decrementa); poção bebida EM combate (item_id do Gemini, qty 2→1); morte com fecho de
saga narrado pelo Gemini + milestone "Aqui termina a saga" + memorial 409.
**4 bugs achados e corrigidos pelo smoke** (MockLLM escondia todos): (1) `/game/new`
descartava `equipment`/`pending_choices` ao remontar o player (api+CLI); (2) XP de
beat grátis no prólogo (gate turn_count>1 — abertura roda com turn=1); (3) `_narrate`
do loot só mandava SystemMessage (Gemini exige HumanMessage) e duplicava o [SISTEMA]
no fallback; (4) `game_over` não existia no `GameState` → LangGraph DESCARTAVA o
update do nó (canal validado via grafo). Pendente: playtest de balanceamento.
**4.5 (party):** companion = ficha estilo bestiário no MESMO motor (perfis 2.5b via
`resolve_ally_turn`); recrutamento/esperar/seguir/dispensar interceptados por regex +
gate Python no npc_actor (relationship ≥7, teto 3, fação hostil nega — LLM não decide);
inimigo escolhe alvo por perfil (tático→menor HP%, implacável→player); companion
canônico morto vira `npc_killed` (crônica/quests órfãs/cascata de graça); Muralha
Humana do Cavaleiro virou condicional real a party ativa; HP bars no HUD; critério
4v5 sem crash testado.
**4.6 (dificuldade/IA/morte):** `encounter_budget.py` — spawn clampado por orçamento
de pontos (minion 2/elite 5/boss 12; base por danger + nível + 2×party; boss nunca
corta, variedade primeiro) + piso com reforço regional; inimigos usam habilidades
MECÂNICAS (schema do player, custo/cooldown/effects 4.2, perfil decide quando —
curadoria: 12 elites + 7 bosses); bosses com FASES por threshold de HP; morte do
player = fecho de saga (SMART com guard + template digno SEMPRE), evento
`player_died` (gate anti-LLM `source=combat`) fecha a crônica, save vira MEMORIAL
(`game_over` persistido, `/game/action` → 409).

**Sessão 2026-07-04 (7a): Fase 4 iniciada — specs 4.1–4.6 escritas; 4.1b DONE; 4.1 implementada.**
Specs da Fase 4 inteira em `specs/` (aprovadas) + ROADMAP limpo de duplicatas (Fase 6
reescrita como evolução da 4.4; "Economia regional"/"Encontros sistêmicos"/"arcos da
crônica" desduplicados).
**4.1b (árvores de Valoria, executor Fable) `done`:** 10 classes × 2 ramos = subclasses
ancoradas nos pilares do mundo (mundo vazio / Abismo / magia corrompe / sacrifício ou
tecnologia prévia); 111 habilidades (66 novas), todas com impacto mecânico (`effects`
tipado pronto p/ 4.2); anti-spoiler ok; design registrado no apêndice A da spec.
**4.1 (progressão) etapas 1–7 implementadas:** `progression.py` puro — XP por kill
(50/200/1000 por `type` do bestiário; fugitivo não conta), beat 150, quest 200;
`grant_xp` multi-level cura só o delta; `pending_choices` não bloqueia o loop;
`player_branch` deriva a subclasse de `known_abilities` (ramo rival tranca pra sempre,
zero campo novo de estado). `known_abilities` virou **ids canônicos**: creator usa
`starting_abilities` da classe, combate casa por id EXATO + gate determinístico (LLM
não libera habilidade fora da ficha), `load_game_state` faz backfill nome→id (descarta
"[Passiva] ..." e flavor não-mapeável, garante `ataque_basico`). Evento `level_up` no
pipeline 2.6 com **gate anti-LLM**: validator exige `source="progression"` — campo que
o schema de proposta do LLM (`ProposedWorldEvent`) não tem; multi-level no mesmo turno
não é duplicata; milestone "O herói alcançou o nível N." na crônica. `POST
/game/levelup` (400 não toca o save); `player_stats` expõe `xp_next_level`/
`pending_choices`/`level_up` (elegíveis + ramos). CLI pergunta no fim do turno (ENTER
adia). Frontend: `LevelUpModal` agrupado por ramo (tema + aviso de escolha
irreversível), botão pulsante "⬆ Nível!" no topbar, Ficha com XP/próximo nível.
**4.2 (buffs mecânicos) implementada:** `condition_modifiers` lido em dano/AC/
acerto/save nos DOIS lados; `effects` tipado da 4.1b aplicado com precedência sobre
texto; parser legado tipa strings ("+5 Dano" → stat/delta); stun perde turno, root
bloqueia fuga, fear -2 acerto; 9/10 passivas data-driven em `passive_effects`
(Sangromante paga mana com HP, Inquisidor imune a medo +2 fogo, Pastor retalia,
Sombra envenena ataque básico, Médico +5 cura <25%, Guardião AC sem armadura...);
Sapador é o único declarativo (sem estruturas no motor — documentado).
**4.3 (inventário/equipamento) implementada:** `inventory.py` puro — `{id, qty}`
com stack, nome→id com acentos, `item_desconhecido` preserva save antigo; slots
weapon/armor/accessory e o combate lê SÓ os slots (fim do auto-scan); "bebo a
poção" vira ação de combate resolvida em Python (cura, decrementa, consome turno);
**3 bugs históricos fechados** (arma inicial canônica com bônus via
`starting_equipment` + 12 artefatos novos; item narrado entra validado via
`StoryUpdate.items_gained`, nunca fantasma; capitalização morta na fonte — API
manda nome canônico). `POST /game/equip`, botão equipar no HUD, comando `equipar`
no CLI, backfill no load.
**4.4 (economia determinística) implementada:** `services/economy.py` puro — preço =
base × regional (`economy_tags`) × mercador × reputação da fação controladora
(projection) × 0.5 venda, arredondado a 5; mercadores com estoque persistente no
world state e restock por relógio; hostil esconde raros e encarece 50%; craft
valida local (`craft_tags`)/ingredientes/ouro; drop tables por região×perigo;
`loot_node` reescrito (TradeIntent FAST com guard → Python resolve → 1 SMART narra
com fallback) — `TransactionResult` (LLM decidia preço) morreu. Dados novos:
`recipes.json`/`merchants.json`/`loot_tables.json` + tags nos 30 nós do mapa.
Suíte: 313 → **424 verdes**. `npm run build` + `smoke_api.sh` ok.
Próximo: smoke real de 4.1–4.6 + playtest de balanceamento → Fase 5 (agentic playtest).

Sessão 2026-07-03 (6): Fase 3.4 DONE — Visualização de estado. FASE 3 COMPLETA.
`services/state_views.py` (novo, 100% puro): `visible_controllers` (mapa mostra quem
domina cada local visitado — verdade `world_projection` 2.5+ vence o legado
`world.controlled` da Fase 2; nome, não id), `recent_control_changes`/`active_threats`
(overlays do mapa: mudança de controle recente, `threat_alerts` ativos, ambos
respeitando fog of war), `reputation_history`/`stability_label` (timeline de fação —
número interno de `stability` NUNCA sai da API, só rótulo qualitativo). Evento novo
`reputation_changed` entra no `event_log` pelo pipeline 2.6 — mas **gerado 100% em
Python** (`agents/storyteller.py`, dentro do loop que já chama `apply_reputation`), não
proposto pelo LLM: zero risco de mapeamento, zero guard de `FallbackLLM` necessário.
Achado que simplificou a implementação: `event_processor.py` não precisou de NENHUMA
mudança — `apply_event` já tinha fallthrough no-op pra tipo sem handler, e
`_chronicle_milestone` já pulava tipo fora de `CHRONICLE_EVENT_TYPES` (reputação não
vira milestone, timeline da fação é o lugar dela). `WorldMap` ganha badge de controle
recém-mudado, ícone ⚠ de ameaça por região e banner de `looming_threat`; `FactionsTab`
ganha sparkline SVG inline (sem lib) + rótulo de estabilidade + últimas mudanças.
Suíte offline: 290 → **313 verdes** (+23 `tests/test_fase34.py`). `npm run build` +
`smoke_api.sh` ok. Smoke com LLM real confirmou `map_overlays`/`controlled` corretos
em jogo real (controlador resolvido = "Lorde Protetor Valerius", não id de fação);
`reputation_changed` em si não depende de schema LLM novo (é Python puro), já coberto
por testes de integração determinísticos. Detalhes/desvios da spec: `CHANGELOG.md` e
`specs/fase-3.4-visualizacao-estado.md` §8.

**Fase 3 (Clareza de campanha) fecha aqui** — 3.1 diário/crônica, 3.2 codex do
jogador/bestiário, 3.3 quest log, 3.4 visualização de estado, todas `done`. Próximo:
Fase 4 — Gameplay Core.

Sessão 2026-07-03 (5) — Fase 3.3 (quest log) `done`; ver `CHANGELOG.md`.

Sessão 2026-07-03 (4) — Fase 3.2 (Codex do jogador + bestiário progressivo) `done`; ver
`CHANGELOG.md`.

Sessão 2026-07-03 (3) — Fase 3.1 (crônica por capítulos) `done`; ver `CHANGELOG.md`.

Sessão 2026-07-03 (2) — faxina de código morto + auditoria de gameplay → **Fase 4 —
Gameplay Core** no ROADMAP (6 fatias `draft`): ver `CHANGELOG.md`. Achados-chave:
`XP_TABLE` sem consumidor (não existe progressão), buffs só texto, party só schema,
craft/shop/loot 100% LLM, poção inutilizável em combate.

**Fases 2.6, 2.7 e 2.8 DONE** (detalhes no `CHANGELOG.md`; specs em `specs/`):
2.6 = LLM propõe eventos estruturados, motor valida/aplica (`world_validators` +
`event_processor`; combate gera `npc_killed` determinístico). 2.7 = rules engine
(`services/rule_engine.py`, cascata determinística com anti-loop, `world_rules.json` +
overlay `components.json` migration-safe). 2.8 = context builder (`build_context_pack`
ranqueia fatos por relevância+local+recência com orçamento por seção; estado vivo entra
ANTES da lore base; 4 agentes integrados: storyteller/npc/combat/campaign_manager).
Smoke LLM real das 3 fases pendente de quota.

**Próximo passo:** smoke com LLM real da 4.1 (§6 da spec) → Fase 4.2 — buffs
mecânicos (spec aprovada em `specs/fase-4.2-buffs-mecanicos.md`).

Entregas da 2.5b (detalhes no `CHANGELOG.md`): mapa de Valoria 30 nós, 18 fações,
6 raças com traits mecânicos (`apply_racial_traits`), bestiário 84 entradas com
`regions`/`behavior`, combate com perfis (tatico/feroz/covarde/implacavel + moral/fuga/
frenesi), fuga → `threat_alerts` → reforços regionais, `pick_encounter_enemy()` por
região, `entities_extra.json` (curadoria manual que `migrate_lore_nova.py` NÃO toca).

**⚠️ Saves pré-2.5b:** carregam sem crash (backfill), mas locais/fações antigos não
existem mais no mapa — sessões antigas ficam narrativamente órfãs. Arquivar saves antigos.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 703 testes offline verdes (contratos de LLM ficam fora)
uv run pytest -m llm_contract -v -s  # 9 contratos contra o Gemini REAL (~13 req; requer chave)
uv run pytest -m llm_playtest -v -s  # Fase 5: 10 perfis jogam campanha curta no LLM REAL (Groq free basta)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python -m playtest run --all --turns 50   # Fase 5: harness offline (MockLLM)
uv run python -m playtest report <run_id>        # Fase 5: relatório agregado
uv run python rag.py                 # reindexar lore (data/codex/) + regras (data/rules.txt)
uv run python scripts/migrate_lore_nova.py  # regerar Codex de lore_nova/ (SOBRESCREVE curadoria)
bash scripts/smoke_api.sh [porta]    # smoke da API (health, map, /game/new, /game/action)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na
raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers:** `LLM_PROVIDER=gemini|ollama|openai|openai_compat` no `.env`
(ver `.env.example`). Sem chave (ou provider sem chave), `get_llm()` devolve `MockLLM` —
jogo jogável sem rede.

**Quota Gemini:** free tier = **20 req/dia por modelo** (flash e pro têm buckets
separados). E2e em lote inviável. `get_llm()` é fail-fast (`max_retries=0`): `429` falha
em ~3s. **MockLLM esconde bugs de mapeamento** — validar nós novos com a chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate:** IA identifica/narra; Python resolve tudo (`combat_mechanics.py`) —
  iniciativa, DoT/condições, custos, cooldowns, saves + perfis de comportamento (2.5b)
- **Mundo:** mapa de Valoria 30 nós, relógio, viagem (fog of war), descanso, gating por
  classe; raças com traits mecânicos (2.5b)
- **Fase 2:** fações com objetivos, reputação, não-onisciência, ascensão, encontros
  temáticos, memória de NPC vetorizada, world_simulator off-screen
- **Fase 2.5:** Codex Valoria + grafo de mundo (558 entidades) + `event_log`/
  `world_projection` no save + RAG com visibilidade (`secret`/`hidden` não vaza ao
  narrador); timeline por era em `data/codex/timeline/`
- Beats de campanha avançam via `StoryUpdate.beat_completed`; HUD mostra objetivo
- **Fase 4.1 (novo):** progressão completa — XP por kill/beat/quest (Python), level up
  com curvas por classe, árvore de 111 habilidades em 20 ramos-subclasse (4.1b),
  escolha via CLI/modal web/`POST /game/levelup`; saves antigos backfillados
- **Fase 3.1:** crônica por capítulos (`arc_title` do planner) — milestones
  determinísticos do event_log (auditáveis por `event_id`) + prosa de menestrel;
  backfill de saves antigos; HUD distingue ⚔ milestone de ❧ prosa
- **Fase 3.2:** Codex do jogador (`GET /game/codex`, aba `CodexTab`) — locais/fações/
  NPCs/segredos derivados do save (zero estado novo); bestiário progressivo com 4 graus
  (`bestiary_knowledge`, 100% Python) revelando ficha crescente da criatura
- **Fase 3.3:** quest log (aba "Missões") — main quest deriva do `campaign_plan`; side
  quests (`GameState.quests`) propostas por NPC/narrador, concluídas via pipeline 2.6
  (`quest_completed`), falha sistêmica automática se a origem canônica morre
- **Fase 3.4:** mapa mostra controlador real por local (verdade 2.5+/projection, não
  o legado da Fase 2), badge de controle recém-mudado, ícone de ameaça regional
  (`threat_alerts`), banner de `looming_threat`; timeline de reputação por facção
  (sparkline + rótulo qualitativo de estabilidade, número interno nunca exposto)
- **Fase 7:** lint de conteúdo (CLI + gate em teste + CI) · curadoria
  migration-safe (`codex_overrides.yaml`, `curated: true`, templates,
  `docs/AUTORIA.md`) · segredos de NPC em docs `hidden` separados (narrador
  não recebe o pacto de Valerius)
- **Fase 5:** harness de playtest agêntico (`playtest/`) — 10 perfis
  determinísticos jogam campanhas offline sobre o grafo real; invariantes de
  estado por turno; telemetria JSONL + relatório agregado com custo/fallback;
  `--real` opt-in com teto de requests/custo
- Multi-provider LLM + typewriter effect no frontend React
- Loot/Craft/Shop/Treasure + economia (sinal do ouro forçado em Python)
- Memória híbrida (resumo + RAG por sessão) + persistência JSON por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância
de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Já blindados: `router.py`, `character_creator.py`, `combat.py` (isinstance). Demais
agentes: dentro de `try`.

---

## Bugs conhecidos (sessão 2026-06-26)

| Bug | Local provável / destino |
|---|---|
| Inventário: item narrado não entra no inventário | `agents/loot.py` — mapeado na **Fase 4.3** |
| Capitalização estranha em itens | Grep `title()` / `capitalize()` — mapeado na **Fase 4.3** |
| NPC errado responde fala destinada a outro | `agents/router.py` — `active_npc_name` não filtra |
| Morte do player sem narrativa (só tela de morte) | Fluxo final de combate — mapeado na **Fase 4.6** |

**Design:** campaign manager coloca plot twists com muita frequência — aumentar
intervalo de triggers de replan.

## Limitações conhecidas

- **Inventário inicial** usa nomes livres, não IDs — `ARTIFACTS_DB.get(item_id)` não acha
  (arma inicial não dá bônus de combate) — mapeado na **Fase 4.3**
- **API stateless por save** — sem sessão concorrente; migrar p/ Postgres+pgvector ao escalar
- **Saves antigos** (schema `class`/`abilities`) carregam mas campos novos ficam ausentes

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
