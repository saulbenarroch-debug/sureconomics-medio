r"""Comprueba la memoria contra lo que de verdad se publico hoy.

    .pyruntime\python.exe pruebas_memoria.py

Los casos NO son inventados: son los titulares que llegaron por el chat el
31/08/2026, algunos ya publicados y otros no. Si la memoria acierta en estos,
sirve para lo que se construyo.
"""

import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from motor import memoria  # noqa: E402

fallos = []

# Como llegaron por el chat, redactados por otros medios: nunca identicos al
# titulo que acabamos publicando. Ese es justo el caso dificil.
REPETIDOS = [
    "Datanálisis proyecta crecimiento del PIB de entre 9% y 10% en 2026",
    "Colombia ya exporta más cocaína que petróleo: ventas al exterior llegan a US$16.500 millones",
    "Steve Hanke entregó su proyecto de dolarización de Venezuela a la administración Trump",
    "Expertos y abogados, desconcertados por el acuerdo petrolero entre Estados Unidos y Venezuela",
    # Los dos casos limite, los que casi se cuelan. El primero es el titular
    # original de Valora Analitik: puntua 0.399 y con el umbral en 0.40 se
    # escapaba por milesimas, y el motor iba a reescribir una nota publicada.
    "Colombia ya exporta más cocaína que petróleo y es el país que pone 70 % de esta droga a nivel mundial",
    "Venezuela reubicará a alumnos de 91 centros afectados por sismos",
]

# Cosas que NO hemos publicado. Si alguna sale como repetida, la memoria estaria
# tapando noticias nuevas, que es el error caro.
NUEVOS = [
    "El Banco Central de Chile recorta la tasa de interés en 25 puntos básicos",
    "Brasil anuncia un nuevo paquete de crédito para la agricultura familiar",
    "El desempleo en Perú cae al 6,2 % en el segundo trimestre",
    "México y Canadá acuerdan revisar el capítulo automotriz del tratado comercial",
    # Este salio de la ronda de vigilancia del 01/09: es del mismo mundo que lo
    # que publicamos (petroleo, mercados) y aun asi tiene que pasar.
    "Wall Street cae y los bonos se desploman ante el temor a una inflación impulsada por el petróleo",
]


def revisar(bien, texto):
    print(("  OK  " if bien else "FALLA ") + texto)
    if not bien:
        fallos.append(texto)


def main():
    catalogo = memoria.publicadas()
    print("catálogo: %d piezas publicadas\n" % len(catalogo))
    if not catalogo:
        print("Sin catálogo no se puede probar nada. ¿Responde el sitio?")
        return 1

    print("--- deberían salir como YA PUBLICADAS ---")
    for t in REPETIDOS:
        ya = memoria.ya_cubierto(t, catalogo)
        revisar(bool(ya), "%s%s" % (t[:56], "  ->  " + ya["titulo"][:40] if ya else ""))

    print("\n--- deberían salir como NUEVAS ---")
    for t in NUEVOS:
        ya = memoria.ya_cubierto(t, catalogo)
        revisar(not ya, "%s%s" % (t[:56], "  ->  la confundió con: " + ya["titulo"][:34] if ya else ""))

    print("\n--- reparto de una lista mezclada ---")
    mezcla = [{"hecho": t} for t in REPETIDOS + NUEVOS]
    nuevos, repetidos = memoria.filtrar(mezcla)
    revisar(len(nuevos) == len(NUEVOS) and len(repetidos) == len(REPETIDOS),
            "%d nuevas y %d repetidas de %d" % (len(nuevos), len(repetidos), len(mezcla)))

    print("\n" + ("TODO EN VERDE" if not fallos else "%d FALLO(S)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
