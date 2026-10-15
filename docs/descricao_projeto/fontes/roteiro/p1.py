from h import *

CHAPTERS = []

# ---------------------------------------------------------------- c01
CHAPTERS.append(ch("Abertura: o que é o rpg-ia-master", "#B8943F", [
    sc("Bem-vindo a Valoria", """
        Imagine um jogo de R P G de mesa em que o mestre nunca se cansa, lembra de tudo
        o que você fez e ainda assim joga limpo com os dados. É isso que o rpg ia master
        tenta ser. Neste vídeo vamos abrir o projeto inteiro, peça por peça, do motor de
        agentes ao processo que mantém tudo de pé.
    """, T("Crônicas de Valoria, por dentro", "Como o rpg-ia-master funciona, de ponta a ponta")),

    sc("O jogo em uma frase", """
        O rpg ia master é um R P G de texto. Você escreve, em português e com suas palavras,
        o que o seu personagem faz. Um mestre de jogo feito de inteligência artificial
        interpreta a intenção, consulta as regras e o mundo, resolve as consequências e
        devolve uma narração. O mundo se chama Valoria, persiste entre as sessões e reage
        ao que você faz.
    """, B("O que o jogador vive",
           "Escreve livremente o que o herói faz, em português",
           "Um mestre de IA interpreta, resolve e narra a consequência",
           "Valoria persiste: lugares, facções, clima e relógio continuam",
           "Personagens lembram de conversas e de favores",
           "Combate tático com Cartas, Ferimentos e morte de verdade")),

    sc("A pilha tecnológica", """
        Por baixo, o projeto é escrito em Python três ponto treze. O cérebro é um grafo de agentes do LangGraph. A memória de longo prazo usa
        busca vetorial, com Faiss em disco ou P G vector no Postgres. A borda é uma
        A P I em Fast A P I, e a interface principal é um aplicativo React com Vite e
        TypeScript. Há ainda um perfil local first com Postgres e Supabase.
    """, TB("A pilha, camada por camada",
            ["Camada", "Tecnologia"],
            [["Linguagem", "Python 3.13 com uv"],
             ["Orquestração", "LangGraph (grafo síncrono)"],
             ["Modelos", "DeepSeek, Groq, Gemini, Anthropic..."],
             ["Memória vetorial", "FAISS ou pgvector"],
             ["Borda HTTP", "FastAPI + SSE"],
             ["Interface", "React + Vite + TypeScript"],
             ["Infra local-first", "Postgres, Supabase Local, workers"]])),

    sc("A visão de cima", """
        Vista de cima, a arquitetura é simples de desenhar. O jogador usa o navegador. O
        navegador conversa com a A P I. A A P I carrega o estado salvo e entrega para o
        grafo de agentes. Dentro do grafo, modelos de linguagem interpretam e narram,
        enquanto código Python determinístico resolve números e regras. No fim, o estado
        novo é salvo e a memória é atualizada. 
    """, G("Arquitetura em uma tela", "LR",
           [("p", "Jogador", "io"), ("w", "Frontend React", "io"), ("a", "API FastAPI", "io"),
            ("g", "Grafo LangGraph", "neutral"), ("l", "Agentes com LLM", "llm"),
            ("m", "Mecânica em Python", "python"), ("s", "Save e checkpoint", "data"),
            ("r", "Memória RAG", "data")],
           [("p", "w"), ("w", "a", "HTTP e SSE"), ("a", "g", "estado"), ("g", "l", "interpretar"),
            ("g", "m", "resolver"), ("l", "s"), ("m", "s"), ("l", "r", "fatos")])),

    sc("O tamanho da coisa", """
        Alguns números dão a escala. O grafo de um turno tem onze nós; o mapa de Valoria tem trinta e cinco
        locais; o bestiário tem cento e vinte e quatro criaturas; o Codex de lore tem quase
        setecentos documentos. A suíte offline passa de mil e oitocentos testes, e o
        projeto já acumulou cento e noventa e oito especificações numeradas. É um laboratório que cresceu com método.
    """, S("Valoria em números",
           ("11", "nós no grafo de um turno"),
           ("35", "locais no mapa, 5 deles interiores"),
           ("124", "criaturas no bestiário"),
           ("699", "documentos no Codex de lore"),
           ("1.898", "testes offline passando"),
           ("198", "specs com ID estável"))),

    sc("Por que não só pedir a uma IA", """
        Você poderia abrir um chat e pedir para uma IA ser seu mestre de jogo. Funciona
        por alguns minutos. Depois ela esquece quem você encontrou, inventa que você tem
        mil moedas, deixa você morrer e reviver na frase seguinte e revela segredos que
        deveriam ficar escondidos. Este projeto existe para resolver exatamente esses
        problemas, colocando a IA dentro de uma estrutura que a vigia.
    """, CMP("Mestre de IA solto versus este motor",
             "Só um chat com IA", ["Esquece fatos antigos", "Inventa números e recompensas",
                                   "Contradiz o que já aconteceu", "Vaza segredos da trama",
                                   "Cada resposta é um improviso"],
             "rpg-ia-master", ["Memória em camadas com proveniência", "Dados e economia em Python",
                               "Validadores barram contradições", "Visibilidade filtra segredos",
                               "Estado salvo, versionado e testado"])),

    sc("O mapa deste vídeo", """
        O roteiro segue camadas. Primeiro os princípios e a anatomia de um turno. Depois
        os agentes e a camada de modelos. Em seguida o mundo e a memória. Aí entramos na mecânica de combate, cartas e progressão, e no mundo
        sistêmico. Depois produto e infraestrutura. Fechamos
        com qualidade, processo, história e uma seção honesta sobre as arestas.
    """, F("Roteiro do vídeo",
           ("Princípios e turno", "IA narra, Python resolve; um turno de ponta a ponta"),
           ("Agentes e modelos", "Os nós do grafo e o roteamento multi-provider"),
           ("Mundo e memória", "Lore, RAG, eventos, segredos, NPCs e crônica"),
           ("Mecânica", "Combate v4, Cartas, Posturas, progressão e mundo"),
           ("Produto", "API, SSE, frontend, jornada e arte"),
           ("Operação", "Persistência, Postgres, leases, observabilidade"),
           ("Qualidade e processo", "Testes, playtest, evals, specs e história"),
           ("Arestas", "Limitações e achados da exploração"))),

    sc("Pequeno glossário", """
        Alguns termos vão aparecer o tempo todo. L L M é o modelo de linguagem, a IA que
        escreve. RAG é a técnica de buscar trechos relevantes num índice antes de pedir a
        resposta. Grafo é a sequência de nós que processa um turno. Spec é o documento que
        descreve uma funcionalidade antes de ela ser escrita. E Mock é um modelo falso,
        determinístico, usado para testar sem internet.
    """, TB("Glossário rápido",
            ["Termo", "Significado aqui"],
            [["LLM", "Modelo que interpreta e narra"],
             ["RAG", "Busca em índice vetorial antes de gerar"],
             ["Grafo", "Nós do LangGraph que processam um turno"],
             ["Tier", "Classe de modelo: CLASSIFY, FAST, SMART"],
             ["Spec", "Documento aprovado antes do código"],
             ["MockLLM", "IA falsa e determinística para testes"]])),

    sc("Recapitulando a abertura", """
        Guarde três ideias desta abertura. Primeiro: é um R P G de texto com um mundo
        persistente chamado Valoria. Segundo: a IA não está solta, ela trabalha dentro de
        um grafo de agentes cercado por código determinístico. Terceiro: o projeto é
        grande e metódico, com milhares de testes e centenas de especificações. Agora vamos
        ao princípio que explica quase todas as decisões.
    """, CO("key", "Recapitulação", "Um RPG de texto com mundo persistente. A IA trabalha dentro de um grafo vigiado por Python. Escala grande, construída com testes e specs.")),
]))

# ---------------------------------------------------------------- c02
CHAPTERS.append(ch("Princípios: a IA narra, o Python resolve", "#9B2C2C", [
    sc("A regra de ouro", """
        Se você lembrar de uma única regra deste projeto, lembre desta: a IA identifica e
        narra, o Python resolve os números. Toda decisão de arquitetura que vamos ver nasce
        dessa separação. Ela parece óbvia, mas aplicá-la de forma consistente em um sistema
        inteiro é o que dá ao jogo justiça, reprodutibilidade e testabilidade.
    """, T("Princípios fundamentais", "A IA identifica e narra. O Python resolve.")),

    sc("Quem faz o quê", """
        Pense numa partida de mesa. O mestre descreve o mundo e interpreta o que os
        jogadores querem. Mas quando alguém ataca, ninguém pede ao mestre para inventar o
        resultado: rola-se o dado e consulta-se a tabela. Aqui é igual. O modelo de
        linguagem classifica a intenção e escreve a prosa. Dados, dano, ferimentos,
        economia, experiência, viagem e descanso são código.
    """, CMP("Divisão de trabalho",
             "O modelo de linguagem faz", ["Classifica a intenção do jogador", "Extrai alvo, item ou destino",
                                           "Escreve a narração e as falas", "Propõe eventos, quests e itens",
                                           "Planeja arcos de campanha"],
             "O Python faz", ["Rola dados e resolve ataques", "Calcula dano, Ferimentos e morte",
                              "Fixa preços, ouro e estoque", "Concede XP e níveis",
                              "Move o relógio, a viagem e o clima"])),

    sc("A IA propõe, o motor aplica", """
         Quando a IA quer mudar o mundo,
        ela não muda, ela propõe. Uma morte de personagem, a revelação de um segredo, uma
        missão nova ou um item ganho chegam como propostas. Um validador em Python confere
        cada uma contra o mapa, o grafo de entidades e o inventário. Só o que passa vira
        estado. O resto vai para um registro de rejeições.
    """, G("Proposta e validação", "LR",
           [("llm", "LLM narra e propõe", "llm"), ("prop", "Propostas pendentes", "data"),
            ("val", "Validador em Python", "python"), ("ok", "Estado do jogo", "data"),
            ("rej", "Registro de rejeições", "neutral")],
           [("llm", "prop"), ("prop", "val"), ("val", "ok", "válida"), ("val", "rej", "inválida")])),

    sc("Guarda de resiliência", """
        O terceiro princípio é sobre falhas. Modelos caem, demoram, devolvem lixo. Quando
        toda a cadeia de provedores falha, o projeto não lança exceção: devolve uma
        mensagem vazia de IA no lugar do objeto esperado. Por isso todo nó que pede saída
        estruturada é obrigado a conferir o tipo do resultado antes de usar qualquer campo.
        Se não for o tipo certo, cai num caminho determinístico.
    """, C("O guard obrigatório em todo nó", "agents/storyteller.py", "python", """
story_engine = llm.with_structured_output(StoryUpdate)
update = story_engine.invoke([sys] + messages[-3:]) # Contexto reduzido

# Guard crítico: FallbackLLM devolve AIMessage, não o schema solicitado.
if not isinstance(update, StoryUpdate):
    update = StoryUpdate(narrative=_deterministic_story_fallback(
        (travel_note, rest_note, world_note, faction_note, weather_note), _ll,
    ))
""")),

    sc("Guardas de prosa e evidência", """
        O quarto princípio protege o que o jogador lê. Mesmo uma narração bonita pode
        afirmar coisas falsas: que você morreu, que ganhou cinquenta moedas, que está em
        outro lugar, que um personagem é de outra espécie. Antes de chegar à tela, a prosa
        passa por guardas que comparam cada frase com o estado confirmado e removem
        contradições. O recibo de recompensa é recalculado a partir da diferença real.
    """, B("O que as guardas removem ou corrigem",
           "Morte falsa do jogador e localização errada",
           "Posse de item que não está no inventário mecânico",
           "Ouro ou XP narrados que não batem com o delta real",
           "Segredos ainda não revelados, mesmo entre aspas",
           "Instruções internas vazando para a narração")),

    sc("Um caminho de jogo, testado", """
        O quinto princípio é estrutural: existe um único caminho de jogo. O grafo é
        compilado uma vez e usado pela A P I, pela linha de comando e pelo harness de
        playtest. Isso significa que o que é testado offline é exatamente o que roda para
        o jogador. Não existe uma versão de teste separada da versão real.
    """, G("Um grafo, três consumidores", "TB",
           [("g", "Grafo compilado (app)", "neutral"), ("api", "API web", "io"),
            ("cli", "CLI no terminal", "io"), ("pt", "Harness de playtest", "python"),
            ("t", "Suíte de testes", "python")],
           [("api", "g"), ("cli", "g"), ("pt", "g"), ("t", "g")])),

    sc("Por que isso importa", """
        Esses princípios trazem quatro benefícios concretos. Justiça, porque o jogador
        sabe que o dado não foi inventado. Reprodutibilidade, porque com a mesma semente o
        combate dá o mesmo resultado. Testabilidade, porque código determinístico pode ser
        verificado sem chamar um modelo pago. E resiliência, porque mesmo sem nenhuma IA
        disponível o jogo continua funcionando de forma degradada.
    """, S("Benefícios da separação",
           ("Justiça", "números não são inventados pela IA"),
           ("Seed", "mesma semente, mesmo combate"),
           ("Offline", "suíte inteira roda sem rede"),
           ("Degradado", "sem IA, o jogo continua jogável"))),

    sc("Recapitulando os princípios", """
        Recapitulando. A IA identifica e narra, o Python resolve. A IA propõe, o motor
        valida e aplica. Toda saída estruturada tem guarda de resiliência. Tudo que o
        jogador lê passa por guardas de prosa e evidência. E existe um único caminho de
        jogo para produção e testes. Com isso em mente, vamos acompanhar um turno inteiro.
    """, B("Os cinco princípios",
           "A IA identifica e narra; o Python resolve números",
           "A IA propõe; validadores em Python aplicam ou rejeitam",
           "Todo structured output tem guard de resiliência",
           "Guardas de prosa e evidência antes da tela",
           "Um único grafo para produção, CLI, playtest e testes")),
]))

# ---------------------------------------------------------------- c03
CHAPTERS.append(ch("Anatomia de um turno", "#3E5C76", [
    sc("Um turno de verdade", """
        Nada explica melhor um sistema do que segui-lo em ação. Neste capítulo vamos
        acompanhar um turno real: um herói de nível dois, em Nova Arcádia, digita vou para a
        Floresta Cinzenta. Vamos ver cada etapa, da tecla enviada até a narração aparecer
        letra por letra, passando pela A P I, pelo grafo e pela gravação do save.
    """, T("Anatomia de um turno", "Do clique em Agir até a narração na tela")),

    sc("A visão de alto nível", """
        Em alto nível, um turno tem sete fases. O navegador envia a ação com um
        identificador único. A A P I trava o jogo e carrega o estado. Confere se a ação já
        foi processada e se o jogo aceita turnos. Roda o grafo. Calcula arte, checkpoint e
        resposta pública. E por fim grava tudo de forma atômica e registra uma linha de log.
    """, F("As fases de um turno",
           ("Envio", "Cliente manda o texto e um action_id UUID"),
           ("Trava e carga", "Lock por jogo; carrega o save e migra a versão"),
           ("Idempotência", "Se o action_id já foi visto, devolve sem rodar"),
           ("Gates", "Memorial, arquivado ou queda pendente: 409"),
           ("Grafo", "action_guard até turn_finalizer"),
           ("Pós-grafo", "Cue visual, arte, checkpoint e resposta"),
           ("Commit e log", "Save atômico e linha JSON rpg.turn"))),

    sc("O identificador da ação", """
        Começa no navegador. Antes de enviar, o cliente gera um identificador único para a
        ação e guarda o pedido no armazenamento local. Se a aba fechar no meio do turno, ao
        voltar o cliente pergunta ao servidor se aquela operação já terminou. Se o
        servidor já processou, devolve o resultado sem rodar de novo. Isso é idempotência:
        repetir o pedido não repete o efeito.
    """, CO("key", "Idempotência por action_id", "Cada ação carrega um UUID. O servidor guarda os últimos 64 IDs processados no save; repetir o mesmo ID devolve o estado atual sem rodar o grafo. Retry seguro, sem turno duplicado.")),

    sc("Gates antes do grafo", """
        Com o estado carregado, a A P I faz três checagens. Se o herói morreu e o jogador
        aceitou o fim, o jogo é um memorial e qualquer ação recebe erro quatrocentos e
        nove. Se o save é muito antigo e foi arquivado, também. E se existe uma morte
        pendente, nenhuma ação passa até o jogador escolher na tela de morte.
    """, TB("Gates do turno",
            ["Situação", "Efeito"],
            [["game_over (memorial)", "409: a saga terminou"],
             ["archived (save pré-v4)", "409: somente leitura"],
             ["death_pending", "409: resolva a tela de morte"],
             ["action_id repetido", "devolve estado sem rodar"],
             ["Combate ativo + chips da UI", "vira combat_declaration"]])),

    sc("Entrando no grafo", """
        Agora o grafo. O primeiro nó é o action guard, que olha a fase vital do herói.  O guarda fotografa o antes: ouro, X P, inventário e missões. Depois o turn prepare avança o contador de turnos
        de dezessete para dezoito. O gerente de campanha confere se precisa replanejar o
        arco e, como faltam turnos para o próximo replanejamento, devolve o plano sem
        chamar modelo nenhum.
    """, EX("Primeiros nós do turno 18",
            ("action_guard", "herói ativo; grava baseline de ouro, XP, itens"),
            ("turn_prepare", "turn_count 17 para 18; ações da sessão +1"),
            ("campaign_manager", "sem replan: plano atual devolvido, zero LLM"),
            ("dm_router", "'vou para' casa a regex: STORY sem LLM"),
            ("dispatch", "lê next = storyteller"))),

    sc("O narrador faz a mecânica primeiro", """
        No narrador, muita coisa acontece antes de qualquer IA. O destino é resolvido
        contra o mapa. O custo de viagem é calculado. O relógio avança, as facções progridem
        e, por ser a primeira visita, um achado ambiental pode ser sorteado. A cena de
        personagens é zerada, porque ninguém se teletransporta junto. Então rola-se um
        possível encontro. Neste exemplo, não houve combate, e o mundo ganha um rumor.
    """, F("Storyteller: mecânica antes da prosa",
           ("Resolve destino", "Nome livre vira id real do mapa, ou recusa canônica"),
           ("Custo e viagem", "travel_cost, apply_travel, relógio e clima"),
           ("Facções", "Progresso determinístico por período"),
           ("Primeira visita", "Achado ambiental ou baú curado"),
           ("Cena zerada", "NPCs saem de cena: ninguém teleporta"),
           ("Encontro?", "Sorteio ponderado; aqui, nenhum combate"),
           ("Ecos do mundo", "Simulador propõe um rumor"))),

    sc("A chamada ao narrador", """
        Só então o narrador monta o contexto e chama o modelo rápido. O prompt leva o
        estado do mundo, a memória relevante, a lore pública, a vitalidade e o ouro exatos,
        as missões ativas e regras de estilo. O modelo devolve a narração e um pacote de
        propostas. Aqui ele introduziu uma guarda florestal chamada Ilse. O motor gera a
        ficha dela e a coloca em cena.
    """, EX("Resposta estruturada do storyteller",
            ("narrative", "A névoa da Floresta Cinzenta engole a estrada..."),
            ("introduced_npcs", "Guarda-florestal Ilse"),
            ("beat_completed", "false"),
            ("proposed_events", "nenhum"),
            ("items_gained", "nenhum"),
            ("Efeito em Python", "gera ficha de Ilse e marca in_scene"))),

    sc("Arquivista e finalizador", """
        Como houve viagem, o turno foi marcado para arquivamento. O arquivista processa
        eventos pendentes, chama o modelo inteligente para reescrever o resumo da história
        e extrair fatos, e grava esses fatos na memória vetorial da sessão. Por último, o
        finalizador revalida a prosa, compara o estado final com a fotografia do início e
        gera o recibo do turno.
    """, G("Fim do turno", "LR",
           [("st", "storyteller", "llm"), ("ar", "archivist", "llm"), ("ev", "Eventos pendentes", "python"),
            ("mem", "FAISS da sessão", "data"), ("fi", "turn_finalizer", "python"), ("rc", "Recibo do turno", "data")],
           [("st", "ar"), ("ar", "ev", "valida"), ("ar", "mem", "fatos"), ("ar", "fi"), ("fi", "rc", "delta real")])),

    sc("De volta à API", """
        O grafo terminou. A A P I decide se algum personagem novo merece uma imagem, marca
        o identificador da ação como processado, avalia se é hora de um checkpoint e monta
        a resposta pública. Depois grava o histórico de apresentação e o save, numa escrita
        atômica: arquivo temporário, sincronização com o disco e troca. Por fim, uma linha
        de log em JSON registra rota, latência, eventos e custo.
    """, F("Pós-grafo na API",
           ("Cue visual", "Primeira aparição de NPC ganha retrato curado"),
           ("Ledger da ação", "action_id entra nos últimos 64 processados"),
           ("Checkpoint?", "A cada 10 turnos ou zona segura"),
           ("Resposta pública", "format_response monta o GameResponse"),
           ("Save atômico", "temp, fsync e os.replace"),
           ("Log rpg.turn", "rota, latência, eventos e custo"))),

    sc("O streaming na tela", """
        Na variante de streaming, o navegador recebe eventos enquanto o grafo trabalha:
        aceito, cada fase concluída e a rota escolhida. Isso vira textos temáticos, como o
        mestre consulta os arcanos. Quando a narração fica pronta, ela chega em pedaços de
        oitenta caracteres, e o cliente faz o efeito de máquina de escrever. Vale notar:
        não é streaming de tokens do modelo, é a resposta pronta, fatiada.
    """, F("Eventos S S E do turno",
           ("accepted", "O servidor aceitou a ação"),
           ("phase", "Cada nó concluído: campaign_manager, storyteller..."),
           ("route", "A rota decidida pelo dm_router"),
           ("visual", "Arte da cena ou do NPC novo"),
           ("narrative", "Pedaços de 80 caracteres até done"),
           ("state", "O GameResponse completo"))),

    sc("Variante: a emboscada", """
        E se o sorteio de encontro tivesse dado combate? Então o narrador nem chama o
        modelo. Ele devolve na hora uma mensagem de sistema de início de combate, já com o
        mundo movido e a informação de quem percebeu quem. A aresta do grafo leva direto ao
        nó de combate, que monta a cena e resolve a primeira rodada no mesmo turno. O
        jogador recebe a chegada e o primeiro golpe numa única resposta. E um herói de nível
        baixo, de vitalidade cheia, ganha a iniciativa da primeira rodada mesmo surpreendido.
    """, F("Emboscada na estrada",
           ("Viagem aplicada", "Relógio, névoa e cena já atualizados"),
           ("Encontro: combate", "Percepção decide quem foi surpreendido"),
           ("Sem narrador", "Nenhuma chamada FAST de exploração"),
           ("COMBAT START", "Mensagem de sistema e next = combat_agent"),
           ("Primeira rodada", "Cena montada e resolvida no mesmo turno"),
           ("Early-game", "Nível até 2 e vida cheia: herói age primeiro"))),

    sc("Recapitulando o turno", """
        Recapitulando. Um turno é um pedido idempotente que atravessa gates, roda um grafo
        de onze nós e termina num save atômico. A maior parte do trabalho é Python
        determinístico. Neste exemplo, os modelos só entraram para escrever: o rumor do
        simulador do mundo, a ficha conceitual de Ilse, a narração e o arquivamento. O
        roteador, a campanha e toda a viagem não custaram nada. A interface mostra fases ao
        vivo e digita a narração. Agora vamos olhar cada nó do grafo com calma.
    """, CO("key", "Recapitulação", "Pedido idempotente, gates, grafo de 11 nós, save atômico. Roteador, campanha e viagem sem IA; modelos só para rumor, NPC novo, narração e arquivo. O SSE mostra fases ao vivo e fatia a narração pronta.")),
]))

# ---------------------------------------------------------------- c04
CHAPTERS.append(ch("O grafo e os agentes, um por um", "#4A6B3A", [
    sc("A linha de montagem", """
        O grafo é como uma linha de montagem de uma oficina medieval. Cada estação tem um
        artesão especializado, e a peça, que aqui é o estado do jogo, passa de mão em mão.
        Neste capítulo visitamos cada estação: o guarda da porta, o preparador, o diretor de
        campanha, o roteador, os quatro agentes de ação, o arquivista e o finalizador.
    """, T("O grafo e os agentes", "Onze estações, cada uma com um ofício")),

    sc("O desenho do grafo", """
        Este é o desenho. Do início, um gate barra jogos encerrados. O guarda de ação pode
        encerrar o turno com uma mensagem fixa. Em seguida vêm preparo, campanha, roteador e
        despacho. O despacho escolhe um de quatro agentes. O narrador pode encaminhar para o
        combate, o ator de personagens pode devolver ao narrador, e o combate vitorioso
        passa pelo saque. Tudo converge no arquivista e no finalizador.
    """, G("Topologia do grafo", "TB",
           [("start", "START + gate", "neutral"), ("ag", "action_guard", "python"),
            ("tp", "turn_prepare", "python"), ("cm", "campaign_manager", "llm"),
            ("rt", "dm_router", "llm"), ("dp", "dispatch", "python"),
            ("npc", "npc_actor", "llm"), ("st", "storyteller", "llm"),
            ("cb", "combat_agent", "llm"), ("lt", "loot_agent", "llm"),
            ("ar", "archivist", "llm"), ("fi", "turn_finalizer", "python")],
           [("start", "ag"), ("ag", "tp"), ("tp", "cm"), ("cm", "rt"), ("rt", "dp"),
            ("dp", "npc"), ("dp", "st"), ("dp", "cb"), ("dp", "lt"),
            ("npc", "st", "sem alvo"), ("npc", "ar"), ("st", "cb", "emboscada"), ("st", "ar"),
            ("cb", "lt", "vitória"), ("cb", "ar"), ("lt", "ar"), ("ar", "fi")])),

    sc("Sequencial ou concorrente", """
        Existe um segundo desenho, experimental. Como o preparo do turno avança o relógio
        uma única vez antes de tudo, a campanha e o roteador podem rodar em paralelo,
        porque escrevem em campos diferentes do estado. Um benchmark controlado mostrou
        sobreposição, mas no DeepSeek real o turno piorou: as duas chamadas brigavam pela
        mesma rota do provedor. A decisão foi não adotar. O padrão de produção continua
        sequencial, e o modo concorrente fica atrás de uma variável de ambiente.
    """, CMP("Dois modos de execução do turno",
             "Sequencial (padrão)", ["preparo, campanha, roteador, despacho", "Sem disputa pelo provedor",
                                     "Usado em produção e na suíte"],
             "Concorrente (experimental)", ["Campanha e roteador em paralelo", "Join no nó de despacho",
                                            "Canais de estado disjuntos", "No-go no DeepSeek real"])),

    sc("O estado e o reducer", """
        Um detalhe técnico importante. No LangGraph, cada nó devolve um pedaço do estado.
        Só um campo acumula: a lista de mensagens, que vai somando. Todo o resto é último
        valor vence. Por isso o roteador devolve explicitamente vazio para alvos de combate,
        de conversa e de saque: para que transitórios do turno anterior não sobrevivam. E
        quando um nó precisa reescrever mensagens, usa uma sobrescrita explícita.
    """, C("O único campo acumulativo", "state.py", "python", """
class GameState(TypedDict):
    game_id: str
    narrative_summary: str
    player: PlayerStats
    world: WorldState
    # único campo com reducer: mensagens são SOMADAS
    messages: Annotated[List[BaseMessage], operator.add]
    next: Optional[str]
    # ... todo o resto: último valor vence
""")),

    sc("O guarda da porta", """
        O action guard não usa IA. Ele classifica o herói numa fase vital: ativo,
        inconsciente, incapacitado, última ação, estado terminal, morte pendente ou morto.
        Um herói inconsciente só pode descansar ou pedir socorro, e a frase precisa casar
        inteira com o padrão de recuperação. Qualquer outra coisa recebe uma mensagem fixa
        e o turno termina sem gastar um centavo. E se encontra um herói em estado terminal
        sem nenhum combate que explique isso, um save corrompido ou antigo, ele repara o
        estado e pede replanejamento.
    """, TB("action_guard: fases e permissões",
            ["Fase vital", "O que é permitido"],
            [["active", "Qualquer ação"],
             ["unconscious / incapacitated", "Só descansar ou pedir socorro"],
             ["last_stand / terminal", "Nada fora do combate"],
             ["death_pending", "Nada: resolva a tela de morte"],
             ["dead", "Nada"],
             ["Combate ativo", "Sempre resolve o combate"]])),

    sc("O diretor de campanha", """
        O campaign manager é o diretor. Ele mantém um arco narrativo com três a cinco
        etapas, chamadas beats, e um clímax. Usa o modelo inteligente, mas só quando precisa:
        sem plano, mudança de região, quinze turnos desde o último plano ou todos os beats
        cumpridos. Em catorze de cada quinze turnos ele não custa nada. E se há combate
        ativo, adia o replanejamento.
    """, B("Quando o campaign_manager replaneja",
           "Não existe plano ou needs_replan foi marcado",
           "O herói mudou para outra região do mapa",
           "Passaram 15 turnos desde o último plano",
           "Todos os beats do arco foram cumpridos",
           "Combate ativo? adia: não gasta SMART numa cena instável")),

    sc("As defesas do plano", """
        O plano passa por camadas de proteção. Se veio em inglês, o diretor tenta de novo
        com instrução reforçada. Cada beat, o clímax e o título passam por um filtro que
        remove verdades ocultas da trama. A localização é sempre a real. E se tudo falhar, há um plano padrão de três beats em português.
        E beats em excesso são cortados em Python.
    """, F("Proteções do plano de campanha",
           ("Tipo certo", "isinstance CampaignPlanModel, senão erro"),
           ("Idioma", "Beat em inglês? regenera uma vez"),
           ("Segredo", "sanitize_beat remove verdades ocultas"),
           ("Geografia", "location é sempre o local real do mundo"),
           ("Excesso", "Mantém os 5 primeiros beats não vazios"),
           ("Falha geral", "Plano fallback de 3 beats em pt-BR"))),

    sc("O roteador em detalhe", """
        O dm router usa o classificador com temperatura zero, mas só depois de cinco atalhos.
        Sem mensagens, vai para a história. Com combate ativo, sempre combate, e uma tentativa
        de viagem vira tentativa de fuga. Recuperação vai para a história. Descanso e viagem
        explícitos também. Só então o modelo classifica entre história, combate, conversa ou
        saque, com o alvo extraído.
    """, F("Ordem de decisão do dm_router",
           ("Sem mensagens", "STORY; última msg é da IA: END"),
           ("Combate ativo", "combat_agent sempre; viagem vira fuga"),
           ("Recuperação", "Herói inconsciente descansando: STORY"),
           ("Regex explícita", "descansar, dormir, viajar: STORY"),
           ("Classificador", "CLASSIFY: STORY, COMBAT, NPC ou LOOT"),
           ("Pós-processo", "NONE vira STORY; alvo e origem gravados"))),

    sc("Dois bugs que viraram regra", """
        O gate de combate fechou dois bugs históricos. O primeiro era o teleporte: em
        combate, dizer vou para a cidade simplesmente movia o herói. Agora vira tentativa
        de fuga, resolvida pela perseguição. O segundo era o combate zumbi, que ficava ativo
        por dezenas de turnos. Agora, após três turnos sem ação de combate, ele expira. E o
        modelo escolher a rota nenhuma, comum com entradas absurdas, vira história.
    """, CMP("Antes e depois do gate de combate",
             "Antes", ["Viajar em combate teleportava o herói", "Combate ativo por 59 turnos seguidos",
                       "Rota NONE quebrava o grafo", "Conversa no meio da luta ignorava inimigos"],
             "Depois", ["Viagem em combate vira tentativa de fuga", "Combate órfão expira em 3 turnos",
                        "NONE é normalizado para STORY", "Conversa e saque bloqueados até o fim"])),

    sc("O narrador", """
        O storyteller é o nó mais denso. Já vimos que ele resolve viagem e descanso antes da
        IA. Depois, monta blocos explícitos no prompt: o estado do herói com vitalidade e
        ouro exatos, luz, clima, só as facções que o jogador conhece, entidades
        canônicas, missões ativas e capacidades da ficha. E pede para fechar com duas ou três opções de ação.
    """, B("Blocos do prompt do storyteller",
           "ESTADO_DO_HEROI: vitalidade e ouro exatos; use exatamente esse ouro",
           "AMBIENTE_DE_LUZ e CLIMA_GLOBAL vindos do motor",
           "FACÇÕES_CONHECIDAS: só as que o jogador já descobriu",
           "ENTIDADES_CANONICAS e QUESTS_ATIVAS",
           "CAPACIDADES_DO_HEROI: utilitárias liberadas pela ficha",
           "Estilo: varie a abertura e feche com 2 ou 3 opções")),

    sc("A quarentena atômica", """
        Depois da resposta, o motor valida antes de mostrar.  E aqui há uma política conservadora: se uma única proposta for
        inválida, todo o pacote livre da resposta vai para quarentena. Personagens novos,
        itens, missões e impactos de facção da mesma resposta são descartados, e a narração
        é trocada por uma versão determinística. A prosa não pode afirmar o que o motor vai
        recusar.
    """, CO("warn", "Quarentena atômica", "Uma proposta inválida põe em quarentena todo o payload livre da resposta: eventos, NPCs, itens, quests e beat. Garante coerência, ao custo de perder propostas legítimas do mesmo turno.")),

    sc("O ator de personagens", """
        O npc actor dá voz aos personagens. Antes da IA, ele resolve casos simples. Sem alvo
        e sem ninguém em cena, devolve o turno ao narrador, que descreve a ausência e sugere
        um caminho. Se o personagem existe mas está em outro lugar, a resposta é fixa: ele
        não está aqui, foi visto pela última vez em tal lugar. Recrutar e dispensar são decididos em Python.
    """, F("Árvore de decisão do npc_actor",
           ("Sem alvo e cena vazia", "Devolve ao storyteller com um gancho concreto"),
           ("Conhecido, fora de cena", "Resposta fixa, zero LLM"),
           ("Inexistente", "generate_new_npc cria na hora"),
           ("Comando de party", "Recrutar ou dispensar: decisão em Python"),
           ("Conversa", "Prompt com persona, memória e filtro de saber"),
           ("Pós", "Relação 0 a 10, memória observável, traits"))),

    sc("Não seja uma Wikipédia", """
        O prompt do personagem tem uma regra de ouro escrita literalmente: não seja uma
        Wikipédia. Um camponês não conhece os planos de cultos distantes. A memória que fica
        gravada não é o resumo livre da IA, mas a experiência observável: o jogador disse
        tal coisa, o personagem respondeu tal outra. E falas de personagens nunca viram
        fatos globais por inferência: são relatos.
    """, EX("Memória gravada após uma conversa",
            ("Turno", "12"),
            ("Fala do jogador", "Quem é você de verdade?"),
            ("Resposta de Magda", "Há coisas que o Anel de Lama não esquece"),
            ("Proveniência", "npc_claim, ou seja, um relato"),
            ("Confiança", "reported, derivada, não escolhida"),
            ("Política do turno", "canonical_only: nada vira fato global"))),

    sc("Combate e saque", """
        O combat agent é um nó fino sobre os serviços de conflito. Ele usa IA em quatro
        pontos, todos de identificação ou narração: descobrir quais inimigos aparecem,
        criar o conceito de uma criatura nova, entender a fala do jogador como declaração
        e narrar a rodada. Há ainda a cicatriz, escrita depois de uma queda sobrevivida. Na vitória, segue para o loot agent, que trata tesouro, compra,
        venda e forja. Preço, estoque e raridade são sempre Python.
    """, TB("Onde o combate e o saque usam IA",
            ["Ponto", "Tier", "Papel"],
            [["Spawn de inimigos", "CLASSIFY", "Quais e quantos, da narrativa"],
             ["Criatura nova", "FAST ou SMART", "Só o conceito; ficha é Python"],
             ["Declaração do jogador", "CLASSIFY", "Fala livre vira TurnDeclaration"],
             ["Narração da rodada", "FAST", "Só a partir do log mecânico"],
             ["Cicatriz", "SMART", "Após sobreviver à queda"],
             ["Intenção de troca", "CLASSIFY", "Comprar, vender, forjar ou olhar"]])),

    sc("Arquivista e finalizador", """
        O archivist tem cadência: só chama o modelo inteligente quando algo relevante
        aconteceu ou a cada dez turnos. Mas um trabalho roda sempre: processar os eventos
        propostos, que é o único caminho para mudar o mundo. O turn finalizer, sem IA,
        revalida a prosa, recusa salvar um estado sem dono de transição e calcula o recibo:
        ouro, X P, itens e missões como diferença real de estado.
    """, CMP("Os dois últimos nós",
             "archivist", ["Processa eventos pendentes todo turno", "SMART só com archive_due ou a cada 10",
                           "Resumo curto de até 1.200 caracteres", "Fatos com proveniência na memória",
                           "Crônica: marcos e prosa do menestrel"],
             "turn_finalizer", ["Sem nenhuma chamada de LLM", "Revalida a prosa contra a evidência",
                                "Barra estado sem dono de transição", "Recibo: ouro, XP, itens, quests",
                                "Remove marcadores falsos de resultado"])),

    sc("Os ajudantes dos agentes", """
        Três ajudantes trabalham por trás dos nós. O bibliotecário evita duplicatas: antes
        de criar um personagem ou criatura, procura um igual em quatro camadas, e só a
        última usa o classificador. O bestiário gera criaturas novas, mas o modelo descreve
        apenas o conceito; a ficha numérica é calculada pelo motor a partir da categoria e
        do nível do encontro. E o simulador do mundo propõe rumores e mudanças de perigo,
        que o Python limita e aplica.
    """, TB("Agentes auxiliares",
            ["Ajudante", "IA usada", "O que o Python garante"],
            [["librarian", "CLASSIFY só no fim", "Slug, tokens e difflib antes"],
             ["bestiary", "FAST ou SMART", "Ficha por categoria e nível"],
             ["world_simulator", "FAST", "Perigo muda no máximo 1"],
             ["generate_new_npc", "FAST, SMART p/ nobres", "Cache e ficha v4 de fallback"]])),

    sc("Objetivo público e direção social", """
        Dois serviços pequenos resolvem um problema sutil. O plano de campanha é privado do
        diretor, então a interface e os personagens nunca leem beats nem clímax. O objetivo
        público mostrado ao jogador é a missão secundária ativa ou, sem ela, um convite a
        investigar o local atual dentro do arco. E quando não há ninguém com quem falar, a
        direção social escolhe, entre as saídas conectadas, a de menor perigo e a oferece
        como gancho concreto, sem inventar interlocutor.
    """, CMP("Público versus privado",
             "Privado do diretor", ["Beats do arco", "Clímax planejado", "Arestas ocultas do grafo"],
             "Público para o jogador", ["Missão secundária ativa", "Investigar o local no arco atual",
                                        "Saída conectada de menor perigo"])),

    sc("Quanto custa um turno", """
        Juntando tudo, dá para estimar o custo de um turno. Uma exploração em cidade sem
        evento custa tipicamente uma classificação e uma narração. A campanha só replaneja
        a cada quinze turnos. O arquivista só entra quando algo relevante aconteceu ou a
        cada dez turnos. Viagens e descansos acrescentam o simulador do mundo, e
        personagens novos acrescentam o designer. Cada ponto tem um caminho determinístico
        se o modelo falhar.
    """, TB("Chamadas de IA por turno típico",
            ["Ponto", "Tier", "Frequência", "Se falhar"],
            [["dm_router", "CLASSIFY", "0 ou 1", "STORY"],
             ["storyteller", "FAST", "1", "Narração por notas"],
             ["world_simulator", "FAST", "Viagem ou descanso", "Sem rumor"],
             ["campaign_manager", "SMART", "1 a cada 15", "Plano de 3 beats"],
             ["archivist", "SMART", "Cadência", "Resumo em texto plano"],
             ["combate: narração", "FAST", "1 por rodada", "Log mecânico"],
             ["loot: troca", "CLASSIFY", "0 ou 1", "Palavras-chave"]])),

    sc("Recapitulando os agentes", """
        Recapitulando a linha de montagem. Guarda e preparo, sem IA. Campanha, que quase
        nunca custa. Roteador com atalhos determinísticos. Narrador, ator de personagens,
        combate e saque, onde a IA identifica e narra mas o Python decide. E arquivista e
        finalizador, que transformam o turno em memória e recibo. Agora vamos ver como o
        projeto escolhe qual modelo atende cada chamada.
    """, B("Os onze nós em uma linha cada",
           "action_guard e turn_prepare: fase vital e relógio, sem IA",
           "campaign_manager: arco de 3 a 5 beats, SMART raro",
           "dm_router: atalhos em Python, CLASSIFY no ambíguo",
           "storyteller, npc_actor, combat_agent, loot_agent: ação",
           "archivist: eventos, resumo, fatos e crônica",
           "turn_finalizer: prosa validada e recibo por delta")),
]))

# ---------------------------------------------------------------- c05
CHAPTERS.append(ch("Modelos de linguagem: tiers, rotas e resiliência", "#5B3A7A", [
    sc("Nunca depender de um só provedor", """
        Um jogo que depende de um único provedor de IA para cada turno é frágil. Cotas
        acabam, saldos zeram, modelos são removidos, servidores demoram. Este capítulo
        mostra como o projeto trata a IA como um recurso intercambiável, com classes de
        modelo, listas de candidatos, recuperação de respostas ruins e um disjuntor para
        provedores mortos.
    """, T("A camada de modelos", "Tiers, rotas multi-provider e resiliência")),

    sc("Três classes de modelo", """
        Tudo começa numa única função, get llm, que recebe uma classe de modelo. CLASSIFY
        é para classificação e parse com temperatura zero: roteador, intenção de combate,
        intenção de troca. FAST é para narração e diálogo. SMART é para coerência de longo
        prazo: campanha, arquivista, ficha e prólogo. Trocar modelo é editar uma tabela.
    """, TB("Os três tiers",
            ["Tier", "Uso", "Exemplos"],
            [["CLASSIFY", "Classificação e parse, temp 0", "router, combate, troca"],
             ["FAST", "Narração e roleplay", "storyteller, npc_actor"],
             ["SMART", "Coerência de longo prazo", "campanha, arquivista, prólogo"]])),

    sc("As rotas", """
        Cada classe é uma lista ordenada de candidatos. O DeepSeek é o primário nas três,
        escolhido depois de um playtest longo por escrever melhor e custar cerca de um
        décimo de centavo de dólar por turno. Logo atrás vem o Groq, que tem camada
        gratuita e mantém o jogo vivo se o pago falhar. Depois vêm MiniMax, Qwen, Anthropic
        e Gemini, conforme a classe.
    """, C("A tabela de rotas", "llm_setup.py", "python", """
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
""")),

    sc("A cascata de get llm", """
        A função segue uma cascata em ordem. Se a variável que força o mock estiver ligada,
        devolve o modelo falso: é o que a suíte usa. Se houver um provedor forçado, todas as
        classes vão para ele. Se não houver chave de nenhum provedor, entra o mock, para
        rodar sem configuração. Caso contrário, devolve um roteador que percorre a lista de
        candidatos daquela classe.
    """, F("Ordem de resolução de get_llm",
           ("RPG_FORCE_MOCK", "MockLLM determinístico: a suíte inteira"),
           ("LLM_PROVIDER", "Força todos os tiers num provider único"),
           ("Sem nenhuma chave", "MockLLM, ou erro explícito com RPG_NO_MOCK"),
           ("Padrão", "RoutedLLM com a lista ROUTES do tier"))),

    sc("O roteador preguiçoso", """
        O objeto central é o Routed L L M. Ele é preguiçoso de propósito: quando um nó pede
        saída estruturada, ele só anota essa transformação. Só na hora de invocar ele
        constrói o cliente de cada candidato e reaplica as transformações. Assim o mesmo
        pedido funciona com provedores diferentes, cada um do seu jeito. 
    """, CO("info", "Transformações acumuladas", "with_structured_output, bind_tools e with_retry são guardadas numa lista e reaplicadas por candidato no invoke. Providers OpenAI-compat usam function_calling; schemas recebem include_raw para recuperar JSON.")),

    sc("O que acontece em cada tentativa", """
        Em cada candidato, a ordem é esta. Se o disjuntor daquele provedor está aberto, pula.
        Constrói o cliente, com cache. Aplica as transformações. Pega uma vaga no semáforo
        do provedor, que limita duas chamadas simultâneas por padrão. Invoca. Se a resposta
        estruturada for inválida, regenera no mesmo provedor. Se a falha for de rede ou
        cota, passa para o próximo. Esgotou tudo, devolve uma mensagem vazia. Nunca levanta.
    """, F("RoutedLLM.invoke por candidato",
           ("Disjuntor", "Circuito aberto? pula e registra circuit_open"),
           ("Cliente", "Cache por provider, modelo e temperatura"),
           ("Transformações", "Reaplica structured output e tools"),
           ("Semáforo", "Até 2 chamadas em voo por provider"),
           ("Invoca", "Timeout curto, max_retries zero"),
           ("Schema inválido", "Tenta JSON local; regenera até 3 gerações"),
           ("Erro de transporte", "Passa para o próximo provider"),
           ("Tudo falhou", "AIMessage vazio: nunca levanta"))),

    sc("Semântica versus transporte", """
        Essa distinção é sutil e importante. Um erro de cota ou de rede não melhora tentando
        de novo no mesmo provedor; então o projeto troca de provedor. Já uma resposta mal
        formatada às vezes melhora numa segunda tentativa; então ele regenera no mesmo
        provedor, até três gerações, dizendo ao modelo qual contrato falhou. E antes de
        regenerar, tenta extrair um JSON válido do texto, sem custo nenhum.
    """, CMP("Duas falhas, dois remédios",
             "Falha de transporte", ["Timeout, 429, erro 5xx", "Não melhora no mesmo provider",
                                     "Ação: próximo da lista", "max_retries zero: fail-fast"],
             "Falha semântica", ["Schema não validou", "Às vezes melhora com instrução",
                                 "Tenta extrair JSON do texto, grátis", "Regenera no mesmo, até 3 gerações"])),

    sc("O disjuntor", """
        Um provedor sem saldo vai falhar sempre. Tentar de novo a cada turno só adiciona
        latência. Por isso existe um disjuntor: erros permanentes, como chave inválida,
        saldo insuficiente, modelo não encontrado ou dependência não instalada, abrem o
        circuito daquele provedor. A partir daí ele é pulado. No harness de playtest, os
        disjuntores são reiniciados a cada campanha.
    """, B("Erros que abrem o disjuntor",
           "401 ou 403: chave inválida ou sem permissão",
           "402 ou insufficient balance: saldo esgotado",
           "404: modelo removido ou inexistente",
           "Chave não configurada no ambiente",
           "Biblioteca do provider não instalada")),

    sc("Timeouts e detalhes de provedor", """
        Cada provedor tem manias. O DeepSeek usa um tempo limite padrão de doze segundos e
        tem o raciocínio oculto desligado, para não adicionar latência. Os demais usam
        noventa segundos. Os modelos Claude mais novos rejeitam o parâmetro de temperatura,
        então ele é omitido. E nenhum candidato faz novas tentativas internas: o plano B é
        sempre outro provedor.
    """, TB("Particularidades por provider",
            ["Provider", "Detalhe"],
            [["DeepSeek", "Timeout padrão 12 s; thinking desligado"],
             ["Groq", "Strict schema: usa function_calling"],
             ["Anthropic", "Sem temperature; sem prefill de IA"],
             ["Gemini", "Free tier: 20 req por dia por modelo"],
             ["Todos", "max_retries 0: o fallback é trocar"]])),

    sc("Telemetria sem derrubar o turno", """
        Dois ganchos observam a camada de modelos. Um recebe cada sucesso, com provedor,
        modelo, classe, latência e se houve fallback. O outro recebe cada tentativa,
        inclusive erros, com um código que diz se o problema foi transporte, ausência de
        chamada de ferramenta, ferramenta errada, parse ou validação. Ambos estão protegidos:
        telemetria nunca derruba o turno. A A P I usa isso para somar o custo real por turno.
    """, S("O que a telemetria registra",
           ("provider", "quem respondeu"),
           ("tier", "CLASSIFY, FAST ou SMART"),
           ("latência", "milissegundos por invoke"),
           ("fell_back", "se caiu para outro candidato"),
           ("código", "transport, parsing, schema..."))),

    sc("O modelo falso", """
        E o Mock L L M? Ele despacha pelo nome do esquema pedido: decisão de rota por
        palavras chave em português, atualização de história, plano de campanha, resposta de
        personagem. Ele até propõe missões, para o harness offline exercitá-las. Mas há um alerta: como ele
        sempre devolve objetos válidos, esconde erros de nome de campo que só aparecem com
        um modelo real.
    """, CO("warn", "O mock esconde bugs de mapeamento", "MockLLM sempre devolve instâncias Pydantic válidas, então res.campo nunca quebra. Bugs de nome ou tipo só aparecem com chave real: todo structured output novo exige smoke real.")),

    sc("Trocar rotas sem deploy", """
        Mudar de modelo não exige mexer nos agentes. Uma variável aponta para um arquivo
        de rotas que é mesclado com o padrão: classes não citadas mantêm a lista original.
        Outra variável força um provedor único para todas as classes, útil para jogar só
        com Gemini ou totalmente local. Provedores extras, como GLM e Kimi, ficam
        registrados para uso por arquivo. E uma função espelha a cascata para que a A P I
        diga ao jogador, sem mentir, quando o jogo está em modo simulado.
    """, TB("Alavancas de configuração dos modelos",
            ["Variável", "Efeito"],
            [["RPG_ROUTES", "Arquivo JSON mesclado com ROUTES"],
             ["LLM_PROVIDER", "Todos os tiers num provider único"],
             ["RPG_FORCE_MOCK", "MockLLM mesmo com chave"],
             ["RPG_NO_MOCK", "Sem chave: erro explícito, não mock"],
             ["DEEPSEEK_TIMEOUT_SECONDS", "Timeout próprio do DeepSeek"],
             ["RPG_LLM_MAX_CONCURRENCY", "Chamadas em voo por provider"]])),

    sc("Recapitulando os modelos", """
        Recapitulando. Três classes de modelo, cada uma com uma lista ordenada de
        candidatos, com DeepSeek na frente e Groq gratuito de reserva. Um roteador preguiçoso
        que separa falha de transporte de falha semântica, recupera JSON do texto e usa um
        disjuntor para provedores mortos. Telemetria por tentativa. E um modelo falso para
        jogar e testar sem rede.
    """, CO("key", "Recapitulação", "Três tiers com rotas ordenadas, DeepSeek primário e Groq de reserva. Transporte troca de provider; semântica regenera no mesmo. Disjuntor para erro permanente. Nunca levanta: devolve AIMessage vazio.")),
]))
