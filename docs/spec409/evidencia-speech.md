# SPEC-409 — evidência do card de STT (R1.2)

Card novo: `data/pricing/speech_rate_card_2026-11-13.json` (`observed_at` 2026-11-13). Leitura do
coordenador em 2026-11-13; trechos em `fontes.md` §§ 2–3. Nenhum preço nem teto mudou.

**Groq `whisper-large-v3-turbo`** (https://console.groq.com/docs/speech-to-text):
`$0.04 (Cost Per Hour)`; "Minimum Billed Length: 10 seconds".

- `usd_per_hour` 0.04, `minimum_seconds` 10.
- `max_cost_usd`: teto de 60 s (`services/speech_pricing.py`, clipes <= 60 s):
  0.04 / 3600 x 60 = 0.0006666... -> arredondado para cima em 9 casas = **0.000666667**.

**OpenAI `gpt-4o-mini-transcribe`** (https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe;
página de pricing confirma `$1.25 | $5.00`): "Audio tokens: Input $1.25 / 1M · Output $5 / 1M";
"16,000 context window · 2,000 max output tokens".

- input 1.25, output 5.00 por milhão; tetos 16000 / 2000 tokens.
- `max_cost_usd` = (16000 x 1.25 + 2000 x 5.00) / 1e6 = 0.020 + 0.010 = **0.030000000**.

As duas contas são conferidas por `tests/test_pricing_card_files.py::test_speech_card_max_cost_matches_the_ceilings`.
