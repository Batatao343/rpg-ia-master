from collections import Counter, defaultdict

from services import cards
from services.content_validator import validate_cards


def test_lote_tem_distribuicao_e_cobertura_exatas():
    cards.reload_cards()
    late = [card for card in cards.all_cards().values()
            if card.get("origem") == "tiers-5-plus"]
    assert len(late) == 80
    assert Counter((bool(card.get("subclasse")), bool(card.get("apex"))) for card in late) == {
        (False, False): 20, (True, False): 45, (True, True): 15,
    }
    by_branch = defaultdict(list)
    for card in late:
        if card.get("subclasse"):
            by_branch[(card["classe"], card["subclasse"])].append(card)
    assert len(by_branch) == 15
    for branch_cards in by_branch.values():
        assert len(branch_cards) == 4
        assert sum(bool(card.get("apex")) for card in branch_cards) == 1
        non_apex_types = {card["tipo"] for card in branch_cards if not card.get("apex")}
        assert "ativa" in non_apex_types and len(non_apex_types - {"ativa"}) >= 1


def test_lote_sem_efeito_fantasma_e_lint_verde():
    findings = validate_cards()
    errors = [finding for finding in findings if finding.severity == "error"]
    assert not errors, [finding.message for finding in errors]
