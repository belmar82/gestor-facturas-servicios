"""Configuración de la aplicación.

Todo lo que puede cambiar con el tiempo (plantilla del oficio, destinataria,
firmantes, textos, colores de la tabla, nombres de los archivos de salida) vive en
`config/config.json`.  Este módulo lo lee, lo completa con los valores por defecto y
sabe guardarlo.
"""
import json
import os
import sys

VERSION = "1.1"


def _carpeta_aplicacion():
    """Carpeta donde viven `config/`, `salidas/`, `respaldos/` y `registros/`.

    Si el programa está empaquetado como .exe, es la carpeta donde está el ejecutable;
    si se ejecuta desde el código fuente, la carpeta del proyecto.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = _carpeta_aplicacion()
RUTA_CONFIG = os.path.join(BASE, "config", "config.json")

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
MESES_MIN = {k: v.lower() for k, v in MESES.items()}
MESES_POR_NOMBRE = {}
for _n, _nombre in MESES.items():
    MESES_POR_NOMBRE[_nombre.lower()] = _n
    MESES_POR_NOMBRE[_nombre.lower()[:3]] = _n
MESES_POR_NOMBRE["setiembre"] = 9

POR_DEFECTO = {
    "version": 1,
    "general": {
        "carpeta_salida": "salidas",
        "carpeta_respaldos": "respaldos",
        "carpeta_registros": "registros",
        "diccionario": "config/diccionario_ejemplo.xlsx",
        "incluir_facturas_sin_poliza": False,
        "incluir_otros_conceptos_en_facturacion": True,
        "incluir_otros_cobros_en_facturacion": False,
        "total_deuda_desde": "2026-08",
        "orden_informe": "diccionario",
    },
    "informe": {
        "titulo": "RELACIÓN DE FACTURAS TRIPLE A - {MES_TITULO} {ANIO}",
        "hoja_detalle": "DETALLE",
        "hoja_informe": "TABLA DE INFORME",
        "hoja_sin_coincidencia": "SIN COINCIDENCIA",
        "nombre_archivo": "TABLA DE INFORME {MES_TITULO} {ANIO}.xlsx",
    },
    "tabla": {
        "fuente": "C:/Windows/Fonts/arial.ttf",
        "fuente_negrita": "C:/Windows/Fonts/arialbd.ttf",
        "dpi": 300,
        "tamano_max": 42,
        "tamano_min": 20,
        "color_encabezado": "#1F4E79",
        "color_encabezado_texto": "#FFFFFF",
        "color_filas_alternas": "#EAF1F8",
        "color_total": "#CDD9E5",
        "color_borde": "#9DB2C6",
        "color_titulo": "#1F4E79",
    },
    "oficio": {
        "plantilla": "config/plantilla_remision.docx",
        "nombre_salida": "REMISION {MES_TITULO} {ANIO}.docx",
        "pdf_con_facturas": True,
        "nombre_pdf": "REMISION Triple A {MES_TITULO} {ANIO} - oficio y facturas.pdf",
        "fecha": "auto",
        "ciudad_fecha": "Ciudad",
        "destinatarios": [
            [
                "Doctora",
                "NOMBRE DEL FUNCIONARIO",
                "Secretaria General.",
            ],
            [
                "Doctora",
                "NOMBRE DEL FUNCIONARIO",
                "Secretaria privada.",
            ],
            [
                "Doctora",
                "NOMBRE DEL FUNCIONARIO",
                "Tesorero Municipal.",
                "Nombre de la entidad",
                "La ciudad.",
            ],
        ],
        "asunto": "Solicitud de CDP y RP para pago de facturas de Triple A, {MES_TITULO} {ANIO}.",
        "cuerpo": (
            "Mediante la presente se envía la relación de las facturas de la empresa Triple A por "
            "valor de {VALOR}, correspondientes a la prestación del servicio de Agua y Alcantarillado "
            "durante el mes de {MES_MIN} de {ANIO} a las Instituciones Educativas del Municipio de "
            "Soledad, las cuales fueron revisadas por parte de la Secretaría de Educación para "
            "solicitar la generación de CDP y RP necesarios para la realizar el proceso de pago."
        ),
        "remitente": [
            "NOMBRE DEL REMITENTE.",
            "Secretaria de Educación.",
            "Nombre de la entidad",
        ],
        "proyecto": ["Proyectó: {NOMBRE}", "\t{CARGO}"],
        "proyecto_nombre": "Nombre del practicante",
        "proyecto_cargo": "Secretario (E)",
        "reviso": ["Revisó: {NOMBRE}", "\t{CARGO}"],
        "reviso_nombre": "Nombre del jefe inmediato",
        "reviso_cargo": "Profesional Universitario",
        "insertar_tabla": True,
        "pagina_nueva_para_tabla": True,
        "ancho_tabla_cm": 0.0,
    },
}


def ruta(*partes):
    """Ruta absoluta a partir de la carpeta de la aplicación."""
    return os.path.join(BASE, *partes)


def _resolver(valor):
    if isinstance(valor, str) and valor and not os.path.isabs(valor):
        return os.path.join(BASE, valor)
    return valor


def _mezclar(base, encima):
    for clave, valor in (encima or {}).items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _mezclar(base[clave], valor)
        else:
            base[clave] = valor
    return base


def cargar(archivo=None):
    """Devuelve la configuración combinada (valores por defecto + config.json)."""
    import copy
    cfg = copy.deepcopy(POR_DEFECTO)
    archivo = archivo or RUTA_CONFIG
    if os.path.exists(archivo):
        with open(archivo, "r", encoding="utf-8") as fh:
            _mezclar(cfg, json.load(fh))
    return cfg


def guardar(cfg, archivo=None):
    archivo = archivo or RUTA_CONFIG
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    return archivo


def nombre_mes(numero):
    return MESES.get(int(numero), "")


def numero_mes(nombre):
    return MESES_POR_NOMBRE.get(str(nombre).strip().lower()[:3]) or MESES_POR_NOMBRE.get(
        str(nombre).strip().lower()
    )
