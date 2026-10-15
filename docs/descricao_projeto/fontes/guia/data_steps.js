/* ===== Passo-a-passo guiados (destacam nós no diagrama associado) ===== */
const STEPPERS = {
  travel: {
    graph: 'turn',
    steps: [
      {t: 'O jogador escreve', hi: [], h: `Herói de nível 2 em Nova Arcádia digita <b>"Vou para a Floresta Cinzenta"</b>. O cliente gera um <code>action_id</code> (UUID), guarda a ação pendente no <code>localStorage</code> e chama <code>POST /game/action/stream</code>.`},
      {t: 'Borda da API', hi: [], h: `Middlewares de sessão, correlação e rate-limit. <code>_execute_action</code> pega o lock do jogo, carrega o save (migrando o schema se for antigo), confere se esse <code>action_id</code> já foi processado (se sim, devolve a resposta sem rodar nada) e barra memorial/arquivado/queda pendente com 409. Acrescenta a fala como <code>HumanMessage</code> (mantém as últimas 20).`},
      {t: 'START → action_guard', hi: ['START', 'guard'], path: [['START', 'guard']], h: `O gate do START vê que o herói não está morto nem arquivado. O <b>action_guard</b> classifica o jogador como <i>active</i> e grava o <code>turn_baseline</code>: ouro, XP, inventário e quests <b>antes</b> do turno. É assim que o recibo será calculado depois — por diferença, não por texto da IA.`},
      {t: 'turn_prepare', hi: ['prep'], path: [['guard', 'prep']], h: `<code>turn_count</code> 17 → 18 e <code>session_action_count</code> + 1. O contador avança exatamente uma vez por turno.`},
      {t: 'campaign_manager', hi: ['cm'], path: [['prep', 'cm']], h: `Precisa replanejar? Faz 5 turnos desde o último plano e ainda há beats — devolve o plano existente <b>sem chamar a IA</b>. (O replanejamento por troca de região acontece no turno seguinte, marcado pelo próprio storyteller.)`},
      {t: 'dm_router — atalho sem IA', hi: ['router'], path: [['cm', 'router']], h: `A frase casa a regex de viagem explícita ("vou para") → rota <b>STORY</b> sem gastar a chamada CLASSIFY. O router devolve o payload completo zerando transitórios antigos (alvo de combate, NPC ativo, fonte de loot).`},
      {t: 'dispatch → storyteller', hi: ['dispatch', 'story'], path: [['router', 'dispatch'], ['dispatch', 'story']], h: `Antes da IA, Python faz o trabalho pesado: resolve o destino no mapa conectado, calcula o custo em períodos <b>antes</b> de mover, aplica a viagem (fog of war, relógio, clima), avança facções, sorteia achado de primeira visita e limpa a cena de NPCs ("ninguém teleporta junto"). Sorteio de encontro: nenhum combate; o simulador de mundo gera um rumor.`},
      {t: 'storyteller — a IA narra e propõe', hi: ['story'], h: `Uma chamada FAST com <code>StoryUpdate</code>: narrativa + propostas (NPC "Guarda-florestal Ilse", eventos, quests, itens). O motor valida tudo: itens só do catálogo, ouro narrado reconciliado com o saldo real, NPC novo gerado e colocado em cena. <code>archive_due=True</code> porque houve viagem.`},
      {t: 'archivist', hi: ['arch'], path: [['story', 'arch']], h: `Processa eventos pendentes (nenhum). Como <code>archive_due</code>, chama SMART <code>MemoryUpdate</code>: novo resumo (≤1200 chars, ancorado no mapa e no inventário), fatos livres como <i>inference / speculative</i>, gravados no FAISS da sessão com metadados.`},
      {t: 'turn_finalizer', hi: ['fin', 'END'], path: [['arch', 'fin'], ['fin', 'END']], h: `Revalida a prosa contra a evidência e calcula o recibo: se a chegada achou um baú, aparece <b>[RESULTADO] +N ouro</b>, derivado do delta real.`},
      {t: 'De volta à API', hi: [], h: `Arte (cue de primeira aparição do NPC), marca o <code>action_id</code> como processado, decide checkpoint (a cada 10 turnos ou ao entrar em zona segura), grava histórico estável, salva de forma atômica (temp + fsync + replace) e escreve uma linha JSON <code>rpg.turn</code> com rota, latência e custo. O SSE envia <code>visual</code>, a narração fatiada em pedaços de 80 caracteres e o <code>state</code>.`},
    ],
  },
  ambush: {
    graph: 'turn',
    steps: [
      {t: 'Mesmo comando de viagem', hi: ['story'], path: [['dispatch', 'story']], h: `Agora o sorteio de encontro (<code>check_encounter</code>) dispara. Teste de percepção (d20 + Mente + clima/luz vs CD 8 + 2×perigo) decide quem foi surpreendido; o tipo sorteado é <b>combat</b>.`},
      {t: 'Sem narrador exploratório', hi: ['story', 'combat'], path: [['story', 'combat']], h: `O storyteller retorna IMEDIATAMENTE com <code>SystemMessage("COMBAT START ...")</code>, alvo, origem causal (<code>travel_encounter</code>) e <code>next="combat_agent"</code>. Nenhuma chamada FAST é gasta narrando a viagem.`},
      {t: 'combat_agent prepara e resolve', hi: ['combat'], h: `Spawn de inimigos (CLASSIFY + bestiário), aliados de cena, orçamento de encontro, cena com zonas em Python, e já resolve a primeira rodada. Herói nível ≤2 com vida cheia ganha a iniciativa da 1ª rodada mesmo surpreendido.`},
      {t: 'Um único response', hi: ['arch', 'fin'], path: [['combat', 'arch'], ['arch', 'fin']], h: `O jogador recebe no mesmo turno a chegada e o primeiro round. Daqui em diante, todo input vira COMBAT pelo gate do router; viajar vira tentativa de fuga.`},
    ],
  },
  npcnone: {
    graph: 'turn',
    steps: [
      {t: 'Pedido de conversa sem ninguém', hi: ['router'], h: `"Pergunto ao taverneiro sobre trabalho" — mas não há NPC em cena. O router classifica NPC.`},
      {t: 'npc_actor delega', hi: ['npc', 'story'], path: [['dispatch', 'npc'], ['npc', 'story']], h: `Sem alvo e sem candidato: <code>{next: "storyteller", npc_fallback_hint}</code>. A resposta seca "Ninguém responde." foi aposentada.`},
      {t: 'O narrador cria a ausência + gancho', hi: ['story'], h: `<code>build_social_direction</code> escolhe a conexão adjacente de <b>menor perigo</b> e sugere um destino concreto; o objetivo público nunca copia beats privados.`},
    ],
  },
  cascade: {
    graph: 'events',
    steps: [
      {t: 'A IA propõe uma morte', hi: ['llm'], h: `Na narração, o storyteller propõe <code>npc_killed</code> para o líder de facção Valerius.`},
      {t: 'Pré-validação', hi: ['pre', 'pend'], path: [['llm', 'pre'], ['pre', 'pend']], h: `Válida → entra em <code>pending_world_events</code>. Se fosse inválida, TODO o payload livre iria para quarentena e a prosa seria substituída.`},
      {t: 'Validação canônica no arquivista', hi: ['proc', 'val', 'log'], path: [['pend', 'proc'], ['proc', 'val'], ['val', 'log']], h: `O alvo existe em <code>entities.json</code>, é NPC e está vivo → <code>GameEvent</code> com uuid e turno.`},
      {t: 'Projeção', hi: ['proj'], path: [['log', 'proj']], h: `<code>apply_event</code> marca <code>alive=False</code>.`},
      {t: 'Cascata de regras', hi: ['rules', 'log'], path: [['proj', 'rules'], ['rules', 'log']], h: `<code>rule_faction_leader_death</code>: Valerius tem o componente <code>power_vacuum_trigger</code> → Legião de Ferro perde 50 de estabilidade → emite <code>location_control_changed</code> (Mão Sombria ocupa Nova Arcádia). Em profundidade 1: <code>rule_control_change_ripple</code> (+5 ao novo controlador) e, se for porto, bloqueio de rotas. Profundidade 2 para.`},
      {t: 'Crônica, memória e contexto', hi: ['chron', 'mem', 'ctx'], path: [['log', 'chron'], ['log', 'mem'], ['proj', 'ctx']], h: `Milestone na crônica; fato <i>canonical_event / confirmed</i> no FAISS; e nos próximos turnos o bloco de estado mostra a mudança de controle com impacto máximo — "o ESTADO ATUAL vence o lore".`},
    ],
  },
  magda: {
    graph: 'memory',
    steps: [
      {t: 'Turno 12: conversa', hi: ['turn'], h: `O jogador pergunta à Velha Magda "Quem é você de verdade?". O npc_actor monta contexto com a memória vetorial DESTA NPC.`},
      {t: 'Fato observável, não a opinião da IA', hi: ['prov'], path: [['turn', 'prov']], h: `Em vez do <code>memory_update</code> livre, grava: <i>"Turno 12: o jogador disse ...; Velha Magda respondeu ..."</i> com <code>provenance="npc_claim"</code> → <b>reported</b>.`},
      {t: 'Validação e escrita física', hi: ['valid', 'npcm', 'ledger'], path: [['prov', 'valid'], ['valid', 'npcm'], ['valid', 'ledger']], h: `<code>add_npc_memory</code> no índice pinado ao provider. Só se o write físico der certo o mesmo registro é espelhado no ledger <code>memory_facts</code>. Falhou → fila <code>pending_npc_memory</code>. A política <code>canonical_only</code> impede o arquivista de transformar a conversa em fato global.`},
      {t: 'Turno 14: volta ao prompt', hi: ['ctx', 'prompt'], path: [['npcm', 'ctx'], ['ledger', 'ctx'], ['ctx', 'prompt']], h: `Novo pedido à Magda: um vetor, leitura paralela de lore/sessão/NPC, e a linha volta rotulada <code>[RELATO | npc_claim | fonte npc:velha_magda | turno 12]</code>. Se contivesse "pacto com Daruun" sem o segredo revelado, seria descartada.`},
    ],
  },
  dying: {
    graph: 'death',
    steps: [
      {t: 'Vitalidade 0 não é morte', hi: ['active'], h: `O herói chega a 0 de Vitalidade mas continua: o excedente de dano vira Ferimento leve, grave ou crítico conforme o Corpo.`},
      {t: 'O último crítico', hi: ['crit', 'last'], path: [['active', 'crit'], ['crit', 'last']], h: `Encheu o último espaço crítico: <b>Última Ação</b> fora de ordem, com Vantagem extrema, ignorando custos.`},
      {t: 'Estado Terminal', hi: ['term'], path: [['last', 'term']], h: `Sem aliado capaz: morte imediata. Com aliado: 2d10 + Mente do ajudante vs CD 12, depois 15. Kit/Médico → 3d10 mantém 2.`},
      {t: 'Se sobrevive', hi: ['scar'], path: [['term', 'scar']], h: `Reanima (metade da Vitalidade com kit, 1 se improvisado) e recebe Cicatriz obrigatória. O combate segue.`},
      {t: 'Se morre', hi: ['pend', 'modal'], path: [['term', 'pend'], ['pend', 'modal']], h: `<code>death_pending=True</code>, evento <code>player_downed</code>, sem loot. Grafo e API recusam novos turnos até a escolha.`},
      {t: 'Continuar', hi: ['restore'], path: [['modal', 'restore']], h: `Restaura o checkpoint e a memória FAISS daquele ponto; <code>timeline_epoch</code> sobe; o histórico de mortes permanece. No Postgres, <code>restore_effects</code> descarta memória/jobs/arte da linha do tempo abandonada.`},
      {t: 'Ou aceitar', hi: ['memorial'], path: [['modal', 'memorial']], h: `Memorial: <code>game_over</code>, evento <code>player_died</code>, milestone. Sem permadeath imposto — o fim é uma escolha.`},
    ],
  },
};

/* ===== Quiz ===== */
const QUIZ = {
  q1: {q: 'Quem decide se um ataque acerta?', o: ['O modelo de linguagem, lendo a cena', 'Código Python: 2d10 + Virtude contra a Esquiva', 'Um sorteio feito pelo frontend'], a: 1, e: 'Princípio central: a IA identifica a intenção e narra; dados, dano, Ferimentos, economia e XP são resolvidos em código determinístico.'},
  q2: {q: 'Por que todo nó com structured output precisa de um guard isinstance?', o: ['Porque o Pydantic é lento', 'Porque, esgotados os provedores, o RoutedLLM devolve AIMessage em vez do modelo', 'Porque o MockLLM devolve strings'], a: 1, e: 'O RoutedLLM nunca levanta exceção: no último recurso devolve AIMessage(""). Acessar resultado.campo sem checar o tipo quebraria o turno.'},
  q3: {q: 'Um turno de exploração em cidade sem evento costuma custar quantas chamadas de IA?', o: ['Nenhuma', 'Cerca de duas (router CLASSIFY + narrador FAST)', 'Sete, uma por agente'], a: 1, e: 'O campaign_manager só replaneja a cada ~15 turnos e o arquivista tem cadência; viagem/descanso nem chamam o router.'},
  q4: {q: 'Qual a confiança de um fato vindo da fala de um NPC?', o: ['confirmed', 'reported', 'speculative'], a: 1, e: 'npc_claim → reported. Só fonte mecânica aplicável (canonical_event) é confirmed; inferência livre é speculative.'},
  q5: {q: 'O que acontece se uma única proposta de evento da IA for inválida?', o: ['Só ela é descartada', 'Todo o payload livre daquela resposta vai para quarentena e a prosa é trocada', 'O turno inteiro falha com erro 500'], a: 1, e: 'Política atômica: a prosa que afirmava a mudança não pode ir ao jogador se o motor vai recusar a mudança.'},
  q6: {q: 'No perfil Postgres, quando um fato de memória passa a existir?', o: ['Assim que o arquivista o gera', 'Só se o turno commitou — ele é escrito no flush do outbox dentro da transação', 'Quando o worker termina o embedding'], a: 1, e: 'TurnEffects acumula intenções; commit_game faz flush na mesma transação. O vetor vem depois (job embed_memory), mas o fato bruto já é canônico.'},
  q7: {q: 'Por que a matriz A/B usa as mesmas seeds, níveis e tetos?', o: ['Para economizar dinheiro', 'Para que a diferença entre A e B seja causada pelas correções e não pelo acaso', 'Porque o DeepSeek exige'], a: 1, e: 'Protocolo pareado: A mede, specs corrigem, B repete exatamente — 12 violações error em A, zero em B.'},
  q8: {q: 'O que o benchmark A/B do Project Index concluiu?', o: ['O índice reduziu custo em 8/8', 'Mesma precisão, mas mais chamadas, bytes e tempo — índice saiu do fluxo padrão', 'O índice piorou a precisão'], a: 1, e: 'Localização empatou 16/16; com índice: 0/8 vitórias de custo, medianas piores. Fica só para consultas explícitas.'},
};
