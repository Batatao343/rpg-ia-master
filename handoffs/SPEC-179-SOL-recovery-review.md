# SPEC-179 — revisão Sol independente da retomada

- Reviewer: `/root/spec176_reviewer`, Sol High; executor: `/root`, Sol High.
- Decisão: **APPROVED técnico offline para uma retomada única**. O resultado
  completo ainda exige revisão independente posterior.
- Primeiro raw imutável: `evals/runs/jev-target-loot/20261008T001750Z/raw.json`,
  SHA-256 `110e11597c79985b0b64a006ca09043a4e57e1a83ea6ee9caab674e3974ea836`.
- Causa confirmada: `target.missing_id` vai a `storyteller` por gate Python,
  com zero chamadas CLASSIFY. A instrumentação inicial parou erroneamente após
  17 chamadas, sem score completo.
- A retomada exige hash aprovado do raw, commit original ancestor do commit
  novo, diff limitado a runner/testes/spec/docs/Project Index, checkout limpo,
  mesmo corpus/opções/ordem, prefixo pareado íntegro e ledger idêntico às
  tentativas persistidas. Preserva a falha anterior e não repete casos completos.
- Conta aprovada: **17 chamadas anteriores + 8 restantes = 25/40**; reserva
  máxima US$ 0,40 cumulativa. Custo real indisponível.
- Corpus, expected, opções, score, produção e paths protegidos intactos.
  20 testes focados e Ruff verdes no snapshot revisado.
