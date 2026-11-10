# SPEC-401 — revisão sol r2 (review)

> **Veredito:** `APPROVED` (com 1 P2 de texto desatualizado)
> **Revisor:** Sol (Sonnet, contexto independente) · **Data:** 2026-11-10 · **HEAD revisado:** `2574f6fb`

## Escopo
Delta `0f786b51..HEAD` (fc3ac772, 5a90b01e, 206306eb, 2574f6fb) contra os achados da rodada 1. Decisões do
coordenador (odre fecha; armador/escuta exceção nominal com dials novos; smoke em processo; P2-4 follow-up) não reabertas.

## Achados da rodada 1
| ID | Estado |
|---|---|
| P1-1 (exclusão protegida editada pelo executor) | Resolvido. `fc3ac772` reverteu; a edição foi refeita em `206306eb`, commit só de autoria de eval (json protegido + teste + adendo §14), sem código de produto. Falta só a aprovação do dono via `eval-governance` na publicação (`/eval-publish`), já prevista. |
| P1-2 (confirmação independente) | Resolvido. `docs/spec401/janela-120-199.json` bate com o RELATORIO e a §9: odre 58,5/56,2 ok; armador `on` 86,3 FORA; escuta `off` 40,3 FORA. Odre fechado, os outros dois exceção nominal (linhas `EXCECAO` no RELATORIO), sem reajuste de dial. |
| P2-1 (grade sondada) | Resolvido: registrada no RELATORIO (~25 pontos, script não preservado, passou do orçamento). |
| P2-2 (sufixo manual do `arena:`) | Resolvido: registrado como manual no RELATORIO. |
| P2-3 (smoke §6) | Resolvido pela decisão do coordenador (em processo, 3 classes x 3 sementes x off/on, sem erro). |
| P2-4 (artefato x dial) | Follow-up, como decidido. |

## Integridade de eval
- `git diff main...HEAD` nos caminhos protegidos: só `docs/bestiario/recalibracoes_posteriores.json`. Commits que o tocam
  desde a r1: `fc3ac772` (reversão) e `206306eb` (autoria). O estado final difere da `main` apenas pelo `206306eb`;
  o executor de produto não deixou edição líquida em caminho protegido.
- `206306eb` contém: json do registro, `tests/test_spec373_montagem.py` (não protegido), adendo §14. Nenhum código de produto.
- O registro tem `spec: SPEC-401` para as 3 ids, todas citadas no RELATORIO, nenhuma em `recalibradas.json`; `fichas`
  fica sem id com dial mudado. O `_doc` cita a guarda nova.

## Guarda nova e M7/M9
- `test_recalibradas_absoluta_com_chave_de_sempre` compara `action_key` de cada `absoluta` da ficha montada com
  `chave_absoluta_esperada(arquetipo)`, uma tabela por arquétipo independente dos dados do bestiário; arquétipo fora da
  tabela reprova. Não é circular: a expectativa não sai da ficha testada. O §14 descreve a M9 (odre com `flank`): sem a
  guarda só o teste do runtime reprova; com a guarda reprovam os dois.
- Perda da M7 (HP do odre) justificada: o dial muda HP/dano de propósito, não existe hash fixo válido; o regime é o mesmo
  das outras ids de `recalibracoes`; o valor de jogo fica nos artefatos de arena (vínculo artefato↔dial = P2-4).

## Achados novos
| ID | Sev. | Arquivo | Problema | Correção |
|---|---|---|---|---|
| P2-5 | P2 | `docs/spec401/RELATORIO.md` (item sobre `recalibracoes_posteriores.json`); spec §9 desvio (3) | Texto desatualizado: diz que o registro NÃO foi editado e que dois testes da 373 ficam vermelhos para o odre. Com o `206306eb` o registro foi editado e os testes passam. | Trocar por "registrado em `206306eb` por autoria de eval separada (adendo §14); testes verdes". |

## Comandos rodados
```text
pytest -n 2 tests/test_spec373_artefatos.py tests/test_spec373_montagem.py tests/test_spec401_calibragem.py tests/test_tactical_archetypes_runtime.py tests/test_size_budget.py -> todos passaram
git diff main...HEAD -- $(cat evals/protected-paths.txt) -> só recalibracoes_posteriores.json
git log 0f786b51..HEAD -- <protegidos> -> fc3ac772 (revert), 206306eb (autoria)
```
