# RPG Engine V8 (LangGraph + Gemini)

Uma engine modular de RPG por turnos, construída sobre LangGraph/LangChain e Google Gemini, com RAG para manter a lore, contratos de validação e modelos em camadas (FAST/SMART) para equilibrar custo e inteligência.

## Visão Geral
- **Grafo de agentes LangGraph** conecta roteamento, narrativa, combate, regras e NPCs para processar cada turno do jogador (`main.py`).
- **ModelTier** define dois níveis de LLM (gemini-1.5-flash e gemini-1.5-pro) para escolher custo vs. raciocínio (`llm_setup.py`).
- **RAG multil índice** consulta lore e regras antes de gerar conteúdo ou resolver física (`rag.py`).
- **Validações Pydantic** protegem atualizações de estado e entradas de dano/estamina contra alucinações (`engine_utils.py`).
- **Planejamento de campanha** mantém um `quest_plan` que o Storyteller consome para garantir início, meio e fim coerentes (`agents/storyteller.py`).

## Requisitos
1. Python 3.11+ e dependências do `pyproject.toml` (LangGraph, LangChain, Streamlit, etc.).
2. Variáveis de ambiente:
   - `GOOGLE_API_KEY`: chave para Gemini e embeddings.
   - Opcional: configure proxys de rede conforme necessário.
3. Índices RAG pre-gerados em `faiss_lore_index/` e `faiss_rules_index/` (ou execute a ingestão abaixo).

## Ingestão de Lore e Regras
Execute uma vez para criar/atualizar os índices FAISS a partir dos textos base:
```bash
python rag.py
```
Isso indexa `world_lore.txt` em `lore` e `rules.txt` em `rules` e habilita consultas de contexto para narrativa, combate e regras.

## Como Executar
### CLI / Simulação
Use o runner de testes interativos que percorre o grafo completo:
```bash
python test_runner.py
```
### UI (Streamlit)
Interface web com HUD, histórico e persistência:
```bash
streamlit run app.py
```
O app carrega o estado inicial, permite salvar/carregar jogos e encaminha cada entrada pelo grafo de agentes.

## Testes e Diagnóstico
- Suite completa com cenários interativos e mocks:
```bash
python test_suite_complete.py
```
- Testes unitários de nós (requer dependências de LangChain instaladas):
```bash
python -m pytest tests/test_nodes.py
```

## Estrutura de Pastas (essencial)
- `agents/`: nós de narrativa (`storyteller.py`), combate (`combat.py`), regras, NPCs e bestiário.
- `rag.py`: utilitários de embedding, ingestão e consulta multi-índice.
- `state.py`: schema tipado do estado de jogo (player, mundo, inimigos, npcs, mensagens).
- `engine_utils.py`: contratos de entrada/saída (Pydantic) e utilidades de aplicação de dano/estado.
- `llm_setup.py`: seleção de modelo FAST/SMART e fallback resiliente.
- `app.py`: interface Streamlit.
- `test_suite_complete.py`: suite manual para validar fluxo completo.

## Fluxo de Um Turno (alto nível)
1. A entrada do jogador vai para `dm_router`, que decide o próximo nó (storyteller, combate, regras ou NPC).
2. Cada nó invoca Gemini com o tier adequado e, quando aplicável, consulta RAG para manter consistência de lore e regras.
3. Atualizações de estado passam por validação; o Storyteller consome `quest_plan` para manter arco narrativo; o combate usa lógica tática especial para chefes.
4. O grafo encerra o turno ou retorna ao roteador para processar ferramentas (ex.: rolagem de dados).
