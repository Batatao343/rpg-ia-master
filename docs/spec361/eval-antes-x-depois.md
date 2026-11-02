# SPEC-361: eval de geração de criatura (antes × depois)

Rodada c = geração fora do turno (decisão do dono, 02/11): prazo do job, `RPG_CREATURE_GEN_DEADLINE_S=30`. Rodadas a e b = desenho anterior, prazo de turno de 12 s.


---

## Rodada c (geração fora do turno, atual)

Gerado por `scripts/bestiario/eval_geracao.py`. Pedidos congelados em `tests/fixtures/spec361_pedidos.yaml`; métricas e limiares em `services/creature_gen_eval.py` (§3.9).

- antes: `docs/spec361/eval-antes-2026-11-02.json` · real=True
- depois: `docs/spec361/eval-depois-2026-11-02c.json` · real=True

| métrica | antes | depois | limiar | ok (depois) |
|---|---|---|---|---|
| lint_primeira | — | 0.5455 | >= 0.7 | **não** |
| lint_final | — | 1.0 | >= 0.9 | sim |
| fallback | — | 0.0 | <= 0.1 | sim |
| caminho_ok | — | 1.0 | >= 1.0 | sim |
| proibidos | 0 | 0 | <= 0 | sim |
| digitos | 0 | 0 | <= 0 | sim |
| idioma_pt | 1.0 | 0.9932 | >= 1.0 | **não** |
| fisico | 0.9167 | 1.0 | >= 0.95 | sim |
| campos_349 | 0.0 | 1.0 | >= 1.0 | sim |
| vizinho_max | 0.0833 | 0.1443 | < 0.45 | sim |
| latencia_nova_p95_ms | 7680 | 19068 | <= 15000 | **não** |
| latencia_variante_p95_ms | 0.0 | 20.0 | <= 50 | sim |
| prompt_chars | 0 | 13923 | <= 14000 | sim |
| variante_vs_nova | — | {'variante': 1, 'nova': 0} | — | — |
| latencia_nova_p50_ms | 5658 | 8568 | — | — |

## Pedidos (depois)

| id | caminho | tentativas | códigos | nome |
|---|---|---|---|---|
| zhur_colmeia_auto | variante | 0 | — | Saltador de Palafita da Mente Única |
| zhur_colmeia_nova | nova | 1 | — | Enxerto de Mente Única |
| zhur_odres | nova | 1 | — | Chupador de Odres Podres |
| arcadia_fundicao | nova | 2 | U2,U3 | Escória de Marcha Lenta |
| pantano_cria | nova | 2 | R20 | Coro de Cabeças Baixas |
| skallgard_cobrado | nova | 2 | U3 | Cobrado de Espinha Oca |
| xylos_fera | nova | 1 | — | Bicho de Peso Trocado |
| costa_ingles | nova | 2 | R20,U3 | Engolido da Maré Vermelha |
| montanhas_injecao | nova | 2 | U3 | Costela de Escória |
| brekmar_docas | nova | 1 | — | Roedor de Quilha Salgada |
| pradaria_guardia | nova | 1 | — | Casco de Cera Fundida |
| aethelgard_medo | nova | 1 | — | Bexiga de Pânico |
| zhur_existente | existente | 0 | — | Saltador de Palafita |
| arcadia_existente | existente | 0 | — | Arame Vivo |

---

## Rodada a (prazo de turno 12 s)

Gerado por `scripts/bestiario/eval_geracao.py`. Pedidos congelados em `tests/fixtures/spec361_pedidos.yaml`; métricas e limiares em `services/creature_gen_eval.py` (§3.9).

- antes: `docs/spec361/eval-antes-2026-11-02.json` · real=True
- depois: `docs/spec361/eval-depois-2026-11-02.json` · real=True

| métrica | antes | depois | limiar | ok (depois) |
|---|---|---|---|---|
| lint_primeira | — | 0.6364 | >= 0.7 | **não** |
| lint_final | — | 1.0 | >= 0.9 | sim |
| fallback | — | 0.0 | <= 0.1 | sim |
| caminho_ok | — | 1.0 | >= 1.0 | sim |
| proibidos | 0 | 0 | <= 0 | sim |
| digitos | 0 | 0 | <= 0 | sim |
| idioma_pt | 1.0 | 0.9932 | >= 1.0 | **não** |
| fisico | 0.9167 | 1.0 | >= 0.95 | sim |
| campos_349 | 0.0 | 1.0 | >= 1.0 | sim |
| vizinho_max | 0.0833 | 0.1286 | < 0.45 | sim |
| latencia_nova_p95_ms | 7680 | 11936 | <= 15000 | sim |
| latencia_variante_p95_ms | 0.0 | 6.0 | <= 50 | sim |
| prompt_chars | 0 | 13401 | <= 14000 | sim |
| variante_vs_nova | — | {'variante': 1, 'nova': 0} | — | — |
| latencia_nova_p50_ms | 5658 | 7654 | — | — |

## Pedidos (depois)

| id | caminho | tentativas | códigos | nome |
|---|---|---|---|---|
| zhur_colmeia_auto | variante | 0 | — | Saltador de Palafita da Mente Única |
| zhur_colmeia_nova | nova | 1 | — | Enxame de Agulha Oca |
| zhur_odres | nova | 1 | — | Bexiga de Odre Podre |
| arcadia_fundicao | nova | 2 | R20,U3 | Escória de Veias Fundidas |
| pantano_cria | nova | 1 | — | Poço de Lamento |
| skallgard_cobrado | nova | 2 | R20 | Cobrado de Vidro Oco |
| xylos_fera | nova | 1 | — | Coro de Bocas Falsas |
| costa_ingles | nova | 1 | — | Engodo de Maré Cheia |
| montanhas_injecao | nova | 2 | R20,U13,U3 | Escória de Bigorna |
| brekmar_docas | nova | 1 | — | Rói-Casco de Brekmar |
| pradaria_guardia | nova | 2 | R20 | Casco de Cal Ardente |
| aethelgard_medo | nova | 1 | — | Bolha de Fôlego Curto |
| zhur_existente | existente | 0 | — | Saltador de Palafita |
| arcadia_existente | existente | 0 | — | Arame Vivo |

---

## Rodada b (prazo de turno 12 s)

Gerado por `scripts/bestiario/eval_geracao.py`. Pedidos congelados em `tests/fixtures/spec361_pedidos.yaml`; métricas e limiares em `services/creature_gen_eval.py` (§3.9).

- antes: `docs/spec361/eval-antes-2026-11-02.json` · real=True
- depois: `docs/spec361/eval-depois-2026-11-02b.json` · real=True

| métrica | antes | depois | limiar | ok (depois) |
|---|---|---|---|---|
| lint_primeira | — | 0.4545 | >= 0.7 | **não** |
| lint_final | — | 0.8182 | >= 0.9 | **não** |
| fallback | — | 0.1818 | <= 0.1 | **não** |
| caminho_ok | — | 1.0 | >= 1.0 | sim |
| proibidos | 0 | 0 | <= 0 | sim |
| digitos | 0 | 0 | <= 0 | sim |
| idioma_pt | 1.0 | 1.0 | >= 1.0 | sim |
| fisico | 0.9167 | 1.0 | >= 0.95 | sim |
| campos_349 | 0.0 | 1.0 | >= 1.0 | sim |
| vizinho_max | 0.0833 | 0.1268 | < 0.45 | sim |
| latencia_nova_p95_ms | 7680 | 12564 | <= 15000 | sim |
| latencia_variante_p95_ms | 0.0 | 11.0 | <= 50 | sim |
| prompt_chars | 0 | 13401 | <= 14000 | sim |
| variante_vs_nova | — | {'variante': 1, 'nova': 0} | — | — |
| latencia_nova_p50_ms | 5658 | 7552 | — | — |

## Pedidos (depois)

| id | caminho | tentativas | códigos | nome |
|---|---|---|---|---|
| zhur_colmeia_auto | variante | 0 | — | Saltador de Palafita da Mente Única |
| zhur_colmeia_nova | fallback | 1 | PRAZO | Aguadeiro de Bucho |
| zhur_odres | nova | 1 | — | Bebedor de Odres |
| arcadia_fundicao | nova | 2 | R20,U2,U3 | Escória de Pulmão Duplo |
| pantano_cria | nova | 1 | — | Barqueiro de Vela Molhada |
| skallgard_cobrado | nova | 2 | R20 | Cobrado de Vidro Oco |
| xylos_fera | nova | 1 | — | Tocaia de Seiva |
| costa_ingles | nova | 1 | U13-padrao-reparado | Mão de Vasa Salgada |
| montanhas_injecao | nova | 2 | U13,U3,U13-padrao-reparado | Cavador de Bigorna |
| brekmar_docas | nova | 1 | — | Rói-Quilha de Brekmar |
| pradaria_guardia | fallback | 2 | R20,U3,PRAZO | Auroque das Ruínas |
| aethelgard_medo | nova | 1 | — | Pulmão de Cracas |
| zhur_existente | existente | 0 | — | Saltador de Palafita |
| arcadia_existente | existente | 0 | — | Arame Vivo |

Notas: `latencia_nova_p95_ms <= 15000` foi desenhado para o turno; com a geração fora do turno ela mede o job (prazo 30 s) e deixa de ser latência de turno (registrado na SPEC-361 §9). `idioma_pt` < 1 vem de "a"/"as" nas duas listas de stopwords do avaliador (empate conta como não-pt); correção é tarefa de autoria de eval.
