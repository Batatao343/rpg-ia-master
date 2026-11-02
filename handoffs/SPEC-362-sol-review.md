# SPEC-362 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / papel Sol · **Data:** 2026-11-02 · **Commit revisado:** `c6a24599`

## Escopo

Branch `spec-362`, `main...c6a24599` (14 commits): `data/classes.json` (Arcanista
`vitalidade_bonus` 6→8), `arcanista_cinzento_calibrado.json` (`pulso_medido` dano 3→4,
Fôlego 1→0, v2), `arcanista_cinzento_improvisador.json` (`truque` proteção 2→3, v2;
`bomba_estopim` de volta à v1), artefatos `docs/spec362/`, `tests/test_spec362_arcanista.py`,
`tests/test_spec355_arena.py` (R13), `tests/test_letalidade_early.py`. Fora: front
(não muda), suíte completa (é do coordenador no pouso).

## Verificação dos pontos pedidos

1. **Catálogo final medido em held-out.** `arena-confirmacao.json` (180–259, 51,4 %) foi
   medido com `bomba_estopim` v2, que depois voltou à v1; o catálogo final só tinha 0–19
   (52,1 %) e as informativas 20–99/100–179 (50,3 %/50,3 %, `versoes` sem a bomba: são do
   catálogo final). Rodei o catálogo final (`c6a24599`) em 180–259, sequencial:
   **`todas` 49,7 %** (padrão 65,3); calibrado 59,5 % (padrão 69,6); descoberto 45,1 %
   (60,1); **improvisador 57,7 % (padrão 68,5 %)**. Piso ≥ 45 % sem exceção e teto ≤ 75 %
   por subclasse cumpridos. Calibrado/descoberto batem com o artefato (a bomba é só do
   improvisador), o que confirma a leitura.
2. **Testes protegidos/avaliador.** `SUPERADO_POR` é o mecanismo prescrito pelo R13; o
   limiar 0,45/0,85 e `EXCECOES_TETO` não mudaram; `sim.py`, arenas 335/341/355,
   orçamento, golden/snapshot da 330, `test_card_sim.py`, `test_spec341_balanco.py` e as
   legadas sem diff (`test_legadas_e_avaliador_sem_diff` verde na branch). Não é
   afrouxamento: o piso continua 0,45 e o número lido cumpre. Ressalva no P2-1 (o
   artefato lido é de um catálogo que não existe mais). `test_letalidade_early` só passa a
   esperar o dado novo (16 de Vitalidade), sem limiar alterado. `test_spec355_exemplos_fora`
   não mudou. `evals/` intocado.
3. **Outras Posturas idênticas** (`test_outras_posturas_identicas_a_base` verde; diff de
   `classes.json` é uma linha). Vitalidade +2: `gamedata.sync_vitality` lê o bônus da
   classe; nenhum teste/golden/front codifica 14 para o Arcanista (os `14` em
   `test_conflito_orquestrador.py:78` e `test_letalidade_early.py:195` são fixtures
   genéricas). Ver P3-3 (saves antigos) e P3-2 (gerador).
4. **`bomba_estopim` dominante pré-existente** (v1 +9,4 pp): follow-up, não bloqueia.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `docs/spec362/arena-confirmacao.json`; `tests/test_spec362_arcanista.py:71-76`; `tests/test_spec355_arena.py:49-53` | A confirmação gravada (51,4 %) é do catálogo com `bomba_estopim` v2; o avaliador da 355 (via `SUPERADO_POR`) e o R15 checam esse número, e `revertidas_depois` existe só para o teste de versões tolerar a divergência. O gate repousa num artefato de catálogo inexistente. | Antes do pouso, regravar `arena-confirmacao.json` com o catálogo final em 180–259 (medido nesta revisão: `todas` 0,497; subclasses padrão ≤ 0,696) mais o `cartas --ids` das duas alteradas, e remover `revertidas_depois` e o desvio no teste. Os números já são conhecidos, então não há risco de reajuste. |
| P2-2 | P2 | `tests/test_spec355_arena.py:15-16` | R14 pede o comentário de `EXCECOES_TETO` citando "aceitas como definitivas pelo dono (SPEC-362 §8 D5)"; o comentário continua o da 355. Critério R14 desmarcado. | Trocar só o comentário (valores iguais), no commit separado do coordenador. |
| P3-1 | P3 | `tests/test_spec355_arena.py:11`; `tests/test_spec362_arcanista.py:100` | Comentários desatualizados: "0-19 53,5 %" (o `arena-final.json` diz 52,1 %) e "confirmacao nas sementes 100-179" (é 180–259). | Corrigir os textos. |
| P3-2 | P3 | `scripts/gen_classes_v2.py` (bloco do Arcanista, `vitalidade_bonus: 6`) | Regerar `classes.json` com o gerador desfaz o buff. Nenhum teste compara gerador × JSON. | Atualizar o gerador para 8 ou anotar que `classes.json` é a fonte. |
| P3-3 | P3 | `gamedata.py:455-460` | `sync_vitality` prefere `actor["vitalidade_base_bonus"]` persistido: Arcanistas de saves existentes ficam com bônus 6 (Vitalidade 14). Coerente com estabilidade de save, mas o buff só vale para fichas novas. | Registrar no CHANGELOG/§8; se o dono quiser o buff retroativo, migrar `vitalidade_base_bonus` no load. |
| P3-4 | P3 | `arcanista_cinzento_improvisador.json` (`arc1_imp_bomba_estopim` v1) | Bandeira `dominante` pré-existente (+9,4 pp, v1). | Follow-up na próxima onda de balanço/esteira (SPEC-336), sem bloquear. |

Sem P0/P1. Smoke §6 item 3 (`orch.run_round` com as alteradas) e item 4 (tela com flags
`on`) não foram verificados aqui; ficam com o executor/coordenador no smoke final.

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

- P2-1 e P2-2: coordenador, antes do `/spec-land` da 362.
- P3-1..P3-3: coordenador ou próxima spec de balanço.
- P3-4: SPEC-336 (esteira de Cartas) ou spec de balanço seguinte.

## Comandos rodados

```text
git diff main...HEAD --stat → 19 arquivos (3 dados, 3 testes, docs/spec362, spec)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec362_arcanista.py tests/test_spec355_arena.py tests/test_letalidade_early.py tests/test_spec341_balanco.py tests/test_card_lint.py tests/test_card_effects_grammar.py tests/test_card_acervo_reparo.py tests/test_spec355_exemplos_fora.py tests/test_balance_classes.py tests/test_balance_classes_v4_runtime.py tests/test_classes_refactor.py tests/test_fix_vitalidade_terminal.py tests/test_conflito_orquestrador.py tests/test_spec355_guardas.py → 249 passed
bash scripts/dev/py.sh docs/spec341/arena_spec341.py posturas --seeds 180:260 --classes "Arcanista Cinzento" --out <scratchpad> → todas 0,497 (padrão 0,653); cal 0,595/0,696; des 0,451/0,601; imp 0,577/0,685
```
