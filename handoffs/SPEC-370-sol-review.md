# SPEC-370 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-370-sol-review.md`.
> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (`claude-opus-5-5`, `spec-reviewer`, papel Sol técnico) · **Data:** 2026-11-04 · **Commit revisado:** `f2c1751e`

## Escopo

Só o código de `git diff main...spec-370`, ou seja, o motor da Etapa 2 (`e49bd686`, que era `9be539bc` antes do
rebase) e as etapas finais (`f2c1751e`). Arquivos: `services/fauna.py` (`region_cap`,
`_make_room`, `_cap_presences(protect=)`, `anuncia_presenca_nova`, `suprimidos_por` em
`eco_multiplier`), `world_utils.py` (migrante × neutro, `_fauna_encounter`), `services/fauna_lint.py`
(E9 por bloco, E17, E18), `scripts/fauna/build.py` (`suprime`/`suprimidos_por`),
`data/world/fauna_config.json` e os testes `tests/test_spec370_{caps,carcaca,latencia,migrante,solo,suprime}.py`.
Também entram as mudanças em `tests/test_spec360_{flags_off,eco,sinais}.py`. O conteúdo das 12
regiões ficou fora (`SPEC-370-independent-review.md`), assim como o avaliador (`ac2004ec`, de outro autor).

## O que confere

- **Integridade de eval.** `git diff ac2004ec..HEAD -- scripts/fauna/eval.py tests/test_spec360_eval.py
  tests/test_spec370_eval.py evals/` vazio. `test_spec360_flags_off.py`, `test_spec360_eco.py` e
  `test_spec360_sinais.py` não são protegidos.
- **Flag `off` byte-idêntica.**
  - `day_hook` sai cedo sem `RPG_FAUNA_SINAIS=on`.
  - O migrante só escala com `fauna_on` (`world_utils.py:1167`).
  - `_fauna_encounter` só roda com sinais `on`.
  - `build.py` só emite `suprime`/`suprimidos_por` quando a criatura tem, por isso o `fauna.json`
    de NA mudou em 4 linhas.
  - O golden `spec360_flags_off_golden.json` (Skallgard) segue verde.
- **R9.** `region_cap` (`fauna.py:171`) é `min(4, nós raiz × 1)`. Dá NA 4, Ophidia 1 e Skallgard 3,
  e região sem nó raiz volta ao teto fixo.
- **R10.** `_make_room` (`fauna.py:187`) roda **antes** de criar a presença. Primeiro sai a não ativa
  mais antiga, depois a ativa mais antiga de outra região. Presença lida da região atual nunca sai.
  Sem vaga, não nasce nem loga (`test_cap_global_sem_log_fantasma`).
- **R11.** `suprime` só libera a presa (`PRESA_LIBERADA`), sem fome inversa. O E17 cobre existência,
  a própria criatura, ciclo de 2, região/adjacente e `presas ∩ suprime`, e o E15 conta `suprime`.
- **R12.** Migrante × `neutral` com a flag `on`, testado. **R13:** carcaça pelo `_combat_node`, testada
  com `on` e com `off`/`shadow`.
- **Ophidia (decisão do dono).** `anuncia_presenca_nova` só vale para região de 1 nó raiz; com
  `ANUNCIA_PRESENCA_NOVA=false`, as outras regiões seguem iguais (`test_outras_regioes_inalteradas`).
  No relatório global, só a linha de Ophidia mudou com `f2c1751e`.
- **H-02/H-03.** O E9 agora mede o bloco renderizado (`len(render_block)/4 ≤ 60`), a mesma medida do
  teste. `test_bloco_sem_nome` olha só o texto do sinal (o envelope é fixo), e o teste novo prova que
  o nome no texto continua sendo pego.
- **Monkeypatch no eco.** Os dois testes tiram `enemy_assassino_cinzeu` do carregador para simular
  criatura sem fauna, por exemplo uma de runtime (SPEC-361). É legítimo: a 370 deu entrada a todas as
  fichas, e o caso "sem entrada" continua existindo em jogo.
- **Determinismo.** O eval é byte-idêntico (M7 em todas as regiões). O caminho `on` com fauna no pool
  é semeado; o `random.Random()` sem semente de `services/ecology.py:59` é anterior, já está registrado
  e só pesa no `off` e no `on` sem fauna no pool. Com 368 entradas, esse segundo caso quase não acontece.
- **Save/load.** `normalize_fauna_sim` não mudou. Save antigo com mais presenças que o `region_cap` não
  quebra: só deixa de nascer presença nova até as atuais expirarem.
- **Desempenho com as 368 entradas reais.** `fauna.day_hook` ~0,43 ms por dia e `encounter_distribution`
  ~0,59 ms por chamada, medidos com as flags `on`. O teto de teste (20 ms) cobre `eco_multiplier` e
  `scene_block` com 400 entradas sintéticas. O loader carrega uma vez.

## `test_zero_chamada_llm_nova`: enfraquece a garantia?

Enfraquece um pouco, e é aceitável porque o lockstep continua de pé. Antes o teste exigia contagem
**total** igual entre `on` e `off`. Isso deixou de valer, porque a fauna troca luta por sinal e a
trajetória muda (off 19 turnos de história / 11 de combate; on 24/6). O teste novo exige duas coisas:
1. 0 chamada originada em `services/fauna.py`, pela pilha do `invoke`, inclusive vinda de helper
   chamado pela fauna;
2. custo por turno de história e por turno de combate ≤ 1,15× o do `off`.

O ponto 2 tolera até ~0,3 chamada extra por turno de história, o que deixaria passar uma chamada nova
a cada 3–4 turnos se ela nascesse fora de `services/fauna.py`, por exemplo o storyteller chamando de
novo por causa do bloco de sinal. Quem fecha esse buraco é
`test_campanha_na_lama_exercita_fauna_sem_chamada_extra`: no mesmo estado e com o mesmo acaso, o turno
`on` nunca chama mais que o `off`, e esse teste segue intocado e verde. A garantia de "0 chamada nova"
vem dos dois testes juntos; ver P2-1.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/test_spec360_flags_off.py:155-161` | A tolerância de 15 % por turno é larga para um teste que se chama "zero chamada nova", e a contagem do roteador (`calls[1]`, P2-10 da 360) deixou de ser conferida. | Baixar para 1,05×, ou comparar por rota (história/NPC/loot) em vez de "tudo que não é combate". Voltar a conferir o roteador por turno. Registrar no docstring que a igualdade estrita mora no lockstep. |
| P2-2 | P2 | `docs/spec360/eval-global.md:5` | M5 global −19,51 % contra o piso de −20 %: folga de 0,49 pp, e a mudança de Ophidia sozinha custou 1,5 pp (−17,98 % → −19,51 %). Qualquer conteúdo novo que troque luta por sinal (`cedo`, presença) estoura o critério que barra. A 372, com as criaturas de trama, tira ~1 % dos combates em NA com tudo `revelada`, mas lá a flag é `off` no eval da 360. | Follow-up: antes da próxima onda de conteúdo ou do ajuste de `P_PRESENCA`/`ANUNCIA`, recalcular o M5 global no PR. Se a folga continuar < 1 pp, o coordenador decide entre devolver luta (por exemplo, a presença de Ophidia anuncia só se `cedo`) e reabrir a faixa com o autor de eval. Não mexer no limiar dentro da 370. |
| P2-3 | P2 | `world_utils.py:1482-1483` | Ophidia M5 −37 % (só alerta, R17). A regra converte em sinal **toda** presença sem sinal, inclusive `imediato`, e por isso Ophidia perde 1/3 das lutas. Além disso, se alguém ligar `ANUNCIA_PRESENCA_NOVA` globalmente, a região de 1 nó passa a exigir `cedo`. A semântica da decisão do dono se inverte por causa de uma constante. | Registrar na §9 que a queda de luta em Ophidia é o custo aceito da decisão. Separar as condições: `solo` converte sempre; a constante global continua com `cedo`. |
| P2-4 | P2 | `services/fauna.py:150-155` | `_cap_presences(protect=)` remove `others[-1]`. O comentário diz "a ativa mais antiga", mas sem não ativas no `keep` esse item é a ativa **mais recente** e pode ser uma presença lida da região atual, o que contraria R10. Só ocorre quando `_make_room` falha, ou seja, com 12 ativas protegidas na região atual (`fauna.py:664`). Na prática não acontece. | Escolher a vítima pela mesma ordem do `_make_room`: a ativa mais antiga sem `sinais_mostrados`. Se não houver, não criar a presença do rastro ou da conversão. |
| P2-5 | P2 | `services/fauna.py:664` | R9 só vale no `day_hook`. Conversão e rastro (`_add_presence`) não olham o `region_cap`, então Ophidia pode ter 2 presenças ativas (a do dia + a de uma conversão de outra criatura). O critério "Ophidia nunca passa de 1 presença ativa" só é testado pela função (`test_region_cap_ophidia_1`). | Documentar que o teto é de nascimento diário, ou fazer `_add_presence` respeitar `region_cap` (reforçar a presença existente em vez de abrir outra). |
| P2-6 | P2 | `world_utils.py:1167` | Se todos os fatores de fauna derem 0, `sum(eco_weights) == 0` e o sorteio volta aos pesos legados, mas o migrante multiplica `neutral = 0` e some. É um efeito colateral pequeno da R12. | Usar `neutral` só quando `eco_weights` foi adotado; senão, 1,0. |
| P2-7 | P2 | `services/fauna.py:526` | O comentário fala em "mais frequentada", mas o código ordena por `region_presence` mais recente. A spec (R10) diz "mais frequentada". | Ajustar o texto da spec ou do código (a mais recente é defensável). |
| P2-8 | P2 | `services/fauna.py`, `services/fauna_lint.py`, `world_utils.py`, `data/world/fauna.json`, `evals/protected-paths.txt` | **Conflito com a SPEC-372.** `git merge-tree HEAD spec-372` acusa conflito nesses 5 arquivos. Pontos semânticos para quem resolver: (a) no `day_hook`, o recorte de locais da trama (`fauna_tramas.birth`) tem de vir **antes** do `_make_room`, para não despejar presença alheia e depois pular o dia por `locais` vazio; (b) em `_weighted_pool`, manter o migrante × `neutral` e o `apply_gate` da 372 **por último**; (c) em `_e1_entry`, juntar o laço de `presas/suprime` da 370 com o `tramas_form_ok` da 372; (d) `fauna.json` só via `build.py`; (e) `protected-paths.txt` como união; (f) o T7 da 372 compara com `docs/spec360/eval-nova_arcadia.md`, que a 370 regenera, então é preciso rodar de novo T2/T4/T7 da 372 depois do rebase. | Ordem e resolução: coordenador no pouso. |

Nenhum P0 ou P1.

## Correções aplicadas

Nenhuma (revisão).

## Pendências

- P2-1 a P2-7: follow-ups técnicos com o executor da 370 (ou de uma spec curta de manutenção da fauna).
- P2-2: o coordenador acompanha a folga do M5 global na próxima onda de conteúdo.
- P2-8: pouso 370/372.

## Comandos rodados

```text
git diff ac2004ec..HEAD -- scripts/fauna/eval.py tests/test_spec3{60,70}_eval.py evals/ → vazio
pytest -n 2 test_spec370_{caps,carcaca,latencia,migrante,solo,suprime} test_spec360_{flags_off,eco,sinais,presenca,saves,caca,rumor,build,schema_lint} test_spec312_seeds test_flag_registry → exit 0
pytest -n 2 -m "not slow" test_spec370_eval.py test_spec360_eval.py → exit 0, 0 FAILED
py.sh -c "fauna.day_hook × 30 dias; encounter_distribution × 50 (368 entradas, flags on)" → 0,43 ms/dia; 0,59 ms/chamada
git diff f2c1751e~1 f2c1751e -- docs/spec360/eval-global.md → M5 global −0,1798 → −0,1951 (só Ophidia mudou)
git merge-tree --write-tree --name-only HEAD spec-372 → conflito em 5 arquivos
```
