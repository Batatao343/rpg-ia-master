# SPEC-418 — medições da Etapa 0

Medido em 12/11/2026, Windows 11, 16 GB (≈ 2,3 GB livres), worktree `rpg-spec-418` em cima de `main` `2711a92c`. Checador sozinho, uma rodada por vez, sem pytest em paralelo. Saídas brutas em `.tmp/spec418/` (não versionado).

## E0.1 Versão

`basedpyright==1.40.2` (pyright 1.1.414), publicada no PyPI em 2026-10-04 (> 7 dias); anteriores: 1.40.1 (10/09), 1.40.0 (07/09). `uv lock` só **acrescentou** `basedpyright` e `nodejs-wheel-binaries 24.19.0` (30 linhas, nenhuma versão existente trocou); `requirements.txt` intacto.

## E0.2 Contagem (escopo cheio da spec: `services`, `infrastructure`, `state.py`, `persistence.py`; todas as regras do `standard` em error)

246 arquivos analisados, 325 erros em 72 arquivos. Por pasta: `services` 278, `infrastructure` 29, `persistence.py` 17, `state.py` 1.
Por regra: reportArgumentType 156, reportOptionalMemberAccess 44, reportReturnType 24, reportAttributeAccessIssue 19, reportOptionalSubscript 18, reportInvalidTypeForm 15, reportPossiblyUnbound(Variable) 13, reportOperatorIssue 8, reportCallIssue 6, reportOptionalCall 5, reportAssignmentType 4, reportTypedDictNotRequiredAccess 3, reportIgnoreCommentWithoutRule 3, reportIncompatibleVariableOverride 3, reportIncompatibleMethodOverride 1, reportGeneralTypeIssues 1, reportOptionalOperand 1, reportRedeclaration 1.

Escopo final (após o corte de E0.7.3): 43 arquivos analisados, **66 erros em 10 arquivos** — `infrastructure` 29, `services` 19, `persistence.py` 17, `state.py` 1. Por regra: ArgumentType 20, InvalidTypeForm 15, OptionalMemberAccess 8, OptionalCall 4, AttributeAccessIssue 4, ReturnType 4, OptionalSubscript 3, IncompatibleVariableOverride 3, AssignmentType 2, OperatorIssue 1, CallIssue 1, Redeclaration 1. PossiblyUnbound e IgnoreCommentWithoutRule: 0 no escopo final.

## E0.3 Tempo e RAM (Windows)

Pico = soma do working set de `node` + launcher, amostrado a cada 0,5 s.

| Escopo | Rodada | Tempo | Pico |
|---|---|---|---|
| cheio | fria | 107,7 s | 2 741 MB |
| cheio | quente | 62,5 s | 2 382 MB |
| final (corte) | fria/quente | 12-14 s | 1 796 MB |

## E0.4 Formato da baseline e CLI

A CLI tem `--baselinefile <FILE>` e `--writebaseline`. Formato: `{"files": {"./caminho.py": [{"code": "regra", "range": {"startColumn", "endColumn", "lineCount"}}, ...]}}` (sem número de linha absoluto, caminhos relativos com `./`, só erros). Baseline do escopo final: 66 entradas, **15 969 bytes** (≈ 16 KB, muito abaixo dos 500 KB).
Semântica de `--writebaseline` sobre baseline existente (testada): imprime `updated <arq> with N errors` e o JSON só com os erros **novos**; a baseline passa a refletir o estado atual (entrada consertada some, nova entra). Sem `--writebaseline`, `--baselinefile` nunca altera o arquivo e a CLI não encolhe sozinha. Então `type_gate.py` roda **uma vez** por check, contra cópia temporária: JSON de saída = erros novos; cópia depois = estado atual (folga = antes − depois).

## E0.5 Estabilidade do casamento

- 5 linhas em branco no topo de `persistence.py`, `infrastructure/speech_finance.py`, `infrastructure/supabase_identity.py` (todos com erros baselinados): **0 erros novos**; R2 não é acionada.
- Renomear `prior` → `prior_x` na linha 94 de `google_play_payments.py`: o erro baselinado de `reportArgumentType` desaparece e entra `reportUndefinedVariable` (erro novo legítimo, regra diferente). Mudar o texto dentro da faixa baselinada não "ressuscita" o erro antigo como novo.

## E0.6 Prova de valor real

`reveal_type(get_llm(0.1, ModelTier.FAST))` → `MockLLM | FallbackLLM | RoutedLLM`; `...with_structured_output(Cena).invoke("x")` → `object | AIMessage | Unknown`; `.titulo` reprova com `reportAttributeAccessIssue` citando `object` e `AIMessage`. **O checador enxerga o `AIMessage` sem anotar nada: Etapa 3 / D-418-2 não acionada, `llm_setup.py` intocado.**
Smoke no arquivo real: função com `get_llm().with_structured_output(ChronicleDigestLLM).invoke([]).summary` em `services/chronicle_compression.py` → rc 1 nas duas linhas (`object` e `AIMessage`), revertida com `git checkout`.

### R18 — casos reais no escopo

Diagnósticos citando `AIMessage` na rodada inicial: **0** (escopo cheio e escopo final). Nenhum dos 325/66 erros é acesso a campo de structured output sem `isinstance`. (Os demais achados `reportAttributeAccessIssue` são `embed_query` em `object`, `GameStore.save_checkpoint/get_checkpoint/pool`, `cryptography` em `google_play.py`: dívida de tipo, fora do guard.) Candidatos a follow-up por indício de bug real: `persistence.py:1219/1347` (`GameStore` sem `save_checkpoint`/`get_checkpoint` no tipo) e `services/cron_internal.py` (`GameStore.pool`, fora do escopo final).

As 8 chamadas de `with_structured_output(` do escopo inicial:

| Chamada | Receptor | Visível ao checador? | No escopo final? |
|---|---|---|---|
| `chronicle_compression.py:86` | `llm or get_llm(...)` | sim (ramo `get_llm`), guardada | sim |
| `creature_gen.py:1454` | `get_llm(...)` direto | sim, guardada (`isinstance` linha 1455) | sim |
| `prologue.py:518` | `get_llm(...)` direto | sim, guardada | sim |
| `shared_pool.py:471` | `llm if llm is not None else get_llm(...)` | parcial (param `llm=None` sem tipo) | sim |
| `death_flow.py:356` | param `llm` sem tipo | ponto cego | não |
| `encounter_preparation.py:455` | param `llm` sem tipo | ponto cego | não |
| `narrative_sink.py:343` | `llm: Any` | ponto cego | não |
| `tactical_profile.py:618` | param `llm` sem tipo | ponto cego | não |

O corte de E0.7.3 só tirou do escopo arquivos que já eram pontos cegos.

## E0.7 Critério de corte (aplicado)

Classificação dos 66 diagnósticos do escopo final (todos listados, amostra < 20 só nas regras pequenas): ruído de biblioteca ≈ 0 (nenhum aponta para LangChain/FAISS/boto3); a maioria é **hint faltando** (`Principal | None` passado onde se espera `Principal`, `return None` em função anotada `dict`, atributos `Optional` de `speech_finance`), com 2 a 3 **suspeitas de bug real** (`GameStore.save_checkpoint/get_checkpoint`, `creature_gen.py:1176` chamada de `.get` com chave `None`). Logo R6 não foi preciso e nenhuma das 7 regras é rebaixada.

- E0.7.3 **acionado**: pico 2 741 MB (frio) e 2 382 MB (quente) > 2 GB no escopo cheio (tempo 62-108 s ficou < 120 s). Corte: `infrastructure/`, `state.py`, `persistence.py` e os 5 arquivos de `services/` que importam `llm_setup` (`chronicle_compression`, `creature_gen`, `daily_spend_cap`, `prologue`, `shared_pool`). O resto de `services/` (≈ 240 arquivos, 278 erros) vira degrau seguinte. Resultado: 13 s e 1,8 GB.
- Níveis finais de R5 (contagem > 0 fora das 7): `reportInvalidTypeForm`, `reportOptionalCall`, `reportIncompatibleVariableOverride`, `reportAssignmentType`, `reportOperatorIssue`, `reportRedeclaration` ficam `warning` (fora da baseline, voltam no degrau 1). As 7 regras e `reportIgnoreCommentWithoutRule` em `error`. Regras do `standard` com contagem 0 no escopo final seguem `error` por padrão.
- **Nome da regra:** na 1.40.2 a chave é `reportPossiblyUnboundVariable` (`reportPossiblyUnbound` dá "Config contains unrecognized setting"); a spec foi emendada.

## E0.8 Windows × Linux

`--pythonplatform Windows` contra `Linux` no escopo final: mesmas 66 contagens por regra. A comparação real fica para o primeiro run do CI (R17 b).

## Calibração do CI (R17)

| Run | Commit | Duração | rc | Motivo de vermelho |
|---|---|---|---|---|
| (aguarda push autorizado pelo dono) | | | | |
