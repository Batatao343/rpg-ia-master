# SPEC — Grounding canônico de locais na memória

> **Status:** `in-progress`
> **Criada:** 2026-08-28 · **Atualizada:** 2026-09-17
> **Depende de:** `hardening-memoria-proveniencia`, `replan-grounding-troca-regiao`
> **Desbloqueia:** reinício válido da matriz B

---

## 1. Contexto & Objetivo

A matriz B `20260828-163531-294638` foi interrompida ao confirmar no ledger o
fato “Anel Dourado, bairro alto de Brekmar”. O mapa canônico define o Anel
Dourado como sublocal de Nova Arcádia. O invariante existente protegia o plano
da campanha, mas não relações geográficas escritas pelo arquivista.

Esta spec fecha a fronteira antes do ledger/RAG, protege saves já contaminados e
faz a mesma regressão aparecer em teste curto.

## 2. Requisitos

- **R1** — Python detecta afirmações explícitas de pertencimento entre um local
  canônico e uma região canônica incorreta.
- **R2** — Menções de viagem/comparação entre duas regiões não são rejeitadas.
- **R3** — Fato contraditório é recusado por `validate_memory_fact` e auditado.
- **R4** — Resumo contraditório não substitui o resumo anterior.
- **R5** — Ledger legado permanece auditável, mas não entra no ContextPack.
- **R6** — O playtest emite `memory.location_grounding` como `error` no turno em
  que um fato novo contraditório surgir.
- **R7** — O prompt recebe local e região derivados de `world_map.json`; a LLM
  não é autoridade para essa relação.

### Fora de escopo

- Validar toda proposição livre de lore ou relações não geográficas.
- Reescrever automaticamente o fato errado para outra região.

## 3. Design técnico

- `services/memory_provenance.py`: detector fechado baseado em nomes/regiões do
  mapa e filtro de resumo.
- `agents/archivist.py`: âncora no prompt e fail-closed do resumo.
- `services/context_builder.py`: quarentena de ledger/vetor legado.
- `playtest/invariants.py`: erro observável apenas para fatos novos (ou auditoria
  integral quando não há snapshot anterior).

## 4. Plano passo a passo

1. Reproduzir a frase exata e contraexemplos válidos em unit tests.
2. Implementar detector, validator e quarentena.
3. Fiar prompt/resumo e invariante.
4. Rodar suíte completa e reiniciar a B desde o par 1.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Corpus determinístico verifica pertencimento correto/incorreto, viagem e
negação direta com expectativas independentes. Não se promete detectar toda
afirmação livre; a campanha real mede cobertura linguística fora desse corpus.
Gates no [adendo pré-matriz](remediacao-local-contratos-pre-matriz.md).

- [x] Frase exata da B é rejeitada e auditada.
- [x] Menção válida Anel Dourado→Brekmar como viagem é aceita.
- [x] ContextPack não expõe o fato legado contraditório.
- [x] Invariante acusa a regressão sem long run.
- [x] Suíte completa offline verde.
- [x] Guard de FallbackLLM: usa o guard existente do arquivista.
- [x] Saves antigos permanecem carregando; somente contexto ativo é filtrado.
- [ ] Smoke real dirigido de memória geográfica confirma integração; B integral é gate global separado.

## 6. Smoke real

A matriz B reinicia do par 1. Qualquer `memory.location_grounding` interrompe o
ciclo novamente.
Gate bloqueado por HTTP 402 DeepSeek; ver
[fechamento local](../docs/fechamento-local-2026-09-17.md).

## 7. Riscos & compatibilidade

O detector cobre apenas construções explícitas de pertencimento e prefere falso
negativo a bloquear frases legítimas de deslocamento. O texto rejeitado fica no
audit de rejeições, não é corrigido silenciosamente.
