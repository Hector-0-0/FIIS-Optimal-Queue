"""
Generador de las 4 figuras del proyecto FIIS-UNI.

Las figuras consumen los artefactos JSON producidos por el pipeline, por lo
que pueden regenerarse de forma independiente al motor Huffman.

Figuras:
    1. figura1_arbol_huffman.png       – árbol binario de Huffman (20 hojas).
    2. figura2_barras_comparativa.png  – longitud fija vs Huffman por trámite.
    3. figura3_arbol_decision.png      – árbol de decisión, 8 nodos coloreados.
    4. figura4_distribucion_tupa.png   – donut de distribución por canal TUPA.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

try:
    import matplotlib.pyplot as plt
except ImportError as e:
    raise ImportError(
        "Falta matplotlib. Instala dependencias con: uv sync"
    ) from e

from src.config import (
    BASELINE_BITS,
    OUTPUT_DIR,
    PORCENTAJE_AUTOMATICA,
    PORCENTAJE_EVALUACION,
    TRAMITES,
    TRAMITE_A_VENTANILLA,
    TUPA_APROBACION_AUTOMATICA,
    TUPA_EVALUACION_PREVIA,
    VENTANILLA_COLOR,
    asegurar_output_dir,
)
from src.arbol_decision import ArbolDecisionFIIS


def _cargar_huffman_json(directorio: str = OUTPUT_DIR) -> Dict:
    """Carga outputs/huffman_resultados.json o lanza error guía."""
    ruta = os.path.join(directorio, "huffman_resultados.json")
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No encuentro {ruta}. Corre primero: python -m src.huffman"
        )
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Figura 1 — Árbol de Huffman
# ---------------------------------------------------------------------------
def figura1_arbol_huffman(directorio: str = OUTPUT_DIR) -> str:
    """Dibuja el árbol binario de Huffman con 20 hojas, conectando aristas
    de extremo a extremo con cada nodo dibujado encima.

    Returns:
        Ruta absoluta del PNG generado.
    """
    out = asegurar_output_dir(directorio)
    data = _cargar_huffman_json(directorio)
    arbol = data["arbol"]
    codigos: Dict[str, str] = data["codigos"]

    # ---- Layout: asigno (x, y) a cada nodo ----
    # x se reparte uniformemente entre las hojas (DFS in-order).
    # y = -profundidad (raíz arriba, hojas más profundas más abajo).
    posiciones: Dict[int, Tuple[float, float]] = {}
    leaf_idx = [0]
    total_leaves = sum(1 for _ in _iter_hojas(arbol))
    step = 1.0 / max(total_leaves - 1, 1)

    def _layout(nodo: Dict, prof: int) -> float:
        if nodo["is_leaf"]:
            x = leaf_idx[0] * step
            posiciones[id(nodo)] = (x, -float(prof))
            leaf_idx[0] += 1
            return x
        xl = _layout(nodo["left"],  prof + 1)
        xr = _layout(nodo["right"], prof + 1)
        x = (xl + xr) / 2.0
        posiciones[id(nodo)] = (x, -float(prof))
        return x

    _layout(arbol, 0)
    max_depth = max(-y for _, y in posiciones.values())

    # ---- Figura ----
    fig, ax = plt.subplots(figsize=(38, 24))
    ax.set_axis_off()
    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(-max_depth - 1.2, 0.5)

    # 1. Aristas (zorder 1) — siempre del centro de un nodo al centro del hijo.
    def _dibujar_aristas(nodo: Dict) -> None:
        if nodo is None or nodo["is_leaf"]:
            return
        x0, y0 = posiciones[id(nodo)]
        for hijo, etiqueta in ((nodo["left"], "0"), (nodo["right"], "1")):
            if hijo is None:
                continue
            x1, y1 = posiciones[id(hijo)]
            ax.plot([x0, x1], [y0, y1], color="#555", lw=1.4,
                    solid_capstyle="round", zorder=1)
            # Etiqueta 0/1 EN EL MEDIO de la arista, con bbox blanco para
            # que se lea bien sobre la línea.
            xm = (x0 + x1) / 2.0
            ym = (y0 + y1) / 2.0
            ax.text(
                xm, ym, etiqueta,
                fontsize=18, fontweight="bold",
                ha="center", va="center", color="#000",
                bbox=dict(boxstyle="circle,pad=0.36",
                          fc="white", ec="#888", lw=1.2),
                zorder=2,
            )
            _dibujar_aristas(hijo)

    _dibujar_aristas(arbol)

    # 2. Nodos internos (zorder 3) — usamos scatter (puntos en unidades físicas)
    #    para que los círculos NO se aplasten por la diferencia entre las
    #    escalas de los ejes X (rango [0,1]) e Y (rango [-9,0]).
    for nodo in _iter_todos(arbol):
        if nodo["is_leaf"]:
            continue
        x, y = posiciones[id(nodo)]
        ax.scatter([x], [y], s=1900, c="#e8e8e8",
                   edgecolors="black", linewidths=1.5, zorder=3)
        # Peso DENTRO del círculo.
        ax.text(x, y, f"{nodo['peso']:.3f}",
                fontsize=12, ha="center", va="center",
                color="#1a1a1a", fontweight="bold", zorder=4)

    # 3. Hojas (zorder 4) — rectángulos coloreados centrados en (x, y).
    #    Formato de la probabilidad:
    #      - p >= 1 %    -> "X.X %"     (ej. 25.0 %, 7.0 %)
    #      - p <  1 %    -> "0.X %"     (ej. 0.8 %, 0.1 %)
    for nodo in _iter_hojas(arbol):
        x, y = posiciones[id(nodo)]
        sym = nodo["symbol"]
        vent = TRAMITE_A_VENTANILLA[sym]
        color = VENTANILLA_COLOR[vent]
        etiqueta = (
            f"{sym.split('_')[0]}\n"
            f"{TRAMITES[sym] * 100:.1f} %\n"
            f"{codigos[sym]}"
        )
        ax.text(
            x, y, etiqueta,
            fontsize=14, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.45", fc=color,
                      ec="black", lw=1.5),
            color="white", fontweight="bold", zorder=4,
        )

    # Sin leyenda ni nota al pie — el árbol ocupa toda la figura.
    # Forzamos márgenes a cero para eliminar el borde blanco circundante.
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    ruta = os.path.join(out, "figura1_arbol_huffman.png")
    fig.savefig(ruta, dpi=200, facecolor="white",
                pad_inches=0, bbox_inches=None)
    plt.close(fig)
    return ruta


def _iter_hojas(nodo: Optional[Dict]):
    if nodo is None:
        return
    if nodo["is_leaf"]:
        yield nodo
        return
    yield from _iter_hojas(nodo.get("left"))
    yield from _iter_hojas(nodo.get("right"))


def _iter_todos(nodo: Optional[Dict]):
    if nodo is None:
        return
    yield nodo
    yield from _iter_todos(nodo.get("left"))
    yield from _iter_todos(nodo.get("right"))


# ---------------------------------------------------------------------------
# Figura 2 — Barras comparativas
# ---------------------------------------------------------------------------
def figura2_barras_comparativa(directorio: str = OUTPUT_DIR) -> str:
    """Barras agrupadas (no apiladas) comparando longitud fija vs Huffman.

    Returns:
        Ruta absoluta del PNG generado.
    """
    out = asegurar_output_dir(directorio)
    data = _cargar_huffman_json(directorio)
    codigos: Dict[str, str] = data["codigos"]
    metricas = data["metricas"]

    orden = sorted(TRAMITES.keys(), key=lambda s: -TRAMITES[s])
    etiquetas = [t.split("_")[0] for t in orden]
    huff = [len(codigos[t]) for t in orden]
    fijo = [BASELINE_BITS] * len(orden)

    fig, ax = plt.subplots(figsize=(28, 21))
    bar_h = 0.46
    y = list(range(len(orden)))
    y_fijo = [yi - bar_h / 2 for yi in y]
    y_huff = [yi + bar_h / 2 for yi in y]

    # Barras separadas (no apiladas) para que ambas longitudes sean visibles.
    ax.barh(y_fijo, fijo, height=bar_h, color="#d62728",
            edgecolor="black", linewidth=0.8,
            label=f"Código fijo ({BASELINE_BITS} bits)")
    ax.barh(y_huff, huff, height=bar_h, color="#1f77b4",
            edgecolor="black", linewidth=0.8,
            label=f"Huffman (L̄ = {metricas['L_huffman']:.3f} bits)")

    # Valor numérico al final de cada barra Huffman.
    for yi, val in zip(y_huff, huff):
        ax.text(val + 0.10, yi, f"{val}", va="center", ha="left",
                fontsize=20, color="#0d3a73", fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(etiquetas, fontsize=21)
    ax.invert_yaxis()
    ax.set_xlabel("Longitud del código (bits)", fontsize=23, fontweight="bold")
    ax.tick_params(axis="x", labelsize=19)
    ax.set_xlim(0, BASELINE_BITS + 5)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    # Línea vertical = entropía H(X).
    ax.axvline(metricas["H_entropia"], color="black", linestyle="--", lw=2.4,
               label=f"H(X) = {metricas['H_entropia']:.3f} bits")

    # (Título omitido — se añadirá en el artículo.)

    # Leyenda fuera del área de barras (arriba a la derecha del axes).
    ax.legend(loc="upper right", fontsize=20, frameon=True,
              edgecolor="#888")

    ruta = os.path.join(out, "figura2_barras_comparativa.png")
    fig.tight_layout()
    fig.savefig(ruta, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return ruta


# ---------------------------------------------------------------------------
# Figura 3 — Árbol de decisión
# ---------------------------------------------------------------------------
def figura3_arbol_decision(directorio: str = OUTPUT_DIR) -> str:
    """Genera el árbol de decisión a través de ArbolDecisionFIIS.graficar()."""
    arbol = ArbolDecisionFIIS()
    arbol.construir()
    return arbol.graficar(directorio=directorio,
                          archivo="figura3_arbol_decision.png")


# ---------------------------------------------------------------------------
# Figura 4 — Distribución TUPA (donut de dos anillos)
# ---------------------------------------------------------------------------
def figura4_distribucion_tupa(directorio: str = OUTPUT_DIR) -> str:
    """Donut de dos anillos coloreado por calificación TUPA UNI 2024.

    - Anillo exterior: los 20 trámites individuales (verde/azul por categoría).
    - Anillo interior: 2 sectores consolidados (Automática 66.5% / Eval. previa 33.5%).
    - Leyenda inferior con los 4 canales (2 TUPA + 2 transversales).
    - Nota al pie con fuente normativa y plazos.

    Returns:
        Ruta absoluta de outputs/figura4_distribucion_tupa.png.
    """
    out = asegurar_output_dir(directorio)
    import math
    from matplotlib.colors import to_rgba

    # Orden: primero los 7 de aprobación automática (ordenados desc por p),
    # luego los 13 de evaluación previa (también ordenados desc por p).
    autom_orden = sorted(TUPA_APROBACION_AUTOMATICA, key=lambda t: -TRAMITES[t])
    eval_orden  = sorted(TUPA_EVALUACION_PREVIA,    key=lambda t: -TRAMITES[t])
    orden_ext: List[str] = autom_orden + eval_orden

    # Colores con leve gradiente de opacidad para distinguir cada trámite
    # dentro de su categoría (verde para automática, azul para eval. previa).
    COLOR_AUTOM = "#2E7D32"
    COLOR_EVAL  = "#1565C0"

    def _shade(base: str, idx: int, total: int) -> Tuple[float, ...]:
        """Devuelve una variante del color base con alpha gradado."""
        a = 0.55 + 0.45 * (1.0 - idx / max(total - 1, 1))
        r, g, b, _ = to_rgba(base)
        return (r, g, b, a)

    colors_ext: List = []
    for i, _ in enumerate(autom_orden):
        colors_ext.append(_shade(COLOR_AUTOM, i, len(autom_orden)))
    for i, _ in enumerate(eval_orden):
        colors_ext.append(_shade(COLOR_EVAL, i, len(eval_orden)))

    sizes_ext = [TRAMITES[t] for t in orden_ext]

    # Anillo interior: 2 sectores consolidados.
    sizes_int  = [sum(TRAMITES[t] for t in autom_orden),
                  sum(TRAMITES[t] for t in eval_orden)]
    colors_int = [COLOR_AUTOM, COLOR_EVAL]

    # ------------------------------------------------------------------
    # Figura sin leyenda, sin nota al pie, sin borde — el donut llena
    # toda la imagen. figsize calibrado al aspect del contenido para
    # evitar franjas blancas arriba/abajo (ver xlim/ylim al final).
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(30, 20), facecolor="white")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_aspect("equal")

    # -- Anillo exterior (20 sectores) ------------------------------------
    wedges_ext, _ = ax.pie(
        sizes_ext, colors=colors_ext, radius=1.00,
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.1),
        labels=None,
    )

    # Etiqueta "Txx (P%)" inline sólo para p >= 2 %; el resto va en callouts.
    THRESHOLD = 0.02
    pequenos: List[Tuple] = []   # (wedge, tramite, ang_deg)
    for wedge, tramite in zip(wedges_ext, orden_ext):
        ang = (wedge.theta2 + wedge.theta1) / 2.0
        if TRAMITES[tramite] >= THRESHOLD:
            rad = math.radians(ang)
            x = 0.86 * math.cos(rad)
            y = 0.86 * math.sin(rad)
            ax.text(x, y,
                    f"{tramite.split('_')[0]}\n({TRAMITES[tramite]*100:.1f} %)",
                    ha="center", va="center",
                    fontsize=14.5, fontweight="bold", color="white")
        else:
            pequenos.append((wedge, tramite, ang))

    # -- Callouts para los slices < 2 % (T12, T13, T14, T15, T16, T17,
    #    T18, T19, T20). Se distribuyen en una columna vertical a la
    #    izquierda del donut, con líneas guía radiales que no atraviesan
    #    el anillo. Cada label lleva un cuadrito con el color TUPA
    #    correspondiente al trámite.
    pequenos.sort(key=lambda t: -math.sin(math.radians(t[2])))   # arriba → abajo
    x_col = -1.62
    y_pos: List[float] = []
    min_gap = 0.15
    for _, _, ang in pequenos:
        y_natural = 1.02 * math.sin(math.radians(ang))
        y_lab = y_natural if not y_pos else min(y_natural, y_pos[-1] - min_gap)
        y_pos.append(y_lab)

    for (wedge, tramite, ang), y_lab in zip(pequenos, y_pos):
        rad = math.radians(ang)
        x_edge = 1.02 * math.cos(rad)
        y_edge = 1.02 * math.sin(rad)
        x_way  = 1.15 * math.cos(rad)
        y_way  = 1.15 * math.sin(rad)
        # Línea: borde → waypoint radial → empalme horizontal → marca.
        ax.plot([x_edge, x_way, x_col + 0.08, x_col + 0.04],
                [y_edge, y_way, y_lab, y_lab],
                color="#888", lw=0.7, zorder=1)
        # Cuadrito del color TUPA del trámite.
        vent = TRAMITE_A_VENTANILLA[tramite]
        ax.plot(x_col, y_lab, marker="s",
                markerfacecolor=VENTANILLA_COLOR[vent],
                markeredgecolor="black", markersize=15, zorder=2)
        ax.text(x_col - 0.07, y_lab,
                f"{tramite.split('_')[0]} ({TRAMITES[tramite]*100:.1f} %)",
                ha="right", va="center", fontsize=16, color="#222")

    # -- Anillo interior (2 sectores consolidados) ------------------------
    wedges_int, _ = ax.pie(
        sizes_int, colors=colors_int, radius=0.68,
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.28, edgecolor="white", linewidth=1.5),
        labels=None,
    )

    # Etiquetas grandes de las 2 categorías TUPA — centradas radialmente
    # en el grosor del anillo interior (radio ≈ 0.54).
    for wedge, txt in zip(
        wedges_int,
        [f"Aprobación\nAutomática\n{PORCENTAJE_AUTOMATICA} %",
         f"Evaluación\nPrevia\n{PORCENTAJE_EVALUACION} %"],
    ):
        ang = (wedge.theta2 + wedge.theta1) / 2.0
        rad = math.radians(ang)
        x = 0.54 * math.cos(rad)
        y = 0.54 * math.sin(rad)
        ax.text(x, y, txt,
                ha="center", va="center",
                fontsize=20, fontweight="bold", color="white")

    # -- Centro del donut --------------------------------------------------
    ax.text(0, 0,
            "20 trámites\nTUPA UNI 2024\nΣP = 1.000",
            ha="center", va="center",
            fontsize=21, fontweight="bold", color="#222")

    # Sin leyenda ni notas — el donut + callouts ocupan toda la figura.
    # xlim asimétrico ajustado al contenido real:
    #   - izquierda: hasta -2.10 para acomodar las etiquetas más largas
    #     de la columna de callouts ("T20 (0.1 %)")
    #   - derecha:   hasta +1.10 para el borde del donut
    # ylim: ±1.07 (el donut llega hasta y=±1.02 con un pequeño margen).
    # Aspect de los datos = 3.20 / 2.14 = 1.495 → figsize = (30, 20) → 1.5
    # → coincidencia ≈ 1.0 → sin franjas blancas.
    ax.set_xlim(-2.10, 1.10)
    ax.set_ylim(-1.07, 1.07)

    ruta = os.path.join(out, "figura4_distribucion_tupa.png")
    fig.savefig(ruta, dpi=200, facecolor="white",
                pad_inches=0, bbox_inches=None)
    plt.close(fig)
    return ruta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(directorio: str = OUTPUT_DIR) -> Dict[str, str]:
    """Genera las 4 figuras y devuelve {nombre_logico: ruta}."""
    rutas = {
        "fig1": figura1_arbol_huffman(directorio),
        "fig2": figura2_barras_comparativa(directorio),
        "fig3": figura3_arbol_decision(directorio),
        "fig4": figura4_distribucion_tupa(directorio),
    }
    for k, r in rutas.items():
        print(f"  ✓ {os.path.basename(r)}")
    return rutas


if __name__ == "__main__":
    main()
