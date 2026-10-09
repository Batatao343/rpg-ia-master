# SPEC-185 — revisão independente Sol High

- **Parecer:** APPROVED, sem bloqueios no diff final.
- **Review run:** `SPEC-185-SOL-20261009T215654Z`.
- **Modelo/esforço:** Sol / High; revisor distinto do executor Sol High
  autorizado após indisponibilidade de Terra High.

O parecer cobre as fronteiras owner/read-model e atribuição por operação e
`timeline_epoch`. Foram endereçados os achados de autenticação de `/account`,
consulta em lote para histórico, degradação segura, UTC, categoria voice,
valores `bigint`, equivalência acessível do gráfico, associação pós-stream e
distinção entre custo técnico USD e débito Estilhas liquidado.

Gates informados ao revisor: pytest completo verde, quatro E2E Chromium,
Ruff, TypeScript, testes Node e integração PostgreSQL local. A integração do
débito normal de Estilhas permanece fora da SPEC-185; até lá, o custo técnico
por turno pode aparecer enquanto o consumo liquidado fica em zero.
