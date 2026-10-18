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

**Chamadas: 60/60 da J1** (P1 52 + P2 8; 60/160 do total da spec), zero CLASSIFY,
zero erro de provider, `max_retries=0`. Reserva interna US$ 0,60 (regra de parada,
não custo). Custo real `unavailable` (o endpoint devolve só uso: P1 69.513 tokens de
entrada / 10.114 de saída; P2 6.418 / 796). Modelo resolvido: `jev-1.13.0` em todas.
Produto: commit `c5a721c` (árvore limpa, `product_dirty=false`).

### P1 — triagem (52 elegíveis DEV, run `SPEC-217-J1-p1-20261018T122448Z`)

Acurácia standalone de rota (argmax, `none`→`storyteller`): **legacy 51/52**
(erro: `Guardo o arco na mochila`→`loot`), **plain 52/52**, **rich 52/52**. Zero
falso positivo de combate nos três. Os casos da SPEC-178/179 que o Jev errava
agora acertam: `FALO COM CORVO` (rota 1,00 / alvo 0,98), `target.alias` (alvo 1,00),
`target.enemy` (alvo 0,62).

| Variante (política) | Cobertura | Erros rota cob. | Erros alvo cob. | Escalada insegura | Fallback (motivos) | Jev p50/p95 ms* | Híbrido estim. p50/p95 ms |
|---|---:|---:|---:|---:|---|---:|---:|
| legacy@0,50 (rota só) | 5/52 | 0 | 0 | 0 | sem estágio de alvo 30, loot 14, abst. 3 | 247 / 288,7 | 1.716 / 1.760,6 |
| plain@0,50 (rota só) | 7/52 | 0 | 0 | 0 | sem estágio de alvo 30, loot 13, abst. 2 | 247 / 288,7 | 1.715,5 / 1.760,6 |
| rich@0,50 (rota só) | 6/52 | 0 | 0 | 0 | sem estágio de alvo 30, loot 13, abst. 2, baixa conf. 1 | 247 / 288,7 | 1.716 / 1.760,6 |
| legacy+target@0,50 | 33/52 | 0 | 0 | 0 | loot 14 (inclui o erro `Guardo o arco`→loot), abst. 3, alvo n/repr. 2 | 247 / 288,7 | 262 / 1.740,05 |
| legacy+target@0,70 / 0,90 | 31 / 30 | 0 | 0 | 0 | + baixa confiança | 247 / 288,7 | 269,5 / 1.750–1.755 |
| **plain+target@0,50** | **35/52 (67,3 %)** | **0** | **0 (25 casos)** | **0** | loot 13, abst. 2, alvo n/repr. 2 | 247 / 288,7 | **260,5 / 1.740,05** |
| plain+target@0,70 / 0,90 | 34 / 32 | 0 | 0 | 0 | + baixa confiança (alvo `enemy` 0,62) | 247 / 288,7 | 260,5 / 1.750–1.755 |
| rich+target@0,50 / 0,70 / 0,90 | 34 / 33 / 27 | 0 | 0 | 0 | + baixa confiança (12 em τ 0,90) | 247 / 288,7 | 261–281,5 / 1.740–1.761 |
| *(+guard em qualquer linha)* | idêntico | — | — | — | guarda nunca disparou no DEV | — | — |

\* P1 envia 3–4 perguntas por chamada; é limite superior da latência de uma
estrutura. Rota-só não muda com τ até 0,90 (cobertura igual). Todas as 108 políticas constam em `summary.json` (campo `variants`);
grade τ completa 0,50…0,90 em passos de 0,05. A guarda de combate não mudou
nenhuma decisão no DEV (todo `combat_agent` do Jev veio com `verbs∋attack`), logo
cada variante `+guard` empata com a sua base.

**Seleção (regra pré-registrada):** viáveis = todas (0 insegura, 0 erro). Maior
cobertura = 35 (`plain+target@0,50` e `plain+target+guard@0,50`); desempate
"sem guarda antes de com" ⇒ **`plain+target@0,50`**. Manter: `plain+target`;
descartar: rota-só (cobertura ≤ 7/52, híbrido mais lento que A), `legacy` (1 erro
standalone, menor cobertura), `rich` (menor cobertura; confiança cai em loot/craft).

### P2 — estrutura exata (8 casos DEV `critical`, run `SPEC-217-J1-p2-20261018T122535Z`)

Requisição real congelada (1 pergunta de rota `plain` + alvo): **8/8 cobertos,
0 erro de rota/alvo, 0 escalada insegura**, concordância com a P1 **8/8 rota e 8/8
alvo**. Latência Jev p50 **247 ms**, p95 **286,55 ms** (`FALO COM CORVO` → `npc_actor`
1,00, alvo `npc_corvo_rapido`).

### Congelado para a J2

`FROZEN_J1_POLICY = Policy(label_set="plain", with_target=True, combat_guard=False, tau=0.50)`
em `evals/experiments/jev_router_hybrid.py`; hash da estrutura (perguntas, alvo,
léxico de verbos, features, política) `sha256:950917371fe7c1c46326996d5adaa518e10f1c1e6e8c778103a9cf88a4d44b81`
(teste `test_frozen_structure_digest_matches_code`). Chamadas por caso elegível na
J2: **1 Jev** (rota e alvo na mesma requisição) + 1 CLASSIFY ⇒ `4 + 16×2×3 = 100`
cabe no teto J2 sem reduzir o FROZEN.

### Limitações

- DEV tem 52 elegíveis e nenhuma variante errou nos cobertos: o DEV não discrimina
  bem entre `plain` e `rich`; a confirmação é o FROZEN (nunca visto).
- A latência híbrida é **estimativa** (CLASSIFY = p50 de 1.473 ms da fase router no
  gate real da SPEC-214, não medido aqui); medida de estação de trabalho.
- Cobertura máxima é limitada pelo contrato: 13/52 DEV são `loot` (fallback por
  escopo). No FROZEN o mix declarado é loot 3/16.
- Exemplos do label set `rich` foram escritos sem copiar frases do DEV.
