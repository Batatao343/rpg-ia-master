# SPEC-296 — mundo-vivo-onda0-religacoes

> **Status:** `in-progress` (aprovada pelo dono em 2026-10-20; Etapas 1–4 implementadas, Etapa 5 = coordenador)
> **Criada:** 2026-10-20 · **Atualizada:** 2026-10-20
> **Depende de:** SPEC-215 (`done`)
> **Desbloqueia:** SPEC-298, SPEC-302 (consomem notícias e ambiente)

---

## 1. Contexto & Objetivo

A auditoria de 20/10 ([docs/mundo-vivo/VISAO.md](../docs/mundo-vivo/VISAO.md))
achou peças prontas do "mundo vivo" que estão desligadas, sem chamador ou
invisíveis ao narrador. Esta onda religa essas peças, com mudança pequena e
sem sistema novo:

1. A propagação de notícias entre NPCs (SPEC-215) existe, mas está `off` em
   todos os ambientes.
2. O ciclo "inimigo foge e volta com reforços" está pronto
   (`world_utils.register_flee_alert`), mas nada o chama.
3. O narrador recebe clima só em fenômeno **global**. Clima local, perigo e
   saídas do local nunca chegam ao prompt, e NPC e combate não recebem
   ambiente nenhum.
4. O pulso do mundo (rumor percebido em viagem/descanso) some no turno
   seguinte, e o jogador não tem onde reler o que ouviu.

Princípios: **mecânica é Python, a LLM só narra**. Regra de ouro do dono:
**o jogador só sabe o que viu ou ouviu**. Tudo o que esta spec mostra já foi
percebido pelo herói.

## 2. Requisitos

- **R1 — Notícias entre NPCs no staging.** O staging roda
  `RPG_NPC_KNOWLEDGE=shadow`. Com os evals da SPEC-215 verdes e um playtest
  Mock de 50 turnos sem violação nova, passa a `on`. O default do código
  continua `off`, e a mudança de default em produção fica para o go do beta
  (SPEC-197). O resultado (shadow → on) é registrado na spec.
- **R2 — Fuga gera retorno.** Quando um encontro termina com ≥1 inimigo
  `fled=True`, por fuga do bestiário ou pelo `_stalemate_guard`, o motor chama
  `register_flee_alert`.
  - Exatamente **1 alerta por encontro**, com o hint e o `enemy_id` do
    primeiro fugitivo.
  - Usa o `faction_id` do inimigo, quando houver.
  - Usa o `turn` do mundo.
  - Fuga do **herói** não registra alerta. O alerta da perseguição é outro
    caminho.
  - O resultado de rendição (`surrendered`) também não registra alerta.
- **R3 — O alerta vira encontro.** Na próxima checagem de encontro na mesma
  região, dentro de `_ALERT_TTL`, o encontro sai com `reason="reinforcements"`
  (o caminho existente em `check_encounter`). Coberto por teste de integração
  com seed.
- **R4 — Bloco de ambiente único.** Uma função pura
  `services/ambient.py::ambient_block(world, player, *, audience) -> str` monta
  `<AMBIENTE>` com:
  - **período e dia**, via `clock_label`;
  - **clima local**, o rótulo de `weather_effects(world)`, e o fenômeno global
    quando houver;
  - **luz**, pelo rótulo de `light_level`, sem número;
  - **perigo em palavras**: `effective_danger` 1–2 = "tranquilo", 3 = "tenso",
    4 = "perigoso", ≥5 = "mortal";
  - **abrigo**, quando o local tiver tag de abrigo;
  - **saídas**: os nomes das conexões do local atual, só para
    `audience="story"`.

  A função não usa RNG nem LLM, e devolve a mesma saída para a mesma entrada.
- **R5 — Consumidores do ambiente.**
  - O storyteller troca `luz_block`/`clima_block` por `ambient_block(...,
    audience="story")`. O comportamento de luz e clima global se mantém: os
    textos-guia continuam.
  - `npc_actor` recebe `audience="npc"` (sem saídas).
  - A narração de combate inclui `audience="combat"` em `world_ctx`, sem
    saídas.
- **R6 — Notícias percebidas persistem.** Todo rumor do pulso do mundo que
  chegou ao jogador (`[ECOS DO MUNDO] …`) é anexado a `world["news"]` como
  `{day, period, location_id, location_name, text, source: "pulse",
  turn}`.
  - Guarda no máximo 12 (FIFO).
  - Não grava texto vazio.
  - Não duplica (mesmo texto + local).
  - Saves sem `news` carregam como lista vazia.
- **R7 — O narrador lembra das notícias.** O storyteller recebe um bloco
  `<OUVIU_DIZER>` com as últimas 3 notícias (texto + local + dia), com a
  instrução "pode referenciar se fizer sentido; não invente detalhes além do
  texto".
- **R8 — A UI mostra "Ouvi dizer".**
  - O bloco de mundo da API (`_world_block`/state) expõe `news` (últimas 12).
  - O HUD/Codex do web ganha a lista "Ouvi dizer", da mais nova para a mais
    antiga, com "Dia N · Período · Local".
  - Sem notícias, a lista mostra estado vazio.

### Fora de escopo

- Os contextos de DC de traços (`comercio`/`intimidacao`/`insight`) vão para a
  SPEC-298: hoje não têm consumidor.
- Tick diário do mundo, decaimento de perigo fora de viagem/descanso, pressões
  e calendário: SPEC-302.
- Rumores vindos de NPCs (propagação → notícia): a SPEC-302/298 consome
  `world.news`.
- Variantes de arte, áudio, ganchos derivados do estado: pilar D.
- Mudar `_ALERT_TTL` ou a força do reforço.

## 3. Design técnico

- **Novo:** `services/ambient.py`.
  - `danger_words(level:int)->str`.
  - `ambient_block(world:dict, player:dict, *, audience:Literal["story","npc","combat"])->str`.
  - `append_news(world:dict, *, text:str, location_id:str, location_name:str, turn:int, source:str="pulse")->dict`,
    que devolve um world novo (não muta).
- **Alterado:**
  - `agents/storyteller.py`: o bloco de luz e clima (~:821-852) dá lugar a
    `ambient_block`. Depois de `simulate_world` (~:791), quando `world_note`
    começar com `[ECOS DO MUNDO]`, chama `append_news`. O prompt ganha
    `<OUVIU_DIZER>`.
  - `agents/npc.py`: o prompt do NPC (~:747-776) recebe
    `ambient_block(audience="npc")`.
  - `agents/combat.py`: `world_ctx` (~:866-909) inclui
    `ambient_block(audience="combat")`. No fechamento do encontro (onde
    `_encounter_outcome`/`_finish_encounter` decidem o desfecho), chama
    `register_flee_alert` para o 1º inimigo com `fled=True`, se o herói não
    fugiu.
  - `api.py` (`_world_block` ~:2792): passa a expor `news`.
  - `web/src/types.ts`: `news?: NewsItem[]`.
  - `web/src/components/Hud.tsx` (`HeardNews`) + `web/src/heardNews.ts` (ordem/rótulo,
    testado em `web/tests/heardNews.test.mjs`), montado na aba Crônica do Codex
    (`ContextSurface.tsx`).
  - `state.py`: `WorldState.news: list[dict]`, opcional.
- **Staging:** as envs vão por `scripts/` do fluxo `staging-deploy`
  (`vercel_env.py`). Tudo fica registrado no CHANGELOG.

## 4. Plano passo a passo

### Etapa 1 — `services/ambient.py` (puro)
1. **Testes** (`tests/test_ambient.py`):
   - `test_danger_words_bands` cobre as 4 faixas.
   - `test_ambient_story_has_weather_light_exits`: Skallgard com nevasca +
     Noite sem tocha resulta em "Nevasca", "escuridão" e nomes de conexões.
   - `test_ambient_npc_and_combat_omit_exits`.
   - `test_ambient_global_weather_included`.
   - `test_ambient_deterministic`: duas chamadas devolvem saída igual.
   - `test_append_news_fifo_dedupe_cap`: 12 no máximo, dedupe por
     texto+local, texto vazio ignorado, e o world original não é mutado.
2. **Implementação.**
3. `bash scripts/dev/py.sh -m pytest tests/test_ambient.py -q`.

### Etapa 2 — Consumidores de ambiente (R5) e notícias (R6–R7)
1. **Testes:**
   - `test_storyteller_prompt_has_ambient_block`: captura o prompt do
     MockLLM e encontra `<AMBIENTE>` com clima local, sem fenômeno global.
   - `test_storyteller_appends_news_on_pulse`: com pulso de rumor fixo,
     `world.news[-1].text` traz o rumor.
   - `test_storyteller_prompt_has_heard_block`.
   - `test_npc_prompt_has_ambient_without_exits`.
   - `test_combat_world_ctx_has_ambient`.
   - `test_legacy_save_without_news_loads`.
2. **Implementação.**

### Etapa 3 — Fuga gera retorno (R2–R3)
1. **Testes** (`tests/test_flee_alert_wiring.py`):
   - `test_enemy_flee_registers_single_alert`.
   - `test_stalemate_flee_registers_alert`.
   - `test_hero_flee_no_alert`.
   - `test_surrender_no_alert`.
   - `test_alert_produces_reinforcements_encounter` (seed, mesma região,
     dentro do TTL).
2. **Implementação** em `agents/combat.py`.

### Etapa 4 — API + UI (R8)
1. **Testes:**
   - `test_world_block_exposes_news` (API).
   - Teste de componente/vitest, se o padrão do `web/` tiver, para a lista
     "Ouvi dizer" vazia e preenchida.
2. **Implementação.** Depois, `npm run build` e
   `npm run lint`/`typecheck` do `web/`.

### Etapa 5 — Notícias entre NPCs no staging (R1), feito pelo coordenador
1. Evals da SPEC-215 (`-m` correspondente/`evals`) verdes localmente com
   `RPG_NPC_KNOWLEDGE=shadow` e `on`.
2. `playtest run --profile explorador --turns 50` (Mock) com
   `RPG_NPC_KNOWLEDGE=on`: 0 violações novas.
3. Staging: `shadow` → smoke → `on` → `e2e_session` verde.

## 5. Critérios de aceite

- [ ] R1: staging em `on`, com evidência (evals + playtest + smoke) registrada.
- [ ] R2–R3 cobertos por teste; o reforço sai de fato com seed.
- [ ] R4–R5: `<AMBIENTE>` nos 3 prompts; zero regressão nos testes de luz e
      clima existentes.
- [ ] R6–R8: notícias persistem, aparecem no prompt e na UI; save antigo
      carrega.
- [ ] `uv run pytest` verde (suíte completa offline, `-n auto`).
- [ ] Nenhum `with_structured_output` novo (nada novo a guardar).
- [ ] `web`: build + lint + typecheck verdes.
- [ ] Revisão independente (spec-reviewer) APPROVED.

## 5.1 Registro de execução (Etapas 1–4, 2026-10-23)

- Desvios: o hint do alerta usa o rótulo canônico da espécie (`_killer_identity`), com o
  nome do inimigo como fallback; `enemy_id` = id base do bestiário. O alerta só é
  registrado no fechamento normal do encontro (não no ramo "sem ativos na entrada").
- Locais: `agents/combat.py::_flee_alert_world`, `_ambient_for_combat`;
  `services/ambient.py` (`ambient_block`, `append_news`, `heard_block`).
- SPEC-215 com `RPG_NPC_KNOWLEDGE=shadow` e `on`: 50 passed em cada.
- `playtest explorador --turns 50` (Mock, `on`): 0 erros, 0 violações.
- `playtest combate --turns 200` (Mock), seeds 1/2: 0 violações (0 `no_progress`).
  Mortes/encontros: baseline `main` 9/19 e 11/19; com a spec 11/25 e 8/18 (0,44 em ambos).

## 6. Smoke test com LLM real

Dentro do teto de US$ 3/dia:
1. Campanha nova, viajar 2x e descansar 1x (DeepSeek). O narrador cita o clima
   local e o período; `world.news` cresce quando houver eco.
2. Falar com um NPC à noite: a fala reflete o ambiente sem citar saídas.
3. Combate: a narração menciona o clima e a luz quando relevantes.

## 7. Riscos & compatibilidade

- **Saves antigos:** `news` é opcional (default `[]`) e os alertas já existem
  no schema.
- **Mock/Fallback:** o bloco é texto determinístico; o MockLLM ignora.
- **Quota/latência:** +~80–150 tokens por prompt; nenhuma chamada nova.
- **R2 aumenta encontros** depois de fugas. Mitigado pelo TTL de 6 turnos,
  pelo consumo único e pelo cooldown de encontro existente. Medir com
  `playtest --profile combate --turns 200` (Mock), mantendo 0 `no_progress` e
  a letalidade dentro das metas da SPEC-285.
