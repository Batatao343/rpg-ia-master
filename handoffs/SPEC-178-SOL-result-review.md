# SPEC-178 — revisão Sol independente do resultado A/B

Data local: 2026-10-05. Revisor: `/root/spec176_reviewer`, Sol High,
read-only. Decisão: **APPROVED** como evidência de desenvolvimento/regressão,
sem promoção de Jev.

## Integridade

- Raw SHA-256 `590876391dd9a97aaad3ea147a672b7368ed3ba3af8eaa00b2380eb3dbaa22`;
  summary SHA-256 `7fcff90f9d73d190154ccf2d64dc2fe347bb9ad3b9013996f25f8ef0c4c958b`.
- Produto limpo no commit `ec68012d5291ccd5428053b5dc76f6694421334d`;
  corpus protegido permaneceu no hash aprovado.
- Três réplicas de 21/16/16 linhas, 48 pares elegíveis, cinco gates Python.
  Raw foi persistido antes do scorer. A tentativa anterior bloqueada foi
  preservada, sem indício de descarte após observar score.
- `_candidate` não inclui `expected`/`oracle`; CLASSIFY recebeu a ação via
  `RoutingAdapter`, Jev recebeu DTO mínimo com informação equivalente.
- 98 chamadas neste run: 49 DeepSeek `deepseek-v4-flash` e 49 Jev
  `jev-1.13.0`; nenhum fallback ou erro.

## Resultado conferido independentemente

| Recorte | CLASSIFY | Jev |
|---|---:|---:|
| Pipeline completo | 21/21 | 20/21 |
| Elegíveis, 3 réplicas | 48/48 | 46/48 |
| Latência p50/p95 elegíveis | 1367,5/1607,45 ms | 265,5/319,65 ms |

Confusion matrix e percentis foram recalculados e coincidem com o resumo.
As duas divergências são o mesmo caso `routing.npc.corvo.case` nas réplicas 1
e 3. Probabilidades válidas, sem erro de parse oculto. Usage está disponível;
**custo real não foi reportado**, portanto o gasto monetário não é certificado.

O usuário autorizou teto total de 120 chamadas/US$ 1,20 após a recarga da
DeepSeek. Quatro chamadas ocorreram antes do run, 98 neste run, 102 no total;
restam 18. A reserva monetária do runner não é medição de cobrança.

O revisor não editou arquivos, não acessou segredos e não fez chamadas externas.
Não é requisito Jev superar o CLASSIFY para concluir esta spec; produção e
promoção permanecem fora de escopo.
