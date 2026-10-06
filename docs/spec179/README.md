# SPEC-179 — pré voo do experimento target/loot

Estado: preparação offline. Não houve chamada externa da SPEC-179, resultado
A/B, revisão de resultado ou promoção.

## Corpus experimental

- 14 casos: 10 de target, 4 de loot_context.
- Hash SHA-256 do JSONL: `748ab52175a9178aab7d6e14c32c49366abfb77d80eb63641e9377ca7fd89034`.
- 12 representáveis e 2 não representáveis (`target.over20` por 21 alvos;
  `target.missing_id` por ator sem ID canônico).
- Mínimo previsto: 26 chamadas externas (A e B nos 12 representáveis; apenas
  A nos dois casos de fallback). A reserva de US$ 0,01 por chamada é uma regra
  de parada, não custo real informado pelos provedores.
- IDs de NPC do corpus usam entidades existentes no grafo; aliases e inimigos
  de runtime só entram se presentes e visíveis na cena.

O corpus não integra a regressão protegida. Hash e commit do corpus precisam
estar congelados antes da primeira chamada Jev. O teto da SPEC-178 foi
específico daquela rodada e não autoriza esta execução.

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
- Revisão Sol independente: **APPROVED técnico offline** após correções de
  identidade, visibilidade relativa, seleção de aliado e preservação de raw
  (`handoffs/SPEC-179-SOL-offline-review.md`).
- Project Index regenerado do source e verificado como `fresh`; não foi usado
  para gerar candidatos.
