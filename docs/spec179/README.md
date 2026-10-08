# SPEC-179 — pré voo do experimento target/loot

Estado: primeiro live interrompido após 17 chamadas; recuperação restrita em
preparação. Ainda não há score A/B completo, revisão de resultado ou promoção.

## Corpus experimental

- 14 casos: 10 de target, 4 de loot_context.
- Hash SHA-256 do JSONL: `748ab52175a9178aab7d6e14c32c49366abfb77d80eb63641e9377ca7fd89034`.
- 12 representáveis e 2 não representáveis (`target.over20` por 21 alvos;
  `target.missing_id` por ator sem ID canônico).
- Mínimo corrigido: 25 chamadas externas (A e B nos 12 representáveis; A no
  caso com mais de 20 alvos; zero no gate Python do ator sem ID). A reserva de
  US$ 0,01 por chamada é uma regra
  de parada, não custo real informado pelos provedores.
- IDs de NPC do corpus usam entidades existentes no grafo; aliases e inimigos
  de runtime só entram se presentes e visíveis na cena.

O corpus não integra a regressão protegida. Hash e commit do corpus precisam
estar congelados antes da primeira chamada Jev. O teto da SPEC-178 foi
específico daquela rodada e não autoriza esta execução.

## Primeiro live e recuperação

- Run `SPEC-179-20261008T001825Z-cbedc714`, raw em
  `evals/runs/jev-target-loot/20261008T001750Z/raw.json` (gitignored), SHA-256
  `110e11597c79985b0b64a006ca09043a4e57e1a83ea6ee9caab674e3974ea836`.
- 17 chamadas externas, 8 pares concluídos e um fallback CLASSIFY para >20
  alvos. O runner interrompeu em `target.missing_id` porque exigia tentativa
  CLASSIFY mesmo quando o router resolveu por gate Python determinístico.
- A verificação offline `_eligible` confirmou `storyteller` por gate nesse caso;
  os quatro casos de loot restantes alcançam CLASSIFY. A recuperação usa o raw
  anterior imutável, preserva a falha original, valida o ledger de 17 chamadas
  e necessita mais 8 chamadas para os quatro pares de loot. O teto aprovado de
  40 chamadas/US$ 0,40 vale para a soma das tentativas.
- A revisão Sol independente aprovou a retomada única após exigir hash
  pré-registrado do raw e diff Git restrito à instrumentação/evidência
  (`handoffs/SPEC-179-SOL-recovery-review.md`). Focados: 20/20; Ruff verde.
- Suíte completa da recuperação: **1.956 passed, 35 skipped, 15 deselected**
  em 219,42 s.

## Guardas do runner

O runner rejeita checkout sujo, hash divergente, overrides de provider/mock e
orçamento abaixo do mínimo. Ele filtra NPCs secretos, ausentes, mortos e
participantes escondidos do jogador, além de recusar conflito de identidade
canônica. Acima de 20 targets, registra `unrepresentable` e a decisão do router
atual como fallback, sem chamar Jev nem truncar as opções. As respostas e
tentativas observadas são persistidas antes do score; uma falha de
autenticação, quota ou custo bloqueia a rodada mantendo o registro disponível.

Produção e régua protegida permanecem sem alterações.

## Verificação offline

- 17 testes focados verdes; Ruff verde.
- Suíte completa no commit de freeze: **1.953 passed, 35 skipped,
  15 deselected** em 181,70 s.
- Revisão Sol independente: **APPROVED técnico offline** após correções de
  identidade, visibilidade relativa, seleção de aliado e preservação de raw
  (`handoffs/SPEC-179-SOL-offline-review.md`).
- Project Index regenerado do source e verificado como `fresh`; não foi usado
  para gerar candidatos.
