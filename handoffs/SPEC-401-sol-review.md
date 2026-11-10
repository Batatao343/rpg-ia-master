# SPEC-401 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus, `spec-reviewer`, contexto independente) · **Data:** 2026-11-09 · **Commit revisado:** `16e572c2`

## Escopo

Branch `spec-401`, commits `a3efd22c` (teste vermelho + base) e `16e572c2` (dials), sobre a `main` `f27238ee`.
Li o diff inteiro de `_ajustes.yaml`, `docs/bestiario/recalibracoes_posteriores.json`, `docs/spec401/*`,
`tests/test_spec401_calibragem.py` e o diff de `data/bestiary.json` e `data/cards/criaturas/*.json`. Julguei
os quatro desvios declarados (a)–(d) contra a spec e contra o contrato de integridade de eval (AGENTS.md
§ Operação; `08_CONTRATO_CODING_AGENT.md`; precedente em `handoffs/SPEC-373-eval-authoring.md` §10–§13).
Fora do escopo: motor (SPEC-400) e suíte completa (é do coordenador, no pouso).

## O que conferi e está certo

- **R1:** `docs/spec401/ajustes-base.yaml` é byte a byte igual ao `_ajustes.yaml` da `main`. `base.json` registra os 3 ids.
- **R3:** gerei o snapshot de novo no HEAD (`docs/spec394/snapshot.py`). Contra `base-snapshot.json`, só
  `mon_armador_de_fosso`, `mon_escuta_do_sinal` e `mon_odre_de_oleo` mudam. As outras 370 curadas têm hash
  `off`/`on` igual, e o snapshot do HEAD sem os 3 bate com `final-snapshot.json`. `ids_com_dial_mudado`
  contra a base dá exatamente os 3.
- **R2, pelo oráculo da spec:** rodei o `arena.py` congelado no HEAD e ele reproduz `arena-final.json` (0–39) e
  `confirmacao-40-119.json` célula por célula. Os 3 dão `ok` nas duas janelas.
- **(d) JSONs regenerados:** aceito. `gerar_mecanica.py --todas` no HEAD não deixa diff, ou seja, o que foi
  commitado é a saída da esteira, sem edição à mão. O diff de `bestiary.json` toca só os 3 ids.
- **(a) sondagem manual de armador e escuta:** aceito como desvio de método (P2-1). O oráculo não mudou:
  `arena.py`, faixa e sementes estão congelados. Para esses dois ids, a confirmação 40–119 veio depois da
  escolha e não houve reajuste.
- O conteúdo da edição (c) está certo: o odre agora tem dial mudado, e a guarda `test_registro_de_posteriores_valido`
  proíbe id com dial em `fichas`. Também não há helper duplicado (`dup_helpers.py`).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `docs/bestiario/recalibracoes_posteriores.json:20-23,42-45` | **(c) Exclusão protegida editada pelo executor de produto, na mesma tarefa da otimização.** O arquivo está em `evals/protected-paths.txt:28`. O contrato diz que quem otimiza não altera exclusões, e todas as edições anteriores desse registro passaram pelo autor de eval (`SPEC-373-eval-authoring.md` §10, §11). Há também um efeito colateral que só o autor de eval pode aceitar: ao sair de `fichas`, o odre deixa de passar por `ficha_vs_base` em `test_spec373_montagem.py:156-161` e sai inteiro do snapshot R2. Isso desliga para ele as mutações M7 e M9 do adendo §13, e o odre era justamente o exemplo da M9. Hoje só `test_tactical_archetypes_runtime.py:512` segura a M9. | **Exige EVAL_AUTHORING.** (1) Um agente que não otimizou o produto reescreve a edição em commit próprio, só com o caminho protegido, e acrescenta o adendo §14 em `handoffs/SPEC-373-eval-authoring.md`. O adendo decide se a perda da M7/M9 para o odre é aceitável ou se entra uma guarda nova (por exemplo, a `absoluta` ainda com a chave de `sempre` nas ids de `recalibracoes`) e registra a mutação M9 refeita. (2) **Exige aprovação do dono via `eval-governance`** na publicação: o caminho protegido dispara `eval-gates.yml:44`. Use `/eval-publish`. O dono não precisa reabrir a calibração. |
| P1-2 | P1 | `docs/spec401/RELATORIO.md:12-13`; spec §9 | **(b) e a robustez do resultado.** A confirmação do odre não é independente: o dial foi escolhido olhando 0–119, e a R2 pede confirmação "uma vez, sem reajuste". Para medir, rodei o `arena.py` congelado numa janela nova, as sementes 120–199, sem mudar nada. O odre passa (58,5 / 56,2). **Armador e escuta saem da faixa:** armador `L3/on` 86,3 % e escuta `L3/off` 40,3 %. Somando 40–199, a escuta fica com `off` em 42,9 %. Então "nenhuma exceção nominal remanescente" exagera: os dois fecham no oráculo da spec, mas no limite, com 1 pp e 0,5 pp de margem. | Gravar a janela 120–199 pelo `arena.py` (`--seed-inicio 120 --seeds 80 --ids <3>`) em `docs/spec401/janela-120-199.json`, sem reajuste. Ela serve de confirmação independente do odre e de registro de robustez dos outros dois. No RELATORIO e na §9: odre fechado com confirmação independente; armador e escuta fechados no oráculo 0–39/40–119, mas marginais, com a leitura 120–199. O coordenador leva ao dono a D1 para os dois: aceitar como fechados ou manter exceção nominal com a leitura nova. **Não reajustar dials nesta spec**: seria calibrar olhando a janela nova. |
| P2-1 | P2 | `docs/spec401/RELATORIO.md:17-20` | (a) Os dials de armador e escuta vieram de cerca de 25 pontos sondados por um script fora do repo. A R2 pedia o `calibrar.py`, com no máximo 2 execuções por id. A busca não é reproduzível e excede o orçamento de busca, o que explica a margem de 0,5–1 pp e o resultado do P1-2. | Registrar no RELATORIO a grade sondada (pontos e células) e manter o desvio na §9. Se armador e escuta voltarem a precisar de ajuste, abrir spec de Carta/mecânica (D1 alternativa), porque o gap `off`/`on` de cerca de 37 pp é estrutural. |
| P2-2 | P2 | `data/bestiario/mecanica/_ajustes.yaml:890` | A R5 pede o texto `arena:` "que o `calibrar.py` grava". O sufixo `(SPEC-401, seeds 0-119)` do odre tem cara de escrito à mão, e os outros dois têm o formato puro. | Usar o texto do `calibrar.py` (medição `--rodadas 0`) ou registrar no RELATORIO que o sufixo é manual. |
| P2-3 | P2 | spec §6, §5 | O smoke §6 (um combate por id pela API local com MockLLM) não tem registro, e os checkboxes do §5 seguem desmarcados. | Rodar o smoke e anotar na §9. Marcar o §5. |
| P2-4 | P2 | `tests/test_spec401_calibragem.py:41-83` | O teste só lê artefatos gravados: nada liga `arena-final.json` ou `final-snapshot.json` aos dials atuais. Se alguém mexer num dial depois, o teste continua verde. O padrão é o mesmo da 394 (`test_bestiario_calibragem.py`). O vermelho na base vinha de artefato ausente, não de `ok=false`, e o odre já estava `ok` na base. | Follow-up: gravar no `arena-final.json` (ou num arquivo ao lado) o hash dos dials dos 3 ids e conferir no teste. O nome `test_spec401_*` contraria o BRIEF, mas a spec o fixou; fica como está. |

## Respostas diretas aos desvios

- **(a)** Aceito como P2-1, sem violação de integridade: o oráculo segue congelado e a confirmação de armador e escuta foi independente. A consequência real aparece no P1-2.
- **(b)** Viola a R2 para o odre. Corrige-se com a janela 120–199 já medida, em que o odre passa (P1-2). Não precisa de nova calibração.
- **(c)** **Sim, exige EVAL_AUTHORING** (commit e adendo §14 por outro agente, decidindo o que fazer com a perda da guarda M7/M9 do odre) **e aprovação do dono via `eval-governance`** na publicação. O conteúdo da edição parece certo, mas o papel errado o fez, e ele afrouxa uma guarda.
- **(d)** Aceito: a regeneração é idempotente e foi conferida.

## Correções aplicadas

(nenhuma ainda)

## Pendências

- P2-4: amarrar os artefatos da calibragem ao hash dos dials. Dono: coordenador. Destino: follow-up do bestiário.
- Se o dono escolher exceção nominal para armador ou escuta (D1), a recalibração deles vira spec de Carta/mecânica.

## Comandos rodados

```text
git diff main...HEAD --stat → 14 arquivos; só os 3 blocos de _ajustes.yaml mudaram
diff <(git show main:_ajustes.yaml) docs/spec401/ajustes-base.yaml → iguais
py.sh docs/spec394/snapshot.py --out C:/t401r/head-snap.json → diferença contra a base só nos 3 ids; HEAD menos os 3 == final-snapshot
py.sh scripts/bestiario/arena.py --seeds 40 --ids <3> → reproduz arena-final.json (MATCH x3)
py.sh scripts/bestiario/arena.py --seed-inicio 40 --seeds 80 --ids <3> → reproduz confirmacao-40-119.json (MATCH x3)
py.sh scripts/bestiario/arena.py --seed-inicio 120 --seeds 80 --ids <3> → odre 58.5/56.2 ok; armador 47/86.3 FORA; escuta 40.3/81.5 FORA
py.sh scripts/bestiario/gerar_mecanica.py --todas → working tree limpo (JSONs commitados == esteira)
pt.sh test_spec401_calibragem test_spec373_artefatos test_spec373_montagem test_bestiario_calibragem test_enemy_decks test_conflito_autoria_bestiario → 101 passed
pt.sh tests/test_tactical_archetypes_runtime.py → 31 passed
py.sh scripts/validate_content.py → 0 erros, 29 avisos (preexistentes)
py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função duplicada
```
