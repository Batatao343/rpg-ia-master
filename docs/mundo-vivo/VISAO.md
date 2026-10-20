# Mundo vivo — visão, diagnóstico e decisões do dono (2026-10-20)

Fonte das specs da iniciativa "mundo vivo". Detalhe técnico mora em cada spec.

## Diagnóstico (auditoria de 2026-10-19/20, 5 frentes)

O motor tem muitos sistemas, mas pouco conectados. O mundo **reage** ao jogador
e quase não **vive** sozinho. Várias peças estão prontas, mas desligadas ou sem
chamador. Os playtests mostram prosa boa, mas viagem só troca o cenário e NPCs e
fações não se movem entre turnos.

- **Tempo:** relógio, fações, clima e pulso do mundo só andam em viagem e
  descanso (`world_utils.advance_clock`, `agents/storyteller.py` ~532-796).
- **Fações:** 19 fações, só com progresso linear. Não guerreiam nem se aliam, e
  o jogador não tem contra-jogo. São só 6 `world_rules`, com 1 tipo de
  componente.
- **Locais:** não têm estado próprio (cerco, festa, praga, escassez). Não há
  calendário. Há só 2 baús em 35 locais, e o achado ambiental só ocorre na 1ª
  visita.
- **Quests:** nascem do texto do LLM, não do estado do mundo. Não têm prazo.
- **Combate:**
  - Cerca de 87% dos combates (lacaio/padrão) acontecem em "sala vazia"
    (`fallback_safe_scene`).
  - Os perfis táticos só fazem atacar, fugir ou se render.
  - Nenhum inimigo tem vulnerabilidade, sentidos ou hábitos.
  - `register_flee_alert` (fuga → retorno com reforços) não tem chamador, e
    `fire_reinforcement` também não.
  - O loot é genérico, não vem do inimigo. Rendição não gera prisioneiro.
- **NPCs:**
  - SPEC-215 (propagação de notícias) está `off` em staging e prod.
  - Dos traços, só o contexto `persuasao` é usado.
  - A relação com o NPC não mexe em preço nem acesso.
  - A reputação é ±12 decidida por palavra-chave.
  - NPCs não têm agenda nem vida off-screen.
  - Companheiros são só ficha de combate.
- **Narração:**
  - Clima local, perigo e saídas não chegam ao prompt (só o clima global).
  - As opções de ação são inventadas pelo LLM, não vêm da cena.
  - Rumores somem no turno seguinte.
  - Arte dinâmica `off`, sem variantes de noite ou clima, e sem som.
- **Lore sem mecânica:** raça (só ficha), Código de Ferro (0 referências no
  código), Éter/Abismo regional, religiões, crafting (6 receitas) e segredos
  (4).

## Decisões do dono

1. **Tudo importa:** o mundo anda sozinho, lembra do jogador, tem cenas táteis
   e companheiros com alma.
2. **Tempo:** continua passando só ao **dormir e viajar**. O mundo simula **1x
   por dia de jogo virado**. Nada de custo de tempo por ação.
3. **Diretor de mundo:**
   - Um **motor determinístico** rola eventos com modificadores, propõe
     eventos/crises e move NPCs (agenda, viagem, troca de lado, morte
     off-screen).
   - Uma **LLM ocasional** (≤ 1 chamada por dia de jogo) só **narra** o que o
     motor decidiu. A LLM nunca decide.
   - O motor tem de se comportar como um mundo, não como uma máquina de crises.
4. **Ritmo:** ecossistema mais curva de tensão.
   - Cada região tem pressões (ex.: fome, guerra, praga, fé) que sobem e descem
     por causas, com evento só ao cruzar um limiar.
   - Por cima, um orçamento global de tensão (calmo → tensão → crise →
     recuperação) limita as crises simultâneas.
5. **Dureza:** o mundo é duro, mas telegrafado. Quest com prazo falha, NPC
   querido pode morrer, cidade pode cair, sempre com aviso antes (rumor,
   sinal).
6. **Reputação em 4 níveis:** por NPC, por fação, por local (fama) e por
   raça/origem (reação conforme a lore).
7. **Visibilidade:** rótulos vagos ("desconfiado / amigável / leal") e
   mudanças ("Brenna não gostou disso"), sem números.
8. **Companheiros:** autonomia alta, com aviso. Opinam, discordam e têm missão
   pessoal. Com aprovação em queda, avisam e depois saem (ou traem, se o traço
   permitir).
9. **Ordem:** Onda 0 (religações) → **C. Sociedade viva** → **A. Mundo
   autônomo** → **D. Presença e sentidos** → **B. Combate vivo**. Os quatro
   pilares serão feitos.

## Decisões detalhadas (entrevista, rodadas 4–9)

**Regra de ouro (dono):** o jogador **não sabe nada que não tenha visto ou
ouvido**. Toda notícia chega por testemunho ou pela propagação entre NPCs
(SPEC-215). Isso inclui narração, diálogo, UI e mapa. Não há onisciência nem em
aba de rumores.

### C. Sociedade viva
- **NPCs simulados off-screen:** os conhecidos pelo jogador mais os
  importantes do grafo (líderes, NPCs-chave), na faixa de ~40–60.
- **Morte off-screen:** pode atingir **qualquer um, inclusive a party**. Basta
  o companheiro estar afastado e num lugar perigoso. Toda morte é telegrafada
  (rumor ou pedido de ajuda) e o jogador tem chance de intervir.
- **Raça/origem:** fiel à lore e com efeito (atitude inicial, preço, raras
  recusas). A reputação pessoal supera o preconceito.
- **Crime e lei por região:**
  - Cada região tem sua lei (ex.: Código de Ferro em Nova Arcádia, outras
    soltas).
  - Crime testemunhado vira notoriedade, que traz guardas, caçadores de
    recompensa e preço pela cabeça.
  - Dá para pagar multa ou fugir.
- **Relação alta destrava:** preço e estoque raro, informação e segredos,
  favores e ajuda (esconder, emprestar, interceder) e romance/vínculo com arco
  próprio. O romance é **fade-to-black**.
- **Companheiros falam:** em escolhas marcantes (detectadas em Python), ao
  descansar e quando o jogador se dirige a eles. Sem chamada LLM extra: entra
  no prompt do narrador.
- **Fações com patente:** o jogador pode entrar, subir de patente, sair ou
  trair. Aceitam membro só as fações que fazem sentido na lore; a
  classificação das 19 vai na spec, para revisão.

### A. Mundo autônomo
- **Pressões regionais:** guerra/conflito, fome/escassez, praga/doença
  (espalha pelas conexões) e Éter/Abismo (corrupção regional que mexe em
  clima, criaturas e eventos).
- **Calendário:** estações (passos de montanha fecham, deserto seca) e festas
  e datas da lore (feriados regionais e religiosos, aniversários de eras).
  **Sem** lua e **sem** dia de mercado.
- **Mudanças no mapa:** permanentes, mas recuperáveis. Cidade cai, fação é
  destruída, local vira ruína, e o mundo pode se reconstruir com o tempo ou
  com a ação do jogador.

### D. Presença e sentidos
- **Luz:**
  - Ganha **níveis** (breu, penumbra, fraca, clara) e fontes de cena
    (fogueira, cristais de Éter).
  - Vira **tática**: luz revela o portador e piora a furtividade, apagar
    esconde, criaturas são atraídas ou repelidas pela luz.
  - Inimigos ganham **sentidos** (visão no escuro, faro, cego-que-ouve).
  - Fonte de luz **sem** duração ou combustível (dono não escolheu).
- **Áudio:** packs **CC0 curados** por bioma, período e tensão. O dono aprova a
  lista.
- **Arte:** tint/filtro por período mais overlays animados (chuva, neve,
  neblina, névoa do Abismo), sem gerar imagem.
- **Opções de ação:** ganchos reais da cena escolhidos em Python (saídas, NPCs
  presentes, objetos, quest), mais a ação livre de sempre.

### B. Combate vivo
- **Natureza do dano:** ~6 naturezas (corte, impacto, perfuração, fogo,
  sagrado/luz, Éter/Abismo) em cartas e itens. Cada criatura tem 1–2 fraquezas
  e resistências pela lore, descobertas pelo bestiário.
- **Cena preparada por LLM para TODO combate**, não só Elite/Chefe (+1
  chamada por combate, aceito).
- **Rendido ou nocauteado:** interrogar, poupar/soltar, entregar/vender,
  recrutar, ou levar como prisioneiro (escolta, resgate).
- **Saque:** partes de criatura que entram em receitas regionais (expande o
  crafting). Humanoide deixa o equipamento do seu tipo.

### Processo
- Playtest com LLM real: teto de **US$ 3/dia**, só campanhas curtas. Long-run
  de 200 turnos só no MockLLM.
- Reporte: push a cada marco (spec pousada, bloqueio de decisão) e resumo no
  fim do dia.
- SPEC-295 (Chefe no topo) já concluída em outra conversa.

## Onda 0 — religar o que já existe

1. SPEC-215: `RPG_NPC_KNOWLEDGE` em `shadow` → `on` no staging, medido por
   playtest.
2. Chamar `register_flee_alert` quando um inimigo foge (fuga → retorno com
   reforços).
3. Bloco de ambiente (clima local, período, perigo, luz, saídas) no
   storyteller, no `npc_actor` e na narração de combate.
4. Traços nos contextos de DC `comercio`, `intimidacao` e `insight`.
5. Persistir o pulso do mundo como `world.news` (últimos N), injetar no
   contexto e mostrar na UI.

## Restrições permanentes

- Mecânica em Python, determinística por seed. A LLM propõe ou narra, o motor
  aplica.
- "O mundo não escala com o herói."
- Sem regressão nas metas de letalidade da SPEC-285.
- Não onisciência: o jogador só vê o que o personagem saberia.
