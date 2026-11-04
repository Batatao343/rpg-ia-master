# SPEC-369 Fase B: relatório antes x depois (sementes 0-19; famílias 0-7, `predador_apice` L3 0-19)

Fonte: `final-0-19.json` (ferramenta da Fase A) e `passos-0-19.json` (passos e sondagens). Estado final **sem** o passo em `mon_automato_fundicao` (ver abaixo), medido de novo sobre a `main` rebaseada (o catálogo e as famílias mudaram na `main` depois da primeira medição).

| Meta | Base (04/11, antes da Fase B) | Final |
|---|---|---|
| R13 Cartas/rodada | 1,915 | **2,144** (Dev 2,007, Cor 2,717, Arc 2,062, Méd 2,122; Sangromante 1,792, isento) - passa |
| R14 dominância | pulso, lente, mofo | `bas_cor_mofo` 0,718 e `med1_fer_garra_de_protese` 0,604 (pulso saiu da lista); voto/vazão isentas (D-369-10); 0 `dominante` |
| R15 duração | p95 12; Médico 19, 4,4 % | p95 total **11**; Médico p95 **17**, timeout **3,3 %** (sem o passo do Autômato) |
| R16 Presságio | 1,034 | **1,0355** (vitória de `on-faixa` 58,9 %) |
| R17 emboscada Corruptor | 50,7 % | 60,6 % - passa |
| R19 guardas | dentro | dentro (Dev 60,2, San 65,0 (+0,0 pp), Cor 60,6, Arc 53,5, Méd 55,8) - passa |
| R20 famílias | 5 células fora | abissal L3 77,0 (Δ +4,0), lider L3 58,5 (+0,5), lider L5 74,0 (+5,5), predador L3 72,0 (-3,0) dentro; `conjurador` L5 39,5 (Δ -7,0) fora |

**Passo da D-369-10 (R15) não aplicável pelo canal permitido.** A agilidade 4 -> 3 do `mon_automato_fundicao` quebra o hash da 373 e foi revertida (`bestiary.json` e fixture da 349). O canal de dial (`_ajustes.yaml`) é inerte para essa criatura: ela é `status: retro` e `gerar_mecanica.py` a pula (testado com `dano: -1`: `bestiary.json` e cartas idênticos byte a byte). Sem o passo, o R15 fica em p95 total 11, Médico p95 17 e timeout 3,3 %, **piores** que o limite registrado (p95 total 9, Médico 16, 0,8 %).
