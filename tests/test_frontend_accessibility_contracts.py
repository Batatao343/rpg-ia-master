from pathlib import Path


def test_scene_art_nao_rotula_div_sem_role_e_imagem_tem_alt():
    source = Path("web/src/components/SceneArtwork.tsx").read_text(encoding="utf-8")
    assert '<div className="scene-art" aria-label=' not in source
    assert "alt={scene.asset.alt}" in source
