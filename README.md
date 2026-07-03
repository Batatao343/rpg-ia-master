# RPG IA Engine

RPG de texto **dark fantasy** com narração gerada por IA. Motor multi-agente em **LangGraph** com RAG híbrido (lore global + memória por sessão) e dois tiers de LLM (Google Gemini).

O jogador digita ações em linguagem natural; o motor classifica a intenção, executa o agente certo (história, combate, NPC ou loot) e devolve narrativa coerente com o mundo e a sessão.

> **Documentação:** `CLAUDE.md` (arquitetura) · `REFERENCE.md` (decisões técnicas) · `ESTADO_ATUAL.md` (estado atual, como rodar, backlog).

---

## Stack

Python 3.13 · FastAPI · LangGraph · FAISS · Google Gemini (`gemini-flash-latest` / `gemini-pro-latest`) · uv

---

## Setup

```bash
uv sync                        # cria o venv (Python 3.13) e instala deps
cp .env.example .env           # cole sua GOOGLE_API_KEY
```

`GOOGLE_API_KEY`: gere em https://aistudio.google.com/app/apikey
Sem a chave o jogo roda em **modo degradado** (não quebra, mas o narrador fica indisponível).

---

## Rodar

```bash
# Jogar no terminal (CLI)
uv run python game_engine.py

# API REST (backend para frontend web/mobile)
uv run uvicorn api:app --reload --port 8000

# Testes (offline, não exigem API key)
uv run pytest

# Reindexar lore/regras após editar data/codex/ ou data/rules.txt
uv run python rag.py
```

---

## Fluxo de um turno

```
START
  → campaign_manager   # planeja arcos (3–5 beats) com RAG de lore; incrementa turn_count
  → dm_router          # classifica intenção: STORY | COMBAT | NPC | LOOT
  → agente especializado (storyteller | combat_agent | npc_actor | loot_agent)
  → archivist          # atualiza resumo (curto prazo) + persiste fatos no FAISS da sessão
  → END → save
```

---

## Estrutura

```
main.py / state.py / llm_setup.py / rag.py / persistence.py
gamedata.py / combat_mechanics.py / world_utils.py / character_creator.py
game_engine.py (CLI)   api.py (REST)
agents/   # router, campaign_manager, storyteller, combat, npc, loot, archivist, ...
data/     # codex/, rules.txt, bestiary.json, classes.json, artifacts.json, ...
tests/    # suíte offline (test_mvp.py)
```

Detalhes de cada módulo e convenções em `CLAUDE.md` e `ESTADO_ATUAL.md`.
