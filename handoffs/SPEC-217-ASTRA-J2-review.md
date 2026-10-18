# SPEC-217 — Revisão Astra independente do resultado J2

**Veredito: `APPROVED`.** O `GO` da J2 é válido: a R9 pré-registrada (R9.1–R9.7) foi
recomputada de forma independente a partir do raw, dos rótulos FROZEN e do oráculo de
fonte selado, e todos os itens passam com os mesmos números do summary. Nenhuma chamada
live nesta revisão; o porte (R14) **não** foi implementado.

- Revisor: Astra (Opus), sem participação na execução da J2.
- Objeto: run `SPEC-217-J2-20261018T134801Z`, runner `3d1aca4`, resultado `02a8196`
  (branch `spec-217`).
- Script de recomputação (fora do worktree, não importa o runner nem a política):
  `scratchpad/astra217/recompute.py`.

## Checagens

| # | Item | Resultado |
|---|---|---|
| 1 | Hashes | `raw.json` `f1a257a7…3519`, `summary.json` `454e814c…8ef1`, `ledger.json` `5c2c32da…9cc1` conferem no worktree **e** na cópia do scratchpad (`spec217-raw/j2/`). FROZEN `442725e5…9d48` = lock = `hybrid.FROZEN_SHA256`; oráculo `d9c860ec…c38d` = lock = constante do runner. |
| 2 | Runner antes da 1ª chamada | Commit `3d1aca4` às 13:47:40Z (só adiciona `spec217_j2.py` + testes); marker às 13:48:01Z; raw `started_at` 13:48:02Z; 1ª entrada J2 do ledger 13:48:12Z (n=91). Raw grava `product_sha=3d1aca4`, `product_dirty=false`. |
| 3 | Execução única | `J2_STARTED.json` tem 1 run (`owner_rerun_authorization=null`); `j2_runs` do ledger tem 1 entrada; nenhum outro diretório de run J2. |
| 4 | Ledger 190/190 | 190 entradas, `n` contíguo 1..190. J1 60 Jev (p1 52 + p2 8), J1b 30 Jev, J2 50 Jev + 50 CLASSIFY. Os `call_n` do raw J2 cobrem 91..190 sem repetição (100/100). Última entrada não-J2 às 13:06Z. |
| 5 | Summary reproduz do raw | `--phase summarize` sobre uma cópia do raw em diretório novo → summary com SHA-256 **idêntico** (`454e814c…8ef1`). |
| 6 | R9 recomputada | Ver tabela abaixo — idêntica ao summary. |
| 7 | Vazamento FROZEN → J1/J1b | Política/léxico/τ congelados em `908d066`/`84aee5f`, antes do runner; nenhum `.py` de política referencia o FROZEN (só o lock de hash). Léxico: as classes decisivas para os guards (`attack`/`trade`/`take`) têm atestação no DEV (`dispar`, `vendo`, `compro`, `pego`); verbos gerais de `talk/observe` existem em `playtest/` antes do corpus. Evidência **contra** tuning: os verbos de combate do FROZEN (`investo`, `encaro`) **não** estão no léxico — exatamente o que causou o fallback de p04 (risco previsto na revisão J1). O oráculo de fonte foi selado (`5463e36`) depois do selo J1b e antes do runner, só com `loot_source` dos 3 casos `loot`; rótulos coerentes com o contrato do router (`pick`⇒TREASURE, `comprar/vender`⇒SHOP). |
| 8 | Braço A = produção | `RoutingAdapter` chama `dm_router_node` real (gates Python → `get_llm(CLASSIFY)`), sem `RPG_ROUTES`/`LLM_PROVIDER`/mock, `RPG_JEV_ROUTER_MODE=off`. 48/48 chamadas com 1 tentativa, `deepseek-v4-flash` (1º candidato do `ROUTES`), sem fallback/retry/regeneração. |
| 9 | Latência comparável | Pareamento intercalado por caso na mesma janela (13:48–13:49Z), braço inicial sorteado (A primeiro 27×, B primeiro 21×); mediana de A não depende da posição (1.487 vs 1.454 ms), idem B (244 vs 235 ms). B no fallback = Jev + A do mesmo caso/réplica (4 obs.: 1.535/1.720/1.916/2.099 ms). Overhead do adapter de A ≈ 4 ms. |
| 10 | Misroutes do CLASSIFY (p13) | Genuínos: "Vendo o escudo rachado a Ogmund" → A `npc_actor` (conf. 0,85, alvo "Ogmund") nas 3 réplicas; o próprio prompt do router define "Comprar/Vender" ⇒ LOOT/SHOP, e a regressão `routing.loot.shop.sell` espera `loot`. O Jev decidiu `loot` 1,00 + `shop` 1,00, guard `trade` ok. |
| 11 | Guard de combate (p04) | "Investo contra o troll da ponte" (fora de combate, verbos `[]`): Jev `combat_agent` 0,91–0,94 + alvo correto, mas o guard (sem `attack`, sem combate ativo) recusou → CLASSIFY acertou `combat_agent`/troll. Comportamento correto e seguro: o guard só converte em latência (não em erro). p11 réplica 3: Jev `storyteller` 0,49 < τ → fallback, CLASSIFY acertou. |
| 12 | Testes | `tests/test_spec217_j2.py`, `test_spec217_j1.py`, `test_spec238_loot.py`, `test_jev_rollout.py`: 107 passed, offline. |

### R9 recomputada (independente)

| Regra | A | B | Passa |
|---|---:|---:|:---:|
| R9.1 rota (48) | 45 | 48; 0 perdas pareadas, 3 ganhos (p13×3) | ✓ |
| R9.2 alvo (24) | 24 | 24; 0 fora dos candidatos | ✓ |
| R9.3 escalada insegura | 0 | 0 | ✓ |
| R9.4 p50 / p95 | 1.480 / 1.806,55 ms | 238 / 1.655,25 ms (ganho 1.242 ms; razão 0,916) | ✓ |
| R9.5 gates | 15/15 iguais, 0 chamadas, 15/15 = oráculo | | ✓ |
| R9.6 provider | status `complete`, 0 erros | | ✓ |
| R9.7 fonte loot | (A 6/9 informativo) | 9/9 = oráculo | ✓ |

Cobertura do Jev 44/48 (combat_guard 3, low_confidence 1). Jev isolado p50 236 / p95 280,9 / máx 352 ms.

## Valores congelados a portar (R14) — sem alteração

```python
# services/jev_rollout.py
PRIMARY_CALIBRATION = ("SPEC-217-J2-20261018T134801Z", 0.50)
```

Estrutura/política a portar **byte-equivalente** ao congelado (digests como evidência do porte):

| Item | Valor |
|---|---|
| Variante | `plain+target+guard@0.50+lootsrc+lguard@0.50` |
| Digest J1 / J1b | `sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5` / `sha256:75635c8994f8a421989653e1383052017feccde024ceaab731da69e739ef2247` |
| Perguntas (1 requisição) | `route` (rótulos `plain`), `target` (opções = IDs de candidatos em cena + `none`), `loot_source` (`treasure/shop/craft/none`) |
| Features | `scene`, `last_speaker`, `verbs` (léxico `_VERB_PATTERNS` atual, **inalterado**), ação em minúsculas; **features de local OFF** |
| τ rota / alvo / fonte | 0,50 / 0,50 / 0,50 (`<` τ ⇒ CLASSIFY) |
| Guard de combate | `combat_agent` só com verbo `attack` **ou** combate ativo; senão CLASSIFY |
| Guard de loot | exige `take/trade/craft`; SHOP⇔`trade`; CRAFT⇔`craft`; TREASURE sem `trade/craft`; senão CLASSIFY |
| Fallback | `none`/abstenção, alvo irrepresentável/baixa confiança, erro/timeout ⇒ CLASSIFY do mesmo turno (gates Python antes do Jev, inalterados) |
| Default | `RPG_JEV_ROUTER_MODE=off`; `primary` continua exigindo `RPG_JEV_ROUTER_PRIMARY_APPROVED=1` + kill switch `decision_backend:jev` |

Requisitos do porte (para a revisão do commit R14): (a) o `_threshold()` atual tem um τ só —
como os três τ são 0,50, usar o mesmo valor e **assertar** a igualdade em teste; (b) o
contrato atual de `primary` aceita só `storyteller/none` — o porte precisa mapear o ID de
alvo do Jev para a chave/nome que `dm_router_node` grava (`active_npc_name`/`combat_target`)
e a fonte para `loot_source` maiúsculo, com teste de paridade contra `map_target_to_id`;
(c) teste que recalcula os digests J1/J1b a partir do código portado (ou importa as funções
congeladas) e falha se divergirem; (d) nenhuma mudança de schema de save.

## Riscos para produção (não bloqueiam o GO; endereçar no porte/shadow)

1. **Cobertura do léxico de verbos.** Combate legítimo sem verbo do léxico (p04 "investo";
   "acerto", "atiro", "encaro" também ausentes) vira fallback → custo de latência (Jev +
   CLASSIFY), nunca erro. Não alterar o léxico sem nova evidência DEV + revisão (mudá-lo
   invalida o digest/calibração). Medir a taxa de `combat_guard` no shadow.
2. **Variância/cauda de latência.** O p95 de B já cai em fallback (4/48 ≈ 8 %). Se a taxa
   real de fallback subir, o p95 de B tende a Jev + CLASSIFY > p95 de A. O shadow deve
   reportar taxa de fallback por motivo e a razão p95 B/A. Medição na estação de trabalho,
   não `gru1`; amostra pequena (16 casos × 3) e ganhos de acurácia vêm de um único caso.
3. **Deadline do Jev.** A J2 usou timeout total de 10 s; o rollout atual usa 8 s em
   `primary`. Isso anula o ganho e piora a cauda se o Jev degradar. O porte deve aplicar um
   deadline curto (proposta: ≤ 1 s, máx. observado 352 ms) e cair para CLASSIFY dentro do
   orçamento; teste com backend falso lento verificando latência ≤ deadline + CLASSIFY.
4. **Disponibilidade TypeSafe.** Erro/timeout/kill switch ⇒ CLASSIFY (já é o caminho do
   rollout); manter `max_retries=0` e a telemetria por `outcome`.
5. **Custo desconhecido.** O Jev não informa custo (`unavailable`); B soma 1 chamada Jev a
   todo turno elegível e ainda paga CLASSIFY nos fallbacks. Não alegar economia.
6. **A no J2 é o caminho feliz** (fallback de cascata parava o run): a cauda real de A em
   produção é pior, o que não favorece indevidamente B.

## Pendências fora desta revisão

- R14: porte atrás de `off` + `PRIMARY_CALIBRATION` em commit separado, com revisão Astra.
- R15: shadow em staging ≥ 50 turnos com teto próprio autorizado pelo dono.
- `primary` em produção: aprovação separada do dono após o shadow.
- Critério da spec "`uv run pytest` verde" ainda precisa da suíte completa no fechamento.
