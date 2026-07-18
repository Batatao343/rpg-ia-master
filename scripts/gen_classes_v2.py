"""Gera data/classes.json e data/player_abilities.json — 5 Posturas diante do
Abismo (spec refatoracao-sistema-classes, etapas 2+5). Números = proposta
[BALANCEAR]. Encoding UTF-8. Roda uma vez; a saída é curada depois se preciso."""
import json
import os

ROOT = os.environ.get("RPG_ROOT", ".")

# --- habilidades -------------------------------------------------------------
AB = {}

def add(aid, name, classe, branch, tier, level_req, *, cost=0, cat="Marcial",
        dmg="0", dtype="Físico", conditions=None, save=None, scaling="0",
        requires=None, effects=None, extra=None):
    AB[aid] = {
        "name": name, "category": cat,
        "description": name + ".",
        "cost": cost, "resource_type": "Entropia" if cost > 0 else "Nenhum",
        "damage_formula": dmg, "damage_type": dtype,
        "conditions": conditions or [], "save_stat": save, "scaling_formula": scaling,
        "classes": [classe], "branch": branch, "tier": tier, "level_req": level_req,
        "requires": requires or [], "effects": effects or [],
    }
    if extra:
        AB[aid].update(extra)

# ataque básico compartilhado (mantido)
AB["ataque_basico"] = {
    "name": "Ataque Básico", "category": "Marcial",
    "description": "Um ataque padrão com a arma equipada.",
    "cost": 0, "resource_type": "Nenhum", "damage_formula": "1d8+str_mod",
    "damage_type": "Físico", "conditions": [], "save_stat": None,
    "scaling_formula": "0", "classes": ["all"], "branch": None, "tier": 1,
    "level_req": 1, "requires": [], "effects": [],
}

# --- DEVOTO DO ABISMO (tank/str) ---
add("provocacao_do_abismo", "Provocação do Abismo", "Devoto do Abismo", None, 1, 1,
    cost=2, dmg="1d6+str_mod", conditions=[{"name": "Provocado", "control": "taunt", "duration": 2}],
    save="cha", extra={"taunt": True})
add("encaixe_do_golpe", "Encaixe do Golpe", "Devoto do Abismo", None, 1, 1,
    cost=2, cat="Defesa", dmg="0", effects=[{"type": "damage_reduction", "amount": 3, "duration": 2}])
# branches
add("marca_consagrada", "Marca Consagrada", "Devoto do Abismo", "consagrado", 2, 3,
    cost=3, cat="Defesa", effects=[{"type": "damage_reduction", "amount": 4, "duration": 3}])
add("fervor_ritual", "Fervor Ritual", "Devoto do Abismo", "consagrado", 3, 5,
    cost=4, dmg="2d6+str_mod")
add("taunt_ciumento", "Provocação Ciumenta", "Devoto do Abismo", "zeloso", 2, 3,
    cost=3, dmg="1d8+str_mod", conditions=[{"name": "Provocado", "control": "taunt", "duration": 2}],
    save="cha", extra={"taunt": True, "aoe": True})
add("retaliacao_do_ciume", "Retaliação do Ciúme", "Devoto do Abismo", "zeloso", 3, 5,
    cost=4, dmg="2d8+str_mod")
add("golpe_melancolico", "Golpe Melancólico", "Devoto do Abismo", "enlutado", 2, 3,
    cost=3, dmg="2d6+str_mod", conditions=[{"name": "Desânimo", "attack_penalty": 2, "duration": 2}], save="wis")
add("intimidade_com_o_fim", "Intimidade com o Fim", "Devoto do Abismo", "enlutado", 3, 5,
    cost=4, dmg="2d8+str_mod")

# --- SANGROMANTE (dano cac/dex) ---
add("corte_de_troca", "Corte de Troca", "Sangromante", None, 1, 1,
    cost=0, dmg="2d6+dex_mod", extra={"self_harm": 3})
add("esquiva_calculada", "Esquiva Calculada", "Sangromante", None, 1, 1,
    cost=2, cat="Defesa", effects=[{"type": "dodge", "amount": 3, "duration": 1}])
add("golpe_espetaculo", "Golpe Espetáculo", "Sangromante", "exposto", 2, 3,
    cost=4, dmg="4d6+dex_mod", extra={"peak": True, "self_harm": 4})
add("pele_de_anuncio", "Pele de Anúncio", "Sangromante", "exposto", 3, 5,
    cost=3, dmg="2d8+dex_mod", conditions=[{"name": "Amedrontado", "control": "fear", "duration": 1}], save="cha")
add("acumulo_de_sangue", "Acúmulo de Sangue", "Sangromante", "avaro", 2, 3,
    cost=0, dmg="1d6+dex_mod", extra={"self_harm": 2})
add("explosao_avara", "Explosão Avara", "Sangromante", "avaro", 3, 5,
    cost=6, dmg="5d6+dex_mod", extra={"peak": True})
add("corte_exato", "Corte Exato", "Sangromante", "silencioso", 2, 3,
    cost=3, dmg="3d6+dex_mod")
add("mao_firme", "Mão Firme", "Sangromante", "silencioso", 3, 5,
    cost=3, dmg="2d8+dex_mod", extra={"self_harm": 1})

# --- CORRUPTOR (DoT/wis) ---
add("toque_da_decadencia", "Toque da Decadência", "Corruptor", None, 1, 1,
    cost=3, cat="Arcano", dmg="1d6+wis_mod", dtype="Necrótico",
    conditions=[{"name": "Decadência", "dot": 3, "duration": 3}], save="con")
add("semear_praga", "Semear Praga", "Corruptor", None, 1, 1,
    cost=3, cat="Arcano", conditions=[{"name": "Praga", "dot": 2, "duration": 3}], save="con", extra={"aoe": True})
add("praga_de_esporos", "Praga de Esporos", "Corruptor", "biologia", 2, 3,
    cost=4, cat="Arcano", dtype="Necrótico", conditions=[{"name": "Esporos", "dot": 4, "duration": 3}], save="con", extra={"aoe": True})
add("contagio", "Contágio", "Corruptor", "biologia", 3, 5,
    cost=4, cat="Arcano", dmg="2d6+wis_mod", dtype="Necrótico", conditions=[{"name": "Contágio", "dot": 3, "duration": 3}], save="con")
add("corroer_vontade", "Corroer Vontade", "Corruptor", "alma", 2, 3,
    cost=4, cat="Arcano", conditions=[{"name": "Desespero", "control": "fear", "duration": 2}], save="wis", extra={"decay_kind": "morale"})
add("eco_do_vazio", "Eco do Vazio", "Corruptor", "alma", 3, 5,
    cost=4, cat="Arcano", dmg="2d8+wis_mod", dtype="Psíquico", save="wis")
add("enferrujar", "Enferrujar", "Corruptor", "inorganica", 2, 3,
    cost=4, cat="Arcano", dmg="2d6+wis_mod", dtype="Ácido", conditions=[{"name": "Corrosão", "attack_penalty": 2, "duration": 3}], extra={"decay_kind": "gear"})
add("po_e_ferrugem", "Pó e Ferrugem", "Corruptor", "inorganica", 3, 5,
    cost=4, cat="Arcano", dmg="3d6+wis_mod", dtype="Ácido")

# --- ARCANISTA CINZENTO (dist/int) ---
add("descarga_do_instrumento", "Descarga do Instrumento", "Arcanista Cinzento", None, 1, 1,
    cost=3, cat="Arcano", dmg="2d6+int_mod", dtype="Arcano", extra={"cools": True})
add("vazao_controlada", "Vazão Controlada", "Arcanista Cinzento", None, 1, 1,
    cost=2, cat="Arcano", dmg="1d8+int_mod", dtype="Arcano", extra={"cools": True})
add("dano_calibrado", "Dano Calibrado", "Arcanista Cinzento", "calibrado", 2, 3,
    cost=4, cat="Arcano", dmg="3d6+int_mod", dtype="Arcano", extra={"cools": True})
add("condensador", "Condensador", "Arcanista Cinzento", "calibrado", 3, 5,
    cost=3, cat="Arcano", dmg="2d8+int_mod", dtype="Arcano", extra={"cools": True})
add("toque_cru", "Toque Cru", "Arcanista Cinzento", "descoberto", 2, 3,
    cost=2, cat="Arcano", dmg="4d6+int_mod", dtype="Arcano", extra={"self_harm": 4})
add("veias_de_eter", "Veias de Éter", "Arcanista Cinzento", "descoberto", 3, 5,
    cost=3, cat="Arcano", dmg="3d6+int_mod", dtype="Arcano", extra={"self_harm": 2})
add("rig_improvisado", "Rig Improvisado", "Arcanista Cinzento", "improvisador", 2, 3,
    cost=3, cat="Arcano", dmg="2d6+int_mod", dtype="Arcano", conditions=[{"name": "Marcado", "attack_penalty": 2, "duration": 2}])
add("pecas_de_reposicao", "Peças de Reposição", "Arcanista Cinzento", "improvisador", 3, 5,
    cost=3, cat="Arcano", dmg="2d8+int_mod", dtype="Arcano")

# --- MÉDICO DE CAMPO (suporte/int) ---
add("sutura_de_campo", "Sutura de Campo", "Médico de Campo", None, 1, 1,
    cost=3, cat="Suporte", effects=[{"type": "heal", "formula": "2d4+int_mod"}])
add("estabilizar", "Estabilizar", "Médico de Campo", None, 1, 1,
    cost=2, cat="Suporte", effects=[{"type": "cleanse", "duration": 1}])
add("intervencao_imediata", "Intervenção Imediata", "Médico de Campo", "cirurgiao_trincheira", 2, 3,
    cost=4, cat="Suporte", effects=[{"type": "heal", "formula": "3d4+int_mod"}])
add("maos_rapidas", "Mãos Rápidas", "Médico de Campo", "cirurgiao_trincheira", 3, 5,
    cost=3, cat="Suporte", effects=[{"type": "heal", "formula": "2d6+int_mod"}])
add("dose_preparada", "Dose Preparada", "Médico de Campo", "boticario", 2, 3,
    cost=3, cat="Suporte", effects=[{"type": "buff", "stat": "attack", "amount": 2, "duration": 3}])
add("purga_da_carga", "Purga da Carga", "Médico de Campo", "boticario", 3, 5,
    cost=5, cat="Suporte", effects=[{"type": "reduce_ally_abyss", "amount": 2}], extra={"heal_abyss": True})
add("protese", "Prótese", "Médico de Campo", "cirurgiao_ferro", 2, 3,
    cost=4, cat="Suporte", effects=[{"type": "buff", "stat": "defense", "amount": 3, "duration": 4}])
add("aco_no_lugar", "Aço no Lugar", "Médico de Campo", "cirurgiao_ferro", 3, 5,
    cost=3, cat="Suporte", effects=[{"type": "buff", "stat": "defense", "amount": 2, "duration": 3}])

# --- classes ----------------------------------------------------------------
def branch(name, identity):
    return {"name": name, "identity": identity}

CLASSES = {
    "Devoto do Abismo": {
        "description": "Ama o Abismo: avança na direção da incerteza porque a deseja.",
        "role": "tank", "posture": "ama",
        "guide_quote": "Vocês seguram a linha com medo. Eu seguro porque quero que ele me escolha primeiro.",
        "passive": "Convite: provocações escalam com a Entropia acumulada no combate.",
        "base_stats": {"hp": 38, "entropy": 14, "mana": 0, "stamina": 0, "defense": 16,
                       "attributes": {"str": 16, "dex": 10, "con": 16, "int": 8, "wis": 12, "cha": 14}},
        "level_gains": {"hp": 7, "entropy": 2, "mana": 0, "stamina": 0},
        "starting_abilities": ["provocacao_do_abismo", "encaixe_do_golpe"],
        "entropy_trigger": {"kind": "on_damage_taken", "damage_divisor": 4, "min_gain": 1,
                            "charge_per": 1, "per_turn_cap": 1,
                            "note": "[BALANCEAR] +1 Entropia por 4 de dano recebido; +1 Carga/turno"},
        "special_rule": {"kind": "taunt_scales_with_entropy", "per_entropy": 0.05, "cap": 0.6,
                         "note": "[BALANCEAR] aggro sobe 5%/ponto de Entropia, teto 60%"},
        "abyss": {"consequence": "insonia", "thresholds": {"leve": 1, "moderado": 4, "severo": 7},
                  "hidden": False, "mitigable_by_ally": True,
                  "params": {"rest_penalty": {"leve": 0.1, "moderado": 0.25, "severo": 0.5}}},
        "branches": {
            "consagrado": branch("O Consagrado", "Ritualiza o amor ao Abismo; marca o corpo antes da luta."),
            "zeloso": branch("O Zeloso", "Amor possessivo; puxa aggro por ciúme."),
            "enlutado": branch("O Enlutado", "Amou quem o Abismo levou; tom melancólico."),
        },
        "passive_effects": [],
        "starting_equipment": ["espada_gasta", "escudo_amassado", "pocao_cura"],
    },
    "Sangromante": {
        "description": "Negocia com o Abismo: paga em sangue pelo que precisa.",
        "role": "dano corpo-a-corpo", "posture": "negocia",
        "guide_quote": "Tudo tem preço. Eu só pago à vista.",
        "passive": "Contrato de Sangue: auto-dano vira Entropia de sangue.",
        "base_stats": {"hp": 26, "entropy": 16, "mana": 0, "stamina": 0, "defense": 12,
                       "attributes": {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 10, "cha": 12}},
        "level_gains": {"hp": 5, "entropy": 3, "mana": 0, "stamina": 0},
        "starting_abilities": ["corte_de_troca", "esquiva_calculada"],
        "entropy_trigger": {"kind": "on_self_harm", "gain_per_hp": 1, "charge_per": 1, "per_turn_cap": 2,
                            "note": "[BALANCEAR] auto-dano vira Entropia (1:1); +1 Carga por ativação"},
        "special_rule": {"kind": "blood_leak", "leak_frac": 0.25,
                         "note": "[BALANCEAR] acerto do inimigo vaza 25% da Entropia de sangue não gasta"},
        "abyss": {"consequence": "cicatriz", "thresholds": {"leve": 1, "moderado": 4, "severo": 7},
                  "hidden": False, "mitigable_by_ally": False,
                  "params": {"scar_hp_loss": 3}},
        "branches": {
            "exposto": branch("O Exposto", "Faz espetáculo da dor; a cicatriz é credencial."),
            "avaro": branch("O Avaro", "Acumula Entropia de sangue para um golpe único."),
            "silencioso": branch("O Silencioso", "Corte exato, economia de dor."),
        },
        "passive_effects": [],
        "starting_equipment": ["adaga_ferro", "pocao_cura"],
    },
    "Corruptor": {
        "description": "Trabalha JUNTO com o Abismo: acelera a decadência que já existe.",
        "role": "controle / DoT", "posture": "trabalha junto",
        "guide_quote": "Eu não trago a ruína. Só chego mais cedo.",
        "passive": "Parceria: a decadência ao seu redor te alimenta.",
        "base_stats": {"hp": 28, "entropy": 18, "mana": 0, "stamina": 0, "defense": 13,
                       "attributes": {"str": 10, "dex": 12, "con": 12, "int": 12, "wis": 16, "cha": 10}},
        "level_gains": {"hp": 5, "entropy": 4, "mana": 0, "stamina": 0},
        "starting_abilities": ["toque_da_decadencia", "semear_praga"],
        "entropy_trigger": {"kind": "on_decay_nearby", "gain": 1, "charge_per": 1, "per_turn_cap": 2,
                            "decay_kind": "any",
                            "note": "[BALANCEAR] algo perto se desfaz (DoT/morte) → +1 Entropia; +1 Carga"},
        "special_rule": {"kind": "domain_decay", "note": "o domínio (subclasse) define o que conta como decadência"},
        "abyss": {"consequence": "transformacao", "thresholds": {"leve": 1, "moderado": 4, "severo": 7},
                  "hidden": False, "mitigable_by_ally": True,
                  "params": {"debuff": {"biologia": "extra_dot", "alma": "save_penalty", "inorganica": "defense_penalty"}}},
        "branches": {
            "biologia": {"name": "Biologia", "identity": "Carne que apodrece.",
                         "overrides": {"entropy_trigger": {"decay_kind": "flesh"}}},
            "alma": {"name": "Alma", "identity": "Vontade que rui.",
                     "overrides": {"entropy_trigger": {"decay_kind": "morale"}}},
            "inorganica": {"name": "Inorgânica", "identity": "Metal e pedra que cedem.",
                           "overrides": {"entropy_trigger": {"decay_kind": "gear"}}},
        },
        "passive_effects": [],
        "starting_equipment": ["cajado_de_galhos", "pocao_cura"],
    },
    "Arcanista Cinzento": {
        "description": "Manipula o Abismo por um instrumento: canaliza a entropia e a descarrega.",
        "role": "dano/controle à distância", "posture": "manipula",
        "guide_quote": "A ferramenta segura o que a mão não deveria tocar.",
        "passive": "Caldeira: canalizar gera Entropia para a próxima descarga.",
        "base_stats": {"hp": 22, "entropy": 20, "mana": 0, "stamina": 0, "defense": 11,
                       "attributes": {"str": 8, "dex": 12, "con": 10, "int": 16, "wis": 12, "cha": 12}},
        "level_gains": {"hp": 4, "entropy": 6, "mana": 0, "stamina": 0},
        "starting_abilities": ["descarga_do_instrumento", "vazao_controlada"],
        "entropy_trigger": {"kind": "on_channel", "gain": 2, "charge_per": 1, "per_turn_cap": 1,
                            "note": "[BALANCEAR] usar habilidade gera Entropia p/ a próxima; +1 Carga"},
        "special_rule": {"kind": "boiler", "cool_deadline": 3, "overload_damage": "2d6",
                         "note": "[BALANCEAR] Entropia não vazada em 3 turnos → instrumento estoura (auto-dano)"},
        "abyss": {"consequence": "dependencia", "thresholds": {"leve": 1, "moderado": 4, "severo": 7},
                  "hidden": False, "mitigable_by_ally": True,
                  "params": {"no_instrument_cost_mult": 2.0}},
        "branches": {
            "calibrado": branch("O Calibrado", "Segurança acima de potência; menos risco de estouro."),
            "descoberto": branch("O Descoberto", "Toca o éter sem instrumento; alto dano, alto risco."),
            "improvisador": branch("O Improvisador", "Monta ferramenta na hora a partir de sucata."),
        },
        "passive_effects": [],
        "starting_equipment": ["cajado_rachado", "pocao_cura"],
    },
    "Médico de Campo": {
        "description": "Nega o Abismo: mantém vivo o que ele quer levar.",
        "role": "suporte / cura", "posture": "nega",
        "guide_quote": "Enquanto eu respirar, você respira.",
        "passive": "Triagem: cura mais quem está mais perto do fim.",
        "base_stats": {"hp": 28, "entropy": 16, "mana": 0, "stamina": 0, "defense": 14,
                       "attributes": {"str": 10, "dex": 12, "con": 12, "int": 16, "wis": 14, "cha": 10}},
        "level_gains": {"hp": 5, "entropy": 3, "mana": 0, "stamina": 0},
        "starting_abilities": ["sutura_de_campo", "estabilizar"],
        "entropy_trigger": {"kind": "on_ally_suffer", "gain": 1, "charge_per": 1, "per_turn_cap": 2,
                            "note": "[BALANCEAR] aliado toma dano/condição → +1 Entropia; +1 Carga"},
        "special_rule": {"kind": "heal_abyss",
                         "note": "única classe que gasta Entropia p/ reduzir Carga de aliado (purga_da_carga)"},
        "abyss": {"consequence": "recidiva", "thresholds": {"leve": 1, "moderado": 4, "severo": 7},
                  "hidden": True, "mitigable_by_ally": False,
                  "params": {"collapse_at": "severo"}},
        "branches": {
            "cirurgiao_trincheira": branch("Cirurgião de Trincheira", "Intervenção imediata sob fogo."),
            "boticario": branch("Boticário", "Compostos, buffs e purga da Carga alheia."),
            "cirurgiao_ferro": branch("Cirurgião de Ferro", "Próteses e reforço físico de aliados."),
        },
        "passive_effects": [],
        "starting_equipment": ["serra_cirurgica", "pocao_cura", "pocao_cura"],
    },
}

with open(os.path.join(ROOT, "data", "player_abilities.json"), "w", encoding="utf-8") as f:
    json.dump(AB, f, ensure_ascii=False, indent=2)
with open(os.path.join(ROOT, "data", "classes.json"), "w", encoding="utf-8") as f:
    json.dump(CLASSES, f, ensure_ascii=False, indent=2)

print("abilities:", len(AB), "| classes:", len(CLASSES))
# valida ids de starting_abilities e branches
for cn, cd in CLASSES.items():
    for aid in cd["starting_abilities"]:
        assert aid in AB, f"{cn}: starting {aid} ausente"
    brs = set(cd["branches"].keys())
    ab_brs = {a["branch"] for a in AB.values() if a["branch"] and cn in a["classes"]}
    assert ab_brs == brs, f"{cn}: branches {brs} vs abilities {ab_brs}"
print("validação OK")
