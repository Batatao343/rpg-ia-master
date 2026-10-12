# SPEC-186 — revisão independente Sol High

- **Parecer:** APPROVED — revisão técnica local independente, sem defeitos bloqueantes no source estável.
- **Review run:** `SPEC-186-SOL-20261012-01`.
- **Modelo/esforço:** Sol / High; contexto `/root/spec186_reviewer_sol`, distinto do executor e do root.
- **Status da spec:** permanece `approved`; smoke real pendente de autorização explícita.

O revisor trabalhou em modo read-only durante a análise e não alterou produto,
testes, evaluator, expected, baseline ou datasets. Este arquivo foi registrado
após pedido expresso do root para persistir o parecer independente.

## Escopo e conclusões

Auth/CSRF, isolamento por owner e rate limit próprio foram confirmados no
endpoint `/account/transcriptions`. Bytes, MIME e duração são validados antes
da reserva e do provider. O WAV enviado é reconstruído a partir dos frames
validados; metadados e chunks extras do upload não chegam ao provider.

O diretório temporário é removido em sucesso, erros, timeout, cancelamento e
falha financeira. Áudio e transcript não entram em DB/log/receipt. O receipt
é somente metadata; o transcript efêmero não chama o grafo nem cria uma ação.

Tickets duráveis precedem cada dispatch. Fallback soma tentativas comprovadas
em um único settlement, sem duplicação; replay não retranscreve. Timeouts,
usage ausente e duração estimada na OpenAI preservam reserva com fence para
reconciliação. Falha de settlement após persistir usage também preserva os
fundos, e recovery respeita eventual terminal já liquidado.

A documentação de reconciliação preserva os eventos estimados append-only:
provas exatas são anexadas pelo writer canônico sob referências distintas,
e o settlement seleciona um evento exato por ticket com o fence atual.
Uma tentativa primária incerta com fallback faturável exato não permite
liberar a reserva inteira como ausência de cobrança. O account classifica
usage e settlements como `voice`, com filtro de owner.

A migration só acrescenta `speech_to_text` à constraint de tipo da operação,
preservando os tipos anteriores e as regras existentes de RLS e atribuição.
Não cria tabelas de gravação, grants, policies ou funções privilegiadas.

## Providers e limite financeiro

IDs e contratos foram reverificados em **2026-10-12** nas documentações
[Groq](https://console.groq.com/docs/speech-to-text) e
[OpenAI](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe).
Groq `whisper-large-v3-turbo` usa a duração validada e o mínimo faturado de
dez segundos. OpenAI `gpt-4o-mini-transcribe` usa contadores de tokens válidos
para custo exato; o valor estimado por minuto não autoriza settlement.

O teto OpenAI de US$0,03 é uma **derivação** dos limites publicados de contexto
e output, aplicada ao contrato de bloco único sem prompt, stream ou chunking,
conforme a [referência de transcrição](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create).
Não é uma tarifa exata por duração. Contadores fora desses limites permanecem
incertos. O ID continua configurável e sua
[desativação anunciada para 2027-02-26](https://developers.openai.com/api/docs/deprecations)
está documentada.

## Evidência executável

Resultados executados pelo executor/root e apresentados ao revisor:

- Gate final `tests/test_speech_to_text.py tests/test_speech_api.py tests/test_speech_finance_local.py`, com Postgres local e ffmpeg real: **44 passed, 2 warnings, 3.36s**, exit 0. Inclui seis testes transacionais Postgres e os três formatos comprimidos reais.
- Suíte default completa com o mesmo ambiente: **100%, exit 0, sem falhas**. A saída com quiet duplicado não fornece contagem total; este parecer não inventa essa contagem.
- Rerun dos casos afetados por drift do ambiente: **19 passed** após aplicação da migration versionada da SPEC-185 no Postgres local e regeneração do Project Index. Nenhum teste foi excluído ou enfraquecido.
- Ruff e `git diff --check`: verdes.

Os módulos centrais foram reconferidos sem alterações após os fixes revisados,
na base `f29fb6c687b7e467c1afb288e67d71bf1aaab245`:

| Arquivo | SHA-256 |
| --- | --- |
| `services/speech_to_text.py` | `e2c8fd80e13c32fb3c6e0faf66bec603f6f7d0459c6bbdacb94bb75a52913648` |
| `services/speech_pricing.py` | `4fa10b96c84605adeeb3c030fa6fe361ea485e47eea03c28927cc7c65e312349` |
| `infrastructure/speech_finance.py` | `7afe2b5987c2b7df7ff33304c491880d899aa4df1d08ec847b529bc4d9a62774` |

## Limite do parecer

**Zero chamadas live de STT ocorreram.** O benchmark/smoke real exige
autorização específica; o pedido genérico de continuar não a fornece.
O plano concreto de até quatro chamadas sob teto de US$0,10 está em
[docs/spec186/README.md](../docs/spec186/README.md).

Este APPROVED cobre a implementação técnica offline/local. **A SPEC-186
permanece `approved`, sem fechamento `done`, até o smoke autorizado ou uma
dispensa explícita.** O parecer não autoriza ativação comercial.
