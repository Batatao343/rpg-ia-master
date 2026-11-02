"""SPEC-349: gate determinístico de unicidade de criatura (regras U1-U13 + R29).

Fonte única: ``content_validator.validate_bestiary_identity`` e ``scripts/bestiario/lint.py``
chamam este módulo. Sem LLM; a similaridade é lexical (Jaccard, ``card_lint.similarity``)
com ``embed`` opcional.

Convenções:
- uma *ficha* é o dict de ``data/bestiario/fichas/<regiao>.yaml`` (``criaturas[]``);
- ``status`` em {nova, reinventada, adotada} = "nova" para o gate; ``retro`` = legado;
- par com ao menos uma ficha nova -> erro; par só de retros -> aviso (o legado não é apagado).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from services import card_lint
from services.card_lint import Issue
from services.encounter_manifest import name_tokens, resolve_bestiary_name

ROOT = Path(__file__).resolve().parent.parent
BESTIARIO_DIR = ROOT / "data" / "bestiario"
FICHAS_DIR = BESTIARIO_DIR / "fichas"
LEXICO_PATH = BESTIARIO_DIR / "_lexico_bestiario.txt"

# --------------------------------------------------------------------------
# Enums fechados (§3.2)
# --------------------------------------------------------------------------
ENUMS: dict[str, frozenset[str]] = {
    "plano_corporal": frozenset(
        "bipede_ereto bipede_curvado quadrupede hexapode_ou_mais serpentiforme segmentado radial "
        "sessil_ancorado alado composto hospedeiro_parasita acoplado".split()
    ),
    "material": frozenset(
        "osso carne_exposta ferro_ferrugem escoria_fuligem quitina vidro_cristal eter_cristalizado "
        "cera_sebo lama_turfa couro_tecido madeira_fibra sal_mineral cinza".split()
    ),
    "escala": frozenset("miuda pequena humana grande enorme".split()),
    "locomocao": frozenset(
        "anda rasteja salta escala_paredes nada plana_voa cava ancorada rola".split()
    ),
    "percepcao": frozenset(
        "visao calor som vibracao sangue_cheiro eter medo_emocao respiracao luz".split()
    ),
    "papel_tatico": frozenset(
        "batedor_rapido bruto_de_linha guarda_protetor controlador emboscador artilharia drenador "
        "quebra_defesa perseguidor_marca saqueador suporte sacrificial tanque_reativo".split()
    ),
}
FAMILIAS_VALORIA = ("corpo_reescrito", "besta_entropia", "humanoide_preco", "demonio_encarnado")
STATUS_NOVOS = frozenset({"nova", "reinventada", "adotada"})
DEMONIOS = frozenset(
    "npc_daruun npc_maalrek npc_vhrak npc_veth npc_dorrhen npc_skarath npc_veleth npc_urath "
    "npc_thessavar npc_solvhara npc_lyss npc_fehk npc_morvath".split()
)
FONTES_CORPO_REESCRITO = frozenset({"praga_ferro", "praga_ossos", "abismo", "eter", "dragao"})
# Eixos comparados em U3 (anatomia.* + papel_tatico).
EIXOS_U3 = ("plano_corporal", "material", "escala", "locomocao", "percepcao", "papel_tatico")
EIXOS_PADRAO_ENUM = ("plano_corporal", "material", "escala", "locomocao", "percepcao")

# Limiares (D6) - calibrados em Etapa 1 (ver SPEC-349 §9).
LIM_ANATOMIA = 0.45
LIM_GANCHO = 0.45
LIM_SILHUETA = 0.5
LIM_ANATOMIA_CODEX = 0.5
LIM_TELEGRAFO = 0.5
LIM_SILHUETA_GLOBAL = 0.6
MAX_EIXOS_IGUAIS = 3

COTAS_PADRAO: dict[str, Any] = {
    "total": (20, 25),
    "familia_min": 4,
    "familias": FAMILIAS_VALORIA,
    "categorias": {"lacaio": (6, None), "padrao": (6, None), "elite": (4, None), "chefe": (1, 2)},
    "papeis_min": 8,
    "arquetipos_min": 7,
}
COTAS_ONDA: dict[str, dict[str, Any]] = {
    "nova_arcadia": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "demonios_obrigatorios": ("npc_fehk",),
        "habitat_min": {"na_anel_dourado": 5, "na_anel_ferro": 5, "na_anel_lama": 5},
    },
    # SPEC-359 (onda 2): Solvhara é o demônio de lugar fixo do Pântano
    "pantano_melancolia": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "demonios_obrigatorios": ("npc_solvhara",),
        "habitat_min": {"pantano_melancolia": 8, "pm_profundezas": 8, "pm_cripta_afogada": 3},
    },
    "pradaria_ruinas": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "habitat_min": {"pradaria_ruinas": 10, "pr_ruinas_assombradas": 8, "pr_vaelorn": 4},
    },
    "brekmar": {
        **COTAS_PADRAO,
        "demonios_min": 5,
        "demonios_obrigatorios": ("npc_lyss",),
        "habitat_min": {"brekmar": 10, "bk_docas_velhas": 8},
    },
    "deserto_zhur": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "demonios_obrigatorios": ("npc_urath",),
        "habitat_min": {"deserto_zhur": 15, "dz_borda_do_vazio": 4},
    },
    "costa_negra": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "habitat_min": {"costa_negra": 8, "cn_o_trono": 5},
    },
    "montanhas_afiadas": {
        **COTAS_PADRAO,
        "demonios_min": 5,
        "habitat_min": {
            "montanhas_afiadas": 8,
            "ma_boca": 8,
            "ma_saidas_baixas": 6,
            "ma_forja_profunda": 4,
        },
    },
    "floresta_sussurros": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "demonios_obrigatorios": ("npc_thessavar",),
        "habitat_min": {"floresta_sussurros": 14, "fs_fronteira_xylos": 6},
    },
    "selva_xylos": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "habitat_min": {"selva_xylos": 12, "sx_profundezas": 4, "sx_cidades_hospedeiros": 6},
    },
    "skallgard": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "habitat_min": {
            "skallgard": 14,
            "sk_farol_chama_negra": 4,
            "sk_fortaleza_vorr": 3,
            "sk_salao_do_jarl": 2,
        },
    },
    "aethelgard": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "demonios_obrigatorios": ("npc_morvath",),
        "habitat_min": {"aethelgard": 8, "ae_ruinas_submersas": 10, "ae_camara_seca": 5},
    },
    "ophidia": {
        **COTAS_PADRAO,
        "demonios_min": 4,
        "habitat_min": {"ophidia": 15},
    },
}


# --------------------------------------------------------------------------
# Léxico e utilitários
# --------------------------------------------------------------------------
_LEX: dict[str, list[str]] | None = None


def _fold(text: Any) -> str:
    t = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def lexico() -> dict[str, list[str]]:
    global _LEX
    if _LEX is None:
        out: dict[str, list[str]] = {}
        section = ""
        if LEXICO_PATH.is_file():
            for raw in LEXICO_PATH.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1]
                    out.setdefault(section, [])
                elif section:
                    out[section].append(_fold(line))
        _LEX = out
    return _LEX


def reload() -> None:
    global _LEX
    _LEX = None


def _has_term(folded: str, term: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?:s|es)?(?![a-z0-9])", folded))


def _terms_in(text: Any, terms: Iterable[str]) -> list[str]:
    folded = _fold(text)
    return [t for t in terms if _has_term(folded, t)]


def nucleo_nome(nome: str) -> str:
    toks = name_tokens(nome)
    return toks[0] if toks else ""


def is_nova(ficha: dict) -> bool:
    return ficha.get("status") in STATUS_NOVOS


def _anat(ficha: dict, eixo: str) -> Any:
    if eixo == "papel_tatico":
        return ficha.get("papel_tatico")
    # vaga (tabuleiro) guarda os eixos no topo; ficha, em ``anatomia``
    return (ficha.get("anatomia") or {}).get(eixo) or ficha.get(eixo)


def eixos_iguais(a: dict, b: dict) -> int:
    """Quantos dos 6 eixos (plano, material, escala, locomoção, percepção, papel) coincidem.

    Eixo ausente em qualquer lado (ex.: ``vagas`` sem escala) não conta como igual."""
    n = 0
    for eixo in EIXOS_U3:
        va, vb = _anat(a, eixo), _anat(b, eixo)
        if va and vb and va == vb:
            n += 1
    return n


def _triple(f: dict) -> tuple | None:
    t = (_anat(f, "plano_corporal"), _anat(f, "material"), _anat(f, "papel_tatico"))
    return t if all(t) else None


def _iss(level: str, code: str, msg: str) -> Issue:
    return Issue(level, code, msg)


def _pair_level(a: dict, b: dict) -> str:
    return "error" if (is_nova(a) or is_nova(b)) else "warn"


def _label(f: dict) -> str:
    return str(f.get("id") or f.get("vaga") or f.get("nome") or "?")


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def _load_yaml_files(regiao: str | None) -> list[dict]:
    docs: list[dict] = []
    if not FICHAS_DIR.is_dir():
        return docs
    for p in sorted(FICHAS_DIR.glob("*.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if regiao is None or doc.get("regiao") == regiao:
            docs.append(doc)
    return docs


def load_fichas(regiao: str | None = None) -> dict[str, dict]:
    """``{id: ficha}`` (com ``regiao`` injetada). ``None`` = todas as regiões."""
    out: dict[str, dict] = {}
    for doc in _load_yaml_files(regiao):
        for f in doc.get("criaturas") or []:
            out[str(f["id"])] = {
                **f,
                "regiao": doc.get("regiao"),
                "onda": f.get("onda", doc.get("onda")),
            }
    return out


def load_vagas(regiao: str) -> list[dict]:
    for doc in _load_yaml_files(regiao):
        return list(doc.get("vagas") or [])
    return []


# --------------------------------------------------------------------------
# Cotas (U12)
# --------------------------------------------------------------------------
def contar_cotas(items: Iterable[dict]) -> dict[str, Any]:
    """Contagens de fichas/vagas *novas* (retro não conta; vaga sem ``status`` conta).

    ``total`` segue D3: só ``status: nova`` (reinventada/adotada ocupa slot existente).
    Os demais contadores (família, categoria, papel, habitat…) incluem reinventadas/adotadas."""
    its = [f for f in items if f.get("status", "nova") in STATUS_NOVOS]
    dem = {
        (f.get("origem_lore") or {}).get("detalhe")
        for f in its
        if f.get("familia") == "demonio_encarnado" and (f.get("origem_lore") or {}).get("detalhe")
    }
    habitat: Counter = Counter()
    for f in its:
        for h in f.get("habitat") or []:
            habitat[h] += 1
    return {
        # D3: reinventadas/adotadas são substituição, não acréscimo; só ``nova`` conta no total
        "total": sum(1 for f in its if f.get("status", "nova") == "nova"),
        "familias": Counter(f.get("familia") for f in its),
        "categorias": Counter(f.get("categoria") for f in its),
        "papeis": {f.get("papel_tatico") for f in its if f.get("papel_tatico")},
        "arquetipos": {f.get("arquetipo") for f in its if f.get("arquetipo")},
        "demonios": dem,
        "habitat": habitat,
    }


def _check_cotas(items: list[dict], cotas: dict[str, Any]) -> list[Issue]:
    if not cotas:
        return []
    c = contar_cotas(items)
    out: list[Issue] = []

    def err(msg: str) -> None:
        out.append(_iss("error", "U12", msg))

    if "total" in cotas:
        lo, hi = cotas["total"]
        if not lo <= c["total"] <= hi:
            err(f"total de criaturas novas {c['total']} fora de {lo}-{hi}")
    for fam in cotas.get("familias", ()):
        if c["familias"].get(fam, 0) < cotas.get("familia_min", 0):
            err(f"família {fam}: {c['familias'].get(fam, 0)} < {cotas.get('familia_min')}")
    for cat, (lo, hi) in (cotas.get("categorias") or {}).items():
        n = c["categorias"].get(cat, 0)
        if n < lo or (hi is not None and n > hi):
            err(f"categoria {cat}: {n} fora de {lo}-{hi if hi is not None else '∞'}")
    if len(c["papeis"]) < cotas.get("papeis_min", 0):
        err(f"papéis táticos distintos {len(c['papeis'])} < {cotas['papeis_min']}")
    if len(c["arquetipos"]) < cotas.get("arquetipos_min", 0):
        err(f"arquétipos distintos {len(c['arquetipos'])} < {cotas['arquetipos_min']}")
    if len(c["demonios"]) < cotas.get("demonios_min", 0):
        err(f"crias de demônios distintos {len(c['demonios'])} < {cotas['demonios_min']}")
    for d in cotas.get("demonios_obrigatorios", ()):
        if d not in c["demonios"]:
            err(f"falta cria de {d}")
    for h, n in (cotas.get("habitat_min") or {}).items():
        if c["habitat"].get(h, 0) < n:
            err(f"habitat {h}: {c['habitat'].get(h, 0)} < {n}")
    return out


# --------------------------------------------------------------------------
# Regras por ficha (U5, U8-U11)
# --------------------------------------------------------------------------
def _ref_ok(ref: str) -> bool:
    path, _, line = str(ref).rpartition(":")
    if not path or not line.isdigit():
        return False
    p = ROOT / path
    if not p.is_file():
        return False
    with open(p, encoding="utf-8", errors="replace") as fh:
        total = sum(1 for _ in fh)
    return 1 <= int(line) <= total


def checar_fisico(texto: str, minimo: int = 3) -> list[str]:
    """U9: texto de criatura física. ``minimo`` de partes do corpo e nenhum termo conceitual."""
    lex = lexico()
    folded = _fold(texto)
    partes = {p for p in lex.get("partes", []) if _has_term(folded, p)}
    out = []
    if len(partes) < minimo:
        out.append(f"anatomia.texto cita {len(partes)} partes do corpo (<{minimo})")
    conc = _terms_in(texto, lex.get("conceituais", []))
    if conc:
        out.append(f"anatomia conceitual {conc}")
    return out


def lint_ficha(ficha: dict, *, exigir_revisao: bool = True) -> list[Issue]:
    """U5, U8-U11 numa ficha. Retro não é julgada (legado não é apagado nem reescrito)."""
    if not is_nova(ficha):
        return []
    out: list[Issue] = []
    lex = lexico()
    fid = _label(ficha)
    anat = ficha.get("anatomia") or {}

    # enums fechados
    for eixo in EIXOS_PADRAO_ENUM:
        if anat.get(eixo) not in ENUMS[eixo]:
            out.append(
                _iss("error", "ENUM", f"{fid}: anatomia.{eixo}={anat.get(eixo)!r} fora do enum")
            )
    if ficha.get("papel_tatico") not in ENUMS["papel_tatico"]:
        out.append(
            _iss("error", "ENUM", f"{fid}: papel_tatico={ficha.get('papel_tatico')!r} fora do enum")
        )

    # U5 - variante
    for campo in ("nome", "silhueta"):
        hit = _terms_in(ficha.get(campo), lex.get("marcadores_variante", []))
        if hit:
            out.append(_iss("error", "U5", f"{fid}: {campo} usa marcador de variante {hit}"))

    # U8 - genérico de manual / léxico de Cartas
    proib = lex.get("proibidos_nome", []) + card_lint.lexico().get("proibidos", [])
    for campo, valor in (
        ("nome", ficha.get("nome")),
        ("description", ficha.get("description")),
        ("anatomia.texto", anat.get("texto")),
        ("silhueta", ficha.get("silhueta")),
    ):
        hit = _terms_in(valor, proib)
        if hit:
            out.append(_iss("error", "U8", f"{fid}: {campo} contém termo proibido {hit}"))

    # U9 - físico
    for msg in checar_fisico(anat.get("texto") or ""):
        out.append(_iss("error", "U9", f"{fid}: {msg}"))

    # U10 - lore
    ol = ficha.get("origem_lore") or {}
    for ref in ol.get("refs") or []:
        if not _ref_ok(ref):
            out.append(_iss("error", "U10", f"{fid}: ref não resolve: {ref}"))
    fam = ficha.get("familia")
    if fam == "demonio_encarnado" and ol.get("detalhe") not in DEMONIOS:
        out.append(
            _iss(
                "error",
                "U10",
                f"{fid}: demonio_encarnado sem npc_<demônio> válido ({ol.get('detalhe')!r})",
            )
        )
    if fam == "humanoide_preco" and not (ficha.get("faccao") or ol.get("fonte") == "eter"):
        out.append(_iss("error", "U10", f"{fid}: humanoide_preco sem facção nem fonte eter"))
    if fam == "corpo_reescrito" and ol.get("fonte") not in FONTES_CORPO_REESCRITO:
        out.append(_iss("error", "U10", f"{fid}: corpo_reescrito com fonte {ol.get('fonte')!r}"))

    # U11 - revisão independente
    if exigir_revisao:
        rev = ficha.get("revisor_unicidade")
        if not card_lint.revisor_valido(rev):
            out.append(_iss("error", "U11", f"{fid}: revisor_unicidade inválido ({rev!r})"))
        elif str(rev).strip().lower() == str(ficha.get("autor") or "").strip().lower():
            out.append(_iss("error", "U11", f"{fid}: revisor igual ao autor"))
        if ficha.get("revisao") != "aprovada":
            out.append(
                _iss("error", "U11", f"{fid}: revisao={ficha.get('revisao')!r} (exige aprovada)")
            )
    return out


# --------------------------------------------------------------------------
# Regras da região
# --------------------------------------------------------------------------
def _tactical(ficha: dict, bestiary: dict) -> tuple[list, Any, str]:
    tp = (bestiary.get(ficha.get("id")) or {}).get("tactical_profile") or {}
    ass = tp.get("assinatura") or {}
    padrao = ficha.get("padrao", tp.get("padrao")) or []
    n = ficha.get("a_cada_n", ass.get("a_cada_n"))
    tele = ficha.get("telegrafo", ass.get("telegrafo")) or ""
    return list(padrao), n, str(tele)


def lint_vagas(vagas: list[dict], cotas: dict[str, Any] | None = None) -> list[Issue]:
    """R8: tabuleiro antes da prosa - U2, U3 e U12 sobre as vagas."""
    out: list[Issue] = []
    for a, b in combinations(vagas, 2):
        ta, tb = _triple(a), _triple(b)
        if ta and ta == tb:
            out.append(_iss("error", "U2", f"vagas {_label(a)}/{_label(b)}: tripla {ta} repetida"))
        if eixos_iguais(a, b) > MAX_EIXOS_IGUAIS:
            out.append(
                _iss(
                    "error",
                    "U3",
                    f"vagas {_label(a)}/{_label(b)}: {eixos_iguais(a, b)} eixos iguais",
                )
            )
    out += _check_cotas(vagas, cotas or {})
    return out


def lint_regiao(
    regiao: str,
    fichas: list[dict],
    *,
    bestiary: dict,
    codex_docs: list[dict],
    cotas: dict[str, Any] | None = None,
    cards: dict[str, dict] | None = None,
    embed: Callable[[str], list[float]] | None = None,
) -> list[Issue]:
    """U1-U4, U6, U7, U12, U13. ``cotas=None`` usa as da onda (ou COTAS_PADRAO)."""
    if cotas is None:
        cotas = COTAS_ONDA.get(regiao, COTAS_PADRAO)
    out: list[Issue] = []
    sim = lambda a, b: card_lint.similarity(a or "", b or "", embed)  # noqa: E731

    # U1 - ids e nomes únicos
    ids = Counter(f.get("id") for f in fichas)
    for fid, n in ids.items():
        if n > 1:
            out.append(_iss("error", "U1", f"id duplicado na região: {fid}"))
    tok_fichas: dict[tuple, str] = {}
    for f in fichas:
        if not is_nova(f):
            continue
        fid, nome = f.get("id"), f.get("nome") or ""
        if not 2 <= len(nome.split()) <= 4:
            out.append(_iss("error", "U1", f"{fid}: nome deve ter 2-4 palavras ({nome!r})"))
        folded = _fold(nome)
        toks = tuple(sorted(set(name_tokens(nome))))
        for bid, entry in bestiary.items():
            if bid == fid:
                continue
            if _fold(entry.get("name")) == folded or (
                toks and tuple(sorted(set(name_tokens(entry.get("name", ""))))) == toks
            ):
                out.append(_iss("error", "U1", f"{fid}: nome já usado no bestiário por {bid}"))
        for d in codex_docs:
            if d.get("id") != fid and _fold(d.get("name")) == folded:
                out.append(_iss("error", "U1", f"{fid}: nome já usado no Codex por {d.get('id')}"))
        if toks in tok_fichas and tok_fichas[toks] != fid:
            out.append(
                _iss("error", "U1", f"{fid}: tokens de nome iguais aos de {tok_fichas[toks]}")
            )
        tok_fichas[toks] = fid
        if fid in bestiary and resolve_bestiary_name(nome, bestiary) != fid:
            out.append(_iss("error", "U1", f"{fid}: resolve_bestiary_name({nome!r}) != id"))

    # pares
    for a, b in combinations(fichas, 2):
        lvl = _pair_level(a, b)
        pa, pb = _label(a), _label(b)
        ta, tb = _triple(a), _triple(b)
        if ta and ta == tb:
            out.append(_iss(lvl, "U2", f"{pa}/{pb}: tripla {ta} repetida"))
        n = eixos_iguais(a, b)
        if n > MAX_EIXOS_IGUAIS:
            out.append(_iss(lvl, "U3", f"{pa}/{pb}: {n} de 6 eixos iguais"))
        na, nb = nucleo_nome(a.get("nome", "")), nucleo_nome(b.get("nome", ""))
        if na and na == nb:
            out.append(_iss(lvl, "U4", f"{pa}/{pb}: núcleo de nome repetido ({na!r})"))
        xa, xb = (a.get("anatomia") or {}).get("texto"), (b.get("anatomia") or {}).get("texto")
        for campo, va, vb, lim in (
            ("anatomia", xa, xb, LIM_ANATOMIA),
            ("gancho", a.get("gancho"), b.get("gancho"), LIM_GANCHO),
            ("silhueta", a.get("silhueta"), b.get("silhueta"), LIM_SILHUETA),
        ):
            if va and vb and (s := sim(va, vb)) >= lim:
                out.append(_iss(lvl, "U6", f"{pa}/{pb}: {campo} parecidos ({s:.2f} >= {lim})"))
        # U7
        ca = (a.get("mecanica_assinatura") or {}).get("carta")
        cb = (b.get("mecanica_assinatura") or {}).get("carta")
        if ca and ca == cb:
            out.append(_iss(lvl, "U7", f"{pa}/{pb}: Carta própria compartilhada ({ca})"))
        elif ca and cb and cards and ca in cards and cb in cards:
            if card_lint.signature(cards[ca]) == card_lint.signature(cards[cb]):
                out.append(_iss(lvl, "U7", f"{pa}/{pb}: assinatura mecânica igual ({ca}/{cb})"))
        # U13
        pda, nda, tela = _tactical(a, bestiary)
        pdb, ndb, telb = _tactical(b, bestiary)
        if pda and pdb:
            sa = card_lint.signature(cards[ca]) if cards and ca in (cards or {}) else None
            sb = card_lint.signature(cards[cb]) if cards and cb in (cards or {}) else None
            if (pda, nda, sa) == (pdb, ndb, sb):
                out.append(_iss(lvl, "U13", f"{pa}/{pb}: padrão + cadência + assinatura iguais"))
            if tela and telb and sim(tela, telb) >= LIM_TELEGRAFO:
                out.append(_iss(lvl, "U13", f"{pa}/{pb}: telégrafos parecidos"))

    # U6 contra o Codex da região
    for f in fichas:
        if not is_nova(f):
            continue
        texto = (f.get("anatomia") or {}).get("texto") or ""
        for d in codex_docs:
            if d.get("id") == f.get("id") or regiao not in (d.get("tags") or []):
                continue
            s = sim(texto, d.get("body") or "")
            if s >= LIM_ANATOMIA_CODEX:
                out.append(
                    _iss(
                        "error",
                        "U6",
                        f"{_label(f)}: anatomia parecida com o Codex {d.get('id')} ({s:.2f})",
                    )
                )

    out += _check_cotas(fichas, cotas)
    return out


# --------------------------------------------------------------------------
# Global (R27/R29)
# --------------------------------------------------------------------------
def lint_global(
    fichas_por_regiao: dict[str, list[dict]], *, esteira: dict | None = None
) -> list[Issue]:
    out: list[Issue] = []
    todas = [(r, f) for r, fs in fichas_por_regiao.items() for f in fs]
    for (ra, a), (rb, b) in combinations(todas, 2):
        if ra == rb:
            continue
        lvl = _pair_level(a, b)
        if a.get("id") == b.get("id") or (
            a.get("nome") and _fold(a.get("nome")) == _fold(b.get("nome"))
        ):
            out.append(
                _iss("error", "R29", f"{_label(a)}/{_label(b)}: id/nome repetido entre regiões")
            )
        if is_nova(a) or is_nova(b):
            s = card_lint.similarity(a.get("silhueta") or "", b.get("silhueta") or "")
            if s >= LIM_SILHUETA_GLOBAL:
                out.append(
                    _iss(
                        lvl,
                        "R29",
                        f"{_label(a)}/{_label(b)}: silhueta parecida entre regiões ({s:.2f})",
                    )
                )
        da, db = (a.get("origem_lore") or {}), (b.get("origem_lore") or {})
        if (
            a.get("familia") == b.get("familia") == "demonio_encarnado"
            and da.get("detalhe")
            and da.get("detalhe") == db.get("detalhe")
            and (_anat(a, "plano_corporal"), _anat(a, "material"))
            == (_anat(b, "plano_corporal"), _anat(b, "material"))
        ):
            out.append(
                _iss(
                    lvl,
                    "R29",
                    f"{_label(a)}/{_label(b)}: cria de {da.get('detalhe')} repete anatomia",
                )
            )

    # cobertura dos 13 demônios: só quando as 12 regiões estiverem pousadas (senão é relatório)
    regs = (esteira or {}).get("regioes") or {}
    if regs and all((v or {}).get("status") == "pousada" for v in regs.values()):
        por_dem: dict[str, list[dict]] = {d: [] for d in DEMONIOS}
        for _, f in todas:
            d = (f.get("origem_lore") or {}).get("detalhe")
            if f.get("familia") == "demonio_encarnado" and d in por_dem:
                por_dem[d].append(f)
        for d, fs in sorted(por_dem.items()):
            anatomias = {(_anat(f, "plano_corporal"), _anat(f, "material")) for f in fs}
            if len(fs) < 2 or len(anatomias) < 2:
                out.append(
                    _iss(
                        "error",
                        "R27",
                        f"{d}: {len(fs)} crias / {len(anatomias)} anatomias (mín. 2/2)",
                    )
                )
    return out


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(i.level == "error" for i in issues)


__all__ = [
    "COTAS_ONDA",
    "COTAS_PADRAO",
    "DEMONIOS",
    "ENUMS",
    "Issue",
    "contar_cotas",
    "eixos_iguais",
    "has_errors",
    "lint_ficha",
    "lint_global",
    "lint_regiao",
    "lint_vagas",
    "load_fichas",
    "load_vagas",
    "nucleo_nome",
]
