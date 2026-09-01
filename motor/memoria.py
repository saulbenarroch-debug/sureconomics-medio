r"""Que se ha publicado ya, para no volver a contarlo.

    from motor import memoria
    if memoria.ya_cubierto("Datanalisis proyecta un PIB de 10 % para Venezuela"):
        ...

POR QUE EXISTE

El motor no tenia ninguna memoria. El 31/08/2026 llego por el chat una captura
con una noticia que se habia publicado esa misma mañana, y lo detecte yo
comparando a ojo. Eso no escala: con dos tandas al dia mas peticiones sueltas
del equipo, la unica forma de no repetirse es preguntar antes de escribir.

LA FUENTE DE VERDAD ES EL PROPIO SITIO, NO UN ARCHIVO LOCAL. Se consulta la API
publica del panel, que no pide autenticacion. Asi tambien se ve lo que subio una
persona a mano, que un archivo local nunca sabria.

COMO DECIDE SI ES LO MISMO

No compara textos enteros, compara las palabras que llevan el significado. Dos
titulares sobre el mismo hecho comparten los nombres propios y los sustantivos
raros ("Datanalisis", "dolarizacion", "Malvinas") aunque esten redactados
distinto. Las palabras vacias se descartan porque aparecen en todo.

EL UMBRAL SALE DE MEDIRLO, NO DE ELEGIRLO A OJO. Contra titulares reales, los
que ya estaban publicados puntuan entre 0.384 y 1.000, y los que son noticia
nueva entre 0.000 y 0.240. El umbral va en 0.31, en medio del hueco.

La primera medicion dio 0.40 porque el peor duplicado que se habia probado
puntuaba 0.53. Al llegar el titular original de Valora Analitik, que puntua
0.399, se colo por milesimas y el motor iba a reescribir una nota ya publicada.
Un umbral calibrado con pocos casos es un umbral provisional: cada duplicado
nuevo que aparezca hay que meterlo en pruebas_memoria.py y volver a mirar el
hueco, no ajustar el numero a ojo.

Ante la duda, el sesgo va a NO bloquear. Un falso positivo significa no publicar
una noticia que si era nueva, y eso no lo echa nadie de menos porque nadie sabe
que falta. Una repetida, en cambio, se ve enseguida y se borra.
"""

import json
import re
import unicodedata
import urllib.request

API = "https://sureconomics-backend.onrender.com"
AGENTE = "SurEconomics/1.0 (motor editorial)"

# Aparecen en cualquier titular y no distinguen nada.
VACIAS = {
    "para", "como", "desde", "hasta", "entre", "sobre", "esta", "este", "esto",
    "sus", "los", "las", "del", "con", "por", "que", "una", "uno", "unos",
    "mas", "segun", "tras", "ante", "todos", "todas", "cada", "ano", "anos",
    "millones", "mil", "millon", "por ciento", "durante", "primer", "primera",
    "nuevo", "nueva", "gran", "grandes", "tiene", "tras", "sera", "seran",
    "puede", "pueden", "hace", "hacen", "dice", "dicen", "ser", "haber",
}

UMBRAL = 0.31


def _plano(texto):
    t = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _palabras(titular):
    """Las que llevan el significado: cuatro letras o mas, sin las vacias."""
    return {p for p in re.findall(r"[a-z0-9]{4,}", _plano(titular))
            if p not in VACIAS}


def publicadas(limite=60, tiempo_espera=40):
    """Titulos ya publicados en el sitio, del mas reciente al mas antiguo."""
    url = "%s/posts?limit=%d" % (API, limite)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo_espera) as r:
            datos = json.loads(r.read().decode())
    except Exception as exc:  # noqa: BLE001
        # Si el sitio no responde NO se bloquea la corrida: se avisa y se sigue.
        # Quedarse sin publicar por no poder comprobar duplicados seria cambiar
        # un problema pequeño por uno grande.
        print("[aviso] no pude consultar lo ya publicado: %s" % str(exc)[:80])
        return []
    lista = datos.get("data") or datos.get("items") or datos
    if not isinstance(lista, list):
        return []
    return [{"titulo": p.get("title") or "", "slug": p.get("slug") or "",
             "formato": p.get("format") or "", "fecha": p.get("published_at") or ""}
            for p in lista]


def pesos(catalogo):
    """Cuanto distingue cada palabra, medido sobre lo que ya publicamos.

    NO TODAS LAS PALABRAS VALEN LO MISMO, y contarlas por igual fue el primer
    error. Un medio de economia venezolana publica "acuerdo", "petrolero" y
    "Venezuela" en media portada: compartirlas no dice nada. Con ese metodo, la
    nota de los expertos que cuestionan el acuerdo se emparejo con la de
    Gonzalez Urrutia, que es otra noticia distinta del mismo asunto.

    Lo que identifica un hecho son las palabras RARAS: "Datanalisis", "Hanke",
    "cocaina". Aqui se mide exactamente eso: una palabra que aparece en muchos
    titulares publicados pesa poco, y una que aparece en uno o dos pesa mucho.
    """
    import math
    total = max(len(catalogo), 1)
    frecuencia = {}
    for pieza in catalogo:
        for p in _palabras(pieza["titulo"]):
            frecuencia[p] = frecuencia.get(p, 0) + 1
    return {p: math.log(total / (1 + n)) + 0.1 for p, n in frecuencia.items()}


def parecido(a, b, peso=None):
    """De 0 a 1. Cuanto comparten dos titulares de lo que de verdad los define."""
    pa, pb = _palabras(a), _palabras(b)
    if not pa or not pb:
        return 0.0
    # Una palabra que no esta en el catalogo es nueva, o sea muy distintiva.
    w = (lambda p: peso.get(p, 2.0)) if peso else (lambda p: 1.0)
    comun = sum(w(p) for p in pa & pb)
    # Se divide por el MENOR de los dos, no por la union: un titular corto
    # contenido en uno largo es el mismo hecho contado con mas detalle.
    base = min(sum(w(p) for p in pa), sum(w(p) for p in pb))
    return comun / base if base else 0.0


def ya_cubierto(titular, catalogo=None, umbral=UMBRAL, peso=None):
    """Devuelve el titulo ya publicado que coincide, o None."""
    if catalogo is None:
        catalogo = publicadas()
    if peso is None:
        peso = pesos(catalogo)
    mejor, puntos = None, 0.0
    for pieza in catalogo:
        p = parecido(titular, pieza["titulo"], peso)
        if p > puntos:
            mejor, puntos = pieza, p
    return mejor if puntos >= umbral else None


def filtrar(candidatos, clave="hecho", umbral=UMBRAL):
    """Parte una lista de candidatos en (nuevos, repetidos).

    Se consulta el catalogo UNA vez para toda la lista, y los pesos se calculan
    UNA vez: son decenas de candidatos y no hacen falta decenas de llamadas ni
    recorrer el catalogo entero por cada uno.
    """
    catalogo = publicadas()
    peso = pesos(catalogo)
    nuevos, repetidos = [], []
    for c in candidatos:
        titular = c.get(clave, "") if isinstance(c, dict) else str(c)
        ya = ya_cubierto(titular, catalogo, umbral, peso)
        if ya:
            repetidos.append((c, ya))
        else:
            nuevos.append(c)
    return nuevos, repetidos
