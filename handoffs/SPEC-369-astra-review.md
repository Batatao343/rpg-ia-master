# SPEC-369 — revisão astra (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1, 2 P2; o resto é P3 informativo)
> **Revisor:** Astra (Opus 5.5, semântica de avaliador; não escreveu o código) · **Data:** 2026-11-04 · **Commit revisado:** `2361ca66` (régua `10935009`)

## Escopo

Fase A (régua, EVAL_AUTHORING) na branch `spec-369`, `main...spec-369` (base `0c41fe07`):
`docs/spec369/{metricas_369.py,bot_pressagio.py,base-0-19.json,BASE.md}`,
`tests/test_spec369_{regua,metas}.py` e o §9 da spec. Conferido contra R1, R2, R6–R11, R13–R20,
D-369-3 e D-369-7. A Fase B e a Fase C ficaram fora (ainda não existem).

Resultado por foco:

1. **R1/R2: ok.** O diff tem só os 6 arquivos da Fase A mais o §9 da spec, que o próprio R1 exige.
   `git diff --exit-code main...HEAD` sai vazio em `scripts/cards/`, `services/`, `docs/spec{285,332,335,341,355,362,368}`,
   `data/`, `tests/spec330_equivalence.py`, `tests/fixtures`, nos 5 testes de artefato, em `web/e2e/contracts` e em `evals/`.
   `tests/test_spec355_arena.py` é só importado, para ler `EXCECOES_TETO`.
2. **R7: o bot segue a regra literal.** `bot_pressagio.py:64-167` cobre os passos 1–6: a visão pública
   por `knowledge_level`, o meio da faixa ou `ct._DANO_BASICO_DEFAULT`, a regra "séria" (25 % da atual ou
   < 50 % da máxima), a troca do ataque mais fraco pela defesa de maior `valor` com Fôlego próprio, a
   mira em quem ataca e morre, e o resto sem mudança. Usar o valor 3 em vez de 4 segue o "confirmar na
   Etapa 0" e está registrado. Escolhas que a spec não define: empate fica com o último ataque, a defesa
   não pode já estar na declaração e passa por `ME._usable`. São razoáveis e não dependem de número.
   O `mirar` usa tipo e alvo do forecast cru, e isso equivale à visão `desconhecida`
   (`enemy_intent.py:280-290`), então não vaza informação.
3. **R9a: a explicação é verdadeira e reproduzível.** Rodei `base --seeds 0-19` de novo, com saída no
   scratchpad. `r9`, `r10`, `equivalencia_368` = false/false e `equivalencia_368_sem_cartas_pos_368` =
   true/true saíram idênticos ao JSON commitado. Os commits citados (`992810fa`, `82ea73dd`) são mesmo
   as reações iniciais da SPEC-371, posteriores ao JSON da 368 (03/11 15:25). O laço próprio do `pressagio`
   reproduz o R10 da 368 nos braços `off` e `on-368` (1.800 lutas, dano e vitória iguais), e o
   `test_base_reproduz_368` confere luta a luta em 2 sementes.
4. **Limiares:** batem com R13, R15, R16, R17, R19 e R20 e com D-369-3/D-369-8. **R14 não bate** (P1-1).
   O xfail é imperativo e só dispara com artefato ausente (`_load`). Com artefato presente, a
   asserção é real, e uma chave faltando estoura em `KeyError`, não vira xfail. Na suíte default ele
   não esconde nada além dos 15 testes de meta.
5. **BASE.md × JSON:** todos os números conferem com `base-0-19.json`, ponto a ponto (7 metas, R8,
   duração, emboscada, famílias, R19). Rodei as funções `r13`…`r20` do teste de meta contra a base, e
   elas reprovam R13, R14, R15, R16 e R20 e aprovam R17 e R19, como o §9 diz.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_spec369_metas.py:68-77` | O R14(d) manda que a **assinatura básica entre na meta (a)** ("o golpe básico é aceito como fallback; a assinatura básica (`bas_cor_mofo`) entra na meta (a)"). O `r14` só conta `categoria == "onda"`, então `bas_cor_mofo` (uso 0,607, categoria `basica`) fica fora. A Fase B poderia passar o R14 com `bas_cor_mofo` > 60 %, e ela não pode editar o teste depois. | Em (a), contar também `categoria == "basica"` que não seja golpe básico (ex.: `not cid.endswith("_golpe")`, ou pelo kind `dano` da Carta `bas_*_golpe`), fora do Sangromante. Acrescentar um caso no teste da régua ou um assert com `bas_cor_mofo` contra a base. Commit de autor de eval, antes do pouso da Fase A. |
| P2-1 | P2 | `docs/spec369/BASE.md:24,41` e spec §9 linha "(2)" | Mesma causa do P1-1: o BASE.md e o §9 dizem que o R14(a) falha "por `arc1_cal_pulso_medido` e `med1_fer_lente_de_protese`". Falta `bas_cor_mofo`, e o dono decide o gate R9c com uma lista incompleta. | Acrescentar `bas_cor_mofo` (0,607) ao R14(a) na tabela das 7 metas, na linha da básica da tabela por categoria (marcada como "assinatura, entra na meta") e no §9. |
| P2-2 | P2 | `docs/spec369/BASE.md:100,111`; `base-0-19.json` `familias.cells["predador_apice|L3"].off.fights = 80` | O R20 e o D-369-7 pedem **200 combates por célula**, e o título do BASE.md diz "200 lutas por célula". `predador_apice` tem só 2 criaturas, então a célula-alvo `predador_apice` L3 tem **80** lutas por modo. O Δ de −12,5 pp tem um erro-padrão de cerca de 7 pp, e é com ele que a célula entra como alvo. O `r20` também não confere o tamanho da amostra. | No BASE.md, registrar a exceção (80 lutas, família com 2 criaturas) e incluí-la no item 4 do pedido ao dono: aceitar com 80, tirar da lista ou medir com mais sementes **só nessa célula**, decidido antes de ver o efeito da Fase B. Não é preciso mexer no código. |
| P3-1 | P3 | `BASE.md:23`; `test_spec369_metas.py:62-64` | O R13 exige "nenhuma Postura < 1,90", e isso inclui o Sangromante (1,792). Todas as Cartas dele estão travadas (R4a), e a alavanca compartilhada é limitada a +2 pp de vitória (R19b). A meta pode ser inalcançável e o pedido ao dono não diz isso. O teste está fiel à spec. | Pôr isso no pedido de aprovação (D-369-3): o Sangromante fica no piso de 1,90 ou é exceção, como no R14. |
| P3-2 | P3 | `BASE.md:24,40,47` | Os 3 `dominante` por Δ (`arc_cal_valvula`, `dev_ombro_porta`, `dev_reflexo_bastiao`) são **reações**, com uso 0,0 pelo bot e Δ por **remoção** (`delta_base: "remocao"`, `taxa_uso_lote` 0). Para a decisão do D-369-4, o dono precisa saber que o `custo_folego` de uma reação disparada sozinha pode não mover esse Δ. | Uma linha no BASE.md, junto à decisão 2(a): tipo `reacao`, uso 0 e Δ por remoção. |
| P3-3 | P3 | `test_spec369_metas.py:43-47` | Com `final-0-19.json` ausente, os testes da Fase B viram xfail e a suíte fica verde. Um pouso da Fase B sem o artefato passaria em silêncio. | A revisão Sol da Fase B (Etapa 8) e o `/spec-land` exigem `test_spec369_metas.py` com **0 xfailed** nos testes R13–R20/R18 (Fase C à parte). Basta anotar no §9; não é preciso mudar código. |
| P3-4 | P3 | `tests/test_spec369_regua.py:200-218` | A causa do R9a (`sem_cartas`) é provada só pelo booleano do artefato. O teste não roda `sem_cartas` e não confere que ele devolve o catálogo e o `A._HEROES` no `finally`. Eu reproduzi o artefato à mão. | Opcional: um teste barato com `with M.sem_cartas(M.CARTAS_POS_368): assert ids fora`, e depois `assert` que voltaram e que `A._HEROES` foi restaurado. |
| P3-5 | P3 | `metricas_369.py:506-510` | `cmd_emboscada` restaura `orch.run_round` para `E._orig_run_round`, não para o valor salvo antes do patch. Hoje é o mesmo objeto. | Opcional: `orig = orch.run_round` antes do patch e restaurar `orig`. |

## Correções aplicadas

(nenhuma ainda; o executor da Fase A corrige P1-1, P2-1 e P2-2 num commit de autor de eval e substitui o `<sha-A>` no §9)

## Pendências

- P3-1, P3-2 e P2-2 vão para o pedido do gate R9c, com o dono (coordenador repassa).
- P3-3 entra no checklist da revisão Sol da Fase B (Etapa 8).
- P3-4 e P3-5 são opcionais, a critério do executor da Fase A.

## Comandos rodados

```text
git diff main...HEAD --stat → 7 arquivos (6 da Fase A + §9 da spec)
git diff --exit-code main...HEAD -- <caminhos R2 + data/ services/ evals/> → vazio (R2_CLEAN)
py.sh -m pytest tests/test_spec369_regua.py tests/test_spec369_metas.py -q -n 0 → 11 passed, 15 xfailed
py.sh docs/spec369/metricas_369.py base --seeds 0-19 --out <scratchpad>/rebase.json → r9/r10/equivalências idênticos ao commitado (157 s)
py.sh -c "r13..r20 do teste de meta contra base-0-19.json" → falham R13, R14, R15, R16, R20; passam R17, R19
py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome repetido
ruff check docs/spec369 tests/test_spec369_*.py → All checks passed
```
