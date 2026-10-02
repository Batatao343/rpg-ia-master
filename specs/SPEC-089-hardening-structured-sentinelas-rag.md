# SPEC — Resiliência de structured output, sentinelas e storage RAG

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `roteamento-multi-provider`, `embeddings-provider`
> **Desbloqueia:** rerun real sem `npc_null` nem erro FAISS oculto

---

## 1. Contexto & Objetivo

Três falhas de borda independentes apareceram juntas no smoke: retorno
estruturado `None` foi aceito como sucesso sem tentar fallback; texto `"null"`
virou NPC real; e um ID Unicode falhou ao gravar FAISS no Windows. Esta spec
fecha as três fronteiras antes de ampliar o comportamento.

## 2. Requisitos

- **R1 — Pós-condição estruturada.** Para schema Pydantic, só o tipo esperado é
  sucesso. Com `include_raw`, `parsed` deve ter o tipo e `parsing_error` ser
  nulo. `None`, `AIMessage` ou tipo errado roteiam ao próximo candidato.
- **R2 — Plain invoke compatível.** Chamadas sem structured output aceitam os
  tipos atuais e todos os candidatos inválidos ainda retornam `AIMessage` de
  fallback, sem lançar ao grafo.
- **R3 — Sentinelas.** Helper compartilhado normaliza vazio,
  `null|none|nil|n/a|undefined|nenhum|ninguém` para `None`, com strip/casefold.
- **R4 — Rotas seguras.** Router só grava alvo na rota aplicável; NPC sem alvo
  escolhe alguém em cena ou delega ao storyteller; combate usa fallback seguro.
  Nenhum cache/contexto cria ou reativa `npc_null`.
- **R5 — Loot fechado.** `loot_context` aceita apenas
  `TREASURE|SHOP|CRAFT|None`.
- **R6 — Paths portáveis.** Componentes ASCII seguros existentes preservam o
  path legado. Unicode, reservado Windows, separador, ponto/ponto-ponto ou
  trailing dot/space vira slug ASCII + hash do ID lógico, sem escapar da raiz.
- **R7 — Falha observável.** Escritas de memória retornam `bool` e emitem evento
  RAG; falha não derruba o turno, mas não pode parecer sucesso.
- **R8 — Rede finita.** O cliente Jina usa `httpx`, timeout configurável e no
  máximo uma repetição para falha transitória (`TransportError`, 408, 429 ou
  5xx). Esgotado o limite, R7 recebe o erro real. O retry nunca troca o provider
  pinado do índice.

### Fora de escopo

- Apagar caches legados.
- Alterar IDs lógicos no estado ou conteúdo.

## 3. Design técnico

- `RoutedLLM` guarda o schema esperado na transformação e valida o retorno antes
  da telemetria de sucesso.
- `services/input_normalization.py` concentra `optional_entity_ref`.
- `rag._safe_storage_component(value, prefix)` usa NFKD, allowlist e SHA-256
  curto; `_get_session_path` e `_get_npc_path` validam containment.
- `rag._JinaEmbeddingsHTTPX` implementa `Embeddings` sem o cliente indireto
  `requests`; `EMBEDDING_TIMEOUT_SECONDS` (30s) e
  `EMBEDDING_MAX_ATTEMPTS` (2) limitam toda chamada.

## 4. Plano passo a passo

1. **Testes/implementação:** structured `None`/tipo errado → fallback; plain
   invoke intacto.
2. **Testes/implementação:** matriz de sentinelas, rota STORY sem alvo residual,
   NPC fallback e save legado com `npcs["null"]`.
3. **Testes/implementação:** roundtrip `npc_a_figura_pálida`, colisões,
   `CON`, `..`, `npc/a`, path ASCII legado e falha de escrita.
4. **Testes/implementação:** Jina timeout/retry transitório, resposta inválida
   e propagação do erro final para a telemetria RAG.

## 5. Critérios de aceite

- [x] Retorno estruturado inválido nunca conta como sucesso.
- [x] Nenhum `npc_null` novo ou reativado.
- [x] IDs Unicode persistem em path estável e portável.
- [x] Falha RAG chega à telemetria/invariante.
- [x] Chamada Jina nunca fica pendurada indefinidamente e retry não troca o
  espaço vetorial do índice.
- [x] Saves antigos carregam e paths ASCII existentes permanecem.
- [x] Suíte completa verde.

## 6. Smoke test com LLM real

Forçar ao menos um fallback estruturado, conversar com NPC acentuado e confirmar
gravação/consulta de memória, sem sentinela ou erro oculto.

**Evidência (2026-08-02):** 148 operações RAG na matriz aceita, zero falha;
fallback Groq concluiu três respostas estruturadas. O reset de conexão e o hang
Jina encontrados durante a primeira tentativa motivaram timeout/retry finitos e
foram cobertos por regressão antes das reruns.

## 7. Riscos & compatibilidade

O novo nome físico só vale para IDs inseguros; índices ASCII permanecem onde
estão. A validação pós-provider complementa — não substitui — os guards dos nós.
