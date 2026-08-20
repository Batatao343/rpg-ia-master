from services.game_serialization import document_sha256, game_projection


def test_hash_canonico_independe_da_ordem_de_chaves():
    assert document_sha256({"a": 1, "b": 2}) == document_sha256({"b": 2, "a": 1})


def test_projection_tem_status_fechado_e_defaults():
    projection = game_projection({"game_over": True, "player": {}, "world": {}})
    assert projection["status"] == "memorial"
    assert projection["player_level"] == 1
    assert projection["world_day"] == 1
