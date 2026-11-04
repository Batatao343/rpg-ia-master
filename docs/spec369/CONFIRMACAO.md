# SPEC-369 Fase C: confirmação única (R22)

Rodada única, sem reajuste. Sementes: 260-339 (base, uso, posturas, emboscada, pressagio `conhecida`/`on`), 260-267 (famílias), 260-279 (`predador_apice` L3, mesclado na célula). Fase B = `final-0-19.json`; Fase C = `confirmacao.json`. A tolerância da Fase C (D-369-11) só vale para limites registrados.

| Meta | Fase B | Fase C | Limite / tolerância | Resultado |
|---|---|---|---|---|
| R13 Cartas/rodada total | 2,144 | 2,152 | >= 2,00 | passa |
| R13 piso por Postura (Devoto / Corruptor / Arcanista / Médico) | 2,007 / 2,717 / 2,062 / 2,122 | 1,998 / 2,676 / 2,071 / 2,156 | >= 1,90 (Sangromante isento: 1,792 B, 1,800 C) | passa |
| R14(a) `arc1_cal_pulso_medido` | 1,000 | 1,000 | limite 1,0 + 0,05 | passa |
| R14(a) `bas_cor_mofo` | 0,718 | 0,682 | limite 0,718 + 0,05 | passa |
| R14(a) `med1_fer_garra_de_protese` | 0,604 | 0,582 | meta 0,60 (limite 0,604 + 0,05) | passa |
| R15 p95 total | 11 | 10 | meta 10; limite 11 + 1 | passa |
| R15 p95 Postura (Devoto / Médico) | 11 / 17 | 11 / 15 | meta 12; Médico limite 17 + 1 | passa |
| R15 timeout Postura (Médico) | 3,3 % | 2,2 % | meta 1,0 %; limite 3,3 % (sem tolerância) | passa |
| R16 razão on-faixa/on-cego | 1,0355 | 1,0328 | meta 0,95; limite 1,0355 + 0,02 | passa |
| R16 vitória on-faixa | 58,9 % | 56,4 % | 45-85 % | passa |
| R17 emboscada Corruptor (`realista_369`) | 60,6 % | 58,2 % | >= 45,0 % | passa |
| R19(a) Posturas 45-85 %, padrão <= 75 %, Arcanista `todas` >= 45 | ok | ok | `guarda_r19.ok` | passa |
| R19(c) vitória total | 67,4 % (on 61,8) | 66,0 % (on 59,3) | 45-85 % | passa |
| R20 `conjurador` L5 (on / Δ) | 39,5 % / -7,0 pp | 47,0 % / -5,5 pp | limite 39,5 % / 7,0 pp + 5 pp | passa |
| R20 `predador_apice` L3 (on / Δ, 200 lutas por modo) | 72,0 % / -3,0 pp | 69,5 % / -2,5 pp | meta 45-85 % / 10 pp | passa |

Testes (`-n 2`): `tests/test_spec369_metas.py` + `tests/test_spec369_regua.py` = 35 passed, 0 xfailed. Os 7 `test_r22_confirmacao` (r13, r14, r15, r16, r17, r19, r20) saíram do xfail e passam.

Números por Postura estão em `confirmacao.json`. Nenhum produto, régua ou limite foi alterado.
