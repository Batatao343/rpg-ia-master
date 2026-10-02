# Smoke real do conflito v4 — 2026-07-25

> **Veredito:** execução operacional completa; **aceite funcional reprovado**.
>
> O run `20260725-101933` concluiu 13 campanhas × 30 turnos com LLM real,
> sem erro de turno registrado pelo harness nem aborto. O stderr, contudo,
> registrou cinco `ValidationError` do scanner antes de o fallback funcionar.
> A inspeção do transcrito, dos saves e das fronteiras do motor encontrou ainda
> defeitos bloqueadores que o harness classificou como verde. A spec
> [`conflito-13`](../specs/SPEC-074-conflito-13-cutover-migracao-playtest.md) permanece
> `in-progress`.

## 1. Resumo executivo

O smoke provou quatro pontos positivos:

1. o `deepseek-v4-flash` sustentou uma campanha longa real;
2. os 13 perfis chegaram a 30/30 turnos e persistiram seus artefatos;
3. os cinco structured outputs inválidos que levantaram exceção caíram para o
   Groq e o jogo continuou;
4. a resolução dentro de `run_round` e dos módulos `conflict_*` é, por
   inspeção estática, livre de chamadas LLM.

Ele também encontrou quatro bloqueadores:

1. golpes repetidos na região padrão `torso` podem manter jogador e inimigo
   indefinidamente em Vitalidade 0 e 1/2 Ferimentos Críticos;
2. HP legado e Vitalidade divergem em criação, descanso, level-up, UI,
   telemetria e persistência;
3. o harness escolhe o texto da ação e a `TurnDeclaration` mecânica
   separadamente, de modo que “beber poção” pode executar uma Carta/ataque;
4. `ConflictSummary` é produzido, mas não chega a loot, archivist ou save.
   A narração livre pode contradizer o motor e a contradição vira memória RAG.

Houve ainda regressões importantes: criação de `npc_null`, perda de memória
FAISS de NPC com ID Unicode no Windows, structured output `None` tratado como
sucesso, fatos malformados no archivist e ausência de consequência mecânica
para ameaças narrativas.

## 2. Decisão dos critérios da spec

| Critério da seção 6 | Resultado | Evidência |
|---|---|---|
| Vertical criação → exploração → preparação → conflito → morte/vitória → loot → resumo → retomada | **Parcial / não aceito** | O perfil `combate` percorreu exploração, preparação, 11 rodadas, Ferimento, vitória, loot no turno 25 e retomada nos turnos 26–30. Reação não é observável na telemetria; o resumo canônico não foi consumido nem persistido; ação textual e declaração mecânica divergiram. |
| Zero LLM durante a resolução | **Aprovado com ressalvas** | `run_round`, turno, resolução, dano, cena, reações, perseguição, Cartas e resumo não têm `get_llm`, `with_structured_output` ou `.invoke`. Há LLM antes/depois. Fichas numéricas de inimigo e parâmetros abertos de evento do Abismo ainda podem nascer da LLM e influenciar a resolução. |
| `--all --turns 30 --real`, 12+ campanhas, zero erro | **Executado, mas não aceito** | 13/13 summaries, 13/13 JSONLs, 390/390 turnos, `mock=false`, `aborted_reason=null`, `errors=0`. O resultado é falso-verde: houve soft-lock, divergência HP/Vitalidade, `npc_null` e erro RAG não capturados. |

## 3. Execução e ambiente

### 3.1 Ajuste de provider necessário

A primeira tentativa, em 2026-07-24, ainda usava `deepseek-chat` e recebeu
HTTP 400. MiniMax respondeu 402 por saldo insuficiente e a chave Qwen respondeu
401. Não houve summary ou JSONL confiável nessa tentativa.

O projeto foi atualizado para `deepseek-v4-flash` nos três tiers, com thinking
desabilitado para preservar o comportamento não-pensante anterior, timeout de
90 segundos por candidato e preços atuais no estimador. A mudança acompanha a
[tabela atual de modelos e preços](https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8)
e o [changelog oficial](https://api-docs.deepseek.com/updates/).

Antes do run longo, os testes focados passaram:

```text
uv run pytest tests/test_routing.py tests/test_fase53.py -q
................s..............
```

### 3.2 Sanity real

```powershell
$env:LLM_TIMEOUT_SECONDS = "90"
uv run python -u -m playtest run `
  --profile combate --turns 5 --real `
  --max-requests 0 --max-cost 0.02
```

Run `20260725-101604`:

- 5/5 turnos;
- 0 erro e 0 violação;
- `mock=false`;
- 19 requests DeepSeek registradas e pelo menos 20 reais, contando a criação
  SMART descartada da telemetria no início do turno 1; zero fallback;
- custo estimado de US$ 0,00532;
- p50 18,59s; p95 25,79s.

Limitação: os cinco turnos foram `storyteller`; o perfil não entrou em conflito.
Esse run validou provider e persistência, não a vertical da spec.

### 3.3 Run de aceite

```powershell
$env:LLM_TIMEOUT_SECONDS = "90"
uv run python -u -m playtest run `
  --all --turns 30 --real `
  --max-requests 0 --max-cost 0.05
```

- run: `20260725-101933`;
- janela observada: 10:19:33–11:48:45, cerca de 1h29m;
- limite de custo: US$ 0,05 **por campanha**, máximo teórico de US$ 0,65;
- 13 summaries e 13 JSONLs;
- 390/390 turnos;
- nenhuma campanha abortada;
- `mock=false` em todas;
- 1.110 invokes bem-sucedidos: DeepSeek 1.105, Groq 5;
- pelo menos 1.128 chamadas reais: as 1.110 registradas, 13 criações SMART
  apagadas por `turn_events.clear()` no turno 1 e cinco falhas DeepSeek antes
  do fallback;
- custo estimado registrado: US$ 0,31060;
- p50/p95 globais por turno: 11,38s / 26,01s;
- 75 turnos com conflito ativo;
- quatro perfis entraram em conflito, cobrindo oito encontros: cinco chegaram
  a vitória/loot, três terminaram ativos e nenhum executou fuga;
- 9 eventos aplicados e nenhum rejeitado nos JSONLs;
- 4 avisos persistidos de `narrative.repeated_opening`;
- 0 mortes e 0 downed registrados.

| Tier | DeepSeek | Groq | Sucessos | Custo estimado |
|---|---:|---:|---:|---:|
| CLASSIFY | 387 | 5 | 392 | US$ 0,10956 |
| FAST | 427 | 0 | 427 | US$ 0,11956 |
| SMART | 291 | 0 | 291 | US$ 0,08148 |
| **Total** | **1.105** | **5** | **1.110** | **US$ 0,31060** |

O custo é uma estimativa por tokens fixos. Startup de campanha, tentativas
falhas, embeddings e invokes que não chegam ao hook não entram no total. Pela
mesma heurística fixa do harness, acrescentar as 18 chamadas conhecidas omitidas
levaria o run a aproximadamente US$ 0,31564. Nenhum dos dois valores deve ser
tratado como faturamento exato.

## 4. Resultado por perfil

Abreviações de rota: `C` combat, `S` storyteller, `L` loot, `N` NPC.

| Perfil | Turnos | Rotas | Combate ativo | Maior sequência | Requests | Fallback | p50/p95 ms | Custo est. | Avisos |
|---|---:|---|---:|---:|---|---:|---:|---:|---|
| agressivo | 30 | C30 | 29 | 23 | DS45/Groq2 | 2 | 5.412/20.707 | $0,01308 | 0 |
| combate | 30 | S20/C10 | 10 | 10 | DS92 | 0 | 15.484/31.034 | $0,02576 | 0 |
| comerciante | 30 | L29/N1 | 0 | 0 | DS122 | 0 | 8.133/19.633 | $0,03416 | 0 |
| diplomatico | 30 | N30 | 0 | 0 | DS94 | 0 | 12.750/24.004 | $0,02632 | 1 |
| explorador | 30 | S7/C23 | 24 | 11 | DS63/Groq2 | 2 | 8.001/34.028 | $0,01812 | 0 |
| fujao | 30 | S17/N1/C12 | 12 | 6 | DS90/Groq1 | 1 | 14.596/34.640 | $0,02544 | 0 |
| loot_abuser | 30 | L29/S1 | 0 | 0 | DS103 | 0 | 7.819/13.103 | $0,02884 | 0 |
| mapa_breaker | 30 | S30 | 0 | 0 | DS70 | 0 | 9.894/26.185 | $0,01960 | 0 |
| npc_only | 30 | N30 | 0 | 0 | DS95 | 0 | 15.822/25.466 | $0,02660 | 0 |
| quester | 30 | S20/N10 | 0 | 0 | DS79 | 0 | 12.005/34.628 | $0,02212 | 2 |
| recrutador | 30 | N30 | 0 | 0 | DS87 | 0 | 13.572/25.263 | $0,02436 | 0 |
| secret_rusher | 30 | N30 | 0 | 0 | DS94 | 0 | 14.118/22.029 | $0,02632 | 0 |
| troll | 30 | S25/N5 | 0 | 0 | DS71 | 0 | 9.494/19.025 | $0,01988 | 1 |

Observações sobre a tabela:

- “combate ativo” pode exceder a rota `C`: o primeiro round pode começar dentro
  de um turno inicialmente roteado ao storyteller;
- o perfil `agressivo` fechou o primeiro encontro, mas ficou 23 rodadas no
  segundo;
- `agressivo`, `explorador` e `fujao` terminaram o run ainda em conflito;
- apenas quatro perfis exerceram conflito ativo.

## 5. Traço da vertical mais completa

O perfil `combate` é a melhor evidência da vertical:

| Turnos | Fase observada |
|---|---|
| 1–14 | exploração, viagem, NPCs, descanso e preparação narrativa |
| 15 | storyteller detecta/prepara três Sapos-Boi Ácidos e executa o primeiro round |
| 16–24 | rounds v4; Vitalidade chega a 0; Ferimento Crítico no torso |
| 25 | conflito passa `active=true → false`; loot narra Erva Amarga e 16 de ouro |
| 26–30 | retomada de viagem e narrativa |

O que impede considerar a vertical aprovada:

- as reações não são exportadas no JSONL;
- `ConflictSummary` não existe no save final;
- loot e archivist não o consomem;
- os turnos 17–25 dizem “Bebo a poção”, mas a mecânica executa Carta/ataque;
- após o conflito, descanso e level-up restauram HP sem restaurar Vitalidade.

## 6. Fronteira entre LLM e mecânica

### 6.1 O que foi comprovado

Não há chamada LLM em:

- `services/conflict_orchestrator.py`;
- `services/conflict_turn.py`;
- `services/conflict_resolution.py`;
- `services/conflict_damage.py`;
- `services/conflict_scene.py`;
- `services/conflict_summary.py`;
- `services/reactions.py`;
- `services/chase.py`;
- `services/cards.py`;
- núcleo compartilhado de `combat_mechanics.py`.

Dentro dessa fronteira, iniciativa, escolha tática do inimigo, rolagens,
dano, Proteção/Integridade, Vitalidade, Ferimentos, terminal, fuga e loot
mecânico são Python.

### 6.2 Chamadas fora da resolução

| Fase | Chamada possível |
|---|---|
| Router inicial | CLASSIFY |
| Scanner de encontro | CLASSIFY estruturado |
| Librarian/bestiário em cache miss | CLASSIFY e geração FAST/SMART |
| Preparação da cena | FAST estruturado |
| Parsing de fala livre | CLASSIFY; bypassado pela declaração do harness |
| Narração pós-round | FAST, depois do log mecânico |
| Cicatriz pós-sobrevivência | SMART estruturado |
| Loot | CLASSIFY/FAST conforme origem |
| Archivist | SMART estruturado; hoje pode repetir plain text |

Assim, “zero LLM” é verdadeiro para **resolver o round**, não para toda a
construção dos inputs do round.

### 6.3 Ressalvas de segurança

1. Em cache miss, `EnemySchema` deixa a LLM gerar HP, AC, atributos e ataques.
   `ensure_combat_sheet` deriva a ficha v4 desses números.
2. `PreparedScene` contém `Dict` abertos. A validação confere base narrativa e
   catálogo, mas parâmetros como `amount`/`duration` podem chegar ao orquestrador
   sem clamp numérico.
3. `EncounterScanner.count` não tem limite Pydantic; o loop instancia
   `max(1, count)` inimigos antes do clamp do orçamento.
4. O perfil tático gerado por LLM existe, mas não está ligado ao fluxo normal;
   `ensure_combat_sheet` usa o perfil default salvo fichas curadas.

## 7. Achados priorizados

### B1 — Bloqueador: Ferimento localizado pode nunca encerrar o conflito

Ataques não direcionados usam sempre `torso`. `apply_wound` remove o Ferimento
existente naquela região e o agrava. Quando ele já é Crítico, a categoria satura
em Crítico; o novo golpe apenas substitui o mesmo registro.

No primeiro perfil:

- jogador e inimigo chegaram a Vitalidade 0;
- ambos ficaram conscientes/ativos com 1 de 2 espaços Críticos;
- o segundo encontro foi do turno 8 ao 30, terminando em `combat.round=23`;
- o harness declarou 0 violações.

Correção mínima: definir a regra para novo trauma numa região já Crítica,
permitir que ele consuma outro espaço/dispare terminal e selecionar regiões de
forma mecânica para ataques não direcionados. Adicionar regressão que prove
encerramento em número limitado de rodadas.

### B2 — Bloqueador: HP legado e Vitalidade são duas fontes de verdade

O Devoto nasce com HP 40/40 e Vitalidade 12/12. O conflito espelha
Vitalidade → HP ao fim do round, mas:

- descanso cura apenas HP;
- level-up aumenta apenas HP/max HP;
- save/load preserva a divergência;
- o próximo conflito preserva Vitalidade e ignora o HP restaurado;
- telemetria e invariantes leem HP;
- o frontend considera `hp <= 0` morte.

No perfil `combate`:

| Momento | HP | Vitalidade |
|---|---:|---:|
| criação | 40/40 | 12/12 |
| level 2 | 47/47 | 12/12 |
| fim do dano, turnos 16–25 | 0/12 | 0/12 |
| descanso, turno 28 | 6/12 | 0/12 |
| level 3, turno 29 | 13/19 | 0/12 |

Dez dos 13 saves finais têm HP/max HP diferentes de
Vitalidade/max Vitalidade. Na UI real, o jogador ficaria bloqueado pela tela
“VOCÊ MORREU” enquanto o backend ainda permite a Última Ação.

Correção mínima: Vitalidade como fonte única; HP apenas derivado na borda até
ser removido. Migrar descanso, progressão, UI, telemetria e invariantes.

### B3 — Bloqueador de QA: intenção e mecânica do harness divergem

O runner chama `next_action()` para produzir o texto e, separadamente,
`combat_declaration()` para produzir a ação mecânica. A declaração base só
escolhe Carta ofensiva ou ataque, nunca item.

Evidência:

- das 75 ações roteadas a combate, 71 tinham texto explicitamente
  não-ofensivo: 35 poções, 23 tentativas de viajar/entrar, 11 fugas e duas
  ativações de “Muralha Viva”;
- mecanicamente, porém, o harness resolveu exatamente 44 Cartas ofensivas e 31
  ataques;
- 35 ações de conflito dizem “Bebo a poção” nos perfis `agressivo` e
  `combate`;
- pelo menos 20 desses turnos registram uma Carta ativa;
- os demais executam ataques/declarações que também não consomem a poção;
- o perfil `fujao` pediu fuga em 11 turnos, mas `flee_requested` nunca foi
  ativado e nenhuma fuga aconteceu;
- o perfil `explorador` tentou viajar ou entrar em locais durante 23 turnos
  roteados a combate, enquanto a declaração mecânica continuou atacando;
- no turno 3 do `agressivo`, o texto pede “Muralha Viva”, mas a telemetria
  registra `dev_golpe_convite`;
- os inventários finais preservam as poções;
- a LLM narra cura e o archivist grava consumo inexistente.

O smoke mede um jogo diferente do texto que apresenta ao modelo. A decisão do
perfil deve ser atômica: texto e `TurnDeclaration` precisam nascer do mesmo
objeto.

### A1 — Alta: `ConflictSummary` é write-only

O combat node monta o resumo antes do loot, mas:

- `loot.py` não lê `conflict_summary` nem usa `loot_context`;
- `archivist.py` não usa `summary_facts`;
- `validate_narrative_consistency` não tem callsite de produção;
- persistência não serializa/carrega o campo;
- nenhum dos 13 saves finais contém o resumo.

Consequência direta: o perfil `mapa_breaker` permaneceu mecanicamente em
`nova_arcadia`, mas a narração afirmou que ele abriu portais e chegou a
“Xanadu-que-não-existe”. O archivist persistiu Xanadu como fato canônico.
Itens rejeitados pela borda também foram registrados na memória como obtidos.

Correção mínima: summary deve alimentar loot, narração e archivist; validar a
prosa contra fatos canônicos; persistir enquanto pendente; limpar após consumo.

### A2 — Alta: string `"null"` vira NPC real

`RouterDecision.target` aceita `Optional[str]` sem normalizar sentinelas.
DeepSeek retornou a string JSON `"null"`; ela é truthy e virou
`active_npc_name`.

Efeitos:

- seis gerações explícitas de NPC chamado `null`;
- seis saves finais com `npcs["null"]`;
- ID `npc_null` gravado em cache e memória;
- a persona foi sobrescrita entre campanhas (`Aris`, `Elias`, `Dorian`,
  `Elara`);
- o fallback “sem interlocutor → storyteller” foi contornado;
- `combat_target` também pode receber `"none"`/`"null"`.

Correção mínima: normalizar `null|none|n/a|""` para `None` no boundary do
`RouterDecision`, com defesa adicional antes de criar NPC/inimigo e teste
router → actor realista.

### A3 — Alta: structured output `None` não aciona o próximo provider

Todos os OpenAI-compat usam `method="function_calling"`.

- Em cinco chamadas de `EncounterScanner`, o DeepSeek gerou argumentos `{}`.
  O Pydantic levantou erro; `RoutedLLM` caiu corretamente para o Groq.
- Em seis chamadas do archivist, o parser devolveu `None` porque não encontrou
  tool call. Como não houve exceção, `RoutedLLM` contou sucesso e não tentou o
  próximo provider. O archivist fez fallback plain-text, perdendo fatos e
  crônica daquele turno.

Também houve quatro mensagens de erro do campaign manager por structured output
inválido.

Correção mínima: quando `with_structured_output` espera um modelo Pydantic,
`None` ou tipo errado deve ser tratado como falha roteável. Registrar tentativas
e outcomes, não só sucessos. O [guia oficial de Tool Calls](https://api-docs.deepseek.com/guides/tool_calls)
confirma o suporte do modelo; o problema observado está na aderência da resposta
e na pós-condição local.

### A4 — Alta: memória FAISS de NPC Unicode falha no Windows

Ao salvar `npc_a_figura_pálida`, o diretório foi criado, mas
`faiss.write_index`/`FileIOWriter(const char*)` não abriu o caminho Unicode.
O diretório ficou vazio. O erro foi capturado e impresso, sem chegar ao harness.

Impacto: a memória longa daquele NPC foi perdida; campanha e memória geral da
sessão continuaram.

Correção mínima: manter ID lógico, mas mapear o componente físico para slug
ASCII seguro + hash curto; preservar paths ASCII legados; neutralizar
separadores, `.`/`..` e nomes reservados do Windows.

### A5 — Alta: “mecânica Python” ainda recebe números abertos da LLM

O resolver não chama LLM, mas duas entradas podem alterar números:

- ficha inicial do bestiário em cache miss;
- `params.amount`/`duration` de eventos do Abismo em `PreparedScene`.

O segundo caso contraria a convenção “LLM propõe categoria; Python calcula
potência”. `potency_value`/`validate_creature_selection` não aparecem no
callsite produtivo auditado.

Correção mínima: reduzir o schema a categorias fechadas e derivar todo número
por `potency_by_level` em Python.

### M1 — Média: telemetria e invariantes produzem falso-verde

- `first_death_turn` usa `hp <= 0`, embora Vitalidade 0 não seja morte v4;
- houve `first_death_turn` em quatro campanhas, mas `deaths=0/downed=0`;
- vitals não verificam Vitalidade nem coerência HP↔Vitalidade;
- “combat zombie” depende apenas de `idle_turns`, não de progresso mecânico;
- exceção dentro de uma invariante é engolida;
- severidade/mensagem/details não sobrevivem no summary;
- CLI pode sair 0 com `errors>0` ou `aborted_reason`;
- attempts falhos, startup e embeddings não contam no teto/custo;
- o primeiro round iniciado dentro do storyteller é subcontado como não-combat.

Correção mínima: novos checks `vitality.consistency`,
`combat.no_progress`, `action.declaration_matches`, `npc.invalid_sentinel`,
`rag.persistence_error` e `summary.lifecycle`; falhar o CLI por erro/aborto.

### M2 — Média: qualidade narrativa e grounding

- uma abertura meta vazou: “Abaixo você encontra a narração…”;
- 15 itens narrados foram rejeitados como desconhecidos, mas alguns viraram
  fatos no RAG;
- fatos do archivist vieram com wrappers `value:`, `description:` e até
  transcritos inteiros;
- ameaças de prisão/expulsão continuaram por muitos turnos sem transição de
  cena;
- o `secret_rusher` não vazou os segredos canônicos, porém inventou versões
  falsas do Rei Subterrâneo, pacto de Valerius e Rede Carmesim.

O gate anti-spoiler passou: não apareceram Daruun, família/imortalidade,
Verme/Raízes, identidade secreta do Arauto nem o segredo real da Rede
Carmesim. A fidelidade ao lore, contudo, falhou.

## 8. O que funcionou bem

- Nenhuma exceção escapou do grafo em 390 turnos.
- Todos os artefatos de campanha foram persistidos.
- DeepSeek respondeu como primário em 99,5% dos invokes bem-sucedidos.
- O fallback para Groq funcionou quando houve `ValidationError`.
- Houve combate multi-round, Ferimentos, vitória, loot e retomada.
- O estado mecânico bloqueou viagens impossíveis; o defeito ficou na prosa e
  memória, não na localização persistida.
- A cerca de secrets protegeu as assinaturas canônicas.
- O limite de US$ 0,05 por campanha não foi atingido; maior campanha estimada:
  `comerciante`, US$ 0,03416.

## 9. Ordem recomendada de correção

1. Unificar HP/Vitalidade e corrigir o gate de morte da UI.
2. Corrigir progressão de Ferimento Crítico/região padrão e adicionar detector
   de conflito sem progresso.
3. Unificar ação textual e `TurnDeclaration` do harness.
4. Ligar `ConflictSummary` a loot → narrativa → archivist → persistência.
5. Normalizar sentinelas do router e remover/impedir `npc_null`.
6. Validar pós-condição de structured output no `RoutedLLM`.
7. Tornar path físico de memória NPC seguro/ASCII no Windows.
8. Fechar números da preparação em categorias calculadas por Python.
9. Fortalecer telemetria, exit code e invariantes.
10. Repetir o mesmo smoke, exigindo:
    - 13 × 30 completos, sem aborto;
    - zero erro operacional e zero invariant `error`;
    - nenhuma divergência HP/Vitalidade;
    - nenhum conflito sem progresso;
    - texto = declaração = efeito;
    - nenhum `npc_null`;
    - zero erro RAG;
    - summary consumido/persistido;
    - vertical com reação observável;
    - anti-spoiler e grounding aprovados.

## 10. Verificação offline pós-smoke

- `uv run pytest -q`: **1123 passed, 1 skipped** (1124 coletados);
- testes focados de roteamento/telemetria: verdes;
- `uv run python scripts/validate_content.py`: 0 erro, 0 aviso;
- `git diff --check`: sem erro de whitespace; apenas avisos de conversão
  LF→CRLF do Git no Windows;
- frontend não foi alterado nesta etapa; o build verde do cutover offline
  permanece a evidência aplicável.

## 11. Artefatos

- [Relatório agregado do harness](../playtest_runs/20260725-101933/report.md)
- [Transcrito completo, 390 turnos](../playtest_runs/20260725-101933/transcript.md)
- [Summary do perfil de combate](../playtest_runs/20260725-101933/combate_0.summary.json)
- [JSONL do perfil de combate](../playtest_runs/20260725-101933/combate_0.jsonl)
- [Summary do mapa breaker](../playtest_runs/20260725-101933/mapa_breaker_0.summary.json)
- [JSONL do secret rusher](../playtest_runs/20260725-101933/secret_rusher_0.jsonl)
- stdout bruto: `playtest_runs/_smoke-real-all-v4.stdout.log`
- stderr bruto: `playtest_runs/_smoke-real-all-v4.stderr.log`
- sanity: `playtest_runs/20260725-101604/`

`playtest_runs/` e `saves_playtest/` são artefatos locais gitignored. Este
documento preserva os números e conclusões necessários para o histórico do
projeto.
