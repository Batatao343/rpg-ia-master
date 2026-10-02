# 03 — Métricas backend/IA

A tabela abaixo é o primeiro registry proposto. “Blocking inicial” indica se a métrica deve impedir merge logo na primeira versão do harness.

| Métrica | Tipo | Oráculo | Blocking inicial |
|---|---|---|---|
| route_accuracy | determinístico | label esperado | sim |
| target_accuracy | determinístico | entity id esperado | sim |
| state_transition_pass_rate | determinístico | before/after esperado | sim |
| invariant_error_count | determinístico | `playtest.invariants` | sim |
| memory_write_precision | determinístico | fatos aceitos/rejeitados | sim |
| memory_recall_at_k | ranking | fact/evidence IDs | após baseline |
| memory_mrr | ranking | fact/evidence IDs | após baseline |
| context_recall_at_k | ranking | evidence IDs | após baseline |
| context_forbidden_leak_rate | determinístico | IDs proibidos | sim, deve ser 0 |
| secret_leak_count | determinístico | visibility/reveal state | sim, deve ser 0 |
| lore_claim_contradictions | determinístico onde coberto | estado + `narrative_evidence` | sim |
| npc_identity_errors | determinístico | canonical entity ID | sim |
| inventory_claim_errors | determinístico | inventory ledger | sim |
| false_player_death_claims | determinístico | lifecycle/event log | sim |
| player_action_ack_rate | híbrido | structured outcome primeiro | após baseline |
| semantic_repetition_rate | híbrido | fingerprints + judge opcional | warning inicialmente |
| npc_persona_score | judge calibrado | rubric | não |
| prose_quality | judge calibrado | rubric | não |
| turn_p50/p95 | observacional | relógio | regressão relativa |
| cost_per_100_turns | observacional | telemetry | regressão relativa |

## A. Routing / interpretação da ação

### Caso

```json
{
  "input": "Tento convencer o guarda a me deixar passar.",
  "state_fixture": "npc_gate_guard.json",
  "expected": {
    "route": "NPC",
    "target_id": "npc_guarda_portao",
    "combat_origin_hint": null
  }
}
```

### Métricas

- route accuracy;
- target accuracy;
- confusion matrix;
- accuracy por categoria: social, combate, viagem, descanso, loot, craft, ambígua.

### Casos metamórficos

A mesma intenção deve permanecer igual com:

- variação de maiúsculas;
- espaços extras;
- pontuação;
- “por favor”/polidez;
- acentos equivalentes;
- ruído textual irrelevante controlado.

Não gerar essas variações em runtime com LLM. Versionar as variantes ou gerar deterministicamente.

## B. State transition correctness

A unidade é `state_before + action + state_after_expected_projection`.

Comparar somente campos que fazem parte do contrato do caso.

Exemplo compra:

```text
before.gold = 100
before.potion_qty = 0
action = compra poção de 25
after.gold = 75
after.potion_qty = 1
```

Falha se a narração disser compra mas o ledger não mudar; falha também se o ledger mudar duas vezes.

## C. Memória — separar write, retrieval e use

### C1. Memory write precision

Pergunta: o sistema gravou apenas fatos válidos?

Casos devem cobrir:

- afirmação positiva;
- negação;
- posse do player vs posse de NPC;
- identidade/alias;
- morte do player vs relato de morte de outro;
- fato especulativo;
- segredo não revelado;
- fato substituído por estado canônico posterior.

O esperado é uma lista de `fact_id` aceitos/rejeitados.

### C2. Retrieval quality

Inserir fatos com IDs controlados e consultar após N turnos lógicos.

Medir:

```text
Recall@1
Recall@3
Recall@5
MRR
forbidden_recall (deve ser 0)
```

A resposta textual do LLM não participa desse score.

### C3. Memory use

Depois de retrieval estar correto, verificar se o contexto entregue contém o `fact_id` esperado. Só em seguida avaliar se a geração o contradisse.

Isso diagnostica:

```text
store -> retrieve -> context -> generate
```

## D. RAG/lore

Dataset deve ligar `query` a:

- IDs obrigatórios;
- IDs aceitáveis;
- IDs proibidos;
- visibility máxima;
- entidade/local relevantes.

Métricas: Recall@K, Precision@K, MRR e leak rate.

Não usar “resposta contém palavra X” como métrica principal quando o índice já possui IDs canônicos.

## E. Context builder

Testar `services/context_builder.py` em isolamento.

Para cada caso:

- fatos dinâmicos obrigatórios;
- lore obrigatório;
- memória obrigatória;
- fatos obsoletos proibidos;
- segredos proibidos;
- orçamento de tokens.

Métricas:

```text
required_evidence_recall
forbidden_evidence_leak
context_token_budget_violation
source_mix_distribution
```

## F. Consistência narrativa determinística

O build atual já possui `services/narrative_evidence.py` e regras em `memory_provenance.py`.

Transformar os checks em corpus versionado.

Exemplos que devem ser 100% determinísticos:

- player morto/vivo;
- localização atual;
- item possuído/não possuído;
- NPC canônico/alias;
- segredo não revelado;
- recompensa concedida/negada;
- entidade fora da cena quando isso viola o contrato;
- outcome consolidado vs texto apresentado.

Métrica: `contradictions / eligible_claims` + contagem hard.

## G. Player agency

Evitar judge enquanto houver estrutura.

Primeiro sinal:

1. ação foi roteada;
2. outcome estruturado existe;
3. outcome contém efeito ou recusa explícita;
4. apresentação deriva do outcome canônico.

Definir `ignored_action` quando nenhum desses caminhos ocorrer e não houver erro/rejeição explícita.

Somente casos subjetivos restantes podem ir para judge.

## H. Repetição

Manter fingerprint determinístico atual para repetição literal/cosmética.

Adicionar:

- n-gram overlap em janelas;
- repeated opening templates;
- repeated NPC response fingerprints.

“Repetição semântica” via judge deve ser warning até calibrado.

## I. Long-run — diagnóstico manual, não gate padrão

Não reinventar. Usar o `playtest/` existente **somente quando solicitado**.

Long-run serve para perguntas de horizonte longo — degradação de estado, loops, repetição acumulada, custo/latência ao longo de campanhas e interações emergentes. Ele não entra no cálculo da baseline-v1 e não é obrigatório para aceitar uma melhoria local.

Quando executado manualmente, o relatório deve referenciar o mesmo `product_sha` e, quando fizer sentido, as versões dos component evals usados para comparação.
