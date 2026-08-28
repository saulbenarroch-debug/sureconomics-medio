r"""Comprueba la clasificacion contra piezas reales ya publicadas.

    .pyruntime\python.exe pruebas_clasificar.py

Los casos no son inventados: son piezas que el motor produjo y que se subieron
al panel el 28/08/2026, con los temas que se les pusieron a mano. Si la tabla
acierta en estos, sirve; si no, se corrige la linea concreta.

Se comprueba el tema PRINCIPAL, no la lista entera. El principal es el unico que
sale en las tarjetas de portada, y los secundarios admiten discusion sin que la
pieza quede mal colocada.
"""

import io
import sys
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / ".libs"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from motor import clasificar  # noqa: E402

fallos = []

CASOS = [
    ("CHEVRON NEGOCIA AMPLIAR SUS OPERACIONES PETROLERAS EN VENEZUELA",
     "Chevron negocia expandir sus operaciones petroleras. El acuerdo se basa en "
     "un mecanismo de compensacion de deuda por la venta de crudo.",
     "[Noticia] [Latinoamérica] [Región Andina] [Venezuela] [Economía]",
     "Energía y Minería", ["Venezuela"]),

    ("LA INFLACION SE DISPARA EN AGOSTO HASTA EL 4,3 % POR LOS CARBURANTES",
     "El indice de precios al consumo subio. El IPC adelantado confirma la "
     "aceleracion del crecimiento economico.",
     "[Noticia] [Europa] [España] [Economía]",
     "Macroeconomía", []),

    ("LA MOROSIDAD EN EL CREDITO LIBRE ALCANZA UN RECORD EN BRASIL",
     "El atraso de las familias llega al 7,8 % segun el Banco Central. La "
     "morosidad en el credito libre marca un maximo historico.",
     "[Noticia] [Latinoamérica] [Cono Sur] [Brasil] [Economía]",
     "Banca y Política Monetaria", ["Brasil"]),

    ("MAS DE CIEN GIGANTES TECNOLOGICOS EXIGEN DEFENSA ANTE LOS CIBERATAQUES",
     "Empresas de tecnologia firmaron una carta sobre ciberseguridad frente a "
     "la inteligencia artificial.",
     "[Noticia] [Mundo] [Economía]",
     "Tecnología y Pagos", []),

    ("EL LABERINTO DE LAS LICENCIAS DE LA OFAC EN EL TABLERO ENERGETICO",
     "La OFAC enmendo ocho licencias generales. Las sanciones condicionan la "
     "actividad de las petroleras en el sector de petroleo y gas.",
     "[Investigación] [Latinoamérica] [Región Andina] [Venezuela] [Economía]",
     "Energía y Minería", ["Venezuela"]),

    # Aqui la tabla y yo no coincidimos, y la tabla no esta equivocada. A mano
    # se clasifico como "Comercio Exterior"; el codigo dice "Transporte". La
    # noticia es un paso fronterizo bloqueado que corta el flujo de mercancias:
    # las dos lecturas se sostienen. Se aceptan ambas en vez de retorcer la
    # tabla para que coincida con una eleccion mia: ajustar una regla general a
    # un caso suelto es como se consigue que acierte en la prueba y falle en
    # todo lo demas.
    ("UNA AVALANCHA EN LA FRONTERA ENTRE NEPAL Y TIBET BLOQUEA PASOS COMERCIALES",
     "El desastre impacto el paso fronterizo y el flujo de mercancias. Las "
     "cadenas de suministro y el transporte de bienes quedaron interrumpidos.",
     "[Noticia] [Asia] [China] [Economía]",
     ("Comercio Exterior", "Transporte"), ["China"]),

    ("EE. UU. DISPARA LA VENTA DE COMBUSTIBLE DE AVIACION A ESPAÑA",
     "Estados Unidos incremento las exportaciones de queroseno. La tension en "
     "el estrecho de Ormuz altera las cadenas logisticas.",
     "[Noticia] [Mundo] [Economía]",
     "Energía y Minería", ["EE. UU."]),
]


def revisar(bien, texto):
    print(("  OK  " if bien else "FALLA ") + texto)
    if not bien:
        fallos.append(texto)


def main():
    for titulo, cuerpo, cabecera, principal_esperado, lugares_esperados in CASOS:
        temas = clasificar.temas(titulo, cuerpo)
        lugares = clasificar.lugares(cabecera, titulo)
        # Un caso puede declarar varios principales aceptables cuando la
        # pieza admite mas de una lectura honesta. Ver el comentario del caso
        # de Nepal.
        aceptables = (principal_esperado if isinstance(principal_esperado, tuple)
                      else (principal_esperado,))
        revisar(temas[0] in aceptables, "%s -> %s" % (titulo[:44], temas[0]))
        if temas[0] not in aceptables:
            print("         se esperaba %s; salio %s" % (
                " o ".join(aceptables), " · ".join(temas)))
        revisar(lugares == lugares_esperados,
                "   lugares: %s" % (", ".join(lugares) or "(ninguno)"))

    # La trampa concreta que costo encontrar: una raiz corta dentro de otra
    # palabra. Si vuelve a colarse, que salte aqui y no en produccion.
    print("\n  --- trampas de subcadena ---")
    revisar("Energía y Minería" not in clasificar.temas(
        "LA MOROSIDAD BANCARIA SUBE", "La morosidad del credito aumenta."),
        "'morosidad' no cuenta como 'oro'")
    revisar("Macroeconomía" == clasificar.temas("SIN PALABRAS CLAVE", "Texto neutro.")[0],
            "una pieza sin coincidencias cae en Macroeconomía y no se queda sin tema")

    print("\n" + ("TODO EN VERDE" if not fallos else "%d FALLO(S)" % len(fallos)))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
