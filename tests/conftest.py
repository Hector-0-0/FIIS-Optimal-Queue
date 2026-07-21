"""Configuración compartida de pytest.

Inserta la raíz del proyecto en sys.path para que `import src.*` funcione al
correr pytest desde cualquier directorio, y expone un fixture con el árbol de
Huffman ya construido (construirlo es O(n log n) pero se repite en casi todos
los tests, así que se reutiliza por sesión).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.huffman import HuffmanFIIS  # noqa: E402
from src.arbol_decision import ArbolDecisionFIIS  # noqa: E402


@pytest.fixture(scope="session")
def huffman() -> HuffmanFIIS:
    """Motor de Huffman construido sobre la distribución oficial."""
    h = HuffmanFIIS()
    h.construir()
    return h


@pytest.fixture(scope="session")
def metricas(huffman: HuffmanFIIS) -> dict:
    """Métricas del código óptimo (L̄, H, η, Kraft, ...)."""
    return huffman.calcular_metricas()


@pytest.fixture(scope="session")
def arbol() -> ArbolDecisionFIIS:
    """Árbol de decisión construido y listo para clasificar."""
    a = ArbolDecisionFIIS()
    a.construir()
    return a
