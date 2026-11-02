# Smoke 3 com LLM real: combate por cartas (épico SPEC-327 a 362)

Data: 02/11/2026, de 05:26 a 06:05 UTC. Código: `main` em `b4f35507`, o mesmo deployado no staging.

**Parte A (local).** API `legacy` em `127.0.0.1:8753`, rodando de uma cópia `git archive` do HEAD em `%TEMP%\claude\rpg-smoke3`, com o build atual de `web/dist`. As flags vieram de `scripts/staging/staging_flags.json`, mais `RPG_CREATURE_ART=on`. Foram ligadas `RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_ENEMY_DECKS`, `RPG_CARD_REWARDS` e `RPG_COMBAT_NONLETHAL`, além de `RPG_LORE_QUESTS`, `RPG_NPC_KNOWLEDGE`, `RPG_WORLD_ENGINE`, `RPG_SHARED_POOL` e `RPG_TOKEN_STREAM`. O LLM era real, via `ROUTES` com o DeepSeek `deepseek-v4-flash` como primário.

Os 3 personagens jogaram 29 turnos de jogo, mais 3 criações:

- **Haldor**, Devoto do Abismo, Skallgard, com Ketil, a 1440. Teve uma vitória sem matar, usou a loja e venceu um encontro de viagem com emboscada (o Mímico agiu primeiro).
- **Ilsa**, Arcanista Cinzento, Brekmar, a 390. Começou com Vitalidade 16, comprou na loja pelo painel e venceu Dorn sem matar.
- **Mirela**, Sangromante, Montanhas Afiadas (cena de 3 zonas com a carta *Névoa Cinza do Ermo*), a 1440. Pagou custo em Vitalidade, tentou fugir 4 vezes (perseguição), chegou à rodada 5 com "O Abismo se aproxima" e morreu, com Última Ação e a Roda.

**Parte B (staging).** `https://rpg-ia-master-staging.vercel.app`, perfil `hosted-supabase`, `git_sha` b4f35507. Usei 2 contas sintéticas pelo mesmo caminho de `two_user_smoke`: `generate_link` e `/auth/verify`. Elas receberam crédito sintético por `credit_verified_purchase`, o caminho já existente de `voice_smoke`/`two_user_smoke`. Houve duas execuções:

- **Execução 1:** abertura do combate, tentativa de retrato pago e conta B.
- **Execução 2:** só a conta A, combate até o fim.

A limpeza confirmou `games_deleted` e `users_exist_after: [false, false]` nas duas execuções.

Evidência (tudo em `scratchpad/smoke3/`):

- `out/*.png`: prints.
- `out/state-<herói>-<rótulo>.json`: estado após cada passo.
- `out/hist-<herói>.json`: `/game/history` completo.
- `server.log`: log JSON da API, com `llm.attempt` e `turn`.
- `out/events.jsonl`: requisições e respostas do navegador.
- `stg1/` e `stg2/`: log do staging (`stg_log.jsonl`, com `usage_events` por turno), estados e histórico.
- `turns.cjs`: script que agrega LLM e latência a partir do `server.log`.

## 1. Tabela por spec (§6)

Legenda: OK = passou · FALHOU · NV = não verificado · BLOQ = bloqueado.

### SPEC-342: acabamento do front

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. Faixa com a carta de cena e "Relógio do Abismo: desperta na rodada 5" | OK. *Névoa Cinza do Ermo* aparece na faixa; a cena não tinha objetivo | `out/7947529-Mirela-t1-1440-combate.png`, `out/stg-board-390.png` |
| 2. Presságio → armar → alvo → prévia → "Jogar em X" → 2ª carta → "Sem matar" → "Encerrar" | OK. O derrubado fica `incapacitado` (`final_status`) e a marginália diz "Encerro a rodada: Golpe do Penitente, Golpe do Penitente. Sem matar." | `out/state-Haldor-r3.json`, `out/state-Ilsa-r3.json`, `out/hist-Haldor.json` (entradas 5 e 7) |
| 3. Rodada 5 ou mais: "O Abismo se aproxima" | OK na narração e no registro (Mirela r5; staging r5). Não confirmei o texto na faixa | `out/state-Mirela-f2.json`, `stg2/stg_log.jsonl` |
| 4. Espólio com tooltip de palavra-chave e ponto `has-loot` | OK. O tooltip de *Interromper* aparece e `has-loot` = 1 nas duas larguras | `out/7402471-Haldor-esp-1440-2-tooltip.png`, `out/7855185-Ilsa-esp-390-0-entrada.png` |
| 5. Passos 1 e 2 a 390 com toque | OK (Ilsa) | `out/7760960-Ilsa-r1-390-2-previa.png`, `out/7763897-Ilsa-r1-390-3-fila.png` |

### SPEC-345: bugs do teste no navegador

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. Modo `off` | NV. Rodei só com as flags `on` | n/a |
| 2. Modo `on`: `mech_log` sem `?` e inimigo a 0 "sem Vitalidade" até cair | OK. Nenhum `?` nos `mech_log`; aparece "Dorn está sem Vitalidade — cada golpe agora abre Ferimentos." | `out/state-Ilsa-r2.json`, `out/state-Mirela-r2b.json` |
| Fronteira de texto: sem `[SISTEMA]`/`[RESULTADO]`, sem id com `_` e sem `Mortos:`/`Espólio:` | FALHOU parcialmente. Não há tags nem `Mortos:`. Vazam `espada_gasta`, `quase_livre` e `item_desconhecido` (P2-4, P3-1) | `out/hist-Haldor.json`, `out/hist-Mirela.json` |
| 3. Provider e modelo | DeepSeek `deepseek-v4-flash`. 2 timeouts no CLASSIFY caíram para Groq `openai/gpt-oss-20b` | `server.log` |

### SPEC-346: combate sem LLM por rodada e desfecho narrado

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. A abertura abre o tabuleiro; rodadas sem `llm.attempt`; registro por rodada | OK. As 12 rodadas de meio de luta e de fuga tiveram **0** chamadas, com p50 de 114 ms. No staging, 4 rodadas com 0 linhas `usage_events` e 0,7 a 1,0 s | `server.log`, `turns.cjs`, `stg2/stg_log.jsonl` |
| 2. Vitória: registro, resumo da IA sem números e com a arma certa, espólio | OK no Haldor 1 ("espada gasta", Golpe do Penitente, Ketil erra) e na Ilsa. FALHOU na vitória do Mímico: o ferimento do inimigo foi atribuído ao herói (P2-2). "Vasculho o corpo" não foi verificado | `out/state-Haldor-r3.json`, `out/state-Haldor-a3.json` |
| 3. Morte do Sangromante: nome de espécie, resumo e Roda sem bullets, DoT, crítico por dupla e Última Ação | Local: OK. A prosa está certa (o Minotauro esmaga, a adaga do herói fere o goblin) e a Roda vem depois. Há ressalvas: "Goblin morre" aparece antes da Última Ação e `death.killer` = "Goblin" (P3-5). Staging: FALHOU. O texto de morte saiu "Você tomba. Goblin tomba. SmokeA cai. SmokeA perde os sentidos." (P1-2) | `out/state-Mirela-f4b.json`, `stg2/stg_state_A_end.json` |
| 4. Fuga resumida | NV. A fuga é perseguição; em 4 tentativas não saiu do combate. O `mech_log` diz "escapou" enquanto a tela diz "Não escapou" (P2-3) | `out/state-Mirela-f1.json`, `out/8588655-Mirela-f1-1440-2-pos.png` |
| 5 e 6. Router esgotado / CLASSIFY só no Groq | NV, porque exigiria reiniciar com `RPG_ROUTES`. Observação real: DeepSeek CLASSIFY deu timeout de 12 s → Groq `gpt-oss-20b` teve sucesso nos turnos t7 e t8 do Haldor | `server.log` |
| 7. Rodada `off` | NV | n/a |

### SPEC-347: layout, retrato e registro da rodada

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. A 390: prévia com "Jogar em X" e "Cancelar" sem rolar; 2 cartas + "Sem matar" com a barra numa linha | OK | `out/7760960-Ilsa-r1-390-2-previa.png`, `out/7763897-Ilsa-r1-390-3-fila.png` |
| 2. A 1440 com 3 zonas: mão sem rolar, chips legíveis | OK. Mostra "Também na cena: Forja Abandonada · Poço de Escória" | `out/7947529-Mirela-t1-1440-combate.png` |
| 3. Desfecho com "Continuar"; o tooltip do espólio não cobre "Levar"; Forja com o motivo; Acervo com "Utilitária" | OK | `out/7370890-Haldor-v3-1440-top.png`, `out/7402471-Haldor-esp-1440-2-tooltip.png`, `out/7404167-Haldor-esp-1440-3-pos-espolio.png` |
| 4. Reabrir o save → Livro na última narração | OK: `scrollTop` = `max` (5153 a 1440; 2323 a 390) | `out/8753253-Haldor-reopen-1440.png`, `out/8767260-Ilsa-reopen-390.png` |
| 5. Retrato pago no staging | BLOQ. A cotação devolve `503 image_generation_disabled`, mas a view oferece `gerar` (P1-1) | `stg1/stg_log.jsonl` (`quote`) |
| 6. Prints em `docs/spec347/depois/` | NV, fica para o coordenador (os prints estão em `out/`) | n/a |

### SPEC-352: retrato pago

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1 a 6 | BLOQ, por 2 motivos. (a) `POST /game/{id}/art/quote` `{image_type: monster, enemy_id: enemy_goblin_1}` → **503 `image_generation_disabled`**, com saldo suficiente (1244 milli contra preço de 1 Estilha). (b) Em paralelo, `combat.enemies[].retrato.gerar = {preco_estilhas: 1, escopo: "tipo"}` aparece para Goblin e Minotauro nas contas A e B, mas o botão "Gerar retrato" não aparece no chip a 390. Nenhuma geração, nenhum débito: o saldo de B ficou igual (311 → 311) | `stg1/stg_log.jsonl` (`portrait_offer`, `quote`, `B_open`), `out/stg-board-390.png` |

### SPEC-353: motor e backend do 2º smoke

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. Rodada 0 sem `npc_ketil`; nome de espécie; texto do Golpe = prévia; ordem igual nas 3 vistas | OK para o id: o chip diz "Ketil". Nome: "Criatura da Fogueira" ainda é genérico (P3-3). A prévia "7–14", o texto "Causa 7 de dano" e o dano real 7 batem. A ordem é igual no Livro, no `mech_log` e no RoundBoard, inclusive na emboscada (Mímico primeiro) | `out/7263107-Haldor-t1-1440-combate.png`, `out/state-Haldor-r2.json`, `out/state-Haldor-a1.json` |
| 2. Objeto de cena jogável | NV. Nenhuma das 4 cenas trouxe objeto (vieram Névoa ×2, Eco da Boca, nenhuma) | n/a |
| 3. Vitória: autoria certa, `registro_rodada` no turno da vitória, Preparação/Baralho, raridade | Autoria: OK em 2 de 3, FALHOU no Mímico (P2-2). Registro: OK ("O que se jogou na rodada final"). Raridade: OK ("Maça de Ferro, item incomum"). Preparação: o rótulo "Preparação 4/24" mistura modelos (P3-7) | `out/7370890-Haldor-v3-1440-top.png`, `out/7404167-Haldor-esp-1440-3-pos-espolio.png` |
| 4. Mirela: linha de custo e conta fechada; queda sem "não encontra alvo" falso, com a Roda | OK: "Você · Corte Raso · custo · 2 Vitalidade"; a conta 18 → 10 → 0 fecha | `out/state-Mirela-r2.json` (rodada após o 409), `out/state-Mirela-r3.json` |
| 5. Fuga: `Fuga · total N vs M` | OK no formato, mas o veredito "escapou" está errado na perseguição (P2-3) | `out/state-Mirela-f1.json` |
| 6. Latência do desfecho até ~8 s | OK: 6,2, 6,2, 7,0 e 7,5 s no local; 7,2 s no staging | `turns.cjs`, `stg2/stg_log.jsonl` |

### SPEC-354: tela do 2º smoke

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. A 1440, 2 inimigos e aliado: mão sem rolar, registro em uma coluna, ícone de família, nenhum id cru | OK. Lua para "desconhecida", caveira para morto-vivo; a auditoria encontrou `leaks: []` em todas as telas. Não houve uma cena com 2 inimigos **e** aliado: Haldor tinha 1 inimigo + Ketil, Mirela 2 inimigos sem aliado | `out/7263107-*.png`, `out/7947529-*.png` |
| 2. A 390: "Desfazer fila" e a nota visíveis acima da barra | OK | `out/7763897-Ilsa-r1-390-3-fila.png` |
| 3. Vitória: sem toast a 1440; a 390, "O desfecho" e "A última rodada" | OK a 390. A 1440, o print foi tirado depois de recarregar, então o toast no instante da vitória não foi verificado | `out/Ilsa-v3-390-full.png` |
| 4. Recarregar, reabrir o save, Livro na última narração | OK nas duas larguras | `reopen2.cjs` + prints de reopen |
| 5. Toque a 1440: abas e cabeçalho com ≥ 44 px | OK: `pointer: coarse` = true e nenhum alvo < 44 | `touch1440.cjs`, `out/Haldor-touch-1440.png` |
| 6. Comparar `docs/spec354/depois/` | NV (coordenador) | n/a |

### SPEC-355: pendências abertas

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. Voto Sussurrado com o presságio em Ketil; mão sem "Aguentar" | Voto: NV. Quando o presságio mirava Ketil, o Voto não estava na mão; quando estava, mirava o herói ou errou. Mão: OK, "Aguentar" está preparada mas nunca aparece na mão | `out/state-Haldor-t1.json`, `stg2/stg_log.jsonl` |
| 2. Leitura de Pressão (Arcanista) | NV: carta fora da mão inicial | n/a |
| 3. "Armadura Comprometida" legível | NV: não apareceu | n/a |
| 4. Skallgard sem "Descarga Arcana"; Golpe do Penitente com `Proteção −N` | Renegado: NV (não apareceu). `Proteção −N`: OK, com "Proteção −1" e "Proteção −6" | `out/state-Haldor-a1.json`, `stg2/stg_log.jsonl` (A-r5) |
| 5. Vitória com Reação | NV: nenhuma Reação disparou | n/a |
| Repetir 1, 3 e 5 no staging (item 17) | Parcial: a abertura, as rodadas sem LLM e o desfecho foram repetidos no staging | `stg2/` |

### SPEC-357: cartas neutras, loja e missões

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1. Brekmar: `loja_cartas` com 3 ofertas, sem `neu1_ka_*`, preço R6 | OK: Quinquilharias da Maré, 3 ofertas a 40 (Skallgard: 50), sem `neu1_ka_*` | `out/state-Ilsa-t0.json` |
| 2. "Quero comprar o <nome> da Okka" → compra | FALHOU com a frase da própria spec. "Quero comprar a Lança de Gancho da Forja dos Clãs" só respondeu o preço, sem cobrar (P2-5). Com "Compro a Lança de Gancho" a compra saiu exata: −50, `known_cards` +1, "+1 Carta: Lança de Gancho \| Ouro −50 (total 20)" | `out/state-Haldor-t7.json`, `out/state-Haldor-t8.json` |
| 3. Pergunta de preço lista as técnicas | OK: a pergunta foi roteada para LOOT e listou 3 linhas "Técnica: …". Mesma lista vaza `item_desconhecido` (P3-1) | `out/state-Haldor-t6.json` |
| 4. Compra pelo painel: a oferta comprada mostra "Você já conhece" | OK (Ilsa, 390). O rótulo "só para o Acervo — Baralho cheio" está errado para quem não tem Baralho (P3-6) | `out/7679990-Ilsa-loja-390-0.png`, `out/7681622-Ilsa-loja-390-1.png` |
| 5. Quest de lore `justa` | NV: não fiz o save de quest | n/a |
| Frase ambígua só responde o preço, sem cobrar | OK: o ouro ficou em 70 nas duas frases | `out/state-Haldor-t6.json`, `out/state-Haldor-t7.json` |

### SPEC-362: balanço do Arcanista

| Item do §6 | Resultado | Evidência |
|---|---|---|
| 1 a 3 (arena e `run_round`) | Fora do escopo deste smoke (executor) | n/a |
| 4. Arcanista com flags `on`: carta alterada na mão com o número novo; mão sem utilitária | Vitalidade 16: OK (`player_stats.max_vitalidade` = 16). Cartas alteradas (`truque`, `pulso_medido`): NV, nenhuma veio na mão (são cartas de onda). Mão sem utilitária: OK, mas o Espólio ofereceu "Leitura Arcana" (utilitária) e ela entrou no Baralho (P3-6) | `out/state-Ilsa-t0.json`, `out/state-Ilsa-esp.json` |

### Pedidos extras do coordenador

| Pedido | Resultado |
|---|---|
| A história abre o tabuleiro; sem caixa de texto livre com o tabuleiro aberto | OK. O composer vira "Na luta, você age pelas cartas do tabuleiro." e a auditoria registrou `ta: []` em combate; a 390 no staging, `textbox 0` |
| O botão Fugir rola o dado e o dado aparece no registro | OK: "Fuga · total 16 vs 12" e "total 7 vs 12 · falhou". Mostra só o total, sem os dados |
| Emboscada: o inimigo age primeiro e o Livro conta na ordem | OK no encontro de viagem do Mímico |
| Carta de iniciativa cancela a surpresa | NV: nenhum personagem tinha `buff_iniciativa` (são cartas de subclasse) |
| Prévia ≈ dano real | OK: Golpe 7 → 7; Fagulha 6 → 5 com Proteção −1; Corte Raso 8 → 15 em crítico |
| Preparação nunca acima do limite após o espólio | OK: 4/24 (Haldor) e 4/24 (Ilsa). O rótulo confunde (P3-7) |
| Ids internos nunca visíveis | FALHOU: `espada_gasta`, `quase_livre`, `item_desconhecido` (P2-4, P3-1). Nenhum `npc_`/`cena_` vazou |
| Inimigo a 0 não fica de pé sem explicação | OK: "está sem Vitalidade — cada golpe agora abre Ferimentos." |
| `/game/history` após recarregar | OK: Haldor 25, Ilsa 9, Mirela 17 entradas, sem duplicata nem perda (`reopen2.cjs`: `miss 0 dup 0`). O 409 da rodada rejeitada não foi persistido |

## 2. Achados

**P1-1. Retrato pago oferecido, mas a geração está desligada no staging.**
- **O que acontece:** `combat.enemies[].retrato.gerar` vem preenchido (`preco_estilhas: 1`, `escopo: tipo`) para todos os inimigos, mas `POST /game/{id}/art/quote` responde `503 image_generation_disabled`.
- **Reprodução:** conta nova, Montanhas Afiadas, "Saco a espada e ataco o goblin mais próximo" → `state.combat.enemies[0].retrato.gerar` ≠ null → quote → 503.
- **Provável causa:**
  - `api.py:2948-2970` (`_enemy_portrait`) e `services/creature_art.py:230-232` oferecem quando `creature_art.mode() == "on"` e há preço, sem consultar o kill switch e o gate da geração dinâmica que a cotação usa (`api.py:~4909-4960`, `image_generation_disabled`).
  - No staging, conferir `RPG_DYNAMIC_ART_ENABLED` e os price profiles. O preset diz `dynamic_art: on`, mas o runtime recusa.
- **Na tela:** a 390 o chip **não** mostrou o botão "Gerar retrato" apesar do `gerar` na API (`out/stg-board-390.png`). Ou a UI esconde o botão por outro critério, ou houve divergência entre instâncias (cache de preço de 60 s em `_portrait_price_estilhas`, `api.py:2862`).
- **Consequência:** a SPEC-352 fica toda bloqueada.

**P1-2. Texto de morte do staging contradiz o motor.** Este é o desfecho mostrado ao jogador.
- **O que acontece:** depois da Última Ação (2 chamadas LLM com sucesso), a mensagem final foi: "Você tomba. Goblin tomba. SmokeA cai. SmokeA perde os sentidos. Você carrega ferimento crítico na perna, ferimento crítico no braço."
- **Erros no texto:**
  - O nome está errado: "SmokeA", quando o herói é "Smoke3A". Parece que algum filtro tira dígitos do nome.
  - O herói aparece três vezes: "Você", "SmokeA cai" e "SmokeA perde os sentidos".
  - "Goblin tomba" repete uma morte da rodada 2.
  - O "ferimento crítico na perna" foi causado pelo herói no Minotauro, mas o texto o põe no herói.
- **Reprodução:** `stg2/stg_log.jsonl` (A-r5) e `stg2/stg_state_A_end.json`.
- **Provável causa:** o fallback ou template do resumo de morte. Procurar "perde os sentidos" e "carrega ferimento" em `agents/combat.py` e `services/death_flow.py`. Ver por que o resumo da IA foi descartado mesmo com sucesso (rejeitado pela validação de autoria?). No local, a mesma morte saiu em prosa correta.

**P2-1. A UI permite mirar um inimigo escondido com carta básica, e a rodada inteira é recusada com 409.**
- **Reprodução:** Mirela, rodada 2, Goblin com `concealment: "escondido"` (Névoa ou flanco). Talho de Sangue Ralo ou Corte Raso → o chip do Goblin aparece válido → "Encerrar" → `409 invalid_target` ("O alvo escolhido deixou de ser válido. Escolha de novo."). A fila continua apontando para o Goblin e o jogador fica preso.
- **Causa:**
  - `api.py:3165` monta `combat.cards` com `prepared_only=True`, então as cartas da mão `bas_*` não recebem `valid_targets`.
  - `web/src/combat/deck.ts:176-178` (`cardTargets`) cai em `enemyIds` (todos os inimigos).
  - `services/combat_targeting.py:96-100` exclui o escondido.
- **Correção sugerida:** a API manda `valid_targets` por carta da mão (`pilhas.mao[]`), ou o fallback do front filtra `concealment`. Faltam também uma marca "escondido" no chip e, na recusa, apontar qual jogada caiu.
- **Evidência:** `out/8029576-Mirela-r2-1440-4-pos-combate.png`, `server.log` (`09f640012c13`).

**P2-2. O resumo da vitória troca a autoria do ferimento.**
- **O que acontece:** na vitória sobre o Mímico (que fugiu), a IA escreveu "o fio de sangue que escorreu pelo seu braço é a única prova…". O ferimento leve no braço foi do Mímico; Haldor estava com 18/18. O mesmo texto diz "o corpo intacto", o que é contraditório.
- **Evidência:** `out/state-Haldor-a3.json`.
- **Provável causa:** o prompt de resumo (`agents/combat.py`, resumo final). A frase do registro "Você ataca Mímico… ferimento leve no braço" não deixa claro de quem é o braço. Passar o ferimento já com o portador ("ferimento leve no braço do Mímico").

**P2-3. A fuga em perseguição registra "escapou" quando não escapou.**
- **O que acontece:** o `mech_log` diz "Fuga · total 16 vs 12 · escapou", enquanto a tela diz "Não escapou: o inimigo ainda está no seu encalço." e o Livro diz "avança na fuga: pressionado → afastado". O combate continua.
- **Causa:** `services/combat_preview.py:326` usa `roll.sucesso`, que na perseguição significa "avançou um passo". Deveria ser "avança"/"perde terreno"/"escapou", conforme `chase_state.escapou`.
- **Também:** em 4 tentativas a Mirela não saiu, porque oscilou entre `quase_livre` e `afastado`. Com 0 de Vitalidade, a fuga não é viável. Isso é observação de balanço.
- **Evidência:** `out/state-Mirela-f1.json`, `out/state-Mirela-f2.json`, `out/state-Mirela-f3.json`.

**P2-4. Ids internos no Livro e no registro.**
- **Arma:** "Você ataca Mímico (Baú) com espada_gasta: erra/acerta" (Ataque de Oportunidade). `services/round_log.py:178-183` (`_weapon_name`) devolve o id quando `equipment.weapon` é string. Resolver o nome pelo catálogo de itens.
- **Trilha da fuga:** "Mirela avança na fuga: afastado → quase_livre". `agents/combat.py:3314-3321` usa o id cru da trilha; precisa de rótulo legível.
- **Evidência:** `out/hist-Haldor.json`, `out/hist-Mirela.json`.

**P2-5. A gramática fechada da compra recusa a frase da própria spec.**
- **O que acontece:** "Quero comprar a Lança de Gancho da Forja dos Clãs" → só preço, sem compra. A §6.2 da SPEC-357 manda testar "Quero comprar o <nome> da Okka".
- **Causa:** `agents/loot.py:385-391` (`tail` aceita só "por favor/agora/então"). Sugestão: aceitar `(?: (?:da|do|de) <nome do mercador ou do NPC presente>)?` no fim. Continua fechado, porque o nome vem da prateleira e do mercador.
- **Evidência:** `out/state-Haldor-t7.json`.

**P2-6 (repetido do smoke 2 P2-8). Crítico por dupla abaixo da defesa e frequente com 3d10.** Exemplos:
- "3d10 2 + 2 +1 = 5 vs 12 · crítico (dupla de 2)"
- "3d10 2 + 2 +5 = 9 vs 12 · crítico (dupla de 2) · 16 dano" (inimigo no staging)
- "13 vs 14 · crítico (dupla de 7)"

O registro agora explica a regra ("dupla nos dados"), mas com 3d10 a chance de dupla é de cerca de 28 % por ataque, o que pesa no balanço. É decisão do dono; o código é o cálculo de crítico do orquestrador.

**P3-1. `item_desconhecido` na consulta do mercado.** A Forja dos Clãs listou "item_desconhecido: compra 30 / venda 15". `agents/loot.py:470-471` cai em `item_id` quando falta `item_name`; a origem é `economy.public_market_snapshot`. Ou o estoque tem item sem catálogo, ou falta filtrar.

**P3-2. Linhas de condição duplicadas e em minúscula no registro e no Livro.** No mesmo turno aparecem "Minotauro Esqueleto ganha a condição Cego." / "Você ganha a condição Cego." e depois "Minotauro Esqueleto: ganha condição cego" / "Mirela: ganha condição cego" (bloco da carta de cena). Também aparecem "Minotauro Esqueleto: cego terminou." e "Smoke3A: condição Cego renovada" no `mech_log` com o nome em vez de "Você". O bloco da carta de cena (`services/round_log.py` `_voce`, e o efeito de cena em `services/conflict_scene.py`) não passa pela mesma normalização.

**P3-3. Nome de inimigo genérico.** "Atacar a criatura que ronda a fogueira" virou "Criatura da Fogueira", família "desconhecida". O Goblin também tem `familia: "desconhecida"` (`services/creature_art.py:101` `family_of`), embora haja `enemy_goblin` no bestiário.

**P3-4. Resumo da vitória de Ilsa mistura "tu" e "você".** O texto traz "teu cajado", "Ficas de pé", "Ficas … teu fôlego". O loot também saiu redundante: "Moeda de Ouro e +24 de ouro".

**P3-5. Morte local fora de ordem e com o matador errado.** O registro diz "Goblin morre." antes de "Você executa a Última Ação em Goblin: acerta — 9 de dano". O `death.killer` diz "Goblin", mas quem acertou o golpe final na Mirela foi o Minotauro, como a prosa diz. Fica `out/state-Mirela-f4b.json`. Depois da morte, o painel de Combate ainda mostra a mão com "Encerrar a rodada" e "Fugir" ativos por alguns segundos (`out/8694215-Mirela-f4-1440-2-pos.png`).

**P3-6. Utilitária no espólio e rótulo errado na loja.**
- **Espólio:** ofereceu "Leitura Arcana" (texto "Fora de combate: decifrar inscrição arcana.") como recompensa de luta, e ela entrou no Baralho (`do_acervo` 4). Ela nunca é comprada na luta, mas conta no total de 13.
- **Loja:** a fresh Arcanista vê "só para o Acervo — Baralho cheio" porque ainda não tem `deck`. `services/card_rewards.py:284-296` devolve "acervo" pelo ramo das preparadas; `web/src/cardRewards.ts:45` traduz isso como "Baralho cheio".

**P3-7. "Preparação 4/24" mistura modelos.** Com o Baralho `on`, `prepared_slots` = `DECK_MAX` (`api.py:2453-2458`, R31), mas o Acervo mostra "Preparação" contando só as cartas do Acervo. Melhor seria "Baralho 13/24" (o `player_stats.baralho` já existe).

**P3-8. Latência fora do combate.**
- Viagem Skallgard → Montanhas: 27,7 s (storyteller + enrich FAST + enrich SMART + archivist).
- Compra na loja: 17,2 s, porque o DeepSeek CLASSIFY deu timeout de 12 s antes de cair no Groq.
- A abertura do combate da Mirela levou 14,1 s com 6 chamadas.

## 3. LLM, latência e custo

**Local** (`server.log`, eventos `turn`, agregados por `turns.cjs`):

| Fase | Turnos | Chamadas LLM | p50 / máx. de latência | Custo (USD) |
|---|---|---|---|---|
| Criação (prólogo + `/game/new`) | 3 | 1 + 3–4 cada (15 no total) | 7,3–10,2 s (prólogo) e 10,5–16,2 s (`new`) | ~0,01 (estimado) |
| Abertura do combate | 3 | 12 (4/2/6) | 9,1 / 14,1 s | 0,0065 |
| Rodada de meio de luta e fuga | 12 | **0** | **114 / 248 ms** | 0 |
| Desfecho (vitória ×3, morte ×1) | 4 | 8 (resumo + arquivista) | 7,0 / 7,5 s | 0,0078 |
| Loja (consulta, preço, compra) | 3 | 8 (2 timeouts → Groq) | 12,8 / 17,2 s | 0,0018 |
| Viagem | 2 | 6 | 5,2 / 27,7 s | 0,0090 |
| **Total** | 27 turnos de jogo + 3 criações | 49 tentativas (2 falhas) | n/a | **~0,035** |

**Staging** (`usage_events` por turno):

| Fase | Chamadas LLM | Tempo |
|---|---|---|
| `new_game` | 3–4 LLM + 3 embedding | ~20 s |
| Abertura do combate | 5 LLM | 13,8–14,2 s |
| 4 rodadas | **0** | 0,7–1,0 s |
| Desfecho (morte) | 2 LLM | 7,2 s |

O staging teve 3 jogos (A1, B, A2), com cerca de 30 chamadas DeepSeek no total, por volta de US$ 0,01–0,02. Nenhuma imagem foi gerada (P1-1), então o custo de imagem foi 0. O crédito sintético deixou linhas no ledger do staging (append-only, como nos smokes 197). Usuários e jogos foram removidos.

No staging, o modal "Você tombou" está correto: Última Ação = Golpe do Penitente, queda diante do Minotauro Esqueleto, botões de checkpoint e de aceitar a morte (`out/stg-end-1440.png`, `out/stg-end-390.png`). O defeito do P1-2 está só no texto do Livro. O `/game/history` do staging tem 13 entradas, 1 por 1, sem duplicata (`stg2/stg_hist_A.json`).

## 4. Limpeza

- O servidor local (uvicorn PID 4720 → 19508) foi encerrado por `taskkill /T /F` e a porta 8753 ficou livre.
- Um `python3 -` disparado por engano (PID 5376 → 22960 → 17604) foi morto por PID logo em seguida.
- Os Chromium do Playwright fecharam junto com cada script. Os `chrome.exe` restantes são do Playwright MCP de 01/11 e não são meus.
- Os cookies do staging, gravados para os prints, foram apagados no `finally`.
- A cópia `%TEMP%\claude\rpg-smoke3` ficou no disco; pode apagar.
- Nada no repositório principal foi editado. A única exceção é `web/dist`, gerado por `npm run build`, que é gitignored.
