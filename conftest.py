"""Garante que a raiz do projeto esteja no sys.path para os testes (import de agents/, etc.)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
