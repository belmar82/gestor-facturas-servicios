"""Contrato que debe cumplir cada módulo de procesamiento.

Agregar un facturador nuevo (AIR-E, Interaseo, otro municipio) o un generador
(conceptos de nómina, horas extras) consiste en crear un archivo en `modulos/` con una
clase que herede de `ModuloProceso`.  La aplicación lo descubre sola.
"""


class ModuloProceso:
    id = "base"
    nombre = "Módulo base"
    clave = "clave"          # campo con el que se identifica al cliente (póliza, NIC, contrato...)
    extensiones = (".pdf",)

    def reconoce(self, texto):
        """¿Este módulo sabe procesar un documento con este texto?"""
        return False

    def extraer(self, ruta):
        """Devuelve un diccionario con los campos del documento."""
        raise NotImplementedError

    def validar(self, datos):
        """Devuelve una lista de observaciones (vacía si todo cuadra)."""
        return []

    def construir_informe(self, registros, dicc, contexto, cfg):
        """Devuelve la tabla que se publica (encabezados, filas, tipos, totales)."""
        raise NotImplementedError

    def construir_detalle(self, registros, dicc, contexto, cfg):
        """Devuelve la tabla de respaldo con todo lo leído de los documentos."""
        raise NotImplementedError
