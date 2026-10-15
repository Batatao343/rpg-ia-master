from h import *

CHAPTERS = []

# ---------------------------------------------------------------- c10
CHAPTERS.append(ch("Combate v4: um jogo tático determinístico", "#7B2E2E", [
    sc("O coração mecânico", """
        O combate é onde a regra de ouro aparece com mais força. Ele foi reescrito num épico
        de dezessete especificações, que substituiu o velho sistema de dado de vinte contra
        classe de armadura por um jogo tático de cartas, totalmente determinístico. Aqui a
        IA só entende o que você quer e narra o que aconteceu. Cada número sai de uma pilha
        de módulos Python puros.
    """, T("Combate v4", "Valoria v2: cena, dados, dano, reações, morte e fuga")),

    sc("A pilha de uma rodada", """
        O nó de combate chama uma função que resolve uma rodada inteira. Ela rola iniciativa
        por lado. Depois, para cada ator em ordem de agilidade, aplica condições e dano
        contínuo, decide a ação da IA inimiga, dispara ataques de oportunidade, abre a
        janela de reações e resolve o turno em três tempos. No fim, trata últimas ações,
        estado terminal, entropia por abate e eventos do Abismo.
    """, G("O que acontece numa rodada", "TB",
           [("cn", "combat_node", "llm"), ("rr", "run_round", "python"), ("in", "Iniciativa por lado", "python"),
            ("ia", "IA tática inimiga", "python"), ("re", "Reações e oportunidade", "python"),
            ("tt", "Turno: Pré, Ação, Pós", "python"), ("at", "Ataque 2d10 + Virtude", "python"),
            ("dm", "Dano e Ferimentos", "python"), ("ls", "Última Ação e Terminal", "python"),
            ("fim", "Fim de rodada", "python")],
           [("cn", "rr"), ("rr", "in"), ("in", "ia"), ("ia", "re"), ("re", "tt"), ("tt", "at"),
            ("at", "dm"), ("dm", "ls"), ("ls", "fim")])),

    sc("A ficha de combate", """
        Todo ator, seja herói, inimigo ou aliado, passa por uma função que normaliza a ficha.
        São cinco Virtudes de zero a cinco: mente, agilidade, força, carisma e corpo. O
        corpo define a vitalidade e os espaços de ferimento. A esquiva é dez mais agilidade.
        Inimigos ganham categoria, perfil tático, política de perseguição, entropia própria
        e uma carta universal de defesa instintiva.
    """, TB("Tabelas-base do combate",
            ["Item", "Valor"],
            [["Vitalidade por Corpo 0 a 5", "6, 8, 10, 12, 14, 16"],
             ["Ferimentos Corpo 3", "4 leves, 2 graves, 2 críticos"],
             ["Esquiva", "10 + Agilidade"],
             ["Dano-base de arma", "leve 3, marcial 4, versátil 6, pesada 8"],
             ["Resistência / vulnerab.", "-2 ou -4 / +2 ou +4"],
             ["Nível máximo", "20"]])),

    sc("Dois dados de dez", """
        O ataque rola dois dados de dez e soma a Virtude da carta ou da arma, contra a
        esquiva do alvo. Vantagem rola três dados e mantém os dois maiores; desvantagem
        mantém os dois menores. Elas se cancelam e não acumulam: só o sinal importa. Uma
        dupla nos dados mantidos é crítico, dobra o efeito e acerta sempre. Dupla de dez é
        supercrítico e triplica.
    """, C("Vantagem: três dados, mantém dois", "services/conflict_resolution.py", "python", """
def roll_kept(advantage: int, rng) -> Dict:
    net = 1 if advantage > 0 else (-1 if advantage < 0 else 0)
    if net == 0:
        rolled = [_d10(rng), _d10(rng)]
        return {"rolled": rolled, "kept": list(rolled)}
    rolled = [_d10(rng) for _ in range(3)]
    ordenado = sorted(rolled)
    kept = ordenado[-2:] if net > 0 else ordenado[:2]
    return {"rolled": rolled, "kept": kept}
""")),

    sc("Iniciativa por lado e surpresa", """
        A iniciativa não é individual. Heróis e aliados formam um lado, inimigos o outro.
        Cada lado rola dois dados de dez mais a maior agilidade entre seus membros
        conscientes, e o maior total age primeiro; dentro do lado, a ordem é por agilidade.
        Se houve surpresa no encontro, o lado que surpreendeu age primeiro sem disputa. As
        condições e o dano contínuo são aplicados no início do turno de cada ator, pelo
        mesmo caminho de dano, sem proteção de armadura.
    """, F("Ordem de uma rodada",
           ("Surpresa?", "Quem surpreendeu age primeiro, sem rolar"),
           ("Lados rolam", "Dois d10 + maior Agilidade consciente"),
           ("Dentro do lado", "Agilidade decrescente, depois id"),
           ("Início do turno", "Condições e dano contínuo do ator"),
           ("Ação", "Pré, Ação e Pós, com reações"),
           ("Fim da rodada", "Abates, Recidiva e Abismo"))),

    sc("Testes gerais: Ímpeto e Presságio", """
        Fora do ataque, o sistema tem um teste geral elegante. Rola-se um dado de Ímpeto e
        um de Presságio, soma-se a Virtude e compara-se com a dificuldade: fácil nove,
        comum doze, difícil quinze, extremo dezoito, quase impossível vinte e um. Além do
        sucesso, os dados contam uma história: Ímpeto maior que Presságio traz uma
        consequência favorável; o contrário, desfavorável; empate é resultado puro. Com
        Ruptura, rolam-se dois dados de Ímpeto e fica o maior.
    """, TB("Dificuldades do teste geral",
            ["Dificuldade", "Alvo"],
            [["Fácil", "9"], ["Comum", "12"], ["Difícil", "15"],
             ["Extremo", "18"], ["Quase impossível", "21"],
             ["Leitura dos dados", "Ímpeto maior favorece; menor complica"]])),

    sc("Um ataque com números reais", """
        Um exemplo executado de verdade. Um Devoto do Abismo de nível um, com força
        quatro, ataca um Rato da Peste, um lacaio com esquiva treze e vitalidade doze. Os
        dados dão três e dez, sem dupla. Total dezessete contra treze: acerto. A carta
        marcial dá quatro de dano, mais dois do bônus de início de jogo. Seis de dano, e o
        rato fica com seis de vitalidade.
    """, EX("Golpe do Convite contra o Rato da Peste",
            ("Dados (seed 1)", "3 e 10, sem dupla"),
            ("Total", "13 + Força 4 = 17"),
            ("Contra Esquiva", "17 >= 13: acerto, multiplicador x1"),
            ("Dano", "marcial 4 + bônus early-game 2 = 6"),
            ("Defesas", "sem resistência, sem armadura"),
            ("Resultado", "Vitalidade 12 para 6; sem Ferimento"))),

    sc("E se sair um crítico", """
        Com outra semente, os dados dão cinco e cinco: dupla, crítico. O total é catorze, que
        já acertaria, e o crítico acerta sempre, mesmo abaixo da esquiva. O dano dobra para doze, e a vitalidade do rato
        vai a zero. E aqui está uma surpresa do sistema: vitalidade zero não é morte. É
        muito ferido. A derrota vem dos ferimentos. Como lacaio, qualquer ferimento derruba o
        rato no próximo golpe.
    """, CO("key", "Vitalidade zero não é morte", "A derrota é por flag: morto, fugido, rendido, inconsciente. Vitalidade 0 é muito ferido. Lacaio cai com qualquer Ferimento; Padrão ao encher o último crítico; Elite, Chefe e o herói passam pelo fluxo de morte rica.")),

    sc("Do dano ao ferimento", """
        O dano segue uma ordem fixa. Multiplica pelo crítico. Imunidade zera; resistência e
        vulnerabilidade somam a mais forte de cada lado. Armadura ou escudo, um só, dá
        proteção contra dano físico. A integridade da armadura pode absorver mais, até se
        esgotar e a armadura ficar comprometida. Dano ígneo soma dois se atravessou. O que
        passa da vitalidade é o excedente, e o excedente vira ferimento.
    """, F("Pipeline de dano, ordem fixa",
           ("Crítico", "dano-base vezes 1, 2 ou 3"),
           ("Imunidade e resist.", "Imune zera; resist e vuln somam"),
           ("Proteção", "Armadura ou escudo, um por ataque"),
           ("Integridade", "Absorve até o limite; zero compromete"),
           ("Ígneo", "+2 se pelo menos 1 atravessou"),
           ("Vitalidade", "Excedente = dano - vitalidade"),
           ("Ferimento", "Faixa por Corpo: leve, grave, crítico"),
           ("Efeito do tipo", "Sangramento, gélido, elétrico, abissal"))),

    sc("Ferimentos que agravam", """
        O excedente cai numa faixa que depende do corpo. Com corpo três, de um a seis é leve,
        de sete a doze é grave, treze ou mais é crítico. Ferimentos têm região: cabeça,
        torso, braço, perna. Um leve sobre um leve na mesma região vira grave. Categoria
        cheia escala para a próxima. Mirar uma região custa desvantagem. E dano cortante
        que fere ainda causa sangramento.
    """, EX("Um golpe que fere",
            ("Alvo", "armadura média, Corpo 3, Vitalidade 3"),
            ("Dano cortante", "8 x1 = 8"),
            ("Proteção", "-2: sobra 6"),
            ("Integridade", "absorve 2: sobra 4"),
            ("Vitalidade", "3 para 0, excedente 1"),
            ("Ferimento", "leve no torso + Sangramento"))),

    sc("A cena por zonas", """
        Não há grade de quadrados. A cena tem zonas, e cada participante tem três eixos
        independentes: distância, que vai de próximo a distante a separado; postura, que
        pode ser protegido, neutro ou exposto; e ocultação, que é relativa a cada observador.
        O engajamento corpo a corpo é uma relação à parte. Objetos da cena têm um catálogo
        fechado de efeitos, e a cena congela depois de preparada.
    """, TB("Manobras e seus custos",
            ["Manobra", "Custo", "Efeito"],
            [["Mover", "Pré ou Pós", "1 estágio; encerra Escondido"],
             ["Engajar", "Pré ou Pós", "Cria engajamento"],
             ["Desengajar", "Ação", "Sai sem ataque de oportunidade"],
             ["Guardar", "Ação", "Postura defensiva universal"],
             ["Esconder-se", "Ação", "Exige fonte plausível"],
             ["Procurar", "Ação", "Revela só para quem procurou"]])),

    sc("Reações", """
        Toda ação declarada abre uma janela de reação. Cada personagem do lado oposto pode
        oferecer uma reação comum por cadeia, com uma carta de reação cujo gatilho case, como
        ao ser atacado ou quando um aliado é atacado. Reação pode responder reação. E há o
        ataque de oportunidade, universal e fora do limite: quem sai de um engajamento sem
        desengajar leva um golpe de cada inimigo engajado. Um detalhe da implementação
        atual: uma reação bem sucedida não aplica o efeito escrito na carta; ela concede ao
        reator uma postura protegida contra o próximo ataque.
    """, B("Regras da janela de reação",
           "Uma reação comum por personagem em cada cadeia",
           "Gatilhos fechados: ao ser atacado, aliado atacado, ao sofrer dano...",
           "Ordem: alvo, aliados do alvo, aliados do ator, maior Agilidade",
           "O jogador escolhe antes, na interface, a carta de reação",
           "Ataque de Oportunidade: universal e fora do limite")),

    sc("A IA tática sem IA", """
        Os inimigos têm inteligência tática, mas sem modelo de linguagem. Cada um tem um
        perfil: uma lista ordenada de prioridades, cada uma com um gatilho e uma ação de um
        catálogo fechado: atacar, proteger, estabilizar, flanquear, controlar, apoiar, fugir
        ou se render. A primeira prioridade cujo gatilho é verdadeiro vence. Os gatilhos são
        calculados do estado real da cena.
    """, TB("Gatilhos táticos e exemplos",
            ["Gatilho", "Definição", "Bruto faz"],
            [["sozinho", "Nenhum parceiro vivo", "ataca"],
             ["muito_ferido", "Vitalidade <= 35% ou grave", "foge"],
             ["cercado", "Engajado com 2 ou mais", "ataca"],
             ["alvo_vulneravel", "Oponente <= 50% ou exposto", "ataca"],
             ["matilha_quebrada", "Metade dos parceiros caiu", "ataca"],
             ["sempre", "Sempre verdadeiro", "ataca"]])),

    sc("Provocação e ordens a companheiros", """
        Duas regras completam a inteligência tática. A provocação do Devoto marca um
        inimigo; ao escolher o alvo, ele ataca o provocador com chance base de cinquenta
        por cento, que sobe com a Entropia do Devoto até oitenta por cento com os números
        atuais. E companheiros recebem ordens do jogador, mas cada um tem
        restrições: uma ordem que fere um limite só é aceita conforme a resistência,
        flexível, resistente, absoluta ou autônoma. Medo ou inconsciência tiram o comando.
    """, TB("Ordens a companheiros",
            ["Resistência", "Ordem que fere a restrição"],
            [["Flexível", "Cede"],
             ["Resistente", "Cede só com argumento ou vantagem"],
             ["Absoluta", "Nunca cede"],
             ["Autônoma", "Nunca cede; age por conta"],
             ["Perda de comando", "Medo, confusão, separação, inconsciência"]])),

    sc("Morte rica", """
        Quando o herói, ou um inimigo de elite, chefe, nomeado ou companheiro, enche o último
        espaço crítico, começa a morte rica. Ele faz uma última ação fora da ordem, com
        vantagem extrema. Depois entra em estado terminal. Um médico com kit ou uma poção
        reanimam com metade da vitalidade. Sem aliado capaz, é morte. Com aliado, até duas
        tentativas de estabilização; duas falhas, morte.
    """, F("Fluxo de morte rica",
           ("Gatilho", "Último espaço crítico preenchido"),
           ("Última Ação", "Fora de ordem, uma vez, Vantagem extrema"),
           ("Estado Terminal", "Aguarda estabilização"),
           ("Automático", "Médico com kit ou poção: metade da Vitalidade"),
           ("Rolagem", "2d10 + Mente do ajudante vs CD 12, depois 15"),
           ("Duas falhas", "Morte real: abre a tela de morte"),
           ("Sobreviveu", "Cicatriz obrigatória gerada por IA"))),

    sc("Rendição, golpe não letal e fim", """
        Há também desfechos não mortais. O golpe final pode ser declarado não letal, salvo
        formas como destruição total. A rendição é determinística, pelo perfil: líder caído,
        vitalidade baixa, aliados abaixo do mínimo, moral quebrada. O combate termina por
        objetivo mecânico, por gatilho preparado ou quando todos os hostis estão fora de ação.
        Nunca porque perderam o interesse. Depois, a consciência do herói depende do pior
        ferimento.
    """, B("Saídas de um conflito",
           "Golpe não-letal, exceto destruição total ou queda fatal",
           "Rendição 100% determinística pelo perfil tático",
           "Fim por objetivo, gatilho preparado ou hostis inativos",
           "Pós-combate: só leves, acordado; grave, tratável; crítico, inconsciente")),

    sc("Fuga e perseguição", """
        Fugir abre uma perseguição numa trilha de quatro estágios: pressionado, afastado,
        quase livre e escapou. A posição inicial depende da distância. Cada rodada, o herói
        rola dois dados de dez mais agilidade contra dez mais a agilidade do perseguidor.
        Sucesso avança; falha recua; abaixo de pressionado, ele é alcançado e o combate
        volta. Se nenhum inimigo persegue, a fuga já nasce bem sucedida.
    """, G("A trilha de perseguição", "LR",
           [("pr", "Pressionado", "neutral"), ("af", "Afastado", "neutral"),
            ("ql", "Quase livre", "neutral"), ("es", "Escapou", "python"), ("al", "Alcançado: combate", "llm")],
           [("pr", "af", "sucesso"), ("af", "ql", "sucesso"), ("ql", "es", "sucesso"), ("pr", "al", "falha")])),

    sc("Fuga: limites e quem fica para trás", """
        A fuga tem mais regras. Enredado não foge. Há um teto de seis tentativas seguidas.
        Se a fuga dá certo e o destino é uma saída conectada, a viagem é aplicada no mesmo
        turno e a cena é limpa. E se um companheiro é abandonado, o destino dele é
        sorteado por uma simulação determinística entre fuga, captura, rendição,
        esconderijo, combate, morte ou reencontro futuro, com pesos que dependem da
        vitalidade, da agilidade e de quantos o perseguem. Sacrifício voluntário só existe
        com o traço certo.
    """, B("Detalhes da perseguição",
           "Condutor é sempre o protagonista; Virtude depende da abordagem",
           "No loop atual a fuga usa Agilidade fixa",
           "Teto de 6 tentativas seguidas de fuga",
           "Sucesso com destino válido aplica a viagem no mesmo turno",
           "Companheiro abandonado: destino por simulação com seed",
           "Ataque corpo a corpo em Pressionado encerra a perseguição")),

    sc("Abismo, preparação e resumo", """
        Três serviços completam o combate. Eventos do Abismo podem ser preparados antes da
        luta, cada um com base em algo real da cena, e disparados por cargas, sem IA. O nível
        do encontro vem do perigo absoluto, nunca da força da comitiva. E ao fim, um resumo canônico com vinte e dois campos registra mortos,
        fugitivos, ferimentos e saque, sem IA, impedindo a narração de desfazer uma morte.
    """, CMP("Antes e depois do conflito",
             "Preparação", ["Nível do Encontro: perigo absoluto, 1 a 10", "Potência por categoria e nível",
                            "IA escolhe a categoria; o número é Python", "Eventos do Abismo com base na cena"],
             "Resumo canônico", ["22 campos montados do estado final", "Mortos, fugidos, rendidos, capturados",
                                 "Loot usa o nível do encontro", "Narração não pode reverter morte"])),

    sc("Por que esta luta começou", """
        Todo combate registra a sua origem, num vocabulário fechado: provocado pelo
        jogador, encontro de viagem, perigo regional, pressão do arco, perseguição
        recorrente ou desconhecida. A origem vem da causa real da cena, não de um rótulo
        antigo. Isso nasceu de um playtest em que toda luta aparecia como provocada pelo
        jogador, até as emboscadas durante o descanso. Cada conflito também ganha um
        identificador por instância e linha do tempo, para não contar duas vezes.
    """, TB("Origens de combate",
            ["Origem", "Quando"],
            [["player_provoked", "Hostilidade explícita do jogador"],
             ["travel_encounter", "Encontro sorteado na viagem"],
             ["regional_danger", "Reforços, facção, descanso perigoso"],
             ["arc_pressure", "Beat ou evento do arco"],
             ["pursuit_recurrence", "Perseguição que voltou"],
             ["unknown", "Sem causa identificável"]])),

    sc("O bestiário que aprende", """
        No começo de uma luta, o jogador só vê o que é público do inimigo: vitalidade,
        esquiva, proteção, condições e posição. Quando uma criatura usa uma Carta ou tem
        uma resistência atingida, isso é revelado e fica gravado no bestiário do
        arquétipo, para os próximos encontros. Cartas exclusivas de uma variante não
        vazam para o arquétipo. E o conhecimento cresce em quatro níveis: rumores,
        encontrada, estudada e dominada.
    """, TB("Níveis de conhecimento de uma criatura",
            ["Nível", "Exige"],
            [["1. Rumores", "Vista uma vez"],
             ["2. Encontrada", "Enfrentada uma vez"],
             ["3. Estudada", "Três derrotas"],
             ["4. Dominada", "Sete derrotas"],
             ["Revelações", "Cartas e resistências persistem"]])),

    sc("Recapitulando o combate", """
        Recapitulando. Uma rodada é uma pilha de módulos Python. Dois dados de dez mais
        Virtude contra esquiva, com vantagem que não acumula e crítico por dupla. Dano em
        ordem fixa até virar ferimento, e vitalidade zero não é morte. Cena por zonas,
        reações e oportunidade. IA tática por prioridades. Morte rica, fuga por trilha e um
        resumo canônico no final. A IA só entende e narra.
    """, CO("key", "Recapitulação", "2d10 + Virtude contra Esquiva; vantagem não acumula; crítico por dupla. Dano em ordem fixa vira Ferimento. Zonas, reações, IA tática por prioridades, morte rica, fuga por trilha e resumo canônico.")),
]))

# ---------------------------------------------------------------- c11
CHAPTERS.append(ch("Cartas, Posturas, Entropia e progressão", "#5B3A7A", [
    sc("O baralho do herói", """
        Se o combate é o tabuleiro, as Cartas são as jogadas. Cada habilidade do herói é uma
        Carta com custo, frequência e efeito de um catálogo fechado. As classes, chamadas
        Posturas diante do Abismo, definem quais Cartas existem e como dois recursos
        especiais se comportam. Neste capítulo vemos Cartas, as cinco Posturas, Entropia,
        Carga do Abismo e a progressão até o nível vinte.
    """, T("Cartas e Posturas", "Acervo, Preparação, Entropia, Carga e níveis")),

    sc("Anatomia de uma Carta", """
        Uma Carta tem um tipo: ativa, passiva, utilitária ou reação. Tem patamar, custo em
        Entropia, frequência de uso, a Virtude permitida e um efeito com um tipo de um
        catálogo fechado: dano, dano contínuo, cura, proteção, provocação, empurrão, marca,
        condições, vantagem e bônus diversos. Uma Carta central por subclasse tem Ruptura e
        duas evoluções possíveis.
    """, EX("Liturgia da Espera, Carta central do Devoto",
            ("Tipo", "ativa, subclasse Consagrado"),
            ("Custo", "3 de Entropia, uma vez por cena"),
            ("Efeito", "protecao valor 4"),
            ("Ruptura", "caminho A protecao 8; caminho B taunt 4"),
            ("Evolução A", "protecao 6; ruptura 10"),
            ("Evolução B", "protecao 4; ruptura taunt 6"))),

    sc("Acervo e Preparação", """
        O herói tem um Acervo, as Cartas que aprendeu, e uma Preparação, as que leva para a
        luta. O número de espaços de preparação cresce com o nível: quatro até o nível três,
        dez no nível vinte. Reorganizar é livre, mas só fora de combate, em local de
        perigo até três e fora de zona extrema.
        As frequências são por turno, cena, descanso curto ou longo, e o descanso longo
        zera tudo em cascata.
    """, TB("Espaços de Preparação por nível",
            ["Níveis", "Espaços"],
            [["1 a 3", "4"], ["4 a 6", "5"], ["7 a 9", "6"], ["10 a 12", "7"],
             ["13 a 16", "8"], ["17 a 19", "9"], ["20", "10"]])),

    sc("Ruptura", """
        A Ruptura é a jogada arriscada. O herói paga o custo normal, ganha vantagem no ataque
        e recebe o efeito especial de ruptura da Carta. Mas ganha um ponto de Carga do
        Abismo, mesmo se falhar. É poder emprestado do Abismo, e o Abismo cobra depois.
        Só Cartas com ruptura definida permitem isso, e a interface mostra o botão apenas
        quando está pronta.
    """, CO("warn", "Ruptura cobra em Carga", "Ruptura: custo normal, +1 de Vantagem e o efeito de ruptura da Carta. Gera +1 de Carga do Abismo mesmo se o ataque falhar. Carga é longo prazo e não cai no descanso.")),

    sc("Os números do catálogo", """
        O catálogo é grande. O acervo autoral começou com dezesseis Cartas por Postura e
        cresceu na expansão de conteúdo: hoje cada Postura tem trinta ou trinta e uma, quase
        metade do tronco e o resto dividido entre as três subclasses, somando cento e
        cinquenta e três. Há mais oitenta Cartas tardias, dos níveis nove a vinte, quinze
        delas Ápices, e quarenta Cartas de inimigos. Um teste de paridade garante que, nas
        Cartas de dano puro, o dano dividido pelo custo fique entre um e meio e quatro.
    """, S("O baralho de Valoria",
           ("30 a 31", "Cartas por Postura, tronco e subclasses"),
           ("153", "Cartas das cinco Posturas"),
           ("80", "Cartas tardias, níveis 9 a 20"),
           ("15", "Ápices, um por subclasse"),
           ("40", "Cartas de inimigos"),
           ("1,5 a 4", "banda de paridade dano por custo"))),

    sc("Entropia e Carga", """
        Dois recursos dão personalidade às Posturas. A Entropia é um pool único que paga as
        Cartas e substitui mana e vigor. Ela recompõe inteira no descanso. A Carga do Abismo
        é de longo prazo: sobe com Ruptura, com gatilhos de classe e com Cartas de pico, e
        não cai no descanso. Ela tem patamares, leve, moderado e severo, e cada Postura sofre
        uma consequência diferente.
    """, CMP("Os dois recursos",
             "Entropia", ["Pool único que paga as Cartas", "Substitui mana e stamina",
                          "Recompõe integral no descanso", "Sobe por gatilhos de classe"],
             "Carga do Abismo", ["Longo prazo: não cai no descanso", "Sobe com Ruptura e gatilhos",
                                 "Patamares: leve 1, moderado 4, severo 7", "Cada Postura paga um preço diferente"])),

    sc("As cinco Posturas", """
        São cinco Posturas, cada uma uma filosofia diante do Abismo. O Devoto ama: é o tanque,
        e ganha Entropia ao levar dano. O Sangromante negocia: dano corpo a corpo, ganha
        Entropia sacrificando o próprio sangue. O Corruptor trabalha junto: controle e dano
        contínuo, alimentado pela decadência ao redor. O Arcanista manipula, à distância.
        O Médico de Campo nega: suporte e cura.
    """, TB("As Posturas diante do Abismo",
            ["Postura", "Papel", "Gatilho de Entropia"],
            [["Devoto do Abismo", "Tanque; ama", "Ao sofrer dano"],
             ["Sangromante", "Dano corpo a corpo; negocia", "Ao sacrificar Vitalidade"],
             ["Corruptor", "Controle e DoT; trabalha junto", "Decadência por perto"],
             ["Arcanista Cinzento", "Dano à distância; manipula", "Ao canalizar"],
             ["Médico de Campo", "Suporte e cura; nega", "Quando aliado sofre"]])),

    sc("O preço de cada Postura", """
        Cada Postura paga a Carga de um jeito. O Devoto sofre insônia: descansa e recupera
        menos. O Sangromante ganha cicatrizes que reduzem a vitalidade máxima para sempre. O
        Corruptor se transforma, com penalidades conforme o domínio. O Arcanista fica
        dependente: com Carga moderada ou pior e sem instrumento, as Cartas custam o dobro. E o Médico esconde a própria
        Carga, até um colapso súbito ao cruzar o patamar severo.
    """, TB("Regra especial e consequência",
            ["Postura", "Regra especial", "Consequência da Carga"],
            [["Devoto", "Provocação cresce com Entropia", "Insônia: descanso rende menos"],
             ["Sangromante", "Entropia de sangue vaza", "Cicatriz: -3 Vitalidade máx."],
             ["Corruptor", "Decadência por domínio", "Transformação por domínio"],
             ["Arcanista", "Caldeira: estoura em 3 turnos", "Dependência: custo x2"],
             ["Médico", "Purga Carga de aliado", "Recidiva oculta e colapso"]])),

    sc("O registro anti órfão", """
        Uma lição de engenharia veio desse sistema. Uma revisão descobriu três mecânicas de
        classe mortas: a provocação, a transformação e a purga estavam prontas e testadas
        isoladamente, mas nunca eram chamadas pelo jogo. A correção foi um registro de tipos
        tratados pelo motor e um teste que varre os arquivos de dados e falha se aparecer um
        tipo sem tratador.
    """, CO("info", "HANDLED_KINDS", "Registro dos kinds de gatilho, regra especial, consequência, efeito e passiva que o motor sabe tratar. Um teste varre os JSONs gerados e fica vermelho para qualquer kind sem handler.")),

    sc("Cartas de Virtude e de inimigos", """
        Dois tipos de Carta vivem fora da mão preparada. As Cartas de Virtude, duas por
        personagem, não ocupam espaço de Preparação: dão um bônus que cresce em estágios
        conforme a Virtude, um para Virtude até dois, dois até quatro, três no cinco, e a
        Maestria acrescenta estágios. Já os inimigos têm Cartas próprias, com assinatura
        oculta até serem vistas, pagas com a Entropia da criatura e uma economia de uso
        reiniciada a cada rodada.
    """, CMP("Fora da mão do herói",
             "Cartas de Virtude", ["Duas por personagem, fora dos slots", "Bônus por estágio da Virtude",
                                   "Estágio 1, 2 ou 3 conforme a Virtude", "Maestria soma até 3 pontos"],
             "Cartas de inimigos", ["40 Cartas de bestiário", "Pagas com Entropia da criatura",
                                    "Usos reiniciados a cada rodada", "Reveladas ao jogador quando usadas"])),

    sc("Passivas, utilitárias e itens vivos", """
        Nem toda Carta é de ataque. As utilitárias abrem capacidades fora de combate: o
        narrador recebe a lista num bloco próprio do prompt e não pode conceder nada fora
        dela. As passivas existem no catálogo, mas a leitura do código não encontrou quem
        as aplique no motor atual, um achado que volta no fim do vídeo. Os itens ganharam
        vida: um item equipado pode ter passiva, consumíveis ofensivos atingem o inimigo
        com teste de resistência, e tochas anulam a penalidade do escuro.
    """, B("Além das Cartas ativas",
           "Utilitárias: capacidades fora de combate, gate determinístico",
           "Passivas de Carta: no catálogo, sem consumidor aparente",
           "Item equipado pode trazer passiva própria",
           "Consumível ofensivo usa teste de resistência d20",
           "Tocha ou lanterna anula a penalidade de escuro")),

    sc("Experiência e níveis", """
        A experiência vem de abates, beats e missões: cinquenta por lacaio, duzentos por
        elite, mil por chefe, cento e cinquenta por beat e duzentos por missão. A tabela sobe
        até o nível vinte, com trezentos e cinquenta e cinco mil pontos. A cada nível sobe a
        Entropia máxima pela curva da classe. Um detalhe: a vitalidade não cresce com o
        nível, só com o Corpo.
    """, S("Progressão",
           ("50", "XP por lacaio; elite 200; chefe 1000"),
           ("150", "XP por beat; 200 por quest"),
           ("300", "XP para o nível 2"),
           ("355 mil", "XP para o nível 20"),
           ("Corpo", "só ele aumenta a Vitalidade"))),

    sc("Escolhas pendentes", """
        Subir de nível gera escolhas pendentes, que não travam o jogo. No nível três, a
        escolha irreversível da subclasse, que bloqueia as demais até ser feita. Do nível
        dois ao dezenove, uma Carta nova ou, a partir do quatro, uma evolução. Nos níveis pares até dez, um ponto de Virtude.
        Nos níveis doze, dezesseis e vinte, Maestria nas Cartas de Virtude. E no vinte, o
        Ápice da subclasse, concedido automaticamente.
    """, F("Escolhas ao subir de nível",
           ("Nível 3", "Subclasse, irreversível, antes de tudo"),
           ("Níveis 2 a 19", "Nova Carta ou, do 4 em diante, evolução A/B"),
           ("Níveis 2 a 10 pares", "+1 numa Virtude, teto 5"),
           ("Níveis 12, 16, 20", "Maestria em Carta de Virtude"),
           ("Nível 20", "Ápice da subclasse, automático"),
           ("Ledger", "Cada concessão é idempotente"))),

    sc("Criação e bônus de início", """
        Na criação, o jogador distribui quatro, três, dois, um e um entre as cinco Virtudes,
        e começa com seis Cartas no Acervo, quatro preparadas e duas de Virtude. Para não
        morrer cedo demais, existe um bônus temporário de dano: mais dois nos níveis um e
        dois, mais um no nível três. Ele nasceu de um playtest que mostrou heróis frágeis sem
        saída nos primeiros turnos.
    """, EX("Devoto do Abismo recém-criado",
            ("Virtudes", "Força 4, Corpo 3, Carisma 2, Mente 1, Agi 1"),
            ("Vitalidade", "18 = Corpo 3 (12) + bônus de classe 6"),
            ("Ferimentos", "4 leves, 2 graves, 2 críticos"),
            ("Entropia", "14 de 14"),
            ("Esquiva", "11"),
            ("Cartas", "6 no Acervo, 4 preparadas, 2 de Virtude"))),

    sc("Como a ficha nasce", """
        A ficha é montada numa ordem fixa. Primeiro os dados oficiais da Postura, depois as
        Virtudes escolhidas e validadas, a Entropia pela curva da classe e as Cartas
        iniciais. O modelo inteligente entra só para dar sabor: um inventário temático da
        região. Ele não define Virtudes, vitalidade nem Cartas. Se falhar, o herói recebe
        um kit básico. Por fim vêm o equipamento inicial, os traços da raça e a vitalidade
        derivada do Corpo, com a ficha curada por completo.
    """, F("Montagem da ficha",
           ("Classe", "Dados oficiais da Postura escolhida"),
           ("Virtudes", "Distribuição 4, 3, 2, 1, 1 validada"),
           ("Entropia e Cartas", "Curva da classe e Acervo inicial"),
           ("Sabor via SMART", "Inventário temático; guard: Kit Básico"),
           ("Equipamento", "Inicial da classe, auto-equipado"),
           ("Raça e vitalidade", "Traços raciais e vida pelo Corpo"))),

    sc("Recapitulando Cartas e Posturas", """
        Recapitulando. Habilidades são Cartas com custo, frequência e efeito fechado,
        organizadas em Acervo e Preparação. Ruptura dá poder e cobra Carga. Cinco Posturas,
        cada uma com seu gatilho de Entropia, regra especial e consequência de Carga. Um
        registro anti órfão impede mecânicas mortas. E a progressão vai ao nível vinte, com
        subclasse no três e Ápice no vinte.
    """, B("O essencial de Cartas e classes",
           "Cartas: tipo, custo em Entropia, frequência, efeito fechado",
           "Acervo aprendido, Preparação limitada por nível",
           "Ruptura: Vantagem e efeito extra, +1 Carga sempre",
           "Cinco Posturas com gatilho, regra e consequência próprias",
           "Níveis 1 a 20: subclasse no 3, Ápice no 20")),
]))

# ---------------------------------------------------------------- c12
CHAPTERS.append(ch("O mundo sistêmico: tempo, viagem, clima e economia", "#2E4E6E", [
    sc("Um mundo que respira", """
        Fora do combate, Valoria também é um sistema. O tempo passa em períodos, viajar custa
        tempo, o clima muda, a luz importa, mercadores repõem estoque, criaturas migram e
        armadilhas esperam. Tudo isso é Python determinístico. A IA só descreve o que esses
        sistemas decidiram. Este capítulo percorre cada um deles.
    """, T("O mundo sistêmico", "Relógio, viagem, descanso, clima, luz, economia e mais")),

    sc("Relógio e viagem", """
        O dia tem cinco períodos: amanhecer, manhã, tarde, anoitecer e noite. Viajar custa
        períodos, normalmente um, ou o tempo específico do mapa. Entrar num interior, como
        uma taverna, custa zero, e sair também. Só aparecem destinos conectados ao local
        atual, e cada visita é marcada no mapa, que nasce coberto por uma névoa de guerra.
        A intenção de viajar é detectada por palavras em português.
    """, F("Uma viagem, em Python",
           ("Intenção", "Palavras-chave: vou para, viajo, sigo para"),
           ("Destino", "Só conexões do local atual; senão, recusa"),
           ("Custo", "Interior 0; travel_times do mapa; padrão 1"),
           ("Relógio", "Avança os períodos e o clima"),
           ("Fog of war", "Marca o local como visitado"),
           ("Cena", "Todos os NPCs saem de cena"))),

    sc("Descanso", """
        Descansar avança dois períodos. Recupera metade da vitalidade máxima, reduzida pela
        insônia do Devoto. Remove todos os ferimentos leves; graves precisam de kit; críticos,
        de um médico. Recupera a integridade da armadura, zera os usos das Cartas e devolve a
        Entropia inteira. A Carga do Abismo continua lá. E um clima de miasma pode impedir o
        descanso.
    """, TB("O que o descanso faz",
            ["Recurso", "Efeito"],
            [["Vitalidade", "+ metade do máximo, menos Insônia"],
             ["Ferimentos", "Leves somem; grave: kit; crítico: Médico"],
             ["Entropia", "Recompõe integral"],
             ["Carga do Abismo", "Intacta"],
             ["Cartas", "Contadores de uso zerados"],
             ["Tempo", "Avança 2 períodos e o clima"]])),

    sc("Encontros", """
        Encontros não são sorteados pela IA. Eles disparam por condições: um alerta de fuga
        ativo, uma facção hostil dominando o local, uma ameaça iminente com perigo três ou
        mais, ou perigo efetivo quatro. Há intervalo mínimo entre encontros, maior no começo
        do jogo. Um herói de nível até três, descansando em zona não extrema de perigo baixo,
        não sofre emboscada: o descanso precisa recuperar.
    """, B("Regras de encontro",
           "Gatilhos: reforços, facção hostil, ameaça, perigo 4",
           "Cooldown de 2 turnos, mais 2 até o nível 3",
           "Força do encontro escala com o nível, exceto em zona apex",
           "Descanso seguro no early-game em perigo até 3",
           "Mesmo template no mesmo local duas vezes é descartado")),

    sc("Orçamento de encontro", """
        Quantos inimigos? Um orçamento decide. Lacaio custa dois, elite cinco, chefe doze. A
        base depende do perigo, somada ao nível e ao número de aliados, com um teto de
        sobrevivência. O corte nunca remove um chefe, prioriza variedade e, no nível um,
        permite no máximo um elite. Encontros fracos são reforçados com criaturas da região
        até um piso.
    """, EX("Orçamento num lugar de perigo 3",
            ("Base por perigo", "7"),
            ("Nível do herói", "+2"),
            ("Aliados", "+2 por aliado: 0"),
            ("Orçamento", "9"),
            ("Teto de sobrevivência", "5 + 3 x nível = 11"),
            ("Composição", "1 elite (5) + 2 lacaios (4)"))),

    sc("Tipos de encontro e percepção", """
        Disparado o encontro, ele pode ser combate, armadilha, rastro ou social, com pesos
        que mudam com o perigo. Antes, um teste de percepção decide quem surpreende quem; ele
        sofre com clima e escuridão. Uma armadilha é testada e, se falhar, causa dano pelo
        pipeline normal. Um detalhe: percepção e armadilhas ainda usam um dado de vinte, um
        resquício do sistema antigo.
    """, TB("Tipos de encontro por perigo",
            ["Tipo", "Perigo 1 a 2", "Perigo 3 a 4"],
            [["Combate", "50%", "60%"],
             ["Rastro", "30%", "10%"],
             ["Social", "20%", "10%"],
             ["Armadilha", "0%", "20%"]])),

    sc("Clima e luz", """
        O clima é uma cadeia de Markov por região, que avança a cada mudança de período. Há
        também fenômenos globais, como a Tempestade de Éter e a Noite Sem Estrelas, que podem
        começar a qualquer transição, com chance maior em lugares perigosos. A luz importa:
        à noite, ou em local escuro fora de abrigo, sem tocha, a percepção perde três e o
        acerto perde um.
    """, CMP("Clima e luz como mecânica",
             "Clima", ["Markov por região a cada período", "Eventos globais: 6% + 3% por perigo",
                       "Afeta percepção, ataque e viagem", "Miasma bloqueia descanso", "DoT ao ar livre"],
             "Luz", ["Escuro: noite ou tag dark, fora de abrigo", "Percepção -3 sem luz",
                     "Acerto -1 sem luz", "Tocha ou lanterna anula", "Inimigos ainda sofrem no escuro natural"])),

    sc("Facções que avançam sozinhas", """
        As facções têm vida própria. Cada uma tem um objetivo e um ritmo, e a cada período
        que passa seu progresso avança, sem sorteio. Ao chegar a cem, dispara uma ascensão
        escrita à mão: dominar um local, expandir para uma região, elevar o perigo, invocar
        uma entidade ou eliminar uma rival. O narrador só nomeia a facção se o jogador já a
        conhece; senão, descreve apenas a consequência sentida. Personagens revelam
        facções em níveis, e a reputação muda por impactos validados em Python.
    """, F("O ciclo de uma facção",
           ("Ritmo", "Progresso += ritmo por período, sem RNG"),
           ("Ascensão", "Ao cruzar 100, efeito autoral no mundo"),
           ("Efeitos", "Dominar, expandir, perigo, invocar, eliminar"),
           ("Narração", "Nome só se a facção é conhecida"),
           ("Descoberta", "Existência, objetivo, depois progresso"),
           ("Reputação", "Delta fixado em Python, evento gravado"))),

    sc("Os ecos do mundo", """
        Quando o tempo passa sem combate, numa viagem ou num descanso, o simulador do mundo
        pede ao modelo rápido um pulso: um rumor, um fato e uma mudança de perigo. O Python
        limita a mudança a um ponto para mais ou para menos e mantém o perigo entre um e
        quatro. O rumor aparece como eco do mundo. Só a consequência realmente aplicada vira
        memória; o fato livre do modelo é descartado. E facções desconhecidas só aparecem
        como sinais sem nome.
    """, EX("Um pulso do mundo",
            ("Proposta do modelo", "rumor, fato e danger_shift +2"),
            ("Clamp em Python", "danger_shift vira +1"),
            ("Perigo do local", "2 para 3, dentro de 1 a 4"),
            ("Narração", "[ECOS DO MUNDO] e o rumor"),
            ("Memória gravada", "o perigo de X mudou de 2 para 3"),
            ("Descartado", "o fato livre, não verificado"))),

    sc("Economia", """
        A economia é inteiramente determinística. O preço base vem do item ou da raridade.
        Ele é multiplicado pela oferta: mais barato onde o item é produzido, normal se há
        produtor alcançável, caro e esgotado se todas as rotas até produtores estão
        bloqueadas. Facção hostil encarece em cinquenta por cento. Venda paga metade. E o
        sinal do ouro é sempre decidido pelo Python, nunca pela IA.
    """, F("Como um preço é calculado",
           ("Base", "value_gold ou raridade: 25 a 6000"),
           ("Oferta", "0,6 local; 1,0 alcançável; 1,8 bloqueado"),
           ("Mercador", "Multiplicador próprio"),
           ("Facção hostil", "Comprador paga x1,5"),
           ("Venda", "x0,5"),
           ("Arredonda", "Múltiplo de 5"))),

    sc("Mercadores, forja e saque", """
        Mercadores têm estoque e repõem a cada três dias pelo relógio. Locais hostis escondem
        itens raros. Itens únicos já reivindicados somem das prateleiras. A forja valida
        local, classe, ingredientes e ouro. E o saque sorteia raridade pela faixa de perigo,
        de pools regionais, removendo antes do sorteio os únicos já reivindicados e os drops
        de criaturas que foram caçadas até quase sumir.
    """, B("Regras de comércio e saque",
           "Reposição determinística a cada 3 dias de relógio",
           "Local hostil esconde itens raros ou melhores",
           "Itens únicos: nunca duplicados, com evento de posse",
           "Forja exige local, classe, ingredientes e ouro",
           "Saque: raridade por perigo, ouro 3 a 12 vezes o perigo")),

    sc("Exploração e ecologia", """
        Explorar compensa. Ao chegar num lugar novo, um baú curado tem prioridade e só pode
        ser saqueado uma vez. Senão, há chance de um achado ambiental, crescente com o
        perigo, que nunca é um item único. O sorteio usa uma semente estável por jogo, local
        e turno. E existe ecologia: criaturas muito caçadas ficam suprimidas e saem do
        sorteio, até a população se recuperar, e vagas atraem migrantes vizinhos.
    """, S("Exploração e ecologia",
           ("12%+8%", "chance de achado por nível de perigo"),
           ("50%", "teto da chance de achado"),
           ("1 vez", "cada baú curado"),
           ("6 kills", "pressão de caça cai a 0,1"),
           ("20 turnos", "população volta ao normal"))),

    sc("Comitiva e aliados de cena", """
        O herói pode ter companheiros. Recrutar exige relação de sete ou mais, comitiva com
        menos de três e facção não hostil, e a decisão é Python. Além disso, um personagem
        amigo presente na cena, com relação seis ou mais, vira aliado temporário no combate:
        no máximo dois, o dano reflete no personagem, e ele não entra para a comitiva. No
        inventário, consumíveis e materiais empilham, e há três espaços de equipamento:
        arma, armadura e acessório.
    """, CMP("Party e inventário",
             "Party e aliados", ["Recrutar: relação 7+, party < 3", "Facção do NPC não pode ser hostil",
                                 "Aliado de cena: relação 6+, máx. 2", "Companheiro ganha ficha v4 completa"],
             "Inventário", ["Entradas com id e quantidade", "Consumíveis e materiais empilham",
                            "Slots: arma, armadura, acessório", "Item único marcado e protegido"])),

    sc("Checkpoints e o laboratório", """
        Dois sistemas fecham o mundo. Checkpoints são gravados a cada dez turnos ou ao entrar
        numa zona segura, mas nunca no meio de um combate ou transição de morte. E existe um
        laboratório de combate: uma arena isolada onde se escolhe classe, nível, inimigo e
        quantidade, usando o mesmo motor de produção, mas sem campanha, memória, saque,
        experiência nem checkpoints.
    """, CMP("Dois modos especiais",
             "Checkpoints", ["A cada 10 turnos ou zona segura", "Nunca em combate ou transição de morte",
                             "Slot único com a memória da sessão", "Checkpoint inicial na criação"],
             "Laboratório de combate", ["Classe, nível 1, 3, 5 ou 10, inimigo e quantidade",
                                        "Mesmo run_round de produção", "Sem campanha, RAG, loot ou XP",
                                        "Texto livre vira ataque básico"])),

    sc("Recapitulando o mundo sistêmico", """
        Recapitulando. Relógio em cinco períodos, viagem com custo e névoa de guerra.
        Descanso que recupera e não recompõe Carga. Encontros por gatilho e orçamento.
        Percepção, clima e luz como modificadores. Facções com ritmo e ascensão, e ecos do
        mundo limitados em Python. Economia de oferta e rotas. Exploração com
        baús e achados. Ecologia de caça. Comitiva e aliados de cena. Checkpoints e um
        laboratório de combate.
    """, CO("key", "Recapitulação", "Relógio, viagem, descanso, encontros, clima, luz, facções, economia, exploração, ecologia, party e checkpoints são Python determinístico. A IA só descreve o que esses sistemas decidiram.")),
]))
