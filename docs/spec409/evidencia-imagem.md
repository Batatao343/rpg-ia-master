# SPEC-409 — evidência do card de imagem (R1.1)

Card novo: `data/pricing/image_rate_card_2026-11-13.json` (`observed_at` 2026-11-13). Leitura feita pelo
coordenador em 2026-11-13; trechos completos em `fontes.md` § 1.

**Preço (https://developers.openai.com/api/docs/pricing, aba Standard, tabela Images, "per 1M tokens"):**

```
gpt-image-2 | Image | $8.00 | $30.00 | $2.00
gpt-image-2 | Text  | $5.00 | -      | $1.25
```

- `text_input_per_million` 5.00, `image_input_per_million` 8.00, `image_output_per_million` 30.00:
  iguais ao card de 12/10. Nenhum preço mudou.
- Mudou a derivação: em 12/10 o Standard de entrada era derivado do Batch (2.50/4.00 x 2); agora a página lista
  o Standard direto. O campo `derivation` do JSON foi reescrito.
- Cache: a página só concede desconto de cache na Responses API; o produto usa a Images API direta
  (`cached_input_discount: false`).

**Descontinuação (https://developers.openai.com/api/docs/deprecations e página do modelo):**

```
gpt-image-2, gpt-image-2-2026-04-21 — Notice date: Nov 10, 2026 — Shutdown: Feb 10, 2027
Replacement: gpt-image-2.6-sunburst or gpt-image-2.6-flare
```

Decisão (coordenador, 2026-11-13, por delegação do dono): o snapshot segue servido com o mesmo id e preço
publicado até 2027-02-10, então o card é renovado para o **mesmo** `model` (casa com
`image_price_profiles.model`). Trocar para `gpt-image-2.6-*` é decisão de produto e vira spec própria, com
prazo 2027-02-10. O `derivation` registra as duas datas.
