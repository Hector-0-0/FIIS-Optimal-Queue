"""
Motor de codificación de Huffman para los 20 trámites FIIS-UNI.

Implementa el algoritmo clásico de Huffman (Huffman, 1952) usando un
min-heap binario para combinar iterativamente los dos símbolos de menor
probabilidad.

Resultados que produce:
    - Árbol binario óptimo (raíz tipo HuffmanNode).
    - Diccionario {tramite: codigo_binario_str}.
    - Métricas: longitud media L̄, entropía H(X), eficiencia η, ahorro
      relativo al baseline de bloque, sumatoria de Kraft K(T) y verificación
      del teorema de Shannon: H(X) <= L̄ < H(X) + 1.
    - Exporta tres CSV (iteraciones, códigos, métricas) y un JSON consolidado.

Teoría:
    Entropía:          H(X)  = - sum_i p_i · log2(p_i)
    Longitud media:    L̄    =   sum_i p_i · l_i
    Kraft equality:    sum_i 2^(-l_i) = 1   (prefijo completo)
    Shannon noiseless: H(X) <= L̄ < H(X) + 1
"""

from __future__ import annotations

import csv
import heapq
import json
import math
import os
from typing import Dict, List, Optional, Tuple

from src.config import (
    BASELINE_BITS,
    OUTPUT_DIR,
    TRAMITES,
    asegurar_output_dir,
    validar_distribucion,
)


# ---------------------------------------------------------------------------
# Nodo del árbol binario de Huffman
# ---------------------------------------------------------------------------
class HuffmanNode:
    """Nodo del árbol binario de Huffman.

    Un nodo es hoja sii tiene `symbol != None`; los nodos internos almacenan
    referencias a sus dos hijos (`left`, `right`) y el peso acumulado igual
    a la suma de probabilidades del subárbol.

    Attributes:
        weight: probabilidad agregada del subárbol.
        symbol: identificador del trámite (solo en hojas).
        left:   hijo izquierdo (arista etiquetada "0").
        right:  hijo derecho  (arista etiquetada "1").
        nombre: etiqueta interna (Tij o Nkk) usada en tablas e iteraciones.
    """

    __slots__ = ("weight", "symbol", "left", "right", "nombre")

    def __init__(
        self,
        weight: float,
        symbol: Optional[str] = None,
        left: Optional["HuffmanNode"] = None,
        right: Optional["HuffmanNode"] = None,
        nombre: str = "",
    ) -> None:
        self.weight = weight
        self.symbol = symbol
        self.left = left
        self.right = right
        self.nombre = nombre or (symbol if symbol else "N??")

    @property
    def is_leaf(self) -> bool:
        """True si el nodo es una hoja del árbol (símbolo asignado)."""
        return self.symbol is not None


# ---------------------------------------------------------------------------
# Motor Huffman
# ---------------------------------------------------------------------------
class HuffmanFIIS:
    """Codificador de Huffman para los 20 trámites de FIIS-UNI.

    Args:
        distribucion: dict {simbolo: probabilidad}. Si es None usa
            `config.TRAMITES`.

    Example:
        >>> h = HuffmanFIIS()
        >>> h.construir()
        >>> h.codigos["T01_Constancia_Matricula"]   # cadena binaria
        '...'
        >>> h.calcular_metricas()["L_huffman"]      # float
    """

    def __init__(self, distribucion: Optional[Dict[str, float]] = None) -> None:
        self.dist: Dict[str, float] = dict(distribucion or TRAMITES)
        validar_distribucion(self.dist)
        self.raiz: Optional[HuffmanNode] = None
        self.codigos: Dict[str, str] = {}
        self.iteraciones: List[Dict] = []

    # ------------------------------------------------------------------
    # Construcción del árbol
    # ------------------------------------------------------------------
    def construir(self) -> HuffmanNode:
        """Construye el árbol óptimo de Huffman con min-heap (O(n log n)).

        Algoritmo (Huffman 1952; van Leeuwen 1976 demuestra cota O(n) con
        cola pre-ordenada). En cada iteración se extraen los dos nodos de
        menor peso, se combinan en uno nuevo y se reinserta en la cola.
        Tras n-1 iteraciones queda un único nodo: la raíz.

        Returns:
            Raíz del árbol (HuffmanNode con weight == 1.0).
        """
        # Inicializamos el heap con (peso, contador_estable, nodo).
        # El contador rompe empates de peso de forma determinista (FIFO).
        heap: List[Tuple[float, int, HuffmanNode]] = []
        items = sorted(self.dist.items(), key=lambda kv: (kv[1], kv[0]))
        counter = 0
        for sym, p in items:
            heapq.heappush(heap, (p, counter, HuffmanNode(p, symbol=sym, nombre=sym[:3])))
            counter += 1

        self.iteraciones.clear()
        # Realizamos exactamente n-1 fusiones (n hojas -> 1 raíz).
        for it in range(1, len(self.dist)):
            w1, _, n1 = heapq.heappop(heap)
            w2, _, n2 = heapq.heappop(heap)
            # Convención: el de menor peso va a la izquierda (arista "0").
            merged = HuffmanNode(
                weight=w1 + w2,
                left=n1,
                right=n2,
                nombre=f"N{it:02d}",
            )
            heapq.heappush(heap, (merged.weight, counter, merged))
            counter += 1

            self.iteraciones.append({
                "iter":         it,
                "nodo_izq":     n1.nombre,
                "peso_izq":     round(w1, 6),
                "nodo_der":     n2.nombre,
                "peso_der":     round(w2, 6),
                "nodo_nuevo":   merged.nombre,
                "peso_nuevo":   round(merged.weight, 6),
            })

        self.raiz = heap[0][2]
        self.raiz.nombre = "ROOT"
        self.obtener_codigos()
        return self.raiz

    # ------------------------------------------------------------------
    # Extracción de códigos por DFS pre-orden
    # ------------------------------------------------------------------
    def obtener_codigos(self) -> Dict[str, str]:
        """Recorre el árbol en DFS y asigna a cada hoja su cadena binaria.

        Convención usada: arista al hijo izquierdo = "0", al derecho = "1".
        El DFS pre-orden garantiza unicidad de trayectoria raíz -> hoja, lo
        cual implica la propiedad de prefijo libre del código resultante.

        Returns:
            Diccionario {simbolo: codigo_binario_str}.
        """
        if self.raiz is None:
            raise RuntimeError("Llama a construir() antes de obtener_codigos().")

        self.codigos.clear()

        def _dfs(nodo: HuffmanNode, prefijo: str) -> None:
            if nodo.is_leaf:
                # Caso especial: un solo símbolo en el alfabeto -> código "0".
                self.codigos[nodo.symbol] = prefijo or "0"
                return
            if nodo.left is not None:
                _dfs(nodo.left, prefijo + "0")
            if nodo.right is not None:
                _dfs(nodo.right, prefijo + "1")

        _dfs(self.raiz, "")
        return self.codigos

    # ------------------------------------------------------------------
    # Métricas teóricas
    # ------------------------------------------------------------------
    def calcular_metricas(self) -> Dict[str, float]:
        """Calcula L̄, H(X), eficiencia, ahorro vs fijo y verifica Kraft.

        Returns:
            Diccionario con claves:
                L_huffman             : longitud media del código (bits/sym)
                H_entropia            : entropía de la fuente (bits/sym)
                eficiencia_pct        : 100 · H / L̄
                ahorro_vs_fijo_pct    : 100 · (l_fix - L̄) / l_fix
                kraft_sum             : sum 2^(-l_i) (debe ser ≈ 1.0)
                verificacion_shannon  : True si H ≤ L̄ < H + 1
                L_fijo                : BASELINE_BITS
        """
        if not self.codigos:
            raise RuntimeError("Construye el árbol antes de calcular métricas.")

        # L̄ = Σ p_i · l_i
        L = sum(self.dist[s] * len(c) for s, c in self.codigos.items())
        # H(X) = - Σ p_i · log2(p_i)
        H = -sum(p * math.log2(p) for p in self.dist.values() if p > 0)
        # Kraft inequality: para un código prefijo completo K(T) = 1.
        kraft = sum(2 ** (-len(c)) for c in self.codigos.values())
        # Teorema de Shannon (noiseless source coding): H(X) ≤ L̄ < H(X) + 1.
        shannon_ok = (H - 1e-9 <= L < H + 1.0 + 1e-9)
        eta = 100.0 * H / L if L > 0 else 0.0
        ahorro = 100.0 * (BASELINE_BITS - L) / BASELINE_BITS

        return {
            "L_huffman":             round(L, 6),
            "H_entropia":            round(H, 6),
            "eficiencia_pct":        round(eta, 4),
            "ahorro_vs_fijo_pct":    round(ahorro, 4),
            "kraft_sum":             round(kraft, 6),
            "verificacion_shannon":  bool(shannon_ok),
            "L_fijo":                BASELINE_BITS,
        }

    # ------------------------------------------------------------------
    # Codificación / decodificación de mensajes
    # ------------------------------------------------------------------
    def codificar(self, mensaje: List[str]) -> str:
        """Codifica una lista de trámites como cadena binaria.

        Args:
            mensaje: lista de identificadores (acepta forma corta "T01" o
                completa "T01_Constancia_Matricula").

        Returns:
            Cadena binaria concatenando los códigos de cada trámite.

        Raises:
            KeyError: si algún identificador no está en el alfabeto.
        """
        partes: List[str] = []
        for token in mensaje:
            sym = self._resolver_simbolo(token)
            partes.append(self.codigos[sym])
        return "".join(partes)

    def decodificar(self, bits: str) -> List[str]:
        """Decodifica una cadena binaria recorriendo el árbol bit a bit.

        Args:
            bits: cadena de "0"/"1".

        Returns:
            Lista de trámites decodificados (en su forma "Tij_...").

        Raises:
            ValueError: si la cadena no termina en una hoja válida.
        """
        if self.raiz is None:
            raise RuntimeError("Construye el árbol antes de decodificar.")
        resultado: List[str] = []
        nodo = self.raiz
        for bit in bits:
            nodo = nodo.left if bit == "0" else nodo.right
            if nodo is None:
                raise ValueError("Cadena binaria inválida (prefijo desconocido).")
            if nodo.is_leaf:
                resultado.append(nodo.symbol)
                nodo = self.raiz
        if nodo is not self.raiz:
            raise ValueError("La cadena no termina en una hoja (longitud parcial).")
        return resultado

    def _resolver_simbolo(self, token: str) -> str:
        """Acepta 'T01' o 'T01_Constancia_Matricula' y devuelve la clave canónica."""
        if token in self.dist:
            return token
        candidatos = [s for s in self.dist if s.startswith(token + "_") or s == token]
        if len(candidatos) == 1:
            return candidatos[0]
        raise KeyError(f"Trámite no reconocido: {token!r}")

    # ------------------------------------------------------------------
    # Exportadores
    # ------------------------------------------------------------------
    def exportar_csv(self, directorio: str = OUTPUT_DIR) -> Dict[str, str]:
        """Exporta tres CSV: iteraciones, códigos y métricas.

        Args:
            directorio: carpeta de salida (se crea si no existe).

        Returns:
            Diccionario {nombre_logico: ruta_absoluta} de los archivos creados.

        Nota:
            Los writers usan lineterminator="\\n" en vez del "\\r\\n" que trae
            csv por defecto (RFC 4180). Estos CSV se versionan, y con git
            normalizando a LF al commitear, el CRLF hacía que los tres
            aparecieran como modificados después de cada corrida aunque el
            contenido fuese idéntico.
        """
        out = asegurar_output_dir(directorio)
        rutas: Dict[str, str] = {}

        rutas["tabla1"] = os.path.join(out, "tabla1_iteraciones.csv")
        with open(rutas["tabla1"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["iter", "nodo_izq", "peso_izq",
                        "nodo_der", "peso_der",
                        "nodo_nuevo", "peso_nuevo"])
            for r in self.iteraciones:
                w.writerow([r["iter"], r["nodo_izq"], r["peso_izq"],
                            r["nodo_der"], r["peso_der"],
                            r["nodo_nuevo"], r["peso_nuevo"]])

        rutas["tabla2"] = os.path.join(out, "tabla2_codigos.csv")
        # Orden de mayor a menor probabilidad (presentación canónica).
        orden = sorted(self.codigos.keys(),
                       key=lambda s: (-self.dist[s], s))
        with open(rutas["tabla2"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["tramite", "probabilidad", "codigo", "longitud_bits"])
            for s in orden:
                c = self.codigos[s]
                w.writerow([s, self.dist[s], c, len(c)])

        m = self.calcular_metricas()
        rutas["tabla3"] = os.path.join(out, "tabla3_metricas.csv")
        with open(rutas["tabla3"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(list(m.keys()))
            w.writerow(list(m.values()))

        return rutas

    def exportar_json(self, directorio: str = OUTPUT_DIR) -> str:
        """Exporta resultados completos en JSON listo para consumir por figuras.

        Args:
            directorio: carpeta de salida.

        Returns:
            Ruta absoluta del archivo `huffman_resultados.json`.
        """
        out = asegurar_output_dir(directorio)
        ruta = os.path.join(out, "huffman_resultados.json")

        # Serializamos el árbol como dict recursivo (referencias seguras).
        def _arbol_a_dict(n: Optional[HuffmanNode]) -> Optional[Dict]:
            if n is None:
                return None
            return {
                "nombre":  n.nombre,
                "peso":    round(n.weight, 6),
                "symbol":  n.symbol,
                "is_leaf": n.is_leaf,
                "left":    _arbol_a_dict(n.left),
                "right":   _arbol_a_dict(n.right),
            }

        payload = {
            "distribucion":  self.dist,
            "codigos":       self.codigos,
            "longitudes":    {s: len(c) for s, c in self.codigos.items()},
            "metricas":      self.calcular_metricas(),
            "iteraciones":   self.iteraciones,
            "arbol":         _arbol_a_dict(self.raiz),
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return ruta


# ---------------------------------------------------------------------------
# Entry point standalone
# ---------------------------------------------------------------------------
def main() -> None:
    """Construye el árbol, exporta artefactos e imprime checklist de métricas."""
    print("Construyendo árbol de Huffman (20 trámites)...")
    h = HuffmanFIIS()
    h.construir()
    h.exportar_csv()
    h.exportar_json()
    m = h.calcular_metricas()
    print(f"  ✓ L̄ = {m['L_huffman']:.3f} bits")
    print(f"  ✓ H(X) = {m['H_entropia']:.3f}")
    print(f"  ✓ η = {m['eficiencia_pct']:.2f}%")
    print(f"  ✓ Ahorro = {m['ahorro_vs_fijo_pct']:.2f}%")
    print(f"  ✓ K(T) = {m['kraft_sum']:.6f}")
    cota_inf = m["H_entropia"]
    cota_sup = m["H_entropia"] + 1
    ok = "✓" if m["verificacion_shannon"] else "✗"
    print(f"  {ok} Shannon: {cota_inf:.3f} ≤ {m['L_huffman']:.3f} < {cota_sup:.3f}")


if __name__ == "__main__":
    main()
