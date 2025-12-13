# npc_data.py

NPC_DEFINITIONS = {
    # --- COMPANHEIROS (Lutam ao seu lado) ---
    "Lyra": {
        "role": "companion",
        "location": "Party", # Especial: Está sempre no grupo
        "persona": "Uma elfa ladina sarcástica e impaciente. Adora ouro, odeia autoridade. Fala gírias de rua e é pragmática.",
        "initial_relationship": 5,
        "combat_stats": { # Usado pelo Oracle no combate
            "hp": 18, "max_hp": 18, 
            "attack": 4, "defense": 14,
            "abilities": ["Tiro Preciso", "Ataque Furtivo"]
        },
        "intro": "Lyra afia sua adaga, olhando ao redor com tédio."
    },
    "Garrick": {
        "role": "companion",
        "location": "Party",
        "persona": "Um clérigo anão velho e resmungão. Cita escrituras sagradas (muitas vezes inventadas) e protege o grupo como um avô ranzinza.",
        "initial_relationship": 7,
        "combat_stats": {
            "hp": 24, "max_hp": 24,
            "attack": 2, "defense": 16,
            "abilities": ["Martelo da Justiça", "Cura Menor"]
        },
        "intro": "Garrick ajusta as correias da mochila, murmurando uma prece."
    },

    # --- NPCs SOCIAIS (Encontrados no mundo) ---
    "Sargento Borin": {
        "role": "npc",
        "location": "Estrada Real",
        "persona": "Um guarda corrupto e cansado. Quer suborno para evitar burocracia. Autoritário com fracos, covarde com fortes.",
        "initial_relationship": 3,
        "intro": "O Sargento bloqueia o caminho, batendo a lança no chão com impaciência."
    },
    "Elara a Sábia": {
        "role": "npc",
        "location": "Biblioteca Antiga",
        "persona": "Uma maga etérea e misteriosa. Fala por enigmas e metáforas. Sabe tudo sobre a Lore do mundo, mas cobra em segredos.",
        "initial_relationship": 5,
        "intro": "Elara flutua entre as estantes empoeiradas, sem tocar o chão."
    },
    "Grum": {
        "role": "npc",
        "location": "Taverna do Dragão",
        "persona": "Um meio-orc taverneiro de poucas palavras. Respeita quem bebe muito e paga em dia. Odeia bardos.",
        "initial_relationship": 5,
        "intro": "Grum limpa um copo com um pano sujo, grunhindo para os clientes."
    },
    "Víbora": {
        "role": "npc",
        "location": "Beco Sombrio",
        "persona": "Líder da guilda dos ladrões. Perigosa, sedutora e letal. Negocia informações por favores ilegais.",
        "initial_relationship": 1, # Hostil/Desconfiada
        "intro": "Víbora surge das sombras, brincando com uma moeda de ouro entre os dedos."
    }
}