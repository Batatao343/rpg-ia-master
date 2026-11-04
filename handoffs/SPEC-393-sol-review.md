# SPEC-393 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `fbe62264`

## Escopo

Branch `spec-393`, `main...fbe62264` (13 arquivos): `services/death_ending.py` (novo), `services/death_prose_guard.py` (novo), `services/checkpoints.py`, `services/round_log.py`, `services/prose_guard.py`, `agents/combat.py`, `agents/loot.py`, `scripts/import_bestiary_art.py`, `observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `docs/guias/AUTORIA.md`, a spec e `tests/test_card_epic_caveats.py`. O smoke real do §6 ficou fora (o executor não tem chave; é do coordenador).

Resumo por requisito:

- **R1:** ok. `apply_accept_text` troca o `WHEEL_TEXT` na última mensagem da IA e nas linhas de `presentation_history`; o `continue` não muda. O round-trip save/load é coberto pelo teste da API (`persistence.load_game_state`). O eval `state.lifecycle.accept-death` projeta só `death_pending`/`game_over` e não é afetado.
- **R2:** ok. Com 1 alvo o texto sai byte-idêntico (os testes da 353 R10 e da 355 R4 passam sem edição). O agrupamento usa (autor, tipo, condição) na ordem de primeira ocorrência, e o verbo vai para o plural com 2 ou mais alvos.
- **R3:** ok no fluxo, com ressalvas de precisão (P2-2). O fallback é o `deterministic_outcome_text` já existente. `log_fallback` gera `combat.death_prose.fallback`, que está no catálogo. Reaproveitar `fallback_attribution`/`outcome_attribution_rejected` é **aceitável**: o código `wounds:<motivo>` em `codes` separa a causa, e o evento `combat.death_prose.fallback` dá a contagem própria. O custo é que a métrica `last_outcome_source` mistura as duas causas, o que é tolerável. Os ferimentos já entram no prompt via `outcome_facts` → `_wound_phrases`.
- **R4:** ok. O grupo `pay` é opcional, com alternância fechada e sem quantificador aninhado ambíguo, então não há ReDoS. A frase condicional ("... se for barato") continua caindo em "nada foi cobrado".
- **R5:** o aviso funciona. O `--strict` tem defeito de ordem (P2-1), e o teste dele não prova nada (P2-3).
- **R6:** a conclusão se sustenta. `mock_llm._acao_eco` (mock_llm.py:79-86) ecoa a última mensagem humana, e `routes/turn.py:212` envia "Descreva o cenário ao meu redor. Sou um …" no `/game/new`. Logo a abertura do mock contém o pedido, e o `continue` restaura exatamente essa abertura.
- **R7:** nada protegido mudou (`evals/`, `web/e2e/contracts`, `sim.py` e golden intactos). `agents/combat.py` ficou em 3731 linhas (+1 −1: uma linha em branco removida para compensar). `round_log.py` foi de 937 para 951 linhas e `loot.py` de 945 para 947, ambos abaixo de 1000. Sem flag nova.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | observability/events.py:8-404 | O arquivo foi regerado por `scripts/gen_event_catalog.py` e não passou pelo `ruff format`: aspas simples e linhas longas, daí o diff de 944 linhas. O CI roda `ruff format --check .` (`.github/workflows/validate.yml:62`) e reprova ("1 file would be reformatted"). Semanticamente está certo: 395 → 397 eventos (`combat.death_prose.fallback`, `import_bestiary_art.pool.fallback`), nenhum removido nem alterado. | Rodar `bash scripts/dev/py.sh -m ruff format observability/events.py`. O diff deve cair para +2 linhas. |
| P2-1 | P2 | scripts/import_bestiary_art.py:253-262 | O `--strict` é checado **depois** de `import_folder` já ter gravado o `visual_assets.json` e os WebP. O "erro" sai com rc 2, mas os efeitos colaterais ficam. | Calcular `pool_warnings` antes e, com `--strict` e avisos, retornar 2 sem chamar `import_folder` (ou passar `strict` e abortar antes de `_plan`). |
| P2-2 | P2 | services/death_prose_guard.py:12-15, 45-57 | O guard tem falsos positivos óbvios (todos caem no fallback determinístico, ou seja, perda de prosa boa e não texto errado). Medido com registro = crítico no torso: (a) negação: "Sem ferimentos graves na perna…" → `gravidade:grave`; (b) "leve" como adjetivo: "Um leve tremor percorre sua perna." → `gravidade:leve`; (c) parte do inimigo em minúscula: "O lobo, ferido na perna, recua." → `parte_fora_do_registro:perna`, porque `_OTHER_OWNER` só reconhece dono com inicial maiúscula. Na morte é comum narrar o inimigo ferido. | Exigir contexto de ferimento (`wound_ctx`) também para a checagem de gravidade. Tratar "d[oae]s? <substantivo>" e "o <inimigo>, ferido" como outro dono (incluindo os nomes dos inimigos em minúscula). Ignorar a sentença com "sem" antes do termo. Adicionar os 3 casos como testes negativos. |
| P2-3 | P2 | tests/test_card_epic_caveats.py:159,165 | `imp.main([tmp, "--strict"]) == 2` passa pelo motivo errado: `b"x"` não é imagem válida, então `import_folder` lança `ImportErrorArt` e o rc 2 vem do ramo de erro. Sem `--strict` o rc também é 2 (verificado). O teste não prova o critério R5. | Testar o `--strict` com uma imagem válida (Pillow, 8×8) e `catalog_path`/`out_dir` em `tmp_path` (ou monkeypatch de `CATALOG`/`OUT_DIR`). Afirmar rc 0 sem `--strict` e rc 2 com `--strict`, e que nada foi gravado com `--strict` (amarra o P2-1). |
| P3-1 | P3 | specs/SPEC-393-cartas-smoke-ressalvas-texto.md:69 | O §9 diz "sem evento novo, catálogo intacto", mas o catálogo ganhou `combat.death_prose.fallback` e `import_bestiary_art.pool.fallback`. | Corrigir o texto do §9. |
| P3-2 | P3 | services/death_prose_guard.py:41 | `_side` é código morto (nenhum uso). | Remover. |
| P3-3 | P3 | services/death_prose_guard.py:20 | `_fold` é mais uma cópia (o `dup_helpers` aponta 5 outras). Dívida sistêmica preexistente. | Opcional: reutilizar um fold existente; a consolidação fica para spec própria. |
| P3-4 | P3 | services/death_ending.py:35-38 | Na história, troca **todas** as linhas que contêm `WHEEL_TEXT`; nas mensagens, só a última. Isso só diverge no caso raro de restore sem ponto de retorno (`restored = state`, não estrito), em que uma pergunta antiga fica no histórico. | Opcional: trocar só a última linha do narrador com `WHEEL_TEXT`, por simetria. |
| P3-5 | P3 | services/round_log.py:860 | Grupos de `dano_continuo` com a mesma condição e `by_actor_id` diferentes geram frases repetidas ("Sangramento termina o serviço: A tomba. Sangramento termina o serviço: B tomba."). É o que a spec define (autor, tipo, condição). | Opcional: para `dano_continuo`, agrupar só por (tipo, condição). |

Sem guard de structured output novo: o caminho de LLM reaproveita `_fast_text`. Nenhum valor do LLM entra sem validação e não há segredo em log (`detail` = código fechado). O `except` em `known_pool_ids` é estreito e chama `log_fallback`. Funções novas ≤ 60 linhas.

## Correções aplicadas

(nenhuma ainda: aguardando o executor)

## Pendências

- Obrigatório antes do pouso: P1-1. Recomendados no mesmo ciclo: P2-1, P2-2 e P2-3 (todos baratos).
- O smoke real do §6 fica com o coordenador.
- P3-3 (fold duplicado) entra numa eventual spec de consolidação de helpers.

## Comandos rodados

```text
git diff main...HEAD --stat → 13 arquivos; events.py 944 linhas (reformatação)
comparação semântica de EVENTS main×HEAD → +2 eventos, 0 removidos, 0 alterados
ruff format --check (arquivos .py alterados) → 1 arquivo seria reformatado (observability/events.py)
ruff check (arquivos .py alterados) → All checks passed
dup_helpers.py --diff main...HEAD → _fold e check duplicam nomes existentes
pt.sh test_card_epic_caveats, spec353_registry, spec355_golpe_reacao, spec363_outcome_text, spec363_rare_scenarios, spec387_seed, spec346_outcome, card_shop_loot_text, death_flow, checkpoints, bug_morte_checkpoint, log_event_registry, size_budget, no_silent_except, error_envelope → 309 passed
sondas do guard (7 frases) → 3 falsos positivos (negação, "leve" adjetivo, inimigo minúsculo)
import_bestiary_art.main([pasta com png inválido]) sem --strict → rc 2 (o teste do --strict é vácuo)
```
