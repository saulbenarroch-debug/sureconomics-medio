"""Pruebas de los frenos del paquete de datos.

No hay framework: se corre con `python pruebas_paquete.py` y se lee la salida,
igual que en los otros repos.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from motor.paquete import Cifra, Fuente, Paquete, formato_es, magnitud_es

fallos = 0
def caso(nombre, condicion, detalle=""):
    global fallos
    print(("  OK  " if condicion else "FALLA ") + nombre + ("" if condicion else f"  -> {detalle}"))
    if not condicion: fallos += 1

print("\n-- formato de numeros --")
caso("decimal con coma", formato_es(25.84) == "25,8", formato_es(25.84))
caso("miles con punto", formato_es(1234567, 0) == "1.234.567", formato_es(1234567, 0))
caso("10^12 es 'billones', NUNCA 'trillones'",
     magnitud_es(35_000_000_000_000).startswith("35,00 billones"), magnitud_es(35e12))
caso("no aparece la palabra 'trillon' jamas",
     "trill" not in magnitud_es(35e12).lower(), magnitud_es(35e12))
caso("10^9 se escribe en millones, como la prensa",
     magnitud_es(890e9).startswith("890.000 millones"), magnitud_es(890e9))

print("\n-- la fuente tiene que ser un documento --")
portada = Fuente("f1", "CEPAL", "Panorama Fiscal", "https://www.cepal.org")
caso("rechaza la portada de la institucion", portada.problemas() != [], "la acepto")
hondo = Fuente("f2", "CEPAL", "Panorama Fiscal 2026",
               "https://www.cepal.org/es/publicaciones/panorama-fiscal-2026")
caso("acepta el enlace al documento", hondo.problemas() == [], hondo.problemas())
propia = Fuente("f3", "SurEconomics", "Observatorio", "https://www.sureconomics.com/obs")
caso("rechaza que el medio se cite a si mismo", propia.problemas() != [], "la acepto")

print("\n-- validacion del paquete --")
p = Paquete(hecho="algo paso", fecha_hecho="2026-08-23",
            cifras=[Cifra("x", "1,0", "%", "2026", "NO_EXISTE")],
            fuentes=[hondo])
caso("rechaza cifra cuya fuente no existe", any("no existe" in e for e in p.validar()), p.validar())

p2 = Paquete(hecho="algo paso", fecha_hecho="2026-08-23",
             cifras=[Cifra("y", "1,0", "%", "", "f2")], fuentes=[hondo])
caso("rechaza cifra sin periodo", any("sin periodo" in e for e in p2.validar()), p2.validar())

p3 = Paquete(hecho="", fecha_hecho="", fuentes=[])
caso("rechaza paquete vacio", len(p3.validar()) >= 2, p3.validar())

p4 = Paquete(hecho="ok", fecha_hecho="2026", fuentes=[hondo],
             cifras=[Cifra("a", "1,83 billones de USD", "USD", "2025", "f2", 1832641364775.0),
                     Cifra("b", "1,83 billones de USD", "USD", "2024", "f2", 1830489311088.0)])
caso("avisa cuando dos cifras distintas se ven iguales",
     p4.avisos_de_formato() != [], "no aviso")

print(f"\n{'TODO EN VERDE' if not fallos else str(fallos) + ' FALLO(S)'}")
sys.exit(1 if fallos else 0)
