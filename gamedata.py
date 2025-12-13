# gamedata.py

# --- CLASSES JOGÁVEIS ---
CLASSES = {
    "Guerreiro": {
        "description": "Tanque de guerra focado em força bruta.",
        "passive": "Adrenalina: Se errar um ataque que custou Stamina, recupera 1 de Stamina.",
        "base_stats": {
            "hp": 30, "mana": 0, "stamina": 20, 
            "defense": 16, 
            "attributes": {"strength": 16, "dexterity": 12, "constitution": 14, "intelligence": 8, "wisdom": 10, "charisma": 10}
        }
    },
    "Ladino": {
        "description": "Assassino ágil e especialista em perícias.",
        "passive": "Evasão: Pode usar Stamina para reduzir dano de área pela metade.",
        "base_stats": {
            "hp": 20, "mana": 5, "stamina": 15,
            "defense": 14,
            "attributes": {"strength": 10, "dexterity": 18, "constitution": 12, "intelligence": 12, "wisdom": 10, "charisma": 14}
        }
    },
    "Mago": {
        "description": "Mestre arcano.",
        "passive": "Recuperação Arcana: Regenera 2 Mana se passar um turno sem atacar.",
        "base_stats": {
            "hp": 14, "mana": 25, "stamina": 8,
            "defense": 11,
            "attributes": {"strength": 8, "dexterity": 12, "constitution": 10, "intelligence": 18, "wisdom": 14, "charisma": 10}
        }
    }
}

# --- HABILIDADES (Mana/Stamina) ---
ABILITIES = {
    "Golpe Pesado": {
        "cost": 3, "resource": "stamina", "type": "dano",
        "effect": "Adiciona +5 de dano fixo ao ataque da arma.",
        "desc": "Um golpe com força total."
    },
    "Esquiva Tática": {
        "cost": 2, "resource": "stamina", "type": "buff",
        "effect": "O próximo ataque do inimigo tem Desvantagem (role dois dados, pegue o menor).",
        "desc": "Movimento rápido para evitar dano."
    },
    "Desengajar": { # Habilidade útil para Ladinos e Goblins
        "cost": 2, "resource": "stamina", "type": "movimento",
        "effect": "Foge do alcance corpo-a-corpo sem levar ataque de oportunidade.",
        "desc": "Recuo tático rápido."
    },
    "Bola de Fogo": {
        "cost": 8, "resource": "mana", "type": "dano",
        "effect": "Dano em área (15 HP). Inimigo faz teste de DEX (DC 14) para metade.",
        "desc": "Explosão arcana."
    },
    "Cura Mística": {
        "cost": 5, "resource": "mana", "type": "cura",
        "effect": "Recupera 10 HP imediatamente.",
        "desc": "Luz divina fecha feridas."
    }
}

# --- ITENS (Armas e Consumíveis) ---
ITEMS_DB = {
    "Espada Longa": {
        "type": "weapon", "bonus": 3, "attr": "strength",
        "desc": "Lâmina de aço (+3 Ataque/Dano)."
    },
    "Adaga Sombria": {
        "type": "weapon", "bonus": 2, "attr": "dexterity",
        "desc": "Lâmina curta e rápida (+2 Ataque/Dano)."
    },
    "Machado de Guerra": {
        "type": "weapon", "bonus": 5, "attr": "strength",
        "desc": "Pesado e brutal (+5 Ataque/Dano)."
    },
    "Poção de Cura": {
        "type": "consumable", "effect": "heal_hp", "value": 15,
        "desc": "Recupera 15 HP."
    },
    "Poção de Mana": {
        "type": "consumable", "effect": "heal_mana", "value": 10,
        "desc": "Recupera 10 Mana."
    }
}

# --- BESTIÁRIO (Fichas de Inimigos) ---
# O Oracle usa isso para spawnar inimigos com stats corretos
BESTIARY = {
    "Goblin Batedor": {
        "hp": 12, "max_hp": 12,
        "stamina": 10, "mana": 0,
        "defense": 13, # AC (Armadura de Couro)
        "attack_mod": 4, # Bônus de acerto
        "attributes": {"strength": 8, "dexterity": 16, "constitution": 10, "intelligence": 10, "wisdom": 8, "charisma": 8},
        "abilities": ["Ataque Furtivo (+1d6 dano se tiver vantagem)", "Desengajar"],
        "desc": "Pequeno, verde e rápido."
    },
    "Guarda Real": {
        "hp": 25, "max_hp": 25,
        "stamina": 20, "mana": 0,
        "defense": 17, # AC (Malha + Escudo)
        "attack_mod": 5, 
        "attributes": {"strength": 16, "dexterity": 10, "constitution": 14, "intelligence": 10, "wisdom": 10, "charisma": 12},
        "abilities": ["Muralha de Escudos (+2 AC para aliados)", "Golpe Atordoante (Gasta 4 Stamina)"],
        "desc": "Blindado e disciplinado."
    },
    "Lobo Atroz": {
        "hp": 18, "max_hp": 18,
        "stamina": 15, "mana": 0,
        "defense": 14, # AC Natural
        "attack_mod": 5,
        "attributes": {"strength": 14, "dexterity": 15, "constitution": 12, "intelligence": 3, "wisdom": 12, "charisma": 6},
        "abilities": ["Derrubar (Se acertar, alvo faz teste de Força ou cai)", "Faro Aguçado"],
        "desc": "Uma fera predadora gigante."
    }
}