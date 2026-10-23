"""Orquesta una corrida completa: leer los PDF, validar, escribir el Excel y el oficio."""
import os
import tempfile
import time
from datetime import datetime

from modulos import cargar_modulos

from . import configuracion as conf
from . import diccionario as diccmod
from . import ensamblado, escritor_excel, oficio_word, soporte
from .lector_pdf import formatear_moneda


def _fecha_para_oficio(cfg):
    valor = str(cfg["oficio"].get("fecha") or "auto").strip()
    if valor.lower() != "auto":
        return valor
    hoy = datetime.now()
    return f"{conf.MESES_MIN.get(hoy.month, '')} {hoy.day} de {hoy.year}"


def _contexto(mes, anio, valor, cfg):
    return {
        "MES_TITULO": conf.nombre_mes(mes or 0) or "",
        "MES_MIN": conf.MESES_MIN.get(int(mes or 0), ""),
        "ANIO": str(anio or ""),
        "VALOR": "$" + formatear_moneda(valor or 0),
        "VALOR_NUMERO": str(int(valor or 0)),
        "FECHA": _fecha_para_oficio(cfg),
    }


def _mes_de_carpeta(nombre):
    """'08-AGOSTO' -> 8 ; 'AGOSTO 2026' -> 8."""
    import re
    limpio = str(nombre).upper()
    hallado = re.match(r"\s*(\d{1,2})\b", limpio)
    if hallado and 1 <= int(hallado.group(1)) <= 12:
        return int(hallado.group(1))
    for numero, titulo in conf.MESES.items():
        if titulo.upper() in limpio:
            return numero
    return None


def _anio_de_carpeta(nombre):
    import re
    hallado = re.search(r"(20\d{2})", str(nombre))
    return hallado.group(1) if hallado else None


def _guardar_con_reintento(accion, ruta, intentos=3, espera=2.0):
    """Guarda el archivo; si está abierto en Office, avisa con claridad."""
    for numero in range(1, intentos + 1):
        try:
            return accion()
        except PermissionError:
            if numero == intentos:
                raise PermissionError(
                    f"No se pudo escribir «{os.path.basename(ruta)}» porque está abierto en Excel o Word. "
                    "Ciérralo e inténtalo de nuevo."
                )
            time.sleep(espera)



def _facturas_para_pdf(registros, dicc):
    """Facturas en el orden del informe (orden del diccionario), para el PDF anexo."""
    por_poliza = {}
    for datos in registros:
        poliza = datos.get("poliza")
        if poliza is not None:
            por_poliza.setdefault(poliza, datos)
    facturas = []
    for poliza in dicc["orden"]:
        datos = por_poliza.get(poliza)
        if not datos:
            continue
        ficha = dicc["por_poliza"].get(poliza) or {}
        facturas.append({
            "ruta": datos.get("ruta"),
            "poliza": poliza,
            "ie": ficha.get("ie") or datos.get("cliente") or "",
            "factura": datos.get("factura"),
        })
    return facturas


def procesar(carpeta_pdf, cfg=None, archivo_diccionario=None, carpeta_salida=None,
             mostrar=None, mes_forzado=None, anio_forzado=None, generar_excel=True, generar_word=True):
    cfg = cfg or conf.cargar()
    registro = soporte.Registro(conf.ruta(cfg["general"]["carpeta_registros"]))
    if mostrar:
        registro.mostrar = mostrar
    anota = registro

    carpeta_pdf = os.path.abspath(carpeta_pdf or "")
    if not os.path.isdir(carpeta_pdf):
        raise NotADirectoryError(f"La carpeta de facturas no existe: {carpeta_pdf}")

    documentos = sorted(f for f in os.listdir(carpeta_pdf) if f.lower().endswith(".pdf"))
    if not documentos:
        raise FileNotFoundError(f"No hay archivos PDF en {carpeta_pdf}")

    anota.titulo(f"Carpeta: {carpeta_pdf} ({len(documentos)} archivos PDF)")

    modulos = cargar_modulos()
    if not modulos:
        raise RuntimeError("No hay módulos de procesamiento instalados.")
    anota.info("Módulos disponibles: " + ", ".join(m.nombre for m in modulos))

    registros, sin_reconocer, incidencias = [], [], []
    for nombre in documentos:
        ruta = os.path.join(carpeta_pdf, nombre)
        try:
            from .lector_pdf import leer_texto
            texto = leer_texto(ruta)
        except Exception as error:
            anota.error(f"{nombre}: no se pudo leer ({error})")
            continue
        modulo = next((m for m in modulos if m.reconoce(texto)), None)
        if modulo is None:
            sin_reconocer.append(nombre)
            anota.aviso(f"{nombre}: ningún módulo reconoce este documento.")
            continue
        datos = modulo.extraer(ruta)
        datos["modulo"] = modulo.id
        datos["ruta"] = ruta
        datos["avisos"] = modulo.validar(datos)
        for aviso in datos["avisos"]:
            incidencias.append(f"{nombre}: {aviso}")
            anota.aviso(f"{nombre}: {aviso}")
        registros.append(datos)

    if not registros:
        raise RuntimeError("No se pudo extraer información de ningún documento.")

    # ---------------------------------------------------------------- periodo
    conteo = {}
    for datos in registros:
        mes, anio = datos.get("periodo") or (None, None)
        if mes:
            conteo[(int(mes), str(anio))] = conteo.get((int(mes), str(anio)), 0) + 1
    mes, anio = (max(conteo, key=conteo.get) if conteo else (None, None))
    if mes_forzado:
        mes = int(mes_forzado)
    if anio_forzado:
        anio = str(anio_forzado)
    if not mes:
        mes = _mes_de_carpeta(os.path.basename(carpeta_pdf))
    if not anio:
        anio = _anio_de_carpeta(os.path.basename(carpeta_pdf)) or str(datetime.now().year)
    if not mes:
        raise ValueError("No se pudo determinar el mes facturado; indícalo manualmente.")
    anota.info(f"Periodo facturado detectado: {conf.nombre_mes(mes)} {anio}")

    mes_carpeta = _mes_de_carpeta(os.path.basename(carpeta_pdf))
    if mes_carpeta and int(mes_carpeta) != int(mes):
        anota.aviso(f"El mes de la carpeta ({conf.nombre_mes(mes_carpeta)}) no coincide con el de las "
                    f"facturas ({conf.nombre_mes(mes)}); revisa los archivos.")

    # ---------------------------------------------------------------- diccionario
    ruta_dicc = archivo_diccionario or conf.ruta(cfg["general"]["diccionario"])
    dicc = diccmod.leer(ruta_dicc)
    anota.info(f"Diccionario: {os.path.basename(ruta_dicc)} ({len(dicc['por_poliza'])} pólizas)")

    faltantes = [p for p in dicc["orden"]
                 if all(r.get("poliza") != p for r in registros)]
    if faltantes:
        anota.aviso(f"Pólizas del diccionario sin factura en este periodo ({len(faltantes)}): "
                    + ", ".join(str(p) for p in faltantes))
    ajenas = [r["poliza"] for r in registros if r.get("poliza") not in dicc["por_poliza"]]
    if ajenas:
        anota.aviso(f"Facturas cuya póliza no está en el diccionario ({len(ajenas)}): "
                    + ", ".join(str(p) for p in ajenas)
                    + f" -> no entran en la tabla ni en el detalle; quedan en la hoja "
                      f"'{cfg['informe']['hoja_sin_coincidencia']}' para revisarlas a mano.")

    # ---------------------------------------------------------------- tablas
    principal = None
    cuenta_modulos = {}
    for datos in registros:
        cuenta_modulos[datos["modulo"]] = cuenta_modulos.get(datos["modulo"], 0) + 1
    id_principal = max(cuenta_modulos, key=cuenta_modulos.get)
    principal = next(m for m in modulos if m.id == id_principal)
    propios = [r for r in registros if r["modulo"] == id_principal]
    if len(cuenta_modulos) > 1:
        anota.aviso("Se procesaron documentos de varios módulos; la tabla del informe se construye con "
                    f"«{principal.nombre}».")

    informe_previo = principal.construir_informe(propios, dicc, {"MES_TITULO": conf.nombre_mes(mes),
                                                                 "MES_MIN": conf.MESES_MIN.get(int(mes), ""),
                                                                 "ANIO": str(anio)}, cfg)
    valor_total = informe_previo["totales"][-1]
    contexto = _contexto(mes, anio, valor_total, cfg)
    informe = principal.construir_informe(propios, dicc, contexto, cfg)
    detalle = principal.construir_detalle(propios, dicc, contexto, cfg)
    sin_coincidencia = principal.construir_sin_coincidencia(propios, dicc, contexto, cfg)

    anota.info(f"Facturas incluidas en la tabla: {len(informe['filas'])}")
    anota.info("Total Valor a Pagar: " + "$" + formatear_moneda(valor_total))
    if informe.get("total_deuda_en_cero"):
        anota.info("Columna 'Total deuda' en 0: desde "
                   + str(cfg["general"].get("total_deuda_desde") or "")
                   + " las facturas estimadas se registran para pago igual que las reales.")

    # ---------------------------------------------------------------- salidas
    carpeta_salida = carpeta_salida or conf.ruta(cfg["general"]["carpeta_salida"])
    os.makedirs(carpeta_salida, exist_ok=True)
    respaldos = conf.ruta(cfg["general"]["carpeta_respaldos"])

    salidas = {"excel": None, "word": None, "pdf": None, "imagenes": []}

    if generar_excel:
        ruta_excel = os.path.join(carpeta_salida, str(cfg["informe"]["nombre_archivo"]).format_map(contexto))
        respaldo = soporte.respaldar(ruta_excel, respaldos)
        if respaldo:
            anota.info(f"Respaldo del Excel anterior: {os.path.basename(respaldo)}")
        _guardar_con_reintento(
            lambda: escritor_excel.escribir(ruta_excel, detalle, informe, sin_coincidencia, cfg),
            ruta_excel)
        salidas["excel"] = ruta_excel
        anota.info(f"Excel generado: {ruta_excel}")

    if generar_word:
        plantilla = conf.ruta(cfg["oficio"]["plantilla"])
        ruta_word = os.path.join(carpeta_salida, str(cfg["oficio"]["nombre_salida"]).format_map(contexto))
        respaldo = soporte.respaldar(ruta_word, respaldos)
        if respaldo:
            anota.info(f"Respaldo del oficio anterior: {os.path.basename(respaldo)}")
        carpeta_imagenes = os.path.join(carpeta_salida, "imagenes")
        resultado = _guardar_con_reintento(
            lambda: oficio_word.generar(plantilla, ruta_word, cfg, contexto, informe, carpeta_imagenes),
            ruta_word)
        salidas["word"] = ruta_word
        salidas["imagenes"] = resultado["imagenes"]
        salidas["paginas_tabla"] = resultado["paginas_tabla"]
        anota.info(f"Oficio generado: {ruta_word} (tabla en {resultado['paginas_tabla']} página(s))")
        anota.info(f"El valor del párrafo coincide con el total de la tabla: {contexto['VALOR']}")

        # PDF del oficio seguido de la primera página de cada factura del periodo
        if cfg["oficio"].get("pdf_con_facturas", True):
            temporal = os.path.join(tempfile.gettempdir(), f"oficio {int(time.time())}.pdf")
            try:
                nombre_pdf = str(cfg["oficio"].get("nombre_pdf") or "").format_map(contexto)
                ruta_pdf = os.path.join(carpeta_salida, nombre_pdf)
                respaldo = soporte.respaldar(ruta_pdf, respaldos)
                if respaldo:
                    anota.info(f"Respaldo del PDF anterior: {os.path.basename(respaldo)}")
                oficio_word.a_pdf(ruta_word, temporal)
                resultado_pdf = ensamblado.unir(
                    temporal, _facturas_para_pdf(propios, dicc), ruta_pdf,
                    titulo=f"Oficio de remisión {contexto['MES_TITULO']} {contexto['ANIO']}",
                    avisar=anota.aviso)
                salidas["pdf"] = ruta_pdf
                anota.info(f"PDF con el oficio y las facturas: {ruta_pdf} "
                           f"({resultado_pdf['paginas']} páginas, {resultado_pdf['facturas']} facturas)")
            except Exception as error:
                anota.aviso(f"No se pudo generar el PDF con las facturas: {error}")
            finally:
                if os.path.exists(temporal):
                    try:
                        os.remove(temporal)
                    except OSError:
                        pass

    resumen = {
        "carpeta": carpeta_pdf,
        "documentos": len(documentos),
        "procesados": len(registros),
        "sin_reconocer": sin_reconocer,
        "mes": conf.nombre_mes(mes),
        "anio": str(anio),
        "filas_informe": len(informe["filas"]),
        "total": int(valor_total or 0),
        "total_texto": contexto["VALOR"],
        "incidencias": incidencias,
        "salidas": salidas,
        "registro": registro.ruta,
    }
    anota.titulo("Corrida terminada.")
    return resumen
