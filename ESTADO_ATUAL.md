# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> Leia isto **primeiro** ao retomar o trabalho.
> Complementa `CLAUDE.md` (arquitetura) e `REFERENCE.md` (decisões técnicas).
> Última atualização: 2026-06-26

---

## TL;DR — Em que pé está

**Fase 2 COMPLETA + multi-provider LLM + typewriter UX.** Grafo LangGraph roda fim-a-fim sem crashar. Suíte **96 testes offline verdes** (`uv run pytest --ignore=tests/test_real_llm.py`).

**Última sessão (2026-06-26):**
- `get_llm()` agora suporta Gemini, Ollama, OpenAI e qualquer endpoint OpenAI-compatível (Qwen, LM Studio) via `LLM_PROVIDER` + vars no `.env`. Sem tocar nos agentes.
- Narrativa do narrador aparece com efeito typewriter (palavra a palavra) no frontend React.
- `stream_ctx.py` criado com ContextVar SSE (infraestrutura para streaming real futuro).
- `MockLLM.stream()` adicionado para compatibilidade.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 96 testes offline verdes
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python rag.py                 # reindexar lore/regras (data/*.txt)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers (novo):**
```env
LLM_PROVIDER=gemini          # padrão — requer GOOGLE_API_KEY
LLM_PROVIDER=ollama          # local — requer uv sync --extra ollama + OLLAMA_MODEL_FAST=llama3.2
LLM_PROVIDER=openai          # requer uv sync --extra openai + OPENAI_API_KEY
LLM_PROVIDER=openai_compat   # Qwen, LM Studio, etc — OPENAI_BASE_URL + OPENAI_API_KEY
```
Ver `.env.example` para lista completa de vars.

**Modo simulado:** sem `GOOGLE_API_KEY` (ou `LLM_PROVIDER` diferente de gemini sem chave), `get_llm()` devolve `MockLLM` — jogo jogável sem rede.

---

## Quota Gemini (IMPORTANTE)

Free tier = **20 req/dia por modelo** (flash e pro têm buckets separados). E2e em lote inviável. `get_llm()` é fail-fast (`max_retries=0`): `429` falha em ~3s em vez de travar minutos.

**MockLLM esconde bugs:** devolve instâncias Pydantic válidas → bugs de mapeamento de campo só aparecem no Gemini real. Validar nós novos com a chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate profundo:** IA identifica ação + narra; Python resolve tudo (`combat_mechanics.py`) — iniciativa, DoT/condições, custos stamina/mana, cooldowns, save por atributo
- **Fase 0:** grafo de 9 locais, relógio, viagem (fog of war), descanso, gating por classe
- **Fase 2:** fações com objetivos, reputação, não-onisciência, ascensão que muda o mundo, encontros temáticos, memória de NPC vetorizada, world_simulator off-screen
- **Beats de campanha** avançam via `StoryUpdate.beat_completed`; HUD mostra objetivo
- **Multi-provider LLM:** Gemini/Ollama/OpenAI/Qwen via `LLM_PROVIDER` no `.env`
- **Typewriter effect:** narrativa revela texto palavra a palavra no frontend
- Loot/Craft/Shop/Treasure + economia (sinal do ouro forçado em Python)
- Memória híbrida: resumo curto (archivist) + RAG FAISS por sessão
- Persistência: saves JSON + RAG por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Já blindados: `router.py`, `character_creator.py`, `combat.py` (isinstance). Demais agentes: dentro de `try`.

---

## Bugs conhecidos (sessão 2026-06-26)

| Bug | Local provável |
|---|---|
| Inventário: item narrado não entra no inventário | `agents/loot.py` ou `world_utils.add_to_inventory` |
| Capitalização estranha em itens (letra maiúscula fora de lugar) | Grep `title()` / `capitalize()` nos agentes |
| NPC errado responde fala destinada a outro | `agents/router.py` — `active_npc_name` não filtra |
| Morte do player sem narrativa (só tela de morte) | Fluxo final de combate — adicionar death_narrative |

**Design:** campaign manager coloca plot twists com muita frequência — aumentar intervalo de triggers de replan.

---

## Limitações conhecidas

- **Inventário inicial** usa nomes livres, não IDs — `ARTIFACTS_DB.get(item_id)` não acha (sem bônus de combate desde nível 1)
- **API stateless por save** — sem sessão concorrente; migrar para Postgres+pgvector ao escalar
- **Saves antigos** (schema `class`/`abilities`) carregam mas campos novos ficam ausentes

---

## Checklist ao começar a próxima tarefa

1. `uv run pytest` verde antes de mexer
2. Nó novo com `with_structured_output`? Garanta o guard de fallback (ver seção CRÍTICA)
3. Mudou schema do player/estado? Atualizar `state.py` + `game_engine.py` + `api.py` + creator
4. Novo agente no grafo? Conectar ao `archivist` no fim (ver REFERENCE.md)
5. Editou `data/world_lore.txt` ou `data/rules.txt`? Rodar `uv run python rag.py`
6. Mecânica nova (números)? Python determinístico, não LLM. Não confiar em sinal/valor do LLM sem validar
7. **Ao finalizar:** `uv run pytest` verde + atualizar ESTADO_ATUAL.md + ROADMAP.md
