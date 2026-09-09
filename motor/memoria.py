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
que ya estaban publicados puntuan entre 0.375 y 1.000, y el peor falso positivo
puntua 0.340. El umbral va en 0.36, en medio de ese hueco.

HISTORIA DEL NUMERO, QUE ES LA ADVERTENCIA:

  0.40  primera medicion. Se colo el titular de Valora Analitik, que puntua
        0.399, y el motor iba a reescribir una nota publicada.
  0.31  segunda. Aguanto hasta que una nota sobre el riesgo pais de cuatro
        paises se emparejo con un articulo sobre la deuda de Honduras: solo
        compartian "riesgo" y "pais", que en economia son una coletilla.
  0.36  actual. Los duplicados reales puntuan de 0.375 a 1.000 y ese falso
        positivo 0.340.

EL HUECO SE ESTA CERRANDO Y CONVIENE SABERLO. Empezo siendo de 0.144 (0.240 a
0.384) y ahora es de 0.035. No es que el umbral este mal: es que dos titulares
de economia comparten vocabulario, y contar palabras tiene un limite. Cuando el
hueco se cierre del todo habra que cambiar de metodo, no de numero.

  09/09/2026, con el catalogo entero (270 piezas, antes se miraban 60):
  el duplicado mas flojo puntua 0.398 y la noticia nueva mas alta 0.394.
  HUECO: +0.004. Practicamente cerrado.

  Barrido sobre los 16 casos de pruebas_memoria.py:
      0.36 (el de hoy) -> 0 se escapan, 2 bloquea de mas
      0.40             -> 1 se escapa,  0 bloquea de mas

  SE QUEDA EN 0.36 A PROPOSITO, y el motivo cambio el 09/09/2026. Antes aqui
  decia que ante la duda el sesgo iba a NO bloquear, porque un falso positivo
  no lo echaba nadie de menos: la pieza desaparecia en silencio. YA NO
  DESAPARECE. Toda pieza que se de por repetida se avisa al chat con dos
  botones -subirla igual o escribirla otra vez-, asi que bloquear de mas cuesta
  un toque y dejar pasar un duplicado cuesta una noticia repetida en el sitio.
  Con eso, mas vale pasarse que quedarse corto.

  Y NO SE MUEVE POR ESTOS 16 CASOS. La diferencia entre 0.36 y 0.40 es un caso
  en cada direccion: ajustar el numero a una muestra de dieciseis es ajustarlo
  a la muestra. Si algun dia hay cincuenta, se vuelve a medir.

CUIDADO AL TOCAR publicadas(): CUANTO MAS CATALOGO, MAS FALSOS POSITIVOS. Al
pasar de 60 piezas a 270 dejaron de escaparse duplicados -los nueve reales se
detectan- pero aparecieron dos choques que antes no existian: el Banco Central
de Chile con la Fed, y una de Wall Street con otra de Wall Street. Es aritmetica,
no un fallo: mas titulares publicados es mas superficie contra la que chocar. Se
acepta porque las nueve deteciones valen mas que los dos toques.

Cada duplicado nuevo que aparezca va a pruebas_memoria.py y se vuelve a mirar el
hueco. No se ajusta a ojo.

Y HACEN FALTA DOS PALABRAS EN COMUN COMO MINIMO. Una sola no es prueba de nada
por rara que sea: los titulares en ingles aportan cuatro palabras utiles y una
coincidencia como "iran" se llevaba mas de un tercio del parecido. Ver el
comentario de parecido().

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

UMBRAL = 0.36


def _plano(texto):
    t = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _palabras(titular):
    """Las que llevan el significado: cuatro letras o mas, sin las vacias."""
    return {p for p in re.findall(r"[a-z0-9]{4,}", _plano(titular))
            if p not in VACIAS}


def publicadas(limite=None, tiempo_espera=40):
    """Titulos ya publicados en el sitio, del mas reciente al mas antiguo.

    SE TRAE EL CATALOGO ENTERO, PAGINANDO. Esto pedia limit=60 y ahi se quedaba,
    y el 09/09/2026 el sitio tenia 270 piezas: la memoria estaba ciega al 78 %
    de lo que el medio habia publicado. Cualquier cosa de mas de cinco dias
    atras -doce piezas al dia entre las dos tandas- se podia volver a publicar
    sin que nada lo notara.

    La API tope las respuestas en 100 aunque se le pida mas, asi que hay que
    recorrer las paginas; 'meta.pages' dice cuantas hay. 'limite' se conserva
    para poder acotarlo en pruebas.
    """
    fuera, pagina, paginas = [], 1, 1
    while pagina <= paginas:
        url = "%s/posts?limit=100&page=%d" % (API, pagina)
        peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(peticion, timeout=tiempo_espera) as r:
                datos = json.loads(r.read().decode())
        except Exception as exc:  # noqa: BLE001
            # Si el sitio no responde NO se bloquea la corrida: se avisa y se
            # sigue. Quedarse sin publicar por no poder comprobar duplicados
            # seria cambiar un problema pequeño por uno grande. Si ya se habian
            # traido paginas, se trabaja con lo que haya: media memoria es
            # mejor que ninguna.
            print("[aviso] no pude consultar lo ya publicado: %s" % str(exc)[:80])
            break
        lista = datos.get("data") or datos.get("items") or datos
        if not isinstance(lista, list):
            break
        fuera += [{"titulo": p.get("title") or "", "slug": p.get("slug") or "",
                   "formato": p.get("format") or "",
                   "fecha": p.get("published_at") or ""}
                  for p in lista]
        if limite and len(fuera) >= limite:
            return fuera[:limite]
        meta = datos.get("meta") if isinstance(datos, dict) else None
        paginas = (meta or {}).get("pages") or 1
        pagina += 1
    return fuera[:limite] if limite else fuera


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

    # UNA SOLA PALABRA EN COMUN NO ES PRUEBA DE NADA, por rara que sea. Lo
    # descubrio la ronda de vigilancia del 01/09/2026: "U.S.-Iran Strikes Put
    # $100 Oil Back in Focus" puntuo 0.369 contra una pieza nuestra sobre la
    # venta de combustible de aviacion a España, y quedo tapada. Lo unico que
    # compartian era "iran".
    #
    # Le pasa a los titulares en INGLES, que es el agujero: aportan cuatro
    # palabras utiles, comparten una, y como esa palabra es rara pesa mucho y el
    # divisor es el menor de los dos. Cualquier titular corto en ingles que
    # nombre un pais ya cubierto se bloqueaba solo. Y los feeds en ingles son
    # material legitimo para un medio en español.
    comunes = pa & pb
    if len(comunes) < 2:
        return 0.0

    # Una palabra que no esta en el catalogo es nueva, o sea muy distintiva.
    w = (lambda p: peso.get(p, 2.0)) if peso else (lambda p: 1.0)
    comun = sum(w(p) for p in comunes)
    # Se divide por el MENOR de los dos, no por la union: un titular corto
    # contenido en uno largo es el mismo hecho contado con mas detalle.
    base = min(sum(w(p) for p in pa), sum(w(p) for p in pb))
    return comun / base if base else 0.0


def ya_cubierto(titular, catalogo=None, umbral=UMBRAL, peso=None,
                formato=None):
    """Devuelve el titulo ya publicado que coincide, o None.

    'formato' ACOTA LA COMPARACION A LAS PIEZAS DE SU MISMA CLASE, y es lo que
    permite comentar lo que ya se reporto.

    Una columna sobre el acuerdo petrolero no es un duplicado de la noticia que
    dio ese acuerdo: es lo que hace un medio todos los dias. Sin esto, pedir una
    opinion o un analisis sobre cualquier tema de actualidad chocaba siempre con
    la noticia que ya lo habia contado, que es precisamente el tema del que se
    quiere opinar. Paso el 05/09/2026 con la primera columna que se encargo.

    Lo que si sigue bloqueando es una SEGUNDA columna sobre lo mismo, porque
    entonces se compara contra las columnas publicadas. Los pesos se calculan
    con el catalogo entero a proposito: lo que hace raro a un termino es que
    aparezca poco en TODO lo publicado, no dentro de un formato.
    """
    if catalogo is None:
        catalogo = publicadas()
    if peso is None:
        peso = pesos(catalogo)
    if formato:
        catalogo = [c for c in catalogo if c.get("formato") == formato]

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
