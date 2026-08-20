from pathlib import Path


def test_frontend_nao_chama_saves_protegidos_antes_de_confirmar_auth():
    source = Path("web/src/App.tsx").read_text(encoding="utf-8")
    auth = source.index("const config = await api.getAuthConfig()")
    guard = source.index("return; // não chama rotas protegidas antes do login")
    saves = source.index("const list = await api.getSaves()")
    assert auth < guard < saves
