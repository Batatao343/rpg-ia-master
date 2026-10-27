# SPEC-333 — Cartas #06: Espólio de cartas, Forja do baralho, Ferimentos e Cicatrizes como cartas

> **Status:** `in-progress` (implementada `off` em 27/10 atrás de `RPG_CARD_REWARDS=off|shadow|on`; falta revisão independente Sol, smoke real §6 e jornadas e2e — ver §8)
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
- [x] R1–R9 com teste (`test_card_rewards.py`, `test_forge.py`, `test_wound_status_cards.py`); jornada e2e autorada em tarefa separada (pendente)
- [x] Nenhuma recompensa fora do tier; ouro só via regra (mecânica é Python)
- [ ] `uv run pytest` verde (suíte completa: coordenador no pouso); saves antigos (sem espólio) carregam (campos opcionais; flag `off` não toca a ficha)

## 6. Smoke real
1. Vencer bandidos da Mão Sombria → espólio com 1 carta da facção. 2. Ganhar Ferimento grave → carta "Membro Falho" na mão, some ao fim. 3. Descanso longo → esquecer 1 carta.

## 7. Riscos
- Inchaço de baralho → R6 + Esquecer + recusa recompensada.
- Maldição frustrante: sempre há como purgar, e o lado positivo da cicatriz fica jogável.

## 8. Implementação e desvios (27/10)
Flag `RPG_CARD_REWARDS=off|shadow|on` (padrão `off`; `shadow` só mede, `source=auto`). Decisões do dono: espólio "1 de 3" a cada vitória real / objetivo `cumprido` (SPEC-331; `falhou` = nada), recusa = 15 de ouro. Módulos: `services/card_rewards.py` (sorteio, `accept`, `forget`, `sharpen`, `purge_curse`, blocos da API), `services/card_status.py` (R7/R9 dentro do conflito), `data/cards/status_e_maldicoes.json` (9 Cartas, `origem: cartas-333`, fora do Acervo/progressão/espólio). API: `POST /game/espolio`, `POST /game/forja` (classe `mutation`; erros `espolio_rejected`/`forja_rejected`/`card_rewards_off`); `player_stats.espolio_pendente` e `.forja` só com a flag `on`. Telemetria: `card_offered`/`card_picked` com `source=espolio`.
Interpretações e desvios (revisar):
- **Fonte "neutras/regionais"**: lê o catálogo dinamicamente (classe vazia/`Neutra`, `regiao` opcional); hoje não há Cartas assim (SPEC-335), então a fatia cai nas demais fontes. "Saque de técnica" = `cartas` dos inimigos derrotados (`enemy_card_ids`; SPEC-332 alimenta). Abissal = `raridade: abissal` ou apice, só com chefe derrotado (`categoria: chefe`); `epica` conta como `rara`.
- **R7**: o status entra no TOPO do monte (chega à mão da rodada seguinte). Dor Surda = injogável, pesa 1 rodada e sai do ciclo (Exaurir); a opção "1 Fôlego para descartar" **não foi implementada** (exigiria nova jogada na UI; follow-up). Membro Falho cobra −1 Fôlego na rodada em que é comprada; Sangue nos Olhos aplica Cego por 1 rodada. Vocabulário: campo `ao_comprar_status` (fechado) lido por `card_status.py`.
- **R8**: a maldição (Fardo + Vazão) é escolhida pela região do Ferimento; o "lado positivo" é um efeito de Vazão fixo por região (a frase do LLM em `habilidade_positiva_relacionada` é só sabor — número vem de Python). `set_deck` não deixa tirar a maldição; Purgar fora de combate (`templo`/`medico`, 40 de ouro). Em combate, `purgar_fardo` continua aliviando só aquele conflito.
- **R9**: Sussurro do Abismo (`sus_sussurro_abismo`) usa `custo_entropia: -2` (ganho de Entropia, limitado a `max_entropy`) e `custo_folego: 0`; jogável via `player["cartas_cena"]` (limpa no fim do conflito). Apodrece em Estilhaço de Cinza após 2 rodadas sem ser jogada.
- **Templo/curandeiro**: sem tag própria no mapa, vale tag `templo|santuario|curandeiro|hospicio` ou cidade segura (`cidade`+`seguro`). Descanso longo concede 1 carga de Esquecer (`forja_esquecer`).
- **Afiar**: material = item `type: material` com raridade rara (novo `essencia_de_cinza`; ainda sem fonte de drop/loja — follow-up). A versão `+` vem de `afiada` na Carta; sem `afiada`, +1 no valor numérico do efeito principal; Carta sem valor numérico (fórmula legada) não é afiável.
- `data/cards/_orcamento.json`: `status`/`maldicao` entram em `tipos_isentos`; `tests/spec330_equivalence.py` e o teste de 323 Cartas passaram a reconhecer `cartas-333`.
