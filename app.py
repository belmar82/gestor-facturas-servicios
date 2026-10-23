"""Gestor de Facturas - punto de entrada.

Uso con ventana:      python app.py
Uso por línea de comandos:
    python app.py --carpeta "D:\\...\\08-AGOSTO"
    python app.py --carpeta "..." --mes 9 --anio 2026 --salida "D:\\salidas"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo import configuracion as conf  # noqa: E402
from nucleo import proceso  # noqa: E402


def _mostrar(mensaje, nivel):
    print(f"[{nivel}] {mensaje}")


def main():
    analizador = argparse.ArgumentParser(
        description="Genera el informe (Excel) y el oficio de remisión (Word) a partir de las facturas PDF.")
    analizador.add_argument("--carpeta", help="carpeta con las facturas PDF del mes")
    analizador.add_argument("--diccionario", help="diccionario de pólizas (.xlsx)")
    analizador.add_argument("--salida", help="carpeta donde dejar el Excel y el oficio")
    analizador.add_argument("--mes", type=int, help="mes facturado (1-12)")
    analizador.add_argument("--anio", help="año facturado")
    analizador.add_argument("--solo-excel", action="store_true", help="no generar el oficio")
    analizador.add_argument("--solo-word", action="store_true", help="no generar el Excel")
    argumentos = analizador.parse_args()

    if not argumentos.carpeta:
        from nucleo import interfaz
        interfaz.iniciar()
        return 0

    resumen = proceso.procesar(
        argumentos.carpeta,
        archivo_diccionario=argumentos.diccionario,
        carpeta_salida=argumentos.salida,
        mostrar=_mostrar,
        mes_forzado=argumentos.mes,
        anio_forzado=argumentos.anio,
        generar_excel=not argumentos.solo_word,
        generar_word=not argumentos.solo_excel,
    )

    print("\n=== RESUMEN ===")
    print(f"Periodo           : {resumen['mes']} {resumen['anio']}")
    print(f"Documentos leídos : {resumen['procesados']} de {resumen['documentos']}")
    print(f"Filas del informe : {resumen['filas_informe']}")
    print(f"Total a pagar     : {resumen['total_texto']}")
    print(f"Excel             : {resumen['salidas']['excel']}")
    print(f"Oficio            : {resumen['salidas']['word']}")
    if resumen["incidencias"]:
        print(f"Incidencias       : {len(resumen['incidencias'])}")
        for incidencia in resumen["incidencias"]:
            print(f"   - {incidencia}")
    print(f"Registro          : {resumen['registro']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
