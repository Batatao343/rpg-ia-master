# Jev no router: o que deu errado na primeira tentativa e o que funciona agora

Para: dono do projeto. Data: 2026-10-18.

> **Atualização (18/10):** o teste confirmatório (**J2**) rodou uma única vez no corpus FROZEN e deu **GO** — ver "Resultado final" abaixo. As seções 5 e 6b continuam sendo resultados de desenvolvimento (DEV).

## 1. O que é o Jev e por que tentamos

O *router* decide, a cada turno, para onde a ação do jogador vai: história, combate, conversa com NPC ou loot. Hoje isso é feito pelo modelo CLASSIFY (DeepSeek).

| Medida | CLASSIFY (hoje) | Jev |
|---|---:|---:|
| Latência típica da decisão | ~1,5 s (p50 1.473 ms) | ~250 ms |
| Peso no turno | ~13% do tempo total (~10,5 s) | — |

O Jev é um serviço de decisão fechada (escolhe entre opções). Se ele acertasse tanto quanto o CLASSIFY, o turno ficaria cerca de 1 s mais rápido.

## 2. A primeira tentativa (SPEC-177 a 180)

| Etapa | O que foi feito | Resultado |
|---|---|---|
| SPEC-177 | Adapter do Jev (código que conversa com o serviço) | Pronto e testado; não usado no jogo |
| SPEC-178 | A/B de rota, 3 réplicas | CLASSIFY **48/48**, Jev **46/48**. Jev ~5x mais rápido (265 ms vs 1.367 ms). Os 2 erros foram o mesmo caso: `FALO COM CORVO` virou combate (confiança 0,27 a 0,30, quase um palpite) |
| SPEC-179 | Alvo e loot | Alvo: CLASSIFY 5/8, Jev 6/8, mas Jev perdeu 2 casos que o CLASSIFY acertava (`alias`, `enemy`). 2 alvos nem puderam ser enviados. Loot 4/4 nos dois |
| SPEC-180 | Decisão de rollout | **NO_GO**. Jev ficou desligado (`off`) |

**Por que o NO_GO** (não foi só "errou 2 vezes"):

1. **Contrato estreito demais.** Só 2 de 16 casos elegíveis (12,5%) cabiam no modo `primary`, que aceitava apenas "história/nada". Conversa e combate, que precisam de alvo, sempre voltavam ao CLASSIFY.
2. **Sem etapa de alvo.** O Jev nunca decidia "com quem" ou "contra quem".
3. **Custo real indisponível.** O provedor não informa custo; só tínhamos uma reserva interna. Não dava para provar economia.
4. **Evidência perdida.** Os arquivos brutos (raw) dos A/B não foram preservados, então não dava para reabrir os erros do Jev.
5. **Regra pré-declarada.** Perder acertos do CLASSIFY sem fallback seguro veta a promoção, mesmo com ganho de velocidade.

## 3. Causas dos erros (diagnóstico J1)

Não era "o Jev é fraco". A forma como perguntávamos atrapalhava:

| # | Problema | Efeito |
|---|---|---|
| D1 | O Jev não recebia a lista de NPCs na cena. "Corvo" também é um bicho; a ação vinha em CAIXA ALTA | Leu como agressão |
| D2 | Não havia abstenção: respostas com confiança 0,27 (quase sorteio entre 5 opções) eram usadas | Palpite virava decisão |
| D3 | Rótulos inconsistentes: instruções diziam `COMBAT/NPC/LOOT/STORY`, as chaves eram `combat_agent/npc_actor/...` | Dois vocabulários para o modelo traduzir |
| D4 | Apelidos de NPC não apareciam nas opções de alvo | Falhou em `alias` |
| D5 | Alvo era perguntado sem a rota e sem os verbos | Falhou em `enemy` |
| D6 | Duas opções de "não sei" (`unknown` e `none`) dividiam a probabilidade | Resposta diluída |

## 4. O que mudou

| Mudança | Para quê |
|---|---|
| Estado estruturado enviado ao Jev: `scene` (NPCs/inimigos em cena com apelidos), `last_speaker`, `verbs` (talk/attack/trade...), ação em minúsculas | O Jev passa a ver a cena |
| Rótulos simples, iguais às chaves reais | Um vocabulário só |
| Rota **e** alvo na mesma requisição, alvo restrito aos candidatos da cena | Torna conversa e combate resolvíveis, sem chamada extra |
| Uma só opção de abstenção; confiança abaixo de τ = 0,50 cai para o CLASSIFY | Palpite não vira decisão |
| Gates em Python vêm primeiro (continuam mandando); `loot` e alvos não representáveis (>20 ou sem ID) vão ao CLASSIFY | Segurança |
| Corpus **DEV** (59 casos, para ajustar) separado do **FROZEN** (21 casos, nunca aberto) | Evita ajustar o teste até ele passar |
| Contador de chamadas durável e backup dos raws | Orçamento controlado e evidência preservada |

Só o formato do estado mudou. O que cruza para o serviço continua sendo o mínimo público, sem segredos, e o payload do rollout de produção não mudou.

## 5. Resultados da J1 (somente DEV, 52 casos elegíveis)

Orçamento: 60 chamadas ao Jev, 0 ao CLASSIFY, zero erro de provedor. Custo real continua indisponível.

| Variante | Acerto de rota | Cobertura (Jev decide sozinho) | Erros nos casos cobertos | Escalada insegura |
|---|---:|---:|---:|---:|
| rótulo antigo, só rota | 51/52 | 5/52 | 0 | 0 |
| plain, só rota | 52/52 | 7/52 | 0 | 0 |
| rich, só rota | 52/52 | 6/52 | 0 | 0 |
| **plain + alvo, τ 0,50 (escolhida e congelada)** | **52/52** | **35/52 (67%)** | **0** | **0** |

Os três casos que o Jev errava agora acertam: `FALO COM CORVO` (rota 1,00, alvo 0,98), `alias` (1,00) e `enemy` (0,62).

Verificação da estrutura exata congelada, em 8 casos críticos de combate: 8/8 corretos, concordando com a triagem, latência p50 247 ms e p95 287 ms.

Estimativa para o turno: o Jev resolve ~67% sozinho, a ~260 ms; no resto, soma o Jev ao CLASSIFY (~1,7 s). Ou seja, **o ganho só existe na parte coberta, e nos fallbacks o turno fica um pouco mais lento**. É estimativa, não medição.

## 6. Limites atuais

| Limite | Detalhe |
|---|---|
| ~~Loot cai para o CLASSIFY~~ | Resolvido no DEV pela SPEC-238 (seção 6b) |
| 2 abstenções | O Jev se declarou inseguro; correto, mas reduz cobertura |
| 2 alvos não representáveis | Mais de 20 opções ou ator sem ID canônico; vão ao CLASSIFY |
| DEV não discrimina bem | Nenhuma variante errou nos cobertos, então não distingue `plain` de `rich` |
| Latência híbrida é estimada | Usa o p50 do CLASSIFY de um teste anterior |
| Custo real | Segue indisponível; só reserva interna |

## 6b. Loot (SPEC-238, J1b — somente DEV)

Você pediu que o Jev cobrisse o loot também. Agora, na **mesma** requisição (sem
chamada extra), o Jev também diz de onde vem o item: **achado** (TREASURE), **loja**
(SHOP) ou **fabricação** (CRAFT). Um guard em Python confere com os verbos (pegar/
vasculhar, comprar/vender, forjar/fabricar) e com o local (mercador ou oficina no
mapa); se não bater, ou se a confiança for baixa, vai para o CLASSIFY.

| Medida (30 casos DEV, 30 chamadas) | Antes (loot → CLASSIFY) | Depois |
|---|---:|---:|
| Casos que o Jev decide sozinho | 15/30 | **28/30** |
| Loot com fonte correta | — | **13/13** |
| Erros (rota, alvo ou fonte) | 0 | **0** |
| Conversa/combate/história: mesma resposta da J1 | — | 17/17 |
| Latência do Jev (p50) | 247 ms | 262 ms |

No DEV inteiro a cobertura projetada sobe de 35/52 (67%) para **48/52 (92%)**.
Orçamento da spec: 90 de 190 chamadas usadas (você aprovou +30). Mesmo aviso: é DEV;
a prova é a J2, que agora também exige que a fonte do loot do Jev bata com a do
CLASSIFY em todo loot que ele decidir.

## 7. O que vem agora

1. **Revisão independente (Astra)** do congelamento da J1 (feita, aprovada) e do novo congelamento com loot (SPEC-238, pendente).
2. **J2, A/B confirmatório** no corpus FROZEN, rodado **uma única vez**, 3 réplicas, 100 chamadas no máximo. Só dá GO se **todos** os itens valerem:
   - acerto de rota no máximo 2,5 pontos abaixo do CLASSIFY e no máximo 1 perda pareada;
   - alvo ao menos igual, sempre entre os candidatos da cena;
   - zero escalada insegura (combate sem o oráculo pedir);
   - ganho de latência de pelo menos 500 ms no p50 e p95 no máximo 10% pior;
   - gates Python idênticos e com zero chamadas;
   - zero erro de provedor.
3. **Shadow em staging** (o Jev observa sem decidir), por pelo menos 50 turnos reais, só se a J2 der GO e com teto próprio autorizado por você.
4. **`primary` em produção** só com sua aprovação separada. Até lá o Jev segue **desligado por padrão** e nada no jogo mudou.

## Resultado final (J2, 18/10)

A/B pareado no corpus FROZEN (16 casos elegíveis × 3 réplicas + 5 gates), rodado **uma vez**, 100 chamadas (50 Jev + 50 CLASSIFY). Regra pré-registrada: **GO** — todos os itens passaram.

| Medida | CLASSIFY (hoje) | Híbrido (Jev + CLASSIFY de reserva) |
|---|---:|---:|
| Acerto de rota | 45/48 | **48/48** (0 perdas, 3 ganhos) |
| Acerto de alvo | 24/24 | 24/24 |
| Combate indevido | 0 | 0 |
| Fonte do loot (contra o oráculo) | 6/9 | **9/9** |
| Latência do router p50 | 1.480 ms | **238 ms** |
| Latência do router p95 | 1.807 ms | 1.655 ms |
| Erros de provedor | 0 | 0 |

O Jev decidiu sozinho 44 de 48 vezes (92%); nas outras 4 (3 pela guarda de combate, 1 por confiança baixa) o CLASSIFY decidiu e acertou. Os 3 ganhos são um mesmo caso de compra que o CLASSIFY mandava para conversa. Orçamento da spec esgotado no limite: 190/190.

**Nada mudou no jogo ainda.** Próximos passos: revisão independente (Astra) deste resultado; depois portar a estrutura para o código de produção **desligada** e congelar a calibração; então um **shadow em staging** (≥ 50 turnos reais, o Jev só observa) com teto que você precisa autorizar. Ligar o Jev de verdade (`primary`) continua exigindo sua aprovação separada.

## Shadow no staging (18/10)

A estrutura vencedora foi para o código de produção **desligada** (`off` é idêntico ao router de antes). A calibração da J2 ficou congelada. Depois ela rodou em **shadow** no staging: o Jev decidia em paralelo, sem mudar nada, enquanto o classificador atual continuava no comando.

| Medida | Resultado |
|---|---|
| Turnos reais | 58 (55 chamaram o Jev; 3 foram decididos por regras em Python) |
| O Jev decidiria sozinho | 54 de 55 (98 %) |
| Concordância com o classificador atual | **52 de 54 (96,3 %)**, critério ≥ 95 % |
| Combate indevido | **0** |
| Latência do Jev no servidor | p50 251 ms, p95 292 ms (o classificador leva ~1,5 s) |
| Atraso no turno | 0 ms |
| Chamadas | 56 de 60 autorizadas |

As 2 discordâncias foram o classificador atual mandando "inspeciono a carroça" e "examino um objeto" para itens. O Jev disse narração, que era o certo. O staging **voltou para desligado**. Ligar o Jev de verdade (`primary`) ainda depende de uma revisão independente do código portado e da sua aprovação. Detalhes: `docs/spec217/shadow-staging-2026-10-18.md` (branch `spec-217`).

## Fontes

- `specs/SPEC-177..180` e `docs/spec177/`, `docs/spec178/`, `docs/spec179/`, `docs/spec180/` (README de cada)
- `handoffs/SPEC-178-SOL-result-review.md`, `handoffs/SPEC-179-SOL-result-review.md`, `handoffs/SPEC-180-SOL-independent-review.md`
- Branch `spec-217`: `specs/SPEC-217-jev-reavaliacao-condicional.md`, `docs/spec217/README.md`, `docs/spec217/j2-result.md`, `docs/spec217/j1-diagnostico.md`, `docs/spec217/j1-variantes.md`, `docs/spec217/corpus.md`
- Latência do router (1.473 ms, ~13% do turno): `docs/spec214/gate-real-2026-10-17.md`
