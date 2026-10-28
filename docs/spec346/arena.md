# SPEC-346 Etapa 8 - arena por Postura (taxa de vitória)

Avaliador congelado da SPEC-341 (`docs/spec341/arena_spec341.py posturas --seeds 20:100`), níveis 1/3/5,
`padrao` + `elite`, máquina em série (1 processo). JSON: `arena-base.json`, `arena-ambush.json`.

- **Base** = código desta branch. A abertura do tabuleiro (R1) não muda a conta da arena: o simulador
  (`scripts/cards/sim.py`) já começa pela rodada 1 com a mão comprada e, em nível <= 2 com Vitalidade cheia,
  o herói age primeiro (proteção de herói novo, mantida no caso neutro). Os números batem com o
  `RELATORIO.md` da SPEC-341.
- **Emboscada (D4)** = `docs/spec346/arena_spec346.py`: embrulha `run_round` para forçar
  `initiator="enemy"` na rodada 1 de TODA luta, inclusive níveis 1-2. É o pior caso (na prática só as
  lutas com `encounter_surprise == "enemy"` são assim).

| Postura (todas as subclasses) | Base total | padrão | elite | Emboscada total | padrão | elite |
|---|---|---|---|---|---|---|
| Devoto do Abismo | 61,2 % | 71,6 % | 50,8 % | 57,7 % | 68,0 % | 47,4 % |
| Sangromante | 62,2 % | 75,6 % | 48,7 % | 55,3 % | 70,7 % | 39,8 % |
| Corruptor | 46,3 % | 58,4 % | 34,1 % | 42,7 % | 52,9 % | 32,5 % |
| Arcanista Cinzento | 45,8 % | 57,2 % | 34,5 % | 39,2 % | 53,3 % | 25,1 % |
| Médico de Campo | 54,6 % | 61,9 % | 47,3 % | 52,8 % | 60,4 % | 45,1 % |

Leitura:

- **Base:** as 5 Posturas ficam dentro de 45-85 % (Corruptor 46,3 e Arcanista 45,8 são as mais
  baixas; `Corruptor/alma` 41,2 e `Arcanista/descoberto` 44,9 já eram assim antes e não mudam aqui).
- **Emboscada em toda luta:** a queda média é de 2 a 7 pontos. **Corruptor (42,7 %) e Arcanista Cinzento
  (39,2 %) saem da faixa** neste pior caso. Não é o cenário real (emboscada é minoria: só o encontro de
  viagem que o jogador não percebeu), mas é o dado para o dono decidir se a emboscada deve ter alguma
  contrapartida (por exemplo, a carta/condição de "vigília" que anula a surpresa, ainda não existente).
