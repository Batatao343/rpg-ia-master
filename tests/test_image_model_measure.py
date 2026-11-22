"""SPEC-425 R8/R9: measurement script with an injected fake generator (zero network)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from infrastructure.ports import GeneratedImage
from scripts.art import measure_image_model as mim
from services import image_pricing

NEW = "gpt-image-2.6-sunburst"


@pytest.fixture(autouse=True)
def card_with_new_model(monkeypatch):
    monkeypatch.setattr(image_pricing, "_CARD", {**image_pricing._CARD, "extra_models": [NEW]})


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch, tmp_path_factory):
    """Safety net: no test here can build a real generator, read a key or write under docs/."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(mim, "_build_generator", lambda: pytest.fail("generator built"))
    monkeypatch.setattr(mim, "_PROJECT_OUT", tmp_path_factory.mktemp("proj") / "medicao.json")


class Fake:
    def __init__(self, out_tokens=1000, *, usage=None):
        self.calls = []
        self.out_tokens = out_tokens
        self.usage = usage

    def generate(self, request):
        self.calls.append(request)
        usage = self.usage or {
            "input_tokens": 100,
            "output_tokens": self.out_tokens,
            "input_tokens_details": {"text_tokens": 100, "image_tokens": 0},
        }
        return GeneratedImage(b"\x89PNGbytes", "image/png", "req", request.model, usage)


def _case(i=0, model=NEW):
    return mim.Case(model, "portrait", "1024x1536", "medium", "high", f"secret prompt {i}")


def test_roda_o_plano_e_grava_campos_sem_bytes_nem_prompt(tmp_path):
    report: dict = {}
    calls = mim.measure(
        [_case(0), _case(1)], Fake(), max_usd=Decimal("1"), out_dir=tmp_path, report=report
    )
    assert len(calls) == 2 and report["stopped"] is None
    call = calls[0]
    for key in (
        "model", "format", "size", "quality", "complexity", "refs", "endpoint",
        "http_status", "latency_ms", "usage", "cost_usd", "cost_basis",
        "canon_min_hamming", "prompt_hash",
    ):  # fmt: skip
        assert key in call
    assert call["cost_basis"] == "rate_card" and call["endpoint"] == "generations"
    blob = json.dumps({"calls": calls, **report})
    assert "secret prompt" not in blob and "PNG" not in blob
    assert len(list(tmp_path.iterdir())) == 2  # bytes only in the out dir


def test_para_antes_de_passar_do_teto(tmp_path):
    fake, report = Fake(1000), {}  # ~0.03 USD per call
    calls = mim.measure(
        [_case(i) for i in range(20)],
        fake,
        max_usd=Decimal("0.40"),
        out_dir=tmp_path,
        report=report,
    )
    assert 0 < len(calls) < 20 and len(fake.calls) == len(calls)
    assert "budget" in report["stopped"]
    assert Decimal(report["spent_usd"]) <= Decimal("0.40")
    tight = {}
    assert (
        mim.measure([_case(0)], Fake(), max_usd=Decimal("0.20"), out_dir=tmp_path, report=tight)
        == []
    )
    assert "budget" in tight["stopped"]


def test_para_com_cost_basis_diferente_de_rate_card(tmp_path):
    fake, report = Fake(usage={"input_tokens": 5}), {}
    calls = mim.measure(
        [_case(0), _case(1)], fake, max_usd=Decimal("2"), out_dir=tmp_path, report=report
    )
    assert len(calls) == 1 and "cost_basis" in report["stopped"]


def test_para_com_custo_acima_de_025(tmp_path):
    fake, report = Fake(out_tokens=9000), {}  # 9000 * 30 / 1e6 = 0.27
    calls = mim.measure(
        [_case(0), _case(1)], fake, max_usd=Decimal("2"), out_dir=tmp_path, report=report
    )
    assert len(calls) == 1 and "0.25" in report["stopped"]


def test_recusa_max_usd_acima_de_2(tmp_path, capsys):
    with pytest.raises(SystemExit):
        mim.main(["--max-usd", "2.01", "--out-dir", str(tmp_path), "--confirm-spend"])


def test_sem_confirm_spend_nenhuma_chamada(tmp_path, monkeypatch, capsys):
    fake = Fake()
    monkeypatch.setattr(mim, "_build_generator", lambda: fake)
    code = mim.main(["--max-usd", "1", "--out-dir", str(tmp_path)])
    assert code == 0 and fake.calls == []
    assert "plan" in capsys.readouterr().out.lower()


def test_canary_e_um_retrato_com_teto_025(tmp_path, monkeypatch):
    fake = Fake()
    monkeypatch.setattr(mim, "_build_generator", lambda: fake)
    monkeypatch.setattr(mim, "_PROJECT_OUT", tmp_path / "medicao.json")
    plan = mim.canary_plan(NEW)
    assert len(plan) == 1 and plan[0].fmt == "portrait"
    with pytest.raises(SystemExit):
        mim.main(["--canary", "--max-usd", "0.30", "--out-dir", str(tmp_path)])


def test_canary_verdict_faixa_de_tokens_e_hamming():
    base = [{"model": NEW, "format": "portrait", "usage": {"output_tokens": 1000}}]
    ok = {"model": NEW, "usage": {"output_tokens": 1200}, "canon_min_hamming": 20}
    assert mim.canary_verdict(ok, base, hamming_min=14) == []
    far = {**ok, "usage": {"output_tokens": 1400}, "canon_min_hamming": 3}
    assert len(mim.canary_verdict(far, base, hamming_min=14)) == 2


# --- review follow-ups (P2-1, P2-2) -------------------------------------------- #
class Flaky(Fake):
    def generate(self, request):
        if len(self.calls) == 1:
            raise RuntimeError("secret provider message")
        return super().generate(request)


def test_falha_na_segunda_chamada_grava_json_parcial(tmp_path, monkeypatch):
    monkeypatch.setattr(mim, "_build_generator", Flaky)
    monkeypatch.setattr(mim, "_PROJECT_OUT", tmp_path / "medicao.json")
    monkeypatch.setattr(mim, "default_plan", lambda: [_case(0), _case(1)])
    out = tmp_path / "out"
    assert mim.main(["--max-usd", "1", "--out-dir", str(out), "--confirm-spend"]) == 0
    data = json.loads((tmp_path / "medicao.json").read_text(encoding="utf-8"))
    assert len(data["calls"]) == 1
    assert data["stopped"] == "provider_error: RuntimeError"
    assert Decimal(data["spent_usd"]) == Decimal(data["calls"][0]["cost_usd"]) > 0
    assert "secret provider message" not in json.dumps(data)


def test_recusa_out_dir_dentro_do_repo(monkeypatch):
    monkeypatch.setattr(mim, "default_plan", lambda: [_case(0)])
    with pytest.raises(SystemExit):
        mim.main(["--max-usd", "1", "--out-dir", str(mim.ROOT / "docs" / "x"), "--confirm-spend"])
