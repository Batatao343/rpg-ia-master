# Relatório de cobertura — Mundo Vivo (`conflito-17`)

Data: 2026-08-02  
Status: aceito

## Resultado executivo

| Frente | Antes | Depois | Meta | Resultado |
|---|---:|---:|---:|---|
| Cartas de jogador | 80 | **153** | ≥150 | ✅ |
| Cartas de inimigo | 19 | **40** | ≥40 | ✅ |
| Criaturas | 84 | **124** | ≥120 | ✅ |
| Criaturas novas | 0 | **40** | ≥40 | ✅ |
| NPCs curados do lote | 0 | **36** | ≥30 | ✅ |

As 15 combinações classe×subclasse possuem **5–6 Cartas próprias** e ao menos
uma Superior. Cada Postura recebeu no lote novo ao menos **2 Reações** e **2
Utilitárias**. As guardas de assinatura de Carta e criatura não encontraram
duplicata pura.

## Cobertura regional de criaturas

| Região | Total | Lacaio | Padrão | Elite | Chefe | Nomeado |
|---|---:|---:|---:|---:|---:|---:|
| Aethelgard | 11 | 3 | 1 | 7 | 0 | 0 |
| Brekmar | 10 | 4 | 1 | 4 | 1 | 0 |
| Costa Negra | 9 | 4 | 1 | 3 | 1 | 0 |
| Deserto de Zhur | 11 | 2 | 1 | 5 | 3 | 0 |
| Floresta dos Sussurros | 9 | 4 | 1 | 4 | 0 | 0 |
| Montanhas Afiadas | 15 | 5 | 1 | 9 | 0 | 0 |
| Nova Arcádia | 18 | 5 | 1 | 8 | 3 | 1 |
| Ophidia | 7 | 1 | 1 | 4 | 1 | 0 |
| Pântano da Melancolia | 11 | 4 | 1 | 5 | 1 | 0 |
| Pradaria das Ruínas | 16 | 5 | 1 | 10 | 0 | 0 |
| Selva de Xylos | 9 | 2 | 1 | 5 | 1 | 0 |
| Skallgard | 13 | 5 | 1 | 4 | 3 | 0 |

Todas as regiões-hub superam seis criaturas e contêm Lacaio + Elite/Chefe.
Ophidia, a maior lacuna do baseline (3 criaturas, nenhuma Lacaio), passou para
7 com Lacaio, Padrão, Elite e Chefe.

## NPCs

Foram adicionados **3 NPCs públicos curados em cada um dos 12 hubs**. Cada
documento tem `home_location_id`, papel, facção declarada, gancho público,
entidade canônica e aresta `located_in`. A camada de traços continua sendo
derivada deterministicamente por `npc_layers`, sem duplicar mecânica nos dados.
O Codex foi reindexado no Jina (2.239 chunks); consulta por `Irena Prego-Frio`
recuperou papel, facção e gancho do documento novo.

## Verificação

- `uv run python scripts/content_report.py`: matrizes completas impressas.
- `uv run python scripts/validate_content.py`: **0 erros, 0 avisos**.
- `uv run pytest`: **1358 passed, 1 skipped, 14 deselected**.
- Reindex: lore e rules atualizados; consulta RAG dos dois índices verde.

## Smoke real de experiência

Run aceita: `20260803-025211-710980`, perfil explorador, seed 1717:

- 3/3 turnos, 4 locais, três regiões atravessadas (Nova Arcádia → Pradaria das
  Ruínas → Montanhas Afiadas/A Boca);
- `mock=false`, 0 erros, 0 violações, 18 requests Groq, 16 sucessos de rede e
  custo estimado de **US$ 0,010528**;
- um encontro real iniciou e revelou `Postura de Muralha` sem vazar o restante
  do bestiário.

Smoke real direcionado, sobre o save isolado da run:

- `Guardião de Basalto` foi encontrado pelo ID curado
  `mon_guardiao_basalto` e carregou as Cartas `bst_eco_montanhas`,
  `bst_saliva_paralisante`, `bst_postura_muralha` e a reação defensiva;
- `Brunna Ponte-Alta` entrou pela rota NPC e teve memória por sessão gravada;
- uma saída Groq inválida para `PreparedScene.positions` foi absorvida pelo
  fallback determinístico, sem exceção nem perda do encontro.

Uma tentativa anterior de 20 turnos (`20260803-014405-602783`) não chegou a
abrir campanha e ficou sem progresso observável; foi terminada e não conta como
evidência. O smoke foi reduzido e fixado no Groq com timeouts/tetos rígidos para
testar o conteúdo novo sem mascarar essa ocorrência operacional.
