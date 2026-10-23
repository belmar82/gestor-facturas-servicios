"""Registro de módulos.

En el código fuente basta con dejar un archivo .py en esta carpeta con una clase que
herede de `ModuloProceso` para que la aplicación lo use: no hay que registrar nada.

Cuando la aplicación está empaquetada como ejecutable, los módulos van compilados
dentro del programa y no se pueden descubrir recorriendo la carpeta; por eso existe
`MODULOS_CONOCIDOS`, que es la lista de los módulos que se incluyen en el paquete.
Al crear un módulo nuevo hay que agregar su nombre a esa lista (una línea).
"""
import importlib
import pkgutil

from .base import ModuloProceso

MODULOS_CONOCIDOS = ("triple_a",)


def _nombres_de_modulos():
    nombres = []
    try:
        nombres = [informacion.name for informacion in pkgutil.iter_modules(__path__)]
    except Exception:
        nombres = []
    for nombre in MODULOS_CONOCIDOS:
        if nombre not in nombres:
            nombres.append(nombre)
    return [n for n in nombres if not n.startswith("_") and n != "base"]


def cargar_modulos():
    modulos = []
    for nombre in _nombres_de_modulos():
        try:
            paquete = importlib.import_module(f"{__name__}.{nombre}")
        except Exception as error:  # un módulo con error no debe tumbar la aplicación
            print(f"AVISO: no se pudo cargar el módulo {nombre}: {error}")
            continue
        for valor in vars(paquete).values():
            if isinstance(valor, type) and issubclass(valor, ModuloProceso) and valor is not ModuloProceso:
                try:
                    modulos.append(valor())
                except Exception as error:
                    print(f"AVISO: no se pudo iniciar {valor.__name__}: {error}")
    return modulos


__all__ = ["ModuloProceso", "cargar_modulos", "MODULOS_CONOCIDOS"]
