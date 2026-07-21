"""Tests del árbol de decisión binario y sus predicados normativos."""

from __future__ import annotations

import networkx as nx
import pytest

from src.config import (
    PORCENTAJE_AUTOMATICA,
    PORCENTAJE_EVALUACION,
    TRAMITES,
    TUPA_APROBACION_AUTOMATICA,
    TUPA_EVALUACION_PREVIA,
    VENTANILLAS,
)
from src.arbol_decision import ARISTAS, _HOJA_VENTANILLA, ArbolDecisionFIIS


# ---------------------------------------------------------------------------
# Estructura de grafo
# ---------------------------------------------------------------------------
def test_tiene_ocho_nodos_y_siete_aristas(arbol):
    assert arbol.G.number_of_nodes() == 8
    assert arbol.G.number_of_edges() == 7


def test_es_un_arbol_dirigido(arbol):
    v = arbol.validar()
    assert v["es_DAG"]
    assert v["es_arbol"]
    assert v["unicidad_trayectoria"]


def test_hay_exactamente_cuatro_hojas(arbol):
    hojas = [n for n, d in arbol.G.out_degree() if d == 0]
    assert sorted(hojas) == ["v4", "v5", "v6", "v7"]


def test_hay_una_sola_raiz(arbol):
    raices = [n for n, d in arbol.G.in_degree() if d == 0]
    assert raices == ["v0"]


def test_cada_hoja_tiene_un_unico_camino_desde_la_raiz(arbol):
    """Unicidad de trayectoria: es lo que hace que el código de ruta
    identifique sin ambigüedad la ventanilla asignada."""
    for hoja in _HOJA_VENTANILLA:
        caminos = list(nx.all_simple_paths(arbol.G, "v0", hoja))
        assert len(caminos) == 1, f"{hoja} tiene {len(caminos)} caminos"


def test_los_nodos_de_decision_son_binarios(arbol):
    """v1, v2 y v3 deben tener exactamente 2 salidas (SÍ / NO)."""
    for nodo in ("v1", "v2", "v3"):
        assert arbol.G.out_degree(nodo) == 2


def test_cada_hoja_apunta_a_una_ventanilla_existente():
    for hoja, ventanilla in _HOJA_VENTANILLA.items():
        assert ventanilla in VENTANILLAS, f"{hoja} → {ventanilla} no existe"


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------
CASOS = [
    # (preferencial, expediente_completo, trámite, ventanilla, código, camino)
    (True,  True,  "T16_Expedito_Bachiller",
     "V_Preferencial",        "1",   ["v0", "v1", "v4"]),
    (True,  False, "T20_Traslado_Externo",
     "V_Preferencial",        "1",   ["v0", "v1", "v4"]),
    (False, False, "T09_Reserva_Matricula",
     "V_Orientacion_Caja",    "00",  ["v0", "v1", "v2", "v5"]),
    (False, True,  "T01_Constancia_Matricula",
     "V1_Express_Automatica", "011", ["v0", "v1", "v2", "v3", "v6"]),
    (False, True,  "T17_Titulo_Profesional",
     "V1_General_Evaluacion", "010", ["v0", "v1", "v2", "v3", "v7"]),
]


@pytest.mark.parametrize(
    "pref,completo,tramite,ventanilla,codigo,camino", CASOS
)
def test_clasificar(arbol, pref, completo, tramite, ventanilla, codigo, camino):
    r = arbol.clasificar({
        "atencion_preferencial": pref,
        "expediente_completo":   completo,
        "codigo_tramite":        tramite,
    })
    assert r["ventanilla"] == ventanilla
    assert r["codigo_binario"] == codigo
    assert r["camino"] == camino


def test_preferencial_gana_sobre_expediente_incompleto(arbol):
    """La Ley 28683 se evalúa primero: un usuario preferencial va a su
    ventanilla aunque le falten requisitos del TUPA."""
    r = arbol.clasificar({
        "atencion_preferencial": True,
        "expediente_completo":   False,
        "codigo_tramite":        "T01_Constancia_Matricula",
    })
    assert r["ventanilla"] == "V_Preferencial"


def test_todos_los_tramites_se_clasifican(arbol):
    """Ningún trámite del catálogo puede quedar sin ventanilla."""
    for tramite in TRAMITES:
        r = arbol.clasificar({
            "atencion_preferencial": False,
            "expediente_completo":   True,
            "codigo_tramite":        tramite,
        })
        assert r["ventanilla"] in ("V1_Express_Automatica",
                                   "V1_General_Evaluacion")


def test_la_calificacion_tupa_concuerda_con_la_ventanilla(arbol):
    for tramite in TRAMITES:
        r = arbol.clasificar({
            "atencion_preferencial": False,
            "expediente_completo":   True,
            "codigo_tramite":        tramite,
        })
        if tramite in TUPA_APROBACION_AUTOMATICA:
            assert r["calificacion_tupa"] == "aprobacion_automatica"
            assert r["ventanilla"] == "V1_Express_Automatica"
        else:
            assert r["calificacion_tupa"] == "evaluacion_previa"
            assert r["ventanilla"] == "V1_General_Evaluacion"


def test_se_reportan_las_fuentes_normativas_aplicadas(arbol):
    """Un caso preferencial sólo evalúa v1, así que cita una única fuente;
    uno que llega hasta v3 cita las tres."""
    solo_v1 = arbol.clasificar({
        "atencion_preferencial": True,
        "expediente_completo":   True,
        "codigo_tramite":        "T01_Constancia_Matricula",
    })
    assert len(solo_v1["fuentes_normativas"]) == 1

    hasta_v3 = arbol.clasificar({
        "atencion_preferencial": False,
        "expediente_completo":   True,
        "codigo_tramite":        "T01_Constancia_Matricula",
    })
    assert len(hasta_v3["fuentes_normativas"]) == 3


def test_clasificar_construye_el_grafo_si_hace_falta():
    """clasificar() sobre una instancia sin construir() no debe reventar."""
    a = ArbolDecisionFIIS()
    r = a.clasificar({
        "atencion_preferencial": False,
        "expediente_completo":   True,
        "codigo_tramite":        "T01_Constancia_Matricula",
    })
    assert r["ventanilla"] == "V1_Express_Automatica"


# ---------------------------------------------------------------------------
# Coherencia entre el código devuelto y la topología declarada
# ---------------------------------------------------------------------------
def test_el_codigo_binario_se_deriva_de_las_etiquetas_de_las_aristas(arbol):
    """clasificar() devuelve códigos escritos a mano ("1", "00", "011", "010").

    Este test los recalcula recorriendo el camino sobre el grafo y concatenando
    las etiquetas reales de cada arista. Si alguien cambia la topología del
    árbol sin actualizar los literales de clasificar(), aquí falla.
    """
    etiquetas = {(u, v): et for u, v, et, _ in ARISTAS}

    for pref, completo, tramite, _, codigo_esperado, _ in CASOS:
        r = arbol.clasificar({
            "atencion_preferencial": pref,
            "expediente_completo":   completo,
            "codigo_tramite":        tramite,
        })
        camino = r["camino"]
        derivado = "".join(
            etiquetas[(u, v)] for u, v in zip(camino, camino[1:])
        )
        assert derivado == r["codigo_binario"] == codigo_esperado


def test_el_camino_devuelto_existe_en_el_grafo(arbol):
    """Cada par consecutivo del camino tiene que ser una arista real."""
    for pref, completo, tramite, _, _, _ in CASOS:
        camino = arbol.clasificar({
            "atencion_preferencial": pref,
            "expediente_completo":   completo,
            "codigo_tramite":        tramite,
        })["camino"]
        for u, v in zip(camino, camino[1:]):
            assert arbol.G.has_edge(u, v), f"arista inexistente {u}→{v}"


# ---------------------------------------------------------------------------
# Coherencia de la clasificación TUPA en config.py
# ---------------------------------------------------------------------------
def test_las_dos_categorias_tupa_particionan_el_catalogo():
    """Ni solapamiento ni huecos entre automática y evaluación previa."""
    automatica = set(TUPA_APROBACION_AUTOMATICA)
    evaluacion = set(TUPA_EVALUACION_PREVIA)
    assert automatica & evaluacion == set()
    assert automatica | evaluacion == set(TRAMITES)


def test_los_porcentajes_tupa_suman_cien():
    assert PORCENTAJE_AUTOMATICA + PORCENTAJE_EVALUACION == pytest.approx(100.0)


def test_las_ventanillas_por_tramite_no_se_solapan():
    """Un trámite no puede estar asignado a dos ventanillas distintas."""
    vistos: dict[str, str] = {}
    for ventanilla, info in VENTANILLAS.items():
        for tramite in info["tramites"]:
            assert tramite not in vistos, (
                f"{tramite} está en {vistos.get(tramite)} y en {ventanilla}"
            )
            vistos[tramite] = ventanilla


def test_los_canales_transversales_no_tienen_tramites_fijos():
    """Preferencial y Orientación dependen del usuario o del expediente, no
    del tipo de trámite."""
    assert VENTANILLAS["V_Preferencial"]["tramites"] == []
    assert VENTANILLAS["V_Orientacion_Caja"]["tramites"] == []
