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
    # EL CASO LIMITE DE LA CASA, y desde el 10/09/2026 FALLA A PROPOSITO.
    # Es el titular original de Valora Analitik: puntua 0.391 y el umbral esta
    # en 0.40, asi que se cuela y se publicara dos veces. Es el mismo caso que
    # en su dia obligo a bajar el umbral DE 0.40, y se ha vuelto a subir
    # sabiendo que lo reabre: el error que importa cambio de bando. Ver la
    # bitacora del docstring de motor/memoria.py antes de "arreglarlo".
    "Colombia ya exporta más cocaína que petróleo y es el país que pone 70 % de esta droga a nivel mundial",
    "Venezuela reubicará a alumnos de 91 centros afectados por sismos",
    # De la ronda de vigilancia del 01/09: es el mismo hecho que publicamos
    # (Ormuz, el crudo por encima de 90) contado un dia despues y con otra
    # cifra.
    #
    # TAMBIEN FALLA A PROPOSITO desde el 10/09/2026: puntua 0.397 contra un
    # umbral de 0.40. Se aviso en su momento de que subir el umbral tiraria
    # este, y se subio igual con la cuenta hecha. No es una sorpresa.
    "El petróleo sube un 4% y toca los 94 dólares tras los últimos ataques de EEUU a Irán",

    # 09/09/2026, pedida por Edicion desde La Vanguardia. Es la misma historia
    # que "EL PETRÓLEO SUPERA LOS 98 DÓLARES TRAS ATAQUES A PETROLEIROS" con el
    # precio actualizado. Se bloqueo bien; lo que fallaba era que no se le decia
    # a quien la pidio, que es lo que arreglo _avisar_descartadas en nota.py.
    "El barril de crudo Brent supera los 100 dólares por la tensión en Oriente Medio",

    # Estaba en la lista de NUEVOS desde el 02/09 y dejo de serlo: la publicamos
    # como "VENEZUELA, ARGENTINA, ECUADOR Y BOLIVIA COMPARTEN EL PEOR RIESGO
    # PAÍS DE LA REGIÓN". La prueba fallaba por la etiqueta, no por el codigo.
    # Un caso caduca cuando el catalogo cambia: hay que moverlo, no relajar nada.
    "¿Por qué Venezuela, Argentina, Ecuador y Bolivia tienen el peor riesgo país de Latinoamérica? Las razones",
]

# Cosas que NO hemos publicado. Si alguna sale como repetida, la memoria estaria
# tapando noticias nuevas, que es el error caro.
NUEVOS = [
    # ESTOS DOS FALLARON EL 09/09/2026 Y YA NO. Al pasar el catalogo de 60 a
    # 270 piezas dejaron de escaparse duplicados, pero aparecieron choques que
    # antes no existian por pura aritmetica: Chile se emparejaba con "LA FED,
    # BANCO CENTRAL DE EE. UU." (0.388) y Wall Street con "WALL STREET
    # DESENFRENADO Y LA DEUDA..." (0.381). Con el umbral en 0.40 los dos pasan.
    #
    # Se arreglaron subiendo el umbral, y no salio gratis: a cambio se cuelan
    # dos duplicados de verdad, los dos marcados arriba. Fue una decision del
    # dueño con la medicion delante.
    "El Banco Central de Chile recorta la tasa de interés en 25 puntos básicos",
    "Brasil anuncia un nuevo paquete de crédito para la agricultura familiar",
    "El desempleo en Perú cae al 6,2 % en el segundo trimestre",
    "México y Canadá acuerdan revisar el capítulo automotriz del tratado comercial",
    # Este salio de la ronda de vigilancia del 01/09: es del mismo mundo que lo
    # que publicamos (petroleo, mercados) y aun asi tiene que pasar.
    "Wall Street cae y los bonos se desploman ante el temor a una inflación impulsada por el petróleo",
    # EL CASO QUE DESTAPO EL AGUJERO DE LOS TITULARES EN INGLES. Puntuaba 0.369
    # contra nuestra pieza de la venta de combustible de aviacion a España, con
    # la que solo comparte la palabra "iran", y quedaba tapado. Un titular en
    # ingles aporta cuatro palabras utiles: una coincidencia rara se llevaba mas
    # de un tercio del parecido. Si esto vuelve a salir como repetido, alguien
    # quito la regla de las dos palabras en memoria.parecido().
    "U.S.-Iran Strikes Put $100 Oil Back in Focus",
    # EL CASO QUE DESTAPO TODO ESTO, del 09/09/2026. Escrita a peticion
    # de Edicion desde un tuit de Banca y Negocios, se descarto contra "GRUPO
    # GILINSKI Y GEOPARK FIRMAN ACUERDO POR 25 AÑOS...", que es un trato entre
    # dos empresas privadas y no tiene nada que ver con un acuerdo entre dos
    # estados. Compartian cuatro palabras -firman, acuerdo, petrolero,
    # venezuela- y con el catalogo recortado a 60 las tres primeras pesaban el
    # maximo, o sea que el sistema las tomaba por rarisimas. Puntuaba 0.492.
    #
    # Lo que lo arreglo NO fue afinar el parecido, sino mirar las 270 piezas
    # publicadas en vez de 60: con el catalogo entero, "acuerdo" y "petrolero"
    # dejan de parecer palabras raras y el choque baja de 0.492 a 0.000.
    "Delcy Rodríguez: cada taladro activado en el sector petrolero generará 200 puestos de empleo",
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
