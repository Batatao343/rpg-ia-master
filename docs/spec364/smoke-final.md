# Smoke final: SPEC-364 §6 (LLM real)

Feito em 02/11/2026, das 16:33 às 16:53 UTC.

**Local.** Perfil `legacy` em `:8755`, rodando de uma cópia `git archive` de `90cfaa18`, com `web/dist` gerado dessa cópia. Usei o preset de `scripts/staging/staging_flags.json` (cartas `on`) e `RPG_CREATURE_ART=on`. A `main` já estava em `1644ce60` (SPEC-366), sem mudança em `web/` desde `90cfaa18`. Provider: DeepSeek `deepseek-v4-flash`. Houve 2 timeouts de 6,5 s no CLASSIFY do `dm_router`, e nos dois o Groq `openai/gpt-oss-20b` assumiu. Personagens: Haldor5 (Devoto do Abismo, Skallgard) na loja e Mirela5 (Sangromante, Montanhas Afiadas) no combate.

**Staging.** `hosted-supabase`, `/health` com `git_sha` `90cfaa18`. A conta sintética veio do caminho de `two_user_smoke` (`User` + `credit_verified_purchase` sintético). Foram 2 execuções, cada uma com 1 conta:
- Na 1ª (Montanhas Afiadas), Goblin e Minotauro Esqueleto já tinham retrato `pronto` no pool compartilhado (criado no smoke 4). Por isso não houve oferta e nada foi gerado.
- Na 2ª (Skallgard) houve a geração paga, uma só.

As duas limparam no fim: `games_deleted: 1` e `users_exist_after: [false]` em cada.

**Turnos de jogo: 10 no local** (4 na loja, 1 abertura, 5 rodadas de fuga) e **2 no staging** (2 aberturas, uma por execução).

Evidência, tudo em `scratchpad/smoke5/` da sessão do coordenador:
- `out/state-*.json`, `out/hist-*.json` e `out/*.png`: estados, histórico e prints do local.
- `server.log`, `turns.cjs` e `llmcount.cjs`: log e chamadas LLM do local.
- `stg/stg_log.jsonl` e `stg/run1/stg_log.jsonl`: log por passo do staging, com balanço, reserva e `usage_events`.
- `stg/done-*.txt`: textos do chip e da confirmação a 390 e a 1440.
- `stg/stg_hist_A.json` e `out/stg-*.png`: histórico e prints do staging.
- `stg/ks_*.txt` e `stg/preflight_*.txt`: kill switch e preflight.

## Tabela R → resultado

| R | Resultado | Evidência |
|---|---|---|
| R1/R2 (fuga, mesma trilha) | **ok** nos casos que ocorreram: avança, perde terreno, chega a "quase livre" e escapa. O `de` de cada fuga é o `para` da anterior, e `mech_log`, registro/mensagem e `/game/history` dizem o mesmo. **Não ocorreram**: "alcançado", 1ª fuga a partir de `distante` e sacrifício (`force_escape`) | f1 `pressionado → afastado`; f2 `afastado → pressionado` (perde terreno); f3 `pressionado → afastado`; f4 `afastado → quase livre`; f5 "Você escapou." (`outcome: fled`). Arquivos: `out/state-Mirela5-f1..f5.json`, `out/hist-Mirela5.json` (entradas 4, 6, 8, 10) |
| R3 (nenhum id da trilha na tela) | **ok**. "quase livre" sai com espaço em `mech_log`, mensagem e Livro. `alcancado`/`quase_livre` aparecem só em campos internos (`chase.track`/`steps`, `death.last_action.chase_track`), nunca em texto exibido | varredura de `state-Mirela5-f*.json` e `hist-*.json` |
| R4 (catálogo vira consulta, sem CLASSIFY do loot) | **ok**. "O que a Forja dos Clãs tem à venda?" deu "Mercado de Forja dos Clãs (consulta sem transação)", sem "para vender" e sem "Você não tem". **0 chamadas `loot`/CLASSIFY** nos 4 turnos de loja. Cada turno teve só o CLASSIFY do `dm_router`, que é o roteamento do turno | `out/state-Haldor5-t1.json`; `llmcount.cjs` |
| R6 (pergunta nunca transaciona) | **ok** quanto a transação: ouro 50 → 50 e inventário igual nas 2 perguntas. Cotação do item: **ok** com "Posso vender a Poção de Cura Menor?" → "Poção de Cura Menor: o mercador paga 55 moedas. Diga claramente que vende para confirmar; nada mudou." Com nome parcial de item livre ("Posso vender a Faca de pedra-sabão?") veio a consulta inteira em vez da cotação: achado A1 | `out/state-Haldor5-t2.json`, `out/state-Haldor5-t2b.json` |
| R7 (duas seções) | **ok**. "À venda:" lista só estoque > 0, mais as Técnicas. "Pelo que você carrega:" mostra "paga N moedas", sem estoque e sem preço de compra. Nenhum item do herói com "estoque 0" | `out/state-Haldor5-t1.json` |
| R8 (nome curto) | **ok**. Exemplo: "Cajado de osso de baleia entalhado com…" e "Manto de pele de foca-negra costurado…", onde o nome inteiro tem mais de 80 caracteres | idem |
| R9 (narração nomeia o mercador) | **ok**. "Quero comprar a Traje Branco da Forja dos Clãs" → "…ao mercador da Forja dos Clãs, em Skallgard, e ele lhe passa a Carta Traje Branco…" e "+1 Carta: Traje Branco \| Ouro −45 (total 5)". Carta `neu1_er_traje_branco` conhecida | `out/state-Haldor5-t3.json` |
| R10–R12 (resumo da vitória no passado) | **não verificado**: a luta terminou em fuga, não em vitória. O resumo da fuga é coerente: "O Goblin-Mineiro e o Minotauro Esqueleto ficam para trás, ilesos", e eles de fato não sofreram dano. `last_outcome_source = "llm"`, lido do save | `saves/45d4730f….json` da cópia local |
| R14–R16 (voz do registro) | **ok** nas superfícies do R16. A Carta de Cena de condição (Névoa Cinza do Ermo) saiu "Você ganha a condição Cego."; nenhuma linha de registro/mensagem/`mech_log`/Livro começa com "Mirela5" ou contém "Mirela5:"; nenhuma condição duplicada (1 linha "X ganha a condição Cego." por participante e rodada). Carta de Cena de **Carga**: não ocorreu. Fora das superfícies do R16, o nome do herói aparece no presságio (achado A3) | `out/state-Mirela5-f1..f4.json` |
| R17 (débito = custo liquidado ≤ cotação; reserva volta a 0) | **ok**. Números abaixo | `stg/stg_log.jsonl` (`portrait_ready.reservations`) |
| R18 (preço exato com "até") | **ok** a 390 e a 1440. A oferta trouxe `gerar: {preco_estilhas: 1, preco_milli: "15", escopo: "tipo"}`. Chip: "Gerar retrato (até 0,015 Estilhas)". Confirmação inline: "Gerar o retrato de Criatura hostil por até 0,015 Estilhas? A imagem fica no bestiário…" | `stg/done-offer.txt`; `out/stg-offer-{390,1440}-{a,b-pergunta}.png` |
| R19 (plural) | **ok**: "0,015 Estilhas" | idem |
| R20 (atalho em milli) | **ok**. Com cotação 15 ≤ `preco_milli` 15, o clique em "Gerar" foi direto: `/art/quote` 200 e `/art/confirm` 200 `pending`, sem o diálogo da 326 | `stg/done-offer.txt` (`1440-art`) |
| R24/R25 (0 LLM por rodada; menos LLM na loja) | **ok**. Local: 4 rodadas no meio da luta com **0** chamadas, latência p50 122 ms (máx. 203). Na loja, 0 CLASSIFY do loot | `turns.cjs` |
| R29 (ids e nome do herói no `/game/history`) | **ok**. Haldor5 (9 entradas), Mirela5 (13) e staging Smoke5A (3): **0** ids `snake_case`, 0 `[SISTEMA]`/`[RESULTADO]`, 0 `alcancado`/`quase_livre` e 0 menções ao nome do herói no texto. Ignorei campos de metadados como `speaker_id` e `technical_cost_basis` | `scan.cjs` sobre `out/hist-*.json` e `stg/stg_hist_A.json` |

## R17: números do retrato pago (staging, 1 geração)

| Momento | Disponível (milli) | Reservado (milli) |
|---|---|---|
| Antes da cotação | 622 | 0 |
| Depois de confirmar, gerando (amostras de 41 a 63 s) | 607 | 15 |
| `pronto` (107 s após a fase de oferta) | 614 | 0 |

- Cotação: `credits_milli: 15`, `pricing_version: spec197-restore-b`, `type: monster`.
- Linha de `app.wallet_reservations`: `ceiling_milli 15`, `settled_milli 8`, `released_milli 7`, `status settled`, `financial_anomaly_milli 0`.
- **Débito = 8 milli (custo liquidado) ≤ 15 (cotação). Reservado no fim = 0.**
- Cotar de novo a mesma chave depois de `pronto` deu `409 creature_portrait_exists`, com o saldo intacto (614/0).
- Retrato `pronto` a 390 e a 1440, com `<img>` assinada do Supabase Storage e sem botão de oferta (`out/stg-ready-*.png`).

## Kill switch e preflight

- Antes: `list` → `image_generation: false`. Preflight: `switch_image: false`, `causa: manual_off`.
- Ligado com `on image_generation --actor coordenador-claude --reason "smoke 364" --apply`. Preflight: `switch_image: true`, `pricing_fresh: true`; `ok: false` só por `causa: dynamic_art_env_off`, o caso que o §6.3 exclui. `creature_art_env` também aparece `false`, porque o preflight lê o arquivo.
- **No fim:** `off image_generation … --reason "smoke 364 fim" --apply` → `enabled: false`. `list` → **`image_generation: false`**. Preflight: `switch_image: false`, `causa: manual_off`.

## LLM, latência e custo

| Onde | Fase | Chamadas LLM | Tempo | Custo (US$) |
|---|---|---|---|---|
| Local | Loja (4 turnos) | 6: 4 `dm_router`, 1 fallback Groq, 1 narração do loot | p50 3,2 s, máx. 8,5 s (com timeout) | 0,0013 |
| Local | Abertura do combate | 7, incluindo 1 timeout com fallback | 18,3 s | 0,0029 |
| Local | Rodadas 1 a 4 (fugas) | **0** | p50 122 ms | 0 |
| Local | Fuga final, com resumo e arquivista | 2 | 5,3 s | 0,0018 |
| Local | 2 criações (prólogo + `/game/new`) | 10 | 8 a 34 s | não medido por turno |
| Staging | 2 aberturas | `usage_events` `llm:turn` 5 e 3 | 13,9 s e 9,7 s | |

Os turnos do local somaram ~US$ 0,006; com as criações, ~US$ 0,01. No staging foram ~US$ 0,01 de texto, mais 1 imagem: 8 milli de Estilhas debitados; o custo do provedor não foi medido.

## Achados

**A1. P3 (R6/R8). Nome parcial de item livre não resolve na pergunta.**
- "Posso vender a Faca de pedra-sabão?" devolveu a consulta inteira, não a cotação da faca. Nada transacionou, então a regra central do R6 vale.
- O item tem nome longo ("Faca de pedra-sabão usada em sacrifícios de sangue ao mar"). `_cites_inventory` (`agents/loot.py:150`) só casa o nome inteiro ou o `short_display`, que termina em "…" e por isso nunca casa com o que o jogador digita.
- Com item de catálogo ("Poção de Cura Menor") a cotação sai certa.
- Sugestão: casar também por prefixo de ≥ 2 palavras do `short_display` sem a reticência.

**A2. P3 (R18, UX). O chip não muda depois de confirmar.**
- Depois de "Gerar", o toast diz "Retrato encomendado. O saldo foi reservado.", mas o chip continua "Gerar retrato (até 0,015 Estilhas)" com o marcador, até o próximo refresh do estado.
- O servidor já estava `gerando` e com 15 milli reservados.
- Risco: um 2º clique cota de novo. Não testei a resposta durante a geração; depois de `pronto` ela é `409 creature_portrait_exists`.
- Evidência: `out/stg-offer-1440-c-gerando.png`, `stg/done-offer.txt` (`1440-pos-gerar`).

**A3. P3 (voz, vizinho do R16). O presságio público usa o nome do herói.**
- Exemplos: "Criatura hostil vai saltar sobre Smoke5A." (staging) e "o frio da cova aponta para Mirela5." (local).
- Aparece no chip do inimigo a 390 e a 1440. O presságio não está na lista do R16, mas contraria a regra de voz D-363-3.
- Evidência: `combat.pressagios_publicos[*].sinal`; `out/stg-offer-390-b-pergunta.png`.

**A4. P3 (arte/conteúdo). Retrato pago gerado para um inimigo de fallback.**
- A abertura em Skallgard ("…ataco a criatura hostil mais próxima") criou `fallback_criatura_hostil_1`, "Criatura hostil", família `desconhecida`. A oferta de retrato apareceu e a única geração autorizada foi para a chave `tipo:fallback_criatura_hostil`, que agora está `ready` no pool compartilhado. Todo inimigo de fallback futuro vai reutilizar essa imagem.
- O texto do jogador provavelmente induziu o fallback.
- Sugestão: não oferecer retrato para `fallback_*`. Decisão do coordenador: purgar a entrada (`scripts/staging/spec222_art_purge.py`) ou mantê-la.
- O R17 continua provado: o motor de cobrança é o mesmo.

**A5. P3 (texto). Condição de inimigo que termina sai em formato técnico.**
- Exemplo: "Goblin-Mineiro: cego terminou." (minúscula, "Nome:"), enquanto as outras linhas dizem "ganha a condição Cego." e "Sua condição Cego terminou.".
- Não envolve o herói, então o R16 passa, mas é o mesmo padrão que o R14/R15 normalizou para o herói.
- Evidência: `out/state-Mirela5-f2.json`.

**A6. Observação (narração).** A compra diz "Você entrega as últimas 45 moedas…" e logo depois "Restam-lhe 5 moedas". O LLM chamou de "últimas" moedas que não eram as últimas. Os números do `[SISTEMA]` estão certos.

**A7. Observação (infra).**
- O DeepSeek deu timeout em 2 de 18 tentativas, as duas no CLASSIFY do `dm_router` (6,5 s), e o Groq assumiu nas duas.
- `admin_kill_switch.py` e `art_preflight.py` contra o staging deram `PoolTimeout` intermitente (pool admin de tamanho 1, 5 s). Funcionaram na 2ª tentativa.

**Não verificados neste smoke:**
- "alcançado" seguido de nova fuga (R2a);
- 1ª fuga a partir de `distante` (R2b);
- sacrifício (R2e);
- vitória com queda anterior (R10–R12);
- Carta de Cena de Carga (R14).

Os testes do R24/R29 e do R21 cobrem esses casos.

## Processos e limpeza

- O uvicorn local (PIDs 11488 e 28436) foi encerrado por árvore. A porta 8755 ficou livre, e a 8000 não foi tocada.
- Os scripts node e o Chromium fecharam sozinhos.
- Removi a junção `rpg-smoke5/web/node_modules`. A cópia `%TEMP%\claude\rpg-smoke5` pode ser apagada.
- Staging: os 2 jogos e as 2 contas sintéticas foram apagados, e os cookies foram removidos.
- No repositório, só este arquivo é novo. Não tirei nenhum valor de `.env`/`.env.staging`.
