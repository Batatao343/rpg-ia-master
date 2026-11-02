# Smoke 4: SPEC-363 §6, correções do smoke 3

Feito em 02/11/2026, das 08:00 às 08:13 UTC, na `main` `cc31a6c1`.

**Staging.** `hosted-supabase`, SHA cc31a6c1, cartas `on`. Antes da geração, o `art_preflight` deu `switch_image: true` e `pricing_fresh: true` (o `ok: false` vem só de `dynamic_art_env_off`, que lê o arquivo). Usei 2 contas sintéticas, A (`Smoke4A`) e B, pelo caminho de `two_user_smoke`, com crédito sintético `credit_verified_purchase`. A limpeza deu `games_deleted: 2` e `users_exist_after: [false, false]`. No fim, o `image_generation` foi desligado com `admin_kill_switch … --apply`; o preflight depois disso: `switch_image: false`, `causa: manual_off`.

**Local.** Perfil `legacy` em `:8754`, rodando de uma cópia `git archive` de cc31a6c1, com o preset de flags do staging e `RPG_CREATURE_ART=on`. LLM DeepSeek `deepseek-v4-flash`, nenhuma tentativa falhou. Personagens: Haldor4 (Devoto, Skallgard) e Mirela4 (Sangromante, Montanhas Afiadas).

**Turnos de jogo: 15.** Staging: 2 aberturas + 5 rodadas. Local: 3 na loja + 1 abertura + 2 rodadas + 2 fugas.

Evidência, tudo em `scratchpad/smoke4/`:
- `stg/stg_log.jsonl`: log por passo do staging, com `usage_events` por turno, cotação, débito e saldo.
- `stg/stg_hist_A.json`: histórico da conta A no staging.
- `out/stg-*.png`: prints do staging.
- `out/state-*.json` e `out/hist-*.json`: estados e histórico do local.
- `server.log` e `turns.cjs`: log e agregado das chamadas LLM do local.

## Tabela §6 / pedidos do coordenador

| Item | Resultado | Evidência |
|---|---|---|
| §6.1 Preflight | Staging pronto: `switch_image` e `pricing_fresh` true. O `ok: false` é só do arquivo, como você previu | saída do preflight |
| §6.1 Chip com "Gerar retrato" a 390 e a 1440, com e sem Carta armada | **PASSOU**: "GERAR RETRATO (1 ESTILHAS)" nos 2 chips, nas 4 combinações | `stg_log` `phase_done offer`; `out/stg-offer-{1440,390}-a.png`, `-b-mira.png` |
| §6.1 Cotação sem 503 → confirmar → geração | **PASSOU**, 2 gerações (Goblin e Minotauro Esqueleto). Cotação 200 com `type: monster` e 15 milli; confirmação 200 `pending`, com 15 milli reservados; estado `pronto` em 99 s e 66 s | `stg_log` `quote`, `confirm`, `portrait_ready` |
| §6.1 Débito único por chave | **PASSOU**. 1 débito por geração. Cotar a mesma chave de novo → `409 creature_portrait_exists`, saldo intacto. A reserva liberou: 0 milli reservados no fim | `requote_same_key` |
| §6.1 Débito igual à cotação | **Diferente**: debitou 8 milli contra 15 cotados nas 2 gerações. Fica ≤ teto, como pede a 352; ver P3-1 | `portrait_ready` (`debit_milli: 8`, `quoted_milli: 15`) |
| §6.1 Retrato no tabuleiro | **PASSOU**: os chips mostram `<img>` assinada de `rpg-shared-art`, estado `pronto`, a 1440 e a 390, sem o botão de oferta | `phase_done ready`; `out/stg-ready-*.png` |
| Reuso: 2º jogo, mesmo tipo, outra conta, sem cobrar | **PASSOU**. Conta B: Goblin e Minotauro `pronto`, `gerar: null`, saldo 1244 → 1244 | `B_open` |
| §6.2 Morte no staging com nome contendo dígito | **NÃO VERIFICADO**: a conta A venceu na rodada 5, com 0 de Vitalidade. Mesmo assim, "Smoke4A" saiu íntegro em todo o Livro (P3-3). O resumo da vitória está correto: ferimentos atribuídos "na perna do Minotauro Esqueleto" e "no seu braço", e só "você" | `A_end`, `out/stg-end-*.png` |
| `last_outcome_source` / quedas no fallback | Vitória no staging: `llm`. **0 fallbacks** no desfecho observado. A morte não aconteceu nem no local nem no staging | `A_end.outcome_source` |
| §6.3 Vitória com ferimento no inimigo: sem troca de autoria | **PASSOU** no staging. O texto diz "abrindo um ferimento crítico na perna e outro grave no braço da criatura"; o ferimento do herói é atribuído à Última Ação do inimigo. Ressalva de tempo verbal: P3-2 | `A_end.message` |
| §6.4 Carta básica não mira o escondido | **PASSOU no servidor**. Com o Goblin `escondido` (staging, após A-r1), as Cartas básicas da mão traziam `valid_targets` só com o Minotauro (R19). Na UI local o caso de esconderijo não se repetiu; os 2 alvos estavam visíveis e os dois eram oferecidos, o que está correto. A UI com inimigo escondido ficou **NÃO VERIFICADA** | `stg_log` A-r1 `after.hand[].vt`; `out/state-Mirela4-r2.json` |
| §6.4 409 tira só a jogada | **NÃO VERIFICADO**: nenhum 409 aconteceu | n/a |
| §6.4 Fuga: veredito igual no `mech_log`, na tela e no Livro | **PASSOU no veredito**. Fuga 1: "alcançado" / "Não escapou" / "os inimigos te alcançam". Fuga 2: "avança" / "Não escapou…" / "avança na fuga". A trilha diverge: P2-1 | `out/state-Mirela4-f1.json`, `out/state-Mirela4-f2.json`, `out/7135206-Mirela4-f2-1440-2-pos.png` |
| §6.5 "Quero comprar a Lança de Gancho da Forja dos Clãs" | **PASSOU** (R28): −50 de ouro, Carta conhecida, "+1 Carta: Lança de Gancho \| Ouro −50 (total 0)". Turno de 5,9 s (R34) | `out/state-Haldor4-t1.json` |
| §6.5 Consulta do mercado sem id (R25) | **PASSOU** com "Quanto custa o Traje Branco?": nenhum `item_desconhecido`. Mas "O que a Forja dos Clãs tem à venda?" virou venda (P2-2), e os nomes saem longos (P3-4) | `out/state-Haldor4-t3.json`, `out/state-Haldor4-t2.json` |
| §6.6 Ids no `/game/history` (R27) | **PASSOU**: 0 ids (`snake_case`, `[SISTEMA]`, `[RESULTADO]`) no histórico. Staging A: 13 entradas; Haldor4: 7; Mirela4: 11. Só o `mech_log` tem `alcancado` (P2-1) | `stg/stg_hist_A.json`, `out/hist-*.json` |
| §6.6 Latência de uma viagem (R35) | **NÃO VERIFICADO**: o teto de 15 turnos acabou | n/a |
| 0 LLM por rodada no meio da luta | **PASSOU**. Staging: rodadas 1 a 4 com 0 `usage_events`, 0,7 a 1,2 s cada. Local: 4 rodadas e fugas com 0 chamadas, p50 de 144 ms | `stg_log` (`usage: {}`), `turns.cjs` |
| Carta de objeto de cena (extra) | Resolve sem "não está preparada". No staging, "Estilhaçar (Veio de Éter Bruto)" mirou um Goblin que caiu antes e o texto disse "já está fora do conflito" | `stg_log` A-r3 |

## Achados

**P2-1. A trilha da fuga diverge entre o `mech_log` e o Livro, e o id cru aparece no `mech_log`.**
- O que aparece na fuga 2: o `mech_log` diz "Fuga · total 18 vs 12 · avança (alcancado → afastado)" e o Livro diz "Você avança na fuga: pressionado → afastado".
- O estado anterior está em conflito entre as duas vistas, e o `mech_log` traz `alcancado`, um id sem acento.
- Provável origem: a linha de fuga do R22 (`services/combat_preview.py`) lê `chase.track` antes do reset de `alcancado` → `pressionado`, que `agents/combat.py` faz por volta da linha 3314. É preciso usar o mesmo `previous_track` e o rótulo legível.
- Reprodução: Mirela4 (local), 2 fugas seguidas; a 1ª termina "alcançado".

**P2-2. Pergunta de catálogo virou venda.**
- "O que a Forja dos Clãs tem à venda?" respondeu "Você não tem 'Forja dos Clãs' para vender."
- O CLASSIFY do loot leu "venda" como intenção de vender. Provável origem: `_parse_trade_intent` em `agents/loot.py`.
- Sugestão: "à venda"/"tem para vender"/"vende" sem item do inventário deveria virar `observe`.
- Evidência: `out/state-Haldor4-t2.json`.

**P3-1. Débito real abaixo da cotação.** As 2 gerações cotaram 15 milli e debitaram 8 milli cada. Cumpre "≤ teto" da SPEC-352, mas o §6.1 da 363 pede "débito igual à cotação". Vale ajustar o texto do critério ou confirmar que o débito é pelo custo real. Também: o chip anuncia "1 Estilhas" (arredondado para cima de 0,015), e o plural fica errado com 1.

**P3-2. O resumo da vitória conta uma queda antiga no presente.**
- O texto do staging diz "o Goblin também tomba sem vida ao seu lado", mas o Goblin morreu na rodada 3 e a vitória veio na 5.
- O R8 da SPEC-363 pede quedas antigas no passado; neste resumo, gerado pelo LLM, ainda não estão.

**P3-3. O registro usa o nome em vez de "Você".**
- Linhas como "Smoke4A sente o Abismo mais perto (+1 Carga)." e "Mirela4: ganha condição cego" aparecem com o nome do herói. O nome com dígito sai íntegro.
- Continuam também as linhas de condição duplicadas: "Goblin ganha a condição Cego." seguida de "Goblin: ganha condição cego", que vem do bloco da carta de cena (P3-2 do smoke 3).

**P3-4. Nomes longos no mercado.** A consulta lista itens com a descrição inteira como nome, por exemplo "Faca de esfolar de osso de baleia, cabo envolto em couro cru — a lâmina que Haldor usa…" a 30 moedas e estoque 0. Os itens de estoque 0 do próprio herói entram na lista do mercador.

**P3-5. Narração genérica na compra.** O texto diz "O mercador de Valoria embolsa…" em vez do nome da Forja dos Clãs.

## LLM, latência e custo

| Onde | Fase | Chamadas LLM | Tempo |
|---|---|---|---|
| Staging | Abertura | 5 por conta | 15,9 s |
| Staging | Rodadas 1 a 4 | 0 | 0,7–1,2 s |
| Staging | Desfecho | 2 (resumo + arquivista) | 9,5 s |
| Local | Loja (3 turnos) | 8 | p50 4,9 s, máx. 5,9 s |
| Local | Abertura | 3 | 6,7 s |
| Local | Meio de luta e fugas | 0 | p50 144 ms |

Custo dos turnos no local: ~US$ 0,004; com 2 criações, ~US$ 0,01. Staging: ~US$ 0,01 de texto mais 2 imagens (8 milli de Estilhas debitados cada; custo do provedor não medido). O débito total da conta A foi 16 milli.

## Processos

O uvicorn local (PIDs 11236 e 24824) foi encerrado e a porta 8754 ficou livre. Os scripts node e o Chromium fecharam sozinhos. Os cookies do staging foram apagados. A cópia `%TEMP%\claude\rpg-smoke4` pode ser removida. No repositório não editei nada; `uv run` reinstalou 1 pacote no `.venv` por causa do bump do pyasn1.
