"""
logic/dice_system.py
Sistema central de rolagens de dados e parsing de fórmulas.
Responsável por traduzir instruções da IA (ex: "8d6 fire") em números reais.
"""
import re
import random
from typing import List

def roll_formula(formula_text: str, default_save_bonus: int = 3) -> str:
    """
    Interpreta fórmulas de RPG e executa as rolagens.
    
    Suporta:
    1. Testes de Resistência: "DC 15 Dex Save" -> Rola d20 pelo inimigo.
    2. Dados de Dano/Ataque: "1d20+5", "8d6", "2d10+4".
    
    Args:
        formula_text: A string vinda da IA (ex: "DC 15 Dex, 6d6 fire").
        default_save_bonus: Bônus genérico para o teste do inimigo (caso não especificado).
        
    Returns:
        String descritiva do resultado (ex: "Save: Falha | Dano: 28").
    """
    output_parts = []
    
    # ==============================================================================
    # 1. DETECÇÃO DE SAVING THROWS (ex: "DC 15", "CD 15")
    # ==============================================================================
    # Procura por padrões como DC 15, CD: 15, DC15
    save_match = re.search(r'(?:DC|CD)\s*:?\s*(\d+)', formula_text, re.IGNORECASE)
    
    if save_match:
        dc = int(save_match.group(1))
        
        # Simulação de rolagem do inimigo (d20 + bonus fixo)
        # Nota: Em um sistema V2, poderíamos passar a ficha do inimigo aqui para usar o bonus real.
        # Por enquanto, usamos um valor médio (+3) para manter o fluxo rápido.
        enemy_roll = random.randint(1, 20)
        total_save = enemy_roll + default_save_bonus
        
        passed = total_save >= dc
        status = "SUCESSO (Metade do Dano)" if passed else "FALHA (Dano Completo)"
        
        output_parts.append(f"Save Inimigo: {total_save} (d20:{enemy_roll}+{default_save_bonus}) vs DC {dc} -> {status}")

    # ==============================================================================
    # 2. DETECÇÃO DE DADOS (ex: "1d20+5", "8d6")
    # ==============================================================================
    # Regex: (Qtd)d(Lados) opcional(Sinal)(Mod)
    # Ex: 1d20+5, 8d6, 1d10 - 2
    pattern = re.compile(r'(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?')
    matches = pattern.finditer(formula_text)
    
    total_value = 0
    dice_details = []
    found_dice = False
    
    for match in matches:
        found_dice = True
        count = int(match.group(1))
        sides = int(match.group(2))
        
        # Captura modificador se existir
        sign = match.group(3)
        mod = int(match.group(4)) if match.group(4) else 0
        
        # Rola os dados individuais
        rolls = [random.randint(1, sides) for _ in range(count)]
        subtotal = sum(rolls)
        
        # Aplica modificador
        desc = ""
        if sign == '-':
            subtotal -= mod
            desc = f"{count}d{sides}-{mod}"
        elif sign == '+':
            subtotal += mod
            desc = f"{count}d{sides}+{mod}"
        else:
            desc = f"{count}d{sides}"
            
        total_value += subtotal
        dice_details.append(f"[{desc}: {subtotal} {rolls}]")

    # ==============================================================================
    # 3. MONTAGEM DA RESPOSTA
    # ==============================================================================
    
    if found_dice:
        # Se achou dados, retorna o total e os detalhes
        output_parts.append(f"Rolagem Total: {total_value} {' '.join(dice_details)}")
    
    elif not save_match:
        # FALLBACK: Se não tem DC nem dados reconhecíveis (ex: IA mandou "Atacar")
        # Rolamos um d20 genérico para não travar o jogo.
        fallback_val = random.randint(1, 20)
        output_parts.append(f"Rolagem Genérica (d20): {fallback_val}")

    return " | ".join(output_parts)