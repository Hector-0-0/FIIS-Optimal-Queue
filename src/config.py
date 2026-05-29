"""
Configuración central del proyecto FIIS-UNI Mesa de Partes.

Define la distribución oficial de 20 trámites, las descripciones legibles,
la agrupación por ventanillas del árbol de decisión y constantes globales
utilizadas por el motor Huffman y por el generador de figuras.

Teoría aplicada:
    - Distribución de probabilidad discreta P(X): sum_i p_i = 1
    - Codificación de longitud fija: l_fix = ceil(log2 |X|)
"""

from __future__ import annotations

import os
from typing import Dict, List

# ---------------------------------------------------------------------------
# Distribución oficial de los 20 trámites (P(X))
# ---------------------------------------------------------------------------
# Frecuencias relativas observadas en Mesa de Partes FIIS-UNI.
# REQUISITO: sum(TRAMITES.values()) == 1.0 (axioma de probabilidad).
TRAMITES: Dict[str, float] = {
    "T01_Constancia_Matricula":         0.250,
    "T02_Record_Academico":             0.150,
    "T03_Certificado_Estudios_Simple":  0.120,
    "T04_Retiro_Asignatura":            0.100,
    "T05_Orden_Merito":                 0.080,
    "T06_Rectificacion_Notas":          0.070,
    "T07_Retiro_Curso":                 0.050,
    "T08_Duplicado_Carnet":             0.040,
    "T09_Reserva_Matricula":            0.030,
    "T10_Retiro_Ciclo":                 0.020,
    "T11_Reincorporacion":              0.020,
    "T12_Constancia_No_Adeudo":         0.015,
    "T13_Examen_Subsanacion":           0.015,
    "T14_Examen_Regularizacion":        0.010,
    "T15_Constancia_Egresado":          0.010,
    "T16_Expedito_Bachiller":           0.008,
    "T17_Titulo_Profesional":           0.005,
    "T18_Bienestar_Universitario":      0.005,
    "T19_Traslado_Interno":             0.001,
    "T20_Traslado_Externo":             0.001,
}

# ---------------------------------------------------------------------------
# Descripción humana de cada trámite (para tablas y gráficos)
# ---------------------------------------------------------------------------
DESCRIPCION: Dict[str, str] = {
    "T01_Constancia_Matricula":         "Constancia de Matrícula",
    "T02_Record_Academico":             "Record Académico",
    "T03_Certificado_Estudios_Simple":  "Certificado de Estudios Simple",
    "T04_Retiro_Asignatura":            "Retiro de Asignatura (FIIS-EPI-FOR-019)",
    "T05_Orden_Merito":                 "Orden de Mérito",
    "T06_Rectificacion_Notas":          "Rectificación de Notas",
    "T07_Retiro_Curso":                 "Retiro de Curso",
    "T08_Duplicado_Carnet":             "Duplicado de Carnet",
    "T09_Reserva_Matricula":            "Reserva de Matrícula",
    "T10_Retiro_Ciclo":                 "Retiro de Ciclo",
    "T11_Reincorporacion":              "Reincorporación",
    "T12_Constancia_No_Adeudo":         "Constancia de No Adeudo",
    "T13_Examen_Subsanacion":           "Examen de Subsanación",
    "T14_Examen_Regularizacion":        "Examen de Regularización",
    "T15_Constancia_Egresado":          "Constancia de Egresado",
    "T16_Expedito_Bachiller":           "Expedito de Bachiller",
    "T17_Titulo_Profesional":           "Título Profesional",
    "T18_Bienestar_Universitario":      "Bienestar Universitario",
    "T19_Traslado_Interno":             "Traslado Interno",
    "T20_Traslado_Externo":             "Traslado Externo",
}

# ---------------------------------------------------------------------------
# Mapeo trámite → ventanilla (define las hojas del árbol de decisión)
# ---------------------------------------------------------------------------
# Clasificación basada en el TUPA UNI 2024 (RR N° 3698-2024-UNI, 64
# procedimientos) y la Ley N° 28683 (modifica Ley N° 27408) de atención
# preferencial.
#
# V1_Express_Automatica : aprobación automática TUPA  (2-5 días hábiles)
# V1_General_Evaluacion : evaluación previa TUPA      (10-30 días hábiles)
# V_Preferencial        : canal transversal (Ley N° 28683) — sin turno
# V_Orientacion_Caja    : canal transversal — expediente incompleto
VENTANILLAS: Dict[str, Dict] = {
    "V1_Express_Automatica": {
        "nombre":   "Ventanilla 1 Express — Aprobación Automática (TUPA UNI 2024)",
        "tramites": [
            "T01_Constancia_Matricula",
            "T02_Record_Academico",
            "T03_Certificado_Estudios_Simple",
            "T05_Orden_Merito",
            "T08_Duplicado_Carnet",
            "T12_Constancia_No_Adeudo",
            "T15_Constancia_Egresado",
        ],
        "color":      "#2E7D32",
        "plazo_tupa": "2–5 días hábiles",
    },
    "V1_General_Evaluacion": {
        "nombre":   "Ventanilla 1 General — Evaluación Previa (TUPA UNI 2024)",
        "tramites": [
            "T04_Retiro_Asignatura",
            "T06_Rectificacion_Notas",
            "T07_Retiro_Curso",
            "T09_Reserva_Matricula",
            "T10_Retiro_Ciclo",
            "T11_Reincorporacion",
            "T13_Examen_Subsanacion",
            "T14_Examen_Regularizacion",
            "T16_Expedito_Bachiller",
            "T17_Titulo_Profesional",
            "T18_Bienestar_Universitario",
            "T19_Traslado_Interno",
            "T20_Traslado_Externo",
        ],
        "color":      "#1565C0",
        "plazo_tupa": "10–30 días hábiles",
    },
    "V_Preferencial": {
        "nombre":   "Ventanilla Preferencial (Ley N° 28683)",
        # Transversal: aplica a cualquier trámite según condición del usuario,
        # no según tipo de trámite. Gestantes, adultos ≥ 60 años, personas
        # con discapacidad, acompañantes con niños (Ley 28683 / Ley 27408).
        "tramites":   [],
        "color":      "#6A1B9A",
        "plazo_tupa": "Inmediata (sin turno)",
    },
    "V_Orientacion_Caja": {
        "nombre":   "Orientación / Caja — Expediente Incompleto (TUPA UNI 2024)",
        # Transversal: aplica cuando el usuario no presenta comprobante de
        # pago vigente o le faltan requisitos del TUPA UNI 2024.
        "tramites":   [],
        "color":      "#E65100",
        "plazo_tupa": "N/A — derivación a completar requisitos",
    },
}

# Lookup inverso: tramite -> nombre de ventanilla. Sólo los canales NO
# transversales asignan trámites; V_Preferencial y V_Orientacion_Caja son
# canales transversales que aplican según condición del usuario o expediente.
TRAMITE_A_VENTANILLA: Dict[str, str] = {
    t: vent for vent, info in VENTANILLAS.items() for t in info["tramites"]
}

# Etiquetas legibles + colores derivados de VENTANILLAS (single source of truth).
VENTANILLA_DESC:  Dict[str, str] = {v: info["nombre"] for v, info in VENTANILLAS.items()}
VENTANILLA_COLOR: Dict[str, str] = {v: info["color"]  for v, info in VENTANILLAS.items()}

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------
# Longitud del código de bloque (baseline): ceil(log2(20)) = 5.
BASELINE_BITS: int = 5

# Carpeta donde el pipeline deposita CSV, JSON y PNG.
OUTPUT_DIR: str = "outputs"

# Tolerancia numérica para verificar sum(p_i) = 1.
PROB_TOL: float = 1e-9


# ---------------------------------------------------------------------------
# Clasificación TUPA UNI 2024 (RR N° 3698-2024-UNI)
# ---------------------------------------------------------------------------
# Lista de trámites con calificación "aprobación automática": el TUPA garantiza
# resolución en 2-5 días hábiles sin evaluación discrecional. El resto requiere
# evaluación previa (10-30 días hábiles).
TUPA_APROBACION_AUTOMATICA: List[str] = [
    "T01_Constancia_Matricula",
    "T02_Record_Academico",
    "T03_Certificado_Estudios_Simple",
    "T05_Orden_Merito",
    "T08_Duplicado_Carnet",
    "T12_Constancia_No_Adeudo",
    "T15_Constancia_Egresado",
]

TUPA_EVALUACION_PREVIA: List[str] = [
    t for t in TRAMITES if t not in TUPA_APROBACION_AUTOMATICA
]

# Porcentaje del volumen total atribuible a cada categoría TUPA.
PORCENTAJE_AUTOMATICA: float = round(
    sum(TRAMITES[t] for t in TUPA_APROBACION_AUTOMATICA) * 100, 1
)  # Resultado esperado: 66.5

PORCENTAJE_EVALUACION: float = round(
    sum(TRAMITES[t] for t in TUPA_EVALUACION_PREVIA) * 100, 1
)  # Resultado esperado: 33.5

# Fuente normativa de cada nodo de decisión del árbol.
FUENTE_NORMATIVA: Dict[str, str] = {
    "v1": "Ley N° 28683 (modifica Ley N° 27408) — atención preferencial",
    "v2": "TUPA UNI 2024, RR N° 3698-2024-UNI — admisibilidad del expediente",
    "v3": "TUPA UNI 2024, RR N° 3698-2024-UNI — calificación procedimental",
}


def validar_distribucion(dist: Dict[str, float] = None) -> None:
    """Verifica que la distribución de probabilidad sea válida.

    Args:
        dist: Diccionario {simbolo: probabilidad}. Si es None usa TRAMITES.

    Raises:
        ValueError: si alguna probabilidad es negativa o la suma difiere de 1
            en más que PROB_TOL.

    Example:
        >>> validar_distribucion({"a": 0.5, "b": 0.5})  # OK
        >>> validar_distribucion({"a": 0.7, "b": 0.7})  # raises ValueError
    """
    d = dist if dist is not None else TRAMITES
    if any(p < 0 for p in d.values()):
        raise ValueError("Toda probabilidad debe cumplir p_i >= 0.")
    total = sum(d.values())
    if abs(total - 1.0) > PROB_TOL:
        raise ValueError(
            f"sum(p_i) = {total:.10f} != 1.0  (diferencia {total - 1.0:+.2e}). "
            f"Ajusta los valores en config.TRAMITES."
        )


def asegurar_output_dir(ruta: str = OUTPUT_DIR) -> str:
    """Crea OUTPUT_DIR si no existe y retorna la ruta absoluta.

    Args:
        ruta: ruta relativa o absoluta a la carpeta de salida.

    Returns:
        Ruta absoluta lista para usar con open()/savefig().

    Raises:
        PermissionError: si no se puede crear la carpeta (mensaje legible).
    """
    try:
        os.makedirs(ruta, exist_ok=True)
    except PermissionError as e:
        raise PermissionError(
            f"No se pudo crear la carpeta '{ruta}'. "
            f"Revisa permisos del directorio actual: {e}"
        ) from e
    return os.path.abspath(ruta)
