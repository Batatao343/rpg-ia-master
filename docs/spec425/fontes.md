# SPEC-425 — fontes externas

Coletadas pelo coordenador em **2026-11-22** (só páginas oficiais da OpenAI; blogs de terceiros
descartados). Trechos em inglês, como na página. O que está marcado **(resumo)** veio de extração
automática de página longa, não de texto literal: conferir antes de virar requisito.
Leitura anterior das mesmas páginas (13/11): `docs/spec409/fontes.md` §1.

## 1. Desligamento — https://developers.openai.com/api/docs/deprecations

```
| Feb 10, 2027 | gpt-image-2, gpt-image-2-2026-04-21 | Deprecated | gpt-image-2.6-sunburst or gpt-image-2.6-flare | Nov 10, 2026 |
Deprecated. OpenAI has announced the model's retirement. You can still use it until its shutdown date.
Shutdown. The model no longer accepts requests through the standard API.
Specialized variants of generally available models and image generation models: At least 3 months.
```

A página não diz qual erro a API devolve depois do desligamento.

## 2. Modelos novos

- https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst
- https://developers.openai.com/api/docs/models/gpt-image-2.6-flare

```
Sunburst: Image generation and editing for detailed visual work
          Use it for detailed compositions and image editing workflows.
Flare:    Image generation and editing for fast iteration
          Use it for interactive image generation and editing workflows.
Default snapshot: gpt-image-2.6-sunburst      (única snapshot listada)
Default snapshot: gpt-image-2.6-flare         (única snapshot listada)
See your organization's limits for the rate limits that apply to your account.
```

Endpoints (iguais nas duas páginas): `v1/images/generations` Supported; `v1/images/edits`
Supported; `v1/responses` Not supported; `v1/batch` Not supported.

Não está nas páginas dos modelos: snapshot datada, tabela de limite por tier, tamanhos, valores de
`quality`, formatos de saída, transparência.

## 3. Modelo atual — https://developers.openai.com/api/docs/models/gpt-image-2

```
Status: Deprecated
gpt-image-2-2026-04-21 — Deprecated        (snapshot padrão)
Rate limits: Build 250,000 TPM / 20 IPM · Launch 3,000,000 TPM / 150 IPM · Grow 8,000,000 TPM / 250 IPM
```

Endpoints: generations, edits e Batch Supported.

## 4. Preço — https://developers.openai.com/api/docs/pricing

Standard, por 1M tokens (as três linhas são iguais):

```
gpt-image-2.6-sunburst | Image | $8.00 | $30.00 | $2.00
gpt-image-2.6-sunburst | Text  | $5.00 | -      | $1.25
gpt-image-2.6-flare    | Image | $8.00 | $30.00 | $2.00
gpt-image-2.6-flare    | Text  | $5.00 | -      | $1.25
gpt-image-2            | Image | $8.00 | $30.00 | $2.00
gpt-image-2            | Text  | $5.00 | -      | $1.25
Cached input rates for GPT Image 2 and GPT-Image-2.5 only apply to images generated with the Responses API.
For image generation cost estimates, use the calculator in the image generation guide
```

A aba Batch lista preço para os dois 2.6 (Image $4.00 / $15.00 / $1.00), mas as páginas dos
modelos dizem `v1/batch` Not supported: **contradição na fonte**. O projeto não usa Batch.

Não há tabela de preço por imagem nem de tokens por tamanho/qualidade para 2.6 ou gpt-image-2
(a calculadora do guia é interativa). **O preço por token não mudou; o custo por imagem só se
sabe medindo `usage` em chamada real.**

## 5. Guia — https://developers.openai.com/api/docs/guides/image-generation

Literal:

```
GPT-Image-2.6 includes Sunburst for detailed visual work and Flare for fast iteration.
Both models support complexity control, markup-guided edits, SVG output, and animated GIF output through the Image API.
The supported complexity levels for Sunburst and Flare are low, medium, and high. If you omit complexity, both models use high.
The separate quality setting controls rendering quality.
Adjusting complexity has no separate fee.
The Images API user parameter is deprecated. Send the same identifier as safety_identifier instead.
To ensure these models are used responsibly, you may need to complete the API Organization Verification from your developer console before using GPT Image models.
```

**(resumo)**, não literal:

- `quality` em Sunburst/Flare: `low`, `medium`, `high`, `xhigh`, `max`, `auto` (padrão `auto`).
  No gpt-image-2: `low`, `medium`, `high`, `auto`.
- Tamanhos recomendados: `1024x1024`, `1536x1024`, `1024x1536`; tamanho livre com lados múltiplos
  de 16, proporção entre 1:3 e 3:1, lado ≤ 3840 px.
- Padrões: `output_format` `png`, `moderation` `auto`; bloqueio pode voltar
  `error.code = "moderation_blocked"`.
- `input_fidelity`: no gpt-image-2, omitir (a API rejeita mudança). Para 2.6 a página não diz.
- Sem número máximo de imagens de referência declarado.
- Os exemplos de código do guia ainda usam `gpt-image-2.5-*`; não há seção "migrar de
  gpt-image-2 para 2.6".

## 6. O que as fontes não respondem (vira medição ou decisão na spec)

1. Tokens de saída por imagem em `1024x1536` e `1536x1024`, `quality: medium`, com o padrão novo
   `complexity: high` (define o custo real e o `usd_per_image` do rate card).
2. Sunburst ou Flare para o estilo gravura da Valoria (qualidade × latência).
3. Limite de imagens por minuto dos 2.6 na conta do projeto.
4. Se `input_fidelity` é aceito e se o parâmetro `user` ainda passa (o guia o dá como obsoleto).
5. Não existe snapshot datada: o id `gpt-image-2.6-sunburst` pode mudar de comportamento sem
   aviso (o projeto hoje fixa `gpt-image-2-2026-04-21`).
