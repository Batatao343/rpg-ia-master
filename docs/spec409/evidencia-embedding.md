# SPEC-409 — evidência do card de embedding (R1.3)

Card novo: `data/pricing/embedding_rate_card_2026-11-13.json` (`observed_at` 2026-11-13).

**ATENÇÃO: o valor vem de FONTE SECUNDÁRIA.** A página oficial https://jina.ai/api-dashboard/pricing foi lida
em 2026-11-13, mas só entregou "We introduced a new pricing model on May 6th, 2025." e os nomes dos pacotes
(Free, Paid, Premium); os valores não vieram (página montada por script). https://jina.ai/embeddings/ também não
mostra preço. O número vem de https://usagepricing.com/blueprint/jina-ai (acesso 2026-11-13; a página diz
"fact-checked on Oct 24, 2026"):

```
Standard (Prototype)  | $50  | 1B tokens  | 0.050 / 1M
Premium (Production)  | $500 | 11B tokens | 0.045 / 1M
```

- `input_per_million` = **0.05** (Standard, o mais alto), igual ao card de 17/10. Outros agregadores citam valores
  menores (alguns US$ 0,02/1M); o card fica no mais alto, que é o conservador.
- O `source` do JSON diz "SECONDARY SOURCE". Quando alguém abrir o painel oficial, conferir e, se divergir,
  renovar o card (arquivo novo).
