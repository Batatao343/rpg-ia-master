# Playtest comerciante pós-upgrade — 2026-08-20

## Resultado

Cinco campanhas MockLLM independentes, seeds 2201–2205, completaram **1.000 de
1.000 turnos** após a atualização do lock (incluindo FastAPI, LangChain e
LangGraph). O agregado teve zero exceção, zero violação `error`, zero warning de
invariante, zero erro de observabilidade, 38 transações bem-sucedidas e restock
observado nas cinco campanhas.

| Seed | Run | Turnos | Transações | Mercados | Regiões | Restocks |
|---:|---|---:|---:|---:|---:|---:|
| 2201 | `20260820-100653-360446` | 200 | 6 | 3 | 2 | 1 |
| 2202 | `20260820-100708-169544` | 200 | 8 | 5 | 4 | 1 |
| 2203 | `20260820-100722-742002` | 200 | 8 | 5 | 4 | 1 |
| 2204 | `20260820-100736-252318` | 200 | 8 | 5 | 4 | 1 |
| 2205 | `20260820-100749-180819` | 200 | 8 | 5 | 4 | 1 |

Todas misturaram comércio, exploração, quest, social e sobrevivência. O perfil
chegou ao nível 5 em todas as seeds; o ouro final variou de 374 a 547, sem saldo
negativo, duplicação de item ou quebra de conservação.

## Achado e correção

O run 2201 registrou um `WinError 5` ao substituir atomicamente
`saves_playtest/runtime/npc_database.json` sob OneDrive. O turno continuou, mas o
catálogo poderia perder aquela ficha gerada. A causa era assimetria: saves já
usavam retry exponencial para locks efêmeros; `LocalRuntimeCatalogStore` e
`FileBlobStore` faziam um único `os.replace`.

A correção adicionou o mesmo retry limitado aos adapters locais e o teste
`test_atomic_json_repete_replace_bloqueado_temporariamente`, que injeta dois
`PermissionError` antes do sucesso. A seed 2201 foi repetida por mais 200 turnos
no run `20260820-100907-737162`: zero erro/violação e nenhum novo aviso de NPC DB
ou `WinError`.

## Conclusão

O aceite offline do comerciante permanece verde após o upgrade. O único item da
spec ainda aberto é 1×200 com LLM real, deliberadamente opt-in por custo e quota;
ele não foi simulado nem declarado concluído neste relatório.
