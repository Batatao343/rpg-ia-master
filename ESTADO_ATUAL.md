# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Documento de estado do projeto. Leia isto **primeiro** ao retomar o trabalho.
> Complementa `CLAUDE.md` (arquitetura) e `REFERENCE.md` (decisões técnicas).
> Última atualização: 2026-06-25 (sessão: validação Gemini real + fix embeddings + Fase 2 fações).

---

## TL;DR — Em que pé está

**MVP funcional e jogável + Fase 2 iniciada.** O grafo LangGraph roda fim-a-fim (criar plano → rotear → narrar/combater/NPC/loot → arquivar → salvar) sem crashar. Suíte offline 100% verde (`uv run pytest` — **49 testes**).

A chave (`GOOGLE_API_KEY`) está **válida** e o caminho do **Gemini real foi validado** fim-a-fim
(`tests/test_real_llm.py`, 4 passed, ~7-10 req). Sem chave o jogo roda no **MockLLM** (jogável).

**Fix crítico real (esta sessão):** `text-embedding-004` saiu do v1beta (404 em `embedContent`) —
o RAG global (lore/rules) e a memória de sessão quebravam silenciosamente sob a chave real. Migrado
para `models/gemini-embedding-001` e índices reindexados (`uv run python rag.py`). Dimensão mudou →
saves/índices de sessão antigos viram incompatíveis (regerados em runtime).

**Fase 2 — Fações (núcleo determinístico):** `state.factions[]` avançam objetivos no tempo
(descanso/viagem), 100% offline; aba "Fações" no HUD. Ver `ROADMAP.md` Fase 2. Falta a camada
narrada (`world_simulator`) e reputação por ação do jogador.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** para o projeto (exige 3.13). Use sempre o venv do `uv`.

`uv` **não está no PATH**; fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13 (já feito)
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example — é versionada)
uv run pytest                        # 39 testes offline (conftest força RPG_FORCE_MOCK=1)
uv run python game_engine.py         # jogar no terminal (CLI)
uv run uvicorn api:app --port 8000   # API REST + FRONTEND WEB
uv run python rag.py                 # reindexar lore/regras (data/*.txt)
```

**Frontend web (jogar no navegador):** suba a API e abra `http://localhost:8000`.
O cliente principal é **React + Vite + TS** em `web/` (tom dark medieval/The Witcher: Cinzel +
EB Garamond, paleta aço+pergaminho+sangue+bronze, ornamentos SVG, `motion` p/ animações). Build:
`cd web && npm install && npm run build` (gera `web/dist`, que o FastAPI serve na raiz; dev:
`npm run dev` :5173 com proxy p/ a API). Se não houver `web/dist`, cai no `frontend/` vanilla (legado).
Tela de criação → tela de jogo: narrativa + HUD em abas **Ficha (barras/stats/habilidades/inventário) ·
Combate · Pessoas (NPCs) · Mapa (fog of war) · Crônica (menestrel)**, **modo combate** no chat (véu
vermelho/urgência), banner de modo simulado. Cache do navegador: use hard refresh/aba anônima ao trocar build.
**Modo simulado (sem API key):** sem `GOOGLE_API_KEY`, `get_llm()` devolve um
`MockLLM` ([mock_llm.py](mock_llm.py)) que gera dados fictícios plausíveis para cada
agente (narrativa, ficha, roteamento por palavra-chave, combate, NPC, loot). O jogo
fica **jogável e testável** sem chave; o front mostra banner "modo simulado". `RPG_FORCE_MOCK=1`
força o MockLLM **mesmo com chave** — usado pela suíte (`tests/conftest.py`) p/ ser determinística
e não depender de quota/rede. Com a
chave, a IA real entra automaticamente. Force o fallback de erro puro com `RPG_NO_MOCK=1`.

`GOOGLE_API_KEY`: gerar em https://aistudio.google.com/app/apikey

---

## Quota e teste real (IMPORTANTE)

A chave free tier do Google AI Studio tem **20 requisições/dia POR MODELO**
(`gemini-flash-latest`≈`gemini-3.5-flash` e `gemini-pro-latest` têm buckets separados, ambos pequenos).
Um e2e real do grafo gasta dezenas de chamadas → **inviável testar IA real em lote no free tier**.

- Para validar o Gemini de verdade: ativar billing **ou** rodar pouquíssimas chamadas/dia.
- Harness frugal pronto: ver `t1_provider.py`/`t2_smart.py` (scratchpad da sessão) — 1 chamada por nó,
  prioriza nós SMART vs FAST (quotas separadas), com detector de degradação (marcadores de fallback).
- `get_llm()` agora é **fail-fast** (`max_retries=0`): no `429` o turno falha em ~3s e cai no fallback,
  em vez de travar minutos com retry/backoff.

**Por que o MockLLM não basta como teste:** ele devolve sempre instâncias Pydantic válidas, então
acesso a campo nunca quebra — **bugs de mapeamento de campo (nome/tipo/ausência) só aparecem no Gemini
real.** A auditoria estática desta sessão cobriu os nós; falta a confirmação online.

---

## O que funciona hoje

- **Criação de personagem** (CLI wizard + endpoint `/game/new`) — resiliente sem API key (cai em stats fallback).
- **Loop de turno completo**: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`.
- **`turn_count`** incrementa por turno (corrigido — antes ficava 0 para sempre).
- **Rota NPC** casa o alvo da fala com NPC presente na cena (corrigido — antes sempre falhava).
- **Combate com profundidade** (2026-06-25): a **IA só identifica** a ação (linguagem natural → `CombatAction`) e **narra**; **Python resolve tudo** em `combat_mechanics.py` — iniciativa (d20+dex), condições/DoT estruturadas, custos stamina/mana + cooldowns, save por atributo real do alvo, turno dos inimigos. Determinístico, testável offline, jogável sem quota. UI mostra painel de combate (inimigos/HP/condições/iniciativa/cooldowns). Spawn via bestiário+cache mantido; vitória roteia para loot. `state.combat` persistido.
- **Fase 0 — modelo de mundo** ([world_utils.py](world_utils.py) + `data/world_map.json`): grafo de 9 locais, relógio (dia/período), viagem entre locais conectados (fog of war via `visited`), descanso (cura + tempo), gating de ação por classe (`class_themes` + Ruler). Tudo determinístico (funciona no modo simulado). Testes em `tests/test_fase0.py`.
- **Loot/Craft/Shop/Treasure**, economia (compra/venda), persistência de itens custom. Sinal do ouro na venda forçado em Python (não depende do LLM).
- **Memória híbrida**: resumo curto (archivist) + RAG por sessão (FAISS por `game_id`).
- **Persistência**: saves JSON em `saves/{game_id}.json`, compatível com saves antigos.
- **Console UTF-8** forçado em `main.py` (corrige crash de emoji no terminal Windows cp1252).

---

## Convenção CRÍTICA de resiliência (não esquecer)

`get_llm()` retorna um **`FallbackLLM`** quando o provider falha (sem key, sem rede). Esse fallback:
- `.with_structured_output(X).invoke(...)` **NÃO** devolve uma instância de `X` — devolve um `AIMessage`.
- Logo, acessar `resultado.campo` (ex: `decision.route`, `update.narrative`, `stats["attributes"]`) **estoura** se feito fora de um `try/except` ou sem checar o tipo.

**Regra ao escrever/editar qualquer nó que use `with_structured_output`:**
1. Envolva o acesso aos campos em `try/except`, **ou**
2. Cheque `isinstance(resultado, SeuModelo)` antes de usar.

Já blindados: `router.py`, `character_creator.py`, `combat.py` (isinstance). Os demais agentes acessam dentro de `try`. Mantenha esse padrão.

**Cuidado — o MockLLM mascara o problema:** ele devolve instâncias Pydantic válidas, então no modo
simulado (e na suíte) o acesso a campo nunca quebra. O guard só é exercitado no `FallbackLLM`/Gemini
real. Ao validar um nó novo, teste também com a chave real (respeitando a quota).

---

## Limitações conhecidas / próximos passos (backlog)

Nada disso quebra o jogo — são melhorias:

1. ~~**Beats da campanha não avançam**~~ — **RESOLVIDO** (sessão 2026-06-25). `StoryUpdate.beat_completed` (sinal do narrador) avança `current_step`, marca beat `done` e dispara replan ao esgotar. UI mostra objetivo + beats (HUD). Testes: `tests/test_mvp.py::test_storyteller_*`.
2. **Combat `next` em rodadas normais** — durante o combate (sem vitória) o nó devolve `next="combat_agent"`; a aresta condicional manda para o archivist (correto). Só a vitória vai para loot. OK para MVP.
3. **Inventário inicial usa nomes, não IDs** — itens gerados pela IA na criação entram como texto livre; `ARTIFACTS_DB.get(item_id)` não acha (apenas ignora, sem bônus de combate). Padronizar IDs se quiser bônus de item desde o nível 1.
4. **Saves antigos** (`saves/quicksave.json` etc.) têm schema legado (`class`/`abilities`). Carregam, mas alguns campos novos (mana/stamina/`class_name`) ficam ausentes. Migrar se necessário.
5. ~~**`dice_system` saving throw** usa bônus fixo (+3)~~ — **RESOLVIDO** (sessão 2026-06-25). `roll_formula(..., save_bonus=)` aceita o mod real; o combate determinístico passa o atributo do alvo.
6. **API é stateless por save** — sem sessão concorrente real; cada request carrega/salva o JSON. Migrar para pgvector/DB se escalar (ver REFERENCE.md).

---

## Histórico de correções (sessão 2026-06-25 — auditoria do fluxo de IA)

Auditoria de todos os nós que usam `with_structured_output` (mapeamento campo→GameState) + hardening:

| Área | Achado / mudança | Arquivo |
|---|---|---|
| Segurança | Chave real estava na `.env.example` (versionada) → removida; nunca foi commitada (working tree). **Rotacionar por precaução.** | `.env.example` |
| NPC | Fallback de `generate_new_npc` sem `initial_relationship` → `KeyError` no storyteller (virava "Erro AI") | `agents/npc.py`, `agents/storyteller.py` |
| Loot | Venda dependia do sinal de `gold_cost` vindo do LLM (risco de jogador perder ouro) → sinal forçado em Python pela semântica | `agents/loot.py` |
| Char | Atributos do Gemini com nomes longos/PT (`dexterity`) quebravam mods/attack_bonus → normalizados via `normalize_attr` | `character_creator.py` |
| LLM | Retry-storm: `429` de quota travava o turno minutos → `max_retries=0` (fail-fast) | `llm_setup.py` |

> Pendente: confirmar o fluxo no Gemini **real** (bloqueado por quota — ver "Quota e teste real").
> Demais nós (router, storyteller, archivist, campaign_manager, combat, ruler, librarian, bestiary)
> auditados e OK (guardas presentes, leituras batem com os schemas).

---

## Histórico de correções (sessão 2026-06-22)

Bugs consertados nesta passada (contexto para não regredir):

| Área | Bug | Arquivo |
|---|---|---|
| Console | Emoji em print quebrava turno no Windows (cp1252) | `main.py` |
| Router | Sem key, `decision.route` estourava (AIMessage) | `agents/router.py` |
| Char | Sem key, `stats["attributes"]` estourava KeyError | `character_creator.py` |
| Fluxo | `turn_count` nunca incrementava | `agents/campaign_manager.py` |
| NPC | `active_npc_name` nunca setado → rota NPC morta | `agents/router.py` |
| Combate | Vitória não dava loot (aresta fixa) | `main.py` |
| RAG | `python rag.py` buscava path errado (raiz vs data/) | `rag.py` |
| NPC | `memory` ausente → KeyError | `agents/npc.py` |
| Schema | Player criado com `class`/`abilities` vs schema `class_name`/`known_abilities`/mana/stamina | `game_engine.py`, `api.py`, `character_creator.py` |
| Testes | Suíte inteira morta (imports de arquitetura antiga) + sem pythonpath | `tests/` reescrito, `conftest.py`, `pyproject.toml` |
| Deps | `requirements.txt` = freeze de 2045 linhas | `requirements.txt` |

---

## Mapa de arquivos

Mapa completo (raiz + `agents/` + `data/` + `tests/`) está em **`CLAUDE.md` → "Estrutura de pastas"**
(fonte única, mantida lá para não duplicar). Schema do estado: `state.py`.

---

## Checklist ao começar a próxima tarefa

1. `uv run pytest` deve estar verde antes de mexer (39 testes).
2. Mudou um nó com `with_structured_output`? Garanta o guard de fallback (ver seção CRÍTICA) — e
   lembre que o MockLLM não exercita o guard; valide com a chave real se possível.
3. Mudou o schema do player/estado? Atualize `state.py` **e** os 2 pontos de criação (`game_engine.py`, `api.py`) **e** o creator.
4. Novo agente no grafo? Conecte ao `archivist` no fim (ver REFERENCE.md).
5. Editou `data/world_lore.txt` ou `data/rules.txt`? Rode `uv run python rag.py` para reindexar.
6. Mecânica nova (números)? Resolva em Python determinístico (`combat_mechanics`/`dice_system`/`world_utils`),
   não no LLM. Não confie em sinal/valor do LLM sem validar.
