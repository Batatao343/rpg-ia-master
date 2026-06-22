# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Documento de estado do projeto. Leia isto **primeiro** ao retomar o trabalho.
> Complementa `CLAUDE.md` (arquitetura) e `REFERENCE.md` (decisões técnicas).
> Última atualização: 2026-06-22.

---

## TL;DR — Em que pé está

**MVP funcional e jogável.** O grafo LangGraph roda fim-a-fim (criar plano → rotear → narrar/combater/NPC/loot → arquivar → salvar) sem crashar. Suíte de testes offline 100% verde (`uv run pytest`).

Falta **apenas** o usuário colar `GOOGLE_API_KEY` no `.env` para a IA narrar de verdade. Sem a chave o jogo roda em **modo degradado**: não quebra, mas o narrador responde mensagens de fallback ("O destino é incerto... (Erro AI)").

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** para o projeto (exige 3.13). Use sempre o venv do `uv`.

`uv` **não está no PATH**; fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13 (já feito)
copy .env.example .env               # cole GOOGLE_API_KEY no .env
uv run pytest                        # 12 testes offline, devem passar
uv run python game_engine.py         # jogar no terminal (CLI)
uv run uvicorn api:app --port 8000   # API REST + FRONTEND WEB
uv run python rag.py                 # reindexar lore/regras (data/*.txt)
```

**Frontend web (jogar no navegador):** suba a API e abra `http://localhost:8000`.
O FastAPI serve `frontend/` (vanilla HTML/CSS/JS, zero build) na raiz `/`. Tela de
criação de personagem → tela de jogo com HUD (HP/mana/vigor, ouro, inventário,
resumo) e barra de ação. Design aplica os skills `impeccable`/`taste` (dark fantasy,
serif narrativo + grotesca no HUD, acento âmbar, vermelho só pra perigo).
**Modo simulado (sem API key):** sem `GOOGLE_API_KEY`, `get_llm()` devolve um
`MockLLM` ([mock_llm.py](mock_llm.py)) que gera dados fictícios plausíveis para cada
agente (narrativa, ficha, roteamento por palavra-chave, combate, NPC, loot). O jogo
fica **jogável e testável** sem chave; o front mostra banner "modo simulado". Com a
chave, a IA real entra automaticamente. Force o fallback de erro puro com `RPG_NO_MOCK=1`.

`GOOGLE_API_KEY`: gerar em https://aistudio.google.com/app/apikey

---

## O que funciona hoje

- **Criação de personagem** (CLI wizard + endpoint `/game/new`) — resiliente sem API key (cai em stats fallback).
- **Loop de turno completo**: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`.
- **`turn_count`** incrementa por turno (corrigido — antes ficava 0 para sempre).
- **Rota NPC** casa o alvo da fala com NPC presente na cena (corrigido — antes sempre falhava).
- **Combate**: spawn de inimigos via bestiário + cache; ao vencer, roteia para loot (aresta condicional).
- **Loot/Craft/Shop/Treasure**, economia (compra/venda), persistência de itens custom.
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

Já blindados: `router.py`, `character_creator.py`. Os demais agentes acessam dentro de `try`. Mantenha esse padrão.

---

## Limitações conhecidas / próximos passos (backlog)

Nada disso quebra o jogo — são melhorias:

1. **Beats da campanha não avançam** — `storyteller_node` tem a lógica de avanço de `current_step` como `pass` (no-op). O replan por tempo (a cada 10 turnos) funciona, mas o avanço beat-a-beat não. Implementar sinal de conclusão de beat.
2. **Combat `next` em rodadas normais** — durante o combate (sem vitória) o nó devolve `next="combat_agent"`; a aresta condicional manda para o archivist (correto). Só a vitória vai para loot. OK para MVP.
3. **Inventário inicial usa nomes, não IDs** — itens gerados pela IA na criação entram como texto livre; `ARTIFACTS_DB.get(item_id)` não acha (apenas ignora, sem bônus de combate). Padronizar IDs se quiser bônus de item desde o nível 1.
4. **Saves antigos** (`saves/quicksave.json` etc.) têm schema legado (`class`/`abilities`). Carregam, mas alguns campos novos (mana/stamina/`class_name`) ficam ausentes. Migrar se necessário.
5. **`dice_system` saving throw** usa bônus fixo (+3) do inimigo, não a ficha real. Melhoria de fidelidade.
6. **API é stateless por save** — sem sessão concorrente real; cada request carrega/salva o JSON. Migrar para pgvector/DB se escalar (ver REFERENCE.md).

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

## Mapa rápido de arquivos

```
main.py              # grafo LangGraph (build_game_graph, app) + setup UTF-8
state.py             # GameState e TypedDicts (fonte da verdade do schema)
llm_setup.py         # get_llm(tier) + FallbackLLM (NUNCA instanciar Gemini direto)
rag.py               # query_rag / add_memory_to_session / ingest_file
persistence.py       # save_game_state / load_game_state (serializa mensagens)
gamedata.py          # carrega JSONs de data/, ARTIFACTS_DB, save_custom_artifact
dice_system.py       # roll_formula (parse de dados e saves)
engine_utils.py      # execute_engine (loop tool-calling: roll/update_hp/transaction)
character_creator.py # cria ficha do player (IA + JSON oficial)
game_engine.py       # CLI interativo (wizard + loop)
api.py               # FastAPI REST (/game/new, /game/action, /game/state)
agents/
  router.py          # dm_router_node — classifica intenção + seta NPC/loot/combat
  campaign_manager.py# planeja arcos + incrementa turn_count
  storyteller.py     # narração + introduz NPCs
  combat.py          # spawn (bestiário) + execute_engine
  npc.py             # generate_new_npc + npc_actor_node
  loot.py            # loot/craft/shop/treasure
  archivist.py       # memória curta (resumo) + longa (RAG)
  bestiary.py / librarian.py / ruler_completo.py / class_themes.py
tests/
  test_mvp.py        # suíte offline (não exige API key)
  conftest.py        # (na raiz) injeta pythonpath
```

---

## Checklist ao começar a próxima tarefa

1. `uv run pytest` deve estar verde antes de mexer.
2. Mudou um nó com `with_structured_output`? Garanta o guard de fallback (ver seção CRÍTICA).
3. Mudou o schema do player/estado? Atualize `state.py` **e** os 2 pontos de criação (`game_engine.py`, `api.py`) **e** o creator.
4. Novo agente no grafo? Conecte ao `archivist` no fim (ver REFERENCE.md).
5. Editou `data/world_lore.txt` ou `data/rules.txt`? Rode `uv run python rag.py` para reindexar.
```
