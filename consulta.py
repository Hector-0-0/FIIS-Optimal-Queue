"""
Consulta rapida de ventanilla y codigo para un tramite.

La idea es no tener que escribir codigo largo en la terminal para probar.
Ingresas el tramite (por ejemplo T01) y te dice a que ventanilla va y con
que codigo quedo (el del arbol de decision y el de Huffman).

Formas de usarlo:
    uv run python consulta.py          -> pregunta los datos paso a paso
    uv run python consulta.py T01      -> consulta directa de un tramite
"""

import sys

from src.config import TRAMITES, DESCRIPCION
from src.huffman import HuffmanFIIS
from src.arbol_decision import ArbolDecisionFIIS


def buscar_tramite(texto):
    # Acepta "t01", "T01" o el nombre completo "T01_Constancia_Matricula".
    texto = texto.strip().upper()
    for t in TRAMITES:
        if texto == t.upper() or texto == t[:3] or t.upper().startswith(texto + "_"):
            return t
    return None


def mostrar_lista():
    print("\nTramites disponibles:")
    for t in TRAMITES:
        print("  " + t[:3] + "  " + DESCRIPCION[t])


def preguntar(texto, defecto_si=False):
    marca = "s" if defecto_si else "n"
    r = input(texto + " [s/n] (enter = " + marca + "): ").strip().lower()
    if r == "":
        return defecto_si
    return r.startswith("s")


def consultar(tramite, preferencial=False, expediente_completo=True):
    # Reusamos las dos clases del proyecto sin tocarlas.
    huffman = HuffmanFIIS()
    huffman.construir()

    arbol = ArbolDecisionFIIS()
    arbol.construir()
    resultado = arbol.clasificar({
        "atencion_preferencial": preferencial,
        "expediente_completo": expediente_completo,
        "codigo_tramite": tramite,
    })

    print()
    print("Tramite     : " + tramite[:3] + " - " + DESCRIPCION[tramite])
    print("Ventanilla  : " + resultado["nombre_ventanilla"])
    print("Codigo ruta : " + resultado["codigo_binario"] +
          "  (" + " -> ".join(resultado["camino"]) + ")")
    print("Codigo Huffman: " + huffman.codigos[tramite])
    print()


def main():
    # Modo directo: te pasan el tramite como argumento.
    if len(sys.argv) > 1:
        tramite = buscar_tramite(sys.argv[1])
        if tramite is None:
            print("No encontre el tramite '" + sys.argv[1] + "'.")
            mostrar_lista()
            return
        consultar(tramite)
        return

    # Modo interactivo.
    print("=== Mesa de Partes FIIS - Consulta de ventanilla ===")
    mostrar_lista()

    entrada = input("\nCodigo del tramite (ej. T01): ")
    tramite = buscar_tramite(entrada)
    if tramite is None:
        print("No encontre ese tramite, revisa la lista de arriba.")
        return

    preferencial = preguntar("Atencion preferencial (gestante, adulto mayor, etc.)?")
    completo = preguntar("Expediente completo (pago y requisitos)?", defecto_si=True)
    consultar(tramite, preferencial, completo)


if __name__ == "__main__":
    main()
