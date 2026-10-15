# As Cinco Posturas diante do Abismo — guia narrativo das classes

> Companheiro criativo de [CLASSES.md](CLASSES.md) (que guarda números e mecânica).
> Este documento é sobre **história**: quem é cada classe, como se parece, que
> fantasia entrega e que campanhas ela puxa.
>
> Contexto do mundo: Valoria é o que sobrou depois da queda. O **Abismo** — a entropia
> que desfaz todas as coisas — pressiona por baixo de tudo. Nenhuma das cinco classes
> é uma profissão: cada uma é uma **resposta filosófica** ao Abismo. Elas não se
> definem pelo que fazem, e sim por **como encaram o fim**: quem o ama, quem negocia,
> quem trabalha junto, quem o manipula por uma ferramenta, quem o nega até o último
> fôlego. Duas mecânicas costuram todas: a **Entropia** (o poder que o Abismo empresta
> no calor da luta) e a **Carga do Abismo** (o preço que ele cobra depois, devagar).

---

## Devoto do Abismo
*"Vocês seguram a linha com medo. Eu seguro porque quero que ele me escolha primeiro."*

**Postura: ama.** O Devoto não teme o Abismo — o deseja. Onde os outros veem o fim, ele
vê um amante que virá buscá-lo, e faz questão de estar na frente da fila. É o tanque de
Valoria: quanto mais apanha, mais **Entropia** acumula, e mais irresistível fica sua
provocação (o Abismo quer quem o corteja). O preço é a **Insônia** — quem ama o fim não
descansa direito; um aliado teimoso ao lado ajuda a passar a noite.

**Visual.** Armadura remendada, marcas rituais na pele, um sorriso que assusta mais que
qualquer grito. Anda na direção do perigo com a calma de quem vai encontrar alguém.

**Subclasses.** *O Consagrado* (ritualiza o amor, marca o corpo antes da luta) ·
*O Zeloso* (amor possessivo, puxa aggro por ciúme) · *O Enlutado* (amou quem o Abismo
levou; tom melancólico).

**Campanha.** Proteger uma cidade que o teme tanto quanto o precisa; caçar o que levou
alguém que ele amava; decidir, no clímax, se abre ou fecha o portão.

---

## Sangromante
*"Tudo tem preço. Eu só pago à vista."*

**Postura: negocia.** O Sangromante trata o Abismo como um credor e paga em carne. Cada
gota de **auto-dano** deliberado vira Entropia de sangue, combustível para golpes de
pico devastadores. Mas ser acertado faz esse sangue **vazar** (a regra `blood_leak`), e
os picos deixam **Cicatriz** — reduzem o HP máximo para sempre. É a classe da decisão
com custo real: poder agora, corpo menor depois.

**Visual.** Cicatrizes exibidas como credencial ou escondidas como vergonha, dependendo
da subclasse. Lâminas curtas, roupas manchadas, olhos de quem já fez as contas.

**Subclasses.** *O Exposto* (faz espetáculo da dor; a cicatriz é troféu) · *O Avaro*
(acumula sangue para um único golpe) · *O Silencioso* (corte exato, economia de dor).

**Campanha.** Uma dívida velha com alguém — ou com o próprio Abismo — que cobra juros;
a busca por um jeito de pagar sem sangrar; o momento em que o corpo não aguenta mais.

---

## Corruptor
*"Eu não trago a ruína. Só chego mais cedo."*

**Postura: trabalha junto.** O Corruptor não luta contra a entropia: colabora com ela.
Toda coisa que **apodrece por perto** o alimenta de Entropia (`on_decay_nearby`), e seu
**domínio** (a subclasse) define o que conta como decadência — carne, alma ou metal.
É controle e dano-ao-longo-do-tempo: envenena, corrói, espera. O preço é a
**Transformação** — quanto mais Carga, mais o corpo/mente cede ao que ele espalha.

**Visual.** Fungos, esporos, ferrugem viva; um cheiro que chega antes dele. Não parece
uma pessoa doente — parece uma pessoa **em acordo** com a doença.

**Subclasses.** *Biologia* (carne que apodrece) · *Alma* (vontade que rui) ·
*Inorgânica* (metal e pedra que cedem).

**Campanha.** Acelerar a queda de algo que já morre (uma fortaleza, uma ordem, um
tirano); ser confundido com a praga que só acompanha; o dilema de parar antes de virar
aquilo que espalha.

---

## Arcanista Cinzento
*"A ferramenta segura o que a mão não deveria tocar."*

**Postura: manipula.** O Arcanista não paga com o corpo nem ama o fim: usa um
**instrumento** para tocar o Abismo à distância. Canalizar (`on_channel`) gera Entropia
para a próxima descarga — mas segurar demais sem vazão faz a **caldeira estourar**
(`boiler`, auto-dano). E se a Carga sobe e o instrumento some, vem a **Dependência**: o
custo dispara. Poder frio, calculado, sempre à beira de escapar do controle.

**Visual.** Lentes, condutores, um bastão que zumbe. Roupa acadêmica gasta na estrada.
Frágil de perto, devastador de longe — posicionamento é a armadura.

**Subclasses.** *O Calibrado* (segurança acima de potência) · *O Descoberto* (toca o
éter sem instrumento; alto dano, alto risco) · *O Improvisador* (monta a ferramenta na
hora, com sucata).

**Campanha.** Recuperar/proteger um instrumento de uma era que ninguém sabe mais
construir; a tentação de largar a ferramenta e tocar o éter cru; o dia em que a
caldeira decide por ele.

---

## Médico de Campo
*"Enquanto eu respirar, você respira."*

**Postura: nega.** O Médico é a recusa teimosa: mantém vivo o que o Abismo quer levar.
Acumula Entropia quando um **aliado sofre** (`on_ally_suffer`) e a gasta para mantê-lo
de pé — e é a **única** classe que pode **purgar a Carga do Abismo de um companheiro**.
Seu preço é o mais cruel: a **Recidiva** é oculta (o HUD não mostra o número), e um dia
estoura sozinha num colapso. Quem cuida de todos raramente conta a própria conta.

**Visual.** Avental manchado, serra, agulha, torniquetes. A calma de quem já viu pior e
segue trabalhando no meio dos gritos. Sem magia, sem milagre — método.

**Subclasses.** *Cirurgião de Trincheira* (intervenção imediata sob fogo) · *Boticário*
(compostos, buffs e a purga da Carga alheia) · *Cirurgião de Ferro* (próteses e reforço
físico de aliados).

**Campanha.** Manter viva uma coluna de refugiados através da ruína; a busca por uma
cura que o mundo diz não existir; o colapso oculto que finalmente o alcança — e quem
estará lá para segurá-lo.

---

> **Nota de design.** As dez classes antigas de Valoria foram reaproveitadas nas cinco
> Posturas (ver [CLASSES.md](CLASSES.md) § 6 — migração). O guia narrativo das dez
> vidas anteriores vive no histórico do git.
