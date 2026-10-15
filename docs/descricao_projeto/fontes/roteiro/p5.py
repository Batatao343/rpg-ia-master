from h import *

CHAPTERS = []

# ---------------------------------------------------------------- c16
CHAPTERS.append(ch("Infraestrutura local-first", "#3D7A5C", [
    sc("Do laboratório ao serviço", """
        Até aqui, o jogo pode rodar com arquivos JSON e índices em disco, travado por
        processo. Isso basta para um jogador local, mas não para muitos usuários. A fase dez
        b transformou o armazenamento num plano substituível: o domínio fala com portas, e
        adaptadores implementam cada porta para dois mundos. Tudo foi ensaiado localmente,
        com custo zero, antes de qualquer nuvem.
    """, T("Infraestrutura local-first", "Portas, Postgres, leases, outbox e operação")),

    sc("Portas e perfis", """
        As portas são contratos em Python: guardar jogos, catálogo de runtime, memória,
        arquivos binários, fila de jobs, coordenador de turnos, limitador de taxa e
        verificador de identidade. Um perfil escolhe os adaptadores. O legado usa arquivos e
        memória em processo. O perfil local usa Postgres e Supabase. Os perfis portátil e
        hospedado trocam Supabase por O I D C e armazenamento S três.
    """, TB("Perfis de runtime",
            ["Perfil", "Jogos e fila", "Blob e auth"],
            [["legacy", "Arquivos, inline", "Arquivos, sem login"],
             ["local", "Postgres e pgvector", "Supabase Storage e Auth"],
             ["portable", "Postgres e pgvector", "S3 e OIDC"],
             ["hosted", "Postgres e pgvector", "S3 e OIDC, sem loopback"]])),

    sc("Nunca segurar transação durante a IA", """
        A decisão mais importante da camada durável: nenhuma transação fica aberta enquanto
        um modelo de linguagem pensa. A mutação acontece em duas fases curtas. Primeiro, uma
        transação reivindica o jogo e cria uma operação com um prazo. Depois o grafo roda
        fora de qualquer transação. Por fim, uma segunda transação confere o prazo e a versão
        e grava tudo de uma vez.
    """, F("Turno durável em duas fases",
           ("Recibo?", "Operação já concluída devolve o recibo"),
           ("Claim", "Trava jogo, cria operação com lease de 180 s"),
           ("Grafo", "Roda fora de transação, com heartbeat"),
           ("Commit", "Confere lease, token e versão"),
           ("Grava", "Jogo, eventos, recibo, custo, jobs"),
           ("Libera", "Limpa a operação ativa do jogo"))),

    sc("Lease e fencing", """
        O mecanismo de exclusão usa dois conceitos. Lease é um empréstimo com prazo: o
        trabalhador tem o jogo por cento e oitenta segundos e renova a cada quarenta e cinco.
        Fencing é um token: o commit só passa se o token gravado for o mesmo do claim. Assim,
        um trabalhador atrasado não consegue publicar. E a ordem de travas é fixa, para evitar impasses.
    """, CO("key", "Lease mais fencing", "Lease: posse com prazo, renovada por heartbeat a cada lease/4. Fencing: o commit exige o mesmo lease_token e a versão base. Worker atrasado não publica. Locks sempre na ordem jogo, depois operação.")),

    sc("Exatamente uma vez", """
        O cálculo pode acontecer mais de uma vez em caso de falha, mas o commit acontece
        exatamente uma vez por chave. A tabela de operações é um livro de idempotência e
        recibos. Repetir a chave com o mesmo pedido devolve o recibo. Repetir com um pedido
        diferente é um conflito. E uma chave de outro dono responde indisponível, sem revelar
        que existe.
    """, TB("Respostas da reivindicação",
            ["Situação", "Resposta"],
            [["Chave nova, jogo livre", "Claim com novo lease"],
             ["Chave concluída", "Devolve o recibo gravado"],
             ["Mesma chave, payload diferente", "409 conflito"],
             ["Outra operação ativa", "409 game_busy"],
             ["Lease expirado", "Retomada com token novo"],
             ["Chave de outro dono", "Indisponível, sem vazar"]])),

    sc("Outbox de memória", """
        A memória segue um padrão chamado outbox. Durante o turno, os fatos de memória não
        são gravados, apenas acumulados. Só no commit eles são escritos, na mesma transação,
        junto com um job de cálculo de embedding. Se o turno não commitar, o fato não existe.
        Um trabalhador separado calcula o vetor depois. Se o serviço de embeddings cair, o
        turno continua válido e o job tenta de novo.
    """, G("Outbox de memória no Postgres", "LR",
           [("tn", "Turno no grafo", "llm"), ("fx", "Efeitos acumulados", "python"),
            ("cm", "commit_game", "infra"), ("md", "memory_documents", "data"),
            ("jb", "Job embed_memory", "data"), ("wk", "Worker de embeddings", "infra"),
            ("vc", "Vetor pronto", "data")],
           [("tn", "fx"), ("fx", "cm", "flush"), ("cm", "md"), ("cm", "jb"), ("jb", "wk"), ("wk", "vc")])),

    sc("Banco e segurança", """
        O esquema vive em migrações versionadas. Um esquema próprio guarda jogos como
        documento JSON com versão otimista, checkpoints, eventos imutáveis com hash,
        operações, turnos, jobs e limites de taxa. A primeira barreira é o filtro explícito
        pelo dono em cada consulta. A segunda é a segurança em nível de linha, ligada e
        forçada nas tabelas, com uma função que extrai o dono do token e um papel sem
        poder de contorná-la. Testes de banco provam o isolamento entre usuários.
    """, B("Defesas do banco",
           "RLS ligada e forçada; policy owner_id = dono do token",
           "Papel rpg_api sem login e sem bypass de RLS",
           "anon e authenticated sem acesso ao schema app",
           "Eventos imutáveis: hash divergente vira conflito",
           "Cookies HttpOnly, CSRF assinado e Origin na allowlist",
           "14 asserts de banco e testes de isolamento A e B")),

    sc("Identidade, cookies e CSRF", """
        Nos perfis com banco, o navegador nunca guarda um token de acesso legível. A sessão
        vive em cookies HttpOnly, e toda mutação exige um token anti C S R F assinado, igual
        no cookie e no cabeçalho, e uma origem permitida. O cookie de renovação só vale
        para a rota de renovação. A identidade é verificada pelo Supabase Auth no perfil
        local, ou por O I D C nos perfis portátil e hospedado. E a chave de serviço nunca
        pode cair no pacote do navegador.
    """, B("Fronteira de sessão",
           "Cookies HttpOnly de acesso e refresh; CSRF legível",
           "Mutação: CSRF assinado igual em cookie e header",
           "Origin obrigatória e na allowlist",
           "Refresh só em /auth/refresh com SameSite Strict",
           "Service role com prefixo VITE_ é recusada")),

    sc("Trabalhadores e a cerca dos jobs", """
        Os trabalhadores processam três tipos de job: calcular embeddings de memória,
        comprimir capítulos da crônica e gerar arte dinâmica. Cada um pega um job por vez,
        com prazo renovado por batimento. Toda escrita derivada trava a linha do job na
        mesma transação e confere o token: quem perdeu o prazo não publica. Falhas esperam
        cada vez mais, até a fila morta. E a arte nunca é tentada de novo quando o
        resultado externo é incerto.
    """, TB("Os três jobs",
            ["Job", "O que faz", "Proteção"],
            [["embed_memory", "Calcula o vetor do fato", "Confere hash e perfil"],
             ["compress_chronicle", "Digest do capítulo", "Raw segue autoritativo"],
             ["generate_dynamic_art", "Gera e grava a imagem", "Sem retry se incerto"],
             ["Todos", "Lease, heartbeat e fence", "Backoff até dead-letter"]])),

    sc("Arquivos e armazenamento", """
        Imagens geradas e outros binários passam por uma porta de armazenamento com três
        implementações: arquivos locais, Supabase Storage e qualquer serviço compatível com
        S três. Toda chave começa com o dono, o que casa com as políticas de acesso do
        bucket privado. O bucket aceita só imagens WebP de até vinte megabytes. A arte
        curada, por outro lado, não passa por aqui: é servida como arquivo estático junto
        com o frontend.
    """, CMP("Dois caminhos para imagens",
             "Arte dinâmica", ["BlobStore: arquivo, Supabase ou S3", "Chave users, dono, jogo e hash",
                               "Bucket privado rpg-dynamic", "URL assinada de curta duração"],
             "Arte curada", ["90 WebPs no frontend", "Servida como arquivo estático",
                             "Catálogo com hash e visibilidade", "Sem storage nem custo"])),

    sc("Fila, observabilidade e backup", """
        A fila de jobs usa travas que pulam linhas ocupadas, recupera jobs de trabalhadores
        mortos e aplica espera exponencial até virar fila morta. A observabilidade tem
        dezessete métricas com rótulos fechados, rastreamento opcional e uma pilha local com
        Prometheus, Grafana, coletor e Tempo, com sete alertas. E há backup com manifesto de
        hashes e restauração medida em trinta e seis segundos.
    """, S("Prontidão local medida",
           ("32 ms", "commit p95 no teste de carga"),
           ("5 de 5", "cenários de caos convergiram"),
           ("1.000", "turnos de soak, zero erros"),
           ("36 s", "RTO medido de DB, Auth e Storage"),
           ("RPO 0", "para turnos confirmados"),
           ("7", "alertas validados"))),

    sc("Operar o laboratório", """
        A operação local tem ferramentas com cinto de segurança. Um script sobe, consulta e
        para a pilha do Supabase local, e recusa rodar contra um projeto remoto. O backup só
        opera em contêineres com o rótulo do laboratório e gera um manifesto de hashes; a
        restauração exige confirmação explícita e destino vazio. Operações presas são
        listadas em modo de prévia, e só são abandonadas com um comando de aplicação, se o
        prazo já expirou.
    """, TB("Runbook de incidentes locais",
            ["Incidente", "Ação"],
            [["API caiu antes do commit", "Repetir o mesmo action_id"],
             ["Worker morreu", "Outro assume após o lease; fencing"],
             ["Operação presa", "recover_operations em preview"],
             ["Embedding ou blob fora", "Turno segue canônico; job reconverge"],
             ["Banco reiniciado", "Reiniciar API e worker; repetir chave"],
             ["Backup inválido", "Não restaurar"]])),

    sc("Prontidão G0 a G7", """
        Antes de declarar a infraestrutura pronta, o projeto passou por oito portões,
        registrados num relatório gerado com dados redigidos. Suíte offline, integração
        local com Postgres, Auth e Storage, segurança, caos, carga com vários processos,
        mil turnos de resistência, backup e restauração, e por fim navegador, build,
        linters e auditorias. O veredito em agosto foi pronto para uso local. A nuvem
        segue fora desse veredito.
    """, TB("Os portões de prontidão",
            ["Portão", "Evidência"],
            [["G0", "Suíte offline verde"],
             ["G1 e G2", "infra 13/13, pgTAP 14/14, security 5/5"],
             ["G3 e G4", "Caos 5 de 5; commit p95 32 ms"],
             ["G5", "Soak de 1.000 turnos, zero erros"],
             ["G6", "Backup e restore: RPO 0, RTO 36 s"],
             ["G7", "Browser, build, audits e 7 alertas"]])),

    sc("Recapitulando a infra", """
        Recapitulando. Portas e adaptadores permitem trocar arquivos por Postgres sem mudar o
        domínio. Nenhuma transação durante a IA: claim curto, grafo livre, commit curto.
        Lease mais fencing garantem um dono por vez. Commit exatamente uma vez por chave.
        Outbox para memória. Segurança em nível de linha. E tudo certificado localmente; a
        certificação em nuvem ainda é um rascunho.
    """, CO("key", "Recapitulação", "Portas e perfis; claim, grafo e commit sem transação durante a IA; lease, fencing e commit exactly-once; outbox de memória; RLS forçada; observabilidade e backup. Cloud ainda não certificada.")),
]))

# ---------------------------------------------------------------- c17
CHAPTERS.append(ch("Qualidade: testes, playtest e evals", "#4B5A8A", [
    sc("Como se garante um jogo de IA", """
        Como garantir que um jogo movido por IA funciona, se a IA é imprevisível? A resposta
        do projeto é uma pilha de garantias, das mais baratas às mais caras: testes offline,
        linters de conteúdo, um harness de playtest que joga campanhas inteiras, uma
        plataforma de avaliações determinísticas e um processo em que nada é feito sem
        especificação.
    """, T("Qualidade", "Testes, playtest agêntico, invariantes e evals")),

    sc("A pirâmide de garantias", """
         Na base, a suíte de testes, com cerca de mil e novecentos
        testes, roda sem rede em alguns minutos e é o portão de toda tarefa. Acima, o lint de
        conteúdo e de código. Depois, o playtest agêntico, offline ou com modelo real. Depois,
        os evals com réguas travadas. E no topo, a cara e rara validação com provedor pago.
    """, F("Camadas de garantia, da base ao topo",
           ("Suíte offline", "1.898 testes com MockLLM, sem rede"),
           ("Linters", "Conteúdo, Ruff e build do frontend"),
           ("Playtest offline", "14 perfis jogam campanhas longas"),
           ("Evals determinísticos", "Datasets travados por hash"),
           ("Contratos reais", "Markers opt-in, com teto de custo"),
           ("Matriz real", "10 campanhas de 200 turnos"))),

    sc("A suíte offline", """
        A suíte força o modelo falso em todos os testes e isola saves, memória e cache em
        pastas temporárias. Testes que dependem de modelo real, banco local ou navegador
        ficam fora do padrão, atrás de marcadores. Há testes por fase e por domínio:
        combate, classes, playtest, evals, infraestrutura, arte e até a integridade do índice
        de especificações.
    """, C("O que fica fora da suíte padrão", "pyproject.toml", "bash", """
addopts = "-q -m \\"not llm_contract and not llm_playtest\\""
markers = [
    "llm_contract: contrato contra provider LLM real (...)",
    "llm_playtest: campanha curta de playtest por perfil (...)",
    "infra_local: integração opt-in com Postgres/Auth/...",
    "security_local: testes opt-in de RLS, CSRF, ownership (...)",
    "chaos_local: testes opt-in de kill/restart/timeouts (...)",
    "browser_local: browser real opt-in contra servidor local",
]
""")),

    sc("O harness de playtest", """
         Robôs jogam campanhas inteiras sobre o mesmo
        grafo de produção. São catorze perfis determinísticos, cada um com uma personalidade:
        o agressivo, o explorador, o comerciante, o diplomático, o troll que manda absurdos,
        o que tenta quebrar o mapa, o caçador de segredos, o fujão, o recrutador e o jogador
        normal, que mistura tudo com prudência.
    """, TB("Alguns dos 14 perfis",
            ["Perfil", "O que testa"],
            [["Explorador", "Fronteira do mapa, sem ir e voltar"],
             ["Comerciante", "Livro de cotações e conservação de ouro"],
             ["Troll", "Absurdos e injeção de prompt"],
             ["SecretRusher", "Pergunta direto pelos segredos"],
             ["Fujao", "Fuga e trilha de perseguição"],
             ["LootAbuser", "Tenta duplicar item único"],
             ["Normal", "Jogador curioso, só visão pública"]])),

    sc("Invariantes", """
        A cada turno, dezenas de invariantes verificam o estado. Vitalidade coerente, ouro sem
        negativos, item único sem duplicata, resumo dentro do limite, memória sem confirmação
        sem fonte, narração sem vazamento de instruções, sem morte falsa, combate sem zumbi,
        latência abaixo de noventa segundos. Só violações de nível erro reprovam a campanha.
        E cada defeito sistêmico achado vira uma invariante nova.
    """, B("Exemplos de invariantes",
           "vitality.consistency e wound.capacity: error",
           "economy: ouro sem negativo, único sem duplicata",
           "memory.summary_bounds e confirmed_without_source",
           "narrative.meta_leak e false_player_death: error",
           "combat.zombie com idle_turns 5 ou mais: error",
           "performance: warning acima de 45 s, error acima de 90 s")),

    sc("Cenários dirigidos e relatórios", """
        Simulações aleatórias às vezes demoram a cair no caso que interessa. Por isso
        existem cenários dirigidos, com pré-condição, ação e oráculo fechados: um de
        recrutamento, com uma personagem específica, e um de comércio, com duzentas moedas.
        Cada campanha grava uma linha JSON por turno e um resumo. O relatório agrega rotas,
        violações, mortes, classes e custo, e o transcrito mostra ação e narração lado a
        lado, para julgar a prosa à mão.
    """, B("O que o harness produz",
           "Cenários recrutamento e comércio, fora do --all",
           "JSONL por turno: rota, latência por nó, violações, LLM",
           "Resumo: % combate, funil de quests, mortes, Entropia",
           "report: Markdown com baseline opcional",
           "transcript: ação e narração turno a turno")),

    sc("Modo real, com freio", """
        O modo real tem freio. Há teto de pedidos e de
        custo por campanha, um vigia que aborta turnos que passam do prazo absoluto, inclusive
        depois de o notebook suspender, e uma regra de falhar fechado: se um grupo de
        tentativas termina sem nenhum sucesso, a matriz para. Sem isso, a resiliência do
        produto mascarava um provedor morto e produzia uma linha de base falsa.
    """, CO("warn", "Fail-closed no playtest real", "Tentativas são agrupadas por invoke; o primeiro grupo sem sucesso aborta a matriz e nenhum par seguinte começa. Nasceu das matrizes A0 e A1, que mediram fallback em vez do modelo.")),

    sc("Preflight, presets e trava", """
        Antes de gastar dinheiro numa matriz, três salvaguardas. Um preflight real faz uma
        chamada estruturada em cada classe de modelo e aborta se algo falhar. Presets de
        rotas isolam o experimento: o preset pago usa só o DeepSeek, sem misturar provedor
        nem mock, com um tempo limite maior só para o teste. E uma trava de arquivo impede
        duas matrizes ao mesmo tempo, depois que um processo órfão competiu por cota e
        contaminou uma medição.
    """, F("Antes de uma matriz real",
           ("Preflight", "Chamada estruturada em CLASSIFY, FAST, SMART"),
           ("Preset", "deepseek-paid: um provider, sem mock"),
           ("Tetos", "Requests e custo por campanha"),
           ("Trava", "Lock atômico com PID e host"),
           ("Manifesto", "Dono e heartbeat; órfão vira aborted"))),

    sc("A matriz pareada", """
        O experimento mais caro é a matriz pareada: dez campanhas de duzentos turnos, cada
        uma com perfil, classe, nível inicial e semente fixos. A matriz A mede a linha de
        base. Seguem diagnóstico, especificações e correções. A matriz B repete exatamente os
        mesmos pares. O resultado mais forte do projeto: de doze violações de erro na A para
        zero na B, em quase dois mil turnos reais.
    """, CMP("Matriz A versus matriz B",
             "Matriz A (agosto)", ["2.000 turnos reais", "Zero erro de turno", "12 violações error",
                                   "193 warnings", "Custo estimado US$ 1,46"],
             "Matriz B (setembro)", ["1.951 de 2.000 turnos", "Zero erro de turno",
                                     "Zero violações error", "Par 10 parou por saldo (402)",
                                     "Custo estimado US$ 1,18"])),

    sc("Evals com régua protegida", """
        A plataforma de evals mede qualidade com datasets travados por hash e oráculos
        estruturados. A régua é protegida: quem otimiza o produto não pode mexer em avaliador,
        esperado, dataset ou linha de base na mesma tarefa. Mudanças na régua exigem aprovação
        humana no C I. Um juiz feito de IA nunca bloqueia. E o conjunto de teste verdadeiro
        fica num repositório privado separado.
    """, TB("Suítes de eval determinísticas",
            ["Suíte", "Casos", "Mede"],
            [["Routing e ações", "25", "Rota, alvo, matriz de confusão"],
             ["Estado e regras", "12", "Transições de projeção"],
             ["Memória e contexto", "27", "Recall, MRR, vazamento, orçamento"],
             ["Narrativa e NPC", "27", "Claims, identidade, segredo"],
             ["Frontend", "16", "Jornadas F01 a F16 com axe"]])),

    sc("A régua travada por hash", """
        A régua tem um cadeado. Um arquivo de bloqueio guarda o hash de cada dataset, de
        cada arquivo do avaliador e do registro de métricas. Uma verificação falha fechada
        se qualquer hash divergir, e uma lista de caminhos protegidos diz o que tarefas de
        otimização não podem tocar. Um incidente recente mostrou a sutileza: em checkout
        limpo, quebras de linha diferentes mudavam os hashes. A correção fixou o formato de
        fim de linha e tornou a linha de base antiga incomparável.
    """, F("Governança da régua",
           ("Lock", "SHA-256 de datasets, avaliadores e registry"),
           ("Check", "Qualquer divergência falha fechado"),
           ("Caminhos protegidos", "Otimização não toca na régua"),
           ("CI", "Mudança na régua exige aprovação humana"),
           ("Incidente LF/CRLF", ".gitattributes fixa LF; relock canônico"),
           ("Consequência", "Baseline v1 histórica e incompatível"))),

    sc("Contratos reais e linha de base", """
        Duas medições completam o quadro. Os contratos reais, fora da suíte padrão,
        conferem o formato das respostas de modelos de verdade: nove passaram no Gemini na
        primeira rodada, e hoje um workflow manual os roda com teto duro de vinte pedidos e
        vinte centavos de dólar. E a linha de base versão um registrou oitenta e seis casos
        determinísticos mais as dezesseis jornadas, todas verdes, sem inventar metas e sem
        provedor pago.
    """, S("Medições de referência",
           ("9", "contratos LLM reais no Gemini"),
           ("20 req", "teto do contrato real manual"),
           ("US$ 0,20", "teto de custo desse workflow"),
           ("86", "casos determinísticos da baseline v1"),
           ("16", "jornadas F01 a F16 na baseline"))),

    sc("O índice do projeto", """
        Uma curiosidade honesta. O projeto construiu um índice do próprio código: um grafo com
        cinco mil e quinhentos nós, gerado da árvore sintática, para ajudar agentes de
        programação a navegar. Depois fez um experimento A B selado, com a resposta
        criptografada antes. Resultado: mesma precisão, mas mais chamadas, mais bytes e mais
        tempo. A decisão foi retirar o índice do fluxo padrão.
    """, TB("Benchmark do Project Index (v6)",
            ["Métrica", "Sem índice", "Com índice"],
            [["Localização correta", "16 de 16", "16 de 16"],
             ["Chamadas medianas", "5", "8"],
             ["Bytes lidos medianos", "24.676", "30.999"],
             ["Tempo mediano", "38,9 s", "58,3 s"],
             ["Vitórias de custo", "n/a", "0 de 8"]])),

    sc("Os workflows de integração contínua", """
        Tudo isso roda também na integração contínua, em cinco workflows. O de validação
        roda Ruff, o lint de conteúdo, a suíte e o build do frontend em todo push e pull
        request. O de auditoria sobe o Supabase local e testa infraestrutura e navegador
        reais. O de evals classifica o que mudou e roda só o necessário. Dois são manuais e
        protegidos: provedor real e holdout privado, e o smoke de pós-deploy, que só lê e
        confere a versão publicada.
    """, TB("Workflows do GitHub Actions",
            ["Workflow", "Quando", "O que faz"],
            [["validate", "push e PR", "Ruff, conteúdo, pytest, build web"],
             ["audit-local", "push, PR e manual", "Supabase local, infra e browser"],
             ["eval-gates", "push, PR e manual", "Evals seletivos; régua com aprovação"],
             ["eval-protected", "manual", "Provider real curto e holdout"],
             ["post-deploy-smoke", "manual", "Read-only; confere o SHA"]])),

    sc("Recapitulando qualidade", """
        Recapitulando. Uma suíte offline de quase mil e novecentos testes como portão. Um
        harness com catorze perfis e invariantes que crescem a cada defeito. Modo real com
        tetos e falha fechada. Matrizes pareadas que mostraram doze erros virarem zero.
        Evals com régua protegida e juiz de IA sem poder de veto. E a coragem de medir e
        descartar uma ferramenta que não ajudava.
    """, CO("key", "Recapitulação", "Suíte offline como portão; playtest com 14 perfis e invariantes; real com tetos e fail-closed; matriz A para B: 12 erros para 0; evals com régua protegida; Project Index medido e retirado do fluxo.")),
]))

# ---------------------------------------------------------------- c18
CHAPTERS.append(ch("Processo spec-driven e a história do projeto", "#6B4E8C", [
    sc("Nada sem especificação", """
        Por trás do código existe um método. Toda funcionalidade nova começa como uma
        especificação escrita, revisada e aprovada antes de qualquer linha de código. Neste
        capítulo vemos esse processo, como ele numerou quase duzentas especificações, e a
        história do projeto, do primeiro motor em dezembro de dois mil e vinte e cinco até
        hoje.
    """, T("Processo e história", "Specs, revisão independente e uma linha do tempo")),

    sc("O ciclo de uma spec", """
        O ciclo tem cinco passos. Copiar um modelo e escrever a spec como rascunho. O usuário
        revisa e ela vira aprovada. A implementação segue o plano, com testes primeiro, e
        qualquer desvio atualiza a spec no mesmo commit. Para concluir, todos os critérios de
        aceite marcados, suíte verde e um teste com modelo real. O roadmap só resume e aponta
        para a spec.
    """, F("Ciclo de vida de uma spec",
           ("draft", "Copiada do TEMPLATE e escrita"),
           ("approved", "Revisada e aprovada pelo usuário"),
           ("Implementação", "Testes primeiro, desvios na própria spec"),
           ("Aceite", "Critérios marcados, pytest verde, smoke real"),
           ("done", "ROADMAP e ESTADO_ATUAL atualizados"))),

    sc("IDs, índice e revisores", """
        Uma spec fez a normalização histórica: as cento e sessenta e duas specs antigas
        ganharam identificadores estáveis pela ordem de criação no Git, e um índice
        reproduzível registra status, commits e dependências. Hoje são cento e noventa e oito.
        O processo também separa quem executa de quem revisa: modelos diferentes por
        complexidade e um revisor independente que não pode autoaprovar.
    """, S("O acervo de specs",
           ("198", "specs com ID estável"),
           ("174", "done"),
           ("22", "approved, pacote v5 de produto"),
           ("1", "draft: certificação cloud"),
           ("1", "review-pending: integridade LF e CRLF"))),

    sc("Executor e revisor", """
        O processo atual também escolhe quem faz o quê. A regra é usar o menor modelo
        suficiente. Tarefas de inventário e relatório vão para o nível mais simples;
        implementação delimitada, para o intermediário; mudanças que cruzam domínios,
        concorrência ou estado, para um revisor técnico mais forte; e questões conceituais
        de avaliação, para o mais capaz. Quem executa não aprova o próprio trabalho: sem o
        revisor certo, gera-se um pedido de revisão formal.
    """, TB("Roteamento de trabalho por modelo",
            ["Papel", "Quando usar"],
            [["Luna", "Inventário, transformações, relatórios"],
             ["Terra", "Implementação delimitada"],
             ["Sol", "Cross-domain, concorrência, revisão"],
             ["Astra", "Checkpoints conceituais e evaluators"],
             ["Sem revisor mínimo", "MODEL_HANDOFF_REQUIRED, sem autoaprovar"]])),

    sc("Rituais e autoria", """
        Dois rituais mantêm o projeto saudável. Durante o trabalho, um comando roda os testes
        mostrando só falhas, para economizar contexto. No fim de toda tarefa, outro roda a
        suíte completa, atualiza o estado atual e o roadmap, o status da spec e faz o commit.
        Para conteúdo, um guia de autoria define templates, curadoria e o lint que bloqueia
        a reindexação se houver erro.
    """, CMP("Rituais do projeto",
             "Durante a tarefa", ["/qa: só falhas e contagem", "Spec aberta como guia",
                                  "Smoke real para structured output"],
             "Ao finalizar", ["/wrap-up: suíte completa verde", "Atualizar ESTADO_ATUAL e ROADMAP",
                              "Status da spec e reindex se mexeu em lore", "Commit"])),

    sc("Autoria de conteúdo", """
        Conteúdo também tem processo. O guia de autoria separa três camadas: a fonte em
        texto, que sempre sobrevive; o Codex gerado, que é refeito a cada migração; e a
        curadoria, que sobrevive. Para adicionar um personagem à mão, copia-se um modelo,
        marca-se como curado, coloca o segredo num documento paralelo oculto, registra a
        entidade, roda o lint e reindexa. O lint cobre cabeçalhos, referências,
        visibilidade, Cartas sem reskin, bestiário e arte.
    """, CMP("Camadas de conteúdo",
             "Não sobrevive à migração", ["Codex gerado em data/codex", "entities.json gerado"],
             "Sobrevive", ["Fonte lore_nova", "codex_overrides.yaml", "Arquivos curated: true",
                           "entities_extra, edges, components", "Templates em docs/guias/templates"])),

    sc("O ROADMAP, fases 0 a 5", """
        O roadmap organiza o projeto em fases. A zero trouxe mapa, relógio, viagem e
        descanso. A um, o frontend React. A dois e suas subfases criaram o mundo vivo:
        facções, Codex, eventos, regras e montador de contexto. A três deu clareza à
        campanha com crônica, conhecimento revelável e livro de missões. A quatro fez o
        núcleo de jogo: progressão, inventário, economia, comitiva e morte digna. A cinco
        criou o playtest agêntico.
    """, TB("Fases 0 a 5",
            ["Fase", "Entrega"],
            [["0", "Mapa, relógio, viagem, descanso"],
             ["1", "Frontend React, Vite e TypeScript"],
             ["2 a 2.8", "Facções, Codex, eventos, regras"],
             ["3", "Crônica, conhecimento, quests, estado"],
             ["4", "Progressão, itens, economia, morte"],
             ["5", "Harness, invariantes, telemetria"]])),

    sc("O ROADMAP, fases 6 a 11", """
        A fase seis trouxe conteúdo sistêmico: economia viva, itens únicos, migração de
        monstros, encontros e clima com efeito. A sete, autoria e validação. A oito, arte,
        curada e dinâmica. A nove, sprites e som, segue no backlog sem especificação. A dez
        endureceu o projeto localmente e, na sua parte b, construiu a infraestrutura local
        first; só a certificação em nuvem continua rascunho. A onze criou os contratos com
        modelos reais.
    """, TB("Fases 6 a 11",
            ["Fase", "Entrega", "Estado"],
            [["6", "Conteúdo sistêmico", "done"],
             ["7", "Autoria, lint e curadoria", "done"],
             ["8A e 8B", "Arte curada e arte dinâmica", "done local"],
             ["9", "Sprites e som", "backlog"],
             ["10 e 10b", "Hardening e infra local-first", "done; cloud draft"],
             ["11", "Contratos LLM reais", "done"]])),

    sc("A linha do tempo, parte um", """
        A história começa em dezembro de dois mil e vinte e cinco, com o motor mínimo: grafo,
        busca vetorial, saves, linha de comando e A P I. Em julho de dois mil e vinte e seis
        vieram o mundo vivo, com Codex, eventos e regras, a crônica, a progressão, a
        economia, o playtest agêntico e o roteamento multi provedor.
    """, TB("Linha do tempo: das origens a julho",
            ["Quando", "Marco"],
            [["Dez 2025 a jun 2026", "MVP: grafo, RAG, saves, CLI, API, React"],
             ["2 e 3 jul", "Mundo vivo: Codex, eventos e regras"],
             ["4 a 6 jul", "Progressão, playtest, multi-provider"],
             ["13 a 18 jul", "SSE, DeepSeek primário, criação imersiva"],
             ["19 a 21 jul", "5 Posturas, checkpoints de morte"],
             ["23 jul a 2 ago", "Épico do combate v4 com Cartas"]])),

    sc("A linha do tempo, parte dois", """
        Agosto foi de endurecimento: laboratório de combate, persistência e streaming,
        arte curada, quatro ciclos de correção nascidos de playtests longos, toda a
        infraestrutura local first e a matriz A de dois mil turnos. Setembro trouxe a
        remediação, a matriz B e o plano de evals. E em outubro, o benchmark do índice, a
        correção de integridade e um pacote de specs para virar produto.
    """, TB("Linha do tempo: agosto a outubro",
            ["Quando", "Marco"],
            [["3 a 12 ago", "Laboratório, hardening, arte curada"],
             ["13 a 16 ago", "Quatro ciclos de remediação de longrun"],
             ["17 a 20 ago", "Fase 10b local, nível 20, arte dinâmica"],
             ["20 a 27 ago", "Matriz A: 2.000 turnos reais"],
             ["17 a 28 set", "Remediação, IDs de spec, matriz B"],
             ["29 set a 2 out", "Evals, benchmark do índice, pacote v5"]])),

    sc("Playtests que mudaram o projeto", """
        Alguns playtests longos viraram marcos. Em julho, três campanhas de cem turnos
        acharam sete defeitos, entre eles combate zumbi e segredo vazando por um beat, e
        levaram o DeepSeek a primário e a Jina aos embeddings. Em agosto, o jogador normal
        expôs uma fuga impossível e memória de morte que sobrevivia ao checkpoint. Outro
        achou checkpoints gravados em combate, prendendo o herói num ciclo de mortes. E as
        matrizes A e B fecharam o ciclo.
    """, TB("Playtests marcantes",
            ["Quando", "Achado principal", "Resultado"],
            [["14 jul", "Combate zumbi, segredo no beat", "8 specs; DeepSeek; Jina"],
             ["12 ago", "Fuga impossível, morte no FAISS", "Perfil normal; 6 fixes"],
             ["12 ago v2", "Turno de 2.256 s após suspensão", "Watchdog absoluto"],
             ["13 ago", "Checkpoint em combate", "Checkpoint seguro"],
             ["20 ago", "A0 e A1 mediram só fallback", "Regra fail-closed"],
             ["27 ago e 28 set", "Matriz A, depois B", "12 errors para 0"]])),

    sc("O padrão que se repete", """
        Um padrão aparece. Cada playtest longo gera especificações. Cada
        especificação gera testes curtos ou invariantes. A matriz seguinte valida. E várias
        vezes a estabilidade formal, com zero violações, escondeu defeitos que só a leitura
        dos transcritos e métricas novas revelaram. Qualidade, aqui, é um ciclo, não um
        estado.
    """, CO("key", "O ciclo de melhoria", "Playtest longo gera specs; specs geram testes e invariantes; a matriz seguinte valida. Zero violações já esconderam defeitos: ler transcritos e criar métricas novas faz parte do método.")),
]))

# ---------------------------------------------------------------- c19
CHAPTERS.append(ch("Estado atual, arestas e encerramento", "#7A4E2D", [
    sc("Uma seção honesta", """
         Nenhum sistema deste tamanho está acabado. Esta seção reúne observações da
        exploração do código: coisas que parecem desligadas, documentação defasada e limites
        conhecidos. São achados de leitura, alguns verificados e outros suspeitos, e servem
        como mapa para o próximo passo, não como veredicto.
    """, T("Estado atual e arestas", "Observações da exploração do código")),

    sc("Arestas da mecânica", """
        Na mecânica, alguns achados se destacam. Cartas de proteção e de bônus gravam
        condições que nenhum cálculo de ataque ou dano parece ler, então podem ser pagas sem
        alterar números. Armadura e escudo do jogador não são instanciados no jogo real. O
        ataque básico sem Carta dá três de dano fixo, ignorando a arma. E percepção, armadilhas
        e itens ainda usam dado de vinte.
    """, B("Achados de mecânica",
           "Buffs de Carta (protecao, buff_*, vantagem) sem consumidor aparente",
           "Armadura e escudo do jogador nunca instanciados em produção",
           "Ataque básico sem Carta = 3 fixo, ignora a arma equipada",
           "Detecção, armadilha e salvaguarda de item ainda em d20",
           "Fuga fixa Agilidade e não usa o Teste de Sorte",
           "Eventos do Abismo não são alimentados no fluxo real")),

    sc("Arestas do núcleo e da memória", """
        No núcleo, três campos do estado são declarados mas nunca escritos, e o tipo de
        mensagem no histórico acaba dependendo de um campo transitório. O modelo falso não
        tem construtor para a declaração de combate e funciona por acaso. Na memória, a busca
        devolve só dois trechos por índice, e o simulador do mundo grava fatos sem
        proveniência. Há também suspeitas, como uma dica de ausência que pode persistir.
    """, B("Achados do núcleo e da memória",
           "Campos active_plan_step, router_confidence, last_routed_intent nunca escritos",
           "MockLLM sem builder para PlayerMove: funciona por acaso",
           "Retrieval de no máximo 2 trechos por índice",
           "world_simulator grava memória sem proveniência",
           "Suspeita: npc_fallback_hint pode persistir entre turnos",
           "Replan por região acontece com um turno de atraso")),

    sc("Arestas de operação e documentação", """
        Na operação, não há arquivo de deploy do trabalhador em segundo plano, a auditoria de
        dependências e o varredor de segredos rodaram à mão e não no C I, e o alerta de
        backup não é alimentado automaticamente. O custo de modelo é estimado, não medido. A
        nuvem nunca foi certificada. E a documentação tem defasagens, como o número de perfis
        e o modelo de embeddings citados.
    """, B("Achados de operação e docs",
           "Sem Dockerfile nem processo worker no Procfile",
           "pip-audit, npm audit e scanner de segredos fora do CI",
           "Métrica de idade do backup sem produtor automático",
           "Custo de LLM estimado por invoke, subconta o real",
           "Cloud (Railway e Supabase remoto) ainda em draft",
           "Docs defasadas: 13 perfis, embedding antigo, nível 10")),

    sc("Mais arestas, observadas no código", """
        Outros detalhes merecem nota. Cartas passivas não parecem ter consumidor no motor
        atual. Reações bem sucedidas dão só postura protegida, e o alvo mais próximo é
        escolhido por agilidade, não por posição. O bibliotecário depende de uma exceção
        para o guard funcionar. O tempo limite de doze segundos do DeepSeek pode empurrar
        gerações longas para o Groq. E no perfil legado, a idempotência só marca a ação
        depois do save, então uma queda no meio pode repetir o turno.
    """, B("Arestas adicionais",
           "Cartas passivas sem consumidor aparente no motor v4",
           "Reação bem-sucedida só concede postura protegida",
           "Alvo 'mais próximo' escolhido por Agilidade",
           "librarian sem isinstance: guard por AttributeError",
           "Timeout de 12 s do DeepSeek afeta gerações SMART",
           "Legacy: ação marcada só após o save bem-sucedido")),

    sc("Limitações conhecidas", """
        Algumas limitações são assumidas. O perfil legado serializa turnos por processo e
        não tem login, por desenho. A pasta de saves ainda mistura campanhas reais com
        fixtures antigas, e limpá-la exige seleção humana. Saves anteriores à migração de
        Virtudes ficam arquivados, somente leitura. A latência real fica em torno de quinze
        segundos na mediana, e a camada gratuita de provedores não sustenta playtests reais
        longos.
    """, B("Limitações declaradas",
           "Legacy: um processo, sem login, por desenho",
           "Saves históricos misturados a fixtures antigas",
           "Saves pré-v4 arquivados em modo leitura",
           "Latência real: p50 perto de 15 s, cauda maior",
           "Free tier não sustenta playtest real longo",
           "Cloud remota nunca medida")),

    sc("O pacote de produto em detalhe", """
        As vinte e duas especificações aprovadas do pacote cinco formam um plano de produto,
        em ordem. Primeiro, quatro medem decisões do roteador e do classificador. Depois vêm
        o contrato de runtime hospedado, a medição real de uso, preços em Estilhas com
        margem, carteira com reservas e painel de custo por conta. Em seguida, voz, cotação
        de imagens pagas, Stripe, segurança de conta e homologação no Supabase remoto e na
        Vercel. Por fim, Android, cobrança do Google Play, reembolsos, FinOps, beta pago
        fechado e publicação na loja.
    """, TB("SPEC-177 a 198, por tema",
            ["Tema", "Specs"],
            [["Decisão e roteamento (JEV)", "177 a 180"],
             ["Runtime hospedado e uso real", "181 e 182"],
             ["Preço, carteira e painel", "183 a 185"],
             ["Voz e imagens pagas", "186 a 188"],
             ["Stripe, conta e staging", "189 a 192"],
             ["Android e Google Play", "193, 194 e 198"],
             ["Reembolso, FinOps e beta", "195 a 197"]])),

    sc("Para onde vai", """
        O próximo horizonte está escrito em vinte e duas especificações aprovadas e ainda não
        iniciadas. Elas cobrem o salto de laboratório para produto: medição real de uso,
        carteira e preços, pagamentos, voz, aplicativo Android, publicação na loja e
        operação financeira. Antes disso, falta concluir a revisão de integridade e uma nova
        linha de base de avaliação. Sprites e som seguem no backlog.
    """, F("Próximos passos registrados",
           ("SPEC-176", "Aprovação humana, push e CI verde"),
           ("Nova baseline", "v1 ficou incompatível por hashes CRLF"),
           ("SPEC-177 a 198", "Medição de uso, carteira, pagamentos"),
           ("Mobile e voz", "Capacitor Android, voz web e mobile"),
           ("Cloud", "Railway e Supabase remoto com orçamento"),
           ("Fase 9", "Sprites e som, ainda sem spec"))),

    sc("Encerramento", """
        Chegamos ao fim da jornada. Vimos um jogo onde a IA identifica e narra, e o Python
        resolve; um grafo de onze nós; um mundo com eventos, segredos e memória que sabe
        quanto confiar em cada fato; um combate tático de Cartas; uma interface robusta; uma
        infraestrutura que nunca segura transação durante a IA; e um método em que cada
        defeito vira teste. Obrigado por atravessar Valoria conosco.
    """, CO("key", "Valoria, em uma frase", "Um RPG de texto onde a IA narra e o Python decide: grafo de agentes, mundo por eventos, memória com proveniência, combate determinístico e um processo em que cada defeito vira teste.")),
]))
