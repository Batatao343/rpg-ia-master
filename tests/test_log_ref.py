"""SPEC-262 R2: scripts/log_ref.py devolve o mesmo pseudonimo do servidor e protege o segredo."""
import importlib.util
import uuid
from pathlib import Path

from observability.telemetry import pseudonym

ROOT = Path(__file__).resolve().parents[1]
SECRET = "segredo-de-teste-com-mais-de-16-chars"


def _load():
    spec = importlib.util.spec_from_file_location("log_ref", ROOT / "scripts" / "log_ref.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_result_as_pseudonym(capsys):
    module = _load()
    user = str(uuid.uuid4())
    assert module.main(["owner", user], {"RPG_TELEMETRY_SECRET": SECRET}) == 0
    assert capsys.readouterr().out.strip() == f"owner_ref={pseudonym(user, secret=SECRET)}"


def test_uppercase_uuid_is_canonicalized(capsys):
    module = _load()
    user = str(uuid.uuid4())
    module.main(["game", user.upper()], {"RPG_TELEMETRY_SECRET": SECRET})
    assert capsys.readouterr().out.strip() == f"game_ref={pseudonym(user, secret=SECRET)}"


def test_refuses_without_secret(capsys, tmp_path, monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "ROOT", tmp_path)        # sem .env
    assert module.main(["action", str(uuid.uuid4())], {}) == 3
    assert "ausente" in capsys.readouterr().err


def test_refuses_short_secret(capsys, tmp_path, monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert module.main(["action", str(uuid.uuid4())], {"RPG_TELEMETRY_SECRET": "curto"}) == 3


def test_secret_never_accepted_from_argv(capsys):
    module = _load()
    assert module.main(["owner", str(uuid.uuid4()), f"--secret={SECRET}"], {}) == 2
    err = capsys.readouterr().err
    assert SECRET not in err and "argumento" in err


def test_secret_from_stdin(monkeypatch, capsys):
    import io
    module = _load()
    user = str(uuid.uuid4())
    monkeypatch.setattr("sys.stdin", io.StringIO(SECRET + "\n"))
    assert module.main(["owner", user, "--stdin"], {}) == 0
    assert capsys.readouterr().out.strip() == f"owner_ref={pseudonym(user, secret=SECRET)}"
