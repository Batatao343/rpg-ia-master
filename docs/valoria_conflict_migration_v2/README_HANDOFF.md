# Handoff — Migração do Sistema de Conflitos de Valoria

Este pacote é a fonte funcional para a migração do combate de Valoria.

Ele foi reescrito depois da análise do projeto atual. O objetivo não é orientar arquivos, classes, serviços, bancos, schemas ou escolhas internas de arquitetura. O coding agent e o harness devem inspecionar o repositório, identificar os sistemas já existentes e decidir a melhor forma de executar a migração.

## Documentos

1. `01_VALORIA_REGRAS_CONSOLIDADAS_CONFLITOS.md`  
   Fonte canônica das regras de combate, perseguição, Ferimentos, cartas, Abismo e comportamento dos personagens.

2. `02_VALORIA_ESCOPO_DA_MIGRACAO.md`  
   Explica o que já existe no jogo, o que deve permanecer e qual transformação funcional está sendo realizada.

3. `03_VALORIA_CENARIOS_DE_ACEITE.md`  
   Casos comportamentais para orientar a quebra do épico em specs e validar o resultado final sem prescrever implementação.

4. `04_VALORIA_DECISOES_FECHADAS_E_BALANCEAMENTO.md`  
   Lista rápida das decisões que não devem ser reabertas e dos números que podem ser ajustados por playtest.

## Orientação para Claude Code e Codex

Leia os quatro documentos integralmente e, antes de propor specs, analise o projeto atual.

A análise deve identificar o que já existe e pode ser preservado, especialmente os sistemas de mundo, narrativa, bestiário regional, NPCs, party, progressão, itens, loot, memória, persistência, eventos, testes e demais fluxos em funcionamento.

Não trate este pacote como uma ordem para reconstruir o projeto. Ele define comportamento, regras, fronteiras e resultados esperados. A forma de implementação deve ser decidida a partir do código real.

Depois da análise, quebre a migração em specs menores e ordenadas por dependência. Não reabra decisões marcadas como fechadas. Parâmetros de balanceamento podem ser configuráveis e refinados por playtest sem alterar a direção do sistema.
