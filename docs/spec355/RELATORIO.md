# SPEC-355 - arena do bloco A (níveis 1/3/5, padrão+elite, avaliador congelado da 341)

Total por Postura (todas as subclasses). `arena-pos-b` = depois do bloco B; `arena-a1` = + R11/R12
(utilitárias fora da compra, 2d6 fora do pool); `arena-final` = cópia do A1 (nenhuma Carta de onda alterada).

| Postura | pós-B 0-19 | A1/final 0-19 | Δ | confirmação 20-99 | 353 (20-99) |
|---|---|---|---|---|---|
| Devoto do Abismo | 61,5 % | 64,2 % | +2,7 | 60,9 % | 61,2 % |
| Sangromante | 62,9 % | 61,0 % | -1,9 | 61,9 % | 62,2 % |
| Corruptor | 46,7 % | 45,6 % | -1,1 | 46,5 % | 46,3 % |
| Arcanista Cinzento | 46,5 % | 44,4 % | -2,1 | **43,9 %** | 45,8 % |
| Médico de Campo | 50,6 % | 52,1 % | +1,5 | 56,9 % | 54,6 % |

R13 (±2,0 pp e 45-85 %): Devoto (+2,7) e Arcanista (-2,1; 44,4 %) saíram da faixa. Passos tentados (1 por
Postura, escolhidos por `atribuicao` 0-19): Arcanista `arc1_imp_bomba_estopim` dano 4→5 (moveu só L5, ±1 luta,
total 44,4 % → 44,4 %); Devoto `dev1_con_postura_de_oracao` Fôlego 1→2 (reprovado no orçamento: power 3,2 fora de
[4,13]) e `valor` 2→1 (0 mudança). Nenhum resolveu; **ambos revertidos** e registrados em §9 (sem 2º passo).

R14 (`san1_sil_corte_sem_aviso` 6→5, v3, sementes 0-19): Sangromante 61,0 → 60,2 %, silencioso padrão
78,7 % (não cai; limite 76,6 %), Carta ainda `dominante` (+11,3 pp). Violaria a faixa → não aplicado
(ver D17 em §9: também derrubaria `test_arena_versoes_batem_com_catalogo`).

Confirmação 20-99 (uma rodada, sem reajuste): Arcanista 43,9 % (<45) e subclasses `avaro` 77,6 % /
`silencioso` 76,8 % padrão acima do teto de 75 % (exceções aceitas pela 341: 75,2 e 76,6).
