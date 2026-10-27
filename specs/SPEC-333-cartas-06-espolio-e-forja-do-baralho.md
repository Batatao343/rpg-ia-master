# SPEC-333 — Cartas #06: Espólio de cartas, Forja do baralho, Ferimentos e Cicatrizes como cartas

> **Status:** `draft`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-328 (baralho), SPEC-330 (Fardo/Purgar), SPEC-209 (aba Combate fora de encontro)
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` (economia + persistência)
> **EVAL_AUTHORING_REQUIRED:** `true` — jornadas "escolher 1 de 3", "esquecer carta no descanso", "cicatriz entra no baralho".

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] Hoje carta nova só chega no level-up (`POST /game/levelup`: carta nova ou evolução A/B, SPEC-063 R4). Entre níveis o baralho não muda. [F] Cicatrizes (`death_flow.generate_scar`) e Ferimentos são estado da ficha, sem presença no jogo de cartas.

[R] O que faz um deckbuilder viciar é **a escolha frequente e pequena**: depois de cada luta, "pego esta, aquela, ou nada?" (Slay the Spire, Monster Train); e **tirar** carta é tão valioso quanto pôr. Ferimento como **carta de status** e cicatriz como **maldição** (StS status × curse; Griftlands "Tipsy" cruzando sistemas) fazem a consequência do combate ser jogada, não só lida.

## 2. Requisitos

**Espólio**
- **R1** — Ao vencer um conflito (ou cumprir objetivo, SPEC-331), o jogador vê **3 cartas** e escolhe 1 ou **recusa** (recusar dá 15 de ouro [D?]). Sorteio determinístico (seed do conflito) ponderado: 60 % Postura do jogador, 25 % neutras/regionais (SPEC-335), 15 % da facção/família derrotada ("Saque de técnica"); raridade 70/25/5 (comum/incomum/rara), Abissal só em chefe.
- **R2** — Cartas do espólio entram no **Acervo** e, por padrão, no baralho (o jogador pode tirá-las depois). Respeita tier/`level_req` do nível atual.
- **R3** — Espólio não interrompe a narração: aparece como painel pós-conflito (`CombatOutcomePanel`) e pode ser decidido depois (pendente em `player["espolio_pendente"]`, expira no próximo conflito).

**Forja (fora de combate, `can_reorganize`)**
- **R4** — **Esquecer**: em descanso longo, remove 1 carta do baralho (não do Acervo). Em templo/curandeiro (`loot SHOP`), por ouro, sem limite.
- **R5** — **Afiar**: evolução A/B continua no level-up; adicionalmente, por material raro (`items`), uma carta comum pode virar sua versão `+` (valor +1 ou custo −1, definido na própria carta em `afiada: {...}`).
- **R6** — Limites do baralho (SPEC-328 R1) valem; baralho < mínimo completa com básicas.

**Consequências como cartas**
- **R7** — **Ferimento → carta de status** no baralho do ferido **durante o conflito**: leve = "Dor Surda" (injogável, Exaurir ao comprar, 1 Fôlego para descartar); grave = "Membro Falho" (Fôlego −1 na rodada em que é comprada); crítico = "Sangue nos Olhos" (Cego 1 ao comprar). Saem no fim do conflito.
- **R8** — **Cicatriz → maldição permanente** (Fardo) no baralho, ligada ao `scar.id`, com o lado positivo já existente (`habilidade_positiva_relacionada`) virando efeito `Vazão` (ao descartar, ganha o benefício). Tratada com Médico de Campo/templo (`Purgar`).
- **R9** — **Carga do Abismo alta** (≥ limiar de classe) insere 1 "Sussurro do Abismo" no baralho por cena: jogável a 0 Fôlego, efeito forte + Entropia +2. Tentação que apodrece: se não jogada em 2 rodadas, vira Fardo (pesquisa: Cultist Simulator).

### Fora de escopo
Loja de cartas em cidades com preço dinâmico (follow-up junto da economia). Troca de cartas com NPC.

## 3. Design técnico
- **Novo** `services/card_rewards.py`: `roll_rewards(state, conflict_summary, seed) -> list[str]`, `accept(state, card_id|None)`, `forget(state, card_id, via)`, `sharpen(state, card_id)`.
- **Novo** `data/cards/status_e_maldicoes.json` (Dor Surda, Membro Falho, Sangue nos Olhos, Sussurro do Abismo, Estilhaço de Cinza, 1 maldição por tipo de cicatriz).
- **Alterado** `api.py`: `POST /game/espolio`, `POST /game/forja` (esquecer/afiar), bloco `espolio_pendente` no state. `death_flow.generate_scar` passa a registrar a carta de maldição.

## 4. Plano (TDD)
1. `tests/test_card_rewards.py` — 3 cartas determinísticas; pesos; recusa paga ouro; respeita tier.
2. `tests/test_forge.py` — esquecer só em descanso longo / templo; afiar consome material.
3. `tests/test_wound_status_cards.py` — Ferimento insere carta e remove no fim; cicatriz vira maldição persistente; save/load.
4. Playtest harness (`playtest/`) 50 turnos: baralho médio fica entre 15–22 cartas.

## 5. Critérios de aceite
- [ ] R1–R9 com teste; jornada e2e autorada em tarefa separada
- [ ] Nenhuma recompensa fora do tier; ouro só via regra (mecânica é Python)
- [ ] `uv run pytest` verde; saves antigos (sem espólio) carregam

## 6. Smoke real
1. Vencer bandidos da Mão Sombria → espólio com 1 carta da facção. 2. Ganhar Ferimento grave → carta "Membro Falho" na mão, some ao fim. 3. Descanso longo → esquecer 1 carta.

## 7. Riscos
- Inchaço de baralho → R6 + Esquecer + recusa recompensada.
- Maldição frustrante: sempre há como purgar, e o lado positivo da cicatriz fica jogável.
