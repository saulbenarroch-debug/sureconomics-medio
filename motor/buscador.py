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


def buscar(consulta, dias=30, maximo=10, solo_lista_blanca=False):
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
        "max_results": maximo,
        "days": dias,
        # include_answer va en False a proposito: ese resumen es de una IA y no
        # se usa en ningun caso. Ver la regla 1 de este modulo.
        "include_answer": False,
    }
    # topic="news" es lo que usa el bot: acota a notas, no a paginas sueltas.
    cuerpo["topic"] = "news"
    if solo_lista_blanca:
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
    return criterio.ordenar(salida)


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
