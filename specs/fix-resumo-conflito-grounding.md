# SPEC — Lifecycle do resumo de conflito e grounding narrativo

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `conflito-12`, `hardening-structured-sentinelas-rag`
> **Desbloqueia:** vertical vitória/fuga→loot→memória auditável

---

## 1. Contexto & Objetivo

`ConflictSummary` é produzido ao terminar o combate, mas loot, archivist e
persistência o ignoram; sua validação narrativa existe só em testes. Ao mesmo
tempo, o smoke gravou prosa contraditória/sem grounding: viagem impossível,
item inexistente e memória de sessão misturada ao bloco rotulado como lore.

Esta spec torna o resumo canônico uma mensagem de domínio com lifecycle
explícito e impede que prosa rejeitada seja promovida a fato persistente.

## 2. Requisitos

- **R1 — Lifecycle.** Presença de `conflict_summary` significa pendente.
  Combate produz; loot enriquece; archivist consome/persiste exatamente uma vez
  e limpa. Fuga/rendição sem loot segue direto ao archivist.
- **R2 — Loot canônico.** Loot usa `encounter_level` do resumo/combate, não
  perigo bruto, e registra ouro/itens efetivamente aplicados em `loot_obtido`.
- **R3 — Persistência.** Save/load preserva summary pendente.
- **R4 — Autoridade narrativa.** Mortos, fuga, resultado, Cicatriz e loot vêm
  do summary. Contradição usa fallback mecânico, não é arquivada.
- **R5 — Memória segura.** `summary_facts` é persistido diretamente e uma vez.
  Em turno com summary ou proposta/item rejeitado, fatos inferidos da prosa não
  entram no RAG.
- **R6 — Lore separado.** Lore global e memória de sessão têm blocos/labels
  distintos; memória nunca é apresentada como cânone.
- **R7 — Viagem/item.** Destino inválido recebe recusa determinística e não
  altera local nem memória. Item desconhecido/rejeitado é removido da afirmação
  factual e não chega ao inventário/RAG.
- **R8 — NPC e mundo.** Prompt NPC recebe nome+local+pergunta+lore público e não
  inventa rumor factual. Pulso de mundo persiste somente consequência
  determinística aplicada.
- **R9 — Higiene de prosa/fatos.** Remover preâmbulos meta; facts aceitam
  allowlist de chaves/tamanho e descartam wrappers/transcritos.
- **R10 — Observabilidade.** Invariante `summary.lifecycle` acusa summary
  envelhecido, consumo duplicado ou término sem fato canônico. Cada summary tem
  `conflict_id`; o ledger persistido e limitado torna o consumo idempotente.
  Um `combat_ended` não pode deixar summary pendente ao fim do mesmo invoke,
  salvo erro RAG explícito; mudar o conteúdo no primeiro turno ou consumi-lo só
  no turno seguinte não produz falso verde.
- **R11 — Commit atômico da resposta.** Se qualquer `proposed_event` da resposta
  do storyteller for inválido, nenhum outro efeito colateral derivado daquela
  mesma resposta da LLM — beat/XP, item, reputação, NPC, quest — é aplicado.
  Efeitos determinísticos já resolvidos antes da LLM, como viagem, descanso e
  pulso de mundo, permanecem.
- **R12 — Rejeição e retry robustos.** O archivist identifica rejeições novas
  por identidade/conteúdo, inclusive com o buffer de auditoria cheio. Uma
  política `canonical_only` pendente só é confirmada depois de uma escrita
  durável real; ausência de fatos não pode apagar silenciosamente um erro/retry
  anterior. Falha de memória de NPC entra em fila limitada e operation-scoped
  (`npc_id` + fato sanitizado), persistida no save e removida apenas após retry
  bem-sucedido. A pré-validação em lote deve observar a mesma evolução de
  projection/regras do processador autoritativo.

### Fora de escopo

- Avaliar subjetivamente toda a qualidade literária.
- Criar um fact-checker LLM adicional.
- Mecânica nova de prisão/expulsão.

## 3. Design técnico

`services/conflict_summary.py` é a fonte canônica. `agents/loot.py` usa
`loot_context` e devolve summary enriquecido. `agents/archivist.py` prioriza
`summary_facts`, persiste-os e limpa o campo. `rag.py/context_builder.py`
separam busca global e sessão. `world_utils.py` reconhece viagem explícita
inválida. `services/prose_guard.py` sanitiza apenas preâmbulo inequivocamente
meta e afirmações rejeitadas. O storyteller trata seus campos estruturados como
uma unidade de commit; o processador expõe identidade estável de rejeição.

## 4. Plano passo a passo

1. **Testes:** save pendente e grafo vitória→loot→archive fecham lifecycle;
   loot usa nível e aparece no summary. A vertical usa `main.app`/stream real do
   grafo e comprova, no mesmo invoke, ordem combat→loot→archivist, write único,
   ledger e clear.
2. **Implementação:** persistência, loot e archivist.
3. **Testes:** morto não reaparece/foge; summary contraditório usa fallback;
   facts são gravados uma vez.
4. **Implementação:** validação narrativa e fatos canônicos.
5. **Testes:** `mapa_breaker` não chega a destino impossível; item/evento
   rejeitado não aparece em mensagem, resumo ou RAG; lore/memória separados.
6. **Implementação:** grounding, NPC/world pulse e prose guard.
7. **Testes/implementação:** lote misto válido/inválido não aplica side effects
   da resposta; buffer cheio não mascara rejeição nova; retries vazios não
   produzem falso commit; memória NPC falha→save/load→retry→clear sem duplicar.

## 5. Critérios de aceite

- [x] Summary percorre produce→enrich→consume→clear exatamente uma vez.
- [x] Vertical do grafo consome no mesmo invoke; invariante não aceita atraso sem
  erro RAG explícito.
- [x] Loot e memória refletem apenas efeitos aplicados.
- [x] Save/load preserva estado pendente.
- [x] Viagem/item/evento rejeitado não contamina narrativa ou RAG.
- [x] Lore global e memória de sessão não são confundidos.
- [x] NPC não inventa fato canônico ausente.
- [x] Preâmbulos meta são removidos.
- [x] Resposta estruturada inválida não produz efeitos colaterais parciais.
- [x] Rejeições e retries continuam fail-loud com buffers cheios/vazios.
- [x] Suíte completa verde.

## 6. Smoke test com LLM real

Executar uma vertical completa até vitória/fuga, auditar JSONL/save/memória e
rodar `mapa_breaker`, `secret_rusher` e NPC acentuado. Confirmar lifecycle,
ausência de contradição e nenhum segredo/fato inventado persistido.

**Evidência (2026-08-02):** lifecycle de resumo e grounding de efeitos aplicados
passaram na matriz offline e real. O smoke revelou um problema distinto e mais
amplo — inferência do storyteller promovida pelo archivist — documentado na
spec `hardening-memoria-proveniencia`; ele não reabre o contrato específico do
resumo canônico de conflito.

## 7. Riscos & compatibilidade

O archivist fica mais conservador: é preferível perder uma formulação livre a
persistir um falso cânone. Saves sem summary continuam compatíveis.
