# Jev no router: o que deu errado na primeira tentativa e o que funciona agora

Para: dono do projeto. Data: 2026-10-18.

> **Aviso importante.** O teste confirmatório (**J2**) **ainda NÃO rodou**. Quando este documento diz "deu certo", refere-se apenas à fase de desenvolvimento (**DEV / J1**), em casos que já foram vistos durante o ajuste. Isso é um bom sinal, não uma prova. A prova é a J2.

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
| **Loot cai para o CLASSIFY** | 13 dos 52 casos (25%). Uma nova spec está tratando disso |
| 2 abstenções | O Jev se declarou inseguro; correto, mas reduz cobertura |
| 2 alvos não representáveis | Mais de 20 opções ou ator sem ID canônico; vão ao CLASSIFY |
| DEV não discrimina bem | Nenhuma variante errou nos cobertos, então não distingue `plain` de `rich` |
| Latência híbrida é estimada | Usa o p50 do CLASSIFY de um teste anterior |
| Custo real | Segue indisponível; só reserva interna |

## 7. O que vem agora

1. **Revisão independente (Astra)** do congelamento da J1.
2. **J2, A/B confirmatório** no corpus FROZEN, rodado **uma única vez**, 3 réplicas, 100 chamadas no máximo. Só dá GO se **todos** os itens valerem:
   - acerto de rota no máximo 2,5 pontos abaixo do CLASSIFY e no máximo 1 perda pareada;
   - alvo ao menos igual, sempre entre os candidatos da cena;
   - zero escalada insegura (combate sem o oráculo pedir);
   - ganho de latência de pelo menos 500 ms no p50 e p95 no máximo 10% pior;
   - gates Python idênticos e com zero chamadas;
   - zero erro de provedor.
3. **Shadow em staging** (o Jev observa sem decidir), por pelo menos 50 turnos reais, só se a J2 der GO e com teto próprio autorizado por você.
4. **`primary` em produção** só com sua aprovação separada. Até lá o Jev segue **desligado por padrão** e nada no jogo mudou.

## Fontes

- `specs/SPEC-177..180` e `docs/spec177/`, `docs/spec178/`, `docs/spec179/`, `docs/spec180/` (README de cada)
- `handoffs/SPEC-178-SOL-result-review.md`, `handoffs/SPEC-179-SOL-result-review.md`, `handoffs/SPEC-180-SOL-independent-review.md`
- Branch `spec-217`: `specs/SPEC-217-jev-reavaliacao-condicional.md`, `docs/spec217/README.md`, `docs/spec217/j1-diagnostico.md`, `docs/spec217/j1-variantes.md`, `docs/spec217/corpus.md`
- Latência do router (1.473 ms, ~13% do turno): `docs/spec214/gate-real-2026-10-17.md`
