# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho. Complementa `CLAUDE.md` (arquitetura).
> Decisões estruturais: `REFERENCE.md` (sob demanda). Histórico de sessões: `CHANGELOG.md`.
> Última atualização: 2026-07-05 (sessão 7: FASE 4 INTEIRA implementada — 4.1 a 4.6 + 4.1b)

---

## TL;DR — Em que pé está

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
uv run pytest                        # 520 testes offline verdes (test_real_llm precisa de chave)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
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
