"""Tests del motor de codificación de Huffman.

Se verifican las propiedades que un código de Huffman debe cumplir por
construcción, no valores numéricos concretos: si mañana se recalibra una
probabilidad en config.TRAMITES, L̄ y H(X) cambian pero estas propiedades
tienen que seguir cumpliéndose.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from src.config import BASELINE_BITS, TRAMITES, validar_distribucion
from src.huffman import HuffmanFIIS


# ---------------------------------------------------------------------------
# Distribución de entrada
# ---------------------------------------------------------------------------
def test_distribucion_suma_uno():
    """Axioma de probabilidad: sum(p_i) = 1."""
    assert sum(TRAMITES.values()) == pytest.approx(1.0, abs=1e-9)


def test_distribucion_sin_probabilidades_negativas():
    assert all(p > 0 for p in TRAMITES.values())


def test_validar_distribucion_rechaza_suma_distinta_de_uno():
    with pytest.raises(ValueError, match="sum"):
        validar_distribucion({"a": 0.7, "b": 0.7})


def test_validar_distribucion_rechaza_negativos():
    with pytest.raises(ValueError, match="p_i >= 0"):
        validar_distribucion({"a": 1.5, "b": -0.5})


# ---------------------------------------------------------------------------
# Propiedades del código generado
# ---------------------------------------------------------------------------
def test_hay_un_codigo_por_tramite(huffman):
    assert set(huffman.codigos) == set(TRAMITES)


def test_igualdad_de_kraft(metricas):
    """K(T) = sum 2^-l_i = 1 exactamente, no sólo <= 1.

    Huffman produce un árbol donde todo nodo interno tiene dos hijos, así que
    el código es prefijo COMPLETO y la desigualdad de Kraft se satura.
    """
    assert metricas["kraft_sum"] == pytest.approx(1.0, abs=1e-9)


def test_codigo_libre_de_prefijos(huffman):
    """Ningún código puede ser prefijo de otro: sin esto la decodificación
    sería ambigua. Se comprueba exhaustivamente sobre los 20 códigos."""
    codigos = sorted(huffman.codigos.values(), key=len)
    for i, corto in enumerate(codigos):
        for largo in codigos[i + 1:]:
            assert not largo.startswith(corto), (
                f"{corto!r} es prefijo de {largo!r}"
            )


def test_cota_de_shannon(metricas):
    """Teorema de codificación sin ruido: H(X) <= L̄ < H(X) + 1."""
    H, L = metricas["H_entropia"], metricas["L_huffman"]
    assert H <= L + 1e-9
    assert L < H + 1.0


def test_entropia_coincide_con_la_formula(metricas):
    esperada = -sum(p * math.log2(p) for p in TRAMITES.values())
    assert metricas["H_entropia"] == pytest.approx(esperada, abs=1e-6)


def test_longitud_media_coincide_con_la_formula(huffman, metricas):
    esperada = sum(TRAMITES[s] * len(c) for s, c in huffman.codigos.items())
    assert metricas["L_huffman"] == pytest.approx(esperada, abs=1e-6)


def test_eficiencia_no_supera_el_cien_por_ciento(metricas):
    """η > 100 % implicaría L̄ < H(X): comprimir bajo el límite de Shannon."""
    assert metricas["eficiencia_pct"] <= 100.0 + 1e-6


def test_huffman_nunca_pierde_contra_el_codigo_fijo(metricas):
    """Huffman es óptimo, así que L̄ <= ceil(log2(n)) siempre."""
    assert metricas["L_huffman"] <= BASELINE_BITS


def test_los_mas_probables_no_tienen_codigos_mas_largos(huffman):
    """Propiedad de optimalidad: si p_i > p_j entonces l_i <= l_j."""
    for a, pa in TRAMITES.items():
        for b, pb in TRAMITES.items():
            if pa > pb:
                assert len(huffman.codigos[a]) <= len(huffman.codigos[b]), (
                    f"{a} (p={pa}) tiene código más largo que {b} (p={pb})"
                )


def test_numero_de_iteraciones_es_n_menos_uno(huffman):
    """n hojas se funden en 1 raíz en exactamente n-1 pasos."""
    assert len(huffman.iteraciones) == len(TRAMITES) - 1


# ---------------------------------------------------------------------------
# Determinismo
# ---------------------------------------------------------------------------
def test_construir_es_determinista():
    """Dos construcciones independientes dan códigos idénticos.

    El desempate por contador estable (FIFO) es lo que lo garantiza; sin él
    los empates de peso (T10/T11 en 0.020, T12/T13 en 0.015, T14/T15 en 0.010,
    T17/T18 en 0.005, T19/T20 en 0.001) romperían la reproducibilidad.
    """
    a, b = HuffmanFIIS(), HuffmanFIIS()
    a.construir()
    b.construir()
    assert a.codigos == b.codigos


# ---------------------------------------------------------------------------
# Codificación / decodificación
# ---------------------------------------------------------------------------
def test_ida_y_vuelta_de_un_mensaje(huffman):
    mensaje = ["T01", "T02", "T01", "T04", "T20", "T19"]
    esperado = [huffman._resolver_simbolo(t) for t in mensaje]
    assert huffman.decodificar(huffman.codificar(mensaje)) == esperado


def test_ida_y_vuelta_de_todos_los_tramites(huffman):
    """Cada trámite debe sobrevivir el viaje de ida y vuelta por separado."""
    for s in TRAMITES:
        assert huffman.decodificar(huffman.codificar([s])) == [s]


def test_codificar_acepta_forma_corta_y_larga(huffman):
    assert huffman.codificar(["T01"]) == huffman.codificar(
        ["T01_Constancia_Matricula"]
    )


def test_codificar_rechaza_tramite_inexistente(huffman):
    with pytest.raises(KeyError):
        huffman.codificar(["T99"])


def test_decodificar_rechaza_cadena_incompleta(huffman):
    """Una cadena que termina a mitad de camino no cae en una hoja."""
    codigo_largo = max(huffman.codigos.values(), key=len)
    with pytest.raises(ValueError, match="hoja"):
        huffman.decodificar(codigo_largo[:-1])


def test_mensaje_vacio_produce_cadena_vacia(huffman):
    assert huffman.codificar([]) == ""
    assert huffman.decodificar("") == []


def test_codificar_ahorra_bits_frente_al_codigo_fijo(huffman):
    """Sobre un mensaje representativo, Huffman debe ganarle al bloque."""
    mensaje = ["T01"] * 25 + ["T02"] * 15 + ["T03"] * 12 + ["T04"] * 10
    bits_huffman = len(huffman.codificar(mensaje))
    bits_fijo = len(mensaje) * BASELINE_BITS
    assert bits_huffman < bits_fijo


# ---------------------------------------------------------------------------
# Casos límite del algoritmo
# ---------------------------------------------------------------------------
def test_alfabeto_de_un_solo_simbolo():
    """Caso degenerado: con un símbolo el árbol no tiene aristas, pero el
    código no puede quedar vacío o no habría nada que transmitir."""
    h = HuffmanFIIS({"unico": 1.0})
    h.construir()
    assert h.codigos == {"unico": "0"}


def test_alfabeto_de_dos_simbolos():
    h = HuffmanFIIS({"a": 0.6, "b": 0.4})
    h.construir()
    assert sorted(h.codigos.values()) == ["0", "1"]


def test_distribucion_uniforme_da_longitudes_parejas():
    """Con 8 símbolos equiprobables el óptimo es el código de bloque de 3 bits."""
    h = HuffmanFIIS({f"s{i}": 0.125 for i in range(8)})
    h.construir()
    assert {len(c) for c in h.codigos.values()} == {3}
    assert h.calcular_metricas()["eficiencia_pct"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Coherencia con los artefactos publicados
# ---------------------------------------------------------------------------
def test_la_tabla_de_codigos_publicada_esta_al_dia(huffman):
    """outputs/tabla2_codigos.csv se versiona y alimenta el artículo.

    Si alguien cambia el algoritmo y no regenera, el artículo queda citando
    códigos que el código ya no produce, y nada avisa. Este test lo detecta.
    """
    ruta = (
        Path(__file__).resolve().parent.parent
        / "outputs"
        / "tabla2_codigos.csv"
    )
    if not ruta.exists():
        pytest.skip("outputs/ no generado todavía: corre run_pipeline.py")

    with open(ruta, encoding="utf-8") as f:
        publicados = {
            fila["tramite"]: fila["codigo"] for fila in csv.DictReader(f)
        }

    assert publicados == huffman.codigos, (
        "outputs/tabla2_codigos.csv no coincide con el código actual; "
        "regenera con: uv run python run_pipeline.py"
    )
