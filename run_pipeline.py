#!/usr/bin/env python3
"""
Orquestador del pipeline FIIS-UNI Mesa de Partes.

Ejecuta en secuencia:
    1. Construcción del árbol Huffman (20 trámites) + exportación CSV/JSON.
    2. Construcción y validación del árbol de decisión + exportación JSON/PNG.
    3. Generación de las 4 figuras del artículo.
    4. Checklist de archivos esperados y verificación de las invariantes
       matemáticas del código (Kraft, cota de Shannon, optimalidad).

Salida: 0 si todo está correcto, 1 si falta algún artefacto o si alguna
invariante no se cumple.

Salidas (en ./outputs/):
    tabla1_iteraciones.csv          – 19 iteraciones del algoritmo de Huffman.
    tabla2_codigos.csv              – Tabla de códigos por trámite.
    tabla3_metricas.csv             – Métricas consolidadas.
    huffman_resultados.json         – Árbol Huffman serializado + métricas.
    arbol_decision.json             – Estructura del árbol de decisión.
    figura1_arbol_huffman.png       – Árbol binario de Huffman.
    figura2_barras_comparativa.png  – Comparativa de longitudes.
    figura3_arbol_decision.png      – Árbol de decisión coloreado.
    figura4_distribucion_tupa.png   – Donut de distribución por calificación.
"""

from __future__ import annotations

import os
import sys
import textwrap
from typing import List, Tuple

# Permite ejecutar desde el directorio raíz del proyecto.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.config import OUTPUT_DIR, asegurar_output_dir
from src.huffman import HuffmanFIIS
from src.arbol_decision import ArbolDecisionFIIS
from src import generar_graficas


# Archivos esperados al final del pipeline, con su destino en el artículo.
# Sirve de checklist de integridad: si falta alguno, el pipeline sale con 1.
ARCHIVOS_ESPERADOS: List[Tuple[str, str]] = [
    ("tabla1_iteraciones.csv",         "§3 Tabla 1 — iteraciones de Huffman"),
    ("tabla2_codigos.csv",             "§3 Tabla 2 — códigos por trámite"),
    ("tabla3_metricas.csv",            "§3 Tabla 3 — métricas consolidadas"),
    ("huffman_resultados.json",        "Apéndice digital — árbol serializado"),
    ("arbol_decision.json",            "§4 — estructura del árbol de decisión"),
    ("figura1_arbol_huffman.png",      "§3 Figura 1 — árbol de Huffman"),
    ("figura2_barras_comparativa.png", "§3 Figura 2 — fijo vs Huffman"),
    ("figura3_arbol_decision.png",     "§4 Figura 3 — árbol de decisión"),
    ("figura4_distribucion_tupa.png",  "§4 Figura 4 — distribución TUPA"),
]


def _print_header() -> None:
    print("══════════════════════════════════════")
    print(" PIPELINE FIIS-UNI | Mesa de Partes   ")
    print(" Matemática Discreta | FIIS-UNI       ")
    print("══════════════════════════════════════")
    print()


def _print_separator(titulo: str) -> None:
    print("══════════════════════════════════════")
    print(f" {titulo}")
    print("══════════════════════════════════════")


def main() -> int:
    """Corre todo el pipeline. Retorna 0 si OK, 1 si hubo WARNINGs."""
    _print_header()
    asegurar_output_dir(OUTPUT_DIR)

    # ----------------------------------------------------------------
    # Paso 1 — Huffman
    # ----------------------------------------------------------------
    print("[1/4] Construyendo árbol de Huffman (20 trámites)...")
    huffman = HuffmanFIIS()
    huffman.construir()
    # Mostramos las primeras 2 y la última iteración (el resto comprime).
    iters = huffman.iteraciones
    for r in iters[:2]:
        print(f"  Iter {r['iter']:02d}: {r['nodo_izq']}({r['peso_izq']:.3f}) + "
              f"{r['nodo_der']}({r['peso_der']:.3f}) → "
              f"{r['nodo_nuevo']}({r['peso_nuevo']:.3f})")
    print("  ...")
    r = iters[-1]
    print(f"  Iter {r['iter']:02d}: {r['nodo_izq']}({r['peso_izq']:.3f}) + "
          f"{r['nodo_der']}({r['peso_der']:.3f}) → Raíz({r['peso_nuevo']:.3f})")
    print(f"  ✓ Árbol construido en {len(iters)} iteraciones")

    huffman.exportar_csv()
    huffman.exportar_json()

    # ----------------------------------------------------------------
    # Paso 2 — Métricas
    # ----------------------------------------------------------------
    print()
    print("[2/4] Calculando métricas...")
    m = huffman.calcular_metricas()
    print(f"  ✓ L̄_huffman   = {m['L_huffman']:.3f} bits")
    print(f"  ✓ H(X)         = {m['H_entropia']:.3f} bits")
    print(f"  ✓ η            = {m['eficiencia_pct']:.2f}%")
    print(f"  ✓ Ahorro/fijo  = {m['ahorro_vs_fijo_pct']:.2f}%")
    print(f"  ✓ Kraft K(T)   = {m['kraft_sum']:.6f}")
    ok = "✓" if m["verificacion_shannon"] else "✗"
    print(f"  {ok} Shannon: {m['H_entropia']:.3f} ≤ "
          f"{m['L_huffman']:.3f} < {m['H_entropia']+1:.3f}")

    # Verificación por invariantes matemáticas.
    #
    # No se compara contra constantes fijas a propósito: L̄ y H(X) dependen de
    # la distribución en config.TRAMITES, así que cablear sus valores obliga a
    # editar este archivo cada vez que se recalibra una probabilidad. Lo que sí
    # debe cumplirse pase lo que pase son las propiedades del código óptimo, y
    # es eso lo que se verifica aquí.
    warnings: List[str] = []

    # Kraft: un código prefijo COMPLETO (todo nodo interno con 2 hijos, como
    # garantiza Huffman) satisface la igualdad, no sólo la desigualdad ≤ 1.
    if abs(m["kraft_sum"] - 1.0) > 1e-6:
        warnings.append(
            f"K(T) = {m['kraft_sum']:.6f} ≠ 1. El árbol no es un código "
            f"prefijo completo: hay un nodo interno con un solo hijo."
        )

    # Teorema de Shannon (codificación sin ruido): H(X) ≤ L̄ < H(X) + 1.
    if not m["verificacion_shannon"]:
        warnings.append(
            f"Cota de Shannon violada: no se cumple {m['H_entropia']:.3f} ≤ "
            f"{m['L_huffman']:.3f} < {m['H_entropia']+1:.3f}. Con un Huffman "
            f"correcto esto es imposible; revisar construir()."
        )

    # η = H/L̄ ≤ 100 %. Superar el 100 % significaría L̄ < H, es decir haber
    # comprimido por debajo del límite de Shannon: imposible.
    if m["eficiencia_pct"] > 100.0 + 1e-6:
        warnings.append(
            f"η = {m['eficiencia_pct']:.2f}% > 100%. Implica L̄ < H(X), lo que "
            f"contradice el límite teórico de compresión."
        )

    # Huffman es óptimo, así que nunca puede ser peor que el código de bloque.
    if m["L_huffman"] > config.BASELINE_BITS:
        warnings.append(
            f"L̄ = {m['L_huffman']:.3f} > {config.BASELINE_BITS} bits del "
            f"código fijo. Un código óptimo jamás puede perder contra el "
            f"baseline de bloque."
        )

    # ----------------------------------------------------------------
    # Paso 3 — Árbol de decisión (predicados normativos)
    # ----------------------------------------------------------------
    print()
    print("[3/4] Validando árbol de decisión (predicados normativos)...")
    arbol = ArbolDecisionFIIS()
    arbol.construir()
    props = arbol.validar()
    print(f"   ✓ DAG: {props['es_DAG']}  |  Árbol: {props['es_arbol']}  "
          f"|  Unicidad: {props['unicidad_trayectoria']}")
    print(f"   ✓ {len(props['caminos'])} caminos únicos raíz → hoja")
    print(f"   ✓ v1 — {config.FUENTE_NORMATIVA['v1']}")
    print(f"   ✓ v2 — {config.FUENTE_NORMATIVA['v2']}")
    print(f"   ✓ v3 — {config.FUENTE_NORMATIVA['v3']}")
    arbol.exportar_json()

    # ----------------------------------------------------------------
    # Paso 4 — Figuras
    # ----------------------------------------------------------------
    print()
    print("[4/4] Generando figuras...")
    generar_graficas.main(OUTPUT_DIR)

    # ----------------------------------------------------------------
    # Checklist + asignación por integrante
    # ----------------------------------------------------------------
    print()
    _print_separator("ARTEFACTOS GENERADOS")
    encontrados = 0
    for archivo, donde in ARCHIVOS_ESPERADOS:
        ruta = os.path.join(OUTPUT_DIR, archivo)
        existe = os.path.exists(ruta)
        marca = "✓" if existe else "✗"
        encontrados += int(existe)
        print(f"  {marca} {archivo:33s} → {donde}")

    print()
    if warnings:
        print("⚠  Advertencias:")
        for w in warnings:
            for linea in textwrap.wrap("- " + w, width=68):
                print(f"    {linea}")
        print()

    n = len(ARCHIVOS_ESPERADOS)
    print(f" Pipeline completado. {encontrados}/{n} archivos generados.")
    print()
    print("  Métricas TUPA UNI 2024:")
    print(f"  Aprobación automática (TUPA)  : "
          f"{config.PORCENTAJE_AUTOMATICA}% del volumen")
    print(f"  Evaluación previa     (TUPA)  : "
          f"{config.PORCENTAJE_EVALUACION}% del volumen")
    print("══════════════════════════════════════")

    return 0 if (encontrados == n and not warnings) else 1


if __name__ == "__main__":
    sys.exit(main())
