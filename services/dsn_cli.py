"""SPEC-225 R7: DSN de scripts de ops sem senha em argv.

Default: ler a URL de uma variável de ambiente (``--dsn-env``, padrão ``DATABASE_URL``). ``--dsn`` com
o valor literal (senha visível em lista de processos e histórico do shell) só funciona com
``--allow-dsn-argv``, e emite aviso.
"""
from __future__ import annotations

import argparse
import os
import sys


def add_dsn_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dsn-env", default="DATABASE_URL",
                        help="nome da variável de ambiente que contém a DSN (padrão: DATABASE_URL)")
    parser.add_argument("--dsn", default=None, help=argparse.SUPPRESS)  # legado; exige --allow-dsn-argv
    parser.add_argument("--allow-dsn-argv", action="store_true",
                        help="aceita --dsn literal (a senha fica visível em argv; evitar)")


def resolve_dsn(parser: argparse.ArgumentParser, args: argparse.Namespace, *, default_dsn: str | None = None) -> str:
    if args.dsn is not None:
        if not args.allow_dsn_argv:
            parser.error("--dsn expõe a senha em argv; use --dsn-env NOME (ou --allow-dsn-argv)")
        sys.stderr.write("aviso: DSN recebida por argv; prefira --dsn-env\n")  # CLI de ops, não log de produção
        return args.dsn
    dsn = os.getenv(args.dsn_env, "")
    if dsn:
        return dsn
    if default_dsn:
        return default_dsn
    parser.error(f"variável {args.dsn_env} ausente ou vazia")
    raise AssertionError("unreachable")  # parser.error encerra o processo
