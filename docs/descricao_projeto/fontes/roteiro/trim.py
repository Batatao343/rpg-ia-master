import re,io
reps = {
"p1.py": [
 ("Neste vídeo vamos abrir o projeto inteiro, peça por peça: o motor de\n        agentes, a mecânica, o mundo, a memória, a interface, a infraestrutura e o processo\n        que mantém tudo de pé. Pegue um café, porque a viagem é longa.",
  "Neste vídeo vamos abrir o projeto inteiro, peça por peça, do motor de\n        agentes ao processo que mantém tudo de pé."),
 ("O mundo se chama Valoria, persiste entre as sessões e reage\n        ao que você faz: facções avançam, o clima muda, personagens lembram de você.",
  "O mundo se chama Valoria, persiste entre as sessões e reage\n        ao que você faz."),
 ("Para rodar como serviço, existe um perfil local first com Postgres\n        e Supabase.", "Há ainda um perfil local first com Postgres e Supabase."),
 ("O resto do vídeo é zoom em cada caixa.", ""),
 ("E se existe uma morte\n        pendente, aguardando a escolha na tela de morte, nenhuma ação passa até essa\n        escolha ser feita. O próprio grafo repete essa barreira na entrada.",
  "E se existe uma morte\n        pendente, nenhuma ação passa até o jogador escolher na tela de morte."),
 ("O guarda tira uma fotografia do antes: ouro, X P, nível,\n        inventário e missões concluídas.", "O guarda fotografa o antes: ouro, X P, inventário e missões."),
 ("Curiosidade: um sexto beat do DeepSeek já derrubou um plano inteiro, então hoje o\n        excesso é cortado em Python.", "E beats em excesso são cortados em Python."),
 ("a luz do ambiente, o clima, só as facções que o jogador conhece, as\n        entidades canônicas que podem ser citadas, as missões ativas e as capacidades\n        utilitárias da ficha.", "luz, clima, só as facções que o jogador conhece, entidades\n        canônicas, missões ativas e capacidades da ficha."),
 ("Recrutar, dispensar e mandar\n        esperar são resolvidos em Python. A IA nunca decide se o personagem aceita.", "Recrutar e dispensar são decididos em Python."),
 ("Para provedores\n        compatíveis com OpenAI, ele força chamada de ferramenta, porque o Groq rejeitava\n        esquemas com dicionários abertos.", ""),
 ("Ele até propõe missões em alguns turnos e marca beats como concluídos,\n        para que o harness offline consiga fechar uma missão. Mas há um alerta:", "Ele até propõe missões, para o harness offline exercitá-las. Mas há um alerta:"),
 ("Providers OpenAI-compat recebem method=function_calling; schemas Pydantic recebem include_raw para recuperar JSON.", "Providers OpenAI-compat usam function_calling; schemas recebem include_raw para recuperar JSON."),
 ("Modelo de linguagem que interpreta e narra", "Modelo que interpreta e narra"),
],
"p2.py": [
 ("O progresso é verificável: chegar ao local grava\n        um marco uma única vez; duas investigações distintas no alvo deixam a missão pronta\n        para concluir, e o próprio sistema emite a conclusão.", "O progresso é verificável: chegar ao local grava\n        um marco, e duas investigações distintas no alvo permitem concluir."),
 ("Depois, a narração repetiu a informação, e o detector\n        acusou vazamento. Mas não era vazamento: o jogador já sabia.", "Quando a narração repetiu o fato, o detector acusou\n        vazamento, mas o jogador já sabia."),
 ("Legião perde 50 de estabilidade", "Legião: -50 estabilidade"),
],
"p3.py": [
 ("O nível\n        do encontro é calculado pelo perigo absoluto do lugar e do evento, nunca pela força\n        da comitiva.", "O nível\n        do encontro vem do perigo absoluto, nunca da força da comitiva."),
 ("+ metade do máximo, vezes fator de Insônia", "+ metade do máximo, menos Insônia"),
 ("Leves somem; graves com kit; críticos, Médico", "Leves somem; graves, kit; críticos, Médico"),
],
"p4.py": [
 ("Outra camada gera um\n        identificador de correlação, mede duração e acrescenta cabeçalhos de segurança.", "Outra camada correlaciona e mede cada pedido."),
 ("A cada\n        dez segundos sem novidade, um ping mantém a conexão viva.", ""),
 ("/game/prologue, /game/new, combat-simulator", "/game/prologue, /game/new, simulador"),
],
"p5.py": [
 ("Assim, um trabalhador atrasado, cujo prazo expirou e foi tomado por outro, não consegue\n        publicar nada.", "Assim, um trabalhador atrasado não consegue publicar."),
 ("No meio de julho, o\n        DeepSeek virou primário e a criação ficou imersiva.", ""),
 ("Mundo vivo: Codex, eventos, regras, contexto", "Mundo vivo: Codex, eventos e regras"),
 ("Progressão, economia, playtest, multi-provider", "Progressão, playtest, multi-provider"),
],
}
for fn, rs in reps.items():
    s = open(fn, encoding="utf-8").read()
    for a, b in rs:
        assert a in s, (fn, a[:50])
        s = s.replace(a, b, 1)
    open(fn, "w", encoding="utf-8").write(s)
print("ok")
