"""Une el oficio en PDF con la primera página de cada factura del periodo.

El resultado es un solo archivo: primero el oficio (con la tabla) y enseguida la
primera cara de cada factura, en el mismo orden de la tabla del informe.
"""
import os

from pypdf import PdfReader, PdfWriter

AUTOR = "Gestor de Facturas"


def _etiqueta(datos):
    """Texto del marcador de cada factura dentro del PDF."""
    poliza = datos.get("poliza")
    institucion = datos.get("ie") or datos.get("nombre") or ""
    factura = datos.get("factura") or ""
    partes = []
    if poliza:
        partes.append(f"Póliza {poliza}")
    if institucion:
        partes.append(str(institucion))
    if factura:
        partes.append(f"factura {factura}")
    return " - ".join(partes) if partes else os.path.basename(str(datos.get("ruta") or "factura"))


def unir(oficio_pdf, facturas, salida, titulo=None, avisar=None):
    """Crea `salida` con el oficio seguido de la primera página de cada factura.

    `facturas` es una lista de diccionarios con al menos la clave `ruta`.
    Devuelve {'paginas': n, 'facturas': n, 'omitidas': [rutas]}.
    """
    avisar = avisar or (lambda mensaje: None)
    if not os.path.exists(oficio_pdf):
        raise FileNotFoundError(f"No se encontró el oficio en PDF: {oficio_pdf}")

    escritor = PdfWriter()
    for pagina in PdfReader(oficio_pdf).pages:
        escritor.add_page(pagina)

    agregadas, omitidas = 0, []
    for datos in facturas:
        ruta = datos.get("ruta")
        if not ruta or not os.path.exists(ruta):
            omitidas.append(ruta or "")
            avisar(f"{_etiqueta(datos)}: no se encontró el archivo de la factura; no se anexa.")
            continue
        try:
            lector = PdfReader(ruta)
            if not lector.pages:
                omitidas.append(ruta)
                continue
            escritor.add_page(lector.pages[0])
            agregadas += 1
            escritor.add_outline_item(_etiqueta(datos), len(escritor.pages) - 1)
        except Exception as error:  # una factura dañada no debe frenar el resto
            omitidas.append(ruta)
            avisar(f"{os.path.basename(ruta)}: no se pudo anexar ({error}).")

    escritor.add_metadata({
        "/Title": titulo or os.path.splitext(os.path.basename(salida))[0],
        "/Author": AUTOR,
        "/Creator": AUTOR,
        "/Subject": "Oficio de remisión con las facturas del periodo",
    })
    temporal = salida + ".parcial"
    with open(temporal, "wb") as archivo:
        escritor.write(archivo)
    os.replace(temporal, salida)
    return {"paginas": len(escritor.pages), "facturas": agregadas, "omitidas": omitidas}
