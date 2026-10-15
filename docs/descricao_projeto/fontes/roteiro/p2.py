from h import *

CHAPTERS = []

# ---------------------------------------------------------------- c06
CHAPTERS.append(ch("O mundo de Valoria: lore, Codex e grafo", "#B7791F", [
    sc("Um mundo antes do jogo", """
        Antes de existir um turno, existe um mundo. Valoria tem história em eras, raças,
        facções com objetivos reais e declarados, criaturas, itens, rumores e segredos que
        os personagens raramente sabem. Neste capítulo vemos como esse lore sai de arquivos
        de texto escritos por humanos e vira três coisas que o motor entende: um Codex, um
        grafo de entidades e um mapa.
    """, T("O mundo de Valoria", "Do texto bruto ao Codex, ao grafo e ao mapa")),

    sc("A fonte do lore", """
        A fonte é uma pasta com onze arquivos de texto, somando cerca de oitocentos
        quilobytes, todos com o título Codex Omnia. Há personagens importantes com motivações
        e segredos, o bestiário, uma linha do tempo da era zero à era sete, itens, locais,
        raças, facções, vida cotidiana, perspectivas conflitantes, rumores de confiabilidade
        variável e um arquivo só de segredos, de uso exclusivo do narrador.
    """, TB("Os onze arquivos de lore",
            ["Arquivo", "Tema", "Tamanho"],
            [["npcs", "Personagens, motivações e segredos", "185 KB"],
             ["creatures", "Fauna, assombrações, aberrações", "152 KB"],
             ["timeline_completa", "Da Era 0 à Era 7", "96 KB"],
             ["items e locations", "Materiais, armas, lugares", "142 KB"],
             ["races e factions", "Seis raças e as facções", "106 KB"],
             ["secrets", "Verdades só do narrador", "31 KB"],
             ["rumors e outros", "Rumores, cotidiano, visões", "84 KB"]])),

    sc("Do texto ao Codex", """
        Um script de migração lê esses textos, reconhece blocos de categoria e etiquetas e
        gera um Codex: quase setecentos documentos em Markdown, cada um com um cabeçalho que
        traz identificador, tipo, nome, etiquetas e visibilidade. A linha do tempo tem um
        parser próprio que divide por era e marca como ocultos os capítulos que revelariam
        as grandes verdades da trama.
    """, G("Pipeline de lore", "LR",
           [("src", "lore_nova (11 .txt)", "data"), ("mig", "Script de migração", "python"),
            ("ov", "Overrides de curadoria", "data"), ("cx", "Codex (699 .md)", "data"),
            ("ent", "entities.json (594)", "data"), ("idx", "Índice vetorial de lore", "data")],
           [("src", "mig"), ("ov", "mig", "aplica depois"), ("mig", "cx"), ("mig", "ent"), ("cx", "idx", "chunks 500/50")])),

    sc("Visibilidade", """
        A peça mais importante do cabeçalho é a visibilidade. Público significa que o
        narrador pode usar. Oculto significa que existe no mundo mas não deve aparecer na
        narração até ser descoberto. Secreto é a verdade profunda da trama. Hoje há
        seiscentos e trinta e nove documentos públicos, quarenta e um ocultos e dezenove
        secretos. O segredo de uma personagem pública mora num documento separado, oculto.
    """, S("Visibilidade no Codex",
           ("639", "documentos public"),
           ("41", "documentos hidden"),
           ("19", "documentos secret"),
           ("36", "arquivos curated, nunca sobrescritos"))),

    sc("Curadoria que sobrevive", """
        Há um problema clássico em conteúdo gerado: se você edita o resultado à mão, a
        próxima geração apaga sua edição. A solução aqui é um arquivo de overrides de
        curadoria, aplicado depois da geração, que pode trocar apelidos, acrescentar
        etiquetas, mudar a visibilidade ou anexar texto. Um caso real: um playtest mostrou
        o narrador vazando uma criatura secreta, e ela foi marcada como oculta por override.
    """, CO("info", "Curadoria migration-safe", "data/codex_overrides.yaml é aplicado depois de gerar o Codex: aliases, tags_extra, visibility, related_entities, append_body. Arquivos curated: true nunca são tocados. Id órfão é erro de lint.")),

    sc("O grafo de entidades", """
        Além do texto, o mundo tem estrutura. Um arquivo gerado lista quinhentas e noventa e
        quatro entidades: monstros, personagens, facções, artefatos, locais e raças, e
        outras oitenta e duas são curadas à mão num arquivo extra. Um
        conjunto curado à mão de cento e uma arestas diz quem está onde, quem opera em que
        região, quem lidera quem, quem é inimigo de quem, quem controla o quê e quem tem
        pacto com quem. Algumas dessas arestas são ocultas ou secretas.
    """, TB("Arestas curadas do grafo",
            ["Tipo", "Quantidade", "Exemplo de sentido"],
            [["located_in", "45", "personagem mora em um local"],
             ["operates_in", "24", "facção atua numa região"],
             ["leads", "21", "líder de uma facção"],
             ["enemy_of", "5", "rivalidade declarada"],
             ["controls", "4", "quem controla um local"],
             ["member_of / pact_with", "1 + 1", "filiação e o pacto secreto"]])),

    sc("Componentes", """
        Algumas entidades carregam componentes, que são dados mecânicos extras. O exemplo
        canônico é o de um líder político: se ele morrer, há um vácuo de poder. O componente
        guarda quanto a facção perde de estabilidade e qual rival pode ocupar o lugar. Esse
        arquivo de componentes não é tocado pela migração; ele é mesclado às entidades na
        hora de carregar.
    """, C("Um componente de vácuo de poder", "data/graph/components.json", "json", """
{
  "npc_valerius": {
    "power_vacuum_trigger": {
      "base_instability_delta": -50,
      "successor_id": null,
      "rival_faction_override": "mao_sombria"
    }
  }
}
""")),

    sc("O mapa", """
        O mapa tem trinta e cinco nós: trinta ao ar livre e cinco interiores, como uma
        taverna dentro de um anel da cidade. Cada nó tem região, coordenadas, perigo de um a
        quatro, etiquetas, conexões, uma semente de lore, etiquetas de forja e de economia,
        e às vezes tempos de viagem específicos. Dois locais escondem baús curados. O início
        padrão é Nova Arcádia, a região com mais nós.
    """, S("O mapa de Valoria",
           ("35", "nós: 30 ao ar livre e 5 interiores"),
           ("12", "regiões, de Nova Arcádia a Ophidia"),
           ("1 a 4", "escala de perigo por local"),
           ("2", "baús curados de tesouro"),
           ("13", "nós com tempos de viagem próprios"))),

    sc("Os demais dados do mundo", """
        Completam o mundo vários catálogos. Seis raças com traços mecânicos e doze regiões
        com bônus iniciais. Oitenta traços ocultos de personagens. O bestiário com cento e
        vinte e quatro criaturas. Dezenove facções ativas com objetivo, ritmo e uma
        ascensão autorada. Tabelas de clima por região e eventos globais. Companheiros,
        mercadores, tabelas de saque, armadilhas e o catálogo de arte.
    """, B("Catálogos estáticos",
           "origins: 6 raças com traços e 12 regiões com bônus",
           "traits: 80 traços ocultos de NPC, revelados com o tempo",
           "bestiary: 124 criaturas, de Lacaio a Nomeado",
           "factions: 19 facções com objetivo, ritmo e ascensão",
           "weather: cadeias por região e eventos globais",
           "merchants, loot_tables, traps, companions, visual_assets")),

    sc("Recapitulando o mundo", """
        Recapitulando. O lore nasce em onze textos editados por humanos. Um script gera o
        Codex com visibilidade por documento e um grafo de entidades. A curadoria vive em
        overrides que sobrevivem à regeneração. Arestas e componentes curados dão estrutura
        política ao mundo, e o mapa dá geografia, perigo e economia. 
    """, CO("key", "Recapitulação", "Texto fonte gera Codex e grafo; visibility separa público, oculto e secreto; overrides preservam a curadoria; arestas e componentes dão política; o mapa dá geografia, perigo e economia.")),
]))

# ---------------------------------------------------------------- c07
CHAPTERS.append(ch("RAG e embeddings: buscar antes de narrar", "#2F6F6A", [
    sc("Uma biblioteca com bibliotecário", """
        Nenhum modelo cabe o Codex inteiro no prompt, e nem deveria. A técnica de RAG
        funciona como um bibliotecário: antes de narrar, você descreve o que precisa, ele
        busca os trechos mais parecidos num índice e entrega só esses. Neste capítulo vemos
        os índices, os provedores de embeddings e uma regra de segurança que impede misturar
        vetores incompatíveis.
    """, T("RAG e embeddings", "Buscar o trecho certo antes de narrar")),

    sc("Quatro escopos de índice", """
        Existem quatro escopos de índice. O de lore global, gerado do Codex e imutável
        durante o jogo. O de regras, gerado de um arquivo de regras. O da sessão, um por
        jogo, escrito pelo arquivista durante a partida. E o de cada personagem, um índice
        por personagem dentro da sessão, com o que aquele personagem viveu com o jogador.
    """, TB("Os quatro escopos",
            ["Escopo", "Quem escreve", "Quando"],
            [["Lore global", "ingest_codex", "Offline, ao reindexar"],
             ["Regras global", "ingest_file de rules.txt", "Offline"],
             ["Sessão", "archivist, world_simulator", "Durante o jogo"],
             ["Por NPC", "npc_actor, retry do archivist", "A cada conversa"]])),

    sc("Do Codex aos vetores", """
        Para indexar o lore, cada documento é cortado em pedaços de quinhentos caracteres com
        sobreposição de cinquenta. Cada pedaço herda do cabeçalho o identificador, o tipo,
        o nome, as etiquetas e a visibilidade. Um modelo de embeddings transforma cada
        pedaço num vetor, e os vetores vão para um índice Faiss. O comando de reindexação
        roda o lint de conteúdo antes e aborta se houver erro.
    """, F("Indexação do lore",
           ("Lint de conteúdo", "Erro de frontmatter ou visibilidade aborta"),
           ("Carregar Codex", "699 documentos com metadados"),
           ("Fatiar", "Chunks de 500 com sobreposição de 50"),
           ("Embeddings", "Provider ativo, hoje Jina"),
           ("Salvar índice", "FAISS + embeddings_meta.json"))),

    sc("A cadeia de embeddings", """
        Os embeddings também têm uma cadeia de provedores: Jina primeiro, depois OpenAI,
        depois Ollama local e por último Gemini. A Jina virou primária depois que o Gemini
        ficou sem créditos e a busca vetorial morreu por erros de cota. O Ollama só conta se
        o endereço do servidor estiver explícito, porque ter a biblioteca instalada não
        significa que o serviço está de pé.
    """, B("EMBEDDING_ROUTES, em ordem",
           "Jina jina-embeddings-v3: primário, bom em português",
           "OpenAI text-embedding-3-small: exige chave",
           "Ollama bge-m3: só com OLLAMA_HOST explícito",
           "Gemini embedding: último recurso",
           "RPG_EMBEDDINGS força um provider específico")),

    sc("Índice pinado", """
         Vetores de provedores
        diferentes vivem em espaços diferentes; consultar um índice da Jina com um vetor do
        Gemini dá lixo. Por isso não existe fallback por pedido. Cada índice grava ao lado um
        arquivo dizendo qual provedor e modelo o gerou. Ao abrir, usa sempre aquele. Se
        aquele provedor não está disponível, o índice é desativado com um aviso.
    """, CO("warn", "Nunca misturar vetores", "Cada índice grava embeddings_meta.json com provider e modelo. A leitura usa o provider pinado, nunca o ativo. Provider indisponível desativa o índice com aviso: reindexe para trocar.")),

    sc("Filtro de visibilidade", """
        Na hora da busca, a visibilidade vira um filtro. Público vale zero, oculto vale um,
        secreto vale dois. E um valor desconhecido vale secreto: falha fechada, para um erro
        de digitação não vazar nada. Como o filtro roda depois da busca vetorial, pede-se
        seis candidatos e ficam os dois melhores permitidos. Todos os leitores de produção
        pedem só o público.
    """, EX("Uma busca no lore",
            ("Consulta", "Quem governa Nova Arcádia?"),
            ("Candidatos buscados", "6 vizinhos mais próximos"),
            ("Filtro", "visibilidade até public"),
            ("Desconhecido", "tratado como secret: descartado"),
            ("Devolvidos", "os 2 melhores permitidos"),
            ("Id de evidência", "entidade mais hash do chunk"))),

    sc("Um vetor, três leituras", """
        Um turno costuma precisar de três buscas: lore, memória da sessão e memória do
        personagem. Para não pagar três vezes, o motor gera um único vetor da consulta e lê
        os três índices em paralelo, numa pequena fila de tarefas. Mas só compartilha o
        vetor se os três índices estiverem pinados no mesmo provedor e dimensão. Se um
        leitor falha, o contexto fica degradado, e o turno segue.
    """, G("Aquisição concorrente de contexto", "LR",
           [("q", "Consulta do turno", "io"), ("e", "Um embedding", "llm"),
            ("lo", "Lore pública", "data"), ("se", "Memória da sessão", "data"),
            ("np", "Memória do NPC", "data"), ("pk", "Fontes de contexto", "python")],
           [("q", "e"), ("e", "lo"), ("e", "se"), ("e", "np"), ("lo", "pk"), ("se", "pk"), ("np", "pk")])),

    sc("No perfil Postgres: busca híbrida", """
        Tudo isso descreve o perfil local de arquivos. Nos perfis com banco, a memória
        vive no Postgres com a extensão P G vector, em vetores de mil e vinte e quatro
        dimensões. A busca é híbrida: une similaridade vetorial e busca textual, e se o
        serviço de embeddings estiver fora, cai só na busca textual. Um detalhe prático:
        a Jina gera mil e vinte e quatro dimensões e serve; o modelo pequeno da OpenAI gera
        mil quinhentas e trinta e seis e não é compatível com esse perfil.
    """, CMP("FAISS versus pgvector",
             "Perfil legacy", ["Índices FAISS em disco", "Escrita direta pelo arquivista",
                               "Busca só vetorial, 2 resultados", "Usado por CLI, testes e playtest"],
             "Perfis com banco", ["memory_documents com vector(1024)", "Escrita por outbox no commit",
                                  "Vetorial mais texto, com fallback", "Visibilidade e dono filtrados"])),

    sc("Recapitulando o RAG", """
        Recapitulando. Quatro escopos de índice: lore, regras, sessão e personagem. Uma
        cadeia de provedores de embeddings com Jina na frente. Cada índice pinado ao provedor
        que o gerou, sem misturar vetores. Visibilidade como filtro que falha fechado. E uma
        consulta, um vetor, três leituras em paralelo. Agora, como o mundo muda de forma
        controlada.
    """, B("O que levar do RAG",
           "Lore e regras são globais e imutáveis em jogo",
           "Sessão e NPC são memórias vivas, escritas no turno",
           "Índice pinado: nunca consultar com vetor alheio",
           "Visibilidade desconhecida conta como secreta",
           "Um embedding por consulta, leituras em paralelo")),
]))

# ---------------------------------------------------------------- c08
CHAPTERS.append(ch("Event sourcing: o mundo que muda", "#8C3B5A", [
    sc("O livro de registros", """
        Um mundo vivo precisa mudar: personagens morrem, cidades trocam de dono, rotas são
        bloqueadas. Mas o lore base é imutável. A solução é um padrão chamado event sourcing,
        algo como o livro de registros de um cartório. Nada é apagado: cada mudança é um
        evento anotado. O estado atual do mundo é derivado da leitura desse livro.
    """, T("Event sourcing", "Um livro de eventos e uma projeção derivada")),

    sc("Quatro campos", """
        O estado do jogo carrega quatro campos para isso. O log de eventos, onde só se
        acrescenta. A projeção do mundo, que é o resultado derivado. As propostas pendentes,
        ainda não validadas. E o registro de rejeições, para auditoria. Quem pode escrever no
        log? Exatamente uma função, que roda no arquivista em todo turno.
    """, G("Os campos do mundo estruturado", "LR",
           [("pd", "pending_world_events", "data"), ("pp", "process_pending_events", "python"),
            ("lg", "event_log (append-only)", "data"), ("pj", "world_projection", "data"),
            ("rj", "event_rejections", "neutral")],
           [("pd", "pp"), ("pp", "lg", "aceita"), ("pp", "pj", "aplica"), ("pp", "rj", "recusa")])),

    sc("Tipos de evento", """
        Há quinze tipos de evento. Alguns a IA pode propor: personagem morto, segredo
        revelado, controle de local alterado, missão concluída, relação entre facções,
        reputação, rota bloqueada ou liberada. Outros só o motor emite: subir de nível,
        escolher subclasse, morrer, cair, reivindicar um item único. O truque é estrutural:
        o esquema de proposta da IA nem tem o campo de origem que esses tipos exigem.
    """, C("A proposta não tem campo de origem", "services/structured_outputs.py", "python", """
class ProposedWorldEvent(BaseModel):
    type: EventType
    actor_id: str = Field(default="player")
    target_id: str = Field(description="id EXATO de entities.json")
    detail: str = Field(default="")
    payload: Dict = Field(default_factory=dict)
    # sem campo source: level_up, player_died e
    # unique_item_* exigem source do motor
""")),

    sc("Validadores", """
        Cada proposta passa por um validador do seu tipo. Para declarar um personagem morto,
        o alvo precisa existir no grafo, ser do tipo personagem e estar vivo. Para revelar um
        segredo, precisa existir uma aresta oculta ou secreta ligada ao alvo, ainda não
        revelada. Para bloquear uma rota, a conexão precisa existir no mapa. Duplicatas no
        mesmo turno são barradas, e um dicionário malformado nunca derruba o turno.
    """, TB("Exemplos de validadores",
            ["Tipo", "Exige"],
            [["npc_killed", "Existe, é NPC e ainda está vivo"],
             ["secret_revealed", "Aresta hidden/secret ligada ao alvo"],
             ["location_control_changed", "Alvo é um local"],
             ["route_blocked", "Conexão direta real, ainda livre"],
             ["level_up / player_died", "source do motor; IA é recusada"],
             ["Qualquer tipo", "Sem duplicata no mesmo turno"]])),

    sc("Aplicação pura", """
        Uma proposta aceita vira um evento com identificador, turno e origem, e é aplicada à
        projeção por uma função pura, que copia antes de mudar. Personagem morto vira vivo
        falso. Segredo revelado entra nos fatos revelados. Troca de controle desativa a
        aresta antiga e cria uma dinâmica nova. O lore base nunca é tocado: o estado efetivo
        é base menos desativadas mais dinâmicas.
    """, CO("info", "Resolver do grafo", "Arestas efetivas = base - disabled_edges + dynamic_edges, com filtro de visibilidade. O controlador atual de um local é a aresta dinâmica mais recente; senão, a da base.")),

    sc("O motor de regras", """
        Eventos têm consequências. Um motor de regras declarativas, com seis regras em JSON,
        reage a cada evento aplicado. A mais dramática: quando morre um líder com o
        componente de vácuo de poder, a facção perde estabilidade e cada local que ele
        controlava muda de dono. Outras regras ajustam estabilidade, marcam missões e, se um
        porto cai em mãos hostis, bloqueiam suas rotas.
    """, B("As seis regras do mundo",
           "Morte de líder com vácuo de poder: estabilidade cai e locais mudam de dono",
           "Morte de NPC comum: apenas marca como morto",
           "Troca de controle: novo controlador ganha +5 de estabilidade",
           "Segredo revelado: estabilidade -10",
           "Quest concluída: marca a entidade",
           "Porto tomado por hostil: emite route_blocked nas conexões")),

    sc("Cascata com freio", """
        Regras podem emitir eventos, que disparam regras, que emitem eventos. Sem freio, isso
        vira laço infinito. Por isso a cascata para na profundidade dois. E as regras não
        executam código arbitrário: valores dinâmicos só podem vir de um resolvedor de
        caminhos com lista branca. Qualquer coisa fora disso faz a regra ser ignorada com um
        log, sem quebrar o turno.
    """, G("Cascata: a morte de Valerius", "TB",
           [("k", "npc_killed: Valerius", "data"), ("r1", "rule_faction_leader_death", "python"),
            ("st", "Legião: -50 estabilidade", "data"), ("cc", "location_control_changed", "data"),
            ("r2", "control_change_ripple", "python"), ("r3", "hostile_port_blockade", "python"),
            ("rb", "route_blocked (se porto)", "data")],
           [("k", "r1", "depth 0"), ("r1", "st"), ("r1", "cc"), ("cc", "r2", "depth 1"),
            ("cc", "r3", "depth 1"), ("r3", "rb")])),

    sc("Pré validação no narrador", """
        Lembra da quarentena atômica? Ela usa uma pré validação somente leitura. Antes de
        mostrar a narração, o narrador simula o processamento das propostas sobre cópias,
        incluindo a cascata, de modo que a proposta seguinte já vê o efeito da anterior. Se
        algo é inválido, a prosa que afirmava a mudança é descartada antes de chegar ao
        jogador.
    """, F("Do narrador ao log",
           ("Narrador propõe", "proposed_events no StoryUpdate"),
           ("Pré-validação", "Sobre cópias, com cascata, sem gravar"),
           ("Inválida?", "Quarentena do payload e prosa determinística"),
           ("Válida", "Entra em pending_world_events"),
           ("Arquivista", "process_pending_events grava o log"),
           ("Crônica", "Milestone de evento aplicado"))),

    sc("Missões verificáveis", """
        O livro de missões segue a mesma filosofia. A IA propõe uma missão; o Python confere
        se os locais e entidades existem. O progresso é verificável: chegar ao local grava
        um marco, e duas investigações distintas no alvo permitem concluir. A recompensa é idempotente:
        X P mais vinte de ouro. Se o personagem que deu a missão morre, ela falha.
    """, F("Ciclo de uma side quest",
           ("created", "Proposta pela IA e validada em Python"),
           ("location_reached", "Gravado uma vez ao chegar"),
           ("investigation", "Ações distintas no alvo"),
           ("completion_ready", "Duas investigações cumpridas"),
           ("completed", "Evento com source system; XP e 20 de ouro"),
           ("failed", "NPC de origem morto: quest órfã falha"))),

    sc("O que o jogador enxerga do mundo", """
        A projeção guarda números internos, mas o jogador vê uma versão filtrada. Visões
        próprias traduzem a estabilidade de uma facção num rótulo qualitativo, sem expor o
        número. Mostram trocas de controle só nos lugares que o jogador já visitou,
        ameaças ativas e quem controla cada local, sem arestas ocultas. O mapa da interface
        usa exatamente essas visões para desenhar selos de facção, ameaça e rotas
        bloqueadas.
    """, B("Visões do mundo para o jogador",
           "Reputação por facção que o jogador conhece",
           "Estabilidade como rótulo, nunca o número interno",
           "Trocas de controle só em locais já visitados",
           "Ameaças ativas e controladores visíveis",
           "Rotas bloqueadas e perigo efetivo no mapa")),

    sc("Recapitulando os eventos", """
        Recapitulando. O mundo muda por eventos anotados num livro que só cresce. A IA
        propõe; validadores por tipo aceitam ou recusam; tipos sensíveis só o motor emite. A
        aplicação é pura e o lore base nunca muda. Seis regras declarativas criam
        consequências em cascata, com freio na profundidade dois. E missões progridem por
        marcos verificáveis.
    """, CO("key", "Recapitulação", "event_log append-only, projeção derivada, validadores por tipo e origem estrutural. Regras declarativas em cascata limitada a profundidade 2. Base imutável: efetivo = base - desativadas + dinâmicas.")),
]))

# ---------------------------------------------------------------- c09
CHAPTERS.append(ch("Memória, segredos, contexto, NPCs e crônica", "#556B2F", [
    sc("Lembrar sem inventar", """
        Memória é o problema central de um mestre de IA. Lembrar pouco quebra a continuidade;
        lembrar errado é pior, porque transforma um boato em fato. Este capítulo mostra as
        cinco camadas de memória, a proveniência que decide quanto confiar em cada fato, a
        proteção de segredos, o montador de contexto com orçamento, os personagens em três
        camadas e a crônica.
    """, T("Memória e conhecimento", "Lembrar sem inventar, saber sem vazar")),

    sc("Cinco camadas", """
        As camadas são cinco. O resumo narrativo de curto prazo, limitado a mil e duzentos
        caracteres e reescrito pelo arquivista. O livro de fatos dentro do save, que existe
        mesmo se a busca vetorial estiver fora. A memória vetorial da sessão. A memória
        vetorial de cada personagem. E o log de eventos, que é a verdade do mundo; a memória
        só espelha.
    """, TB("As cinco camadas de memória",
            ["Camada", "Onde vive", "Papel"],
            [["Resumo curto", "narrative_summary", "Até 1.200 caracteres"],
             ["Ledger de fatos", "memory_facts no save", "Até 500, com proveniência"],
             ["Vetorial da sessão", "FAISS ou pgvector", "Busca semântica de fatos"],
             ["Vetorial por NPC", "Um índice por NPC", "O que o NPC viveu"],
             ["Eventos canônicos", "event_log", "Fonte da verdade"]])),

    sc("Proveniência", """
        Cada fato tem uma proveniência, e a confiança é derivada dela por uma tabela fechada.
        Um evento canônico do motor é confirmado. Uma observação do jogador ou a fala de um
        personagem é um relato. Uma inferência livre da IA, ou um fato antigo sem metadado, é
        especulativa. O ponto principal: a IA não escolhe a confiança. Qualquer tentativa de
        elevá-la é sobrescrita.
    """, C("Confiança derivada da proveniência", "services/memory_provenance.py", "python", """
_CONFIDENCE_BY_PROVENANCE = {
    "canonical_event": "confirmed",
    "player_observation": "reported",
    "npc_claim": "reported",
    "inference": "speculative",
    "legacy_unverified": "speculative",
}
""")),

    sc("Validar antes de gravar", """
        Antes de gravar, cada fato é validado e a política é falhar fechado. É rejeitado se
        contradiz a localização atual, o delta de recompensa ou a vida do jogador. Se contém
        um segredo não revelado. Se confunde cair com morrer.  Se afirma posse de um item ausente. Se troca a espécie de um
        personagem. Ou se diz confirmado sem uma fonte aplicável.
    """, B("Motivos de rejeição de um fato",
           "Contradiz localização, recompensa ou a vida do jogador",
           "Contém segredo ainda não revelado",
           "Trata queda como morte",
           "Região e local incompatíveis com o mapa canônico",
           "Posse de item ausente ou NPC com espécie trocada",
           "Confirmado sem fonte aplicável no estado")),

    sc("Repetir não promove", """
        Fatos idênticos são mesclados. Se o mesmo texto reaparece com confiança maior, ele é
        promovido, de especulativo para relato para confirmado, e a promoção é contada. Mas
        repetição por si só nunca promove. Um boato repetido dez vezes continua boato. Na
        volta ao prompt, cada fato aparece com um rótulo, como confirmado, relato ou não
        verificado, para o modelo saber o peso.
    """, EX("Fatos formatados no prompt",
            ("Confirmado", "[CONFIRMADO | canonical_event | turno 7] ..."),
            ("Relato", "[RELATO | npc_claim | fonte npc:velha_magda]"),
            ("Especulativo", "[RESUMO NARRATIVO | speculative] ..."),
            ("Legado", "[NÃO VERIFICADO | legacy_unverified] ..."),
            ("Regra", "Repetir texto não promove confiança"))),

    sc("O arquivista e a memória", """
        O arquivista grava com cuidado. Primeiro tenta de novo as gravações
        que falharam antes, e só avança o livro depois que a escrita física deu certo. Os
        fatos livres da IA viram inferências. Em turno de combate, ou quando algo foi
        rejeitado, os fatos livres são suprimidos: a prosa não pode reintroduzir um fato
        recusado. E o resumo é cortado onde contradiz mapa, inventário ou aparência.
    """, F("Política de gravação do archivist",
           ("Retry primeiro", "Fatos e memória de NPC pendentes"),
           ("Escrita física", "Ledger só avança após gravar"),
           ("Fatos livres", "Viram inference, especulativos"),
           ("Turno sensível", "Combate ou rejeição: suprime fatos livres"),
           ("Grounding", "Corta frases contra mapa, inventário, aparência"),
           ("Crônica", "Conflito canônico e prosa permitida"))),

    sc("Segredos em três camadas", """
        Segredos são protegidos em três camadas independentes. No índice, documentos ocultos
        e secretos nunca saem das buscas do narrador. Por assinatura de texto, frases da
        verdade oculta de quatro grandes segredos são detectadas e removidas, a menos que o
        jogador já as conheça. E por evento, um segredo só passa a valer quando uma revelação
        válida, ligada a uma aresta oculta, é aceita.
    """, G("Defesa em profundidade contra vazamento", "TB",
           [("q", "Texto candidato", "io"), ("ix", "Filtro de visibilidade", "python"),
            ("sg", "Assinaturas de segredo", "python"), ("ev", "Evento secret_revealed", "data"),
            ("ok", "Pode aparecer ao jogador", "neutral")],
           [("q", "ix", "camada 1"), ("ix", "sg", "camada 2"), ("ev", "sg", "libera"), ("sg", "ok")])),

    sc("O caso da Velha Magda", """
        Um caso real mostra a sutileza. Num playtest, a Velha Magda contou ao jogador sobre o
        pacto secreto de Valerius. Quando a narração repetiu o fato, o detector acusou
        vazamento, mas o jogador já sabia. A correção foi incluir
        no corpo do que é conhecido o resumo narrativo e os segredos conhecidos pelo
        jogador. O planejador de campanha, por sua vez, vê segredos, mas seus beats são
        higienizados.
    """, CO("info", "Segredo já conhecido não é vazamento", "O corpus revelado inclui eventos secret_revealed, fatos da projeção, o resumo narrativo e player.known_secrets. Se a Magda contou o pacto, repetir não é vazamento.")),

    sc("O montador de contexto", """
        Tudo isso precisa caber no prompt. O montador de contexto tem um orçamento de três mil
        e quinhentos tokens, dividido em seis seções: estado atual, local ativo, relações,
        entidades, lore e memória da sessão, cada uma com sua cota. As seções são
        preenchidas em ordem, com os fatos de maior nota primeiro. A sobra de uma seção
        rola para a próxima, o teto global admite cinco por cento a mais, e o que é
        cortado fica anotado com o motivo, como visibilidade ou orçamento.
    """, TB("Orçamento de contexto: 3.500 tokens",
            ["Seção", "Cota"],
            [["current_state", "25%"],
             ["active_location", "20%"],
             ["relations", "15%"],
             ["entities", "15%"],
             ["lore", "15%"],
             ["session_memory", "10% (sobra rola adiante)"]])),

    sc("A nota de cada fato", """
        Como o montador decide o que entra? Cada fato candidato recebe uma nota de zero a
        um, sem nenhum embedding: trinta e cinco por cento pela relevância às palavras da
        consulta, vinte e cinco por estar no mesmo local, vinte por envolver entidades em
        cena, dez pelo impacto do tipo de evento e dez pela recência. Uma morte ou troca
        de controle tem impacto máximo; um segredo revelado ou rota bloqueada, alto. Os
        tokens são estimados como caracteres divididos por quatro.
    """, S("Pesos da nota de relevância",
           ("0,35", "termos da consulta"),
           ("0,25", "mesmo local"),
           ("0,20", "entidades em cena"),
           ("0,10", "impacto do tipo de evento"),
           ("0,10", "recência, zerada em 50 turnos"))),

    sc("O estado atual vence", """
        O bloco de estado do mundo entra no prompt com uma frase explícita: se o estado atual
        contradisser a lore ou os fatos, o estado atual vence. Assim, se o comandante Thrace
        foi morto no turno quinze, o motor renderiza esse evento com impacto máximo, e a lore
        antiga que o descreve vivo perde. Só o planejador de campanha enxerga arestas
        ocultas e secretas nesse montador.
    """, EX("Um evento chegando ao prompt",
            ("Proposta", "npc_killed: npc_comandante_thrace"),
            ("Validação", "existe, é NPC, está vivo"),
            ("Projeção", "alive = false; regra de líder dispara"),
            ("Memória", "canonical_event, confirmed, fonte event_id"),
            ("Contexto", "[turno 15] Thrace foi morto, impacto 1,0"),
            ("Prompt", "o ESTADO ATUAL vence a lore antiga"))),

    sc("Personagens em três camadas", """
        Os personagens têm três camadas. Todos os da sessão. Os conhecidos pelo jogador, que
        a interface mostra sem traços ocultos. E os que estão em cena, os únicos com quem se
        pode conversar. Cada personagem sorteia de um a três traços ocultos, com semente
        estável, e eles são revelados com o tempo de convivência. Os traços afetam
        dificuldades mesmo antes de conhecidos: o mundo é real antes de ser descoberto.
    """, G("NPCs em três camadas", "TB",
           [("all", "Camada 1: todos da sessão", "data"), ("known", "Camada 2: conhecidos", "data"),
            ("scene", "Camada 3: em cena", "data"), ("ui", "Painel da interface", "io"),
            ("talk", "Rota de conversa", "llm")],
           [("all", "known", "known_by_player"), ("known", "scene", "in_scene"), ("known", "ui", "sem traits"), ("scene", "talk")])),

    sc("Anti carrossel", """
        Um playtest achou um sobrevivente moribundo idêntico surgindo em três lugares em seis
        turnos. A correção prende cada personagem gerado ao local onde surgiu: só entra no
        contexto se estiver em cena, na comitiva ou vinculado ao local atual. Viajar tira
        todos de cena. E um personagem pode se mudar quando faz sentido, por exemplo ao ser
        recrutado ou reintroduzido pela narrativa em outro lugar.
    """, CMP("Antes e depois do vínculo de local",
             "Antes", ["Mesmo NPC em vários locais", "Contexto arrastava NPC de outra cena",
                       "Template de encontro repetido"],
             "Depois", ["NPC preso ao local de origem", "Contexto só com cena, party ou local",
                        "Viagem limpa a cena", "Reintrodução pode relocalizar"])),

    sc("Uma identidade, muitos nomes", """
        Um mesmo personagem pode aparecer como identificador do Codex, identificador gerado
        em jogo, nome próprio ou apelido. Um serviço de identidade normaliza todas essas
        referências numa chave única, funde duplicatas de personagens gerados e resolve a
        entidade canônica. Essa peça sustenta o anti carrossel, o recrutamento, a memória
        por personagem que sobrevive ao recarregar o save e a escolha determinística do
        retrato na primeira aparição.
    """, EX("Várias referências, uma pessoa",
            ("Identificador do Codex", "npc_mv_brunna_ponte_alta"),
            ("Forma curta", "mv_brunna_ponte_alta"),
            ("Nome na fala", "Brunna Ponte-Alta"),
            ("Normalização", "sem acento, minúsculas, sem npc_ ou mv_"),
            ("Chave única", "brunna ponte alta"),
            ("Usos", "dedupe, recrutamento, memória e retrato"))),

    sc("A crônica", """
        Por fim, a crônica, o diário da aventura. Ela é dividida em capítulos, um por arco de
        campanha. Tem duas fontes: marcos determinísticos gerados por modelo de texto a partir
        de eventos aplicados, como uma morte ou uma subida de nível, e a prosa do menestrel,
        escrita pelo arquivista. Capítulos longos ganham um resumo comprimido, mas os marcos
        originais continuam valendo. E há busca híbrida e exportação em texto.
    """, B("A crônica por dentro",
           "Capítulo novo quando o título do arco muda",
           "Marcos por template a partir de eventos aplicados",
           "Prosa do menestrel vinda do arquivista",
           "Digest comprimido; raw e marcos seguem autoritativos",
           "Busca léxica mais semântica fundida por RRF",
           "Exportação em .txt pelo HUD")),

    sc("Recapitulando memória", """
        Recapitulando. Cinco camadas de memória, com o log de eventos como verdade. Confiança
        derivada da proveniência, nunca escolhida pela IA. Validação fecha falha antes de
        gravar, e repetição não promove. Segredos em três camadas. Contexto com orçamento e
        a regra de que o estado atual vence. Personagens em três camadas, presos ao seu
        local. E uma crônica por capítulos.
    """, CO("key", "Recapitulação", "Cinco camadas; confiança derivada da proveniência; validação fail-closed; segredos em três camadas; contexto de 3.500 tokens onde o estado atual vence; NPCs em três camadas; crônica por capítulos.")),
]))
