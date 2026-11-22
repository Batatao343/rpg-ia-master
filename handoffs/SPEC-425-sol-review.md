# SPEC-425 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Nota do veredito:** final, após `d43765c4`; a checagem de delta pediu mudança por P2-3, agora fechado.
> **Revisor:** Claude Opus 5.5 / sol (spec-reviewer, independente do executor) · **Data:** 2026-11-22 · **Commit revisado:** `9d438086`, delta `7ac7798e` + `49b00e0a` (shas de antes do rebase) e `d43765c4`

## Escopo

Só a **Etapa 0** (suporte inerte ao gpt-image-2.6): commit `9d438086` na branch `spec-425`, diff contra
`ac3d2025`. Arquivos: `infrastructure/ports.py`, `infrastructure/openai_images.py`, `services/art_brief.py`,
`services/image_pricing.py`, `workers/dynamic_art_jobs.py`, `scripts/art/measure_image_model.py` (+ `__init__`),
os testes novos e o desvio registrado na spec (sem card novo em `data/pricing/`; `extra_models` provado com card
de teste). Fora: Etapas 1–3, `specs/index.yaml` e specs alheias (a branch está atrás da `main`).

Conferido, por ponto pedido pelo coordenador:

1. **I1 (idempotência/requisição).** Sem `complexity`, `key_material` é a mesma f-string de antes
   (`openai_images.py:81`); o ramo novo só troca o material quando `complexity` é truthy (`:82-86`); o digest das
   referências segue igual. `fields` só ganha a chave quando há valor (`:97-98`), nas duas rotas (o mesmo dict vai
   como `json=` e como `data=`). `test_idempotency_key_sem_complexity_e_igual_a_de_hoje` fixa o hash literal
   `sha256(b"m\n1x1\nlow\np")`; `test_sem_complexity_nao_envia_campo` compara o payload exato nas duas rotas. Um job
   em voo não muda de chave: OK.
2. **R1.** `priced_models()` = `{model} ∪ extra_models`; o card atual não tem `extra_models`, logo o conjunto é
   exatamente `{gpt-image-2-2026-04-21}` (teste de conjunto exato). `require_image_prices` e `price_image_event` só
   trocam `!=` por `not in`; as taxas e o resto da validação de `usage` não mudam; `IMAGE_PRICING_VERSION` não muda
   (bytes do card iguais). Modelo fora do conjunto segue `PricingUnavailable` e evento não exato
   (`test_modelo_desconhecido_segue_indisponivel`). `finops_alerts.installed_freshness` só lê `observed_at`. OK.
3. **R5/R6/worker.** `complexity_for` lê só o brief (sem fallback ao profile); os quatro builders usam
   `**_complexity(profile, fmt)`, que com o profile atual não acrescenta chave alguma: brief idêntico, logo
   `render_image_prompt`, o hash de prompt da cotação (`image_quotes.py:106`) e o `Jsonb(brief)` persistido ficam
   iguais. O épico descarta a `complexity` herdada do retrato e aplica a do `epic_scene`. `profile_complexity_problems`
   roda no profile real dentro do teste (é o "teste de validação do JSON" que R6 pede). `_image_request` passa os
   mesmos cinco argumentos posicionais na mesma ordem e acrescenta `complexity_for(brief)` como sexto campo (o novo,
   com default `None`, no fim do dataclass). `generation["model"]` continua vindo do job (I2 preservado). OK.
4. **Script de medição.** Sem `--confirm-spend`: imprime só modelo/formato/complexity/refs, não lê chave, não cria
   gerador nem diretório. `--max-usd` fora de `(0, 2.00]` (ou `(0, 0.25]` no canário) é recusado no `main` e de novo
   em `measure`. Antes de cada chamada para se `gasto + 0,25 > max`; para depois da primeira imagem com
   `cost_basis != "rate_card"` ou `cost_usd > 0,25`. A chave sai de `OPENAI_API_KEY` e não é impressa; o JSON guarda
   `prompt_hash` (16 hex) e `usage` saneado, sem prompt nem bytes. Imports de topo não fazem rede. Ressalvas em
   P2-1 e P2-2.
5. **Testes.** 21 testes novos; 15 vermelhos na `main` e verdes na branch; os 6 verdes nos dois lados são guardas de
   invariante (I1, conjunto fechado, gate R2) e foram aceitos com `--allow-green`. Nenhum `noqa`, `type: ignore` ou
   `except` novo no diff. `tests/test_size_budget.py` verde. `dup_helpers`: só nomes privados genéricos
   (`_parser`, `_player`, `_record`, `measure`) sem duplicação real.
6. **Guia (api, persistência).** "Trava de allowlist = conjunto exato": atendido (`priced_models() == frozenset({MODEL})`).
   "Asserção vacuamente verdadeira": `test_no_image_card_lists_the_retired_model_after_shutdown` é vácuo hoje (nenhum
   card ≥ 2027-02-10), mas a regra é provada à parte por `test_retired_model_rule_flags_a_late_card`. "Guard mais
   largo que o uso documentado": ver P3-3/P3-4. "Writer persistente novo": não há; o brief ganha uma chave string que
   faz round-trip em JSONB sem mudança de schema. "Modo off byte a byte": é o I1, coberto.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/art/measure_image_model.py:198` e `:276-281` | Se `generator.generate` levanta (403 de safety, 5xx, timeout, chave vazia) depois de N chamadas pagas, `measure` propaga a exceção, o `report` não é preenchido e o `main` não grava `medicao.json`: o gasto real some do registro e uma nova execução repete o gasto. Não há estouro de teto (o script para), mas a evidência de quanto foi gasto se perde. | Envolver o laço em `try/finally` (ou capturar `ImageProviderError`/`httpx.HTTPError`) que registra `stopped = f"provider_error: {type(exc).__name__}"` sem a mensagem, e fazer o `main` gravar o JSON parcial também nesse caminho. Teste com fake que levanta na 2ª chamada: 1 chamada no JSON, `stopped` preenchido. **Antes do primeiro `--confirm-spend` (Etapa 1).** |
| P2-2 | P2 | `scripts/art/measure_image_model.py:184` | R8 exige que os bytes de imagem fiquem **fora do repo**, mas `--out-dir` aceita qualquer caminho, inclusive dentro do checkout (ex.: `docs/spec425/`), e um `git add` levaria os PNGs. | Recusar `out_dir.resolve()` dentro de `ROOT.resolve()` (`parser.error` no `main`, `ValueError` em `measure`) e testar com `tmp_path` dentro de um `ROOT` monkeypatched. **Antes da Etapa 1.** |
| P3-1 | P3 | `scripts/art/measure_image_model.py:267-281` | `--canary` roda o retrato, mas não chama `canary_verdict` nem lê `medicao.json`: a comparação de R15 não acontece pelo CLI. Está no desvio registrado ("só roda de fato depois da Etapa 1"). | Ligar `canary_verdict` no `main` quando `medicao.json` existir e gravar as divergências em `canario.json`, junto com a Etapa 1. |
| P3-2 | P3 | `infrastructure/openai_images.py:81-86` | O material da chave é concatenação com `\n`: uma requisição antiga com prompt começando por `high\n` e uma nova com `complexity="high"` e o resto do prompt geram a mesma chave. Só colide com o mesmo `model`, e `complexity` só existe com `gpt-image-2.6-*`, então o risco prático é nulo hoje. | Opcional: prefixar o campo (`complexity=high`) no ramo novo; o ramo legado fica intacto. |
| P3-3 | P3 | `services/image_pricing.py:24` | `extra_models` não é validado como `list[str]`: uma string por engano no card seria desempacotada em caracteres e precificaria modelos de uma letra. | No teste do card renovado (R3, dezembro), afirmar `isinstance(extra_models, list)` e o conjunto exato `["gpt-image-2.6-sunburst", "gpt-image-2.6-flare"]`. |
| P3-4 | P3 | `services/art_brief.py:127-132` | `complexity_for` aceita qualquer valor truthy do brief sem conferir `low/medium/high`; o único gate é o teste do profile (R6). Briefs vêm do profile no momento da cotação, então hoje é seguro. | Opcional: devolver `None` (com log) para valor fora do conjunto, ou registrar que R6 é a única barreira. |

## Evidência verificada

`bash scripts/dev/red_green.sh 425 --allow-green <6 guardas de invariante>` (os 6 nodeids estão na tabela como
`OK (allow-green)`; a primeira rodada sem `--allow-green` deu 15/21, com os mesmos 6 verdes nos dois lados):

| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_dynamic_art_brief.py::test_builders_gravam_complexity_do_formato | vermelho | verde | OK |
| tests/test_dynamic_art_brief.py::test_complexity_for_ignora_profile | vermelho | verde | OK |
| tests/test_dynamic_art_brief.py::test_profile_complexity_so_em_2_6 | vermelho | verde | OK |
| tests/test_dynamic_art_brief.py::test_sem_complexity_no_profile_o_brief_nao_tem_a_chave | verde | verde | OK (allow-green) |
| tests/test_image_model_measure.py::test_canary_e_um_retrato_com_teto_025 | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_canary_verdict_faixa_de_tokens_e_hamming | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_para_antes_de_passar_do_teto | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_para_com_cost_basis_diferente_de_rate_card | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_para_com_custo_acima_de_025 | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_recusa_max_usd_acima_de_2 | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_roda_o_plano_e_grava_campos_sem_bytes_nem_prompt | vermelho (import) | verde | OK |
| tests/test_image_model_measure.py::test_sem_confirm_spend_nenhuma_chamada | vermelho (import) | verde | OK |
| tests/test_image_pricing.py::test_card_prices_extra_models | vermelho | verde | OK |
| tests/test_image_pricing.py::test_card_sem_extra_models_so_cobre_o_modelo_do_card | vermelho | verde | OK |
| tests/test_image_pricing.py::test_modelo_desconhecido_segue_indisponivel | verde | verde | OK (allow-green) |
| tests/test_openai_images.py::test_envia_complexity_quando_brief_tem | vermelho | verde | OK |
| tests/test_openai_images.py::test_idempotency_key_muda_com_complexity | vermelho | verde | OK |
| tests/test_openai_images.py::test_idempotency_key_sem_complexity_e_igual_a_de_hoje | verde | verde | OK (allow-green) |
| tests/test_openai_images.py::test_sem_complexity_nao_envia_campo | verde | verde | OK (allow-green) |
| tests/test_pricing_card_files.py::test_no_image_card_lists_the_retired_model_after_shutdown | verde | verde | OK (allow-green) |
| tests/test_pricing_card_files.py::test_retired_model_rule_flags_a_late_card | verde | verde | OK (allow-green) |

red_green: 21/21 OK

## Correções aplicadas

Nenhuma até aqui (revisão da Etapa 0).

## Pendências

- P2-1 e P2-2: o executor da SPEC-425 corrige **antes do primeiro `--confirm-spend`** (gate da Etapa 1, que já
  espera D8 do dono). O coordenador confere os dois testes novos antes de liberar a medição.
- P3-1: junto com a Etapa 1 (desvio registrado na spec).
- P3-3: no teste do card renovado (R3, renovação de dezembro).
- P3-2 e P3-4: opcionais, a critério do executor.

## Comandos rodados

```text
git show 9d438086 --stat / diff por área → 13 arquivos, +632/-12
py.sh -m pytest tests/test_image_model_measure.py tests/test_openai_images.py tests/test_image_pricing.py tests/test_pricing_card_files.py tests/test_dynamic_art_brief.py tests/test_dynamic_art_jobs.py tests/test_image_quotes.py tests/test_size_budget.py -p no:cacheprovider -q --tb=short -W ignore (serial; RAM 2,6 GB) → 129 passed
red_green.sh 425 → 15/21 (6 guardas verdes nos dois lados)
red_green.sh 425 --allow-green ×6 → 21/21 OK
py.sh scripts/dev/dup_helpers.py --diff 9d438086~1..9d438086 → só nomes privados genéricos, sem duplicação real
git show 9d438086 | grep noqa/except/type: ignore → nada novo
```

## Checagem de delta (7ac7798e, 49b00e0a)

Escopo: só os dois commits posteriores a `de40cbf0`. Veredito do delta: **`CHANGES_REQUIRED`**. O código de produção
está correto; falta um P2 num teste, que hoje pode virar chamada paga.

**(a) P2-1 e P2-2.** Os dois foram corrigidos como pedi. O laço de `measure` captura a exceção do provider, grava
`stopped = "provider_error: <tipo>"` sem a mensagem e devolve o JSON parcial (`measure_image_model.py:198-206`).
`main` recusa `--out-dir` dentro de `ROOT` antes do plano e antes de qualquer gerador (`:249-250`, `:275-276`), e no
Windows `is_relative_to` não diferencia maiúsculas. `test_falha_na_segunda_chamada_grava_json_parcial` falharia sem
a correção, porque o `RuntimeError` propagaria. `test_recusa_out_dir_dentro_do_repo` também falharia, mas pelo motivo
errado (P2-3).

**(b) `price_image_event`.** Não levanta em nenhum caminho novo: `PricingUnavailable` de `priced_models()` vira
retorno do evento não exato (`image_pricing.py:41-44`). O conjunto precificado só encolheu: um card malformado
(string, dict, `[1]`, `[""]`) agora fecha cotação e preço, até para o modelo fixado, onde antes uma string seria
desempacotada letra a letra. Com o card atual (sem `extra_models`) nada muda. O parametrizado cobre os três caminhos
(`priced_models`, `require_image_prices` e o evento não exato com o modelo fixado).

**(c) `complexity_for`.** `"ultra"`, `""`, `"High"`, `3` e `None` devolvem `None`; `"medium"` passa. Ressalva em P3-5.

**(d) Budget e lint.** `test_size_budget.py` passou. BLE está no `select` (`pyproject.toml:79`), então o
`# noqa: BLE001` é de regra ativa. O motivo do `silent-ok` serve: a falha não é silenciosa, porque o tipo vai para
`stopped` no JSON e para a linha final do `main`, e a mensagem é descartada de propósito, para não vazar texto do
provider. O `try` só envolve `generator.generate`. Não há outro `noqa` nem `except` novo.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-3 | P2 | `tests/test_image_model_measure.py:149-152` | `test_recusa_out_dir_dentro_do_repo` chama `main(... --confirm-spend)` sem trocar `_build_generator` nem `_PROJECT_OUT`. Se o guard de `--out-dir` regredir, o teste cria um `OpenAIImageGenerator` real com `OPENAI_API_KEY` do ambiente (o `tests/conftest.py` não a remove), gera um retrato 1024x1536 pago, grava PNG em `docs/x/` e sobrescreve `docs/spec425/medicao.json`. E ainda passaria a falhar só por não haver `SystemExit`. O "vermelho reconstruído" do executor pode ter sido exatamente isso, com chave vazia (401). | Trocar o gerador por um fake que levanta se chamado (`monkeypatch.setattr(mim, "_build_generator", lambda: pytest.fail("generator built"))`) e apontar `_PROJECT_OUT` para `tmp_path`. Opcional: `monkeypatch.delenv("OPENAI_API_KEY", raising=False)` nos testes do script. |
| P3-5 | P3 | `services/art_brief.py:135` | `value in _COMPLEXITIES` levanta `TypeError: unhashable type: 'list'` se o brief persistido trouxer lista/dict (confirmado com `complexity_for({"complexity": ["high"]})`). Os builders só gravam string, então hoje não acontece. | `return value if isinstance(value, str) and value in _COMPLEXITIES else None`, e `["high"]` no loop do teste. |
| P3-6 | P3 | `scripts/art/measure_image_model.py:204-206` | `stopped` guarda só o tipo: um `ImageProviderError` perde o `http_status` (401 x 429 x 5xx), que é o dado útil para decidir se repete. | Opcional: acrescentar `getattr(exc, "http_status", None)` ao `stopped`; continua sem a mensagem. |

Guia: acrescentei uma linha em `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § api (P2-3), num commit separado.

Testes do delta: `py.sh -m pytest tests/test_image_model_measure.py tests/test_image_pricing.py tests/test_dynamic_art_brief.py tests/test_size_budget.py -n 2 -p no:cacheprovider -q --tb=short -W ignore` → 81 passaram.

Para fechar: corrigir o P2-3 (só teste). Os P3-5 e P3-6 podem entrar no mesmo commit ou ficar como follow-up.
Com o P2-3 corrigido e o arquivo verde, o veredito passa a `APPROVED_WITH_FOLLOWUPS` sem nova revisão completa: basta
o coordenador conferir o diff do teste.

**Checagem de d43765c4:** P2-3 fechado. A fixture autouse `no_paid_calls` remove `OPENAI_API_KEY`, troca `_build_generator` por `pytest.fail` e põe `_PROJECT_OUT` num tmp. `Failed` é `BaseException`, então o `except Exception` de `measure` não o engole, e os testes que trocam o gerador por um fake continuam valendo, porque o monkeypatch do teste roda depois da fixture. P3-5 fechado (`isinstance(value, str)`, casos de lista e dict no teste). P3-6 fechado (` http <status>` só quando há status; a mensagem continua fora). Revisão só do diff, sem rodar testes neste worktree a pedido do coordenador. Veredito final: `APPROVED_WITH_FOLLOWUPS`. Ficam P3-1 (canário no CLI, Etapa 1), P3-3 (tipo e conjunto exato de `extra_models` no teste do card renovado de dezembro) e P3-2 (opcional).
