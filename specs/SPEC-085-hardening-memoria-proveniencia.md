# SPEC — Proveniência e confiança da memória narrativa

> **Status:** `done`
> **Criada:** 2026-08-02 · **Atualizada:** 2026-08-02
> **Depende de:** `fix-resumo-conflito-grounding`, `fase-2.6-structured-events`
> **Desbloqueia:** memória de sessão auditável fora do fluxo de conflito

---

## 1. Contexto & Objetivo

O smoke real pós-correções mostrou que o `secret_rusher` não revelou nenhum
segredo estruturado, mas a prosa especulativa sobre Valerius foi resumida e
persistida como se fosse fato. Não houve vazamento literal do segredo canônico
oculto: o Rei Subterrâneo é lore pública, e o pacto secreto real envolve Daruun.
O defeito é de proveniência: rumor, hipótese e interpretação narrativa podem
voltar em turnos posteriores com autoridade de memória factual.

Esta spec estende o grounding já aplicado ao `ConflictSummary` para a memória
narrativa geral. O objetivo é manter fatos aplicados como fonte de verdade e
preservar rumores somente com rótulo e confiança explícitos, sem transformar
uma inferência do narrador em cânone da campanha.

## 2. Requisitos

- **R1 — Classes de proveniência:** todo fato candidato à memória deve ser
  classificado como `canonical_event`, `player_observation`, `npc_claim` ou
  `inference`, com `source_id`/turno quando disponível.
- **R2 — Confiança fechada:** usar enum `confirmed | reported | speculative`;
  texto livre da LLM não pode elevar sua própria confiança.
- **R3 — Commit canônico:** somente eventos aceitos, projeção, quest log,
  `ConflictSummary` consumido e fatos explícitos de NPC/codex podem entrar como
  `confirmed`.
- **R4 — Rumor não vira fato:** `npc_claim` e `inference` podem ser recuperados
  para continuidade, mas o contexto deve rotulá-los e proibir sua apresentação
  como fato confirmado.
- **R5 — Segredos:** conteúdo `hidden`/`secret` só pode ser persistido como
  confirmado depois de `secret_revealed` aceito para o mesmo ID.
- **R6 — Atomicidade:** falha de structured output, validação ou persistência
  mantém o item pendente para retry sem commit parcial ou duplicado.
- **R7 — Compatibilidade:** memórias antigas sem metadados continuam legíveis e
  entram como `legacy_unverified`, nunca como confirmação automática.
- **R8 — Observabilidade:** JSONL do playtest registra contagem por proveniência,
  rejeições e promoções; invariante acusa fato confirmado sem fonte aplicável.

### Fora de escopo

- Detectar toda contradição semântica possível no texto livre.
- Reescrever o Codex ou alterar visibilidade de lore pública.
- Impedir personagens de mentir, especular ou espalhar rumores na ficção.
- Trocar o provedor de embeddings ou reindexar os índices globais.

## 3. Design técnico

- **`state.py`:** acrescentar schema persistido de fato de memória com
  `text`, `provenance`, `confidence`, `source_id`, `source_turn` e
  `canonical_entity_ids`.
- **`agents/archivist.py`:** produzir candidatos estruturados, validar contra
  eventos/projeção/reveals e separar fatos confirmados de relatos e inferências.
- **`services/context_builder.py`:** renderizar confiança/proveniência e manter
  rumores fora da seção de fatos canônicos.
- **`rag.py` / `services/memory_retry.py`:** persistir metadados e preservar a
  semântica de retry idempotente.
- **`playtest/invariants.py`, `playtest/telemetry.py`:** detectar confirmação sem
  fonte e expor métricas de memória.

Formato proposto:

```json
{
  "text": "Valerius pode ter feito um pacto com o Rei Subterrâneo.",
  "provenance": "inference",
  "confidence": "speculative",
  "source_id": null,
  "source_turn": 18,
  "canonical_entity_ids": ["npc_valerius", "mon_rei_subterraneo"]
}
```

## 4. Plano passo a passo

### Etapa 1 — Contrato e compatibilidade

1. **Testes:** roundtrip do novo schema; memória legada vira
   `legacy_unverified`; enums rejeitam valores livres.
2. **Implementação:** schemas, serialização e migração lazy.
3. **Verificação:** suíte focada verde.

### Etapa 2 — Classificação e commit

1. **Testes:** evento aceito vira confirmado; rumor permanece reportado;
   inferência permanece especulativa; segredo sem reveal é recusado.
2. **Implementação:** validação do archivist e commit idempotente.
3. **Verificação:** nenhuma resposta estruturada inválida gera efeito parcial.

### Etapa 3 — Recuperação e observabilidade

1. **Testes:** context pack separa fatos/rumores; invariante detecta promoção
   indevida; JSONL contabiliza proveniência e rejeições.
2. **Implementação:** context builder, telemetria e relatório.
3. **Verificação:** `secret_rusher` offline e real não promovem hipótese.

## 5. Critérios de aceite

- [x] Toda memória nova tem proveniência e confiança fechadas.
- [x] Inferência/rumor nunca aparece como fato confirmado sem evento-fonte.
- [x] Segredo não revelado não é confirmado nem recuperado como conhecimento.
- [x] Memória legada permanece legível e explicitamente não verificada.
- [x] Retry é idempotente e falha continua observável.
- [x] Playtest expõe promoção indevida como violação `error`.
- [x] `uv run pytest` e smoke real verdes.

## 6. Smoke test com LLM real

Rodar `secret_rusher`, `diplomatico` e `npc_only` por 30 turnos. Auditar memória,
context packs e eventos: rumores podem existir rotulados, mas nenhuma inferência
pode virar `confirmed`; o caminho positivo exige um `secret_revealed` aceito.

## 7. Riscos & compatibilidade

- Structured output adicional aumenta tokens/latência do archivist; limitar o
  número de candidatos por turno.
- Memória legada perde autoridade automática, mas não é descartada.
- Classificação semântica perfeita não é prometida; o gate determinístico de
  fonte é a barreira de segurança.

## 8. Execução e evidências — 2026-08-02

- `services/memory_provenance.py` fecha os enums, deriva confiança sem aceitar
  autopromoção da LLM, gera IDs estáveis, valida fontes e bloqueia assinaturas
  secretas sem `secret_revealed` aceito para o mesmo ID.
- O save passou a persistir `memory_facts`, `pending_memory_facts`, rejeições e
  promoções. Strings legadas migram lazy para
  `legacy_unverified/speculative`.
- O archivist converte texto livre em `inference/speculative`; eventos e
  `ConflictSummary` recebem fonte mecânica. Writes FAISS carregam metadata e o
  retry global é atômico/idempotente. Eventos fora da cadência apenas agendam a
  indexação derivada, sem forçar uma chamada SMART.
- O context pack separa `CONFIRMADO`, `RELATO`, `ESPECULATIVO`,
  `NÃO VERIFICADO` e resumo narrativo; conteúdo secreto ainda não revelado é
  omitido inclusive quando vem de vetor legado/NPC.
- JSONL e summary expõem ledger, writes por proveniência, rejeições e promoções;
  `memory.confirmed_without_source` é violação `error`.
- Achado operacional do smoke: Anthropic e Gemini não recebiam
  `LLM_TIMEOUT_SECONDS`, permitindo hang no fallback SMART. Ambos agora têm
  timeout explícito (`timeout`/`request_timeout`) e regressão dedicada.

Smoke offline (seed 42, 30 turnos):

- `secret_rusher` `20260802-182701-821956`: 30/30, 0 erros, 0 violações.
- `diplomatico` `20260802-182701-774790`: 30/30, 0 erros, 0 violações.
- `npc_only` `20260802-182701-779416`: 30/30, 0 erros, 0 violações.

Smoke real aceito (seed 42, 30 turnos):

- `secret_rusher` `20260802-184026-492723`: 30/30, 0 erros, 0 violações
  `error`, 70/70 invokes, US$ 0,01960, 12 `inference/speculative` e somente 1
  `canonical_event/confirmed` com evento-fonte; 0 promoções indevidas.
- `diplomatico` `20260802-234057-869414`: 30/30, 0 erros, 0 violações
  `error`, 71/71 invokes, US$ 0,01988, 12 `inference/speculative`, nenhum
  `confirmed`.
- `npc_only` `20260802-235207-031964`: 30/30, 0 erros, 0 violações,
  86 invokes (1 falha de conexão recuperada), US$ 0,02422, 15 writes
  `npc_claim`, nenhum relato promovido a `confirmed`, 0 falhas RAG.

Tentativas diagnósticas rejeitadas como aceite:

- `20260802-182929-811945`: timeout externo aos 10 minutos no turno 29/30.
- `20260802-184553-896085`: hang no turno 10 revelou o timeout ausente nos
  builders Anthropic/Gemini; árvore de smoke foi encerrada e a correção aplicada.

Gate final: `uv run pytest` → **1349 passed, 1 skipped, 14 deselected**.
