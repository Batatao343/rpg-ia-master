# SPEC — Rota NPC sem alvo: fallback útil + party em cena

> **Status:** `done` (2026-07-18 — 844 offline verdes; quester+npc_only mock 50t
> 0 "Ninguém responde"; smoke real: aliado cita objetivo, sozinho → gancho.
> Ordem de dev: **5/8**)
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** npcs-3-camadas (`done`), Fase 4.5 party (`done`)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achado E): o quester perdeu **7+ turnos** com a
resposta seca `"Ninguém responde."` (agents/npc.py:188 — dispara quando o
router não seta `active_npc_name`). Pior: nos turnos 96/97/99 o aliado
**Gorim estava na cena narrada** (membro de party) e mesmo assim ninguém
respondeu — a pergunta era genérica ("Pergunto a quem estiver por perto..."),
o router não escolheu alvo, e o fallback atual joga o turno fora.

Um turno custa ~15s e ~$0.001 pro jogador real — resposta de 1 linha sem
conteúdo é o pior resultado possível de um turno.

## 2. Requisitos

- **R1** — Rota NPC sem `active_npc_name`: antes de desistir, resolver alvo
  deterministicamente nesta ordem: (a) NPC com `in_scene=True` no local atual;
  (b) membro de party presente (não `waiting`); (c) `active_npc_name` do turno
  anterior se ainda em cena. Achou → conversa normal com esse alvo.
- **R2** — Sem nenhum candidato (R1 vazio): rotear para o **storyteller** com
  a ação original + instrução de narrar a ausência de interlocutores E dar um
  gancho útil (onde há gente por perto / objetivo atual). NUNCA devolver a
  string seca `"Ninguém responde."`.
- **R3** — Membros de party contam como `in_scene` para o gate da camada 3
  (npc.py já tem `in_party` bypass na conversa nomeada — estender ao caso sem
  nome via R1b).
- **R4** — Perguntas sobre "a missão/objetivo atual" com party presente:
  o NPC alvo responde usando o beat atual do `campaign_plan` no contexto
  (o quester pergunta isso o run inteiro — hoje é silêncio).

### Fora de escopo

- Mudar o gate `in_scene` de NPC nomeado fora de cena (correto hoje).
- Memória de NPC / traits (specs anteriores).

## 3. Design técnico

- **`agents/npc.py`** (`npc_actor_node`) — substituir o early-return da linha
  188 pela cascata R1; caso R2, devolver
  `{"next": "storyteller", "npc_fallback_hint": <ação original>}` — exige
  aresta condicional nova `npc_actor → storyteller` em **`main.py`** (hoje
  npc_actor → archivist fixo; adicionar conditional edge igual ao padrão do
  storyteller→combat, main.py:81).
- **`services/npc_layers.py`** — helper novo
  `npcs_in_scene(state) -> list[str]` (NPCs `in_scene` no local + party ativa);
  usado por R1 e reutilizável pela API/frontend.
- **`agents/storyteller.py`** — se `npc_fallback_hint`: cláusula no prompt
  (narrar solidão/gancho, sem inventar NPC novo em cena).
- **`agents/router.py`** — sem mudança estrutural; comentário da linha 89
  atualizado (o "Ninguém responde" deixa de existir).

## 4. Plano passo a passo

### Etapa 1 — `npcs_in_scene` + cascata de alvo
1. **Testes** (`tests/test_npc_fallback.py`):
   `test_npcs_in_scene_inclui_party_e_exclui_waiting`;
   `test_sem_nome_escolhe_npc_em_cena`; `test_sem_nome_escolhe_party`
   (cenário Gorim: party presente → Gorim responde);
   `test_alvo_do_turno_anterior_persiste`.
2. **Implementação:** helper + cascata no npc_actor_node.
3. `uv run pytest` verde.

### Etapa 2 — fallback pro storyteller
1. **Testes:** `test_sem_candidato_roteia_storyteller` (asserta `next` e que a
   resposta NÃO é "Ninguém responde."); teste de grafo: aresta
   npc_actor→storyteller→archivist executa (mock).
2. **Implementação:** edge no main.py + hint no prompt.
3. `uv run pytest` verde.

### Etapa 3 — pergunta de objetivo (R4)
1. **Testes:** `test_pergunta_de_missao_usa_beat_no_contexto` (prompt do NPC
   contém o beat atual quando a ação menciona missão/objetivo).
2. **Implementação:** injetar beat no contexto do npc_actor.
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [x] R1–R4 com testes (`tests/test_npc_fallback.py`, 9 casos)
- [x] Perfil `quester` mock 50 turnos: ZERO ocorrências de "Ninguém responde."
  (validado; `npc_only` idem)
- [x] Perfil `npc_only` continua verde (gate de NPC fora de cena intacto)
- [x] `uv run pytest` verde (suíte completa offline) — **844 passed**
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (nenhum novo;
  cascata e helpers são determinísticos)
- [x] Saves antigos continuam carregando
- [x] Smoke §6 real — Parte 1: aliado (Gorim) respondeu citando o objetivo
  (Aldo/mercador/Docas); Parte 2: sozinho → storyteller narrou gancho rico (não
  o `AIMessage` seco de turno morto)

## 6. Smoke test com LLM real

1. Com party recrutada, perguntar "o que a missão exige agora?" sem nomear
   ninguém → aliado responde citando o objetivo.
2. Sozinho no ermo, mesma pergunta → narração do storyteller com gancho
   (não a string seca).

## 7. Riscos & compatibilidade

- Grafo ganha 1 aresta condicional — conferir que npc_actor SEMPRE termina em
  archivist (direto ou via storyteller), regra do CLAUDE.md.
- MockLLM: cascata é 100% determinística; só a prosa final é LLM.
- Loop infinito npc→storyteller→npc: impossível — storyteller não devolve
  `next="npc_actor"`.
