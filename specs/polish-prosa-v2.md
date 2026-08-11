# SPEC — Polish de prosa v2: saída diegética e repetição residual

> **Status:** `done` (2026-08-03 — 1377 offline verdes; smoke real 3/3)
> **Criada:** 2026-08-03 · **Atualizada:** 2026-08-03
> **Depende de:** `polish-prosa` (`done`)
> **Desbloqueia:** sessões longas sem marcadores internos ou respostas mecânicas repetidas

---

## 1. Contexto & Objetivo

A matriz real pós-cutover registrou 44 warnings `narrative.repeated_opening`, e
o smoke `20260803-025211-710980` exibiu `Contexto do local:` e
`[ECOS DO MUNDO]` ao jogador. A primeira spec de polish instruiu o modelo e
mediu o problema, mas deliberadamente não corrigiu a saída depois da geração.

Esta fatia fecha a fronteira de apresentação em Python: marcadores do motor não
podem chegar à UI, e uma abertura idêntica recebe variação neutra e
determinística, sem nova chamada de LLM.

## 2. Requisitos

- **R1** — remover da narração visível marcadores internos conhecidos
  (`Contexto do local:`, `[ECOS DO MUNDO]`) preservando o conteúdo útil.
- **R2** — remover imperativos de prompt eventualmente ecoados (`Descreva...`,
  `Narre...`) sem apagar a prosa anterior.
- **R3** — se a nova saída repetir as primeiras seis palavras de uma abertura
  recente, prefixar uma transição neutra escolhida deterministicamente e que não
  repita a mesma moldura recente.
- **R4** — invariante `narrative.meta_leak` detecta regressão em playtest real.
- **R5** — todos os fallbacks do storyteller passam pela mesma sanitização.
- **R6** — aquisição monetária rejeitada remove o parágrafo contraditório mesmo
  quando o schema usa algarismo e a prosa escreve a quantia por extenso.

### Fora de escopo

- Segunda chamada de LLM para reescrever estilo.
- Alterar temperatura, conteúdo canônico ou resolução mecânica.

## 3. Design técnico

- `services/prose_guard.py` — `sanitize_player_facing()` e
  `vary_repeated_opening()` puros.
- `agents/storyteller.py` — aplica a fronteira antes de persistir a mensagem e
  também no fallback determinístico.
- `playtest/invariants.py` — check de marcadores internos.
- `tests/test_prose_guard.py` — regressões de sanitização, variação e invariante.

## 4. Plano passo a passo

### Etapa 1 — fronteira de saída

1. **Testes primeiro:** casos de marcador no meio, eco de imperativo, conteúdo
   preservado e fallback.
2. **Implementação:** helpers puros + uso no storyteller.
3. **Verificação:** testes focados verdes.

### Etapa 2 — repetição e observabilidade

1. **Testes primeiro:** repetição recebe moldura distinta; texto variado não muda;
   `narrative.meta_leak` aponta marcador residual.
2. **Implementação:** pós-processamento determinístico + invariante.
3. **Verificação:** smoke real curto e transcrito sem marcadores.

## 5. Critérios de aceite

- [x] R1–R6 cobertos por testes.
- [x] Smoke real sem marcador interno e sem abertura consecutiva idêntica.
- [x] `uv run pytest` verde (1377 passed, 1 skipped, 14 deselected).
- [x] Nenhum `with_structured_output` novo; guard existente preservado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Rodar explorador real por 3–5 turnos.
2. Gerar transcrito e procurar `Contexto do local`, `ECOS DO MUNDO`, `Descreva`
   e `Narre` — zero ocorrências na narração.
3. Confirmar zero `narrative.meta_leak` e zero abertura consecutiva idêntica.

## 7. Riscos & compatibilidade

- Sanitização é limitada a marcadores fechados; não tenta reescrever livremente.
- A variação só atua quando a repetição é literal nas seis primeiras palavras.
- Zero chamadas/custo adicionais de LLM.

## 8. Evidência de conclusão

- Run real final `20260803-114646-799077`: 3/3, `mock=false`, zero erro e
  violação, p95 16,4 s; transcrito sem
  `Contexto do local`, `ECOS DO MUNDO`, `Descreva` ou `Narre`.
- O smoke expôs uma quantia inválida escrita por extenso; R6 passou a remover o
  parágrafo inteiro por categoria monetária. A correção visível deixou de usar
  `[SISTEMA]` e a rejeição auditável continua em `narrative_rejections`.
