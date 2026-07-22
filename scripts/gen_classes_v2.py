"""Gera data/classes.json e data/player_abilities.json — 5 Posturas diante do
Abismo (spec refatoracao-sistema-classes, etapas 2+5). Números = proposta
[BALANCEAR]. Encoding UTF-8. Roda uma vez; a saída é curada depois se preciso.

IMPORTANTE — schema alinhado ao MOTOR (combat_mechanics):
- efeitos usam `effects: [{"kind": buff|debuff|dot|control, ...}]` (Fase 4.2),
  nunca `type` — o `_split_typed_effects`/`_condition_from_effect` só leem `kind`.
- CURA é `damage_type: "Cura"` + `damage_formula` POSITIVA (o `_is_healing` decide),
  não um effect; "Remove X"/"Recupera N" ficam em `conditions` (strings) no caminho de cura.
- gatilhos/consequências de Entropia são config TIPADA por classe (entropy_trigger/
  special_rule/abyss), lidos por Python — a habilidade só carrega marcadores
  (self_harm/peak/cools/taunt/decay_kind).
"""
import json
import os

ROOT = os.environ.get("RPG_ROOT", ".")

# --- habilidades -------------------------------------------------------------
AB = {}


def add(aid, name, classe, branch, tier, level_req, *, cost=0, cat="Marcial",
        dmg="0", dtype="Físico", effects=None, conditions=None, save=None,
        scaling="0", requires=None, extra=None):
    """Registra habilidade no schema que o motor consome.

    `effects` = lista tipada (kind buff/debuff/dot/control). `conditions` só p/
    cura (strings "Remove X"/"Recupera N"). `extra` = marcadores mecânicos."""
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


def dot(delta, dur=3):
    return {"kind": "dot", "delta": delta, "duration": dur}


def control(kind, dur=2):
    return {"kind": "control", "control": kind, "duration": dur}


def debuff(stat, delta, dur=3):
    return {"kind": "debuff", "stat": stat, "delta": delta, "duration": dur}


def buff(stat, delta, dur=3):
    return {"kind": "buff", "stat": stat, "delta": delta, "duration": dur}


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
    cost=2, dmg="1d6+str_mod", save="cha",
    effects=[control("taunt", 2)], extra={"taunt": True})
add("encaixe_do_golpe", "Encaixe do Golpe", "Devoto do Abismo", None, 1, 1,
    cost=2, cat="Defesa", effects=[buff("ac", 3, 2)])
# branches
add("marca_consagrada", "Marca Consagrada", "Devoto do Abismo", "consagrado", 2, 3,
    cost=3, cat="Defesa", effects=[buff("ac", 4, 3)])
# spec balanceamento-classes-pos-playtest (parity): 2d6→2d8 — era o ÚNICO outlier
# de dano puro (1.75/custo vs 2.25 dos irmãos Retaliação/Intimidade, mesmo custo).
add("fervor_ritual", "Fervor Ritual", "Devoto do Abismo", "consagrado", 3, 5,
    cost=4, dmg="2d8+str_mod", scaling="str", requires=["marca_consagrada"])
add("taunt_ciumento", "Provocação Ciumenta", "Devoto do Abismo", "zeloso", 2, 3,
    cost=3, dmg="1d8+str_mod", save="cha",
    effects=[control("taunt", 2)], extra={"taunt": True, "aoe": True})
add("retaliacao_do_ciume", "Retaliação do Ciúme", "Devoto do Abismo", "zeloso", 3, 5,
    cost=4, dmg="2d8+str_mod", scaling="str", requires=["taunt_ciumento"])
add("golpe_melancolico", "Golpe Melancólico", "Devoto do Abismo", "enlutado", 2, 3,
    cost=3, dmg="2d6+str_mod", save="wis", effects=[debuff("attack", -2, 2)])
add("intimidade_com_o_fim", "Intimidade com o Fim", "Devoto do Abismo", "enlutado", 3, 5,
    cost=4, dmg="2d8+str_mod", scaling="str", requires=["golpe_melancolico"])

# --- SANGROMANTE (dano cac/dex) ---
add("corte_de_troca", "Corte de Troca", "Sangromante", None, 1, 1,
    cost=0, dmg="2d6+dex_mod", extra={"self_harm": 3})
add("esquiva_calculada", "Esquiva Calculada", "Sangromante", None, 1, 1,
    cost=2, cat="Defesa", effects=[buff("ac", 3, 1)])
add("golpe_espetaculo", "Golpe Espetáculo", "Sangromante", "exposto", 2, 3,
    cost=4, dmg="4d6+dex_mod", scaling="dex", extra={"peak": True, "self_harm": 4})
add("pele_de_anuncio", "Pele de Anúncio", "Sangromante", "exposto", 3, 5,
    cost=3, dmg="2d8+dex_mod", save="cha", requires=["golpe_espetaculo"],
    effects=[control("fear", 1)])
add("acumulo_de_sangue", "Acúmulo de Sangue", "Sangromante", "avaro", 2, 3,
    cost=0, dmg="1d6+dex_mod", extra={"self_harm": 2})
add("explosao_avara", "Explosão Avara", "Sangromante", "avaro", 3, 5,
    cost=6, dmg="5d6+dex_mod", scaling="dex", requires=["acumulo_de_sangue"],
    extra={"peak": True})
add("corte_exato", "Corte Exato", "Sangromante", "silencioso", 2, 3,
    cost=3, dmg="3d6+dex_mod")
add("mao_firme", "Mão Firme", "Sangromante", "silencioso", 3, 5,
    cost=3, dmg="2d8+dex_mod", scaling="dex", requires=["corte_exato"],
    extra={"self_harm": 1})

# --- CORRUPTOR (DoT/wis) ---
add("toque_da_decadencia", "Toque da Decadência", "Corruptor", None, 1, 1,
    cost=3, cat="Arcano", dmg="1d6+wis_mod", dtype="Necrótico", save="con",
    effects=[dot(3, 3)])
add("semear_praga", "Semear Praga", "Corruptor", None, 1, 1,
    cost=3, cat="Arcano", save="con", effects=[dot(2, 3)], extra={"aoe": True})
add("praga_de_esporos", "Praga de Esporos", "Corruptor", "biologia", 2, 3,
    cost=4, cat="Arcano", dtype="Necrótico", save="con",
    effects=[dot(4, 3)], extra={"aoe": True})
add("contagio", "Contágio", "Corruptor", "biologia", 3, 5,
    cost=4, cat="Arcano", dmg="2d6+wis_mod", dtype="Necrótico", save="con",
    scaling="wis", requires=["praga_de_esporos"], effects=[dot(3, 3)])
add("corroer_vontade", "Corroer Vontade", "Corruptor", "alma", 2, 3,
    cost=4, cat="Arcano", save="wis", effects=[control("fear", 2)],
    extra={"decay_kind": "morale"})
add("eco_do_vazio", "Eco do Vazio", "Corruptor", "alma", 3, 5,
    cost=4, cat="Arcano", dmg="2d8+wis_mod", dtype="Psíquico", save="wis",
    scaling="wis", requires=["corroer_vontade"], effects=[debuff("save", -2, 2)])
add("enferrujar", "Enferrujar", "Corruptor", "inorganica", 2, 3,
    cost=4, cat="Arcano", dmg="2d6+wis_mod", dtype="Ácido",
    effects=[debuff("attack", -2, 3)], extra={"decay_kind": "gear"})
add("po_e_ferrugem", "Pó e Ferrugem", "Corruptor", "inorganica", 3, 5,
    cost=4, cat="Arcano", dmg="3d6+wis_mod", dtype="Ácido", scaling="wis",
    requires=["enferrujar"], effects=[debuff("ac", -2, 2)])

# --- ARCANISTA CINZENTO (dist/int) ---
add("descarga_do_instrumento", "Descarga do Instrumento", "Arcanista Cinzento", None, 1, 1,
    cost=3, cat="Arcano", dmg="2d6+int_mod", dtype="Arcano", extra={"cools": True})
add("vazao_controlada", "Vazão Controlada", "Arcanista Cinzento", None, 1, 1,
    cost=2, cat="Arcano", dmg="1d8+int_mod", dtype="Arcano", extra={"cools": True})
add("dano_calibrado", "Dano Calibrado", "Arcanista Cinzento", "calibrado", 2, 3,
    cost=4, cat="Arcano", dmg="3d6+int_mod", dtype="Arcano", scaling="int",
    extra={"cools": True})
add("condensador", "Condensador", "Arcanista Cinzento", "calibrado", 3, 5,
    cost=3, cat="Arcano", dmg="2d8+int_mod", dtype="Arcano", scaling="int",
    requires=["dano_calibrado"], save="dex", effects=[debuff("attack", -2, 2)],
    extra={"cools": True})
add("toque_cru", "Toque Cru", "Arcanista Cinzento", "descoberto", 2, 3,
    cost=2, cat="Arcano", dmg="4d6+int_mod", dtype="Arcano", extra={"self_harm": 4})
add("veias_de_eter", "Veias de Éter", "Arcanista Cinzento", "descoberto", 3, 5,
    cost=3, cat="Arcano", dmg="3d6+int_mod", dtype="Arcano", scaling="int",
    requires=["toque_cru"], extra={"self_harm": 2})
add("rig_improvisado", "Rig Improvisado", "Arcanista Cinzento", "improvisador", 2, 3,
    cost=3, cat="Arcano", dmg="2d6+int_mod", dtype="Arcano",
    effects=[debuff("attack", -2, 2)])
add("pecas_de_reposicao", "Peças de Reposição", "Arcanista Cinzento", "improvisador", 3, 5,
    cost=3, cat="Arcano", dmg="2d8+int_mod", dtype="Arcano", scaling="int",
    requires=["rig_improvisado"], save="dex", effects=[debuff("ac", -2, 2)])

# --- MÉDICO DE CAMPO (suporte/int) ---
# CURA: damage_type "Cura" + fórmula positiva (o motor cura o próprio herói).
add("sutura_de_campo", "Sutura de Campo", "Médico de Campo", None, 1, 1,
    cost=3, cat="Suporte", dtype="Cura", dmg="2d4+int_mod",
    conditions=["Remove Sangramento"])
add("estabilizar", "Estabilizar", "Médico de Campo", None, 1, 1,
    cost=2, cat="Suporte", dtype="Cura", dmg="1d4+int_mod",
    conditions=["Remove Veneno"])
add("intervencao_imediata", "Intervenção Imediata", "Médico de Campo", "cirurgiao_trincheira", 2, 3,
    cost=4, cat="Suporte", dtype="Cura", dmg="3d4+int_mod")
add("maos_rapidas", "Mãos Rápidas", "Médico de Campo", "cirurgiao_trincheira", 3, 5,
    cost=3, cat="Suporte", dtype="Cura", dmg="2d6+int_mod",
    requires=["intervencao_imediata"], conditions=["Remove Sangramento"])
add("dose_preparada", "Dose Preparada", "Médico de Campo", "boticario", 2, 3,
    cost=3, cat="Suporte", effects=[buff("attack", 2, 3)])
add("purga_da_carga", "Purga da Carga", "Médico de Campo", "boticario", 3, 5,
    cost=5, cat="Suporte", requires=["dose_preparada"],
    effects=[{"kind": "reduce_ally_abyss", "amount": 2}], extra={"heal_abyss": True})
add("protese", "Prótese", "Médico de Campo", "cirurgiao_ferro", 2, 3,
    cost=4, cat="Suporte", effects=[buff("ac", 3, 4)])
add("aco_no_lugar", "Aço no Lugar", "Médico de Campo", "cirurgiao_ferro", 3, 5,
    cost=3, cat="Suporte", requires=["protese"], effects=[buff("ac", 2, 3)])

# --- passivas + utilitárias (spec arvores-habilidade-classes) ---------------
# Passiva: efeito permanente ao aprender (passive_effects tipado — vocabulário
# lido por combat_mechanics.player_passives). Utilitária: capacidade fora de
# combate (out_of_combat: label/scope/prompt_hint — gate determinístico, LLM narra).

def addp(aid, name, classe, branch_id, tier, level_req, desc, passive_effects,
         requires=None):
    AB[aid] = {
        "name": name, "category": "Passiva",
        "description": desc,
        "cost": 0, "resource_type": "Nenhum",
        "damage_formula": "0", "damage_type": "Físico",
        "conditions": [], "save_stat": None, "scaling_formula": "0",
        "classes": [classe], "branch": branch_id, "tier": tier,
        "level_req": level_req, "requires": requires or [], "effects": [],
        "ability_kind": "passive", "passive_effects": passive_effects,
    }


def addu(aid, name, classe, branch_id, tier, level_req, desc, scope, hint):
    AB[aid] = {
        "name": name, "category": "Utilitária",
        "description": desc,
        "cost": 0, "resource_type": "Nenhum",
        "damage_formula": "0", "damage_type": "Físico",
        "conditions": [], "save_stat": None, "scaling_formula": "0",
        "classes": [classe], "branch": branch_id, "tier": tier,
        "level_req": level_req, "requires": [], "effects": [],
        "ability_kind": "utility",
        "out_of_combat": {"label": name, "scope": scope, "prompt_hint": hint},
    }


# ===== DEVOTO DO ABISMO — tronco =====
addu("convite_do_abismo", "O Convite", "Devoto do Abismo", None, 1, 1,
     "Você sente quem, numa sala cheia, o Abismo já começou a escolher — o cansaço além do sono, o olhar que ficou tempo demais no escuro.",
     "detection", "sente quem numa cena está tocado/marcado pelo Abismo, antes de qualquer sinal visível")
addu("pararraios_social", "Para-raios", "Devoto do Abismo", None, 1, 1,
     "Quando o medo de um grupo procura um alvo, você se oferece. O pânico, o motim, a acusação — tudo desce por você e se aterra.",
     "social", "atrai para si o medo ou a raiva coletiva de uma cena, evitando pânico ou motim")
addp("postura_do_convite", "Postura do Convite", "Devoto do Abismo", None, 1, 2,
     "O corpo que deseja o golpe aprende exatamente onde ele cai.",
     [{"trigger": "always", "stat": "ac", "delta": 1}])
# — Consagrado
addp("disciplina_do_rito", "Disciplina do Rito", "Devoto do Abismo", "consagrado", 2, 3,
     "O rito organiza o amor: o Abismo cobra menos de quem se oferece na forma correta.",
     [{"trigger": "charge_discount", "delta": 1}])
addp("fervor_silencioso", "Fervor Silencioso", "Devoto do Abismo", "consagrado", 2, 4,
     "A oração não pede nada; afia.",
     [{"trigger": "always", "stat": "attack", "delta": 1}])
addu("leitura_de_pressagio", "Leitura de Presságio", "Devoto do Abismo", "consagrado", 2, 3,
     "Cinza, sangue seco, vento errado: o dia sempre avisa quem sabe ler.",
     "investigation", "lê presságios em sinais mundanos e extrai um aviso concreto sobre o que vem")
# — Zeloso
addp("ciume_do_abismo", "Ciúme do Abismo", "Devoto do Abismo", "zeloso", 2, 3,
     "Quem encosta no que é seu — no aliado, na linha, no fim que você reivindicou — sangra por isso.",
     [{"trigger": "melee_retaliate", "name": "Ciúme do Abismo", "formula": "1d4"}])
addp("possessao_zelosa", "Possessão Zelosa", "Devoto do Abismo", "zeloso", 2, 4,
     "Quanto mais fundo o Abismo mora em você, mais certeiro o golpe de quem defende o que ama.",
     [{"trigger": "carga_embrace", "stat": "attack", "per_tier": 1}])
addu("farejar_rival", "Farejar Rival", "Devoto do Abismo", "zeloso", 2, 3,
     "Você reconhece de longe quem mais corteja o seu amado.",
     "detection", "identifica na cena quem também corteja o Abismo — cultista, tocado, condenado")
# — Enlutado
addp("luto_que_pesa", "Luto que Pesa", "Devoto do Abismo", "enlutado", 2, 3,
     "A perda vira lastro; o lastro vira força de queda.",
     [{"trigger": "carga_embrace", "stat": "damage", "per_tier": 1}])
addp("vigilia_do_luto", "Vigília do Luto", "Devoto do Abismo", "enlutado", 2, 4,
     "Quem já perdeu o que mais temia perder não tem mais para onde temer.",
     [{"trigger": "resist", "name": "medo"}])
addu("vozes_dos_levados", "Vozes dos Levados", "Devoto do Abismo", "enlutado", 2, 3,
     "Diante do que sobrou, você ouve o que os levados ainda tentam contar.",
     "investigation", "diante de restos e lugares onde o Abismo levou alguém, recompõe o que aconteceu")

# ===== SANGROMANTE — tronco =====
addu("avaliacao_de_preco", "Avaliação de Preço", "Sangromante", None, 1, 1,
     "Tudo tem preço. Você sabe qual é — mesmo quando escondem.",
     "social", "sabe o custo/valor real de qualquer coisa — mercadoria, favor, silêncio — mesmo quando escondido")
addu("leitura_forense", "Leitura Forense", "Sangromante", None, 1, 1,
     "Sangue seco conta a história inteira para quem paga na mesma moeda.",
     "investigation", "lê feridas, sangue e corpos: o que feriu, quando, e se a dívida foi paga")
addp("contrato_de_sangue", "Contrato de Sangue", "Sangromante", None, 1, 2,
     "O corpo que negocia todo dia aprende a guardar mais moeda.",
     [{"trigger": "entropy_max_bonus", "delta": 2}])
# — Exposto
addp("cicatriz_credencial", "Cicatriz Credencial", "Sangromante", "exposto", 2, 3,
     "Cada cicatriz é um recibo; quem lê seu corpo sabe que você paga.",
     [{"trigger": "carga_embrace", "stat": "attack", "per_tier": 1}])
addp("pele_de_palco", "Pele de Palco", "Sangromante", "exposto", 2, 4,
     "Você sangra quando decide, não quando mandam.",
     [{"trigger": "resist", "name": "sangramento"}])
addu("presenca_que_cala", "Presença que Cala", "Sangromante", "exposto", 2, 3,
     "Você entra, e o preço de mexer com você fica visível.",
     "social", "impõe presença numa cena hostil: a conversa esfria, a ameaça reconsiderada")
# — Avaro
addp("cofre_de_sangue", "Cofre de Sangue", "Sangromante", "avaro", 2, 3,
     "Nada vaza, nada se perde; o cofre cresce.",
     [{"trigger": "entropy_max_bonus", "delta": 3}])
addp("juros_do_corpo", "Juros do Corpo", "Sangromante", "avaro", 2, 4,
     "Todo golpe seu cobra o principal — mais juros.",
     [{"trigger": "always", "stat": "damage", "delta": 1}])
addu("farejar_divida", "Farejar Dívida", "Sangromante", "avaro", 2, 3,
     "Segredos têm preço, e você sente o cheiro dos caros.",
     "investigation", "sente o que numa cena vale caro e quem deve a quem — dívidas, chantagens, segredos com preço")
# — Silencioso
addp("economia_de_dor", "Economia de Dor", "Sangromante", "silencioso", 2, 3,
     "Corte exato não desperdiça sangue — nem o seu.",
     [{"trigger": "entropy_cost_reduction", "category": "Marcial", "delta": 1}])
addp("corte_sem_eco", "Corte sem Eco", "Sangromante", "silencioso", 2, 4,
     "A lâmina que não anuncia chega antes.",
     [{"trigger": "always", "stat": "attack", "delta": 1}])
addu("ferida_invisivel", "Ferida Invisível", "Sangromante", "silencioso", 2, 3,
     "Nenhum médico achará a marca — nem a sua, nem a que você deixou.",
     "medical", "fere ou trata sem deixar marca que outro exame encontre depois")

# ===== CORRUPTOR — tronco =====
addu("olho_da_ruina", "Olho da Ruína", "Corruptor", None, 1, 1,
     "Você vê o que já está cedendo: a viga rachada, o pulmão doente, a fé quebrando.",
     "detection", "identifica o que numa cena já está cedendo — estrutura, corpo ou vontade prestes a falhar")
addu("rede_de_pragas", "Rede de Pragas", "Corruptor", None, 1, 1,
     "Os pequenos decompositores contam onde estiveram e o que roeram.",
     "investigation", "consulta ratos, vermes e insetos como informantes: o que passou por aqui, o que apodrece onde")
addp("parceria_com_o_fim", "Parceria com o Fim", "Corruptor", None, 1, 2,
     "Toda morte por perto é um pagamento adiantado.",
     [{"trigger": "entropy_on_kill", "amount": 1}])
# — Biologia
addp("carne_receptiva", "Carne Receptiva", "Corruptor", "biologia", 2, 3,
     "A colônia não envenena o próprio jardim.",
     [{"trigger": "resist", "name": "veneno"}])
addp("florescer_da_podridao", "Florescer da Podridão", "Corruptor", "biologia", 2, 4,
     "Onde sua mão passa, o apodrecer acelera com gosto.",
     [{"trigger": "damage_type", "damage_type": "Necrótico", "delta": 2}])
addu("ler_doenca", "Ler Doença", "Corruptor", "biologia", 2, 3,
     "Um olhar, e você sabe o nome da doença — e quanto tempo resta.",
     "medical", "diagnostica doença, praga e veneno num olhar, incluindo prognóstico")
# — Alma
addp("eco_persistente", "Eco Persistente", "Corruptor", "alma", 2, 3,
     "O desespero que você semeia ecoa mais fundo.",
     [{"trigger": "damage_type", "damage_type": "Psíquico", "delta": 2}])
addp("vontade_ja_ruida", "Vontade já Ruída", "Corruptor", "alma", 2, 4,
     "Não se assusta quem já fez as pazes com a ruína.",
     [{"trigger": "resist", "name": "medo"}])
addu("cheiro_de_mentira", "Cheiro de Mentira", "Corruptor", "alma", 2, 3,
     "Toda história mal contada apodrece por dentro; você sente onde.",
     "social", "sente a mentira apodrecendo numa história — o ponto exato onde a versão cede")
# — Inorgânica
addp("toque_corrosivo", "Toque Corrosivo", "Corruptor", "inorganica", 2, 3,
     "Tudo que você toca começa a ceder — inclusive o que o inimigo veste.",
     [{"trigger": "basic_attack_dot", "name": "Corrosão", "dot": 1, "duration": 2}])
addp("pele_de_oxido", "Pele de Óxido", "Corruptor", "inorganica", 2, 4,
     "A ferrugem que você veste amortece o que a lâmina queria.",
     [{"trigger": "always", "stat": "ac", "delta": 1}])
addu("ponto_fraco", "Ponto Fraco", "Corruptor", "inorganica", 2, 3,
     "Toda estrutura tem o parafuso que, cedendo, entrega o resto.",
     "engineering", "acha o ponto exato que, cedendo, derruba uma estrutura ou trava um mecanismo")

# ===== ARCANISTA CINZENTO — tronco =====
addu("deteccao_tecnica", "Detecção Técnica", "Arcanista Cinzento", None, 1, 1,
     "Éter ativo e residual, lidos como um instrumento lê: o quê, quando, com que vazão.",
     "detection", "lê éter ativo/residual numa cena: o que foi conjurado, quando e com que intensidade")
addu("engenharia_de_campo", "Engenharia de Campo", "Arcanista Cinzento", None, 1, 1,
     "Não há mecanismo quebrado; há mecanismo mal explicado.",
     "engineering", "conserta, desarma e reconfigura mecanismos com o que a cena oferece")
addp("disciplina_da_caldeira", "Disciplina da Caldeira", "Arcanista Cinzento", None, 1, 2,
     "Vazão certa, pressão certa: o Abismo passa pelo instrumento sem morar em você.",
     [{"trigger": "charge_discount", "delta": 1}])
# — Calibrado
addp("valvula_extra", "Válvula Extra", "Arcanista Cinzento", "calibrado", 2, 3,
     "Nada de desperdício: cada descarga sai pelo preço mínimo.",
     [{"trigger": "entropy_cost_reduction", "category": "Arcano", "delta": 1}])
addp("medidor_fino", "Medidor Fino", "Arcanista Cinzento", "calibrado", 2, 4,
     "Quem mede duas vezes dispara uma.",
     [{"trigger": "always", "stat": "attack", "delta": 1}])
addu("calibrar_aparelho", "Calibrar Aparelho", "Arcanista Cinzento", "calibrado", 2, 3,
     "Todo aparelho rende mais na mão de quem entende a válvula.",
     "engineering", "ajusta instrumento alheio (arcano ou mecânico) para render mais — ou falhar na hora certa")
# — Descoberto
addp("pele_marcada", "Pele Marcada", "Arcanista Cinzento", "descoberto", 2, 3,
     "As marcas que o éter deixou respondem quando a Carga sobe.",
     [{"trigger": "carga_embrace", "stat": "damage", "per_tier": 1}])
addp("veias_condutoras", "Veias Condutoras", "Arcanista Cinzento", "descoberto", 2, 4,
     "O corpo virou condutor; conduz mais do que devia.",
     [{"trigger": "entropy_max_bonus", "delta": 3}])
addu("sentir_eter", "Sentir Éter", "Arcanista Cinzento", "descoberto", 2, 3,
     "Sem instrumento, sem filtro: a pele sabe primeiro.",
     "detection", "sente éter pela pele nua — direção, densidade e perigo, sem instrumento")
# — Improvisador
addp("engenhoca_pronta", "Engenhoca Pronta", "Arcanista Cinzento", "improvisador", 2, 3,
     "Sempre há algo na sua mão antes de haver um plano.",
     [{"trigger": "initiative_attr", "attr": "int"}])
addp("pecas_no_bolso", "Peças no Bolso", "Arcanista Cinzento", "improvisador", 2, 4,
     "Entre você e o golpe, sempre existe uma sucata sacrificável.",
     [{"trigger": "always", "stat": "ac", "delta": 1}])
addu("ferramenta_de_sucata", "Ferramenta de Sucata", "Arcanista Cinzento", "improvisador", 2, 3,
     "Funciona uma vez, talvez duas. Quase sempre basta.",
     "engineering", "monta na hora, de sucata, a ferramenta que a cena pede — de vida curta")

# ===== MÉDICO DE CAMPO — tronco =====
addu("diagnostico_social", "Diagnóstico Social", "Médico de Campo", None, 1, 1,
     "A conversa também é um paciente: estresse, mentira e doença aparecem no corpo de quem fala.",
     "social", "lê estresse, mentira e doença no corpo e na voz de quem fala")
addu("aritmetica_de_desastre", "Aritmética de Desastre", "Médico de Campo", None, 1, 1,
     "Quantos, quão grave, quem primeiro. Em segundos.",
     "investigation", "numa cena de desastre, calcula rápido: quantos feridos, gravidade, ordem de atendimento")
addp("triagem", "Triagem", "Médico de Campo", None, 1, 2,
     "Quem está mais perto do fim recebe mais de você — sempre foi assim.",
     [{"trigger": "heal_bonus_low", "threshold": 0.25, "delta": 5}])
# — Cirurgião de Trincheira
addp("sangue_frio", "Sangue Frio", "Médico de Campo", "cirurgiao_trincheira", 2, 3,
     "O medo espera a cirurgia acabar; depois, se quiser, volta.",
     [{"trigger": "resist", "name": "medo"}])
addp("instinto_de_trincheira", "Instinto de Trincheira", "Médico de Campo", "cirurgiao_trincheira", 2, 4,
     "Você lê a cena como lê um ferimento: primeiro o que mata, depois o resto.",
     [{"trigger": "initiative_attr", "attr": "int"}])
addu("milagre_improvisado", "Milagre Improvisado", "Médico de Campo", "cirurgiao_trincheira", 2, 3,
     "Barro, pano e teimosia fazem o que um hospital faria.",
     "medical", "improvisa com material precário um procedimento digno de hospital — uma vez por paciente")
# — Boticário
addp("composto_estavel", "Composto Estável", "Médico de Campo", "boticario", 2, 3,
     "Fórmula estável desperdiça menos — do frasco e de você.",
     [{"trigger": "entropy_cost_reduction", "category": "Suporte", "delta": 1}])
addp("reservas_preparadas", "Reservas Preparadas", "Médico de Campo", "boticario", 2, 4,
     "Quem prepara antes carrega mais.",
     [{"trigger": "entropy_max_bonus", "delta": 2}])
addu("destilar_remedio", "Destilar Remédio", "Médico de Campo", "boticario", 2, 3,
     "A fauna que mata é a farmácia que sobra.",
     "medical", "destila remédio do veneno e da flora local — cura a partir do que fere")
# — Cirurgião de Ferro
addp("proteses_proprias", "Próteses Próprias", "Médico de Campo", "cirurgiao_ferro", 2, 3,
     "Carne reforçada com aço não sangra fácil.",
     [{"trigger": "resist", "name": "sangramento"}])
addp("armadura_de_oficio", "Armadura de Ofício", "Médico de Campo", "cirurgiao_ferro", 2, 4,
     "O avental tem placas; o ofício ensinou onde.",
     [{"trigger": "always", "stat": "ac", "delta": 1}])
addu("forjar_membro", "Forjar Membro", "Médico de Campo", "cirurgiao_ferro", 2, 3,
     "O corpo acaba; o ofício continua de onde ele parou.",
     "engineering", "forja, ajusta e conserta membros mecânicos e próteses — inclusive em campo")


# --- classes ----------------------------------------------------------------
def branch(name, identity):
    return {"name": name, "identity": identity}

CLASSES = {
    "Devoto do Abismo": {
        "description": "Ama o Abismo: avança na direção da incerteza porque a deseja.",
        "role": "tank", "posture": "ama",
        "guide_quote": "Vocês seguram a linha com medo. Eu seguro porque quero que ele me escolha primeiro.",
        "passive": "Convite: provocações escalam com a Entropia acumulada no combate.",
        # spec letalidade-early-game-v2 (alavanca 3): HP base subido (baseline 38 → 40)
        # p/ dar piso de sobrevivência ao early-game; afinado por cima pela spec de balanceamento.
        "base_stats": {"hp": 40, "entropy": 14, "mana": 0, "stamina": 0, "defense": 16,
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
        # spec letalidade-early-game-v2 (alavanca 2): +1 poção inicial (recovery cedo).
        "starting_equipment": ["espada_gasta", "escudo_amassado", "pocao_cura", "pocao_cura"],
    },
    "Sangromante": {
        "description": "Negocia com o Abismo: paga em sangue pelo que precisa.",
        "role": "dano corpo-a-corpo", "posture": "negocia",
        "guide_quote": "Tudo tem preço. Eu só pago à vista.",
        "passive": "Contrato de Sangue: auto-dano vira Entropia de sangue.",
        # spec letalidade-early-game-v2 (alavanca 3): HP base 26 → 30 (frágil demais nível 1).
        "base_stats": {"hp": 30, "entropy": 16, "mana": 0, "stamina": 0, "defense": 12,
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
        # spec letalidade-early-game-v2 (alavanca 2): +1 poção inicial.
        "starting_equipment": ["adaga_ferro", "pocao_cura", "pocao_cura"],
    },
    "Corruptor": {
        "description": "Trabalha JUNTO com o Abismo: acelera a decadência que já existe.",
        "role": "controle / DoT", "posture": "trabalha junto",
        "guide_quote": "Eu não trago a ruína. Só chego mais cedo.",
        "passive": "Parceria: a decadência ao seu redor te alimenta.",
        # spec letalidade-early-game-v2 (alavanca 3): HP base 28 → 30.
        "base_stats": {"hp": 30, "entropy": 18, "mana": 0, "stamina": 0, "defense": 13,
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
        # spec letalidade-early-game-v2 (alavanca 2): +1 poção inicial.
        "starting_equipment": ["cajado_de_galhos", "pocao_cura", "pocao_cura"],
    },
    "Arcanista Cinzento": {
        "description": "Manipula o Abismo por um instrumento: canaliza a entropia e a descarrega.",
        "role": "dano/controle à distância", "posture": "manipula",
        "guide_quote": "A ferramenta segura o que a mão não deveria tocar.",
        "passive": "Caldeira: canalizar gera Entropia para a próxima descarga.",
        # spec letalidade-early-game-v2 (alavanca 3): HP base 22 → 26 (a classe que
        # mais morria nível 1 no run 20260720-093014).
        "base_stats": {"hp": 26, "entropy": 20, "mana": 0, "stamina": 0, "defense": 11,
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
        # spec letalidade-early-game-v2 (alavanca 2): +1 poção inicial.
        "starting_equipment": ["cajado_rachado", "pocao_cura", "pocao_cura"],
    },
    "Médico de Campo": {
        "description": "Nega o Abismo: mantém vivo o que ele quer levar.",
        "role": "suporte / cura", "posture": "nega",
        "guide_quote": "Enquanto eu respirar, você respira.",
        "passive": "Triagem: cura mais quem está mais perto do fim.",
        # spec letalidade-early-game-v2 (alavanca 3): HP base 28 → 30.
        "base_stats": {"hp": 30, "entropy": 16, "mana": 0, "stamina": 0, "defense": 14,
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
        # spec letalidade-early-game-v2 (alavanca 2): Médico começa com 3 poções.
        "starting_equipment": ["serra_cirurgica", "pocao_cura", "pocao_cura", "pocao_cura"],
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
# validação: requires apontam para ids existentes, sem ramo cruzado
for aid, a in AB.items():
    for r in a.get("requires", []):
        assert r in AB, f"{aid}: requires {r} inexistente"
        assert AB[r].get("branch") in (None, a.get("branch")), f"{aid}: requires ramo cruzado"
print("validação OK")
