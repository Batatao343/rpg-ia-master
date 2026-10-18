# SPEC-217 J1 — registro de variantes (R4)

Corpus: **DEV** apenas (`evals/experiments/data/spec217_dev.jsonl`,
`sha256:256d24bd…5f3d`; 59 casos, 52 elegíveis ao CLASSIFY, 7 gates Python — a
sonda do router real concorda com o campo `python_gate` em 59/59). O FROZEN não
foi aberto: só o hash do lock é registrado nos raws.

Código: `evals/experiments/jev_router_hybrid.py` (features, perguntas, política
híbrida, score e seleção — puros) e `evals/experiments/spec217_j1.py` (runner live
com ledger em disco). Testes: `tests/test_spec217_j1.py`.

## Pré-registro (escrito e commitado antes de qualquer chamada live)

**Desenho de chamadas (≤ 60, zero CLASSIFY):**

- **P1 — triagem, 52 chamadas:** uma chamada Jev por caso elegível com o estado
  enriquecido e **todas** as perguntas de rota (`route_legacy`, `route_plain`,
  `route_rich`) mais `target` quando há candidatos de cena. Todas as variantes de
  política são pontuadas offline a partir dessas mesmas respostas.
- **P2 — verificação de estrutura, 8 chamadas:** a requisição **exata** da
  variante escolhida (uma pergunta de rota + alvo, se houver) nos 8 casos DEV
  `critical=combat_escalation`. Mede latência da estrutura real e concordância com
  a P1. Não reabre a seleção, salvo escalada insegura (registrada).
- Ledger durável `evals/runs/jev-router-ab/spec217-j1/ledger.json` incrementa
  **antes** de cada requisição; teto J1 60 / spec 160; qualquer erro de provider
  (HTTP, timeout, resposta inválida) para o run sem score; `max_retries=0`.

**Espaço de variantes (política, tudo offline sobre a P1):**
`label ∈ {legacy, plain, rich}` × `alvo ∈ {sem, com}` × `guarda de combate ∈ {sem, com}`
× `τ ∈ {0,50, 0,55, …, 0,90}` = 108 políticas. Em todas: gates Python antes;
`none` ⇒ CLASSIFY; confiança de rota (e de alvo, quando houver) < τ ⇒ CLASSIFY;
`loot` ⇒ CLASSIFY (o `loot_context` pelo Jev está fora de escopo); alvo não
representável (> 20 ou sem ID canônico) ⇒ CLASSIFY; sem estágio de alvo,
`npc_actor`/`combat_agent` ⇒ CLASSIFY. Guarda de combate: `combat_agent` só é
aceito com `verbs∋attack` ou combate ativo.

**Métricas (por política, sobre os 52 elegíveis):** acurácia de rota standalone
do Jev (`none`→`storyteller`, como na SPEC-178); falsos positivos de combate
standalone; cobertura (fração resolvida pelo Jev); taxa de fallback/abstenção e
motivos; erros de rota e de alvo nos casos cobertos; escaladas inseguras
(`combat_agent` coberto com oráculo diferente); latência Jev p50/p95 (P1 =
requisição com 3–4 perguntas, **limite superior**); latência híbrida **estimada**
= Jev + 1.473 ms nos fallbacks (p50 real da fase router, SPEC-214 gate de
2026-10-17; nenhum CLASSIFY é chamado na J1).

Como o CLASSIFY acertou 48/48 nos elegíveis da SPEC-178, as únicas perdas que a
política híbrida pode introduzir contra A são os **erros nos casos cobertos**;
por isso a seleção usa o desempenho coberto.

**Regra de seleção:** viável ⇔ 0 escalada insegura **e** ≤ 1 erro de rota coberto
**e** 0 erro de alvo coberto. Entre viáveis, maior cobertura; empates → menos
erros → τ mais próximo de 0,50 → `plain` < `rich` < `legacy` → sem alvo/guarda
antes de com. Sem viável: mesma ordenação sobre todas (resultado reportado como
não viável). A variante escolhida e seu `τ` são congelados em código com hash.

**Referência V0 (SPEC-178, histórico, sem chamada nova):** rota Jev 46/48 nos
elegíveis da regressão; erros = `FALO COM CORVO`→`combat_agent` (2/3); p50
265,5 ms / p95 319,65 ms. SPEC-179 alvo: 6/8 representáveis.

## Resultados

(preenchido após a P1/P2 — ver abaixo)
