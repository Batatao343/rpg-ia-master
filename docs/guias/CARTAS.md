# Guia de autoria de Cartas (SPEC-336)

Como a esteira cresce o acervo sem repetir cartas. Fonte das regras de máquina:
`services/card_lint.py` (lint), `services/card_effects.py` (gramática, `power_score`,
`render_card_text`), `data/cards/_roda_posturas.json`, `_glossario.json`,
`_orcamento.json`, `_lexico_valoria.txt`. Template: [`docs/templates/carta.json`](../templates/carta.json).

## A esteira

```
draft.py  ->  lint.py  ->  sim.py  ->  (curadoria) -> promote.py  -> data/cards/posturas/
 rascunho     regras      arena        voz: amostra     pool + _ondas.yaml
```

Tudo via `bash scripts/dev/py.sh scripts/cards/<passo>.py`. O rascunho (SMART, custa token)
só roda sob demanda do dono e com chave; sem chave devolve lote vazio. Gere ~2× o que quer
e corte. Cadência: **1 onda por mês**, >= +60 cartas de jogador e +20 de inimigo, cortes
permitidos; meta de 12 meses ~1 200. `painel.py` gera `docs/cartas/PAINEL.md`. Cada onda cria
no máximo **2 palavras-chave novas**, cada uma com >= 6 cartas na mesma onda (marque a
palavra no glossário com `"onda": N`). Revisão de voz do dono: **amostra de 20 %** (o
`promote.py` sorteia e registra em `_ondas.yaml`).

## Roda das Posturas (color pie de Valoria)

| Postura | Primário | Secundário | Nunca (vira ERRO no lint) |
|---|---|---|---|
| Devoto do Abismo | Vigília, provocar, dano ao ser atingido, Entropia por dor | Interromper, cura própria pequena | comprar muitas cartas, Esconder |
| Sangromante | Sacrifício, Sangria, Eco, dano alto barato | Ressoar, roubo de Vitalidade | Vigília grande, cura de aliado |
| Corruptor | Rachadura, Torpor, Fardo no inimigo, decadência por domínio | Marca do Abismo, controle de zona | cura, proteção a aliado |
| Arcanista Cinzento | Chamado, comprar/descartar, Vazão, dano em área | Ressoar, Guardar | Sacrifício, provocar |
| Médico de Campo | cura, purgar, Guardar, reduzir Carga de aliado | Torpor, estabilizar, comprar | dano alto, Rachadura |

Os limites numéricos ("muitas", "grande", "alto") estão em `_roda_posturas.json`
(`limites_kind`); ajuste lá, não no código.

## Raridade = complexidade

| Raridade | Regra | Distribuição por lote |
|---|---|---|
| comum | <= 1 efeito, <= 1 palavra-chave, uma interação | 50 % |
| incomum | <= 2 efeitos | 30 % |
| rara | livre dentro do orçamento; pode ser "espetada" | 15 % |
| abissal | custo explícito (Entropia/Vitalidade) e um efeito que quebra uma regra, com Exaurir | 5 % |

O **orçamento** (`power_score` na faixa de raridade x custo de Fôlego) é checado por
`budget_error`; a faixa vem de `_orcamento.json`. Mudança de poder = nova `versao`.

## Voz

- Nome: <= 4 palavras, PT-BR, sem anglicismo. Descrição: <= 140 caracteres, concreta, sensorial,
  de Valoria (Abismo, cinza, ferro, sangue, éter). **Nunca número na descrição** (o número vem
  de `render_card_text`). Termos proibidos em `[proibidos]` do léxico; sabor em `[valoria]`.
- Exemplo bom: "Cinza de fornalha fecha a ferida e pesa no braço de quem a abriu."
- Exemplo ruim: "Cura 3 de HP e dá debuff no inimigo" (número, anglicismo, nada de Valoria).

## Glossário

As 14 palavras-chave de Valoria estão em `data/cards/_glossario.json` (regra e sabor de cada
uma): Rachadura, Torpor, Sangria, Vigília, Marca do Abismo, Interromper, Sacrifício, Chamado,
Exaurir, Guardar, Eco, Ressoar, Fardo, Vazão. Só existe o que está no vocabulário fechado de
`card_effects` (kinds, gatilhos, condições, alvos). Proposta de palavra nova = nova onda + spec.

## Checklist do `momento`

Todo cartão novo traz `momento`: UMA frase "melhor jogada quando…", não exibida ao jogador.

1. Descreve uma situação de jogo (estado do alvo, da mão, do Fôlego), não a carta repetida.
2. É **distinto** de todos os momentos da mesma Postura (o lint compara e acusa duplicata).
3. Existe uma carta do baralho que, naquela situação, a torna a melhor jogada — se não existe,
   a carta é de enfeite: reescreva ou corte.
4. Sem número e sem nome de carta.

## Versão e corte

Mudar uma carta publicada = novo objeto com o mesmo `id` e `versao` + 1 (o motor lê a de maior
`versao`; saves guardam só o id). Regra de corte por `metrics.py`: pick rate < 5 % em >= 200
ofertas -> reescrever ou cortar; > 60 % -> nerf. Telemetria: eventos `cards.card_offered`,
`card_picked`, `card_played`, `card_exhausted`.
