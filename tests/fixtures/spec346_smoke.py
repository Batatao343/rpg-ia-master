"""SPEC-346: textos REAIS do smoke de 27/10 (DeepSeek) usados como respostas simuladas da LLM.

Nenhum trecho é inventado: são as frases que escaparam do filtro e motivaram R12-R15.
"""

# Trechos da prosa por rodada que vazaram aritmética/jargão do motor (itens 4/5).
LEAKS = {
    "forca_vs_esquiva": "Sua lâmina corta o ar com força de 23 contra a esquiva de 13. Sete pontos de vigor se esvaem do goblin.",
    "seta_parenteses": "O goblin cambaleia (3 → 0) e solta a adaga.",
    "esquiva_parenteses": "O golpe resvala na guarda (14 contra Esquiva 14) e arranha o couro.",
    "critico": "Um crítico de 5 contra 12 que rasga 16 de vitalidade abre o flanco da criatura.",
    "folegos": "O corte desce, tirando-lhe três fôlegos antes que ela recue.",
}

# Texto com hifenização escondida (U+00AD + U+2011), do Ysolde t5.
SOFT_HYPHEN = "A lâmina que desferi­‑o rasga o ar."

# O resumo que a LLM devolveria contradizendo o motor (saqueador morto "sobrevive e foge").
CONTRADICTION = "O Saqueador de Barba de Cobre sobrevive e foge pela mata, ainda rindo."

# Desfechos do smoke que hoje saíam como template/bullets.
BRANNOC_T8_OLD = (
    "Saqueador de Barba de Cobre perde os sentidos.\n\nMaça de Ferro (incomum) e +12 de ouro"
)
YSOLDE_T7_OLD = (
    "⚔️ • primeira criatura hostil que surgir na galeria: ganha condição cego\n"
    "• Ysolde: ganha condição cego\n"
    "• Ysolde executa sua Última Ação.\n\n☠️ Você tomba..."
)

# Resumo bom da LLM (sem números), usado nos testes de chamada única.
GOOD_SUMMARY = (
    "O Saqueador de Barba de Cobre cambaleia e perde os sentidos. "
    "A Espada Gasta ainda pinga enquanto você recupera o fôlego."
)
