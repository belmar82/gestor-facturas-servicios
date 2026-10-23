"""Ventana de la aplicación: se elige la carpeta de facturas y se genera todo.

El trabajo corre en un hilo aparte y se comunica con la ventana por una única cola de
mensajes.  Un solo lector atiende esa cola: así el aviso de fin siempre llega y el botón
vuelve a quedar disponible para generar otro informe.
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import configuracion as conf
from . import proceso

AZUL = "#1F4E79"
VERDE = "#1E7B34"
ROJO = "#B00020"


class Aplicacion:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cfg = conf.cargar()
        self.cola = queue.Queue()
        self.trabajando = False
        self.resumen = None
        self.error = None

        raiz.title(f"Gestor de Facturas v{conf.VERSION} - Secretaría de Educación de Soledad")
        raiz.geometry("900x660")
        raiz.minsize(760, 560)

        contenedor = ttk.Frame(raiz, padding=12)
        contenedor.pack(fill="both", expand=True)

        ttk.Label(contenedor, text="Gestor de facturas de servicios públicos",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        padre = os.path.dirname(conf.BASE)
        self.var_carpeta = tk.StringVar(value=self._carpeta_mes(padre))
        self.var_dicc = tk.StringVar(value=conf.ruta(self.cfg["general"]["diccionario"]))
        self.var_salida = tk.StringVar(value=conf.ruta(self.cfg["general"]["carpeta_salida"]))
        self.var_mes = tk.StringVar(value="")
        self.var_anio = tk.StringVar(value="")
        self.var_auto = tk.BooleanVar(value=True)

        self._fila(contenedor, 1, "Carpeta de facturas PDF:", self.var_carpeta, self._elegir_carpeta)
        self._fila(contenedor, 2, "Diccionario de pólizas:", self.var_dicc, self._elegir_diccionario)
        self._fila(contenedor, 3, "Carpeta de salida:", self.var_salida, self._elegir_salida)

        marco = ttk.LabelFrame(contenedor, text="Periodo facturado", padding=8)
        marco.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Checkbutton(marco, text="Detectar automáticamente desde las facturas",
                        variable=self.var_auto, command=self._cambiar_auto).grid(row=0, column=0, sticky="w")
        ttk.Label(marco, text="Mes:").grid(row=0, column=1, padx=(16, 4))
        self.combo_mes = ttk.Combobox(marco, textvariable=self.var_mes, width=14, state="disabled",
                                      values=[""] + [conf.MESES[i] for i in range(1, 13)])
        self.combo_mes.grid(row=0, column=2)
        ttk.Label(marco, text="Año:").grid(row=0, column=3, padx=(16, 4))
        self.entrada_anio = ttk.Entry(marco, textvariable=self.var_anio, width=8, state="disabled")
        self.entrada_anio.grid(row=0, column=4)

        botones = ttk.Frame(contenedor)
        botones.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        self.boton = ttk.Button(botones, text="Generar informe y oficio", command=self._generar)
        self.boton.pack(side="left")
        ttk.Button(botones, text="Abrir carpeta de salidas", command=self._abrir_salidas).pack(side="left", padx=8)
        self.barra = ttk.Progressbar(botones, mode="indeterminate", length=220)
        self.barra.pack(side="right")

        self.estado = ttk.Label(contenedor, text="Listo. Elige la carpeta del mes y pulsa «Generar».",
                                foreground=AZUL, font=("Segoe UI", 9, "bold"))
        self.estado.grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.texto = tk.Text(contenedor, height=18, wrap="word", font=("Consolas", 9))
        self.texto.grid(row=7, column=0, columnspan=3, sticky="nsew")
        contenedor.rowconfigure(7, weight=1)
        contenedor.columnconfigure(1, weight=1)

        self._escribir("Listo. Elige la carpeta del mes (por ejemplo 08-AGOSTO) y pulsa «Generar».", "PASO")
        self._bombear()

    # ------------------------------------------------------------------ ayudas
    @staticmethod
    def _carpeta_mes(padre):
        try:
            candidatas = [d for d in os.listdir(padre)
                          if os.path.isdir(os.path.join(padre, d)) and d[:2].isdigit()]
            if candidatas:
                return os.path.join(padre, sorted(candidatas)[-1])
        except Exception:
            pass
        return padre

    def _fila(self, contenedor, numero, etiqueta, variable, accion):
        ttk.Label(contenedor, text=etiqueta).grid(row=numero, column=0, sticky="w", pady=3)
        ttk.Entry(contenedor, textvariable=variable).grid(row=numero, column=1, sticky="ew", padx=6, pady=3)
        ttk.Button(contenedor, text="Examinar...", command=accion).grid(row=numero, column=2, pady=3)

    def _cambiar_auto(self):
        estado = "disabled" if self.var_auto.get() else "normal"
        self.combo_mes.configure(state=estado)
        self.entrada_anio.configure(state=estado)

    def _elegir_carpeta(self):
        elegida = filedialog.askdirectory(title="Carpeta con las facturas PDF")
        if elegida:
            self.var_carpeta.set(elegida)

    def _elegir_diccionario(self):
        elegido = filedialog.askopenfilename(title="Diccionario de pólizas",
                                             filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")])
        if elegido:
            self.var_dicc.set(elegido)

    def _elegir_salida(self):
        elegida = filedialog.askdirectory(title="Carpeta de salida")
        if elegida:
            self.var_salida.set(elegida)

    def _abrir_salidas(self):
        carpeta = self.var_salida.get()
        if os.path.isdir(carpeta):
            os.startfile(carpeta)
        else:
            messagebox.showinfo("Gestor de facturas", "La carpeta de salida todavía no existe.")

    def _escribir(self, mensaje, nivel="INFO"):
        self.texto.insert("end", f"[{nivel}] {mensaje}\n")
        self.texto.see("end")

    def _mostrar(self, mensaje, nivel):
        """Lo llama el hilo de trabajo: solo deja el mensaje en la cola."""
        self.cola.put((mensaje, nivel))

    # ------------------------------------------------------------------ cola
    def _bombear(self):
        """Único lector de la cola: mensajes del proceso y aviso de fin."""
        try:
            while True:
                mensaje, nivel = self.cola.get_nowait()
                if mensaje == "__FIN__":
                    self._terminar()
                else:
                    self._escribir(mensaje, nivel)
        except queue.Empty:
            pass
        self.raiz.after(120, self._bombear)

    # ------------------------------------------------------------------ proceso
    def _generar(self):
        if self.trabajando:
            return
        carpeta = self.var_carpeta.get()
        if not os.path.isdir(carpeta):
            messagebox.showerror("Gestor de facturas", "La carpeta de facturas no existe.")
            return
        dicc = self.var_dicc.get()
        if not os.path.exists(dicc):
            messagebox.showerror("Gestor de facturas", "No se encuentra el diccionario de pólizas.")
            return

        mes = None
        if not self.var_auto.get():
            nombre = self.var_mes.get().strip()
            mes = conf.numero_mes(nombre) if nombre else None
            if not mes:
                messagebox.showerror("Gestor de facturas", "Elige un mes válido.")
                return

        self.resumen, self.error = None, None
        self.trabajando = True
        self.boton.configure(state="disabled", text="Generando...")
        self.estado.configure(text="Generando... no cierres el Excel ni el Word.", foreground=AZUL)
        self.barra.configure(mode="indeterminate")
        self.barra.start(12)
        self.texto.delete("1.0", "end")
        self._escribir("Procesando las facturas...", "PASO")

        # los valores de la ventana se leen aquí (hilo principal) y se pasan al hilo
        salida = self.var_salida.get() or None
        anio = self.var_anio.get().strip() or None

        threading.Thread(target=self._correr, args=(carpeta, dicc, mes, salida, anio),
                         daemon=True).start()

    def _correr(self, carpeta, dicc, mes, salida, anio):
        try:
            self.resumen = proceso.procesar(
                carpeta,
                cfg=self.cfg,
                archivo_diccionario=dicc,
                carpeta_salida=salida,
                mostrar=self._mostrar,
                mes_forzado=mes,
                anio_forzado=anio,
            )
            self.cola.put((f"Listo. Total Valor a Pagar: {self.resumen['total_texto']}", "FIN"))
            self.cola.put((f"Excel: {self.resumen['salidas']['excel'] or '(no generado)'}", "FIN"))
            self.cola.put((f"Oficio: {self.resumen['salidas']['word'] or '(no generado)'}", "FIN"))
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            self.cola.put((self.error, "ERROR"))
        finally:
            self.cola.put(("__FIN__", "CONTROL"))

    def _terminar(self):
        """Devuelve la ventana a su estado normal para poder generar otro informe."""
        self.trabajando = False
        self.boton.configure(state="normal", text="Generar informe y oficio")
        # la barra vuelve a quedar vacía (si no, parece que el proceso sigue)
        self.barra.stop()
        self.barra.configure(mode="determinate", value=0)
        if self.error:
            self.estado.configure(text="Terminó con error. Revisa el mensaje en el registro.", foreground=ROJO)
            return
        if not self.resumen:
            self.estado.configure(text="Terminó sin resultados. Revisa el registro.", foreground=ROJO)
            return
        avisos = len(self.resumen.get("incidencias") or [])
        texto = (f"Terminado: {self.resumen['filas_informe']} facturas · "
                 f"total {self.resumen['total_texto']}")
        if avisos:
            texto += f" · {avisos} aviso(s) por revisar"
        texto += "   —   Ya puedes generar otro informe."
        self.estado.configure(text=texto, foreground=VERDE)


def iniciar():
    raiz = tk.Tk()
    Aplicacion(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    iniciar()
