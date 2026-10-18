# SPEC-217 — handoff de autoria de eval (corpora DEV e FROZEN do router Jev)

Tarefa SEPARADA e anterior à execução da SPEC-217 (J1 e J2). O autor não executa
chamadas live, não altera produto e não participa da J1/J2. `evals/datasets/regression/`
é régua protegida (SPEC-165): **não editar**; os corpora desta spec ficam em
`evals/experiments/data/`, como o corpus da SPEC-179.

## 1. Entregáveis

| Arquivo | Conteúdo |
|---|---|
| `evals/experiments/data/spec217_dev.jsonl` | corpus DEV (iteração da J1) |
| `evals/experiments/data/spec217_dev.sha256` | SHA-256 do JSONL (LF, UTF-8) |
| `evals/experiments/data/spec217_frozen.jsonl` | corpus FROZEN (J2, confirmatório, usado uma vez) |
| `evals/experiments/data/spec217_frozen.sha256` | SHA-256 do JSONL |
| `evals/experiments/spec217_corpus_check.py` | verificador: schema, hashes, não-sobreposição, contagens |
| `docs/spec217/corpus.md` | contagens por rota/tipo, hashes, commit de congelamento, saída do verificador |

Ambos os JSONL com LF fixado em `.gitattributes` (lição da SPEC-176). Congelar num
commit próprio **antes** de qualquer trabalho da J1; registrar o SHA do commit.

## 2. Formato de caso (ambos os corpora)

Mesmo shape do `routing_actions.jsonl`/`spec179_corpus.jsonl`, com campos extras:

```json
{"id": "spec217.dev.npc.caps.01", "split": "dev", "kind": "route|target",
 "input": {"operation": "route", "action": "...", "state": {"world": {...}, "combat": {...},
           "npcs": {...}, "enemies": [...], "active_npc_name": null}},
 "expected": {"route": "npc_actor", "target": "npc_corvo_rapido|null"},
 "python_gate": false, "critical": "combat_escalation|null",
 "origin": "regression:routing.npc.corvo.case|spec179:target.alias|synthetic",
 "rationale": "uma linha: por que este oráculo"}
```

- `expected.route` ∈ `storyteller | combat_agent | npc_actor | loot` (`none` normaliza para `storyteller`).
- `expected.target` só para `kind=target`: ID canônico presente e visível na cena da fixture, ou `null`.
- `python_gate=true` quando o router atual resolve por gate determinístico (combate ativo, recovery, viagem); confirmar com o `_eligible` de `evals/experiments/jev_router_ab.py`, sem rede.
- `critical="combat_escalation"` em todo caso cujo oráculo não é `combat_agent` mas contém sinal ambíguo (caixa alta, interjeição, arma mencionada sem ataque, NPC hostil em cena).
- Estado só com dados públicos (sem segredo, PII ou lore `hidden`); IDs de NPC existentes no grafo (`data/graph/entities.json`).

## 3. Corpus DEV (pode reaproveitar o que já foi visto)

- Todos os casos de `evals/datasets/regression/routing_actions.jsonl` (25, copiados com `origin` apontando o ID original), incluindo os de gate Python.
- Os 14 casos de `evals/experiments/data/spec179_corpus.jsonl` (target/loot; os de loot entram como `kind=route` com rota `loot`).
- **≥ 16 sintéticos novos** cobrindo as falhas conhecidas: variações de caixa/pontuação de fala com NPC (`FALO COM X`, `ei, X!`), fala com NPC hostil em cena sem ataque, alias de NPC, inimigo como alvo, alvo ausente da cena, mais de um NPC em cena com último interlocutor diferente, menção de arma sem atacar, comprar/vender falado a um mercador (rota `loot` vs `npc_actor`, oráculo justificado), observação pura.
- Sem teto de tamanho; a J1 escolhe subconjuntos dentro do orçamento de 60 chamadas.

## 4. Corpus FROZEN (confirmatório, nunca visto)

- **Somente casos novos**, escritos sem consultar resultados de Jev/CLASSIFY de nenhuma spec.
- **16 casos elegíveis** (chamam provider) + **≥ 4 casos de gate Python** (0 chamadas). Orçamento J2: `4 + 16 × 2 × 3 = 100`. Se a estrutura congelada na J1 tiver dois estágios, o executor reduz casos por seleção determinística (seed declarada em `docs/spec217/corpus.md`) antes de ler o conteúdo; por isso marque a ordem de prioridade (`priority` 1..16) no FROZEN.
- Distribuição alvo dos 16: 5 `npc_actor` (≥ 3 com alvo), 4 `storyteller`, 3 `loot`, 2 `combat_agent`, 2 ambíguos com `critical="combat_escalation"`.
- Pelo menos 4 casos com mais de um NPC em cena e 2 com alvo por alias.

## 5. Não-sobreposição (verificada pelo script)

O verificador falha se houver entre DEV e FROZEN:
1. `id` igual;
2. ação normalizada igual (casefold, NFKD sem acento, sem pontuação, espaços colapsados);
3. ação normalizada com distância de edição ≤ 3 ou que difere só por nome de NPC/local (template igual);
4. fixture idêntica (hash do `input.state` canônico) combinada com a mesma rota esperada.

Também falha se algum JSONL não bater com seu `.sha256`, se houver `expected.target` fora
dos candidatos visíveis da fixture, ou se as contagens do §4 não forem atendidas.
Comando: `uv run python evals/experiments/spec217_corpus_check.py` (exit 0 = ok).

## 6. Regras para o executor da SPEC-217

- J1 lê apenas DEV. Do FROZEN, só hash, contagem e prioridades até o run J2.
- Nenhum dos dois arquivos muda depois do commit de congelamento; o runner valida o hash antes da primeira chamada.
- Revisão Astra confere o commit de congelamento e a saída do verificador antes da J1.
