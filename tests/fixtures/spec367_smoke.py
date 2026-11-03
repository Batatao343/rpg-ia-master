"""SPEC-367 R17: narração real da compra do smoke 5 (staging) e um texto correto escrito à mão."""

from __future__ import annotations

ANTES, PRECO, DEPOIS = 50, 45, 5
ALLOWED = {ANTES, PRECO, DEPOIS}

# Trecho real: "últimas moedas" com saldo 5 > 0 (o 45 era o preço certo, a afirmação é falsa).
SMOKE_TEXT = (
    "Você entrega as últimas 45 moedas ao mercador, que as pesa na palma antes de "
    "empurrar o Traje Branco sobre o balcão."
)
CORRECT_TEXT = "Você conta 45 moedas sobre o balcão; restam 5 na bolsa."

BENIGN = [
    "A forja ronca ao fundo e o ouro tilinta na bancada.",
    "O mercador ergue a última Carta da prateleira e a entrega sem cerimônia.",
    "Você conta 45 moedas sobre o balcão.",
    "Restam 5 moedas na bolsa, e o frio de Skallgard entra pela porta.",
    "O mercador sorri: cinquenta moedas era o que você carregava, quarenta e cinco ficam com ele.",
    "Uma bolsa de couro pesa no cinto, e o brilho do ouro some na penumbra.",
    "Ele pesa cada moeda com desconfiança, depois assente.",
    "O trato está feito; a rua lá fora cheira a ferro e chuva.",
]
