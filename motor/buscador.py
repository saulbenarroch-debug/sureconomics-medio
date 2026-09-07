"""Buscador (Tavily): encuentra DÓNDE está la nota, no qué dice.

La clave de Tavily lleva meses en el .env —la usa el bot de Telegram— y estuvo
sin aprovechar mientras peleabamos con feeds RSS. Resuelve el problema que el
RSS no puede: encontrar una nota concreta que ningun feed nuestro trae.

DOS REGLAS, Y LA PRIMERA NO SE NEGOCIA

1. **El resumen de Tavily NO se usa jamas.** Su campo `answer` lo escribe una IA
   a partir de los resultados, y en la primera prueba afirmo que Mexico habia
   emitido bonos Samurai en 2026 citando notas de 2019. Usarlo seria meter por
   la puerta de atras justo lo que este sistema existe para impedir.

2. **Busca en toda la web, pero PUNTUA lo que encuentra.** La primera version
   restringia los dominios a la lista blanca y eso dejaba fuera cosas buenas
   -los comunicados de Hacienda de Mexico, por ejemplo- sin filtrar el ruido de
   dentro. El criterio esta en motor/criterio.py, portado del bot de Telegram,
   que lleva meses resolviendo esto: no bloquea a nadie, ordena a todos. Un
   medio reconocido suma puntos, pero uno desconocido puede compensarlos si trae
   cifras, es macro y es reciente.

LO QUE DEVUELVE son candidatos: titular, medio y enlace. A partir de ahi, alguien
tiene que abrir la nota y verificarla —con el navegador o a mano— y registrarla
como fuente. El buscador acorta la busqueda, no sustituye la comprobacion.
"""

import os
import re
import unicodedata
from urllib.parse import urlparse

import requests

from motor import criterio
from motor.fuentes.noticias import MEDIOS

API = "https://api.tavily.com/search"

# Barrido tematico: consultas fijas para descubrir que hay de nuevo cuando nadie
# ha pedido un tema concreto. Vienen de la revision externa del 25/08/2026.
CONSULTAS_PREDETERMINADAS = [
    "inflacion venezuela bcv colombia argentina mexico",
    "banco central tasas interes latam banxico banrep bcra bcv",
    "riesgo pais bonos soberanos deuda latinoamerica embi",
    "pib crecimiento economico exportaciones comercio latam",
    "petroleo pdvsa produccion venezuela exportacion crudo",
    "inversion extranjera directa fusiones adquisiciones latam",
]

# Dominios que no estan en la lista blanca pero son referencia obligada para
# comercio internacional y deuda soberana, que es donde nuestros feeds no llegan.
# Van aqui y no en MEDIOS porque no tienen feed utilizable: solo se buscan.
REFERENCIA = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "eleconomista.com.mx", "lanacion.com.ar", "americaeconomia.com",
    "bnamericas.com", "gob.mx", "dane.gov.co", "banrep.gov.co",
    "banxico.org.mx", "imf.org", "worldbank.org", "cepal.org",
    # Banca y Negocios cubre la economia venezolana con detalle y llega a cosas
    # que los grandes no tocan: entro el 02/09/2026 porque fue el unico medio con
    # las tres licencias de la OFAC sobre mineria, y el motor se nego a escribir
    # esa noticia por no tener fuente en la lista.
    #
    # VA AQUI Y NO EN MEDIOS PORQUE SU RSS ESTA MUERTO: /feed/ y /rss cierran la
    # conexion sin responder. Los ARTICULOS si se leen (13 parrafos, 3.500
    # caracteres, comprobado). Son dos dominios distintos y hay que probar los
    # dos: darlo por bueno por la portada habria metido una fuente que el
    # recolector no puede usar.
    "bancaynegocios.com",
]


# DONDE VIVEN LOS ARTICULOS de los medios cuyo feed esta en otro dominio. No es
# ampliar la lista blanca: estos medios YA estan aprobados, lo que faltaba era
# el dominio donde se leen sus notas. La lista guarda la direccion del RSS y de
# ahi se deducia el dominio, asi que de El Pais solo constaba
# "feeds.elpais.com" y una busqueda restringida no podia encontrar jamas un
# articulo suyo. Se vio el 01/09/2026 con una captura real de El Pais: la
# busqueda devolvio tres paginas de Euronews y ninguna era la noticia.
ARTICULOS_DE = {
    "feeds.bbci.co.uk": "bbc.com",          # BBC Mundo publica en bbc.com
}


def dominios_de(nombre):
    """Los dominios de un medio nombrado a la ligera, o [] si no esta en la lista.

    PARA QUE SIRVE: cuando una captura o un post de Instagram dice de QUE MEDIO
    es, esa es la pista mas fuerte que hay y hasta el 07/09/2026 se tiraba. Una
    captura de Bloomberg Línea sobre Radia Perlman se buscaba por palabras del
    titular en los 45 medios de la lista, no encontraba nada y la corrida
    terminaba con "no encuentro esta noticia en ninguna fuente verificable"
    teniendo el medio delante.

    Se compara SIN espacios ni tildes contra el nombre de la lista, porque quien
    lo escribe es un modelo leyendo un logo: dijo "bloomberglinea" y en la lista
    pone "Bloomberg Línea". Comparar las cadenas tal cual no casa nunca.
    """
    buscado = re.sub(r"[^a-z0-9]", "",
                     unicodedata.normalize("NFKD", str(nombre or "").lower()))
    buscado = "".join(c for c in buscado if not unicodedata.combining(c))
    if len(buscado) < 4:
        return []
    # GANA LA COINCIDENCIA MAS LARGA, que es la mas especifica. Vale la
    # coincidencia por dentro porque la captura puede decir
    # "bloomberglineamercados" o un post firmar "El Nacional Web"; pero sin esta
    # regla, "bloomberglinea" arrastraba tambien a Bloomberg -"bloomberg" cabe
    # dentro-, que es OTRO medio y ademas de pago. Buscar el original en el
    # diario equivocado no es un matiz.
    exactos, parciales = [], []
    for clave, m in MEDIOS.items():
        pelado = re.sub(r"[^a-z0-9]", "", unicodedata.normalize(
            "NFKD", m["nombre"].lower()))
        pelado = "".join(c for c in pelado if not unicodedata.combining(c))
        if pelado == buscado or clave == buscado:
            exactos.append((len(pelado), m["url"]))
        elif pelado in buscado or buscado in pelado:
            parciales.append((len(pelado), m["url"]))

    # LO EXACTO MANDA SOBRE LO PARCIAL. Sin esto, "Bloomberg" a secas caia en
    # Bloomberg Línea, porque "bloomberg" cabe dentro y es la cadena mas larga.
    # Son dos medios distintos y en direcciones contrarias: Bloomberg no se deja
    # leer y Bloomberg Línea si.
    encajes = exactos or parciales
    if not encajes:
        return []
    mejor = max(n for n, _ in encajes)

    fuera = set()
    for n, url in encajes:
        if n != mejor:
            continue
        host = urlparse(url).netloc.replace("www.", "")
        fuera.add(ARTICULOS_DE.get(host, host))
        if host.startswith("feeds."):
            fuera.add(host[len("feeds."):])
    return sorted(fuera)


def dominios_permitidos():
    de_la_lista = set()
    for m in MEDIOS.values():
        host = urlparse(m["url"]).netloc.replace("www.", "")
        de_la_lista.add(host)
        if host in ARTICULOS_DE:
            de_la_lista.add(ARTICULOS_DE[host])
        # Caso general: feeds.elpais.com -> elpais.com. El prefijo "feeds." es
        # del servidor de RSS, no del medio.
        elif host.startswith("feeds."):
            de_la_lista.add(host[len("feeds."):])
    return sorted(de_la_lista | set(REFERENCIA))


def _limpio(s):
    """Quita emojis y caracteres que revientan la consola de Windows."""
    return re.sub(r"[^\x20-\x7e\xc0-\xff]", "", s or "").strip()


# Las dos señales de que una direccion es un indice y no una nota. Van por la
# RUTA y por el TITULAR, porque cada medio marca una cosa: Clarín y El Tiempo no
# ponen /tag/ en la direccion pero titulan «Nombre - Clarín.com» o «Nombre:
# Noticias, Fotos y Videos», y El Estímulo si pone /etiqueta/.
_RUTA_INDICE = re.compile(
    r"/(tag|tags|etiqueta|etiquetas|tema|temas|topic|topics|autor|author|"
    r"seccion|secciones|categoria|category|buscar|search|archivo)(/|$|\?)|"
    # El archivo paginado de una seccion: /venezuela/page/731/
    r"/(page|pagina)/\d+", re.I)
_TITULAR_INDICE = re.compile(
    r"noticias,?\s+fotos\s+y\s+videos|^etiqueta\s*:|^tema\s*:|^tag\s*:|"
    r"ultimas?\s+noticias\s+de|toda\s+la\s+informaci[oó]n\s+sobre|"
    # «Venezuela - Página 731 de 8174 - EL NACIONAL» y «Venezuela Archives»:
    # el archivo de una seccion. Se colo el 03/09/2026 y fue la primera fuente
    # que se leyo, con once parrafos que eran titulares sueltos.
    r"p[aá]gina\s+\d+\s+de\s+\d+|page\s+\d+\s+of\s+\d+|\barchives\b|"
    r"^[^|·\-]{3,40}\s+[-|]\s+[a-z0-9áéíóúñ.]+\.com$", re.I)

# UN PODCAST TAMPOCO ES UNA NOTA. El 03/09/2026, buscando lo que habia dicho
# María Corina Machado, la unica pagina que se dejo leer fue «BBC Audio | Global
# News Podcast»: cinco parrafos de descripcion del episodio. La pieza se escribio
# desde ahi y hablaba del acuerdo petrolero en general, no de lo que ella dijo.
# Una ficha de audio o de video no tiene el texto de la noticia, solo su resumen.
_MEDIO_NO_ESCRITO = re.compile(
    r"^bbc\s+audio\b|\|\s*(podcast|audio|video|en vivo|directo)\b|"
    r"\b(podcast|videos?)\s*\||^escucha\b", re.I)
_RUTA_NO_ESCRITA = re.compile(
    r"/(audio|audios|podcast|podcasts|video|videos|multimedia|galeria|"
    r"en-vivo|directo)(/|$|\?)", re.I)


def _es_indice(titular, url):
    """¿Es la pagina indice de un tema, en vez de una noticia?"""
    ruta = urlparse(url or "").path
    if _RUTA_INDICE.search(ruta) or _RUTA_NO_ESCRITA.search(ruta):
        return True
    if _MEDIO_NO_ESCRITO.search(_limpio(titular)):
        return True
    # Una portada o una raiz de seccion tampoco es una nota: sin ruta no hay
    # articulo que leer.
    if len(ruta.strip("/")) < 3:
        return True
    return bool(_TITULAR_INDICE.search(_limpio(titular)))


def buscar(consulta, dias=30, maximo=10, solo_lista_blanca=False,
           como_noticias=True, ordenar=True, dominios=None):
    """Devuelve candidatos: [{titular, medio, url, fecha, extracto}].

    Lista vacia si no hay clave, si Tavily falla o si no encuentra nada dentro
    de los dominios permitidos. Nunca inventa un resultado.
    """
    clave = os.environ.get("TAVILY_API_KEY", "").strip()
    if not clave:
        print("[aviso] no hay TAVILY_API_KEY: sin buscador")
        return []

    cuerpo = {
        "api_key": clave,
        "query": consulta,
        "search_depth": "advanced",
        # SE PIDE DE SOBRA PORQUE LUEGO SE DESCARTA. Los indices por personaje
        # se llevan los primeros puestos en una busqueda por texto, asi que
        # pidiendo justo 'maximo' se filtraban los seis y quedaban CERO
        # resultados, con articulos de Reuters y BBC esperando en el puesto
        # siete. Se piden tres veces mas y se corta despues de limpiar.
        "max_results": min(maximo * 3, 30),
        "days": dias,
        # include_answer va en False a proposito: ese resumen es de una IA y no
        # se usa en ningun caso. Ver la regla 1 de este modulo.
        "include_answer": False,
    }
    # topic="news" acota a notas y no a paginas sueltas, que es lo que se quiere
    # para DESCUBRIR temas. Pero para BUSCAR UNA NOTICIA CONCRETA hay que
    # apagarlo: el indice de noticias de Tavily no tiene a los medios pequeños.
    # Medido el 02/09/2026 con las licencias de la OFAC sobre mineria: con
    # topic="news" no aparecia en ningun sitio, y sin el salia la primera en
    # bancaynegocios, que fue el unico medio que la dio.
    if como_noticias:
        cuerpo["topic"] = "news"
        cuerpo["search_depth"] = "advanced"
    else:
        # El indice general con "advanced" reordena y criterio.ordenar acababa
        # descartandola igual. En "basic" sobrevive.
        cuerpo["search_depth"] = "basic"
    # 'dominios' acota a UNOS medios concretos y manda sobre la lista entera.
    # Se usa cuando ya se sabe de que diario es la noticia -lo dice la captura o
    # la cuenta que la publico- y entonces buscarla en los otros 44 es ruido.
    if dominios:
        cuerpo["include_domains"] = list(dominios)
    elif solo_lista_blanca:
        cuerpo["include_domains"] = dominios_permitidos()

    try:
        r = requests.post(API, json=cuerpo, timeout=60)
    except Exception as exc:  # noqa: BLE001
        print(f"[aviso] el buscador no respondio: {type(exc).__name__}")
        return []
    if not r.ok:
        print(f"[aviso] Tavily respondio {r.status_code}")
        return []

    salida = []
    for x in r.json().get("results", []):
        # DE UNA PAGINA DE ETIQUETA NO SE PUEDE ESCRIBIR NADA. Buscando "María
        # Corina Machado" el 03/09/2026, los primeros resultados eran «María
        # Corina Machado: Noticias, Fotos y Videos», «María Corina Machado -
        # Clarín.com» y «Etiqueta: María Corina Machado»: los indices que cada
        # medio tiene por personaje, que no cuentan ningun hecho. Se colaban
        # porque son las paginas donde ese nombre aparece mas veces, que es
        # justo lo que premia una busqueda por texto. Ocupaban los primeros
        # puestos y el bot se quedaba sin fuente que leer aunque debajo hubiera
        # articulos de Reuters y BBC sobre ella.
        if _es_indice(x.get("title"), x["url"]):
            continue
        dominio = urlparse(x["url"]).netloc.replace("www.", "")
        medio = next((m["nombre"] for m in MEDIOS.values()
                      if urlparse(m["url"]).netloc.replace("www.", "") == dominio),
                     dominio)
        salida.append({
            "titular": _limpio(x.get("title")),
            "medio": medio,
            "url": x["url"],
            "fecha": (x.get("published_date") or "")[:10],
            "extracto": _limpio(x.get("content"))[:280],
        })
    # Se filtra el ruido y se ordena por puntuacion, no por el orden de Tavily.
    # Con ordenar=False se devuelve tal cual: cuando se busca UNA noticia
    # concreta, quien llama filtra por parecido con el titular, y criterio
    # puntua interes periodistico, que es otra pregunta y descarta aciertos.
    # El recorte va DESPUES de ordenar: si se cortase antes, el orden por
    # criterio periodistico se aplicaria solo a un trozo arbitrario de lo que
    # devolvio el buscador.
    salida = criterio.ordenar(salida) if ordenar else salida
    return salida[:maximo]


def informe(consulta, candidatos):
    """Los candidatos en texto, listos para que un periodista elija."""
    if not candidatos:
        return (f'Sin resultados para "{consulta}" en los medios de confianza.\n'
                f'Puede que el hecho no esté cubierto por ninguno, o que haya que '
                f'aflojar la consulta.')
    lineas = [f'Candidatos para "{consulta}" ({len(candidatos)}):', ""]
    for i, c in enumerate(candidatos, 1):
        lineas.append(f"{i}. [{c['medio']}] {c['fecha'] or 'sin fecha'}"
                      f"  ({c.get('puntos', 0)} puntos)")
        lineas.append(f"   {c['titular'][:78]}")
        lineas.append(f"   {c['url'][:96]}")
        if c["extracto"]:
            lineas.append(f"   «{c['extracto'][:150]}…»")
        lineas.append("")
    lineas.append("Ninguno es fuente todavía: hay que abrir la nota, verificarla y "
                  "registrarla con agregar_fuente.py.")
    return "\n".join(lineas)


def barrido_tematico(dias=3, por_consulta=4):
    """Recorre las consultas fijas y devuelve todo lo que encuentre, ordenado.

    Sirve para el arranque del dia: en vez de esperar a que alguien traiga un
    tema, se pregunta a la web que hay de nuevo en los asuntos que el medio
    cubre siempre. Lo que salga son candidatos, como en cualquier busqueda.
    """
    vistos, todo = set(), []
    for consulta in CONSULTAS_PREDETERMINADAS:
        for c in buscar(consulta, dias=dias, maximo=por_consulta):
            if c["url"] in vistos:
                continue
            vistos.add(c["url"])
            todo.append(c)
    return sorted(todo, key=lambda x: x.get("puntos", 0), reverse=True)
