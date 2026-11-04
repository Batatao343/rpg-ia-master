"""pytest -p mutplug: carrega MUT_FILE no lugar de MUT_MODULE antes de qualquer import."""

import importlib.util
import os
import sys

_mod, _file = os.environ.get("MUT_MODULE"), os.environ.get("MUT_FILE")
if _mod and _file:
    pkg, _, leaf = _mod.rpartition(".")
    parent = importlib.import_module(pkg) if pkg else None
    spec = importlib.util.spec_from_file_location(_mod, _file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[_mod] = m
    spec.loader.exec_module(m)
    if parent is not None:
        setattr(parent, leaf, m)
    sys.stderr.write(f"[mutplug] {_mod} <- {_file}\n")
