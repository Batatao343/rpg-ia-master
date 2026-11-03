# Smoke local (LLM real): SPEC-368 §6

Feito em 03/11/2026, das 18:10 às 19:20 (horário local), pelo agente de smoke local. O item 11 (staging, imagem, concorrência) é do coordenador e não está aqui.

**Ambiente.** Cópia `git archive` de `2a6e0945` (HEAD da `main` na hora) em pasta fora do OneDrive, `web/dist` gerado dela, `.env` copiado do checkout. Perfil `legacy`, saves na pasta da cópia. Quatro APIs, cada uma na sua porta:
- `:8756`, preset de `scripts/staging/staging_flags.json` (cartas `on`) mais `RPG_CREATURE_ART=on`, `RPG_NPC_KNOWLEDGE=on`, `RPG_WORLD_ENGINE=on` (o Jev router do preset não foi ligado);
- `:8757`, cartas `off` (item 9);
- `:8758` e `:8759`, rotas só Groq (item 10), com cartas `on` e `off`.

Os saves dos itens 1–7, 12–14 vieram de `tests/fixtures/spec368_seed.py::seed_save`, e os jogos novos pela API. A cópia foi apagada no fim; as APIs foram mortas por PID.

**LLM.** DeepSeek `deepseek-v4-flash` em todos os tiers. Groq entrou só como fallback (8756: 1 CLASSIFY e 2 FAST do DeepSeek deram `invoke_error` e caíram no Groq) e nas portas 8758/8759.

Evidência bruta (fora do repo), em `C:/Users/guilh/AppData/Local/Temp/claude/c--Users-guilh-OneDrive--rea-de-Trabalho-rpg-ia-master/f66a5847-73fa-4458-abe7-93e60a175ae9/scratchpad/`:
- `out/*.json`: estados e respostas por rodada.
- `out/*.png`: prints a 390 e a 1440.
- `out/llm-*.jsonl`: uma linha por tentativa de LLM, com tokens.
- `out/server-*.log`: logs das APIs.
- `out/rascunhos/`: lotes do `draft.py`, com `_ondas.yaml`.
- `out/saves-copia/`: saves.
- `*.py` e `ui.cjs`: scripts do smoke.

## Tabela item → resultado

| Item | Resultado | Evidência |
|---|---|---|
| 1 (328 §6.2, R1–R3) | **ok**. Pacto: 1 Fôlego emprestado debitou **-2 Entropia (16 → 14)** e somou **+1 Carga**, com a mensagem "Pacto do Abismo: … -2 Entropia e +1 Carga". Com 2 empréstimos na rodada (3 cartas de custo 1, Fôlego 1) a Carga ficou em 1 (1×/rodada) e a Entropia caiu 4 (16 → 12). **Recusa:** 5 cartas de custo 1 com Fôlego 2 e `pacto_max` 2 deram "Fôlego insuficiente… o Pacto do Abismo empresta no máximo 2 por rodada", sem gasto, rodada igual e **presságio idêntico** (mesma faixa [10,20] e mesmo sinal), isto é, sem reroll. **Rollback:** save `1/rollback` com `on`: Preparadas = 3 do baralho (`corte_troca`, `finta`, `esquiva`); na API `off`, as 4 de antes (`+ san_pacto`); de volta ao `on`, as mesmas 3. Round-trip exato. | `out/i1b.json`, `out/i1c-r1.json`, `out/i1r-*.json` |
| 2 (329 §6.2/§6.3) | **ok em parte**. Família estudada (Goblin com Cartas reveladas): a partir da rodada 1 o chip mostra faixa e nome ("ataque, faixa [10,20], Pancada Esmagadora"; depois "Pancada de Tronco" [8,16]), e o inimigo executou exatamente essa Carta nas 3 rodadas ("cumpre o que o presságio anunciava"). **Não verificado:** presságio **frustrado** (exige atordoar o executor; as Cartas que atordoam são de patamar avançado, fora da seed). O chip da UI traz "82 % · 7–14 de dano · frustra o presságio" na confirmação da jogada. | `out/i2-r*.json`, `out/i2-1440.png`, `out/i12-1440-1.png` |
| 3 (330 §6) | **ok com ressalvas**. Rachadura + golpe: "Junta Emperrada" aplicou a condição "Rachadura" e o golpe de texto "Causa 6" saiu **7 de dano** (+25 %), conferido no registro (`dano 7`). Mas a linha "Goblin ganha a condição Rachadura" vem **depois** do ataque do goblin, e o `mech_log` não explica o 7 (achado 8). **Eco:** "Segundo Ato" jogada depois de um golpe da mesma Postura, em 4 sementes, **errou 3 vezes** (e na 4ª o goblin morreu antes). **Efeito Eco com acerto: não verificado.** A seed original não funciona (achado 2). | `out/i3r-r0.json`, `out/i3e-r0.json` |
| 4 (331 §6.2) | **ok depois de ajuste na seed**. O save da seed falha o objetivo na 1ª rodada (achado 3). Com um aliado transitório "Escoltado" em `combat.scene_allies`: o escoltado atacou e foi alvo, a luta terminou em vitória e o log trouxe `combat.scene_objective_resolved ok=true tipo=proteger`. | `out/i4-r*.json`, `out/server-8756.log` |
| 5 (332 §6) | **ok em parte**. Legião de Ferro: sinal de assinatura "ergue a voz em ordem de formação: o bando se aperta" (`reforco_proprio`), Cartas de assinatura jogadas (Pressão da Matilha, Voz de Sargento, Estandarte Fincado, Mordida do Alfa) e padrão visível (faixa [5,10] e depois [14,28]). Chefe Valerius, 4 rodadas, vitalidade 16 → 7: o conjunto de jogadas mudou na rodada 3 (Voz de Sargento, Pele de Veterano "+6 Proteção"), com "age de novo". **Não há linha explícita de "troca de fase"** nem aviso ao jogador, e a mensagem vazou "Ataque sem alvo válido." (achado 9). **Golpe do Penitente em alvo com defesa:** `Proteção −3 · 4 dano` e `Proteção −2 · 5 dano` no `mech_log`. Facção nova (Costurado de Lentes, `mon_costurado_de_lentes`): 4 rodadas jogadas sem erro. | `out/5_*-auto*.json` |
| 6 (333 §6.1/§6.3, R6) | **ok**. Espólio da Mão Sombria pela UI a 1440: 3 ofertas, entre elas "Pó nos Olhos" (`inf_fac_mao_sombria_*`); "Levar Pó nos Olhos" fez `POST /game/espolio`, a Carta foi ao Acervo e o espólio sumiu. **Esquecer:** depois do descanso longo (LLM) `forja.esquecer.descanso = true`; `POST /game/forja esquecer` removeu a Carta e o descanso passou a `false` ("Só dá para esquecer depois de um descanso longo"). Foi preciso ativar o baralho no save (achado 4). **Dor Surda:** na UI o botão "Descartar (1 Fôlego)" apareceu, entrou na fila ("Descartar Dor Surda"), "Encerrar a rodada" a moveu para `exaurida` e o Fôlego fechou a rodada em 2/2. | `out/i6e-*.png`, `out/i6d2-1440-1.png`, `out/i6e-rest.json` |
| 7 (335 §6) | **ok**. 1 conflito de Corruptor (Toque da Decadência e Esporos, com "Transformação (Podridão)") e 1 de Médico de Campo (Bisturi de Campanha, Serra Cirúrgica) contra 2 goblins; os dois acabaram em **morte** (viram o item 10). Há linhas "O ferimento abre espaço no Baralho: Dor Surda / Membro Falho". | `out/7_*-auto*.json` |
| 8 (336 §6) | **achado** (o pipeline recusa). `draft.py` com chave real (DeepSeek SMART, 3 chamadas): Médico/boticário, 4 pedidos: **0 Cartas válidas**, 4 recusadas pelo vocabulário (`alvo 'aliado' fora do catálogo`, `escala.por`). Sangromante/avaro comum: 2 Cartas, **2 reprovadas no lint** (raridade: comum com 2 efeitos; o prompt não segura a orçamento) e 2 recusadas. Sangromante/avaro incomum: 2 Cartas, **2 verdes no lint**, mas a sim marcou **`dominante`** (uso 1,0 e 0,897). `promote` no protocolo `lote` recusou as duas; com `--protocolo lote-v2` (sim com `--protocolo lote-v2`) **promoveu as duas**, com voz pendente e 1 na amostra. Jogada 1 Carta ("Letra de Sangue", custo 0, `Aplica Sangria 4`): "Você joga Letra de Sangue em Goblin… Erra." (rodou na API com o pool promovido). Custo das 3 chamadas: 10 432 tokens de entrada e 2 754 de saída, ~US$ 0,006. O `lint.py --lote` do roteiro está errado (o lote é posicional). | `out/rascunhos/`, `out/llm-tools.jsonl`, `out/sim3681*.json` |
| 9 (345 §6.1, D-368-2) | **ok, local com preset `off`** (D-368-2): API `:8757` com as 5 flags de cartas `off`. Jogo novo, abertura e 4 rodadas até a derrota: `combat.pilhas` **ausente**, sem presságios, sem Cartas de cena; `mech_log` vazio e narração do LLM a cada rodada (~3 s). Observações: nesse modo a prosa chama o herói pelo nome ("…no peito de Hero9") e a derrota veio pela narração. Round-trip `on` → `off` → `on` das Preparadas confirmado no item 1. | `out/i9-last.json`, `out/server-8757.log` |
| 10 (346 §6.5/§6.6/§6.7) | **achado** (ver 1). **Router esgotado:** com `RPG_ROUTES` só Groq e cartas `on`, CLASSIFY (`gpt-oss-20b`) deu **HTTP 400 `tool_use_failed`** no `dm_router` e FAST (`llama-3.3-70b-versatile`) deu **HTTP 404 `model_not_found`**. O jogo **não quebrou**: caiu em `storyteller`, "Ataco o goblin" não abriu combate e a narração foi o texto neutro "O momento passa em silêncio; o mundo aguarda seu próximo passo.". `GROQ_API_KEY=invalida` **não teve efeito**: `llm_setup.py:38` usa `load_dotenv(override=True)`, que sobrepõe a variável (a chave real do `.env` foi usada); o roteiro precisa de outra forma de falhar. **Rodada `off` com LLM esgotado (`:8759`):** 3 rodadas resolveram mecanicamente com texto de fallback ("⚔️ • Hero10o → Goblin 1: acerto (total 14 vs Esquiva 12)…"), que vaza `enemy_goblin_1 não está na cena` (save de baralho aberto em API `off`; achado 12). **Morte real (DeepSeek):** Médico, `outcome=death`, `death_pending=true`, `killer: Goblin`, prosa coerente e "Voltar ao último respiro seguro, ou aceitar o fim aqui?". | `out/server-8758.log`, `out/llm-8758.jsonl`, `out/7_medico-auto3.json` |
| 11 | do coordenador | — |
| 12 (354) | **ok**. Vitória a 1440 pela UI (Goblin com 1 de vitalidade): o cartão "Vitória · Goblin — abatido · +50 XP · +9 ouro · CONTINUAR" ficou **no painel de Combate**; `.outcome-chip` = 0 (sem toast sobre o Livro) e a última linha do Livro ("+9 de ouro") continuou visível. | `out/i12-1440-2.png` |
| 13 (355 §6) | **ok em parte**. Voto Sussurrado: jogado, "provocado: a próxima intenção dele mira você (com chance)"; a mão não tem "Aguentar". **Não verificado:** "muda de alvo / resiste" com Ketil (a seed não tem Ketil). Leitura de Pressão (acerto): o presságio seguinte mostra `carta_nome = "Pancada Esmagadora"` (R9 **ok**). Armadura Comprometida: "Fadiga do Material" acertou, mas o goblin não tem armadura; **não verificado**, e 0 ocorrências de `armadura_comprometida` no payload. Renegado do Ermo: nenhum "Descarga Arcana" no payload (R10 **ok**). Vitória com Reação: **não verificado** (achado 5). | `out/i13-*.json` |
| 14 (357 §6.5) | **não verificado a entrega**. A quest `justa` aparece com `reward_hint: "justa · uma técnica"` (R11 **ok**). Dois turnos reais de conclusão no lugar errado não concluíram (a quest é de Brekmar e o herói estava em Nova Arcádia): o narrador diz que "não há contratante". Falta ir a Brekmar e passar pelo evento `quest_completed`. | `out/i14-*.json` |

### LLM por rodada, provider e custo

- **Chamadas no meio do combate:** **0 por rodada** (5 rodadas seguidas medidas pela contagem de linhas do `llm-8756.jsonl`; `on`). A rodada final custa 1 chamada (FAST, ~9,7 s no maior caso) e o desfecho com SMART do arquivista, 1 a 2.
- **Provider/modelo:** DeepSeek `deepseek-v4-flash` em CLASSIFY, FAST e SMART. Fallback para Groq `gpt-oss-20b` e `gpt-oss-120b` quando o DeepSeek falhou (3 `invoke_error`: 1 CLASSIFY, 6,5 s; 2 FAST, ~24 s no total).
- **Tokens (DeepSeek):** `:8756` 73 219 entrada (6 912 em cache) e 9 216 saída; `:8757` 28 749 e 5 144; `draft.py` 10 432 e 2 754. Total ~112 400 de entrada (16 384 em cache) e ~17 100 de saída.
- **Custo aproximado** (tarifa `rate_card_2026-10-08`: US$ 0,30 / 0,006 cache / 1,20 por milhão): **~US$ 0,05** (~R$ 0,27). Groq no free tier (custo 0). Nenhuma imagem paga.

## Achados

1. **P2: o fallback Groq está quebrado em 2 dos 3 tiers.** `openai/gpt-oss-20b` (CLASSIFY) devolve HTTP 400 `tool_use_failed` no `dm_router`, e `llama-3.3-70b-versatile` (FAST) devolve 404 `model_not_found` com a chave atual. Só o SMART (`gpt-oss-120b`) respondeu. Com o DeepSeek fora, o jogo continua (cai em `storyteller` com texto neutro) mas não abre combate nem narra. Além disso, o roteiro do item 10 (`GROQ_API_KEY=invalida`) não funciona por causa do `load_dotenv(override=True)`. Atualizar `ROUTES`/`AGENTS.md` ou o roteiro.
2. **P2: `seed_save` 3 (Rachadura e Eco) coloca na mão Cartas que o herói não tem preparadas/no baralho.** Jogar "Junta Emperrada" ou "Segundo Ato" devolve `result: ok` sem linha no registro, sem efeito e consome a Carta (descarte). Com a Carta em `prepared_cards` + `deck` + `known_cards` a jogada funciona. O motor também engole a jogada em silêncio (P3): vale uma recusa explicada.
3. **P2: `seed_save` 4 não produz escolta.** O objetivo `proteger` aponta para um id que não existe como ator; o objetivo falha na 1ª rodada e o combate vira `defeat` com o herói em 8/18. A narração do LLM então descreve o herói caindo ("o mundo se apaga antes que você sinta o impacto"), que **não corresponde à causa** (objetivo falhou, vitalidade 8/18). Só funciona com o aliado em `combat.scene_allies`.
4. **P3: `seed_save` 6 `espolio` não tem baralho** (`player.deck` vazio): a Forja e o Esquecer não aparecem até `activate_deck`.
5. **P3: `seed_save` 13 `reacao`:** o goblin com 1 de vitalidade prevê `fugir` em 8 de 8 sementes; nunca ataca, então a Reação "Encaixe do Golpe" não dispara e a "vitória com Reação" não acontece. `13` padrão não tem Ketil e `13 armadura` usa goblin sem armadura.
6. **P2: `draft.py` com chave real rende pouco ou nada.** Médico/boticário: 0 de 4 pedidos válidos. Sangromante comum: 2 Cartas, ambas reprovadas no lint por orçamento. A saída pede `--n 4` e devolve 2 Cartas. O gate funcionou (nada ruim foi promovido no protocolo `lote`), mas o rendimento do prompt é baixo. Corrigir o roteiro (`lint.py` é posicional).
7. **P3: texto tautológico** "Presságio cumprido: cumpre o presságio" em "Efeitos da rodada" (390 e 1440).
8. **P3: Rachadura.** O golpe de texto 6 saiu 7 e o `mech_log` não anota o bônus. A linha "ganha a condição Rachadura" vem depois do ataque do inimigo.
9. **P3: vazamento de mensagem interna** em rodadas do chefe Valerius: "Lorde Protetor Valerius age de novo. Ataque sem alvo válido." (rodadas 3 e 4). A troca de fase também não tem linha para o jogador.
10. **P3: rótulo bruto "MAO_SOMBRIA"** como tag de facção na Carta do Acervo (UI a 1440).
11. **P3 (observação): a 390, a barra fixa** (Sem matar / Fugir / Encerrar a rodada) cobre a linha do presságio na posição de rolagem padrão; o chip aparece ao rolar. Print: `out/i367p-390-1.png`.
12. **P3: no modo `off`** o texto de fallback com o LLM esgotado vaza `enemy_goblin_1 não está na cena` e ": Defesa Instintiva terminou" (só vi isso com um save de baralho aberto numa API `off`, que não é o uso normal). A prosa do `off` com LLM chama o herói pelo nome.
13. **P3: a mensagem de recusa do Pacto** diz "(0/1)" quando o Fôlego é 2, e o lote inteiro foi recusado (5 cartas para 4 de capacidade). Confuso, não errado.
14. **Observação:** o embedding da Jina deu 429 durante a criação de jogo (retry e continua); já conhecido pelo ESTADO.

## O que ficou não verificado

- Item 2: presságio frustrado.
- Item 3: efeito Eco com acerto.
- Item 5: aviso de troca de fase do chefe (a troca ocorreu; sem texto).
- Item 13: Voto contra presságio mirando Ketil; Armadura Comprometida; vitória com Reação.
- Item 14: entrega da técnica na conclusão.
- Itens 1, 3, 4, 5, 7 e 13 foram conferidos pela API (`/game/state`, `/game/action`, `/game/history`); só 2, 6, 12 e o chip do presságio foram abertos na UI.
- Item 11: com o coordenador.
