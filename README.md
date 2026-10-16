# RPG IA Engine

RPG de texto **dark fantasy** com narração gerada por IA. Motor multi-agente em
**LangGraph**, RAG híbrido (lore global + memória por sessão) e conflito tático
determinístico por Cartas, Virtudes, Vitalidade e Ferimentos.

O jogador digita ações em linguagem natural; o motor classifica a intenção, executa o agente certo (história, combate, NPC ou loot) e devolve narrativa coerente com o mundo e a sessão.

> **Documentação:** `CLAUDE.md` (arquitetura) · `REFERENCE.md` (decisões técnicas) · `ESTADO_ATUAL.md` (estado atual, como rodar, backlog).

---

## Stack

Python 3.13 · FastAPI · LangGraph · FAISS/Jina · React/Vite/TypeScript · uv.

LLM em três tiers (`CLASSIFY`, `FAST`, `SMART`) com fallback entre DeepSeek,
Groq, MiniMax, Qwen, Anthropic e Gemini. A configuração efetiva vive em
`llm_setup.ROUTES`; agentes nunca instanciam provider diretamente.

---

## Setup

```bash
uv sync                        # cria o venv (Python 3.13) e instala deps
cp .env.example .env           # configure uma ou mais chaves de provider
```

Sem nenhuma chave o jogo usa `MockLLM`: continua jogável, determinístico e sem rede.

---

## Rodar

```bash
# Jogar no terminal (CLI)
uv run python game_engine.py

# API REST (backend para frontend web/mobile)
uv run uvicorn api:app --reload --port 8000

# Testes (offline, não exigem API key)
uv run pytest

# Lint Python + conteúdo
uv run ruff check .
uv run python scripts/validate_content.py

# Reindexar lore/regras após editar data/codex/ ou data/rules.txt
uv run python rag.py
```

Frontend principal:

```bash
cd web
npm install
npm run build                  # web/dist passa a ser servido pela API
npm run dev                    # :5173 com proxy para :8000
```

### Superficies operacionais (SPEC-221)

- `/metrics`: em perfis Postgres exige `Authorization: Bearer $RPG_METRICS_TOKEN` (>=32 chars)
  e responde **404** sem token valido (ou se a env nao estiver definida; nada e exposto, o boot
  nao muda). Em `legacy` sem a env o scrape segue aberto; com a env, exige. Sondas sem token
  valido: 12 req/min/IP (quando `RPG_RATE_LIMIT>0`; scraper autenticado isento) e bloco SQL cacheado 15 s (`RPG_METRICS_SQL_CACHE_S`); falha de DB
  mantem os ultimos valores e publica `rpg_metrics_db_error 1`. Prometheus local: adicione
  `authorization: {credentials_file: /etc/prometheus/metrics_token}` ao job `valoria-api`.
- Respostas de `/game`, `/account` e `/auth` saem com `Cache-Control: no-store`; HSTS
  (`max-age=63072000; includeSubDomains`, sem `preload`) so com `RPG_COOKIE_SECURE=1`; CSP com
  `form-action 'self'` (`style-src 'unsafe-inline'` mantido, divida registrada).
- Teto de body (HTTP 413 `payload_too_large`): 256 KiB por default, 64 KiB em `/game/new` e
  `/game/prologue`, 8 MiB+64 KiB em `/account/transcriptions`, 320 KiB no webhook Stripe (o handler
  aplica o proprio teto de 256 KiB). Upload chunked sem `Content-Length` e cortado por contagem.

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

Durante um conflito, a LLM só interpreta a intenção/prepara a cena e narra o
resultado canônico. Cartas, rolagens 2d10, dano, Ferimentos, Reações, fuga e IA
tática são resolvidos em Python.

---

## Estrutura

```
main.py / state.py / llm_setup.py / rag.py / persistence.py
gamedata.py / combat_mechanics.py / world_utils.py / character_creator.py
game_engine.py (CLI)   api.py (REST)
agents/   # router, campaign_manager, storyteller, combat, npc, loot, archivist, ...
data/     # codex/, rules.txt, bestiary.json, classes.json, artifacts.json, ...
services/conflict_orchestrator.py  # motor tático determinístico
web/     # frontend React/Vite
tests/   # suíte offline completa; contratos LLM reais ficam em markers opt-in
```

Detalhes de cada módulo e convenções em `CLAUDE.md` e `ESTADO_ATUAL.md`.
