from h import *

CHAPTERS = []

# ---------------------------------------------------------------- c13
CHAPTERS.append(ch("A API, o streaming e a persistência", "#A0522D", [
    sc("A fronteira do sistema", """
        Toda a mecânica precisa de uma porta de entrada. Essa porta é uma A P I em Fast A P I,
        a única borda H T T P do projeto, com cerca de trinta rotas. Ela autentica, limita
        abusos, garante que um turno não rode duas vezes, transmite o progresso ao vivo e
        grava o estado de forma segura. 
    """, T("API e persistência", "Rotas, streaming, saves, checkpoints e morte")),

    sc("As rotas", """
        As rotas se dividem em grupos. Autenticação, que só existe nos perfis com banco.
        Dados estáticos, como opções de criação, introdução do mundo, mapa e catálogo do
        laboratório. Ciclo de jogo: prólogo, novo jogo, ação, ação com streaming, morte,
        equipar e subir de nível. Leitura: estado, Codex, histórico, saves, busca e
        exportação da crônica. Arte. E infraestrutura: saúde e métricas.
    """, TB("Catálogo de rotas",
            ["Grupo", "Rotas principais"],
            [["Auth (perfis com banco)", "/auth/config, login, signup, refresh"],
             ["Dados", "/data/options, onboarding, map"],
             ["Criação", "/game/prologue, /game/new, simulador"],
             ["Turno", "action, action/stream, operations"],
             ["Mutação", "death, equip, levelup, DELETE save"],
             ["Leitura", "state, codex, history, saves, crônica"],
             ["Arte e infra", "/game/art/*, /health, /metrics"]])),

    sc("Middlewares", """
        Antes de chegar às rotas, cada pedido passa por camadas. C O R S restringe as
        origens. Nos perfis com banco, uma fronteira de sessão confere o cookie de acesso e,
        em mutações, exige um token anti C S R F e uma origem permitida. Outra camada correlaciona e mede cada pedido. E um
        limitador barra mais de trinta pedidos por minuto por endereço nas rotas caras.
    """, G("Camadas de um pedido HTTP", "LR",
           [("rq", "Pedido HTTP", "io"), ("co", "CORS", "infra"), ("se", "Sessão e CSRF", "infra"),
            ("cr", "Correlação e métricas", "infra"), ("rl", "Rate limit", "infra"), ("rt", "Rota", "python")],
           [("rq", "co"), ("co", "se", "perfis DB"), ("se", "cr"), ("cr", "rl"), ("rl", "rt", "30 por min")])),

    sc("Streaming com garantia", """
        A rota de streaming tem um desenho cuidadoso. Ela responde imediatamente com um evento
        de aceito e entrega o trabalho a uma thread separada, que é dona do lock, da execução
        e do save. Se o navegador desconectar, o turno termina e é gravado mesmo assim.  Se o stream falhar, o
        cliente refaz o pedido normal com o mesmo identificador, sem duplicar.
    """, CO("key", "O worker SSE é dono do turno", "A thread worker segura o lock, roda o grafo e grava o save. Cliente desconectado não corta o turno. Ping a cada 10 s. Fallback POST com o mesmo action_id é idempotente.")),

    sc("A resposta pública", """
        A resposta é uma visão pública do estado. Leva a mensagem e seu tipo, a ficha com
        vitalidade, ferimentos, entropia e Carga, o inventário, o mundo com relógio, névoa,
        clima e luz, missões, personagens conhecidos, crônica, facções, comitiva e flags de
        morte. No combate, mostra só o que é público do inimigo: vitalidade, esquiva e o que
        já foi revelado. Detalhes internos e custos nunca saem.
    """, B("O que o GameResponse expõe",
           "message e message_type: STORY, COMBAT, NPC ou LOOT",
           "player_stats: Vitalidade, Ferimentos, Entropia, Carga, Cartas",
           "world: relógio, fog of war, clima, luz, rotas bloqueadas",
           "combat: só o painel público do inimigo e a cena",
           "death_pending, game_over, continuity e visual",
           "Nunca: custo de LLM, traits ocultos, beats privados")),

    sc("Saves atômicos e versionados", """
        No perfil legado, cada jogo é um arquivo JSON com nome de U U I D, confinado à pasta
        de saves para impedir travessia de caminho. A escrita é atômica: grava num temporário,
        força o disco e troca, com até seis tentativas para tolerar travas do OneDrive e de
        antivírus. Cada save tem versão de esquema, hoje oito, e migrações puras e
        idempotentes atualizam saves antigos ao carregar.
    """, TB("Histórico do schema de save",
            ["Versão", "O que mudou"],
            [["v2 e v3", "NPC em camadas; 5 Posturas e Entropia"],
             ["v4", "Virtudes, Vitalidade e Ferimentos"],
             ["v5", "Vitalidade canônica e aliases de HP"],
             ["v6", "Ledger visual"],
             ["v7", "Metatempo: continuity"],
             ["v8", "Crônica com IDs e progressão 1 a 20"],
             ["Abaixo de v4", "Arquivado: somente leitura"]])),

    sc("A tela de morte", """
        Quando o herói morre de verdade, no combate ou num descanso fatal, o estado fica
        com morte pendente, e tanto o grafo quanto a A P I recusam novos turnos. A interface abre a tela
        de morte com duas opções. Continuar do checkpoint restaura o último ponto seguro,
        inclusive a memória vetorial daquela época. Aceitar a morte transforma o save num
        memorial, com o evento de morte e um marco na crônica.
    """, G("Do golpe fatal à escolha", "TB",
           [("hit", "Morte real confirmada", "python"), ("dp", "death_pending", "data"),
            ("modal", "Tela de morte", "io"), ("cont", "Continuar do checkpoint", "python"),
            ("acc", "Aceitar a morte", "python"), ("rest", "Estado restaurado", "data"),
            ("mem", "Memorial game_over", "data")],
           [("hit", "dp"), ("dp", "modal"), ("modal", "cont"), ("modal", "acc"),
            ("cont", "rest", "epoch + 1"), ("acc", "mem", "player_died")])),

    sc("Metatempo", """
        Restaurar cria uma questão filosófica: que horas são? O projeto separa dois relógios.
        O turno canônico do mundo volta ao do checkpoint. Mas o contador de ações da sessão
        nunca retrocede, e uma época da linha do tempo sobe a cada restauração. O histórico
        de mortes guarda o que foi mantido e o que foi revertido, e a tela de morte mostra
        exatamente quantos turnos serão perdidos.
    """, EX("Restauração após uma morte",
            ("Turno da morte", "73"),
            ("Último checkpoint", "70"),
            ("Turnos revertidos", "3"),
            ("Mantém", "histórico de mortes e ações da sessão"),
            ("Reverte", "mundo, inventário, posição e memória"),
            ("timeline_epoch", "1 para 2"))),

    sc("O log de cada turno", """
        Cada turno deixa uma única linha de log em JSON, pensada para não vazar nada. O
        jogo aparece por um pseudônimo, não pelo identificador real. Há rota, latência,
        eventos aplicados e rejeitados, custo estimado e as tentativas de modelo. Um erro
        registra só o nome da exceção, nunca a mensagem, e o jogador recebe um erro
        quinhentos genérico. Métricas no formato do Prometheus medem duração por rota,
        commits, banco e o tempo até o primeiro evento do streaming.
    """, EX("Uma linha rpg.turn",
            ("evt", "turn"),
            ("game_id_ref", "pseudônimo HMAC, não o id"),
            ("route e latency_ms", "storyteller, 14230"),
            ("events", "aplicados 1, rejeitados 0"),
            ("llm", "provider, tier, fallback e custo"),
            ("error", "só o nome da exceção, se houver"))),

    sc("Histórico estável para o cliente", """
        O histórico que o jogador vê não é a lista curta de mensagens que o modelo recebe.
        Ele é um registro separado e paginado, com uma linha para cada ação e cada
        narração, e um identificador derivado do jogo, da época e do turno, para nunca
        duplicar. A paginação usa um cursor com a época da linha do tempo: depois de uma
        restauração, um cursor antigo é recusado, para não misturar linhas de linhas do
        tempo diferentes. Saves antigos ganham um histórico reconstruído, marcado como
        parcial.
    """, CMP("Dois históricos",
             "Transcrito do modelo", ["Últimas 20 mensagens na API", "Entrada curta do grafo",
                                      "Reescrito pelas guardas"],
             "Histórico de apresentação", ["Linhas de jogador e narrador", "Id por jogo, época e turno",
                                           "Cursor época e offset", "Cursor de outra época: 409"])),

    sc("Mover saves com segurança", """
        Para migrar saves de arquivo para o banco, há uma ferramenta que mostra antes de
        agir. A varredura classifica cada arquivo e calcula seu hash, sem escrever nada. A
        importação só insere: repetir uma importação idêntica pula, e uma colisão com
        conteúdo diferente falha. A exportação gera um pacote portátil por dono, com hashes
        independentes que podem ser verificados depois. A mesma serialização serve ao
        arquivo, ao checkpoint e ao banco.
    """, F("Transferência preview-first",
           ("Scan", "Classifica e calcula SHA-256, sem escrita"),
           ("Preview", "O operador vê o que vai acontecer"),
           ("Import", "Insert-only; idêntico pula, divergente falha"),
           ("Export", "Pacote portátil por dono com hashes"),
           ("Verify", "Confere o pacote exportado"))),

    sc("Jogar no terminal", """
        Além do navegador, dá para jogar pela linha de comando, sobre o mesmo grafo. O
        terminal carrega o save mais recente ou abre um assistente de criação. Comandos
        locais como status e equipar não gastam turno. A cada ação, imprime a mensagem
        final, resolve escolhas de nível, grava o save e, na morte, oferece continuar do
        checkpoint ou aceitar o fim. Uma diferença: se um turno falha, o terminal avisa e
        segue sem gravar aquele turno.
    """, CMP("Terminal versus A P I",
             "Linha de comando", ["Mesmo grafo compilado", "Mantém 15 mensagens",
                                  "Erro: avisa e continua o loop", "Sem login nem streaming"],
             "API web", ["Mesmo grafo compilado", "Mantém 20 mensagens",
                         "Erro: 500 genérico, save anterior", "Login nos perfis com banco, SSE"])),

    sc("Recapitulando a API", """
        Recapitulando. Uma única borda com trinta rotas, protegida por C O R S, sessão,
        C S R F, correlação e limite de taxa. Streaming em que a thread é dona do turno.
        Resposta pública sem vazar o interno. Saves atômicos com esquema versionado e
        migrações. E uma tela de morte com checkpoint, memorial e um metatempo que lembra
        das mortes mesmo depois de voltar no tempo.
    """, CO("key", "Recapitulação", "Uma borda HTTP com middlewares de segurança, SSE com worker dono do turno, resposta pública, saves atômicos versionados (v8) e morte com checkpoint, memorial e metatempo.")),
]))

# ---------------------------------------------------------------- c14
CHAPTERS.append(ch("O frontend e a jornada do jogador", "#B8943F", [
    sc("A cara de Valoria", """
        Agora, o que o jogador vê. O cliente principal é um aplicativo React com
        Vite e TypeScript, num tom escuro medieval inspirado em The Witcher, com animações
        suaves e brasas flutuando ao fundo. Neste capítulo percorremos a jornada do jogador,
        tela a tela, e os detalhes que tornam a experiência robusta.
    """, T("Frontend e jornada", "React, Vite e TypeScript em tom dark medieval")),

    sc("Uma máquina de telas", """
        O aplicativo não usa roteador de páginas. Ele é uma máquina de telas: abertura,
        login quando exigido, lista de saves, criação, jogo e laboratório. Ao abrir, consulta
        se a autenticação é exigida. Se houver saves, mostra a lista para continuar; senão,
        vai direto para a criação. Uma sessão expirada dispara um evento que devolve ao login.
    """, G("Telas do aplicativo", "LR",
           [("boot", "Bootstrap", "io"), ("auth", "Login", "io"), ("saves", "Saves", "io"),
            ("create", "Criação", "io"), ("sim", "Laboratório", "io"), ("play", "Jogo", "io")],
           [("boot", "auth", "auth exigida"), ("boot", "saves"), ("boot", "create", "sem saves"),
            ("auth", "saves"), ("saves", "create"), ("saves", "play", "continuar"),
            ("create", "play"), ("create", "sim")])),

    sc("A criação imersiva", """
        A criação é um assistente de cinco passos. O Mundo apresenta Valoria. Origem mostra
        seis raças com arte e traços. Vocação mostra as cinco Posturas. Região mostra os
        bônus de cada lugar. Identidade pede nome, história e aparência. Por fim, um prólogo
        gerado pelo modelo inteligente propõe um arco pessoal com personagens semente. Você
        pode refinar ou começar a jornada.
    """, F("Assistente de criação",
           ("O Mundo", "Introdução de Valoria, ou pular"),
           ("Origem", "6 raças com arte e traços mecânicos"),
           ("Vocação", "As 5 Posturas diante do Abismo"),
           ("Região", "12 regiões com bônus"),
           ("Identidade", "Nome, história, aparência, brief de arte"),
           ("Prólogo", "Arco pessoal, beats e NPCs semente"),
           ("Começar", "/game/new semeia arco, NPCs e cena"))),

    sc("O prólogo e uma lição", """
        O prólogo deixou uma lição. A primeira versão do esquema tinha
        limites rígidos de tamanho, e todos os provedores escreviam um pouco além: o
        validador derrubava tudo e o jogo caía sempre no modelo padrão. A solução foi
        deixar o tamanho como dica para a IA, truncar em Python e aplicar limites estritos só
        na entrada da A P I. O modelo falso nunca teria mostrado isso.
    """, CO("info", "Padrão para todo schema novo", "Tamanho vira dica na description; Python trunca e normaliza; limites estritos só na borda da API, com erro 422. O MockLLM não detecta esse tipo de falha: smoke real obrigatório.")),

    sc("A tela de jogo", """
        A tela de jogo tem uma barra superior com local, dia, período, clima e luz. Uma
        ilustração do lugar. O registro da narrativa com efeito de máquina de escrever. Uma
        barra de ação para escrever livremente. E um painel lateral com oito abas: ficha,
        combate, personagens, mapa, facções, missões, crônica e Codex. No celular, o painel
        vira uma gaveta deslizante.
    """, B("O HUD em oito abas",
           "Ficha: Vitalidade, Entropia, Carga, Virtudes e equipamento",
           "Combate: inimigos públicos, iniciativa e condições",
           "Personagens e Facções: relações e reputação",
           "Mapa: névoa de guerra, clique para viajar",
           "Missões e Crônica: busca e exportação",
           "Codex: conhecimento descoberto, carregado sob demanda")),

    sc("Combate na interface", """
        No combate, a tela muda. Aparece uma mão de Cartas preparadas, cada uma com custo,
        frequência, estado e botão de Ruptura quando pronta. Um seletor de reação escolhe uma
        carta para a rodada. Há a trilha de ferimentos, as zonas da cena e botões de manobra:
        engajar, guardar, esconder, procurar e fugir. O texto enviado é cosmético: o servidor
        usa o identificador estruturado da carta.
    """, EX("Clique em uma Carta",
            ("Jogador clica", "Jogar Carta: Golpe Sombrio"),
            ("Texto enviado", "Uso Golpe Sombrio."),
            ("Campos estruturados", "card_id, target_id, ruptura"),
            ("Reação da rodada", "reaction_card_id escolhido antes"),
            ("No servidor", "vira combat_declaration, sem LLM"),
            ("Resultado", "rodada resolvida em Python e narrada"))),

    sc("Ação pendente e retomada", """
        A interface leva a robustez a sério. Antes de enviar, grava a ação pendente no
        armazenamento local, com um identificador e um hash do pedido. Se a aba fechar, ao
        voltar ela pergunta ao servidor se a operação terminou. Respostas atrasadas de outra
        sessão são descartadas. Um 401 dispara uma única renovação de sessão compartilhada.
        E tudo respeita a preferência por menos movimento.
    """, B("Robustez no cliente",
           "Ação pendente em localStorage com UUID e hash do payload",
           "Retomada: consulta a operação antes de reenviar",
           "Contador de sessão descarta respostas atrasadas",
           "Refresh de sessão single-flight em 401",
           "Fallback POST com o mesmo action_id se o stream falhar",
           "Reduced motion desliga animações e brasas")),

    sc("Saves, modais e primeiros passos", """
        Outras telas completam a jornada. A lista de saves mostra cada herói com classe,
        nível, local e dia, com selos para memorial e laboratório, e pede confirmação antes
        de apagar uma saga. Quando há escolhas de nível, um modal pergunta subclasse,
        Carta, Virtude ou Maestria, e pode ser adiado. A tela de morte mostra o que será
        mantido e revertido. E no primeiro turno, uma dica dispensável lista exemplos de
        comandos.
    """, TB("Telas e modais de apoio",
            ["Elemento", "Papel"],
            [["SaveScreen", "Continuar, apagar, nova jornada"],
             ["LevelUpModal", "Subclasse, Carta, Virtude, Maestria"],
             ["DeathModal", "Continuar do checkpoint ou aceitar"],
             ["Overlay de memorial", "Começar de novo ou ler a crônica"],
             ["OnboardingHint", "Exemplos de comando no turno 1"],
             ["Banners", "Modo simulado ou degradado, uma vez"]])),

    sc("Tema, celular e acessibilidade", """
        O visual usa tokens de cor num espaço perceptual, dourado sobre bronze escuro, com
        fontes de inspiração medieval para títulos e uma serifada clássica para o texto.
        Abaixo de novecentos pixels, o painel lateral vira uma gaveta; em telas de
        celular, ocupa a largura toda, com botão de fechar. A preferência por menos
        movimento desliga animações e brasas. E dezesseis jornadas automatizadas verificam
        acessibilidade e layout em quatro larguras de tela.
    """, S("Interface verificada",
           ("900 px", "HUD vira gaveta deslizante"),
           ("390 px", "largura de celular validada"),
           ("16", "jornadas F01 a F16 no Playwright"),
           ("4", "viewports: 320, 390, 768 e 1440"),
           ("0", "violações a11y sérias ou críticas"))),

    sc("Recapitulando o frontend", """
        Recapitulando. Uma máquina de telas em React, com criação em cinco passos e um
        prólogo pessoal. Uma tela de jogo com narrativa animada, ilustração do lugar e um
        painel de oito abas. Combate tático com mão de Cartas e manobras estruturadas. E uma
        camada de robustez com ações pendentes, retomada e renovação de sessão. Ainda existe
        um cliente legado sem build, usado só se o novo não estiver compilado.
    """, CO("key", "Recapitulação", "SPA em máquina de telas; criação em 5 passos com prólogo; HUD de 8 abas; combate com Cartas e manobras estruturadas; ação pendente, retomada e refresh single-flight. Cliente vanilla legado como fallback.")),
]))

# ---------------------------------------------------------------- c15
CHAPTERS.append(ch("Arte visual: curada e dinâmica", "#8A6D2F", [
    sc("Imagens com critério", """
        Um R P G de texto ganha muito com algumas imagens bem escolhidas. O projeto tem duas
        fases de arte. Uma usa ilustrações curadas, escolhidas sem nenhuma IA na hora do jogo.
        A outra gera arte rara sob demanda, com orçamento rígido, desligada por padrão. Em
        ambas, a escolha da imagem é determinística: a IA nunca decide qual arquivo mostrar.
    """, T("Arte visual", "Fase 8A curada e Fase 8B dinâmica")),

    sc("A arte curada", """
        A fase curada tem quarenta e cinco ilustrações em noventa versões otimizadas, nos
        tamanhos miniatura e exibição: seis raças, cinco classes, vinte e dois locais e doze
        personagens. Locais sem arte própria usam uma arte da região. Um importador valida
        hash e visibilidade, remove metadados e respeita limites de bytes. Personagens
        secretos nunca entram no catálogo público.
    """, S("Catálogo curado",
           ("45", "ilustrações aprovadas"),
           ("90", "arquivos WebP: thumb e display"),
           ("22", "locais com arte exata"),
           ("13", "locais com fallback regional"),
           ("12", "retratos de NPC"))),

    sc("Primeira aparição", """
        Quando um personagem conhecido aparece pela primeira vez na cena, a interface mostra
        seu retrato antes do texto. A identidade vem de identificadores canônicos e apelidos,
        nunca de procurar nomes na prosa. Um personagem gerado em jogo sem arte recebe um
        monograma, e nunca empresta o rosto de outro. O registro é por ação, então repetir o
        pedido devolve a mesma imagem, no stream e no pedido normal.
    """, F("Cue visual de NPC",
           ("Elegíveis", "Conhecidos, em cena e ainda não vistos"),
           ("Escolha", "NPC ativo ou o que acabou de entrar"),
           ("Identidade", "ID canônico e aliases, nunca a prosa"),
           ("Sem arte", "Monograma: nunca outro rosto"),
           ("Ledger", "Por action_id: retry mostra a mesma"))),

    sc("A arte dinâmica rara", """
        A fase dinâmica gera imagens com um modelo de imagem pinado numa versão exata. Ela é
        rara de propósito: um retrato do jogador, com uma única reformulação, e por arco de
        campanha até quatro personagens novos sem arte, com intervalo de quinze turnos, e um
        momento épico, como um combate contra chefe. Escolher subclasse nunca gera imagem.
        O jogador revisa o pedido antes e confirma o custo possível.
    """, TB("Gatilhos e orçamento da arte dinâmica",
            ["Gatilho", "Limite"],
            [["Retrato do jogador", "1 + 1 reformulação"],
             ["NPC sem arte curada", "4 por arco, cooldown 15 turnos"],
             ["Momento épico", "1 por arco: combate com chefe"],
             ["Escolha de subclasse", "Zero jobs, zero custo"],
             ["Resultado incerto", "Nunca regenerado automaticamente"]])),

    sc("O pipeline da arte dinâmica", """
        Por dentro, a arte dinâmica é um pipeline com várias travas. O pedido nasce de um
        brief com âncoras de estilo, raça e classe, e o texto do jogador é higienizado
        contra injeção de instruções. A reserva entra no orçamento do arco e vira um job.
        O trabalhador chama o gerador uma única vez, valida e converte a imagem para WebP
        sem metadados, e grava num armazenamento privado. O cliente acompanha o estado e
        recebe endereços assinados de curta duração.
    """, F("Da ideia ao retrato",
           ("Brief", "Âncoras de estilo; texto do jogador higienizado"),
           ("Reserva", "Orçamento por arco e id determinístico"),
           ("Job", "Na mesma transação do turno, nos perfis DB"),
           ("Geração", "Uma chamada ao modelo de imagem pinado"),
           ("Processamento", "Até 20 MiB; WebP full e thumb sem EXIF"),
           ("Storage privado", "Chave users, dono, jogo, sha"),
           ("Cliente", "Polling com backoff; URL assinada 300 s"),
           ("Restore", "Gerações da linha descartada: superseded"))),

    sc("Recapitulando a arte", """
        Recapitulando. Arte curada com catálogo validado, retratos na primeira aparição e
        escolha sempre determinística. Arte dinâmica rara, opcional e com orçamento por arco,
        produzida por um trabalhador em segundo plano que processa a imagem, remove metadados
        e grava num armazenamento privado. E uma regra de ouro: nunca cobrar duas vezes por
        um resultado incerto.
    """, CO("key", "Recapitulação", "Arte curada: 45 ilustrações, escolha por ID canônico. Arte dinâmica: modelo pinado, orçamento por arco, revisão e confirmação do jogador, worker com storage privado e proteção contra cobrança dupla.")),
]))
