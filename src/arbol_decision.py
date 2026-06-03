"""
Árbol de decisión binario para asignación a ventanillas en FIIS-UNI.

Modelo actualizado tras auditoría del catálogo de trámites contra el TUPA
UNI 2024 (RR N° 3698-2024-UNI) y la Ley N° 28683 (atención preferencial).

Predicados (todos con respaldo normativo explícito):
    v1 — ¿atención_preferencial?    (Ley N° 28683)
    v2 — ¿expediente_completo?       (TUPA UNI 2024 — admisibilidad)
    v3 — ¿aprobación_automática?     (TUPA UNI 2024 — calificación)

Estructura (8 nodos):
    v0 raíz       Lectura de carnet
    v1 decisión   ¿atención preferencial?       (Ley 28683)
        SÍ -> v4 hoja  -> V_Preferencial
        NO -> v2
    v2 decisión   ¿expediente completo?          (TUPA 2024)
        NO -> v5 hoja  -> V_Orientacion_Caja
        SÍ -> v3
    v3 decisión   ¿aprobación automática?        (TUPA 2024)
        SÍ -> v6 hoja  -> V1_Express_Automatica  (T01, T02, T03, T05, T08, T12, T15)
        NO -> v7 hoja  -> V1_General_Evaluacion  (los 13 restantes)
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

try:
    import networkx as nx
except ImportError as e:
    raise ImportError(
        "Falta networkx. Instala dependencias con: uv sync"
    ) from e

from src.config import (
    FUENTE_NORMATIVA,
    OUTPUT_DIR,
    TUPA_APROBACION_AUTOMATICA,
    VENTANILLAS,
    asegurar_output_dir,
)


# ---------------------------------------------------------------------------
# Estructura del árbol — fuente única de verdad para construir() y graficar()
# ---------------------------------------------------------------------------
NODOS: Dict[str, Dict[str, str]] = {
    "v0": {
        "tipo":  "raiz",
        "label": "v₀\nLectura\nde Carnet",
        "color": "#37474F",
    },
    "v1": {
        "tipo":  "intermedio",
        "label": "v₁\n¿Atención\nPreferencial?\n(Ley N°28683)",
        "color": "#6A1B9A",
    },
    "v2": {
        "tipo":  "intermedio",
        "label": "v₂\n¿Expediente\nCompleto?\n(TUPA UNI 2024)",
        "color": "#E65100",
    },
    "v3": {
        "tipo":  "intermedio",
        "label": "v₃\n¿Aprobación\nAutomática?\n(TUPA UNI 2024)",
        "color": "#1565C0",
    },
    "v4": {
        "tipo":  "hoja",
        "label": "v₄\nV. Preferencial\n(Ley N°28683)\nSin turno",
        "color": "#6A1B9A",
    },
    "v5": {
        "tipo":  "hoja",
        "label": "v₅\nOrientación/Caja\nExpediente\nIncompleto",
        "color": "#E65100",
    },
    "v6": {
        "tipo":  "hoja",
        "label": "v₆\nV1 Express\nAprobación\nAutomática",
        "color": "#2E7D32",
    },
    "v7": {
        "tipo":  "hoja",
        "label": "v₇\nV1 General\nEvaluación\nPrevia",
        "color": "#1565C0",
    },
}

PREDICADOS: Dict[str, str] = {
    "v1": "¿atencion_preferencial == True?\n"
          "(gestante | adulto ≥60 | discapacidad | acompaña niño)\n"
          "Fuente: Ley N° 28683",
    "v2": "¿expediente_completo == True?\n"
          "(pago cancelado + requisitos TUPA completos)\n"
          "Fuente: TUPA UNI 2024",
    "v3": "¿calificacion_tupa == 'aprobacion_automatica'?\n"
          "(2–5 días hábiles, sin evaluación discrecional)\n"
          "Fuente: TUPA UNI 2024",
}

# (origen, destino, etiqueta_bit, descripción_semántica)
ARISTAS: List[Tuple[str, str, str, str]] = [
    ("v0", "v1", "",  "inicio → primera validación"),
    ("v1", "v4", "1", "SÍ → Ventanilla Preferencial (Ley 28683)"),
    ("v1", "v2", "0", "NO → verificar completitud del expediente"),
    ("v2", "v5", "0", "NO (incompleto) → Orientación/Caja"),
    ("v2", "v3", "1", "SÍ (completo) → clasificar por calificación TUPA"),
    ("v3", "v6", "1", "SÍ → Automática → V1 Express (2–5 días)"),
    ("v3", "v7", "0", "NO → Eval. Previa → V1 General (10–30 días)"),
]

# Mapeo nodo-hoja -> ventanilla destino.
_HOJA_VENTANILLA: Dict[str, str] = {
    "v4": "V_Preferencial",
    "v5": "V_Orientacion_Caja",
    "v6": "V1_Express_Automatica",
    "v7": "V1_General_Evaluacion",
}


class ArbolDecisionFIIS:
    """Árbol de decisión de 8 nodos con predicados normativos.

    Example:
        >>> arbol = ArbolDecisionFIIS()
        >>> arbol.construir()
        >>> arbol.clasificar({
        ...     "atencion_preferencial": False,
        ...     "expediente_completo":   True,
        ...     "codigo_tramite":        "T01_Constancia_Matricula",
        ... })["ventanilla"]
        'V1_Express_Automatica'
    """

    def __init__(self) -> None:
        self.G: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Construcción del DAG
    # ------------------------------------------------------------------
    def construir(self) -> "nx.DiGraph":
        """Construye el DAG con los 8 nodos y 7 aristas etiquetadas.

        Returns:
            DiGraph con atributos por nodo (`tipo`, `label`, `color`,
            `predicado`) y por arista (`etiqueta` ∈ {"","0","1"},
            `descripcion`).
        """
        self.G.clear()

        for nid, attrs in NODOS.items():
            extra: Dict = {}
            if nid in PREDICADOS:
                extra["predicado"] = PREDICADOS[nid]
            if nid in _HOJA_VENTANILLA:
                extra["ventanilla"] = _HOJA_VENTANILLA[nid]
            self.G.add_node(nid, **attrs, **extra)

        for u, v, etiqueta, desc in ARISTAS:
            self.G.add_edge(u, v, etiqueta=etiqueta, descripcion=desc)
        return self.G

    # ------------------------------------------------------------------
    # Validación estructural
    # ------------------------------------------------------------------
    def validar(self) -> Dict[str, object]:
        """Verifica propiedades estructurales del DAG.

        Returns:
            Dict con flags:
                es_DAG:                True si no hay ciclos.
                es_arbol:              True si es árbol con raíz.
                unicidad_trayectoria:  True si cada nodo no-raíz tiene in_degree ≤ 1.
                caminos:               Lista [(hoja, [nodos del camino])].
        """
        if self.G.number_of_nodes() == 0:
            raise RuntimeError("Llama a construir() antes de validar().")

        es_dag = nx.is_directed_acyclic_graph(self.G)
        raices = [n for n, d in self.G.in_degree() if d == 0]
        es_arbol = (
            len(raices) == 1
            and self.G.number_of_edges() == self.G.number_of_nodes() - 1
            and es_dag
        )
        unicidad = all(d <= 1 for _, d in self.G.in_degree())

        hojas = [n for n, d in self.G.out_degree() if d == 0]
        caminos: List[Tuple[str, List[str]]] = []
        for h in hojas:
            try:
                p = next(nx.all_simple_paths(self.G, raices[0], h))
                caminos.append((h, p))
            except (StopIteration, nx.NetworkXNoPath):
                pass

        return {
            "es_DAG":                bool(es_dag),
            "es_arbol":              bool(es_arbol),
            "unicidad_trayectoria":  bool(unicidad),
            "caminos":               caminos,
        }

    # ------------------------------------------------------------------
    # Clasificación
    # ------------------------------------------------------------------
    def clasificar(self, perfil: dict) -> dict:
        """
        Clasifica a un usuario en su ventanilla de atención según los
        predicados normativos del árbol de decisión.

        Args:
            perfil (dict): Diccionario con los siguientes campos:
                - atencion_preferencial (bool):
                    True si el usuario es gestante, adulto mayor de 60 años,
                    persona con discapacidad o acompañante con niño.
                    Fuente: Ley N° 28683 / Ley N° 27408.
                - expediente_completo (bool):
                    True si el usuario presenta comprobante de pago vigente
                    (BCP, Scotiabank, Niubiz o Págalo.pe) y todos los
                    requisitos del TUPA UNI 2024 para su trámite.
                    False si le falta el pago o algún documento.
                - codigo_tramite (str):
                    Clave del trámite, e.g. "T01_Constancia_Matricula".
                    Debe existir en config.TRAMITES.

        Returns:
            dict con las claves:
                - ventanilla (str): clave de VENTANILLAS en config.py
                - nombre_ventanilla (str): nombre legible
                - camino (list): nodos recorridos desde v0 hasta la hoja
                - codigo_binario (str): concatenación de etiquetas de aristas
                - calificacion_tupa (str): "aprobacion_automatica",
                  "evaluacion_previa" o "N/A"
                - fuentes_normativas (list): fuentes aplicadas en este caso

        Ejemplo:
            perfil = {
                "atencion_preferencial": False,
                "expediente_completo": True,
                "codigo_tramite": "T01_Constancia_Matricula"
            }
            resultado = arbol.clasificar(perfil)
            # → ventanilla: "V1_Express_Automatica"
        """
        if self.G.number_of_nodes() == 0:
            self.construir()

        fuentes: List[str] = []
        camino:  List[str] = ["v0"]

        # v1 — Ley N° 28683: atención preferencial
        fuentes.append(FUENTE_NORMATIVA["v1"])
        camino.append("v1")
        if perfil["atencion_preferencial"]:
            camino.append("v4")
            return {
                "ventanilla":         "V_Preferencial",
                "nombre_ventanilla":  VENTANILLAS["V_Preferencial"]["nombre"],
                "camino":             camino,
                "codigo_binario":     "1",
                "calificacion_tupa":  "N/A",
                "fuentes_normativas": fuentes,
            }

        # v2 — TUPA UNI 2024: completitud del expediente
        fuentes.append(FUENTE_NORMATIVA["v2"])
        camino.append("v2")
        if not perfil["expediente_completo"]:
            camino.append("v5")
            return {
                "ventanilla":         "V_Orientacion_Caja",
                "nombre_ventanilla":  VENTANILLAS["V_Orientacion_Caja"]["nombre"],
                "camino":             camino,
                "codigo_binario":     "00",
                "calificacion_tupa":  "N/A",
                "fuentes_normativas": fuentes,
            }

        # v3 — TUPA UNI 2024: calificación procedimental
        fuentes.append(FUENTE_NORMATIVA["v3"])
        camino.append("v3")
        es_automatica = perfil["codigo_tramite"] in TUPA_APROBACION_AUTOMATICA
        if es_automatica:
            camino.append("v6")
            return {
                "ventanilla":         "V1_Express_Automatica",
                "nombre_ventanilla":  VENTANILLAS["V1_Express_Automatica"]["nombre"],
                "camino":             camino,
                "codigo_binario":     "011",
                "calificacion_tupa":  "aprobacion_automatica",
                "fuentes_normativas": fuentes,
            }
        else:
            camino.append("v7")
            return {
                "ventanilla":         "V1_General_Evaluacion",
                "nombre_ventanilla":  VENTANILLAS["V1_General_Evaluacion"]["nombre"],
                "camino":             camino,
                "codigo_binario":     "010",
                "calificacion_tupa":  "evaluacion_previa",
                "fuentes_normativas": fuentes,
            }

    # ------------------------------------------------------------------
    # Exportadores
    # ------------------------------------------------------------------
    def exportar_json(self, directorio: str = OUTPUT_DIR) -> str:
        """Serializa nodos, aristas, fuentes normativas y validación."""
        out = asegurar_output_dir(directorio)
        ruta = os.path.join(out, "arbol_decision.json")
        val = self.validar()
        payload = {
            "nodos":   [{"id": n, **self.G.nodes[n]} for n in self.G.nodes],
            "aristas": [
                {"u": u, "v": v, **self.G.edges[u, v]}
                for u, v in self.G.edges
            ],
            "predicados":       PREDICADOS,
            "fuentes_normativas": FUENTE_NORMATIVA,
            "hojas_ventanilla": _HOJA_VENTANILLA,
            "validacion": {
                "es_DAG":               val["es_DAG"],
                "es_arbol":             val["es_arbol"],
                "unicidad_trayectoria": val["unicidad_trayectoria"],
                "caminos":              [{"hoja": h, "ruta": p} for h, p in val["caminos"]],
            },
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return ruta

    def graficar(self, directorio: str = OUTPUT_DIR,
                 archivo: str = "figura3_arbol_decision.png") -> str:
        """Dibuja el árbol con layout jerárquico y exporta PNG (1300×900, 200dpi)."""
        try:
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise ImportError(
                "Falta matplotlib. Instala con: uv sync"
            ) from e

        out = asegurar_output_dir(directorio)
        ruta = os.path.join(out, archivo)

        # Layout jerárquico explícito (top-down) conforme a especificación.
        pos: Dict[str, Tuple[float, float]] = {
            "v0": (4.0, 5.0),
            "v1": (4.0, 4.0),
            "v4": (1.5, 3.0),
            "v2": (5.5, 3.0),
            "v5": (3.5, 2.0),
            "v3": (7.0, 2.0),
            "v6": (6.0, 1.0),
            "v7": (8.0, 1.0),
        }

        # Lista abreviada de trámites por hoja TUPA, embebida en el label.
        TRAMITES_POR_HOJA = {
            "v6": "T01 T02 T03\nT05 T08 T12 T15",
            "v7": "T04 T06 T07 T09\nT10 T11 T13 T14\nT16 T17 T18 T19 T20",
        }

        fig, ax = plt.subplots(figsize=(28, 20), facecolor="#F8F9FA")
        # Sin título, sin leyenda, sin borde — el árbol ocupa toda la figura.
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.set_facecolor("#F8F9FA")
        ax.set_axis_off()
        # Bounds ajustados al contenido del árbol, sin márgenes.
        ax.set_xlim(0.6, 8.9)
        ax.set_ylim(0.55, 5.45)

        # 1. Aristas + etiquetas "1·SÍ" / "0·NO" al MEDIO de cada arista.
        for u, v, et, _ in ARISTAS:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            ax.annotate(
                "",
                xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color="#333",
                                lw=3.8, shrinkA=55, shrinkB=55),
                zorder=1,
            )
            if et == "1":
                texto, fc = "1·SÍ", "#FFEBEE"
            elif et == "0":
                texto, fc = "0·NO", "#FFEBEE"
            else:
                continue
            # Punto medio EXACTO de la arista.
            xm = (x0 + x1) / 2.0
            ym = (y0 + y1) / 2.0
            ax.text(
                xm, ym, texto,
                fontsize=22, fontweight="bold",
                color="#B71C1C", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.50",
                          fc=fc, ec="#B71C1C", lw=2.0),
                zorder=2,
            )

        # 2. Nodos — usamos text con bbox redondeado para todos los nodos,
        #    así el rectángulo se adapta automáticamente al contenido (evita
        #    recortes con etiquetas multi-línea como "TUPA UNI 2024" o las
        #    listas de trámites de las hojas v6, v7).
        for nid, (x, y) in pos.items():
            info = NODOS[nid]
            es_hoja = info["tipo"] == "hoja"
            label = info["label"]
            if nid in TRAMITES_POR_HOJA:
                label = label + "\n" + TRAMITES_POR_HOJA[nid]

            pad = 0.80 if es_hoja else 0.65
            fs  = 18   if es_hoja else 18
            ax.text(
                x, y, label,
                fontsize=fs, ha="center", va="center",
                color="white", fontweight="bold",
                bbox=dict(boxstyle=f"round,pad={pad}",
                          fc=info["color"], ec="black", lw=2.2),
                zorder=3,
            )

        # Sin leyenda ni título — el árbol ocupa toda la figura.
        fig.savefig(ruta, dpi=200, facecolor="#F8F9FA",
                    pad_inches=0, bbox_inches=None)
        plt.close(fig)
        return ruta


def main() -> None:
    """Construye el árbol, valida y muestra ejemplos de clasificación."""
    arbol = ArbolDecisionFIIS()
    arbol.construir()
    v = arbol.validar()
    print(f"  ✓ DAG: {v['es_DAG']} | Árbol: {v['es_arbol']} | "
          f"Unicidad: {v['unicidad_trayectoria']}")
    print(f"  ✓ {len(v['caminos'])} caminos únicos raíz → hoja")
    arbol.exportar_json()
    arbol.graficar()

    # ----------------------------------------------------------------
    # Ejemplos de clasificar()
    # ----------------------------------------------------------------
    # Ejemplo A — usuario regular, expediente completo, trámite automático
    perfil_A = {
        "atencion_preferencial": False,
        "expediente_completo":   True,
        "codigo_tramite":        "T01_Constancia_Matricula"
    }
    # Resultado esperado: V1_Express_Automatica, código "011"

    # Ejemplo B — adulto mayor de 60 años (cualquier trámite)
    perfil_B = {
        "atencion_preferencial": True,
        "expediente_completo":   True,
        "codigo_tramite":        "T16_Expedito_Bachiller"
    }
    # Resultado esperado: V_Preferencial, código "1"

    # Ejemplo C — sin comprobante de pago
    perfil_C = {
        "atencion_preferencial": False,
        "expediente_completo":   False,
        "codigo_tramite":        "T09_Reserva_Matricula"
    }
    # Resultado esperado: V_Orientacion_Caja, código "00"

    # Ejemplo D — trámite de evaluación previa, expediente completo
    perfil_D = {
        "atencion_preferencial": False,
        "expediente_completo":   True,
        "codigo_tramite":        "T17_Titulo_Profesional"
    }
    # Resultado esperado: V1_General_Evaluacion, código "010"

    # Ejemplo E — simulación de 5 usuarios en secuencia
    usuarios = [perfil_A, perfil_B, perfil_C, perfil_D,
                {"atencion_preferencial": False, "expediente_completo": True,
                 "codigo_tramite": "T11_Reincorporacion"}]
    print()
    for i, u in enumerate(usuarios, 1):
        r = arbol.clasificar(u)
        print(f"  Usuario {i}: {r['ventanilla']:25s} | "
              f"camino: {r['camino']} | "
              f"código: {r['codigo_binario']}")


if __name__ == "__main__":
    main()
