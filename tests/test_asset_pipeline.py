from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from services.asset_pipeline import can_serve, object_key, process_image


def _png() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (640, 480), (60, 20, 20))
    image.info["comment"] = "segredo"
    image.save(output, "PNG")
    return output.getvalue()


def test_pipeline_valida_converte_variantes_e_remove_metadata():
    variants = process_image(_png())
    assert {item.variant for item in variants} == {"full", "thumb"}
    assert all(item.mime_type == "image/webp" and len(item.sha256) == 64 for item in variants)
    for item in variants:
        with Image.open(BytesIO(item.payload)) as image:
            assert image.format == "WEBP" and "comment" not in image.info


def test_pipeline_rejeita_bytes_falsos_e_gates_segredo():
    with pytest.raises(ValueError):
        process_image(b"not-a-png")
    assert not can_serve(visibility="secret", revealed=False)
    assert can_serve(visibility="secret", revealed=True)


def test_object_key_e_server_side_e_sanitizada():
    owner, game, asset = uuid4(), uuid4(), uuid4()
    key = object_key(owner_id=owner, game_id=game, asset_kind="npc",
                     entity_id="Lady Áurea", asset_id=asset, variant="thumb", sha256="a" * 64)
    assert ".." not in key and key.startswith(f"users/{owner}/games/{game}/npc/")
