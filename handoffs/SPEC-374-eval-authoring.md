# SPEC-374 — parecer de autoria de eval (Etapa E)

- **Autor:** agente de eval (Opus), diferente do executor de produto (R1). Não toquei em
  código de produto (`services/creature_gen*.py` além do avaliador `creature_gen_eval.py`,
  que a spec define como avaliador em R1/§3 Etapa E).
- **Branch:** `spec-374` · worktree `C:/Users/guilh/AppData/Local/Temp/claude/rpg-spec-374`
- **Commit da Etapa E:** `d3019102` "test(eval): fix idioma_pt ties, job latency threshold,
  tuning set (SPEC-374)". Antes de qualquer commit de produto (a branch só tinha a aprovação
  da spec, `f6718f97`).
- **Status:** `EVAL_AUTHORING_REQUIRED`, publicação depende do dono (ver §5).

## 1. O que mudou (caminhos agora protegidos)

| Requisito | Onde | O quê |
|---|---|---|
| R4/D1 | `services/creature_gen_eval.py` `_EN` | sem "a" e "as"; `_PT` e a regra de empate iguais |
| R5/D2 | `LIMIARES` | `latencia_nova_p95_ms <= 15000` → `latencia_job_p95_ms <= 30000`; mesma medição (`latencia_ms` das `forcar: nova`, fallback incluso); `latencia_nova_p50_ms` informativa |
| R6/D6 | `PROTOCOLO`, `checar_protocolo()` | exatamente 2 rodadas; `depois`+`real`+`mock=False`; mesmo commit, conhecido e sem `+sujo`; `pedidos_sha256` = set da 361; `lint_primeira` agregado >= 0,70 (16/22) e cada rodada >= 7/11; os demais `LIMIARES` valem em cada rodada (o 0,70 de uma rodada só não se aplica por rodada) |
| P2-8 b | `avaliar()` + `.md` | `n_gerados` e `lint_primeira_n` nas métricas; nota de denominador em todo `.md` |
| D3 | docstring do avaliador | fronteira confirmada sem mudança: conta o que roda antes do 1º lint e não escolhe conteúdo; nada depois do 1º lint conta |
| R6 | `scripts/bestiario/eval_geracao.py` | `--rodada N`; JSON leva `commit` (sha12, `+sujo` se houver rastreado alterado) e `vizinho_max` por registro; `--repontuar JSON… --md-out` e `--protocolo JSON JSON --md-out` (sai 1 se não passar); protocolo no docstring |
| R7 | `tests/fixtures/spec374_pedidos_ajuste.yaml` | 14 pedidos novos (ver §3) |
| R8 | `evals/protected-paths.txt` | + `services/creature_gen_eval.py`, `tests/test_spec361_eval.py`, `tests/fixtures/spec361_pedidos.yaml`, `tests/fixtures/spec374_pedidos_ajuste.yaml`, `scripts/bestiario/eval_geracao.py` (o script entrou também, por coerência com o R1 e com `scripts/fauna/eval.py`) |

Testes novos em `tests/test_spec361_eval.py`: `test_idioma_pt_sem_empate_falso`,
`test_limiar_latencia_job`, `test_denominadores_explicitos`, `test_protocolo_duas_rodadas`
(known-good 8+8 e 9+7; known-bad 8+7, 11+6, 1 rodada, 3 rodadas, mock, outro set, commits
diferentes, sem commit, `+sujo`, outro limiar falhando), `test_pedidos_ajuste_congelados`,
`test_pedidos_ajuste_disjuntos`, `test_avaliador_protegido`.
Rodados (sem `-n`): `tests/test_spec361_*.py` 106 passed; `test_eval_governance`,
`test_ci_eval_gates`, `test_spec360_eval` + o eval da 361: 42 passed. Ruff check/format ok.
Smoke offline: `eval_geracao.py --modo depois --pedidos <ajuste> --rodada 1` no MockLLM
grava `commit`/`rodada`/`vizinho_max`; 1 variante, 2 existentes, 11 novas; `--protocolo`
sobre ela devolve `passou: False` (mock, set errado, `+sujo`), como deve.

## 2. Re-pontuação sem LLM (R4) — `docs/spec374/eval-repontuado.md`

JSON originais da 361 não reescritos. `vizinho_max` fica herdado (os JSON antigos não gravaram
os vizinhos); as demais métricas são recalculadas dos registros.

| métrica | antes | 361-a | 361-b | 361-c |
|---|---|---|---|---|
| idioma_pt (antes → depois da correção) | 1,0 → 1,0 | 0,9932 → **1,0** | 1,0 → 1,0 | 0,9932 → **1,0** |
| p95 de latência (limiar antigo 15 000 → job 30 000) | 7 680 | 11 936 ok | 12 564 ok | 19 068 (falhava → **ok**) |
| lint_primeira (inalterado) | — | 7/11 | 5/11 | 6/11 |
| lint_final / fallback | — | 1,0 / 0 | 0,818 / 0,18 ✗ | 1,0 / 0 |
| n_gerados (denominador de fisico/campos/vizinho) | 12 | 11 | 9 | 11 |

Nenhuma outra métrica mudou (proibidos, dígitos, físico, campos, prompt_chars idênticos).
Leitura: com o avaliador corrigido, o único bloqueio real das rodadas da 361 é o
`lint_primeira` (e o fallback da b). Pelo D6, nenhum par passaria: melhor par a+c = 13/22
(precisa de 16/22), e b fica abaixo do piso 7/11.

## 3. Set de ajuste (R7)

`tests/fixtures/spec374_pedidos_ajuste.yaml`, sha256 (LF)
`13ec924e27825bd64699fd474ac5661fb959870b41373a53e0162d44c80aa3df`.
11 `forcar: nova` em 11 regiões (inclui `ophidia` e `floresta_sussurros`, ausentes no set
da 361), famílias corpo_reescrito ×2, besta_entropia ×3, humanoide_preco ×2,
demonio_encarnado ×2 (+ 1 inglês e 1 injeção sem família); 3 sem motivo; 1 em inglês
(`pradaria_ingles`); 1 injeção com dígitos (`montanhas_injecao`). 3 `auto`: variante
`floresta_jaula_auto` → `enemy_aranha_lobo` + `fugido_da_jaula` (conferido com
`decidir_caminho` no MockLLM em `d3019102`), existentes `Vespa Coveira` e
`Casco de Costelas`. Jaccard máximo contra os 14 da 361: 0,14 (limite do teste 0,6).
A família declarada por pedido fica no teste (`FAMILIA_AJUSTE`), não no YAML, para o
formato ficar igual ao da 361.

Observação para o executor: a base esperada da variante depende do catálogo e do
`score_base` atuais. Se o produto mudar a escolha de base, o `caminho_ok` do set de ajuste
cai; é sinal, não motivo para editar o set (pedir nova autoria de eval).

## 4. Riscos e limites que o revisor Sol deve olhar

1. **`lint_primeira` vem do produto** (`ResultadoGeracao.lint_primeira`): o avaliador não
   recomputa o 1º lint. A integridade depende de o produto gravar o resultado do 1º `lint`
   antes de qualquer reparo (D3). A revisão Sol confere isso no diff do produto.
2. As rodadas medidas precisam rodar **seguidas, sem commit entre elas**, com a árvore
   rastreada limpa (o JSON de saída novo é não rastreado; não commitar `eval-medido-1.json`
   antes da rodada 2, senão o commit muda e o protocolo reprova).
3. `eval_geracao.py --out docs/spec374/...` escreve também `docs/spec374/eval-antes-x-depois.md`
   (comportamento antigo); a tabela oficial é a de `--protocolo ... --md-out`.
4. Long-run não se aplica: 2 rodadas de 14 pedidos (~25 chamadas FAST cada).

## 5. Publicação (R8) — EVAL_AUTHORING_REQUIRED

Caminho protegido mudou (inclusive o próprio `evals/protected-paths.txt`), então o CI
`eval-gates` pede o environment `eval-governance`. Não fiz push nem aprovei nada.
O avaliador vive em `services/`, que o `eval_publish.py` classifica como produto; o commit
da Etapa E é só eval, mas a branch terá produto depois. Comando para o coordenador, depois
do push do commit `d3019102` (ou da branch, se o lote for por onda):

```bash
bash scripts/dev/py.sh scripts/dev/eval_publish.py --base origin/main --allow-mixed
```

(`--allow-mixed` só porque `services/creature_gen_eval.py` casa com o prefixo `services/`.)
O script imprime o `gh api ... pending_deployments ... state=approved` que o **dono** roda.
O R1 já trava o executor enquanto a aprovação não sai.

## 6. Decisões do dono ainda abertas (não bloqueiam)

- D2 (30 s, não 60 s) e D6 (2 rodadas, agregado 16/22, piso 7/11) aplicados como default.
  Se o dono quiser a leitura literal (1 rodada >= 8/11), é nova autoria de eval antes de
  medir: mudar `PROTOCOLO` e o teste `test_protocolo_duas_rodadas`.
