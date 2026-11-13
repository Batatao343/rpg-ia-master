# SPEC-409 — evidência do card LLM geral (R1.4)

Card novo: `data/pricing/rate_card_2026-11-13.json` (`version` `2026-11-13-v1`, `observed_at` 2026-11-13).
Leitura do coordenador em 2026-11-13; trechos em `fontes.md` §§ 5–6. **Nenhum preço, teto ou `pricing_mode`
mudou** em relação ao card de 08/10 (conferido por `tests/test_pricing_card_files.py`).

| Modelo | input | cache | output | Fonte |
|---|---|---|---|---|
| `groq:openai/gpt-oss-20b` | 0.075 | 0.037 | 0.30 | `console.groq.com/docs/models` ($0.075 / $0.30); cache em `console.groq.com/docs/model/openai/gpt-oss-20b` (Cached Input $0.037) |
| `groq:openai/gpt-oss-120b` | 0.15 | 0.075 | 0.60 | `console.groq.com/docs/models` ($0.15 / $0.60); cache em `console.groq.com/docs/model/openai/gpt-oss-120b` (Cached Input $0.075) |
| `deepseek:deepseek-flash` | 0.30 | 0.006 | 1.20 | `api-docs.deepseek.com/quick_start/pricing/` (pico: miss $0.3, hit $0.006, output $1.2) |
| `deepseek:deepseek-v4-flash` | 0.30 | 0.006 | 1.20 | idem (nome legado ainda aceito e cobrado no preço Flash) |

- Groq: a página de modelos não lista cache; por isso o `source` de cada modelo Groq cita as duas URLs. A unidade
  "por 1M de tokens" não está escrita nas páginas por modelo; sai da conta "13M / $1" -> $0.075/1M.
- DeepSeek: `conservative_peak` = o maior preço publicado (pico 01–04 e 06–10 UTC, seg–sex; fora do pico é metade).
- `max_input_units`/`max_output_units`: sem evidência de mudança (Groq 131072/65536; DeepSeek 1000000/384000).
