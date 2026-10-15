# Crônicas de Valoria por dentro: como funciona o rpg-ia-master

Roteiro de vídeo longo, pedagógico, sobre o projeto rpg-ia-master. Fonte única: o mesmo conteúdo está estruturado em `roteiro.json` (consumido pelo Remotion). Narração em pt-BR para TTS (voz Microsoft Maria).

## Sumário

- **c01** Abertura: o que é o rpg-ia-master (9 cenas, cor `#B8943F`)
- **c02** Princípios: a IA narra, o Python resolve (8 cenas, cor `#9B2C2C`)
- **c03** Anatomia de um turno (12 cenas, cor `#3E5C76`)
- **c04** O grafo e os agentes, um por um (19 cenas, cor `#4A6B3A`)
- **c05** Modelos de linguagem: tiers, rotas e resiliência (13 cenas, cor `#5B3A7A`)
- **c06** O mundo de Valoria: lore, Codex e grafo (10 cenas, cor `#B7791F`)
- **c07** RAG e embeddings: buscar antes de narrar (9 cenas, cor `#2F6F6A`)
- **c08** Event sourcing: o mundo que muda (11 cenas, cor `#8C3B5A`)
- **c09** Memória, segredos, contexto, NPCs e crônica (16 cenas, cor `#556B2F`)
- **c10** Combate v4: um jogo tático determinístico (22 cenas, cor `#7B2E2E`)
- **c11** Cartas, Posturas, Entropia e progressão (16 cenas, cor `#5B3A7A`)
- **c12** O mundo sistêmico: tempo, viagem, clima e economia (15 cenas, cor `#2E4E6E`)
- **c13** A API, o streaming e a persistência (13 cenas, cor `#A0522D`)
- **c14** O frontend e a jornada do jogador (10 cenas, cor `#B8943F`)
- **c15** Arte visual: curada e dinâmica (6 cenas, cor `#8A6D2F`)
- **c16** Infraestrutura local-first (14 cenas, cor `#3D7A5C`)
- **c17** Qualidade: testes, playtest e evals (15 cenas, cor `#4B5A8A`)
- **c18** Processo spec-driven e a história do projeto (12 cenas, cor `#6B4E8C`)
- **c19** Estado atual, arestas e encerramento (9 cenas, cor `#7A4E2D`)

## C01 — Abertura: o que é o rpg-ia-master

_Cor do capítulo: `#B8943F` · 9 cenas · 582 palavras (~3.9 min)_

### c01s01 — Bem-vindo a Valoria

**Narração:** Imagine um jogo de R P G de mesa em que o mestre nunca se cansa, lembra de tudo o que você fez e ainda assim joga limpo com os dados. É isso que o rpg ia master tenta ser. Neste vídeo vamos abrir o projeto inteiro, peça por peça, do motor de agentes ao processo que mantém tudo de pé.

**Visual:** Cartão de abertura — **Crônicas de Valoria, por dentro** / _Como o rpg-ia-master funciona, de ponta a ponta_

### c01s02 — O jogo em uma frase

**Narração:** O rpg ia master é um R P G de texto. Você escreve, em português e com suas palavras, o que o seu personagem faz. Um mestre de jogo feito de inteligência artificial interpreta a intenção, consulta as regras e o mundo, resolve as consequências e devolve uma narração. O mundo se chama Valoria, persiste entre as sessões e reage ao que você faz.

**Visual:** Lista — **O que o jogador vive**
  - Escreve livremente o que o herói faz, em português
  - Um mestre de IA interpreta, resolve e narra a consequência
  - Valoria persiste: lugares, facções, clima e relógio continuam
  - Personagens lembram de conversas e de favores
  - Combate tático com Cartas, Ferimentos e morte de verdade

### c01s03 — A pilha tecnológica

**Narração:** Por baixo, o projeto é escrito em Python três ponto treze. O cérebro é um grafo de agentes do LangGraph. A memória de longo prazo usa busca vetorial, com Faiss em disco ou P G vector no Postgres. A borda é uma A P I em Fast A P I, e a interface principal é um aplicativo React com Vite e TypeScript. Há ainda um perfil local first com Postgres e Supabase.

**Visual:** Tabela — **A pilha, camada por camada**

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.13 com uv |
| Orquestração | LangGraph (grafo síncrono) |
| Modelos | DeepSeek, Groq, Gemini, Anthropic... |
| Memória vetorial | FAISS ou pgvector |
| Borda HTTP | FastAPI + SSE |
| Interface | React + Vite + TypeScript |
| Infra local-first | Postgres, Supabase Local, workers |

### c01s04 — A visão de cima

**Narração:** Vista de cima, a arquitetura é simples de desenhar. O jogador usa o navegador. O navegador conversa com a A P I. A A P I carrega o estado salvo e entrega para o grafo de agentes. Dentro do grafo, modelos de linguagem interpretam e narram, enquanto código Python determinístico resolve números e regras. No fim, o estado novo é salvo e a memória é atualizada.

**Visual:** Grafo (LR) — **Arquitetura em uma tela**
  - Nós: Jogador [io]; Frontend React [io]; API FastAPI [io]; Grafo LangGraph [neutral]; Agentes com LLM [llm]; Mecânica em Python [python]; Save e checkpoint [data]; Memória RAG [data]
  - Jogador → Frontend React
  - Frontend React → API FastAPI (HTTP e SSE)
  - API FastAPI → Grafo LangGraph (estado)
  - Grafo LangGraph → Agentes com LLM (interpretar)
  - Grafo LangGraph → Mecânica em Python (resolver)
  - Agentes com LLM → Save e checkpoint
  - Mecânica em Python → Save e checkpoint
  - Agentes com LLM → Memória RAG (fatos)

### c01s05 — O tamanho da coisa

**Narração:** Alguns números dão a escala. O grafo de um turno tem onze nós; o mapa de Valoria tem trinta e cinco locais; o bestiário tem cento e vinte e quatro criaturas; o Codex de lore tem quase setecentos documentos. A suíte offline passa de mil e oitocentos testes, e o projeto já acumulou cento e noventa e oito especificações numeradas. É um laboratório que cresceu com método.

**Visual:** Painel de números — **Valoria em números**
  - **11** — nós no grafo de um turno
  - **35** — locais no mapa, 5 deles interiores
  - **124** — criaturas no bestiário
  - **699** — documentos no Codex de lore
  - **1.898** — testes offline passando
  - **198** — specs com ID estável

### c01s06 — Por que não só pedir a uma IA

**Narração:** Você poderia abrir um chat e pedir para uma IA ser seu mestre de jogo. Funciona por alguns minutos. Depois ela esquece quem você encontrou, inventa que você tem mil moedas, deixa você morrer e reviver na frase seguinte e revela segredos que deveriam ficar escondidos. Este projeto existe para resolver exatamente esses problemas, colocando a IA dentro de uma estrutura que a vigia.

**Visual:** Comparação — **Mestre de IA solto versus este motor**
  - _Só um chat com IA_: Esquece fatos antigos · Inventa números e recompensas · Contradiz o que já aconteceu · Vaza segredos da trama · Cada resposta é um improviso
  - _rpg-ia-master_: Memória em camadas com proveniência · Dados e economia em Python · Validadores barram contradições · Visibilidade filtra segredos · Estado salvo, versionado e testado

### c01s07 — O mapa deste vídeo

**Narração:** O roteiro segue camadas. Primeiro os princípios e a anatomia de um turno. Depois os agentes e a camada de modelos. Em seguida o mundo e a memória. Aí entramos na mecânica de combate, cartas e progressão, e no mundo sistêmico. Depois produto e infraestrutura. Fechamos com qualidade, processo, história e uma seção honesta sobre as arestas.

**Visual:** Fluxo numerado — **Roteiro do vídeo**
  1. **Princípios e turno** — IA narra, Python resolve; um turno de ponta a ponta
  2. **Agentes e modelos** — Os nós do grafo e o roteamento multi-provider
  3. **Mundo e memória** — Lore, RAG, eventos, segredos, NPCs e crônica
  4. **Mecânica** — Combate v4, Cartas, Posturas, progressão e mundo
  5. **Produto** — API, SSE, frontend, jornada e arte
  6. **Operação** — Persistência, Postgres, leases, observabilidade
  7. **Qualidade e processo** — Testes, playtest, evals, specs e história
  8. **Arestas** — Limitações e achados da exploração

### c01s08 — Pequeno glossário

**Narração:** Alguns termos vão aparecer o tempo todo. L L M é o modelo de linguagem, a IA que escreve. RAG é a técnica de buscar trechos relevantes num índice antes de pedir a resposta. Grafo é a sequência de nós que processa um turno. Spec é o documento que descreve uma funcionalidade antes de ela ser escrita. E Mock é um modelo falso, determinístico, usado para testar sem internet.

**Visual:** Tabela — **Glossário rápido**

| Termo | Significado aqui |
|---|---|
| LLM | Modelo que interpreta e narra |
| RAG | Busca em índice vetorial antes de gerar |
| Grafo | Nós do LangGraph que processam um turno |
| Tier | Classe de modelo: CLASSIFY, FAST, SMART |
| Spec | Documento aprovado antes do código |
| MockLLM | IA falsa e determinística para testes |

### c01s09 — Recapitulando a abertura

**Narração:** Guarde três ideias desta abertura. Primeiro: é um R P G de texto com um mundo persistente chamado Valoria. Segundo: a IA não está solta, ela trabalha dentro de um grafo de agentes cercado por código determinístico. Terceiro: o projeto é grande e metódico, com milhares de testes e centenas de especificações. Agora vamos ao princípio que explica quase todas as decisões.

**Visual:** Destaque (key) — **Recapitulação**: Um RPG de texto com mundo persistente. A IA trabalha dentro de um grafo vigiado por Python. Escala grande, construída com testes e specs.

## C02 — Princípios: a IA narra, o Python resolve

_Cor do capítulo: `#9B2C2C` · 8 cenas · 478 palavras (~3.2 min)_

### c02s01 — A regra de ouro

**Narração:** Se você lembrar de uma única regra deste projeto, lembre desta: a IA identifica e narra, o Python resolve os números. Toda decisão de arquitetura que vamos ver nasce dessa separação. Ela parece óbvia, mas aplicá-la de forma consistente em um sistema inteiro é o que dá ao jogo justiça, reprodutibilidade e testabilidade.

**Visual:** Cartão de abertura — **Princípios fundamentais** / _A IA identifica e narra. O Python resolve._

### c02s02 — Quem faz o quê

**Narração:** Pense numa partida de mesa. O mestre descreve o mundo e interpreta o que os jogadores querem. Mas quando alguém ataca, ninguém pede ao mestre para inventar o resultado: rola-se o dado e consulta-se a tabela. Aqui é igual. O modelo de linguagem classifica a intenção e escreve a prosa. Dados, dano, ferimentos, economia, experiência, viagem e descanso são código.

**Visual:** Comparação — **Divisão de trabalho**
  - _O modelo de linguagem faz_: Classifica a intenção do jogador · Extrai alvo, item ou destino · Escreve a narração e as falas · Propõe eventos, quests e itens · Planeja arcos de campanha
  - _O Python faz_: Rola dados e resolve ataques · Calcula dano, Ferimentos e morte · Fixa preços, ouro e estoque · Concede XP e níveis · Move o relógio, a viagem e o clima

### c02s03 — A IA propõe, o motor aplica

**Narração:** Quando a IA quer mudar o mundo, ela não muda, ela propõe. Uma morte de personagem, a revelação de um segredo, uma missão nova ou um item ganho chegam como propostas. Um validador em Python confere cada uma contra o mapa, o grafo de entidades e o inventário. Só o que passa vira estado. O resto vai para um registro de rejeições.

**Visual:** Grafo (LR) — **Proposta e validação**
  - Nós: LLM narra e propõe [llm]; Propostas pendentes [data]; Validador em Python [python]; Estado do jogo [data]; Registro de rejeições [neutral]
  - LLM narra e propõe → Propostas pendentes
  - Propostas pendentes → Validador em Python
  - Validador em Python → Estado do jogo (válida)
  - Validador em Python → Registro de rejeições (inválida)

### c02s04 — Guarda de resiliência

**Narração:** O terceiro princípio é sobre falhas. Modelos caem, demoram, devolvem lixo. Quando toda a cadeia de provedores falha, o projeto não lança exceção: devolve uma mensagem vazia de IA no lugar do objeto esperado. Por isso todo nó que pede saída estruturada é obrigado a conferir o tipo do resultado antes de usar qualquer campo. Se não for o tipo certo, cai num caminho determinístico.

**Visual:** Código — **O guard obrigatório em todo nó** (`agents/storyteller.py`)

```python
story_engine = llm.with_structured_output(StoryUpdate)
update = story_engine.invoke([sys] + messages[-3:]) # Contexto reduzido

# Guard crítico: FallbackLLM devolve AIMessage, não o schema solicitado.
if not isinstance(update, StoryUpdate):
    update = StoryUpdate(narrative=_deterministic_story_fallback(
        (travel_note, rest_note, world_note, faction_note, weather_note), _ll,
    ))
```

### c02s05 — Guardas de prosa e evidência

**Narração:** O quarto princípio protege o que o jogador lê. Mesmo uma narração bonita pode afirmar coisas falsas: que você morreu, que ganhou cinquenta moedas, que está em outro lugar, que um personagem é de outra espécie. Antes de chegar à tela, a prosa passa por guardas que comparam cada frase com o estado confirmado e removem contradições. O recibo de recompensa é recalculado a partir da diferença real.

**Visual:** Lista — **O que as guardas removem ou corrigem**
  - Morte falsa do jogador e localização errada
  - Posse de item que não está no inventário mecânico
  - Ouro ou XP narrados que não batem com o delta real
  - Segredos ainda não revelados, mesmo entre aspas
  - Instruções internas vazando para a narração

### c02s06 — Um caminho de jogo, testado

**Narração:** O quinto princípio é estrutural: existe um único caminho de jogo. O grafo é compilado uma vez e usado pela A P I, pela linha de comando e pelo harness de playtest. Isso significa que o que é testado offline é exatamente o que roda para o jogador. Não existe uma versão de teste separada da versão real.

**Visual:** Grafo (TB) — **Um grafo, três consumidores**
  - Nós: Grafo compilado (app) [neutral]; API web [io]; CLI no terminal [io]; Harness de playtest [python]; Suíte de testes [python]
  - API web → Grafo compilado (app)
  - CLI no terminal → Grafo compilado (app)
  - Harness de playtest → Grafo compilado (app)
  - Suíte de testes → Grafo compilado (app)

### c02s07 — Por que isso importa

**Narração:** Esses princípios trazem quatro benefícios concretos. Justiça, porque o jogador sabe que o dado não foi inventado. Reprodutibilidade, porque com a mesma semente o combate dá o mesmo resultado. Testabilidade, porque código determinístico pode ser verificado sem chamar um modelo pago. E resiliência, porque mesmo sem nenhuma IA disponível o jogo continua funcionando de forma degradada.

**Visual:** Painel de números — **Benefícios da separação**
  - **Justiça** — números não são inventados pela IA
  - **Seed** — mesma semente, mesmo combate
  - **Offline** — suíte inteira roda sem rede
  - **Degradado** — sem IA, o jogo continua jogável

### c02s08 — Recapitulando os princípios

**Narração:** Recapitulando. A IA identifica e narra, o Python resolve. A IA propõe, o motor valida e aplica. Toda saída estruturada tem guarda de resiliência. Tudo que o jogador lê passa por guardas de prosa e evidência. E existe um único caminho de jogo para produção e testes. Com isso em mente, vamos acompanhar um turno inteiro.

**Visual:** Lista — **Os cinco princípios**
  - A IA identifica e narra; o Python resolve números
  - A IA propõe; validadores em Python aplicam ou rejeitam
  - Todo structured output tem guard de resiliência
  - Guardas de prosa e evidência antes da tela
  - Um único grafo para produção, CLI, playtest e testes

## C03 — Anatomia de um turno

_Cor do capítulo: `#3E5C76` · 12 cenas · 812 palavras (~5.4 min)_

### c03s01 — Um turno de verdade

**Narração:** Nada explica melhor um sistema do que segui-lo em ação. Neste capítulo vamos acompanhar um turno real: um herói de nível dois, em Nova Arcádia, digita vou para a Floresta Cinzenta. Vamos ver cada etapa, da tecla enviada até a narração aparecer letra por letra, passando pela A P I, pelo grafo e pela gravação do save.

**Visual:** Cartão de abertura — **Anatomia de um turno** / _Do clique em Agir até a narração na tela_

### c03s02 — A visão de alto nível

**Narração:** Em alto nível, um turno tem sete fases. O navegador envia a ação com um identificador único. A A P I trava o jogo e carrega o estado. Confere se a ação já foi processada e se o jogo aceita turnos. Roda o grafo. Calcula arte, checkpoint e resposta pública. E por fim grava tudo de forma atômica e registra uma linha de log.

**Visual:** Fluxo numerado — **As fases de um turno**
  1. **Envio** — Cliente manda o texto e um action_id UUID
  2. **Trava e carga** — Lock por jogo; carrega o save e migra a versão
  3. **Idempotência** — Se o action_id já foi visto, devolve sem rodar
  4. **Gates** — Memorial, arquivado ou queda pendente: 409
  5. **Grafo** — action_guard até turn_finalizer
  6. **Pós-grafo** — Cue visual, arte, checkpoint e resposta
  7. **Commit e log** — Save atômico e linha JSON rpg.turn

### c03s03 — O identificador da ação

**Narração:** Começa no navegador. Antes de enviar, o cliente gera um identificador único para a ação e guarda o pedido no armazenamento local. Se a aba fechar no meio do turno, ao voltar o cliente pergunta ao servidor se aquela operação já terminou. Se o servidor já processou, devolve o resultado sem rodar de novo. Isso é idempotência: repetir o pedido não repete o efeito.

**Visual:** Destaque (key) — **Idempotência por action_id**: Cada ação carrega um UUID. O servidor guarda os últimos 64 IDs processados no save; repetir o mesmo ID devolve o estado atual sem rodar o grafo. Retry seguro, sem turno duplicado.

### c03s04 — Gates antes do grafo

**Narração:** Com o estado carregado, a A P I faz três checagens. Se o herói morreu e o jogador aceitou o fim, o jogo é um memorial e qualquer ação recebe erro quatrocentos e nove. Se o save é muito antigo e foi arquivado, também. E se existe uma morte pendente, nenhuma ação passa até o jogador escolher na tela de morte.

**Visual:** Tabela — **Gates do turno**

| Situação | Efeito |
|---|---|
| game_over (memorial) | 409: a saga terminou |
| archived (save pré-v4) | 409: somente leitura |
| death_pending | 409: resolva a tela de morte |
| action_id repetido | devolve estado sem rodar |
| Combate ativo + chips da UI | vira combat_declaration |

### c03s05 — Entrando no grafo

**Narração:** Agora o grafo. O primeiro nó é o action guard, que olha a fase vital do herói. O guarda fotografa o antes: ouro, X P, inventário e missões. Depois o turn prepare avança o contador de turnos de dezessete para dezoito. O gerente de campanha confere se precisa replanejar o arco e, como faltam turnos para o próximo replanejamento, devolve o plano sem chamar modelo nenhum.

**Visual:** Exemplo passo a passo — **Primeiros nós do turno 18**
  - action_guard: `herói ativo; grava baseline de ouro, XP, itens`
  - turn_prepare: `turn_count 17 para 18; ações da sessão +1`
  - campaign_manager: `sem replan: plano atual devolvido, zero LLM`
  - dm_router: `'vou para' casa a regex: STORY sem LLM`
  - dispatch: `lê next = storyteller`

### c03s06 — O narrador faz a mecânica primeiro

**Narração:** No narrador, muita coisa acontece antes de qualquer IA. O destino é resolvido contra o mapa. O custo de viagem é calculado. O relógio avança, as facções progridem e, por ser a primeira visita, um achado ambiental pode ser sorteado. A cena de personagens é zerada, porque ninguém se teletransporta junto. Então rola-se um possível encontro. Neste exemplo, não houve combate, e o mundo ganha um rumor.

**Visual:** Fluxo numerado — **Storyteller: mecânica antes da prosa**
  1. **Resolve destino** — Nome livre vira id real do mapa, ou recusa canônica
  2. **Custo e viagem** — travel_cost, apply_travel, relógio e clima
  3. **Facções** — Progresso determinístico por período
  4. **Primeira visita** — Achado ambiental ou baú curado
  5. **Cena zerada** — NPCs saem de cena: ninguém teleporta
  6. **Encontro?** — Sorteio ponderado; aqui, nenhum combate
  7. **Ecos do mundo** — Simulador propõe um rumor

### c03s07 — A chamada ao narrador

**Narração:** Só então o narrador monta o contexto e chama o modelo rápido. O prompt leva o estado do mundo, a memória relevante, a lore pública, a vitalidade e o ouro exatos, as missões ativas e regras de estilo. O modelo devolve a narração e um pacote de propostas. Aqui ele introduziu uma guarda florestal chamada Ilse. O motor gera a ficha dela e a coloca em cena.

**Visual:** Exemplo passo a passo — **Resposta estruturada do storyteller**
  - narrative: `A névoa da Floresta Cinzenta engole a estrada...`
  - introduced_npcs: `Guarda-florestal Ilse`
  - beat_completed: `false`
  - proposed_events: `nenhum`
  - items_gained: `nenhum`
  - Efeito em Python: `gera ficha de Ilse e marca in_scene`

### c03s08 — Arquivista e finalizador

**Narração:** Como houve viagem, o turno foi marcado para arquivamento. O arquivista processa eventos pendentes, chama o modelo inteligente para reescrever o resumo da história e extrair fatos, e grava esses fatos na memória vetorial da sessão. Por último, o finalizador revalida a prosa, compara o estado final com a fotografia do início e gera o recibo do turno.

**Visual:** Grafo (LR) — **Fim do turno**
  - Nós: storyteller [llm]; archivist [llm]; Eventos pendentes [python]; FAISS da sessão [data]; turn_finalizer [python]; Recibo do turno [data]
  - storyteller → archivist
  - archivist → Eventos pendentes (valida)
  - archivist → FAISS da sessão (fatos)
  - archivist → turn_finalizer
  - turn_finalizer → Recibo do turno (delta real)

### c03s09 — De volta à API

**Narração:** O grafo terminou. A A P I decide se algum personagem novo merece uma imagem, marca o identificador da ação como processado, avalia se é hora de um checkpoint e monta a resposta pública. Depois grava o histórico de apresentação e o save, numa escrita atômica: arquivo temporário, sincronização com o disco e troca. Por fim, uma linha de log em JSON registra rota, latência, eventos e custo.

**Visual:** Fluxo numerado — **Pós-grafo na API**
  1. **Cue visual** — Primeira aparição de NPC ganha retrato curado
  2. **Ledger da ação** — action_id entra nos últimos 64 processados
  3. **Checkpoint?** — A cada 10 turnos ou zona segura
  4. **Resposta pública** — format_response monta o GameResponse
  5. **Save atômico** — temp, fsync e os.replace
  6. **Log rpg.turn** — rota, latência, eventos e custo

### c03s10 — O streaming na tela

**Narração:** Na variante de streaming, o navegador recebe eventos enquanto o grafo trabalha: aceito, cada fase concluída e a rota escolhida. Isso vira textos temáticos, como o mestre consulta os arcanos. Quando a narração fica pronta, ela chega em pedaços de oitenta caracteres, e o cliente faz o efeito de máquina de escrever. Vale notar: não é streaming de tokens do modelo, é a resposta pronta, fatiada.

**Visual:** Fluxo numerado — **Eventos S S E do turno**
  1. **accepted** — O servidor aceitou a ação
  2. **phase** — Cada nó concluído: campaign_manager, storyteller...
  3. **route** — A rota decidida pelo dm_router
  4. **visual** — Arte da cena ou do NPC novo
  5. **narrative** — Pedaços de 80 caracteres até done
  6. **state** — O GameResponse completo

### c03s11 — Variante: a emboscada

**Narração:** E se o sorteio de encontro tivesse dado combate? Então o narrador nem chama o modelo. Ele devolve na hora uma mensagem de sistema de início de combate, já com o mundo movido e a informação de quem percebeu quem. A aresta do grafo leva direto ao nó de combate, que monta a cena e resolve a primeira rodada no mesmo turno. O jogador recebe a chegada e o primeiro golpe numa única resposta. E um herói de nível baixo, de vitalidade cheia, ganha a iniciativa da primeira rodada mesmo surpreendido.

**Visual:** Fluxo numerado — **Emboscada na estrada**
  1. **Viagem aplicada** — Relógio, névoa e cena já atualizados
  2. **Encontro: combate** — Percepção decide quem foi surpreendido
  3. **Sem narrador** — Nenhuma chamada FAST de exploração
  4. **COMBAT START** — Mensagem de sistema e next = combat_agent
  5. **Primeira rodada** — Cena montada e resolvida no mesmo turno
  6. **Early-game** — Nível até 2 e vida cheia: herói age primeiro

### c03s12 — Recapitulando o turno

**Narração:** Recapitulando. Um turno é um pedido idempotente que atravessa gates, roda um grafo de onze nós e termina num save atômico. A maior parte do trabalho é Python determinístico. Neste exemplo, os modelos só entraram para escrever: o rumor do simulador do mundo, a ficha conceitual de Ilse, a narração e o arquivamento. O roteador, a campanha e toda a viagem não custaram nada. A interface mostra fases ao vivo e digita a narração. Agora vamos olhar cada nó do grafo com calma.

**Visual:** Destaque (key) — **Recapitulação**: Pedido idempotente, gates, grafo de 11 nós, save atômico. Roteador, campanha e viagem sem IA; modelos só para rumor, NPC novo, narração e arquivo. O SSE mostra fases ao vivo e fatia a narração pronta.

## C04 — O grafo e os agentes, um por um

_Cor do capítulo: `#4A6B3A` · 19 cenas · 1288 palavras (~8.6 min)_

### c04s01 — A linha de montagem

**Narração:** O grafo é como uma linha de montagem de uma oficina medieval. Cada estação tem um artesão especializado, e a peça, que aqui é o estado do jogo, passa de mão em mão. Neste capítulo visitamos cada estação: o guarda da porta, o preparador, o diretor de campanha, o roteador, os quatro agentes de ação, o arquivista e o finalizador.

**Visual:** Cartão de abertura — **O grafo e os agentes** / _Onze estações, cada uma com um ofício_

### c04s02 — O desenho do grafo

**Narração:** Este é o desenho. Do início, um gate barra jogos encerrados. O guarda de ação pode encerrar o turno com uma mensagem fixa. Em seguida vêm preparo, campanha, roteador e despacho. O despacho escolhe um de quatro agentes. O narrador pode encaminhar para o combate, o ator de personagens pode devolver ao narrador, e o combate vitorioso passa pelo saque. Tudo converge no arquivista e no finalizador.

**Visual:** Grafo (TB) — **Topologia do grafo**
  - Nós: START + gate [neutral]; action_guard [python]; turn_prepare [python]; campaign_manager [llm]; dm_router [llm]; dispatch [python]; npc_actor [llm]; storyteller [llm]; combat_agent [llm]; loot_agent [llm]; archivist [llm]; turn_finalizer [python]
  - START + gate → action_guard
  - action_guard → turn_prepare
  - turn_prepare → campaign_manager
  - campaign_manager → dm_router
  - dm_router → dispatch
  - dispatch → npc_actor
  - dispatch → storyteller
  - dispatch → combat_agent
  - dispatch → loot_agent
  - npc_actor → storyteller (sem alvo)
  - npc_actor → archivist
  - storyteller → combat_agent (emboscada)
  - storyteller → archivist
  - combat_agent → loot_agent (vitória)
  - combat_agent → archivist
  - loot_agent → archivist
  - archivist → turn_finalizer

### c04s03 — Sequencial ou concorrente

**Narração:** Existe um segundo desenho, experimental. Como o preparo do turno avança o relógio uma única vez antes de tudo, a campanha e o roteador podem rodar em paralelo, porque escrevem em campos diferentes do estado. Um benchmark controlado mostrou sobreposição, mas no DeepSeek real o turno piorou: as duas chamadas brigavam pela mesma rota do provedor. A decisão foi não adotar. O padrão de produção continua sequencial, e o modo concorrente fica atrás de uma variável de ambiente.

**Visual:** Comparação — **Dois modos de execução do turno**
  - _Sequencial (padrão)_: preparo, campanha, roteador, despacho · Sem disputa pelo provedor · Usado em produção e na suíte
  - _Concorrente (experimental)_: Campanha e roteador em paralelo · Join no nó de despacho · Canais de estado disjuntos · No-go no DeepSeek real

### c04s04 — O estado e o reducer

**Narração:** Um detalhe técnico importante. No LangGraph, cada nó devolve um pedaço do estado. Só um campo acumula: a lista de mensagens, que vai somando. Todo o resto é último valor vence. Por isso o roteador devolve explicitamente vazio para alvos de combate, de conversa e de saque: para que transitórios do turno anterior não sobrevivam. E quando um nó precisa reescrever mensagens, usa uma sobrescrita explícita.

**Visual:** Código — **O único campo acumulativo** (`state.py`)

```python
class GameState(TypedDict):
    game_id: str
    narrative_summary: str
    player: PlayerStats
    world: WorldState
    # único campo com reducer: mensagens são SOMADAS
    messages: Annotated[List[BaseMessage], operator.add]
    next: Optional[str]
    # ... todo o resto: último valor vence
```

### c04s05 — O guarda da porta

**Narração:** O action guard não usa IA. Ele classifica o herói numa fase vital: ativo, inconsciente, incapacitado, última ação, estado terminal, morte pendente ou morto. Um herói inconsciente só pode descansar ou pedir socorro, e a frase precisa casar inteira com o padrão de recuperação. Qualquer outra coisa recebe uma mensagem fixa e o turno termina sem gastar um centavo. E se encontra um herói em estado terminal sem nenhum combate que explique isso, um save corrompido ou antigo, ele repara o estado e pede replanejamento.

**Visual:** Tabela — **action_guard: fases e permissões**

| Fase vital | O que é permitido |
|---|---|
| active | Qualquer ação |
| unconscious / incapacitated | Só descansar ou pedir socorro |
| last_stand / terminal | Nada fora do combate |
| death_pending | Nada: resolva a tela de morte |
| dead | Nada |
| Combate ativo | Sempre resolve o combate |

### c04s06 — O diretor de campanha

**Narração:** O campaign manager é o diretor. Ele mantém um arco narrativo com três a cinco etapas, chamadas beats, e um clímax. Usa o modelo inteligente, mas só quando precisa: sem plano, mudança de região, quinze turnos desde o último plano ou todos os beats cumpridos. Em catorze de cada quinze turnos ele não custa nada. E se há combate ativo, adia o replanejamento.

**Visual:** Lista — **Quando o campaign_manager replaneja**
  - Não existe plano ou needs_replan foi marcado
  - O herói mudou para outra região do mapa
  - Passaram 15 turnos desde o último plano
  - Todos os beats do arco foram cumpridos
  - Combate ativo? adia: não gasta SMART numa cena instável

### c04s07 — As defesas do plano

**Narração:** O plano passa por camadas de proteção. Se veio em inglês, o diretor tenta de novo com instrução reforçada. Cada beat, o clímax e o título passam por um filtro que remove verdades ocultas da trama. A localização é sempre a real. E se tudo falhar, há um plano padrão de três beats em português. E beats em excesso são cortados em Python.

**Visual:** Fluxo numerado — **Proteções do plano de campanha**
  1. **Tipo certo** — isinstance CampaignPlanModel, senão erro
  2. **Idioma** — Beat em inglês? regenera uma vez
  3. **Segredo** — sanitize_beat remove verdades ocultas
  4. **Geografia** — location é sempre o local real do mundo
  5. **Excesso** — Mantém os 5 primeiros beats não vazios
  6. **Falha geral** — Plano fallback de 3 beats em pt-BR

### c04s08 — O roteador em detalhe

**Narração:** O dm router usa o classificador com temperatura zero, mas só depois de cinco atalhos. Sem mensagens, vai para a história. Com combate ativo, sempre combate, e uma tentativa de viagem vira tentativa de fuga. Recuperação vai para a história. Descanso e viagem explícitos também. Só então o modelo classifica entre história, combate, conversa ou saque, com o alvo extraído.

**Visual:** Fluxo numerado — **Ordem de decisão do dm_router**
  1. **Sem mensagens** — STORY; última msg é da IA: END
  2. **Combate ativo** — combat_agent sempre; viagem vira fuga
  3. **Recuperação** — Herói inconsciente descansando: STORY
  4. **Regex explícita** — descansar, dormir, viajar: STORY
  5. **Classificador** — CLASSIFY: STORY, COMBAT, NPC ou LOOT
  6. **Pós-processo** — NONE vira STORY; alvo e origem gravados

### c04s09 — Dois bugs que viraram regra

**Narração:** O gate de combate fechou dois bugs históricos. O primeiro era o teleporte: em combate, dizer vou para a cidade simplesmente movia o herói. Agora vira tentativa de fuga, resolvida pela perseguição. O segundo era o combate zumbi, que ficava ativo por dezenas de turnos. Agora, após três turnos sem ação de combate, ele expira. E o modelo escolher a rota nenhuma, comum com entradas absurdas, vira história.

**Visual:** Comparação — **Antes e depois do gate de combate**
  - _Antes_: Viajar em combate teleportava o herói · Combate ativo por 59 turnos seguidos · Rota NONE quebrava o grafo · Conversa no meio da luta ignorava inimigos
  - _Depois_: Viagem em combate vira tentativa de fuga · Combate órfão expira em 3 turnos · NONE é normalizado para STORY · Conversa e saque bloqueados até o fim

### c04s10 — O narrador

**Narração:** O storyteller é o nó mais denso. Já vimos que ele resolve viagem e descanso antes da IA. Depois, monta blocos explícitos no prompt: o estado do herói com vitalidade e ouro exatos, luz, clima, só as facções que o jogador conhece, entidades canônicas, missões ativas e capacidades da ficha. E pede para fechar com duas ou três opções de ação.

**Visual:** Lista — **Blocos do prompt do storyteller**
  - ESTADO_DO_HEROI: vitalidade e ouro exatos; use exatamente esse ouro
  - AMBIENTE_DE_LUZ e CLIMA_GLOBAL vindos do motor
  - FACÇÕES_CONHECIDAS: só as que o jogador já descobriu
  - ENTIDADES_CANONICAS e QUESTS_ATIVAS
  - CAPACIDADES_DO_HEROI: utilitárias liberadas pela ficha
  - Estilo: varie a abertura e feche com 2 ou 3 opções

### c04s11 — A quarentena atômica

**Narração:** Depois da resposta, o motor valida antes de mostrar. E aqui há uma política conservadora: se uma única proposta for inválida, todo o pacote livre da resposta vai para quarentena. Personagens novos, itens, missões e impactos de facção da mesma resposta são descartados, e a narração é trocada por uma versão determinística. A prosa não pode afirmar o que o motor vai recusar.

**Visual:** Destaque (warn) — **Quarentena atômica**: Uma proposta inválida põe em quarentena todo o payload livre da resposta: eventos, NPCs, itens, quests e beat. Garante coerência, ao custo de perder propostas legítimas do mesmo turno.

### c04s12 — O ator de personagens

**Narração:** O npc actor dá voz aos personagens. Antes da IA, ele resolve casos simples. Sem alvo e sem ninguém em cena, devolve o turno ao narrador, que descreve a ausência e sugere um caminho. Se o personagem existe mas está em outro lugar, a resposta é fixa: ele não está aqui, foi visto pela última vez em tal lugar. Recrutar e dispensar são decididos em Python.

**Visual:** Fluxo numerado — **Árvore de decisão do npc_actor**
  1. **Sem alvo e cena vazia** — Devolve ao storyteller com um gancho concreto
  2. **Conhecido, fora de cena** — Resposta fixa, zero LLM
  3. **Inexistente** — generate_new_npc cria na hora
  4. **Comando de party** — Recrutar ou dispensar: decisão em Python
  5. **Conversa** — Prompt com persona, memória e filtro de saber
  6. **Pós** — Relação 0 a 10, memória observável, traits

### c04s13 — Não seja uma Wikipédia

**Narração:** O prompt do personagem tem uma regra de ouro escrita literalmente: não seja uma Wikipédia. Um camponês não conhece os planos de cultos distantes. A memória que fica gravada não é o resumo livre da IA, mas a experiência observável: o jogador disse tal coisa, o personagem respondeu tal outra. E falas de personagens nunca viram fatos globais por inferência: são relatos.

**Visual:** Exemplo passo a passo — **Memória gravada após uma conversa**
  - Turno: `12`
  - Fala do jogador: `Quem é você de verdade?`
  - Resposta de Magda: `Há coisas que o Anel de Lama não esquece`
  - Proveniência: `npc_claim, ou seja, um relato`
  - Confiança: `reported, derivada, não escolhida`
  - Política do turno: `canonical_only: nada vira fato global`

### c04s14 — Combate e saque

**Narração:** O combat agent é um nó fino sobre os serviços de conflito. Ele usa IA em quatro pontos, todos de identificação ou narração: descobrir quais inimigos aparecem, criar o conceito de uma criatura nova, entender a fala do jogador como declaração e narrar a rodada. Há ainda a cicatriz, escrita depois de uma queda sobrevivida. Na vitória, segue para o loot agent, que trata tesouro, compra, venda e forja. Preço, estoque e raridade são sempre Python.

**Visual:** Tabela — **Onde o combate e o saque usam IA**

| Ponto | Tier | Papel |
|---|---|---|
| Spawn de inimigos | CLASSIFY | Quais e quantos, da narrativa |
| Criatura nova | FAST ou SMART | Só o conceito; ficha é Python |
| Declaração do jogador | CLASSIFY | Fala livre vira TurnDeclaration |
| Narração da rodada | FAST | Só a partir do log mecânico |
| Cicatriz | SMART | Após sobreviver à queda |
| Intenção de troca | CLASSIFY | Comprar, vender, forjar ou olhar |

### c04s15 — Arquivista e finalizador

**Narração:** O archivist tem cadência: só chama o modelo inteligente quando algo relevante aconteceu ou a cada dez turnos. Mas um trabalho roda sempre: processar os eventos propostos, que é o único caminho para mudar o mundo. O turn finalizer, sem IA, revalida a prosa, recusa salvar um estado sem dono de transição e calcula o recibo: ouro, X P, itens e missões como diferença real de estado.

**Visual:** Comparação — **Os dois últimos nós**
  - _archivist_: Processa eventos pendentes todo turno · SMART só com archive_due ou a cada 10 · Resumo curto de até 1.200 caracteres · Fatos com proveniência na memória · Crônica: marcos e prosa do menestrel
  - _turn_finalizer_: Sem nenhuma chamada de LLM · Revalida a prosa contra a evidência · Barra estado sem dono de transição · Recibo: ouro, XP, itens, quests · Remove marcadores falsos de resultado

### c04s16 — Os ajudantes dos agentes

**Narração:** Três ajudantes trabalham por trás dos nós. O bibliotecário evita duplicatas: antes de criar um personagem ou criatura, procura um igual em quatro camadas, e só a última usa o classificador. O bestiário gera criaturas novas, mas o modelo descreve apenas o conceito; a ficha numérica é calculada pelo motor a partir da categoria e do nível do encontro. E o simulador do mundo propõe rumores e mudanças de perigo, que o Python limita e aplica.

**Visual:** Tabela — **Agentes auxiliares**

| Ajudante | IA usada | O que o Python garante |
|---|---|---|
| librarian | CLASSIFY só no fim | Slug, tokens e difflib antes |
| bestiary | FAST ou SMART | Ficha por categoria e nível |
| world_simulator | FAST | Perigo muda no máximo 1 |
| generate_new_npc | FAST, SMART p/ nobres | Cache e ficha v4 de fallback |

### c04s17 — Objetivo público e direção social

**Narração:** Dois serviços pequenos resolvem um problema sutil. O plano de campanha é privado do diretor, então a interface e os personagens nunca leem beats nem clímax. O objetivo público mostrado ao jogador é a missão secundária ativa ou, sem ela, um convite a investigar o local atual dentro do arco. E quando não há ninguém com quem falar, a direção social escolhe, entre as saídas conectadas, a de menor perigo e a oferece como gancho concreto, sem inventar interlocutor.

**Visual:** Comparação — **Público versus privado**
  - _Privado do diretor_: Beats do arco · Clímax planejado · Arestas ocultas do grafo
  - _Público para o jogador_: Missão secundária ativa · Investigar o local no arco atual · Saída conectada de menor perigo

### c04s18 — Quanto custa um turno

**Narração:** Juntando tudo, dá para estimar o custo de um turno. Uma exploração em cidade sem evento custa tipicamente uma classificação e uma narração. A campanha só replaneja a cada quinze turnos. O arquivista só entra quando algo relevante aconteceu ou a cada dez turnos. Viagens e descansos acrescentam o simulador do mundo, e personagens novos acrescentam o designer. Cada ponto tem um caminho determinístico se o modelo falhar.

**Visual:** Tabela — **Chamadas de IA por turno típico**

| Ponto | Tier | Frequência | Se falhar |
|---|---|---|---|
| dm_router | CLASSIFY | 0 ou 1 | STORY |
| storyteller | FAST | 1 | Narração por notas |
| world_simulator | FAST | Viagem ou descanso | Sem rumor |
| campaign_manager | SMART | 1 a cada 15 | Plano de 3 beats |
| archivist | SMART | Cadência | Resumo em texto plano |
| combate: narração | FAST | 1 por rodada | Log mecânico |
| loot: troca | CLASSIFY | 0 ou 1 | Palavras-chave |

### c04s19 — Recapitulando os agentes

**Narração:** Recapitulando a linha de montagem. Guarda e preparo, sem IA. Campanha, que quase nunca custa. Roteador com atalhos determinísticos. Narrador, ator de personagens, combate e saque, onde a IA identifica e narra mas o Python decide. E arquivista e finalizador, que transformam o turno em memória e recibo. Agora vamos ver como o projeto escolhe qual modelo atende cada chamada.

**Visual:** Lista — **Os onze nós em uma linha cada**
  - action_guard e turn_prepare: fase vital e relógio, sem IA
  - campaign_manager: arco de 3 a 5 beats, SMART raro
  - dm_router: atalhos em Python, CLASSIFY no ambíguo
  - storyteller, npc_actor, combat_agent, loot_agent: ação
  - archivist: eventos, resumo, fatos e crônica
  - turn_finalizer: prosa validada e recibo por delta

## C05 — Modelos de linguagem: tiers, rotas e resiliência

_Cor do capítulo: `#5B3A7A` · 13 cenas · 809 palavras (~5.4 min)_

### c05s01 — Nunca depender de um só provedor

**Narração:** Um jogo que depende de um único provedor de IA para cada turno é frágil. Cotas acabam, saldos zeram, modelos são removidos, servidores demoram. Este capítulo mostra como o projeto trata a IA como um recurso intercambiável, com classes de modelo, listas de candidatos, recuperação de respostas ruins e um disjuntor para provedores mortos.

**Visual:** Cartão de abertura — **A camada de modelos** / _Tiers, rotas multi-provider e resiliência_

### c05s02 — Três classes de modelo

**Narração:** Tudo começa numa única função, get llm, que recebe uma classe de modelo. CLASSIFY é para classificação e parse com temperatura zero: roteador, intenção de combate, intenção de troca. FAST é para narração e diálogo. SMART é para coerência de longo prazo: campanha, arquivista, ficha e prólogo. Trocar modelo é editar uma tabela.

**Visual:** Tabela — **Os três tiers**

| Tier | Uso | Exemplos |
|---|---|---|
| CLASSIFY | Classificação e parse, temp 0 | router, combate, troca |
| FAST | Narração e roleplay | storyteller, npc_actor |
| SMART | Coerência de longo prazo | campanha, arquivista, prólogo |

### c05s03 — As rotas

**Narração:** Cada classe é uma lista ordenada de candidatos. O DeepSeek é o primário nas três, escolhido depois de um playtest longo por escrever melhor e custar cerca de um décimo de centavo de dólar por turno. Logo atrás vem o Groq, que tem camada gratuita e mantém o jogo vivo se o pago falhar. Depois vêm MiniMax, Qwen, Anthropic e Gemini, conforme a classe.

**Visual:** Código — **A tabela de rotas** (`llm_setup.py`)

```python
ROUTES = {
    ModelTier.CLASSIFY: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-flash-lite-latest"),
    ],
    ModelTier.FAST: [
        ("deepseek", "deepseek-v4-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("minimax", "MiniMax-M2.5"),
        ("qwen", "qwen-plus"),
        ("gemini", "gemini-flash-latest"),
    ],
    # SMART: deepseek, groq, anthropic, gemini
}
```

### c05s04 — A cascata de get llm

**Narração:** A função segue uma cascata em ordem. Se a variável que força o mock estiver ligada, devolve o modelo falso: é o que a suíte usa. Se houver um provedor forçado, todas as classes vão para ele. Se não houver chave de nenhum provedor, entra o mock, para rodar sem configuração. Caso contrário, devolve um roteador que percorre a lista de candidatos daquela classe.

**Visual:** Fluxo numerado — **Ordem de resolução de get_llm**
  1. **RPG_FORCE_MOCK** — MockLLM determinístico: a suíte inteira
  2. **LLM_PROVIDER** — Força todos os tiers num provider único
  3. **Sem nenhuma chave** — MockLLM, ou erro explícito com RPG_NO_MOCK
  4. **Padrão** — RoutedLLM com a lista ROUTES do tier

### c05s05 — O roteador preguiçoso

**Narração:** O objeto central é o Routed L L M. Ele é preguiçoso de propósito: quando um nó pede saída estruturada, ele só anota essa transformação. Só na hora de invocar ele constrói o cliente de cada candidato e reaplica as transformações. Assim o mesmo pedido funciona com provedores diferentes, cada um do seu jeito.

**Visual:** Destaque (info) — **Transformações acumuladas**: with_structured_output, bind_tools e with_retry são guardadas numa lista e reaplicadas por candidato no invoke. Providers OpenAI-compat usam function_calling; schemas recebem include_raw para recuperar JSON.

### c05s06 — O que acontece em cada tentativa

**Narração:** Em cada candidato, a ordem é esta. Se o disjuntor daquele provedor está aberto, pula. Constrói o cliente, com cache. Aplica as transformações. Pega uma vaga no semáforo do provedor, que limita duas chamadas simultâneas por padrão. Invoca. Se a resposta estruturada for inválida, regenera no mesmo provedor. Se a falha for de rede ou cota, passa para o próximo. Esgotou tudo, devolve uma mensagem vazia. Nunca levanta.

**Visual:** Fluxo numerado — **RoutedLLM.invoke por candidato**
  1. **Disjuntor** — Circuito aberto? pula e registra circuit_open
  2. **Cliente** — Cache por provider, modelo e temperatura
  3. **Transformações** — Reaplica structured output e tools
  4. **Semáforo** — Até 2 chamadas em voo por provider
  5. **Invoca** — Timeout curto, max_retries zero
  6. **Schema inválido** — Tenta JSON local; regenera até 3 gerações
  7. **Erro de transporte** — Passa para o próximo provider
  8. **Tudo falhou** — AIMessage vazio: nunca levanta

### c05s07 — Semântica versus transporte

**Narração:** Essa distinção é sutil e importante. Um erro de cota ou de rede não melhora tentando de novo no mesmo provedor; então o projeto troca de provedor. Já uma resposta mal formatada às vezes melhora numa segunda tentativa; então ele regenera no mesmo provedor, até três gerações, dizendo ao modelo qual contrato falhou. E antes de regenerar, tenta extrair um JSON válido do texto, sem custo nenhum.

**Visual:** Comparação — **Duas falhas, dois remédios**
  - _Falha de transporte_: Timeout, 429, erro 5xx · Não melhora no mesmo provider · Ação: próximo da lista · max_retries zero: fail-fast
  - _Falha semântica_: Schema não validou · Às vezes melhora com instrução · Tenta extrair JSON do texto, grátis · Regenera no mesmo, até 3 gerações

### c05s08 — O disjuntor

**Narração:** Um provedor sem saldo vai falhar sempre. Tentar de novo a cada turno só adiciona latência. Por isso existe um disjuntor: erros permanentes, como chave inválida, saldo insuficiente, modelo não encontrado ou dependência não instalada, abrem o circuito daquele provedor. A partir daí ele é pulado. No harness de playtest, os disjuntores são reiniciados a cada campanha.

**Visual:** Lista — **Erros que abrem o disjuntor**
  - 401 ou 403: chave inválida ou sem permissão
  - 402 ou insufficient balance: saldo esgotado
  - 404: modelo removido ou inexistente
  - Chave não configurada no ambiente
  - Biblioteca do provider não instalada

### c05s09 — Timeouts e detalhes de provedor

**Narração:** Cada provedor tem manias. O DeepSeek usa um tempo limite padrão de doze segundos e tem o raciocínio oculto desligado, para não adicionar latência. Os demais usam noventa segundos. Os modelos Claude mais novos rejeitam o parâmetro de temperatura, então ele é omitido. E nenhum candidato faz novas tentativas internas: o plano B é sempre outro provedor.

**Visual:** Tabela — **Particularidades por provider**

| Provider | Detalhe |
|---|---|
| DeepSeek | Timeout padrão 12 s; thinking desligado |
| Groq | Strict schema: usa function_calling |
| Anthropic | Sem temperature; sem prefill de IA |
| Gemini | Free tier: 20 req por dia por modelo |
| Todos | max_retries 0: o fallback é trocar |

### c05s10 — Telemetria sem derrubar o turno

**Narração:** Dois ganchos observam a camada de modelos. Um recebe cada sucesso, com provedor, modelo, classe, latência e se houve fallback. O outro recebe cada tentativa, inclusive erros, com um código que diz se o problema foi transporte, ausência de chamada de ferramenta, ferramenta errada, parse ou validação. Ambos estão protegidos: telemetria nunca derruba o turno. A A P I usa isso para somar o custo real por turno.

**Visual:** Painel de números — **O que a telemetria registra**
  - **provider** — quem respondeu
  - **tier** — CLASSIFY, FAST ou SMART
  - **latência** — milissegundos por invoke
  - **fell_back** — se caiu para outro candidato
  - **código** — transport, parsing, schema...

### c05s11 — O modelo falso

**Narração:** E o Mock L L M? Ele despacha pelo nome do esquema pedido: decisão de rota por palavras chave em português, atualização de história, plano de campanha, resposta de personagem. Ele até propõe missões, para o harness offline exercitá-las. Mas há um alerta: como ele sempre devolve objetos válidos, esconde erros de nome de campo que só aparecem com um modelo real.

**Visual:** Destaque (warn) — **O mock esconde bugs de mapeamento**: MockLLM sempre devolve instâncias Pydantic válidas, então res.campo nunca quebra. Bugs de nome ou tipo só aparecem com chave real: todo structured output novo exige smoke real.

### c05s12 — Trocar rotas sem deploy

**Narração:** Mudar de modelo não exige mexer nos agentes. Uma variável aponta para um arquivo de rotas que é mesclado com o padrão: classes não citadas mantêm a lista original. Outra variável força um provedor único para todas as classes, útil para jogar só com Gemini ou totalmente local. Provedores extras, como GLM e Kimi, ficam registrados para uso por arquivo. E uma função espelha a cascata para que a A P I diga ao jogador, sem mentir, quando o jogo está em modo simulado.

**Visual:** Tabela — **Alavancas de configuração dos modelos**

| Variável | Efeito |
|---|---|
| RPG_ROUTES | Arquivo JSON mesclado com ROUTES |
| LLM_PROVIDER | Todos os tiers num provider único |
| RPG_FORCE_MOCK | MockLLM mesmo com chave |
| RPG_NO_MOCK | Sem chave: erro explícito, não mock |
| DEEPSEEK_TIMEOUT_SECONDS | Timeout próprio do DeepSeek |
| RPG_LLM_MAX_CONCURRENCY | Chamadas em voo por provider |

### c05s13 — Recapitulando os modelos

**Narração:** Recapitulando. Três classes de modelo, cada uma com uma lista ordenada de candidatos, com DeepSeek na frente e Groq gratuito de reserva. Um roteador preguiçoso que separa falha de transporte de falha semântica, recupera JSON do texto e usa um disjuntor para provedores mortos. Telemetria por tentativa. E um modelo falso para jogar e testar sem rede.

**Visual:** Destaque (key) — **Recapitulação**: Três tiers com rotas ordenadas, DeepSeek primário e Groq de reserva. Transporte troca de provider; semântica regenera no mesmo. Disjuntor para erro permanente. Nunca levanta: devolve AIMessage vazio.

## C06 — O mundo de Valoria: lore, Codex e grafo

_Cor do capítulo: `#B7791F` · 10 cenas · 632 palavras (~4.2 min)_

### c06s01 — Um mundo antes do jogo

**Narração:** Antes de existir um turno, existe um mundo. Valoria tem história em eras, raças, facções com objetivos reais e declarados, criaturas, itens, rumores e segredos que os personagens raramente sabem. Neste capítulo vemos como esse lore sai de arquivos de texto escritos por humanos e vira três coisas que o motor entende: um Codex, um grafo de entidades e um mapa.

**Visual:** Cartão de abertura — **O mundo de Valoria** / _Do texto bruto ao Codex, ao grafo e ao mapa_

### c06s02 — A fonte do lore

**Narração:** A fonte é uma pasta com onze arquivos de texto, somando cerca de oitocentos quilobytes, todos com o título Codex Omnia. Há personagens importantes com motivações e segredos, o bestiário, uma linha do tempo da era zero à era sete, itens, locais, raças, facções, vida cotidiana, perspectivas conflitantes, rumores de confiabilidade variável e um arquivo só de segredos, de uso exclusivo do narrador.

**Visual:** Tabela — **Os onze arquivos de lore**

| Arquivo | Tema | Tamanho |
|---|---|---|
| npcs | Personagens, motivações e segredos | 185 KB |
| creatures | Fauna, assombrações, aberrações | 152 KB |
| timeline_completa | Da Era 0 à Era 7 | 96 KB |
| items e locations | Materiais, armas, lugares | 142 KB |
| races e factions | Seis raças e as facções | 106 KB |
| secrets | Verdades só do narrador | 31 KB |
| rumors e outros | Rumores, cotidiano, visões | 84 KB |

### c06s03 — Do texto ao Codex

**Narração:** Um script de migração lê esses textos, reconhece blocos de categoria e etiquetas e gera um Codex: quase setecentos documentos em Markdown, cada um com um cabeçalho que traz identificador, tipo, nome, etiquetas e visibilidade. A linha do tempo tem um parser próprio que divide por era e marca como ocultos os capítulos que revelariam as grandes verdades da trama.

**Visual:** Grafo (LR) — **Pipeline de lore**
  - Nós: lore_nova (11 .txt) [data]; Script de migração [python]; Overrides de curadoria [data]; Codex (699 .md) [data]; entities.json (594) [data]; Índice vetorial de lore [data]
  - lore_nova (11 .txt) → Script de migração
  - Overrides de curadoria → Script de migração (aplica depois)
  - Script de migração → Codex (699 .md)
  - Script de migração → entities.json (594)
  - Codex (699 .md) → Índice vetorial de lore (chunks 500/50)

### c06s04 — Visibilidade

**Narração:** A peça mais importante do cabeçalho é a visibilidade. Público significa que o narrador pode usar. Oculto significa que existe no mundo mas não deve aparecer na narração até ser descoberto. Secreto é a verdade profunda da trama. Hoje há seiscentos e trinta e nove documentos públicos, quarenta e um ocultos e dezenove secretos. O segredo de uma personagem pública mora num documento separado, oculto.

**Visual:** Painel de números — **Visibilidade no Codex**
  - **639** — documentos public
  - **41** — documentos hidden
  - **19** — documentos secret
  - **36** — arquivos curated, nunca sobrescritos

### c06s05 — Curadoria que sobrevive

**Narração:** Há um problema clássico em conteúdo gerado: se você edita o resultado à mão, a próxima geração apaga sua edição. A solução aqui é um arquivo de overrides de curadoria, aplicado depois da geração, que pode trocar apelidos, acrescentar etiquetas, mudar a visibilidade ou anexar texto. Um caso real: um playtest mostrou o narrador vazando uma criatura secreta, e ela foi marcada como oculta por override.

**Visual:** Destaque (info) — **Curadoria migration-safe**: data/codex_overrides.yaml é aplicado depois de gerar o Codex: aliases, tags_extra, visibility, related_entities, append_body. Arquivos curated: true nunca são tocados. Id órfão é erro de lint.

### c06s06 — O grafo de entidades

**Narração:** Além do texto, o mundo tem estrutura. Um arquivo gerado lista quinhentas e noventa e quatro entidades: monstros, personagens, facções, artefatos, locais e raças, e outras oitenta e duas são curadas à mão num arquivo extra. Um conjunto curado à mão de cento e uma arestas diz quem está onde, quem opera em que região, quem lidera quem, quem é inimigo de quem, quem controla o quê e quem tem pacto com quem. Algumas dessas arestas são ocultas ou secretas.

**Visual:** Tabela — **Arestas curadas do grafo**

| Tipo | Quantidade | Exemplo de sentido |
|---|---|---|
| located_in | 45 | personagem mora em um local |
| operates_in | 24 | facção atua numa região |
| leads | 21 | líder de uma facção |
| enemy_of | 5 | rivalidade declarada |
| controls | 4 | quem controla um local |
| member_of / pact_with | 1 + 1 | filiação e o pacto secreto |

### c06s07 — Componentes

**Narração:** Algumas entidades carregam componentes, que são dados mecânicos extras. O exemplo canônico é o de um líder político: se ele morrer, há um vácuo de poder. O componente guarda quanto a facção perde de estabilidade e qual rival pode ocupar o lugar. Esse arquivo de componentes não é tocado pela migração; ele é mesclado às entidades na hora de carregar.

**Visual:** Código — **Um componente de vácuo de poder** (`data/graph/components.json`)

```json
{
  "npc_valerius": {
    "power_vacuum_trigger": {
      "base_instability_delta": -50,
      "successor_id": null,
      "rival_faction_override": "mao_sombria"
    }
  }
}
```

### c06s08 — O mapa

**Narração:** O mapa tem trinta e cinco nós: trinta ao ar livre e cinco interiores, como uma taverna dentro de um anel da cidade. Cada nó tem região, coordenadas, perigo de um a quatro, etiquetas, conexões, uma semente de lore, etiquetas de forja e de economia, e às vezes tempos de viagem específicos. Dois locais escondem baús curados. O início padrão é Nova Arcádia, a região com mais nós.

**Visual:** Painel de números — **O mapa de Valoria**
  - **35** — nós: 30 ao ar livre e 5 interiores
  - **12** — regiões, de Nova Arcádia a Ophidia
  - **1 a 4** — escala de perigo por local
  - **2** — baús curados de tesouro
  - **13** — nós com tempos de viagem próprios

### c06s09 — Os demais dados do mundo

**Narração:** Completam o mundo vários catálogos. Seis raças com traços mecânicos e doze regiões com bônus iniciais. Oitenta traços ocultos de personagens. O bestiário com cento e vinte e quatro criaturas. Dezenove facções ativas com objetivo, ritmo e uma ascensão autorada. Tabelas de clima por região e eventos globais. Companheiros, mercadores, tabelas de saque, armadilhas e o catálogo de arte.

**Visual:** Lista — **Catálogos estáticos**
  - origins: 6 raças com traços e 12 regiões com bônus
  - traits: 80 traços ocultos de NPC, revelados com o tempo
  - bestiary: 124 criaturas, de Lacaio a Nomeado
  - factions: 19 facções com objetivo, ritmo e ascensão
  - weather: cadeias por região e eventos globais
  - merchants, loot_tables, traps, companions, visual_assets

### c06s10 — Recapitulando o mundo

**Narração:** Recapitulando. O lore nasce em onze textos editados por humanos. Um script gera o Codex com visibilidade por documento e um grafo de entidades. A curadoria vive em overrides que sobrevivem à regeneração. Arestas e componentes curados dão estrutura política ao mundo, e o mapa dá geografia, perigo e economia.

**Visual:** Destaque (key) — **Recapitulação**: Texto fonte gera Codex e grafo; visibility separa público, oculto e secreto; overrides preservam a curadoria; arestas e componentes dão política; o mapa dá geografia, perigo e economia.

## C07 — RAG e embeddings: buscar antes de narrar

_Cor do capítulo: `#2F6F6A` · 9 cenas · 574 palavras (~3.8 min)_

### c07s01 — Uma biblioteca com bibliotecário

**Narração:** Nenhum modelo cabe o Codex inteiro no prompt, e nem deveria. A técnica de RAG funciona como um bibliotecário: antes de narrar, você descreve o que precisa, ele busca os trechos mais parecidos num índice e entrega só esses. Neste capítulo vemos os índices, os provedores de embeddings e uma regra de segurança que impede misturar vetores incompatíveis.

**Visual:** Cartão de abertura — **RAG e embeddings** / _Buscar o trecho certo antes de narrar_

### c07s02 — Quatro escopos de índice

**Narração:** Existem quatro escopos de índice. O de lore global, gerado do Codex e imutável durante o jogo. O de regras, gerado de um arquivo de regras. O da sessão, um por jogo, escrito pelo arquivista durante a partida. E o de cada personagem, um índice por personagem dentro da sessão, com o que aquele personagem viveu com o jogador.

**Visual:** Tabela — **Os quatro escopos**

| Escopo | Quem escreve | Quando |
|---|---|---|
| Lore global | ingest_codex | Offline, ao reindexar |
| Regras global | ingest_file de rules.txt | Offline |
| Sessão | archivist, world_simulator | Durante o jogo |
| Por NPC | npc_actor, retry do archivist | A cada conversa |

### c07s03 — Do Codex aos vetores

**Narração:** Para indexar o lore, cada documento é cortado em pedaços de quinhentos caracteres com sobreposição de cinquenta. Cada pedaço herda do cabeçalho o identificador, o tipo, o nome, as etiquetas e a visibilidade. Um modelo de embeddings transforma cada pedaço num vetor, e os vetores vão para um índice Faiss. O comando de reindexação roda o lint de conteúdo antes e aborta se houver erro.

**Visual:** Fluxo numerado — **Indexação do lore**
  1. **Lint de conteúdo** — Erro de frontmatter ou visibilidade aborta
  2. **Carregar Codex** — 699 documentos com metadados
  3. **Fatiar** — Chunks de 500 com sobreposição de 50
  4. **Embeddings** — Provider ativo, hoje Jina
  5. **Salvar índice** — FAISS + embeddings_meta.json

### c07s04 — A cadeia de embeddings

**Narração:** Os embeddings também têm uma cadeia de provedores: Jina primeiro, depois OpenAI, depois Ollama local e por último Gemini. A Jina virou primária depois que o Gemini ficou sem créditos e a busca vetorial morreu por erros de cota. O Ollama só conta se o endereço do servidor estiver explícito, porque ter a biblioteca instalada não significa que o serviço está de pé.

**Visual:** Lista — **EMBEDDING_ROUTES, em ordem**
  - Jina jina-embeddings-v3: primário, bom em português
  - OpenAI text-embedding-3-small: exige chave
  - Ollama bge-m3: só com OLLAMA_HOST explícito
  - Gemini embedding: último recurso
  - RPG_EMBEDDINGS força um provider específico

### c07s05 — Índice pinado

**Narração:** Vetores de provedores diferentes vivem em espaços diferentes; consultar um índice da Jina com um vetor do Gemini dá lixo. Por isso não existe fallback por pedido. Cada índice grava ao lado um arquivo dizendo qual provedor e modelo o gerou. Ao abrir, usa sempre aquele. Se aquele provedor não está disponível, o índice é desativado com um aviso.

**Visual:** Destaque (warn) — **Nunca misturar vetores**: Cada índice grava embeddings_meta.json com provider e modelo. A leitura usa o provider pinado, nunca o ativo. Provider indisponível desativa o índice com aviso: reindexe para trocar.

### c07s06 — Filtro de visibilidade

**Narração:** Na hora da busca, a visibilidade vira um filtro. Público vale zero, oculto vale um, secreto vale dois. E um valor desconhecido vale secreto: falha fechada, para um erro de digitação não vazar nada. Como o filtro roda depois da busca vetorial, pede-se seis candidatos e ficam os dois melhores permitidos. Todos os leitores de produção pedem só o público.

**Visual:** Exemplo passo a passo — **Uma busca no lore**
  - Consulta: `Quem governa Nova Arcádia?`
  - Candidatos buscados: `6 vizinhos mais próximos`
  - Filtro: `visibilidade até public`
  - Desconhecido: `tratado como secret: descartado`
  - Devolvidos: `os 2 melhores permitidos`
  - Id de evidência: `entidade mais hash do chunk`

### c07s07 — Um vetor, três leituras

**Narração:** Um turno costuma precisar de três buscas: lore, memória da sessão e memória do personagem. Para não pagar três vezes, o motor gera um único vetor da consulta e lê os três índices em paralelo, numa pequena fila de tarefas. Mas só compartilha o vetor se os três índices estiverem pinados no mesmo provedor e dimensão. Se um leitor falha, o contexto fica degradado, e o turno segue.

**Visual:** Grafo (LR) — **Aquisição concorrente de contexto**
  - Nós: Consulta do turno [io]; Um embedding [llm]; Lore pública [data]; Memória da sessão [data]; Memória do NPC [data]; Fontes de contexto [python]
  - Consulta do turno → Um embedding
  - Um embedding → Lore pública
  - Um embedding → Memória da sessão
  - Um embedding → Memória do NPC
  - Lore pública → Fontes de contexto
  - Memória da sessão → Fontes de contexto
  - Memória do NPC → Fontes de contexto

### c07s08 — No perfil Postgres: busca híbrida

**Narração:** Tudo isso descreve o perfil local de arquivos. Nos perfis com banco, a memória vive no Postgres com a extensão P G vector, em vetores de mil e vinte e quatro dimensões. A busca é híbrida: une similaridade vetorial e busca textual, e se o serviço de embeddings estiver fora, cai só na busca textual. Um detalhe prático: a Jina gera mil e vinte e quatro dimensões e serve; o modelo pequeno da OpenAI gera mil quinhentas e trinta e seis e não é compatível com esse perfil.

**Visual:** Comparação — **FAISS versus pgvector**
  - _Perfil legacy_: Índices FAISS em disco · Escrita direta pelo arquivista · Busca só vetorial, 2 resultados · Usado por CLI, testes e playtest
  - _Perfis com banco_: memory_documents com vector(1024) · Escrita por outbox no commit · Vetorial mais texto, com fallback · Visibilidade e dono filtrados

### c07s09 — Recapitulando o RAG

**Narração:** Recapitulando. Quatro escopos de índice: lore, regras, sessão e personagem. Uma cadeia de provedores de embeddings com Jina na frente. Cada índice pinado ao provedor que o gerou, sem misturar vetores. Visibilidade como filtro que falha fechado. E uma consulta, um vetor, três leituras em paralelo. Agora, como o mundo muda de forma controlada.

**Visual:** Lista — **O que levar do RAG**
  - Lore e regras são globais e imutáveis em jogo
  - Sessão e NPC são memórias vivas, escritas no turno
  - Índice pinado: nunca consultar com vetor alheio
  - Visibilidade desconhecida conta como secreta
  - Um embedding por consulta, leituras em paralelo

## C08 — Event sourcing: o mundo que muda

_Cor do capítulo: `#8C3B5A` · 11 cenas · 666 palavras (~4.4 min)_

### c08s01 — O livro de registros

**Narração:** Um mundo vivo precisa mudar: personagens morrem, cidades trocam de dono, rotas são bloqueadas. Mas o lore base é imutável. A solução é um padrão chamado event sourcing, algo como o livro de registros de um cartório. Nada é apagado: cada mudança é um evento anotado. O estado atual do mundo é derivado da leitura desse livro.

**Visual:** Cartão de abertura — **Event sourcing** / _Um livro de eventos e uma projeção derivada_

### c08s02 — Quatro campos

**Narração:** O estado do jogo carrega quatro campos para isso. O log de eventos, onde só se acrescenta. A projeção do mundo, que é o resultado derivado. As propostas pendentes, ainda não validadas. E o registro de rejeições, para auditoria. Quem pode escrever no log? Exatamente uma função, que roda no arquivista em todo turno.

**Visual:** Grafo (LR) — **Os campos do mundo estruturado**
  - Nós: pending_world_events [data]; process_pending_events [python]; event_log (append-only) [data]; world_projection [data]; event_rejections [neutral]
  - pending_world_events → process_pending_events
  - process_pending_events → event_log (append-only) (aceita)
  - process_pending_events → world_projection (aplica)
  - process_pending_events → event_rejections (recusa)

### c08s03 — Tipos de evento

**Narração:** Há quinze tipos de evento. Alguns a IA pode propor: personagem morto, segredo revelado, controle de local alterado, missão concluída, relação entre facções, reputação, rota bloqueada ou liberada. Outros só o motor emite: subir de nível, escolher subclasse, morrer, cair, reivindicar um item único. O truque é estrutural: o esquema de proposta da IA nem tem o campo de origem que esses tipos exigem.

**Visual:** Código — **A proposta não tem campo de origem** (`services/structured_outputs.py`)

```python
class ProposedWorldEvent(BaseModel):
    type: EventType
    actor_id: str = Field(default="player")
    target_id: str = Field(description="id EXATO de entities.json")
    detail: str = Field(default="")
    payload: Dict = Field(default_factory=dict)
    # sem campo source: level_up, player_died e
    # unique_item_* exigem source do motor
```

### c08s04 — Validadores

**Narração:** Cada proposta passa por um validador do seu tipo. Para declarar um personagem morto, o alvo precisa existir no grafo, ser do tipo personagem e estar vivo. Para revelar um segredo, precisa existir uma aresta oculta ou secreta ligada ao alvo, ainda não revelada. Para bloquear uma rota, a conexão precisa existir no mapa. Duplicatas no mesmo turno são barradas, e um dicionário malformado nunca derruba o turno.

**Visual:** Tabela — **Exemplos de validadores**

| Tipo | Exige |
|---|---|
| npc_killed | Existe, é NPC e ainda está vivo |
| secret_revealed | Aresta hidden/secret ligada ao alvo |
| location_control_changed | Alvo é um local |
| route_blocked | Conexão direta real, ainda livre |
| level_up / player_died | source do motor; IA é recusada |
| Qualquer tipo | Sem duplicata no mesmo turno |

### c08s05 — Aplicação pura

**Narração:** Uma proposta aceita vira um evento com identificador, turno e origem, e é aplicada à projeção por uma função pura, que copia antes de mudar. Personagem morto vira vivo falso. Segredo revelado entra nos fatos revelados. Troca de controle desativa a aresta antiga e cria uma dinâmica nova. O lore base nunca é tocado: o estado efetivo é base menos desativadas mais dinâmicas.

**Visual:** Destaque (info) — **Resolver do grafo**: Arestas efetivas = base - disabled_edges + dynamic_edges, com filtro de visibilidade. O controlador atual de um local é a aresta dinâmica mais recente; senão, a da base.

### c08s06 — O motor de regras

**Narração:** Eventos têm consequências. Um motor de regras declarativas, com seis regras em JSON, reage a cada evento aplicado. A mais dramática: quando morre um líder com o componente de vácuo de poder, a facção perde estabilidade e cada local que ele controlava muda de dono. Outras regras ajustam estabilidade, marcam missões e, se um porto cai em mãos hostis, bloqueiam suas rotas.

**Visual:** Lista — **As seis regras do mundo**
  - Morte de líder com vácuo de poder: estabilidade cai e locais mudam de dono
  - Morte de NPC comum: apenas marca como morto
  - Troca de controle: novo controlador ganha +5 de estabilidade
  - Segredo revelado: estabilidade -10
  - Quest concluída: marca a entidade
  - Porto tomado por hostil: emite route_blocked nas conexões

### c08s07 — Cascata com freio

**Narração:** Regras podem emitir eventos, que disparam regras, que emitem eventos. Sem freio, isso vira laço infinito. Por isso a cascata para na profundidade dois. E as regras não executam código arbitrário: valores dinâmicos só podem vir de um resolvedor de caminhos com lista branca. Qualquer coisa fora disso faz a regra ser ignorada com um log, sem quebrar o turno.

**Visual:** Grafo (TB) — **Cascata: a morte de Valerius**
  - Nós: npc_killed: Valerius [data]; rule_faction_leader_death [python]; Legião: -50 estabilidade [data]; location_control_changed [data]; control_change_ripple [python]; hostile_port_blockade [python]; route_blocked (se porto) [data]
  - npc_killed: Valerius → rule_faction_leader_death (depth 0)
  - rule_faction_leader_death → Legião: -50 estabilidade
  - rule_faction_leader_death → location_control_changed
  - location_control_changed → control_change_ripple (depth 1)
  - location_control_changed → hostile_port_blockade (depth 1)
  - hostile_port_blockade → route_blocked (se porto)

### c08s08 — Pré validação no narrador

**Narração:** Lembra da quarentena atômica? Ela usa uma pré validação somente leitura. Antes de mostrar a narração, o narrador simula o processamento das propostas sobre cópias, incluindo a cascata, de modo que a proposta seguinte já vê o efeito da anterior. Se algo é inválido, a prosa que afirmava a mudança é descartada antes de chegar ao jogador.

**Visual:** Fluxo numerado — **Do narrador ao log**
  1. **Narrador propõe** — proposed_events no StoryUpdate
  2. **Pré-validação** — Sobre cópias, com cascata, sem gravar
  3. **Inválida?** — Quarentena do payload e prosa determinística
  4. **Válida** — Entra em pending_world_events
  5. **Arquivista** — process_pending_events grava o log
  6. **Crônica** — Milestone de evento aplicado

### c08s09 — Missões verificáveis

**Narração:** O livro de missões segue a mesma filosofia. A IA propõe uma missão; o Python confere se os locais e entidades existem. O progresso é verificável: chegar ao local grava um marco, e duas investigações distintas no alvo permitem concluir. A recompensa é idempotente: X P mais vinte de ouro. Se o personagem que deu a missão morre, ela falha.

**Visual:** Fluxo numerado — **Ciclo de uma side quest**
  1. **created** — Proposta pela IA e validada em Python
  2. **location_reached** — Gravado uma vez ao chegar
  3. **investigation** — Ações distintas no alvo
  4. **completion_ready** — Duas investigações cumpridas
  5. **completed** — Evento com source system; XP e 20 de ouro
  6. **failed** — NPC de origem morto: quest órfã falha

### c08s10 — O que o jogador enxerga do mundo

**Narração:** A projeção guarda números internos, mas o jogador vê uma versão filtrada. Visões próprias traduzem a estabilidade de uma facção num rótulo qualitativo, sem expor o número. Mostram trocas de controle só nos lugares que o jogador já visitou, ameaças ativas e quem controla cada local, sem arestas ocultas. O mapa da interface usa exatamente essas visões para desenhar selos de facção, ameaça e rotas bloqueadas.

**Visual:** Lista — **Visões do mundo para o jogador**
  - Reputação por facção que o jogador conhece
  - Estabilidade como rótulo, nunca o número interno
  - Trocas de controle só em locais já visitados
  - Ameaças ativas e controladores visíveis
  - Rotas bloqueadas e perigo efetivo no mapa

### c08s11 — Recapitulando os eventos

**Narração:** Recapitulando. O mundo muda por eventos anotados num livro que só cresce. A IA propõe; validadores por tipo aceitam ou recusam; tipos sensíveis só o motor emite. A aplicação é pura e o lore base nunca muda. Seis regras declarativas criam consequências em cascata, com freio na profundidade dois. E missões progridem por marcos verificáveis.

**Visual:** Destaque (key) — **Recapitulação**: event_log append-only, projeção derivada, validadores por tipo e origem estrutural. Regras declarativas em cascata limitada a profundidade 2. Base imutável: efetivo = base - desativadas + dinâmicas.

## C09 — Memória, segredos, contexto, NPCs e crônica

_Cor do capítulo: `#556B2F` · 16 cenas · 1065 palavras (~7.1 min)_

### c09s01 — Lembrar sem inventar

**Narração:** Memória é o problema central de um mestre de IA. Lembrar pouco quebra a continuidade; lembrar errado é pior, porque transforma um boato em fato. Este capítulo mostra as cinco camadas de memória, a proveniência que decide quanto confiar em cada fato, a proteção de segredos, o montador de contexto com orçamento, os personagens em três camadas e a crônica.

**Visual:** Cartão de abertura — **Memória e conhecimento** / _Lembrar sem inventar, saber sem vazar_

### c09s02 — Cinco camadas

**Narração:** As camadas são cinco. O resumo narrativo de curto prazo, limitado a mil e duzentos caracteres e reescrito pelo arquivista. O livro de fatos dentro do save, que existe mesmo se a busca vetorial estiver fora. A memória vetorial da sessão. A memória vetorial de cada personagem. E o log de eventos, que é a verdade do mundo; a memória só espelha.

**Visual:** Tabela — **As cinco camadas de memória**

| Camada | Onde vive | Papel |
|---|---|---|
| Resumo curto | narrative_summary | Até 1.200 caracteres |
| Ledger de fatos | memory_facts no save | Até 500, com proveniência |
| Vetorial da sessão | FAISS ou pgvector | Busca semântica de fatos |
| Vetorial por NPC | Um índice por NPC | O que o NPC viveu |
| Eventos canônicos | event_log | Fonte da verdade |

### c09s03 — Proveniência

**Narração:** Cada fato tem uma proveniência, e a confiança é derivada dela por uma tabela fechada. Um evento canônico do motor é confirmado. Uma observação do jogador ou a fala de um personagem é um relato. Uma inferência livre da IA, ou um fato antigo sem metadado, é especulativa. O ponto principal: a IA não escolhe a confiança. Qualquer tentativa de elevá-la é sobrescrita.

**Visual:** Código — **Confiança derivada da proveniência** (`services/memory_provenance.py`)

```python
_CONFIDENCE_BY_PROVENANCE = {
    "canonical_event": "confirmed",
    "player_observation": "reported",
    "npc_claim": "reported",
    "inference": "speculative",
    "legacy_unverified": "speculative",
}
```

### c09s04 — Validar antes de gravar

**Narração:** Antes de gravar, cada fato é validado e a política é falhar fechado. É rejeitado se contradiz a localização atual, o delta de recompensa ou a vida do jogador. Se contém um segredo não revelado. Se confunde cair com morrer. Se afirma posse de um item ausente. Se troca a espécie de um personagem. Ou se diz confirmado sem uma fonte aplicável.

**Visual:** Lista — **Motivos de rejeição de um fato**
  - Contradiz localização, recompensa ou a vida do jogador
  - Contém segredo ainda não revelado
  - Trata queda como morte
  - Região e local incompatíveis com o mapa canônico
  - Posse de item ausente ou NPC com espécie trocada
  - Confirmado sem fonte aplicável no estado

### c09s05 — Repetir não promove

**Narração:** Fatos idênticos são mesclados. Se o mesmo texto reaparece com confiança maior, ele é promovido, de especulativo para relato para confirmado, e a promoção é contada. Mas repetição por si só nunca promove. Um boato repetido dez vezes continua boato. Na volta ao prompt, cada fato aparece com um rótulo, como confirmado, relato ou não verificado, para o modelo saber o peso.

**Visual:** Exemplo passo a passo — **Fatos formatados no prompt**
  - Confirmado: `[CONFIRMADO | canonical_event | turno 7] ...`
  - Relato: `[RELATO | npc_claim | fonte npc:velha_magda]`
  - Especulativo: `[RESUMO NARRATIVO | speculative] ...`
  - Legado: `[NÃO VERIFICADO | legacy_unverified] ...`
  - Regra: `Repetir texto não promove confiança`

### c09s06 — O arquivista e a memória

**Narração:** O arquivista grava com cuidado. Primeiro tenta de novo as gravações que falharam antes, e só avança o livro depois que a escrita física deu certo. Os fatos livres da IA viram inferências. Em turno de combate, ou quando algo foi rejeitado, os fatos livres são suprimidos: a prosa não pode reintroduzir um fato recusado. E o resumo é cortado onde contradiz mapa, inventário ou aparência.

**Visual:** Fluxo numerado — **Política de gravação do archivist**
  1. **Retry primeiro** — Fatos e memória de NPC pendentes
  2. **Escrita física** — Ledger só avança após gravar
  3. **Fatos livres** — Viram inference, especulativos
  4. **Turno sensível** — Combate ou rejeição: suprime fatos livres
  5. **Grounding** — Corta frases contra mapa, inventário, aparência
  6. **Crônica** — Conflito canônico e prosa permitida

### c09s07 — Segredos em três camadas

**Narração:** Segredos são protegidos em três camadas independentes. No índice, documentos ocultos e secretos nunca saem das buscas do narrador. Por assinatura de texto, frases da verdade oculta de quatro grandes segredos são detectadas e removidas, a menos que o jogador já as conheça. E por evento, um segredo só passa a valer quando uma revelação válida, ligada a uma aresta oculta, é aceita.

**Visual:** Grafo (TB) — **Defesa em profundidade contra vazamento**
  - Nós: Texto candidato [io]; Filtro de visibilidade [python]; Assinaturas de segredo [python]; Evento secret_revealed [data]; Pode aparecer ao jogador [neutral]
  - Texto candidato → Filtro de visibilidade (camada 1)
  - Filtro de visibilidade → Assinaturas de segredo (camada 2)
  - Evento secret_revealed → Assinaturas de segredo (libera)
  - Assinaturas de segredo → Pode aparecer ao jogador

### c09s08 — O caso da Velha Magda

**Narração:** Um caso real mostra a sutileza. Num playtest, a Velha Magda contou ao jogador sobre o pacto secreto de Valerius. Quando a narração repetiu o fato, o detector acusou vazamento, mas o jogador já sabia. A correção foi incluir no corpo do que é conhecido o resumo narrativo e os segredos conhecidos pelo jogador. O planejador de campanha, por sua vez, vê segredos, mas seus beats são higienizados.

**Visual:** Destaque (info) — **Segredo já conhecido não é vazamento**: O corpus revelado inclui eventos secret_revealed, fatos da projeção, o resumo narrativo e player.known_secrets. Se a Magda contou o pacto, repetir não é vazamento.

### c09s09 — O montador de contexto

**Narração:** Tudo isso precisa caber no prompt. O montador de contexto tem um orçamento de três mil e quinhentos tokens, dividido em seis seções: estado atual, local ativo, relações, entidades, lore e memória da sessão, cada uma com sua cota. As seções são preenchidas em ordem, com os fatos de maior nota primeiro. A sobra de uma seção rola para a próxima, o teto global admite cinco por cento a mais, e o que é cortado fica anotado com o motivo, como visibilidade ou orçamento.

**Visual:** Tabela — **Orçamento de contexto: 3.500 tokens**

| Seção | Cota |
|---|---|
| current_state | 25% |
| active_location | 20% |
| relations | 15% |
| entities | 15% |
| lore | 15% |
| session_memory | 10% (sobra rola adiante) |

### c09s10 — A nota de cada fato

**Narração:** Como o montador decide o que entra? Cada fato candidato recebe uma nota de zero a um, sem nenhum embedding: trinta e cinco por cento pela relevância às palavras da consulta, vinte e cinco por estar no mesmo local, vinte por envolver entidades em cena, dez pelo impacto do tipo de evento e dez pela recência. Uma morte ou troca de controle tem impacto máximo; um segredo revelado ou rota bloqueada, alto. Os tokens são estimados como caracteres divididos por quatro.

**Visual:** Painel de números — **Pesos da nota de relevância**
  - **0,35** — termos da consulta
  - **0,25** — mesmo local
  - **0,20** — entidades em cena
  - **0,10** — impacto do tipo de evento
  - **0,10** — recência, zerada em 50 turnos

### c09s11 — O estado atual vence

**Narração:** O bloco de estado do mundo entra no prompt com uma frase explícita: se o estado atual contradisser a lore ou os fatos, o estado atual vence. Assim, se o comandante Thrace foi morto no turno quinze, o motor renderiza esse evento com impacto máximo, e a lore antiga que o descreve vivo perde. Só o planejador de campanha enxerga arestas ocultas e secretas nesse montador.

**Visual:** Exemplo passo a passo — **Um evento chegando ao prompt**
  - Proposta: `npc_killed: npc_comandante_thrace`
  - Validação: `existe, é NPC, está vivo`
  - Projeção: `alive = false; regra de líder dispara`
  - Memória: `canonical_event, confirmed, fonte event_id`
  - Contexto: `[turno 15] Thrace foi morto, impacto 1,0`
  - Prompt: `o ESTADO ATUAL vence a lore antiga`

### c09s12 — Personagens em três camadas

**Narração:** Os personagens têm três camadas. Todos os da sessão. Os conhecidos pelo jogador, que a interface mostra sem traços ocultos. E os que estão em cena, os únicos com quem se pode conversar. Cada personagem sorteia de um a três traços ocultos, com semente estável, e eles são revelados com o tempo de convivência. Os traços afetam dificuldades mesmo antes de conhecidos: o mundo é real antes de ser descoberto.

**Visual:** Grafo (TB) — **NPCs em três camadas**
  - Nós: Camada 1: todos da sessão [data]; Camada 2: conhecidos [data]; Camada 3: em cena [data]; Painel da interface [io]; Rota de conversa [llm]
  - Camada 1: todos da sessão → Camada 2: conhecidos (known_by_player)
  - Camada 2: conhecidos → Camada 3: em cena (in_scene)
  - Camada 2: conhecidos → Painel da interface (sem traits)
  - Camada 3: em cena → Rota de conversa

### c09s13 — Anti carrossel

**Narração:** Um playtest achou um sobrevivente moribundo idêntico surgindo em três lugares em seis turnos. A correção prende cada personagem gerado ao local onde surgiu: só entra no contexto se estiver em cena, na comitiva ou vinculado ao local atual. Viajar tira todos de cena. E um personagem pode se mudar quando faz sentido, por exemplo ao ser recrutado ou reintroduzido pela narrativa em outro lugar.

**Visual:** Comparação — **Antes e depois do vínculo de local**
  - _Antes_: Mesmo NPC em vários locais · Contexto arrastava NPC de outra cena · Template de encontro repetido
  - _Depois_: NPC preso ao local de origem · Contexto só com cena, party ou local · Viagem limpa a cena · Reintrodução pode relocalizar

### c09s14 — Uma identidade, muitos nomes

**Narração:** Um mesmo personagem pode aparecer como identificador do Codex, identificador gerado em jogo, nome próprio ou apelido. Um serviço de identidade normaliza todas essas referências numa chave única, funde duplicatas de personagens gerados e resolve a entidade canônica. Essa peça sustenta o anti carrossel, o recrutamento, a memória por personagem que sobrevive ao recarregar o save e a escolha determinística do retrato na primeira aparição.

**Visual:** Exemplo passo a passo — **Várias referências, uma pessoa**
  - Identificador do Codex: `npc_mv_brunna_ponte_alta`
  - Forma curta: `mv_brunna_ponte_alta`
  - Nome na fala: `Brunna Ponte-Alta`
  - Normalização: `sem acento, minúsculas, sem npc_ ou mv_`
  - Chave única: `brunna ponte alta`
  - Usos: `dedupe, recrutamento, memória e retrato`

### c09s15 — A crônica

**Narração:** Por fim, a crônica, o diário da aventura. Ela é dividida em capítulos, um por arco de campanha. Tem duas fontes: marcos determinísticos gerados por modelo de texto a partir de eventos aplicados, como uma morte ou uma subida de nível, e a prosa do menestrel, escrita pelo arquivista. Capítulos longos ganham um resumo comprimido, mas os marcos originais continuam valendo. E há busca híbrida e exportação em texto.

**Visual:** Lista — **A crônica por dentro**
  - Capítulo novo quando o título do arco muda
  - Marcos por template a partir de eventos aplicados
  - Prosa do menestrel vinda do arquivista
  - Digest comprimido; raw e marcos seguem autoritativos
  - Busca léxica mais semântica fundida por RRF
  - Exportação em .txt pelo HUD

### c09s16 — Recapitulando memória

**Narração:** Recapitulando. Cinco camadas de memória, com o log de eventos como verdade. Confiança derivada da proveniência, nunca escolhida pela IA. Validação fecha falha antes de gravar, e repetição não promove. Segredos em três camadas. Contexto com orçamento e a regra de que o estado atual vence. Personagens em três camadas, presos ao seu local. E uma crônica por capítulos.

**Visual:** Destaque (key) — **Recapitulação**: Cinco camadas; confiança derivada da proveniência; validação fail-closed; segredos em três camadas; contexto de 3.500 tokens onde o estado atual vence; NPCs em três camadas; crônica por capítulos.

## C10 — Combate v4: um jogo tático determinístico

_Cor do capítulo: `#7B2E2E` · 22 cenas · 1529 palavras (~10.2 min)_

### c10s01 — O coração mecânico

**Narração:** O combate é onde a regra de ouro aparece com mais força. Ele foi reescrito num épico de dezessete especificações, que substituiu o velho sistema de dado de vinte contra classe de armadura por um jogo tático de cartas, totalmente determinístico. Aqui a IA só entende o que você quer e narra o que aconteceu. Cada número sai de uma pilha de módulos Python puros.

**Visual:** Cartão de abertura — **Combate v4** / _Valoria v2: cena, dados, dano, reações, morte e fuga_

### c10s02 — A pilha de uma rodada

**Narração:** O nó de combate chama uma função que resolve uma rodada inteira. Ela rola iniciativa por lado. Depois, para cada ator em ordem de agilidade, aplica condições e dano contínuo, decide a ação da IA inimiga, dispara ataques de oportunidade, abre a janela de reações e resolve o turno em três tempos. No fim, trata últimas ações, estado terminal, entropia por abate e eventos do Abismo.

**Visual:** Grafo (TB) — **O que acontece numa rodada**
  - Nós: combat_node [llm]; run_round [python]; Iniciativa por lado [python]; IA tática inimiga [python]; Reações e oportunidade [python]; Turno: Pré, Ação, Pós [python]; Ataque 2d10 + Virtude [python]; Dano e Ferimentos [python]; Última Ação e Terminal [python]; Fim de rodada [python]
  - combat_node → run_round
  - run_round → Iniciativa por lado
  - Iniciativa por lado → IA tática inimiga
  - IA tática inimiga → Reações e oportunidade
  - Reações e oportunidade → Turno: Pré, Ação, Pós
  - Turno: Pré, Ação, Pós → Ataque 2d10 + Virtude
  - Ataque 2d10 + Virtude → Dano e Ferimentos
  - Dano e Ferimentos → Última Ação e Terminal
  - Última Ação e Terminal → Fim de rodada

### c10s03 — A ficha de combate

**Narração:** Todo ator, seja herói, inimigo ou aliado, passa por uma função que normaliza a ficha. São cinco Virtudes de zero a cinco: mente, agilidade, força, carisma e corpo. O corpo define a vitalidade e os espaços de ferimento. A esquiva é dez mais agilidade. Inimigos ganham categoria, perfil tático, política de perseguição, entropia própria e uma carta universal de defesa instintiva.

**Visual:** Tabela — **Tabelas-base do combate**

| Item | Valor |
|---|---|
| Vitalidade por Corpo 0 a 5 | 6, 8, 10, 12, 14, 16 |
| Ferimentos Corpo 3 | 4 leves, 2 graves, 2 críticos |
| Esquiva | 10 + Agilidade |
| Dano-base de arma | leve 3, marcial 4, versátil 6, pesada 8 |
| Resistência / vulnerab. | -2 ou -4 / +2 ou +4 |
| Nível máximo | 20 |

### c10s04 — Dois dados de dez

**Narração:** O ataque rola dois dados de dez e soma a Virtude da carta ou da arma, contra a esquiva do alvo. Vantagem rola três dados e mantém os dois maiores; desvantagem mantém os dois menores. Elas se cancelam e não acumulam: só o sinal importa. Uma dupla nos dados mantidos é crítico, dobra o efeito e acerta sempre. Dupla de dez é supercrítico e triplica.

**Visual:** Código — **Vantagem: três dados, mantém dois** (`services/conflict_resolution.py`)

```python
def roll_kept(advantage: int, rng) -> Dict:
    net = 1 if advantage > 0 else (-1 if advantage < 0 else 0)
    if net == 0:
        rolled = [_d10(rng), _d10(rng)]
        return {"rolled": rolled, "kept": list(rolled)}
    rolled = [_d10(rng) for _ in range(3)]
    ordenado = sorted(rolled)
    kept = ordenado[-2:] if net > 0 else ordenado[:2]
    return {"rolled": rolled, "kept": kept}
```

### c10s05 — Iniciativa por lado e surpresa

**Narração:** A iniciativa não é individual. Heróis e aliados formam um lado, inimigos o outro. Cada lado rola dois dados de dez mais a maior agilidade entre seus membros conscientes, e o maior total age primeiro; dentro do lado, a ordem é por agilidade. Se houve surpresa no encontro, o lado que surpreendeu age primeiro sem disputa. As condições e o dano contínuo são aplicados no início do turno de cada ator, pelo mesmo caminho de dano, sem proteção de armadura.

**Visual:** Fluxo numerado — **Ordem de uma rodada**
  1. **Surpresa?** — Quem surpreendeu age primeiro, sem rolar
  2. **Lados rolam** — Dois d10 + maior Agilidade consciente
  3. **Dentro do lado** — Agilidade decrescente, depois id
  4. **Início do turno** — Condições e dano contínuo do ator
  5. **Ação** — Pré, Ação e Pós, com reações
  6. **Fim da rodada** — Abates, Recidiva e Abismo

### c10s06 — Testes gerais: Ímpeto e Presságio

**Narração:** Fora do ataque, o sistema tem um teste geral elegante. Rola-se um dado de Ímpeto e um de Presságio, soma-se a Virtude e compara-se com a dificuldade: fácil nove, comum doze, difícil quinze, extremo dezoito, quase impossível vinte e um. Além do sucesso, os dados contam uma história: Ímpeto maior que Presságio traz uma consequência favorável; o contrário, desfavorável; empate é resultado puro. Com Ruptura, rolam-se dois dados de Ímpeto e fica o maior.

**Visual:** Tabela — **Dificuldades do teste geral**

| Dificuldade | Alvo |
|---|---|
| Fácil | 9 |
| Comum | 12 |
| Difícil | 15 |
| Extremo | 18 |
| Quase impossível | 21 |
| Leitura dos dados | Ímpeto maior favorece; menor complica |

### c10s07 — Um ataque com números reais

**Narração:** Um exemplo executado de verdade. Um Devoto do Abismo de nível um, com força quatro, ataca um Rato da Peste, um lacaio com esquiva treze e vitalidade doze. Os dados dão três e dez, sem dupla. Total dezessete contra treze: acerto. A carta marcial dá quatro de dano, mais dois do bônus de início de jogo. Seis de dano, e o rato fica com seis de vitalidade.

**Visual:** Exemplo passo a passo — **Golpe do Convite contra o Rato da Peste**
  - Dados (seed 1): `3 e 10, sem dupla`
  - Total: `13 + Força 4 = 17`
  - Contra Esquiva: `17 >= 13: acerto, multiplicador x1`
  - Dano: `marcial 4 + bônus early-game 2 = 6`
  - Defesas: `sem resistência, sem armadura`
  - Resultado: `Vitalidade 12 para 6; sem Ferimento`

### c10s08 — E se sair um crítico

**Narração:** Com outra semente, os dados dão cinco e cinco: dupla, crítico. O total é catorze, que já acertaria, e o crítico acerta sempre, mesmo abaixo da esquiva. O dano dobra para doze, e a vitalidade do rato vai a zero. E aqui está uma surpresa do sistema: vitalidade zero não é morte. É muito ferido. A derrota vem dos ferimentos. Como lacaio, qualquer ferimento derruba o rato no próximo golpe.

**Visual:** Destaque (key) — **Vitalidade zero não é morte**: A derrota é por flag: morto, fugido, rendido, inconsciente. Vitalidade 0 é muito ferido. Lacaio cai com qualquer Ferimento; Padrão ao encher o último crítico; Elite, Chefe e o herói passam pelo fluxo de morte rica.

### c10s09 — Do dano ao ferimento

**Narração:** O dano segue uma ordem fixa. Multiplica pelo crítico. Imunidade zera; resistência e vulnerabilidade somam a mais forte de cada lado. Armadura ou escudo, um só, dá proteção contra dano físico. A integridade da armadura pode absorver mais, até se esgotar e a armadura ficar comprometida. Dano ígneo soma dois se atravessou. O que passa da vitalidade é o excedente, e o excedente vira ferimento.

**Visual:** Fluxo numerado — **Pipeline de dano, ordem fixa**
  1. **Crítico** — dano-base vezes 1, 2 ou 3
  2. **Imunidade e resist.** — Imune zera; resist e vuln somam
  3. **Proteção** — Armadura ou escudo, um por ataque
  4. **Integridade** — Absorve até o limite; zero compromete
  5. **Ígneo** — +2 se pelo menos 1 atravessou
  6. **Vitalidade** — Excedente = dano - vitalidade
  7. **Ferimento** — Faixa por Corpo: leve, grave, crítico
  8. **Efeito do tipo** — Sangramento, gélido, elétrico, abissal

### c10s10 — Ferimentos que agravam

**Narração:** O excedente cai numa faixa que depende do corpo. Com corpo três, de um a seis é leve, de sete a doze é grave, treze ou mais é crítico. Ferimentos têm região: cabeça, torso, braço, perna. Um leve sobre um leve na mesma região vira grave. Categoria cheia escala para a próxima. Mirar uma região custa desvantagem. E dano cortante que fere ainda causa sangramento.

**Visual:** Exemplo passo a passo — **Um golpe que fere**
  - Alvo: `armadura média, Corpo 3, Vitalidade 3`
  - Dano cortante: `8 x1 = 8`
  - Proteção: `-2: sobra 6`
  - Integridade: `absorve 2: sobra 4`
  - Vitalidade: `3 para 0, excedente 1`
  - Ferimento: `leve no torso + Sangramento`

### c10s11 — A cena por zonas

**Narração:** Não há grade de quadrados. A cena tem zonas, e cada participante tem três eixos independentes: distância, que vai de próximo a distante a separado; postura, que pode ser protegido, neutro ou exposto; e ocultação, que é relativa a cada observador. O engajamento corpo a corpo é uma relação à parte. Objetos da cena têm um catálogo fechado de efeitos, e a cena congela depois de preparada.

**Visual:** Tabela — **Manobras e seus custos**

| Manobra | Custo | Efeito |
|---|---|---|
| Mover | Pré ou Pós | 1 estágio; encerra Escondido |
| Engajar | Pré ou Pós | Cria engajamento |
| Desengajar | Ação | Sai sem ataque de oportunidade |
| Guardar | Ação | Postura defensiva universal |
| Esconder-se | Ação | Exige fonte plausível |
| Procurar | Ação | Revela só para quem procurou |

### c10s12 — Reações

**Narração:** Toda ação declarada abre uma janela de reação. Cada personagem do lado oposto pode oferecer uma reação comum por cadeia, com uma carta de reação cujo gatilho case, como ao ser atacado ou quando um aliado é atacado. Reação pode responder reação. E há o ataque de oportunidade, universal e fora do limite: quem sai de um engajamento sem desengajar leva um golpe de cada inimigo engajado. Um detalhe da implementação atual: uma reação bem sucedida não aplica o efeito escrito na carta; ela concede ao reator uma postura protegida contra o próximo ataque.

**Visual:** Lista — **Regras da janela de reação**
  - Uma reação comum por personagem em cada cadeia
  - Gatilhos fechados: ao ser atacado, aliado atacado, ao sofrer dano...
  - Ordem: alvo, aliados do alvo, aliados do ator, maior Agilidade
  - O jogador escolhe antes, na interface, a carta de reação
  - Ataque de Oportunidade: universal e fora do limite

### c10s13 — A IA tática sem IA

**Narração:** Os inimigos têm inteligência tática, mas sem modelo de linguagem. Cada um tem um perfil: uma lista ordenada de prioridades, cada uma com um gatilho e uma ação de um catálogo fechado: atacar, proteger, estabilizar, flanquear, controlar, apoiar, fugir ou se render. A primeira prioridade cujo gatilho é verdadeiro vence. Os gatilhos são calculados do estado real da cena.

**Visual:** Tabela — **Gatilhos táticos e exemplos**

| Gatilho | Definição | Bruto faz |
|---|---|---|
| sozinho | Nenhum parceiro vivo | ataca |
| muito_ferido | Vitalidade <= 35% ou grave | foge |
| cercado | Engajado com 2 ou mais | ataca |
| alvo_vulneravel | Oponente <= 50% ou exposto | ataca |
| matilha_quebrada | Metade dos parceiros caiu | ataca |
| sempre | Sempre verdadeiro | ataca |

### c10s14 — Provocação e ordens a companheiros

**Narração:** Duas regras completam a inteligência tática. A provocação do Devoto marca um inimigo; ao escolher o alvo, ele ataca o provocador com chance base de cinquenta por cento, que sobe com a Entropia do Devoto até oitenta por cento com os números atuais. E companheiros recebem ordens do jogador, mas cada um tem restrições: uma ordem que fere um limite só é aceita conforme a resistência, flexível, resistente, absoluta ou autônoma. Medo ou inconsciência tiram o comando.

**Visual:** Tabela — **Ordens a companheiros**

| Resistência | Ordem que fere a restrição |
|---|---|
| Flexível | Cede |
| Resistente | Cede só com argumento ou vantagem |
| Absoluta | Nunca cede |
| Autônoma | Nunca cede; age por conta |
| Perda de comando | Medo, confusão, separação, inconsciência |

### c10s15 — Morte rica

**Narração:** Quando o herói, ou um inimigo de elite, chefe, nomeado ou companheiro, enche o último espaço crítico, começa a morte rica. Ele faz uma última ação fora da ordem, com vantagem extrema. Depois entra em estado terminal. Um médico com kit ou uma poção reanimam com metade da vitalidade. Sem aliado capaz, é morte. Com aliado, até duas tentativas de estabilização; duas falhas, morte.

**Visual:** Fluxo numerado — **Fluxo de morte rica**
  1. **Gatilho** — Último espaço crítico preenchido
  2. **Última Ação** — Fora de ordem, uma vez, Vantagem extrema
  3. **Estado Terminal** — Aguarda estabilização
  4. **Automático** — Médico com kit ou poção: metade da Vitalidade
  5. **Rolagem** — 2d10 + Mente do ajudante vs CD 12, depois 15
  6. **Duas falhas** — Morte real: abre a tela de morte
  7. **Sobreviveu** — Cicatriz obrigatória gerada por IA

### c10s16 — Rendição, golpe não letal e fim

**Narração:** Há também desfechos não mortais. O golpe final pode ser declarado não letal, salvo formas como destruição total. A rendição é determinística, pelo perfil: líder caído, vitalidade baixa, aliados abaixo do mínimo, moral quebrada. O combate termina por objetivo mecânico, por gatilho preparado ou quando todos os hostis estão fora de ação. Nunca porque perderam o interesse. Depois, a consciência do herói depende do pior ferimento.

**Visual:** Lista — **Saídas de um conflito**
  - Golpe não-letal, exceto destruição total ou queda fatal
  - Rendição 100% determinística pelo perfil tático
  - Fim por objetivo, gatilho preparado ou hostis inativos
  - Pós-combate: só leves, acordado; grave, tratável; crítico, inconsciente

### c10s17 — Fuga e perseguição

**Narração:** Fugir abre uma perseguição numa trilha de quatro estágios: pressionado, afastado, quase livre e escapou. A posição inicial depende da distância. Cada rodada, o herói rola dois dados de dez mais agilidade contra dez mais a agilidade do perseguidor. Sucesso avança; falha recua; abaixo de pressionado, ele é alcançado e o combate volta. Se nenhum inimigo persegue, a fuga já nasce bem sucedida.

**Visual:** Grafo (LR) — **A trilha de perseguição**
  - Nós: Pressionado [neutral]; Afastado [neutral]; Quase livre [neutral]; Escapou [python]; Alcançado: combate [llm]
  - Pressionado → Afastado (sucesso)
  - Afastado → Quase livre (sucesso)
  - Quase livre → Escapou (sucesso)
  - Pressionado → Alcançado: combate (falha)

### c10s18 — Fuga: limites e quem fica para trás

**Narração:** A fuga tem mais regras. Enredado não foge. Há um teto de seis tentativas seguidas. Se a fuga dá certo e o destino é uma saída conectada, a viagem é aplicada no mesmo turno e a cena é limpa. E se um companheiro é abandonado, o destino dele é sorteado por uma simulação determinística entre fuga, captura, rendição, esconderijo, combate, morte ou reencontro futuro, com pesos que dependem da vitalidade, da agilidade e de quantos o perseguem. Sacrifício voluntário só existe com o traço certo.

**Visual:** Lista — **Detalhes da perseguição**
  - Condutor é sempre o protagonista; Virtude depende da abordagem
  - No loop atual a fuga usa Agilidade fixa
  - Teto de 6 tentativas seguidas de fuga
  - Sucesso com destino válido aplica a viagem no mesmo turno
  - Companheiro abandonado: destino por simulação com seed
  - Ataque corpo a corpo em Pressionado encerra a perseguição

### c10s19 — Abismo, preparação e resumo

**Narração:** Três serviços completam o combate. Eventos do Abismo podem ser preparados antes da luta, cada um com base em algo real da cena, e disparados por cargas, sem IA. O nível do encontro vem do perigo absoluto, nunca da força da comitiva. E ao fim, um resumo canônico com vinte e dois campos registra mortos, fugitivos, ferimentos e saque, sem IA, impedindo a narração de desfazer uma morte.

**Visual:** Comparação — **Antes e depois do conflito**
  - _Preparação_: Nível do Encontro: perigo absoluto, 1 a 10 · Potência por categoria e nível · IA escolhe a categoria; o número é Python · Eventos do Abismo com base na cena
  - _Resumo canônico_: 22 campos montados do estado final · Mortos, fugidos, rendidos, capturados · Loot usa o nível do encontro · Narração não pode reverter morte

### c10s20 — Por que esta luta começou

**Narração:** Todo combate registra a sua origem, num vocabulário fechado: provocado pelo jogador, encontro de viagem, perigo regional, pressão do arco, perseguição recorrente ou desconhecida. A origem vem da causa real da cena, não de um rótulo antigo. Isso nasceu de um playtest em que toda luta aparecia como provocada pelo jogador, até as emboscadas durante o descanso. Cada conflito também ganha um identificador por instância e linha do tempo, para não contar duas vezes.

**Visual:** Tabela — **Origens de combate**

| Origem | Quando |
|---|---|
| player_provoked | Hostilidade explícita do jogador |
| travel_encounter | Encontro sorteado na viagem |
| regional_danger | Reforços, facção, descanso perigoso |
| arc_pressure | Beat ou evento do arco |
| pursuit_recurrence | Perseguição que voltou |
| unknown | Sem causa identificável |

### c10s21 — O bestiário que aprende

**Narração:** No começo de uma luta, o jogador só vê o que é público do inimigo: vitalidade, esquiva, proteção, condições e posição. Quando uma criatura usa uma Carta ou tem uma resistência atingida, isso é revelado e fica gravado no bestiário do arquétipo, para os próximos encontros. Cartas exclusivas de uma variante não vazam para o arquétipo. E o conhecimento cresce em quatro níveis: rumores, encontrada, estudada e dominada.

**Visual:** Tabela — **Níveis de conhecimento de uma criatura**

| Nível | Exige |
|---|---|
| 1. Rumores | Vista uma vez |
| 2. Encontrada | Enfrentada uma vez |
| 3. Estudada | Três derrotas |
| 4. Dominada | Sete derrotas |
| Revelações | Cartas e resistências persistem |

### c10s22 — Recapitulando o combate

**Narração:** Recapitulando. Uma rodada é uma pilha de módulos Python. Dois dados de dez mais Virtude contra esquiva, com vantagem que não acumula e crítico por dupla. Dano em ordem fixa até virar ferimento, e vitalidade zero não é morte. Cena por zonas, reações e oportunidade. IA tática por prioridades. Morte rica, fuga por trilha e um resumo canônico no final. A IA só entende e narra.

**Visual:** Destaque (key) — **Recapitulação**: 2d10 + Virtude contra Esquiva; vantagem não acumula; crítico por dupla. Dano em ordem fixa vira Ferimento. Zonas, reações, IA tática por prioridades, morte rica, fuga por trilha e resumo canônico.

## C11 — Cartas, Posturas, Entropia e progressão

_Cor do capítulo: `#5B3A7A` · 16 cenas · 1090 palavras (~7.3 min)_

### c11s01 — O baralho do herói

**Narração:** Se o combate é o tabuleiro, as Cartas são as jogadas. Cada habilidade do herói é uma Carta com custo, frequência e efeito de um catálogo fechado. As classes, chamadas Posturas diante do Abismo, definem quais Cartas existem e como dois recursos especiais se comportam. Neste capítulo vemos Cartas, as cinco Posturas, Entropia, Carga do Abismo e a progressão até o nível vinte.

**Visual:** Cartão de abertura — **Cartas e Posturas** / _Acervo, Preparação, Entropia, Carga e níveis_

### c11s02 — Anatomia de uma Carta

**Narração:** Uma Carta tem um tipo: ativa, passiva, utilitária ou reação. Tem patamar, custo em Entropia, frequência de uso, a Virtude permitida e um efeito com um tipo de um catálogo fechado: dano, dano contínuo, cura, proteção, provocação, empurrão, marca, condições, vantagem e bônus diversos. Uma Carta central por subclasse tem Ruptura e duas evoluções possíveis.

**Visual:** Exemplo passo a passo — **Liturgia da Espera, Carta central do Devoto**
  - Tipo: `ativa, subclasse Consagrado`
  - Custo: `3 de Entropia, uma vez por cena`
  - Efeito: `protecao valor 4`
  - Ruptura: `caminho A protecao 8; caminho B taunt 4`
  - Evolução A: `protecao 6; ruptura 10`
  - Evolução B: `protecao 4; ruptura taunt 6`

### c11s03 — Acervo e Preparação

**Narração:** O herói tem um Acervo, as Cartas que aprendeu, e uma Preparação, as que leva para a luta. O número de espaços de preparação cresce com o nível: quatro até o nível três, dez no nível vinte. Reorganizar é livre, mas só fora de combate, em local de perigo até três e fora de zona extrema. As frequências são por turno, cena, descanso curto ou longo, e o descanso longo zera tudo em cascata.

**Visual:** Tabela — **Espaços de Preparação por nível**

| Níveis | Espaços |
|---|---|
| 1 a 3 | 4 |
| 4 a 6 | 5 |
| 7 a 9 | 6 |
| 10 a 12 | 7 |
| 13 a 16 | 8 |
| 17 a 19 | 9 |
| 20 | 10 |

### c11s04 — Ruptura

**Narração:** A Ruptura é a jogada arriscada. O herói paga o custo normal, ganha vantagem no ataque e recebe o efeito especial de ruptura da Carta. Mas ganha um ponto de Carga do Abismo, mesmo se falhar. É poder emprestado do Abismo, e o Abismo cobra depois. Só Cartas com ruptura definida permitem isso, e a interface mostra o botão apenas quando está pronta.

**Visual:** Destaque (warn) — **Ruptura cobra em Carga**: Ruptura: custo normal, +1 de Vantagem e o efeito de ruptura da Carta. Gera +1 de Carga do Abismo mesmo se o ataque falhar. Carga é longo prazo e não cai no descanso.

### c11s05 — Os números do catálogo

**Narração:** O catálogo é grande. O acervo autoral começou com dezesseis Cartas por Postura e cresceu na expansão de conteúdo: hoje cada Postura tem trinta ou trinta e uma, quase metade do tronco e o resto dividido entre as três subclasses, somando cento e cinquenta e três. Há mais oitenta Cartas tardias, dos níveis nove a vinte, quinze delas Ápices, e quarenta Cartas de inimigos. Um teste de paridade garante que, nas Cartas de dano puro, o dano dividido pelo custo fique entre um e meio e quatro.

**Visual:** Painel de números — **O baralho de Valoria**
  - **30 a 31** — Cartas por Postura, tronco e subclasses
  - **153** — Cartas das cinco Posturas
  - **80** — Cartas tardias, níveis 9 a 20
  - **15** — Ápices, um por subclasse
  - **40** — Cartas de inimigos
  - **1,5 a 4** — banda de paridade dano por custo

### c11s06 — Entropia e Carga

**Narração:** Dois recursos dão personalidade às Posturas. A Entropia é um pool único que paga as Cartas e substitui mana e vigor. Ela recompõe inteira no descanso. A Carga do Abismo é de longo prazo: sobe com Ruptura, com gatilhos de classe e com Cartas de pico, e não cai no descanso. Ela tem patamares, leve, moderado e severo, e cada Postura sofre uma consequência diferente.

**Visual:** Comparação — **Os dois recursos**
  - _Entropia_: Pool único que paga as Cartas · Substitui mana e stamina · Recompõe integral no descanso · Sobe por gatilhos de classe
  - _Carga do Abismo_: Longo prazo: não cai no descanso · Sobe com Ruptura e gatilhos · Patamares: leve 1, moderado 4, severo 7 · Cada Postura paga um preço diferente

### c11s07 — As cinco Posturas

**Narração:** São cinco Posturas, cada uma uma filosofia diante do Abismo. O Devoto ama: é o tanque, e ganha Entropia ao levar dano. O Sangromante negocia: dano corpo a corpo, ganha Entropia sacrificando o próprio sangue. O Corruptor trabalha junto: controle e dano contínuo, alimentado pela decadência ao redor. O Arcanista manipula, à distância. O Médico de Campo nega: suporte e cura.

**Visual:** Tabela — **As Posturas diante do Abismo**

| Postura | Papel | Gatilho de Entropia |
|---|---|---|
| Devoto do Abismo | Tanque; ama | Ao sofrer dano |
| Sangromante | Dano corpo a corpo; negocia | Ao sacrificar Vitalidade |
| Corruptor | Controle e DoT; trabalha junto | Decadência por perto |
| Arcanista Cinzento | Dano à distância; manipula | Ao canalizar |
| Médico de Campo | Suporte e cura; nega | Quando aliado sofre |

### c11s08 — O preço de cada Postura

**Narração:** Cada Postura paga a Carga de um jeito. O Devoto sofre insônia: descansa e recupera menos. O Sangromante ganha cicatrizes que reduzem a vitalidade máxima para sempre. O Corruptor se transforma, com penalidades conforme o domínio. O Arcanista fica dependente: com Carga moderada ou pior e sem instrumento, as Cartas custam o dobro. E o Médico esconde a própria Carga, até um colapso súbito ao cruzar o patamar severo.

**Visual:** Tabela — **Regra especial e consequência**

| Postura | Regra especial | Consequência da Carga |
|---|---|---|
| Devoto | Provocação cresce com Entropia | Insônia: descanso rende menos |
| Sangromante | Entropia de sangue vaza | Cicatriz: -3 Vitalidade máx. |
| Corruptor | Decadência por domínio | Transformação por domínio |
| Arcanista | Caldeira: estoura em 3 turnos | Dependência: custo x2 |
| Médico | Purga Carga de aliado | Recidiva oculta e colapso |

### c11s09 — O registro anti órfão

**Narração:** Uma lição de engenharia veio desse sistema. Uma revisão descobriu três mecânicas de classe mortas: a provocação, a transformação e a purga estavam prontas e testadas isoladamente, mas nunca eram chamadas pelo jogo. A correção foi um registro de tipos tratados pelo motor e um teste que varre os arquivos de dados e falha se aparecer um tipo sem tratador.

**Visual:** Destaque (info) — **HANDLED_KINDS**: Registro dos kinds de gatilho, regra especial, consequência, efeito e passiva que o motor sabe tratar. Um teste varre os JSONs gerados e fica vermelho para qualquer kind sem handler.

### c11s10 — Cartas de Virtude e de inimigos

**Narração:** Dois tipos de Carta vivem fora da mão preparada. As Cartas de Virtude, duas por personagem, não ocupam espaço de Preparação: dão um bônus que cresce em estágios conforme a Virtude, um para Virtude até dois, dois até quatro, três no cinco, e a Maestria acrescenta estágios. Já os inimigos têm Cartas próprias, com assinatura oculta até serem vistas, pagas com a Entropia da criatura e uma economia de uso reiniciada a cada rodada.

**Visual:** Comparação — **Fora da mão do herói**
  - _Cartas de Virtude_: Duas por personagem, fora dos slots · Bônus por estágio da Virtude · Estágio 1, 2 ou 3 conforme a Virtude · Maestria soma até 3 pontos
  - _Cartas de inimigos_: 40 Cartas de bestiário · Pagas com Entropia da criatura · Usos reiniciados a cada rodada · Reveladas ao jogador quando usadas

### c11s11 — Passivas, utilitárias e itens vivos

**Narração:** Nem toda Carta é de ataque. As utilitárias abrem capacidades fora de combate: o narrador recebe a lista num bloco próprio do prompt e não pode conceder nada fora dela. As passivas existem no catálogo, mas a leitura do código não encontrou quem as aplique no motor atual, um achado que volta no fim do vídeo. Os itens ganharam vida: um item equipado pode ter passiva, consumíveis ofensivos atingem o inimigo com teste de resistência, e tochas anulam a penalidade do escuro.

**Visual:** Lista — **Além das Cartas ativas**
  - Utilitárias: capacidades fora de combate, gate determinístico
  - Passivas de Carta: no catálogo, sem consumidor aparente
  - Item equipado pode trazer passiva própria
  - Consumível ofensivo usa teste de resistência d20
  - Tocha ou lanterna anula a penalidade de escuro

### c11s12 — Experiência e níveis

**Narração:** A experiência vem de abates, beats e missões: cinquenta por lacaio, duzentos por elite, mil por chefe, cento e cinquenta por beat e duzentos por missão. A tabela sobe até o nível vinte, com trezentos e cinquenta e cinco mil pontos. A cada nível sobe a Entropia máxima pela curva da classe. Um detalhe: a vitalidade não cresce com o nível, só com o Corpo.

**Visual:** Painel de números — **Progressão**
  - **50** — XP por lacaio; elite 200; chefe 1000
  - **150** — XP por beat; 200 por quest
  - **300** — XP para o nível 2
  - **355 mil** — XP para o nível 20
  - **Corpo** — só ele aumenta a Vitalidade

### c11s13 — Escolhas pendentes

**Narração:** Subir de nível gera escolhas pendentes, que não travam o jogo. No nível três, a escolha irreversível da subclasse, que bloqueia as demais até ser feita. Do nível dois ao dezenove, uma Carta nova ou, a partir do quatro, uma evolução. Nos níveis pares até dez, um ponto de Virtude. Nos níveis doze, dezesseis e vinte, Maestria nas Cartas de Virtude. E no vinte, o Ápice da subclasse, concedido automaticamente.

**Visual:** Fluxo numerado — **Escolhas ao subir de nível**
  1. **Nível 3** — Subclasse, irreversível, antes de tudo
  2. **Níveis 2 a 19** — Nova Carta ou, do 4 em diante, evolução A/B
  3. **Níveis 2 a 10 pares** — +1 numa Virtude, teto 5
  4. **Níveis 12, 16, 20** — Maestria em Carta de Virtude
  5. **Nível 20** — Ápice da subclasse, automático
  6. **Ledger** — Cada concessão é idempotente

### c11s14 — Criação e bônus de início

**Narração:** Na criação, o jogador distribui quatro, três, dois, um e um entre as cinco Virtudes, e começa com seis Cartas no Acervo, quatro preparadas e duas de Virtude. Para não morrer cedo demais, existe um bônus temporário de dano: mais dois nos níveis um e dois, mais um no nível três. Ele nasceu de um playtest que mostrou heróis frágeis sem saída nos primeiros turnos.

**Visual:** Exemplo passo a passo — **Devoto do Abismo recém-criado**
  - Virtudes: `Força 4, Corpo 3, Carisma 2, Mente 1, Agi 1`
  - Vitalidade: `18 = Corpo 3 (12) + bônus de classe 6`
  - Ferimentos: `4 leves, 2 graves, 2 críticos`
  - Entropia: `14 de 14`
  - Esquiva: `11`
  - Cartas: `6 no Acervo, 4 preparadas, 2 de Virtude`

### c11s15 — Como a ficha nasce

**Narração:** A ficha é montada numa ordem fixa. Primeiro os dados oficiais da Postura, depois as Virtudes escolhidas e validadas, a Entropia pela curva da classe e as Cartas iniciais. O modelo inteligente entra só para dar sabor: um inventário temático da região. Ele não define Virtudes, vitalidade nem Cartas. Se falhar, o herói recebe um kit básico. Por fim vêm o equipamento inicial, os traços da raça e a vitalidade derivada do Corpo, com a ficha curada por completo.

**Visual:** Fluxo numerado — **Montagem da ficha**
  1. **Classe** — Dados oficiais da Postura escolhida
  2. **Virtudes** — Distribuição 4, 3, 2, 1, 1 validada
  3. **Entropia e Cartas** — Curva da classe e Acervo inicial
  4. **Sabor via SMART** — Inventário temático; guard: Kit Básico
  5. **Equipamento** — Inicial da classe, auto-equipado
  6. **Raça e vitalidade** — Traços raciais e vida pelo Corpo

### c11s16 — Recapitulando Cartas e Posturas

**Narração:** Recapitulando. Habilidades são Cartas com custo, frequência e efeito fechado, organizadas em Acervo e Preparação. Ruptura dá poder e cobra Carga. Cinco Posturas, cada uma com seu gatilho de Entropia, regra especial e consequência de Carga. Um registro anti órfão impede mecânicas mortas. E a progressão vai ao nível vinte, com subclasse no três e Ápice no vinte.

**Visual:** Lista — **O essencial de Cartas e classes**
  - Cartas: tipo, custo em Entropia, frequência, efeito fechado
  - Acervo aprendido, Preparação limitada por nível
  - Ruptura: Vantagem e efeito extra, +1 Carga sempre
  - Cinco Posturas com gatilho, regra e consequência próprias
  - Níveis 1 a 20: subclasse no 3, Ápice no 20

## C12 — O mundo sistêmico: tempo, viagem, clima e economia

_Cor do capítulo: `#2E4E6E` · 15 cenas · 981 palavras (~6.5 min)_

### c12s01 — Um mundo que respira

**Narração:** Fora do combate, Valoria também é um sistema. O tempo passa em períodos, viajar custa tempo, o clima muda, a luz importa, mercadores repõem estoque, criaturas migram e armadilhas esperam. Tudo isso é Python determinístico. A IA só descreve o que esses sistemas decidiram. Este capítulo percorre cada um deles.

**Visual:** Cartão de abertura — **O mundo sistêmico** / _Relógio, viagem, descanso, clima, luz, economia e mais_

### c12s02 — Relógio e viagem

**Narração:** O dia tem cinco períodos: amanhecer, manhã, tarde, anoitecer e noite. Viajar custa períodos, normalmente um, ou o tempo específico do mapa. Entrar num interior, como uma taverna, custa zero, e sair também. Só aparecem destinos conectados ao local atual, e cada visita é marcada no mapa, que nasce coberto por uma névoa de guerra. A intenção de viajar é detectada por palavras em português.

**Visual:** Fluxo numerado — **Uma viagem, em Python**
  1. **Intenção** — Palavras-chave: vou para, viajo, sigo para
  2. **Destino** — Só conexões do local atual; senão, recusa
  3. **Custo** — Interior 0; travel_times do mapa; padrão 1
  4. **Relógio** — Avança os períodos e o clima
  5. **Fog of war** — Marca o local como visitado
  6. **Cena** — Todos os NPCs saem de cena

### c12s03 — Descanso

**Narração:** Descansar avança dois períodos. Recupera metade da vitalidade máxima, reduzida pela insônia do Devoto. Remove todos os ferimentos leves; graves precisam de kit; críticos, de um médico. Recupera a integridade da armadura, zera os usos das Cartas e devolve a Entropia inteira. A Carga do Abismo continua lá. E um clima de miasma pode impedir o descanso.

**Visual:** Tabela — **O que o descanso faz**

| Recurso | Efeito |
|---|---|
| Vitalidade | + metade do máximo, menos Insônia |
| Ferimentos | Leves somem; grave: kit; crítico: Médico |
| Entropia | Recompõe integral |
| Carga do Abismo | Intacta |
| Cartas | Contadores de uso zerados |
| Tempo | Avança 2 períodos e o clima |

### c12s04 — Encontros

**Narração:** Encontros não são sorteados pela IA. Eles disparam por condições: um alerta de fuga ativo, uma facção hostil dominando o local, uma ameaça iminente com perigo três ou mais, ou perigo efetivo quatro. Há intervalo mínimo entre encontros, maior no começo do jogo. Um herói de nível até três, descansando em zona não extrema de perigo baixo, não sofre emboscada: o descanso precisa recuperar.

**Visual:** Lista — **Regras de encontro**
  - Gatilhos: reforços, facção hostil, ameaça, perigo 4
  - Cooldown de 2 turnos, mais 2 até o nível 3
  - Força do encontro escala com o nível, exceto em zona apex
  - Descanso seguro no early-game em perigo até 3
  - Mesmo template no mesmo local duas vezes é descartado

### c12s05 — Orçamento de encontro

**Narração:** Quantos inimigos? Um orçamento decide. Lacaio custa dois, elite cinco, chefe doze. A base depende do perigo, somada ao nível e ao número de aliados, com um teto de sobrevivência. O corte nunca remove um chefe, prioriza variedade e, no nível um, permite no máximo um elite. Encontros fracos são reforçados com criaturas da região até um piso.

**Visual:** Exemplo passo a passo — **Orçamento num lugar de perigo 3**
  - Base por perigo: `7`
  - Nível do herói: `+2`
  - Aliados: `+2 por aliado: 0`
  - Orçamento: `9`
  - Teto de sobrevivência: `5 + 3 x nível = 11`
  - Composição: `1 elite (5) + 2 lacaios (4)`

### c12s06 — Tipos de encontro e percepção

**Narração:** Disparado o encontro, ele pode ser combate, armadilha, rastro ou social, com pesos que mudam com o perigo. Antes, um teste de percepção decide quem surpreende quem; ele sofre com clima e escuridão. Uma armadilha é testada e, se falhar, causa dano pelo pipeline normal. Um detalhe: percepção e armadilhas ainda usam um dado de vinte, um resquício do sistema antigo.

**Visual:** Tabela — **Tipos de encontro por perigo**

| Tipo | Perigo 1 a 2 | Perigo 3 a 4 |
|---|---|---|
| Combate | 50% | 60% |
| Rastro | 30% | 10% |
| Social | 20% | 10% |
| Armadilha | 0% | 20% |

### c12s07 — Clima e luz

**Narração:** O clima é uma cadeia de Markov por região, que avança a cada mudança de período. Há também fenômenos globais, como a Tempestade de Éter e a Noite Sem Estrelas, que podem começar a qualquer transição, com chance maior em lugares perigosos. A luz importa: à noite, ou em local escuro fora de abrigo, sem tocha, a percepção perde três e o acerto perde um.

**Visual:** Comparação — **Clima e luz como mecânica**
  - _Clima_: Markov por região a cada período · Eventos globais: 6% + 3% por perigo · Afeta percepção, ataque e viagem · Miasma bloqueia descanso · DoT ao ar livre
  - _Luz_: Escuro: noite ou tag dark, fora de abrigo · Percepção -3 sem luz · Acerto -1 sem luz · Tocha ou lanterna anula · Inimigos ainda sofrem no escuro natural

### c12s08 — Facções que avançam sozinhas

**Narração:** As facções têm vida própria. Cada uma tem um objetivo e um ritmo, e a cada período que passa seu progresso avança, sem sorteio. Ao chegar a cem, dispara uma ascensão escrita à mão: dominar um local, expandir para uma região, elevar o perigo, invocar uma entidade ou eliminar uma rival. O narrador só nomeia a facção se o jogador já a conhece; senão, descreve apenas a consequência sentida. Personagens revelam facções em níveis, e a reputação muda por impactos validados em Python.

**Visual:** Fluxo numerado — **O ciclo de uma facção**
  1. **Ritmo** — Progresso += ritmo por período, sem RNG
  2. **Ascensão** — Ao cruzar 100, efeito autoral no mundo
  3. **Efeitos** — Dominar, expandir, perigo, invocar, eliminar
  4. **Narração** — Nome só se a facção é conhecida
  5. **Descoberta** — Existência, objetivo, depois progresso
  6. **Reputação** — Delta fixado em Python, evento gravado

### c12s09 — Os ecos do mundo

**Narração:** Quando o tempo passa sem combate, numa viagem ou num descanso, o simulador do mundo pede ao modelo rápido um pulso: um rumor, um fato e uma mudança de perigo. O Python limita a mudança a um ponto para mais ou para menos e mantém o perigo entre um e quatro. O rumor aparece como eco do mundo. Só a consequência realmente aplicada vira memória; o fato livre do modelo é descartado. E facções desconhecidas só aparecem como sinais sem nome.

**Visual:** Exemplo passo a passo — **Um pulso do mundo**
  - Proposta do modelo: `rumor, fato e danger_shift +2`
  - Clamp em Python: `danger_shift vira +1`
  - Perigo do local: `2 para 3, dentro de 1 a 4`
  - Narração: `[ECOS DO MUNDO] e o rumor`
  - Memória gravada: `o perigo de X mudou de 2 para 3`
  - Descartado: `o fato livre, não verificado`

### c12s10 — Economia

**Narração:** A economia é inteiramente determinística. O preço base vem do item ou da raridade. Ele é multiplicado pela oferta: mais barato onde o item é produzido, normal se há produtor alcançável, caro e esgotado se todas as rotas até produtores estão bloqueadas. Facção hostil encarece em cinquenta por cento. Venda paga metade. E o sinal do ouro é sempre decidido pelo Python, nunca pela IA.

**Visual:** Fluxo numerado — **Como um preço é calculado**
  1. **Base** — value_gold ou raridade: 25 a 6000
  2. **Oferta** — 0,6 local; 1,0 alcançável; 1,8 bloqueado
  3. **Mercador** — Multiplicador próprio
  4. **Facção hostil** — Comprador paga x1,5
  5. **Venda** — x0,5
  6. **Arredonda** — Múltiplo de 5

### c12s11 — Mercadores, forja e saque

**Narração:** Mercadores têm estoque e repõem a cada três dias pelo relógio. Locais hostis escondem itens raros. Itens únicos já reivindicados somem das prateleiras. A forja valida local, classe, ingredientes e ouro. E o saque sorteia raridade pela faixa de perigo, de pools regionais, removendo antes do sorteio os únicos já reivindicados e os drops de criaturas que foram caçadas até quase sumir.

**Visual:** Lista — **Regras de comércio e saque**
  - Reposição determinística a cada 3 dias de relógio
  - Local hostil esconde itens raros ou melhores
  - Itens únicos: nunca duplicados, com evento de posse
  - Forja exige local, classe, ingredientes e ouro
  - Saque: raridade por perigo, ouro 3 a 12 vezes o perigo

### c12s12 — Exploração e ecologia

**Narração:** Explorar compensa. Ao chegar num lugar novo, um baú curado tem prioridade e só pode ser saqueado uma vez. Senão, há chance de um achado ambiental, crescente com o perigo, que nunca é um item único. O sorteio usa uma semente estável por jogo, local e turno. E existe ecologia: criaturas muito caçadas ficam suprimidas e saem do sorteio, até a população se recuperar, e vagas atraem migrantes vizinhos.

**Visual:** Painel de números — **Exploração e ecologia**
  - **12%+8%** — chance de achado por nível de perigo
  - **50%** — teto da chance de achado
  - **1 vez** — cada baú curado
  - **6 kills** — pressão de caça cai a 0,1
  - **20 turnos** — população volta ao normal

### c12s13 — Comitiva e aliados de cena

**Narração:** O herói pode ter companheiros. Recrutar exige relação de sete ou mais, comitiva com menos de três e facção não hostil, e a decisão é Python. Além disso, um personagem amigo presente na cena, com relação seis ou mais, vira aliado temporário no combate: no máximo dois, o dano reflete no personagem, e ele não entra para a comitiva. No inventário, consumíveis e materiais empilham, e há três espaços de equipamento: arma, armadura e acessório.

**Visual:** Comparação — **Party e inventário**
  - _Party e aliados_: Recrutar: relação 7+, party < 3 · Facção do NPC não pode ser hostil · Aliado de cena: relação 6+, máx. 2 · Companheiro ganha ficha v4 completa
  - _Inventário_: Entradas com id e quantidade · Consumíveis e materiais empilham · Slots: arma, armadura, acessório · Item único marcado e protegido

### c12s14 — Checkpoints e o laboratório

**Narração:** Dois sistemas fecham o mundo. Checkpoints são gravados a cada dez turnos ou ao entrar numa zona segura, mas nunca no meio de um combate ou transição de morte. E existe um laboratório de combate: uma arena isolada onde se escolhe classe, nível, inimigo e quantidade, usando o mesmo motor de produção, mas sem campanha, memória, saque, experiência nem checkpoints.

**Visual:** Comparação — **Dois modos especiais**
  - _Checkpoints_: A cada 10 turnos ou zona segura · Nunca em combate ou transição de morte · Slot único com a memória da sessão · Checkpoint inicial na criação
  - _Laboratório de combate_: Classe, nível 1, 3, 5 ou 10, inimigo e quantidade · Mesmo run_round de produção · Sem campanha, RAG, loot ou XP · Texto livre vira ataque básico

### c12s15 — Recapitulando o mundo sistêmico

**Narração:** Recapitulando. Relógio em cinco períodos, viagem com custo e névoa de guerra. Descanso que recupera e não recompõe Carga. Encontros por gatilho e orçamento. Percepção, clima e luz como modificadores. Facções com ritmo e ascensão, e ecos do mundo limitados em Python. Economia de oferta e rotas. Exploração com baús e achados. Ecologia de caça. Comitiva e aliados de cena. Checkpoints e um laboratório de combate.

**Visual:** Destaque (key) — **Recapitulação**: Relógio, viagem, descanso, encontros, clima, luz, facções, economia, exploração, ecologia, party e checkpoints são Python determinístico. A IA só descreve o que esses sistemas decidiram.

## C13 — A API, o streaming e a persistência

_Cor do capítulo: `#A0522D` · 13 cenas · 898 palavras (~6.0 min)_

### c13s01 — A fronteira do sistema

**Narração:** Toda a mecânica precisa de uma porta de entrada. Essa porta é uma A P I em Fast A P I, a única borda H T T P do projeto, com cerca de trinta rotas. Ela autentica, limita abusos, garante que um turno não rode duas vezes, transmite o progresso ao vivo e grava o estado de forma segura.

**Visual:** Cartão de abertura — **API e persistência** / _Rotas, streaming, saves, checkpoints e morte_

### c13s02 — As rotas

**Narração:** As rotas se dividem em grupos. Autenticação, que só existe nos perfis com banco. Dados estáticos, como opções de criação, introdução do mundo, mapa e catálogo do laboratório. Ciclo de jogo: prólogo, novo jogo, ação, ação com streaming, morte, equipar e subir de nível. Leitura: estado, Codex, histórico, saves, busca e exportação da crônica. Arte. E infraestrutura: saúde e métricas.

**Visual:** Tabela — **Catálogo de rotas**

| Grupo | Rotas principais |
|---|---|
| Auth (perfis com banco) | /auth/config, login, signup, refresh |
| Dados | /data/options, onboarding, map |
| Criação | /game/prologue, /game/new, simulador |
| Turno | action, action/stream, operations |
| Mutação | death, equip, levelup, DELETE save |
| Leitura | state, codex, history, saves, crônica |
| Arte e infra | /game/art/*, /health, /metrics |

### c13s03 — Middlewares

**Narração:** Antes de chegar às rotas, cada pedido passa por camadas. C O R S restringe as origens. Nos perfis com banco, uma fronteira de sessão confere o cookie de acesso e, em mutações, exige um token anti C S R F e uma origem permitida. Outra camada correlaciona e mede cada pedido. E um limitador barra mais de trinta pedidos por minuto por endereço nas rotas caras.

**Visual:** Grafo (LR) — **Camadas de um pedido HTTP**
  - Nós: Pedido HTTP [io]; CORS [infra]; Sessão e CSRF [infra]; Correlação e métricas [infra]; Rate limit [infra]; Rota [python]
  - Pedido HTTP → CORS
  - CORS → Sessão e CSRF (perfis DB)
  - Sessão e CSRF → Correlação e métricas
  - Correlação e métricas → Rate limit
  - Rate limit → Rota (30 por min)

### c13s04 — Streaming com garantia

**Narração:** A rota de streaming tem um desenho cuidadoso. Ela responde imediatamente com um evento de aceito e entrega o trabalho a uma thread separada, que é dona do lock, da execução e do save. Se o navegador desconectar, o turno termina e é gravado mesmo assim. Se o stream falhar, o cliente refaz o pedido normal com o mesmo identificador, sem duplicar.

**Visual:** Destaque (key) — **O worker SSE é dono do turno**: A thread worker segura o lock, roda o grafo e grava o save. Cliente desconectado não corta o turno. Ping a cada 10 s. Fallback POST com o mesmo action_id é idempotente.

### c13s05 — A resposta pública

**Narração:** A resposta é uma visão pública do estado. Leva a mensagem e seu tipo, a ficha com vitalidade, ferimentos, entropia e Carga, o inventário, o mundo com relógio, névoa, clima e luz, missões, personagens conhecidos, crônica, facções, comitiva e flags de morte. No combate, mostra só o que é público do inimigo: vitalidade, esquiva e o que já foi revelado. Detalhes internos e custos nunca saem.

**Visual:** Lista — **O que o GameResponse expõe**
  - message e message_type: STORY, COMBAT, NPC ou LOOT
  - player_stats: Vitalidade, Ferimentos, Entropia, Carga, Cartas
  - world: relógio, fog of war, clima, luz, rotas bloqueadas
  - combat: só o painel público do inimigo e a cena
  - death_pending, game_over, continuity e visual
  - Nunca: custo de LLM, traits ocultos, beats privados

### c13s06 — Saves atômicos e versionados

**Narração:** No perfil legado, cada jogo é um arquivo JSON com nome de U U I D, confinado à pasta de saves para impedir travessia de caminho. A escrita é atômica: grava num temporário, força o disco e troca, com até seis tentativas para tolerar travas do OneDrive e de antivírus. Cada save tem versão de esquema, hoje oito, e migrações puras e idempotentes atualizam saves antigos ao carregar.

**Visual:** Tabela — **Histórico do schema de save**

| Versão | O que mudou |
|---|---|
| v2 e v3 | NPC em camadas; 5 Posturas e Entropia |
| v4 | Virtudes, Vitalidade e Ferimentos |
| v5 | Vitalidade canônica e aliases de HP |
| v6 | Ledger visual |
| v7 | Metatempo: continuity |
| v8 | Crônica com IDs e progressão 1 a 20 |
| Abaixo de v4 | Arquivado: somente leitura |

### c13s07 — A tela de morte

**Narração:** Quando o herói morre de verdade, no combate ou num descanso fatal, o estado fica com morte pendente, e tanto o grafo quanto a A P I recusam novos turnos. A interface abre a tela de morte com duas opções. Continuar do checkpoint restaura o último ponto seguro, inclusive a memória vetorial daquela época. Aceitar a morte transforma o save num memorial, com o evento de morte e um marco na crônica.

**Visual:** Grafo (TB) — **Do golpe fatal à escolha**
  - Nós: Morte real confirmada [python]; death_pending [data]; Tela de morte [io]; Continuar do checkpoint [python]; Aceitar a morte [python]; Estado restaurado [data]; Memorial game_over [data]
  - Morte real confirmada → death_pending
  - death_pending → Tela de morte
  - Tela de morte → Continuar do checkpoint
  - Tela de morte → Aceitar a morte
  - Continuar do checkpoint → Estado restaurado (epoch + 1)
  - Aceitar a morte → Memorial game_over (player_died)

### c13s08 — Metatempo

**Narração:** Restaurar cria uma questão filosófica: que horas são? O projeto separa dois relógios. O turno canônico do mundo volta ao do checkpoint. Mas o contador de ações da sessão nunca retrocede, e uma época da linha do tempo sobe a cada restauração. O histórico de mortes guarda o que foi mantido e o que foi revertido, e a tela de morte mostra exatamente quantos turnos serão perdidos.

**Visual:** Exemplo passo a passo — **Restauração após uma morte**
  - Turno da morte: `73`
  - Último checkpoint: `70`
  - Turnos revertidos: `3`
  - Mantém: `histórico de mortes e ações da sessão`
  - Reverte: `mundo, inventário, posição e memória`
  - timeline_epoch: `1 para 2`

### c13s09 — O log de cada turno

**Narração:** Cada turno deixa uma única linha de log em JSON, pensada para não vazar nada. O jogo aparece por um pseudônimo, não pelo identificador real. Há rota, latência, eventos aplicados e rejeitados, custo estimado e as tentativas de modelo. Um erro registra só o nome da exceção, nunca a mensagem, e o jogador recebe um erro quinhentos genérico. Métricas no formato do Prometheus medem duração por rota, commits, banco e o tempo até o primeiro evento do streaming.

**Visual:** Exemplo passo a passo — **Uma linha rpg.turn**
  - evt: `turn`
  - game_id_ref: `pseudônimo HMAC, não o id`
  - route e latency_ms: `storyteller, 14230`
  - events: `aplicados 1, rejeitados 0`
  - llm: `provider, tier, fallback e custo`
  - error: `só o nome da exceção, se houver`

### c13s10 — Histórico estável para o cliente

**Narração:** O histórico que o jogador vê não é a lista curta de mensagens que o modelo recebe. Ele é um registro separado e paginado, com uma linha para cada ação e cada narração, e um identificador derivado do jogo, da época e do turno, para nunca duplicar. A paginação usa um cursor com a época da linha do tempo: depois de uma restauração, um cursor antigo é recusado, para não misturar linhas de linhas do tempo diferentes. Saves antigos ganham um histórico reconstruído, marcado como parcial.

**Visual:** Comparação — **Dois históricos**
  - _Transcrito do modelo_: Últimas 20 mensagens na API · Entrada curta do grafo · Reescrito pelas guardas
  - _Histórico de apresentação_: Linhas de jogador e narrador · Id por jogo, época e turno · Cursor época e offset · Cursor de outra época: 409

### c13s11 — Mover saves com segurança

**Narração:** Para migrar saves de arquivo para o banco, há uma ferramenta que mostra antes de agir. A varredura classifica cada arquivo e calcula seu hash, sem escrever nada. A importação só insere: repetir uma importação idêntica pula, e uma colisão com conteúdo diferente falha. A exportação gera um pacote portátil por dono, com hashes independentes que podem ser verificados depois. A mesma serialização serve ao arquivo, ao checkpoint e ao banco.

**Visual:** Fluxo numerado — **Transferência preview-first**
  1. **Scan** — Classifica e calcula SHA-256, sem escrita
  2. **Preview** — O operador vê o que vai acontecer
  3. **Import** — Insert-only; idêntico pula, divergente falha
  4. **Export** — Pacote portátil por dono com hashes
  5. **Verify** — Confere o pacote exportado

### c13s12 — Jogar no terminal

**Narração:** Além do navegador, dá para jogar pela linha de comando, sobre o mesmo grafo. O terminal carrega o save mais recente ou abre um assistente de criação. Comandos locais como status e equipar não gastam turno. A cada ação, imprime a mensagem final, resolve escolhas de nível, grava o save e, na morte, oferece continuar do checkpoint ou aceitar o fim. Uma diferença: se um turno falha, o terminal avisa e segue sem gravar aquele turno.

**Visual:** Comparação — **Terminal versus A P I**
  - _Linha de comando_: Mesmo grafo compilado · Mantém 15 mensagens · Erro: avisa e continua o loop · Sem login nem streaming
  - _API web_: Mesmo grafo compilado · Mantém 20 mensagens · Erro: 500 genérico, save anterior · Login nos perfis com banco, SSE

### c13s13 — Recapitulando a API

**Narração:** Recapitulando. Uma única borda com trinta rotas, protegida por C O R S, sessão, C S R F, correlação e limite de taxa. Streaming em que a thread é dona do turno. Resposta pública sem vazar o interno. Saves atômicos com esquema versionado e migrações. E uma tela de morte com checkpoint, memorial e um metatempo que lembra das mortes mesmo depois de voltar no tempo.

**Visual:** Destaque (key) — **Recapitulação**: Uma borda HTTP com middlewares de segurança, SSE com worker dono do turno, resposta pública, saves atômicos versionados (v8) e morte com checkpoint, memorial e metatempo.

## C14 — O frontend e a jornada do jogador

_Cor do capítulo: `#B8943F` · 10 cenas · 633 palavras (~4.2 min)_

### c14s01 — A cara de Valoria

**Narração:** Agora, o que o jogador vê. O cliente principal é um aplicativo React com Vite e TypeScript, num tom escuro medieval inspirado em The Witcher, com animações suaves e brasas flutuando ao fundo. Neste capítulo percorremos a jornada do jogador, tela a tela, e os detalhes que tornam a experiência robusta.

**Visual:** Cartão de abertura — **Frontend e jornada** / _React, Vite e TypeScript em tom dark medieval_

### c14s02 — Uma máquina de telas

**Narração:** O aplicativo não usa roteador de páginas. Ele é uma máquina de telas: abertura, login quando exigido, lista de saves, criação, jogo e laboratório. Ao abrir, consulta se a autenticação é exigida. Se houver saves, mostra a lista para continuar; senão, vai direto para a criação. Uma sessão expirada dispara um evento que devolve ao login.

**Visual:** Grafo (LR) — **Telas do aplicativo**
  - Nós: Bootstrap [io]; Login [io]; Saves [io]; Criação [io]; Laboratório [io]; Jogo [io]
  - Bootstrap → Login (auth exigida)
  - Bootstrap → Saves
  - Bootstrap → Criação (sem saves)
  - Login → Saves
  - Saves → Criação
  - Saves → Jogo (continuar)
  - Criação → Jogo
  - Criação → Laboratório

### c14s03 — A criação imersiva

**Narração:** A criação é um assistente de cinco passos. O Mundo apresenta Valoria. Origem mostra seis raças com arte e traços. Vocação mostra as cinco Posturas. Região mostra os bônus de cada lugar. Identidade pede nome, história e aparência. Por fim, um prólogo gerado pelo modelo inteligente propõe um arco pessoal com personagens semente. Você pode refinar ou começar a jornada.

**Visual:** Fluxo numerado — **Assistente de criação**
  1. **O Mundo** — Introdução de Valoria, ou pular
  2. **Origem** — 6 raças com arte e traços mecânicos
  3. **Vocação** — As 5 Posturas diante do Abismo
  4. **Região** — 12 regiões com bônus
  5. **Identidade** — Nome, história, aparência, brief de arte
  6. **Prólogo** — Arco pessoal, beats e NPCs semente
  7. **Começar** — /game/new semeia arco, NPCs e cena

### c14s04 — O prólogo e uma lição

**Narração:** O prólogo deixou uma lição. A primeira versão do esquema tinha limites rígidos de tamanho, e todos os provedores escreviam um pouco além: o validador derrubava tudo e o jogo caía sempre no modelo padrão. A solução foi deixar o tamanho como dica para a IA, truncar em Python e aplicar limites estritos só na entrada da A P I. O modelo falso nunca teria mostrado isso.

**Visual:** Destaque (info) — **Padrão para todo schema novo**: Tamanho vira dica na description; Python trunca e normaliza; limites estritos só na borda da API, com erro 422. O MockLLM não detecta esse tipo de falha: smoke real obrigatório.

### c14s05 — A tela de jogo

**Narração:** A tela de jogo tem uma barra superior com local, dia, período, clima e luz. Uma ilustração do lugar. O registro da narrativa com efeito de máquina de escrever. Uma barra de ação para escrever livremente. E um painel lateral com oito abas: ficha, combate, personagens, mapa, facções, missões, crônica e Codex. No celular, o painel vira uma gaveta deslizante.

**Visual:** Lista — **O HUD em oito abas**
  - Ficha: Vitalidade, Entropia, Carga, Virtudes e equipamento
  - Combate: inimigos públicos, iniciativa e condições
  - Personagens e Facções: relações e reputação
  - Mapa: névoa de guerra, clique para viajar
  - Missões e Crônica: busca e exportação
  - Codex: conhecimento descoberto, carregado sob demanda

### c14s06 — Combate na interface

**Narração:** No combate, a tela muda. Aparece uma mão de Cartas preparadas, cada uma com custo, frequência, estado e botão de Ruptura quando pronta. Um seletor de reação escolhe uma carta para a rodada. Há a trilha de ferimentos, as zonas da cena e botões de manobra: engajar, guardar, esconder, procurar e fugir. O texto enviado é cosmético: o servidor usa o identificador estruturado da carta.

**Visual:** Exemplo passo a passo — **Clique em uma Carta**
  - Jogador clica: `Jogar Carta: Golpe Sombrio`
  - Texto enviado: `Uso Golpe Sombrio.`
  - Campos estruturados: `card_id, target_id, ruptura`
  - Reação da rodada: `reaction_card_id escolhido antes`
  - No servidor: `vira combat_declaration, sem LLM`
  - Resultado: `rodada resolvida em Python e narrada`

### c14s07 — Ação pendente e retomada

**Narração:** A interface leva a robustez a sério. Antes de enviar, grava a ação pendente no armazenamento local, com um identificador e um hash do pedido. Se a aba fechar, ao voltar ela pergunta ao servidor se a operação terminou. Respostas atrasadas de outra sessão são descartadas. Um 401 dispara uma única renovação de sessão compartilhada. E tudo respeita a preferência por menos movimento.

**Visual:** Lista — **Robustez no cliente**
  - Ação pendente em localStorage com UUID e hash do payload
  - Retomada: consulta a operação antes de reenviar
  - Contador de sessão descarta respostas atrasadas
  - Refresh de sessão single-flight em 401
  - Fallback POST com o mesmo action_id se o stream falhar
  - Reduced motion desliga animações e brasas

### c14s08 — Saves, modais e primeiros passos

**Narração:** Outras telas completam a jornada. A lista de saves mostra cada herói com classe, nível, local e dia, com selos para memorial e laboratório, e pede confirmação antes de apagar uma saga. Quando há escolhas de nível, um modal pergunta subclasse, Carta, Virtude ou Maestria, e pode ser adiado. A tela de morte mostra o que será mantido e revertido. E no primeiro turno, uma dica dispensável lista exemplos de comandos.

**Visual:** Tabela — **Telas e modais de apoio**

| Elemento | Papel |
|---|---|
| SaveScreen | Continuar, apagar, nova jornada |
| LevelUpModal | Subclasse, Carta, Virtude, Maestria |
| DeathModal | Continuar do checkpoint ou aceitar |
| Overlay de memorial | Começar de novo ou ler a crônica |
| OnboardingHint | Exemplos de comando no turno 1 |
| Banners | Modo simulado ou degradado, uma vez |

### c14s09 — Tema, celular e acessibilidade

**Narração:** O visual usa tokens de cor num espaço perceptual, dourado sobre bronze escuro, com fontes de inspiração medieval para títulos e uma serifada clássica para o texto. Abaixo de novecentos pixels, o painel lateral vira uma gaveta; em telas de celular, ocupa a largura toda, com botão de fechar. A preferência por menos movimento desliga animações e brasas. E dezesseis jornadas automatizadas verificam acessibilidade e layout em quatro larguras de tela.

**Visual:** Painel de números — **Interface verificada**
  - **900 px** — HUD vira gaveta deslizante
  - **390 px** — largura de celular validada
  - **16** — jornadas F01 a F16 no Playwright
  - **4** — viewports: 320, 390, 768 e 1440
  - **0** — violações a11y sérias ou críticas

### c14s10 — Recapitulando o frontend

**Narração:** Recapitulando. Uma máquina de telas em React, com criação em cinco passos e um prólogo pessoal. Uma tela de jogo com narrativa animada, ilustração do lugar e um painel de oito abas. Combate tático com mão de Cartas e manobras estruturadas. E uma camada de robustez com ações pendentes, retomada e renovação de sessão. Ainda existe um cliente legado sem build, usado só se o novo não estiver compilado.

**Visual:** Destaque (key) — **Recapitulação**: SPA em máquina de telas; criação em 5 passos com prólogo; HUD de 8 abas; combate com Cartas e manobras estruturadas; ação pendente, retomada e refresh single-flight. Cliente vanilla legado como fallback.

## C15 — Arte visual: curada e dinâmica

_Cor do capítulo: `#8A6D2F` · 6 cenas · 387 palavras (~2.6 min)_

### c15s01 — Imagens com critério

**Narração:** Um R P G de texto ganha muito com algumas imagens bem escolhidas. O projeto tem duas fases de arte. Uma usa ilustrações curadas, escolhidas sem nenhuma IA na hora do jogo. A outra gera arte rara sob demanda, com orçamento rígido, desligada por padrão. Em ambas, a escolha da imagem é determinística: a IA nunca decide qual arquivo mostrar.

**Visual:** Cartão de abertura — **Arte visual** / _Fase 8A curada e Fase 8B dinâmica_

### c15s02 — A arte curada

**Narração:** A fase curada tem quarenta e cinco ilustrações em noventa versões otimizadas, nos tamanhos miniatura e exibição: seis raças, cinco classes, vinte e dois locais e doze personagens. Locais sem arte própria usam uma arte da região. Um importador valida hash e visibilidade, remove metadados e respeita limites de bytes. Personagens secretos nunca entram no catálogo público.

**Visual:** Painel de números — **Catálogo curado**
  - **45** — ilustrações aprovadas
  - **90** — arquivos WebP: thumb e display
  - **22** — locais com arte exata
  - **13** — locais com fallback regional
  - **12** — retratos de NPC

### c15s03 — Primeira aparição

**Narração:** Quando um personagem conhecido aparece pela primeira vez na cena, a interface mostra seu retrato antes do texto. A identidade vem de identificadores canônicos e apelidos, nunca de procurar nomes na prosa. Um personagem gerado em jogo sem arte recebe um monograma, e nunca empresta o rosto de outro. O registro é por ação, então repetir o pedido devolve a mesma imagem, no stream e no pedido normal.

**Visual:** Fluxo numerado — **Cue visual de NPC**
  1. **Elegíveis** — Conhecidos, em cena e ainda não vistos
  2. **Escolha** — NPC ativo ou o que acabou de entrar
  3. **Identidade** — ID canônico e aliases, nunca a prosa
  4. **Sem arte** — Monograma: nunca outro rosto
  5. **Ledger** — Por action_id: retry mostra a mesma

### c15s04 — A arte dinâmica rara

**Narração:** A fase dinâmica gera imagens com um modelo de imagem pinado numa versão exata. Ela é rara de propósito: um retrato do jogador, com uma única reformulação, e por arco de campanha até quatro personagens novos sem arte, com intervalo de quinze turnos, e um momento épico, como um combate contra chefe. Escolher subclasse nunca gera imagem. O jogador revisa o pedido antes e confirma o custo possível.

**Visual:** Tabela — **Gatilhos e orçamento da arte dinâmica**

| Gatilho | Limite |
|---|---|
| Retrato do jogador | 1 + 1 reformulação |
| NPC sem arte curada | 4 por arco, cooldown 15 turnos |
| Momento épico | 1 por arco: combate com chefe |
| Escolha de subclasse | Zero jobs, zero custo |
| Resultado incerto | Nunca regenerado automaticamente |

### c15s05 — O pipeline da arte dinâmica

**Narração:** Por dentro, a arte dinâmica é um pipeline com várias travas. O pedido nasce de um brief com âncoras de estilo, raça e classe, e o texto do jogador é higienizado contra injeção de instruções. A reserva entra no orçamento do arco e vira um job. O trabalhador chama o gerador uma única vez, valida e converte a imagem para WebP sem metadados, e grava num armazenamento privado. O cliente acompanha o estado e recebe endereços assinados de curta duração.

**Visual:** Fluxo numerado — **Da ideia ao retrato**
  1. **Brief** — Âncoras de estilo; texto do jogador higienizado
  2. **Reserva** — Orçamento por arco e id determinístico
  3. **Job** — Na mesma transação do turno, nos perfis DB
  4. **Geração** — Uma chamada ao modelo de imagem pinado
  5. **Processamento** — Até 20 MiB; WebP full e thumb sem EXIF
  6. **Storage privado** — Chave users, dono, jogo, sha
  7. **Cliente** — Polling com backoff; URL assinada 300 s
  8. **Restore** — Gerações da linha descartada: superseded

### c15s06 — Recapitulando a arte

**Narração:** Recapitulando. Arte curada com catálogo validado, retratos na primeira aparição e escolha sempre determinística. Arte dinâmica rara, opcional e com orçamento por arco, produzida por um trabalhador em segundo plano que processa a imagem, remove metadados e grava num armazenamento privado. E uma regra de ouro: nunca cobrar duas vezes por um resultado incerto.

**Visual:** Destaque (key) — **Recapitulação**: Arte curada: 45 ilustrações, escolha por ID canônico. Arte dinâmica: modelo pinado, orçamento por arco, revisão e confirmação do jogador, worker com storage privado e proteção contra cobrança dupla.

## C16 — Infraestrutura local-first

_Cor do capítulo: `#3D7A5C` · 14 cenas · 947 palavras (~6.3 min)_

### c16s01 — Do laboratório ao serviço

**Narração:** Até aqui, o jogo pode rodar com arquivos JSON e índices em disco, travado por processo. Isso basta para um jogador local, mas não para muitos usuários. A fase dez b transformou o armazenamento num plano substituível: o domínio fala com portas, e adaptadores implementam cada porta para dois mundos. Tudo foi ensaiado localmente, com custo zero, antes de qualquer nuvem.

**Visual:** Cartão de abertura — **Infraestrutura local-first** / _Portas, Postgres, leases, outbox e operação_

### c16s02 — Portas e perfis

**Narração:** As portas são contratos em Python: guardar jogos, catálogo de runtime, memória, arquivos binários, fila de jobs, coordenador de turnos, limitador de taxa e verificador de identidade. Um perfil escolhe os adaptadores. O legado usa arquivos e memória em processo. O perfil local usa Postgres e Supabase. Os perfis portátil e hospedado trocam Supabase por O I D C e armazenamento S três.

**Visual:** Tabela — **Perfis de runtime**

| Perfil | Jogos e fila | Blob e auth |
|---|---|---|
| legacy | Arquivos, inline | Arquivos, sem login |
| local | Postgres e pgvector | Supabase Storage e Auth |
| portable | Postgres e pgvector | S3 e OIDC |
| hosted | Postgres e pgvector | S3 e OIDC, sem loopback |

### c16s03 — Nunca segurar transação durante a IA

**Narração:** A decisão mais importante da camada durável: nenhuma transação fica aberta enquanto um modelo de linguagem pensa. A mutação acontece em duas fases curtas. Primeiro, uma transação reivindica o jogo e cria uma operação com um prazo. Depois o grafo roda fora de qualquer transação. Por fim, uma segunda transação confere o prazo e a versão e grava tudo de uma vez.

**Visual:** Fluxo numerado — **Turno durável em duas fases**
  1. **Recibo?** — Operação já concluída devolve o recibo
  2. **Claim** — Trava jogo, cria operação com lease de 180 s
  3. **Grafo** — Roda fora de transação, com heartbeat
  4. **Commit** — Confere lease, token e versão
  5. **Grava** — Jogo, eventos, recibo, custo, jobs
  6. **Libera** — Limpa a operação ativa do jogo

### c16s04 — Lease e fencing

**Narração:** O mecanismo de exclusão usa dois conceitos. Lease é um empréstimo com prazo: o trabalhador tem o jogo por cento e oitenta segundos e renova a cada quarenta e cinco. Fencing é um token: o commit só passa se o token gravado for o mesmo do claim. Assim, um trabalhador atrasado não consegue publicar. E a ordem de travas é fixa, para evitar impasses.

**Visual:** Destaque (key) — **Lease mais fencing**: Lease: posse com prazo, renovada por heartbeat a cada lease/4. Fencing: o commit exige o mesmo lease_token e a versão base. Worker atrasado não publica. Locks sempre na ordem jogo, depois operação.

### c16s05 — Exatamente uma vez

**Narração:** O cálculo pode acontecer mais de uma vez em caso de falha, mas o commit acontece exatamente uma vez por chave. A tabela de operações é um livro de idempotência e recibos. Repetir a chave com o mesmo pedido devolve o recibo. Repetir com um pedido diferente é um conflito. E uma chave de outro dono responde indisponível, sem revelar que existe.

**Visual:** Tabela — **Respostas da reivindicação**

| Situação | Resposta |
|---|---|
| Chave nova, jogo livre | Claim com novo lease |
| Chave concluída | Devolve o recibo gravado |
| Mesma chave, payload diferente | 409 conflito |
| Outra operação ativa | 409 game_busy |
| Lease expirado | Retomada com token novo |
| Chave de outro dono | Indisponível, sem vazar |

### c16s06 — Outbox de memória

**Narração:** A memória segue um padrão chamado outbox. Durante o turno, os fatos de memória não são gravados, apenas acumulados. Só no commit eles são escritos, na mesma transação, junto com um job de cálculo de embedding. Se o turno não commitar, o fato não existe. Um trabalhador separado calcula o vetor depois. Se o serviço de embeddings cair, o turno continua válido e o job tenta de novo.

**Visual:** Grafo (LR) — **Outbox de memória no Postgres**
  - Nós: Turno no grafo [llm]; Efeitos acumulados [python]; commit_game [infra]; memory_documents [data]; Job embed_memory [data]; Worker de embeddings [infra]; Vetor pronto [data]
  - Turno no grafo → Efeitos acumulados
  - Efeitos acumulados → commit_game (flush)
  - commit_game → memory_documents
  - commit_game → Job embed_memory
  - Job embed_memory → Worker de embeddings
  - Worker de embeddings → Vetor pronto

### c16s07 — Banco e segurança

**Narração:** O esquema vive em migrações versionadas. Um esquema próprio guarda jogos como documento JSON com versão otimista, checkpoints, eventos imutáveis com hash, operações, turnos, jobs e limites de taxa. A primeira barreira é o filtro explícito pelo dono em cada consulta. A segunda é a segurança em nível de linha, ligada e forçada nas tabelas, com uma função que extrai o dono do token e um papel sem poder de contorná-la. Testes de banco provam o isolamento entre usuários.

**Visual:** Lista — **Defesas do banco**
  - RLS ligada e forçada; policy owner_id = dono do token
  - Papel rpg_api sem login e sem bypass de RLS
  - anon e authenticated sem acesso ao schema app
  - Eventos imutáveis: hash divergente vira conflito
  - Cookies HttpOnly, CSRF assinado e Origin na allowlist
  - 14 asserts de banco e testes de isolamento A e B

### c16s08 — Identidade, cookies e CSRF

**Narração:** Nos perfis com banco, o navegador nunca guarda um token de acesso legível. A sessão vive em cookies HttpOnly, e toda mutação exige um token anti C S R F assinado, igual no cookie e no cabeçalho, e uma origem permitida. O cookie de renovação só vale para a rota de renovação. A identidade é verificada pelo Supabase Auth no perfil local, ou por O I D C nos perfis portátil e hospedado. E a chave de serviço nunca pode cair no pacote do navegador.

**Visual:** Lista — **Fronteira de sessão**
  - Cookies HttpOnly de acesso e refresh; CSRF legível
  - Mutação: CSRF assinado igual em cookie e header
  - Origin obrigatória e na allowlist
  - Refresh só em /auth/refresh com SameSite Strict
  - Service role com prefixo VITE_ é recusada

### c16s09 — Trabalhadores e a cerca dos jobs

**Narração:** Os trabalhadores processam três tipos de job: calcular embeddings de memória, comprimir capítulos da crônica e gerar arte dinâmica. Cada um pega um job por vez, com prazo renovado por batimento. Toda escrita derivada trava a linha do job na mesma transação e confere o token: quem perdeu o prazo não publica. Falhas esperam cada vez mais, até a fila morta. E a arte nunca é tentada de novo quando o resultado externo é incerto.

**Visual:** Tabela — **Os três jobs**

| Job | O que faz | Proteção |
|---|---|---|
| embed_memory | Calcula o vetor do fato | Confere hash e perfil |
| compress_chronicle | Digest do capítulo | Raw segue autoritativo |
| generate_dynamic_art | Gera e grava a imagem | Sem retry se incerto |
| Todos | Lease, heartbeat e fence | Backoff até dead-letter |

### c16s10 — Arquivos e armazenamento

**Narração:** Imagens geradas e outros binários passam por uma porta de armazenamento com três implementações: arquivos locais, Supabase Storage e qualquer serviço compatível com S três. Toda chave começa com o dono, o que casa com as políticas de acesso do bucket privado. O bucket aceita só imagens WebP de até vinte megabytes. A arte curada, por outro lado, não passa por aqui: é servida como arquivo estático junto com o frontend.

**Visual:** Comparação — **Dois caminhos para imagens**
  - _Arte dinâmica_: BlobStore: arquivo, Supabase ou S3 · Chave users, dono, jogo e hash · Bucket privado rpg-dynamic · URL assinada de curta duração
  - _Arte curada_: 90 WebPs no frontend · Servida como arquivo estático · Catálogo com hash e visibilidade · Sem storage nem custo

### c16s11 — Fila, observabilidade e backup

**Narração:** A fila de jobs usa travas que pulam linhas ocupadas, recupera jobs de trabalhadores mortos e aplica espera exponencial até virar fila morta. A observabilidade tem dezessete métricas com rótulos fechados, rastreamento opcional e uma pilha local com Prometheus, Grafana, coletor e Tempo, com sete alertas. E há backup com manifesto de hashes e restauração medida em trinta e seis segundos.

**Visual:** Painel de números — **Prontidão local medida**
  - **32 ms** — commit p95 no teste de carga
  - **5 de 5** — cenários de caos convergiram
  - **1.000** — turnos de soak, zero erros
  - **36 s** — RTO medido de DB, Auth e Storage
  - **RPO 0** — para turnos confirmados
  - **7** — alertas validados

### c16s12 — Operar o laboratório

**Narração:** A operação local tem ferramentas com cinto de segurança. Um script sobe, consulta e para a pilha do Supabase local, e recusa rodar contra um projeto remoto. O backup só opera em contêineres com o rótulo do laboratório e gera um manifesto de hashes; a restauração exige confirmação explícita e destino vazio. Operações presas são listadas em modo de prévia, e só são abandonadas com um comando de aplicação, se o prazo já expirou.

**Visual:** Tabela — **Runbook de incidentes locais**

| Incidente | Ação |
|---|---|
| API caiu antes do commit | Repetir o mesmo action_id |
| Worker morreu | Outro assume após o lease; fencing |
| Operação presa | recover_operations em preview |
| Embedding ou blob fora | Turno segue canônico; job reconverge |
| Banco reiniciado | Reiniciar API e worker; repetir chave |
| Backup inválido | Não restaurar |

### c16s13 — Prontidão G0 a G7

**Narração:** Antes de declarar a infraestrutura pronta, o projeto passou por oito portões, registrados num relatório gerado com dados redigidos. Suíte offline, integração local com Postgres, Auth e Storage, segurança, caos, carga com vários processos, mil turnos de resistência, backup e restauração, e por fim navegador, build, linters e auditorias. O veredito em agosto foi pronto para uso local. A nuvem segue fora desse veredito.

**Visual:** Tabela — **Os portões de prontidão**

| Portão | Evidência |
|---|---|
| G0 | Suíte offline verde |
| G1 e G2 | infra 13/13, pgTAP 14/14, security 5/5 |
| G3 e G4 | Caos 5 de 5; commit p95 32 ms |
| G5 | Soak de 1.000 turnos, zero erros |
| G6 | Backup e restore: RPO 0, RTO 36 s |
| G7 | Browser, build, audits e 7 alertas |

### c16s14 — Recapitulando a infra

**Narração:** Recapitulando. Portas e adaptadores permitem trocar arquivos por Postgres sem mudar o domínio. Nenhuma transação durante a IA: claim curto, grafo livre, commit curto. Lease mais fencing garantem um dono por vez. Commit exatamente uma vez por chave. Outbox para memória. Segurança em nível de linha. E tudo certificado localmente; a certificação em nuvem ainda é um rascunho.

**Visual:** Destaque (key) — **Recapitulação**: Portas e perfis; claim, grafo e commit sem transação durante a IA; lease, fencing e commit exactly-once; outbox de memória; RLS forçada; observabilidade e backup. Cloud ainda não certificada.

## C17 — Qualidade: testes, playtest e evals

_Cor do capítulo: `#4B5A8A` · 15 cenas · 989 palavras (~6.6 min)_

### c17s01 — Como se garante um jogo de IA

**Narração:** Como garantir que um jogo movido por IA funciona, se a IA é imprevisível? A resposta do projeto é uma pilha de garantias, das mais baratas às mais caras: testes offline, linters de conteúdo, um harness de playtest que joga campanhas inteiras, uma plataforma de avaliações determinísticas e um processo em que nada é feito sem especificação.

**Visual:** Cartão de abertura — **Qualidade** / _Testes, playtest agêntico, invariantes e evals_

### c17s02 — A pirâmide de garantias

**Narração:** Na base, a suíte de testes, com cerca de mil e novecentos testes, roda sem rede em alguns minutos e é o portão de toda tarefa. Acima, o lint de conteúdo e de código. Depois, o playtest agêntico, offline ou com modelo real. Depois, os evals com réguas travadas. E no topo, a cara e rara validação com provedor pago.

**Visual:** Fluxo numerado — **Camadas de garantia, da base ao topo**
  1. **Suíte offline** — 1.898 testes com MockLLM, sem rede
  2. **Linters** — Conteúdo, Ruff e build do frontend
  3. **Playtest offline** — 14 perfis jogam campanhas longas
  4. **Evals determinísticos** — Datasets travados por hash
  5. **Contratos reais** — Markers opt-in, com teto de custo
  6. **Matriz real** — 10 campanhas de 200 turnos

### c17s03 — A suíte offline

**Narração:** A suíte força o modelo falso em todos os testes e isola saves, memória e cache em pastas temporárias. Testes que dependem de modelo real, banco local ou navegador ficam fora do padrão, atrás de marcadores. Há testes por fase e por domínio: combate, classes, playtest, evals, infraestrutura, arte e até a integridade do índice de especificações.

**Visual:** Código — **O que fica fora da suíte padrão** (`pyproject.toml`)

```bash
addopts = "-q -m \"not llm_contract and not llm_playtest\""
markers = [
    "llm_contract: contrato contra provider LLM real (...)",
    "llm_playtest: campanha curta de playtest por perfil (...)",
    "infra_local: integração opt-in com Postgres/Auth/...",
    "security_local: testes opt-in de RLS, CSRF, ownership (...)",
    "chaos_local: testes opt-in de kill/restart/timeouts (...)",
    "browser_local: browser real opt-in contra servidor local",
]
```

### c17s04 — O harness de playtest

**Narração:** Robôs jogam campanhas inteiras sobre o mesmo grafo de produção. São catorze perfis determinísticos, cada um com uma personalidade: o agressivo, o explorador, o comerciante, o diplomático, o troll que manda absurdos, o que tenta quebrar o mapa, o caçador de segredos, o fujão, o recrutador e o jogador normal, que mistura tudo com prudência.

**Visual:** Tabela — **Alguns dos 14 perfis**

| Perfil | O que testa |
|---|---|
| Explorador | Fronteira do mapa, sem ir e voltar |
| Comerciante | Livro de cotações e conservação de ouro |
| Troll | Absurdos e injeção de prompt |
| SecretRusher | Pergunta direto pelos segredos |
| Fujao | Fuga e trilha de perseguição |
| LootAbuser | Tenta duplicar item único |
| Normal | Jogador curioso, só visão pública |

### c17s05 — Invariantes

**Narração:** A cada turno, dezenas de invariantes verificam o estado. Vitalidade coerente, ouro sem negativos, item único sem duplicata, resumo dentro do limite, memória sem confirmação sem fonte, narração sem vazamento de instruções, sem morte falsa, combate sem zumbi, latência abaixo de noventa segundos. Só violações de nível erro reprovam a campanha. E cada defeito sistêmico achado vira uma invariante nova.

**Visual:** Lista — **Exemplos de invariantes**
  - vitality.consistency e wound.capacity: error
  - economy: ouro sem negativo, único sem duplicata
  - memory.summary_bounds e confirmed_without_source
  - narrative.meta_leak e false_player_death: error
  - combat.zombie com idle_turns 5 ou mais: error
  - performance: warning acima de 45 s, error acima de 90 s

### c17s06 — Cenários dirigidos e relatórios

**Narração:** Simulações aleatórias às vezes demoram a cair no caso que interessa. Por isso existem cenários dirigidos, com pré-condição, ação e oráculo fechados: um de recrutamento, com uma personagem específica, e um de comércio, com duzentas moedas. Cada campanha grava uma linha JSON por turno e um resumo. O relatório agrega rotas, violações, mortes, classes e custo, e o transcrito mostra ação e narração lado a lado, para julgar a prosa à mão.

**Visual:** Lista — **O que o harness produz**
  - Cenários recrutamento e comércio, fora do --all
  - JSONL por turno: rota, latência por nó, violações, LLM
  - Resumo: % combate, funil de quests, mortes, Entropia
  - report: Markdown com baseline opcional
  - transcript: ação e narração turno a turno

### c17s07 — Modo real, com freio

**Narração:** O modo real tem freio. Há teto de pedidos e de custo por campanha, um vigia que aborta turnos que passam do prazo absoluto, inclusive depois de o notebook suspender, e uma regra de falhar fechado: se um grupo de tentativas termina sem nenhum sucesso, a matriz para. Sem isso, a resiliência do produto mascarava um provedor morto e produzia uma linha de base falsa.

**Visual:** Destaque (warn) — **Fail-closed no playtest real**: Tentativas são agrupadas por invoke; o primeiro grupo sem sucesso aborta a matriz e nenhum par seguinte começa. Nasceu das matrizes A0 e A1, que mediram fallback em vez do modelo.

### c17s08 — Preflight, presets e trava

**Narração:** Antes de gastar dinheiro numa matriz, três salvaguardas. Um preflight real faz uma chamada estruturada em cada classe de modelo e aborta se algo falhar. Presets de rotas isolam o experimento: o preset pago usa só o DeepSeek, sem misturar provedor nem mock, com um tempo limite maior só para o teste. E uma trava de arquivo impede duas matrizes ao mesmo tempo, depois que um processo órfão competiu por cota e contaminou uma medição.

**Visual:** Fluxo numerado — **Antes de uma matriz real**
  1. **Preflight** — Chamada estruturada em CLASSIFY, FAST, SMART
  2. **Preset** — deepseek-paid: um provider, sem mock
  3. **Tetos** — Requests e custo por campanha
  4. **Trava** — Lock atômico com PID e host
  5. **Manifesto** — Dono e heartbeat; órfão vira aborted

### c17s09 — A matriz pareada

**Narração:** O experimento mais caro é a matriz pareada: dez campanhas de duzentos turnos, cada uma com perfil, classe, nível inicial e semente fixos. A matriz A mede a linha de base. Seguem diagnóstico, especificações e correções. A matriz B repete exatamente os mesmos pares. O resultado mais forte do projeto: de doze violações de erro na A para zero na B, em quase dois mil turnos reais.

**Visual:** Comparação — **Matriz A versus matriz B**
  - _Matriz A (agosto)_: 2.000 turnos reais · Zero erro de turno · 12 violações error · 193 warnings · Custo estimado US$ 1,46
  - _Matriz B (setembro)_: 1.951 de 2.000 turnos · Zero erro de turno · Zero violações error · Par 10 parou por saldo (402) · Custo estimado US$ 1,18

### c17s10 — Evals com régua protegida

**Narração:** A plataforma de evals mede qualidade com datasets travados por hash e oráculos estruturados. A régua é protegida: quem otimiza o produto não pode mexer em avaliador, esperado, dataset ou linha de base na mesma tarefa. Mudanças na régua exigem aprovação humana no C I. Um juiz feito de IA nunca bloqueia. E o conjunto de teste verdadeiro fica num repositório privado separado.

**Visual:** Tabela — **Suítes de eval determinísticas**

| Suíte | Casos | Mede |
|---|---|---|
| Routing e ações | 25 | Rota, alvo, matriz de confusão |
| Estado e regras | 12 | Transições de projeção |
| Memória e contexto | 27 | Recall, MRR, vazamento, orçamento |
| Narrativa e NPC | 27 | Claims, identidade, segredo |
| Frontend | 16 | Jornadas F01 a F16 com axe |

### c17s11 — A régua travada por hash

**Narração:** A régua tem um cadeado. Um arquivo de bloqueio guarda o hash de cada dataset, de cada arquivo do avaliador e do registro de métricas. Uma verificação falha fechada se qualquer hash divergir, e uma lista de caminhos protegidos diz o que tarefas de otimização não podem tocar. Um incidente recente mostrou a sutileza: em checkout limpo, quebras de linha diferentes mudavam os hashes. A correção fixou o formato de fim de linha e tornou a linha de base antiga incomparável.

**Visual:** Fluxo numerado — **Governança da régua**
  1. **Lock** — SHA-256 de datasets, avaliadores e registry
  2. **Check** — Qualquer divergência falha fechado
  3. **Caminhos protegidos** — Otimização não toca na régua
  4. **CI** — Mudança na régua exige aprovação humana
  5. **Incidente LF/CRLF** — .gitattributes fixa LF; relock canônico
  6. **Consequência** — Baseline v1 histórica e incompatível

### c17s12 — Contratos reais e linha de base

**Narração:** Duas medições completam o quadro. Os contratos reais, fora da suíte padrão, conferem o formato das respostas de modelos de verdade: nove passaram no Gemini na primeira rodada, e hoje um workflow manual os roda com teto duro de vinte pedidos e vinte centavos de dólar. E a linha de base versão um registrou oitenta e seis casos determinísticos mais as dezesseis jornadas, todas verdes, sem inventar metas e sem provedor pago.

**Visual:** Painel de números — **Medições de referência**
  - **9** — contratos LLM reais no Gemini
  - **20 req** — teto do contrato real manual
  - **US$ 0,20** — teto de custo desse workflow
  - **86** — casos determinísticos da baseline v1
  - **16** — jornadas F01 a F16 na baseline

### c17s13 — O índice do projeto

**Narração:** Uma curiosidade honesta. O projeto construiu um índice do próprio código: um grafo com cinco mil e quinhentos nós, gerado da árvore sintática, para ajudar agentes de programação a navegar. Depois fez um experimento A B selado, com a resposta criptografada antes. Resultado: mesma precisão, mas mais chamadas, mais bytes e mais tempo. A decisão foi retirar o índice do fluxo padrão.

**Visual:** Tabela — **Benchmark do Project Index (v6)**

| Métrica | Sem índice | Com índice |
|---|---|---|
| Localização correta | 16 de 16 | 16 de 16 |
| Chamadas medianas | 5 | 8 |
| Bytes lidos medianos | 24.676 | 30.999 |
| Tempo mediano | 38,9 s | 58,3 s |
| Vitórias de custo | n/a | 0 de 8 |

### c17s14 — Os workflows de integração contínua

**Narração:** Tudo isso roda também na integração contínua, em cinco workflows. O de validação roda Ruff, o lint de conteúdo, a suíte e o build do frontend em todo push e pull request. O de auditoria sobe o Supabase local e testa infraestrutura e navegador reais. O de evals classifica o que mudou e roda só o necessário. Dois são manuais e protegidos: provedor real e holdout privado, e o smoke de pós-deploy, que só lê e confere a versão publicada.

**Visual:** Tabela — **Workflows do GitHub Actions**

| Workflow | Quando | O que faz |
|---|---|---|
| validate | push e PR | Ruff, conteúdo, pytest, build web |
| audit-local | push, PR e manual | Supabase local, infra e browser |
| eval-gates | push, PR e manual | Evals seletivos; régua com aprovação |
| eval-protected | manual | Provider real curto e holdout |
| post-deploy-smoke | manual | Read-only; confere o SHA |

### c17s15 — Recapitulando qualidade

**Narração:** Recapitulando. Uma suíte offline de quase mil e novecentos testes como portão. Um harness com catorze perfis e invariantes que crescem a cada defeito. Modo real com tetos e falha fechada. Matrizes pareadas que mostraram doze erros virarem zero. Evals com régua protegida e juiz de IA sem poder de veto. E a coragem de medir e descartar uma ferramenta que não ajudava.

**Visual:** Destaque (key) — **Recapitulação**: Suíte offline como portão; playtest com 14 perfis e invariantes; real com tetos e fail-closed; matriz A para B: 12 erros para 0; evals com régua protegida; Project Index medido e retirado do fluxo.

## C18 — Processo spec-driven e a história do projeto

_Cor do capítulo: `#6B4E8C` · 12 cenas · 771 palavras (~5.1 min)_

### c18s01 — Nada sem especificação

**Narração:** Por trás do código existe um método. Toda funcionalidade nova começa como uma especificação escrita, revisada e aprovada antes de qualquer linha de código. Neste capítulo vemos esse processo, como ele numerou quase duzentas especificações, e a história do projeto, do primeiro motor em dezembro de dois mil e vinte e cinco até hoje.

**Visual:** Cartão de abertura — **Processo e história** / _Specs, revisão independente e uma linha do tempo_

### c18s02 — O ciclo de uma spec

**Narração:** O ciclo tem cinco passos. Copiar um modelo e escrever a spec como rascunho. O usuário revisa e ela vira aprovada. A implementação segue o plano, com testes primeiro, e qualquer desvio atualiza a spec no mesmo commit. Para concluir, todos os critérios de aceite marcados, suíte verde e um teste com modelo real. O roadmap só resume e aponta para a spec.

**Visual:** Fluxo numerado — **Ciclo de vida de uma spec**
  1. **draft** — Copiada do TEMPLATE e escrita
  2. **approved** — Revisada e aprovada pelo usuário
  3. **Implementação** — Testes primeiro, desvios na própria spec
  4. **Aceite** — Critérios marcados, pytest verde, smoke real
  5. **done** — ROADMAP e ESTADO_ATUAL atualizados

### c18s03 — IDs, índice e revisores

**Narração:** Uma spec fez a normalização histórica: as cento e sessenta e duas specs antigas ganharam identificadores estáveis pela ordem de criação no Git, e um índice reproduzível registra status, commits e dependências. Hoje são cento e noventa e oito. O processo também separa quem executa de quem revisa: modelos diferentes por complexidade e um revisor independente que não pode autoaprovar.

**Visual:** Painel de números — **O acervo de specs**
  - **198** — specs com ID estável
  - **174** — done
  - **22** — approved, pacote v5 de produto
  - **1** — draft: certificação cloud
  - **1** — review-pending: integridade LF e CRLF

### c18s04 — Executor e revisor

**Narração:** O processo atual também escolhe quem faz o quê. A regra é usar o menor modelo suficiente. Tarefas de inventário e relatório vão para o nível mais simples; implementação delimitada, para o intermediário; mudanças que cruzam domínios, concorrência ou estado, para um revisor técnico mais forte; e questões conceituais de avaliação, para o mais capaz. Quem executa não aprova o próprio trabalho: sem o revisor certo, gera-se um pedido de revisão formal.

**Visual:** Tabela — **Roteamento de trabalho por modelo**

| Papel | Quando usar |
|---|---|
| Luna | Inventário, transformações, relatórios |
| Terra | Implementação delimitada |
| Sol | Cross-domain, concorrência, revisão |
| Astra | Checkpoints conceituais e evaluators |
| Sem revisor mínimo | MODEL_HANDOFF_REQUIRED, sem autoaprovar |

### c18s05 — Rituais e autoria

**Narração:** Dois rituais mantêm o projeto saudável. Durante o trabalho, um comando roda os testes mostrando só falhas, para economizar contexto. No fim de toda tarefa, outro roda a suíte completa, atualiza o estado atual e o roadmap, o status da spec e faz o commit. Para conteúdo, um guia de autoria define templates, curadoria e o lint que bloqueia a reindexação se houver erro.

**Visual:** Comparação — **Rituais do projeto**
  - _Durante a tarefa_: /qa: só falhas e contagem · Spec aberta como guia · Smoke real para structured output
  - _Ao finalizar_: /wrap-up: suíte completa verde · Atualizar ESTADO_ATUAL e ROADMAP · Status da spec e reindex se mexeu em lore · Commit

### c18s06 — Autoria de conteúdo

**Narração:** Conteúdo também tem processo. O guia de autoria separa três camadas: a fonte em texto, que sempre sobrevive; o Codex gerado, que é refeito a cada migração; e a curadoria, que sobrevive. Para adicionar um personagem à mão, copia-se um modelo, marca-se como curado, coloca o segredo num documento paralelo oculto, registra a entidade, roda o lint e reindexa. O lint cobre cabeçalhos, referências, visibilidade, Cartas sem reskin, bestiário e arte.

**Visual:** Comparação — **Camadas de conteúdo**
  - _Não sobrevive à migração_: Codex gerado em data/codex · entities.json gerado
  - _Sobrevive_: Fonte lore_nova · codex_overrides.yaml · Arquivos curated: true · entities_extra, edges, components · Templates em docs/guias/templates

### c18s07 — O ROADMAP, fases 0 a 5

**Narração:** O roadmap organiza o projeto em fases. A zero trouxe mapa, relógio, viagem e descanso. A um, o frontend React. A dois e suas subfases criaram o mundo vivo: facções, Codex, eventos, regras e montador de contexto. A três deu clareza à campanha com crônica, conhecimento revelável e livro de missões. A quatro fez o núcleo de jogo: progressão, inventário, economia, comitiva e morte digna. A cinco criou o playtest agêntico.

**Visual:** Tabela — **Fases 0 a 5**

| Fase | Entrega |
|---|---|
| 0 | Mapa, relógio, viagem, descanso |
| 1 | Frontend React, Vite e TypeScript |
| 2 a 2.8 | Facções, Codex, eventos, regras |
| 3 | Crônica, conhecimento, quests, estado |
| 4 | Progressão, itens, economia, morte |
| 5 | Harness, invariantes, telemetria |

### c18s08 — O ROADMAP, fases 6 a 11

**Narração:** A fase seis trouxe conteúdo sistêmico: economia viva, itens únicos, migração de monstros, encontros e clima com efeito. A sete, autoria e validação. A oito, arte, curada e dinâmica. A nove, sprites e som, segue no backlog sem especificação. A dez endureceu o projeto localmente e, na sua parte b, construiu a infraestrutura local first; só a certificação em nuvem continua rascunho. A onze criou os contratos com modelos reais.

**Visual:** Tabela — **Fases 6 a 11**

| Fase | Entrega | Estado |
|---|---|---|
| 6 | Conteúdo sistêmico | done |
| 7 | Autoria, lint e curadoria | done |
| 8A e 8B | Arte curada e arte dinâmica | done local |
| 9 | Sprites e som | backlog |
| 10 e 10b | Hardening e infra local-first | done; cloud draft |
| 11 | Contratos LLM reais | done |

### c18s09 — A linha do tempo, parte um

**Narração:** A história começa em dezembro de dois mil e vinte e cinco, com o motor mínimo: grafo, busca vetorial, saves, linha de comando e A P I. Em julho de dois mil e vinte e seis vieram o mundo vivo, com Codex, eventos e regras, a crônica, a progressão, a economia, o playtest agêntico e o roteamento multi provedor.

**Visual:** Tabela — **Linha do tempo: das origens a julho**

| Quando | Marco |
|---|---|
| Dez 2025 a jun 2026 | MVP: grafo, RAG, saves, CLI, API, React |
| 2 e 3 jul | Mundo vivo: Codex, eventos e regras |
| 4 a 6 jul | Progressão, playtest, multi-provider |
| 13 a 18 jul | SSE, DeepSeek primário, criação imersiva |
| 19 a 21 jul | 5 Posturas, checkpoints de morte |
| 23 jul a 2 ago | Épico do combate v4 com Cartas |

### c18s10 — A linha do tempo, parte dois

**Narração:** Agosto foi de endurecimento: laboratório de combate, persistência e streaming, arte curada, quatro ciclos de correção nascidos de playtests longos, toda a infraestrutura local first e a matriz A de dois mil turnos. Setembro trouxe a remediação, a matriz B e o plano de evals. E em outubro, o benchmark do índice, a correção de integridade e um pacote de specs para virar produto.

**Visual:** Tabela — **Linha do tempo: agosto a outubro**

| Quando | Marco |
|---|---|
| 3 a 12 ago | Laboratório, hardening, arte curada |
| 13 a 16 ago | Quatro ciclos de remediação de longrun |
| 17 a 20 ago | Fase 10b local, nível 20, arte dinâmica |
| 20 a 27 ago | Matriz A: 2.000 turnos reais |
| 17 a 28 set | Remediação, IDs de spec, matriz B |
| 29 set a 2 out | Evals, benchmark do índice, pacote v5 |

### c18s11 — Playtests que mudaram o projeto

**Narração:** Alguns playtests longos viraram marcos. Em julho, três campanhas de cem turnos acharam sete defeitos, entre eles combate zumbi e segredo vazando por um beat, e levaram o DeepSeek a primário e a Jina aos embeddings. Em agosto, o jogador normal expôs uma fuga impossível e memória de morte que sobrevivia ao checkpoint. Outro achou checkpoints gravados em combate, prendendo o herói num ciclo de mortes. E as matrizes A e B fecharam o ciclo.

**Visual:** Tabela — **Playtests marcantes**

| Quando | Achado principal | Resultado |
|---|---|---|
| 14 jul | Combate zumbi, segredo no beat | 8 specs; DeepSeek; Jina |
| 12 ago | Fuga impossível, morte no FAISS | Perfil normal; 6 fixes |
| 12 ago v2 | Turno de 2.256 s após suspensão | Watchdog absoluto |
| 13 ago | Checkpoint em combate | Checkpoint seguro |
| 20 ago | A0 e A1 mediram só fallback | Regra fail-closed |
| 27 ago e 28 set | Matriz A, depois B | 12 errors para 0 |

### c18s12 — O padrão que se repete

**Narração:** Um padrão aparece. Cada playtest longo gera especificações. Cada especificação gera testes curtos ou invariantes. A matriz seguinte valida. E várias vezes a estabilidade formal, com zero violações, escondeu defeitos que só a leitura dos transcritos e métricas novas revelaram. Qualidade, aqui, é um ciclo, não um estado.

**Visual:** Destaque (key) — **O ciclo de melhoria**: Playtest longo gera specs; specs geram testes e invariantes; a matriz seguinte valida. Zero violações já esconderam defeitos: ler transcritos e criar métricas novas faz parte do método.

## C19 — Estado atual, arestas e encerramento

_Cor do capítulo: `#7A4E2D` · 9 cenas · 603 palavras (~4.0 min)_

### c19s01 — Uma seção honesta

**Narração:** Nenhum sistema deste tamanho está acabado. Esta seção reúne observações da exploração do código: coisas que parecem desligadas, documentação defasada e limites conhecidos. São achados de leitura, alguns verificados e outros suspeitos, e servem como mapa para o próximo passo, não como veredicto.

**Visual:** Cartão de abertura — **Estado atual e arestas** / _Observações da exploração do código_

### c19s02 — Arestas da mecânica

**Narração:** Na mecânica, alguns achados se destacam. Cartas de proteção e de bônus gravam condições que nenhum cálculo de ataque ou dano parece ler, então podem ser pagas sem alterar números. Armadura e escudo do jogador não são instanciados no jogo real. O ataque básico sem Carta dá três de dano fixo, ignorando a arma. E percepção, armadilhas e itens ainda usam dado de vinte.

**Visual:** Lista — **Achados de mecânica**
  - Buffs de Carta (protecao, buff_*, vantagem) sem consumidor aparente
  - Armadura e escudo do jogador nunca instanciados em produção
  - Ataque básico sem Carta = 3 fixo, ignora a arma equipada
  - Detecção, armadilha e salvaguarda de item ainda em d20
  - Fuga fixa Agilidade e não usa o Teste de Sorte
  - Eventos do Abismo não são alimentados no fluxo real

### c19s03 — Arestas do núcleo e da memória

**Narração:** No núcleo, três campos do estado são declarados mas nunca escritos, e o tipo de mensagem no histórico acaba dependendo de um campo transitório. O modelo falso não tem construtor para a declaração de combate e funciona por acaso. Na memória, a busca devolve só dois trechos por índice, e o simulador do mundo grava fatos sem proveniência. Há também suspeitas, como uma dica de ausência que pode persistir.

**Visual:** Lista — **Achados do núcleo e da memória**
  - Campos active_plan_step, router_confidence, last_routed_intent nunca escritos
  - MockLLM sem builder para PlayerMove: funciona por acaso
  - Retrieval de no máximo 2 trechos por índice
  - world_simulator grava memória sem proveniência
  - Suspeita: npc_fallback_hint pode persistir entre turnos
  - Replan por região acontece com um turno de atraso

### c19s04 — Arestas de operação e documentação

**Narração:** Na operação, não há arquivo de deploy do trabalhador em segundo plano, a auditoria de dependências e o varredor de segredos rodaram à mão e não no C I, e o alerta de backup não é alimentado automaticamente. O custo de modelo é estimado, não medido. A nuvem nunca foi certificada. E a documentação tem defasagens, como o número de perfis e o modelo de embeddings citados.

**Visual:** Lista — **Achados de operação e docs**
  - Sem Dockerfile nem processo worker no Procfile
  - pip-audit, npm audit e scanner de segredos fora do CI
  - Métrica de idade do backup sem produtor automático
  - Custo de LLM estimado por invoke, subconta o real
  - Cloud (Railway e Supabase remoto) ainda em draft
  - Docs defasadas: 13 perfis, embedding antigo, nível 10

### c19s05 — Mais arestas, observadas no código

**Narração:** Outros detalhes merecem nota. Cartas passivas não parecem ter consumidor no motor atual. Reações bem sucedidas dão só postura protegida, e o alvo mais próximo é escolhido por agilidade, não por posição. O bibliotecário depende de uma exceção para o guard funcionar. O tempo limite de doze segundos do DeepSeek pode empurrar gerações longas para o Groq. E no perfil legado, a idempotência só marca a ação depois do save, então uma queda no meio pode repetir o turno.

**Visual:** Lista — **Arestas adicionais**
  - Cartas passivas sem consumidor aparente no motor v4
  - Reação bem-sucedida só concede postura protegida
  - Alvo 'mais próximo' escolhido por Agilidade
  - librarian sem isinstance: guard por AttributeError
  - Timeout de 12 s do DeepSeek afeta gerações SMART
  - Legacy: ação marcada só após o save bem-sucedido

### c19s06 — Limitações conhecidas

**Narração:** Algumas limitações são assumidas. O perfil legado serializa turnos por processo e não tem login, por desenho. A pasta de saves ainda mistura campanhas reais com fixtures antigas, e limpá-la exige seleção humana. Saves anteriores à migração de Virtudes ficam arquivados, somente leitura. A latência real fica em torno de quinze segundos na mediana, e a camada gratuita de provedores não sustenta playtests reais longos.

**Visual:** Lista — **Limitações declaradas**
  - Legacy: um processo, sem login, por desenho
  - Saves históricos misturados a fixtures antigas
  - Saves pré-v4 arquivados em modo leitura
  - Latência real: p50 perto de 15 s, cauda maior
  - Free tier não sustenta playtest real longo
  - Cloud remota nunca medida

### c19s07 — O pacote de produto em detalhe

**Narração:** As vinte e duas especificações aprovadas do pacote cinco formam um plano de produto, em ordem. Primeiro, quatro medem decisões do roteador e do classificador. Depois vêm o contrato de runtime hospedado, a medição real de uso, preços em Estilhas com margem, carteira com reservas e painel de custo por conta. Em seguida, voz, cotação de imagens pagas, Stripe, segurança de conta e homologação no Supabase remoto e na Vercel. Por fim, Android, cobrança do Google Play, reembolsos, FinOps, beta pago fechado e publicação na loja.

**Visual:** Tabela — **SPEC-177 a 198, por tema**

| Tema | Specs |
|---|---|
| Decisão e roteamento (JEV) | 177 a 180 |
| Runtime hospedado e uso real | 181 e 182 |
| Preço, carteira e painel | 183 a 185 |
| Voz e imagens pagas | 186 a 188 |
| Stripe, conta e staging | 189 a 192 |
| Android e Google Play | 193, 194 e 198 |
| Reembolso, FinOps e beta | 195 a 197 |

### c19s08 — Para onde vai

**Narração:** O próximo horizonte está escrito em vinte e duas especificações aprovadas e ainda não iniciadas. Elas cobrem o salto de laboratório para produto: medição real de uso, carteira e preços, pagamentos, voz, aplicativo Android, publicação na loja e operação financeira. Antes disso, falta concluir a revisão de integridade e uma nova linha de base de avaliação. Sprites e som seguem no backlog.

**Visual:** Fluxo numerado — **Próximos passos registrados**
  1. **SPEC-176** — Aprovação humana, push e CI verde
  2. **Nova baseline** — v1 ficou incompatível por hashes CRLF
  3. **SPEC-177 a 198** — Medição de uso, carteira, pagamentos
  4. **Mobile e voz** — Capacitor Android, voz web e mobile
  5. **Cloud** — Railway e Supabase remoto com orçamento
  6. **Fase 9** — Sprites e som, ainda sem spec

### c19s09 — Encerramento

**Narração:** Chegamos ao fim da jornada. Vimos um jogo onde a IA identifica e narra, e o Python resolve; um grafo de onze nós; um mundo com eventos, segredos e memória que sabe quanto confiar em cada fato; um combate tático de Cartas; uma interface robusta; uma infraestrutura que nunca segura transação durante a IA; e um método em que cada defeito vira teste. Obrigado por atravessar Valoria conosco.

**Visual:** Destaque (key) — **Valoria, em uma frase**: Um RPG de texto onde a IA narra e o Python decide: grafo de agentes, mundo por eventos, memória com proveniência, combate determinístico e um processo em que cada defeito vira teste.

## Estimativa de duração

- Capítulos: 19
- Cenas: 239
- Palavras de narração: 15734
- Ritmo de referência: ~150 palavras por minuto
- Duração estimada da narração: ~105 minutos (1.75 h), sem contar pausas e transições entre cenas.
