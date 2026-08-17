from agents import loot
from services import prose_guard


def test_normaliza_terceira_pessoa_do_protagonista():
    text = (
        "O jogador encontra uma moeda. O personagem guarda o achado. "
        "O herói segue adiante."
    )

    rendered = prose_guard.normalize_protagonist_voice(text)

    assert rendered == (
        "Você encontra uma moeda. Você guarda o achado. Você segue adiante."
    )


def test_mensagem_de_loot_preserva_bloco_sistema_byte_a_byte():
    system = "[SISTEMA] Espada de Aço Temperado (raro) e +40 de ouro"

    rendered = loot._player_facing_message(
        "O jogador encontra a espada entre as dunas.", system,
    )

    assert rendered.startswith("Você encontra a espada")
    assert rendered.split("\n\n", 1)[1] == system
