# Revisão do roteiro — rpg-ia-master

Revisão técnico-pedagógica de `roteiro.json` / `roteiro.md`. O conteúdo foi editado nas fontes `p1.py`…`p5.py` (scratchpad `roteiro_src/`) e regerado com `build.py`, então md e json saem do mesmo ponto. As fontes de verdade foram os seis relatórios `explore_0*.md`; nos pontos de dúvida, a verificação foi feita direto no código (`llm_setup.py`, `state.py`, `services/*`, `data/cards/*`, `pyproject.toml`, `specs/`).

## Números

| | Antes | Depois |
|---|---|---|
| Capítulos | 19 | 19 |
| Cenas | 193 | 239 (+46 novas) |
| Palavras de narração | 12.000 | 15.734 |
| Duração estimada (150 ppm) | ~80 min | ~105 min |
| Correções factuais/pedagógicas | — | 31 |

Validação: `build.py` (validador embutido) e um validador independente (`scratchpad/validate_roteiro.py`), rodados sobre o `roteiro.json` final, deram **0 erros**. O validador confere chaves do esquema, IDs `cNNsMM` únicos e sequenciais, narração com 40 a 110 palavras e sem símbolos de código, caminhos ou emoji, e limites de cada tipo de visual. Também confere que todo grafo é DAG e que cada capítulo abre com `title` e fecha com recap (`bullets` ou `callout key`).

## Checklist de cobertura (item → cenas)

**Núcleo e grafo**
- Princípios (IA narra / Python resolve, propõe/aplica, guard, guardas de prosa, caminho único) → c02s01–s08
- Turno ponta a ponta, idempotência por action_id, gates 409, log → c03s01–s12, c13s09
- Emboscada no mesmo turno e iniciativa de early-game → c03s11
- Topologia, gate START, arestas condicionais, laboratório → c04s02
- Modo sequencial e concorrente (no-go SPEC-143) → c04s03
- GameState e reducer (só `messages` acumula) → c04s04
- action_guard: fases do ator, regex de recuperação, transição órfã → c04s05
- campaign_manager: cadência de replan, defesas do plano → c04s06–s07
- dm_router: atalhos, gate de combate, NONE→STORY → c04s08–s09
- storyteller: mecânica antes da prosa, blocos do prompt, quarentena atômica → c03s06–s07, c04s10–s11
- npc_actor: árvore de decisão, "não seja uma Wikipédia", memória observável → c04s12–s13
- combat_agent e loot_agent → c04s14
- archivist e turn_finalizer/recibo → c03s08, c04s15
- Ajudantes (librarian, bestiary, world_simulator, generate_new_npc) → c04s16
- Objetivo público e direção social → c04s17
- Custo de IA por nó → c04s18

**Camada de modelos**
- Tiers, ROUTES, cascata get_llm → c05s02–s04
- RoutedLLM preguiçoso, function_calling, include_raw → c05s05
- Tentativa por candidato, semáforo, regeneração e recuperação local de JSON → c05s06–s07
- Circuit breaker → c05s08
- Timeouts e particularidades de provider → c05s09
- Telemetria (dois hooks) → c05s10
- MockLLM e FallbackLLM → c02s04, c05s11
- RPG_ROUTES, LLM_PROVIDER, flags de mock, concorrência → c05s12

**Mundo, RAG e memória**
- Lore fonte, migração, Codex, visibilidade, overrides → c06s02–s05
- Grafo de entidades (incluindo entities_extra), arestas, componentes → c06s06–s07
- Mapa, interiores, baús; demais catálogos → c06s08–s09
- Escopos de índice, chunking, cadeia de embeddings, índice pinado → c07s02–s05
- Filtro de visibilidade, vetor compartilhado, leitura concorrente → c07s06–s07
- pgvector e busca híbrida → c07s08
- Event sourcing: campos, tipos, validadores, aplicação pura, resolver → c08s02–s05
- Rule engine e cascata com profundidade 2 → c08s06–s07
- Pré-validação → c08s08
- Quests verificáveis → c08s09
- Visões do mundo para o jogador → c08s10
- Memória em 5 camadas, proveniência, validação fail-closed, promoção → c09s02–s06
- Segredos em 3 camadas e o caso Magda → c09s07–s08
- Context builder: orçamento e nota de relevância → c09s09–s11
- NPCs em 3 camadas, traits, anti-carrossel, identidade/aliases → c09s12–s14
- Crônica, compressão e busca RRF → c09s15

**Combate v4**
- Pilha de uma rodada e ficha v4 → c10s02–s03
- 2d10, vantagem e crítico (código fiel) → c10s04
- Iniciativa por lado e surpresa → c10s05
- Testes gerais Ímpeto/Presságio → c10s06
- Exemplos numéricos reais → c10s07–s08
- Dano R8, Ferimentos, regiões, agravamento → c10s09–s10
- Cena, zonas, engajamento, ocultação, manobras → c10s11
- Reações e ataque de oportunidade → c10s12
- IA tática, provocação, ordens a companheiros → c10s13–s14
- Morte rica, rendição, golpe não letal, fim do conflito → c10s15–s16
- Fuga/chase, limites, abandono de companheiro → c10s17–s18
- Abismo, preparação de encontro, resumo canônico → c10s19
- Origem de combate → c10s20
- Conhecimento revelado do bestiário → c10s21
- Aliados de cena → c12s13
- Laboratório de combate → c12s14

**Cartas, Posturas e progressão**
- Anatomia, acervo/preparação, frequências, Ruptura, evolução → c11s02–s04
- Volume do catálogo e paridade → c11s05
- Entropia, Carga, 5 Posturas, gatilhos, consequências → c11s06–s08
- HANDLED_KINDS → c11s09
- Cartas de Virtude, Maestria, Cartas de inimigos → c11s10
- Utilitárias, passivas, itens vivos, luz → c11s11
- XP, níveis 1–20, subclasse, Maestria, Ápice → c11s12–s13
- Criação, bônus de early-game, montagem da ficha → c11s14–s15

**Mundo sistêmico**
- Relógio, viagem, fog of war, interiores, descanso → c12s02–s03
- Encontros, orçamento, percepção, armadilhas, rastros → c12s04–s06
- Clima global e luz → c12s07
- Facções (ritmo, ascensão, intel, reputação) → c12s08
- World simulator → c12s09
- Economia, mercadores, forja, itens únicos, saque → c12s10–s11
- Exploração, baús, ecologia → c12s12
- Party e inventário/equipamento → c12s13
- Checkpoints → c12s14, c13s07–s08

**API e persistência**
- Rotas, middlewares, rate limit → c13s02–s03
- SSE com worker dono do turno → c03s10, c13s04
- GameResponse → c13s05
- Saves atômicos, schema v8, migrações, arquivamento → c13s06
- Tela de morte e metatempo → c13s07–s08
- Log rpg.turn e métricas → c13s09
- Histórico de apresentação → c13s10
- Transferência preview-first de saves → c13s11
- CLI → c13s12

**Frontend e arte**
- Telas, wizard, prólogo e a lição do schema → c14s02–s04
- HUD de 8 abas, combate tático, pendingOperation e retomada → c14s05–s07
- SaveScreen, modais, onboarding → c14s08
- Tema, mobile, reduced motion, F01–F16/axe → c14s09
- Arte 8A (catálogo, primeira aparição) → c15s02–s03
- Arte 8B (orçamento e pipeline) → c15s04–s05

**Infraestrutura local-first**
- Portas, adapters e perfis → c16s02
- Claim → grafo → commit, lease e fencing, exactly-once → c16s03–s05
- Outbox de memória → c16s06
- Schema Postgres, RLS, filtro por dono → c16s07
- Auth, cookies, CSRF → c16s08
- Workers e fence de jobs → c16s09
- Blob storage → c16s10
- Fila, observabilidade, backup/RTO → c16s11
- Runbook e scripts de operação → c16s12
- Readiness G0–G7 → c16s13

**Qualidade e processo**
- Pirâmide de garantias, suíte e markers → c17s02–s03
- Harness de 14 perfis, invariantes, cenários, relatório/transcript → c17s04–s06
- Modo real, fail-closed, watchdog, preflight, presets, lock, manifesto → c17s07–s08
- Matriz A/B → c17s09
- Evals SPEC-165..176: régua protegida, suítes, lock por hash, LF/CRLF, baseline v1, contratos reais → c17s10–s12
- Project Index e benchmark v6 → c17s13
- Workflows de CI → c17s14
- Ciclo de spec, IDs/índice, executor ≠ revisor (AGENTS.md) → c18s02–s04
- /qa, /wrap-up, autoria de conteúdo → c18s05–s06
- ROADMAP das fases 0 a 11 → c18s07–s08
- Linha do tempo e playtests marcantes → c18s09–s11
- Arestas, limitações, pacote SPEC-177..198, próximos passos → c19s02–s08

## Correções feitas (31)

1. c01s05: a narração começava cortada em minúscula; foi reescrita.
2. c02s04: o snippet de código foi trocado pelo trecho real de `storyteller.py`.
3. c03s02: "seis fases" passou a "sete", que é o número de passos do fluxo.
4. c03s12: o recap dizia "só duas chamadas de modelo". Pelo próprio exemplo houve quatro (simulador, designer de NPC, narrador, arquivista).
5. c04s04: no snippet, `next: str` passou a `Optional[str]`, como no `state.py`.
6. c04s05: incluído o reparo de transição órfã feito pelo action_guard.
7. c04s14: a narração não citava a cicatriz, que já aparecia na tabela; foi acrescentada.
8. c05s06: "regenera até 3 vezes" passou a "até 3 gerações no total", com a tentativa de JSON local antes.
9. c05s07: mesma correção de "gerações".
10. c06s07: o JSON de componentes ganhou o campo `successor_id` real.
11. c06s06: incluídas as 82 entidades curadas de `entities_extra`.
12. c06s09: "facções jogáveis" passou a "facções ativas"; elas não são jogáveis.
13. c09s06: a narração começava cortada; foi reescrita.
14. c09s09: a tabela emparelhava pesos de nota com cotas de seção, o que estava errado. Ficou só com as cotas, e os pesos foram para uma cena própria (c09s10).
15. c10s08: o texto sugeria que 14 contra esquiva 13 erraria. Corrigido: acertaria de qualquer forma, e o crítico acerta sempre.
16. c10s12: incluído que, hoje, uma reação bem-sucedida só concede postura protegida.
17. c10s14 (nova): a chance de provocação foi verificada no código. Chega a no máximo 80% com a configuração atual, não 90%.
18. c10s19: o resumo canônico tem 22 campos, não 21 (narração e visual).
19. c11s03: "lugar seguro" passou a "perigo até 3, fora de zona apex".
20. c11s05: os números do catálogo estavam defasados (16 por Postura). Hoje são 30 a 31 por Postura, 153 no total, 80 tardias dos níveis 9 a 20 (15 Ápices) e 40 de inimigos.
21. c11s08: a Dependência do Arcanista também exige Carga moderada ou maior.
22. c11s13: "a cada nível uma Carta" passou a "níveis 2–19; evolução a partir do 4" (narração e visual).
23. c11s11 (nova, a partir do achado): as Cartas passivas não têm consumidor no motor v4 (`learned_passives` retorna `[]`). As utilitárias estão fiadas via `utility_context_block`.
24. c12s03: na tabela de descanso, "graves e críticos: kit" passou a "grave: kit; crítico: Médico".
25. c12s13: corrigida a frase confusa sobre itens e espaços de equipamento.
26. c12s15: o recap passou a incluir as facções.
27. c13s02: a tabela de rotas ganhou operations, DELETE, crônica e arte.
28. c13s07: a narração começava cortada. O nó "duas estabilizações falham" passou a "morte real confirmada", porque a morte também pode vir sem aliado ou de um descanso fatal.
29. c14s01: a narração começava cortada; foi reescrita.
30. c16s07: o texto dizia que o papel da API não contorna a RLS. Corrigido: a barreira primária é o filtro explícito por dono, e a RLS é a segunda camada. O coordenador não faz `SET ROLE`.
31. c17s03: o bloco do `pyproject.toml` foi alinhado ao arquivo real, com `browser_local` e as descrições literais truncadas.

## Cenas adicionadas (46)

- c03s11 Variante: a emboscada
- c04s03 Sequencial ou concorrente
- c04s16 Os ajudantes dos agentes
- c04s17 Objetivo público e direção social
- c04s18 Quanto custa um turno
- c05s12 Trocar rotas sem deploy
- c07s08 No perfil Postgres: busca híbrida
- c08s10 O que o jogador enxerga do mundo
- c09s10 A nota de cada fato
- c09s14 Uma identidade, muitos nomes
- c10s05 Iniciativa por lado e surpresa
- c10s06 Testes gerais: Ímpeto e Presságio
- c10s14 Provocação e ordens a companheiros
- c10s18 Fuga: limites e quem fica para trás
- c10s20 Por que esta luta começou
- c10s21 O bestiário que aprende
- c11s10 Cartas de Virtude e de inimigos
- c11s11 Passivas, utilitárias e itens vivos
- c11s15 Como a ficha nasce
- c12s08 Facções que avançam sozinhas
- c12s09 Os ecos do mundo
- c13s09 O log de cada turno
- c13s10 Histórico estável para o cliente
- c13s11 Mover saves com segurança
- c13s12 Jogar no terminal
- c14s08 Saves, modais e primeiros passos
- c14s09 Tema, celular e acessibilidade
- c15s05 O pipeline da arte dinâmica
- c16s08 Identidade, cookies e CSRF
- c16s09 Trabalhadores e a cerca dos jobs
- c16s10 Arquivos e armazenamento
- c16s12 Operar o laboratório
- c16s13 Prontidão G0 a G7
- c17s06 Cenários dirigidos e relatórios
- c17s08 Preflight, presets e trava
- c17s11 A régua travada por hash
- c17s12 Contratos reais e linha de base
- c17s14 Os workflows de integração contínua
- c18s04 Executor e revisor
- c18s06 Autoria de conteúdo
- c18s07 O ROADMAP, fases 0 a 5
- c18s08 O ROADMAP, fases 6 a 11
- c18s11 Playtests que mudaram o projeto
- c19s05 Mais arestas, observadas no código
- c19s06 Limitações conhecidas
- c19s07 O pacote de produto em detalhe

## O que ficou de fora e por quê

- **Conteúdo do lore** (eras, raças, NPCs específicos, segredos). O roteiro explica o mecanismo, não a ficção. Além disso, a regra do projeto proíbe ler os arquivos de lore inteiros, e citar segredos `hidden` num vídeo seria vazamento.
- **Lista completa de invariantes, de métricas Prometheus, de colunas das migrations e de endpoints de auth**. Cada uma tem cena com exemplos representativos. A lista exaustiva estoura os limites visuais e não ajuda o espectador.
- **Detalhes de baixo nível**, como cooldown de controle tático, efeitos de dano corrosivo/perfurante, fórmula de ouro inicial (50 × nível), portas do `supabase/config.toml` e o placeholder "AGUARDANDO ARTE" (não publicado). São precisos, mas muito granulares para o vídeo.
- **Benchmarks R28/R29 e versões v2–v5 do benchmark do Project Index**. Só o resultado relevante entrou: o no-go do modo concorrente e o v6 confirmatório.
- **Histórico pré-cutover** (árvore de 101 habilidades, combate d20+AC, "O Saque"). Aparece só como contexto em c10s01 e c11s11, porque foi substituído.
