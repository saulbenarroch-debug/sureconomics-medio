r"""Elige foto de apertura sin que nadie mire, o no elige ninguna.

    from motor import foto
    elegida = foto.para("EL PETROLEO VENEZOLANO...", ["Venezuela"], "Energía y Minería")

LO QUE ESTE ARCHIVO NO PUEDE HACER, Y HAY QUE SABERLO

No puede comprobar que la foto sea DEL SITIO del que habla la nota. El 26/08/2026
salieron fotos buenisimas de migrantes venezolanos para una pieza sobre Colombia
y eran del cruce entre Ecuador y Colombia. Eso lo ve una persona y no una regla.

Por eso las piezas quedan en BORRADOR y por eso el pie dice siempre "Archivo":
la foto ilustra, no documenta el hecho. Y por eso `para()` prefiere devolver
None antes que una candidata dudosa. Una pieza sin foto se arregla en un minuto;
una pieza con la foto equivocada se arregla despues de que la lea alguien.

LAS REGLAS, Y DE DONDE SALE CADA UNA

1. Autor y licencia declarados. Sin eso no se puede acreditar, y publicar sin
   acreditar una CC BY no es un descuido de estilo: incumple la licencia.
2. Apaisada. El 28/08/2026 subimos una de 1494x2056 y se recortaba mal en
   portada.
3. Al menos 1000 px de ancho. Por debajo se ve blanda en la apertura.
4. Nada de capturas. Ese mismo dia una candidata perfecta del puesto fronterizo
   de Gyirong resulto ser una captura de un video de YouTube de un medio
   estatal: licencia CC BY sobre el papel, procedencia turbia en la practica.
5. Obra propia por delante. Una foto subida por quien la hizo tiene mejor
   trazabilidad que una reproducida de un tercero.
"""

import pathlib
import re
import sys
import unicodedata

AQUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))

ANCHO_MINIMO = 1000

SOSPECHOSAS = re.compile(
    r"screenshot|captura|screen.?shot|thumbnail|logo|poster|cartel|"
    r"portada|diagram|chart|grafico", re.I)

# Palabras del titular que no dicen nada como busqueda de imagen.
VACIAS = {"para", "como", "desde", "hasta", "entre", "sobre", "esta", "este",
          "sus", "los", "las", "del", "con", "por", "que", "una", "uno", "mas",
          "segun", "tras", "ante", "todos", "todas", "cada", "millones", "mil",
          "anos", "ano", "durante", "primer", "segundo", "nuevo", "nueva"}

# Que buscar en ingles segun el tema del sitio. Commons esta catalogado sobre
# todo en ingles: buscar "petroleo Venezuela" devuelve mucho menos que "oil
# refinery Venezuela", y peor.
POR_TEMA = {
    "Energía y Minería": "oil refinery",
    "Agro y Alimentos": "farm harvest field",
    "Transporte": "cargo port ship",
    "Infraestructura": "construction infrastructure",
    "Tecnología y Pagos": "data center servers",
    "Clima y Sostenibilidad": "wind turbines landscape",
    "Trabajo y Migración": "factory workers",
    "Banca y Política Monetaria": "central bank building",
    "Política Fiscal y Deuda": "government finance ministry building",
    "Mercados e Inversión": "stock exchange trading floor",
    "Comercio Exterior": "container port cargo",
    "Geoeconomía": "flags diplomacy building",
    "Empresas y Negocios": "office building corporate",
    "Sociedad y Bienestar": "city street people",
    "Tecnología": "data center servers",
    "Política": "government palace building",
    "Macroeconomía": "city skyline economy",
}

# Como puede aparecer escrito el pais en la ficha de Commons, que mezcla
# ingles y el idioma de quien subio la foto. Se comprueba contra todas.
EN_ESPANOL = {
    "EE. UU.": ["United States", "USA", "Estados Unidos", "U.S."],
    "Brasil": ["Brazil", "Brasil"],
    "México": ["Mexico"],
    "Perú": ["Peru"],
    "Panamá": ["Panama"],
    "República Dominicana": ["Dominican Republic"],
    "Haití": ["Haiti"],
    "China": ["China", "Chinese"],
}

# Palabras del asunto que casan con cualquier cosa. "building" aparece en la
# ficha de medio Commons, incluido el Museu do Ipiranga, que asi se colaba en
# una nota sobre morosidad bancaria en Brasil.
ASUNTO_VACIO = {"building", "city", "economy", "view", "general", "floor",
                "central", "corporate", "office", "trading",
                "people", "street", "landscape", "field"}

# Para comprobar el lugar, no para el panel. Incluye paises que el sitio NO
# tiene dados de alta: la nota de la inflacion española no lleva lugar en la
# ficha, pero su titular dice ESPAÑA, y una vista de Kuala Lumpur encima de ese
# titular sigue diciendole al lector que eso es España.
PAISES_EN_TITULAR = {
    "espana": "Spain", "españa": "Spain", "portugal": "Portugal",
    "francia": "France", "alemania": "Germany", "italia": "Italy",
    "reino unido": "United Kingdom", "japon": "Japan", "india": "India",
    "rusia": "Russia", "nepal": "Nepal", "noruega": "Norway",
    "canada": "Canada", "australia": "Australia", "turquia": "Turkey",
    "iran": "Iran", "israel": "Israel", "egipto": "Egypt",
}

EN_INGLES = {"Venezuela": "Venezuela", "Colombia": "Colombia", "Perú": "Peru",
             "México": "Mexico", "Brasil": "Brazil", "EE. UU.": "United States",
             "Argentina": "Argentina", "Chile": "Chile", "Ecuador": "Ecuador",
             "Bolivia": "Bolivia", "Uruguay": "Uruguay", "Paraguay": "Paraguay",
             "Cuba": "Cuba", "Panamá": "Panama", "China": "China",
             "República Dominicana": "Dominican Republic"}


def _plano(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def sirve(c, pais=None, asunto=None):
    """Un solo sitio donde estan todas las reglas. Devuelve (bool, motivo)."""
    if "no declarado" in c["autor"] or "no declarada" in c["licencia"]:
        return False, "sin autor o licencia declarados"
    # UN SVG NO TIENE MEDIDAS. Es vectorial: se dibuja al tamaño que se le pida
    # y lo que declara es nominal. «Flag of Venezuela.svg» dice 900x600 y se
    # rechazaba por estrecha; el logo de Deutsche Bank dice 150x150 y se
    # rechazaba por vertical siendo cuadrado. Las dos son justo las imagenes que
    # Edicion pidio. Las medidas solo significan algo en un mapa de bits, y ahi
    # las dos reglas siguen enteras: el logo de Barclays, que es un JPEG de 437
    # px, se sigue descartando con razon.
    vectorial = c["titulo"].lower().endswith(".svg")
    if not vectorial:
        if c["ancho"] <= c["alto"]:
            return False, "vertical (%sx%s)" % (c["ancho"], c["alto"])
        if c["ancho"] < ANCHO_MINIMO:
            return False, "estrecha (%s px)" % c["ancho"]

    # SOSPECHOSAS descarta lo que PARECE material grafico colado por una
    # busqueda de texto. Cuando el archivo lo declara Wikidata como la imagen
    # de la entidad no hay nada que adivinar: si pedimos el logo de Nvidia, que
    # el archivo se llame «NVIDIA logo.svg» es la confirmacion, no la sospecha.
    if not c.get("de_wikidata"):
        if (SOSPECHOSAS.search(c["titulo"])
                or SOSPECHOSAS.search(c.get("fuente_declarada", ""))):
            return False, "parece captura o material grafico, no foto"

    # Un grabado del XIX no es una foto de archivo, es otra cosa. La primera
    # corrida ilustro una nota sobre la venta de granos de esta semana con una
    # lamina de la revista Outing de 1885.
    #
    # NO APLICA A BANDERAS NI LOGOS. Commons fecha esos archivos por cuando se
    # ADOPTO el diseño, no por cuando se hizo la imagen: la bandera del Reino
    # Unido consta como de 1801 y se descartaba por antigua. Un simbolo no
    # envejece como una fotografia, y ademas no promete haber presenciado nada,
    # que es lo unico que hacia peligrosa la lamina de 1885.
    if (not c.get("simbolo") and c["anio"].isdigit()
            and int(c["anio"]) < 1980):
        return False, "demasiado antigua (%s), no es fotografia de archivo" % c["anio"]

    # LA REGLA QUE MAS DESCARTA, Y LA MAS NECESARIA. Si la pieza habla de un
    # pais, la foto tiene que decir en alguna parte que es de ese pais. Sin
    # esto, Commons devolvia Melbourne para una nota sobre la inflacion en
    # España y el distrito financiero de Boston para la morosidad en Brasil:
    # imagenes correctas, bien acreditadas, y de otro continente. Un pie que
    # dice "Archivo" no arregla eso; sigue sugiriendo un lugar que no es.
    ficha = _plano(" ".join((c["titulo"], c.get("descripcion", ""),
                             c.get("fuente_declarada", ""))))
    if pais:
        nombres = {_plano(pais)} | {_plano(n) for n in EN_ESPANOL.get(pais, [])}
        if not any(n in ficha for n in nombres):
            return False, "no consta que sea de %s" % pais

    # Y QUE SEA DE LO QUE SE HABLA. Con la regla del pais sola salian imagenes
    # del pais correcto y del asunto equivocado: un autobus para una nota sobre
    # la venta de granos, el Museu do Ipiranga para una sobre morosidad
    # bancaria. Buscar en Commons devuelve lo que sea que comparta una palabra;
    # aqui se exige que la ficha nombre de verdad la cosa que se busca.
    if asunto:
        if not any(_plano(p) in ficha for p in asunto if len(p) > 3):
            return False, "del pais, pero no de %s" % " o ".join(asunto)
    return True, ""


def que_fotografiar(titulo, resumen=""):
    """Que se tiene que ver en la portada, en ingles y en sustantivos.

    COMMONS ESTA INDEXADO EN INGLES y nuestros titulares estan en español, asi
    que sacar palabras del titular no basta: "muere apunalada times" no
    encuentra nada, y "cocaina supera petroleo" tampoco, porque "supera" no se
    fotografia. Hace falta traducir el asunto a un OBJETO.

    Esto es prosa, no una cifra, asi que lo hace el modelo. Si no responde, se
    devuelve vacio y consultas() se apaña con las palabras del titular como
    antes: perder la portada no puede tumbar la pieza.
    """
    from motor.ia import pedir_json

    prompt = (
        "Eres editor grafico de un medio de economia. Te doy el titular de una "
        "noticia en español. Dime QUE OBJETO O LUGAR CONCRETO deberia verse en "
        "la foto de portada, para buscarlo en Wikimedia Commons.\n\n"
        "Reglas:\n"
        "- Responde en INGLES y con SUSTANTIVOS concretos y fotografiables.\n"
        "- Nada de verbos ni de abstracciones ('growth', 'crisis', 'economy').\n"
        "- Si la nota va de una empresa, su sede o su logo. Si va de una "
        "mercancia, LA MERCANCIA MISMA. Si va de un lugar, ese lugar.\n"
        "- No esquives el asunto. Si la noticia es sobre cocaina, la foto es de "
        "cocaina, no de un puerto ni de una bandera. Ilustrar de que trata una "
        "noticia no es aprobar lo que cuenta, y una portada que evita el tema "
        "deja al lector sin saber de que va la pieza.\n"
        # De las personas se ocupa entidad.py, que pregunta a Wikidata cual es
        # su retrato. Aqui NO, y el motivo ya no es que no existan fotos libres
        # de nadie -de un jefe de Estado las hay-, sino que esta via busca por
        # texto: "Delcy Rodriguez" en Commons devuelve tambien a quien estuviera
        # a su lado en el acto. Sin la ficha que confirme de quien es la cara,
        # una foto de persona no se puede publicar.
        "- NUNCA propongas fotografiar a una persona concreta por su nombre. De "
        "las personas se ocupa otro paso, que si puede comprobar de quien es la "
        "cara; esta busqueda no.\n"
        "- Entre dos y cuatro palabras.\n\n"
        'Devuelve solo JSON: {"buscar": ["...", "..."]} con dos propuestas, de '
        "la mas concreta a la mas general.\n\n"
        "Titular: %s\n%s" % (titulo, resumen[:300]))

    r = pedir_json(prompt, etiqueta="foto", temperatura=0.2)
    if not isinstance(r, dict):
        return []
    salida = [str(x).strip() for x in (r.get("buscar") or []) if str(x).strip()]
    return salida[:2]


def consultas(titulo, lugares, tema, describir=None):
    """De la mas concreta a la mas generica. Se prueban en ese orden.

    PRIMERO LO CONCRETO DE LA NOTA, DESPUES LO GENERICO. Instruccion del dueño
    el 01/09/2026: si la pieza habla de una cosa, la imagen es de esa cosa. Si
    la nota va de que Colombia exporta mas cocaina que petroleo, lo que tiene
    que verse es cocaina, no una vista de Bogota. Antes se probaba primero el
    termino generico del tema mas el pais, y de ahi salian portadas correctas y
    completamente mudas: la pieza podia ir de cualquier cosa.

    SIN PAIS NO HAY BUSQUEDA GENERICA. Antes, cuando las dos consultas con pais
    fallaban, se caia a una generica ("city skyline economy") y ahi aparecia
    cualquier ciudad del mundo. Para una pieza sobre un pais concreto, una vista
    generica de otro sitio es peor que ninguna foto: el lector supone que es el
    lugar del que se habla. Si la pieza no tiene lugar, si vale la generica,
    porque entonces no promete ningun sitio.

    Y LO CONCRETO NO EXIME DE MIRAR LA FOTO. Buscando "Times Square" para la
    nota del ataque del 31/08/2026, la segunda candidata era un Lamborghini
    cromado rodeado de turistas. Era del sitio correcto y era inservible. El
    filtro de sirve() no ve lo que sale en la imagen: eso lo mira una persona.
    """
    pais = EN_INGLES.get(lugares[0]) if lugares else ""
    generica = POR_TEMA.get(tema, "economy city")

    plano = _plano(titulo)
    # Tres y no dos: con dos, un titular largo se quedaba en el verbo y el
    # sujeto, que es lo que menos se puede fotografiar.
    palabras = [p for p in re.findall(r"[a-z]{5,}", plano) if p not in VACIAS][:3]

    # Lo que dice el editor grafico va DELANTE de todo: son sustantivos en
    # ingles, que es como esta indexado Commons, y describen que se tiene que
    # ver. Si el modelo no contesto, esta lista viene vacia y sigue todo igual.
    # El termino suelto va primero: una bolsa de cocaina o la torre de un banco
    # se fotografian igual en cualquier sitio, y atarlo al pais deja fuera la
    # unica imagen que dice de que va la nota.
    if pais:
        intentos = [d for x in (describir or []) for d in (x, "%s %s" % (x, pais))]
    else:
        intentos = list(describir or [])

    if not pais:
        intentos += [" ".join(palabras)] if palabras else [generica]
        return intentos
    if palabras:
        intentos.append("%s %s" % (" ".join(palabras), pais))
        # Lo concreto SIN el pais: una bolsa de cocaina o un buque metanero se
        # fotografian igual en cualquier sitio, y atar la busqueda al pais deja
        # fuera la unica imagen que dice de que va la nota. sirve() sigue
        # comprobando que la candidata no prometa un lugar que no es.
        intentos.append(" ".join(palabras))
    intentos.append("%s %s" % (generica, pais))
    intentos.append(pais + " " + tema.split()[0].lower())
    return intentos


def para(titulo, lugares, tema, explicar=False, resumen=""):
    """Devuelve {url, credito, ...} o None. Ver la cabecera del archivo."""
    from buscar_foto import buscar

    # PRIMERO, DE QUIEN O DE QUE HABLA. Preguntarle a Wikidata cual es la imagen
    # de una entidad es otra pregunta que buscar en Commons palabras del
    # titular, y da otra respuesta: "la imagen de Nvidia" es su logo, mientras
    # que "fotos que digan Nvidia" es cualquier placa base. De aqui salen las
    # portadas que Edicion pidio el 03/09/2026: si la nota es de Trump, Trump;
    # si es de Venezuela, la bandera; si es de oro, oro; si es de una marca, su
    # logo. Cuando no hay entidad reconocible se sigue como siempre.
    from motor import entidad
    por_entidad, conocidas = entidad.para(titulo, lugares, resumen, explicar)
    if por_entidad:
        return por_entidad

    # SI SE SABE DE QUIEN HABLA, ES SU IMAGEN O NINGUNA. Cuando Wikidata
    # reconoce la entidad pero no hay foto suya utilizable, buscar por texto es
    # peor que no poner nada: la nota de la salida a bolsa de Shein cayo a la
    # busqueda y eligio un retrato de Ali Mohamed Shein, expresidente de
    # Zanzibar. Una persona real y ajena, de portada, por compartir apellido con
    # una empresa. La busqueda por texto solo puede actuar cuando NO se ha
    # identificado a nadie, que es cuando no hay nada que traicionar.
    if conocidas:
        print("   [foto] se sabe que habla de %s y no hay imagen suya: sin "
              "portada" % ", ".join(conocidas))
        return None

    # Que se tiene que ver, en ingles. Si el modelo no responde, vuelve vacio y
    # la busqueda sigue con las palabras del titular, como antes.
    describir = que_fotografiar(titulo, resumen)
    if describir:
        print("   [foto] buscar: %s" % ", ".join(describir))

    pais = lugares[0] if lugares else None
    if not pais:
        # El titular puede nombrar un pais que la taxonomia del sitio no tiene.
        # Para la foto da igual que no este dado de alta: si el titular dice
        # España, la foto no puede ser de Malasia.
        plano = _plano(titulo)
        for clave, ingles in PAISES_EN_TITULAR.items():
            if _plano(clave) in plano:
                pais = ingles
                break
    # Las palabras del tema son las que tienen que aparecer en la ficha de la
    # foto: si buscamos una refineria, que ponga "refinery" en alguna parte.
    asunto = [p for p in POR_TEMA.get(tema, "").split() if p not in ASUNTO_VACIO]
    descartes = []
    for consulta in consultas(titulo, lugares, tema, describir):
        for c in buscar(consulta, n=8):
            bien, motivo = sirve(c, pais, asunto)
            if bien:
                c["consulta"] = consulta
                c["descartadas"] = descartes
                return c
            descartes.append("%s: %s" % (c["titulo"][:34], motivo))
    if explicar and descartes:
        for d in descartes[:6]:
            print("        descartada %s" % d)
    return None
