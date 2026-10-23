"""Lectura de los PDF: texto completo, texto por página y valores de la columna derecha.

Los recuadros de resumen de las facturas (SERVICIOS FACTURADOS, TOTAL DEUDA, etc.) traen
las etiquetas como imagen, así que los valores se ubican por su posición en la página:
los que están a la derecha y ordenados de arriba hacia abajo.
"""
import re

from pypdf import PdfReader


def abrir(ruta):
    return PdfReader(ruta)


def leer_texto(ruta):
    """Texto de todas las páginas, unido con saltos de línea."""
    lector = abrir(ruta)
    return "\n".join((pagina.extract_text() or "") for pagina in lector.pages)


def leer_pagina(ruta, indice=0):
    lector = abrir(ruta)
    if indice >= len(lector.pages):
        return ""
    return lector.pages[indice].extract_text() or ""


def normalizar(texto):
    """Quita espacios repetidos y espacios duros para poder buscar con expresiones."""
    texto = (texto or "").replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", texto)


def sin_acentos(texto):
    """Quita tildes (y la diéresis) para comparar textos sin depender del acento."""
    reemplazos = str.maketrans("áéíóúüÁÉÍÓÚÜñÑ", "aeiouuAEIOUUnN")
    return (texto or "").translate(reemplazos)


def valores_derecha(ruta, pagina=0, umbral=0.55, patron=r"\$\s?-?[\d.,]+"):
    """Valores monetarios de la columna derecha, de arriba hacia abajo."""
    lector = abrir(ruta)
    if pagina >= len(lector.pages):
        return []
    hoja = lector.pages[pagina]
    ancho = float(hoja.mediabox.width)
    hallados = []

    def visitante(texto, cm, tm, fuente, tamano):
        t = (texto or "").strip()
        if re.fullmatch(patron, t):
            hallados.append((round(tm[5]), round(tm[4]), t))

    hoja.extract_text(visitor_text=visitante)
    derecha = [h for h in hallados if h[1] > umbral * ancho]
    derecha.sort(key=lambda h: -h[0])
    return [h[2] for h in derecha]


def a_entero(texto):
    """'$ 24.736.180' -> 24736180 ; '$-64,562' -> -64562."""
    if texto is None:
        return None
    crudo = str(texto)
    negativo = "-" in crudo
    digitos = re.sub(r"[^\d]", "", crudo)
    if not digitos:
        return None
    valor = int(digitos)
    return -valor if negativo else valor


def buscar(patrones, texto, grupo=1):
    """Devuelve el primer grupo que coincida con alguno de los patrones."""
    for patron in patrones:
        hallado = re.search(patron, texto, re.IGNORECASE)
        if hallado:
            return hallado.group(grupo)
    return None


def formatear_moneda(valor):
    """1234567 -> '1.234.567' (formato colombiano)."""
    if valor is None or valor == "":
        return ""
    return f"{int(round(float(valor))):,}".replace(",", ".")
