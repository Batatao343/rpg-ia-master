# SPEC-217 — revisão Astra independente do congelamento J1 (R6)

Revisor: Astra (≡ Opus, contexto separado; não escreveu a J1). Objeto: branch
`spec-217`, commits `c5a721c` (código) e `1264c6f` (resultados/freeze).
Nenhuma chamada live nesta revisão. O FROZEN (`spec217_frozen.jsonl`) **não foi
aberto**: só `sha256sum` do arquivo (= selo `442725e5…9d48`). O verificador de
autoria (`spec217_corpus_check.py`) lê o FROZEN e por isso **não** foi executado.

## Veredito: **APPROVED** — com uma emenda do revisor (guarda de combate ligada)

Estrutura final congelada para a J2:

```python
FROZEN_J1_POLICY = Policy(label_set="plain", with_target=True, combat_guard=True, tau=0.50)
# variant_id = "plain+target+guard@0.50"
FROZEN_J1_STRUCTURE_DIGEST = (
    "sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5"
)
```

O hash anterior (`950917…4b81`, guarda desligada) fica **superado**. A requisição
enviada ao Jev é a mesma (a guarda é pós-decisão, em Python), logo a P2 continua
válida para a estrutura emendada: 1 Jev por caso elegível (rota `plain` + alvo).

## Verificações

| # | Item | Resultado |
|---|---|---|
| 1 | Payload de produção inalterado | OK. `wire_body` já usava `model_dump(exclude_none=True)` antes da SPEC-217 (não está no diff); os campos novos `scene/last_speaker/verbs` são `None` por default. Teste existente (`test_production_rollout_payload_is_unchanged`) + novo com `active_npc_name`/NPCs em cena (`test_production_rollout_payload_unchanged_with_active_npc`). `RPG_JEV_ROUTER_MODE` default `off`; `PRIMARY_CALIBRATION = None`; `jev_rollout.py` sem diff. O ajuste em `test_jev_rollout.py` (`exclude_none`) é equivalente ao fio. |
| 2 | Hash do freeze | OK, mas **reforçado**: o digest cobria perguntas/léxico/política e só uma *descrição textual* das features. Agora inclui o código-fonte (LF) de `normalize_action`, `_fold`, `extract_verbs`, `scene_view`, `decision_state`, `target_question`, `frozen_request`, `hybrid_decision` e `_target_options` (SPEC-179). Teste novo `test_frozen_digest_pins_decision_code`. |
| 3 | Vazamento | OK. `c5a721c`/`1264c6f` não tocam `evals/experiments/data/` (`git diff --stat 5f4aef2 1264c6f`); nenhum código referencia `spec217_frozen.jsonl` (só o `.sha256`). Raws gravam só `frozen_lock_hash_only`. Pré-registro: commit `c5a721c` 12:24:41Z; 1ª entrada do ledger 12:24:50Z, raw P1 `product_sha=c5a721c`, `product_dirty=false`. Seleção, τ e desempate só com DEV. |
| 3b | Artifacts | Hashes de raw/summary P1/P2 e ledger conferem com `docs/spec217/README.md`. Ledger: 60 J1 / 60 total. Recomputei offline do raw: `plain+target@0.50` e `+guard` = cobertura 35, 0 erro rota/alvo, 0 inseguras, p50 estim. 260,5 ms; summary reproduz a escolha. |
| 4 | Prontidão da J2 | **Não implementada** (declarado no handoff). Requisitos abaixo. Conta: 60 + 4 + 16×2×3 = **160 exatos** — zero folga. |
| 5 | Guarda de combate | **Exigida** (emenda). Ver abaixo. |
| 6 | `loot` e gates Python | OK. `loot ⇒ CLASSIFY` sempre (`accept_loot=False`, teste novo `test_frozen_policy_sends_loot_to_classify`); `eligible_cases` exige concordância da sonda do router real com `python_gate` antes de qualquer chamada. Consistente com §2 "Fora de escopo" e R9.5. |

## Ponto 5 — por que ligar a guarda

- **O DEV não carrega informação sobre a guarda:** ela nunca disparou (os 9
  `combat_agent` do Jev no DEV vieram todos com `verbs∋attack`, conf. 0,85–0,99).
  Com/sem empatam em todas as métricas; o desempate pré-registrado era uma
  preferência de simplicidade, não um resultado. Trocar não é ajuste a dados —
  não há dado a que ajustar —, e nada do FROZEN foi visto.
- **Perda assimétrica da spec:** R9.3 dá `NO_GO` com **uma** decisão final de
  combate errada. O FROZEN tem 2 casos `ambiguous` com `critical=combat_escalation`
  × 3 réplicas = 6 oportunidades, exatamente a classe do único erro histórico do
  Jev (D1, `FALO COM CORVO`→`combat_agent`). τ protege só quando a confiança é
  baixa; a guarda é uma segunda barreira independente e determinística.
- **Custo da guarda é só cobertura/latência, nunca acurácia pareada:** caso
  guardado cai no CLASSIFY do *mesmo* caso/réplica (R7) ⇒ B = A naquela
  observação; não cria perda pareada (R9.1) nem escalada de B que A não tenha.
  Se o léxico de ataque não reconhecer um combate legítimo do FROZEN
  (ex.: "acerto", "atiro" não estão no léxico), o custo é latência nesse caso. Com
  loot 3/16 + 2 combate guardados no pior caso, a cobertura máxima fica ~11/16
  (> 50 %), mantendo o p50 de B na faixa do Jev — R9.4 continua alcançável.
- O léxico **não** foi alterado (mudá-lo agora seria tuning pós-dados).

## Requisitos para o executor da J2 (bloqueantes antes da 1ª chamada)

1. **Runner FROZEN** (`--corpus frozen`): valida o hash contra o selo e o `.sha256`;
   recusa sem `FROZEN_J1_STRUCTURE_DIGEST == structure_digest(FROZEN_J1_POLICY)`;
   recusa 2ª execução (marcador durável) sem flag explícita do dono; a sonda de
   gate (`eligible_cases`) roda **antes** de qualquer chamada e o conteúdo FROZEN
   só é lido por esse processo.
2. **Ledger compartilhado** (`spec217-j1/ledger.json`, total 60): J2 cap 100,
   spec cap 160; incrementa antes de cada tentativa de rede **de cada braço**.
   Braço A reutiliza `jev_router_ab._capture_classify` (consome por
   `_provider_slot`, captura tentativas/fallback) ligado a esse ledger.
3. **Parada (R10):** qualquer tentativa CLASSIFY com `outcome != success`,
   `fell_back`, `attempt_index > 0` ou regeneração de structured output (o
   `RoutedLLM` regenera no mesmo provider — isso é chamada extra e "resposta
   inválida") ⇒ status `blocked-by-provider`, sem score. Idem `JevError`. Com zero
   folga, qualquer chamada extra também esgota o teto: o runner deve checar
   `remaining() ≥ 4 + 2×N×3` antes de começar.
4. **Sanidade:** 2 chamadas por braço (4) num caso fora dos dois corpora; erro ⇒ parar.
5. **Pareamento:** 3 réplicas; em cada réplica, ordem dos casos elegíveis
   embaralhada por seed declarada no raw; dentro do caso, ordem dos braços também
   declarada (alternar por seed para não favorecer cache/aquecimento). Gates
   Python: 0 chamadas, mesma rota em A e B (R9.5).
6. **Braço A medido ao vivo** (a J1 usou a estimativa de 1.473 ms): latência A =
   wall time do CLASSIFY; B = Jev se coberto, Jev + CLASSIFY (mesmo caso/réplica)
   no fallback.
7. **R9 como funções puras testadas**, sobre o raw: não-inferioridade −2,5 pp e
   ≤ 1 perda pareada; alvo: comparar ID de B com o alvo de A mapeado nome→ID
   pelo mesmo `scene_view` (A devolve `active_npc_name`); nenhum alvo fora dos
   candidatos; 0 escalada insegura; Δp50 ≥ 500 ms e p95(B) ≤ 1,10×p95(A);
   gates; zero erro de provider.
8. Raw antes do score; summary reproduzível; hashes no README; diretório
   `evals/runs/jev-router-hybrid/<ts>/` (R11) — ou documentar o desvio como na J1.

## Observações não bloqueantes

- `hybrid_decision` aceita `npc_actor`/`combat_agent` com alvo `none` quando há
  candidatos (vira alvo `None`); no FROZEN isso conta como erro de alvo se o
  oráculo tem alvo. Não mudei (decisão pós-dados sem evidência DEV).
- Raws da J1 vivem dentro do worktree (gitignored): copiar para fora antes de
  remover o worktree (os raws 178/179 se perderam assim).
- Porte (R14), só se GO: mapear ID→chave de `npcs` para `active_npc_name`.

## Verificação desta revisão

Testes focados Jev/SPEC-217: 102 passed. Suíte completa e Ruff: ver commit.
