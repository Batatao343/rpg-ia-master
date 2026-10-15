# Equivalência de modelos — Codex → Claude Code (SPEC-191 a SPEC-198)

As specs 176–198 foram escritas para execução no Codex, com campos
`EXECUTOR_MODEL`/`REVIEW_MODEL` e o contrato
`docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml`.
Em 2026-10-15 o usuário moveu a execução para o Claude Code e aprovou
explicitamente a substituição abaixo (isso satisfaz a cláusula
"SUBSTITUIÇÃO DE MODELO: proibida sem aprovação explícita do usuário").

| Papel no Codex | Uso original | Equivalente Claude |
|---|---|---|
| Sol (high) | executor/revisor de maior risco | **Opus** (planejamento e revisão independente) |
| Astra (high) | revisor independente adversarial | **Opus** em contexto novo e separado |
| Terra (high) | executor de implementação | **Sonnet** |
| Luna | inventário, coleta de evidência, relatórios | **Haiku** |

Regra operacional definida pelo usuário:

- Opus planeja e quebra cada spec em partes pequenas; nunca delega o
  planejamento.
- Sonnet executa exploração e implementação, inclusive onde o contrato pedia
  Sol como executor.
- Opus revisa cada spec num subagent de contexto independente antes de `done`.
- Haiku cobre tarefas mecânicas (aplicar artefatos verbatim, inventários).
- Cada spec concluída é commitada na `main` e implantada no staging.
