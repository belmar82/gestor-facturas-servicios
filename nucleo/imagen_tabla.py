"""Dibuja la tabla del informe como imagen para pegarla en el oficio.

* Se elige el mayor tamaño de letra con el que la tabla quepa en el ancho y el alto
  disponibles (el alto útil de una página del oficio).
* La columna de la Institución Educativa recibe el espacio sobrante y, si un nombre no
  cabe, se parte en dos líneas; en el peor caso se recorta con puntos suspensivos.
* Si la tabla no cabe en una página, se reparte en varias y en cada una se repite el
  encabezado.
"""
import os

from PIL import Image, ImageDraw, ImageFont

FUENTES = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
           "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/tahoma.ttf"]
FUENTES_NEGRITA = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                   "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/tahomabd.ttf"]

ALINEACION = {
    "item": "centro",
    "poliza": "centro",
    "factura": "centro",
    "centrado": "centro",
    "texto": "izquierda",
    "entero": "derecha",
    "moneda": "derecha",
    "moneda_oculta": "derecha",
}


class PaginaTabla:
    """Una imagen de tabla lista para insertar en una página del oficio."""

    def __init__(self, imagen, primera):
        self.imagen = imagen
        self.primera = primera


def _fuente(preferida, alternativas, tamano):
    for ruta in [preferida] + alternativas:
        if ruta and os.path.exists(ruta):
            try:
                return ImageFont.truetype(ruta, tamano)
            except Exception:
                continue
    return ImageFont.load_default()


def _ancho(dibujo, texto, fuente):
    caja = dibujo.textbbox((0, 0), texto or "", font=fuente)
    return caja[2] - caja[0]


def _alto(dibujo, texto, fuente):
    caja = dibujo.textbbox((0, 0), texto or "Ag", font=fuente)
    return caja[3] - caja[1]


def _recortar(dibujo, texto, fuente, ancho_max):
    if _ancho(dibujo, texto, fuente) <= ancho_max:
        return texto
    while texto and _ancho(dibujo, texto + "…", fuente) > ancho_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _partir(dibujo, texto, fuente, ancho_max, max_lineas=2):
    """Parte el texto en varias líneas para que quepa en el ancho de la columna."""
    if not texto:
        return [""]
    if _ancho(dibujo, texto, fuente) <= ancho_max:
        return [texto]
    palabras = str(texto).split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if not actual or _ancho(dibujo, prueba, fuente) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
        if len(lineas) == max_lineas - 1:
            break
    if actual:
        lineas.append(actual)
    lineas = lineas[:max_lineas]
    return [_recortar(dibujo, linea, fuente, ancho_max) for linea in lineas]


def formatear(valor, tipo):
    if valor is None or valor == "":
        return ""
    if tipo in ("moneda", "entero", "moneda_oculta"):
        return f"{int(round(float(valor))):,}".replace(",", ".")
    return str(valor)


def _texto_celda(dibujo, caja, lineas, fuente, alineacion, color):
    x0, y0, x1, y1 = caja
    if isinstance(lineas, str):
        lineas = [lineas]
    alto_linea = max(_alto(dibujo, linea, fuente) for linea in lineas) + 4
    total = alto_linea * len(lineas)
    y = y0 + max(0, (y1 - y0 - total) / 2)
    for linea in lineas:
        ancho = _ancho(dibujo, linea, fuente)
        if alineacion == "derecha":
            x = x1 - ancho - max(6, (x1 - x0) * 0.03)
        elif alineacion == "centro":
            x = x0 + (x1 - x0 - ancho) / 2
        else:
            x = x0 + max(6, (x1 - x0) * 0.02)
        dibujo.text((x, y), linea, font=fuente, fill=color)
        y += alto_linea


def construir(titulo, encabezados, filas, totales, tipos, ancho_cm, alto_cm, cfg):
    """Devuelve la lista de páginas (imágenes) con la tabla dibujada."""
    dpi = int(cfg.get("dpi", 300))
    px_cm = dpi / 2.54
    ancho_px = int(ancho_cm * px_cm)
    alto_px = int(alto_cm * px_cm)
    tamano_max = int(cfg.get("tamano_max", 42))
    tamano_min = int(cfg.get("tamano_min", 20))
    indice_texto = tipos.index("texto") if "texto" in tipos else None

    elegido = None
    for tamano in range(tamano_max, tamano_min - 1, -2):
        fuente = _fuente(cfg.get("fuente"), FUENTES, tamano)
        negrita = _fuente(cfg.get("fuente_negrita"), FUENTES_NEGRITA, tamano)
        relleno = max(6, int(tamano * 0.5))
        provisional = Image.new("RGB", (10, 10), "white")
        dibujo = ImageDraw.Draw(provisional)

        anchos = []
        for indice, titulo_col in enumerate(encabezados):
            ancho = _ancho(dibujo, str(titulo_col), negrita)
            for fila in list(filas) + ([totales] if totales else []):
                if indice < len(fila):
                    ancho = max(ancho, _ancho(dibujo, formatear(fila[indice], tipos[indice]), fuente))
            anchos.append(ancho + 2 * relleno)

        # la columna de texto no puede acaparar más de la mitad de la tabla
        if indice_texto is not None:
            tope = int(ancho_px * 0.5)
            anchos[indice_texto] = min(anchos[indice_texto], max(tope, int(tamano * 8)))

        sobrante = ancho_px - sum(anchos)
        if sobrante > 0 and indice_texto is not None:
            anchos[indice_texto] += sobrante

        ancho_total = sum(anchos)
        if indice_texto is not None and ancho_total > ancho_px:
            exceso = ancho_total - ancho_px
            anchos[indice_texto] = max(int(tamano * 8), anchos[indice_texto] - exceso)
            ancho_total = sum(anchos)

        alto_fila = int(tamano * 1.5) + 6
        alto_encabezado = alto_fila + 10
        alto_titulo = int(tamano * 1.7) + 16 if titulo else 0

        lineas_filas, alto_filas = [], []
        for fila in filas:
            if indice_texto is not None and indice_texto < len(fila):
                disponible = anchos[indice_texto] - 2 * relleno
                lineas = _partir(dibujo, formatear(fila[indice_texto], "texto"), fuente, disponible)
            else:
                lineas = [""]
            lineas_filas.append(lineas)
            alto_filas.append(alto_fila * len(lineas))

        alto_total = alto_titulo + alto_encabezado + sum(alto_filas) + alto_fila
        elegido = (tamano, fuente, negrita, anchos, relleno, alto_fila, alto_encabezado,
                   alto_titulo, lineas_filas, alto_filas, ancho_total)
        if ancho_total <= ancho_px and alto_total <= alto_px:
            break

    (tamano, fuente, negrita, anchos, relleno, alto_fila, alto_encabezado, alto_titulo,
     lineas_filas, alto_filas, ancho_total) = elegido

    # reparto por páginas según el alto real de cada fila
    disponible = alto_px - alto_titulo - alto_encabezado - alto_fila
    paginas_indices, actual, acumulado = [], [], 0
    for indice, alto in enumerate(alto_filas):
        if actual and acumulado + alto > disponible:
            paginas_indices.append(actual)
            actual, acumulado = [], 0
        actual.append(indice)
        acumulado += alto
    if actual or not paginas_indices:
        paginas_indices.append(actual)

    colores = {
        "encabezado": cfg.get("color_encabezado", "#1F4E79"),
        "encabezado_texto": cfg.get("color_encabezado_texto", "#FFFFFF"),
        "alternas": cfg.get("color_filas_alternas", "#EAF1F8"),
        "total": cfg.get("color_total", "#CDD9E5"),
        "borde": cfg.get("color_borde", "#9DB2C6"),
        "titulo": cfg.get("color_titulo", "#1F4E79"),
    }

    paginas = []
    for numero_pagina, indices in enumerate(paginas_indices):
        ultima = numero_pagina == len(paginas_indices) - 1
        alto = alto_titulo + alto_encabezado + sum(alto_filas[i] for i in indices)
        alto += alto_fila if ultima else 0
        imagen = Image.new("RGB", (ancho_total, max(alto + 4, 40)), "white")
        dibujo = ImageDraw.Draw(imagen)
        y = 0

        if titulo:
            _texto_celda(dibujo, (0, y, ancho_total, y + alto_titulo), titulo, negrita, "centro", colores["titulo"])
            y += alto_titulo

        limites, x = [], 0
        for ancho in anchos:
            limites.append((x, x + ancho))
            x += ancho

        dibujo.rectangle([0, y, ancho_total - 1, y + alto_encabezado - 1], fill=colores["encabezado"])
        for indice, titulo_col in enumerate(encabezados):
            _texto_celda(dibujo, (limites[indice][0], y, limites[indice][1], y + alto_encabezado),
                         str(titulo_col), negrita, "centro", colores["encabezado_texto"])
        y += alto_encabezado

        for posicion, indice_fila in enumerate(indices):
            alto_f = alto_filas[indice_fila]
            if posicion % 2 == 1:
                dibujo.rectangle([0, y, ancho_total - 1, y + alto_f - 1], fill=colores["alternas"])
            fila = filas[indice_fila]
            for columna, valor in enumerate(fila):
                lineas = lineas_filas[indice_fila] if columna == indice_texto else formatear(valor, tipos[columna])
                _texto_celda(dibujo, (limites[columna][0], y, limites[columna][1], y + alto_f),
                             lineas, fuente, ALINEACION.get(tipos[columna], "izquierda"), "#000000")
            dibujo.line([0, y + alto_f, ancho_total, y + alto_f], fill=colores["borde"], width=1)
            y += alto_f

        if ultima:
            dibujo.rectangle([0, y, ancho_total - 1, y + alto_fila - 1], fill=colores["total"])
            for columna, valor in enumerate(totales):
                _texto_celda(dibujo, (limites[columna][0], y, limites[columna][1], y + alto_fila),
                             formatear(valor, tipos[columna]), negrita,
                             ALINEACION.get(tipos[columna], "izquierda"), "#000000")
            y += alto_fila

        # las divisiones verticales arrancan debajo del título: así el título se ve
        # como una sola celda combinada, igual que en el Excel
        inicio_divisiones = alto_titulo if titulo else 0
        for x0, _ in limites[1:]:
            dibujo.line([x0, inicio_divisiones, x0, y], fill=colores["borde"], width=1)
        if titulo:
            dibujo.line([0, alto_titulo, ancho_total, alto_titulo], fill=colores["borde"], width=1)
        dibujo.rectangle([0, 0, ancho_total - 1, y - 1], outline=colores["borde"], width=2)

        paginas.append(PaginaTabla(imagen.crop((0, 0, ancho_total, y)), numero_pagina == 0))

    return paginas
