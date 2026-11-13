# SPEC-409 — fontes de preço lidas pelo coordenador

Lidas em **2026-11-13** (o executor não tem web). Ferramenta: WebFetch, que entrega a página
resumida por um modelo; os números abaixo são os trechos que ele citou entre aspas. Onde a
página oficial não mostrou o número, está dito. Nada aqui foi copiado de memória.

`observed_at` dos cards novos = `2026-11-13`.

## 1. Imagem — OpenAI `gpt-image-2-2026-04-21`

**Fonte A:** https://developers.openai.com/api/docs/pricing (acesso 2026-11-13)

Tabela "Images", aba Standard, cabeçalho `Model | Modality | Input | Output | Cached input`,
"Prices per 1M tokens unless noted":

```
gpt-image-2 | Image | $8.00 | $30.00 | $2.00
gpt-image-2 | Text  | $5.00 | -      | $1.25
```

Aba Batch: `gpt-image-2 | Image | $4.00 | $15.00 | $1.00` e `gpt-image-2 | Text | $2.50 | - | $0.625`.
Nota da página: "Cached input rates for GPT Image 2 and GPT-Image-2.5 only apply to images
generated with the Responses API."

Conclusão: o Standard agora é listado direto (antes era derivado do Batch × 2). Valores iguais
aos do card de 12/10: texto 5.00, imagem entrada 8.00, imagem saída 30.00. O produto usa a
Images API direta, então segue sem desconto de cache.

**Fonte B:** https://developers.openai.com/api/docs/models/gpt-image-2 (acesso 2026-11-13)

A página não traz preço (aponta para a de pricing). Snapshot listado: `gpt-image-2-2026-04-21`,
com o status **"Deprecated"**.

**Fonte C:** https://developers.openai.com/api/docs/deprecations (acesso 2026-11-13)

Tabela "Upcoming deprecations":

```
gpt-image-2, gpt-image-2-2026-04-21 — Notice date: Nov 10, 2026 — Shutdown: Feb 10, 2027
Replacement: gpt-image-2.6-sunburst or gpt-image-2.6-flare
```

**Decisão do coordenador (13/11, por delegação do dono):** o modelo foi marcado como
descontinuado, mas segue servido com o mesmo id até 10/02/2027 e com preço publicado. O R1.1
manda parar se o snapshot "saiu de linha ou o `model` mudou"; nenhum dos dois aconteceu ainda.
O card é renovado para o **mesmo** modelo. A troca para `gpt-image-2.6-*` é decisão de produto
e vira spec própria, com prazo 10/02/2027. O JSON novo registra a descontinuação em `derivation`.

## 2. STT — Groq `whisper-large-v3-turbo`

**Fonte:** https://console.groq.com/docs/speech-to-text (acesso 2026-11-13)

```
whisper-large-v3-turbo | $0.04 (Cost Per Hour) | Multilingual | ...
Minimum Billed Length: 10 seconds. If you submit a request less than this, you will still be billed for 10 seconds.
```

Sem mudança: `usd_per_hour` 0.04, `minimum_seconds` 10.

## 3. STT — OpenAI `gpt-4o-mini-transcribe`

**Fonte A:** https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe (acesso 2026-11-13)

```
Audio tokens: Input | $1.25 | 1M tokens · Output | $5 | 1M tokens
16,000 context window · 2,000 max output tokens
```

**Fonte B:** https://developers.openai.com/api/docs/pricing (acesso 2026-11-13)

```
gpt-4o-mini-transcribe | Transcription | $1.25 | $5.00 | $0.003 / minute
```

Sem mudança: entrada 1.25, saída 5.00, tetos 16000/2000. A página do modelo rotula a tabela
como "Audio tokens" e não lista preço de token de texto à parte.

## 4. Embedding — Jina `jina-embeddings-v3`

**Fonte oficial:** https://jina.ai/api-dashboard/pricing (acesso 2026-11-13). A página só
entregou "We introduced a new pricing model on May 6th, 2025." e os nomes das chaves (Free,
Paid, Premium); os valores dos pacotes **não** vieram na leitura (página montada por script).
https://jina.ai/embeddings/ também não mostra preço.

**Fonte secundária (é dela que vem o número):** https://usagepricing.com/blueprint/jina-ai
(acesso 2026-11-13; a página diz "fact-checked on Oct 24, 2026")

```
Standard (Prototype)  | $50  | 1B tokens  | 0.050 / 1M
Premium (Production)  | $500 | 11B tokens | 0.045 / 1M
Tokens never expire and are shared across all Search Foundation APIs.
```

Sem mudança: 0.05 por milhão (o Standard, mais alto). **O JSON e o README têm de dizer que o
valor vem de fonte secundária.** Outros agregadores divergem (alguns citam US$ 0,02/1M); o card
fica no valor mais alto, que é o conservador.

## 5. LLM — Groq `openai/gpt-oss-20b` e `openai/gpt-oss-120b`

**Fonte A:** https://console.groq.com/docs/models (acesso 2026-11-13)

```
openai/gpt-oss-120b: "$0.15 input" · "$0.60 output" · 131,072 context · 65,536 max output
openai/gpt-oss-20b:  "$0.075 input" · "$0.30 output" · 131,072 context · 65,536 max output
```

Essa página **não** lista o preço de entrada em cache.

**Fonte B (cache):** https://console.groq.com/docs/model/openai/gpt-oss-20b e
https://console.groq.com/docs/model/openai/gpt-oss-120b (acesso 2026-11-13)

```
gpt-oss-20b:  Input $0.075 (13M / $1) · Cached Input $0.037 (27M / $1) · Output $0.30 (3.3M / $1)
gpt-oss-120b: Input $0.15 (6.7M / $1) · Cached Input $0.075 (13M / $1) · Output $0.60 (1.7M / $1)
```

A unidade "por 1M de tokens" não está escrita nessas páginas; sai da conta "13M / $1". Sem
mudança nos seis números nem nos tetos. `source` do JSON novo deve citar as duas URLs.

## 6. LLM — DeepSeek `deepseek-flash` e `deepseek-v4-flash`

**Fonte:** https://api-docs.deepseek.com/quick_start/pricing/ (acesso 2026-11-13)

```
deepseek-flash — input cache hit: $0.003 off-peak / $0.006 peak
                 input cache miss: $0.15 off-peak / $0.3 peak
                 output: $0.6 off-peak / $1.2 peak · context 1M · max output 384K
"Off-peak rates are half of the peak rates."
Peak: 01:00–04:00 e 06:00–10:00 UTC, segunda a sexta, fora feriados chineses.
```

A página diz que `deepseek-flash` aponta para DeepSeek-V4.1-Flash-1017 e que o nome legado
`deepseek-v4-flash` ainda é aceito e cobrado no preço Flash. Sem mudança no pico:
0.30 / 0.006 / 1.20, `pricing_mode: conservative_peak`.

## 7. Staging, somente leitura (R0(b), 2026-11-13)

`app.pricing_versions` (version_id | sha256 | observed_at | max_age_seconds):

```
spec191-smoke     | 3f62239b…f53e99 | 2026-10-08 | 86400
spec197-restore   | 3f62239b…f53e99 | 2026-10-08 | 31536000
spec197-restore-b | 3f62239b…f53e99 | 2026-10-08 | 31536000
```

`app.image_price_profiles` (profile_id | pricing_version_id | model | expires_at):

```
spec197-staging-portrait | spec197-restore-b | gpt-image-2-2026-04-21 | 2026-12-14
staging-326-portrait     | spec197-restore-b | gpt-image-2-2026-04-21 | 2027-01-24
staging-326-scene        | spec197-restore-b | gpt-image-2-2026-04-21 | 2027-01-24
```

Os três profiles ainda não venceram. As três `pricing_versions` têm o hash do card LLM de
08/10: depois de trocar o card, é preciso linha nova e profiles novos (Etapa 4, feita pelo
coordenador ou pelo dono, não pelo executor).
