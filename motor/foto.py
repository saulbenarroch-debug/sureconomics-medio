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
    if c["ancho"] <= c["alto"]:
        return False, "vertical (%sx%s)" % (c["ancho"], c["alto"])
    if c["ancho"] < ANCHO_MINIMO:
        return False, "estrecha (%s px)" % c["ancho"]
    if SOSPECHOSAS.search(c["titulo"]) or SOSPECHOSAS.search(c.get("fuente_declarada", "")):
        return False, "parece captura o material grafico, no foto"

    # Un grabado del XIX no es una foto de archivo, es otra cosa. La primera
    # corrida ilustro una nota sobre la venta de granos de esta semana con una
    # lamina de la revista Outing de 1885.
    if c["anio"].isdigit() and int(c["anio"]) < 1980:
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


def consultas(titulo, lugares, tema):
    """De la mas concreta a la mas generica. Se prueban en ese orden.

    SIN PAIS NO HAY BUSQUEDA GENERICA. Antes, cuando las dos consultas con pais
    fallaban, se caia a una generica ("city skyline economy") y ahi aparecia
    cualquier ciudad del mundo. Para una pieza sobre un pais concreto, una vista
    generica de otro sitio es peor que ninguna foto: el lector supone que es el
    lugar del que se habla. Si la pieza no tiene lugar, si vale la generica,
    porque entonces no promete ningun sitio.
    """
    pais = EN_INGLES.get(lugares[0]) if lugares else ""
    generica = POR_TEMA.get(tema, "economy city")

    plano = _plano(titulo)
    palabras = [p for p in re.findall(r"[a-z]{5,}", plano) if p not in VACIAS][:2]

    if not pais:
        return [generica]
    intentos = ["%s %s" % (generica, pais)]
    if palabras:
        intentos.append("%s %s" % (" ".join(palabras), pais))
    intentos.append(pais + " " + tema.split()[0].lower())
    return intentos


def para(titulo, lugares, tema, explicar=False):
    """Devuelve {url, credito, ...} o None. Ver la cabecera del archivo."""
    from buscar_foto import buscar

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
    for consulta in consultas(titulo, lugares, tema):
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
