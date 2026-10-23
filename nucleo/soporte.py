"""Registro de la corrida y respaldos de los archivos que se van a reemplazar."""
import os
import shutil
from datetime import datetime


class Registro:
    """Guarda el detalle de la corrida en un archivo y lo muestra en pantalla."""

    def __init__(self, carpeta, mostrar=None):
        self.carpeta = carpeta
        self.mostrar = mostrar
        self.lineas = []
        os.makedirs(carpeta, exist_ok=True)
        self.ruta = os.path.join(carpeta, "corrida_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")

    def _anotar(self, nivel, mensaje):
        linea = f"[{datetime.now().strftime('%H:%M:%S')}] {nivel}: {mensaje}"
        self.lineas.append(linea)
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(linea + "\n")
        if self.mostrar:
            self.mostrar(mensaje, nivel)

    def info(self, mensaje):
        self._anotar("INFO", mensaje)

    def aviso(self, mensaje):
        self._anotar("AVISO", mensaje)

    def error(self, mensaje):
        self._anotar("ERROR", mensaje)

    def titulo(self, mensaje):
        self._anotar("PASO", mensaje)


def respaldar(archivo, carpeta_respaldos):
    """Copia el archivo a la carpeta de respaldos antes de sobrescribirlo."""
    if not archivo or not os.path.exists(archivo):
        return None
    os.makedirs(carpeta_respaldos, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre, extension = os.path.splitext(os.path.basename(archivo))
    destino = os.path.join(carpeta_respaldos, f"{nombre} ({marca}){extension}")
    shutil.copy2(archivo, destino)
    return destino
