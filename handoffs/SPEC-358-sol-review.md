# SPEC-358 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-11-01 · **Commit revisado:** `f918867f` (branch `spec-358`, base `b145f4ba`)

## Escopo

`git diff main...spec-358` (6 commits, `6ca7c16b..f918867f`): `scripts/cards/sim.py`,
`scripts/cards/promote.py`, `tests/test_card_sim_v2.py`, `tests/fixtures/spec358_sim_v1_golden.json`,
`docs/spec358/*` (gerador do golden, equivalência, arena v2, dados e relatório), `docs/guias/CARTAS.md`
e a spec. O foco foi a integridade do avaliador: v1 byte-idêntico, nada protegido alterado, gate da
esteira inalterado, correção do v2 e fidelidade do relatório. A suíte completa ficou fora (é do
coordenador, no pouso).

### Conferências (todas OK)

1. **v1 byte-idêntico.**
   - O golden (`9d538dd7`, 10:22) precede o primeiro commit que edita o `sim.py` (`2b55c662`, 13:43).
   - A regeneração em `1d41ae11` é **legítima**. Recomputei o golden de forma independente, com
     `git show main:scripts/cards/sim.py` extraído para um arquivo temporário, no motor atual:
     `main_sim == golden: True`, `new_sim == golden: True`, `main == new: True`. O drift veio do
     motor (`services/`, SPEC-355), não do `sim.py` editado.
   - O ramo v1 de `simulate_batch` não foi reescrito. O diff é só a assinatura e o desvio
     `if protocolo == "v2"`.
2. **Protegidos intocados.** O `git diff --exit-code main -- data/cards services
   tests/fixtures/spec330_legacy_golden.json evals docs/spec335 docs/spec339 docs/spec341
   tests/test_card_sim.py docs/spec335/arena_posturas.py` saiu com `EXIT=0`. Limiares e
   `PROTOCOLO_LOTE` não mudaram.
3. **`promote.py`.**
   - `evaluate` não mudou. Só `bandeiras` recusa, e `avisos` é uma chave separada, então não reprova
     no v2.
   - Sem `--sim-report`, o default `--protocolo lote` chama `simulate_protocolo_lote(batch)`
     exatamente como antes (`promote.py:199`), então o v1 reprova como reprovava.
4. **v2.**
   - Os três braços usam a mesma tag `"par"`, os mesmos encontros e as mesmas sementes. `seen` é
     medido só no braço `com`.
   - A referência é injetada aninhada em `injected(batch)`, que restaura no `finally`. O teste prova
     que não sobra `~ref`.
   - A Carta testada não entra no `ref_deck`. Ela fica no catálogo durante o braço ref, como já
     ficava no braço "sem" do v1, e o baralho é explícito.
   - O X da referência é o ponto médio da faixa, e `budget_error(ref) is None` é testado. A posição
     no baralho (R9) é checada.
   - O fallback para remoção (sem referência) segue R10/R11.
5. **Relatório: bandeiras v1 derivadas × v1 real**, amostradas em 2 subclasses rodando o `sim.py
   --protocolo lote` agora.
   - `devoto_consagrado.json`: 12/12 idênticos em delta, vitórias, uso e bandeiras.
   - `medico_cirurgiao_trincheira.json`: 11/12 idênticos. `med1_tri_pulso_emprestado` (level 15)
     diverge. O v2 rodado agora concorda com o v1 rodado agora, e o que diverge é o
     `arena-v2.json`, gerado num motor anterior (ver P2-1).
   - Nenhuma bandeira ou veredito muda nas amostras.
6. **R15 e D6.** R15 não se confirmou (remoção +10,6 pp × substituição −11,2 pp). A seção "0.
   Leitura" do relatório e a §4 dizem isso e aplicam a D6. O default continua v1
   (`promote.py:181-183`, `CARTAS.md`).

Também conferi: não há structured output nem LLM (o guard não se aplica), nenhum segredo em log,
nenhum writer de estado de jogo, e `evals/` está intocado.

## Achados

Não há P0 nem P1.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `docs/spec358/arena-v2.json:2-10` (meta), `docs/spec358/arena_v2.py:145` | Os dados da arena v2 foram gerados num motor anterior ao da base atual: `med1_tri_pulso_emprestado` dá `vitoria_sem` 0.725 hoje contra 0.688 no JSON. A causa provável é a "boss promise" da SPEC-355 em `services/`, em encontro de nível 15. O meta não registra o SHA do motor, então o relatório chama de [F] números que não se reproduzem exatamente na base de pouso. | Gravar `git rev-parse HEAD` (e o da `main`) no `_meta` da fase 1, 2 e 3. Ou rerodar `rodar.sh` (fases 1-3) na base de pouso, ou declarar no relatório o SHA em que os números valem. |
| P2-2 | P2 | `docs/spec358/equivalencia-v1.json:4` | A equivalência 15/15 foi feita contra a `main` `be7212f3`, antes do rebase. O R13 pede a prova "uma vez, no pouso". A minha recomputação do golden cobre o caso sintético no motor atual, mas os 15 arquivos reais não foram refeitos. | No pouso, rerodar `docs/spec358/equivalencia_v1.py` (sozinho, em background) e commitar o JSON com o SHA atual. |
| P2-3 | P2 | `docs/spec358/gerar_golden_v1.py:143-149` | `_meta.gerado_de` grava o `HEAD` da branch (hoje `efde0e2b`, um SHA órfão do pré-rebase), não o da `main` nem a origem do `--sim`. O R12 pede o "SHA da main". O conteúdo está correto (verificado), mas a proveniência gravada engana. | Gravar `gerado_de` = `git rev-parse main` e `sim_fonte` = caminho ou ref passado em `--sim`. |
| P2-4 | P2 | `specs/SPEC-358-arena-substituicao-uso.md:321` | O §7 diz que a spec "não pode regenerá-lo depois de editar o `sim.py`". `1d41ae11` regenerou o golden (com o `sim.py` da `main`, o que está correto), mas o desvio não está registrado na spec. | Acrescentar uma linha no §7 ou no §4: regeneração por drift do motor, com o `sim.py` da `main` via `--sim`, no commit `1d41ae11`. |
| P2-5 | P2 | `docs/spec358/arena_v2.py:368`, `docs/spec358/rodar.sh:11` | `relatorio()` sobrescreve o `RELATORIO-arena-v2.md` inteiro, e o `rodar.sh` roda `--fase relatorio`. Quem seguir o script apaga a seção manual "0. Leitura" sem nenhum aviso em tempo de execução. O título da seção avisa, mas o script não. | Preservar o bloco entre `## 0.` e `## 1.` se o arquivo existir, ou ler a "Leitura" de um arquivo à parte, ou abortar se a seção 0 existir sem `--forcar`. |
| P2-6 | P2 | `docs/spec358/arena_v2.py:261-267` | `cont()` é código morto (`and False`, nunca chamado). | Remover. |
| P2-7 | P2 | `docs/spec358/RELATORIO-arena-v2.md:10` | O texto "Das 76 recusas do v1, 40 … e 9 … e 32 …" soma 81: as categorias se sobrepõem, porque um item pode ser `dominante` por uso e por delta. Lido como partição, o texto confunde. | Dizer "motivos (um item pode ter mais de um)" ou contar os exclusivos. |
| P2-8 | P2 | `tests/test_card_sim_v2.py` | Lacunas de teste: (a) nenhum teste prova que `promote.main` sem `--sim-report` chama o v1 e com `--protocolo lote-v2` chama o v2 (R17); (b) o caminho `referencia_fora_de_posicao` (`sim.py:484`, `:532`) não é exercitado; (c) `test_referencia_familia_segue_o_bot:84` aceita `dot is None`, uma asserção fraca. | Testar com `monkeypatch` de `sim.simulate_protocolo_lote` em `promote.main`. Montar uma Carta com um id que caia entre `cid` e `cid~ref` no baralho. Fixar a família do `dot`. |
| P2-9 | P2 | `scripts/cards/sim.py:484` | `build_arms_v2` devolve `{"fora_de_posicao": True}` como `ref_card`, quando a assinatura e o R9 dizem `None`. Hoje os chamadores checam `ref_deck is None`, mas um chamador que teste `ref_card` como verdadeiro trataria o sentinela como referência. | Devolver `None` e sinalizar a posição por outro meio (5º elemento ou exceção capturada), ou documentar o sentinela no tipo de retorno. |

## Correções aplicadas

Nenhuma até aqui. Revisor só leitura: nenhum P2 foi corrigido no código.

## Pendências

- **Semântica do avaliador, antes de qualquer D5. Dono: coordenador, depois Astra; spec de balanço
  ou referência futura.**
  - A faixa de orçamento é muito larga. No controle do R15 ela vai de −3,0 a 16,0, e o ponto médio
    vira dano 7 contra dano 4.
  - A referência concentra todo o orçamento no único efeito que o bot valoriza. Por isso o v2 é
    estruturalmente leniente: 75 das 76 recusas do v1 passam e os deltas saem quase sempre
    negativos.
  - Como gate, o v2 hoje quase nunca dispara.
  - O relatório já registra isso ([H] e D6). Não se deve trocar o default sem recalibrar a
    referência: por exemplo, a mediana do poder real das Cartas da mesma Postura e patamar, ou o
    quartil inferior da faixa.
- Os P2-1 e P2-2 são do pouso (coordenador): rerodar e carimbar o SHA. Os P2-3 a P2-9 são
  follow-ups do executor ou de uma spec de limpeza.

## Comandos rodados

```text
git diff --exit-code main -- data/cards services tests/fixtures/spec330_legacy_golden.json evals docs/spec335 docs/spec339 docs/spec341 tests/test_card_sim.py docs/spec335/arena_posturas.py → EXIT=0
scratch/check_golden.py (gg.compute com git show main:scripts/cards/sim.py e com o sim.py novo) → main==golden True, new==golden True, main==new True
sim.py --lote data/cards/posturas/devoto_consagrado.json --protocolo lote → 12/12 iguais ao derivado do arena-v2.json
sim.py --lote data/cards/posturas/medico_cirurgiao_trincheira.json --protocolo lote → 11/12 (pulso_emprestado: drift do motor; veredito igual)
sim.py --lote …/medico_cirurgiao_trincheira.json --protocolo lote-v2 → v1-agora == v2-agora (remoção) 12/12; difere do arena-v2.json só em pulso_emprestado
py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_card_sim.py tests/test_card_sim_v2.py tests/test_card_lint.py → 72 passed (test_card_sim_v2: 14 passed), exit 0
```
