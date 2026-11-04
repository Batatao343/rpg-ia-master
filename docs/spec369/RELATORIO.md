# SPEC-369 Fase B: relatório antes x depois (sementes 0-19; famílias 0-7, `predador_apice` L3 0-19)

Fonte: `final-0-19.json` (ferramenta da Fase A, sha-A `6ed6815d`) e `passos-0-19.json` (passos com antes/depois).

| Meta | Limiar | Base | Final | Passa? |
|---|---|---|---|---|
| R13 Cartas/rodada | total ≥ 2,00; Postura ≥ 1,90 (Sangromante isento) | 1,915 | **2,150** (Dev 2,007, Cor 2,717, Arc 2,097, Méd 2,122) | sim |
| R14 dominância | 0 de onda/assinatura básica > 60 % fora do Sangromante; 0 `dominante` | 3 (pulso, lente, mofo) | `arc1_cal_pulso_medido` 1,0 e `bas_cor_mofo` 0,714 (limite do conteúdo); `bas_dev_voto`/`bas_arc_vazao` 1,0 isentas pela D-369-10; 0 `dominante` | limite registrado |
| R15 duração | p95 total ≤ 10; Postura ≤ 12; timeout ≤ 1 % | p95 12; Médico 19, 4,4 % | p95 total **9**; timeout Médico **0,8 %**; Médico p95 **16** (> 12) | parcial (limite: Médico p95 16) |
| R16 Presságio | `on-faixa` ≤ 95 % de `on-cego` | 1,034 | **1,026** | limite registrado |
| R17 emboscada Corruptor | ≥ 45 % | 50,7 % | 60,6 % (`realista_369`) | sim |
| R19 guardas | Posturas 45-85 %, Sangromante ≤ +2 pp, nenhuma queda > 5 pp | dentro | dentro (Dev 60,2, San 65,0, Cor 60,6, Arc 57,1, Méd 55,8) | sim |
| R20 famílias | 5 células com `on` 45-85 % e \|Δ\| ≤ 10 | 5 fora | 3 fechadas (abissal L3, lider L3 e L5); `conjurador` L5 (38,5 %; Δ -8,0) e `predador_apice` L3 (61,5 %; Δ -13,5) ficam como limite | limite registrado |

Passos: 6 mantidos no B3 (5 Cartas), 3 tentados e revertidos no B5 (3 Cartas), 5 no B6 (4 Cartas de inimigo; 1 revertido). Total de Cartas de herói: 8.

`tests/test_spec369_metas.py`: R13, R17, R18 e R19 passam; R14, R15, R16 e R20 falham pelo motivo certo (números acima); `test_r22_confirmacao` é xfail (Fase C, ainda sem `confirmacao.json`). 0 xfail nos testes R13-R20 e R18.

D-369-10 (04/11): +1 passo em `mon_automato_fundicao` (`virtudes.agilidade` 4 -> 3, esquiva 14 -> 13): p95 total 11 -> 9, timeout do Médico 3,3 -> 0,8 %, Médico p95 17 -> 16; Posturas inalteradas. As isenções e os limites registrados valem para os testes de meta (ajuste do autor da régua).
