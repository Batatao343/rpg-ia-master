"""SPEC-198: rename_package.py on a temp copy fixture."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "rename_package", ROOT / "scripts/android/rename_package.py"
)
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
OLD = "dev.old.app"


@pytest.fixture
def repo(tmp_path):
    def w(rel, txt):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")

    w("web/capacitor.config.ts", f"export default {{ appId: '{OLD}', appName: 'Old' }};\n")
    w(
        "web/android/app/build.gradle",
        f'android {{ namespace = "{OLD}"\n defaultConfig {{ applicationId "{OLD}" }} }}\n',
    )
    w(
        "web/android/app/src/main/res/values/strings.xml",
        f'<resources><string name="app_name">Old</string><string name="package_name">{OLD}</string></resources>',
    )
    base = "web/android/app/src/main/java/dev/old/app"
    w(f"{base}/MainActivity.java", f"package {OLD};\n")
    w(f"{base}/sub/Helper.java", f"package {OLD}.sub;\n")
    w("web/android/app/build/gen/Skip.java", OLD)  # build output must be ignored
    w("scripts/android_billing_smoke.mjs", f"const PKG = '{OLD}';\n")
    w("scripts/android/store_screenshots.mjs", f"const PKG = '{OLD}';\n")
    w("scripts/android/rename_package.py", "# self\n")
    return tmp_path


def test_apply_renames_everything(repo):
    assert (
        rp.main(
            ["--new", "com.acme.valoria", "--root", str(repo), "--apply", "--app-name", "Valoria"]
        )
        == 0
    )
    java = repo / "web/android/app/src/main/java/com/acme/valoria"
    assert (java / "MainActivity.java").read_text() == "package com.acme.valoria;\n"
    assert (java / "sub/Helper.java").read_text() == "package com.acme.valoria.sub;\n"
    assert not (repo / "web/android/app/src/main/java/dev").exists()
    assert "com.acme.valoria" in (repo / "scripts/android/store_screenshots.mjs").read_text()
    assert "appName: 'Valoria'" in (repo / "web/capacitor.config.ts").read_text()


def test_dry_run_changes_nothing(repo):
    assert rp.main(["--new", "com.acme.valoria", "--root", str(repo)]) == 0
    assert OLD in (repo / "web/capacitor.config.ts").read_text()


@pytest.mark.parametrize("name", ["A'B", 'A"B', "A\1", "A&B", "A<B", "A\nB", ""])
def test_rejects_bad_app_name(repo, name):
    with pytest.raises(SystemExit):
        rp.main(["--new", "com.acme.valoria", "--root", str(repo), "--apply", "--app-name", name])


def test_rejects_invalid_id(repo):
    with pytest.raises(SystemExit):
        rp.main(["--new", "Com.Bad", "--root", str(repo)])
