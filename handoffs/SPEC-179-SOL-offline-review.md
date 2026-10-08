# SPEC-179 — revisão Sol independente (offline)

- Reviewer: `/root/spec176_reviewer`, Sol High; executor: `/root`, Sol High.
- Decisão: **APPROVED técnico offline** após duas rodadas de correção.
- Escopo: corpus experimental, opções canônicas, visibilidade, fallback,
  integridade de raw e limite de chamadas. Não houve live call.
- Primeira revisão detectou ID de runtime prevalecendo sobre o grafo, morte e
  ocultação ignoradas, perda de resposta no teto de custo e fallback >20 não
  exercitado. As quatro falhas foram corrigidas e receberam testes focados.
- Segunda revisão detectou aliado ativo com NPC homônimo fora da cena e
  ocultação relativa a outro observador. Ambos foram corrigidos; dois testes
  novos e três regressões verdes na revisão final; Ruff verde.
- Corpus revisado: SHA-256
  `748ab52175a9178aab7d6e14c32c49366abfb77d80eb63641e9377ca7fd89034`.
- Ajuste final de score (contagem de target inválido inclui A nos casos sem
  Choice Jev) e guard de checkout sujo também aprovados; dois testes focados
  verdes na verificação adicional.
- Gates posteriores: suíte completa, freeze commit, budget live e revisão Sol
  do resultado antes de marcar SPEC-179 `done`.
