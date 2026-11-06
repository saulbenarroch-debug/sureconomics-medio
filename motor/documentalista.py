"""El documentalista (A3): arma el expediente antes de escribir.

Es la pieza que faltaba y la que separa un medio de un reescritor de notas
ajenas.

EL PROBLEMA QUE RESUELVE
Hasta ahora la cadena era: una nota de RSS -> un indicador macro -> pieza. El
sistema cogia UNA sola noticia y escribia alrededor de ella, sin preguntarse
nunca "que mas se sabe de esto". Dos fallos graves del 24/08/2026 salieron de
ahi, y en los dos casos la informacion ESTABA en nuestras propias fuentes:

  - Una pieza afirmo que no habia datos macroeconomicos actuales de Venezuela.
    La inflacion de julio (19,9 %, BCV) llevaba 12 dias publicada en El Nacional.
  - Otra dio a entender que no habia respuesta financiera al terremoto. Los
    creditos subsidiados a damnificados llevaban 13 dias en el mismo diario.

No fue falta de cobertura, fue falta de busqueda. Ampliar la lista de fuentes no
lo habria arreglado.

COMO TRABAJA
Del hecho saca de que hay que buscar, barre las 28 fuentes UNA sola vez y filtra
en memoria, y devuelve un expediente de notas relacionadas. Cada una conserva su
medio y su enlace: el expediente no funde fuentes, las acumula.

Y si no encuentra nada, lo dice. Un hecho sin cobertura alrededor tambien es
informacion: puede ser el sitio donde hace falta investigacion propia.
"""

import re

from motor import criterio, ia
from motor.fuentes import noticias

MAX_NOTAS = 6
DIAS = 21


def _terminos(paquete):
    """Le pide al modelo de que hay que buscar. Devuelve lista de patrones."""
    resumen = paquete.citas[0]["texto"] if paquete.citas else ""
    prompt = "\n\n".join([
        "Eres el documentalista de un medio de economía. Antes de que se escriba "
        "la pieza, tu trabajo es reunir todo lo que la prensa ya publicó sobre "
        "este hecho.",
        "=== EL HECHO ===",
        f"{paquete.hecho}\n{resumen}",
        "=== TU TAREA ===",
        "Propón entre 3 y 5 búsquedas para barrer los diarios. Piensa como un "
        "periodista que prepara una cobertura, no como un buscador:",
        "- una por el HECHO mismo (lugar, actor, suceso)",
        "- una por la RESPUESTA: qué se ha hecho, qué medidas, qué anunció el "
        "gobierno, los bancos o el sector",
        "- una por las CIFRAS del asunto (inflación, empleo, producción, precios)",
        "- una por los AFECTADOS o el sector implicado",
        "- una por los ANTECEDENTES si el hecho tiene historia",
        "Cada búsqueda es una expresión regular sencilla en español, con "
        "alternativas separadas por | y sin acentos obligatorios "
        "(usa [ií] donde haga falta). Ejemplo: 'cr[eé]dito|financiamiento|banca'.",
        "=== RESPUESTA ===",
        'Solo este JSON: {"busquedas": [{"patron": "...", "busca": "qué esperas '
        'encontrar"}]}',
    ])
    r = ia.pedir_json(prompt, etiqueta="documentalista", temperatura=0.3)
    if not r:
        return []
    return [b for b in (r.get("busquedas") or []) if b.get("patron")]


# Gentilicios y capitales, para reconocer de que pais habla una nota aunque no
# escriba el nombre del pais. "sismo en Maiquetia" es Venezuela sin decirlo.
PISTAS_PAIS = {
    "Venezuela": r"venezue|caracas|maiquet|la guaira|zulia|maracaibo|bcv|pdvsa|bol[ií]var",
    "Colombia": r"colombi|bogot|medell|barranquilla|banrep",
    "Argentina": r"argentin|buenos aires|porte[ñn]|bcra",
    "Brasil": r"brasil|brasile|s[ãa]o paulo|r[ií]o de janeiro",
    "Chile": r"chile|chilen|santiago de chile",
    "Perú": r"per[uú]|peruan|lima",
    "México": r"m[eé]xic|mexican|cdmx|banxico",
    "España": r"espa[ñn]|madrid|barcelona",
    "El Salvador": r"salvador",
    "Guatemala": r"guatemal",
    "Ecuador": r"ecuador|quito|guayaquil",
    "Bolivia": r"bolivia|la paz|santa cruz de la sierra",
    "Uruguay": r"uruguay|montevideo",
    "Paraguay": r"paraguay|asunci[oó]n",
    "Panamá": r"panam[aá]",
    "Honduras": r"hondur",
    "Nicaragua": r"nicarag",
    "Costa Rica": r"costa rica|costarric",
    "República Dominicana": r"dominican|santo domingo",
    "Cuba": r"cuba|habana",
    "Haití": r"hait[ií]",
}

# Medios sin pais propio para estos efectos: cubren la region o el mundo, asi que
# una nota suya puede hablar de cualquier sitio y no se descarta por origen.
MEDIOS_SIN_PAIS = {"Latam", "Reino Unido", "EE. UU.", "Alemania", "Francia"}


def _pais_del_texto(texto):
    """De que pais habla un texto. Usa la tabla del bot, no la mia.

    La primera version de este modulo tenia su propia lista de gentilicios. La
    del bot detecta ademas por politico, indice bursatil y empresa insignia:
    "Ecopetrol cae en bolsa" es Colombia sin que aparezca la palabra Colombia.
    """
    return criterio.pais_de(texto)


def _pais_objetivo(paquete):
    """El pais de la noticia principal: primero por el texto, luego por el medio.

    None cuando la pieza es REGIONAL. Un paquete que nombra a media docena de
    paises no tiene uno solo del que hable, y elegirle uno hace daño: el ranking
    de PIB de America Latina decia «encabeza Brasil», de ahi se dedujo que la
    pieza era sobre Brasil, y el barrido entero quedo acotado a ese pais. De 400
    notas sobrevivio una: una multinacional japonesa de pañales que se expande
    en Brasil. Acabo de parrafo en una nota sobre el PIB de la region.
    """
    paises_nombrados = {e for e in paquete.entidades if e in PISTAS_PAIS}
    if len(paises_nombrados) >= 3:
        return None

    texto = paquete.hecho + " " + (paquete.citas[0]["texto"] if paquete.citas else "")
    del_texto = _pais_del_texto(texto)
    if del_texto:
        return del_texto
    del_medio = paquete.entidades[1] if len(paquete.entidades) > 1 else None
    return del_medio if del_medio in PISTAS_PAIS else None


def _viene_al_caso(candidata, objetivo, terminos_originales):
    """Decide si una nota del barrido pertenece al expediente.

    Dos filtros, y los dos hicieron falta: sin el de pais, una pieza sobre el
    terremoto de La Guaira arrastraba "Reclamaciones por sismo en San Jose del
    Palmar", que es Colombia. Sin el de solape, entraba "Los empleos del futuro"
    solo por compartir la palabra "empleo".
    """
    texto = candidata.hecho + " " + (candidata.citas[0]["texto"] if candidata.citas else "")

    # Antes que nada, la basura. El expediente de la pieza sobre las sanciones a
    # Cuba se llevo los numeros ganadores del Powerball: hablaba de Estados
    # Unidos, decia "81 millones de dolares" y compartia palabras con la nota.
    # Los dos filtros de abajo lo dejaron pasar porque los dos miran el sentido,
    # y esa nota tenia sentido. Lo que no tenia era nada que ver.
    url = candidata.fuentes[0].url if candidata.fuentes else ""
    if criterio.JUNK.search(texto) or (url and criterio.JUNK_URL.search(url)):
        return False

    if objetivo:
        pais_candidata = _pais_del_texto(texto)
        medio = candidata.entidades[1] if len(candidata.entidades) > 1 else ""
        # Se descarta si habla claramente de OTRO pais. Si no se le detecta pais
        # y ademas viene de un medio regional, se deja pasar: puede ser contexto
        # legitimo (una nota de Bloomberg Linea sobre la region, por ejemplo).
        if pais_candidata and pais_candidata != objetivo:
            return False
        if not pais_candidata and medio not in MEDIOS_SIN_PAIS and medio != objetivo:
            return False

    # Solape de vocabulario con la noticia original: coincidir en una palabra
    # suelta del patron no basta para entrar al expediente.
    palabras = set(re.findall(r"\w{6,}", texto.lower()))
    comunes = palabras & terminos_originales
    if len(comunes) < 2:
        return False
    # Y al menos una de las coincidencias tiene que decir algo. Dos palabras en
    # comun suena a mucho hasta que se ve cuales son: la pieza sobre el ranking
    # de PIB se trajo una nota de Folha sobre una empresa japonesa de pañales
    # porque las dos decian «mundial» y «segun». Coincidir en el vocabulario
    # generico de la economia no es coincidir en el tema.
    return bool(comunes - criterio.PALABRAS_DE_RELLENO)


def _parecidas(a, b):
    """Dos notas son la misma si sus titulares comparten casi todo."""
    pa = set(re.findall(r"\w{5,}", a.lower()))
    pb = set(re.findall(r"\w{5,}", b.lower()))
    if not pa or not pb:
        return False
    return len(pa & pb) / min(len(pa), len(pb)) > 0.7


def armar_expediente(paquete, max_notas=MAX_NOTAS, dias=DIAS):
    """Devuelve (expediente, informe).

    expediente: lista de paquetes de notas relacionadas, sin la original.
    informe:    lo que se buscó y lo que se encontró, para enseñarlo en pantalla.
    """
    busquedas = _terminos(paquete)
    if not busquedas:
        return [], ["el documentalista no respondió: sigo sin expediente"]

    # UNA sola lectura de los feeds. Buscar cinco veces contra la red seria
    # cinco veces mas lento por nada: se filtra en memoria.
    universo = noticias.extraer(None, horas=dias * 24, limite=400)

    objetivo = _pais_objetivo(paquete)
    original = paquete.hecho + " " + (paquete.citas[0]["texto"] if paquete.citas else "")
    terminos_originales = set(re.findall(r"\w{6,}", original.lower()))

    informe = [f"barrido de {len(universo)} notas de los últimos {dias} días"
               + (f", acotado a {objetivo}" if objetivo else
                  " (sin país detectado: no se acota)")]

    expediente, vistos, descartadas = [], [paquete.hecho], 0
    for b in busquedas:
        try:
            patron = re.compile(b["patron"], re.IGNORECASE)
        except re.error:
            informe.append(f"· patrón inválido, lo salto: {b['patron'][:40]}")
            continue

        encontradas = []
        for p in universo:
            texto = p.hecho + " " + (p.citas[0]["texto"] if p.citas else "")
            if not patron.search(texto):
                continue
            if any(_parecidas(p.hecho, v) for v in vistos):
                continue
            if not _viene_al_caso(p, objetivo, terminos_originales):
                descartadas += 1
                continue
            encontradas.append(p)

        # Se prefiere la que trae cifras: para dar fondo vale mas un dato que un
        # titular mas reciente.
        encontradas.sort(key=lambda x: len(x.cifras), reverse=True)
        if encontradas:
            elegida = encontradas[0]
            vistos.append(elegida.hecho)
            expediente.append(elegida)
            informe.append(f"· {b.get('busca', b['patron'])[:52]} -> "
                           f"[{elegida.fuentes[0].institucion}] "
                           f"{elegida.hecho[:48]}")
        else:
            # Un hueco declarado es informacion: quiza ahi falta cobertura y hay
            # una investigacion propia que hacer.
            informe.append(f"· {b.get('busca', b['patron'])[:52]} -> NADA")

        if len(expediente) >= max_notas:
            break

    if descartadas:
        informe.append(f"{descartadas} nota(s) descartadas por país o por no venir "
                       f"al caso")

    if not expediente:
        informe.append("SIN EXPEDIENTE: ninguna fuente cubre este hecho más allá "
                       "de la nota original. Puede ser terreno para investigación "
                       "propia, o señal de que el hecho no da para una pieza.")
    return expediente, informe


# INFORMACIÓN COMPLEMENTARIA DE LA WEB (pedido de Comunicación, 06/11/2026).
#
# El barrido de arriba solo ve los feeds de la lista blanca, y de esos solo la
# sección de economía de los últimos 21 días. Comunicación pidió que cada
# noticia se enriquezca con antecedentes, cifras y comparaciones de fuentes
# confiables (organismos oficiales, bancos centrales, agencias y medios
# económicos), y que eso no salga de la memoria del modelo, que es donde
# aparecen los datos viejos o inventados.
#
# Así que se busca en la web con Tavily, ACOTADO a los dominios de confianza
# (buscador.dominios_permitidos: la lista blanca más REFERENCIA, que trae FMI,
# Banco Mundial, CEPAL y bancos centrales), y lo encontrado entra al paquete
# como cualquier fuente: con su medio, su enlace y sus cifras atribuidas, así
# que el auditor lo comprueba igual que la nota original.
#
# UNA búsqueda por pieza, en modo «basic»: cuesta 1 crédito de Tavily y el plan
# gratuito trae 1.000 al mes. Por eso solo la pide /nota (--web en
# producir.py); las tandas no la usan mientras no haya un plan pagado.
#
# Se usa el TEXTO DE LA PÁGINA (raw_content) y nunca el resumen de Tavily
# (`answer`), que lo escribe una IA: ver la regla 1 de motor/buscador.py.
WEB_MAXIMO = 3
WEB_CARACTERES = 2500


# Los organismos de REFERENCIA no traen nombre (su valor es ""), y el nombre
# importa: el redactor escribe «según el FMI» y la línea «Sacado de» solo
# acredita a quien aparece NOMBRADO en el texto. Con «imf.org» no casaría nunca.
OFICIALES = {
    "imf.org": "FMI", "worldbank.org": "Banco Mundial", "cepal.org": "CEPAL",
    "banxico.org.mx": "Banco de México", "banrep.gov.co": "Banco de la República",
    "dane.gov.co": "DANE", "gob.mx": "Gobierno de México",
}


def _nombre_del_sitio(url):
    from motor import buscador
    dominio = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])

    def es(d):
        return dominio == d or dominio.endswith("." + d)
    for d, n in OFICIALES.items():
        if es(d):
            return n
    for d, n in buscador.REFERENCIA.items():
        if n and es(d):
            return n
    for m in noticias.MEDIOS.values():
        host = re.sub(r"^https?://", "", m["url"]).split("/")[0]
        host = re.sub(r"^(www|feeds)\.", "", buscador.ARTICULOS_DE.get(host, host))
        if es(host):
            return m["nombre"]
    return dominio


def _parrafos(crudo, minimo=90):
    """Los párrafos de verdad de una página en markdown o texto: fuera menús,
    imágenes, tablas, cabeceras y la forma de los enlaces (se queda el texto)."""
    fuera = []
    for p in re.split(r"\n+", crudo or ""):
        p = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", p).strip(" *#>|\t")
        if len(p) > minimo and not re.match(
                r"(Title|URL Source|Published Time|Markdown Content):", p):
            fuera.append(p)
    return re.sub(r"\s+", " ", " ".join(fuera)).strip()


def _leer_pagina(url):
    """Los párrafos de la página, sin IA. El mismo criterio que nota.leer_enlace."""
    import urllib.request
    try:
        pet = urllib.request.Request(url, headers={"User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")})
        with urllib.request.urlopen(pet, timeout=30) as r:
            crudo = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    crudo = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>",
                   " ", crudo)
    trozos = []
    for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", crudo):
        p = re.sub(r"(?s)<[^>]+>", " ", p).replace("&nbsp;", " ").replace("&amp;", "&")
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) > 90:
            trozos.append(p)
    return " ".join(trozos[:12])


def complementar_en_la_web(paquete, maximo=WEB_MAXIMO):
    """Devuelve (paquetes, informe): notas complementarias leídas de la web."""
    import os

    import requests

    from motor import buscador
    from motor.paquete import Fuente, Paquete

    clave = os.environ.get("TAVILY_API_KEY", "").strip()
    if not clave:
        return [], ["sin TAVILY_API_KEY: no busco información complementaria"]
    hecho = re.sub(r"\s+", " ", paquete.hecho or "").strip()[:300]
    if not hecho:
        return [], ["sin hecho que buscar"]
    # Con el titular a secas, la búsqueda devuelve la MISMA noticia contada por
    # otros tres medios. Pidiendo antecedentes y datos, trae contexto: probado
    # el 06/11/2026 con el petróleo y Ormuz, pasó de tres copias de la nota de
    # Goldman Sachs a notas de marzo y a ganadores y perdedores del cierre del
    # estrecho.
    consulta = hecho + ": antecedentes, datos oficiales y comparaciones"
    try:
        r = requests.post(buscador.API, timeout=60, json={
            "api_key": clave,
            "query": consulta,
            "search_depth": "basic",
            "max_results": 10,
            "time_range": "year",
            "include_answer": False,
            "include_raw_content": True,
            "include_domains": buscador.dominios_permitidos(),
        })
    except Exception as exc:  # noqa: BLE001
        return [], [f"la búsqueda web no respondió ({type(exc).__name__})"]
    if not r.ok:
        return [], [f"la búsqueda web respondió {r.status_code}"]

    originales = {f.url.rstrip("/") for f in paquete.fuentes}
    vistos = [paquete.hecho]
    salida, informe = [], []
    for x in r.json().get("results", []):
        url, titulo = x.get("url", ""), buscador._limpio(x.get("title"))
        if not url or url.rstrip("/") in originales or buscador._es_indice(titulo, url):
            continue
        # La misma nota que ya tenemos, contada por otro medio, no complementa:
        # repite. Se buscan antecedentes y contexto, no copias.
        if any(_parecidas(titulo, v) for v in vistos):
            continue
        # El texto, por orden de preferencia: el de la página que trae Tavily,
        # la página leída por nosotros (gratis; en modo «basic» Tavily la
        # devuelve vacía la mitad de las veces) y, si nada, su extracto.
        texto = _parrafos(x.get("raw_content") or "")
        if len(texto) < 300:
            texto = _leer_pagina(url)
        if len(texto) < 300:
            texto = _parrafos(x.get("content") or "", minimo=0)
        if len(texto) < 200:
            continue
        texto = texto[:WEB_CARACTERES]
        medio = _nombre_del_sitio(url)
        m = re.search(r"/(20\d\d)[/-](\d\d)[/-](\d\d)(?:/|-|$)", url)
        fecha = ((x.get("published_date") or "")[:10]
                 or ("%s-%s-%s" % m.groups() if m else ""))
        fid = f"web{len(salida) + 1}"
        salida.append(Paquete(
            hecho=titulo,
            fecha_hecho=fecha,
            cifras=noticias.cifras_del_texto(texto, fid, medio),
            citas=[{"texto": texto, "autor": medio, "fuente_id": fid}],
            entidades=[medio],
            fuentes=[Fuente(id=fid, institucion=medio, documento=titulo, url=url,
                            fecha=fecha)],
            advertencias=[
                f"INFORMACIÓN COMPLEMENTARIA de {medio}"
                + (f", publicada el {fecha}" if fecha else ", sin fecha conocida")
                + f": «{titulo[:90]}». No es el hecho de la noticia: úsala solo "
                f"para antecedentes, cifras o comparaciones, nombra a {medio} en "
                f"el cuerpo y anótala en `complementarios`."
            ],
        ))
        vistos.append(titulo)
        informe.append(f"· [{medio}] {titulo[:70]}")
        if len(salida) >= maximo:
            break
    if not salida:
        informe.append("la web no trajo nada que complemente, más allá de la nota original")
    return salida, informe
