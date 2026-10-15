# Valoria — Cenários Funcionais de Aceite

Estes cenários descrevem resultados esperados. Eles não determinam como o código deve ser estruturado.

---

## 1. Entrada em conflito

### Cenário 1 — Lado inicia claramente

**Dado** que o protagonista prepara uma emboscada e ataca antes de ser percebido  
**Quando** o conflito começa  
**Então** a party age primeiro automaticamente na primeira rodada  
**E** não há disputa de iniciativa.

### Cenário 2 — Confronto simultâneo

**Dado** que os dois lados percebem a ameaça ao mesmo tempo  
**Quando** o conflito começa  
**Então** ambos disputam iniciativa usando 2d10 e a maior Agilidade consciente do lado.

### Cenário 3 — Cena congelada

**Dado** que o conflito começou com uma ponte, uma alavanca e dois inimigos  
**Quando** a segunda rodada começa  
**Então** nenhuma LLM pode acrescentar uma porta secreta, um terceiro inimigo ou uma vantagem improvisada.

---

## 2. Preparação pela LLM

### Cenário 4 — Objeto coerente

**Dado** que a narrativa mostrou uma alavanca ligada a mecanismos sob o piso  
**Quando** a cena de combate é preparada  
**Então** a alavanca pode aparecer como objeto interativo  
**E** o jogador vê a interação “Ativar” e seu custo  
**Mas** não vê obrigatoriamente o efeito antes de utilizá-la.

### Cenário 5 — Objeto sem base narrativa

**Dado** que nada na cena sugere explosivos  
**Quando** a LLM prepara o encontro  
**Então** ela não deve inserir um barril explosivo apenas para criar uma opção tática.

### Cenário 6 — Catálogo fechado

**Dado** que a LLM descreve “o piso devora a sombra do inimigo”  
**Quando** o encontro é validado  
**Então** a consequência precisa corresponder a efeitos conhecidos, como dano, estado, alteração de terreno ou reposicionamento  
**E** texto livre não pode executar uma regra desconhecida.

### Cenário 7 — Provider inválido

**Dado** que um provider retorna uma preparação incompatível  
**Quando** a validação falha  
**Então** outro provider pode ser utilizado  
**E** o conflito não começa até existir uma preparação válida ou uma cena simplificada de fallback.

---

## 3. Bestiário e NPCs

### Cenário 8 — Seleção regional

**Dado** que a party está no Pântano da Melancolia  
**Quando** um encontro aleatório é preparado  
**Então** os inimigos são selecionados entre criaturas válidas para a região ou justificadas pelo evento.

### Cenário 9 — Comerciante atacado

**Dado** que a LLM criou anteriormente um comerciante nomeado  
**Quando** o jogador decide atacá-lo  
**Então** o NPC já possui ficha completa, cartas, recursos e perfil tático  
**E** não precisa ser improvisado durante o combate.

### Cenário 10 — Conhecimento persistente

**Dado** que o jogador já viu uma criatura usar “Mordida Putrefata”  
**Quando** encontra novamente o mesmo arquétipo  
**Então** essa carta começa revelada  
**E** cartas ainda não observadas permanecem ocultas.

---

## 4. Turnos e movimento

### Cenário 11 — Turno completo

**Dado** que é o turno do protagonista  
**Quando** ele joga  
**Então** pode realizar uma Pré-Ação, uma Ação e uma Pós-Ação, respeitando as regras de cada etapa.

### Cenário 12 — Dois movimentos

**Dado** que o protagonista começa Próximo  
**Quando** usa Pré-Ação para ficar Distante e Pós-Ação para ficar Separado  
**Então** percorre dois estágios no turno.

### Cenário 13 — Ataque corpo a corpo

**Dado** que o alvo está Próximo, mas não Engajado  
**Quando** o protagonista tenta um ataque corpo a corpo comum  
**Então** precisa primeiro Engajar ou utilizar uma carta que ignore essa exigência.

---

## 5. Ataques, críticos e Ruptura

### Cenário 14 — Ataque normal

**Dado** que o personagem usa uma arma de Força  
**Quando** ataca  
**Então** rola 2d10, soma Força e compara com Esquiva.

### Cenário 15 — Crítico por dupla

**Dado** que os dados mantidos são 7 e 7  
**Quando** o ataque é resolvido  
**Então** é acerto automático e o efeito principal é multiplicado por 2.

### Cenário 16 — Supercrítico

**Dado** que os dados mantidos são 10 e 10  
**Quando** o ataque é resolvido  
**Então** é acerto automático e o efeito principal é multiplicado por 3.

### Cenário 17 — Ruptura com falha

**Dado** que o jogador declarou Ruptura antes da rolagem  
**Quando** a ação falha  
**Então** a Carga do Abismo ainda é gerada  
**E** não pode afetar a própria ação que a gerou.

### Cenário 18 — Ruptura e Crítico

**Dado** que uma carta em Ruptura também obtém dados iguais  
**Quando** é resolvida  
**Então** o efeito de Ruptura e o Crítico se acumulam.

---

## 6. Reações

### Cenário 19 — Reação defensiva

**Dado** que um inimigo declara um ataque Defensável contra o protagonista  
**Quando** o protagonista possui uma carta de Reação válida  
**Então** pode utilizá-la antes da rolagem do ataque.

### Cenário 20 — Inimigo reage à reação

**Dado** que o protagonista utiliza uma Reação  
**E** o inimigo possui uma Reação com gatilho válido e Entropia suficiente  
**Quando** a cadeia continua  
**Então** o inimigo pode reagir  
**Desde que** ainda não tenha utilizado sua reação comum naquela cadeia.

### Cenário 21 — Limite da cadeia

**Dado** que vários personagens possuem reações válidas  
**Quando** uma ação inicia uma cadeia  
**Então** cada personagem pode utilizar no máximo uma reação comum  
**E** a cadeia termina quando todos passam ou não possuem reação válida.

### Cenário 22 — Ataques de oportunidade não limitados

**Dado** que o protagonista está Engajado com três inimigos  
**Quando** declara Fuga sem Desengajar  
**Então** os três inimigos podem realizar ataques de oportunidade  
**Mesmo que** já tenham utilizado uma reação comum na cadeia relevante.

---

## 7. Informação do inimigo

### Cenário 23 — Painel inicial

**Dado** que o combate começou  
**Então** o jogador vê Vitalidade, Esquiva, Proteção, Integridade, recursos visíveis, estados, posição e Engajamentos do inimigo.

### Cenário 24 — Carta oculta

**Dado** que o inimigo ainda não utilizou sua habilidade especial  
**Então** a carta não aparece no painel.

### Cenário 25 — Carta revelada

**Dado** que o inimigo usa sua habilidade especial  
**Quando** a carta é declarada  
**Então** ela é revelada antes da reação do jogador  
**E** permanece visível até o fim do combate  
**E** passa a ser conhecida no bestiário.

### Cenário 26 — Resistência descoberta

**Dado** que o jogador causa dano ígneo  
**Quando** a criatura reduz esse dano por Resistência  
**Então** o cálculo completo é exibido  
**E** a Resistência passa a ser conhecida.

---

## 8. Armadura e Ferimentos

### Cenário 27 — Dano excede Vitalidade

**Dado** que o alvo possui 3 Vitalidade  
**E** recebe 8 de dano final  
**Quando** o golpe é resolvido  
**Então** a Vitalidade cai a 0  
**E** o excedente 5 é comparado aos limites de Gravidade do alvo.

### Cenário 28 — Agravamento na mesma região

**Dado** que o personagem já possui um Ferimento Leve no braço direito  
**Quando** sofre outro Leve na mesma região  
**Então** o Ferimento se torna Grave em vez de criar dois registros independentes.

### Cenário 29 — Espaço cheio

**Dado** que todos os espaços Graves estão preenchidos  
**Quando** outro Ferimento Grave seria criado  
**Então** ele sobe para Crítico.

### Cenário 30 — Armadura Comprometida

**Dado** que a armadura chega a 0 Integridade  
**Então** mantém a Proteção básica e as penalidades  
**Mas** não pode gastar Integridade nem utilizar propriedades especiais.

---

## 9. Última Ação e morte

### Cenário 31 — Último Crítico

**Dado** que o personagem preenche seu último espaço Crítico  
**Quando** o Ferimento é aplicado  
**Então** realiza imediatamente a Última Ação  
**E** depois entra em Estado Terminal.

### Cenário 32 — Última Ação sem recursos

**Dado** que o personagem não possui Entropia suficiente  
**Quando** usa uma carta preparada na Última Ação  
**Então** pode utilizá-la sem pagar o recurso ausente  
**E** não cria Ferimentos adicionais por esse déficit.

### Cenário 33 — Sem aliado

**Dado** que o personagem entra em Estado Terminal  
**E** não existe aliado capaz de intervir  
**Então** ele morre imediatamente.

### Cenário 34 — Reanimação do Médico

**Dado** que um Médico de Campo possui kit com carga  
**Quando** intervém no personagem Terminal  
**Então** a reanimação é automática  
**E** o personagem retorna com metade da Vitalidade máxima.

### Cenário 35 — Cicatriz obrigatória

**Dado** que o personagem sobreviveu ao fluxo de Última Ação e Terminal  
**Quando** o conflito termina  
**Então** a LLM deve gerar uma Cicatriz com consequência negativa e habilidade relacionada.

---

## 10. Companheiros

### Cenário 36 — Ordem válida

**Dado** que o jogador ordena a um companheiro atacar um inimigo hostil  
**E** a ação não viola seus traços  
**Então** a ordem pode ser executada.

### Cenário 37 — Ordem moralmente proibida

**Dado** que um paladino possui a restrição absoluta de proteger inocentes  
**Quando** o jogador ordena que ele assassine um inocente  
**Então** a ordem é recusada  
**E** o jogador escolhe outra ação.

### Cenário 38 — Protagonista fora do combate

**Dado** que o protagonista fugiu, mas um companheiro continua consciente no conflito  
**Então** o jogador continua controlando a party.

---

## 11. Derrota, rendição e encerramento

### Cenário 39 — Golpe não letal

**Dado** que um ataque compatível reduz o inimigo ao estado de derrota  
**Quando** o atacante escolhe não matar  
**Então** o alvo fica inconsciente ou incapacitado.

### Cenário 40 — Rendição por perfil

**Dado** que o líder morreu e o perfil do inimigo prevê rendição  
**Quando** o gatilho é atendido  
**Então** ele se rende sem decisão da LLM.

### Cenário 41 — Objetivo concluído

**Dado** que o encontro possui o objetivo de fechar um portal  
**Quando** o portal é fechado  
**Então** o conflito pode terminar mesmo que existam inimigos vivos, se essa condição estava prevista.

---

## 12. Fuga e perseguição

### Cenário 42 — Fuga Engajada

**Dado** que o protagonista está Engajado  
**Quando** usa a Ação Fugir  
**Então** sofre ataques de oportunidade de todos os inimigos aptos  
**E** inicia a fuga se continuar capaz.

### Cenário 43 — Guardião não persegue

**Dado** que um guardião possui prioridade absoluta de proteger o portão  
**Quando** o protagonista foge para longe  
**Então** o guardião não abandona o posto para persegui-lo.

### Cenário 44 — Testes de Sorte

**Dado** que três companheiros fogem com o protagonista  
**Quando** rolam 2, 7 e 10  
**Então** existe uma Complicação, um resultado Neutro e uma Ajuda  
**E** Ajuda e Complicação se anulam  
**E** o teste principal é normal.

### Cenário 45 — Abandono

**Dado** que um companheiro gerou uma Complicação  
**Quando** o jogador decide deixá-lo para trás  
**Então** a Complicação é removida  
**E** o companheiro é separado  
**E** seu destino é simulado automaticamente  
**E** a decisão gera fatos relacionais para a narrativa posterior.

### Cenário 46 — Sacrifício voluntário

**Dado** que o companheiro possui o traço `se_sacrifica_pelo_grupo` em prioridade válida  
**Quando** os gatilhos ocorrem  
**Então** ele pode se oferecer para ficar  
**E** o jogador escolhe aceitar ou recusar.

### Cenário 47 — Reengajamento

**Dado** que o fugitivo está Pressionado  
**Quando** o perseguidor usa Pré-Ação para Engajar  
**Então** a perseguição termina  
**E** o combate normal retorna  
**E** o perseguidor pode atacar corpo a corpo com a Ação.

---

## 13. Abismo

### Cenário 48 — Evento preparado

**Dado** que a cena possui uma corrente enferrujada acima do salão  
**E** a LLM preparou um evento do Abismo associado  
**Quando** seus gatilhos e custo são atendidos  
**Então** o evento pode ser carregado sem chamada de LLM.

### Cenário 49 — Evento não preparado

**Dado** que não existe qualquer água, reservatório ou tubulação na cena  
**Quando** uma Carga é gasta  
**Então** o jogo não pode criar uma inundação do nada.

### Cenário 50 — Resultado protegido

**Dado** que uma ação já foi rolada e resolvida com sucesso  
**Quando** ocorre uma intervenção do Abismo depois  
**Então** ela pode alterar uma consequência posterior  
**Mas** não pode negar o sucesso já concluído.

---

## 14. Loot e retorno à LLM

### Cenário 51 — Loot antes da narrativa

**Dado** que o combate terminou  
**Quando** existem recompensas ou itens recuperáveis  
**Então** o fluxo de loot é concluído sem LLM  
**E** só depois o resumo é enviado à narrativa.

### Cenário 52 — Resumo canônico

**Dado** que um inimigo morreu, um companheiro foi capturado e uma ponte foi destruída  
**Quando** a LLM retoma a cena  
**Então** ela deve narrar a partir desses fatos  
**E** não pode transformar a morte em fuga, libertar o companheiro ou restaurar a ponte sem um novo acontecimento posterior.

---

## 15. Reprodução e consistência

### Cenário 53 — Mesma partida

**Dado** o mesmo estado inicial, a mesma seed e as mesmas escolhas  
**Quando** o conflito é reproduzido  
**Então** as rolagens, ações inimigas, eventos, Ferimentos, fuga e resultado final são iguais.

### Cenário 54 — Conhecimento não vaza

**Dado** que um inimigo possui três cartas ocultas  
**Quando** o combate começa  
**Então** nenhuma delas é mostrada ao jogador até ser utilizada ou previamente descoberta.
