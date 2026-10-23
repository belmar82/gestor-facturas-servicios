"""Módulo Triple A S.A. E.S.P. (acueducto, alcantarillado y aseo).

Reglas ya validadas contra las facturas de julio, agosto y septiembre:
  * la póliza y el No. de factura se leen del texto;
  * el recuadro «SERVICIOS FACTURADOS» no trae etiquetas, así que sus valores se ubican
    por posición (columna derecha, de arriba hacia abajo):
      cupo, acueducto, alcantarillado, aseo, otros conceptos, otros cobros,
      total factura servicios del periodo, TOTAL DEUDA, total factura a pagar;
  * los totales «TOTAL ACUEDUCTO», etc. de la página de detalle sirven de contraste.

Tabla del informe (según lo indicado):
  Facturación    = acueducto + alcantarillado + aseo
  Valor a Pagar  = Facturación - Aseo - Intereses x Mora
"""
import os
import re

from nucleo import lector_pdf
from nucleo.configuracion import MESES, MESES_MIN, numero_mes
from nucleo.lector_pdf import (a_entero, buscar, formatear_moneda, leer_texto, normalizar,
                               sin_acentos, valores_derecha)

from .base import ModuloProceso

MESES_ABREV = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}


class TripleA(ModuloProceso):
    id = "triple_a"
    nombre = "Triple A - Acueducto, Alcantarillado y Aseo"
    clave = "poliza"

    # ---------------------------------------------------------------- reconocer
    def reconoce(self, texto):
        # Las etiquetas del recuadro van como imagen, así que se reconoce por los
        # totales del detalle, que sí vienen en el texto del PDF.
        plano = sin_acentos(normalizar(texto)).lower()
        return ("total acueducto" in plano and "total alcantarillado" in plano
                and "poliza" in plano)

    # ---------------------------------------------------------------- extraer
    def extraer(self, ruta):
        plano = normalizar(leer_texto(ruta))
        datos = {"archivo": os.path.basename(ruta), "ruta": ruta, "avisos": []}

        datos["poliza"] = a_entero(buscar([r"P[ÓO]LIZA\s*:?\s*(\d{4,8})"], plano))
        if datos["poliza"] is None:
            datos["poliza"] = a_entero(buscar([r"\$\s*(0\d{5,7})"], plano))
        datos["factura"] = a_entero(buscar([r"No\.?\s*de factura\s*(\d{5,12})"], plano))
        datos["cliente"] = (buscar([r"Nombre del cliente:\s*\n?\s*(.+)"], plano) or "").strip()
        datos["direccion"] = (buscar([r"Direcci[óo]n donde se presta el servicio:\s*\n?\s*(.+)"], plano) or "").strip()
        datos["consumo"] = a_entero(buscar([r"CONSUMO DEL MES:\s*([\d.,]+)", r"CONSUMO DEL MES:\s*\n?\s*([\d.,]+)"], plano))
        datos["metodo_consumo"] = (buscar(
            [r"CONSUMO REAL/ESTIMADO:\s*\n?\s*([A-Za-zÁÉÍÓÚáéíóúñ]+)"], plano) or "").strip().upper()

        # periodo facturado (mes y año del servicio: debe coincidir con la carpeta)
        datos["periodo"] = (None, None)
        datos["periodo_texto"] = ""
        hallado = re.search(r"(?:Periodo facturado|PERIODO)\s*([A-Za-zÁÉÍÓÚáéíóúñ]+)\s*-\s*(\d{2,4})",
                            plano, re.IGNORECASE)
        if hallado:
            mes = numero_mes(hallado.group(1))
            anio = hallado.group(2)
            datos["periodo"] = (mes, "20" + anio if len(anio) == 2 else anio)
            datos["periodo_texto"] = f"{MESES.get(mes, hallado.group(1))} {datos['periodo'][1]}".strip()

        # totales de la página de detalle (contraste)
        datos["acueducto_detalle"] = a_entero(buscar([r"TOTAL ACUEDUCTO\s*\$?\s*([\d.,]+)"], plano))
        datos["alcantarillado_detalle"] = a_entero(buscar([r"TOTAL ALCANTARILLADO\s*\$?\s*([\d.,]+)"], plano))
        datos["aseo_detalle"] = a_entero(buscar([r"TOTAL ASEO\s*\$?\s*([\d.,]+)"], plano))
        datos["otros_conceptos_detalle"] = a_entero(buscar([r"TOTAL OTROS CONCEPTOS\s*\$?\s*([\d.,]+)"], plano))
        datos["otros_cobros_detalle"] = a_entero(buscar([r"TOTAL OTROS COBROS\s*\$?\s*([\d.,]+)"], plano))
        datos["total_periodo_cupon"] = a_entero(
            buscar([r"Total factura del periodo[\s\S]{0,300}?TOTAL\s*\$?\s*([\d.,]+)"], plano)
        )

        # descripción de los rubros «otros conceptos» y «otros cobros» (viene en el detalle)
        lineas = plano.splitlines()
        datos["descripcion_otros_conceptos"] = self._descripcion_bloque(lineas, r"TOTAL OTROS CONCEPTOS")
        datos["descripcion_otros_cobros"] = self._descripcion_bloque(lineas, r"TOTAL OTROS COBROS")

        # recuadro SERVICIOS FACTURADOS: valores por posición
        valores = [a_entero(v) for v in valores_derecha(ruta)]
        if len(valores) >= 9:
            datos["acueducto"] = valores[1]
            datos["alcantarillado"] = valores[2]
            datos["aseo"] = valores[3]
            datos["otros_conceptos"] = valores[4]
            datos["otros_cobros"] = valores[5]
            datos["periodo_servicios"] = valores[6]
            datos["total_deuda"] = valores[7]          # campo TOTAL DEUDA del recuadro
            datos["total_a_pagar"] = valores[8]
        else:
            datos["avisos"].append("No se pudo leer el recuadro SERVICIOS FACTURADOS; se usan los totales de detalle.")
            datos["acueducto"] = datos["acueducto_detalle"]
            datos["alcantarillado"] = datos["alcantarillado_detalle"]
            datos["aseo"] = datos["aseo_detalle"]
            datos["otros_conceptos"] = datos["otros_conceptos_detalle"]
            datos["otros_cobros"] = datos["otros_cobros_detalle"]
            datos["periodo_servicios"] = None
            datos["total_deuda"] = None
            datos["total_a_pagar"] = None

        return datos

    # ---------------------------------------------------------------- validar
    def validar(self, datos):
        avisos = list(datos.get("avisos") or [])
        if datos.get("poliza") is None:
            avisos.append("No se pudo leer la póliza de la factura.")
        if datos.get("factura") is None:
            avisos.append("No se pudo leer el No. de factura.")

        for nombre, del_recuadro, del_detalle in (
            ("Acueducto", datos.get("acueducto"), datos.get("acueducto_detalle")),
            ("Alcantarillado", datos.get("alcantarillado"), datos.get("alcantarillado_detalle")),
            ("Aseo", datos.get("aseo"), datos.get("aseo_detalle")),
            ("Otros conceptos", datos.get("otros_conceptos"), datos.get("otros_conceptos_detalle")),
            ("Otros cobros", datos.get("otros_cobros"), datos.get("otros_cobros_detalle")),
        ):
            if del_recuadro is not None and del_detalle is not None and del_recuadro != del_detalle:
                avisos.append(f"{nombre}: el recuadro dice {del_recuadro} y el detalle dice {del_detalle}.")

        suma = sum(datos.get(campo) or 0 for campo in
                   ("acueducto", "alcantarillado", "aseo", "otros_conceptos"))
        if datos.get("periodo_servicios") is not None and suma != datos["periodo_servicios"]:
            avisos.append(f"La suma de conceptos ({suma}) no coincide con el total facturado del periodo "
                          f"({datos['periodo_servicios']}).")

        total = (datos.get("periodo_servicios") or 0) + (datos.get("otros_cobros") or 0)
        if datos.get("total_periodo_cupon") is not None and total != datos["total_periodo_cupon"]:
            avisos.append(f"El total del periodo ({total}) no coincide con el del cupón "
                          f"({datos['total_periodo_cupon']}).")

        if (datos.get("otros_conceptos") or 0) or (datos.get("otros_cobros") or 0):
            avisos.append("La factura trae OTROS CONCEPTOS u OTROS COBROS distintos de cero: "
                          "revisa si deben sumarse a la facturación.")

        # control de la columna 'Total factura a pagar' (conceptos + deuda anterior, sin otros cobros)
        calculado = self._total_factura_a_pagar(datos)
        if datos.get("total_a_pagar") is not None and calculado != datos["total_a_pagar"]:
            avisos.append("La suma de los conceptos y la deuda anterior, sin otros cobros ("
                          + formatear_moneda(calculado) + "), no coincide con el TOTAL FACTURA A PAGAR de la "
                          "factura (" + formatear_moneda(datos["total_a_pagar"]) + ").")
        return avisos

    # ---------------------------------------------------------------- apoyo
    @staticmethod
    def _descripcion_bloque(lineas, etiqueta):
        """Texto de las líneas de detalle que están justo antes del total indicado.

        Las facturas listan cada rubro en una línea («Seguro vida mapfre $19,292»,
        «Instalación medidor $95,521.00 60 ...») y cierran con «TOTAL OTROS ...».
        """
        patron = re.compile(r"^\s*" + etiqueta, re.IGNORECASE)
        for indice, linea in enumerate(lineas):
            if not patron.match(linea):
                continue
            textos, posicion = [], indice - 1
            while posicion >= 0:
                anterior = lineas[posicion].strip()
                if not anterior or "$" not in anterior or anterior.lower().startswith("descripci"):
                    break
                texto = re.split(r"\s*\$", anterior)[0].strip()
                if texto:
                    textos.insert(0, texto)
                posicion -= 1
            return " / ".join(textos)
        return ""

    @staticmethod
    def _facturacion(datos, cfg):
        """Facturación del mes = acueducto + alcantarillado + aseo + otros conceptos.

        Debe dar exactamente lo mismo que la fórmula de la hoja TABLA DE INFORME
        (=SUMA(DETALLE!G;DETALLE!H;DETALLE!I;DETALLE!J)).  Los «otros cobros» solo se
        suman si se activan en la configuración.
        """
        general = cfg["general"]
        valor = ((datos.get("acueducto") or 0) + (datos.get("alcantarillado") or 0)
                 + (datos.get("aseo") or 0))
        if general.get("incluir_otros_conceptos_en_facturacion", True):
            valor += datos.get("otros_conceptos") or 0
        if general.get("incluir_otros_cobros_en_facturacion", False):
            valor += datos.get("otros_cobros") or 0
        return valor

    def _ordenados(self, registros, dicc, cfg):
        por_poliza = {r["poliza"]: r for r in registros if r.get("poliza") is not None}
        lista, usadas = [], set()
        for poliza in dicc["orden"]:
            if poliza in por_poliza:
                lista.append(por_poliza[poliza])
                usadas.add(poliza)
        for registro in registros:
            if registro.get("poliza") not in usadas:
                lista.append(registro)
                usadas.add(registro.get("poliza"))
        return lista, por_poliza

    def _solo_diccionario(self, lista, dicc, incluir_sin_poliza):
        """Deja únicamente las facturas cuya póliza está en el diccionario.

        Las demás no se pierden: se publican en la hoja SIN COINCIDENCIA para
        revisarlas a mano antes de incluirlas.
        """
        if incluir_sin_poliza:
            return lista
        return [registro for registro in lista if registro.get("poliza") in dicc["por_poliza"]]

    # ---------------------------------------------------------------- informes
    @staticmethod
    def _aplica_deuda(cfg, contexto):
        """¿En este periodo la columna «Total deuda» lleva la deuda de las estimadas?

        La regla vigente es que desde `total_deuda_desde` (por ejemplo 2026-08) las facturas
        estimadas se pagan igual que las reales, así que la columna queda en 0.
        """
        corte = str(cfg["general"].get("total_deuda_desde") or "").strip()
        if not corte:
            return True
        try:
            anio_corte, mes_corte = corte.split("-")[:2]
            mes_actual = numero_mes(contexto.get("MES_TITULO")) or 0
            anio_actual = int(str(contexto.get("ANIO") or 0))
            return (anio_actual, int(mes_actual)) < (int(anio_corte), int(mes_corte))
        except Exception:
            return True

    def construir_informe(self, registros, dicc, contexto, cfg):
        incluir_sin_poliza = bool(cfg["general"].get("incluir_facturas_sin_poliza", True))
        aplicar_deuda = self._aplica_deuda(cfg, contexto)
        mes = contexto["MES_TITULO"]

        encabezados = ["Item", "Póliza", "Institución Educativa", f"Consumo {mes}", "Real/Estimado",
                       f"Facturación {mes}", "Aseo", "Intereses x Mora", "Total deuda", "Valor a Pagar"]
        tipos = ["item", "poliza", "texto", "entero", "centrado",
                 "moneda", "moneda", "moneda", "moneda", "moneda"]

        lista, _ = self._ordenados(registros, dicc, cfg)
        lista = self._solo_diccionario(lista, dicc, incluir_sin_poliza)
        filas = []
        suma_consumo = suma_facturacion = suma_aseo = suma_intereses = suma_deuda = suma_valor = 0
        for numero, registro in enumerate(lista, start=1):
            ficha = dicc["por_poliza"].get(registro.get("poliza"), {})
            institucion = ficha.get("ie") or registro.get("cliente") or ""
            facturacion = self._facturacion(registro, cfg)
            aseo = registro.get("aseo") or 0
            intereses = 0                      # no se conoce el origen del dato: queda en cero
            consumo = registro.get("consumo") or 0
            metodo = registro.get("metodo_consumo") or ""
            # la deuda solo se trae si el periodo es anterior al corte y el consumo es estimado
            deuda = ((registro.get("total_deuda") or 0)
                     if aplicar_deuda and metodo.upper() == "ESTIMADO" else 0)
            valor = facturacion + deuda - aseo - intereses
            filas.append([numero, registro.get("poliza"), institucion, consumo, metodo,
                          facturacion, aseo, intereses, deuda, valor])
            suma_consumo += consumo
            suma_facturacion += facturacion
            suma_aseo += aseo
            suma_intereses += intereses
            suma_deuda += deuda or 0
            suma_valor += valor
        # en la fila de totales solo va "Total" en la columna de la póliza;
        # la celda de Institución Educativa debe quedar vacía
        totales = ["", "Total", "", suma_consumo, "",
                   suma_facturacion, suma_aseo, suma_intereses, suma_deuda, suma_valor]

        titulo = str(cfg["informe"]["titulo"]).format_map(contexto)
        return {"titulo": titulo, "encabezados": encabezados, "filas": filas,
                "tipos": tipos, "totales": totales,
                "total_deuda_en_cero": not aplicar_deuda}

    # campos que se suman para reconstruir el «Total factura a pagar» de la factura
    CAMPOS_PAGAR = ("acueducto", "alcantarillado", "aseo", "otros_conceptos", "otros_cobros", "total_deuda")
    CAMPOS_RESTAN = ("otros_cobros",)      # por ahora se restan (seguros y similares)

    @classmethod
    def _total_factura_a_pagar(cls, registro):
        # igual que la fórmula de Excel: =SUMA(acueducto:total deuda) - otros cobros
        total = sum(registro.get(campo) or 0 for campo in cls.CAMPOS_PAGAR)
        return total - sum(registro.get(campo) or 0 for campo in cls.CAMPOS_RESTAN)

    @classmethod
    def _indicador_pagar(cls, registro):
        """Compara la suma calculada con el TOTAL FACTURA A PAGAR del PDF."""
        calculado = cls._total_factura_a_pagar(registro)
        factura = registro.get("total_a_pagar")
        if factura is None:
            return "SIN DATO EN LA FACTURA"
        if calculado == factura:
            return "COINCIDE"
        diferencia = calculado - factura
        return ("NO COINCIDE (factura " + formatear_moneda(factura)
                + "; diferencia " + formatear_moneda(diferencia) + ")")

    @classmethod
    def _observacion(cls, registro):
        """Explica a qué corresponden los valores de «otros conceptos» y «otros cobros»."""
        partes = []
        conceptos = registro.get("otros_conceptos") or 0
        cobros = registro.get("otros_cobros") or 0
        if conceptos:
            detalle = registro.get("descripcion_otros_conceptos") or "sin descripción en la factura"
            partes.append("Otros conceptos: " + detalle + " (" + formatear_moneda(conceptos) + ")")
        if cobros:
            detalle = registro.get("descripcion_otros_cobros") or "sin descripción en la factura"
            partes.append("Otros cobros: " + detalle + " (" + formatear_moneda(cobros)
                          + "); se resta del total factura a pagar")
        return " | ".join(partes)

    def construir_detalle(self, registros, dicc, contexto, cfg):
        encabezados = ["Item", "Póliza", "Institución Educativa", "No. de factura", "CONSUMO DEL MES",
                       "CONSUMO REAL/ESTIMADO", "Servicio de Acueducto", "Servicio de Alcantarillado",
                       "Servicio de Aseo", "Servicio Otros Conceptos", "Otros Cobros", "Total deuda",
                       "Total factura a pagar", "Coincide con la factura", "Observación"]
        tipos = ["item", "poliza", "texto", "factura", "entero", "centrado",
                 "moneda", "moneda", "moneda", "moneda", "moneda", "moneda",
                 "moneda", "centrado", "texto"]

        lista, _ = self._ordenados(registros, dicc, cfg)
        lista = self._solo_diccionario(lista, dicc, bool(cfg["general"].get("incluir_facturas_sin_poliza", True)))
        filas = []
        for numero, registro in enumerate(lista, start=1):
            ficha = dicc["por_poliza"].get(registro.get("poliza"), {})
            filas.append([
                numero,
                registro.get("poliza"),
                ficha.get("ie") or registro.get("cliente") or "",
                registro.get("factura"),
                registro.get("consumo") or 0,
                registro.get("metodo_consumo") or "",
                registro.get("acueducto") or 0,
                registro.get("alcantarillado") or 0,
                registro.get("aseo") or 0,
                registro.get("otros_conceptos") or 0,
                registro.get("otros_cobros") or 0,
                registro.get("total_deuda") or 0,
                self._total_factura_a_pagar(registro),
                self._indicador_pagar(registro),
                self._observacion(registro),
            ])
        return {"encabezados": encabezados, "filas": filas, "tipos": tipos}

    def construir_sin_coincidencia(self, registros, dicc, contexto, cfg):
        encabezados = ["Póliza", "Nombre del cliente", "Dirección", "No. de factura", "CONSUMO DEL MES",
                       "CONSUMO REAL/ESTIMADO", "Servicio de Acueducto", "Servicio de Alcantarillado",
                       "Servicio de Aseo", "Servicio Otros Conceptos", "Otros Cobros", "Total deuda",
                       "Total factura a pagar", "Coincide con la factura", "Observación"]
        tipos = ["poliza", "texto", "texto", "factura", "entero", "centrado",
                 "moneda", "moneda", "moneda", "moneda", "moneda", "moneda",
                 "moneda", "centrado", "texto"]
        filas = []
        for registro in registros:
            if registro.get("poliza") in dicc["por_poliza"]:
                continue
            filas.append([
                registro.get("poliza"), registro.get("cliente") or "", registro.get("direccion") or "",
                registro.get("factura"), registro.get("consumo") or 0,
                registro.get("metodo_consumo") or "",
                registro.get("acueducto") or 0, registro.get("alcantarillado") or 0,
                registro.get("aseo") or 0, registro.get("otros_conceptos") or 0,
                registro.get("otros_cobros") or 0, registro.get("total_deuda") or 0,
                self._total_factura_a_pagar(registro),
                self._indicador_pagar(registro),
                self._observacion(registro),
            ])
        return {"encabezados": encabezados, "filas": filas, "tipos": tipos}
